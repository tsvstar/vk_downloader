# coding=utf8

import re
import time
import warnings

import sys      # for stdout

from vk.utils import make_handy

try:
    from urlparse import urlparse, parse_qsl  # Python 2
except ImportError:
    from urllib.parse import urlparse, parse_qsl  # Python 3

try:
    import simplejson as json
except ImportError:
    import json

import requests

# vk.com API Errors
INTERNAL_SERVER_ERROR = 10  # Invalid access token
CAPTCHA_IS_NEEDED = 14
TOO_MANY_REQUESTS = 6

""" Improvements:
            dynamic pause between reqests + re-request if TOO_MANY_REQUESTS
            progress (show_blink)
            _NON_FATAL flag for method
            logging
"""

RE_LOGIN_HASH = re.compile(r'name="lg_h" value="([a-z0-9]+)"')
def search_re(reg, string):
    s = reg.search(string)
    if s:
        return s.groups()[0]

""" ========== DEBUG =============== """

import os, codecs, time,traceback

LOG_DIR = './LOG_TRACE'
LOG_FILE = '%s/vk_api.log' % LOG_DIR

def SayToLog( text, tracebackLog = True ):
    #return
    with codecs.open(LOG_FILE,'ab','utf-8') as f:
        ts = time.strftime("%d.%m.%y %H:%M:%S")
        f.write( "%s [%05x] %s\n" % (ts, os.getpid(), text ) )
        if not tracebackLog:
            return
        for stack in list(reversed(traceback.extract_stack()))[3:-2]:
          f.write("\t%s:%s\t%s %s\n"%stack)
          #f.write("\t%s:%s\t%s\n"%(stack[0],stack[1],stack[2]))
        #f.write( repr(list(reversed(traceback.extract_stack()))[3:-3])+"\n" )

""" ==================== """

def json_iter_parse(response_text):
    decoder = json.JSONDecoder(strict=False)
    idx = 0
    while idx < len(response_text):
        obj, idx = decoder.raw_decode(response_text, idx)
        yield obj



_safe_vkmethods = [ '.get',
                    'messages.getHistory',
                    'photos.getAlbums',
                    'messages.getDialogs',
                    'photos.getAll',
                    'photos.getAllComments',
                    'messages.getById',
                    'likes.getList',
                    'wall.getComments',
                 ]

# Return TRUE if method is non-destructive, so could be repeated safely in case of error
def isMethodSafe( method_name ):
    if ( method_name in _safe_vkmethods ):
        return True
    for s in _safe_vkmethods:
        if s.startswith('.') and method_name.endswith(s):
            return True
    return False


class APISession(object):
    def __init__(self, app_id=None, user_login=None, user_password=None, access_token=None, user_email=None,
                 scope='offline', timeout=1, api_version='5.20'):

        user_login = user_login or user_email


        self.logRequest = True                  # Should log api requests
        self.logAnswer = False                  # Should log api answers

        if self.logAnswer or self.logRequest:
            if not os.path.exists(LOG_DIR):
                os.makedirs(LOG_DIR)
            SayToLog( "vk.API(access_token=%s; user_login=%s; timeout=%s; scope=%s)" % (access_token, user_login, timeout,scope) )

        if (not user_login or not user_password) and not access_token:
            raise ValueError('Arguments user_login and user_password, or access_token are required')

        if user_email:  # deprecated at April 11, 2014
            warnings.simplefilter('once')
            warnings.warn("Use 'user_login' instead of deprecated 'user_email'", DeprecationWarning, stacklevel=2)

        self.app_id = app_id

        self.user_login = user_login
        self.user_password = user_password

        self.access_token = access_token
        self.scope = scope or ''

        self.api_version = api_version
        self._default_timeout = timeout

        self.repeat_on_timeout = 1              # how many times repeat on network timeout safe commands before raise exception
        self.pause = 0.35                       # pause between requests
        self.pause_after_error = self.pause     # pause after 'too many request error'
        self.show_blink = False                 # should be displayed each api request
        self.wasErrorFlag = False               # True if error happens and we need to show '?' as blink

        self.session = requests.Session()
        self.session.headers['Accept'] = 'application/json'
        self.session.headers['Content-Type'] = 'application/x-www-form-urlencoded'

        if not access_token and user_login and user_password:
            self.get_access_token()

    blink=-1
    blink_list = [ '|', '/', '-', '\\', '|', '/', '-', '\\' ]
    def print_blink(self, sym=None):
        APISession.blink = (APISession.blink+1)%len(APISession.blink_list)
        if sym:
            sys.stdout.write( sym + chr(8))
        else:
            sys.stdout.write( APISession.blink_list[APISession.blink] + chr(8))

    def session_get( self, url, blink=True, chunk_size=64*1024, **kww ):
        if not blink:
            response = self.session.get( url, **kww )
            return response, response._content
        result = ''
        response = self.session.get( url, stream=True, **kww )
        for _buffer in response.iter_content(chunk_size):
            result += _buffer
            self.print_blink()
        return response, result

    def get_access_token(self):

        session = requests.Session()

        response = session.get('https://vk.com/')

        # Login
        login_data = {
            'act': 'login',
            'utf8': '1',
            'email': self.user_login,
            'pass': self.user_password,
            'lg_h': search_re(RE_LOGIN_HASH, response.text)	##
        }

        response = session.post('https://login.vk.com', login_data)

        if 'remixsid' in session.cookies:
            pass
        elif 'sid=' in response.url:
            raise VkAuthorizationError('Authorization error (captcha)')
        elif 'security_check' in response.url:
            raise VkAuthorizationError('Authorization error (phone number is needed)')
        elif 'm=1' in response.url:
            raise VkAuthorizationError('Authorization error (bad password)')
        else:
            raise VkAuthorizationError('Unknown authorization error')

        # OAuth2
        oauth_data = {
            'response_type': 'token',
            'client_id': self.app_id,
            'scope': self.scope,
            'display': 'mobile',
        }
        response = session.post('https://oauth.vk.com/authorize', oauth_data)

        ##print response.text.encode('cp866','backslashreplace')

        if 'access_token' not in response.url:
            form_action = re.findall(u'<form method="post" action="(.+?)">', response.text)
            if form_action:
                response = session.get(form_action[0])
            else:
                try:
                    json_data = response.json()
                except ValueError:  # not json in response
                    error_message = 'OAuth2 grant access error'
                else:
                    error_message = 'VK error: [{0}] {1}'.format(
                        json_data['error'],
                        json_data['error_description']
                    )
                session.close()
                raise VkAuthorizationError(error_message)

        session.close()

        parsed_url = urlparse(response.url)
        token_dict = dict(parse_qsl(parsed_url.fragment))
        ##print token_dict
        if 'access_token' in token_dict:
            self.access_token = token_dict['access_token']
            self.expires_in = token_dict['expires_in']
        else:
            raise VkAuthorizationError('OAuth2 authorization error')

    def __getattr__(self, method_name):
        return APIMethod(self, method_name)

    cntrCall = 0
    tr_m = { 'g':'get', 'G': 'getComments', 'C': 'createComment', 'D':'deleteComment' }
    tr_o = { 'p': 'photos', 'w': 'wall', 'a':'audio', 'm':'messages', 'g':'groups','u':'users' }

    def __call__(self, method_name, **method_kwargs):
        now = time.time()
        if self.cntrCall:
            pause = self.pause
            ##print now
            if float(int(now))!=now:
                pause = self.pause - (now - self.prev_tstamp)
            ##print "{%s}"%pause
            if pause>0:
                time.sleep(pause)
        self.prev_tstamp = now
        self.cntrCall += 1
        if method_name[0]=='_':
          method_name = self.tr_o[method_name[1]]+'.'+self.tr_m.get(method_name[2:],method_name[2:])

        if self.show_blink:
            self.print_blink( '?' if self.wasErrorFlag else None )
        if self.logRequest:
            SayToLog( "%s %s(%s)" % ( ( '?' if self.wasErrorFlag else '' ), method_name, str(method_kwargs) ) )
        nonFatalFlag = method_kwargs.pop( '_NON_FATAL', False )
        safeToRerunFlag = method_kwargs.pop( '_SAFE_RERUN', False )
        ##print method_name
        ##print "%s(%s)" % (method_name, repr(method_kwargs))
        response = self.method_request(method_name, safeToRerunFlag=safeToRerunFlag, **method_kwargs)
        response.raise_for_status()
        method_kwargs['_NON_FATAL'] = nonFatalFlag      # push auxilary value back if need repeat method
        method_kwargs['_SAFE_RERUN'] = safeToRerunFlag
        ##sys.stdout.write('!')

        # there are may be 2 dicts in 1 json
        # for example: {'error': ...}{'response': ...}
        errors = []
        error_codes = []
        for data in json_iter_parse(response.text):
            if self.logAnswer:
                SayToLog( "%s %s" %(method_name, data), tracebackLog = False )
            if 'error' in data:
                error_data = data['error']
                if not self.logAnswer:
                    SayToLog( "%s %s" %(method_name, data), tracebackLog = False )
                if error_data['error_code'] == CAPTCHA_IS_NEEDED:
                    if nonFatalFlag:
                        return None
                    return self.captcha_is_needed(error_data, method_name, **method_kwargs)

                error_codes.append(error_data['error_code'])
                errors.append(error_data)

            if 'response' in data:
                for error in errors:
                    warnings.warn(str(error))

                self.pause_after_error = max( self.pause_after_error-self.pause, self.pause )     # reset pause_after_error
                self.wasErrorFlag = False

                # return make_handy(data['response'])
                self.data = data
                return data['response']

        if INTERNAL_SERVER_ERROR in error_codes:  # invalid access token
            self.get_access_token()
            return self(method_name, **method_kwargs)
        elif TOO_MANY_REQUESTS in error_codes:    # too many requests per second
            #print "{..too many requests.. - repeat it}"
            self.wasErrorFlag = True
            ##sys.stdout.write('?')
            self.pause_after_error += max( 0.4, self.pause/2 )
            ##self.pause += 0.05
            ##sys.stdout.write("{%.2f}"%self.pause)
            ##sys.stdout.write("{%.2f}"%self.pause_after_error)
            time.sleep( self.pause_after_error )
            return self(method_name, **method_kwargs)
        else:
            if nonFatalFlag:
                return None
            raise VkAPIMethodError(errors[0])

    def method_request(self, method_name, timeout=None, safeToRerunFlag=False,  **method_kwargs):
        retries = range(0,self.repeat_on_timeout)
        while True:
            try:
                if self.access_token:
                    params = {
                        'access_token': self.access_token,
                        'timestamp': int(time.time()),
                        'v': self.api_version,
                    }
                    params.update(method_kwargs)
                    url = 'https://api.vk.com/method/' + method_name

                ##print ">>%s<< (%s)" % (url, str(params))
                rv = self.session.post(url, params, timeout=timeout or self._default_timeout)
            except requests.Timeout as e:
                ##print "Timeout"
                isSafe = safeToRerunFlag or isMethodSafe( method_name )
                if isSafe:
                    if retries:
                        retries.pop()
                        if self.logRequest:
                            SayToLog( ">>REPEAT BECAUSE OF TIMEOUT (%s try) -  %s(%s)" % ((self.repeat_on_timeout-len(retries)), method_name, str(method_kwargs) ) )
                        continue
                SayToLog( ">>FAIL BECAUSE OF TIMEOUT (%s tries done) -- %s(%s) " % ((self.repeat_on_timeout+1), method_name, str(method_kwargs) ) )
                raise
            break
            ##print "======>>\n%s\n<<======" % rv.text.encode('cp866','backslashreplace')
        return rv

    def captcha_is_needed(self, error_data, method_name, **method_kwargs):
        """
        Default behavior on CAPTCHA is to raise exception
        Reload this in child
        """
        raise VkAPIMethodError(error_data)


class APIMethod(object):
    __slots__ = ['_api_session', '_method_name']

    def __init__(self, api_session, method_name):
        self._api_session = api_session
        self._method_name = method_name

    def __getattr__(self, method_name):
        return APIMethod(self._api_session, self._method_name + '.' + method_name)

    def __call__(self, **method_kwargs):
        return self._api_session(self._method_name, **method_kwargs)


class VkError(Exception):
    pass


class VkAuthorizationError(VkError):
    pass


class VkAPIMethodError(VkError):
    __slots__ = ['error', 'code']

    def __init__(self, error):
        self.error = error
        self.code = error['error_code']
        super(Exception, self).__init__()

    def __str__(self):
        er = { 'error_code':'?', 'error_msg':'no error', 'request_params':'no param'}
        er.update( self.error )
        return "{error_code}. {error_msg}. params = {request_params}".format(**er)
