from sqlalchemy import Table, Boolean, Column, ForeignKey, Integer, String, DateTime, Numeric
from sqlalchemy.orm import relationship, backref
from datetime import datetime
from .database import Base

# Association table between groups and members
group_member = Table('group_member', Base.metadata,
                    Column('group_id', Integer, ForeignKey('groups.id'), primary_key = True),
                    Column('member_id', Integer, ForeignKey('members.id'), primary_key = True),
                    )

# Association table between uploads and expenses
uploads_expenses = Table('uploads_expenses', Base.metadata,
                    Column('upload_id', Integer, ForeignKey('uploads.id'), primary_key = True),
                    Column('expense_id', Integer, ForeignKey('expenses.id'), primary_key = True),
                    )

class User(Base):
    __tablename__ = "users" 
    id = Column(Integer, primary_key=True, index = True)
    username = Column(String, nullable=False)
    hashed_password = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    email     = Column(String) 

    def __repr__(self):
        return f'<User "{self.username}">'

class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True, index = True, autoincrement=True)
    name = Column(String)
    sw_id = Column(Integer)
    members = relationship(
        "Member", # To what class we point
        secondary = group_member,
        back_populates = "member_of_groups")

    def __repr__(self):
        return f'<Group "{self.id}", name: {self.name}>'

class Upload(Base):
    __tablename__ = "uploads"
    id = Column(Integer, primary_key=True, index = True)
    creator_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    group_id = Column(Integer, ForeignKey('groups.id'))
    expenses = relationship(
        "Expense",
        secondary = uploads_expenses,
        back_populates = "uploads",
    )
    def __repr__(self):
        return f'<Upload ID {self.id}, Creator: {self.creator_id}>'

class Member(Base):
    __tablename__ = "members"
    id = Column(Integer, primary_key=True, index = True, autoincrement=True)
    sw_id = Column(Integer)
    name = Column(String)
    member_of_groups = relationship(
        "Group", # To what class we point
        secondary = group_member, #
        back_populates = "members")
    def __repr__(self):
        return f'<Member "{self.id}", name: {self.name}>'
  
class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True, index = True)
    upload_id = Column(Integer, ForeignKey('uploads.id'))
    sw_id = Column(Integer)
    within_upload_id = Column(Integer)
    description = Column(String, nullable = False)
    date = Column(DateTime, nullable = False)
    amount = Column(Numeric, nullable = False)
    currency = Column(String, nullable = False)
    payer_id = Column(Integer, nullable = False) # FK to members
    all_equal = Column(Boolean, nullable = False)
    split_type = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    creator_id = Column(Integer, nullable = False)
    uploads = relationship(
        "Upload",
        secondary = uploads_expenses,
        back_populates = "expenses"
    )
    def __repr__(self):
        return f'<Expense {self.id}, Descr: {self.description}>'

class ExpenseMember(Base):
    __tablename__ = "expense_members"
    id = Column(Integer, primary_key=True)
    
    member_id = Column(Integer, ForeignKey(Member.id))
    member = relationship('Member', backref = backref('expense_members', passive_deletes='all'))    
    
    expense_id = Column(Integer, ForeignKey(Expense.id))
    expense = relationship('Expense', backref = backref('expense_members', passive_deletes='all'))    
    
    share_owed = Column(Numeric)
    share_paid = Column(Numeric)
    def __repr__(self):
        return f'<Expense-member {self.id}, expense: {self.expense_id}, member: {self.member_id}>'

