# -*- coding: utf-8 -*-
import base64
import re
import urllib.parse

from resources.lib.ui import client, control, utils


class BrowserBase(object):
    _BASE_URL = None

    @staticmethod
    def handle_paging(hasnextpage, base_url, page):
        if not hasnextpage or not control.is_addon_visible() and control.getBool('widget.hide.nextpage'):
            return []

        next_page = page + 1
        name = "Next Page (%d)" % next_page
        next_url = re.sub(r'page=%d', f'page={next_page}', base_url)
        url_path, sep, query = next_url.partition('?')

        try:
            from resources.lib import Main
            plugin_path = getattr(Main, 'plugin_url', '')
            if plugin_path and plugin_path.startswith(url_path):
                url_path = plugin_path
        except Exception:
            pass

        next_url = url_path + (sep + query if query else '')
        return [utils.allocate_item(name, next_url, True, False, [], 'next.png', {'plot': name}, 'next.png')]

    @staticmethod
    def open_completed():
        import json
        try:
            with open(control.completed_json) as file:
                completed = json.load(file)
        except FileNotFoundError:
            completed = {}
        return completed

    @staticmethod
    def duration_to_seconds(duration_str):
        # Regular expressions to match hours, minutes, and seconds
        hours_pattern = re.compile(r'(\d+)\s*hr')
        minutes_pattern = re.compile(r'(\d+)\s*min')
        seconds_pattern = re.compile(r'(\d+)\s*sec')

        # Extract hours, minutes, and seconds
        hours_match = hours_pattern.search(duration_str)
        minutes_match = minutes_pattern.search(duration_str)
        seconds_match = seconds_pattern.search(duration_str)

        # Convert to integers, default to 0 if not found
        hours = int(hours_match.group(1)) if hours_match else 0
        minutes = int(minutes_match.group(1)) if minutes_match else 0
        seconds = int(seconds_match.group(1)) if seconds_match else 0

        # Calculate total duration in seconds
        total_seconds = hours * 3600 + minutes * 60 + seconds

        return total_seconds

    @staticmethod
    def _clean_title(text):
        return text.replace(u'×', ' x ')

    @staticmethod
    def clean_embed_title(text):
        return re.sub(r'\W', '', text).lower()

    def _to_url(self, url=''):
        assert self._BASE_URL is not None, "Must be set on inherentance"

        if url.startswith("/"):
            url = url[1:]
        return "%s/%s" % (self._BASE_URL, url)

    @staticmethod
    def _send_request(url, data=None, headers=None):
        if data:
            response = client.post(url, data=data, headers=headers)
        else:
            response = client.get(url, headers=headers)
        return response.text if response else None

    def _post_request(self, url, data={}, headers=None):
        return self._send_request(url, data, headers)

    def _get_request(self, url, data=None, headers=None):
        if data:
            url = "%s?%s" % (url, urllib.parse.urlencode(data))
        return self._send_request(url, data=None, headers=headers)

    @staticmethod
    def _get_redirect_url(url, headers=None):
        if headers is None:
            headers = {}
        response = client.get(url, redirect=False, headers=headers)
        if response:
            return response.headers.get('Location')
        return ''

    @staticmethod
    def _bencode(text):
        return (base64.b64encode(control.bin(text))).decode('latin-1')

    @staticmethod
    def _bdecode(text, binary=False):
        dec = base64.b64decode(text)
        return dec if binary else dec.decode('latin-1')

    @staticmethod
    def _get_origin(url):
        purl = urllib.parse.urlparse(url)
        return '{0}://{1}'.format(purl.scheme, purl.netloc)

    @staticmethod
    def _get_size(size=0):
        power = 1024.0
        n = 0
        power_labels = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB'}
        while size > power:
            size /= power
            n += 1
        return '{0:.2f} {1}'.format(size, power_labels[n])

    @staticmethod
    def _sphinx_clean(text):
        text = text.replace('+', r'\+')
        text = text.replace('-', r'\-')
        text = text.replace('!', r'\!')
        text = text.replace('^', r'\^')
        text = text.replace('"', r'\"')
        text = text.replace('~', r'\~')
        text = text.replace('*', r'\*')
        text = text.replace('?', r'\?')
        text = text.replace(':', r'\:')
        return text

    @staticmethod
    def embeds():
        return control.getStringList('embed.config')

    # control.setStringList('embed.config', ['bunny', 'doodstream', 'filelions', 'filemoon', 'hd-2',
    #                       'iga', 'kwik', 'megaf', 'moonf', 'mp4upload', 'mp4u',
    #                       'mycloud', 'noads', 'noadsalt', 'swish', 'streamtape',
    #                       'streamwish', 'vidcdn', 'vidhide', 'vidplay', 'vidstream',
    #                       'yourupload', 'zto'])
