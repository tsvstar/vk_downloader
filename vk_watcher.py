# coding=utf8
import os, sys, time, base64,re,codecs, subprocess,random,re
import vk
#import collections
import traceback, imp

import vk_utils
import tsv_utils as util
from tsv_utils import DBG

"""========================================="""

BASE_DIR='"C:\\MY\\VK_DOWLOAD\\'

import config
def LoadConfig():
    more_options = { 'PIN':           '0000',       # pin for vk_status and vk_help; have to be empty or string at least 2 digit
                     #'PIN_COMMAND':   '',           # if given then you have to enter command like 'vk_watch3222 opt'
                     #'ALLOWED_USERS': '',           # separated by '|' list of ids of allowed to give commands users
                     #'USER2NOTIFY':   '',
                     'COMMAND_USER':  '',           # userid from who will comes commands
                     'DEFAULT_USER':  '',           # default argument "WHO" for bot commands if not given (have to be userid)

                     'ALIASES':     {111: 'D'},     # JSON-like value to make shorter and hidden names ( {1:"Д", -15:"-FM" } )
                     'USERS':       {'Durov':111},  # JSON-like value to give user/group in command

                     'MACHINE':     True,           # Replace this with False only to initialize passwords

                     'DOWNLOAD_OPT': '--DOWNLOAD_MP3=True --DAYBEFORE=7', # extra command line options to run vk_downlaoder
                     'AUTOCLEAN_OPT': '',
                     'WATCH_OPT': '',

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


""" Command object """
class CMD(object):

    cmdl = []       # [list of command] normalized to [0CMD, 1STATE, 2WHO, 3EXTRA]
    cmd = ""        # name of command without api suffix (autodel2 -> autodel )
    main_cmd =""    # real name of command (resolved alias: autodel -> autoclean )
    vk_api = None   # correspondend to suffix vk_api
    isWatcher = False # False if this is instant command, True if this is watcher object
    tag = ""        # tag = "CommandSuffix:WHO"
    userid = 0
    username = ""   # resolved user name

    def __init__( self, cmdl ):
        cmdl = map( str.lower, cmdl )
        if len(cmdl)>=2 and cmdl[0] in ['on','off']:
            cmdl = [ cmdl[1], cmdl[0] ] + cmdl[2:]
        self.cmdl = cmdl

        self.cmd, self.vk_api = self.getCommandName( cmdl[0] )

        if self.cmd not in COMMAND_PROCESSORS:
            raise SkipError(u"unknown command '%s'"% cmdl[0])

        self.main_cmd = COMMAND_PROCESSORS[ self.cmd ] if isinstance( COMMAND_PROCESSORS[ self.cmd ], basestring ) else self.cmd
        self.isWatcher = maincmd in WATCH_PROCESSORS

        pin = str( config.CONFIG.get('PIN','') )
        if len(pin)>1 and self.cmdl[0].endswith(pin):     # cutoff pin
            self.cmdl[0] = self.cmdl[0][:-len(pin)]

        if self.isWatcher:
            if len(cmdl)<2:
                raise SkipError(u"no state given for command %s"%cmdl[0])
            if cmdl[1] not in ['on','off']:
                raise SkipError(u"wrong state '%s' given for command %s"%(cmdl[1],cmdl[0]))

        # add default user
        min_size = 3 if isWatcher else 2
        if len(cmdl)<min_size:
            if not config.CONFIG['DEFAULT_USER']:
                raise SkipError(u'no user given and no default exists')
            self.cmdl.append( config.CONFIG['DEFAULT_USER'] )

        # resolve to userid "who"
        who_pos = (min_size - 1)
        if self.main_cmd!='userdef':
            self.userid = util.make_int( self.cmdl[who_pos], -1 )
            if self.userid<=0:
                if self.cmdl[who_pos] not in config.CONFIG['USERS']:
                    raise SkipError( util.unicformat(u"Unknown user '%s' for command %s",[self.cmdl[who_pos],self.cmdl[0]]) )
                self.userid = config.CONFIG['USERS'][self.cmdl[who_pos]]
            #self.username = config.CONFIG['ALIASES'].get( self.userid, str(self.userid) )
            self.cmdl[who_pos] = str(userid)

        self.who_pos = who_pos
        self.tag = "%s%d:%s" % ( self.main_cmd, 1 if self.vk_api==vk_api1 else 2, self.cmdl[who_pos] )

    """ """
    def get( self, name ):
        if name=='cmd':
            idx = self.getStatePos()
            if idx==0:
                return self.cmdl[1]
            else:
                return self.cmdl[0]
        elif name=='state':
            idx = self.getStatePos()
            if idx<0:
                return None
            else:
                return self.cmdl[idx]
        elif name=='who':
            return self.cmdl[who_pos]
        else:
            return None

    def getStatePos( self ):
        if not self.isWatcher:
            return -1
        return 0 if self.cmdl[1] not in ['on','off'] else 1


    """ Normalize to "NORMAL" format CMD_STATE_WHO_EXTRA  """
    def setNormalFormat( self ):
        if not self.isWatcher or self.cmdl[1] not in ['on','off']:
            return self.cmdl
        self.cmdl = [ self.cmdl[1], self.cmdl[0] ] + self.cmdl[2:]
        return self.cmdl

    """ Normalize to "FILE" format STATE_CMD_WHO_EXTRA """
    def setFileFormat( self ):
        if not self.isWatcher or self.cmdl[0] not in ['on','off']:
            return self.cmdl
        self.cmdl = [ self.cmdl[1], self.cmdl[0] ] + self.cmdl[2:]
        return self.cmdl

    """ Parse command name and return ( name, vk_api ) """
    @staticmethod
    def getCommandName( cmd ):
        if len(cmd)==0 or cmd[-1] not in ['1','2']:
            return cmd, vk_api1
        elif cmd[-1]=='2':
            return cmd[:-1], vk_api2
        return cmd[:-1], vk_api1

    """ Set status of command in filesystem to cmdl[0]
        NOTES: 1) fname  - if not None then this is current file name (could differ from regular if postponed)
               2) assumed that give command in "FILE" format
    """
    @staticmethod
    def CommandSetStatus( fname, cmdl ):
        opposite_cmd = ['off' if (cmdl[0]=='on') else 'on'] + cmdl[1:]
        fname_old, fpath, fpath_opposite = fname, getPath('_'.join(cmdl)), getPath('_'.join(opposite_cmd))
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
                f.write("# coding=utf8\n")

        # clean up
        if fname_old and os.path.exists( fpath_old ):
            os.unlink( fpath_old )

"""========================================="""
class CMDPool(object):

    @staticmethod
    def ScanCommands( handler ):
        for fname in os.listdir(DIR_MAIN):
            fpath = os.path.join(DIR_MAIN,fname)
            if not os.path.isfile(fpath):
                continue

            cmdl = fname.lower().split('_')
            if handler( fname, cmdl ):
                break

    # check for posponed actions
    """!TODO!"""
    @staticmethod
    def HandlerPostponed( fname, cmdl ):

        if cmdl[0]=='time' and len(cmdl)>3:
            t = util.make_int(cmdl[1])
            if (t>now):
                return
            cmdl = cmdl[2:]                       # cutoff time_TIMESTAMP
            CMD.setNormalFormat(cmd)
            maincmd, isWatcher = getCommand( cmd[0] )
            if isWatcher:
                CommandSetStatus( fname, cmd )
                CommandLog( cmd, status = None )
            else:
                CommandExecute( cmd, mode = 'postponed' )
        return False

    """!TODO!"""
    @staticmethod
    def HandlerCheck( fname, cmdl ):

        # skip postponed
        if cmdl[0]=='time' and len(cmdl)>3:
            return False

        if cmdl[0]=='cfg':
            if cmdl[1]=='defaultuser':
                try:
                    with open( getPath(fname), 'rb' ) as f:
                        config.CONFIG['DEFAULT_USER']= int(f.read().strip())
                except Exception as e:
                    print "Wrong %s - not integer" % fname
                continue

        # skip on/off actions
        if len(cmdl)>2 and  cmdl[0] in ('off','on'):
            return False

        util.say( "ERROR: unknown format file: %s", [fname] )


"""========================================="""
class WatcherExecutor(object):
    vk_api = []
    watchers = []

    def __init__( self ):
        self.vk_api = []
        self.watchers = []

    def collectWatchers( self, fname, cmdl ):
        if cmdl[0] in ['on','off']:
            watcher.append( Watcher( self, fname, cmdl ) )


class Watcher(object):

    def __init__( self, pool, fname, cmdl ):
        self.pool = pool
        self.cmd = CMD(cmdl)
        self.api = 1 if self.cmd.vk_api==vk_api1 else 2
        self.me = me1 if self.api==1 else me2
        self.Error = ''
        self.tmpFileName = os.path.join( DIR_TMP, '.'+'_'.join(cmdl[1:]))

        self.module = None
        if not self.cmd.isWatcher:
            self.Error = u"unknown watcher '%s'" % self.cmd.main_cmd
            DBG.important(self.Error)
            return

        self.default_module = WATCH_PROCESSORS[self.cmd.main_cmd]

        try:
            was = sys.dont_write_bytecode
            self.module = imp.load_source("module", getPath(fname) )
        except Exception as e:
            self.Error = u"fail to load '%s':%s" % (fname,str(e))
            DBG.important(self.Error)
            return
        finally:
            sys.dont_write_bytecode = was

        global_export = [ 'now', 'me1', 'me2', 'flags', 'USER_LOGIN', 'COMMAND_USER',
                      'DIR_MAIN', 'DIR_LOG','DIR_TMP', 'vk_utils', 'util', 'config',
                      'DBG', 'ReplaceAlias', 'ExecuteDownloadMSG', 'SendMsg' ]
        util.import_vars( self.module, self, ['cmd','me','tmpFileName','default_module'], isOverwrite=True )
        util.import_vars( self.module, self.default_module, '*', isOverwrite=False )
        util.import_vars( self.module, globals(), global_export, isOverwrite=True )
        DBG.trace("Loaded '%s':\n%s" % (fname,util.debugDump(self.module,short=True)) )


    def run( self, method, **kww ):
        defaultHandler = kww.pop('defaultHandler',False)
        handlerModule = self.default_module if ( defaultHandler or not hasattr(self.module,method) ) else self.module
        DBG.trace("%s.run('%s',%s)" % (self, self.method, kww) )
        DBG.trace(" --> module=%s, default=%s, choosed=%s" % (self.module, self.default_module, handlerModule))
        if not hasattr(handlerModule,method):
            raise SkipError("no '%s' method" % method)

        module = self.module
        ( module.vk_api1, module.vk_api2, module.vk_api ) = (pool.vk_api[0], pool.vk_api[1], pool.vk_api[self.api-1] )
        module.vk_api = module.vk_api1 if self.api==1 else module.vk_api2
        module.errorMessage = self.Error
        DBG.trace(" --> execute %s() with vk_api=%s/me=%s" % ( getattr( handlerModule, method ), module.vk_api, module.me))
        rv = getattr( handlerModule, method )( module, *kww )
        self.Error = module.errorMessage
        DBG.trace(" --> result=%s (err=%s)" % ( rv, self.Error) )
        return rv



"""========================================="""

class CmdHandlers(object):
    @staticmethod
    def cmdStatus( cmd_obj, current_frame ):
        current_frame[2]= True
        if flags.get('vk_status',False):
            current_frame[0]=None
            return
        flags['vk_status'] = True

    @staticmethod
    def cmdHelp( cmd_obj, current_frame ):
        current_frame[2]= True
        if flags.get('vk_help',False):
            current_frame[0]=None
            return
        flags['vk_help'] = True
        text = """
vk_statusPIN
vk_keep|vk_clean [WHO]           =
vk_join|vk_leave [WHO]           = join/leave group
vk_autoclean[1|2] on|off [WHO]   = periodic vk_clean(on)/vk_keep(off)
vk_watch[1|2] on|off [WHO]       = watch wall/ph/video/audio
vk_userdef[1|2] on|off [WHO] EXTRA = control userdefined modules
... /XX[m|h] - postponed command (todo)
... @ - silent command
        """.strip()
        vk_api1.messages.send( user_id=COMMAND_USER, message='vk:\n'+text )

    @staticmethod
    def cmdSetWatcher( cmd_obj, current_frame ):
        try:
            # need 'file' format
            cmd_obj.setFileFormat()
            # ensure that resolved command with suffix is used
            cmd_obj.cmdl[1] = cmd_obj.main_cmd + ('2' if cmd_obj.vk_api==vk_api2 else '1')
            # set status
            cmd_obj.CommandSetStatus( None, cmd_obj.cmdl )
        finally:
            cmd_obj.setNormalFormat()

    @staticmethod
    def cmdJoinLeave( cmd_obj, current_frame ):
        if cmd_obj.cmdl[0]=='join':
            cmd_obj.vk_api.groups.join(group_id=cmd)
        else:
            cmd_obj.vk_api.groups.leave(group_id=cmd)

    @staticmethod
    def cmdMsgDload( cmd_obj, current_frame ):
        IF_DELETE = 1 if cmd_obj.cmdl[0]=='clean' else -1
        tag = "msg:%s" % cmd_obj.userid
        if tag in flags:
            current_frame[1] = "already done"
        #RunMainScript( cmd )
        # ExecuteMainScriptAsMachine()
        message, stderr =  ExecuteDownloadMSG( cmd_obj.userid, IF_DELETE, config.CONFIG.get('DOWNLOAD_OPT',[]) )

        # if not silent - say
        if not current_frame[2]:
            SendMsg( vk_api1, message, prefix=(u'vk:%s/'%cmd_obj.userid), _replaceAlias = True )

        # we said so no need to say more
        current_frame[2]= True

"""========================================="""
def RunMainScript( cmd ):
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

def SendMsg( vk_api, message, prefix = None, _replaceAlias = False ):
    DBG.trace(u"SendMsg( %s, msg='%s', prefix='%s', aliase=%s\n%s", [vk_api,message,prefix,_replaceAlias,traceback.format_stack(5)] )
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
import vk_watcher_modules

COMMAND_PROCESSORS = { 'keep':  'store',
                       'store': CmdHandlers.cmdMsgDload,
                       'clean': CmdHandlers.cmdMsgDload,
                       'del':   'clean',
                       'join':  CmdHandlers.cmdJoinLeave,
                       'leave': CmdHandlers.cmdJoinLeave,
                       'status'+config.CONFIG.get('PIN',''): CmdHandlers.cmdStatus,
                       'help'+config.CONFIG.get('PIN',''):   CmdHandlers.cmdHelp,
                       #'restore': CmdHandlers.cmdRestore,

                       'autoclean':  CmdHandlers.cmdSetWatcher,
                       'autodel':    'autoclean',
                       'watch':      CmdHandlers.cmdSetWatcher,
                       'backupwall': CmdHandlers.cmdSetWatcher,
                     }

WATCH_PROCESSORS = {    'autoclean': vk_watcher_modules.AutoCleanWatcher,
                        'userdef':   vk_watcher_modules.DefaultWatcher,
                        'watch':     vk_watcher_modules.GroupWatcher,
                        #'backupwall': vk_watcher_modules.BackupWall,
                   }


"""========================================="""

def main():

    util.init_console()
    DBG.logfile_name='./LOG_WATCHER/vk_watch'
    DBG.level = DBG.TRACE

    DBG.important( u">>> RUN vk_watcher at %s" % os.getcwdu() )
    if 'BASE_DIR' in globals() and BASE_DIR:
        os.chdir(BASE_DIR)

    LoadConfig()
    USER_LOGIN = config.CONFIG['USER_LOGIN'].strip()
    if not USER_LOGIN:
        raise util.FatalError('Unknown USER_LOGIN')


    DIR_MAIN = os.path.join( os.getcwdu(), '.vk_watcher-%s'%USER_LOGIN )
    DIR_LOG = os.path.join( DIR_MAIN, 'log' )
    DIR_TMP = os.path.join( DIR_MAIN, 'tmp' )

    global LOCKFILE
    LOCKFILE = os.path.join(DIR_TMP,'lockfile.group_watch')
    AddLockFile( timeout=50 )

    """"
    BASEDIR = os.path.join( os.getcwdu(),u"MSG-%s" % USER_LOGIN )
    if not os.path.exists(BASEDIR):
        os.makedirs(BASEDIR)
    """

    import vk.api
    vk.api.LOG_DIR = "./LOG_WATCHER"
    vk_api1, me1, USER_PASSWORD1 = vk_utils.VKSignIn( USER_LOGIN, False )
    vk_api2, me2, USER_PASSWORD2 = vk_utils.VKSignInSecondary( False )
    now = time.time()

    COMMAND_USER = config.CONFIG.get('COMMAND_USER','')
    if not COMMAND_USER:
        COMMAND_USER = me1
        config.CONFIG['COMMAND_USER']=COMMAND_USER

    flags = {}              # any kind of common flags (already done executed)
    commands = []           # [ [0CMD, 1msg, 2silence], ... ]
    logMessage = []
    toDelMsgIds = set()
    #executedCmd = collections.OrderedDict()     # ['cmd' = status]

    # IMPORTANT: set all local values to globals
    util.import_vars( globals(), locals(), '*', isOverwrite=True )

    CMD_PREFIX = 'vk_'

    try:
        # Execute posponed commands
        ##CMDPool.ScanCommands( CMDPool.HandlerPostponed )
        ##CMDPool.ScanCommands( CMDPool.HandlerCheck )

        # Scan incoming messages to get commands
        res =  vk_api.messages.getHistory( offset=0, count = 30, user_id = me, rev = 1 )
        for item in res[u'items']:
            body = item.get(u'body','').strip().lower()
            if not body.startswith(CMD_PREFIX):
                continue

            delMsgId = item.get(u'id',0)
            lst = map(str.strip, body.split('\n') )
            DBG.info( u"catch command(id=%s): %s", (delMsgId,lst) )
            for cmd in lst:
                if not cmd.startswith(CMD_PREFIX):
                    continue
                toDelMsgIds.add( delMsgId )
                silence = cmd.endswith('@')
                if silence:
                    cmd = cmd[:-1]
                try:
                    command.append( [ CMD(cmd[len(CMD_PREFIX):].split()), None, silence ] )
                except Exception as e:
                    command.append( [ None, str(e), False ] )       # u"%s - FAIL(%s)" % (cmd,str(e))

        dbg = "==COMMANDS:\n"
        for c in commands:
            dbg+= "=%s\n"%repr(c)
            if c[0] is not None:
                dbg+= util.debugDump(c[0],True)
        DBG.trace( dbg )

        # Execute commands
        DBG.TODO('Execute commands')
        for frame in commands:
            try:
                if frame[0] is not None:
                    DBG.trace("COMMAND: %s -> %s(%s)", [ frame[0].main_cmd, COMMAND_PROCESSORS.get(frame[0].main_cmd,None), frame ] )
                    COMMAND_PROCESSORS[frame[0].main_cmd]( frame[0], frame )
            except Exception as e:
                frame[1] = str(e)

        # Observers: a) prepare the list
        DBG.TODO('Observers')
        pool = WatcherExecutor()
        pool.vk_api = [ vk_utils.BatchExecutor(vk_api1),
                        vk_utils.BatchExecutor(vk_api2) ]
        CMDPool.ScanCommands( pool.collectWatchers )

        # b) 1st pass (prepare cached queries)
        postponed = []
        for c in pool.watchers:
            try:
                if c.Error:
                    raise util.SkipError(c.Error)
                if not c.run('CheckWatcherStatus'):
                    continue
                if c.run( 'Prepare', isDryRun = True ):
                    c.run( 'DoAction', isDryRun = True )
                    postponed.append(c)
            except Exception as e:
                DBG.important(str(e))
                c.Error = str(e)
        for c in postponed:
            try:
                c.run( 'Postprocess' )
            except Exception as e:
                DBG.important(str(e))
                c.Error = str(e)

        # c) 2nd pass (actually execute watchers)
        for idx in [0,1]:
            pool.vk_api[idx] = vk_utils.CachedVKAPI( pool.vk_api[idx].vk_api, pool.vk_api[ix] )

        for c in pool.watchers:
            try:
                if c.Error:
                    raise util.SkipError(c.Error)
                if not c.run('CheckWatcherStatus'):
                    continue
                message = None
                if c.run( 'Prepare', isDryRun = False ):
                    message = c.run( 'DoAction', isDryRun = False )
                    c.run( 'Postprocess', isDryRun = False )
                #if message and not c.Error:
                if message and not c.Error:
                    if c.run( 'Notify', message = message ):
                        c.run( 'Notify', message = message, defaultHandler = True )

                if not c.Error:     # no need to include this into status
                    continue
            except Exception as e:
                DBG.important(str(e))
                c.Error = str(e)

            c.cmd.cmdl[0] = u"[auto]" + c.cmd.cmdl[0]
            commands.append( [ c.cmd, c.Error, True ] )

    finally:

        # execute 'vk_status' command
        try:
            status = {}
            users = map( lambda i: [ i[1], str(i[0]) ], config.CONFIG.get('USERS',{}).iteritems() )
            def addStatus(fname, cmdl):
                DBG.trace('addStatus(%s,%s)', [fname,cmdl])
                if cmdl[0] not in ['on','off'] or len(cmdl)<3:
                    return
                cmdl[2] = users.get( cmdl[2], cmdl[2] )
                status[fname] = ' '.join(cmdl)

            if 'vk_status' in flags:
                CMDPool.ScanCommands(addStatus)
                DBG.trace(status)
                status = map( lambda k: status[k], sorted(status.keys()) )
            if status:
                SendMsg( vk_api1, '\n'.join(status), prefix=u'vk: status\n' )

        except Exception as e:
            DBG.TODO(str(e))

        # send the commands status message if any non-silent or error
        try:
            if filter(lambda c: c[2] or c[1], commands ):
                aliases = map( lambda i: [ str(i[0]), repr(i[1])], config.CONFIG.get('ALIASES',{}).iteritems() )
                logMessageCmd = []
                for c in commands:
                    if not c[0].cmdl:
                        continue
                    cmdl = ' '.join(c[0].cmdl)
                    for a in aliases:
                        cmdl = cmdl.replace(a[0],a[1])
                    logMessageCmd.append( u"%s%s" % (cmdl, u' - FAIL(%s)'%c[1] if c[1] is not None else '') )
                logMessage = logMessageCmd + logMessage
            if logMessage:
                SendMsg( vk_api1, '\n'.join(logMessage), prefix=u'vk: ' )
        except Exception as e:
            DBG.TODO(str(e))

        # delete messages
        if toDelMsgIds:
            util.TODO('Maybe filter only that messages which were completely executed or failed??')
            DBG.trace("%s", [toDelMsgIds])
            vk_api1.messages.delete( message_ids = ','.join(map(str,toDelMsgIds)) )


exit()

"""*************************************************************************************************************"""
"""*************************************************************************************************************"""
"""*************************************************************************************************************"""

executed = {}       # list of tags for executed commands (prevent to execute already done keep ) (??? maybe just list of users for which messages was stored)??

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


