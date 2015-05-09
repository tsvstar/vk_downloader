# coding=utf8

# UNIVERSAL VK DOWNLOADER - message, wall, photo, mp3; +restore messages

# script.py LOGIN PASSWORD [uid=x,uid=y,chat=z]

import sys,os,traceback
import config
import tsv_utils as util
from requests import RequestException

def waitkey():
    util.say("Нажми любую кнопку для продолжения")
    util.getchar()

def main():
    errorFlag = True
    util.DBG.level = util.DBG.TRACE
    util.DBG.logfile_name = './LOG_TRACE/vk_downloader'
    try:
      try:
        # Set console encoding
        util.init_console()
        sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

        # initialize argv
        sysargv = util.getSysArgv()
        ARGV = util.getWinSysArgv()

        util.DBG.important( u">>> RUN VK_DOWNLOADER[%x]. Cmd: %s", [os.getpid(),' '.join(ARGV) ])

        # ..do any util.sysargv/ARGV changes here
        #


        cfg_loaded  = config.load_config( config.CFGFILE )                    # load config
        argv_loaded = config.InitConfigFromARGV( startsfrom = 4 )             # load arguments from ARGV
        ##util.DBG.trace( util.debugDump(config.CONFIG, False) )
        try:                                                                  # extend console - made after first load config to load CONSOLE_SIZE
            import util_console
            c_w, c_h = (config.CONFIG['CONSOLE_SIZE'].split(':')+['0'])[:2]
            util_console.extendConsoleSize( c_w, c_h )
        except:
            pass
        if cfg_loaded:
            print "Loaded values from %s: %s" % ( config.CFGFILE, str(cfg_loaded) )
        if argv_loaded:
            print "Loaded values from ARGV: %s" % str(argv_loaded)

        util.CONFIG = config.CONFIG                                         # initialize util.CONFIG (needed to process 'MACHINE' key)


        # do action
        import vk_utils
        import vk_downloader_V7 as myvk

        WHAT, RESTORE_FLAG, MAIN_PROFILE = myvk.Initialize()
        LOGIN = myvk.VKEnterLogin()
        myvk.InitializeDir( LOGIN, WHAT )
        myvk.vk_api, myvk.me, myvk.USER_PASSWORD = vk_utils.VKSignIn( LOGIN )
        vk_utils.vk_api = myvk.vk_api               # required for batch_preload

        me = myvk.me
        if config.CONFIG['APP_ID']==config.dflt_config['APP_ID']:
          # Проверка доверенных пользователей
          #@APP_CHECK@
            raise util.FatalError('Неизвестный APP_ID - должен быть указан в vk.cfg')

        myvk.load_queue = []				        # Init "load_queue"
        if WHAT=='ask':
            WHAT, RESTORE_FLAG, MAIN_PROFILE = myvk.executeAsk()    # "Ask" action
            myvk.InitializeDir( LOGIN, WHAT )                       # update dirs

        myvk.PrepareLoadQueue( WHAT, RESTORE_FLAG, MAIN_PROFILE )
        myvk.PreprocessLoadQueue()
        if RESTORE_FLAG:
            myvk.executeRESTORE( WHAT, RESTORE_FLAG )
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

      except Exception as e:
        util.DBG.important("EXCEPTION %s for [%x]: %s\n%s", [type(e), os.getpid(), str(e), traceback.format_exc()])
        raise

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
        util.say( unicode(e) )
        sys.stderr.write("%s: %s\n"%(type(e), str(e)))
        print traceback.print_exc()     #file=sys.stdout)

    util.DBG.info( u"<<< END VK_DOWNLOADER[%x]\n", [os.getpid() ])

    isWaitFlag = True
    try:
       isWaitFlag = config.CONFIG.get( 'WAIT_AFTER', True )
    except:
        pass

    if isWaitFlag:
        waitkey()

if __name__ == '__main__':
    main()
