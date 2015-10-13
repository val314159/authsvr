from gevent import monkey;monkey.patch_all()
import bottle,json
from bottle import route, run, template, request, response, hook
from bottle import abort, redirect, default_app, HTTPResponse, HTTPError
from bottle.ext import sqlalchemy
from sqlalchemy import create_engine, Column, Integer, Sequence, String, Table, MetaData, select
from sqlalchemy.ext.declarative import declarative_base
from uuid import uuid1, uuid4

from model_plugin import engine
from models import User,Token,Base

from config_auth import Config

app = default_app()

@hook('after_request')
def enable_cors():
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token'
