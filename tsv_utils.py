# coding=utf8

import os, sys, time, base64,re,codecs, types
from msvcrt import getch
from ctypes import *

import inspect

class FatalError(Exception):
    pass

class OkExit(Exception):
    pass

class SkipError(Exception):
    pass


def make_int( value, default = 0 ):
    try: return int(value)
    except: return default

def is_any_find( base, pattern_lst ):
    for p in pattern_lst:
        find = base.find(p)
        if find >= 0:
            return find+1
    return 0

def str_fulltime( t ):
    t = time.localtime(t)
    tt = "%02d.%02d.%04d %02d:%02d:%02d" % ( t.tm_mday, t.tm_mon, t.tm_year, t.tm_hour, t.tm_min, t.tm_sec)
    return tt

def make_join( sep, lst ):
    return sep.join( map(lambda v: str(v), lst) )

################################################################
#		STR FUNC
################################################################

baseencode = 'cp1251'
##baseencode = sys.getfilesystemencoding()      # 'mbcs' - doesn't decode
scriptencoding = 'utf-8'

# REPLACE DANGEROUS SYMBOLS
def fname_prepare(fname):
   for repl in ['"', ':', '\\', '/', '?', '*', '|' ]:
        fname = fname.replace( repl, '_' )
   return fname.strip()

# SAFE MAKE UNICODE STRING
def str_decode( s, enc=None ):
     if isinstance(s, str):
        if enc is None:
            enc = baseencode
        s = s.decode(enc,'xmlcharrefreplace')
     return s

# SAFE MAKE FROM UNICODE STRING
def str_encode( s, enc=None ):
     if isinstance(s, unicode):
        if enc is None:
            enc = baseencode
        s = s.encode(enc,'xmlcharrefreplace')
     return s

# SAFE TRANSCODING FROM ONE ENCODING TO ANOTHER
def str_transcode( s, src, tgt ):
    return str_encode( str_decode( s, src ), tgt )

# TRANSCODE src(baseencode) -> cp866
def str_cp866( s, src = None ):
    return str_encode( str_decode( s, src ), 'cp866' )


def str_encode_all( lst, enc = None ):
    return map( lambda s: str_encode(s,enc), lst )

def str_decode_all( lst, enc = None ):
    return  map( lambda s: str_decode(s,enc), lst )

def makehtml_unsafe( s, convertBR = False ):
    if convertBR:
        return s.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('  ',' &nbsp;').replace("\n", "<br>\n")
    else:
        return s.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('  ',' &nbsp;')
"""
    s = s.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('  ',' &nbsp;')
    if convertBR:
        s = s.replace("\n", "<br>\n")
"""

re_xmlref1 = re.compile("&amp;(#[0-9]+;)")
def makehtml( s, convertBR = False ):
    s = makehtml_unsafe( s, convertBR )
    return re_xmlref1.sub( '&\g<1>', s )



################################################################
#		STDOUT					       #
################################################################

def init_console():
    # Set console encoding
    reload(sys)
    sys.setdefaultencoding('utf-8')

DEBUG_LEVEL = 0
def dbg_print( level, s ):
    if level <= DEBUG_LEVEL:
        print s

def print_mark( mark ):
    sys.stdout.write(mark)
    sys.stdout.flush()

def unicformat( s, arg = None ):
    if arg is None:
        return str_decode( s, scriptencoding )
    if isinstance(arg,tuple):
        arg=list(arg)
    if not isinstance(arg,list):
        arg = [arg]
    for idx in xrange(0,len(arg)):
        if isinstance(arg[idx],str):
            arg[idx] = str_decode( str(arg[idx]) )
    try:
        return str_decode( s, scriptencoding ) % tuple(arg)
    except UnicodeDecodeError:
        for a in arg: print type(a)
        raise
    except UnicodeEncodeError:
        for a in arg: print type(a)
        raise

def _say_console( s = '', arg = None ):
    print unicformat( s, arg ).encode('cp866','xmlcharrefreplace')

say_buffer = ''
def _say_string ( s = '', arg = None ):
    say_buffer += unicformat( s, arg ).encode('cp866','xmlcharrefreplace') + "\n"

say = _say_console

def say_cp866( s ):
    print str_encode( s, 'cp866' )

def getinput( s ):
    if s:
        s = str_transcode(s,scriptencoding,'cp866')
        print_mark(s)
    if CONFIG.get('MACHINE',False):
        raise Exception('getinput() call for non-interactive mode')
    return raw_input('')

def getchar():
    if CONFIG.get('MACHINE',False):
        raise Exception('getchar() call for non-interactive mode')
    return getch()

def confirm( prompt, choiceList = None ):
        if choiceList is None:
            #choiceList = {'n':0,'y':1,u'д':1,u'н':0}
            choiceList = ['n','y']  #ignore Д/Н because 'Н' is on the same button as 'Y' and so could give wrong answer accidentally


        if not isinstance(choiceList,dict):
            choiceList = dict( map(lambda idx: [ str_decode(choiceList[idx],'utf-8').lower(), idx], range(0,len(choiceList))) )

        sys.stdout.write( str_decode( prompt, scriptencoding ) )
        sys.stdout.flush()
        if CONFIG.get('MACHINE',False):
            raise Exception('confirm() call for non-interactive mode')
        val = ''
        while val.lower() not in choiceList:
          val = str_decode(getch(),'cp866')
          if ord(val)==3:
             raise KeyboardInterrupt
          if ord(val)<32:
            print_mark( "{%d}"%ord(val) )
            continue
          sys.stdout.write(val)
        print
        val = str_decode(val).lower()
        return choiceList[val]

################################################################


def TODO( mark, fatal=False ):
    frame = inspect.stack()[1]
    say( "%s at %s:%s", (mark, frame[1], frame[2]) )
    if fatal:
        exit(1)

class DBG(object):
    OFF = -1
    IMPORTANT = 0
    ERROR = IMPORTANT
    INFO = 1
    TRACE = 2

    """ members """

    logfile_name='./LOG/vk_downloader'
    createdFlag = False         # If initialized with True - donot create logdir
    level = IMPORTANT           # -1=turn off, 0-important, 1-info, 2-trace
    level_exception = IMPORTANT
    fname_suffixes = ['.log', '_info.log', '_trace.log' ]

    """ methods """

    @staticmethod
    def _write( fname, text ):
        with codecs.open(fname,'ab','utf-8') as f:
            f.write(text)

    @staticmethod
    def _log( lev, *kw, **kww ):
        if DBG.level<lev:
            return None
        message = unicformat(*kw,**kww)
        try:
            if not DBG.createdFlag:
                dname = os.path.split(os.path.abspath(DBG.logfile_name))[0]
                if not os.path.exists(dname):
                    os.makedirs( dname )
                DBG.createdFlag = True
            txt = u"%s %s\n" % ( time.strftime("%d.%m %H:%M:%S"), message  )
            for lev in range(lev,3):
                if lev<=DBG.level:
                    DBG._write( DBG.logfile_name + DBG.fname_suffixes[lev], txt)
        except:
            pass
        return message

    @staticmethod
    def say( lev, *kw, **kww ):
        say(*kw,**kww)
        DBG._log( lev, *kw, **kww )

    @staticmethod
    def exception( *kw, **kww ):
        prefix = ''
        if kw:
            prefix = unicformat(*kw,**kww)
        t, value, tb = sys.exc_info()
        frame= tb[0]
        txt = unicformat( u"%s %s:%s at %s:%s {%s}", ( prefix, type(t), value, frame[1],frame[2],fname[3] ) )
        DBG._log( DBG.level_exception, txt )
        return message

    @staticmethod
    def TODO( *kw, **kww ):
        frame = inspect.stack()[1]
        txt = unicformat(*kw,**kww)
        txt += u" at %s:%s {%s}" % (frame[1],frame[2],fname[3])
        DBG.say( 0, txt )

    @staticmethod
    def important( *kw, **kww ):
        DBG._log( 0, *kw, **kww )

    @staticmethod
    def error( *kw, **kww ):
        DBG._log( 0, *kw, **kww )

    @staticmethod
    def info( *kw, **kww ):
        DBG._log( 1, *kw, **kww )

    @staticmethod
    def trace( *kw, **kww ):
        DBG._log( 2, *kw, **kww )

_debugGuard = False
def debugDump( obj, short = False ):
    global _debugGuard
    if _debugGuard:
         return
    _debugGuard = True
    rv = "Object %s (%d)" % ( obj.__class__, id(obj) )
    for attr in dir(obj):
        if short and attr.startswith('__') and attr.endswith('__'):
                continue
        rv += "\nobj.%s = %s" % (attr, getattr(obj,attr))
    _debugGuard = False
    return rv


################################################################

def get_args( delFirst = True ):
    size = c_int()
    ptr = windll.shell32.CommandLineToArgvW(windll.kernel32.GetCommandLineW(), byref(size))
    ref = c_wchar_p * size.value
    raw = ref.from_address(ptr)
    args = [arg for arg in raw]
    windll.kernel32.LocalFree(ptr)
    if delFirst and len(args)>1:
      if args[1]==sys.argv[0].decode('cp1251','ignore'):
        args = args[1:]
    return args


sysargv = sys.argv
def getSysArgv():
    global sysargv
    return sysargv

winsysargv = None
def getWinSysArgv( delFirst = True ):
    global winsysargv
    if winsysargv is None:
        winsysargv = get_args( delFirst )
    return winsysargv

################################################################
#		CONFIG/DATA FILES MANIPULATE
################################################################

# auxilary func
def _load_splited_lines( fname, enc, tgt_enc ):
    frame = inspect.stack()[1]
    func_name = frame[3]
    if not os.path.exists( fname ) or not os.path.isfile(fname):
        DBG.error( "No file '%s' found at %s()", [fname,func_name] )
        return None
    DBG.trace( "Load '%s' at %s() as '%s'/%s", [fname,func_name,enc,tgt_enc] )
    with codecs.open(fname, 'r', enc) as f:
        if tgt_enc is None:
            rv = f.read().splitlines()
        else:
            rv = str_encode( f.read(), tgt_enc ).splitlines()
    if func_name!='load_data_file':
        DBG.trace( u"CONTENT:\n%s", u'\n'.join(rv))
    return rv

#
# load plain data file
#       enc - encoding of file
#       tgt_enc - if None - leave unicode, otherwise - convert to this encoding
#
#  RETURNS: lines, resset
#       lines[row] = [ col1, col2, ...]
#       resset = set() of col[main_col]
#                or dict():  resset[main_col[0]]=main_col[1]
#
def load_data_file( fname, main_col = 0, sep = "\t", enc="utf-8", tgt_enc = None ):
    lines = _load_splited_lines( fname, enc, tgt_enc )

    is_int = isinstance( main_col, types.IntType)
    if lines is None:
        return [], ( set() if is_int else dict() )
    lines = map( lambda s: s.split(sep), lines )
    if is_int:
        resset = set( map(lambda a: a[main_col], lines) )
    else:
        kcol, vcol = main_col[:2]
        resset = dict( map(lambda a: [ a[kcol], a[vcol] ], lines) )
    return lines, resset

#
# Save plain data file
#       enc - encoding of file
#       src_enc - if None - leave as is, otherwise - needs transcoding from this
#
def save_data_file( fname, lst, sep = '\t', enc='utf-8', src_enc = None ):
    if not ( isinstance(lst,list) or isinstance(lst,tuple) ):
        return
    with codecs.open(fname,'w',enc) as f:
        for l in lst:
            if src_enc is None:
                f.write( sep.join(l) + '\n' )
            else:
                f.write( str_decode( sep.join(l), src_enc ) + u'\n' )

    if DBG.level >= DBG.TRACE:
        DBG.trace("save_data_file('%s',%s)", [fname,lst])
        with codecs.open(fname,'rb',enc) as f:
            DBG.trace( u"%s", [f.read()] )

#
# load dictionary file ( default: key=val1|val2| )
#       enc - encoding of file
#       tgt_enc - if None - leave unicode, otherwise - convert to this encoding
#
def load_dict_file( fname, key_sep = "\t", val_sep = "|", enc="utf-8", tgt_enc = None ):
    lines = _load_splited_lines( fname, enc, tgt_enc )
    if lines is None:
        return dict()
    res = {}
    for l in lines:
        ar = l.split(key_sep,1)
        if len(ar)<2:
            continue
        ar_v = ar[1].split(val_sep)
        if len(ar_v)==1:
            ar_v=ar_v[0]
        res[ar[0]] = ar_v
    return res

#
# Save dictionary file
#       enc - encoding of file
#       src_enc - if None - leave as is, otherwise - needs transcoding from this
#
def save_dict_file( fname, d, key_sep = "\t", val_sep = "|", enc="utf-8", src_enc = None ):
    if not isinstance(d, dict):
        return
    with codecs.open(fname,'w',enc) as f:
        for k in sorted(d):
            v = d[k]
            if isinstance(v,list) or isinstance(v,tuple):
                v = val_sep.join(v)
            if src_enc is None:
                f.write( "%s%s%s\n" %(k,key_sep,v) )
            else:
                f.write( str_decode( "%s%s%s\n" %(k,key_sep,v) ) )

    if DBG.level >= DBG.TRACE:
        DBG.trace("save_dict_file('%s',%s)", [fname,lst])
        with codecs.open(fname,'rb',enc) as f:
            DBG.trace( u"%s", [f.read()] )


################################################################
#		SIMPLE ENCRYPTION			       #
################################################################

def str_crypt64( s, key ):
    ar = map( ord, s )
    for i in range(0,len(ar)):
        ar[i] = ar[i]^ord(key[-i%len(key)] )
    return base64.b64encode( ''.join(map(chr,ar)) )

def str_decrypt64( s, key ):
    try:
       ar = map( ord, base64.b64decode(s) )
    except Exception as e:
        print "Malformed pwd: %s" % str(e)
        return ''
    for i in range(0,len(ar)):
        ar[i] = ar[i]^ord(key[-i%len(key)] )
    return  ''.join(map(chr,ar))


################################################################
#		OPERATIONS WITH IMPORT			       #
################################################################

class ObjAsDict(object):
    def __init__( self, d ):
        self.d = d

    def __setitem__( self, k, v ):
        setattr( self.d, k, v )

    def setdefault( self, k, v ):
        if not hasattr(self.d,k):
            setattr( self.d, k, v )

class PatternSimple(object):
    def __init__( self, p ):
        if p=='*':
            self.handler = PatternSimple._all
        elif isinstance(p,list):
            self.p = p
            self.handler = PatternSimple._exactList
        elif p[0]=='*':
            self.p = p[1:]
            self.handler = PatternSimple._end
        elif p[-1]=='*':
            self.p = p[:-1]
            self.handler = PatternSimple._start
        else:
            self.p = p
            self.handler = PatternSimple._exact

    def do( self, v):
        return self.handler(self,v)
        ##print "%s=%s (%s)" % (v,r,self.handler)
    def _all( self, v ):        return not v.startswith('__')
    def _start( self, v ):      return v.startswith(self.p)
    def _end( self, v ):        return v.endswith(self.p)
    def _exact( self, v ):      return v == self.p
    def _exactList( self, v ):  return v in self.p


# USAGE:
#   import_vars( dstdict|dstmodule, srcdict|srcmodule, [pattern1,pattern2,..] )
#
# EXAMPLES:
#   import_vars( globals(), module2, ['CONF*'] )
#   import_vars( module1, my_dict )
#   import_vars( my_dict2, my_dict, ['CONF*'] )
#
def import_vars( to_dict, from_, patterns = None, isOverwrite = True ):
    ##print "==\nimportvars(__, %s, %s, %s)" % (from_, patterns, isOverwrite)

    if isinstance( from_, types.ModuleType ):
        d = {}
        for attr in dir(from_):
            if not attr.startswith('__'):
                d[attr]=getattr(from_,attr)
        from_ = d

    if isinstance( to_dict, types.ModuleType ):
        to_ = ObjAsDict( to_dict )
    else:
        to_ = to_dict

    if patterns is None:
        patterns=['*']
    elif isinstance( patterns, str ):
        patterns = [ patterns ]

    # performance optimization
    if '*' in patterns:     # if asterisk defined - no other needed
        patterns=['*']
    else:
        patterns = filter( len, patterns )
    exactPatterns = filter(lambda s: s[0]!='*' and s[-1]!='*', patterns )
    fuzzyPatterns = filter(lambda s: s not in exactPatterns, patterns )

    patterns = map( lambda p: PatternSimple(p), fuzzyPatterns )
    if len(exactPatterns):
        patterns.append( PatternSimple(exactPatterns) )

    for k, v in from_.iteritems():
        for p in patterns:
            if p.do(k):
                if isOverwrite:
                    to_[k]=v
                else:
                    to_.setdefault(k,v)
                break

###
def print_vars( varlist, vardict ):
    for v in varlist:
        print "%s=%s" % ( v, repr(vardict.get(v,None)) )

