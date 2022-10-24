from flask import Flask, url_for, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from flask_session.__init__ import Session
from datetime import datetime
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, update_portfolios

from splitwise import Splitwise
import config as Config

#Create app and Splitwise secret key
app = Flask(__name__)
app.secret_key = "test_secret_key"

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

Session(app)

#Initalize the database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db' # three '/' is relative path, 4 would be aboslute
db = SQLAlchemy(app)


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
        sObj = Splitwise(Config.consumer_key,Config.consumer_secret)
        sObj.setAccessToken(session['access_token'])

        groups = sObj.getGroups()
    return render_template('groups.html', groups=groups)


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

        # Try to load access_token (only if user has authorized Splitwise before)
        try:
            sObj = Splitwise(Config.consumer_key,Config.consumer_secret)
            url, secret = sObj.getAuthorizeURL()
            access_token = sObj.getAccessToken(rows[0]["split_oauth_token"], secret,rows[0]["split_oauth_verifier"])
            session['access_token'] = access_token
        except:
            return redirect("/")     
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