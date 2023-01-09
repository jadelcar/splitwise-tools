from typing import List, Union 
from pydantic import BaseModel
from datetime import datetime

# Group
# Base Model
class GroupBase(BaseModel):
    name: str

# Model for creating: For any attributes that we don't want to show when reading (e.g. password/personal data)
class GroupCreate(GroupBase):
    creator_id: int # FK to users.sw_user_id

# Model for reading: Vars that are only available after creation (e.g. id in the database)
class Group(GroupBase):
    id: int
    
    class Config:
        orm_mode = True


# Friend
class MemberBase(BaseModel):
    name: str

class MemberCreate(MemberBase):
    pass
class Member(MemberBase):
    id: int
    group_id: List[Group] = []
    sw_tools_user: bool
    class Config:
        orm_mode = True

# User
class UserBase(BaseModel):
    created_at: str = datetime.utcnow
    username: str

class UserCreate(UserBase):
    password: str
class User(UserBase): 
    id: int
    email: str
    sw_user_id: int
    member_of: List[Group] = []
    friends: List[Member] = []
    class Config:
        orm_mode = True

# Expense
class ExpenseBase(BaseModel):
    id: int
    
class ExpenseCreate(ExpenseBase):
    created_at: str = datetime.utcnow
    
class Expense(ExpenseBase): 
    sw_id: int
    description: str
    date: datetime
    amount: float
    currency: str
    payer_id: int
    all_equal: bool
    split_type: str
    sw_id: int

    members: List[Member] = []
    class Config:
        orm_mode = True

# Upload
class UploadBase(BaseModel):
    id: int
    
class UploadCreate(UploadBase):
    created_at: str = datetime.utcnow
    creator_id: int
    
class Upload(UploadBase): 
    expenses: List[Expense] = []
    class Config:
        orm_mode = True
