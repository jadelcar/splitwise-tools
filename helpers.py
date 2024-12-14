import pandas as pd

from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from typing import Tuple

# Configure templating
templates = Jinja2Templates(directory="static/templates")

from splitwise import Splitwise
from splitwise.group import Group
from config.settings import get_settings
from constants import *


settings = get_settings()
URL = f"http://{settings.APP_HOST}:{settings.APP_PORT}"
CONSUMER_KEY = settings.CONSUMER_KEY
CONSUMER_SECRET = settings.CONSUMER_SECRET



def get_access_token(request: Request):
    """ Obtain Splitwise object (only if there is an access token """
    # try:
    sObj = Splitwise(CONSUMER_KEY, CONSUMER_SECRET)
    # except:
    # raise Exception("Could not obtain the Splitwise object, consumer key/secret has expired")
    # try:
    sObj.setOAuth2AccessToken(request.session.get('access_token'))
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

def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"

def group_to_dict(group: Group):
    """Returns a group converted to dict, with elements ID, Name and Members (list of tuples)"""
    return {
        "id": group.id,
        "name": group.name,
        "members" : [(member.id, member.first_name, member.last_name) for member in group.members]
    }

def describe_errors(expenses_df: pd.DataFrame, members_df: pd.DataFrame, group: Group) -> Tuple[dict,  list, int]:
    """ Describe all errors in the excel file. Returns

    We create `error_master`, a dict of dicts. Each dict refers to one type of error (description too long, date format, wrong group member etc.) and contains:
        `message`: Displayed to user
        `element_type`: Type of element affected (expense, member etc.)
        `error_list`: List of elements affected

    Example:

    error_master = {
        'descr' : {
            "message" : f"Expense description is longer than 50 characters" ,
            "element_type" : "expense(s)" 
            "error_list" : [1, 7, 9]
            } ,
        (...)
    }

    As we identify errors, we populate the dicts with function 'add_error' and build the error message progressively with function 'add_to_error_msg'.
    
    To edit error types and descriptions, go to constants.py
    """
    def add_to_error_list(error_type : str, element_id : int):
        """ Add an element to error list, indicating error type and element ID """
        errors[error_type]['error_list'].append(str(element_id))
        return element_id
    
    def new_error_msg(error_type : str, error_master : dict):
        """ Adds error type (error description + list of items) to the overall error_message"""
        error_dict = error_master[error_type]
        if error_dict['element_type'] == 'general':
            message = error_dict['message']+ "."
        else:
            error_list_str = ', '.join(error_dict['error_list'])
            message = error_dict['message'] + " (" + error_dict['element_type'] + " " + error_list_str + ")."
        return message

    # Initialize error list for each type of error
    # For each error type, add to dict list of items ('error_list') affected by this error
    errors = ERROR_MASTER.copy()
    for descr in ERROR_MASTER.keys(): 
        errors[str(descr)]['error_list'] = [] 
    
    # File-level errors
    # Error 1: Friend names don't match in the two sheets
    list_expenses = [m[1:] for m in expenses_df.filter(regex='^_', axis=1)]
    list_expenses.sort()
    list_members = members_df['Name'].values.tolist()
    list_members.sort()
    differences = set(list_expenses) ^ set(list_members) 
    for diff in differences:
        add_to_error_list(error_type = "group_member", element_id = diff)

    # Error 2: Number of friends in file is different than total group members
    if len(members_df['Name']) != len(group.members) : add_to_error_list("n_members", 1, errors)

    # Expense-level errors
    
    for i, row in expenses_df.iterrows():
        # Error 3: Description length > max 
        if len(row["Description"]) > EXP_DESCR_MAX_CHARS: 
            add_to_error_list("descr", row['ID'])

        # Error 4: Shares do not add up
        # cols_to_add = [col_name for col_name in expenses_df.filter(regex='^_', axis=1)]
        if row['Split type'] == "amount" and row['Total Shares'] != row['Amount'] : 
            add_to_error_list("shares_no_addup", row['ID'])
        elif row['Split type'] == "shares" and row['Total Shares'] != 100 : 
            add_to_error_list("shares_no_addup", row['ID'])
        
        # Error 5: Split type not supported
        if row["Split type"] not in SPLIT_TYPES and row["All equal"] != True: 
            add_to_error_list("split_type_unsupported", row['ID'])

        # Error 6: Payer name does not match
        if row["Paid by"] not in list_members:
            add_to_error_list("payer_name_error", element_id = row['ID'])

    # Build the error message, looping over the different errors
    error_messages = []
    for type in errors.keys():
        if len(errors[type]['error_list']) > 0 : error_messages.append(new_error_msg(type, errors))
    
    # Get the total sum of errors
    error_count = 0
    for type in errors.values():
        error_count += len(type['error_list'])
    
    # Return
    return errors, error_messages, error_count