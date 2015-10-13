"""
# put this in a shell
virtualenv .ve
.ve/bin/pip install bottle==0.12.8
.ve/bin/pip install rauth==0.7.1
.ve/bin/pip install gevent==1.0.2
.ve/bin/pip install requests-oauthlib==0.5.0
.ve/bin/pip install SQLAlchemy==1.0.8
.ve/bin/pip install bottle-extras==0.1.0
.ve/bin/pip install bottle-sqlalchemy==0.4.2
.ve/bin/pip install bottle-web2pydal==0.0.1

"""
from gevent import monkey;monkey.patch_all()
import bottle,json
from bottle import route, run, template, request, response, hook
from bottle import abort, redirect, default_app, HTTPResponse, HTTPError
from bottle.ext import sqlalchemy
from sqlalchemy import create_engine, Column, Integer, Sequence, String, Table, MetaData, select
from sqlalchemy.ext.declarative import declarative_base
from uuid import uuid1, uuid4

from config_auth import Config

Base = declarative_base()
#engine = create_engine('sqlite://', echo=True)
engine = create_engine('sqlite:////tmp/my.db', echo=True)

app = default_app()
plugin = sqlalchemy.Plugin(
    engine, # SQLAlchemy engine created with create_engine function.
    Base.metadata, # SQLAlchemy metadata, required only if create=True.
    keyword='db', # Keyword used to inject session database in a route (default 'db').
    create=True, # If it is true, execute `metadata.create_all(engine)` when plugin is applied (default False).
    commit=True, # If it is true, plugin commit changes after route is executed (default True).
    use_kwargs=False # If it is true and keyword is not defined, plugin uses **kwargs argument to inject session database (default False).
)

app.install(plugin)

metadata = MetaData()
users = Table('users', metadata,
              Column('uid',   String, unique=True, index=True, primary_key=True),
              Column('fb_id', String, unique=True, index=True),
              Column('tw_id', String, unique=True, index=True),
              Column('value', String),
              )
users = Table('tokens', metadata,
              Column('uid',   String, unique=True, index=True, primary_key=True),
              Column('token', String, unique=True, index=True),
              )
metadata.create_all(engine) 

conn = engine.connect()

@hook('after_request')
def enable_cors():
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token'

class AuthThing(object):
    def refresh_facebook(_, **kw):
        from rauth import OAuth2Service

        _.update( **kw )

        _.facebook = OAuth2Service(
            client_id    = _.config['fb_app_id'],
            client_secret= _.config['fb_secret'],
            name='facebook',
            authorize_url='https://graph.facebook.com/oauth/authorize',
            access_token_url='https://graph.facebook.com/oauth/access_token',
            base_url='https://graph.facebook.com/')

        _.config['fb_login'] = _.facebook.get_authorize_url(
            response_type= 'code',
            redirect_uri= _.config['fb_redirect'],
        )
        pass
    def facebook_get_auth_session(_,code):
        session = _.facebook.get_auth_session(
            data={'code': code,
                  'redirect_uri': _.config['fb_redirect']})
        return session

    def refresh_twitter(_,**kw):
        _.update( **kw )
        pass

    def __getitem__(_,k): return _.config[k]
    def update(_,**kw):
        if not hasattr(_,'config'): _.config = dict()
        _.config.update( kw )
        pass

    pass

class persistentdict(object):
    def get(_,k,d=None):
        try:
            return _[k]
        except IndexError:
            return d

    def __getitem__(_,k):
        try:
            print "GETITEM", k
            value, = conn.execute(
                select([users.c.value])
                .where(users.c.token == k)).fetchone()
            print "GETITEM V", value
            return json.loads( value )
        except:
            raise IndexError

app.users = persistentdict()

Thing = AuthThing()
Thing.update(**Config)
Thing.refresh_twitter()
Thing.refresh_facebook()

def verify(token=None):
    if token is None:
        token = (request.params.get('access_token',None) or
                 request.headers.get('Authorization',None) or
                 request.get_cookie('access_token'))
        pass
    if token and token.startswith('Bearer '): token = token[7:] # hacky
    print "TOKEN", token
    user = app.users.get(token)
    if not user:
        raise abort(401, "Sorry, access denied.")
    user['token'] = token
    return user

@route('/')
def _():
    return [
        '<li><a href="/fb/login/test">FACEBOOK</a>',
        '<li><a href="/tw/login/test">TWITTER</a>',
        '<li><a href="/anon/login">ANONYMOUS</a>',
    ]

@route('/verify/token/<token>')
def _(token):
    result = verify(token)
    return dict( result = result )

@route('/verify/hello')
def _():
    uid = verify()
    return ["hello"]

@route('/app/main')
def _():
    uid = verify()
    return ["<h1>app main</h1>", str(uid), "<hr>", "<a href='/fb/login/test'>Facebook Re-Login</a>"]

@route('/app/start')
def _():
    uid = verify()
    response.set_cookie('access_token',uid['token'],path='/')
    redirect( "/app/main" )
    return ["hello ", str(uid), '<hr><a href="/app/main?access_token='+
            uid['token']+'">GO TO MAIN</a>']

@route('/anon/login')
def _():
    uid = str( uuid1() )
    token = str( uuid4() )

    jstr = json.dumps( dict( anonymous = True ) )

    conn.execute( users.insert()
                  .values(uid=uid, token=token, value=jstr) )

    redirect_url = Config['main_redirect']
    raise redirect(redirect_url + '?access_token=' + token )

@route('/fb/update')
def _():
    req = dict(request.params)
    Thing.refresh_facebook( req.get('client_id'),
                            req.get('client_secret'),
                            req.get('redirect_uri') )
    return ['OK']

@route('/tw/login/test')
def _(): return ["<a href='/tw/login/xyz'>TWITTER LOGIN</a>"]

@route('/tw/login')
def _(): return dict ( url = '/tw/login/xyz' )

@route('/tw/login/xyz')
def _():
    from requests_oauthlib import OAuth1Session
    Thing.oauth_session = oauth_session = OAuth1Session(Thing['tw_client_key'],
                                                        client_secret=Thing['tw_client_secret'],
                                                        callback_uri=Thing['tw_callback_uri'])
    request_token_url = 'https://api.twitter.com/oauth/request_token'
    oauth_session.fetch_request_token(request_token_url)

    # Second step. Follow this link and authorize
    authorization_url = 'https://api.twitter.com/oauth/authorize'
    raise redirect( oauth_session.authorization_url(authorization_url) )
    #pass

@route('/tw/auth')
def _():
    redirect_response = 'http://ccl.io:9080/tw/auth?' + request.query_string
    Thing.oauth_session.parse_authorization_response(redirect_response)
    access_token_url = 'https://api.twitter.com/oauth/access_token'
    me = Thing.oauth_session.fetch_access_token(access_token_url)
    uid = str( uuid1() )
    token = str( uuid4() )

    tw_id = me['user_id']
    jstr = json.dumps( me )

    try:
        # create a new one
        conn.execute( users.insert()
                      .values(uid=uid, token=token, tw_id=tw_id, value=jstr) )
    except:
        # unless it already exists
        # then just update.  uid stays the same, token gets updated
        conn.execute( users.update()
                      .values( token=token, value=jstr ).where(
                          users.c.tw_id==tw_id ) )
        pass

    redirect_url = Config['main_redirect']
    raise redirect(redirect_url + '?access_token=' + token )

@route('/fb/login/test')
def _(): return ["<a href='%s'>FACEBOOK LOGIN</a>" % Thing['fb_login']]

@route('/fb/login')
def _(): return dict( url = Thing['fb_login'] )

@route('/fb/auth')
def _():
    req = dict(request.params)
    session = Thing.facebook_get_auth_session( req['code'] )
    me = session.get('me').json()
    uid = str( uuid1() )
    token = str( uuid4() )

    fb_id = me['id']
    jstr = json.dumps( me )

    try:
        # create a new one
        conn.execute( users.insert()
                      .values(uid=uid, token=token, fb_id=fb_id, value=jstr) )
    except:
        # unless it already exists
        # then just update.  uid stays the same, token gets updated
        conn.execute( users.update()
                      .values( token=token, value=jstr ).where(
                          users.c.fb_id==fb_id ) )
        pass

    redirect_url = Config['main_redirect']
    raise redirect(redirect_url + '?access_token=' + token )

if __name__=='__main__': run(host='', port=9080, server='gevent')
