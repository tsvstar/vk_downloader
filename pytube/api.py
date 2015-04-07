#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from models import Video
from utils import safe_filename
from utils import MultipleObjectsReturned, YouTubeError, CipherError
try:
    from urllib2 import urlopen
    from urlparse import urlparse, parse_qs, unquote
except ImportError:
    from urllib.parse import urlparse, parse_qs, unquote
    from urllib.request import urlopen


import re
import json

YT_BASE_URL = 'http://www.youtube.com/get_video_info'

# YouTube quality and codecs id map.
# source: http://en.wikipedia.org/wiki/YouTube#Quality_and_codecs
YT_ENCODING = {
    # Flash Video
    5: ["flv", "240p", "Sorenson H.263", "N/A", "0.25", "MP3", "64"],
    6: ["flv", "270p", "Sorenson H.263", "N/A", "0.8", "MP3", "64"],
    34: ["flv", "360p", "H.264", "Main", "0.5", "AAC", "128"],
    35: ["flv", "480p", "H.264", "Main", "0.8-1", "AAC", "128"],

    # 3GP
    36: ["3gp", "240p", "MPEG-4 Visual", "Simple", "0.17", "AAC", "38"],
    13: ["3gp", "NA",   "MPEG-4 Visual", "N/A", "0.5", "AAC", "N/A"],
    17: ["3gp", "144p", "MPEG-4 Visual", "Simple", "0.05", "AAC", "24"],

    # MPEG-4
    18: ["mp4", "360p", "H.264", "Baseline", "0.5", "AAC", "96"],
    22: ["mp4", "720p", "H.264", "High", "2-2.9", "AAC", "192"],
    37: ["mp4", "1080p", "H.264", "High", "3-4.3", "AAC", "192"],
    38: ["mp4", "3072p", "H.264", "High", "3.5-5", "AAC", "192"],
    82: ["mp4", "360p", "H.264", "3D", "0.5", "AAC", "96"],
    83: ["mp4", "240p", "H.264", "3D", "0.5", "AAC", "96"],
    84: ["mp4", "720p", "H.264", "3D", "2-2.9", "AAC", "152"],
    85: ["mp4", "1080p", "H.264", "3D", "2-2.9", "AAC", "152"],

    # WebM
    43: ["webm", "360p", "VP8", "N/A", "0.5", "Vorbis", "128"],
    44: ["webm", "480p", "VP8", "N/A", "1", "Vorbis", "128"],
    45: ["webm", "720p", "VP8", "N/A", "2", "Vorbis", "192"],
    46: ["webm", "1080p", "VP8", "N/A", "N/A", "Vorbis", "192"],
    100: ["webm", "360p", "VP8", "3D", "N/A", "Vorbis", "128"],
    101: ["webm", "360p", "VP8", "3D", "N/A", "Vorbis", "192"],
    102: ["webm", "720p", "VP8", "3D", "N/A", "Vorbis", "192"]
}

# The keys corresponding to the quality/codec map above.
YT_ENCODING_KEYS = (
    'extension',
    'resolution',
    'video_codec',
    'profile',
    'video_bitrate',
    'audio_codec',
    'audio_bitrate'
)


class BaseProvider(object):
    # TODO: just cause you CAN do this, doesn't mean you should. `hasattr` is
    # much cleaner.
    _filename = None
    _fmt_values = []
    _video_url = None
    _js_code = False
    _precompiled = False
    title = None
    videos = []
    # fmt was an undocumented URL parameter that allowed selecting
    # YouTube quality mode without using player user interface.

    @property
    def url(self):
        return self._video_url

    @url.setter
    def url(self, url):
        self._video_url = url
        self._filename = None
        self._get_video_info()

    @property
    def filename(self):
        if not self._filename:
            self._filename = safe_filename(self.title)
        return self._filename

    @filename.setter
    def filename(self, filename):
        self._filename = filename
        if self.videos:
            for video in self.videos:
                video.filename = filename

    def get(self, extension=None, resolution=None, profile="High"):
        """Return a single video given an extention and resolution.

        :params extention: The desired file extention (e.g.: mp4).
        :params resolution: The desired video broadcasting standard.
        :params profile: The desired quality profile.
        """
        result = []
        for v in self.videos:
            if extension and v.extension != extension:
                continue
            elif resolution and v.resolution != resolution:
                continue
            elif profile and v.profile != profile:
                continue
            else:
                result.append(v)
        if not len(result):
            return
        elif len(result) is 1:
            return result[0]
        else:
            raise MultipleObjectsReturned(
                "get() returned more than one object")

    def filter(self, extension=None, resolution=None):
        """Return a filtered list of videos given an extention and resolution
        criteria.

        :params extention: The desired file extention (e.g.: mp4).
        :params resolution: The desired video broadcasting standard.
        """
        results = []
        for v in self.videos:
            if extension and v.extension != extension:
                continue
            elif resolution and v.resolution != resolution:
                continue
            else:
                results.append(v)
        return results

"""
================================================
            YOUTUBE SERVICE
================================================
"""

class YouTube(BaseProvider):
    @property
    def video_id(self):
        """Gets the video ID extracted from the URL.
        """
        parts = urlparse(self._video_url)
        qs = getattr(parts, 'query', None)
        if qs:
            video_id = parse_qs(qs).get('v', None)
            if video_id:
                return video_id.pop()


    def _fetch(self, path, data):
        """Given a path, traverse the response for the desired data. (A
        modified ver. of my dictionary traverse method:

        https://gist.github.com/2009119)

        :params path: A tuple representing a path to a node within a tree.
        :params data: The data containing the tree.
        """
        elem = path[0]
        # Get first element in tuple, and check if it contains a list.
        if type(data) is list:
            # Pop it, and let's continue..
            return self._fetch(path, data.pop())
        # Parse the url encoded data
        data = parse_qs(data)
        # Get the element in our path
        data = data.get(elem, None)
        # Offset the tuple by 1.
        path = path[1::1]
        # Check if the path has reached the end OR the element return
        # nothing.
        if len(path) is 0 or data is None:
            if type(data) is list and len(data) is 1:
                data = data.pop()
            return data
        else:
            # Nope, let's keep diggin'
            return self._fetch(path, data)

    def _parse_stream_map(self, text):
        """Python's `parse_qs` can't properly decode the stream map
        containing video data so we use this instead.
        """
        videoinfo = {
            "itag": [],
            "url": [],
            "quality": [],
            "fallback_host": [],
            "s": [],
            "type": []
        }

        # Split individual videos
        videos = text.split(",")
        # Unquote the characters and split to parameters
        videos = [video.split("&") for video in videos]

        for video in videos:
            for kv in video:
                key, value = kv.split("=")
                value = value.encode('ascii')           #@tsv hack - unquote fail to parse unicode
                videoinfo.get(key, []).append(unquote(value))

        return videoinfo

    def _get_video_info(self):
        """This is responsable for executing the request, extracting the
        necessary details, and populating the different video resolutions and
        formats into a list.
        """
        # TODO: split up into smaller functions. Cyclomatic complexity => 15
        self.title = None
        self.videos = []

        url = self.url.replace('feature=player_embedded&','')
        response = urlopen(url)

        if response:
            content = response.read().decode("utf-8")
            try:
                player_conf = content[18 + content.find("ytplayer.config = "):]
                bracket_count = 0
                for i, char in enumerate(player_conf):
                    if char == "{":
                        bracket_count += 1
                    elif char == "}":
                        bracket_count -= 1
                        if bracket_count == 0:
                            break
                else:
                    raise YouTubeError("Cannot get JSON from HTML")

                index = i + 1
                data = json.loads(player_conf[:index])
            except Exception as e:
                raise YouTubeError("Cannot decode JSON: {0}".format(e))

            is_vevo = False
            if data['args'].get('ptk', '') in ['vevo', 'dashmpd']:
                # Vevo videos with encrypted signatures
                is_vevo = True

            stream_map = self._parse_stream_map(
                data["args"]["url_encoded_fmt_stream_map"])

            self.title = data["args"]["title"]
            js_url = "http:" + data["assets"]["js"]
            video_urls = stream_map["url"]

            for i, url in enumerate(video_urls):
                try:
                    fmt, fmt_data = self._extract_fmt(url)
                    ##print fmt_data
                except (TypeError, KeyError):
                    continue

                # If the signature must be ciphered...
                ###print "ptk=%s"%data['args'].get('ptk',''), is_vevo, (url.split('signature=')+[''])[1].split('&')[0]
                if "signature=" not in url:
                    if is_vevo:
                        has_decrypted_signature = False
                        try:
                            signature = self._decrypt_signature(
                                stream_map['s'][0])
                            url += '&signature=' + signature
                            has_decrypted_signature = True
                        except TypeError:
                            pass

                        if not has_decrypted_signature:
                            raise CipherError(
                                "Couldn't cipher the vevo signature. "
                                "Maybe YouTube has changed the cipher "
                                "algorithm.")

                    else:
                        signature = self._cipher2(stream_map["s"][i], js_url)
                        url = "%s&signature=%s" % (url, signature)

                self.videos.append(Video(url, self.filename, **fmt_data))
                self._fmt_values.append(fmt)
            self.videos.sort()

    @staticmethod
    def _decrypt_signature(s):
        """Comment me :)
        """
        def tu(a, b):
            c = a[0]
            a[0] = a[b % len(a)]
            a[b] = c
            return a

        def splice(a, b):
            return a[b:]

        a = list(s)
        a = tu(a[::-1], 26)
        a = tu(a[::-1], 28)
        a = tu(a, 38)
        a = splice(a[::-1], 3)
        return "".join(a)

    def _cipher(self, s, url):
        """
        (OBSOLETE DECHYPHERING FUNCTION - user _cipher2)
        Get the signature using the cipher implemented in the JavaScript code

        :params s: Signature
        :params url: url of JavaScript file
        """
        import tinyjs

        # Getting JS code (if hasn't downloaded yet)
        if not self._js_code:
            self._js_code = (urlopen(url).read().decode()
                             if not self._js_code else self._js_code)

        try:
            # Find first function
            regexp = r'function \w{2}\(\w{1}\)\{\w{1}=\w{1}\.split\(\"\"\)' \
                '\;(.*)\}'
            code = re.findall(regexp, self._js_code)[0]
            code = code[:code.index("}")]

            # pre-code
            signature = "a='" + s + "'"

            # Tiny JavaScript VM
            jsvm = tinyjs.JSVM()

            # Precompiling with the super JavaScript VM (if hasn't compiled yet)
            if not self._precompiled:
                self._precompiled = jsvm.compile(code)
            # Make first function + pre-code
            jsvm.setPreinterpreted(jsvm.compile(signature) + self._precompiled)

            # Executing the JS code
            return jsvm.run()["return"]

        except Exception as e:
            ##raise
            raise CipherError("Couldn't cipher the signature. Maybe YouTube "
                              "has changed the cipher algorithm(%s)" % e)

    def _re_search( self, pattern, s):
        """auxilary function - find first answer for pattern"""
        mobj = re.search( pattern, s)
        return next(g for g in mobj.groups() if g is not None)


    def _parse_sig_js(self, jscode):
        """auxilary function - prepare javascript decryption function"""
        import pytube.jsinterp
        # found required function from by pattern
        funcname = self._re_search(
            r'\.sig\|\|([a-zA-Z0-9$]+)\(', jscode )

        # prepare function body to run
        jsi = pytube.jsinterp.JSInterpreter(jscode)
        initial_function = jsi.extract_function(funcname)
        return lambda s: initial_function([s])

    def _cipher2(self, s, url):
        """(ACTUAL DECIPHERING FUNCTION)
            s - signature
            url - url of decryptor javascript
        """
        # load JS if needed
        if not self._js_code:
            self._js_code = (urlopen(url).read().decode()
                             if not self._js_code else self._js_code)

        try:
            # get decryptor function
            dec_func = self._parse_sig_js(self._js_code)
            # run decryptor function
            return dec_func(s)
        except Exception as e:
            ##raise
            raise CipherError("Couldn't cipher the signature. Maybe YouTube "
                              "has changed the cipher algorithm(%s)" % e)


    def _extract_fmt(self, text):
        """YouTube does not pass you a completely valid URLencoded form, I
        suspect this is suppose to act as a deterrent.. Nothing some regulular
        expressions couldn't handle.

        :params text: The malformed data contained within each url node.
        """
        itag = re.findall('itag=(\d+)', text)
        if itag and len(itag) is 1:
            itag = int(itag[0])
            attr = YT_ENCODING.get(itag, None)
            if not attr:
                return itag, None
            return itag, dict(zip(YT_ENCODING_KEYS, attr))


"""
================================================
            VIMEO SERVICE
================================================
"""

VIMEO_ENCODING = {
    'mobile': ["mp4", "270p", "H.264", "Base", "0.3", "AAC", "112"],     # '480x270 H.264/AAC Stereo MP4',
    'sd': ["mp4", "360p", "H.264", "High", "0.7", "AAC", "112"],     # '640x360 H.264/AAC Stereo MP4',
    'hd': ["mp4", "720p", "H.264", "High", "1.5-1.6", "AAC", "160"],   #'1280x720 H.264/AAC Stereo MP4',
}


def _download(url):
        response = urlopen(url)
        if response:
            return response.read().decode("utf-8")
        return ''

class Vimeo(BaseProvider):
    def _get_video_info(self):
        """This is responsable for executing the request, extracting the
        necessary details, and populating the different video resolutions and
        formats into a list.
        """
        self.title = None
        self.videos = []

        html = _download(self.url)
        match = re.search('content="?(https?://player.vimeo.com/video/([0-9]+))">',html)
        if match:
            _id = match.group(1)
            self.title = "vimeo%s" % match.group(2)
        else:
            raise YouTubeError("Fail to parse vimeo page: %s"%self.url)

        match = re.search('<meta name="description" content="([^"]+)',html)
        if match:
            self.title = match.group(1)

        html = _download("%s/config"%_id)
        try:
            j = json.loads( html )
            files = j['request']['files'].get('h264',{})
            for t, fmap in files.items():
                fmt =  list( VIMEO_ENCODING['sd'] )
                if t in VIMEO_ENCODING:
                    fmt = VIMEO_ENCODING[t]
                fmt_data = dict(zip(YT_ENCODING_KEYS, fmt))
                if 'height' in fmap:
                    fmt_data['resolution'] = str(fmap['height']) + 'p'
                if 'bitrate' in fmap:
                    fmt_data['video_bitrate'] = "%0.1f" % (fmap['bitrate']/1000)

                self.videos.append( Video(fmap['url'], self.filename, **fmt_data) )
        except Exception as e:
            raise YouTubeError("Cannot decode JSON: {0}".format(e))

