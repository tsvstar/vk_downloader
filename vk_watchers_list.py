#coding is utf-8

"""
# HERE IS THE PYTHON CODE WHICH DESCRIBE ALL REQUIRED WATCHERS
Format:
   Watch( rate, userid_or_groupid, internal_name, [item1, item2, ...], [notify1,notify2] )

   rate			- minimal period (in minutes) before next check
   userid_or_groupid	- id of user (positive) or group (negative) to watch
   internal_name	- name of watcher (it is used in notification as context descriptor + in state file name)
   [item1,..]		- list of things to watch. each item have format "name:option1,option2,.."
				allowed names: wall, video, photo, mp3, status, online, message
				possible options:
					wall:likes,comments,reposts,*   - track wall changes + changes of likes/... of posts
					wall:new_only_as_msg		- notify about new messages on wall and send its text
					video:likes,comments,views,*
					photo:comments,*
   [notify1,..]		- list of notifier which should process this. each notifier have format "type:queue"
				possible notifier types: vk, jeapie, pushbullet
				each "queue" is collector which accumulate notification and into one message
				(special case: queue '!' means - do not collect, each notification is separate message)
"""


#Add your own watchers here. Below are just samples

hour_now = time.localtime().tm_hour
silent = (hour_now>=23 or hour_now<7)


# Track "live vk" community (not more frequent than once per 9 minutes)
Watch( 9, -2158488,  "live_vk",     [ "wall:*", "video:*", "photo:*", "mp3"], ["vk", 'bullet'] ) 
# Track "Pavel Durov" page  (not more frequent than once per 5 minutes)
Watch( 5, 1,  "durov",     [ "wall:*", "video:*", "photo:*", "mp3"], ["vk", 'bullet'] ) 
# Track "Pavel Durov" status (incoming messages, change offline->online, status text)
Watch( 1, 1,  "durov_msg",        [ "message", "online",'status' ],   [] if silent else ['bullet:!'] )

# Continuosly store message history with Durov
Run( 1, "msg.durov", ['message', '', '1', '0','--DOWNLOAD_VIDEO=False','--DOWNLOAD_MP3=False'], ['vk:msg.n'] )

# Continuosly backup Durov wall
Run( 3, "backup", ['wall', '', "1", '0', '--LOAD_LIKES=False', '--SEPARATE_TEXT=None',
                    '--DAYSBEFORE=7', '--DOWNLOAD_MP3=False', '--DOWNLOAD_VIDEO=False'], [] )
