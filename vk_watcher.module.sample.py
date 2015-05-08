"""
All files in .vk_watcher-LOGIN are python modules.
It could ar could not contain "callback" functions. If function is absent, default one for given kind of file is used.
Allow to make any kind of specific processing

They are called as in following pseudoCode:
    FIRST PASS
    for module in list:
        if module.Prepare( module, True ):
            module.doAction( module, True )
            postponed.append(module)
    for module in postponed:
        module.PostProcess( module, True )


    SECOND PASS

    init_module_variables
    if module.Prepare( module, False ):
        msg = module.DoAction( module, False )
        if msg is not None:
            moreNotifyFlag = module.Notify( module, msg )
            if moreNotifyFlag:
                default.Notify( module, msg )
        module.PostProcess( module, False )
    if module.errorMessage is not None:
        raise Error(module.errorMessage)

IMPORTANT: To store any module-local changes you have to use "module.var = value" syntax

To make more convenient and short following modules are already enforcedly imported to the module before run sequence:
    import vk_utils, tsv_utils as util, config
    from vk_watcher import XXX
Also following global variables are accessible:
    vk_api, me
    vk_api1, me1, vk_api2, me2

    'now', 'me1', 'me2', 'flags', 'USER_LOGIN', 'COMMAND_USER',
     'DIR_MAIN', 'DIR_LOG','DIR_TMP'

To more communitcation between module and watcher following variables exists in the module:
    errorMessage - set it to different than None value if any error happens during processing
    tmpFileName  - pre-initialized name of file for "module-local persistent storage"
    cmd      - CMD() object
                    ##pre-initialized by list of command [ command, who, state, extra]
    options      - replacement for default DOWNLOAD_OPT from config
    ##isDryRun     - is False if this first pass and watcher collect sequence of all required queries



Files should follow patterns "STATE_COMMAND[VKAPI]_WHO[_EXTRA]".
    STATE = on|off
    COMMAND = watch|autoclean|userdef + num of vk_api
    WHO = id of group or user
    EXTRA = optional value to extra specific thing
Examples:
    off_autoclean1_322   - periodic clean chat with the user 322
    on_watch2_-322223    - watch of changes for the group -322223 using secondary login
    on_userdef2_3222_schedule    - custom periodic function which do something by schedule as in its code
    on_userdef_1_ok     - odnoklassniki watch module (_1 is just because requirement)
"""



#errorMessage = None
#tmpFileName = './.vk_watcher-LOGIN/tmp/.COMMAND_WHO_EXTRA'
#command = []

import vk_utils, tsv_utils as util, config

def Prepare( module, isDryRun ):
    # a) do any prepare values (like join)
    # b) change schedule - execute not each time
    return True     # True - proceed, False - skip

def DoAction( module, isDryRun ):
    # main action
    return None     # None if no Message, 'msg' - to make message


def PostProcess( module, isDryRun ):
    # do any action which should be done after action (like leave)
    pass

def Notify( module, message ):
    return False        # True - if ask to make common notification too, False - use only this command

