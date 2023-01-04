import uvicorn
# import jinja2
# import traceback
import json
import random
# from typing import Union, List

from fastapi import FastAPI, HTTPException, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.requests import Request

# from sqlalchemy import create_engine,  Boolean, Column, ForeignKey, Integer, String
# from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker, relationship

from starlette.applications import Starlette
import starlette.status as status
from starlette_core.messages import message
from starlette_core.templating import Jinja2Templates
# from starlette.routing import Route
# from starlette_admin import config as admin_config


# from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
# from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware

from sql_app.database import engine, SessionLocal
from sql_app import crud, models, schemas

# from werkzeug.security import check_password_hash, generate_password_hash

# from jinja2 import pass_context

from splitwise import Splitwise
from splitwise.expense import Expense
from splitwise.user import ExpenseUser


from decimal import *
from tempfile import mkdtemp
import config as Config
import pandas as pd
import numpy as np
from openpyxl import Workbook
from openpyxl.styles import Font, Border, Side

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


@app.post("/batch_upload_process", response_class = HTMLResponse)
def batch_upload_process(request: Request, group_for_upload = Form(), batch_expenses_file : UploadFile = File(...)):
    sObj = get_access_token(request)
    app_current_user = sObj.getCurrentUser()
    # Fetch group info
    group = sObj.getGroup(group_for_upload)
    
    # Import and parse user file 
    file = batch_expenses_file.file.read()
    
    expenses_df = pd.read_excel(file, sheet_name = "Expenses")
    cols_member_names = list(expenses_df.filter(regex='^_', axis=1))
    expenses_df['Total Shares'] = expenses_df[cols_member_names].sum(axis = 1)
    members_df = pd.read_excel(file, sheet_name = "Members")
    
    # List with members entered in columns with their respective ID
    members_in_cols = []
    for member in expenses_df[cols_member_names].columns:
        members_in_cols.append(
            {
                'name' : member[1:] ,
                'id' :  int(members_df[members_df['Name'] == member[1:]]['ID'].values[0]) # Search in column'Name' of members_df and return the column 'ID'
            })

    # Calculate share owed and paid for a given member
    def get_share_owed(row, member_name):
        """ Calculate share owed for a given expense (row) and user"""
        if row['All equal'] == "y": # Default: Split equally among all group members
            return row['Amount'] / len(group.members)
        elif pd.isna(row[member_name]):
            return 0
        else:
            if row["Split type"] == "share":
                return round((row[member_name]/100)*row['Amount'], 2) # e.g. share = 10 --> 0.1*amount
            elif row["Split type"] == "amount":
                return row[member_name] # e.g. share_owed for Javier is the value under column "_Javier"
            elif row["Split type"] == "equal":
                members_to_split = row[cols_member_names].count() # Count members participating in this expense
                return round(row['Amount'] / members_to_split, 2)
        
    for col_name in cols_member_names:
        # Share paid
        expenses_df[f'{col_name[1:]}_share_paid'] = np.where(expenses_df["Paid by"] == col_name[1:],  expenses_df['Amount'], 0)

        # Share owed
        expenses_df[f'{col_name[1:]}_share_owed'] = expenses_df.apply(get_share_owed, axis = 1, member_name = f"_{col_name[1:]}")

    # Round share owed if it doesn't add up
    def assign_rounding_diff(row):
        """Assign the rounding difference to a random member within the expense
        Add up share_owed of all members and compare with total amount: If the difference is due to rounding (<0.02), add/substract this from a random user within the expense
        """
        share_owed_columns = [f"{col_name[1:]}_share_owed" for col_name in cols_member_names if row[f"{col_name[1:]}_share_owed"] > 0] # Members in this expense
        sum_share_owed = row[share_owed_columns].sum()
        diff = sum_share_owed - row['Amount']
        if abs(diff) > 0 and abs(diff) < 0.02:
            random_member = random.choice(share_owed_columns)
            row[random_member] += -diff # Substract the difference
        return row

    expenses_df = expenses_df.apply(assign_rounding_diff, axis = 1)

    # Obtain error message
    errors, error_messages, error_count = describe_errors(expenses_df, members_df, group)

    # Store data temporarily so it can be pushed later
    if error_count == 0:
        app.state.temp_expenses_to_push = {
            'expenses' : expenses_df.to_dict('records'),
            'group' : group,
            'members_in_cols' : members_in_cols,
        }

    
    # Prepare context to be passed to template
    context = {
        "request" : request,
        "group" : group_to_dict(group), 
        "members_in_cols" : members_in_cols, 
        "expenses" : expenses_df.to_dict('records'),
        "errors" : errors,
        "error_messages" : error_messages,
        "file_valid" : error_count == 0,
    }

    return templates.TemplateResponse("upload_edit.html", context)

@app.post('/push_expenses', response_class = HTMLResponse)
def push_expenses(request: Request):
    #Another option: Parse the data received as JSON in the Splitwise format needed (https://flask.palletsprojects.com/en/2.2.x/api/#flask.Request.get_json), also see the property 'JSON'
    sObj = get_access_token(request)

    # The data to upload was stored in app.state
    try:
        data_to_push = app.state._state.pop('temp_expenses_to_push')
    except:
        apology("You probably went back and tried again? Sorry, please upload the file again", request)
    expenses = data_to_push['expenses']
    group = data_to_push['group']
    members_in_cols = data_to_push['members_in_cols']

    # Upload each expense to Splitwise
    expenses_to_push = {}
    for e in expenses:
        expense = Expense()
        expense.setCost(e['Amount'])
        expense.setDescription(e['Description'])
        expense.setGroupId(group.id)
        expense.setCreationMethod('Splitwise tools')
        expense.setDate(e['Date'])
        expense.setCurrencyCode(e['Currency'])
        if e['All equal'] == "y" and str.lower(e['Paid by']) == 'you': 
            expense.setSplitEqually() # Default is 'should_split = True'
            pass
        else:
            for member in members_in_cols:
                share_paid = e[f"{member['name']}_share_paid"] #e.g. Javier_share_paid
                share_owed = e[f"{member['name']}_share_owed"]

                if (share_paid + share_owed) > 0: # if any of share_owed or share_paid  is > 0, the user is a member of this expense 
                    user = ExpenseUser()
                    user.setId(member['id'])
                    user.setPaidShare(e[f"{member['name']}_share_paid"]) 
                    user.setOwedShare(e[f"{member['name']}_share_owed"])
                    expense.addUser(user)
        expenses_to_push[e['ID']] = expense # Add to dictionary, using 'Id' (specified by user) as key
    
    # Upload expenses
    expenses_failed = []
    for expense_id, expense in expenses_to_push.items():
        nExpense, errors = sObj.createExpense(expense)
        if nExpense is not None: 
            print("Expense ID in Splitwise: " + str(nExpense.getId()))
        else:
            errors_list = errors.getErrors()['base']
            print(f"Expense errors: {errors_list}")
            expenses_failed.append(
                {
                    'id': str(expense_id),
                    'errors' : errors_list
                }
            )

    context = {
        "request": request,
        "group" : group_to_dict(group),
        "expenses_failed" : expenses_failed,
    }

    # Return summary
    return templates.TemplateResponse("upload_summary.html", context)


"""       ----------           Retrieve data       -----------            """

@app.get("/groups", response_class=HTMLResponse)
def get_groups_by_id(request: Request):
    """Get groups of the current user logged in the app, using it's app user ID"""
    sObj = get_access_token(request)
    groups = sObj.getGroups()
    return templates.TemplateResponse("groups.html", {"request": request, "groups" : groups})

@app.get("/reset_group", response_class = HTMLResponse):
def reset_group(request: Request):
    sObj = get_access_token(request)
    groups = sObj.getGroups()
    return templates.TemplateResponse("reset_group.html", {"request": request, "groups" : groups})

@app.post("/delete_expenses/{group_id}"):



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
app.add_middleware(SessionMiddleware, secret_key="some-random-string", same_site = 'None') # https://github.com/tiangolo/fastapi/issues/4746#issuecomment-1133866839

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, reload_dirs=["sql_app",""])