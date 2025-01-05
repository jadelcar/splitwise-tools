from splitwise.expense import Expense
from splitwise.user import ExpenseUser

from starlette.requests import Request
from fastapi import APIRouter, Depends, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse
from core.config.settings import get_settings
from core.exceptions import handlers
from core.templates import templates
from api.routes import auth
from db import crud, models, schemas, database
from services.helpers.expense_utils import describe_errors, group_to_dict

from sqlalchemy.orm import Session

import pandas as pd
import numpy as np
import random

from core.config.settings import get_settings

router = APIRouter(
    tags=["batch_upload"]
)

settings = get_settings()
URL = f"http://{settings.APP_HOST}:{settings.APP_PORT}"

"""       ----------           Retrieve data       -----------            """

@router.get('/batch_upload', response_class = HTMLResponse)
def batch_upload_show_form(request: Request):
    """
    Show form for uploading an excel file
    """
    sObj = auth.get_access_token(request)
    groups = sObj.getGroups()
    return templates.TemplateResponse("batch_upload.html", {"request": request, "groups" : groups})


@router.post("/batch_upload_process", response_class = HTMLResponse)
def batch_upload_process(request: Request, db: Session = Depends(database.get_db),group_for_upload = Form(), batch_expenses_file : UploadFile = File(...)):
    """
    Process the data uploaded
    """
    # Access tokens
    sObj = auth.get_access_token(request)
    current_user = sObj.getCurrentUser()
    
    group = sObj.getGroup(group_for_upload) # Fetch group info
    request.session.pop('upload_id', None) # Erase from session any previous upload
    file = batch_expenses_file.file.read() # Import and parse user file 
    
    expenses_df = pd.read_excel(file, sheet_name = "Expenses") # Import expenses sheet
    members_df = pd.read_excel(file, sheet_name = "Members") # Import the members sheet
    
    # Parse the expenses sheet
    cols_member_names = list(expenses_df.filter(regex='^_', axis=1)) # Make a list with member names
    expenses_df['Total Shares'] = expenses_df[cols_member_names].sum(axis = 1) # Create col to add shares from all members
    
    expenses_df['All equal'] = expenses_df['All equal'].astype(str).apply(str.lower).replace(['y','n',''], [True, False, False]) # Read the 'All equal' columns
        
    # Create a list of dicts {name: , id:} to hold member info (name and ID)
    members_in_cols = []
    for member_name in expenses_df[cols_member_names].columns:
        member_info = members_df[members_df['Name'] == member_name[1:]]
        members_in_cols.append(
            {
                'name': member_name[1:],
                'id': int(member_info['ID'].values[0])
            }
        )

    # Payer ID
    expenses_df = expenses_df.merge(members_df, 
                                    how = 'left', 
                                    left_on = "Paid by", 
                                    right_on = 'Name').rename(
                                        columns = {'ID_x': "ID", 'ID_y': "Payer ID"}
                                        )

    # Calculate share owed and paid for a given member
    def getShareOwed(row, member_name, cols_member_names):
        """ Calculate share owed for a given expense (row) and user (member name), taking into account split type"""
        member_cell_value = row[member_name]
        if pd.isna(member_cell_value):
            return 0
        elif row['All equal']:
            return round(row['Amount'] / len(group.members), 2) # Divide equally by the number of members in group
        elif row["Split type"] == "share":
            return round(member_cell_value / 100 * row['Amount'], 2) # Divide based on %
        elif row["Split type"] == "amount":
            return member_cell_value # Assign the amount specified
        elif row["Split type"] == "equal":
            members_for_division = [member['name'] for member in members_in_cols if not pd.isna(row[f"_{member['name']}"])]
            return round(row['Amount'] / len(members_for_division), 2)
        else:
            return 0 # An error will be raise to the user
        
    for col_name in cols_member_names:
        # Share paid
        expenses_df[f'{col_name[1:]}_share_paid'] = np.where(expenses_df["Paid by"] == col_name[1:],  expenses_df['Amount'], 0)

        # Share owed
        expenses_df[f'{col_name[1:]}_share_owed'] = expenses_df.apply(getShareOwed, axis = 1, member_name = f"_{col_name[1:]}", cols_member_names=cols_member_names)

    # Round share owed if it doesn't add up
    def AssignRoundingDiff(row):
        """Assign the rounding difference to a random member within the expense
        Add up share_owed of all members and compare with total amount: If the difference is due to rounding (<0.02), subtract this from a random user within the expense
        """
        share_owed_columns = [f"{col_name[1:]}_share_owed" for col_name in cols_member_names if row[f"{col_name[1:]}_share_owed"] > 0] # List of columns to parse in this expense
        sum_share_owed = row[share_owed_columns].sum()
        diff = sum_share_owed - row['Amount']
        if abs(diff) > 0 and abs(diff) < 0.02:
            diff_round = round(diff, 2)
            random_member = random.choice(share_owed_columns)
            row[random_member] += -diff_round # Subtract the difference
        return row

    expenses_df = expenses_df.apply(AssignRoundingDiff, axis = 1)

    # Obtain error message
    errors, error_messages, error_count = describe_errors(expenses_df, members_df, group)

    # Store data temporarily so it can be pushed later
    expenses = expenses_df.to_dict('records')
    if error_count == 0:

        # Create upload and expenses in database
        new_upload = crud.create_upload(db, creator_user_id = current_user.id, group_id = group.id)
             
        for exp in expenses:
            crud.create_expense(db, upload_id = new_upload.id, expense = exp, group_members = members_in_cols, creator_user_id = current_user.id)
    
    # Prepare context to be passed to template
    context = {
        "request" : request,
        "group" : group_to_dict(group), 
        "members_in_cols" : members_in_cols, 
        "expenses" : expenses,
        "errors" : errors,
        "error_messages" : error_messages,
        "file_valid" : error_count == 0,
        "upload_id" : new_upload.id if error_count==0 else 0,
    }

    return templates.TemplateResponse("upload_edit.html", context)

@router.post('/push_expenses/{upload_id}', response_class = HTMLResponse)
def push_expenses(request: Request, upload_id: int, db: Session = Depends(database.get_db)):

    sObj = auth.get_access_token(request)
        
    upload = crud.get_upload_by_id(db, upload_id = upload_id)
    expenses = crud.get_expenses_by_upload_id(db, upload_id = upload_id)
    group = crud.get_group_by_id(db, group_db_id = upload.group_id) # DB ID, not SW ID

    # Upload each expense to Splitwise
    expenses_to_push = {}
    for e in expenses:
        expense = Expense()
        expense.setCost(e.amount)
        expense.setDescription(e.description)
        expense.setGroupId(group.sw_id)
        expense.setCreationMethod('Splitwise tools')
        expense.setDate(e.date)
        expense.setCurrencyCode(e.currency)
        # If we split all equal, no need to add members
        if e.all_equal == True and e.payer_id == sObj.getCurrentUser().getId(): 
            expense.setSplitEqually()
        # O/w, add each member of the expense
        else:
            for member in e.expense_members:
                user = ExpenseUser()
                user.setId(member.member.sw_id)
                user.setPaidShare(member.share_paid) 
                user.setOwedShare(member.share_owed)
                expense.addUser(user)

        expenses_to_push[e.within_upload_id] = expense # Add to dictionary, using 'Id' (specified by user) as key
    
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
        "group" :   {   
                        'id': group.sw_id,
                        'name': group.name,
                    },
        "expenses_failed" : expenses_failed,
    }

    # Return summary
    return templates.TemplateResponse("upload_summary.html", context)
