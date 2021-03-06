# coding=utf8

# script.py LOGIN PASSWORD [uid=x,uid=y,chat=z]


import os, time, base64, re, codecs, random     #, pickle,urllib
import vk, pytube
import config
import vk_utils
import tsv_utils as util
from tsv_utils import str_encode, str_decode, str_cp866, fname_prepare, makehtml, say, unicformat, OkExit, FatalError, DBG, inputencoding
from vk_utils import profiles, get_profile, make_profilehtml, make_profiletext

DBGprint = util.dbg_print        # alias
try:
    O_BINARY = os.O_BINARY
except:
    O_BINARY = 0

"""
##########################################
#   LOAD AND PROCESS CONFIG + SYSARGV    #
##########################################
"""

def Initialize():
    global WHAT,RESTORE_FLAG,MAIN_PROFILE, IF_DELETE_GLOBAL, CONFIG

    # Copy util.CONFIG to this module globals
    CONFIG = config.CONFIG
    util.import_vars( globals(), config.CONFIG, config.dflt_config.keys(), isOverwrite=True )
    IF_DELETE_GLOBAL = CONFIG['IF_DELETE']

    say()

    # Parse main ARGV parameters
    sysargv = util.getSysArgv()
    if os.name=='nt':
        ARGV = util.getWinSysArgv()
    else:
        ARGV = list( sysargv )

    WHAT = sysargv[1].lower() if len(sysargv)>1 else ''
    if not WHAT:
        WHAT='ask'
    RESTORE_FLAG =  -1 if ( WHAT.find('restore')==0 ) else 0
    if RESTORE_FLAG:
       WHAT = WHAT[len('restore:'):]
       if len(WHAT)==0: WHAT='message'
    if len(sysargv)>2 and len(sysargv[2]): CONFIG['USER_LOGIN'] = sysargv[2]
    if len(sysargv)>3: MAIN_PROFILE  = ARGV[3]
    try:
        if len(sysargv)>4: IF_DELETE_GLOBAL = int(sysargv[4])
    except:
        pass


    if CONFIG['USER_LOGIN'] and not CONFIG['USER_LOGIN'].startswith('+') and CONFIG['USER_LOGIN'].find('@')<0:
        raise FatalError( unicformat("Неверный логин - %s",[CONFIG['USER_LOGIN']]) )


    # Basic validations
    try:
        if CONFIG['APP_ID'] is None:
            raise FatalError()
        CONFIG['APP_ID'] = int(APP_ID)
    except:
        raise FatalError("Неизвестное значение APP_ID - оно должно быть задано как число в vk.cfg файле")

    if WHAT not in ['','message','photo','mp3','wall','ask','video', 'delete']:
        say( "\nERROR: Неизвестное действие - %s\n\n", WHAT )
        ARGV=[]

    if not ARGV:
        help = """
Как использовать:
  vk_downloader_all.py ДЕЙСТВИЕ ЛОГИН СПИСОК_ЦЕЛЕЙ ФЛАГИ

ДЕЙСТВИЕ     = одно из ask, message, photo, mp3, wall, restore, delete
СПИСОК_ЦЕЛЕЙ = через запятую имена, ники, URL, конкретные id или '*'(скачать всё)
      например: "chat=100,user=6879766" или "https://vk.com/mariposa_en_el_viento, Хижняк"
      для 'video' - пустое(скачать все отложенные), URL или путь к файлу со списком URL
ФЛАГИ = опциональные настройки чтобы изменить значения по умолчанию из vk.cfg

Итого примеры:
 * скачать две стенки без комментариев но с лайками: группы и человека
    vk_downloader_all.py wall smth@mail.com "https://vk.com/club86104428,Каневский" --LOAD_COMMENTS=False --LOAD_LIKES=False
 * сохранить сообщения общения с человеком
    vk_downloader_all.py message smth@mail.com "Каневский"
 * скачать альбом фоток у другого человека
    vk_downloader_all.py photo smth@mail.com "https://vk.com/album8296250_211849784"
 * скачать все свои MP3
    vk_downloader_all.py mp3 smth@mail.com "*"
     """
        raise FatalError(help)
    return WHAT, RESTORE_FLAG, MAIN_PROFILE




def VKEnterLogin( fldName = 'USER_LOGIN' ):
    USER_LOGIN = CONFIG[fldName]
    while len(USER_LOGIN.strip())==0:
        USER_LOGIN = util.getinput("Введите логин VK: ").strip()
        if len(USER_LOGIN) and util.confirm( "Запомнить логин[y/n]?" ):
            with open(config.CFGFILE, "at") as cfgfile:
                cfgfile.write('%s="%s"\n' % (fldName, USER_LOGIN ) )
        say()
    CONFIG[fldName] = USER_LOGIN
    return USER_LOGIN


"""
#########################################
#   INITIALIZE DIRNAMES AND FILENAMES   #
#########################################
"""

def InitializeDir( USER_LOGIN, WHAT ):
    DIR_PREFIX = config.CONFIG.get('DIR_PREFIX','').strip()
    if DIR_PREFIX:
        pass
    elif WHAT in ['photo','mp3','video']:
        DIR_PREFIX = "DLOAD"
    elif WHAT in ['wall']:
        DIR_PREFIX = "WALL"
    else:
        DIR_PREFIX = "MSG"
    BASEDIR = "./%s-%s" % (DIR_PREFIX,USER_LOGIN)

    if not os.path.exists(BASEDIR):
        os.makedirs(BASEDIR)
    IMGDIRBASE = '%s/images' % BASEDIR
    MP3DIRBASE = '%s/media' % BASEDIR
    DOCDIR = None                           #if None - get from MP3DIR
    SCRIPT_DIR = ""

    FILE_STORED = "%s/__msg.stored" % BASEDIR
    FILE_BAKDEL = "%s/__msg.bakdel" % BASEDIR
    FILE_MAIN   = "%s/__msg_all.last" % BASEDIR

    FILE_MP3_SKIP = "./__vk.mp3list-%s" % USER_LOGIN
    FILE_VIDEO    = "./__vk.videolist"

    # Copy locals to this module globals (just do not declare them
    util.import_vars( globals(), locals(), '*', isOverwrite=True )
    globals()['USER_LOGIN'] = USER_LOGIN



"""
##########################################
#       MY VK UTILITY FUNCTIONS          #
##########################################
"""


repl_ar = {     "&#55357;&#56835;": ":-D ",
                "&#55357;&#56838;": ":-D ",
                "&#55357;&#56836;": ":-D ",
                "&#55357;&#56832;": ":-D ",
                "&#55357;&#56843;": ":-p ",
                "&#55357;&#56863;": ":( ",
                "&#55357;&#56904;": "*DON'T SEE* ",
                "&#55357;&#56850;": ":( ",
                "&#55357;&#56861;": "%-p ",
                "&#9889;": "*LIGHTING* ",
                "&#55357;&#56441;": "*DEVIL*",

                "&#55357;&#56880;": ":``( ",
                "&#55357;&#56881;": "*OH* ",
                "&#55356;&#57204;": "*FORK* ",
                "&#55357;&#56365;": "*MOUSE* ",
                "&#55357;&#56344;": "*ELEPHANT* ",
                "&#55357;&#56451;": "*DANCE* ",
                "&#55357;&#56873;": ":(( ",
                "&#55357;&#56840;": "*EVIL* ",
                "&#55357;&#56864;": "8-( ",
                "&#55357;&#56896;": ">8-O ",
                "&#55357;&#56847;": "*SHY* ",
                "&#9786;": "8) ",
                "&#55357;&#56488;": "*WIND* ",
                "&#10052;": "*ICE*",
                "&#55356;&#57226;": "*HOLIDAY*",
                "&#55357;&#56984;": "*BLUE CAR*",


                #	&#55357;&#56391;
                #	&#55357;&#56847;
                "&#55357;&#56885;": "X-O ",
                "&#55357;&#56484;": "*zzZZZ* ",
                "&#55357;&#56890;": "*CAT_SMILE* ",
                "&#55357;&#56844;": "*CLOSED_EYES* ",

                "&#9679;": '* ',
                '&#9829;': '@-}-- ',

                "&#9995;": "*PALM* ",
                "&#9996;": "*V* ",
                "&#55356;&#57118;": "*SUN* ",
                "&#55357;&#56876;": ":-E ",
                "&#55357;&#56865;": "*ANGRY* ",
                "&#55357;&#56869;": ":`( ",
                "&#55357;&#56850;": "*SAD* ",
                "&#55357;&#56862;": "*SAD* ",
                "&#55357;&#56878;": ":-O ",
                "&#55357;&#56399;": "*APPLAUSE* ",
                "&#55357;&#56834;": ":``)",
                "&#55357;&#56387;": "*NOSE* ",
                "&#55357;&#56833;": ":( ",
                "&#55356;&#57171;": "*STRAWBERRY* ",
                "&#55356;&#57170;": "*CHERRY* ",
                "&#55357;&#56853;": ":-( ",
                "&#55357;&#56619;": "*REVOLVER* ",
                "&#55357;&#56906;": "*SILENT MONKEY* ",

                "&#55357;&#56841;": ";) ",
                "&#55357;&#56397;": "*THUMB UP* ",
                "&#55357;&#56883;": "=8-O ",
                "&#55357;&#56879;": "=:-O ",
                "&#55357;&#56872;": "=8-[ ",
                "&#55357;&#56859;": ":-p ",
                "&#55357;&#56860;": ";-p ",
                "&#55357;&#56842;": ":-) ",
                "&#55357;&#56835;": ":-D ",
                "&#55357;&#56839;": "*HOLY* ",
                "&#55357;&#56852;": "3( ",
                "&#55357;&#56846;": "B-) ",
                "&#55357;&#56866;": ":`( ",

                "&#55357;&#56856;": "*KISS* ",
                "&#55357;&#56459;": "*KISS* " ,
                "&#9728;": "*SUN* ",
                "&#55357;&#56613;": "*FIRE* ",
                "&#55357;&#56485;": "*EXPLODE* ",
                "&#55357;&#56870;": ":( ",
                "&#55356;&#57218;": "*CAKE* ",
                "&#55356;&#57225;": "*HOLYDAY* ",
                "&#10084;": "*HEART* ",
                "&#55357;&#56845;": "*IN LOVE* ",
                "&#55357;&#56858;": "*KISS* ",
                "&#55357;&#56911;": "*PRAY* ",
                "&#55357;&#56877;": "*CRY* ",
                "&#55356;&#57119;": "*STAR* ",
                "&#55357;&#56384;": "*EYES* ",

                # smiles on linux
                "&#128522;": ":) ",
                "&#128523;": "%-p ",
                "&#128521;": ";-) ",
                "&#128539;": ":-p ",
                "&#128550;": ":( ",
                "&#128563;": "=8-O ",
                "&#128519;": "*HOLY* ",
                "&#128540;": ";-p ",
                "&#128516;": ":-D ",
                "&#128515;": ":-D ",
                "&#128512;": ":-D ",
                "&#128077;": "*THUMB UP* ",
                "&#128526;": "*GLASSES* ",
                "&#128536;": ":-* ",
                "&#127874;": "*CAKE* ",
                "&#9757;": "*ATTENTION* ",
                "&#128545;": ":-E ",
                "&#128293;": "*FIRE* ",
                "&#128513;": ":-[ ",
                "&#128543;": ":( ",
                "&#128545;": "*ANGRY* ",
                "&#11088;": "*STAR* ",
                "&#127929;": "*PIANO* ",
                "&#127931;": "*VIOLIN* ",
                "&#127881;": "*HOLIDAY* ",
                "&#128170;": "*BICEPS* ",
                "&#9992;": "*PLANE* ",
                "&#128557;": "*CRY* ",
                "&#128525;": "*LOVE_EYES* ",
                "&#128564;": "*SLEEP* ",
                "&#128527;": "*HMM* ",

                "&#128542;": ":-(( ",
                "&#128532;": "*SAD* ",
                "&#127831;": "*MEAT_LEG* ",
                "&#127858;": "*SOUP* ",
                "&#127837;": "*PASTA* ",
                "&#127828;": "*CHEESBURGER* ",
                "&#128524;": "*CLOSED_EYES* ",
                "&#128562;": "X-[ ] ",
                "&#128546;": ":`( ",
                "&#128549;": ":`( ",
                "&#128518;": "*LOL* ",
                "&#128547;": "%( ",
                "&#128299;": "*REVOLVER* ",
                "&#127827;": "*STRAWBERRY* ",
                "&#128165;": "*EXPLODE* ",
                "&#128584;": "*MONKEY_CLOSED_EYES* ",
                "&#128127;": "*PURPLE_SAD* ",
                "&#128517;": ":`-D ",
                "&#128556;": ":-E ",
                "&#128005;": "*TIGER* ",
                "&#128115;": "*ARAB_MAN* ",
                "&#127873;": "*GIFT* ",
                "&#127775;": "*STAR* ",
                "&#127774;": "*SUN* ",
                "&#128553;": ":`(( ",
                "&#128703;": "*SHOWER* ",
                "&#127876;": "*ELKA* ",
                "&#127755;": "*VOLCANO* ",
                #"&#128517;": "*CANNABIS* ",
                "&#128559;": "8-) ",
                "&#128552;": "8-<I ",
                "&#128544;": "*FROWN* ",
                "&#128060;": "*PANDA* ",
                "&#127818;": "*ORANGE* ",
                "&#127863;": "*WINE* ",
         }

stop_id = {}            # [profileid] = id of last saved message
lastdel_id = {}         # [profileid] = id of last deleted message (no need to go deeper)
last_times = {}		# [profileid] = timestamp of last saved message

re_xmlref = re.compile("&#[0-9]+;")

# return '>' for outgoing / '<' for incoming / '?' for error
def get_msgdirection( msg, me ):
    if not msg or len(msg)<2:
        return '?'
    return '>' if msg[1]==me else '<'

def get_duration( val ):
    val = int(val)
    m = int(val/60)
    s = val%60
    return  "%s:%02d"%( m, s )

def make_body( body, html ):
    body = str_encode(body)
    for [k,v] in repl_ar.iteritems():
        body = body.replace(k,v)
    if html:
        return makehtml(body,True)
    return body

def dload_attach( dirname, fname, url, mark = None, needPrefix = True, type = None, skipDownload = False ):

     if url=='' or url is None:
        return
     if not os.path.exists(dirname):
        os.makedirs(dirname)
     if not os.path.isdir(dirname):
        return

     if needPrefix:
        lt = time.localtime(CURMSG_TIME)
        fname = "%04d%02d%02d%s" % (lt.tm_year, lt.tm_mon, lt.tm_mday, fname )

     fname = fname_prepare(fname)
     fullfname = "%s/%s" % ( dirname, fname )
     ##print "%s\t%s" % (fname, url )

     if (type=='mp3'):
        s = str_decode(fname)
        if len(s)>5 and s[0]=='[' and s[5]==']':
            s = s[6:]
        DBGprint( 5, "CHECK SKIP %s" % str_cp866(s) )
        if s in SKIP_MP3_SET:
            return fullfname
        # check that not common 'unknown artist,...' - to not block
        s1 = s.lower().replace('unknown artist','').replace('unknown','').replace('untitled','').replace(u'без названия','').replace(u'неизвестен','').replace('-','').replace('.mp3','').strip()
        if len(s1):
            SKIP_MP3_LIST.append( util.str_decode_all( [ s, '', url.split('?')[0], fullfname ] ) )

     if CONFIG['SKIP_EXISTED_FILE'] and os.path.exists(fullfname) and os.path.isfile(fullfname):
        return fullfname
     if skipDownload:
        if CONFIG['SHOW_SKIPED_MEDIA']: say("%s", fname )
        return None
     if mark:
        util.print_mark(mark)
     DBGprint( 5, unicformat("DLOAD %s<-- %s", [fname, url] ) )
     response, content = vk_api.session_get( url )
     DBGprint( 5, "DLOAD finished" )
     if os.path.exists(fname) and os.path.isfile(fullfname) and os.path.getsize(fullfname)==len(content):
        # same sized filed exists - do not overwrite (keep last_modify_time)
        pass
     else:
        try:
          tmpfp = os.open( fullfname, os.O_RDWR|os.O_TRUNC|os.O_CREAT|O_BINARY, 0644 )
        except Exception as e:
          raise FatalError( unicformat( "Ошибка при записи файла %s\n%s", [fullfname,e] ) )
        os.write( tmpfp, content )
        os.close( tmpfp )
     return fullfname

# PARSE ATTACHMENT()
def parse_attachment( attach, pre, html = False, got_from = '' ):
    global kww,pww,CONFIG,IMGDIR,MP3DIR, DOCDIR, VIDEO_LIST, VIDEO_LIST_SET
    add_body = []
    preview = []

    def get_fname_url( fname ):
        tmp,fname=os.path.split(fname)
        tmp,dname=os.path.split(tmp)
        ##return "file://./%s/%s" % ( urllib.quote_plus(dname), urllib.quote_plus(fname) )
        return str_encode( "./%s/%s" % ( dname, fname ), util.fsencode )

    def make_attachbody( prefix, title, attach_item, url, dloaded_fname = None ):
        url = str_encode(url)
        text = prefix + ( ' "%s"' % title )
        duration = attach_item.get(u'duration',None)
        if duration is not None:
            text += " " + get_duration(duration)
        if not html:
            return text + ( " (%s)" % url )
        elif dloaded_fname is None:
            return '<A HREF="%s" class=b>%s</A>' % ( url, makehtml(text) )
        return '<A HREF="%s" class=b>%s</A> <font size=-1><i>(<A HREF="%s" class=b>%s</A>)</i></font>' % ( get_fname_url(dloaded_fname), makehtml(text), url, makehtml(url) )

    def make_attachimage( url, fname, w_h ):
        return ' <A HREF="%(fname)s" class=b><IMG src="%(fname)s" alt="%(url)s" %(wh)s></A>' % {
                         'url': makehtml(url),  #urllib.quote_plus
                         'fname': get_fname_url(fname),
                         'wh': w_h }

    num_of_this_foto = -1

    for a in attach:
        add_body.append( pre )
        ph = a.get(u'photo', None )
        ph = a.get(u'sticker', ph )

        if ph is not None:
            maxsize=-1
            url = ''
            for [k,v] in ph.iteritems():
                k.encode('ascii','xmlcharrefreplace')
                if k.startswith('photo_'):
                    size = int(k[len('photo_'):])
                    if maxsize < size:
                        maxsize = size
                        url = v.encode('ascii','xmlcharrefreplace')

            ph_path = url.split('/')
            if u'photo' in a:
               lt = time.localtime(CURMSG_TIME)
               n = "_%02d%02d-%s" % (lt.tm_hour, lt.tm_min, ph_path[-1] )
               ( w, h ) = ( a[u'photo'].get(u'width',-1), a[u'photo'].get(u'height', -1) )
            else:
               n = "-stickers-%s-%s" % (ph_path[-2], ph_path[-1] )
               ( w, h ) = ( a[u'sticker'].get(u'width',-2), a[u'sticker'].get(u'height', -2) )
            fname = dload_attach( IMGDIR, n, url )

            if not html:
                add_body[-1] += url
                continue

            # html processing of image
            preview.append( "IMG "+ os.path.basename(fname) )
            w_h = ""
            if w>0 and h>0:
                w_new = min(240,w)
                w_h = " width=%d height=%d " % ( w_new, int( w_new*float(h)/float(w) ) )
            num_of_this_foto += 1               # place three fotos in row
            if ( num_of_this_foto % 3 ) != 0:
                add_body.pop()
            add_body[-1] += make_attachimage( url, fname, w_h )
            if w<0 or h<0:
                add_body[-1] += "\n<BR>%d/%d="%(w,h) + makehtml(str(a))
            continue


        elif u'video' in a:
            a = a[u'video']
            title = str_encode( a.get(u'title','') )
            videoid = "%s_%s" % ( a.get(u'owner_id',0), a.get(u'id',0) )
            if u'access_key' in a:
                videoidfull = "%s%s|%s" % ( videoid, "?list="+a[u'access_key'], got_from )
            url = "http://vk.com/video" + videoidfull
            preview.append( 'video "%s"'%title )
            add_body[-1] += make_attachbody( "video", title, a, url, None )
            #tmp, dname = os.path.split(MP3DIR)
            dname = MP3DIR
            fname = "[%s]%s" % ( videoid, fname_prepare(title) )
            fname = "%s/%s"%(dname,fname)
            if CONFIG['DOWNLOAD_VIDEO'] and (str_decode(fname) not in VIDEO_LIST_SET):
                VIDEO_LIST.append( util.str_decode_all( ['',url, fname, title,get_duration(a.get(u'duration',0))] ) )

        elif u'audio' in a:
            a = a[u'audio']
            title = "%s - %s" % ( str_encode(a.get(u'artist','Unknown')),
                                  str_encode(a.get(u'title','')) )
            url = str_encode( a.get(u'url','') ).split('.mp3?')
            url = url[0]+'.mp3'
            url2download = a.get(u'url','').encode('ascii','xmlcharrefreplace')
            #@ADVANCED_MP3_PROCESSING@
            lt = time.localtime(CURMSG_TIME)
            n = "_%02d%02d-{%s}-%x.mp3" % ( lt.tm_hour, lt.tm_min, title[:70], a[u'id'] )
            fname = dload_attach( MP3DIR, n, url2download, '*', needPrefix=True, type='mp3', skipDownload = not CONFIG['DOWNLOAD_MP3'] )
            preview.append( 'audio "%s"'%title )
            add_body[-1] += make_attachbody( "audio", title, a, url, fname )

        elif u'doc' in a:
            a = a[u'doc']
            title = str_encode( a.get(u'title','') )
            url = str_encode( a.get(u'url','') )

            lt = time.localtime(CURMSG_TIME)
            name, ext = os.path.splitext(title)
            n = "_%02d%02d-%s" % (lt.tm_hour, lt.tm_min, "%s%s" % (name[:70], ext) )
            fname = dload_attach( DOCDIR if DOCDIR else MP3DIR, n, url )

            if not html:
                add_body[-1] += make_attachbody( "doc", title, a, url, fname )
                add_body[-1] += "|" + str_encode( str(a) )
            else:
                preview.append( 'doc "%s"'%title )
                if ext.lower() in ['.gif', '.jpg', '.png' ]:
                    add_body[-1] += make_attachimage( url, fname, "" )
                else:
                    add_body[-1] += make_attachbody( "doc", title, a, url, fname )
                add_body[-1] += '<BR>(<A href="%s" class=b>%s</A>)' % ( url, url )
                ##add_body[-1] += ( '| {%s} %s (<A href="%s" class=b>%s</A>)' % ( ext, makehtml(title), url, url ) )

        elif u'link' in a:
            a = a[u'link']
            title = str_encode( a.get(u'title','') )
            url = str_encode( a.get(u'url','') )
            desc = str_encode( a.get(u'description','') )
            img = a.get(u'img_src',None)

            preview.append( 'link "%s"'%title )
            if img is None or not html:
                add_body[-1] += make_attachbody( "link", title, a, url )
            else:

                add_body[-1] += ' <A HREF="%(url)s" class=b><IMG src="%(url)s" alt="%(title)"></A> (%(title)s)' % {
                         'url': url,
                         'title': makehtml(title) }
            if len(desc):
                desc = "\n" + desc
                add_body[-1] +=  makehtml(desc,True) if html else desc

        elif u'wall' in a:
            a = a[u'wall']
            hist = a.get( u'copy_history', [a] )[0]
            fromid = hist.get( u'from_id', 0 )
            postid = hist.get( u'id', 0 )
            text = hist.get( u'text', '' )
            url_repost = "http://vk.com/wall%s_%s" % ( fromid, postid )
            if fromid==0:
                text_who = '??'
            else:
                text_who = make_profiletext(int(fromid))

            if not html:
                add_body[-1] += "== REPOST WALL: %s (%s)\n" % ( url_repost, text_who )
                pre_new = pre + '> '
                if len(text)>0:
                    text = make_body( text, html )
                    add_body[-1] += pre_new + ('\n'+pre_new).join( text.split('\n') ) + "\n"
                postfix = "\n" + pre + "== END OF REPOST ==="

            else:
                preview.append( 'REPOST "%s"'%text_who )
                preview.append( make_body(text,False)[:100] )
                add_body[-1] += '<table border=0><tr><td colspan=2>== REPOST WALL: <A HREF="%s">%s</A></td>\n' % ( url_repost, text_who )
                add_body[-1] += '<tr><td bgcolor=#606060 style="color:#606060;" width=1%>&gt;&gt;<td>' + make_body(text,html)
                pre_new = ''
                postfix = "</td></table>\n"

            body_attach, preview_attach = parse_attachment( hist.get(u'attachments', []), pre_new, html, got_from )
            if len(text)>0 and len(body_attach)>0:
                add_body[-1] += '<BR>' if html else '\n'
            preview += preview_attach
            add_body[-1] += body_attach + postfix

        else:
            if not html:
                add_body[-1] += str_encode(str(a))
            else:
                add_body[-1] += makehtml( str_encode(str(a)) )

        # reset photo sequence counter
        num_of_this_foto = -1

    body = ('<BR>\n' if html else '\n').join( map(str_encode,add_body) )
    if not html:
        preview = []
    return body, preview

#  GET MESSAGES
def get_msg( lst, key_body = u'body', reinitHandler = None, html = False, cacheHandler = None, textHandler = None, got_from = '' ):
    global CURMSG_TIME

    # set defaults
    stop_id[MAIN_PROFILE] = stop_id.get(MAIN_PROFILE,0)
    lastdel_id[MAIN_PROFILE] = lastdel_id.get(MAIN_PROFILE,0)
    last_times[MAIN_PROFILE] = last_times.get(MAIN_PROFILE,0)
    stoptime = time.time() - 24*3600*CONFIG['DAYSBEFORE'];

    min_id = -1
    util.print_mark('.')

    batcher = vk_utils.BatchExecutor( vk_api )

    # do preload all possible related users and groups
    batch = []
    for m in lst[u'items']:
        batch.append( util.make_int(m.get(u'from_id',1)) )
        fwd = m.get(u'fwd_messages',[])
        attachments = list( m.get(u'attachments',[]) )
        for f in fwd:
            if u'user_id' in f:
                batch.append( util.make_int(f[u'user_id']) )
            attachments += f.get( u'attachments', [] )
        for a in attachments:
            if u'wall' in a:
                a = a[u'wall']
                hist = a.get( u'copy_history', [a] )[0]
                fromid = hist.get( u'from_id', 0 )
                batch.append( util.make_int(fromid) )
    vk_utils.lazy_profile_batch += batch

    # main cycle
    #print lst
    for m in lst[u'items']:
        id = int(m.get(u'id',0))
        DBGprint( 4, id )
        if ( id in messages ): continue
        t = int(m.get(u'date'))
        CURMSG_TIME = t
        ##print "id%s, t%s, stopt%s, lastdel%s, stopid%s" % (id,t,stoptime,lastdel_id[MAIN_PROFILE],stop_id[MAIN_PROFILE])
        if ( stoptime > t ): continue
        if IF_DELETE>0:
            stop = ( lastdel_id[MAIN_PROFILE] >= id )
        else:
            stop = ( stop_id[MAIN_PROFILE] >= id )
        if ( not stop and ( id < min_id or min_id == -1 ) ): min_id = id
        ##print "stop%s, min_id%s; read_state%s"% (stop,min_id,m.get(u'read_state',0))

        who = get_profile( m.get(u'from_id',1) )
        if reinitHandler is not None:
            reinitHandler( id, t, who )

        attach = m.get(u'attachments',[])
        fwd = m.get(u'fwd_messages',[])
        count_likes = m.get(u'likes',{}).get(u'count',0)
        if not CONFIG['LOAD_LIKES']: count_likes = 0
        count_comments = m.get(u'comments',{}).get(u'count',0)
        if not CONFIG['LOAD_COMMENTS']: count_comments = 0

        if cacheHandler:
            # [ 0owner, 1id, 2time, 3who, 4remark, 5likes, 6preview_text, 7is_only_img_attach, -1body ]
            ##print [ textHandler, id, t, who, ';', count_comments, count_likes ]
            msg_cached = cacheHandler( textHandler, id, t, who )
            ##print msg_cached
            if msg_cached is not None:
                ##print int(msg_cached[4]), count_comments, int(msg_cached[5]), count_likes
                if CONFIG.get('WALL_BACKUP',False) and (int(msg_cached[4])>count_comments or int(msg_cached[5])>count_likes):
                    globals()["MSG2BACKUP"].append(id)
                elif int(msg_cached[4])>=count_comments and int(msg_cached[5])>=count_likes:
                    ##print "!RESTORED!"
                    # NO NEED FOR UPDATE - comments and likes are same
                    ##messages[id] = [ t, who ]
                    continue
            #print "!FAIL!"

        body = make_body( m.get(key_body,''), html=False )
        preview = [ body[:200] ]
        if html:
             body = makehtml(body, True)

        if u'copy_history' in m:
            rec = dict(m)
            #rec['from_id'] = m[u'copy_history'][0]['from_id']
            attach.append({u'wall':rec})

        # do not delete unreaded, important, attached, empty messages and unknown smiles
        if (( CONFIG['DEL_ENFORCED'] or                 # delete if enforced flag or NOT:
             ( m.get(u'read_state',0)!=0 )                # ...unreaded
               and m.get(u'important',0)==0               # ...important
               and len(attach)==0 and len(fwd)==0         # ...specific(attachments or forward)
               and len(body.strip())!=0  )                # ...empty body - probably something goes wrong
           and not re_xmlref.search(body) ):           # ...+always keep if unknown smile
            if ( lastdel_id[MAIN_PROFILE] < id ):
                list_to_del.append(id)

        ##if ( stop_id[MAIN_PROFILE] >= id ): continue
        def _addAttach( mbody, preview, mpreview ):
            if len(body_attach)>0 and len(mbody)>0:
                mbody += "<BR>\n" if html else '\n'
            preview += mpreview
            return mbody + str_encode(body_attach)


        for f in fwd:
            if u'user_id' in f:
                suffix = "FROM %s" % make_profiletext(f[u'user_id'])
                cbody = f.get(u'body','')
            else:
                suffix = ''
                cbody =  str(f)

            body += "*** FWD %s ***\n" % suffix
            body += make_body( cbody, html )
            preview += [ "** FWD %s" % suffix ]
            body_attach, preview_attach = parse_attachment( f.get( u'attachments', [] ),'> ', html=html, got_from = "%s_%s"%(got_from,id) )
            body = _addAttach( body, preview, preview_attach )
            body += "\n*************\n"

        body_attach, preview_attach = parse_attachment( attach, '', html=html, got_from = "%s_%s"%(got_from,id) )
        body = _addAttach( body, preview, preview_attach )

        ##print "------------"
        ##print m

        likes = []
        if count_likes>0:
            batcher.likes.getList( _ID_CMD='likes:%s'%id, type='post', owner_id=m.get(u'owner_id',0), item_id=m.get(u'id',0), filter='likes', count=100)

        comments = {}
        if count_comments>0:
            batcher.wall.getComments( _ID_CMD='comments:%s'%id, owner_id=m.get(u'owner_id',0), post_id=m.get(u'id',0), need_likes=0, count=100, preview_length=0, extended=0)

        ##print "process %s" %id
        if html:
            preview = ('\n'.join(map(str_encode,preview))).strip().replace('\n\n','\n')
            preview = makehtml( preview[:150], False ).replace('\n','<BR>').replace('\t',' ')

        is_only_img_attach = not( len(attach) - len( filter(lambda a: (u'photo' not in a) ,attach) ) )
        #               0time, 1who, 2body, 3comments, 4likes, 5preview, 6 is_only_img_attach
        messages[id] = [ t, who,      body, comments, likes, preview,    is_only_img_attach ]

    # postprocess batch executor (quickly load comments and likes)
    _, resMap = batcher.execute()

    for key, val in resMap.iteritems():
        t, id = key.split(':')
        res = val[0]
        if t=='comments' and val[1] is None:
            for c in res[u'items']:
                if u'from_id' in c:
                    vk_utils.lazy_profile_batch.append( c[u'from_id'] )

    for key, val in resMap.iteritems():
        t, id = key.split(':')
        res = val[0]

        if val[1] is not None:
            DBG.say( DBG.ERROR, "ERROR: error during execution %s - %s", [key,val[1]] )

        elif t=='likes':
            likes = res[u'items']
            vk_utils.lazy_profile_batch += list( likes )
            messages[int(id)][4] = likes
            ##print "LIKES"
            ##print res

        elif t=='comments':
            ##print "COMMENTS"
            comments = {}
            preview = [ ]
            for c in res[u'items']:
                ##print c
                cbody = make_body( c.get(u'text',''), html )
                body_attach, preview_attach = parse_attachment( c.get(u'attachments',[]), '', html=html, got_from = "%s_%s"%(got_from,id) )
                cbody = _addAttach( cbody, preview, [] )
                ct = int(m.get(u'date'))
                cwho = get_profile( c.get(u'from_id',1) )
                comments[ c[u'id'] ] = [ ct, cwho, cbody, c.get(u'reply_to_user',None)]
            ##print comments
            messages[int(id)][3] = comments
            if preview and html:
                base_preview = messages[int(id)][5]
                if len(base_preview)<150:
                    preview = makehtml( '\n'.join(map(str_encode,preview)).strip()[:150-len(base_preview)], False ).replace('\n','<BR>').replace('\t',' ')
                    messages[int(id)][5] = '%s<BR>%s' % ( base_preview,preview)
        else:
            DBG.say( DBG.ERROR, "ERROR: unknown key %s", [key] )

    ##print "result %s"%min_id
    return min_id

# MAKE DICT FOR vk_api.*.GET()
def get_album_kw( uid, albumid=None ):
        if uid<0:
                kw = { 'gid': -uid }
        else:
                kw = { 'uid': uid }
        if albumid is not None:
                kw['album_id']=albumid
        return kw

# GET PHOTO ALBUM LIST FOR USER/GROUP AND CACHE IT
albumsCache = {}
def get_cached_albums_list( user_id ):
    if user_id not in albumsCache:
          albumsCache[user_id] = vk_api.photos.getAlbums( **get_album_kw(user_id) )
    return albumsCache[user_id]

def init_dirs( objtype, objid, objname ):
    global MAIN_PROFILE, IMGDIR, IMGDIRBASE, MP3DIR, MP3DIRBASE, DOCDIR

    MAIN_PROFILE = str_encode( '%s_%s' % ( objtype, objid ), util.fsencode )
    IMGDIR = unicformat(u"%s-%s-%s", ( IMGDIRBASE, MAIN_PROFILE, fname_prepare(objname) ) )
    MP3DIR = unicformat(u"%s-%s-%s", ( MP3DIRBASE, MAIN_PROFILE, fname_prepare(objname) ) )
    DOCDIR = None


"""
##########################################
#               MAIN FUNCTION            #
##########################################
"""

DAYS = ( u"ПН", u"ВТ", u"СР", u"ЧТ", u"ПТ", u"СБ", u"ВС")
#@MORE_INIT@


load_queue = []				# load_queue[idx] = [0type, 1id, 2title, 3album]

""" Do 'ASK' """
def executeAsk():
   menu = [ 'Скачать сообщения',
            'Скачать фото',
            'Скачать MP3',
            'Скачать стену',
            'Удалить сообщения',
            'Восстановить сообщения'
          ]

   say( "МЕНЮ")
   for k in xrange(0, len(menu)):
        say( u" %d - %s" % (k+1, unicformat(menu[k])) )
   menu_keys = map(lambda v: str(v), range(1, len(menu)+1) )
   RESTORE_FLAG = 0
   while True:
       answ = util.confirm( "Выберите действие:", menu_keys )
       action_ar = ['message','photo','mp3', 'wall','delete','restore:message']
       WHAT = action_ar[answ]
       if WHAT.startswith('restore:'):
            RESTORE_FLAG = -1
            WHAT=WHAT.split(':')[1]
       say ("Выбрано: "+ menu[answ] )
       if util.confirm("Верно[y/n]?"):
           say()
           break
       say()

   if WHAT=='wall':
        CONFIG['LOAD_COMMENTS'] = not not util.confirm('Сохранять комментарии[y/n]?')
        CONFIG['LOAD_LIKES']    = not not util.confirm('Сохранять лайки[y/n]?')
        say()

   url = 'smt'
   if RESTORE_FLAG:
        RESTORE_FLAG = util.make_int( util.getinput("За сколько последних минут скачивать?").strip() )
        if RESTORE_FLAG<=0:
            RESTORE_FLAG = 25*60
        #if not util.confirm('Восстановить всё за последние несколько часов[y/n]?'):
        #    raise OkExit('Отмена действия')
        url = ''
        MAIN_PROFILE=''

   MAIN_PROFILE = '*'
   while url!='':
       say('Для того чтобы закончить ввод - на очередном вопросе просто нажмите ENTER ничего не вводя\n')
       while (url!=''):
            url = util.getinput("Введите что скачивать(фамилию, URL):" ).strip().decode(inputencoding)
            if url:
                 load_queue.append( [ 'value' if RESTORE_FLAG else 'user', url, None ] )
                 MAIN_PROFILE = '~'
       say
       if len(load_queue):
            break
       if util.confirm(menu[answ]+' - все [y/n]?'):
            break
   return WHAT, RESTORE_FLAG, MAIN_PROFILE

"""  PARSE MAIN_PROFILE -> load_queue"""

def PrepareLoadQueue( WHAT, RESTORE_FLAG, MAIN_PROFILE ):
    global load_queue

    MAIN_PROFILE = MAIN_PROFILE.strip()

    # 1) Video - have specific processing (could give URL, filelist, non-VK URLs)
    if WHAT in ['video']:
        match = re.search( "(video(-?[0-9]+)(_([0-9]+)))([%2Flist\?=]+[0-9Fa-f]+)", MAIN_PROFILE )
        if MAIN_PROFILE.find('vk.com/')>0 and match:
            accesskey=''
            if match.group(5).startswith('%2F'):
                accesskey=match.group(5)[3:]
            elif match.group(5).startswith('?list='):
                accesskey=match.group(5)[6:]

            got_from =''
            if accesskey:
                if MAIN_PROFILE.find('im?')>=0 and MAIN_PROFILE.find('sel=')>0:
                    match1 = re.search("sel=([0-9]+)",MAIN_PROFILE)
                    if match1:
                        got_from = "|user=%s_0"%match1.group(1)   #chat=
                else:
                    match1 = re.search("(-?[0-9]+)\?",MAIN_PROFILE)
                    if match1:
                        if MAIN_PROFILE.find("/wall")>=0 or MAIN_PROFILE.find("/id")>=0 or match1.group(1).startswith('-'):
                            got_from = "|wall%s" % match1.group(1)
                        else:
                            #wall, club, event, public
                            got_from = "|wall-%s" % match1.group(1)

            MAIN_PROFILE = "https://vk.com/%s%s%s" % ( match.group(1), '?list=%s'%accesskey if accesskey else '', got_from )
            owner  = int(match.group(2))    #, int(match.group(4))
            videoid = "%s%s%s" % (match.group(2), match.group(3), '_%s'%accesskey if accesskey else '' )
            res = vk_api.video.get(owner_id=owner, videos=videoid)[u'items']

            if len(res):
                title = str_encode( res[0][u'title'] )
                t = time.strftime("%d.%m.%y %H:%M", time.localtime(res[0][u'date']))
                duration = res[0].get(u'duration',0)
                fname = "%s/%s-%s" % ( BASEDIR, t, fname_prepare(title) )
            else:
                title = ''
                fname = ''  ##"%s/%s" % ( BASEDIR, fname_prepare(match.group(0)) )
                duration=0

            load_queue.append( [ 'value', MAIN_PROFILE, MAIN_PROFILE,
                                    #item3 = [ 0size(if dloaded), 1url, 2fname, 3title, 4duration, 5urltodownload ]
                                    [ '', MAIN_PROFILE, fname, title, get_duration(duration) ] ] )

            MAIN_PROFILE = "~"
        elif MAIN_PROFILE in ['','*']:
            say( 'Загружаем все отложенные ранее видео' )
            load_queue.append( [ 'value', '','' ] )
            MAIN_PROFILE = '~'
        elif util.is_any_find( MAIN_PROFILE, ['youtube.com/','youtu.be/','vimeo.com/','vk.com/'] ):
            load_queue.append( [ 'value', MAIN_PROFILE, MAIN_PROFILE,
                                    #item3 = [ 0size(if dloaded), 1url, 2fname, 3title, 4duration, 5urltodownload ]
                                    [ '', MAIN_PROFILE, '', '' ] ] )
            MAIN_PROFILE = "~"
        elif  os.path.isfile(MAIN_PROFILE):
            print"FILE"
            # load in below file
            pass
        else:
            raise FatalError( unicformat( "Не могу расшифровать URL - %s", MAIN_PROFILE ) )


    if os.path.isfile(MAIN_PROFILE):
        say( "Загружаем файл %s", MAIN_PROFILE )
        with open(MAIN_PROFILE,'r') as f:
            lines = f.read().splitlines()
            # filter empty and commented lines
            lines = filter(lambda s: len(s) and not s.strip().startswith('#'), lines)
        load_queue.append( [ 'file', MAIN_PROFILE, MAIN_PROFILE, '\n'.join(lines) ] )

    elif MAIN_PROFILE=='~':
        # a) load_queue is already filled
        pass

    elif RESTORE_FLAG:
        load_queue.append( [ 'value', MAIN_PROFILE, 'value', MAIN_PROFILE ] )

    elif MAIN_PROFILE in ['', '*']:
        # b) '*' - means load all

        say( "Режим 'Скачать всё'" )
        if WHAT=='delete':
            if not util.confirm("Вы действительно хотите удалять все диалоги[y/n]?"):
                raise OkExit()

        if WHAT not in ['message', 'delete']:
            ##print "ERROR: For '%s' action -- source have to be defined" % WHAT
            load_queue.append( ['user', me, None ] )
        else:
            vv = vk_api.messages.getDialogs( count = 100, preview_length = 50 )
            for k in vv[u'items']:
                if u'chat_id' in k[u'message']:
                    load_queue.append( ['chat', k[u'message'][u'chat_id'], k[u'message'][u'title'] ] )
                else:
                    uid = k[u'message'][u'user_id']
                    load_queue.append( ['user', k[u'message'][u'user_id'], None ] )

    else:
        if not CONFIG.get('MACHINE',False):
            say( "Скачать: %s", MAIN_PROFILE )
            try:
                 say( "%s", util.str_cp866(MAIN_PROFILE) )      # different encoding
            except:
                pass

        # c) load given sequence (  [type1=]value1,[type2=]value2,.. )
        MAIN_PROFILE = map( lambda a: a.split('=',1), MAIN_PROFILE.split(',') )
        for p in MAIN_PROFILE:
            if len(p) < 2:
                p = ['user', p[0] ]
            elif p[0].find('vk.com/')>=0:
                p = ['user', '='.join(p) ]
            ##print "SPLIT: %s" % str(p)
            load_queue.append( [p[0].lower(), p[1], '%s_%s'%(p[0].lower(),p[1]) ] )


"""  PROCESS load_queue """
def PreprocessLoadQueue():
    global load_queue

    # PARSE FRIENDS AND TRY TO FIND GIVEN NAMES IN IT
    friends = None  # cache of all friends

    for idx in range(0,len(load_queue)):
       # 0. Add extra entry (potential 'album')
       load_queue[idx] += [ None ]

       # no need to parse specific cases
       if load_queue[idx][0] in [ 'file','value' ]:
            continue

       # check id
       try:
            v = int(load_queue[idx][1])
            load_queue[idx][1] = v
            #say( "DETECTED ID: %s", load_queue[idx][1] )
       except:
            #https://vk.com/id101866147
            name = load_queue[idx][1].strip()

            found = None

            # 1A. parse http address with id
            match = re.search( "vk\.com/id([0-9]+)$", name )
            if match:
                load_queue[idx][1] = int( match.group(1) )
                #say( "DETECTED vk.com/id: %s", load_queue[idx][1] )
                continue
            match = re.search( "vk\.com/((event)|(club))([0-9]+)$", name )
            if match:
                load_queue[idx][1] = -int( match.group(4) )
                #say( "DETECTED vk.com/event: %s", load_queue[idx][1] )
                continue

            # 1B. parse http address for message page
            match = re.search( "vk\.com/im\?(.+)$", name )
            if match:
               id_lst = match.group(1).replace('peers=','').replace('sel=','').replace('&','_').split('_')
               for idx1 in range(0,len(id_lst)):
                  if (id_lst[idx1][0]=='c'):
                      cur = ['chat', int(id_lst[idx1][1:]), None, None ]
                  else:
                      cur = ['user', int(id_lst[idx1]), None, None ]

                  #say( "DETECTED vk.com/im: %s|%s", [ load_queue[idx][0], load_queue[idx][1] ] )
                  if (idx1!=0):
                      load_queue.append( cur )
                  else:
                      load_queue[idx][0] = cur[0]
                      load_queue[idx][1] = cur[1]
               continue


            # 1C. parse http address for audio page
            match = re.search( "vk\.com/audios(-?[0-9]+)(\?album_id=([0-9]+))?$", name )
            if match:
                load_queue[idx][1] = int( match.group(1) )
                if match.group(2) is not None:
                    load_queue[idx][3] = int( match.group(3) )
                #say( "DETECTED vk.com/audio: %s|%s", [ load_queue[idx][1],load_queue[idx][3] ] )
                continue

            # 1D. parse http address for photo page
            match = re.search( "vk\.com/albums?(-?[0-9]+)(_([0-9]+))?$", name )
            if match:
                load_queue[idx][1] = int( match.group(1) )
                if match.group(2)!='':
                    load_queue[idx][3] = int( match.group(3) )
                #say( "DETECTED vk.com/albums: %s|%s", [ load_queue[idx][1],load_queue[idx][3] ] )
                continue

            if friends is None:
               ##say( "Parse friends" )
               friends = vk_api.friends.get( fields="uid,first_name,last_name,domain" )[u'items']
               for f in friends:
                    vk_utils._add_profile( f[u'id'], f )
               get_profile( me )
               friends = friends + [ { u'id':me, u'first_name': str_decode(profiles[me][0]), u'last_name': str_decode(profiles[me][1]) } ]

            # 2. parse http address with nickname
            match = re.search( "vk\.com/(.+)$", name )
            if match:
               name1 = match.group(1)
               for i in friends:
                    if ( name1 in i.get(u'domain','') ):
                        found = int(i[u'id'])
                        break
               if found is None:
                    raise FatalError( unicformat("ОШИБКА: не могу разобрать URL - %s", name ) )
            if found is not None:
                load_queue[idx][1] = found
                #say( "DETECTED BY NICKNAME: %s -> %s", [ name, load_queue[idx][1] ] )
                continue

            # 3. parse as first/full name

            # make transcoding (to ensure that we are able to process name in any encoding)
            try:
               name866 =  str_encode(name,'cp866').decode('cp1251','xmlcharrefreplace').lower()
            except:
               name866 =''
            try:
               nameutf8 =  name.decode('utf-8').lower()
            except:
               nameutf8 =''
            foundname = None
            for i in friends:
               to_find = [ i[u'last_name'].lower(), ("%s %s" %(i[u'first_name'],i[u'last_name'])).lower() ]
               if ( name866 in to_find ) or ( name.lower() in to_find ) or (nameutf8 in to_find):
                    if found is None:
                        found=int(i[u'id'])
                        foundname = name866 if ( name866 in to_find ) else str_cp866( name )
                    else:
                        say( "Обнаружена неоднозначность: id1=%d, id2=%s\n Укажите id или полное имя для разрешения" , (found, i[u'id']) )
                        say( "%d=%s", (found, make_profiletext(found) ) )
                        say( "%d=%s", ( int(i[u'id']), make_profiletext(i[u'id']) ) )
                        raise FatalError()
            else:
               # post processing
               if found is None:
                    try:
                       say( "НЕ ОБНАРУЖЕНО: %s (%s) - ПРОПУСКАЕМ ЭТО", ( name, name866 if os.name=='nt' else nameutf8) )  # @tsv -- transcode??
                    except:
                       say( "НЕ ОБНАРУЖЕНО: ... - ПРОПУСКАЕМ ЭТО" )
                    load_queue[idx][0] = 'skip'
               else:
                    load_queue[idx][1] = found
                    #say( "DETECTED BY NAME: %s -> %s", (foundname, load_queue[idx][1]) )


    # BATCH PRELOAD
    preload=[]
    for load in load_queue:
       if load[0]=='group' or load[1]<0: preload.append(-abs(load[1]))
       elif load[0]=='user':  preload.append(load[1])
    vk_utils.lazy_profile_batch += preload

    # FINALIZE PREPROCESSING
    for idx in range(0,len(load_queue)):

       # no need to parse specific cases
       if load_queue[idx][0] in[ 'file','value']:
            continue

       # 1. negative id means 'group'
       if load_queue[idx][1]<0:
            load_queue[idx][0] = 'group'
       if load_queue[idx][0]=='group' and load_queue[idx][1]>0:
            load_queue[idx][1] = -load_queue[idx][1]

       # 2. fill name
       if load_queue[idx][0]=='user':
            load_queue[idx][2]= make_profiletext(load_queue[idx][1])
       elif load_queue[idx][0]=='group':
            p = profiles[ get_profile(load_queue[idx][1]) ]
            load_queue[idx][2]=p[0]
       elif load_queue[idx][2] is None:
            load_queue[idx][2] = "%s_%s" % ( load_queue[idx][0], load_queue[idx][1] )
       #print str(load_queue[idx]).encode('cp866')


"""
#############################################
#     ACTION 'restore'                      #
#############################################
"""

# PURPOSE: GENTLY DETECT OF LAST MESSAGE(scan up from last)
#       Long time deleted messages could have date=0, so we have no stop-signal and need to scan up everything
# RETURN VALUE: ( last_non_deleted_msg_id, last_real_msg_id, loaded messages)
def FindRealLast():
    # Get last active message
    last_msg = vk_api.messages.get(count=1)[u'items']
    if not len(last_msg):
        last_msg= [ {u'id':0}]
    last_active = last = last_msg[0][u'id']

    # Check stored ids (could contain deleted message id which is bigger than last active)
    if 'msg_util_val' in globals():
        global msg_util_val
        for id, values in msg_util_val.iteritems():
            try: last = max([last, int(values[0]), int(values[1])])   # + stop_id, lastdel_id
            except: pass

    msgs = LoadBlock( range(last+1, last+1001) )
    msgs1 = filter(lambda v: v.get(u'date')>0, msgs)
    DBG.trace("FindRealLast(): last_active=%s, last_from_cfg=%s, loaded_non_empty=%s/%s",[last_active,last,len(msgs1), len(msgs)])
    if not msgs1:
        last = last_active
        msgs=[]
    else:
        last = max( map(lambda v: v[u'id'],msgs) )

    msgs = dict( map(lambda v: [v[u'id'],v],msgs) )
    return last_active, last, msgs


# Batch load messages by ids (if batch size <2500 then this is one request)
def LoadBlock( to_load ):
    to_load = filter( lambda i: i>0, to_load )
    if not to_load:
        return []

    batcher = vk_utils.BatchExecutor( vk_api )
    BLOCK_SIZE = 100        # MAX SIZE IN FOR getById is 100 ids
    while to_load:
        ids = ','.join( map(str, to_load[:BLOCK_SIZE] ) )
        to_load = to_load[BLOCK_SIZE:]
        batcher.messages.getById(message_ids=ids, preview_length=1)
    ##DBG.trace('execute %s-%s', [msg_id,msg_id1])
    _,res= batcher.execute()
    msgs1=[]
    for v in res.values():
        msgs1 += v[0].get(u'items',[])
    return msgs1

#TODO: userCond - lambda to check should this be restored(?) or maybe userId= None(everything except me)|id
def RestoreCycle( to_restore, finalize_callback, restoreDepthMinutes=-1, excludeMe=True, BLOCK_SIZE = 50, verbose = True):
        idx_block = 0
        now = time.time()
        queue = []          # queue to restore [ [idx_in_mark, item], [], [],...]
        mark = []           # list of marks ( .=ok, ?=fail, ^=yourself, -=skip)
        last_msg = None
        last_date = now
        if verbose:
            say( "\nВосстанавливаем сообщения (%d записей/msgid=%s/%s минут)", [len(to_restore),max(to_restore) if len(to_restore) else 'NO', restoreDepthMinutes] )
        for id in reversed(sorted(to_restore)):
            if idx_block%BLOCK_SIZE==0:
                finalize_callback( mark, queue, last_msg, last_date, False)
                last_msg = None
            idx_block+=1
            if id in msgs:
                last_msg = m = msgs[id]
                if m[u'date']:
                    last_date = m[u'date']
                # If message is out of requested period, break the cycle
                ##DBG.trace("%s/%s/%s>%s", [m[u'date'], restoreDepthMinutes,(now - m[u'date']),restoreDepthMinutes*60])
                if m[u'date'] and restoreDepthMinutes>0 and (now - m[u'date'])>restoreDepthMinutes*60:
                    finalize_callback( mark, queue, last_msg, last_date, False)
                    if verbose:
                        say( "Восстановление завершено - остаток записей имеет возраст больше %d минут" % restoreDepthMinutes )
                    break
                # ignore messages to yourself ( if excludeMe==True)
                #           or to other ( if excludeMe=False)
                if bool(m[u'user_id']==me) == bool(excludeMe):
                    mark.append('^')
                    continue
                # If date<=0 then message was removed too long time ago - ignore such
                if m[u'date']<=0 :
                    mark.append(' ')
                    continue
                # If not deleted then messages exists - ignore this
                if m[u'date']<=0 or not m.get(u'deleted',0):
                    mark.append('-')
                    continue

            # this message should be restored
            queue.append([len(mark),m])
            mark.append('?')
        finalize_callback( mark, queue, last_msg, last_date, True)



def executeRESTORE( WHAT, RESTORE_FLAG ):
    global me, load_queue
    global msgs

    if WHAT!='message':
        raise FatalError( "Only 'restore:message' is implemented" )

    for load in load_queue:
        if load[0] not in ['file','value']:
            continue

        load_objtype, load_objid, load_objname, load_value = load[:4]

        if load_value in ['', '*']:
            load_value = '-2000'

        to_restore = []
        for l in load_value.splitlines():
            to_restore += sorted( filter( len, l.split('|')[0].strip().split(',') ) )

        minutes = filter( lambda s: s.endswith('m'), to_restore )
        to_restore = filter( lambda s: not s.endswith('m'), to_restore )
        print minutes
        if len(minutes)>0:
                RESTORE_FLAG = util.make_int(minutes[0][:-1], RESTORE_FLAG)

        re_range = re.compile("^([0-9])-([0-9]+)$")
        def _convert_val( s ):
            m = re_range.match(s)
            if m:   return range( int(m.group(1)), int(m.group(2))+1 )
            try:    return int(s)
            except: return 0
        to_restore = map( _convert_val, to_restore )

        min_id = min(to_restore)
        # If negative value given (or *) - detect last message id and try to restore last N messages
        msgs = {}
        if min_id < 0:
            global msg_util_val
            msg_util_val = util.load_dict_file( FILE_MAIN, key_sep='=', val_sep=',' )
            ( last_active, last, msgs ) = FindRealLast()
            to_restore += range( last+min_id, last )        # restore down "min_id" messages (negative value) from last real message

        ##{k: v for k, v in points.iteritems() if v[0] < 5 and v[1] < 5}    # filter dict example
        to_restore = set( filter(lambda v: v>0, to_restore) )

        # Batch load of all absent messages
        to_load = sorted( to_restore - set(msgs.keys()) )
        msgs1 = LoadBlock( to_load )
        msgs1 = dict( map(lambda v: [v[u'id'],v],msgs1) )
        msgs.update(msgs1)

        def finalizeRestoreBlock( mark, queue, last_msg, last_date, isTail ):
            DBG.trace("finalizeRestoreBlock() queue:%s", [queue])
            if not mark:
                del queue[:]
                return
            if queue:
                r = {}
                for idx, item in queue:
                    batcher.messages.restore(message_id = item[u'id'],_ID_CMD=idx)
                    r[idx]=item
                _,resMap = batcher.execute()
                DBG.trace(resMap)
                for idx, res in resMap.iteritems():
                    idx = int(idx)
                    if res[1] is not None:
                        mark[idx] = '?'
                    else:
                        mark[idx] = '.'
                        restoredlst.append(int(r[idx][u'id']))
                        restoredusers.add( int(r[idx][u'user_id']) )
                    ##DBG.trace("DBG:%s/%s/%s", [idx, r[idx][u'id'], res[1]])
            sout = ''.join(mark)
            ##DBG.info( "%s",  [sout] )
            if last_msg is None:
                say( "%s", [sout])
            else:
                suff = "(msgid=%d) %s%s" % ( last_msg[u'id'],
                                           '' if last_msg[u'date']==last_date else 'before ',
                                           time.strftime("%d.%m.%y %H:%M", time.localtime(last_date)) )
                say( "%s%s", [sout,suff] )
                ##DBG.info(suff)
            del queue[:]
            del mark[:]


        #Scan of messages and try to restore
        restoredlst = []
        restoredusers = set()
        batcher = vk_utils.BatchExecutor( vk_api )
        RestoreCycle( to_restore, finalizeRestoreBlock, restoreDepthMinutes=RESTORE_FLAG, excludeMe=True, verbose = True)
        restoredusers = map( lambda v: make_profiletext(v), restoredusers )
        say( "Восстановлено %s сообщений", len(restoredlst) )
        say( "Восстановлены сообщения для: %s", ', '.join(restoredusers) )


"""
#################################################
#     ACTION 'video' (download video from files)#
#################################################
"""

firstTimeVideo = True
session = None
vkLoginDone = False

#VIDEO_LIST = [ 0status, 1url, 2fname, 3title, 4duration, 5to_download ]

def downloadVideo( file_videolist, start_idx ):
        global VIDEO_LIST, vkLoginOk, firstTimeVideo, changeFlag

        if start_idx>=len(VIDEO_LIST):
            return

        resolution = [1080, 720, 480, 360, 240, 144]

        VIDEO_LIST_DICT = {}        # url -> fname
        TO_LOAD_IDX = []

        import requests
        def getVKInstance():
            global session, vkLoginDone, USER_PASSWORD

            if vkLoginDone:
                return session

            """
            # this still reveal me to online
            if os.path.isfile(FILE_AUTH_SESSION):
                try:
                        with open(FILE_AUTH_SESSION, 'r') as f:
                            session = pickle.load(f)
                        say('..восстанавливаем из сессии')
                        vkLoginDone = True
                        return session
                except Exception as e:
                        print e
                        pass
            """

            if util.confirm( "Для скачивания видео необходимо полная авторизация. Выполнить полную авторизацию[y/n]?" ):
                #USER_LOGIN2 =  VKEnterLogin( fldName = 'SECONDARY_LOGIN' )
                USER_LOGIN2 = CONFIG.get('SECONDARY_LOGIN','').strip()
                if USER_LOGIN2=='':
                    # if no secondary login given, use main one (and get/ask for password)
                    if USER_PASSWORD=='':
                        _, _, USER_PASSWORD = vk_utils.VKLoginByPassword( USER_LOGIN, FileAuth = None )
                    USER_LOGIN2, USER_PASSWORD2 = USER_LOGIN, USER_PASSWORD
                else:
                    # if secondary login is given, get/ask its password
                    _, _, USER_PASSWORD2 = vk_utils.VKLoginByPassword( USER_LOGIN2, fldPwdEncoded='SECONDARY_PWD_ENC', FileAuth = None )
            else:
                raise OkExit("Скачивание видео отменено")

            vkLoginDone = True
            if USER_LOGIN2.strip()=='' or USER_PASSWORD2=='':
                return session
                #raise FatalError( unicform( "No login or pwd given:", (USER_LOGIN, USER_PASSWORD) ) )

            # INVISIBLE LOGING
            session = requests.Session()
            login_data = {
                        'act': 'login',
                        'expire': '',
                        '_origin': 'https://vk.com',

                        'email': USER_LOGIN2,
                        'pass': USER_PASSWORD2,
                    }
            response = session.post('https://login.vk.com', login_data, allow_redirects=False )
            if not 'location' in response.headers:
                say( "ОШИБКА ВХОДА В VK - удостоверьтесь что логин/пароль верны" )
                session = None
                return session
            response = session.get(response.headers['location'], allow_redirects=False )
            ## it still make ONLINE
            ##with open(FILE_AUTH_SESSION, 'w') as f:
            ##    pickle.dump(session,f)
            return session

        map_line_validx = { 'size':0, 'url':1, 'fname':2, 'title':3, 'duration':4, 'to_download':5 }
        def ChangeLine( t, value ):
            global changeFlag
            idx2 = map_line_validx[t]
            VIDEO_LIST[idx][idx2] = value
            changeFlag = True

        def GetLine( t, cutSuffix=False ):
            idx2 = map_line_validx.get(t,-1)
            if idx<0:
                DBG.TODO('Wrong key %s' % t)
                raise Exception()
            rv = VIDEO_LIST[idx][idx2]
            if cutSuffix:
                return rv.split('|')[0]
            return rv


        # 1. Find all downloaded video
        changeFlag = False
        for idx in xrange(start_idx,len(VIDEO_LIST)):
            #VIDEO_LIST[] = [ 0size(if dloaded), 1url, 2fname, 3title, 4duration, 5urltodownload ]
            line = VIDEO_LIST[idx]

            if len(line)<3:
                continue

            VIDEO_LIST[idx] = map(lambda s: s.strip(), line )
            line = VIDEO_LIST[idx]

            url, fname = line[1], line[2]
            if not( len(url) ):     ## and len(fname) ):
                continue

            if not util.is_any_find( url, ['youtube.com/','youtu.be/','vimeo.com/','vk.com/'] ) :
                say("Неизвестный видеохостинг: %s", url )
                ChangeLine( 'size', '##UNKNOWN HOSTING' )
                continue

            # check existance of loaded video
            fsize = 0
            for res in resolution:
                fname1 = "%s.%d.mp4" % (fname,res)
                fsize = os.path.getsize(fname1) if os.path.isfile(fname1) else 0
                if fsize>0:
                    say( "Видео уже загружено - %s", fname1 )
                    ChangeLine( 'size', "#LOADED=" + fname1 )
                    VIDEO_LIST_DICT.setdefault( url, fname1 )
                    if len(line)>5:
                        VIDEO_LIST_DICT.setdefault( line[5], fname1 )   # remember

            if line[0]=='':
                if fsize>0:
                    pass
                    #line[0]=str(fsize)
                    #changeFlag = True
                else:
                    TO_LOAD_IDX.append(idx)

        # 2. Download
        loadAllVideo = False
        for idx in TO_LOAD_IDX:
            line = VIDEO_LIST[idx]
            fname = VIDEO_LIST_DICT.get( GetLine('url',cutSuffix=True), None )

            if fname is not None:
                say( "\n%s\n  --> Существует как: %s", ( GetLine('fname'), fname ) )
                continue

            if firstTimeVideo:
                firstTimeVideo = False
                say( "\nОпции загрузки видео" )
                util.print_vars(["VIDEO_MAX_SIZE"], CONFIG)

            #if changeFlag:
            #    util.save_data_file( file_videolist,  VIDEO_LIST )
            #    changeFlag = False

            while len(line)<6:
                line.append('')
                changeFlag = True

            ##if line[5]!='':
            ##    continue

            fullfname = GetLine('fname')
            say( "\nСкачиваем: %s\t(%s)", ( GetLine('url'), GetLine('title')) )

            if GetLine('url').find('vk.com/')<0 and GetLine('to_download')=='':
                ChangeLine( 'to_download', GetLine('url') )

            # load url and parse to find content url
            to_download = None
            htmlline='???'
            if util.is_any_find( GetLine('to_dowload'), ['youtu.be/','youtube.com/','vimeo.com/'] ):
                # If we know that this comes from
                to_download = GetLine('to_dowload')
            elif util.is_any_find( GetLine('to_dowload'), ['rutube.ru/'] ):
                # If remember resource link to known restricted provider - no need to ask VK again
                htmlline = GetLine('to_dowload')
            else:
                session = getVKInstance()
                if session is None:
                    return

                response = session.get( GetLine('url', cutSuffix=True ) )
                ##DBG.trace("GOT VIDEO\n>>>\n%s\n<<<<\n", [response._content])
                idx_f = response._content.find("\najax.preload('al_video.php',")
                values=[]
                if idx_f>0:
                    htmlline = response._content[idx_f+1:].splitlines()[0].replace('\\\\','\\').replace('\\/','/')
                    values =  htmlline.split('"url')

                if len(values)<2:
                    htmlline, values = extendedVKVideoParse( GetLine('url') )
                if len(values)<2:
                    say( "Не могу загрузить видео %s - возможно уже удалено!! (или неверены hardcoded cookies)", GetLine('url') )
                    ChangeLine( 'size', '##' )
                    ChangeLine( 'to_download', str_decode("##"+htmlline) )
                    continue
                if not GetLine('title').strip():
                    match_title = re.search("<title>([^<]+)", response._content)
                    if match_title:
                        ChangeLine( 'title', str_decode(match_title.group(1)) )


            if to_download is None:
                # If parse VK - check maybe it is based on YOUTUBE
                find = htmlline.find('src=\\"https://www.youtube.com/')
                if find>=0:
                    to_download = htmlline[find+6:].split('\\"')[0]
                    ChangeLine( 'to_download', to_download )

                # .. or maybe based on VIMEO
                find = htmlline.find('.vimeo.com/video/')
                if find>0:
                    ##match = re.search('https?://[^\\/]+?vimeo.com/video/([0-9]+)',htmlline)
                    match = re.search('\.vimeo\.com/video/([0-9]+)',htmlline)
                    if match:
                        to_download = "https://vimeo.com/" + match.group(1)
                        ChangeLine( 'to_download', to_download )

            if to_download is None:
                # We still can't find provider - check restricted list
                if htmlline.find('rutube.ru/') > 0:
                    match = re.search('rutube\.ru/play/embed/([0-9]+)',htmlline)
                    if match:
                        url=match.group(0)
                        say( "Видео расположено на RUTUBE и поэтому не может быть скачано:\n%s", url )
                        ChangeLine( 'to_download', url )
                        ChangeLine( 'size', url )
                        continue

            if to_download is not None:
                # this is known side videohosting - process it

                # for embed youtube - reformat it
                if util.is_any_find(to_download,['youtu.be/','youtube.com/']):
                    find= to_download.find('/embed/')
                    if find>0:
                        to_download = "https://www.youtube.com/watch?v=" + (to_download[find+7:].split('?')[0])
                        ChangeLine( 'to_download', to_download )

                try:
                    yvideo = pytube.getVideo( to_download, CONFIG['VIDEO_MAX_SIZE'] )
                except pytube.utils.BaseYoutubeError as e:
                    say("%s: %s\nURL: %s", [type(e).__name__, str(e), to_download])
                    ChangeLine( 'size', '##%s: %s' %(type(e).__name__, str(e)) )
                    continue

                if yvideo is None:
                    say("Нет подходящих размеров видео: %s", to_download )
                    continue
                maxres = int(yvideo.resolution[:-1])
                vdict = { maxres: to_download }
            else:
                # finalize parse -- it is surely VK video, so try to find matches
                values = map(lambda s: s.replace('\\/','/').split('\"')[:3], values[1:] )
                vdict = dict( map(lambda v: [int(v[0].rstrip('\\')), v[2][:-1]], values[:-1]) )
                if len(vdict)==0:
                    say( "Не могу загрузить видео %s - возможно удалено {2}", GetLine('url') )
                    ChangeLine( 'size', '##' )
                    ChangeLine( 'to_download', str_decode("##"+htmlline) )
                    continue

                ar_r = filter(lambda v: v<=int(CONFIG['VIDEO_MAX_SIZE']), vdict.keys() )
                if len(ar_r)==0:
                    say("Нет подходящих размеров видео: %s", GetLine('url') )
                    continue
                maxres = max(ar_r)
                yvideo = pytube.models.VKVideo( vdict[maxres], fname_prepare(GetLine('title')), vk_api=vk_api, resolution=maxres, extension='mp4' )

            # prepare filename (if not given, use title):
            if not fullfname.strip():
                fullfname = "%s/%s" % (BASEDIR,yvideo.filename)
            fullfname = "%s.%d.mp4" % (fullfname,maxres)

            fsize = os.path.getsize(fullfname) if os.path.isfile(fullfname) else 0
            if fsize>0:
                say( "Видео уже загружено - %s", fullfname )
                VIDEO_LIST_DICT.setdefault( url, fullfname )
                if len(line)>5:
                    VIDEO_LIST_DICT.setdefault( GetLine('to_dowload'), fullfname )   # remember
                ChangeLine( 'size', '#LOADED=%s' % fullfname )
                continue

            say( "   --> %s", fullfname )

            if not loadAllVideo:
                answ = util.confirm("Вы хотите скачать это видео с разрешением %s (Y/N/Skipall/All)?"%maxres, ['n','y','s','a'])        #chr(13)
                if answ==0:
                    continue
                elif answ==2:
                    say("..скачивание всех видео отложено на потом")
                    break
                elif answ==3:
                    say("..подтверждено скачивание всех видео")
                    loadAllVideo = True

            # prepare directory (if no given - use BASEDIR)
            dname, tmp = os.path.split(fullfname)
            if dname=='':
                dname = BASEDIR
                fullfname = '%s/%s' % ( BASEDIR, tmp )
            try:     os.makedirs( dname )
            except:  pass

            try:
                yvideo.download( path=fullfname, on_progress=pytube.showProgress, silent=True, force_overwrite=True )
                print
            except IOError:
                say( "\nОшибка записи в файл '%s'", fullfname)
                raise

            VIDEO_LIST_DICT[ GetLine('url',cutSuffix=True) ] = GetLine('fname')             # map url->saved_file
            ChangeLine( 'size', "%.01fM" %float(os.path.getsize(fullfname)/(1024*1024)) )   # remember size (and mark that is downloaded)
            ChangeLine( 'to_download', vdict[maxres] )                                      # remember real resource url
            util.save_data_file( file_videolist,  VIDEO_LIST )
            changeFlag = False

        if changeFlag:
            util.save_data_file( file_videolist,  VIDEO_LIST )

def executeVIDEO():
    global VIDEO_LIST, VIDEO_LIST_SET, load_queue

    VIDEO_LIST, VIDEO_LIST_SET = util.load_data_file( FILE_VIDEO, main_col=2 )
    start_video_idx = None
    for load in load_queue:
        if load[0]=='value':
            if load[1] in ['','*']:
                # 'Download all postponed'
                start_video_idx = 0
            else:
                # 'Add a new URL'
                if start_video_idx is None:
                    start_video_idx = len(VIDEO_LIST)
                VIDEO_LIST.append( load[3] )
        elif load[0]=='file':
            lines = map( lambda s: (s.split('\t')+[''])[:2], filter(len, load[3].splitlines() ) )
            if start_video_idx is None:
                start_video_idx = len(VIDEO_LIST)
            for l in lines:
                if not util.is_any_find( l[0], ['youtube.com/','youtu.be/','vimeo.com/','vk.com/'] ):
                    say("Неизвестный видеохостинг: %s", l[0])
                else:
                    say("%s", l[0])
                    if len(l[1]) and l[1].find('/')<0:
                        l[1] = BASEDIR + "/" + l[1]
                    VIDEO_LIST.append( ['', l[0], l[1] ] )
        else:
            raise FatalError("Внутренняя ошибка - неизвестный тип объекта в очереди")
        util.save_data_file( FILE_VIDEO,  VIDEO_LIST )

        downloadVideo( FILE_VIDEO, start_video_idx )


# Парсинг стенки и диалогов через m.vk.com чтобы найти верный access token для текущей сессии
def  extendedVKVideoParse( url ):

    def findVKVideo( content ):
        ##DBG.trace( u'\n%s' % content )
        idx = content.find(url_to_find)
        if idx<0:
            return None
        DBG.trace( content[idx:].splitlines()[0])
        pattern = '(%s\?list=[0-9a-fA-F]+)'%url_to_find
        match = re.search(pattern, content)
        DBG.trace('something found. pattern=%s, match=%s', [pattern,match])
        if not match:
            DBG.TODO('failed to get listid for %s'%url_to_find)
            return None

        DBG.trace('load %s' % match.group(0) )
        url = 'https://vk.com'+match.group(0)
        response = session.get( url  )
        DBG.trace( u'\n%s', str_decode( response._content ) )
        idx_f = response._content.find("\najax.preload('al_video.php',")
        values=[]
        if idx_f>0:
            htmlline = response._content[idx_f+1:].splitlines()[0].replace('\\\\','\\').replace('\\/','/')
            values =  htmlline.split('"url')
            return htmlline, values
        return None

    url, got_from = url.split('|')
    url_to_find = ('/video'+url.split('/video')[1]).split('?list=')[0]
    DBG.trace( "extendedVKVideoParse: %s", [[url_to_find,got_from]] )

    if got_from.startswith('wall'):
        if got_from.find('_')<0:
            DBG.trace("# wall_id not given - scan first 100 records")
            res = vk_api.wall.get(owner_id=int(got_from[4:], count=100))
            for c in res[u'items']:
                fwd = m.get(u'fwd_messages',[])
                attachments = list( m.get(u'attachments',[]) )
                for f in fwd:
                    attachments += f.get( u'attachments', [] )
                for a in attachments:
                    if u'wall' in a:
                        a = a[u'wall']
                        hist = a.get( u'copy_history', [a] )[0]
                        attachments += hist.get(u'attachments', [])
                for a in attachments:
                    if u'video' in a:
                        a = a[u'video']
                        videoid = "/video%s_%s" % ( a.get(u'owner_id',0), a.get(u'id',0) )
                        if videoid == url_to_find:
                            got_from += "_%d" % res[u'id']
                            break
                if got_from.find('_')>0:
                    break

        DBG.trace('session.get("https://m.vk.com/%s")' % got_from )
        response = session.get( "https://m.vk.com/%s" % got_from )
        rv = findVKVideo( response._content )
        if rv:
            return rv
        return ['',[]]


    peer, msgid = got_from.split('_')
    msgid = int(msgid)
    re_msgid = re.compile('<a +name="msg([0-9]+)"')
    err_pattern = '<a name="msg%s"' % msgid

    # Initialize cookies (needed to give non-empty an answer from VK)
    session.cookies.set("remixflash","15.0.0")
    session.cookies.set("remixscreen_depth","24")
    session.cookies.set("audio_vol","11")
    session.cookies.set("remixrefkey","f53ccbec41bfb820c6")
    session.cookies.set("remixseenads","0")
    session.cookies.set("audio_time_left","0")
    session.cookies.set("remixdt","0")
    session.cookies.set("remixtst","6b2275e1")
    session.cookies.set("remixmdevice","1920/1080/1/!!-!!!!")
    session.cookies.set("remixmdv","JhlfJclfjPOUzOW6")
    ##DBG.trace( "COOKIES\n>>>\n%s\n<<<", [ session.cookies.get_dict() ] )

    for offset in xrange(0,2000,20):
        url = "https://m.vk.com/mail?act=show&%s&offset=%d" % (peer,offset)
        DBG.trace('session.get("%s")' % url )

        """
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:28.0) Gecko/20100101 Firefox/28.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': url
        }

        response2 = session.post(url, data="_ajax=1", headers=headers) #
        DBG.trace(u'response2\n%s', [response2._content])
        """

        response = session.get( url )
        rv = findVKVideo( response._content )
        if rv:
            return rv
        if response._content.find(err_pattern)>=0:
            DBG.TODO('Not found video %s|%s but exists %s', [url,got_from,err_pattern] )
        for match in re_msgid.finditer(response._content):
            if int(match.group(1)) > msgid:
                DBG.trace('found %s' % match.group(1))
                break
        else:
            DBG.TODO('Nothing found in message. Maybe need to fix cookies.')
            DBG.trace('no greater than %s found' % msgid )
            # no msgid greater than required found - stop scan
            return ['',[]]
    DBG.trace('offset = %s' % offset)
    # scan too far - stop it
    return ['',[]]




"""
#############################################
"""
#vk_api.show_blink = True

"""
#############################################
#     ACTION 'photo' (download images)      #
#############################################
"""

def executePHOTO():
    global MAIN_PROFILE, TGTDIR


    for load in load_queue:
        if load[0] not in ['user','group']:
            continue

        load_objtype, load_objid, load_objname, load_albumname = load[:4]

        say( "\n\nСкачиваем фото %s '%s' {%s}", (load_objtype, load_objname, load_objid) )

        MAIN_PROFILE = '%s_%s' % (load_objtype, load_objid )
        TGTDIR = "%s/IMG-%s-%s" % ( BASEDIR, MAIN_PROFILE, fname_prepare(load_objname) )

        ##say( "Получаем список альбомов" )
        answ = get_cached_albums_list( load_objid )
        albums = {}
        for a in answ[u"items"]:
                if load_albumname is not None and load_albumname!=a[u'id']:
                        continue
                title = str_encode( a[u"title"] ).translate(None,"/:?*\\\"").strip().rstrip(". \t")	#re.sub( "[\/:\?\*\\]", "_", title )
                say( "  %s", a[u"title"] )
                albums[ a[u"id"] ] = fname_prepare(title)


        step = 25
        ofs  = 0
        count = -1
        kw = get_album_kw( load_objid, load_albumname )
        say("   в --> %s", TGTDIR )
        say( "Скачивание в процессе. Пожалуйста ожидайте..." )
        while ( count < 0 or ofs < count ):
                if load_albumname is None:
                        answ = vk_api.photos.getAll( owner_id = load_objid, offset=ofs, count=step, **kw )
                else:
                        answ = vk_api.photos.get( offset=ofs, count=step, **kw )

                for a in answ[u'items']:
                        maxsize=-1
                        url = ''
                        for [k,v] in a.iteritems():
                            k.encode('ascii','xmlcharrefreplace')
                            if k.startswith('photo_'):
                                size = int(k[len('photo_'):])
                                if maxsize < size:
                                    maxsize = size
                                    url = v.encode('ascii','xmlcharrefreplace')

                        aid = a[u'album_id']
                        # skip if not matched
                        if int(aid)>=0 and aid not in albums:
                            say( "skip %s", aid )
                            continue

                        albumid = albums.get( aid, str(aid) )
                        to_path = "./%s/%s" % (TGTDIR, fname_prepare(albumid) )

                        n = "%s-%s" % ( int(a[u'id']), url.split('/')[-1] )
                        dload_attach( to_path, n, url, None, False )
                util.print_mark(".(%d)"%ofs)

                count = int( answ[u'count'] )
                #count = 110
                ofs = ofs + step
                #print answ

"""
#############################################
#           Some extra prepare              #
#############################################
"""

# DOWNLOAD MP3 SKIP LIST

def _cut_prefix( s ):
    s = s.strip()
    if len(s)>5 and s[0]=='[' and s[5]==']':
        return s[6:]
    return s


def PrepareMediaConfigs():
    global SKIP_MP3_LIST, SKIP_MP3_SET, len_mp3list
    global VIDEO_LIST, VIDEO_LIST_SET, len_videolist, start_video_idx

    SKIP_MP3_LIST, SKIP_MP3_SET = util.load_data_file( FILE_MP3_SKIP, main_col=0 )
    SKIP_MP3_SET = set( map(lambda s: _cut_prefix(s), SKIP_MP3_SET ) )


    #VIDEO_LIST[] = [ 0size(if dloaded), 1url, 2fname, 3title, 4duration ]
    VIDEO_LIST, VIDEO_LIST_SET = util.load_data_file( FILE_VIDEO, main_col=2 )
    ##for l in VIDEO_LIST_SET:
    ##    say( "%s %s", [type(l),l] )

    len_mp3list, len_videolist = len(SKIP_MP3_LIST), len(VIDEO_LIST)
    start_video_idx = len_videolist

def save_mp3_video():
    global len_mp3list, len_videolist

    if len(VIDEO_LIST)!= len_videolist:
        util.save_data_file( FILE_VIDEO,  VIDEO_LIST )
    if ( CONFIG['DOWNLOAD_MP3_ONCE'] and
            len(SKIP_MP3_LIST)!= len_mp3list ):
        util.save_data_file( FILE_MP3_SKIP,  SKIP_MP3_LIST )
    len_mp3list, len_videolist = len(SKIP_MP3_LIST), len(VIDEO_LIST)


"""
#############################################
#       ACTION 'mp3' (download MP3)         #
#############################################
"""

# Process MP3 downloading
def executeMP3():
    global MAIN_PROFILE, MP3DIR

    for load in load_queue:
        if load[0] not in ['user','group']:
            continue

        load_objtype, load_objid, load_objname, load_albumname = load[:4]

        say( "\nСкачиваем MP3 %s '%s' {%s}", ( load_objtype, load_objname, load_objid ) )

        MAIN_PROFILE = '%s_%s' % ( load_objtype, load_objid )
        MP3DIR = "%s/MP3-%s-%s" % ( BASEDIR, MAIN_PROFILE, fname_prepare(str_decode(load_objname)) )

        kw = get_album_kw( load_objid, load_albumname )
        ##say( "*** %s",  kw )
        if load_albumname is not None:
            say("Альбом #%s", load_albumname)
        say("   в --> %s", MP3DIR )

        answ = vk_api.audio.get( count = 2000, **kw )
        idx = int(answ[u'count'])
        for item in answ[u'items']:
                log = "[%04d] %s - %s" % ( idx, item[u'artist'][:50], item[u'title'][:50])
                say("%s", log)      #.replace("&#1110;","i")
                url = item[u'url']
                fname = "[%04d]%s - %s.mp3" % ( idx, item[u'artist'][:50], item[u'title'][:100] )
                dload_attach( MP3DIR, fname, url, mark=None, needPrefix=False, type='mp3' )
                ##print "[%04d] %s - %s ==> %s" % ( idx, item[u'artist'], item[u'title'], item[u'url'] )
                idx = idx - 1
        ##print answ

    save_mp3_video()



"""
##########################################################
#       ACTION 'wall' (download wall+comment+like)       #
##########################################################
"""

def executeWALL():
    global load_queue, MAIN_PROFILE, IF_DELETE, start_video_idx
    global list_to_del, messages
    global cacheHandler, MSG_CACHE, MSG_CACHE_FILES, MSG2BACKUP

    say( "\nНастройки сохранения стены:" )
    util.print_vars( ['WALL_QUICKUPDATE', 'DOWNLOAD_AS_HTML', 'LOAD_COMMENTS', 'LOAD_LIKES', 'SEPARATE_TEXT'], CONFIG )
    say()
    util.print_vars( ['SEPARATE_MEDIA', 'DOWNLOAD_MP3', 'DOWNLOAD_MP3_ONCE', 'DOWNLOAD_VIDEO'], CONFIG )

    for load in load_queue:
        if load[0] not in ['user','group']:
            continue
        try: load[1] = int(load[1])
        except: pass

        load_objtype, load_objid, load_objname = load[:3]

        init_dirs( objtype='WALL', objid=load[1], objname=load[2] )
        MAIN_PROFILE = ''
        IF_DELETE = 0
        list_to_del = []        # []            = [id_to_del, id_to_del,..]
        messages = {}           # [msgid]     = [time, who, body]

        say( "\nСохраняем стену %s {%s}", (load[2], load[1]) )

        """ -- Media split handlers --"""

        def reinitPerMsg( msgid, msgtime, who ):
            global IMGDIR, MP3DIR, DOCDIR, BASEDIR
            lt = time.localtime(CURMSG_TIME)
            tstamp = "%04d%02d%02d_%02d%02d%02d" % (lt.tm_year, lt.tm_mon, lt.tm_mday, lt.tm_hour,lt.tm_min,lt.tm_sec )
            IMGDIR =  os.path.join( BASEDIR, "[%04d]%s-%s-%s" % ( msgid, tstamp, load[1], fname_prepare(load[2]) ) ).strip()
            MP3DIR = IMGDIR


        def reinit_Calendar( template, tstamp ):
            global IMGDIR, MP3DIR, DOCDIR, BASEDIR
            IMGDIR =  os.path.join( BASEDIR, template % ( load[1], tstamp, fname_prepare(load[2]) ) ).strip()
            MP3DIR = IMGDIR

        def reinitPerYear( msgid, msgtime, who ):
            lt = time.localtime(CURMSG_TIME)
            reinit_Calendar( "(%s)-y%s-%s", "%04d" % (lt.tm_year) )

        def reinitPerMonth( msgid, msgtime, who ):
            lt = time.localtime(CURMSG_TIME)
            reinit_Calendar( "(%s)-%s-%s", "%04d%02d" % (lt.tm_year, lt.tm_mon) )

        def reinitPerDay( msgid, msgtime, who ):
            lt = time.localtime(CURMSG_TIME)
            reinit_Calendar( "(%s)-%s-%s", "%04d%02d%02d" % (lt.tm_year, lt.tm_mon, lt.tm_mday) )

        mediaHandlersDict = { 'id': reinitPerMsg, 'month': reinitPerMonth, 'year': reinitPerYear, None: None }
        mediaHandler =   mediaHandlersDict.get( CONFIG['SEPARATE_MEDIA'], reinitPerMonth )

        """ -- Text handlers --"""

        # Define text separation handlers

        # handler( msgid, [time, who] )
        def textAll( k, v ):     return None
        def textByDay( k, v ): return time.strftime("%Y%m%d", time.localtime(v[0]))
        def textByMonth( k, v ): return time.strftime("%Y%m", time.localtime(v[0]))
        def textByYear( k, v ):  return time.strftime("%Y", time.localtime(v[0]))
        def textById( k, v ):    return "%05d{%s}" % ( k, time.strftime("%Y%m%d", time.localtime(v[0])) )

        # Prepare text handlers
        ##template = '%(dir)s/%(type)s_%(id)s(%(name)s)%(suffix)s.%(ext)s'
        templateFname = '%(dir)s/wall_%(id)s(%(name)s)%(suffix)s.%(ext)s'
        templateTitle = 'WALL OF %(who)s at %(key)s'

        textHandleDict = { 'day': textByDay, 'month': textByMonth, 'year': textByYear, 'id': textById, None: textAll }

        isHTML = CONFIG['DOWNLOAD_AS_HTML']
        textHandler = textHandleDict.get( CONFIG['SEPARATE_TEXT'], textByYear )
        if ( not isHTML or textHandler==textAll ):
            template_title = 'WALL OF %(who)s'

        def _makeFName( vv, html ):
            return templateFname % {
                                'dir': BASEDIR,
                                'type': load[0],        #wall
                                'id': load[1],
                                'name': fname_prepare(load[2]),
                                'suffix': '_%s'%vv if vv else '',
                                'ext': 'html' if html else 'txt' }

        # Handler which check existance of msg in cache and try to load cache from .html file
        # RETURN: None or
        #      [ 0owner, 1id, 2time, 3who, 4remark, 5likes, 6preview_text, 7is_only_img_attach, -1body ]

        def cacheHandler( textHandler, msgid, t, who ):
            global MSG_CACHE_FILES          # MSG_CACHE_FILES[suffix] = True if that file was loaded to cache,
                                            #                           Absent if not processed yet
            global MSG_CACHE                # MSG_CACHE[msgid] = [ 0owner, 1id, 2time, 3who, 4remark, 5likes, 6preview_text, 7is_only_img_attach, -1body ]

            if msgid in MSG_CACHE:
                return MSG_CACHE[msgid]

            vv = textHandler( msgid, [t, who] )
            if vv in MSG_CACHE_FILES:
                return None

            MSG_CACHE_FILES[vv] = True      # Mark file as processed

            TGT_FILE = _makeFName( vv, True )
            ##print str_cp866(TGT_FILE)
            if not os.path.isfile(TGT_FILE):
                return None

            msg = None
            with open( TGT_FILE, 'rb' ) as f:
                for l in f:
                    if msg is None:
                        # check is file use the same paths for attachment
                        if l.startswith('<!--\tSEPARATE_MEDIA\t'):
                            l1 = l.split('\t')
                            if l1[2]!=CONFIG['SEPARATE_MEDIA']:
                                return None

                        # detect beginning of the record
                        if l.startswith('<!--\tWALL\t'):
                            l1 = l.split('\t')
                            msg = l1[2:-1] + [ [] ]
                    elif l.startswith('<!--\tSTOPWALL\t'):
                        # load body of the record
                        msg[-1] = ''.join(msg[-1])
                        MSG_CACHE[int(msg[1])] = msg
                        msg = None
                    else:
                        msg[-1].append(l)

            return MSG_CACHE.get( msgid, None )


        """ -- SAVE WALL Processor --"""

        def _writeHTMLPrefix( fp, html_title ):
            fp.write('<html>\n<head>\n<meta http-equiv="Content-Type" content="text/html;charset=cp1251">\n')
            fp.write('<title>' + html_title +'</title>\n' )
            fp.write('<style>a.b:link, a.b:visited, a.b:active,a.b:hover { color: black; text-decoration: underline;}</style>\n')
            fp.write('<!--\tSEPARATE_MEDIA\t%s\t-->\n' % CONFIG['SEPARATE_MEDIA'] )
            fp.write('</head>\n<body>\n\n')


        # Write Wall by templates and split handler
        def writeWall( handler, title, html, writeIndex = False ):
            conv = {}           # msgid -> target_file_suffix

            for k, v in MSG_CACHE.iteritems():
                conv[k] = handler( k, [int(v[2]), int(v[3])] )

            for k, v in messages.iteritems():
                if v is not None:
                    conv[k] = handler(k,v)

            dedupe_by_preview = {}      # preview_text -> main_msg_id
            duplicates = {}             # duplicated_id -> main_msg_id
            if CONFIG['WALL_DEDUPE']:
                for k in reversed(sorted(conv.keys())):
                    if k in messages:
                        preview = messages[k][5]
                    else:
                        preview = MSG_CACHE[k][6]

                    if preview in dedupe_by_preview:
                        duplicates[k] = dedupe_by_preview[preview]
                    else:
                        dedupe_by_preview[preview] = k

            preview = {}
            TAG_HIDE_DUPE = '<!-- HIDE: DUPLICATE OF THE WALL RECORD'
            TAG_HIDE_IMGONLY = '<!-- HIDE: ONLY IMAGE'
            for vv in set(conv.values()):

                TGT_FILE = _makeFName( vv, html )
                with open( TGT_FILE, 'wb' ) as f:
                    if html:
                        _writeHTMLPrefix( f, title % {'who':makehtml(load[2]), 'key':vv} )

                    keys = filter( lambda k: conv[k]==vv, conv.keys() )
                    for k in sorted( keys ):
                        v = messages.get( k, [0] )
                        t = time.localtime(v[0])
                        timestr = time.strftime("%d.%m.%y %H:%M", t )

                        # CASE 1: TEXT SAVE - no any extra action
                        if not html:
                            f.write( "===== %s (%s) %s =====\n\n" % ( timestr, str_encode(DAYS[t.tm_wday]), make_profiletext(v[1]) ) )
                            f.write( v[2].strip() +"\n\n")
                            if len(v[4])>0:
                                f.write( "***LIKES**\n")
                                f.write( ', '.join( map( lambda i: make_profiletext(i), v[4]) ) )
                                f.write( "\n\n")
                            for ck in sorted(v[3].keys()):
                                c = v[3][ck]
                                ctimestr = time.strftime("%d.%m.%y %H:%M", time.localtime(c[0]) )
                                f.write( "***COMMENT %d:: "%ck)
                                f.write( "%s %s" % ( ctimestr, make_profiletext(c[1]) ) )
                                if c[3] is not None:
                                    f.write(" -> %s" % make_profiletext(c[3]) )
                                f.write( "\n%s\n\n" % c[2] )

                        elif len(v)==1:
                            # CASE 2: RESTORE FROM MSG_CACHE COMPLETELY
                            #   trigger - there is nothing in stored in message - so nothing were changed
                            # [ 0owner, 1id, 2time, 3who, 4remark, 5likes, 6preview_text, 7is_only_img_attach, -1body ]
                            msg = MSG_CACHE[k]
                            f.write('<!--\tWALL\t%s\tRESTORED-->\n' % ('\t'.join(msg[:-1])) )
                            body = msg[-1]
                            if ( k in duplicates and
                                 not body.startswith(TAG_HIDE_DUPE) ):
                                body = ('%s %s\n' % (TAG_HIDE_DUPE,duplicates[k]) ) + body

                            f.write( body )
                            f.write('<!--\tSTOPWALL\t%d\t%d\t-->\n\n' % (load[1],k) )

                            #               0tofile, 1time, 2who, 3preview
                            preview[k] = [ os.path.basename(TGT_FILE), msg[2], msg[3], msg[6] ]

                        else:
                            # CASE 3: REMEMBER THE MESSAGE (something was changed)
                            # a) likes or comments are encreased
                            # b) likes/comments are decreased and WALL_BACKUP=True

                            preview[k] = [ os.path.basename(TGT_FILE), v[0], v[1], v[5] ]
                                                                                          #0owner,1id,2time,3who, 4remark,  5likes,    6preview text,  7is_only_img_attach
                            f.write('<!--\tWALL\t%d\t%d\t%d\t%d\t%d\t%d\t%s\t%s\t-->\n' % (load[1],k, v[0],v[1], len(v[3]), len(v[4]), v[5],           v[6]) )
                            if k in duplicates:
                                f.fwrite( TAG_HIDE_DUPE + ' %s\n' % duplicates[k] )
                            if v[6] and len(v[5])==0 and CONFIG['WALL_HIDE_ONLY_IMAGE']:
                                f.fwrite( TAG_HIDE_IMGONLY + ' %s\n' % duplicates[k])

                            f.write('<table border=0 width=75%>\n')
                            f.write('<tr><td width=5% nowrap>' +
                                        '<b><A target=_blank HREF="https://vk.com/wall%s_%s" class=b>%s</A></b></td><td align=left><A name="%s"> &nbsp; %s</td>\n' % (load[1],k, timestr, k, make_profilehtml(v[1])) )
                            f.write('<tr><td>&nbsp;</td><td align=left>%s</td>\n' % v[2].strip() )
                            # list comments
                            if len(v[3])>0:
                                f.write('<tr><td><td align=left><hr width=50% align=left>\n')
                                f.write('<tr><td><td><table border=0 bgcolor=#F0F0F0>\n')
                                for ck in sorted(v[3].keys()):
                                    c = v[3][ck]
                                    ctimestr = time.strftime("%d.%m.%y %H:%M", time.localtime(c[0]) )

                                    #f.write('	<tr><td colspan=2><A name="%s_%s"><font size=-1>%s &nbsp; %s' % (k,ck, ctimestr, make_profilehtml(c[1])) )
                                    f.write('	<tr><td width=1% nowrap>' + '<A name="%s_%s"><font size=-1>%s</td><td> &nbsp; %s' % (k,ck, ctimestr, make_profilehtml(c[1])) )
                                    if c[3] is not None:
                                        f.write(" -> %s" % make_profiletext(c[3]) )
                                    #f.write( "</td>\n	<tr><td> &nbsp; </td><td>%s</td>\n" % c[2] )
                                    f.write( "</td>\n	<tr><td> </td><td>%s</td>\n" % c[2] )
                                f.write(' </table></td>\n')
                            # list likes
                            if len(v[4])>0:
                                likes =  ', '.join( map( lambda i: make_profilehtml(i), v[4]) )
                                f.write('<tr><td><td align=left><hr width=50% align=left>\n')
                                #f.write('<tr><td><td bgcolor=#F0F0F0><i>Likes: %s</i></td>\n' % likes )
                                f.write('<tr><td><td bgcolor=#F0F0F0><table border=0><tr><td><i>Likes</td><td><i>%s</i></td></table></td>\n' % likes )
                            f.write('</table>\n<HR>\n')

                            # ... Process WALL_BACKUP
                            if CONFIG['WALL_BACKUP'] and (k in MSG_CACHE):
                                msg_cached = MSG_CACHE[k]
                                body = msg_cached[-1]

                                # a) values were decreased - add last entry to backup list
                                if (k in MSG2BACKUP):
                                    f.write('<!--\tBACKUP\t%s\\tRESTORED-->\n' % ('\t'.join(msg_cached[:-1])) )
                                    body = replace("<tr><td width=1% nowrap>", "<tr><td width=1% bgcolor=#80FF80 nowrap>")
                                    f.write( body )
                                # b) values were increased - keep previous backup list
                                else:
                                    ar = body.split('<!--\tBACKUP\t',1)
                                    if len(ar)>1:
                                        f.write('<!--\tBACKUP\t'+ar[1])

                            f.write('<!--\tSTOPWALL\t%d\t%d\t-->\n\n' % (load[1],k))

                    if html:
                        f.write('\n\n</body></html>\n')

            if writeIndex and len(preview):
                min_id = min( preview.iterkeys() )
                TGT_FILE = _makeFName( "index%d"%min_id, True )
                with open(TGT_FILE, 'wb') as indexFile:
                    _writeHTMLPrefix( indexFile, "INDEX OF WALL OF %s" % makehtml(load[2]) )
                    indexFile.write('<table border=0 width=75%>\n')
                    prev_year = None
                    for msgid in reversed( sorted(preview.iterkeys()) ):
                        pfname, ptime, pwho, pbody = preview[msgid]
                        timestr = time.strftime("%d.%m.%y %H:%M", time.localtime(int(ptime)) )

                        cur_year = time.strftime("%Y", time.localtime(int(ptime)) )
                        if prev_year is not None and cur_year!=prev_year:
                            indexFile.write('<tr><td>&nbsp;</td>\n'+
                                            '<tr valign=top><td>&nbsp</td><td colspan=2><hr></td>\n')
                        prev_year = cur_year

                        indexFile.write('<tr><td>&nbsp;</td>\n'+
                                        '<tr valign=top><td width=5% nowrap><B>' +
                                        '<A HREF="%s#%s" class=b>%s</A></td><td>%s</td><td>%s</td>\n' % ( str_encode(pfname), msgid, timestr, make_profilehtml(int(pwho)), pbody )
                                       )

                    indexFile.write('</table>\n</body></html>\n')


        """ -- LOAD WALL --"""
        # Load wall
        offs = 0
        BLOCK_SIZE = 50 if not CONFIG['LOAD_LIKES'] else 30
        MSG_CACHE = {}
        MSG_CACHE_FILES = {}
        MSG2BACKUP = []                         # id of messages which comments/likes were decreased
        got_from = "wall%s"%(load[1])
        while True:
            res = vk_api.wall.get( owner_id=load[1], offset=offs, count=BLOCK_SIZE, filter='all', extended=1 )
            DBG.trace( "%d: ln=%d" % (offs,len(res[u'items']) ) )
            offs += BLOCK_SIZE
            if len(res[u'items'])==0:
                break
            preload  = map( lambda item:  int(item[u'id']), res[u'profiles'] )
            preload += map( lambda item: -int(item[u'id']), res[u'groups'] )
            vk_utils.lazy_profile_batch += preload

            if isHTML and CONFIG['WALL_QUICKUPDATE']:
                minid = get_msg( res, key_body = u'text', reinitHandler = mediaHandler, html=isHTML, cacheHandler=cacheHandler, textHandler = textHandler, got_from = got_from )
            else:
                minid = get_msg( res, key_body = u'text', reinitHandler = mediaHandler, html=isHTML, got_from = got_from )

            # auto-save wall and lists (on case of fail inside)
            if CONFIG['WALL_QUICKUPDATE']:
                ##util.print_mark('>')
                writeWall( textHandler, templateTitle, html=isHTML )
                ##util.print_mark('!')
                save_mp3_video()
                ##util.print_mark('<')
            if minid<0:
                break

        # Final write with index (in progress we do not write index because it partial and we spam with names)
        writeWall( textHandler, templateTitle,  html=isHTML, writeIndex = True )
        save_mp3_video()
        try:
            downloadVideo( FILE_VIDEO, start_video_idx )
        except OkExit:
            pass
        start_video_idx = len_videolist

        say()

"""
###################################################
#       ACTION 'delete' (delete chat)             #
###################################################
"""
def removeMessage( list_to_del ):
        list_to_del = list(list_to_del)
        list_to_del.sort()
        lst = list_to_del
        batch_size = 100
        with open( FILE_BAKDEL, "ab" ) as tmpfp:
            while len(lst) > 0:
               if len(lst) > batch_size :
                    delids = ','.join( map( lambda s: str(s), lst[0:batch_size] ) )
                    lst = lst[batch_size:]
               else:
                    delids = ','.join( map( lambda s: str(s), lst ) )
                    lst = []
               #print "DELETE %s" % str(delids)
               tmpfp.write( str_encode(delids) + "\n" )
               tmpfp.flush()
               vk_api.messages.delete( message_ids=delids )
               util.print_mark('.')
            say()

def executeDELETE():
    global load_queue

    # transform loaded from API messages to form good to investigate
    def load_short_messages( messages ):
        res = {}
        for m in messages:
            id = int(m.get(u'id',0))
            t = int(m.get(u'date'))
            who = get_profile( m.get(u'from_id',1) )

            attach = m.get(u'attachments',[])
            fwd = m.get(u'fwd_messages',[])

            body =  m.get(u'body','')
            if u'copy_history' in m:
                attach.append({u'wall':dict(m)})

            for f in fwd:
                if u'user_id' in f:
                    cbody = f.get(u'body','')
                else:
                    cbody =  str(f)
                body += '\n' + cbody
            for a in attach:
                if u'wall' in a:
                    a = a[u'wall']
                    hist = a.get( u'copy_history', [a] )[0]
                    text = hist.get( u'text', '' )
                    body += '\n' + text


            delFlag = (( CONFIG['DEL_ENFORCED'] ) or             # delete if
                        ( m.get(u'read_state',0)!=0                # ...readed
                        and m.get(u'important',0)==0               # ...and unimportant
                        and len(attach)==0 and len(fwd)==0         # ...not specific(have no attachments or forward)
                        and len(body.strip())!=0                   # ...have not empty body - so everything was ok
                        ) )

            body = str_encode(body.strip())
            for [k,v] in repl_ar.iteritems():
                body = body.replace(k,v)
            body = str_decode(body)
            res[id] = [ t, body, delFlag ]
        return res


    # NOTE: PRESUMED THAT WE GET BLOCKS OF MESSAGES IN REVERSE ORDER
    def prepare_del( all_messages, control, messages ):
        messages = load_short_messages( messages[u'items'] )

        # If there are no more messages - just stop
        if len(messages)==0:
            return -1

        all_messages.update(messages)

        ##for m in sorted(messages.iterkeys()):
        ##    say( "%s\t%s", [m, util.str_fulltime(messages[m][0]) ] )

        # we should care about case of border (all prev block match, but none of current match)
        if control['startid'] is None:
            # If start from time - then just accumulate all later messages and when find first when stop to accumulate
            if isinstance(startcond,float):
                mfiltered = dict( filter( lambda item: item[1][0]>=startcond, messages.items() ) )
                ##print 'start '+ util.make_join(',',sorted(mfiltered.keys()))
                control['startlist'] += mfiltered.keys()
                if len(mfiltered)!=len(messages):
                    if len(control['startlist']):
                        control['startid'] = min(control['startlist'])  # ok
                    else:
                        control['startid'] = -1                         # empty list - noone message starts after starttime
                    ##print 'set startid '+ str(control['startid'])

            # If start by text - then stop at the moment when we found it
            elif len(startcond):
                mfiltered = dict( filter( lambda item: item[1][1].lower().find(startcond)>=0, messages.items() ) )
                if len(mfiltered):
                    control['startid'] = max(mfiltered.keys())

        # we iterate blocks in reverse order, so if we already found stopid - we don't need to check it more
        if control['stopid'] is None:

            # If stop by time - then find max of from all <=
            if isinstance(stopcond,float):
                mfiltered = dict( filter( lambda item: item[1][0]<=stopcond, messages.items() ) )
                if len(mfiltered):
                    ##print 'stop '+ util.make_join(',',sorted(mfiltered.keys()))
                    control['stopid'] = max(mfiltered.keys())
                    ##print 'set stopid '+ str(control['stopid'])

            # If stop by text - then we get id of any matched
            elif len(stopcond):
                mfiltered = dict( filter( lambda item: item[1][1].lower().find(stopcond)>=0, messages.items() ) )
                if len(mfiltered):
                    control['stopid'] = max(mfiltered.keys())
        return min(messages.keys())

    def prepareinput( value, def_time  ):
        match = re.match("([0-9]+)\.([0-9]+)\.?([0-9]+)?( +([0-9]+):([0-9]+):?([0-9]+)?)?",value)
        if match:
            match = map(lambda g: match.group(g), range(0,7+1))
            today = time.time()
            match[3] =  time.strftime("%Y", time.localtime(today)) if match[3] is None else match[3]
            if match[4] is None:
                match[5]=def_time[0]
                match[6]=def_time[1]
                match[7]=def_time[2]
            match[7] =  def_time[2] if match[7] is None else match[7]
            match[4]=0
            day, month, year, tmp, hour,minutes, sec = map(lambda v: int(v), match[1:])
            if year <100:
                year += 1900 if year>50 else 2000
            t = time.mktime( tuple([year, month, day, hour, minutes, sec, -1, -1, -1]) )
            say("Ввведено: дата %s", util.str_fulltime(t) )
            return t

        value = str_decode( value.strip(), inputencoding )
        if value:
            say("Введено: в сообщении должен быть текст \"%s\"", value)
        else:
            say("Введено: без ограничений")
        return value.lower()



    for load in load_queue:
        # PREPARE AND PRINT NAME
        if load[0]=='user':
                load[2]=make_profiletext(load[1])
                name = load[2]
        elif load[0]=='chat':
                name = unicformat("чата '%s'", load[2])
        else:
                continue

        say("Удаление множества сообщений  %s {%s}", (name, load[1]))

        today_str = time.strftime("%d.%m.%y %H:%M")

        say("\nВведите дату (в формате %s) или текст первого сообщения или пустую строку - чтобы удалить с самого начала.", today_str)
        start = util.getinput("Удалить начиная с: ").strip()
        startcond = prepareinput( start, def_time=[0,0,0] )

        say("\nВведите дату (в формате 31.01.2014 22:03) или текст последнего сообщения или пустую строку - чтобы удалить по сейчас.")
        stop = util.getinput("Удалить заканчивая(включительно): ").strip()
        stopcond = prepareinput( stop, def_time=[23,59,59])

        say("\nИщем записи...\n---------\n")

        kw = { ("%s_id" % load[0]) : load[1] }
        BLOCK_SIZE=200
        all_messages = {}
        control = {'startid': None, 'stopid': None, 'startlist':[] }
        id = prepare_del( all_messages, control, vk_api.messages.getHistory( offset=0, count = BLOCK_SIZE, **kw ) )
        while control['startid'] is None and id>0:
            id = prepare_del( all_messages, control, vk_api.messages.getHistory( start_message_id=id, offset=-1, count = BLOCK_SIZE, **kw ) )

        if len(all_messages)==0:
            say("Нечего удалять...")
            continue
        startid, stopid = control['startid'], control['stopid']
        startid = min(all_messages.keys()) if startid is None else startid
        stopid  = max(all_messages.keys()) if stopid is None  else stopid
        if startid>stopid or startid<0:
            say("Нечего удалять...")
            continue

        say("Будут удалены сообщения:")
        say("[НАЧИНАЯ С %s]\n%s\n",  [ util.str_fulltime(all_messages[startid][0]), all_messages[startid][1][:250].strip() ] )
        say("[ЗАКАНЧИВАЯ %s]\n%s\n", [ util.str_fulltime(all_messages[stopid][0]),  all_messages[stopid][1][:250].strip() ] )

        id_list = filter(lambda i: i>=startid and i<=stopid, all_messages.keys() )
        id_list = filter(lambda i:  all_messages[i][2], id_list )
        ##for k in sorted(id_list):
        ##    say("%d\t%s\t%s\t%s", [k, util.str_fulltime(all_messages[k][0]), str(all_messages[k][2]), all_messages[k][1]])

        if not util.confirm("Вы уверены[y/n]?"):
            continue

        say( "Удаляем сообщения" )
        removeMessage( id_list )



"""
###################################################
#       ACTION 'message' (download chat)          #
###################################################
"""


def executeMESSAGE():
    global MAIN_PROFILE, load_queue
    global stop_id, lastdel_id, last_times, msg_util_val
    global list_to_del, messages, start_video_idx, IF_DELETE

    #Load current:
    #    profile_id = stop_id, lastdeleted_id, last_msg_time
    ##say( "Load last messages ids" )
    msg_util_val = util.load_dict_file( FILE_MAIN, key_sep='=', val_sep=',' )
    for id, values in msg_util_val.iteritems():
        values += [0,0,0]
        stop_id[id] = int(values[0])
        lastdel_id[id] = min( [ stop_id[id], int(values[1]) ] )
        last_times[id] = int(values[2])

    DBG.trace("stop_id=%s", [stop_id])
    DBG.trace("lastdel_id=%s", [lastdel_id])
    DBG.trace("last_times=%s", [last_times])

    # # If nothing was stored - at least 200 days
    #if not os.path.exists( FILE_STORED ):
    #	stop_id[MAIN_PROFILE] = 0
    #	DAYSBEFORE = max( DAYSBEFORE, 200 )
    # stoptime =

    # Process MESSAGE downloading
    for load in load_queue:
        try:

            stored = []
            purged_cnt = 0
            to_remember = []

            # 1. PREPARE AND PRINT NAME
            if load[0]=='user':
                    load[2]=make_profiletext(load[1])
                    name = load[2]
            elif load[0]=='chat':
                    name = unicformat("чата '%s'", load[2] )
            else:
                    continue
            say( "\nСкачиваем сообщения  %s {%s}", (name, load[1]) )

            IF_DELETE = IF_DELETE_GLOBAL
            if IF_DELETE is None:
                    IF_DELETE = util.confirm( "Вы хотите удалить скачанные сообщения[y/n]? " )
                    IF_DELETE = 1 if IF_DELETE else -1
            if IF_DELETE>0:
                    say( "Сообщения будут удалены после скачивания" )
            elif IF_DELETE<0:
                    say( "Сообщения останутся после скачивания" )
            else:
                    say( "Сообщения останутся после скачивания, но будут удалены после следующего скачивания с удалением" )

            # 2. INIT AUX ARRAYS
            list_to_del = []        # []            = [id_to_del, id_to_del,..]
            messages = {}           # [msgid]     = [time, who, body]

            # 3. DOWNLOAD MESSAGES
            kw = { ("%s_id" % load[0]) : load[1] }
            init_dirs( objtype=load[0], objid=load[1], objname=load[2] )

            stop_id[MAIN_PROFILE] = stop_id.get(MAIN_PROFILE,0)
            lastdel_id[MAIN_PROFILE] = lastdel_id.get(MAIN_PROFILE,0)
            last_times[MAIN_PROFILE] = last_times.get(MAIN_PROFILE,0)
            say( "stop=%s, del=%s " % (stop_id[MAIN_PROFILE], lastdel_id[MAIN_PROFILE]) )

            lastdel_time, stopmsg_time = 0,0
            was_stop, was_last = stop_id[MAIN_PROFILE], lastdel_id[MAIN_PROFILE]

            if lastdel_id[MAIN_PROFILE]<1:

                if IF_DELETE>0:
                    DBG.error("UNSAFE CLEANING!!")
                    if not CONFIG.get('MACHINE',False):
                        say( "Небезопасное удаление (вся переписка) отменено" )
                    else:
                        say( "{MACHINE}: unsafe clean canceled" )
                IF_DELETE = -1


            res = vk_api.messages.getHistory( offset=0, count = 200, **kw )
            if len(res):
                m = res[u'items'][0]
                if CONFIG.get('NOT_KEEP_IF_MINE',False) and util.make_int(m.get(u'from_id',1))==me:
                    config.CONFIG['KEEP_LAST_SECONDS'] = 0

            got_from = "%s=%s"%(load[0],load[1])
            id = get_msg( res, got_from = got_from )
            while id > 0:
                id = get_msg( vk_api.messages.getHistory( start_message_id=id, offset=-1, count = 200, **kw ), got_from = got_from )
            say()

            if IF_DELETE==0:
                list_to_del = []

            if len(messages)==0 and len(list_to_del)==0:
                continue

            # 4. WRITE TO TGT FILE --> only text is supported now
            TGT_FILE = str_encode( u'%s/%s_%s.txt' % ( BASEDIR, str_decode(MAIN_PROFILE), str_decode(load[2]) ), util.fsencode  )
            firstTimeFlag = not os.path.exists(TGT_FILE)
            tmpfp = os.open( TGT_FILE, os.O_RDWR|os.O_APPEND|os.O_CREAT|O_BINARY, 0644 )
            if not tmpfp:
                raise FatalError( unicformat("Ошибка открытия файла сообщений %s", TGT_FILE ) )
            if firstTimeFlag:
                    os.write( tmpfp, load[2] )
                    os.write( tmpfp, "\n\n")

            prev = [ last_times[MAIN_PROFILE], 0, '']

            keys = messages.keys()
            keys.sort()
            prev_dir = ''
            for k in keys:
                v = messages[k]
                t = time.localtime(v[0])
                if not len(stored):
                    stopmsg_time = time.strftime("%d.%m.%y %H:%M", t )
                ##print "%s => %s" % (k,str(v))
                if stop_id[MAIN_PROFILE] >= k:
                    ##prev = v
                    continue
                stored.append( k )
                last_times[MAIN_PROFILE] = max( last_times[MAIN_PROFILE], v[0] )
                p = time.localtime(prev[0])
                cross = (t.tm_year!=p.tm_year or t.tm_yday!=p.tm_yday )
                ##print "%s/%s %s/%s" %(t.tm_year,p.tm_year,t.tm_yday,p.tm_yday )
                if cross:
                    timestr = time.strftime("%d.%m.%y", t )
                    timestr = "%s (%s) " % (timestr,str_encode(DAYS[t.tm_wday]))
                    os.write( tmpfp, "\n===== %s\n\n" % timestr )

                if CONFIG['WRITE_MSGID']:
                    os.write( tmpfp, "%s\n" % k )
                pref_who = get_msgdirection( v, me )
                tmsg = time.strftime("%d.%m %H:%M ",t)
                if pref_who==prev_dir:
                    tmsg = '\t'
                    pref_who = ''
                else:
                    prev_dir = pref_who
                to_log_body = to_remember.append(  tmsg +pref_who +"\t"+str_decode(v[2]) )
                #to_log_body = to_remember.append( time.strftime("%d.%m %H:%M",t) +"\t"+str_decode(v[2]) )
                body = v[2].replace('  ',' ').split('\n')               # squeeze spaces (mostly between smiles)
                how_many_t = "\t\t\t" if load[0]=='chat' else "\t\t"
                body = ("\r\n%s" % how_many_t).join(body)
                if abs(v[0]-prev[0]) > 10*60 or v[1]!=prev[1]:
                    timestr = time.strftime("%H:%M",t)
                    if load[0]=='chat':
                        who = "%-10s" % profiles[ v[1] ][1]
                    else:
                        who = profiles[ v[1] ][0]
                    os.write( tmpfp, "%s %s\t" % (timestr,who) )
                else:
                    body = how_many_t + body

                os.write( tmpfp, body + "\r\n" )

                prev = v
            os.close(tmpfp)

            # 5. Remember index of stored messages (debug purpose)
            ##print "Remember stored"
            storedids = ','.join( map( lambda s: str(s), stored ) )
            with open(FILE_STORED, "ab") as tmpfp:
                ##print messages
                prev = ''
                for id in storedids.split(','):
                    if id=='': continue
                    tmpfp.write( id.encode('ascii','xmlcharrefreplace') )
                    v = messages[int(id)]
                    t = time.localtime(v[0])
                    datestr = time.strftime(" %d.%m.%y", t )
                    timestr = time.strftime("%H%M", t )
                    tmpfp.write( "| %s%s%s%s\n" % ('>' if v[1]==me else '<',
                                                     timestr,
                                                     '' if datestr==prev else datestr,
                                                     ' *' if len(v[2].split('\n'))>1 else '' ) )
                    prev = datestr
                tmpfp.write( str_encode(storedids) )

            # 6. PURGE MESSAGES
            purged_cnt = 0

            # a) clean up according to KEEP_LAST_SECONDS
            keep_after_time = time.time() - util.make_int( CONFIG['KEEP_LAST_SECONDS'], 0 )
            filtered = filter( lambda id: messages[int(id)][0]>=keep_after_time, list_to_del )
            if len(filtered):
                print "Keep because of KEEP_LAST_SECONDS: %s" %filtered         #@tsv
            list_to_del = filter( lambda id: messages[int(id)][0]<keep_after_time, list_to_del )

            # b) prepare last visible message in human-readable form
            if len(list_to_del):
                first = sorted(list_to_del)[0]
                v = messages[int(first)]
                t = time.localtime(v[0])
                lastdel_time = time.strftime("%d.%m.%y %H:%M",t )
            elif lastdel_id[MAIN_PROFILE]>0:
                res = vk_api.messages.getById(message_ids=lastdel_id[MAIN_PROFILE])
                if len(res[u'items']):
                    t = time.localtime(res[u'items'][0][u'date'])
                    lastdel_time = time.strftime("after %d.%m.%y %H:%M",t )

            ##print list_to_del
            # c) actually purge them
            if IF_DELETE>0 and len(list_to_del)>0:
                say( "Удаляем сообщения" )
                say( "  minid=%d, maxid=%d", [min(list_to_del), max(list_to_del)])
                purged_cnt = len(list_to_del)
                removeMessage( list_to_del )

            stop_id[MAIN_PROFILE] = max( [ stop_id[MAIN_PROFILE] ] + messages.keys() )
            lastdel_id[MAIN_PROFILE] = max( [ lastdel_id[MAIN_PROFILE] ] + list_to_del )

        finally:
            #7. Log
            if IF_DELETE>0:   mode="del"
            elif IF_DELETE<0: mode="keep"
            else:             mode="postp"
            if isinstance(stopmsg_time,str): stopmsg_time = stopmsg_time.replace('.','')
            if isinstance(lastdel_time,str): lastdel_time = lastdel_time.replace('.','')

            _stopid, _lastdelid = stop_id[MAIN_PROFILE], lastdel_id[MAIN_PROFILE]

            ##print sorted(messages.keys()), repr(_stopid)  #@tsv

            logmsg= u"mode=%s. *%d(t=%s/%s%s,id=%s), -%d(t=%s/%s%s,id=%s), post%d" % ( mode,
                                                                                len(stored), stopmsg_time, get_msgdirection( messages.get(_stopid,None), me ),    was_stop, _stopid,
                                                                                purged_cnt,  lastdel_time, get_msgdirection( messages.get(_lastdelid,None), me ), was_last, _lastdelid,
                                                                                len(list_to_del)-purged_cnt )
            if not CONFIG.get('MACHINE',False):
                say( u"Сохранено %d новых сообщений, удалено %d сообщений", ( len(stored), purged_cnt ) )
            else:
                say( u"{MACHINE}: %s" % logmsg )
            try:
                if not os.path.exists("./LOG"):
                    os.makedirs('./LOG')
                LOG_FILE = "./LOG/store-%s.log"%USER_LOGIN
                content = []
                if os.path.isfile(LOG_FILE):
                    with codecs.open(LOG_FILE,'r','utf-8') as f:
                        content = f.read().splitlines(True)

                if len(content)>2:
                    prelast = content[-2]
                    last = content[-1]
                    if last.find(". *0(")>0 and last.find(", -0(")>0:
                        content = content[:-1]
                        if prelast!='...\n':
                            content.append('...\n')

                with codecs.open(LOG_FILE,'w','utf-8') as f:
                    f.write(''.join(content))
                    nowstr = time.strftime("%d.%m %H:%M", time.localtime() )
                    f.write( "%s %s: %s\n" % (nowstr,str_decode(load[2]),logmsg) )

                if  CONFIG.get('MACHINE',False):
                    LOG_TXT_FILE = "./LOG/store-msg-%s.log"%USER_LOGIN
                    with codecs.open(LOG_TXT_FILE,'a','utf-8') as f:
                        f.write('\n'.join(to_remember+['']))
                DBG.info( logmsg )
            except Exception as e:
                print e

        # 8. Remember new borders

        DBG.trace( "Remember last message" )

        DBG.trace("stopid: %s->%s; lastdelid: %s->%s", [was_stop, stop_id[MAIN_PROFILE], was_last, lastdel_id[MAIN_PROFILE]])

        FILE_MAIN_BAK = FILE_MAIN + '.bak'
        try:
            if os.path.exists(FILE_MAIN_BAK):
                os.unlink(FILE_MAIN_BAK)
                DBG.trace("unlink%s",[FILE_MAIN_BAK])
            if os.path.exists(FILE_MAIN):
                os.rename(FILE_MAIN,FILE_MAIN_BAK)
                DBG.trace("rename %s->%s",[FILE_MAIN,FILE_MAIN_BAK])

            vk_utils.lazy_profile_batch += map( lambda k: util.make_int(k.split('_')[1]), stop_id.iterkeys() )

            with codecs.open(FILE_MAIN,'w','utf-8') as f:
            #with open(FILE_MAIN,"w") as f:
                for [id,stop] in stop_id.iteritems():
                    f.write( "%s=%s,%s,%s,%s\n" % ( id, stop, lastdel_id.get(id,0), last_times.get(id,0), str_decode(make_profiletext(id.split('_')[1]))) )
            with codecs.open(FILE_MAIN,'r','utf-8') as f:
                DBG.trace(u"Writed:\n%s", [f.read()])
        except Exception as e:
            DBG.TODO( "ERR: %s" %str(e) )
            # rollback if anything goes wrong
            if os.path.exists(FILE_MAIN_BAK):
                if os.path.exists(FILE_MAIN):
                    os.unlink(FILE_MAIN)
                    DBG.trace("unlink %s",[FILE_MAIN])
                os.rename(FILE_MAIN_BAK,FILE_MAIN)
                DBG.trace("rename %s->%s",[FILE_MAIN_BAK,FILE_MAIN])


        # 9. Save MP3 and video LIST
        save_mp3_video()
        try:
            downloadVideo( FILE_VIDEO, start_video_idx )
        except OkExit:
            pass
        start_video_idx = len_videolist
