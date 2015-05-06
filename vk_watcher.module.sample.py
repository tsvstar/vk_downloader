"""
All files in .vk_watcher-LOGIN are python modules.
It could ar could not contain "callback" functions. If function is absent, default one for given kind of file is used.
Allow to make any kind of specific processing

They are called as in following pseudoCode:
    init_module_variables
    if module.Prepare( module, module.command ):
        msg = module.DoAction( module, module.command )
        if msg is not None:
            moreNotifyFlag = module.Notify( module, module.command, msg )
            if moreNotifyFlag:
                default.Notify( module, module.command, msg )
        module.PostProcess( module, module.command )
    if module.errorMessage is not None:
        raise Error(module.errorMessage)

IMPORTANT: To store any module-local changes you have to use "module.var = value" syntax

To make more convenient and short following modules are already enforcedly imported to the module before run sequence:
    import vk_utils, tsv_utils as util, config
    from vk_watcher import XXX
Also following global variables are accessible:
    vk_api, me, vk_api2, me2

To more communitcation between module and watcher following variables exists in the module:
    errorMessage - set it to different than None value if any error happens during processing
    tmpFileName  - pre-initialized name of file for "module-local persistent storage"
    command      - pre-initialized by list of command [ command, who, state, extra]
    options      - replacement for default DOWNLOAD_OPT from config

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

def Prepare( module, command ):
    # a) do any prepare values (like join)
    # b) change schedule - execute not each time
    return True     # True - proceed, False - skip

def DoAction( module, command ):
    # main action
    return None     # None if no Message, 'msg' - to make message


def PostProcess( module, command ):
    # do any action which should be done after action (like leave)
    pass

def Notify( module, command, message ):
    return False        # True - if ask to make common notification too, False - use only this command

