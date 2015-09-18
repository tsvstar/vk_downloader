# coding=utf8
import os, sys, time, base64,re,codecs, subprocess,random,re
import vk
#import collections
import traceback, imp

# TODO:
#       postponed send (up to N changes since first change are collected) - minimize num of notification
#       option: -XX means exclude notifier for this item ('-vk' - exclude vk)
#       COMMAND
#       exclude view/comments/like for not owned by user video (for group not owned by any user?)
#       minimum offline period
"""
vk_help
vk_list                     --> task - status(active,disabled), notify(silent)
vk_list_full                --> task - arg1, arg2, ..
vk_join/vk_leave groupid    - join/leave group
vk_notify +/- task,...      - turn on/off notification for task(s)
vk_enable +/- task,...      - turn on/off task(s)
vk_store  [task]            - run message task with store (regardless of its rate right now) and notify about state
vk_clean [task]             - run message task with enforced message delete
vk_autoclean on/off [task]  - change mode for message task
vk_default task             - set default message task
vk_restore                  - restore messages
"""

# DONE:
# "Run" handler
# log: notify, vkerror, traceback, online status
# config: PRECISE, ENFORCE

import vk_utils
import tsv_utils as util
from tsv_utils import DBG, str_decode

"""========================================="""

#BASE_DIR='"C:\\MY\\VK_DOWLOAD\\'

import config
def LoadConfig():
    more_options = { 'MACHINE':     True,           # Replace this with False only to initialize passwords

                     'ENFORCE':     False,          # If TRUE, then ignore lock file and rate
                     'PRECISE':     True,           # If TRUE, then use big packets to better change detection; If FALSE then sacrifice detection accuracy for trafic/speed

                     'PYTHON_EXE':      sys.executable,
                     'VK_DOWNLOADER':   os.path.join(os.path.split(__file__)[0],'vk_downloader.py'),
                   }

    config.dflt_config.update(more_options)
    config.CONFIG = config.dflt_config.copy()

    config.CFGFILE = './vk_watcher.cfg'
    cfg_loaded  = config.load_config( config.CFGFILE )                    # load config

    util.CONFIG = config.CONFIG
    if cfg_loaded:
        print "Loaded values from %s: %s" % ( config.CFGFILE, str(cfg_loaded) )

def AddLockFile( timeout=100 ):
    if os.path.isfile(LOCKFILE):
        if (time.time() - os.path.getmtime(LOCKFILE))>timeout:
            os.unlink(LOCKFILE)
        else:
            DBG.say( DBG.IMPORTANT, "LOCK FILE" )
            exit()
    with open(LOCKFILE,'wb') as f:
        f.write('1')


def getPath (fname):
    return os.path.join( DIR_MAIN, fname )

def ReplaceByMap():
    for a in aliases:
        value = value.replace(a[0],a[1])
    return value

def ReplaceAlias( value ):
    aliases = map( lambda i: [ str(i[0]), repr(i[1])], config.CONFIG.get('ALIASES',{}).iteritems() )
    return ReplaceByMap( value )


"""========================================="""
def RunMainScript( cmd ):
        util.say( 'RunMainScript(%s)', [cmd] )
        cmd = [ config.CONFIG['PYTHON_EXE'], config.CONFIG['VK_DOWNLOADER'] ] + cmd
        if len(cmd)<5:
                return '??', 'Too short cmd: %s'%str(cmd)
        cmd += ["--WAIT_AFTER=False", "--MACHINE=True"]
        DBG.info('RunMainScript(%s)',repr(cmd) )
        #print ' '.join(map(lambda s: '"%s"'%s, cmd) )
        try:
            fp = subprocess.Popen( cmd, stdout=subprocess.PIPE, stderr = subprocess.PIPE, shell = False )
            stdout,stderr = fp.communicate()
        except Exception as e:
            stdout, stderr = '', u'FAIL TO RUN: %s' %str(e)

        if isinstance(stdout,str): stdout = stdout.decode('cp866')
        if isinstance(stderr,str): stderr = stderr.decode('cp866')

        print "--\n%s" % stdout
        DBG.trace(u"STDOUT:%s", stdout)
        if stderr:
            DBG.trace(u"STDERR:%s", stdout)
        return stdout, stderr

import inspect
def SendMsg( vk_api, message, prefix = None, _replaceAlias = False ):
    DBG.trace(u"SendMsg( %s, msg='%s', prefix='%s', alias=%s\n%s", [vk_api,message,prefix,_replaceAlias,traceback.format_stack()] )
    DBG.important(u'\nSENDMSG>>>\n%s\n<<<<', [message] )
    if prefix is None:
        if not message.startswith(u'vk:'):
            prefix = u'vk:'
        else:
            prefix = ''
    if _replaceAlias:
        message = ReplaceAlias( message )
    message = u"%s%s {rnd%x}" % ( prefix, message, random.randint(0,99999) )
    vk_api.messages.send( user_id=COMMAND_USER, message=message )


def ExecuteDownloadMSG( who, delFlag, options ):
        # DO PLUGIN AUTODEL_CHECK
        cmd = [ "message", USER_LOGIN, who ]
        if delFlag is not None:
            cmd.append( delFlag )
        cmd += ["--DOWNLOAD_MP3=True", "--DOWNLOAD_VIDEO=False", "--DAYSBEFORE=7" ] + options
        stdout,stderr = RunMainScript( cmd )
        ##res = filter(lambda s: s.find("{MACHINE}:")>=0, stdout.splitlines(True) )       # filter only {MACHINE} lines
        res = map( lambda s: (s.split('{MACHINE}: mode=',1)+[s])[1], res )              # safe cutoff {MACHINE} and before from each line
        stdout = (''.join(res)).strip()

        stdout += (u'\nERR: %s'%stderr if stderr else '')
        return stdout, stderr


"""========================================="""

glob_vkapi  = None      # current cached vkapi object
##glob_path   = None      # path to state file (MAINDIR/objid.type) -- povestki.wall
glob_fname  = None      # objid (ex: povestki)
glob_main   = None      # type (ex:wall)
glob_options = []       # list of requested extra options (comments,...)
glob_notify = []        # list of notification target [  [notify_type1,notify_queue1], .. ]     ( [ ['vk', ''] , ['jeapie','!'], .. )
notifications = {}      # notifications[notify_type][queue][objid] = [ wall_notify, ..]
glob_sendto_vk = None   # id of target user for notify
glob_queue = None       # currently processed queue
glob_precise = True

def get_glob_path():
    global glob_fname, glob_main, DIR_MAIN
    return os.path.join( DIR_MAIN, '%s.%s' % (glob_fname,glob_main) )

""" ==================================================================== """

# get optionally parameter count
#   val = item_dict (comes as answer from vk request)
#   key = name of parameter
#   sub = if True then it is [key]['count'], otherwise just [key]
def getcount( val, key, sub=True ):
    global glob_options
    if (key not in glob_options) and ('*' not in glob_options):
        return '?'

    if sub:
        return val.get(key,{}).get(u'count',0)
    else:
        return val.get(key,0)


# PURPOSE: load "glob_path" file (lines. fields separated by tab; last one - is evaluated)
# if file is empty - replace by "empty" value
def loadfile( empty = [] ):
    res = []
    if os.path.exists( get_glob_path() ):
        with open( get_glob_path(), 'rb') as f:
            res1 = f.read().splitlines()
            for r in res1:
                ar = r.split('\t')
                try:
                    if len(ar)>1:
                        ar[-1] = eval(ar[-1])
                except:
                    pass
                res.append(ar)
    if not len(res):
        res = list( empty )
    return res

# PURPOSE: Save items to "glob_path" file + logs
def save_file( items, shortLog = False ):
    global glob_fname, glob_main
    DBG.trace('save_file() to %s.%s' % (glob_fname,glob_main) )
    def convert_ ( items, dorepr ):
        res = []
        for i in items:
            if isinstance(i,list):
                i = list(i)
            else:
                i = [ i ]
            if len(i)>1:
                if dorepr:
                    i[-1] = repr(i[-1])
                else:
                    i[-1] = util.str_encode( unicode(i[-1]), 'utf-8' )
            res.append( '\t'.join( map(str, i) ) )
        return res

    with open( get_glob_path(), 'wb') as f:
        f.write( '\n'.join( convert_(items,True) ) )

    # add to "log" file
    with open( '%s.log' % get_glob_path(), 'ab') as f:
        t = time.strftime("%d.%m.%y %H:%M", time.localtime())
        if shortLog:
            f.write( '%s: %s\n' % ( t, convert_(items,False)[0].strip() ) )
        else:
            f.write( '=====%s\n' % t )
            f.write( '\n'.join(convert_(items,False)+['']) )

# PURPOSE: each item add to dict with id=item[0] + add items with idx>max_num to extra
def make_dict( items, max_num ):
    res_dict = {}
    extra = set()
    for i in items:
        #if not ( isinstance(i,tuple) or isinstance(i,list) ):
        #   continue
        if len(i)<2:
            continue
        res_dict[ str(i[0]) ] = i
        if len(res_dict)>=max_num:
            extra.add( str(i[0]) )
    return res_dict, extra


def TRACE_AR( name, ar ):
    if isinstance(ar,tuple) or isinstance(ar,list):
        DBG.trace( 'name=%s (%s count=%d)\n%s', [name, type(ar), len(ar), '\n'.join( map( lambda v: '%d=\t%s' % (v[0],v[1]), enumerate(ar) ) )] )
    elif isinstance(ar, dict):
        DBG.trace( 'name=%s (dict count=%d)\n%s', [name, len(ar), '\n'.join( map( lambda v: '%s:\t%s' % (repr(v[0]),v[1]), ar.iteritems() ) )] )
    else:
        DBG.trace( 'name=%s (%s)\n%s', [ name, type(ar), ar ])
    #    print


# FIND OUT WHAT WAS CHANGED IN ITEMS LIST
#       items - current items list (always start from [overall_count])
#       max_num - after this limit do not check for delete (so if N new were added, then last N will go away from list if limited)
#       extra_fields_names - list of names fields starting from idx=1 (if changed - notify using this name)
# NOTE:
#       a) used glob_fname/glob_fpath to load prev/save this list [TODO: postponed save? -- to avoid missed notification??]
#       b) presumed that in normal item idx=0 always id, idx=-1 always 'human readable name'
def compare_items( items, max_num, extra_fields_names, show_new_as_text = True ):
    was = loadfile( [ [ 0 ] ] )
    was_dict, was_extra = make_dict( was, max_num )
    now_dict, now_extra = make_dict( items, max_num )
    was_set, now_set = set( was_dict.keys() ), set( now_dict.keys() )
    ##TRACE_AR('was',was)
    ##TRACE_AR('now',items)
    ##TRACE_AR('was_dict',was_dict)
    ##TRACE_AR('now_dict',now_dict)

    notify = []

    # compare count
    if int(was[0][0])!=int(items[0][0]):
        notify.append( u"cnt %s->%s" % (was[0][0], items[0][0]) )

    if int(was[0][0]) and int(items[0][0]):
        # find new
        new_set = now_set - was_set - now_extra
        if not len(new_set):
            pass
        elif len(new_set) > 10:
            notify.append(u"%d new"% len(new_set))
        elif len(new_set)>5 or not show_new_as_text:
            notify.append(u"%d new(%s) "% ( len(new_set), ', '.join(map(str,new_set)) ) )
        else:
            for id in new_set:
                txt = now_dict[id][-1].strip()
                notify.append(u'add "%s"' % (txt if txt else 'id%s'%id) )

        # find del
        del_set = was_set - now_set - was_extra
        if len(del_set) > 10:
            notify.append(u"%d removed"% len(del_set))
        elif len(del_set)>5:
            notify.append(u"%d removed(%s) "% ( len(new_set), ', '.join(map(str,del_set)) ) )
        else:
            for id in del_set:
                txt = was_dict[id][-1].strip()
                notify.append(u'del "%s"' % (txt if txt else 'id%s'%id) )

    # find changes
    range_extra_fields = range( len(extra_fields_names) )
    for i in was:
        if len(i)<2:
            continue
        if i[0] not in now_dict:
            continue
        compare = []
        for idx in range_extra_fields:
            old_val = str(i[idx+1])
            new_val = str( now_dict[ str(i[0]) ][idx+1] )
            if i[idx+1] != new_val:
                try:
                    new_val = int(new_val)
                    old_val = int(old_val)
                    compare.append(u'%s %s->%s' % (extra_fields_names[idx],old_val, new_val) )
                except:
                    compare.append(u'%s changed' % extra_fields_names[idx] )
        if len(compare):
            txt = str( i[-1] if len(i[-1])<100 else i[-1][:100] ).strip()
            notify.append( u'%s changed: %s' % ( (txt if txt else 'id%s'%i[0]), ', '.join(compare)) )

    if len(notify):
        save_file( items )
        make_notify( [ u'>%s: %s' % (glob_main.upper(), u';\n'.join(notify) ) ] )

# PURPOSE: add regarding to "glob_notify" notifications from list
def make_notify( notify, logfile = '.notificatons-main.log' ):
    global glob_notify, notifications

    DBG.trace( "make_notify %s", [notify] )
    for n_type, n_queue in glob_notify:
        ref = notifications.setdefault(n_type,{}).setdefault(n_queue,{}).setdefault(glob_fname,[])
        ref += notify
        #for n in notify:
        #    ref.append( n )

    for n_type, n_queue in glob_notify:
        ref = notifications.setdefault('logger',{}).setdefault(logfile,{}).setdefault(glob_fname,[])
        ref += notify

""" ==================================================================== """

def wall_handler( vk_api, vk_id, options ):
    precision = 100 if glob_precise else 75
    res = vk_api.wall.get( owner_id=vk_id, count=precision, filter='all')
    if vk_api.doPrepareOnly:
        return

    items = [ [ res[u'count'] ] ]
    for i in res[u'items']:
        items.append( [ i[u'id'], getcount(i,u'comments'), getcount(i,u'likes'), getcount(i,u'reposts'), i.get(u'text','') ] )
    if 'new_only_as_msg' not in options:
        compare_items( items, precision-10, ['comments','likes','reposts', 'text'], 'new' in options )
    else:
        # SPECIAL CASE: send text of all new posts on the wall
        was = loadfile( [ [ 0 ] ] )
        was_dict, was_extra = make_dict( was, precision-10 )
        now_dict, now_extra = make_dict( items, precision-10 )
        was_set, now_set = set( was_dict.keys() ), set( now_dict.keys() )
        if was[0][0] and items[0][0]:
            # find new
            new_set = now_set - was_set - now_extra
            notify = []
            for id in new_set:
                notify.append(u'WALL\n%s' % now_dict[id][-1] )
            if len(notify):
                save_file( items )
                make_notify( notify )


def video_handler( vk_api, vk_id, options ):
    precision = 200 if glob_precise else 100
    res = vk_api.video.get( owner_id=vk_id, count=precision, extended=1)
    if vk_api.doPrepareOnly:
        return

    items = [ [ res[u'count'] ] ]
    for i in res[u'items']:
        items.append( [ i[u'id'], getcount(i,u'likes'), getcount(i,u'views',False), getcount(i,u'comments',False), i.get(u'title','') ] )
    compare_items( items, precision-10, ['likes','views','comments'] )


def mp3_handler( vk_api, vk_id, options ):
    precision = 500 if glob_precise else 350
    res = vk_api.audio.get( owner_id=vk_id, count=precision, extended=1)
    if vk_api.doPrepareOnly:
        return

    items = [ [ res[u'count'] ] ]
    for i in res[u'items']:
        items.append( [ '%s_%s'%(i[u'owner_id'],i[u'id']), u'%s - %s (%ssec)'% (i[u'artist'],i[u'title'],i['duration']) ] )
    compare_items( items, precision-50, [] )


def photo_handler( vk_api, vk_id, options ):
    precision = 600 if glob_precise else 200
    precision_comm = 100 if glob_precise else 75
    res = vk_api.photos.getAlbums( owner_id=vk_id, need_system=1, count=precision )
    res_comment = None
    if ('comments' in options) or ('*' in options):
        res_comment = vk_api.photos.getAllComments( owner_id=vk_id, count=precision_comm)
    if vk_api.doPrepareOnly:
        return

    items = [ [ res[u'count'] ] ]
    for i in res[u'items']:
        #items.append( [ i[u'id'], i[u'size'], i.get(u'updated',0), i[u'title'] ] )
        items.append( [ i[u'id'], i[u'size'], i[u'title'] ] )
    compare_items( items, precision-30, ['size'] )

    if res_comment is None:
        return

    ##TRACE_AR( "res_com",res_comment )
    global glob_main
    glob_main = 'ph_comments'
    items = [ [ res_comment[u'count'] ] ]
    for i in res_comment[u'items']:
        items.append( [ '%s:%s'%(i[u'id'],i[u'pid']), u'%s_%s: %s' % ( vk_id, i[u'pid'], i[u'text'][:100] ) ] )
    compare_items( items, precision_comm-10, [] )


def message_handler( vk_api, vk_id, options ):
    res = vk_api.messages.getHistory( user_id=vk_id, count=1 )
    if vk_api.doPrepareOnly:
        return

    first_item = res[u'items'][0] if len(res[u'items']) else {}
    msgid = first_item.get(u'id',0)

    was = loadfile( [ [ 0 ] ] )+[0]
    if msgid > int(was[0][0]):
        save_file( [ msgid ], shortLog=True )
        if int(was[0][0]) and first_item.get(u'from_id',0)==vk_id and not first_item.get(u'read_state',1):
            make_notify( ["incoming message"], '.notificatons-messages.log' )

def status_handler( vk_api, vk_id, options ):
    if vk_id>0:
        res = vk_api.status.get( user_id=vk_id )
    else:
        res = vk_api.status.get( group_id=-vk_id )
    if vk_api.doPrepareOnly:
        return

    text = res.get(u'text','')
    audio = None
    if u'audio' in res:
        audio = res.get(u'audio',{})
        text += ' ~(%s_%s)~' % (audio[u'owner_id'],audio[u'id'])
    text = text.strip()
    items = [ text ]
    was = loadfile() + [ [''],[''] ]
    ##DBG.trace( 'compare %s -- %s // %s', [text,str_decode(was[0][0],'utf-8'),audio])
    if text!= was[0][0]:
        items.append( was[1] if audio else text )       # [0]=current_status, [1]=last_non_mp3_status
        save_file( items, shortLog=True )
        mp3_pattern = re.compile("\~\([0-9\-_]+\)\~$")
        if mp3_pattern.search( was[0][0] ):
            # skip notification mp3->mp3
            if audio:
                return
            # skip notification mp3->old_text
            if text==was[1][0]:
                return
        make_notify( [u'STATUS = %s'%text] )

def online_handler( vk_api, vk_id, options ):
    platform_dict = {   1: 'mobile',
                        2: 'iphone',
                        3: 'ipad',
                        4: 'android',
                        5: 'wphone',
                        6: 'win8',
                        7: 'web'
                    }
    res = vk_api.users.get( user_ids=vk_id, fields='online,last_seen' )
    if vk_api.doPrepareOnly:
        return

    online =  res[0][u'online']
    if online:
        platform = platform_dict.get( res[0][u'last_seen'][u'platform'], '??')    # https://vk.com/dev/using_longpoll (7=web)
    items = [ platform if online else '---' ]

    was = loadfile() + [['']]
    DBG.trace( 'online answer for %s is %s' % (vk_id,res) )
    ##DBG.trace( "compare online %s -- %s", [was[0],items[0]])
    if was[0][0]!=items[0]:
        save_file( items, shortLog=True )
        if online and was[0][0]=='---':
            #notify only when come online
            make_notify( [u' ONLINE(%s)'%platform],'.notificatons-online.log' )


""" ==================================================================== """

def logger_notifier(  text , enforce ):
    text = text.strip()
    if not text:
		return False

    global DIR_MAIN
    fpath = os.path.join( DIR_MAIN, glob_queue)
    with open( fpath, 'ab' ) as f:
        t = time.strftime("%d.%m.%y %H:%M", time.localtime())
        f.write( util.str_encode( u'*** %s ***\n%s\n' % ( t, text ), 'utf-8' ) )
    return True

def vk_notifier( text , enforce ):
    text = text.strip()
    if not enforce and len(text)>2000:
        return False
    if not text:
		return False

    #global glob_vkapi, glob_sendto_vk
    #glob_vkapi.messages.send( user_id=glob_sendto_vk, message=text )
    globals()['COMMAND_USER'] =  glob_sendto_vk
    SendMsg( glob_vkapi, text )
    return True

def jeapie_notifier( text, enforce ):
    text = text.strip()
    if not enforce and len(text)>2000:
        return False
    if not text:
        return False
    DBG.trace("jeapie: %s", [ text ] )

    import httplib, urllib
    global conn
    try:
        conn = httplib.HTTPSConnection("api.jeapie.com:443")
        conn.request("POST", "/v2/personal/send/message.json",
               urllib.urlencode({
               "token": config.CONFIG.get('TOKEN_JEAPIE',''),
               "message": text,
               }), { "Content-type": "application/x-www-form-urlencoded" })
        ##print text
        print "RESPONSE ", conn.getresponse().status
    except Exception as e:
        print "EXCEPTION: (%s)" % e
        return False

    return True

# short class based on https://github.com/Azelphur/pyPushBullet
class PushBullet(object):
    import requests
    import json

    HOST = "https://api.pushbullet.com/v2"

    def __init__( self, apiKey ):
        import requests.auth
        self.apiKey = requests.auth.HTTPBasicAuth(apiKey, "")

    def _request(self, method, url, postdata=None, params=None, files=None):
        headers = {"Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "pyPushBullet"}
        if postdata:
            postdata = PushBullet.json.dumps(postdata)
        r = PushBullet.requests.request(method,
                PushBullet.HOST + url,
                data=postdata,
                params=params,
                headers=headers,
                files=files,
                auth=self.apiKey)
        r.raise_for_status()
        print r.headers
        return r.json()

    def pushNote(self, recipient, title, body, recipient_type="device_iden"):
        data = {"type": "note",
                "title": title,
                "body": body}
        data[recipient_type] = recipient
        return self._request("POST", "/pushes", data)

#def pushbullet_notifier( text, enforce ):
def bullet_notifier( text, enforce ):
    text = text.strip()
    if not enforce and len(text)>2000:
        return False
	if not text:
		return False

    devices = bullet._request("GET", "/devices")["devices"]
    bullet.pushNote( devices[0]['iden'], 'VK', text )
    return True


def ExecuteNotification():
    global notifications
    DBG.trace('ExecuteNotification()')
    for notify_type, ar1 in notifications.iteritems():
        func = globals().get( '%s_notifier' % notify_type, None )
        if not callable( func ):
            continue
        for queue, ar2 in ar1.iteritems():
            collected_notify=[]
            for objid, ar_notifies in ar2.iteritems():
                DBG.trace( 'do notify [%s][%s][%s] -- list of %d', [notify_type,queue,objid, len(ar_notifies)] )
                if queue=='!':
                    for notify in ar_notifies:
                        text = u'%s: %s' % ( objid.upper(), notify )
                        DBG.trace("INDIVIDUAL NOTIFY: %s", [text] )
                        func( text, enforce = True )
                elif len(ar_notifies)==0:
                    continue
                elif len(ar_notifies)==1:
                    collected_notify.append( u'%s: %s' % ( objid.upper(), ar_notifies[0] ) )
                else:
                    collected_notify.append( u'%s:\n%s' % ( objid.upper(), '\n'.join(ar_notifies) ) )
            global glob_queue
            glob_queue = queue
            while collected_notify:
                text = '\n=====\n'.join(collected_notify)
                DBG.trace("TRY TO COLLECTED NOTIFY: %s", [text] )
                res = func( text, enforce = False)
                if res:
                    break
                DBG.trace("FAIL DUE TO LENGTH - TRY FIRST ELEM ONLY")
                func( collected_notify.pop(0), enforce = True )


""" ==================================================================== """

def main():
    global DIR_MAIN, DIR_LOG, DIR_TMP

    util.init_console()
    DBG.logfile_name='./LOG_WATCHER/vk_watch'
    DBG.level = DBG.TRACE

    DBG.important( u">>> RUN vk_watcher at %s" % os.getcwdu() )
    if 'BASE_DIR' in globals() and BASE_DIR:
        os.chdir(BASE_DIR)

    LoadConfig()
    config.InitConfigFromARGV( startsfrom = 1 )
    USER_LOGIN = config.CONFIG['USER_LOGIN'].strip()
    if not USER_LOGIN:
        raise util.FatalError('Unknown USER_LOGIN')

    DIR_MAIN = os.path.join( os.getcwdu(), '.vk_watcher-%s'%USER_LOGIN )
    DIR_LOG = os.path.join( DIR_MAIN, 'log' )
    DIR_TMP = os.path.join( DIR_MAIN, 'tmp' )

    for path in [ DIR_MAIN, DIR_LOG, DIR_TMP ]:
        if not os.path.exists( path ):
            os.makedirs( path )

    global LOCKFILE
    LOCKFILE = os.path.join(DIR_TMP,'lockfile.group_watch')
    if not config.CONFIG.get('ENFORCE',0):
        AddLockFile( timeout=55 )

    # Initialize push services token
    global bullet
    bullet = PushBullet( config.CONFIG.get('TOKEN_PUSHBULLET','') )

    globals()['glob_precise'] = config.CONFIG.get('PRECISE',True)

    # Do Login
    import vk.api
    vk.api.LOG_DIR = "./LOG_WATCHER"
    vk.api.LOG_FILE = '%s/vk_api.log' % vk.api.LOG_DIR
    interactive = 'first_time' in sys.argv
    if interactive:
        config.CONFIG['INVISIBLE_MODE'] = False
    vk_api1, me1, USER_PASSWORD1 = vk_utils.VKSignIn( USER_LOGIN, interactive )
    ##vk_api2, me2, USER_PASSWORD2 = vk_utils.VKSignInSecondary( False )
    now = time.time()

    # Load watchers
    with open( config.CONFIG.get('WATCHERS_PY','./vk_watchers_list.py'), 'rb') as f:
        watchers_code = f.read()#, 'utf-8')

    global notifications
    notifications = {}

    global glob_vkapi
    glob_vkapi = vk_utils.CachedVKAPI( vk_api1 )
    for pass_ in [ 1, 2 ]:
        glob_vkapi.doPrepareOnly = ( pass_==1 )
        util.say( "Do %d pass", pass_ )
        #compile( watchers_code , "<watchers_py>", "exec")
        exec( watchers_code )

        DBG.trace('execute requests')
        glob_vkapi.execute()
        DBG.trace('request done')

    global glob_sendto_vk
    glob_vkapi = vk_api1
    glob_sendto_vk = me1
    ExecuteNotification()


hash_cache = {}
def isAllowByRate( rate, prefix, hash_ ):
    global hash_cache, glob_vkapi, hashfile

    hashfile = os.path.join( DIR_TMP, '.check_rate.%s.%x' % ( prefix, hash_ ) )
    if config.CONFIG.get('ENFORCE',0):
        return True

    # negative rate means 'disable'
    if rate<0:
        return False

    if hashfile not in hash_cache:
        if os.path.exists( hashfile ):
            hash_cache[hashfile] = time.time() - os.path.getmtime( hashfile )
        else:
            hash_cache[hashfile] = None
    pause = hash_cache[hashfile]
    if pause is not None and pause < 60*rate:
        DBG.trace('skip because of not expired yet (%.1f/%s)- %s' % (pause/60,rate,hashfile) )
        if glob_vkapi.doPrepareOnly:
            print "skip %s - %.1f from %d minutes after last check" % ( prefix, pause/60, rate )
        return False
    return True

def TouchHashFile():
    global hashfile
    with open( hashfile, 'wb') as f:
        f.write( '%s' % time.time() )


""" ================== API =========================="""
def Watch( rate, vk_id, fname, to_watch, to_notify ):
    global glob_vkapi

    if not isAllowByRate( rate, '%s.%s'%(fname, vk_id), hash( repr([to_watch,to_notify]) ) ):
        return

    res = {}
    for w in to_watch:
        main, options = (w.replace(' ','').replace('\t','').lower().split(':')+[''])[:2]
        options = options.split(',')
        func = globals().get( '%s_handler' % main, None )
        if not callable( func ):
            print "NO '%s' HANDLER FOUND" % main
            continue
        notify_ar = map( lambda s: (s.strip().split(':')+[''])[:2], to_notify )

        global glob_options, glob_notify, glob_fname, glob_main
        glob_options, glob_notify, glob_main = options, notify_ar, main
        glob_fname = fname
        DBG.trace( 'WATCH %s/%s [%spass]', [fname,main, 1 if glob_vkapi.doPrepareOnly else 2 ])
        try:
            func( glob_vkapi, vk_id, options )
        except vk.VkError as e:
            util.say( "VKError: %s", [str(e)] )
            DBG.trace( "VKError: %s", [str(e)] )

    # after 2nd pass - mark that check done
    if not glob_vkapi.doPrepareOnly:
        TouchHashFile()

def Run( rate, fname, cmd, to_notify ):
    global glob_vkapi

    if not isAllowByRate( rate, '-run-%s'%fname, hash( repr([cmd,to_notify]) ) ):
        return
    if glob_vkapi.doPrepareOnly:
        return

    stdout,stderr = RunMainScript( cmd )
    res = filter(lambda s: s.find("{MACHINE}:")>=0, stdout.splitlines(True) )       # filter only {MACHINE} lines
    res = map( lambda s: (s.split('{MACHINE}: mode=',1)+[s])[1], res )              # safe cutoff {MACHINE} and before from each line
    stdout = (''.join(res)).strip()
    print "--\n%s\n%s" % ( stdout, stderr )

    TouchHashFile()

    if cmd[0]!='message':
        return

    msgid = 'default'   # -- this is for todo (is because of vk command received)

    IF_DEL = int(cmd[3])
    # case: default regular save (store msg with postponed del) - do not notify because this is regular thing. Check result in the log
    if ( IF_DEL==0 ):
        return

    # case: autosave on - do not notify if nothing was stored/deleted
    if ( IF_DEL==1 and msgid=='default' and stdout.find('. *0')>=0 and stdout.find('), -0(')>=0 ):
        return

    make_notify( [stdout + (u'\nERR: %s'%stderr if stderr else '')], '.notificatons-messagebackup.log')


if __name__ == '__main__':
    try:
        main()
        util.say("execution finished")
    except Exception as e:
        tb = traceback.format_exception(sys.exc_type, sys.exc_value, sys.exc_traceback)
        DBG.trace( 'EXCEPTION: %s %s\n%s', [ type(e), unicode(e),
                            '\n'.join( filter(len, map( lambda s: s.rstrip(), tb)) ) ] )
        bullet_notifier( 'EXCEPTION: %s %s' % (type(e),e), enforce = True )
        util.say_cp866( unicode(e) )
        raise


