__title__ = 'pytube'
__version__ = '0.2.0'
__author__ = 'Nick Ficano'
__license__ = 'MIT License'
__copyright__ = 'Copyright 2013 Nick Ficano'

from api import YouTube, Vimeo
YouTube
Vimeo

"""
==============MY FUNCTIONS =======================
"""
#
def getVideo( url, maxr=480 ):
    if url.find('vimeo.com/')>=0:
        yt = Vimeo()
    elif ( url.find('youtu.be/')>=0 or url.find('youtube.com/')>=0 ):
        yt = YouTube()
    else:
        raw_input('')
        print "Unknown video provider: %s" % url
        return None

    yt.url = url    #   set and load info

    lst = {}
    for v in yt.videos:
        if v.resolution[-1]=='p':
            lst.setdefault(int(v.resolution[:-1]), {})[v.extension]=v

    lst_res = filter(lambda v: v<=int(maxr),  list(lst.keys()) )
    if len(lst_res)==0:
        return None
    res=max(lst_res)
    fmts_ = [ 'mp4', 'webm', 'flv', '3gp' ]
    for f in fmts_:
        if f in lst[res]:
            return lst[res][f]
    return None

import sys

"""================================="""
blink=-1
blink_list = [ '|', '/', '-', '\\', '|', '/', '-', '\\' ]
def print_blink():
    global blink
    blink = (blink+1)%len(blink_list)
    sys.stdout.write( blink_list[blink] + chr(8))


"""================================="""
youtube_progress = 0
percent_progress = 5            # how many perc
def showProgress( cur_, all_, starttime ):
    global youtube_progress
    cur_ = int( (100/float(percent_progress)) * float(cur_)/all_)
    print_blink()
    if youtube_progress!=cur_:
        import sys
        sys.stdout.write('.')
    youtube_progress = cur_
    return None
