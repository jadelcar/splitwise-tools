import os
import requests
import urllib.parse
import pandas as pd

from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from starlette.middleware.sessions import SessionMiddleware

# Configure templating
templates = Jinja2Templates(directory="static/templates")

from functools import wraps
from splitwise import Splitwise
from splitwise.group import Group
import config as Config

from constants import *


def get_access_token(request: Request):
    """ Obtain Splitwise object (only if there is an access token """
    # try:
    sObj = Splitwise(Config.consumer_key,Config.consumer_secret)
    # except:
    # raise Exception("Could not obtain the Splitwise object, consumer key/secret has expired")
    # try:
    sObj.setAccessToken(request.session['access_token'])
    return sObj
    # except:
    # raise Exception("Could not set access token. Maybe the user has not authorized Splitwise or the session has expired")
        

def apology(message, request, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return templates.TemplateResponse("apology.html", {"request": request, "top" : code, "bottom" : escape(message)}, status_code=code)


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"


"""
Verification of file

error_master is a dict of dicts. Each dict refers to one type of error (description too long, date format, wrong group member etc.) and contains:
    'message': Displayed to user
    'element_type': Type of element affected (expense, member etc.)
    'error_list': List of elements affected

As we identify errors, we populate the dicts with function 'add_error' and build the error message progressively with function 'add_to_error_msg'.
"""


def describe_errors(expenses_df: pd.DataFrame, members_df: pd.DataFrame, group_members: list):
    """ Describe all errors in the file"""
    
    def add_to_error_list(error_type : str, element_id : int):
        """ Add an element to error list, indicating error type and element ID """
        errors[error_type]['error_list'].append(str(element_id))
        return element_id
    
    def new_error_msg(error_type : str, error_master : dict):
        """ Adds error type (error description + list of items) to the overall error_message"""
        error_dict = error_master[error_type]
        if error_dict['element_type'] == 'general':
            message = error_dict['message']+ ".\n"
        else:
            error_list_str = ', '.join(error_dict['error_list'])
            message = error_dict['message'] + " (" + error_dict['element_type'] + " " + error_list_str + ").\n"
        return message

    # Initialize error list for each type of error
    # For each error type, add to dict list of items ('error_list') affected by this error
    # To edit error types and descriptions, go to constants.py
    errors = ERROR_MASTER.copy()
    for descr in ERROR_MASTER.keys(): 
        errors[str(descr)]['error_list'] = [] 
    
    # Error 1: Friend names don't match in the two sheets
    for member_name in expenses_df.filter(regex='^_', axis=1):
        if member_name not in members_df['Name']:
            add_to_error_list(error_type = "group_member", element_id = member_name)

    # Error 2: Number of friends in file is different than total group members
    if len(members_df['Name']) != len(group_members) : add_to_error_list("n_members", 1, errors)

    # Error 3: Description length > max 
    for id, descr in zip(expenses_df["ID"], expenses_df["Description"]):
        if len(descr) > EXP_DESCR_MAX_CHARS: 
            add_to_error_list("descr", id, errors)

    # Error 4: Shares do not add up
    cols_to_add = [col_name for col_name in expenses_df.filter(regex='^_', axis=1)] # List of column names we want to add up to calculate shares

    # Add column with the sum of shares and compare with total amount
    for i, row in expenses_df.iterrows():
        if row['Split type'] == "amount" and total_shares != amount : 
            add_to_error_list("shares_no_addup", id, errors)
        elif type_split == "shares" and total_shares != 100 : 
            add_to_error_list("shares_no_addup", id, errors)
    for id, type_split, amount, total_shares in zip(expenses_df["ID"], expenses_df["Split type"], expenses_df["Amount"], expenses_df["Total Shares"]):
        if type_split == "amount" and total_shares != amount : 
            add_to_error_list("shares_no_addup", id, errors)
        elif type_split == "shares" and total_shares != 100 : 
            add_to_error_list("shares_no_addup", id, errors)
    
    # Error 5: Split type not supported
    for id, type_split, all_equal in zip(expenses_df['ID'], expenses_df['Split type'], expenses_df['All equal']):
        if type_split not in SPLIT_TYPES and all_equal != 'y': 
            add_to_error_list("split_type_unsupported", id, errors)

    # Date cannot be parsed (TBD)
    # for date in df.date:
    #     if is_date(date) == TRUE:

    # Build the error message, looping over the different errors
    error_message = ""
    for type in errors.keys():
        if len(errors[type]['error_list']) > 0 : error_message += new_error_msg(type, errors)
    
    # Get the total sum of errors
    error_count = 0
    for type in errors.values():
        error_count += len(type['error_list'])
    
    # Return
    return error_message, error_count




