import uvicorn
import jinja2
import traceback
import json
# from typing import Union, List

from fastapi import FastAPI, HTTPException, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
# from fastapi.templating import Jinja2Templates

# from sqlalchemy import create_engine,  Boolean, Column, ForeignKey, Integer, String
# from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session

from starlette.applications import Starlette
from starlette.requests import Request
# from starlette.routing import Route
import starlette.status as status
from starlette_core.messages import message
from starlette_admin import config as admin_config
from starlette_core.templating import Jinja2Templates


# from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
# from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware

from sql_app.database import engine, SessionLocal
from sql_app import crud, models, schemas

# from werkzeug.security import check_password_hash, generate_password_hash

from jinja2 import pass_context

from splitwise import Splitwise
from splitwise.expense import Expense
from splitwise.user import ExpenseUser


# from cmath import nan
# from datetime import datetime
from decimal import *
from tempfile import mkdtemp
import config as Config
import pandas as pd
import numpy as np
# from thefuzz import fuzz
import math
from openpyxl import Workbook
from openpyxl.styles import Font, Border, Side


# import re

from helpers import *
from classes import *
from constants import *

# Create app
app = FastAPI(debug=True)

# Configure database
models.Base.metadata.create_all(bind = engine) # Creates DB if not yet created

# Dependency
def get_db():
    """ Opens a session and makes sure it's closed at the end"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Configure templating
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="static/templates")


"""       ----------           PATHS       -----------            """

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    """Return home page """
    return templates.TemplateResponse("home.html", {"request": request})


"""       ----------           Authentication       -----------            """

@app.get("/login_sw")
def login_sw(request: Request):
    sObj = Splitwise(Config.consumer_key, Config.consumer_secret) #Special object for authentication in Splitwise
    url, secret = sObj.getAuthorizeURL() # Method in sObj 'getAuthorizeURL()' returns the URL for authorizing the app
    
    request.session['secret'] = secret 
    
    return RedirectResponse(url) #Redirect user to SW authorization website. After login, redirects user to the URL defined in the app's settings

@app.get("/authorize", response_class = HTMLResponse)
def authorize(request: Request, oauth_token: str, oauth_verifier: str):
    # Get parameters needed to obtain the access token
    sObj = Splitwise(Config.consumer_key,Config.consumer_secret)
    
    user_secret = request.session['secret']
    
    access_token = sObj.getAccessToken(oauth_token, user_secret, oauth_verifier)
    sObj.setAccessToken(access_token)
    # Store user data and tokens in session
    request.session['access_token'] = access_token
    current_user = sObj.getCurrentUser()
    request.session['user_id'] = current_user.id
    request.session['user_fname'] = current_user.first_name
    return templates.TemplateResponse("authorize_success.html", {"request": request})

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")


"""       ----------           Retrieve data       -----------            """

@app.get('/batch_upload', response_class = HTMLResponse)
def batch_upload_show_form(request: Request):
    sObj = get_access_token(request)
    groups = sObj.getGroups()
    return templates.TemplateResponse("batch_upload.html", {"request": request, "groups" : groups})


@app.post("/batch_upload_post", response_class = HTMLResponse)
def batch_upload_process(request: Request, group_for_upload = Form(), batch_expenses_file : UploadFile = File(...)):
    sObj = get_access_token(request)
    app_current_user = sObj.getCurrentUser()
    # Fetch group info
    group = sObj.getGroup(group_for_upload)
    group_dict = {
        'id' : group.id, 
        'name' : group.getName(), 
        'members' :  group.getMembers()
    }
    
    # Import and parse user file 
    file = batch_expenses_file.file.read()
    
    expenses_df = pd.read_excel(file, sheet_name = "Expenses")
    cols_member_names = list(expenses_df.filter(regex='^_', axis=1))
    expenses_df['Total Shares'] = expenses_df[cols_member_names].sum(axis = 1)
    # expenses_df['Date'] = pd.to_datetime(expenses_df['Date']).dt.date
    members_df = pd.read_excel(file, sheet_name = "Members")
    
    members_in_cols = []
    for member in expenses_df[cols_member_names].columns:
        members_in_cols.append(
            {
                'name' : member[1:] ,
                'id' :  members_df[members_df['Name'] == member[1:]]['ID'].values[0] # Search for name and return ID
            })

    # Calculate share owed and paid by each member
    def get_share_owed(df, member_name):
        """ Calculate share paid and owed by expense and user"""
        # Share owed, depends on the type of split
        if df['All equal'] == "y": # Default: Split equally among all group members
            return df['Amount'] / len(group.members)
        else:
            if df["Split type"] == "share":
                return round((df[member_name]/100)*df['Amount'], 2) # e.g. share = 10 --> 0.1*amount
            elif df["Split type"] == "amount":
                return df[member_name] # e.g. share_owed for Javier is the value under column "_Javier"
            elif df["Split type"] == "equal":
                members_to_split = df[cols_member_names].count()
                return round(df['Amount'] / members_to_split) # Get value from cell under the person's column
        
    for col_name in cols_member_names:
        # Share paid
        expenses_df[f'{col_name[1:]}_share_paid'] = np.where(expenses_df["Paid by"] == col_name[1:],  expenses_df['Amount'], 0)

        # Share owed
        expenses_df[f'{col_name[1:]}_share_owed'] = expenses_df.apply(get_share_owed, axis = 1, member_name = f"_{col_name[1:]}")

    # Obtain error message
    errors, error_messages, error_count = describe_errors(expenses_df, members_df, group)

    # Prepare context to be passed to template
    request.session['expenses_to_upload'] = expenses_df.to_json(orient = 'records')
    
    context = {
        "request" : request,
        "group" : group_to_dict(group), 
        "members_in_cols" : members_in_cols, 
        "expenses" : expenses_df.to_dict('records'),
        "errors" : errors,
        "error_messages" : error_messages,
    }
    

    # Return a table with expenses
    if error_count == 0:
        context['file_valid'] = 'yes'
        return templates.TemplateResponse("upload_edit.html", context)
    else:
        context['file_valid'] = 'no'
        return templates.TemplateResponse("upload_edit.html", context)

"""       ----------           Retrieve data       -----------            """

@app.get("/groups", response_class=HTMLResponse)
def get_groups_by_id(request: Request):
    """Get groups of the current user logged in the app, using it's app user ID"""
    sObj = get_access_token(request)
    groups = sObj.getGroups()
    return templates.TemplateResponse("groups.html", {"request": request, "groups" : groups})

@app.get("/template/{group_id}")
def get_template_by_group_id(request: Request, group_id: int):
    """Create a template excel for a group"""
    sObj = get_access_token(request)
    group = sObj.getGroup(group_id)
    members = group.members
    
    # Define headers    
    expense_headers = ["ID","Description","Date","Amount","Currency","Paid by","All equal","Split type"]
    members_headers = ["Name", "ID"]
    
    # List of member names
    member_names = []
    for member in members:
        member_last_name = "" if member.last_name == None else member.last_name
        member_full_name = f"{member.first_name} {member_last_name}".strip()
        member_names.append(member_full_name)

    # For repeated names, enumerate them 1-N (e.g. Javier 1, Javier 2...)
    member_names_enum = []
    for i, name in enumerate(member_names): 
        count = member_names.count(name)
        if count > 1:
            member_names_enum.append(name + " " + str(member_names[0:i + 1].count(name)))
        else:
            member_names_enum.append(name)

    # Append to headers
    expense_headers += [f"_{name}" for name in member_names_enum] # add prefix "_"
    
    # Create and configure excel file
    wb = Workbook()
    expenses_ws = wb.active
    expenses_ws.title = "Expenses"
    expenses_ws.sheet_properties.tabColor = "00cc00"

    members_ws = wb.create_sheet(title="Members")
    members_ws.sheet_properties.tabColor = "009933"

    # Create headers
    for sheet_headers, sheet in zip([expense_headers, members_headers], [expenses_ws, members_ws]):
        for c, header in enumerate(sheet_headers, start=1):
            cell = sheet.cell(row=1, column=c)
            cell.value = header
            cell.font = Font(bold=True)
            cell.border = Border(bottom=Side(style='thick', color="000000"))

    # Add member data in 'members' sheet
    for r, (member, member_name) in enumerate(zip(members, member_names_enum), start = 2):
        members_ws.cell(row = r, column = 1, value = member_name)
        members_ws.cell(row = r, column = 2, value = member.id)

    #Save and return file
    file_path = f"static/assets/group_templates/{group_id}.xlsx"
    wb.save(file_path)

    headers = {'Content-Disposition': f'attachment; filename="template-{group.name}.xlsx"'}
    return FileResponse(file_path, headers=headers, media_type = "application/vnd.ms-excel")


"""       ----------           User registration       -----------            """
"""Register user in database"""

@app.get("/register/", response_class = HTMLResponse)
def register_show_form(request: Request):
    """ Show user a page for registering"""
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register_submit/")
def register(request: Request, username: str = Form(), password: str = Form(), confirmation: str = Form(), db: Session = Depends(get_db)):
    """ Register user using data in their registration form"""
    # Obtain user's data entered in the form
    # username = request.get("username")
    # password = request.get("password")
    # confirmation = request.get("confirmation")
    
    if password != confirmation:
        return apology("You didn't write the same pass twice, didn't you?", request, 400)
    # Check if the username is being used
    db_user_byusername = crud.get_user_by_username(db, username=username)
    if db_user_byusername:
        return apology("That username is taken...", request, 400)

    # Validate data
    elif username=="" or password=="" or confirmation=="":
        # If at least one of the above are missing
        return apology("You didn't complete all the fields, right?", request, 400)
    elif password != confirmation :
        return apology("Passwords don't match bro", request, 400)

    # Create user in database
    try:
        new_user = schemas.UserCreate(username = username, password = password)
        crud.create_user(db, new_user)
        new_db_user = crud.get_user_by_username(db, username)
        request.session['user_id'] = new_db_user.id # Store the user id in session 
        request.session['username'] = new_db_user.username # Store the user id in session 
    except:
        return apology("Could not insert you in the database", request, 400)

    # Redirect to home
    return RedirectResponse('/', status_code=status.HTTP_302_FOUND) # See https://stackoverflow.com/a/65512571/19667698


@app.get("user/{username}")
def get_user_byusername(username: int, db: Session = Depends(get_db)):
    user = crud.get_user_by_username(db, username = username).first()
    return user

""" Create users and groups in database"""
# Create a new user (Registration) """
@app.post("/users/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Create a user"""
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user: #If db_user exists (i.e. the search by email return something)
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db=db, user=user)

#Add middleware
app.add_middleware(SessionMiddleware, secret_key="some-random-string") # https://github.com/tiangolo/fastapi/issues/4746#issuecomment-1133866839

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)