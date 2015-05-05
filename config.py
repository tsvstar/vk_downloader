# coding=utf8

import os.path
import tsv_utils as util


CFGFILE = "./vk.cfg"

# Default values of  CONFIG. Only matched here will be parsed to globals()
dflt_config = {
    'APP_ID':            '#@MY_TOKEN@', # aka API/Client id
    'USER_LOGIN':        '',        # user email or phone number
    'USER_PASSWORD':     '',

    'MAIN_PROFILE':      '*',       # Which user/chat history load (*=all) {usually given in command line}

    'DOWNLOAD_VIDEO':    True,      # Store video for later download
    'VIDEO_MAX_SIZE':    500,       # Maximum resolution to download
    'DAYSBEFORE':        700,       # How deeply load history
    'IF_DELETE':         None,      # Delete messages: None - ask, 1-delete, -1=keep_and_do_not_delete, 0=keep_but_delete_later
    'DOWNLOAD_MP3':      True,      # True = download mp3 in messages/wall
    'DOWNLOAD_MP3_ONCE': True,      # True - if mp3 was dloaded then remember and do not download even if it was deleted locally {REMEMBER_SKIP_MP3}
    'SKIP_EXISTED_FILE': True,      # If img/media exists then do not update it

    'WRITE_MSGID':       False,      # DBG: print message id
    'SHOW_SKIPED_MEDIA': False,      # DBG: print MEDIA file name

    'LOAD_COMMENTS':     True,      # Need to Download comments for wall
    'LOAD_LIKES':        False,     # Need to Download likes for wall
    'DOWNLOAD_AS_HTML':  True,      # Download as plain text or as html
    'SEPARATE_TEXT':     'year',    # How to separate media [None|day|month|year|id]
    'SEPARATE_MEDIA':    'month',   # How to separate media [None|day|month|year|id]

    'WALL_QUICKUPDATE':  True,      # If True update existed wall records only if like/comment count was changed            !!!TODO
    'WALL_DEDUPE':       False,     # if True - check for existance (by preview) of same post and exclude(comment out) it
    'WALL_HIDE_ONLY_IMAGE': False,  # if True - comment out messages with no body and only images

    'SKIP_AUTH_TOKEN':   False,     # Do not authenticate using AUTH TOKEN
    'INVISIBLE_MODE':    0,         # -1= only auth_token authentication(completely invisible)
                                    # 0= allowed full authorization if needed
                                    # >0 = if user with this id is online then can use full authorization (write your account id, then hidden auth will happens)

    #'CONSOLE_SIZE':      '80:25',  # line/width
    'CONSOLE_SIZE':      '100:35',  # line/width
    'SECONDARY_LOGIN':    '',       # If defined,then use this to download video
    'SECONDARY_PWD_ENC':  '',       #

    'WAIT_AFTER':       True,       # If False - do not wait after finish the script
    "MACHINE":          False,      # If True - say in machine format and prevent any waiting for answer
    "KEEP_LAST_SECONDS": 0,         # Period (in seconds) from now to past to not immediate but postoponed remove
                                        # (in case of automatic store&clean message could be removed right after appearance,
                                        #so user even do not noticed about it)
    "DEL_ENFORCED":     False,      # Delete messages which are not readed yet and with attachments
}

CONFIG={}
CONFIG = dflt_config.copy()

"""
===========================================
   Initialize CONFIG options from main
===========================================
"""

def InitConfigFromARGV( startsfrom ):
    sysargv = util.getSysArgv()

    # get keys from argv
    if len(sysargv)>startsfrom:
        lines = []
        for arg in sysargv[startsfrom:]:
            a = arg.split('=',1)
            if len(a)>1 and a[0].startswith('--'):
                k = a[0][2:].replace('-','_').upper()
                if k not in CONFIG:
                    util.say( "ERROR: Неизвестная опция %s", arg )
                else:
                    lines.append( [k, a[1]] )
        return load_config_lines( lines )
    return []

def load_config_lines( lines ):
    global CONFIG
    VALUES={ 'true':True, 'false':False, 'none':None }  #, 'month': 'month', 'year': 'year', 'id':'id'
    #lines = map(lambda s: (s.strip().split('=') + ['']), lines )
    loaded=[]
    for l in lines:
        ( key, val ) = ( l[0].strip().upper(), l[1].split('#')[0].strip() )
        if len(key) and len(val):
            if val.lower() in VALUES:
                CONFIG[key] = VALUES[val.lower()]
                ##print "VAL: %s %s" % (key, repr(CONFIG[key]))
            elif val[0]=='"' and val[-1]=='"':
                CONFIG[key] = (val[1:])[:-1]
                ##print "STR\": %s %s" % (key, repr(CONFIG[key]))
            elif val[0]=="'" and val[-1]=="'":
                CONFIG[key] = (val[1:])[:-1]
                ##print "STR': %s %s" % (key, repr(CONFIG[key]))
            else:
                try:
                    CONFIG[key] =  int(val)
                    ##print "INT: %s %s" % (key, repr(CONFIG[key]))
                except:
                    CONFIG[key] =  val
                    ##print "DFLT: %s %s" % (key, repr(CONFIG[key]))
            loaded.append(key)
    return loaded

def load_config( fname ):
    if not os.path.exists( fname ) or not os.path.isfile(fname):
        return
    print "Loaded config: %s" %util.str_cp866(fname)
    with open(fname, "r") as f:
        lines = f.readlines()
    lines = filter(lambda s: not s.lstrip().startswith('#'), lines )
    lines = map(lambda s: (s.strip().split('=',1) + ['']), lines )
    loaded = load_config_lines( lines )
    return loaded


