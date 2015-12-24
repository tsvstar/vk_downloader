# coding=utf8
import os, sys, time, base64,re,codecs, subprocess,random,re
import vk
#import collections
import traceback, imp

# TODO:
#       COMMAND
#       option: -XX means exclude notifier for this item ('-vk' - exclude vk)
#       option everywhere: exXXX|YY| - exclude by id
#       accumulate changes ( if same entity changed continuosly - remember values and send whole way once it will be stabilized) - ACCUMULATE_MINUTES=11
#       postponed send (up to N changes since first change are collected) - minimize num of notification
#           + suppressed jitter (that is more simple - if detected for something - add ./tmp/.jitter.id.fname -- and if on next request it still another - process)
#       programmable options '@optname' (turn on/off offline for example)

# autodel - twice more rare
# incoming message - only if last unread message at least 3 minutes ago
# fix:  wall:new_only_as_msg doesn't work
# vk_store,vk_del
#    cmdlst.append( 'TODO ...{+x, +hh:mm, hh:mm, dd.mm hh:mm}' )
#    cmdlst.append( 'TODO vk_restore' )
#    cmdlst.append( 'TODO vk_delete dd.mm hh:mm [- dd.mm hh:mm]' )
#    cmdlst.append( 'TODO vk_confirm confirmid' )


"""
vk_help
vk_list                     --> task - status(active,disabled), notify(silent); options list
vk_list_full                --> task - arg1, arg2, ..
vk_join/vk_leave groupid    - join/leave group
vk_notify +/-task,...       - turn on/off notification for task(s)
vk_enable +/-task,...       - turn on/off task(s)
vk_option optname=value     - set value for programmable options
vk_store  [task]            - run message task with store (regardless of its rate right now) and notify about state
vk_clean [task]             - run message task with enforced message delete
vk_autoclean on/off [task]  - change mode for message task
vk_default task             - set default message task
vk_restore                  - restore messages
"""

# DONE:
# "Run" handler
# log: notify, vkerror, traceback, online status, squeezed online status, vk_answer if something changed; DBG.trace2; send to pushbullet when DBG.error
# config: PRECISE, ENFORCE
# options:   wall:from=XX|YY, wall:id, online:XX, video:owneronly, online:verbose
# jitter suppresion: if count or any extra changed to zero then do enforced re-request immediately

import vk_utils
import tsv_utils as util
from tsv_utils import DBG, str_decode

"""========================================="""

#BASE_DIR='"C:\\MY\\VK_DOWLOAD\\'

import config
def LoadConfig():
    more_options = { 'MACHINE':     True,           # Replace this with False only to initialize passwords

                     'API2':        False,          # If TRUE, then we need to secondary login too
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
        if not stderr:
            DBG.trace2(u"STDOUT:%s", stdout)
        else:
            DBG.trace(u"STDOUT:%s", stdout)
            DBG.trace(u"STDERR:%s", stderr)
        return stdout, stderr

import inspect
def SendMsg( vk_api, message, prefix = None, _replaceAlias = False ):
    DBG.trace(u"SendMsg( %s, msg='%s', prefix='%s', alias=%s\n%s", [vk_api,message,prefix,_replaceAlias,traceback.format_stack()] )
    DBG.important(u'\nSENDMSG>>>\n%s\n<<<<', [message] )
    if prefix is None:
        if not message.startswith(u'vk:'):
            prefix = u'vk: '
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
        res = filter(lambda s: s.find("{MACHINE}:")>=0, stdout.splitlines(True) )       # filter only {MACHINE} lines
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
COMMAND_USER = None   # id of target user for notify
glob_queue = None       # currently processed queue
glob_precise = True     # True if high precision check, False if low precision check
glob_jitter_detected = False  # raise to True if suspect about jitter
glob_jitter_hour = False # True if currently time which is rich for long-time jitter (01:00-05:00 usually)

old_dbg_important = DBG.important   # remember real DBG.important


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
        message = util.unicformat( 'name=%s (%s count=%d)\n%s', [name, type(ar), len(ar), '\n'.join( map( lambda v: '%d=\t%s' % (v[0],v[1]), enumerate(ar) ) )] )
    elif isinstance(ar, dict):
        message = util.unicformat( 'name=%s (dict count=%d)\n%s', [name, len(ar), '\n'.join( map( lambda v: '%s:\t%s' % (repr(v[0]),v[1]), ar.iteritems() ) )] )
    else:
        message = util.unicformat( 'name=%s (%s)\n%s', [ name, type(ar), ar ])

    import md5, base64
    hashname = base64.b64encode( md5.new(message).digest() ).replace('/','=')
    dname = os.path.join( os.path.split(os.path.abspath(DBG.logfile_name))[0], 'HASHED_FILES' )
    if not os.path.exists(dname):
        os.makedirs( dname )
    log_filename = os.path.join( dname, hashname )

    try:
        with open( log_filename, 'wb') as out:
            out.write( util.str_encode( message, 'utf-8') )
        DBG.trace( 'name=%s --> %s', [name,log_filename] )
    except Exception as e:
        DBG.trace( '<fail to create hashed file %s>: %s', [log_filename,str(e)] )
        DBG.trace( message )

    #    print

# FIND OUT WHAT WAS CHANGED IN ITEMS LIST
#       items - current items list (always start from [overall_count])
#       max_num - after this limit do not check for delete (so if N new were added, then last N will go away from list if limited)
#       extra_fields_names - list of names fields starting from idx=1 (if changed - notify using this name)
#       show_new_as_text - if false then always use id instead of human-readable
#       vk_resp - answers of vk to logging in trace in case if something was changed
# RETURN:
#       True if suspect jitter
# NOTE:
#       a) used glob_fname/glob_fpath to load prev/save this list [TODO: postponed save? -- to avoid missed notification??]
#       b) presumed that in normal item idx=0 always id, idx=-1 always 'human readable name'
def compare_items( items, max_num, extra_fields_names, show_new_as_text = True, vk_resp = {} ):
    was = loadfile( [ [ 0 ] ] )
    was_dict, was_extra = make_dict( was, max_num )
    now_dict, now_extra = make_dict( items, max_num )
    was_set, now_set = set( was_dict.keys() ), set( now_dict.keys() )
    range_extra_fields = range( len(extra_fields_names) )
    ##TRACE_AR('was',was)
    ##TRACE_AR('now',items)
    ##TRACE_AR('was_dict',was_dict)
    ##TRACE_AR('now_dict',now_dict)

    # Check for possible jitter
    def isSuspectJitter():
        if int(was[0][0]) > int(items[0][0]):
            DBG.trace('count %s->%s', [was[0], items[0]])
            return True
        else:
            for i in was:
                if len(i)<2:
                    continue
                if i[0] not in now_dict:
                    continue
                compare = []
                for idx in range_extra_fields:
                    old_val = str(i[idx+1])
                    new_val = str( now_dict[ str(i[0]) ][idx+1] )
                    if old_val not in ['',0,'0','?'] and new_val in ['',0,'0']:
                        DBG.trace("change %s: %s->%s\n%s\n->\n%s", [extra_fields_names[idx],old_val,new_val, i, now_dict[ str(i[0]) ]])
                        return True
        return False

    global glob_jitter_detected, glob_jitter_hour
    global glob_fname, glob_main
    jitter_fname = '.jitter~%s.%s'%(glob_fname,glob_main)

    if not glob_jitter_detected:
        if isSuspectJitter():
            TRACE_AR( 'SUSPECT JITTER. This is correspondend vk_response', items )
            # 1. First suspection of jitter
            if not _check( '', jitter_fname):
                # a) 1pass (no file mark exists from previous cron call) - raise local flag to do immediate re-request (supress most of them)
                glob_jitter_detected = True
                DBG.info('suspect jitter for %s.%s - 1pass', [glob_fname, glob_main])
                return True
            else:
                DBG.info('suspect jitter for %s.%s - 3pass. that is not a jitter', [glob_fname, glob_main])
                # b) 3rd pass (previous cron call also suspected jitter), so this is real change
                os.unlink( os.path.join( DIR_TMP, jitter_fname ) )
        else:
            # There is not suspected changes found, delete file mark
            if _check( '', jitter_fname ):
                DBG.info('clean %s. looks like that was a jitter' % jitter_fname )
                os.unlink( os.path.join( DIR_TMP, jitter_fname ) )
    else:
        TRACE_AR( 'SUSPECT JITTER. This is correspondend vk_response', items )
        # 2. Check for jitter after immediate re-request (2nd pass)
        if isSuspectJitter():
            DBG.info('suspect jitter for %s.%s - 2pass', [glob_fname, glob_main])
            # changes are still here. probably it is real changes. lets wait one more tick
            # add file to remember that and skip checks/write new state
            with open( os.path.join(DIR_TMP,jitter_fname), 'wb' ) as f:
                f.write('1')
            return False
        else:
            # no suspected changes found, so that was jitter. now we have normal values
            DBG.info('%s: that was jitter. 2nd pass' % jitter_fname )


    notify = []
    enforceSave = False

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
    for i in was:
        if len(i)<2:
            continue
        if i[0] not in now_dict:
            continue
        compare = []
        for idx in range_extra_fields:
            old_val = str(i[idx+1])
            new_val = str( now_dict[ str(i[0]) ][idx+1] )
            if old_val != new_val:
                # only like could jitter for long period - so if it happens in jitter hour wait forawhile
                if glob_jitter_hour and new_val in ['0',0] and extra_fields_names[idx]=='likes':
                    DBG.trace("Suppress jitter because of hour: [%s][%s] ignore change %s->%s" % (i[0],idx+1,old_val,new_val) )
                    now_dict[ str(i[0]) ][idx+1] = old_val
                    continue

                enforceSave = True
                if old_val=='?' or new_val=='?':
                    continue
                try:
                    new_val = int(new_val)
                    old_val = int(old_val)
                    compare.append(u'%s %s->%s' % (extra_fields_names[idx],old_val, new_val) )
                except:
                    compare.append(u'%s changed' % extra_fields_names[idx] )
        if len(compare):
            txt = str( i[-1] if len(i[-1])<100 else i[-1][:100] ).strip()
            notify.append( u'%s changed: %s' % ( (txt if txt else 'id%s'%i[0]), ', '.join(compare)) )

    if enforceSave or len(notify):
        save_file( items )

    if len(notify):
        make_notify( [ u'>%s: %s' % (glob_main.upper(), u';\n'.join(notify) ) ] )
        trace = [ {'main:count': vk_resp.get(u'count','??')} ]
        trace += vk_resp.get(u'items', [] )
        TRACE_AR( 'CHANGE DETECTED. This is correspondend vk_response', trace )
    return False



main_notification_log = '.notificatons-main.log'
# PURPOSE: add regarding to "glob_notify" notifications from list
def make_notify( notify, logfile = main_notification_log ):
    global glob_notify, notifications

    DBG.trace( "make_notify %s", [notify] )
    for n_type, n_queue in glob_notify:
        ref = notifications.setdefault(n_type,{}).setdefault(n_queue,{}).setdefault(glob_fname,[])
        ref += notify
        #for n in notify:
        #    ref.append( n )

    silent_flag = 'silent:' if not glob_notify else ''
    ref = notifications.setdefault('logger',{}).setdefault(logfile,{}).setdefault(silent_flag+glob_fname,[])
    ref += notify

def _get_numeric_opt( options, default = 0 ):
    for i in options:
        try:
            val = int(i.strip())
            if val>=0:
                return val
        except:
            pass
    return default


""" ====================================================================
                    WATCHER HANDLERS
    ==================================================================== """

def wall_handler( vk_api, vk_id, options ):
    precision = 100 if glob_precise else 75
    res = vk_api.wall.get( owner_id=vk_id, count=precision, filter='all')
    if hasattr(vk_api,'doPrepareOnly') and vk_api.doPrepareOnly is True:
        return

    # find 'from=XX|YY' option
    only_from = []
    for o in options:
        if not o.startswith('from='):
            continue
        ids = map( lambda s: s.strip(), o.split('=',1)[1].split('|') )
        for i in ids:
            try:
                only_from.append( int(i) )
            except:
                pass
    if only_from:
        print "onlyfrom", only_from

    count = '1' if only_from else res[u'count']     # for "only_from" filter common count is useless and produce false alarms
    items = [ [ count  ] ]
    for i in res[u'items']:
        if only_from and int(i[u'from_id']) not in only_from:
            continue
        items.append( [ i[u'id'], getcount(i,u'comments'), getcount(i,u'likes'), getcount(i,u'reposts'), i.get(u'text','') ] )

    if 'new_only_as_msg' not in options:
        return compare_items( items, precision-10, ['comments','likes','reposts', 'text'], 'id' not in options, vk_resp=res )
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
    if hasattr(vk_api,'doPrepareOnly') and vk_api.doPrepareOnly is True:
        return

    items = [ [ res[u'count'] ] ]
    for i in res[u'items']:
        items.append( [ i[u'id'], getcount(i,u'likes'), getcount(i,u'views',False), getcount(i,u'comments',False), i.get(u'title','') ] )
        if ('owneronly' in options ) and int(i[u'owner_id'])!=vk_id:
            # ignore extras for added(not loaded) video, if option 'owneronly' defined
            items[-1] =[ i[u'id'], '?', '?', '?', i.get(u'title','') ]
    return compare_items( items, precision-10, ['likes','views','comments'], vk_resp=res )


def mp3_handler( vk_api, vk_id, options ):
    precision = 500 if glob_precise else 350
    res = vk_api.audio.get( owner_id=vk_id, count=precision, extended=1)
    if hasattr(vk_api,'doPrepareOnly') and vk_api.doPrepareOnly is True:
        return

    items = [ [ res[u'count'] ] ]
    for i in res[u'items']:
        items.append( [ '%s_%s'%(i[u'owner_id'],i[u'id']), u'%s - %s (%ssec)'% (i[u'artist'],i[u'title'],i['duration']) ] )
    return compare_items( items, precision-50, [], vk_resp=res )


def photo_handler( vk_api, vk_id, options ):
    precision = 600 if glob_precise else 200
    precision_comm = 100 if glob_precise else 75
    res = vk_api.photos.getAlbums( owner_id=vk_id, need_system=1, count=precision )
    res_comment = None
    if ('comments' in options) or ('*' in options):
        res_comment = vk_api.photos.getAllComments( owner_id=vk_id, count=precision_comm)
    if hasattr(vk_api,'doPrepareOnly') and vk_api.doPrepareOnly is True:
        return

    items = [ [ res[u'count'] ] ]
    for i in res[u'items']:
        #items.append( [ i[u'id'], i[u'size'], i.get(u'updated',0), i[u'title'] ] )
        items.append( [ i[u'id'], i[u'size'], i[u'title'] ] )
    if  compare_items( items, precision-30, ['size'], vk_resp=res ):
        return True     # jitter detected

    if res_comment is None:
        return

    ##TRACE_AR( "res_com",res_comment )
    global glob_main
    glob_main = 'ph_comments'
    items = [ [ res_comment[u'count'] ] ]
    for i in res_comment[u'items']:
        items.append( [ '%s:%s'%(i[u'id'],i[u'pid']), u'%s_%s: %s' % ( vk_id, i[u'pid'], i[u'text'][:100] ) ] )
    return compare_items( items, precision_comm-10, [], vk_resp=res )


def message_handler( vk_api, vk_id, options ):
    res = vk_api.messages.getHistory( user_id=vk_id, count=1 )
    if hasattr(vk_api,'doPrepareOnly') and vk_api.doPrepareOnly is True:
        return

    first_item = res[u'items'][0] if len(res[u'items']) else {}
    msgid = first_item.get(u'id',0)
    date = first_item.get(u'date',0)
    notify_after = _get_numeric_opt( options, 3 )   # in minutes

    was = loadfile( [ [ 0 ] ] )+[0]
    if msgid > int(was[0][0]) and (time.time()-date)>notify_after*60:
        save_file( [ msgid ], shortLog=True )
        if int(was[0][0]) and first_item.get(u'from_id',0)==vk_id and not first_item.get(u'read_state',1):
            make_notify( ["incoming message"], '.notificatons-messages.log' )

def status_handler( vk_api, vk_id, options ):
    if vk_id>0:
        res = vk_api.status.get( user_id=vk_id )
    else:
        res = vk_api.status.get( group_id=-vk_id )
    if hasattr(vk_api,'doPrepareOnly') and vk_api.doPrepareOnly is True:
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
    if hasattr(vk_api,'doPrepareOnly') and vk_api.doPrepareOnly is True:
        return

    # try to find numeric option - that is value for max ignored pause of offline
    ignore_offline_pause = _get_numeric_opt( options, 0 )    # in minutes

    online =  res[0][u'online']
    if online:
        platform = platform_dict.get( res[0][u'last_seen'][u'platform'], '??')    # https://vk.com/dev/using_longpoll (7=web)
    items = [ [ platform if online else '---' ], [time.time()] ]

    was = loadfile() + [['0'],[0]]
    DBG.trace( 'online answer for %s is %s' % (vk_id,res) )
    ##DBG.trace( "compare online %s -- %s", [was[0],items[0]])
    if was[0][0]!=items[0][0]:
        save_file( items, shortLog=True )
        last_online_start = squeeze_online_log( ignore_offline_pause )
        if 'verbose' in options:
            if online:
                make_notify( [u' ONLINE(%s)'%platform],'.notificatons-online.log' )
            else:
                ln = int( (25+time.time()-last_online_start)/60 )
                make_notify( [u'OFFLINE(len %2d:%02d)'%(int(ln/60), ln%60)],'.notificatons-online.log' )
        elif online and was[0][0]=='---':
            #notify only when come online
            try:
                become_offline=int(float(was[1][0]))
                if (items[1][0]-become_offline) < 60*ignore_offline_pause:
                    DBG.trace( "Become offline %s. Ignore because period %1.f minutes is lower than ignore_offline_pause=%d ",
                                     [ time.strftime("%d.%m.%y %H:%M", time.localtime(become_offline)), (items[1][0]-become_offline)/60, ignore_offline_pause] )
                    return
            except Exception as e:
                DBG.trace('fail to get lastseen from was - %s\n%s', [repr(was), str(e) ] )
            make_notify( [u' ONLINE(%s)'%platform],'.notificatons-online.log' )

# PURPOSE: produce squeezed online log from full version ( with respecting ignore_offline_pause argument, which is nominated in minutes )
def squeeze_online_log( ignore_offline_pause ):

    with open( '%s.log' % get_glob_path(), 'rb') as f:
        res = f.read().strip().splitlines()

    # Fill up periods list
    periods = [ ]       # [ [from, till, type], .. ]

    last_online_start = 0
    last = [0,'']
    for i in res:
        i = i.split(': ',1)
        if i[1]=='---' and last[1]=='':
            # skip leading 'offline' (find first online)
            continue
        now = time.mktime( time.strptime( i[0], "%d.%m.%y %H:%M") )
        if last[1] not in ['---','']:
            periods.append( [ last[0], now, last[1] ] )
        last = [ now, i[1] ]
    # if last period is not closed
    if last[1] not in ['---','']:
        periods.append( [ last[0], 0, last[1] ] )
    if len(periods):
        last_online_start = periods[-1][0]

    # skip ignore_offline_pause intervals
    ignore_offline_pause *= 60      # convert to seconds
    periods_new = []
    for start,end,type_ in periods:
        # if first item or different type - enforce insert
        if ( not periods_new ) or type_!=periods_new[-1][2]:
            periods_new.append( [start,end,type_] )
        else:
            diff = start - periods_new[-1][1]
            ##DBG.trace( "%s -> %s = %d-%d = %d vs %d" %(time.strftime('%H:%M',time.localtime(end)), time.strftime('%H:%M',time.localtime(start)), end, start, diff, ignore_offline_pause ) )
            if diff < ignore_offline_pause:
                # short offline - join to previous
                periods_new[-1][1] = end
            else:
                periods_new.append( [start,end,type_] )

    periods  = periods_new

    # Make output
    squeezedlog = '%s.log.squeezed' % get_glob_path()
    with open( squeezedlog, 'wb' ) as f:
        prev_date=''
        prev_end_time = -1
        start_period_time = -1
        for start,end,type_ in periods:
            d = time.strftime( "%d.%m.%y(%a)", time.localtime(start) )
            if d!=prev_date:
                prev_date = d
                f.write("\n===== %s ======\n" % d )

            if prev_end_time==start:
                t1 = '.....'
                ln = int( (25+end-start_period_time)/60 )
                total = " / total %d:%02d" % (int(ln/60), ln%60)
            else:
                t1 = time.strftime( "%H:%M", time.localtime(start) )
                total = ''
                start_period_time = start
            prev_end_time=end

            if end:
                t2 = time.strftime( "%H:%M", time.localtime(end) )
                ln = int( (25+end-start)/60 )
                f.write("%s\t%s - %s\t(len %2d:%02d%s)\n" % (type_,t1,t2, int(ln/60), ln%60, total) )
            else:
                ln = int( (25+time.time()-start)/60 )
                f.write("%s\t%s - NOW\t(len %2d:%02d%s)\n" % (type_,t1, int(ln/60), ln%60, total) )

    return last_online_start


""" ====================================================================
                        NOTIFY HANDLERS
    ==================================================================== """

class Notifiers(object):
    def logger_notifier( self, text , enforce ):
        print 'logger',text
        text = text.strip()
        if not text:
    		return False

        global DIR_MAIN
        fpath = os.path.join( DIR_MAIN, glob_queue)
        with open( fpath, 'ab' ) as f:
            t = time.strftime("%d.%m.%y %H:%M", time.localtime())
            f.write( util.str_encode( u'*** %s ***\n%s\n' % ( t, text ), 'utf-8' ) )
        return True

    def vk_notifier( self, text , enforce ):
        text = text.strip()
        if not enforce and len(text)>2000:
            return False
        if not text:
    		return False

        #global glob_vkapi, glob_sendto_vk
        #glob_vkapi.messages.send( user_id=glob_sendto_vk, message=text )
        SendMsg( glob_vkapi, text )
        return True

    def jeapie_notifier( self, text, enforce ):
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

    #def pushbullet_notifier( text, enforce ):
    def bullet_notifier( self, text, enforce ):
        text = text.strip()
        if not enforce and len(text)>2000:
            return False
    	if not text:
    		return False

        global bullet
        devices = bullet._request("GET", "/devices")["devices"]
        if devices:
            bullet.pushNote( devices[0]['iden'], 'VK', u'%s: %s' % ( time.strftime("%H:%M",time.localtime()), text ) )
        return True

# short class based on https://github.com/Azelphur/pyPushBullet
class PushBullet(object):
    import requests
    import json

    HOST = "https://api.pushbullet.com/v2"

    def __init__( self, apiKey ):
        import requests.auth
        self.apiKey = requests.auth.HTTPBasicAuth(apiKey, "")
        self.validkey = apiKey.strip()

    def _request(self, method, url, postdata=None, params=None, files=None):
        if not self.validkey:
            print "unable to pushbullet - empty apikey"
            return { 'devices':''}
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


def ExecuteNotification():
    global notifications
    DBG.trace('ExecuteNotification()')
    for notify_type, ar1 in notifications.items():
        func = getattr( Notifiers, '%s_notifier' % notify_type, None )
        if not callable( func ):
            continue
        for queue, ar2 in ar1.items():
            collected_notify=[]
            try:
                for objid, ar_notifies in ar2.items():
                    DBG.trace( 'do notify [%s][%s][%s] -- list of %d', [notify_type,queue,objid, len(ar_notifies)] )
                    if queue=='!':
                        ar_notifies = notifications[notify_type][queue][objid]
                        while ar_notifies:
                            notify = ar_notifies.pop(0)
                            text = u'%s: %s' % ( objid.upper(), notify )
                            DBG.trace("INDIVIDUAL NOTIFY: %s", [text] )
                            func( Notifiers(), text, enforce = True )
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
                    res = func( Notifiers(), text, enforce = False)
                    if res:
                        break
                    DBG.trace("FAIL DUE TO LENGTH - TRY FIRST ELEM ONLY")
                    func( collected_notify.pop(0), enforce = True )
                del notifications[notify_type][queue]
            except Exception as e:
                print e
                print traceback.print_exception
                pass

    r = repr(notifications)
    with open( os.path.join(DIR_TMP,'.postponed-notifications'), 'wb' ) as f:
        f.write(r)

    if notifications:
        if filter( len, notifications.values() ):
            DBG.trace( 'unexecuted notifications: %s', [r] )


""" ==================================================================== """
glob_watchers = {}      # glob_watchers[taskname] = [ [type,id,extra], [type,id,extra],.. ]
glob_cmd_notify = {}    # glob_cmd_notify[task] = [notify1, notify2]
glob_backup_status = {} # glob_backup_status[task] = if temporary request given - set it

# Internal function which register all handlers in glob_watchers dictionary
def doRegistration( watchers_code ):
    class Mock( object ):
        def Watch( self, rate, vk_id, fname, to_watch, to_notify ):
            global glob_watchers
            glob_watchers.setdefault( fname, [] ).append( ['watcher',vk_id, to_watch] )

        def Run( self, rate, fname, cmd, to_notify ):
            global glob_watchers
            glob_watchers.setdefault( fname, [] ).append( ['backup', cmd, 'default'] )

    util.say( "Do cmd registering" )
    vk1 = Mock()
    vk2 = Mock()
    exec( watchers_code )           ##compile( watchers_code , "<watchers_py>", "exec")

# add notification
def cmdNotifyCollect( cmd, notify, category = '!' ):
    global glob_cmd_notify
    glob_cmd_notify.setdefault( category, [] )
    notify[0] = '%s - %s'%(cmd,notify[0])
    glob_cmd_notify[category] += notify

# parse opt from "grpid1,taskid,..." to lists ok/failed
def _get_groups( opt ):
    ok = {}
    failed = []
    ar = filter( len, map( lambda s: s.strip(), (opt+[''])[0].split(',') ) )
    for task in ar:
        found = glob_watchers.get( task, [[None]] )[0]
        if found[0]=='watch':
            if found[1]>0:
                failed.append(found[1])
            else:
                ok[task] = found[1]
        else:
            try:
                ok[task] = abs(int(task.strip()))
            except:
                failed.append(task)
    return ok, failed

# find watcher and generate error notification if not found
def _findWatcher( task, category, cmd ):
    found = glob_watchers.get( task, [[None]] )[0]
    if found[0] is None:
        cmdNotifyCollect( cmd, ["unknown task '%s'" % task] )
        return None
    if category is not None and found[0]!=category:
        cmdNotifyCollect( cmd, ["given task '%s' is not %s" % (task,category)] )
        return None
    return found

# parse "+-taskid,+-taskid" command options
def _get_tasks_op( cmd, opt, category=None ):
    result = []
    ar = filter( len, map( lambda s: s.strip(), (opt+[''])[0].split(',') ) )
    if not ar:
        cmdNotifyCollect( cmd, ["no operation for '%s'" % cmd] )
    for task in ar:
        operation = task[0]
        who = task[1:]
        if operation not in ['+','-']:
            cmdNotifyCollect( cmd, ["unknown operation for '%s'" % task] )
            continue

        if who=='':
            who = _get_default_task()
        found = _findWatcher( who, category, cmd  )
        if found:
            result.append( [operation, who, found] )
    return result

# generic command processor (create/delete file)
def _process_task( cmd, opt, pass_, prefix, category = None, op = '-' ):
    if pass_!=0:
        return
    result = _get_tasks_op( cmd, opt, category )
    if not result:
        return

    for r in result:
        fname = os.path.join( DIR_TMP, '%s.%s' % (prefix,r[1]) )
        if r[0]==op:
            with open(fname,'wb') as f:
                f.write('1')
        else:
            if os.path.exists(fname):
                os.unlink(fname)
    result = map( lambda r: '%s%s'%(r[0],r[1]),result )
    cmdNotifyCollect( cmd, ['OK: '+ ','.join(result)] )

# check file existance
def _check( prefix, who ):
    fname = os.path.join( DIR_TMP,  '%s.%s' % (prefix,who) if prefix else who )
    #DBG.trace('_check(%s) = %s', [fname,os.path.exists( fname )])
    return os.path.exists( fname )

def _get_default_task():
    global glob_default_task
    if 'glob_default_task' in globals():
        return glob_default_task
    fname = os.path.join( DIR_TMP, 'default_task' )
    if os.path.exists(fname):
        with open(fname,'rb') as f:
            glob_default_task = f.read().strip()
            return

    keys = filter( lambda k: glob_watchers[k][0][0]=='backup', glob_watchers.keys() )
    keys += filter( lambda k: glob_watchers[k][0][0]!='backup', glob_watchers.keys() )
    if keys:
        return keys[0]
    return 'ABSENT'


"""===================================================================================
                            VK_COMMAND HANDLERS
   ==================================================================================="""

class CMD(object):
    def cmd_help( self, cmd, opt, pass_ ):
        if pass_!=0 or 'flag_cmd_help' in globals():
            return
        globals()['flag_cmd_help'] = True

        cmdlst = []
        cmdlst.append( 'vk_help' )
        cmdlst.append( 'vk_list|vk_list_full')
        cmdlst.append( 'vk_join|vk_leave GROUPID' )
        cmdlst.append( 'vk_notify|vk_enable +/-task1,+/-task2,..' )
        cmdlst.append( 'vk_store|vk_clean [msgtask]' )
        cmdlst.append( 'vk_autoclean +/-[task]' )
        cmdlst.append( 'vk_default task' )

        cmdlst.append( 'TODO ...{+x, +hh:mm, hh:mm, dd.mm hh:mm}' )
        cmdlst.append( 'TODO vk_restore' )
        cmdlst.append( 'TODO vk_delete dd.mm hh:mm [- dd.mm hh:mm]' )
        cmdlst.append( 'TODO vk_confirm confirmid' )
        SendMsg( vk_api1, "\n".join(cmdlst) )

    def _join_leave( self, cmd, opt, pass_, func, name2):
        name = cmd[3:]
        ok, failed = _get_groups( opt )
        for task, id_ in ok.items():
            try:
                func( group_id=id_ )
                cmdNotifyCollect( cmd, ['%s %s'%(name2,task)] )
            except Exception as e:
                cmdNotifyCollect( cmd, ['fail to %s %s: %s'%(task,name,str(e))] )
        if failed:
            cmdNotifyCollect( cmd, ['fail to %s %s: unknown group(s)'%(name,','.join(failed))] )

    def cmd_join(  self, cmd, opt, pass_ ):
        if pass_==0:
            self._join_leave(  cmd, opt, pass_, vk_api1.groups.join, 'joined to' )

    def cmd_leave( self, cmd, opt, pass_ ):
        if pass_==2:
            self._join_leave(  cmd, opt, pass_, vk_api1.groups.leave, 'leave' )

    def cmd_notify( self, cmd, opt, pass_ ):
        _process_task( cmd, opt, pass_, '.silent')

    def cmd_enable( self, cmd, opt, pass_ ):
        _process_task( cmd, opt, pass_, '.disable')

    def cmd_autoclean( self, cmd, opt, pass_ ):
        _process_task( cmd, opt, pass_, '.autoclean', category='backup', op='+')

    def cmd_default( self, cmd, opt, pass_ ):
        if pass_!=0:
            return
        if not opt:
            cmdNotifyCollect( cmd, ["no task given"] )

        found = _findWatcher( opt[0], 'backup', cmd )
        if found:
            fname = os.path.join( DIR_TMP, 'default_task' )
            globals()['glob_default_task'] = opt[0]
            with open(fname,'wb') as f:
                    f.write(opt[0])


    def cmd_list( self, cmd, opt, pass_ ):
        if pass_!=0:
            return
        keys = filter( lambda k: glob_watchers[k][0][0]!='backup', glob_watchers.keys() )
        keys += filter( lambda k: glob_watchers[k][0][0]=='backup', glob_watchers.keys() )

        lst = []
        for k in keys:
            v = k + ( ' -  disabled' if _check( '.disable',k ) else ' - enabled' )
            if _check('.silent',k):
                v+= ' silent'
            if _check('.autoclean',k):
                v+= ' autoclean'
            lst.append(v)
        if lst:
            lst.append( "DEFAULT: %s"%_get_default_task() )
            SendMsg( vk_api1, "\n".join([' STATUS']+lst) )

    def _process_cmd_taskstatus( self, cmd, opt, pass_, status ):
        if pass_!=0:
            return

        global glob_backup_status
        ar = filter( len, map( lambda s: s.strip(), (opt+[''])[0].split(',') ) )
        if not ar:
            ar.append( _get_default_task() )
        for task in ar:
            found = _findWatcher( task, 'backup', cmd )
            if found:
                glob_backup_status[task]= status

    def cmd_store( self, cmd, opt, pass_ ):
        self._process_cmd_taskstatus( cmd, opt, pass_, 'store' )

    def cmd_clean( self, cmd, opt, pass_ ):
        self._process_cmd_taskstatus( cmd, opt, pass_, 'clean' )

    def cmd_del( self, cmd, opt, pass_ ):
        self._process_cmd_taskstatus( cmd, opt, pass_, 'clean' )


""" ==================================================================== """

def main():
    global DIR_MAIN, DIR_LOG, DIR_TMP

    util.init_console()
    DBG.logfile_name='./LOG_WATCHER/vk_watch'
    DBG.level = DBG.TRACE

    DBG.error = classmethod( new_dbg_important )

    DBG.important( u">>> RUN vk_watcher at %s" % os.getcwdu() )
    if 'BASE_DIR' in globals() and BASE_DIR:
        os.chdir(BASE_DIR)

    LoadConfig()
    config.InitConfigFromARGV( startsfrom = 1 )

    # Initialize push services token
    global bullet
    bullet = PushBullet( config.CONFIG.get('TOKEN_PUSHBULLET','') )
    globals()['glob_precise'] = config.CONFIG.get('PRECISE',True)

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

    global notifications
    notifications = {}

    # Do Login
    global vk_api1, vk_api2
    import vk.api
    vk.api.LOG_DIR = "./LOG_WATCHER"
    vk.api.LOG_FILE = '%s/vk_api.log' % vk.api.LOG_DIR
    interactive = 'first_time' in sys.argv
    if interactive:
        config.CONFIG['INVISIBLE_MODE'] = False

    vk_api1, me1, USER_PASSWORD1 = vk_utils.VKSignIn( USER_LOGIN, interactive )
    vk1 = Watcher( vk_api1 )
    api_list = [ vk1 ]
    if config.CONFIG.get('API2',False):
        vk_api2, me2, USER_PASSWORD2 = vk_utils.VKSignInSecondary( interactive )
        vk2 = Watcher( vk_api2 )
        api_list.append( vk2 )
    now = time.time()

    global COMMAND_USER     # who is the source of command and target for vk notify
    COMMAND_USER =  me1

    # Load watchers
    with open( config.CONFIG.get('WATCHERS_PY','./vk_watchers_list.py'), 'rb') as f:
        watchers_code = f.read()#, 'utf-8')

    try:
        f = os.path.join(DIR_TMP,'.postponed-notifications')
        if os.path.exists( f ):
            with open( f, 'rb') as f:
                 notifications = eval( f.read() )
    except Exception as e:
        DBG.info('fail to load postponed notifications: %s',[str(e)])

    # load commands and remember lastid
    commands = []
    lastidfile = os.path.join(DIR_TMP,'lastid')
    lastid = 0
    if os.path.isfile( lastidfile ):
        with open( lastidfile, 'rb') as f:
            lastid = int( '0' + f.read().strip() )
    res = vk_api1.messages.getHistory( user_id=COMMAND_USER )
    for r in res[u'items']:
        if int(r[u'id'])<=lastid:
            break
        if r[u'body'].strip().lower().startswith(u'vk_'):
            commands.append( r[u'body'].strip() )
    if len(res[u'items']):
        with open( lastidfile, 'wb' ) as f:
            f.write( u'%s' % res[u'items'][0][u'id'] )
    commands.reverse()

    global glob_cmd_notify
    # Preprocess commands
    if commands:
        print "Process commands"
        # register requested process
        doRegistration( watchers_code )
        # register command handlers
        command_dict = {}
        for n in dir(CMD):
            if n.startswith('cmd_'):
                func = getattr(CMD,n)
                if callable(func):
                    command_dict[ n[4:] ] = func
        glob_cmd_notify = {}
        for c in commands:
            c_ar = c.strip().split()
            func = command_dict.get( c_ar[0][3:].lower(), None )
            print c_ar[0], func
            DBG.info("CMD: %s", [ c_ar[0] ] )
            if not func:
                cmdNotifyCollect( c_ar[0], [ u"unknown command" ] )
            else:
                func( CMD(), c_ar[0], c_ar[1:], pass_=0 )
        for k in sorted( glob_cmd_notify.keys() ):
            v = '\n'.join(glob_cmd_notify[k])
            if v:
                SendMsg( vk_api1, v )

    global glob_vkapi
    glob_vkapi = vk_api1

    for pass_ in [ 1, 2 ]:
        for a in api_list:
            a.vk.doPrepareOnly = ( pass_==1 )
        util.say( "Do %d pass", pass_ )
        #checkCommands()
        exec( watchers_code )           ##compile( watchers_code , "<watchers_py>", "exec")

        DBG.trace('execute requests')
        for a in api_list:
            a.vk.execute()
        DBG.trace('request done')

    ExecuteNotification()



""" ================== API =========================="""
hash_cache = {}
class Watcher( object ):
    def __init__( self, vk_api ):
        self.vk = vk_utils.CachedVKAPI( vk_api )

    def isAllowByRate( self, rate, prefix, hash_ ):
        global hash_cache, hashfile

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
            if self.vk.doPrepareOnly:
                ##DBG.trace('skip because of not expired yet (%.1f/%s)- %s' % (pause/60,rate,hashfile) )
                print "skip %s - %.1f from %d minutes after last check" % ( prefix, pause/60, rate )
            return False
        return True

    def TouchHashFile( self ):
        global hashfile
        with open( hashfile, 'wb') as f:
            f.write( '%s' % time.time() )


    def Watch( self, rate, vk_id, fname, to_watch, to_notify ):
        if not self.isAllowByRate( rate, '%s.%s'%(fname, vk_id), hash( repr([to_watch,to_notify]) ) ):
            return
        if _check( '.disable', fname ):
            DBG.info( 'disabled %s', [fname])
            return

        notify_ar = map( lambda s: (s.strip().split(':')+[''])[:2], to_notify )
        if notify_ar and _check( '.silent', fname ):
            DBG.info( 'silent %s', [fname])
            notify_ar = []

        res = {}
        for w in to_watch:
            main, options = (w.replace(' ','').replace('\t','').lower().split(':')+[''])[:2]
            options = filter( len, map( lambda s: s.strip(), options.split(',') ) )
            func = globals().get( '%s_handler' % main, None )
            if not callable( func ):
                print "NO '%s' HANDLER FOUND" % main
                continue

            global glob_options, glob_notify, glob_fname, glob_main
            glob_options, glob_notify, glob_main = options, notify_ar, main
            glob_fname = fname
            DBG.trace( 'WATCH %s/%s [%spass]', [fname,main, 1 if self.vk.doPrepareOnly else 2 ])
            try:
                global glob_jitter_detected
                glob_jitter_detected = False
                rv = func( self.vk, vk_id, options )
		DBG.trace('rv=%s; jitter=%s',[rv,glob_jitter_detected])
                if rv is True:
                    DBG.important("jitter detected - do re-request")
                    glob_jitter_detected = True
                    func( self.vk.vk_api, vk_id, options )
            except vk.VkError as e:
                DBG.say( DBG.TRACE, "VKError: %s", [str(e)] )

        # after 2nd pass - mark that check done
        if not self.vk.doPrepareOnly:
            self.TouchHashFile()

    def Run( self, rate, fname, cmd, to_notify ):
        global  glob_fname
        glob_fname = fname

        request = glob_backup_status.get(fname,'default')
        if request=='default' and _check( '.autoclean', fname ):
            request = 'default+autoclean'
            rate *= 2

        if not request.startswith('default'):
            DBG.trace('enforce because of request %s', [request])
        elif not self.isAllowByRate( rate, '-run-%s'%fname, hash( repr([cmd,to_notify]) ) ):
            return
        if self.vk.doPrepareOnly:
            return

        notify_ar = map( lambda s: (s.strip().split(':')+[''])[:2], to_notify )
        if notify_ar and _check( '.silent', fname ):
            DBG.info( 'silent %s', [fname])
            notify_ar = []

        global glob_notify
        glob_notify = notify_ar

        #debug
        #if request!='default':
        #    make_notify( ['TASK %s - request=%s'%(fname,request)], '.notificatons-messagerequest.log')

        if cmd[0]=='message' and len(cmd)>=4:
            if request=='default+autoclean':
                cmd += ["--KEEP_LAST_SECONDS=90", "--NOT_KEEP_IF_MINE=True", "--DEL_ENFORCED=True"] #- no del enforced because could del private video
                cmd[3]='1'
            if request=='store':
                cmd[3]='-1'
            elif request=='clean':
                cmd[3]='1'
                cmd+=["--KEEP_LAST_SECONDS=15", "--NOT_KEEP_IF_MINE=True"]

        stdout,stderr = RunMainScript( cmd )
        res = filter(lambda s: s.find("{MACHINE}:")>=0, stdout.splitlines(True) )       # filter only {MACHINE} lines
        res = map( lambda s: (s.split('{MACHINE}: mode=',1)+[s])[1], res )              # safe cutoff {MACHINE} and before from each line
        stdout = (''.join(res)).strip()
        print "--\n%s\n%s" % ( stdout, stderr )

        self.TouchHashFile()

        if cmd[0]!='message':
            return

        #msgid = 'default'   # -- this is for todo (is because of vk command received)

        IF_DEL = int(cmd[3])
        # case: default regular save (store msg with postponed del) - do not notify because this is regular thing. Check result in the log
        if ( IF_DEL==0 ):
            return

        # case: autosave on - do not notify if nothing was stored/deleted
        if ( IF_DEL==1 and request.startswith('default') and stdout.find('. *0')>=0 and stdout.find('), -0(')>=0 ):
            return

        make_notify( [stdout + (u'\nERR: %s'%stderr if stderr else '')], '.notificatons-messagebackup.log')


# Send notification about internal errors
def new_dbg_important( self, *kw, **kww ):
    old_dbg_important( *kw,**kww )
    try:
        Notifiers.bullet_notifier( util.unicformat(*kw,**kww), enforce = True )
    except Exception as e:
        tb = traceback.format_exception(sys.exc_type, sys.exc_value, sys.exc_traceback)
        old_dbg_important( 'FAIL TO notify DBG.important -- EXCEPTION: %s %s\n%s', [ type(e), unicode(e),
                            '\n'.join( filter(len, map( lambda s: s.rstrip(), tb)) ) ] )


if __name__ == '__main__':
    try:
        main()
        util.say("execution finished")
        fname = os.path.join( DIR_TMP, '.exception-notification' )
        if os.path.exists( fname ):
            os.unlink( fname )
    except Exception as e:
        tb = traceback.format_exception(sys.exc_type, sys.exc_value, sys.exc_traceback)
        DBG.important('EXCEPTION: %s %s\n%s', [ type(e), unicode(e),
                            '\n'.join( filter(len, map( lambda s: s.rstrip(), tb)) ) ] )
        msg = 'EXCEPTION: %s %s' % (type(e),e)

        # detect that we already notified about same exception on previous call
        sameFlag = False
        if 'DIR_TMP' in globals():
            fname = os.path.join( DIR_TMP, '.exception-notification' )
            if os.path.exists( fname ):
                with open(fname,'rb') as f:
                    storedmsg = str_decode( f.read(), 'utf-8' )
                    sameFlag = (storedmsg==unicode(msg))
            #if sameFlag and (os.path.getmtime()+600)>time.time():       # "same flag" expired in 10 minutes
            #    sameFlag = False

            if not sameFlag:
                for func in [Notifiers.bullet_notifier, Notifiers.logger_notifier ]:
                    glob_queue = main_notification_log
                    try:
                        func( Notifiers(), msg, enforce = True )
                    except Exception as e:
                        DBG.important('EXCEPTION WHEN NOTIFY: %s %s', [ type(e), unicode(e)] )
                with open(fname,'wb') as f:
                    storedmsg = f.write( util.str_encode( msg, 'utf-8' ) )
            else:
                DBG.trace('suppressed repeat of exception notification')
            ExecuteNotification()

        util.say_cp866( unicode(msg) )
        raise


