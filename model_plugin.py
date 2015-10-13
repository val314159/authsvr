import bottle,json
from bottle import route, run, template, request, response, hook
from bottle import abort, redirect, default_app, HTTPResponse, HTTPError
from bottle.ext import sqlalchemy
from sqlalchemy import create_engine, Column, Integer, Sequence, String, Table, MetaData, select
from sqlalchemy.ext.declarative import declarative_base

from models import User,Token,Base

from config_auth import Config

app = default_app()

engine = create_engine('sqlite:////tmp/my.db', echo=True)

plugin = sqlalchemy.Plugin( engine, Base.metadata, create=True )
app.install(plugin)

Base.metadata.create_all(engine)
