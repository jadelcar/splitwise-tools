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
import json

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

@router.get("/batch_upload", name = "batch_upload", response_class = HTMLResponse)
def batch_upload_show_form(request: Request):
    """
    Show form for uploading an excel file
    """
    sObj = auth.get_access_token(request)
    groups = sObj.getGroups()
    return templates.TemplateResponse("batch_upload.html", {"request": request, "groups" : groups})


@router.post("/batch_upload_process", name = "batch_upload_process", response_class = HTMLResponse)
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
    
    members_json = json.loads(members_df.to_json(orient='records'))
    members_json = {str(item['ID']): {'name': item['Name']} for item in members_json}
    # Example:
    # members_json{
    #     '4822038': {'name': 'Javier D'},
    #     '78448867': {'name': 'Xián'},
    #     '78448868': {'name': 'Mario'},
    #     '78448869': {'name': 'Faith'}
    # }
    
    # Parse the expenses sheet
    members_in_expenses_names = expenses_df.filter(regex='^_', axis=1).columns.str.lstrip('_').tolist()
    expenses_df = expenses_df.rename(columns = {member_name : member_name[1:] for member_name in expenses_df.filter(regex='^_', axis=1)})

    # Keep a separate dict only with the members present in the expenses sheet
    members_in_expenses = {}
    for id, member_info in members_json.items():
        if member_info['name'] in members_in_expenses_names:
            members_in_expenses[id] = member_info

    # Round the 'Amount' column and member data columns to 2 decimals
    expenses_df['Amount'] = expenses_df['Amount'].round(2)
    expenses_df[members_in_expenses_names] = expenses_df[members_in_expenses_names].round(2)

    # Calculate columns
    expenses_df['Total Shares'] = expenses_df[members_in_expenses_names].sum(axis=1)  # Create col to add shares from all members
    expenses_df['All equal'] = expenses_df['All equal'].astype(str).apply(str.lower).replace(['y','n',''], [True, False, False]) # Read the 'All equal' columns

    # members_in_expenses = []
    # for member_name in cols_member_names:
    #     member_id = members_json[member_name[1:]]['ID']
    #     # Search for the key where the value equals 'x'
    #     key_with_value_x = next((key for key, value in members_json.items() if value['name'] == 'x'), None)

    #     member_info = members_df[members_df['Name'] == member_name[1:]]
    #     members_in_cols.append(
    #         {
    #             'name': member_name[1:],
    #             'id': int(member_info['ID'].values[0])
    #         }
    #     )

    # Payer ID, get it from the members sheet
    expenses_df = expenses_df.merge(members_df, 
                                    how = 'left', 
                                    left_on = "Paid by", 
                                    right_on = 'Name').rename(
                                        columns = {'ID_x': "ID", 'ID_y': "Payer ID"}
                                        )

    # Calculate share owed and paid for a given member and expense
    def getShareOwed(row, member_name):
        """ Calculate share owed for a given expense (row) and user (member name), taking into account split type"""
        member_cell_value = row[member_name]
        if pd.isna(member_cell_value):
            result = 0
        elif row['All equal']:
            result = round(row['Amount'] / len(group.members), 2) # Divide equally by the number of members in group
        elif row["Split type"] == "share":
            result = round(member_cell_value / 100 * row['Amount'], 2) # Divide based on %
        elif row["Split type"] == "amount":
            result = member_cell_value # Assign the amount specified
        elif row["Split type"] == "equal":
            members_for_division = [member['name'] for member in members_in_expenses.values() if not pd.isna(row[f"{member['name']}"])]
            result = round(row['Amount'] / len(members_for_division), 2)
        else:
            result = 0 # An error will be raised to the user
        return result
        
    for col_name in members_in_expenses_names:
        # Share paid
        expenses_df[f'{col_name}_share_paid'] = np.where(expenses_df["Paid by"] == col_name,  expenses_df['Amount'], 0)

        # Share owed
        expenses_df[f'{col_name}_share_owed'] = expenses_df.apply(getShareOwed, axis = 1, member_name = f"{col_name}")

    # Round share owed if it doesn't add up
    def AssignRoundingDiff(row):
        """Assign the rounding difference to a random member within the expense
        Add up share_owed of all members and compare with total amount: If the difference is due to rounding (<0.02), subtract this from a random user within the expense
        """
        share_owed_columns = [f"{col_name}_share_owed" for col_name in members_in_expenses_names if row[f"{col_name}_share_owed"] > 0] # List of columns to parse in this expense
        sum_share_owed = row[share_owed_columns].sum()
        diff = sum_share_owed - row['Amount']
        if abs(diff) > 0 and abs(diff) < 0.02:
            diff_round = round(diff, 2)
            random_member = random.choice(share_owed_columns)
            row[random_member] += -diff_round # Subtract the difference
        return row

    expenses_df = expenses_df.apply(AssignRoundingDiff, axis = 1)

    # Obtain error message
    errors, error_messages, error_count = describe_errors(expenses_df, members_df, group, members_in_expenses_names)

    # Convert to dict that will be passed to jinja
    expenses = expenses_df.replace({np.nan: None}).to_dict(orient="records")


    # Create upload and expenses in database
    if error_count == 0:
        new_upload = crud.create_upload(db, creator_user_id = current_user.id, group_id = group.id)
        for exp in expenses:
            crud.create_expense(db, upload_id = new_upload.id, expense = exp, group_members = members_in_expenses, creator_user_id = current_user.id)
    
    # Prepare context to be passed to template
    context = {
        "request" : request,
        "group" : group_to_dict(group), 
        "members_in_cols" : [{'id' : member_id, 'name' : member_info['name']} for member_id, member_info in members_in_expenses.items()], 
        "expenses" : expenses,
        "errors" : errors,
        "error_messages" : error_messages,
        "file_valid" : error_count == 0,
        "upload_id" : new_upload.id if error_count==0 else 0,
    }

    return templates.TemplateResponse("upload_edit.html", context)

@router.post('/push_expenses/{upload_id}', name = "push_expenses", response_class = HTMLResponse)
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
        # If payer is the logged in user, simply use setSplitEqually
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
