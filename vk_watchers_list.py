#coding is utf-8

"""
# HERE IS THE PYTHON CODE WHICH DESCRIBE ALL REQUIRED WATCHERS
Format:
   vk1.Watch( rate, userid_or_groupid, internal_name, [item1, item2, ...], [notify1,notify2] )

   vk1                - check from primary login (vk2-secondary, and you need to add the line "API2=True" to config)
   rate               - minimal period (in minutes) before next check

   userid_or_groupid  - id of user (positive) or group (negative) to watch

   internal_name      - name of watcher (it is used in notification as context descriptor + in state file name)

   [item1,..]          - list of things to watch. each item have format "name:option1,option2,.."
        allowed names: wall, video, photo, mp3, status, online, message
        possible options:
            wall:likes,comments,reposts,*   - track wall changes + changes of likes/... of posts
                from=XX|YY                      -- track only post from that users/groups on this wall ("wall:from=1,-533")
                id                              -- do not show ever body of post in notification
                new_only_as_msg                 -- notify about new messages on wall and send its text
            video:likes,comments,views,*    - track video changes + changes of likes/... for them
                ,owneronly                       -- if defined then ignore likes/comments/view for not owned by user videos
            photo:comments,*                - track photo changes + changes of its comments (likes are not tracked)
            mp3                             - track audio changes. no options

            online:XXX                      - track online status
                                                -- if numeric value defined (ex: "online:5"), then ignore offline period
                                                  which are no longer than this term (5 minutes in this case)
                ,verbose                        -- notify about going offline too(and ignore numeric value)
            status                          - track status changes (do not notify audio->audio changes); no options
            message                         - track incoming unread messages(if other notify is turned off); no options

   [notify1,..]        - list of notifier which should process this. each notifier have format "type:queue"
                implemented notifier types: vk, jeapie, pushbullet
                each "queue" is collector which accumulate notification and into one message
                (special case: queue '!' means - do not collect, each notification is separate message)


Regular run main downloader (backup message/wall/...)
     vk1.Run( rate, internal_name, [cmdline], [notify1,..] )

            vk1/2 - same as for Watch
            rate  - same as for Watch
            internal_name  - same as for Watch
            cmdline  - separated by comma list of arguments to run downloader (see example below)
            notify   - target notify

"""


#Add your own watchers here. Below are just samples

hour_now = time.localtime().tm_hour
silent = (hour_now>=23 or hour_now<7)

global glob_jitter_hour
glob_jitter_hour = hour_now in range(1,6)           # on period 1-6a.m. VK like values could temporary be droped to zero for some minutes/hour. ignore that

# Track "live vk" community (not more frequent than once per 9 minutes)
vk1.Watch( 9, -2158488,  "live_vk",     [ "wall:*", "video:*", "photo:*", "mp3"], ["vk", 'bullet'] )
# Track "Pavel Durov" page  (not more frequent than once per 5 minutes)
vk1.Watch( 5, 1,  "durov",     [ "wall:*", "video:*", "photo:*", "mp3"], ["vk", 'bullet'] )
# Track "Pavel Durov" status (incoming messages, change offline->online, status text)
vk2.Watch( 1, 1,  "durov_msg",        [ "message", "online",'status' ],   [] if silent else ['bullet:!'] )

# Continuosly store message history with Durov
vk1.Run( 1, "msg.durov", ['message', '', '1', '0','--DOWNLOAD_VIDEO=False','--DOWNLOAD_MP3=False'], ['vk:msg.n'] )

# Continuosly backup Durov wall
vk1.Run( 3, "backup", ['wall', '', "1", '0', '--LOAD_LIKES=False', '--SEPARATE_TEXT=None',
                    '--DAYSBEFORE=7', '--DOWNLOAD_MP3=False', '--DOWNLOAD_VIDEO=False'], [] )
