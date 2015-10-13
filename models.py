from sqlalchemy import create_engine, Column, Integer, Sequence, String, Table, MetaData, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from uuid import uuid1, uuid4

from config_auth import Config

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id    = Column(Integer, primary_key=True)
    uid   = Column(String, unique=True, index=True)
    fb_id = Column(String, unique=True, index=True)
    tw_id = Column(String, unique=True, index=True)
    value = Column(String)

class Token(Base):
    __tablename__ = 'tokens'
    id    = Column(Integer, primary_key=True)
    token = Column(String, unique=True, index=True)
    uid   = Column(String)
