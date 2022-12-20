from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash, generate_password_hash

from . import models, schemas



def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()


def get_users(db: Session, skip: int = 0, limit: int = 100):
    """Get the first N users in db (default is 100)"""
    return db.query(models.User).offset(skip).limit(limit).all()


def get_groups(db: Session, skip: int = 0, limit: int = 100):
    """Get the first N groups in db (default is 100)"""
    return db.query(models.Group).offset(skip).limit(limit).all()

def get_groups_of_user(db: Session, user_id: int, limit: int = 100):
    """Get the groups where User is a member in 'db' (by default the first 100 groups)"""
    return db.query(models.User.id, models.User.member_of).filter(models.User.id == user_id).limit(limit)

def get_groups_of_sw_user(db: Session, sw_user_id: int, limit: int = 100):
    """Get the groups where User is a member in db (by default the first 100 groups)"""
    return db.query(models.User.id, models.User.member_of).filter(models.User.id == sw_user_id).limit(limit)

def create_user(db: Session, user: schemas.UserCreate):
    new_hashed_password = user.password + generate_password_hash(user.password)
    db_user = models.User(email = user.email, hashed_password = new_hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def create_user(db: Session, user: schemas.UserCreate):
    password_hashed = generate_password_hash(user.password)
    db_user = models.User(username=user.username, hashed_password = password_hashed)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def create_group(db: Session, group: schemas.GroupCreate, user_id: int):
    """Create a group. Requires a sw_user_id, that will appear as creator of the group (creator_id)"""
    # First, we create an instance of the class Group
    # Instead of passing each of the keyword arguments to 'group' and reading each one of them from the Pydantic model, we are generating a dict with the Pydantic model's data with group.dict() and passing these key-value pairs as keyword arguments to the SQLAlchemy Group.
    db_group = models.Group(**group.dict(), owner_id=user_id) 
    db.add(db_group) # Add instance object to the database
    db.commit() # Commit the changes to the database (so that they are saved).
    db.refresh(db_group) # Refresh your instance (so that it contains any new data from the database, like the generated ID)
    return db_group

