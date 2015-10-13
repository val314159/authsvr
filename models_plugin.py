import bottle
from bottle.ext import sqlalchemy
from sqlalchemy import create_engine
from models import Base
from config_auth import Config

app=bottle.default_app()
engine = create_engine('sqlite:///'+Config['db_file'], echo=True)
app.install( sqlalchemy.Plugin(engine, Base.metadata, create=True) )
Base.metadata.create_all( engine )
