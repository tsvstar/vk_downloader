# coding=utf8

# UNIVERSAL VK DOWNLOADER - message, wall, photo, mp3; +restore messages

# script.py LOGIN PASSWORD [uid=x,uid=y,chat=z]

import sys,os,traceback
import tsv_utils as util
from requests import RequestException

def waitkey():
    util.say("Нажми любую кнопку для продолжения")
    util.getchar()

errorFlag = True
try:

    # Set console encoding
    util.init_console()
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

    # initialize argv
    sysargv = util.getSysArgv()
    ARGV = util.getWinSysArgv()

    # ..do any util.sysargv/ARGV changes here
    #

    # do action
    import vk_downloader_V7 as myvk

    WHAT, RESTORE_FLAG, MAIN_PROFILE = myvk.Initialize()
    LOGIN = myvk.VKEnterLogin()
    myvk.InitializeDir( LOGIN, WHAT )
    myvk.VKSignIn( LOGIN )

    myvk.load_queue = []				            # Init "load_queue"
    if WHAT=='ask':
        WHAT, RESTORE_FLAG, MAIN_PROFILE = myvk.executeAsk()    # "Ask" action
        myvk.InitializeDir( LOGIN, WHAT )                       # update dirs

    myvk.PrepareLoadQueue( WHAT, RESTORE_FLAG, MAIN_PROFILE )
    myvk.PreprocessLoadQueue()
    if RESTORE_FLAG:
        myvk.executeRESTORE( WHAT )
    elif WHAT=='video':
        myvk.executeVIDEO()
    elif WHAT=='photo':
        myvk.vk_api.show_blink = True
        myvk.executePHOTO()
    else:
        myvk.vk_api.show_blink = True
        myvk.PrepareMediaConfigs()

        if WHAT=='mp3':
            myvk.executeMP3()
        elif WHAT=='wall':
            myvk.executeWALL()
        elif WHAT=='delete':
            myvk.executeDELETE()
        elif WHAT=='message':
            myvk.executeMESSAGE()
        else:
            raise util.FatalError( util.unicformat("Действие '%s' еще не обрабатывается", WHAT ) )
        errorFlag = False

except util.FatalError as e:
    util.say( unicode(e) )
    #print traceback.print_exc()     #file=sys.stdout)
except util.OkExit as e:
    errorFlag = False
    util.say( unicode(e) )
    #sys.exit(0)
except KeyboardInterrupt as e:
    util.say("\n^C - выполнение программы прервано")
except RequestException as e:
    util.say( "Ошибка сети: %s", e )
except Exception as e:
    print e
    print traceback.print_exc()     #file=sys.stdout)

isWaitFlag = True
try:
   isWaitFlag = myvk.CONFIG.get( 'WAIT_AFTER', True )
except:
    pass

if isWaitFlag:
    waitkey()
