import itertools
import json
import pickle
import re
import six

from functools import partial
from bs4 import BeautifulSoup, SoupStrainer
from resources.lib import debrid
from resources.lib.ui import control, database, source_utils
from resources.lib.ui.BrowserBase import BrowserBase
from six.moves import urllib_parse


class sources(BrowserBase):
    _BASE_URL = 'https://nyaa-si.translate.goog/?_x_tr_sl=es&_x_tr_tl=en&_x_tr_hl=en/' if control.getSetting('provider.nyaaalt') == 'true' else 'https://nyaa.si/'

    @staticmethod
    def _parse_nyaa_episode_view(res, episode):
        source = {
            'release_title': res['name'].encode('utf-8') if six.PY2 else res['name'],
            'hash': res['hash'],
            'type': 'torrent',
            'quality': source_utils.getQuality(res['name']),
            'debrid_provider': res['debrid_provider'],
            'provider': 'nyaa',
            'episode_re': episode,
            'size': res['size'],
            'info': source_utils.getInfo(res['name']),
            'lang': source_utils.getAudio_lang(res['name'])
        }

        return source

    @staticmethod
    def _parse_nyaa_cached_episode_view(res, episode):
        source = {
            'release_title': res['name'].encode('utf-8') if six.PY2 else res['name'],
            'hash': res['hash'],
            'type': 'torrent',
            'quality': source_utils.getQuality(res['name']),
            'debrid_provider': res['debrid_provider'],
            'provider': 'nyaa (Local Cache)',
            'episode_re': episode,
            'size': res['size'],
            'info': source_utils.getInfo(res['name']),
            'lang': source_utils.getAudio_lang(res['name'])
        }

        return source

    def _process_nyaa_episodes(self, url, episode, season=None):
        html = self._get_request(url)
        mlink = SoupStrainer('div', {'class': 'table-responsive'})
        soup = BeautifulSoup(html, "html.parser", parse_only=mlink)
        rex = r'(magnet:)+[^"]*'

        list_ = [
            {'magnet': i.find('a', {'href': re.compile(rex)}).get('href'),
             'name': i.find_all('a', {'class': None})[1].get('title'),
             'size': i.find_all('td', {'class': 'text-center'})[1].text.replace('i', ''),
             'downloads': int(i.find_all('td', {'class': 'text-center'})[-1].text)}
            for i in soup.select("tr.danger,tr.default,tr.success")
        ]

        regex = r'\ss(\d+)|season\s(\d+)|(\d+)+(?:st|[nr]d|th)\sseason'
        regex_ep = r'\de(\d+)\b|\se(\d+)\b|\s-\s(\d{1,3})\b'
        rex = re.compile(regex)
        rex_ep = re.compile(regex_ep)
        filtered_list = []

        for idx, torrent in enumerate(list_):
            torrent['hash'] = re.findall(r'btih:(.*?)(?:&|$)', torrent['magnet'])[0]
            if season:
                title = torrent['name'].lower()

                ep_match = rex_ep.findall(title)
                ep_match = list(map(int, list(filter(None, itertools.chain(*ep_match)))))
                if ep_match and ep_match[0] != int(episode):
                    regex_ep_range = r'\s\d+-\d+|\s\d+~\d+|\s\d+\s-\s\d+|\s\d+\s~\s\d+'
                    rex_ep_range = re.compile(regex_ep_range)
                    if not rex_ep_range.search(title):
                        continue

                match = rex.findall(title)
                match = list(map(int, list(filter(None, itertools.chain(*match)))))
                if not match or match[0] == int(season):
                    filtered_list.append(torrent)
            else:
                filtered_list.append(torrent)

        cache_list = debrid.TorrentCacheCheck().torrentCacheCheck(filtered_list)
        cache_list = sorted(cache_list, key=lambda k: k['downloads'], reverse=True)
        mapfunc = partial(self._parse_nyaa_episode_view, episode=episode)
        all_results = list(map(mapfunc, cache_list))
        return all_results

    def _process_nyaa_backup(self, url, anilist_id, _zfill, episode='', rescrape=False):
        json_resp = self._get_request(url)
        results = BeautifulSoup(json_resp, 'html.parser')
        rex = r'(magnet:)+[^"]*'
        search_results = [
            (i.find_all('a', {'href': re.compile(rex)})[0].get('href'),
             i.find_all('a', {'class': None})[1].get('title'),
             i.find_all('td', {'class': 'text-center'})[1].text,
             i.find_all('td', {'class': 'text-center'})[-1].text)
            for i in results.select("tr.danger,tr.default,tr.success")
        ][:30]
        list_ = [
            {'magnet': magnet,
             'name': name,
             'size': size.replace('i', ''),
             'downloads': int(downloads)}
            for magnet, name, size, downloads in search_results
        ]

        for torrent in list_:
            torrent['hash'] = re.findall(r'btih:(.*?)(?:&|$)', torrent['magnet'])[0]

        if not rescrape:
            database.addTorrentList(anilist_id, list_, _zfill)

        cache_list = debrid.TorrentCacheCheck().torrentCacheCheck(list_)
        cache_list = sorted(cache_list, key=lambda k: k['downloads'], reverse=True)
        mapfunc = partial(self._parse_nyaa_episode_view, episode=episode)
        all_results = list(map(mapfunc, cache_list))
        return all_results

    def _process_nyaa_movie(self, url, episode):
        json_resp = self._get_request(url)
        results = BeautifulSoup(json_resp, 'html.parser')
        rex = r'(magnet:)+[^"]*'
        search_results = [
            (i.find_all('a', {'href': re.compile(rex)})[0].get('href'),
             i.find_all('a', {'class': None})[1].get('title'),
             i.find_all('td', {'class': 'text-center'})[1].text,
             i.find_all('td', {'class': 'text-center'})[-1].text)
            for i in results.select("tr.danger,tr.default,tr.success")
        ]
        list_ = [
            {'magnet': magnet,
             'name': name,
             'size': size.replace('i', ''),
             'downloads': int(downloads)}
            for magnet, name, size, downloads in search_results
        ]

        for idx, torrent in enumerate(list_):
            torrent['hash'] = re.findall(r'btih:(.*?)(?:&|$)', torrent['magnet'])[0]

        cache_list = debrid.TorrentCacheCheck().torrentCacheCheck(list_)
        cache_list = sorted(cache_list, key=lambda k: k['downloads'], reverse=True)
        mapfunc = partial(self._parse_nyaa_episode_view, episode=episode)
        all_results = list(map(mapfunc, cache_list))
        return all_results

    def _process_cached_sources(self, list_, episode):
        cache_list = debrid.TorrentCacheCheck().torrentCacheCheck(list_)
        mapfunc = partial(self._parse_nyaa_cached_episode_view, episode=episode)
        all_results = list(map(mapfunc, cache_list))
        return all_results

    def get_sources(self, query, anilist_id, episode, status, media_type, rescrape):
        query = self._clean_title(query)

        if media_type == 'movie':
            return self._get_movie_sources(query, anilist_id, episode)

        sources = self._get_episode_sources(query, anilist_id, episode, status, rescrape)

        if not sources and ':' in query:
            q1, q2 = query.split('|')
            q1 = q1[1:-1].split(':')[0]
            q2 = q2[1:-1].split(':')[0]
            query2 = '({0})|({1})'.format(q1, q2)
            sources = self._get_episode_sources(query2, anilist_id, episode, status, rescrape)

        if not sources:
            sources = self._get_episode_sources_backup(query, anilist_id, episode)

        return sources

    def _get_episode_sources(self, show, anilist_id, episode, status, rescrape):
        if rescrape:
            return self._get_episode_sources_pack(show, anilist_id, episode)

        try:
            cached_sources, zfill_int = database.getTorrentList(anilist_id)
            if cached_sources:
                return self._process_cached_sources(cached_sources, episode.zfill(zfill_int))
        except ValueError:
            pass

        query = '%s "- %s"' % (show, episode.zfill(2))
        season = database.get_season_list(anilist_id)
        if season:
            season = str(season['season']).zfill(2)
            query += '|"S%sE%s "' % (season, episode.zfill(2))

        url = '%s?f=0&c=1_0&q=%s&s=downloads&o=desc' % (self._BASE_URL, urllib_parse.quote_plus(query))

        if status == 'FINISHED':
            query = '%s "Batch"|"Complete Series"' % show
            episodes = pickle.loads(database.get_show(anilist_id)['kodi_meta'])['episodes']
            if episodes:
                query += '|"01-{0}"|"01~{0}"|"01 - {0}"|"01 ~ {0}"'.format(episodes)

            if season:
                query += '|"S{0}"|"Season {0}"'.format(season)
                query += '|"S%sE%s "' % (season, episode.zfill(2))

            query += '|"- %s"' % (episode.zfill(2))
            url = '%s?f=0&c=1_0&q=%s&s=seeders&&o=desc' % (self._BASE_URL, urllib_parse.quote_plus(query))

        return self._process_nyaa_episodes(url, episode.zfill(2), season)

    def _get_episode_sources_backup(self, db_query, anilist_id, episode):
        show = self._get_request('https://kaito-title.firebaseio.com/%s.json' % anilist_id)
        show = json.loads(show)

        if not show:
            return []

        if 'general_title' in show:
            query = show['general_title'].encode('utf-8') if six.PY2 else show['general_title']
            _zfill = show.get('zfill', 2)
            episode = episode.zfill(_zfill)
            query = urllib_parse.quote_plus(query)
            url = '%s?f=0&c=1_0&q=%s&s=downloads&o=desc' % (self._BASE_URL, query)
            return self._process_nyaa_backup(url, anilist_id, _zfill, episode)

        try:
            kodi_meta = pickle.loads(database.get_show(anilist_id)['kodi_meta'])
            kodi_meta['query'] = db_query + '|{}'.format(show['general_title'])
            database.update_kodi_meta(anilist_id, kodi_meta)
        except:
            pass

        query = '%s "- %s"' % (show.encode('utf-8') if six.PY2 else show, episode.zfill(2))
        season = database.get_season_list(anilist_id)
        if season:
            season = str(season['season']).zfill(2)
            query += '|"S%sE%s"' % (season, episode.zfill(2))

        url = '%s?f=0&c=1_0&q=%s' % (self._BASE_URL, urllib_parse.quote_plus(query))
        return self._process_nyaa_episodes(url, episode)

    def _get_episode_sources_pack(self, show, anilist_id, episode):
        query = '%s "Batch"|"Complete Series"' % show

        episodes = pickle.loads(database.get_show(anilist_id)['kodi_meta'])['episodes']
        if episodes:
            query += '|"01-{0}"|"01~{0}"|"01 - {0}"|"01 ~ {0}"'.format(episodes)

        season = database.get_season_list(anilist_id)
        if season:
            season = season['season']
            query += '|"S{0}"|"Season {0}"'.format(season)

        url = '%s?f=0&c=1_2&q=%s&s=seeders&&o=desc' % (self._BASE_URL, urllib_parse.quote_plus(query))
        return self._process_nyaa_backup(url, anilist_id, 2, episode.zfill(2), True)

    def _get_movie_sources(self, query, anilist_id, episode):
        query = urllib_parse.quote_plus(query)
        url = '%s?f=0&c=1_2&q=%s&s=downloads&o=desc' % (self._BASE_URL, query)
        sources = self._process_nyaa_movie(url, '1')

        if not sources:
            sources = self._get_movie_sources_backup(anilist_id)

        return sources

    def _get_movie_sources_backup(self, anilist_id, episode='1'):
        show = self._get_request("https://kimetsu-title.firebaseio.com/%s.json" % anilist_id)
        show = json.loads(show)
        if not show:
            return []

        if 'general_title' in show:
            query = show['general_title']
            query = urllib_parse.quote_plus(query)
            url = '%s?f=0&c=1_2&q=%s&s=downloads&o=desc' % (self._BASE_URL, query)
            return self._process_nyaa_backup(url, episode)

        query = urllib_parse.quote_plus(show)
        url = '%s?f=0&c=1_2&q=%s' % (self._BASE_URL, query)
        return self._process_nyaa_movie(url, episode)
