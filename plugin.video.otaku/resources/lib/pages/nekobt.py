import re

from functools import partial
from resources.lib.debrid import Debrid
from resources.lib.ui import database, source_utils, control, client, utils
from resources.lib.ui.BrowserBase import BrowserBase


class Sources(BrowserBase):
    _BASE_URL = 'https://nekobt.to/api/v1'

    def __init__(self):
        self.media_type = None
        self.cached = []
        self.uncached = []
        self.sources = []
        self.media_id = None

    @staticmethod
    def _parse_titles(query):
        """Extract individual titles from the '(Title1)|(Title2)' format."""
        titles = re.findall(r'\(([^)]+)\)', query)
        if not titles:
            titles = [query.strip()]
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for t in titles:
            t_stripped = t.strip()
            if t_stripped and t_stripped.lower() not in seen:
                seen.add(t_stripped.lower())
                unique.append(t_stripped)
        return unique

    def _get_tvdb_id(self, mal_id):
        """Look up the TVDB ID from the mapping database."""
        mapping = database.get_mappings(mal_id, 'mal_id')
        if mapping:
            tvdb_id = mapping.get('thetvdb_id')
            if tvdb_id:
                return int(tvdb_id)
        return None

    def _resolve_media_id(self, titles, mal_id):
        """Search nekoBT /media/search by title and match by TVDB ID to find the internal media_id."""
        tvdb_id = self._get_tvdb_id(mal_id)
        for title in titles:
            response = client.get(f'{self._BASE_URL}/media/search', params={'query': title, 'limit': 10}, timeout=20)
            if not response or response.status_code != 200:
                continue
            try:
                data = response.json()
                if data.get('error') or 'data' not in data:
                    continue
                results = data['data'].get('results', [])
                # If we have a TVDB ID, match on it for precision
                if tvdb_id:
                    for media in results:
                        if media.get('tvdbId') == tvdb_id:
                            control.log(f"nekoBT: Resolved media_id={media['id']} via TVDB {tvdb_id} for '{title}'")
                            return media['id']
                # Fallback: take the first result if it has high similarity
                if results:
                    best = results[0]
                    control.log(f"nekoBT: Using best media match media_id={best['id']} for '{title}'")
                    return best['id']
            except Exception as e:
                control.log(f"nekoBT: Media search failed for '{title}': {e}")
        return None

    def _get_episode_ids(self, media_id, season, episode):
        """Fetch episode list from /media/<media_id> and find matching nekoBT episode IDs."""
        response = client.get(f'{self._BASE_URL}/media/{media_id}', timeout=20)
        if not response or response.status_code != 200:
            return []
        try:
            data = response.json()
            if data.get('error') or 'data' not in data:
                return []
            episodes = data['data'].get('episodes', [])
            episode_int = int(episode)
            season_int = int(season) if season else 1

            # Strategy 1: Exact season + episode match
            matched = [str(ep['id']) for ep in episodes if ep.get('season') == season_int and ep.get('episode') == episode_int]

            # Strategy 2: Try season 0 (absolute numbering) if no match
            if not matched:
                matched = [str(ep['id']) for ep in episodes if ep.get('season') == 0 and ep.get('episode') == episode_int]

            # Strategy 3: Match just by episode number regardless of season
            if not matched:
                matched = [str(ep['id']) for ep in episodes if ep.get('episode') == episode_int]

            control.log(f"nekoBT: Found episode_ids={matched} for S{season_int:02d}E{episode_int:02d} from {len(episodes)} total episodes")
            return matched
        except Exception as e:
            control.log(f"nekoBT: Failed to get episode IDs: {e}")
            return []

    def _search_torrents(self, params):
        """Execute a search against the nekoBT /torrents/search endpoint."""
        control.log(f"nekoBT: Searching torrents with params: {params}")
        response = client.get(f'{self._BASE_URL}/torrents/search', params=params, timeout=30)
        if response and response.status_code == 200:
            try:
                data = response.json()
                if not data.get('error') and 'data' in data:
                    return data['data'].get('results', [])
            except Exception as e:
                control.log(f"nekoBT: Failed to parse torrent response: {e}")
        return []

    @staticmethod
    def _format_size(filesize_bytes):
        """Convert byte size to human-readable string."""
        try:
            size = int(filesize_bytes)
        except (ValueError, TypeError):
            return '0 B'
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f'{size:.2f} {unit}'
            size /= 1024
        return f'{size:.2f} PB'

    def get_sources(self, query, mal_id, episode, status, media_type, season=None, part=None):
        query = self._clean_title(query).replace('-', ' ')
        self.media_type = media_type
        titles = self._parse_titles(query)
        control.log(f"nekoBT: Parsed titles: {titles}")

        # Resolve nekoBT's internal media_id using title search + TVDB matching
        self.media_id = self._resolve_media_id(titles, mal_id)
        control.log(f"nekoBT: Resolved media_id={self.media_id} for mal_id={mal_id}")

        # Resolve episode IDs for precise API-level filtering
        self.episode_ids = []
        if self.media_id and media_type != 'movie':
            self.episode_ids = self._get_episode_ids(self.media_id, season, episode)

        if media_type == 'movie':
            return self.get_movie_sources(titles, mal_id)

        episode_sources = self.get_episode_sources(titles, mal_id, episode, season, part, status)

        # Retry with simplified titles if colon present and no results
        if not episode_sources:
            simplified = [t.split(':')[0].strip() for t in titles if ':' in t]
            if simplified:
                control.log(f"nekoBT: Retrying with simplified titles: {simplified}")
                self.media_id = self._resolve_media_id(simplified, mal_id) or self.media_id
                if self.media_id and not self.episode_ids:
                    self.episode_ids = self._get_episode_ids(self.media_id, season, episode)
                episode_sources = self.get_episode_sources(simplified, mal_id, episode, season, part, status)

        self.sources = episode_sources
        self.append_cache_uncached_noduplicates()
        return {'cached': self.cached, 'uncached': self.uncached}

    def get_episode_sources(self, titles, mal_id, episode, season, part, status):
        season_zfill = str(season).zfill(2) if season else '01'
        episode_zfill = episode.zfill(2)
        ep_hint = f'S{season_zfill}E{episode_zfill}'

        # Include secondary groups, parent groups, and contributions for full coverage
        group_params = {
            'group_secondary': 'true',
            'group_parents': 'true',
            'uploader_contributions': 'true',
        }

        search_tasks = []

        if self.media_id:
            # 1. Episode-specific search using nekoBT episode IDs (most precise)
            if self.episode_ids:
                search_tasks.append({
                    'params': {
                        'media_id': self.media_id,
                        'episode_ids': ','.join(self.episode_ids),
                        'episode_match_any': 'true',
                        'sort_by': 'seeders',
                        'limit': 100,
                        **group_params
                    },
                    'name': 'episode_ids'
                })

            # 2. Media + episode hint query (API hint system filters server-side)
            search_tasks.append({
                'params': {
                    'media_id': self.media_id,
                    'query': ep_hint,
                    'sort_by': 'seeders',
                    'limit': 100,
                    **group_params
                },
                'name': 'media_id+hint'
            })

            # 3. Media + batch query (catches complete season/series packs)
            search_tasks.append({
                'params': {
                    'media_id': self.media_id,
                    'query': 'batch',
                    'sort_by': 'seeders',
                    'limit': 100,
                    **group_params
                },
                'name': 'media_id+batch'
            })

            # 4. Media + latest sort (catches newer uploads with fewer seeders)
            if self.episode_ids:
                search_tasks.append({
                    'params': {
                        'media_id': self.media_id,
                        'episode_ids': ','.join(self.episode_ids),
                        'episode_match_any': 'true',
                        'sort_by': 'latest',
                        'limit': 100,
                        **group_params
                    },
                    'name': 'episode_ids+latest'
                })

        # Title-based searches as fallback when no media_id was resolved
        if not self.media_id:
            for title in titles:
                search_tasks.append({
                    'params': {
                        'query': f'{title} {ep_hint}',
                        'sort_by': 'seeders',
                        'limit': 50,
                        **group_params
                    },
                    'name': f'title+ep:{title}'
                })
                search_tasks.append({
                    'params': {
                        'query': title,
                        'sort_by': 'seeders',
                        'limit': 50,
                        **group_params
                    },
                    'name': f'title:{title}'
                })

        control.log(f"nekoBT: Running {len(search_tasks)} searches in parallel for {ep_hint}")

        def run_search(task):
            try:
                raw_results = self._search_torrents(task['params'])
                list_ = self._results_to_list(raw_results)
                filtered = source_utils.filter_sources('nekobt', list_, mal_id, int(season_zfill), int(episode_zfill), part)
                control.log(f"nekoBT: {task['name']} returned {len(raw_results)} raw, {len(filtered)} after filter")
                return filtered
            except Exception as e:
                control.log(f"nekoBT: {task['name']} search failed: {e}")
                return []

        all_results = utils.parallel_process(search_tasks, run_search)

        # Deduplicate by hash across all searches
        seen_hashes = set()
        combined = []
        for torrents in all_results:
            for t in torrents:
                h = t.get('hash', '')
                if h and h not in seen_hashes:
                    seen_hashes.add(h)
                    combined.append(t)

        if not combined:
            return []

        # Single debrid cache check for all results
        cache_list, uncached_list_ = Debrid().torrentCacheCheck(combined, mal_id=mal_id, episode=episode_zfill, media_type='episode')
        cache_list = sorted(cache_list, key=lambda k: k['downloads'], reverse=True)
        uncached_list = [i for i in uncached_list_ if i['seeders'] > 0]
        uncached_list = sorted(uncached_list, key=lambda k: k['seeders'], reverse=True)
        control.log(f"nekoBT: {len(combined)} unique torrents — {len(cache_list)} cached, {len(uncached_list)} uncached")

        mapfunc = partial(self.parse_nekobt_view, episode=episode_zfill)
        nekobt_sources = utils.parallel_process(cache_list, mapfunc) if cache_list else []
        if control.getBool('show.uncached') and uncached_list:
            mapfunc2 = partial(self.parse_nekobt_view, episode=episode_zfill, cached=False)
            nekobt_sources += utils.parallel_process(uncached_list, mapfunc2)

        control.log(f"nekoBT: Episode search complete - returning {len(nekobt_sources)} sources")
        return nekobt_sources

    def get_movie_sources(self, titles, mal_id):
        group_params = {
            'group_secondary': 'true',
            'group_parents': 'true',
            'uploader_contributions': 'true',
        }
        search_tasks = []

        if self.media_id:
            search_tasks.append({
                'params': {'media_id': self.media_id, 'sort_by': 'seeders', 'limit': 100, **group_params},
                'name': 'media_id'
            })

        for title in titles:
            search_tasks.append({
                'params': {'query': title, 'sort_by': 'seeders', 'limit': 50, **group_params},
                'name': f'title:{title}'
            })

        def run_search(task):
            try:
                return self._search_torrents(task['params'])
            except Exception as e:
                control.log(f"nekoBT: Movie {task['name']} search failed: {e}")
                return []

        all_api_results = utils.parallel_process(search_tasks, run_search)

        combined = []
        for results in all_api_results:
            combined.extend(results)

        self.sources = self._process_movie_results(combined, mal_id)
        self.append_cache_uncached_noduplicates()
        return {'cached': self.cached, 'uncached': self.uncached}

    def _results_to_list(self, results):
        """Convert nekoBT API results to standardized torrent list format."""
        list_ = []
        for item in results:
            try:
                magnet = item.get('magnet') or item.get('private_magnet', '')
                infohash = item.get('infohash', '')
                if not magnet and not infohash:
                    continue

                filesize = int(item.get('filesize', 0))
                list_.append({
                    'name': item.get('title', ''),
                    'magnet': magnet,
                    'hash': infohash.lower() if infohash else re.findall(r'btih:(.*?)(?:&|$)', magnet)[0].lower(),
                    'size': self._format_size(filesize),
                    'byte_size': filesize,
                    'seeders': int(item.get('seeders', 0)),
                    'leechers': int(item.get('leechers', 0)),
                    'downloads': int(item.get('completed', 0)),
                })
            except Exception as e:
                control.log(f"nekoBT: Failed to parse result: {e}")
                continue
        return list_

    def _process_movie_results(self, results, mal_id):
        if not results:
            return []

        list_ = self._results_to_list(results)
        filtered_list = source_utils.filter_sources('nekobt', list_, mal_id)

        cache_list, uncached_list_ = Debrid().torrentCacheCheck(filtered_list, mal_id=mal_id, episode='1', media_type='movie')
        cache_list = sorted(cache_list, key=lambda k: k['downloads'], reverse=True)

        uncached_list = [i for i in uncached_list_ if i['seeders'] > 0]
        uncached_list = sorted(uncached_list, key=lambda k: k['seeders'], reverse=True)

        mapfunc = partial(self.parse_nekobt_view, episode="1")
        all_results = utils.parallel_process(cache_list, mapfunc) if cache_list else []
        if control.getBool('show.uncached') and uncached_list:
            mapfunc2 = partial(self.parse_nekobt_view, episode="1", cached=False)
            all_results += utils.parallel_process(uncached_list, mapfunc2)
        return all_results

    @staticmethod
    def parse_nekobt_view(res, episode, cached=True):
        source = {
            'release_title': res['name'],
            'hash': res['hash'],
            'type': 'torrent',
            'quality': source_utils.getQuality(res['name']),
            'debrid_provider': res.get('debrid_provider'),
            'provider': 'nekobt',
            'episode_re': episode,
            'size': res['size'],
            'byte_size': res.get('byte_size', 0),
            'info': source_utils.getInfo(res['name']),
            'lang': source_utils.getAudio_lang(res['name']),
            'channel': source_utils.getAudio_channel(res['name']),
            'sub': source_utils.getSubtitle_lang(res['name']),
            'cached': cached,
            'seeders': res['seeders'],
        }

        if not source['byte_size']:
            match = re.match(r'(\d+).(\d+) (\w+)', res['size'])
            if match:
                source['byte_size'] = source_utils.convert_to_bytes(float(f'{match.group(1)}.{match.group(2)}'), match.group(3))

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
