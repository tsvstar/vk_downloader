import tsv_utils as util


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
        util.TODO('SHOULD BE DEFAULT NOTIFIER HERE + scan notifiers here')
        return False        # True - if ask to make common notification too, False - use only this command


"""
    Default sequence for 'autoclean' command
"""
class AutoCleanWatcher( DefaultWatcher ):
    @staticmethod
    def CheckWatcherStatus( module, isDryRun ):
        # intialize option
        if not hasattr(module,'options'):
            module.options = module.config.CONFIG.get('AUTOCLEAN_OPT',[])
        # autoclean modules are always executed
        return True

    @staticmethod
    def DoAction( module, isDryRun = False ):
        util.TODO('')
        return None     # None if no Message, 'msg' - to make message

    @staticmethod
    def Notify( module, message ):
        util.TODO('SHOULD BE EXTENDED')
        return False        # True - if ask to make common notification too, False - use only this command


"""
    Default sequence for 'watch' command
"""
class GroupWatcher( DefaultWatcher ):
    @staticmethod
    def DoAction( module, isDryRun = False ):
        util.TODO('')
        return None     # None if no Message, 'msg' - to make message

