from sqlalchemy import Table, Boolean, Column, ForeignKey, Integer, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from .database import Base

# Classes created inherit from class 'Base', which has properties that are important for FastAPI to work

# Relationships: relationship("NameClass", back_populates = "attribute in class")

# Docs:
    # https://www.digitalocean.com/community/tutorials/how-to-use-many-to-many-database-relationships-with-flask-sqlalchemy
    # https://www.gormanalysis.com/blog/many-to-many-relationships-in-fastapi/

# Association table between groups and members
group_member = Table('group_member', Base.metadata,
                    Column('group_id', Integer, ForeignKey('groups.id'), primary_key = True),
                    Column('member_id', Integer, ForeignKey('members.id'), primary_key = True),
                    )
    # Same as above, but using models
        # class GroupMember():
        #     __tablename__ = "group_members"
        #     id = Column(Integer, primary_key=True, index = True)
        #     group_id = Column(Integer, ForeignKey("groups.id"))
        #     member_id = Column(Integer, ForeignKey("members.id"))

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
    id = Column(Integer, primary_key=True, index = True)
    name = Column(String)

    members = relationship(
        "Member", # To what class we point
        secondary = group_member,
        back_populates = "member_of")
    def __repr__(self):
        return f'<Group "{self.id}", name: {self.name}>'

class Member(Base):
    __tablename__ = "members"
    id = Column(Integer, primary_key=True, index = True)
    name = Column(String)
    member_of = relationship(
        "Group", # To what class we point
        secondary = group_member, #
        back_populates = "members")
  
    def __repr__(self):
        return f'<Member "{self.id}", name: {self.name}>'


""" Example from FastAPI
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)

    items = relationship("Item", back_populates="owner")


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User", back_populates="items")
"""