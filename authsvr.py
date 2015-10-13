from gevent import monkey;monkey.patch_all()
import os,sys,bottle,json
from bottle import route, run, template, request, response, hook
from bottle import abort, redirect, default_app, HTTPResponse, HTTPError
from bottle.ext import sqlalchemy
from sqlalchemy import create_engine, Column, Integer, Sequence, String, Table, MetaData, select
from sqlalchemy.ext.declarative import declarative_base
from uuid import uuid1, uuid4

from models_plugin import engine
from models import Base,User,Token

from sqlalchemy.orm import sessionmaker

from config_auth import Config
import cors

app = default_app()

Session = sessionmaker(autoflush=True,autocommit=True)
Session.configure(bind=engine)

app.db_session = Session()
app.add        = app.db_session.add
app.query      = app.db_session.query

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

    def twitter_get_auth_session(_, query_string):
        redirect_response = 'http://ccl.io:9080/tw/auth?' + query_string
        _.oauth_session.parse_authorization_response(redirect_response)
        access_token_url = 'https://api.twitter.com/oauth/access_token'
        me = _.oauth_session.fetch_access_token(access_token_url)
        return me

    def __getitem__(_,k): return _.config[k]
    def update(_,**kw):
        if not hasattr(_,'config'): _.config = dict()
        _.config.update( kw )
        pass

    pass

Thing = AuthThing()
Thing.update(**Config)
Thing.refresh_twitter()
Thing.refresh_facebook()

def verify(token=None, load_user=False):
    if token is None:
        token = (request.params.get('access_token',None) or
                 request.headers.get('Authorization',None) or
                 request.get_cookie('access_token'))
        pass
    if token and token.startswith('Bearer '): token = token[7:] # hacky
    tok = app.db_session.query(Token).filter_by(token=token).first()
    if not tok:
        raise abort(401, "Sorry, access denied.")
    if not load_user:
        return token
    return tok
    user = app.db_session.query(User).filter_by(uid=tok.uid).first()
    if not user:
        raise abort(401, "Sorry, access denied.")
    return token, user

LINKS = [
    '<li><a href="/fb/login/test">FACEBOOK</a>',
    '<li><a href="/tw/login/test">TWITTER</a>',
    '<li><a href="/anon/login">ANONYMOUS</a>',
]

@route('/')
def _():
    return LINKS

@route('/verify/token/<token>')
def _(token):
    result = verify(token)
    return dict( result = result )

@route('/verify/hello')
def _():
    verify()
    return ["hello"]

@route('/app/main')
def _():
    token = verify()

    tok = verify(load_user=True)

    print >>sys.stderr, "TOK --------------------------------- ", repr(tok)
    print >>sys.stderr, "TOK --------------------------------- ", repr(tok.token)
    print >>sys.stderr, "TOK --------------------------------- ", repr(tok.uid)

    user = app.db_session.query(User).filter_by(uid=tok.uid).first()
    print >>sys.stderr, "USER --------------------------------- ", repr(tok.uid)
    print >>sys.stderr, "USER --------------------------------- ", repr(tok.uid)
    print "USER", repr(user)
    print "USER", repr(user.value)

    return ["<h1>app main</h1>", str((token)), "<hr>"] + LINKS


    token, user = verify(load_user=True)
    return ["<h1>app main</h1>", str((token,user)), "<hr>"] + LINKS

@route('/app/start')
def _():
    token = verify()
    response.set_cookie('access_token',token,path='/')
    raise redirect( "/app/main" )

@route('/anon/login')
def _():
    uid = str( uuid1() )
    token = str( uuid4() )

    jstr = json.dumps( dict( anonymous = True ) )

    user = User(uid=uid, value=jstr)
    app.db_session.add( user )

    tok  = Token(token=token,uid=uid)
    app.db_session.add( tok )
    app.db_session.flush()

    redirect_url = Config['main_redirect']
    raise redirect(redirect_url + '?access_token=' + token )

@route('/settings/update')
def _():
    req = dict(request.params)
    Thing.refresh_facebook( *req )
    Thing.refresh_twitter()
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
    me = Thing.twitter_get_auth_session( request.query_string )

    uid = str( uuid1() )
    token = str( uuid4() )

    tw_id = me['user_id']
    jstr = json.dumps( me )

    user = app.db_session.query(User).filter_by(tw_id=tw_id).first()
    if user:
        user.value = jstr
        app.db_session.merge( user )
    else:
        user = User(uid=uid, tw_id=tw_id, value=jstr)
        app.db_session.add( user )
        pass

    tok  = Token(token=token,uid=user.uid)
    app.db_session.add( tok )
    app.db_session.flush()

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

    user = app.db_session.query(User).filter_by(fb_id=fb_id).first()
    if user:
        user.value = jstr
        app.db_session.merge( user )
    else:
        user = User(uid=uid, fb_id=fb_id, value=jstr)
        app.db_session.add( user )
        pass

    tok  = Token(token=token,uid=user.uid)
    app.db_session.add( tok )
    app.db_session.flush()

    redirect_url = Config['main_redirect']
    raise redirect(redirect_url + '?access_token=' + token )

if __name__=='__main__': run(host='', port=9080, server='gevent')
