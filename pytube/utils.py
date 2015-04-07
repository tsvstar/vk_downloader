#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re

from os import path
from sys import stdout
from time import clock

class BaseYoutubeError(Exception):
    pass
class FileExistsError(BaseYoutubeError):
    pass
class MultipleObjectsReturned(BaseYoutubeError):
    pass
class YouTubeError(BaseYoutubeError):
    pass
class CipherError(BaseYoutubeError):
    pass


##import argparse
##class FullPaths(argparse.Action):
##    """Expand user- and relative-paths"""
##    def __call__(self, parser, namespace, values, option_string=None):
##        setattr(namespace, self.dest, path.abspath(path.expanduser(values)))


def safe_filename(text, max_length=200):
    """Sanitizes filenames for many operating systems.

    :params text: The unsanitized pending filename.
    """
    # Quickly truncates long filenames.
    truncate = lambda text: text[:max_length].rsplit(' ', 0)[0]

    # Tidy up ugly formatted filenames.
    text = text.replace('_', ' ')
    text = text.replace(':', ' -')

    # NTFS forbids filenames containing characters in range 0-31 (0x00-0x1F)
    ntfs = [chr(i) for i in range(0, 31)]

    # Removing these SHOULD make most filename safe for a wide range of
    # operating systems.
    paranoid = ['\"', '\#', '\$', '\%', '\'', '\*', '\,', '\.', '\/', '\:',
                '\;', '\<', '\>', '\?', '\\', '\^', '\|', '\~', '\\\\']

    blacklist = re.compile('|'.join(ntfs + paranoid), re.UNICODE)
    filename = blacklist.sub('', text)
    return truncate(filename)


def sizeof(bytes):
    """Takes the size of file or folder in bytes and returns size formatted in
    KB, MB, GB, TB or PB.

    :params bytes: size of the file in bytes
    """
    alternative = [
        (1024 ** 5, ' PB'),
        (1024 ** 4, ' TB'),
        (1024 ** 3, ' GB'),
        (1024 ** 2, ' MB'),
        (1024 ** 1, ' KB'),
        (1024 ** 0, (' byte', ' bytes')),
    ]

    for factor, suffix in alternative:
        if bytes >= factor:
            break
    amount = int(bytes / factor)
    if isinstance(suffix, tuple):
        singular, multiple = suffix
        if amount == 1:
            suffix = singular
        else:
            suffix = multiple
    return "%s%s" % (str(amount), suffix)


def print_status(progress, file_size, start):
    """
    This function - when passed as `on_progress` to `Video.download` - prints
    out the current download progress.

    :params progress: The lenght of the currently downloaded bytes.
    :params file_size: The total size of the video.
    :params start: time when started
    """

    percentDone = int(progress) * 100. / file_size
    done = int(50 * progress / int(file_size))
    dt = (clock() - start)
    if dt > 0:
        stdout.write("\r  [%s%s][%3.2f%%] %s at %s/s\r " %
                    ('=' * done, ' ' * (50 - done), percentDone, sizeof(file_size),
                        sizeof(progress // dt)))
    stdout.flush()


"""============ REPLACE URLLIB -- because 'latin1' is unknown ================"""


"""-------------------"""
import sys, traceback
class ExtractorError(Exception):
    """Error during info extraction."""

    def __init__(self, msg, tb=None, expected=False, cause=None, video_id=None):
        """ tb, if given, is the original traceback (so that it can be printed out).
        If expected is set, this is a normal error message and most likely not a bug in youtube-dl.
        """

        ##if sys.exc_info()[0] in (compat_urllib_error.URLError, socket.timeout, UnavailableVideoError):
        ###    expected = True
        if video_id is not None:
            msg = video_id + ': ' + msg
        if cause:
            msg += ' (caused by %r)' % cause
        if not expected:
            ##if ytdl_is_updateable():
            ##    update_cmd = 'type  youtube-dl -U  to update'
            ##else:
            ##    update_cmd = 'see  https://yt-dl.org/update  on how to update'
            msg += '; please report this issue on https://yt-dl.org/bug .'
            msg += ' Make sure you are using the latest version; %s.' % update_cmd
            msg += ' Be sure to call youtube-dl with the --verbose flag and include its complete output.'
        super(ExtractorError, self).__init__(msg)

        self.traceback = tb
        self.exc_info = sys.exc_info()  # preserve original exception
        self.cause = cause
        self.video_id = video_id

    def format_traceback(self):
        if self.traceback is None:
            return None
        return ''.join(traceback.format_tb(self.traceback))
