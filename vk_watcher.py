# coding=utf8
import os, sys, time, base64,re,codecs, subprocess,random,re
import vk

import vk_utils
import tsv_utils as util

"""========================================="""

import config
def LoadConfig():
    more_options = { 'ALLOWED_USERS': '',           # separated by '|' list of ids of allowed to give commands users
                     'PIN':           '0000',       # pin for vk_status and vk_help
                     'PIN_COMMAND':   '',           # if given then you have to enter command like 'vk_watch3222 opt'
                     'USER2NOTIFY':    '',
                     'DEFAULT_USER':    '1',        # default argument "WHO" for bot commands if not given

                     'PYTHON_EXE':      util.TODO('DETECT CURRENT PYTHON INTERPRETER EXE'),
                     'VK_DOWNLOADER':   os.path.join(os.path.split(__file__)[0],'vk_downloader.py'),
                   }

    config.dflt_config.update(more_options)
    config.CONFIG = config.dflt_config.copy()

    config.CFGFILE = './vk_watcher.cfg'
    cfg_loaded  = config.load_config( config.CFGFILE )                    # load config
    #config.CONFIG['MACHINE'] = True

    util.CONFIG = config.CONFIG
    if cfg_loaded:
        print "Loaded values from %s: %s" % ( config.CFGFILE, str(cfg_loaded) )

LOCKFILE = os.path.join(DIR_TMP,'lockfile.group_watch')
def AddLockFile():
    if os.path.isfile(LOCKFILE):
        if (time.time() - os.path.getmtime(LOCKFILE))>100:
            os.unlink(LOCKFILE)
        else:
            print "LOCK FILE"
            exit()
    with open(LOCKFILE,'wb') as f:
        f.write('1')



def getHash( last, call, **kww ):
    try:
      res = call(**kww)
    except Exception as e:
        print e
        return last
    ##print res
    if not res[u'count'] or not res[u'items']:
           return str(res[u'count'])
    return "%s:%s" % ( res[u'count'], res[u'items'][0][u'id'] )



util.init_console()

USER_LOGIN = config.CONFIG['USER_LOGIN'].strip()
if not USER_LOGIN:
    raise util.FatalError('Unknown USER_LOGIN')


DIR_MAIN = os.path.join( os.getcwdu(), '.vk_watcher-%s'%USER_LOGIN )
DIR_LOG = os.path.join( DIR_MAIN, 'log' )
DIR_TMP = os.path.join( DIR_MAIN, 'tmp' )


""""
BASEDIR = os.path.join( os.getcwdu(),u"MSG-%s" % USER_LOGIN )
if not os.path.exists(BASEDIR):
    os.makedirs(BASEDIR)
"""

vk_api, me, USER_PASSWORD = vk_utils.VKSignIn( USER_LOGIN, False )
vk_api2, me2, USER_PASSWORD2 = vk_utils.VKSignInSecondary( False )

now = time.time()

def getPath (fname):
    return os.path.join( DIR_MAIN, fname )

def ScanCommands( handler ):
    for fname in os.listdir(DIR_MAIN):
        fpath = os.path.join(DIR_MAIN,fname)
        if not os.path.isfile(fpath):
            continue

        res = fname.lower().split('_')
        if handler( fname, res ):
            break

def CommandSetStatus( fname, cmd ):
    cmd = [ cmd[1], cmd[0] ] + cmd[2:]                              # change the order to reversed ( STATE _ COMMAND _ WHO _EXTRA )
    opposite_cmd = ['off' if (cmd[0]=='on') else 'on'] + cmd[1:]
    fname_old, fpath, fpath_opposite = fname, getPath('_'.join(cmd)), getPath('_'.join(opposite_cmd))
    fpath_old = getPath(fname_old)

    # a) if cmd already in required state - just skip
    if os.path.exists( fpath ) :
        pass
    # b) if exists opposite state command - rename it
    elif os.path.exists( fpath_opposite ):
        os.rename( fpath_opposite, fpath )

    # c) if given and exists fname (for example comes as time_*) - rename it
    elif fname_old and os.path.exists( fpath_old ):
        os.rename( fpath_old, fpath )

    # d) otherwise - create a new file
    else:
        with open( fpath, 'wb' ) as f:
            pass

    # clean up
    if fname_old and os.path.exists( fpath_old ):
        os.unlink( fpath_old )

# check for posponed actions
def HandlerPostponed( fname, cmd ):

    if cmd[0]=='time' and len(cmd)>3:
        t = util.make_int(cmd[1])
        if (t>now):
            return
        cmd = cmd[2:]                       # cutoff time_TIMESTAMP
        cmd = [ cmd[1], cmd[0] ] + cmd[2:]  # change the order to regular ( CMD _ STATE _ WHO _EXTRA )
        maincmd, isWatcher = getCommand( cmd[0] )
        if isWatcher:
            CommandSetStatus( fname, cmd )
            CommandLog( cmd, status = None )
        else:
            CommandExecute( cmd, mode = 'postponed' )
    return False


def HandlerCheck( fname, res ):

    # skip postponed
    if cmd[0]=='time' and len(cmd)>3:
        return False

    if res[0]=='cfg':
        if res[1]=='defaultuser':
            try:
                with open( getPath(fname), 'rb' ) as f:
                    config.CONFIG['DEFAULT_USER']= int(f.read().strip())
            except Exception as e:
                print "Wrong %s - not integer" % fname
            continue

    # skip on/off actions
    if len(res)>2 and  res[0] in ('off','on'):
        return False

    util.say( "ERROR: unknown format file: %s", [fname] )



ScanCommands( HandlerPostponed )
ScanCommands( HandlerCheck )

def cmdKeep( res, **kww ):
    if kww.get('checkWatcher',False):
        return False            # this is not watch command
    util.TODO('cmdKeep main job')

COMMAND_PROCESSORS = { 'keep':  'store',
                       'store': cmdKeep,
                       'clean': cmdClean,
                       'del':   'clean',

                       'autoclean': cmdAutoClean,
                       'autodel': 'autoclean',
                       'watch': cmdWatchGroup,
                     }


def getCommand( res ):
    cmd = res[0]
    if cmd not in COMMAND_PROCESSORS:
        raise SkipError()
        util.say( "ERROR: unknown command from msg - %s", [cmdline] )
        return None

    main_cmd = COMMAND_PROCESSORS[ cmd ] if isinstance( COMMAND_PROCESSORS[ cmd ], basestring ) else cmd
    isWatcher = COMMAND_PROCESSORS[maincmd]( [cmd], checkWatcher=True )
    min_size = 3 if isWatcher else 2
    if len(cmd_ar)<min_size:
        cmd_ar.append( config.CONFIG['DEFAULT_USER'] )
    return main_cmd, isWatcher



commands = []
res =  vk_api.messages.getHistory( offset=0, count = 30, user_id = me, rev = 1 )
re_postponed = re.compile("/ *([0-9]+)([hm])$", re.IGNORECASE)

flagHelp = flagStatus = False

logMessage = []
import collections
executedCmd = collections.OrderedDict()     # ['cmd' = status]
for item in res[u'items']:
    body = item.get(u'body','').strip().lower()
    if not body.startswith('vk_'):
        continue

    delMsgId = item.get(u'id',0)

    #if item.get(u'from_id') not in config.CFGFILE['ALLOWED_USERS']:
    #    continue
    # util.TODO('only from yourself - no need ALLOWED_USERS')

    lst = map(str.strip, body.split('\n') )
    for cmd in lst:
        if not cmd.startswith('vk_'):
            continue

        # If given
        match = re_postponed.search(cmd)
        if match:
            cmd = cmd[:-len(match.group(0))].strip()                # cut off posponed suffix
            mult = 3600 if match.group(2).lower()=='h' else 60      # detect min/hour multiplier
            ts = now + util.make_int(match.group(1))*mult           # get target timestamp

            res = cmd.split()
            maincmd, isWatcher = getCommand( res )
            if isWatcher:
                status = checkStatus( cmd )
                if status==cmd[1]:
                    raise SkipError("Already %s status"%status)
                CommandSetStatus( )


                # apply command
                # clean

            #if not maincmd( res, checkWatcher=True ):
            #    raise SkipError('Only watchers could be postponed')

            # apply command
            # clean all other such postponed commands
            # add opposite command
            util.TODO('do postponed command')
            logMessage = ['%s (until %s)' % ( ' '.join(cmd),
                                              time.strftime( '%d.%m %H:%M', time.localtime(ts) ) ) ]
            continue

        res = cmd.split()
        # status and help commands are executed not in the time
        if res[0].endswith(config.CONFIG.get('PIN','')):
            if res[0].startswith('vk_status'):
                flagStatus = True
                continue
            if res[0].startswith('vk_help'):
                flagHelp = True
                continue

        maincmd = getCommand( res[0] )

        util.TODO( 'processing of commands (import, add globals, use defaults)' )
        COMMAND_PROCESSORS[maincmd]( res )

    vk_api.messages.delete( message_ids=delMsgId )

util.TODO( 'processing of regular commands' )

exit()




USER2NOTIFY = config.CONFIG['USER2NOTIFY']
if USER2NOTIFY=='':
    USER2NOTIFY = me
AUTO_CLEAN_FLAG_FILE = "./!group-autoclean"





""" 2: CHECK GROUP CHANGES """
print "Do checks"
#for MAIN_PROFILE in MAIN_PROFILE_LIST:
def checkGroup( BASEDIR,MAIN_PROFILE, vk_api ):
  FILE_MAIN   = "%s/__group%s.watch" % (BASEDIR,MAIN_PROFILE)

  stored = []
  try:
     with open(FILE_MAIN,'r') as f:
        stored = map(lambda s: s.strip(), f.readlines() )
  except:
     pass
  stored =  (stored + ['','','',''])[:4]

  wall1 = getHash( stored[0], vk_api.wall.get,  owner_id=MAIN_PROFILE, offset=0, count=1, filter='all', extended=0  )
  aud1  = getHash( stored[1], vk_api.audio.get, owner_id=MAIN_PROFILE, offset=0, count=1 )
  vid1  = getHash( stored[2], vk_api.video.get, owner_id=MAIN_PROFILE, offset=0, count=1  )
  try:
    res =  vk_api.photos.getAlbums( owner_id=MAIN_PROFILE )[u'items']
    photo1 = '+'.join( map(lambda h: str(h[u'size']), res ) )
  except Exception as e:
    print e
    photo1 = stored[3]

  cur_state = [ wall1, aud1, vid1, photo1 ]


  with open(FILE_MAIN,'w') as f:
        f.write( '\n'.join(cur_state) )

  if cur_state == stored:
    print "Nothing changed for %s" % MAIN_PROFILE
  else:
     msg = []
     if stored[0]!=cur_state[0]:  msg.append("WALL was changed (%s -> %s)" % (stored[0],cur_state[0]))
     if stored[1]!=cur_state[1]:  msg.append("AUDIOS was changed (%s -> %s)" % (stored[1],cur_state[1]))
     if stored[2]!=cur_state[2]:  msg.append("VIDEOS was changed (%s -> %s)" % (stored[2],cur_state[2]))
     if stored[3]!=cur_state[3]:  msg.append("PHOTOS was changed (%s -> %s)" % (stored[3],cur_state[3]))

     lt = time.localtime()
     msg = ('%s: '%MAIN_PROFILE) + '\n'.join(msg)
     msg += " at %04d-%02d-%02d %02d:%02d"  % (lt.tm_year, lt.tm_mon, lt.tm_mday, lt.tm_hour, lt.tm_min)

     print "SEND NOTIFY TO %s:\n%s" % (USER2NOTIFY,msg)
     VK_API_MAIN.messages.send( user_id=int(me), message='groupvk='+msg )

     #PLUGIN NOTIFIER


VK_API_MAIN = vk_api
# WATCHER

def RunMainScript( cmd ):
        os.chdir("C:\\MY\\VK_DOWLOAD\\")
        cmd = [ "C:\\MY\\VK_DOWLOAD\\Python27\\App\\python.exe", "C:\\MY\\VK_DOWLOAD\\Python27\\vk_downloader\\vk_downloader.py" ] + cmd
        if len(cmd)<5:
                return '??', 'Too short cmd: %s'%str(cmd)
        cmd += ["--WAIT_AFTER=False", "--MACHINE=True"]
        print ' '.join(map(lambda s: '"%s"'%s, cmd) )
        fp = subprocess.Popen( cmd, stdout=subprocess.PIPE, stderr = subprocess.PIPE, shell = False )
        stdout,stderr = fp.communicate()

        if isinstance(stdout,str): stdout = stdout.decode('cp866')
        if isinstance(stderr,str): stderr = stderr.decode('cp866')

        print "--\n%s" % stdout
        return stdout, stderr

def SendMsgAndDelBase( delMsgId, msg):
        SendMsg(msg)
        if delMsgId:
            vk_api.messages.delete( message_ids=delMsgId )

def SendMsg( msg ):
        try: vk_api.messages.send( user_id=int(me), message='vk:'+msg )
        except: pass

def SendMsg2( stdout, stderr, msgid ):
        with open('group_watch.log','ab') as f:
                f.write( stdout+'\n' )
        msg = stdout + (u'\nERR: %s'%stderr if stderr else '') + u": req="+str(msgid)+u",rnd%x"%random.randint(0,99999)
        try: vk_api.messages.send( user_id=int(me), message='vk:'+msg )
        except: pass

def ExecuteCheck( IF_DEL, msgid ):
        print IF_DEL, msgid

        opt = ["--DEL_ENFORCED=True", "--KEEP_LAST_SECONDS=60"] if msgid=='default' and IF_DEL>0 else []

        # DO PLUGIN AUTODEL_CHECK
        stdout,stderr = RunMainScript( [ "message", USER_LOGIN, WHO, str(IF_DEL), "--DOWNLOAD_MP3=True", "--DOWNLOAD_VIDEO=False", "--DAYSBEFORE=7" ] + opt )


        #res = filter(lambda s: not s.startswith("Loaded "), stdout.splitlines(True) )
        #res = filter(lambda s: (s.strip()) and re.search("[^\\/\-\|\.\?\n\r\t ]",s), res )
        res = filter(lambda s: s.find("{MACHINE}:")>=0, stdout.splitlines(True) )       # filter only {MACHINE} lines
        res = map( lambda s: (s.split('{MACHINE}: mode=',1)+[s])[1], res )              # safe cutoff {MACHINE} and before from each line

        stdout = (''.join(res)).strip()

        print "--\n%s\n%s" % ( stdout, stderr )

        # case: default regular save (store msg with postponed del) - do not notify because this is regular thing. Check result in the log
        if ( IF_DEL==0 ):
            return

        # case: autosave on - do not notify if nothing was stored/deleted
        if ( IF_DEL==1 and msgid=='default' and stdout.find('. *0')>=0 and stdout.find('), -0(')>=0 ):
            return

        SendMsg2( stdout, stderr, msgid )



""" 3: PROCESS COMMANDS ('vk_clean','vk_store') + regular message save """
# CHECK CLEAN REQUEST
res =  vk_api.messages.getHistory( offset=0, count = 20, user_id = me )
now = time.time()
processed = False
restore = None
for item in res[u'items']:
    body = item.get(u'body','').strip().lower()
    if body=='vk_store':
        IF_DEL = -1
    elif body=='vk_clean' or body=='vk_del':
        IF_DEL = 1
    elif body.startswith('vk_restore'):
        res = body.split()
        try: restore = int(res[1])
        except: restore = '*'
        print "RESTORE %s"% restore
        vk_api.messages.delete( message_ids=item[u'id'] )
        continue
    elif body.startswith('vk_autoclean ') or body.startswith('vk_autodel '):
        res = body.split()
        if res[1]=='on' or res[1].find('1')>=0:
            stat='autodel on'
            with open(AUTO_CLEAN_FLAG_FILE,'wb') as f1:
                pass
        else:
            stat='autodel off'
            if os.path.exists(AUTO_CLEAN_FLAG_FILE):
                os.unlink(AUTO_CLEAN_FLAG_FILE)
        SendMsgAndDelBase( item[u'id'], u": %s"%stat )
        continue
    elif body.startswith('vk:'):
        continue                            # skip reports
    elif body.startswith('vk'):
        SendMsgAndDelBase( item[u'id'], u": wrong command '%s'. should starts from vk_"%body )
        continue
    else:
        continue

    if (now - item[u'date'])>1*3600:
        continue

    if not processed:
        processed = True
        ExecuteCheck( IF_DEL,item[u'id'] )
    vk_api.messages.delete( message_ids=item[u'id'] )

if restore is not None:
        stdout,stderr = RunMainScript(['restore',"",'-2000,%sm'%restore])
        res = stdout.split(' offline-')
        stdout = res[1] if len(res)>1 else stdout

        SendMsg2(stdout,stderr, str(restore) )

if not processed:
    deltype = 1 if os.path.exists(AUTO_CLEAN_FLAG_FILE) else 0
    ExecuteCheck( deltype, 'default' )

#VISA
#TARANENKO SERGII

#os.unlink(LOCKFILE)
sys.exit()


"""

...
if (parseInt(photo_items[index].photo_2560.length) > 0)
{
    photo_list = photo_list + [photo_items[index].photo_2560];
}
...
else if (parseInt(photo_items[index].photo_75.length) > 0)
{
    photo_list = photo_list + [photo_items[index].photo_75];
}
...

Ну и напоследок полный код функции:


var owner_id = 8296250;
var album_id = 211849784;

var output = [];
var user_info = API.users.get({user_ids:owner_id});
var owner_name = user_info@.first_name[0] + " " + user_info@.last_name[0];
output = output +[ ["owner_name",0, owner_name] ];

var album = API.photos.getAlbums({owner_id: owner_id, album_ids: album_id});
output = output +["album",0,"album_body"];

var photo_items = API.photos.get({album_id: album_id, owner_id: owner_id}).items;
output = output +["photo_items",0,photo_items];

var index = 0;
while (index < 20 )
{
    var id =  owner_id + "_" + photo_items[index].id;
    var value = API.photos.getById({photos: id});
    output = output + ["ID", id, value];
    index = index + 1;
}

return {output: output};
"""