import tsv_utils as util


"""
    Stub for userdef. So it do nothing.
    The only thing which more important it make is default notification sequence
"""
class DefaultWatcher( object ):
    @staticmethod
    def Prepare( module, isDryRun ):
        # a) do any prepare values (like join)
        # b) change schedule - execute not each time
        return True     # True - proceed, False - skip

    @staticmethod
    def DoAction( module, isDryRun ):
        # main action
        return None     # None if no Message, 'msg' - to make message

    @staticmethod
    def PostProcess( module, isDryRun ):
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
    def DoAction( module, isDryRun ):
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
    def DoAction( module, isDryRun ):
        util.TODO('')
        return None     # None if no Message, 'msg' - to make message

