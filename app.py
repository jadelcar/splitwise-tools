from cmath import nan

from flask import Flask, url_for, render_template, request, redirect, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_session.__init__ import Session
from datetime import datetime
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from jinja2 import pass_context

from splitwise import Splitwise
from splitwise.expense import Expense
from splitwise.user import ExpenseUser
import config as Config

import pandas as pd
from thefuzz import fuzz
import math
import re


#Create app and Splitwise secret key
app = Flask(__name__)
app.secret_key = "test_secret_key"

# Ensure templates are auto-reloaded
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

Session(app)

# #Initalize the database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db' # three '/' is relative path, 4 would be aboslute
db = SQLAlchemy(app)



#Import classes and helper functions
from helpers import *
from classes import *

@app.context_processor
def include_UpMember_class():
    return {'UpMember': UpMember}

# app.add_template_global(UpExpense, 'UpExpense')
# app.add_template_global(UpMember, 'UpMember')


"""
Create a class to define the object 'todo'. This is useful because the whole app revolves around this type of unit, so it's nice that we don't have to specify every time the characteristics of a 'todo', we simply use this definition.

Note the argument of this class is 'db.Model', meaning that this is a SQLAlchemy model class:
    The SQLAlchemy Object Relational Mapper presents a method of associating user-defined Python classes with database tables, and instances of those classes (objects) with rows in their corresponding tables. 

i.e. with this class definition we are associating the object class 'todo' with a table and the characteristics of such table.

In particular, a 'todo' will have the following characteristics: (id, content, completed, date_created)

    new_todo = Todo(content="X") # Create a 'todo' object where the column 'content' has the value "X"

Other fields will have a default (such as completed or date_created) or have a primary key (does it self-increment?)

To modify the database, use sqlite3 in the terminal:
sqlite3 instance/database.db
# Add a column:
ALTER TABLE user ADD COLUMN split_access_token type text;

"""
class Todo(db.Model):
    #__tablename__ = "to_dos" # Define the table name (Not in the tutorial)
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(200), nullable=False) #nullable false means the user cannot leave it null (empty)
    #completed =db.Column(db.Integer, default=0)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    
    #Function that returns a string every time we create a new element
    def __repr__(self):
        return '<Task %r>' % self.id

class User(db.Model):
    #__tablename__ = "to_dos" # Define the table name (Not in the tutorial)
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(25), nullable=False) #nullable false means the user cannot leave it null (empty)
    #completed =db.Column(db.Integer, default=0)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    pass_hash = db.Column(db.String(200), nullable=False) 
    split_user_id = db.Column(db.String(40))
    split_token = db.Column(db.String(200))
    split_secret = db.Column(db.String(200))
    split_oauth_token = db.Column(db.String(200))
    split_oauth_verifier = db.Column(db.String(200))
    
    #Function that returns the ID every time we create a new element
    def __repr__(self):
        return '<You were assigned ID %r>' % self.id


# @app.after_request
# def after_request(response):
#     """Ensure responses aren't cached"""
#     response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
#     response.headers["Expires"] = 0
#     response.headers["Pragma"] = "no-cache"
#     return response

@app.route("/")
def home():
    return render_template("home.html")

@app.route('/groups', methods=['GET','POST'])
def groups():
    """Show a list of groups"""
    if request.method == 'POST':
        pass
    #If method is 'GET'
    else:
        # Fetch groups
        if 'access_token' not in session:
            return redirect(url_for("home"))
        # sObj = Splitwise(Config.consumer_key,Config.consumer_secret)
        # sObj.setAccessToken(session['access_token'])
        sObj = get_access_token() # Helper function
        groups = sObj.getGroups()
    return render_template('groups.html', groups=groups)

@app.route('/batch_upload', methods=['GET','POST'])
def batch_upload():
    if request.method == 'GET':
        sObj = get_access_token()
        groups = sObj.getGroups()
        return render_template('batch_upload.html', groups=groups)
    else:
        sObj = get_access_token()
        app_current_user = sObj.getCurrentUser()

        # Fetch group info
        group_obj = sObj.getGroup(request.form.get("group_for_upload"))
        group = {
            'id' : group_obj.getId(), 
            'name' : group_obj.getName(), 
            'members' :  group_obj.getMembers()
        }
        
        """
        Create a list of dictionaries, each dict containing individual member's data
         Dict structure:
        group_members = [
            {   
                'id' : 1001
                'fname' : Javier
                'lname' : Delgado
            }, 
            (...)
        ]
        """
        group_members = []
        for member in group["members"]: 
            group_members.append(
                {
                    'id' : member.getId() ,
                    'fname' : member.getFirstName(),
                    'lname' : member.getLastName()
                } 
            )

        # Import user file 
            # See https://flask.palletsprojects.com/en/2.2.x/quickstart/#file-uploads 
            # See https://flask.palletsprojects.com/en/2.2.x/api/#flask.Request.files
        file = request.files['batch_expenses_file'] 
        expenses_df = pd.read_excel(file)
        
        """Map raw user names to Splitwise group member names, using fuzzy matching """
        # Create a list for holding users in the uploaded file
        up_users = {}

        # Create an instance of class 'UpMember' for the user uploading the file         
        current_user_UpMember = UpMember(
            orig_name = app_current_user.getFirstName(), 
            candidates = [{'id' : app_current_user.getId(), 'name' : app_current_user.getFirstName()}],
            final_id = app_current_user.getId(), 
            final_name = app_current_user.getFirstName()
            )
        up_users[app_current_user.getFirstName()] = current_user_UpMember
        
        """ 
        users_raw = [
            {
                'name' : app_current_user.getFirstName(), 
                'candidates' : [app_current_user.getId()] ,
                'candidates_names' : [app_current_user.getFirstName()],
                'id' : app_current_user.getId() ,
                'correct' : "yes"
            }
        ]
        """

        #Loop over columns starting with "_"
        for column in expenses_df.filter(regex='^_', axis=1): # Loop over columns that start with "_"
            raw_user_name = str(column).replace("_","",1)
            curr_UpMember = UpMember(orig_name = raw_user_name)

            # Loop over the members of the group, calculate similscores (ratio) and add to candidate list if they are close. Package https://github.com/seatgeek/thefuzz.
            for member in group_members:
                ratio = fuzz.ratio(raw_user_name, member['fname'])
                if ratio == 100: # In case of a perfect match we stop looking
                    curr_UpMember.candidates = [{ 'id' : member['id'], 'name' : member['fname'] }]
                    continue # Go to next member uploaded in file
                elif ratio > 90:
                    curr_UpMember.add_candidate(member['id'], member['fname'])
            
            # Review and consolidate results (e.g. If there's only one candidate, replace name by the database name)
            if len(curr_UpMember.candidates) == 1: #If only one candidate, replace
                curr_UpMember.final_id = curr_UpMember.candidates[0]['id']
                curr_UpMember.final_name = curr_UpMember.candidates[0]['name']
                curr_UpMember.correct = True
            else:
                curr_UpMember.correct = False

            #Append the member to the dict with key beign the name (e.g. 'Javier')of users in the file uploaded
            up_users[raw_user_name] = curr_UpMember

        """ Replace column names in dataframe by the Splitwise names """

        # Replace in the dataframe column names    
        expenses_df = expenses_df.rename(columns = lambda x : re.sub('^_','', x)) 
        expenses_df = expenses_df.rename(columns = lambda x : re.sub('(?i)you',app_current_user.first_name, x)) # (?i) makes it case insensitive       

        # (TBD) Show user the results and ask for verification

        """
        Verification of file

        error_master is a dict of dicts. Each dict refers to one type of error (description too long, date format, wrong group member etc.) and contains:
            'message': Displayed to user
            'element_type': Type of element affected (expense, member etc.)
            'error_list': List of elements affected
        
        As we identify errors, we populate the dicts with function 'add_error' and build the error message progressively with function 'add_to_error_msg'.
        """
        # Split types supported         
        split_types = ['amount', 'equal', 'share'] 

        # Dictionary with different error types
        error_master = {
            'descr' : {
                "message" : "Expense description is longer than 20  characters" ,
                "element_type" : "expense(s)" } ,
            'date' : {
                "message" : "Review date format" ,
                "element_type" : "expense(s)" },
            'group_member' : {
                "message" : "Name should only match one group member" ,
                "element_type" : "column(s)" },
            'n_members' : {
                "message" : "Number of friends in file is different from members in the group" ,
                "element_type" : "general" },    
            'shares_no_addup' : {
                "message" : "Shares do not add up" ,
                "element_type" : "expense(s)" },
            'split_type_unsupported' : {
                "message" : "Split type is not supported, choose one of the following: " + ", ".join(["'" + t + "'" for t in split_types]),
                "element_type" : "expense(s)" }
        }
        for d in error_master.keys(): 
            error_master[str(d)]['error_list'] = [] # Initialize error list for each type of error

        # Error 1: Friend name matches none or > 1 group member
        for raw_user in up_users.values():
            if len(raw_user.candidates) != 1: add_to_error_list("group_member", raw_user.orig_name, error_master)

        # Error 2: Number of friends in file is different than group members
        if len(up_users) != len(group['members'])  : add_to_error_list("n_members", 1, error_master)

        # Error 3: Description length > 50 ('descr')
        for id, descr in zip(expenses_df.id, expenses_df.description):
            if len(descr) > 50: 
                add_to_error_list("descr", id, error_master)

        # Error 4: Shares do not add up
        
        cols_to_add = [member.getFirstName() for member in group['members']] # Make a list of column names we want to add up

        # Add column with the sum of shares and compare with total amount
        expenses_df['total_shares'] = expenses_df[cols_to_add].sum(axis=1) 
        for id, type_split, amount, total_shares in zip(expenses_df.id, expenses_df.type_split, expenses_df.amount, expenses_df.total_shares):
            if type_split == "amount" and total_shares != amount : 
                add_to_error_list("shares_no_addup", id, error_master)
            elif type_split == "shares" and total_shares != 100 : 
                add_to_error_list("shares_no_addup", id, error_master)
        
        # Error 5: Split type not supported
        for id, type_split, all_equal in zip(expenses_df.id, expenses_df.type_split, expenses_df.all_equal):
            if type_split not in split_types and all_equal != 'y': 
                add_to_error_list("split_type_unsupported", id, error_master)

        # Date cannot be parsed
        # for date in df.date:
        #     if is_date(date) == TRUE:

        # Build the error message, looping over the different errors
        error_message = ""
        for type in error_master.keys():
            if len(error_master[type]['error_list']) > 0 : error_message += new_error_msg(type, error_master)
        
        # Get the total sum of errors
        error_count = 0
        for t in error_master.values():
            error_count += len(t['error_list'])
        
        """
        Description of a comprehension (one-liner) [Not implemented bc it was written for a simple dict so it was replaced by a conventional loop]

        A one liner is better read from back to front and from inside to outside
            function(   return (passed on to function)  loop                            if condition)
            sum     (   len(t['error_list'])            for t in error_master.values()  if t)
        
        Steps (application in our case)
            1. Loop over certain values (keys in the dict)
            2. Apply an if condition (if the key exists)
            3. Write expression to be returned (# of elements in list found under key 'error_list')
            4. Apply function using all the returned values (sum all the 'lengths')
        """

        # Loop through payers and add the payer ID (if they are correct)
        expenses_df['paid_by'].replace("(?i)you", app_current_user.getFirstName(), regex=True, inplace=True) # Change 'you' by the app user name

        for index, expense in expenses_df.iterrows():
            raw_payer_name = expense['paid_by']
            if str.lower(raw_payer_name) == "you": # Set values if payer = 'you'
                expenses_df.at[index,'paid_by'] = app_current_user.getFirstName() 
                expenses_df.at[index,'payer_name'] = app_current_user.getFirstName()
                expenses_df.at[index,'payer_id'] = app_current_user.getId()
            else: 
                for user in up_users.values():
                    if user.final_name == raw_payer_name:
                        if user.correct == "yes": # Payer matches a column which also matches a group member
                            expenses_df.at[index,'payer_id'] = user['candidates'][0] # First element in the list 'candidate', which we know because correct = 'y'
                            expenses_df.at[index,'payer_check'] = "correct"
                        elif user.correct == "no": # Payer matches column, but col didn't match a group member
                            expenses_df.at[index,'payer_id'] = nan
                            expenses_df.at[index,'payer_check'] = "No match in group members"
                    else: 
                        continue # Move to next 
                if "payer_id" not in expense.keys(): # If after checking all the members no match was found, record this result
                    expenses_df.at[index,'payer_id'] = nan
                    expenses_df.at[index,'payer_check'] = "No match in column names"

        """ 
        Structure of dicts in users_raw
        users_raw = [
            {
                'raw_name' : "Jvier" ,
                'candidates' : [1245, 1765]
            }
            (...)
        ]
        """        



        # Pass dataframe to a list of dicts
        expenses = expenses_df.to_dict('records')

        # Calculate share paid and owed for each user in each expense, and store in a dict within expense
        for expense in expenses:
            if expense['type_split'] in split_types and expense['all_equal'] != "y":
                for member in group['members']:
                    # Share paid: Full amount or zero (no support for several payers yet)
                    member_name = member.getFirstName()
                    member_id = member.getId()
                    if expense['paid_by'] == member_name : share_paid = expense['amount']
                    else: share_paid = 0
                    
                    # Share owed, depends on the type of split
                    indiv_cell_owed = expense[member_name] # fetch number under this member's column
                    if expense['all_equal'] == "y": # Default: Split equally among all group members
                        share_owed = expense['amount'] / len(group['members'])
                    else:
                        if expense['type_split'] == "share":
                            share_owed = round((indiv_cell_owed/100)*expense['amount'], 2) # e.g. share = 10 --> 0.1*amount
                        elif expense['type_split'] == "amount":
                            share_owed = indiv_cell_owed # e.g. share_owed for Javier is the value under column "_Javier"
                        elif expense['type_split'] == "equal":
                            members_to_split = 0
                            for member_inner in group['members']: 
                                if expense[member_inner.getFirstName()] != '': members_to_split += 1 # Count how many members to split among
                            share_owed = round(expense['amount'] / members_to_split) # Get value from cell under the person's column
                    
                    #Add the 'shares' dict to the corresponding key inside the expense
                    shares = {
                        "user_id" : member_id ,
                        "share_owed" : share_owed ,
                        "share_paid" : share_paid
                    }

                    expense[member_name + "_shares"] = shares # e.g. expense['javier_shares'] = {"share_owed" : 7.5, "share_paid" : 15}
            else: 
                #If paid_equal = y 
                for member in group['members']:
                    member_name = member.getFirstName()
                    member_id = member.getId() 
                    if expense['paid_by'] == member_name : share_paid = expense['amount']
                    else: share_paid = 0
                    
                    shares = { 
                        "user_id" : member_id ,
                        "share_owed" : expense['amount'] / len(group['members']),
                        "share_paid" : share_paid
                    }
                    expense[member_name + "_shares"] = shares
            """
            Ensure shares add up to the total amount by adding/substracting the difference from the uploading user (Since we are checking for errors, it should only be because of rounding and thus small)
            """
            # Add up the shares owed of all members in the expense: For this, loop over members, go to the expense and get the share owed, whtich is within a dict called after member name (expense[*MemberName*_shares]["share_owed"]). But only if there is a key called 'share_owed' within the dict(if "share_owed" in expense[*MemberName*_shares].keys()). Once you have this list of values, we sum them up
            indiv_shares_added = sum(
                expense[member.getFirstName() + "_shares"]["share_owed"] 
                for member in group['members'] 
                if expense[member.getFirstName() + "_shares"]["share_owed"] != "") 

            #print("Expense" + str(expense['id']) + ": " + str(indiv_shares_added))
                                    
            if indiv_shares_added != expense['amount'] and math.isnan(indiv_shares_added) == False:
                diff = expense['amount'] - indiv_shares_added
                user_share_owed = expense[app_current_user.getFirstName() + '_shares']['share_owed']
                #print("Total shares: " + str(expense[app_current_user.getFirstName() + '_shares']['share_owed']))
                #print("Diff: " + str(diff))
                if user_share_owed!= '':
                    user_share_owed += diff
            
        """
        expenses = [
            {
                'id' : 1
                'description' : "Expenditure for..."
                (...)
                '_you' : 20
                'Alberto' : 15
                'Pedro' : 30
            }
        ]
        """

        # Convert up_users back to a dict of dicts so it can be used
        users_raw = {}
        for user in up_users:
            # print(up_users[user])
            # print(up_users[user].__dict__)
            todict = vars(up_users[user])
            obj = up_users[user]
            users_raw[user] = {
                'orig_name' : obj.orig_name,
                'final_id' : obj.final_id,
                'final_name' : obj.final_name
                }
        
        if error_count == 0:
            # Store the dict in session and redirect to editing site
            session['expenses_upload'] = expenses
            session['expenses_upload_group_members'] = group_members
            session['expenses_upload_group_id'] = group['id']
            session['expenses_upload_group_name'] = group['name']

            # Redirect to the website for editing (edit_upload.html), passing on the data on expenses for display
            # Consider improving this view with using pivottable.js (https://github.com/nicolaskruchten/jupyter_pivottablejs)
            # Making classes available in Jinja2 (https://stackoverflow.com/questions/29257476/how-can-i-make-a-class-variable-available-to-jinja2-templates-with-flask)
            
            return render_template("upload_edit.html", file_valid = "yes", group = group, users_raw = users_raw, expenses = expenses, error_master = error_master)
        else:
            flash(error_message)
            return render_template("upload_edit.html", file_valid = "no",  group = group, users_raw = users_raw, expenses = expenses, error_master = error_master)

# TBD: Depending on the process result
    # If the process fails: Show errors
    # If the process timeouts: Show apology
    # If the process succeeds:

@app.route('/push_expenses', methods=['POST'])
def push_expenses():
    #Another option: Parse the data received as JSON in the Splitwise format needed (https://flask.palletsprojects.com/en/2.2.x/api/#flask.Request.get_json), also see the property 'JSON'
    sObj = get_access_token()
    app_current_user = sObj.getCurrentUser()

    # The data to upload was stored in session
    expenses = session['expenses_upload']
    group_id = session['expenses_upload_group_id']
    group = sObj.getGroup(group_id)
    group_name = group.name

    # Extract needed data
    group_members = []
    for member in group.getMembers():
        group_members.append(
            {
                "name" : member.first_name ,
                "id" : member.id
            }
        )

    # Upload each expense to Splitwise
    expenses_failed = []
    expenses_sw_obj = []
    for e in expenses:
        expense = Expense()
        expense.setCost(e['amount'])
        expense.setDescription(e['description'])
        expense.setGroupId(group.id)
        expense.setCreationMethod('app_tools')
        expense.setDate(e['date'])
        expense.setCurrencyCode(e['currency'])
        if e['all_equal'] == "y" and str.lower(e['paid_by']) == 'you': 
            expense.setSplitEqually() #Default is 'should_split = True'
            pass
        else:
            for member in group_members:
                user_share_dict = e[member['name'] + "_shares"] # Contains share_owed and share_paid
                if sum(user_share_dict.values()) > 0: # if any of share_owed or share_paid  is > 0, the user is a member of this expense 
                    user = ExpenseUser()
                    user.setId(user_share_dict['user_id'])
                    user.setPaidShare(user_share_dict['share_paid'])
                    user.setOwedShare(user_share_dict['share_owed'])
                    expense.addUser(user)
        expenses_sw_obj.append(expense)
    
    
    # Upload expenses
    for expense in expenses_sw_obj:
        nExpense, errors = sObj.createExpense(expense)
        if nExpense is not None: 
            print("Expense number: " + str(nExpense.getId()))
        else:
            print("Expense errors: " + str(errors))
            expenses_failed.append(
                {
                    'id': e['id'],
                    'error' : errors
                }
            )

    # Return summary
    if len(expenses_failed) > 0:
        return render_template("upload_fail_summary.html", expenses_failed = expenses_failed, group_id = group_id, group_name = group_name)
    else:
        return render_template("upload_success_summary.html", group_id = group_id)


@app.route("/login_app", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        #Docs: https://docs.sqlalchemy.org/en/14/core/connections.html#sqlalchemy.engine.RowMapping
        users_query = User.query.filter_by(username=request.form.get("username"))
        
        rows = [u.__dict__ for u in users_query]
        # rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["pass_hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        session["user_name"] = rows[0]["username"]
        

        # Try to load access_token (only if user has authorized Splitwise before)
        # try:
        #     sObj = Splitwise(Config.consumer_key,Config.consumer_secret)
        #     url, secret = sObj.getAuthorizeURL()
        #     access_token = sObj.getAccessToken(rows[0]["split_oauth_token"], secret,rows[0]["split_oauth_verifier"])
        #     session['access_token'] = access_token
        # except:
        #     return redirect("/")     
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

"""
Splitwise login: Uses two routes. /login_sw redirects the user to SW's URL for authorization using 'getAuthorizeURL()'. Then, SW will redirect to the URL defined in app's settings, which in this case is "/authorize".

In /authorize the user's access token is stored in the session for later use
"""

@app.route("/login_sw")
def login_sw():
    sObj = Splitwise(Config.consumer_key,Config.consumer_secret) #Special object for authentication in Splitwise
    url, secret = sObj.getAuthorizeURL() # Method in sObj 'getAuthorizeURL()' returns the URL for authorizing the app
    
    session['secret'] = secret 

    # Store secret in DB
    current_user = User.query.get_or_404(session["user_id"])
    current_user.split_secret = secret
    try:
        db.session.commit()
    except:
        return 'There was an issue updating your user access token'
    return redirect(url) #Redirect user to SW authorization website. After login, redirects user to the URL defined in the app's settings

@app.route("/authorize")
def authorize():
    if 'secret' not in session:
        return redirect(url_for("home"))

    # Get token and verifier from Splitwise's POST request
    oauth_token    = request.args.get('oauth_token')
    oauth_verifier = request.args.get('oauth_verifier')

    # Store these in DB
    current_user = User.query.get_or_404(session["user_id"])
    current_user.split_oauth_token = oauth_token
    current_user.split_oauth_verifier = oauth_verifier
    try:
        db.session.commit()
    except:
        return 'There was an issue updating your user access token'

    # Get parameters needed to obtain the access token
    sObj = Splitwise(Config.consumer_key,Config.consumer_secret)
    
    current_user = User.query.filter_by(id=session["user_id"])
    rows = [u.__dict__ for u in current_user]
    user_secret = rows[0]['split_secret']
    
    access_token = sObj.getAccessToken(oauth_token, user_secret,oauth_verifier)
    session['access_token'] = access_token
    return render_template("authorize_success.html") # 'url_for' generates a url given the input (in this case, an html file).

@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # If they reach via "GET" we redirect to the page for registering
    if request.method == "GET":
        return render_template("register.html")

    # O/w they reach via post, meaning that they have entered name and password
    else:
        # Obtain user's data entered in the form
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Validate data
        if username=="" or password=="" or confirmation=="" :
            # If at least one of the above are missing
            return apology("Sorry, username or password was missing...", 400)

        elif password != confirmation :
            return apology("Sorry, passwords don't match")

        # Hash the password
        password_hashed = generate_password_hash(password)

        new_user = User(username=username, pass_hash=password_hashed)
        # Insert into table "users", initializing cash to a starting value (initial_cash)
        try:
            db.session.add(new_user)
            db.session.commit()
        except:
            return apology("Could not insert you in the database")
    # Redirect to home (showing a summary of stocks owned and cash)
    return render_template("home.html")

if __name__ == "__main__":
    app.run(debug=True)
    # app.jinja_env.auto_reload = True
    # app.config['TEMPLATES_AUTO_RELOAD'] = True
    # app.run(debug=True, host='127.0.0.1:5000')