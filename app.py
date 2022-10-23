from flask import Flask, url_for, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from flask_session.__init__ import Session
from datetime import datetime
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, update_portfolios

app = Flask(__name__)

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
    
    #Function that returns the ID every time we create a new element
    def __repr__(self):
        return '<You were assigned ID %r>' % self.id



@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route('/', methods=['GET','POST'])
def index():
    if request.method == 'POST':
        task_content = request.form['content'] #Get from the form the object named 'content'
        new_task = Todo(content=task_content)
        
        try:
            db.session.add(new_task)
            db.session.commit()
            return redirect("/")
        except:
            return 'There was an issue adding your task'
    #If method is 'GET'
    else:
        # Obtain the list of tasks
        # Within the class 'Todo', make a query, ordered by 'date_created' (one of the columns of the table) and extract all. Other options would be to extract the first record (first())
        tasks = Todo.query.order_by(Todo.date_created).all() 
        return render_template('index.html', tasks=tasks)

"""
Route for deleting a task. When we call this route, we need to indicate the id of the task we want to delete
eg: "/delete/145"
the ID will be passed on to the function as an argument
"""
@app.route('/delete/<int:id>')
def delete(id):
    task_to_delete = Todo.query.get_or_404(id) #It will make a query to get the task using the 'id' and if it fails it will throw a 404 error

    try:
        db.session.delete(task_to_delete)
        db.session.commit()
        return redirect('/')
    except:
        return 'There was a problem deleting that task'

@app.route('/update/<int:id>', methods=['GET', 'POST'])
def update(id):
    task = Todo.query.get_or_404(id)

    if request.method == 'POST':
        task.content = request.form['content'] #Set the content of the current task to the content submitted in the form via a POST request

        try:
            db.session.commit() # Simply commit this session, where we have update the content of the task
            return redirect('/')
        except:
            return 'There was an issue updating your task'

    else:
        return render_template('update.html', task=task)


@app.route("/login", methods=["GET", "POST"])
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
        rows = User.query.filter_by(username=request.form.get("username")).__dict__
        # rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["pass_hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


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
    #If they reach via "GET" we redirect to the page for registering
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
        # Redirect to index (showing a summary of stocks owned and cash)
    return render_template("base.html")




if __name__ == "__main__":
    app.run(debug=True)

