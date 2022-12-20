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
    sw_user_id: int
    member_of: List[Group] = []
    friends: List[Member] = []
    email: str
    class Config:
        orm_mode = True
