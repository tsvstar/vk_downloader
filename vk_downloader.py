# coding=utf8

# UNIVERSAL VK DOWNLOADER - message, wall, photo, mp3; +restore messages

# script.py LOGIN PASSWORD [uid=x,uid=y,chat=z]

import sys,os,traceback
import tsv_utils as util
from requests import RequestException

def waitkey():
    util.say("Нажми любую кнопку для продолжения")
    util.getchar()


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
    import vk_downloader_V7

except util.FatalError as e:
    util.say( unicode(e) )
    #print traceback.print_exc()     #file=sys.stdout)
except util.OkExit as e:
    util.say( unicode(e) )
    #sys.exit(0)
except KeyboardInterrupt as e:
    util.say("\n^C - выполнение программы прервано")
except RequestException as e:
    util.say( "Ошибка сети: %s", e )
except Exception as e:
    print e
    print traceback.print_exc()     #file=sys.stdout)

waitkey()
