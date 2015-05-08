import re, os
import tsv_utils as util
from tsv_utils import DBG


"""
    Stub for userdef. So it do nothing.
    The only thing which more important it make is default notification sequence
"""
class DefaultWatcher( object ):
    @staticmethod
    def CheckWatcherStatus( module, isDryRun = False ):
        # intialize option

        # return True if watcher should be executed (for most modules that means status=='on')
        return (module.cmd.get('status') == 'on' )

    @staticmethod
    def Prepare( module, isDryRun = False ):
        # a) do any prepare values (like join)
        # b) change schedule - execute not each time
        return True     # True - proceed, False - skip

    @staticmethod
    def DoAction( module, isDryRun = False ):
        # main action
        return None     # None if no Message, 'msg' - to make message

    @staticmethod
    def PostProcess( module, isDryRun = False ):
        # do any action which should be done after action (like leave)
        pass

    @staticmethod
    def Notify( module, message ):
        module.SendMsg( module.vk_api, message, prefix='' )
        DBG.TODO('+ scan notifiers here')
        return False        # True - if ask to make common notification too, False - use only this command


"""
    Default sequence for 'autoclean' command
"""
class AutoCleanWatcher( DefaultWatcher ):
    re_foundid = re.compile("/([\?><])([0-9]+)")

    flagSkipNotifyIfLastOutgoing = True

    @staticmethod
    def CheckWatcherStatus( module, isDryRun ):
        # intialize option
        if not hasattr(module,'options'):
            module.options = module.config.CONFIG.get( 'AUTOCLEAN_OPT', ["--DEL_ENFORCED=True", "--KEEP_LAST_SECONDS=60"] )
        # autoclean modules are always executed
        return True

    @staticmethod
    def DoAction( module, isDryRun = False ):
        tag = "msg:%s" % module.cmd.userid
        if tag in module.flags:
            return None

        state = module.cmd.get('state')
        #module.foundIds = {}                    # output
        module.directions = set()               # set of directions of found messages (last_stored and last_deleted)

        # 1st pass - actually do everything
        if isDryRun:
            # execute downloading on first pass
            stdout, stderr = module.ExecuteDownloadMSG( module.cmd.userid, 1 if state=='on' else 0, module.options )

            module.Message, module.errorMessage = stdout, stderr

            # do not notify if state=='off' (store messages but not delete them)
            if state!='on':
                module.Message = None
            # do not notify if no essential info happens
            elif stdout.find('. *0')>=0 and stdout.find('), -0(')>=0:
                module.Message = None

            # notify anyway if that is error
            if stderr:
                # send previous message if exists
                if module.Notify( module, None ):
                    module.default_module.Notify( module, None )

                # send current error
                if module.Notify( module, stdout ):
                    module.default_module.Notify( module, stdout )
                return None

        # On 1st pass, mark that we want to find out direction of messages
        # On 2nd pass, use that result
        if module.Message and flagSkipNotifyIfLastOutgoing:
            matches = re_foundid.findall(module.Message)
            module.directions = set( map( lambda m: m.group(1), matches ) )
            if '>' not in module.directions:
                ids = map( lambda m: m.group(2), matches )
                foundIds = module.vk_api.messages.getById( message_ids=ids )
                if not isDryRun:
                    for i in foundIds[u'items']:
                        module.directions.add( '>' if int(i[u'from_id'])==module.me else '<' )

        return module.Message

    @staticmethod
    def Notify( module, message ):

        # if any of messages is outgoing then no need to notify at all (this and previous)
        if flagSkipNotifyIfLastOutgoing:
            if '>' in module.directions:
                if os.path.isfile(module.tmpFileName):
                    os.unlink(module.tmpFileName)
                return False


        # Twice rarely output

        if not message:
            # 1) no current message - only send posponed
            if os.path.isfile(module.tmpFileName):
                with open(module.tmpFileName,'rb') as f:
                    message = util.str_decode( f.read(), 'utf-8')
                if message:
                    module.SendMsg( module.vk_api, message, ( u'vk: %s/'%module.cmd.userid), _replaceAlias = True  )
                os.unlink(module.tmpFileName)
        else:
            # 2) message given and posponed existed - means we need to send current one
            if os.path.isfile(module.tmpFileName):
                module.SendMsg( module.vk_api, message, ( u'vk: %s/'%module.cmd.userid), _replaceAlias = True  )
                os.unlink(module.tmpFileName)
            else:
            # 3) message given but no posponed existed - postpone current
                with open(module.tmpFileName,'wb') as f:
                    f.write( util.str_encode( message, 'utf-8') )

        return False        # True - if ask to make common notification too, False - use only this command


"""
    Default sequence for 'watch' command
"""
class GroupWatcher( DefaultWatcher ):

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

    @staticmethod
    def DoAction( module, isDryRun = False ):
        stored = []
        if not dryRun:
          try:
             with open(module.tmpFileName,'r') as f:
                stored = map(lambda s: s.strip(), f.readlines() )
          except:
             pass
        stored =  (stored + ['','','',''])[:4]
        empty_file = filter(lambda v: v, stored )      # true if any value were initialized

        wall1 = getHash( stored[0], vk_api.wall.get,  owner_id=MAIN_PROFILE, offset=0, count=1, filter='all', extended=0  )
        aud1  = getHash( stored[1], vk_api.audio.get, owner_id=MAIN_PROFILE, offset=0, count=1 )
        vid1  = getHash( stored[2], vk_api.video.get, owner_id=MAIN_PROFILE, offset=0, count=1  )

        try:
            res =  vk_api.photos.getAlbums( owner_id=MAIN_PROFILE )[u'items']
            photo1 = '+'.join( map(lambda h: str(h[u'size']), res ) )
        except Exception as e:
            print e
            photo1 = stored[3]

        if isDryRun:
            return

        cur_state = [ wall1, aud1, vid1, photo1 ]

        with open(module.tmpFileName,'w') as f:
            f.write( '\n'.join(cur_state) )

        if cur_state == stored:
            print "Nothing changed for %s" % MAIN_PROFILE
            return None

        msg = []
        if stored[0]!=cur_state[0]:  msg.append("WALL was changed (%s -> %s)" % (stored[0],cur_state[0]))
        if stored[1]!=cur_state[1]:  msg.append("AUDIOS was changed (%s -> %s)" % (stored[1],cur_state[1]))
        if stored[2]!=cur_state[2]:  msg.append("VIDEOS was changed (%s -> %s)" % (stored[2],cur_state[2]))
        if stored[3]!=cur_state[3]:  msg.append("PHOTOS was changed (%s -> %s)" % (stored[3],cur_state[3]))

        lt = time.localtime()
        msg = ('%s: '%MAIN_PROFILE) + '\n'.join(msg)
        msg += " at %04d-%02d-%02d %02d:%02d"  % (lt.tm_year, lt.tm_mon, lt.tm_mday, lt.tm_hour, lt.tm_min)

        return u'groupvk='+msg
