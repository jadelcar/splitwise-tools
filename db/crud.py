from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash, generate_password_hash

from . import models, schemas

"""---------- Get data  --------------------"""

# Users
def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def get_users(db: Session, skip: int = 0, limit: int = 100):
    """Get the first N users in db (default is 100)"""
    return db.query(models.User).offset(skip).limit(limit).all()

# Members
def get_member_by_sw_id(db: Session, sw_id: int) -> models.Member:
    return db.query(models.Member).filter(models.Member.sw_id == sw_id).first()

# Uploads
def get_upload_by_id(db: Session, upload_id: int):
    return db.query(models.Upload).filter(models.Upload.id == upload_id).first()

def get_uploads(db: Session, skip: int = 0, limit: int = 100):
    """Get the first N uploads in db (default is 100)"""
    return db.query(models.Upload).offset(skip).limit(limit).all()

def get_uploads_by_sw_user_id(db: Session, sw_user_id: int, skip: int = 0, limit: int = 100):
    """Get the first N uploads in db (default is 100)"""
    return db.query(models.Upload).filter(models.Upload.creator_id == sw_user_id).offset(skip).limit(limit).all()

# Expenses
def get_expenses_by_upload_id(db: Session, upload_id: int, skip: int = 0, limit: int = 100):
    return db.query(models.Expense).filter(models.Expense.upload_id == upload_id).offset(skip).limit(limit).all()

# Share owed/paid (TBD)
def get_shares_by_expense_member():
    """Get share owned/paid for a member in a given expense"""
    pass

# Groups
def get_groups(db: Session, skip: int = 0, limit: int = 100):
    """Get the first N groups in db (default is 100)"""
    return db.query(models.Group).offset(skip).limit(limit).all()

def get_groups_of_user(db: Session, user_id: int, limit: int = 100):
    """Get the groups where User is a member in 'db' (by default the first 100 groups)"""
    return db.query(models.User.id, models.User.member_of).filter(models.User.id == user_id).limit(limit)

def get_groups_of_sw_user(db: Session, sw_user_id: int, limit: int = 100):
    """Get the groups where User is a member in db (by default the first 100 groups)"""
    return db.query(models.User.id, models.User.member_of).filter(models.User.id == sw_user_id).limit(limit)

def get_group_by_sw_id(db: Session, sw_id: int) -> models.Group:
    """ Get group by Splitwise ID"""
    return db.query(models.Group).filter(models.Group.sw_id == sw_id).first()

def get_group_by_id(db: Session, group_db_id: int) -> models.Group:
    """ Get group by Splitwise ID"""
    return db.query(models.Group).filter(models.Group.id == group_db_id).first()


"""---------- Create data  --------------------"""

def create_user(db: Session, user: schemas.UserCreate):
    new_hashed_password = user.password + generate_password_hash(user.password)
    db_user = models.User(username = user.username, hashed_password = new_hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def create_upload(db: Session, creator_user_id: int, group_id: int):
    # Get the group from database, and if it doesn't exist we create it
    group_curr_upload = get_group_by_sw_id(db, sw_id = group_id)
    if group_curr_upload == None:
        group_curr_upload = create_group(db, sw_id = group_id)
    db_upload = models.Upload(creator_id = creator_user_id, group_id = group_curr_upload.id)
    db.add(db_upload)
    db.commit()
    db.refresh(db_upload)
    return db_upload

def create_member(db: Session, sw_id: int, name: str):
    """ Create a new member in table 'members'"""
    new_member = models.Member(sw_id = sw_id, name = name)
    db.add(new_member)
    db.commit()
    db.refresh(new_member)
    return new_member

def create_expense_member(db: Session, expense_id: int, member_id : int, share_owed: float, share_paid: float):
    """Create a new member within an expense"""
    new_expense_member = models.ExpenseMember(member_id = member_id, expense_id = expense_id, share_owed = share_owed, share_paid = share_paid)
    db.add(new_expense_member)
    db.commit()
    db.refresh(new_expense_member)
    # Create entries in the table 'expense_members'
    # https://stackoverflow.com/questions/25668092/flask-sqlalchemy-many-to-many-insert-data

def create_expense(db: Session, expense: dict, group_members : list,  creator_user_id: int, upload_id : int):

    new_expense = models.Expense(
        within_upload_id = expense['ID'],
        description = expense['Description'],
        date = expense['Date'],
        amount = expense['Amount'],
        currency = expense['Currency'],
        payer_id = expense['Payer ID'],
        all_equal = expense['All equal'],
        split_type = expense['Split type'],
        creator_id = creator_user_id,
        upload_id = upload_id,
        )

    db.add(new_expense)
    db.commit()
    db.refresh(new_expense)
    # Create the expense-member relationship
    for member in group_members:
        share_paid = expense[f"{member['name']}_share_paid"] # e.g. Javier_share_paid
        share_owed = expense[f"{member['name']}_share_owed"]
        if (share_paid + share_owed) > 0: 
            # Get the member from database
            new_member = get_member_by_sw_id(db, sw_id = member['id']) # If member not in DB, create it
            if new_member == None:
                # If it doesn't exist, create it
                new_member = create_member(db, sw_id = member['id'], name = member['name'])
            # Create the expense-member relationship
            create_expense_member(db, expense_id = new_expense.id, member_id = new_member.id, share_owed = share_owed, share_paid = share_paid)
    db.refresh(new_expense)
    return new_expense

def create_group(db: Session, sw_id: int):
    """ Create a new group in table 'groups'"""
    new_group = models.Group(sw_id = sw_id)
    db.add(new_group)
    db.commit()
    db.refresh(new_group)
    return new_group
# def create_group(db: Session, group: schemas.GroupCreate, user_id: int):
#     """Create a group. Requires a sw_user_id, that will appear as creator of the group (creator_id)"""
#     # First, we create an instance of the class Group
#     # Instead of passing each of the keyword arguments to 'group' and reading each one of them from the Pydantic model, we are generating a dict with the Pydantic model's data with group.dict() and passing these key-value pairs as keyword arguments to the SQLAlchemy Group.
#     db_group = models.Group(**group.dict(), owner_id=user_id) 
#     db.add(db_group) # Add instance object to the database
#     db.commit() # Commit the changes to the database (so that they are saved).
#     db.refresh(db_group) # Refresh your instance (so that it contains any new data from the database, like the generated ID)
#     return db_group


# Transformers from dict to model (TBD)
def to_expense(dict):
    expense_instance = models.Expense(

    )
    return expense_instance