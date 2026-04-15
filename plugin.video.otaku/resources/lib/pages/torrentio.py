import re

from functools import partial
from resources.lib.debrid import Debrid
from resources.lib.ui import database, source_utils, control, client, utils
from resources.lib.ui.BrowserBase import BrowserBase


class Sources(BrowserBase):
    _BASE_URL = 'https://torrentio.strem.fun'

    def __init__(self):
        self.media_type = None
        self.cached = []
        self.uncached = []
        self.sources = []
        self.kitsu_id = None

    def _build_config(self):
        providers = control.getStringList('torrentio.config')
        if providers:
            return f"providers={','.join(providers)}"
        return ''

    def get_sources(self, query, mal_id, episode, status, media_type, season=None, part=None):
        self.media_type = media_type

        show_ids = database.get_mappings(mal_id, 'mal_id')
        if show_ids:
            self.kitsu_id = show_ids.get('kitsu_id')

        if not self.kitsu_id:
            control.log('Torrentio: No kitsu_id found, skipping', 'warning')
            return {'cached': [], 'uncached': []}

        if media_type == 'movie':
            return self.get_movie_sources(mal_id)

        episode_zfill = episode.zfill(2)
        self.sources = self.process_torrentio_episodes(mal_id, episode_zfill, season, part)

        self.append_cache_uncached_noduplicates()
        return {'cached': self.cached, 'uncached': self.uncached}

    def get_movie_sources(self, mal_id):
        self.sources = self.process_torrentio_movie(mal_id)

        self.append_cache_uncached_noduplicates()
        return {'cached': self.cached, 'uncached': self.uncached}

    def process_torrentio_episodes(self, mal_id, episode, season, part):
        config = self._build_config()
        path = f"/{config}" if config else ""
        url = f"{self._BASE_URL}{path}/stream/series/kitsu:{self.kitsu_id}:{episode}.json"
        control.log(f"Torrentio: Fetching episode sources from kitsu:{self.kitsu_id}:{episode}")

        response = client.get(url, timeout=30)
        if not response:
            return []

        data = response.json()
        if not data:
            return []

        list_ = self._parse_stream_list(data)
        control.log(f"Torrentio: Got {len(list_)} raw streams")
        if not list_:
            return []

        season_int = int(season) if season else None
        filtered_list = source_utils.filter_sources('torrentio', list_, mal_id, season_int, int(episode), part)
        control.log(f"Torrentio: {len(filtered_list)} sources after filtering")

        cache_list, uncached_list_ = Debrid().torrentCacheCheck(filtered_list, mal_id=mal_id, episode=episode, media_type=self.media_type)
        cache_list = sorted(cache_list, key=lambda k: k['seeders'], reverse=True)

        uncached_list = [i for i in uncached_list_ if i['seeders'] > 0]
        uncached_list = sorted(uncached_list, key=lambda k: k['seeders'], reverse=True)

        mapfunc = partial(self.parse_torrentio_view, episode=episode)
        all_results = utils.parallel_process(cache_list, mapfunc) if cache_list else []
        if control.getBool('show.uncached') and uncached_list:
            mapfunc2 = partial(self.parse_torrentio_view, episode=episode, cached=False)
            all_results += utils.parallel_process(uncached_list, mapfunc2)
        return all_results

    def process_torrentio_movie(self, mal_id):
        config = self._build_config()
        path = f"/{config}" if config else ""
        url = f"{self._BASE_URL}{path}/stream/movie/kitsu:{self.kitsu_id}.json"
        control.log(f"Torrentio: Fetching movie sources from kitsu:{self.kitsu_id}")

        response = client.get(url, timeout=30)
        if not response:
            return []

        data = response.json()
        if not data:
            return []

        list_ = self._parse_stream_list(data)
        control.log(f"Torrentio: Got {len(list_)} raw movie streams")
        if not list_:
            return []

        filtered_list = source_utils.filter_sources('torrentio', list_, mal_id)

        cache_list, uncached_list_ = Debrid().torrentCacheCheck(filtered_list, mal_id=mal_id, episode='1', media_type=self.media_type)
        cache_list = sorted(cache_list, key=lambda k: k['seeders'], reverse=True)

        uncached_list = [i for i in uncached_list_ if i['seeders'] > 0]
        uncached_list = sorted(uncached_list, key=lambda k: k['seeders'], reverse=True)

        mapfunc = partial(self.parse_torrentio_view, episode='1')
        all_results = utils.parallel_process(cache_list, mapfunc) if cache_list else []
        if control.getBool('show.uncached') and uncached_list:
            mapfunc2 = partial(self.parse_torrentio_view, episode='1', cached=False)
            all_results += utils.parallel_process(uncached_list, mapfunc2)
        return all_results

    @staticmethod
    def _parse_stream_list(data):
        re_seeders = re.compile(r'👤\s*(\d+)')
        re_provider = re.compile(r'⚙️\s*(.+)')

        list_ = []
        for stream in data.get('streams', []):
            torrent_hash = stream.get('infoHash', '')
            if not torrent_hash:
                continue

            title = stream.get('title', '')
            name = title.split('\n', 1)[0].strip()
            if not name:
                continue

            behaviorhints = stream.get('behaviorHints', {})
            match_seeders = re_seeders.search(title)
            match_provider = re_provider.search(title)
            size_match = re.search(r'([\d.]+\s*[GMKT]B)', title, re.IGNORECASE)

            list_.append({
                'name': name,
                'hash': torrent_hash,
                'magnet': f"magnet:?xt=urn:btih:{torrent_hash}&dn={name}",
                'filename': behaviorhints.get('filename', ''),
                'size': size_match.group(1) if size_match else 'NA',
                'seeders': int(match_seeders.group(1)) if match_seeders else 0,
                'source_provider': match_provider.group(1).strip() if match_provider else '',
            })

        return list_

    @staticmethod
    def parse_torrentio_view(res, episode, cached=True):
        source = {
            'release_title': res['name'],
            'hash': res['hash'],
            'filename': res.get('filename', ''),
            'type': 'torrent',
            'quality': source_utils.getQuality(res['name']),
            'debrid_provider': res.get('debrid_provider'),
            'provider': f"Tio ({res['source_provider']})" if res.get('source_provider') else 'Torrentio',
            'episode_re': episode,
            'size': res['size'],
            'byte_size': 0,
            'info': source_utils.getInfo(res['name']),
            'lang': source_utils.getAudio_lang(res['name']),
            'channel': source_utils.getAudio_channel(res['name']),
            'sub': source_utils.getSubtitle_lang(res['name']),
            'cached': cached,
            'seeders': res['seeders'],
        }

        match = re.match(r'([\d.]+)\s*(\w+)', res['size'])
        if match:
            try:
                source['byte_size'] = source_utils.convert_to_bytes(float(match.group(1)), match.group(2))
            except (ValueError, KeyError):
                pass

        if not cached:
            source['magnet'] = res['magnet']
            source['type'] += ' (uncached)'

        return source

    def append_cache_uncached_noduplicates(self):
        unique = {}
        for source in self.sources:
            key = (source.get('hash'), source.get('debrid_provider'))
            if not key[0]:
                continue
            if key in unique:
                current = unique[key]
                if source.get('seeders', -1) > current.get('seeders', -1):
                    unique[key] = source
                elif (source.get('seeders', -1) == current.get('seeders', -1)
                      and source.get('byte_size', 0) > current.get('byte_size', 0)):
                    unique[key] = source
            else:
                unique[key] = source

        self.cached = []
        self.uncached = []
        for source in unique.values():
            if source['cached']:
                self.cached.append(source)
            else:
                self.uncached.append(source)
