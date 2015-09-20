# coding=utf8
"""
 VK UTILS:

 * Authorization procedures:
        VKSignIn( USER_LOGIN, interactive = True ) - sign in (with respecting config options) to primary login
        VKSignInSecondary( interactive = True )    - sign in (with respecting config options) to primary login

        VKLoginByToken( FILE_AUTH, FILE_AUTH_BAK ) - authorize using stored token
        VKLoginByPassword( USER_LOGIN, fldPwd, fldPwdEncoded, FileAuth, interactive) - authorize using login/pwd (ask if interactive)
        VKSaveToken( vk_api, FILE_AUTH )           - store token after authorization

 * Profiles cache:
        profiles = { int_id: [ first_name, last_name] } - contain actually loaded profiles info
        prof_id = get_profile( prof_id )                - load info about user/group profile if not exists
        batch_preload( preload, isGroup = None )        - load info about multiple profiles
        text = make_profilehtml( prof_id )              - get full name of profile in html appearance
        text = make_profiletext( prof_id )              - get full name of profile in plain text appearance

 * Batch functions:
    class BatchExecutor     - to quickly make several commands in the row
	class CachedVKAPI		- transparent wrapper to vk.api which allow to cache query answers and
"""


import os, vk
import config, tsv_utils as util

# Cache of secondary login
secondary = { 'vk_api': None, 'me': None, 'USER_PASSWORD': '' }

"""
===============================================
*           AUTHORIZATION FUNCTIONS           *
===============================================
"""



"""========================================="""
def VKLoginByToken( FILE_AUTH, FILE_AUTH_BAK ):
    vk_api, me = None, None
    if not os.path.exists( FILE_AUTH ):
        ##print "No %s file token exists" % FILE_AUTH
        return vk_api, me, False

    ##print "..try to use token authorization (to remain offline)"
    #check auth
    try:
        with open(FILE_AUTH,'r') as f:
            first = f.readlines()[0]
            vk_api = vk.API( access_token=first, timeout=5 )
            print vk_api

        answer = vk_api.users.get()[0]
        me = answer[u'id']
        _add_profile( me, answer )
        util.say( "Залогинены в offline-режиме как %s", config.CONFIG['USER_LOGIN'] )
    except Exception as e:
        util.DBG.TODO( e )
        vk_api = None
    if vk_api is not None and FILE_AUTH_BAK is not None:
        with open(FILE_AUTH_BAK,'wb') as fout:
            fout.write(first)
    return vk_api, me, False


"""========================================="""

# Login by Password:
#    USER_LOGIN         - login
#    fldPwd             - name of config option with unencrypted password (if None than only encrypted used)
#    fldPwdEncoded      - name of config option with encrypted password
#    FileAuth          - if given, then delete this token (to delete expired/wrong token)
#    interactive        - if True then ask password if it is not given
#
# RETURN:
#   vk_api, me_id, USER_PASSWORD
#   raise error if can't authorize
def VKLoginByPassword( USER_LOGIN, fldPwd = None, fldPwdEncoded='USER_PASSWORD_ENC', FileAuth = None, interactive = True):
    global token

    PWD_ENC =  config.CONFIG.get( fldPwdEncoded, '' )
    USER_PASSWORD = util.str_decrypt64( PWD_ENC, USER_LOGIN )
    if fldPwd and USER_PASSWORD =='':
        USER_PASSWORD = config.CONFIG.get( fldPwd, '' )

    util.say( "Авторизуемся как %s", USER_LOGIN )
    if FileAuth and os.path.isfile( FileAuth ):
        os.unlink( FileAuth )

    WAS_PWD_ENC = PWD_ENC
    while True:
      while interactive and (USER_PASSWORD==''):
         USER_PASSWORD = util.getinput( util.unicformat("Введите пароль для '%s': ", USER_LOGIN) )
         PWD_ENC = util.str_crypt64( USER_PASSWORD, USER_LOGIN )
      try:
         vk_api = vk.API( config.CONFIG['APP_ID'], USER_LOGIN, USER_PASSWORD, scope='offline,messages,groups,photos,audio,video,wall,status,friends', timeout=5)
         if not interactive:
                break
         token = USER_LOGIN + '|'+ USER_PASSWORD
         if PWD_ENC!='' and WAS_PWD_ENC!=PWD_ENC and util.confirm("Вы хотите запомнить пароль(y/n)?"):
            with open(config.CFGFILE, "at") as cfgfile:
                cfgfile.write('%s="%s"\n' % ( fldPwdEncoded, PWD_ENC ) )
         break
      except Exception as e:
         util.DBG.say( "ERROR: %s\n", e )
         USER_PASSWORD =''

    answer = vk_api.users.get()[0]
    me = answer[u'id']
    _add_profile( me, answer )

    return vk_api, me, USER_PASSWORD

"""========================================="""
def VKSaveToken( vk_api, FileAuth ):
    #remember token
    if not config.CONFIG['SKIP_AUTH_TOKEN']:
        with open(FileAuth,'w') as f:
            f.write(str(vk_api.access_token))

def _VKGetAUTHFile( USER_LOGIN ):
  return "./__vk.token-%s" % USER_LOGIN


"""========================================="""
def VKSignInSecondary( interactive ):
  global secondary

  try:
     if secondary['vk_api'] is not None:
        raise util.OkExit('')

     secondary['USER_PASSWORD'] = ''
     USER_LOGIN2 = config.CONFIG.get(SECONDARY_LOGIN, '')
     if not USER_LOGIN2:
        raise FatalError('No login found')
     FILE_AUTH2 = _VKGetAUTHFile(USER_LOGIN2)
     if not config.CONFIG['SKIP_AUTH_TOKEN']:
        vk_api2, me2, _ = VKLoginByToken(  FILE_AUTH, None )
     if vk_api2 is None:
        vk_api2, me2, USER_PASSWORD2 = VKLoginByPassword( USER_LOGIN2, 'SECONDARY_PWD', 'SECONDARY_PWD_ENC', FileAuth = None, interactive = interactive )
     VKSaveToken( vk_api2, FILE_AUTH2 )

     secondary = { 'vk_api': vk_api2, 'me': me2, 'USER_PASSWORD': USER_PASSWORD2 }
  except Exception:
        pass
  return secondary['vk_api'], secondary['me'], secondary['USER_PASSWORD']


"""========================================="""
def VKSignIn( USER_LOGIN, interactive = True ):
  #global vk_api, me, USER_PASSWORD

  vk_api = None
  USER_PASSWORD = ''
  FILE_AUTH   = _VKGetAUTHFile(USER_LOGIN)
  FILE_AUTH_BAK = FILE_AUTH + '.bak'
  if not config.CONFIG['SKIP_AUTH_TOKEN']:
     vk_api, me, _ = VKLoginByToken(  FILE_AUTH, FILE_AUTH_BAK )
     if vk_api is None:
         vk_api, me, _ = VKLoginByToken( FILE_AUTH_BAK, FILE_AUTH )

  if vk_api is None:
    keep_offline = config.CONFIG['INVISIBLE_MODE']
    # KEEP_OFFLINE=-1 - only token-authorization is allowed (completely invisible)
    if keep_offline<0:
        raise util.FatalError('Ошибка авторизации - невозмозможно войти в режиме полной невидимки (отсутствует или неверный токен)')
    # KEEP_OFFLINE>0 - if user with id "KEEP_OFFLINE" is online than full auth is allowed
    if keep_offline>0:
        try:
           vk_api2, me2, _ = VKSignInSecondary( interactive = False )
           me_status = vk_api2.users.get( user_id=keep_offline, fields='online' )[0]
           ##print "Status of %d is %s" % ( keep_offline, 'ONLINE' if me[u'online'] else 'OFFLINE' )
           if not me_status[u'online']:
             raise util.FatalError('')
        except Exception as e:
              util.DBG.TODO( e )  # @tsv
              raise util.FatalError('Ошибка авторизации - скрытый вход невозмозможен(отсутствует или неверный токен и вы не онлайн сейчас)')


    try:
        ##util.say( "..full authorize.." )
        vk_api, me, USER_PASSWORD = VKLoginByPassword( USER_LOGIN, 'USER_PASSWORD', 'USER_PASSWORD_ENC', FILE_AUTH, interactive = interactive )
        VKSaveToken( vk_api, FILE_AUTH )
        VKSaveToken( vk_api, FILE_AUTH_BAK )
    except Exception as e:
        util.DBG.TODO( e ) # @tsv
        raise util.FatalError('Ошибка авторизации - неверный пароль')

  return vk_api, me, USER_PASSWORD



"""
===============================================
*           PROCESSING PROFILES               *
===============================================
"""

profiles = {}
lazy_profile_batch = []

# AUXILARY FUNCTION
def _add_profile( id, answ ):
    if id in profiles:
        return
    v = []
    if id >= 0:
        v.append( util.str_encode( answ[u'first_name'] ) )
        v.append( util.str_encode( answ[u'last_name'] ) )
    else:
        title = answ.get( u'name', answ.get(u'screen_name', 'group%s'%(-id)) )
        v.append( util.str_encode( title ) )
        v.append( '' )
    profiles[id] = v

# GET (AND LOAD IF NEEDED) PROFILE BY ID
def get_profile( id ):
    try: id = int(id)
    except: pass

    if id in profiles:
        return id

    if lazy_profile_batch:
        batch_preload( set(lazy_profile_batch) )
        globals()['lazy_profile_batch'] = []
        return get_profile( id )

    if id >= 0:
        p = vk_api.users.get( user_id=id )
    else:
        p = vk_api.groups.getById( group_id=-id )
    _add_profile( id, p[0] )
    ##print "profile %s"%id
    return id

# PRELOAD PROFILE CACHE
def batch_preload( preload, isGroup = None ):
    ##dbg_print( 6, "BATCH %s %s" % ( isGroup, str(preload) ) )
    preload = filter( lambda i: i not in profiles, preload )
    if len(preload)==0:
        return

    if isGroup is None:
        #try: preload = map(lambda v: int(v), preload)
        #except: pass
        batch_preload( filter( lambda i: i>=0, preload), False )
        batch_preload( filter( lambda i: i<0,  preload), True )
        return

    if len(preload)>500:
        preload = list(preload)
        batch_preload(preload[:495])
        batch_preload(preload[495:])
        return

    if isGroup:
         answ = vk_api.groups.getById( group_ids = ','.join(map(lambda i: str(abs(i)),preload)) )
    else:
         answ = vk_api.users.get( user_ids = ','.join(map(str,preload)) )
    for item in answ:
        id = int(item[u'id'])
        _add_profile( -id if isGroup else id, item )


def make_profilehtml( prof_id ):
    prof_id = int(prof_id)
    return '<A HREF="https://vk.com/id%d" class=b>%s</A>' % ( prof_id, ' '.join(profiles[get_profile(prof_id)]) )

def make_profiletext( prof_id ):
    return ' '.join(profiles[get_profile(prof_id)])


"""
===============================================
        QUICK PROCESSING USING VKScript

  Usage sample:
    batcher = vk_utils.BatchExecutor(vk_api)
    batcher.users.get(id=me)
    batcher.messages.restore(message_id=409027, _ID_CMD='restore:%s'%40927 )
    res,resmap = batcher.execute()

===============================================
"""

# Batch Command Executor
class BatchExecutor():
    def __init__( self, vk_api ):
        self.vk_api = vk_api
        self.commands = []          # list of triples [ ["cmd:ID", method, kww] ]
        self.result = []            # list of pairs [ ["cmd:ID", answer, errorCode] ]
        self.resultMap = {}         # map: {"cmd:ID": [answer,errorCode(None-no error)]}

    def execute( self ):
        self.result = []
        self.resultMap = {}

        offset = 0
        while (len(self.commands)>25):
            self._execute(self.commands[:25], offset)
            self.commands = self.commands[25:]
            offset += 25
        self._execute(self.commands[:25], offset)
        self.commands = []

        for id, answer, err in self.result:
            self.resultMap[id] = [answer,err]
        return self.result, self.resultMap

    def _execute( self, cmd_list, offset ):
        if not cmd_list:
            return

        code = "var output=[];\n"
        for idx in range(0,len(cmd_list)):
            code += ' var info_%s = API.%s(%s);\n' % (idx,cmd_list[idx][1],repr(cmd_list[idx][2]))
            code += ' output = output + [ ["%s",info_%s,%s] ];\n' % ( cmd_list[idx][0], idx, idx+offset )
        code += "return {output:output}; "

        try:
            result = self.vk_api.execute( code = code.replace("'",'"') ).get('output',[])
        except Exception as e:
            util.DBG.TODO("Exception: %s" % e)

        errors = self.vk_api.data.get('execute_errors',[])
        for ar in result:
            ##print ar, type(ar)
            if ar[1]==False and isinstance(ar[1],type(False)):
                if len(errors):
                    #output is {u'error_code': 15, u'method': u'photos.getAlbums', u'error_msg': u'Access denied: group photos are disabled'}
                    ar[2]=errors.pop(0)
                else:
                    ar[2]=None
                    util.DBG.TODO('Unexepected end of errors list')
            else:
                ar[2]=None
        self.result += result

    def __str__( self ):
        return "BatchExecutor(%x)" % (id(self))

    def __nonzero__(self):
        return 1

    def __getattr__(self, method_name):
        return vk.api.APIMethod(self, method_name)

    def __call__(self, method_name, **kww):
        #if '_ID_CMD' not in kww:
        #    raise util.FatalError('No _ID_CMD defined for batch command')
        ID_CMD = kww.pop('_ID_CMD', None)
        if ID_CMD is None:
            ID_CMD = "%s:%s" % ( method_name, repr(kww).replace("'",""))

        self.commands.append( [ID_CMD, method_name, kww ] )


"""
===============================================
        CACHED vk_api WRAPPER

  Usage sample:
    vk_api = vk_utils.CachedVKAPI(vk_api)
    vk_api._prepare_.users.get(id=me)                       # prepare cache - just give usual command with prefix _prepare_
    vk_api._prepare_.messages.restore(message_id=409027)    #
    vk_api.users.get(id=me)            # just use vk_api as regular one; if query was cached - cached value will be used

  or

    vk_api = vk_utils.CachedVKAPI(vk_api)
    vk_api.doPrepareOnly = True
    vk_api.users.get(id=me)                       # prepare cache - just give usual command with prefix _prepare_
    vk_api.messages.restore(message_id=409027)    #
    vk_api.doPrepareOnly = False
    vk_api.users.get(id=me)            # just use vk_api as regular one; if query was cached - cached value will be used



  Any new batch preloading could be done at any moment. Cache could be cleaned using vk_api.cleanCache()

===============================================
"""
class CachedVKAPI( object ):

    def __init__( self, vk_api, batch_executor = None ):
        self.vk_api = vk_api
        if batch_executor is not None:
            self._prepare_ = batch_executor
        else:
            self._prepare_ = BatchExecutor( vk_api )
        self._resMap = {}
        self.doPrepareOnly = False
        self._rememberUncached = False              # If True - then result of uncached requests will be cached implicitly
                                                    # (this could cause unexpected missing call - because next calls got from cache)

    # execute preparation (calls implicitly if needed)
    def execute( self ):
        _, resMap = self._prepare_.execute()
        self._resMap.update( resMap )

    def cleanCache( self ):
        self._resMap = {}
        self._prepare_.commands = []

    def __str__( self ):
        return "CachedVKAPI(%x)" % (id(self))

    def __nonzero__(self):
        return 1

    def __getattr__(self, method_name):
        if self.doPrepareOnly:
            return getattr( self._prepare_, method_name )
        return vk.api.APIMethod(self, method_name)

    def __call__(self, method_name, **kww):
        ID_CMD = "%s:%s" % ( method_name, repr(kww).replace("'",""))

        if self.doPrepareOnly:
            return self._prepare_.__call__( method_name, **kww )

        # If not cached yet but something was added to queue - execute queue first
        if ID_CMD not in self._resMap:
            if self._prepare_.commands:
                self.execute()

        # If still not in the cache - execute as a single command and place result to the cache
        if ID_CMD not in self._resMap:
            try:
                response = self.vk_api.__call__( method_name, **kww )
            except vk.api.VkAPIMethodError as e:
                if self._rememberUncached:
                    self._resMap[ID_CMD] = [ False, e.error ]
                raise
            if self._rememberUncached:
                self._resMap[ID_CMD] = [ response, None ]
            return response

        # If it is in the cache, get it and emulate execution
        response, error = self._resMap[ID_CMD]
        if error is None:
            return response
        raise vk.api.VkAPIMethodError(error)
