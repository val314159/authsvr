"""
# put this in a shell
virtualenv .ve
.ve/bin/pip install bottle==0.12.8
.ve/bin/pip install rauth==0.7.1
.ve/bin/pip install gevent==1.0.2
.ve/bin/pip install requests-oauthlib==0.5.0

"""
from gevent import monkey;monkey.patch_all()
import json
from bottle import route, run, template, request, response, hook
from bottle import abort, redirect, default_app, HTTPResponse
from uuid import uuid1, uuid4

from config_auth import Config

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

class persistentdict(dict):
    def __init__(_,*a,**kw):
        import sqlite3
        dict.__init__(_,*a,**kw)
        print "INIT", (a, kw)
        _.db = sqlite3.connect(Config.get('db_file','/tmp/authsvr.db'))
        _.db.execute('CREATE TABLE IF NOT EXISTS user' +
                     '(k text PRIMARY KEY, v text)')
        for k,v in _.db.execute('SELECT k,v FROM user'):
            print "K AND V", repr( (k,v) )
            _._setitem( k, json.loads(v) )
            pass
        pass
    def _setitem(_,k,v): return dict.__setitem__( _, k, v )
    def __setitem__(_,k,v):
        ret = _._setitem( k, v )
        print "SAVE", (k, json.dumps(v))
        _.db.execute('INSERT INTO user (k,v) VALUES (?,?)', 
                     (k,json.dumps(v)))
        _.db.commit()
        return ret
    pass

app = default_app()
if Config.get('db_type') == 'sqlite3':
    app.users = persistentdict()
elif not Config.get('db_type'):
    app.users = dict()
    pass

Thing = AuthThing()
Thing.update(**Config)
Thing.refresh_twitter()
Thing.refresh_facebook()

def verify(token=None):
    print '      verify'
    print '*'*40
    print 1, 2, 3, dict(request.headers)
    print 4, 5, 6, dict(request.cookies)
    print '*'*40
    print
    if token is None:
        token = (request.params.get('access_token',None) or
                 request.headers.get('Authorization',None) or
                 request.get_cookie('access_token'))
        pass
    if token and token.startswith('Bearer '): token = token[7:] # hacky
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
    print "UID", uid
    response.set_cookie('access_token',uid['token'],path='/')
    redirect( "/app/main" )
    return ["hello ", str(uid), '<hr><a href="/app/main?access_token='+
            uid['token']+'">GO TO MAIN</a>']

@route('/anon/login')
@route('/anonymous/login')
def _():
    uid = str( uuid1() )
    token = str( uuid4() )
    app.users[token] = dict( uid = uid, anonymous = True )
    result = dict( app.users[token], token = token )
    redirect_url = Config['main_redirect']
    raise redirect(redirect_url + '?access_token=' + token )
    #return dict( result = result )

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
    app.users[token] = dict( uid = uid, twitter = me )
    result = dict( app.users[token], token=token )
    redirect_url = Config['main_redirect']
    raise redirect(redirect_url + '?access_token=' + token )
    #return dict( result = result )

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
    app.users[token] = dict( uid = uid, facebook = me )
    result = dict( app.users[token], token=token )
    redirect_url = Config['main_redirect']
    raise redirect(redirect_url + '?access_token=' + token )
    #return dict( result = result )

if __name__=='__main__': run(host='', port=9080, server='gevent')
