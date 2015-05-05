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
        TODO - move this


"""


import os, vk
import config, tsv_utils as util

# Cache of secondary login
secondary = { 'vk_api': None, 'me': None, 'USER_PASSWORD': '' }


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

        me = vk_api.users.get()[0][u'id']
        util.say( "Залогинены в offline-режиме как %s", config.CONFIG['USER_LOGIN'] )
    except Exception as e:
        util.TODO( e )
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
         vk_api = vk.API( config.CONFIG['APP_ID'], USER_LOGIN, USER_PASSWORD, scope='offline,messages,groups,photos,audio,video,friends', timeout=5)
         if not interactive:
                break
         token = USER_LOGIN + '|'+ USER_PASSWORD
         if PWD_ENC!='' and WAS_PWD_ENC!=PWD_ENC and util.confirm("Вы хотите запомнить пароль(y/n)?"):
            with open(config.CFGFILE, "at") as cfgfile:
                cfgfile.write('%s="%s"\n' % ( fldPwdEncoded, PWD_ENC ) )
         break
      except Exception as e:
         util.say( "ERROR: %s\n", e )
         USER_PASSWORD =''

    me = vk_api.users.get()[0][u'id']
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
              util.TODO( e )  # @tsv
              raise util.FatalError('Ошибка авторизации - скрытый вход невозмозможен(отсутствует или неверный токен и вы не онлайн сейчас)')


    try:
        ##util.say( "..full authorize.." )
        vk_api, me, USER_PASSWORD = VKLoginByPassword( USER_LOGIN, 'USER_PASSWORD', 'USER_PASSWORD_ENC', FILE_AUTH, interactive = interactive )
        VKSaveToken( vk_api, FILE_AUTH )
        VKSaveToken( vk_api, FILE_AUTH_BAK )
    except Exception as e:
        util.TODO( e ) # @tsv
        raise util.FatalError('Ошибка авторизации - неверный пароль')

  return vk_api, me, USER_PASSWORD
