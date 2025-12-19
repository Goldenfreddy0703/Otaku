import re
import pickle

from functools import partial
from bs4 import BeautifulSoup, SoupStrainer
from resources.lib.debrid import Debrid
from resources.lib.ui import database, source_utils, control, client, utils
from resources.lib.ui.BrowserBase import BrowserBase


class Sources(BrowserBase):
    _BASE_URL = 'https://nyaa-si.translate.goog/?_x_tr_sl=es&_x_tr_tl=en&_x_tr_hl=en/' if control.getBool('provider.nyaaalt') else 'https://nyaa.si/'

    def __init__(self):
        self.media_type = None
        self.cached = []
        self.uncached = []
        self.sources = []

    def get_sources(self, query, mal_id, episode, status, media_type):
        query = self._clean_title(query).replace('-', ' ')
        self.media_type = media_type
        if media_type == 'movie':
            return self.get_movie_sources(query, mal_id)

        if 'part' in query.lower() or 'cour' in query.lower():
            part_match = re.search(r'(?:part|cour) ?(\d+)', query.lower())
            if part_match:
                part = int(part_match.group(1).strip())
            else:
                part = None
        else:
            part = None

        # If the part could not be determined from the query, try to get it from the MAL mappings.
        if part is None:
            mal_mapping = database.get_mappings(mal_id, 'mal_id')
            if mal_mapping and 'thetvdb_part' in mal_mapping:
                part = mal_mapping['thetvdb_part']

        episode_sources = self.get_episode_sources(query, mal_id, episode, part, status)
        show_sources = self.get_show_sources(query, mal_id, episode, part)
        self.sources = episode_sources + show_sources

        if not self.sources and ':' in query:
            q1, q2 = query.split('|', 2)
            q1 = q1[1:-1].split(':')[0]
            q2 = q2[1:-1].split(':')[0]
            query2 = '({0})|({1})'.format(q1, q2)
            self.sources = self.get_episode_sources(query2, mal_id, episode, part, status)

        # remove any duplicate sources
        self.append_cache_uncached_noduplicates()
        return {'cached': self.cached, 'uncached': self.uncached}

    def get_episode_sources(self, show, mal_id, episode, part, status):
        season = database.get_episode(mal_id)['season']
        season_zfill = str(season).zfill(2)
        episode_zfill = episode.zfill(2)

        # Build all search queries
        search_tasks = []

        # Primary episode search
        query1 = f'{show} "- {episode_zfill}"|"S{season_zfill}E{episode_zfill}"'
        search_tasks.append({
            'query': query1,
            'params': {'f': '0', 'c': '1_0', 'q': query1.replace(' ', '+'), 's': 'downloads', 'o': 'desc'},
            'name': 'primary'
        })

        # Batch/Complete series search (only for finished shows)
        if status in ["FINISHED", "Finished Airing"]:
            query2 = '%s "Batch"|"Complete Series"' % show
            episodes = pickle.loads(database.get_show(mal_id)['kodi_meta'])['episodes']
            if episodes:
                query2 += f'|"01-{episode_zfill}"|"01~{episode_zfill}"|"01 - {episode_zfill}"|"01 ~ {episode_zfill}"|"E{episode_zfill}"|"Episode {episode_zfill}"'
            if season_zfill:
                query2 += f'|"S{season_zfill}"|"Season {season_zfill}"'
            if episode_zfill and season_zfill:
                query2 += f'|"{season_zfill}-{episode_zfill}"|"{season_zfill}~{episode_zfill}"|"{season_zfill} - {episode_zfill}"|"{season_zfill} ~ {episode_zfill}"'
                query2 += f'|"S{season_zfill}E{episode_zfill}"'
            query2 += f'|"- {episode_zfill}"'

            search_tasks.append({
                'query': query2,
                'params': {'f': '0', 'c': '1_0', 'q': query2.replace(' ', '+'), 's': 'seeders', 'o': 'desc'},
                'name': 'batch'
            })

        # Fallback search without sorting
        query3 = query1  # Reuse primary query
        search_tasks.append({
            'query': query3,
            'params': {'f': '0', 'c': '1_0', 'q': query3.replace(' ', '+')},
            'name': 'fallback'
        })

        # Season search
        query4 = show
        show_lower = show.lower()
        if 'season' in show_lower:
            query1_part, query2_part = show.rsplit('|', 2)
            match_1 = re.match(r'.+?(?=season)', query1_part)
            if match_1:
                match_1 = match_1.group(0).strip() + ')'
            match_2 = re.match(r'.+?(?=season)', query2_part)
            if match_2:
                match_2 = match_2.group(0).strip() + ')'
            query4 = f'{match_1}|{match_2}'

        search_tasks.append({
            'query': query4,
            'params': {'f': '0', 'c': '1_0', 'q': query4.replace(' ', '+')},
            'name': 'additional'
        })

        # Execute all searches in parallel
        control.log(f"Nyaa: Running {len(search_tasks)} searches in parallel for episode {episode_zfill}")

        def run_search(task):
            try:
                sources = self.process_nyaa_episodes(self._BASE_URL, task['params'], mal_id, episode_zfill, season_zfill, part)
                control.log(f"Nyaa: {task['name']} search returned {len(sources)} sources")
                return sources
            except Exception as e:
                control.log(f"Nyaa: {task['name']} search failed: {str(e)}")
                return []

        all_search_results = utils.parallel_process(search_tasks, run_search, max_workers=4)

        # Combine all results
        nyaa_sources = []
        for sources in all_search_results:
            nyaa_sources.extend(sources)

        control.log(f"Nyaa: Episode search complete - returning {len(nyaa_sources)} total sources")
        return nyaa_sources

    def get_show_sources(self, show, mal_id, episode, part):
        control.log(f"Nyaa: Searching show/batch sources for '{show}'")
        season = database.get_episode(mal_id)['season']
        season_zfill = str(season).zfill(2)
        episode_zfill = episode.zfill(2)
        query = show

        params = {
            'f': '0',
            'c': '1_0',
            'q': query.replace(' ', '+'),
            's': 'downloads',
            'o': 'desc'
        }

        nyaa_sources = self.process_nyaa_episodes(self._BASE_URL, params, mal_id, episode_zfill, season_zfill, part)
        control.log(f"Nyaa: Show search complete - found {len(nyaa_sources)} sources")
        return nyaa_sources

    def get_movie_sources(self, query, mal_id):
        control.log(f"Nyaa: Searching movie sources for '{query}'")
        params = {
            'f': '0',
            'c': '1_2',
            'q': query.replace(' ', '+'),
            's': 'downloads',
            'o': 'desc'
        }

        self.sources = self.process_nyaa_movie(self._BASE_URL, params, mal_id)

        # make sure no duplicate sources
        self.append_cache_uncached_noduplicates()
        return {'cached': self.cached, 'uncached': self.uncached}

    def process_nyaa_episodes(self, url, params, mal_id, episode_zfill, season_zfill, part):
        response = client.get(url, params=params)
        if response:
            html = response.text
            mlink = SoupStrainer('div', {'class': 'table-responsive'})
            soup = BeautifulSoup(html, "html.parser", parse_only=mlink)
            rex = r'(magnet:)+[^"]*'
            list_ = [
                {'magnet': i.find('a', {'href': re.compile(rex)}).get('href'),
                 'name': i.find_all('a', {'class': None})[1].get('title'),
                 'size': i.find_all('td', {'class': 'text-center'})[1].text.replace('i', ''),
                 'downloads': int(i.find_all('td', {'class': 'text-center'})[-1].text),
                 'seeders': int(i.find_all('td', {'class': 'text-center'})[-3].text)
                 } for i in soup.select("tr.danger,tr.default,tr.success")
            ]

            for idx, torrent in enumerate(list_):
                torrent['hash'] = re.findall(r'btih:(.*?)(?:&|$)', torrent['magnet'])[0]

            filtered_list = source_utils.filter_sources('nyaa', list_, mal_id, int(season_zfill), int(episode_zfill), part)

            cache_list, uncashed_list_ = Debrid().torrentCacheCheck(filtered_list)
            cache_list = sorted(cache_list, key=lambda k: k['downloads'], reverse=True)

            uncashed_list = [i for i in uncashed_list_ if i['seeders'] > 0]
            uncashed_list = sorted(uncashed_list, key=lambda k: k['seeders'], reverse=True)

            # Parse sources in parallel for faster processing
            mapfunc = partial(self.parse_nyaa_view, episode=episode_zfill)
            all_results = utils.parallel_process(cache_list, mapfunc, max_workers=5) if cache_list else []
            if control.getBool('show.uncached') and uncashed_list:
                mapfunc2 = partial(self.parse_nyaa_view, episode=episode_zfill, cached=False)
                all_results += utils.parallel_process(uncashed_list, mapfunc2, max_workers=5)
            return all_results

    def process_nyaa_movie(self, url, params, mal_id):
        response = client.get(url, params=params)
        if response:
            res = response.text
            results = BeautifulSoup(res, 'html.parser')
            rex = r'(magnet:)+[^"]*'
            search_results = [
                (i.find_all('a', {'href': re.compile(rex)})[0].get('href'),
                 i.find_all('a', {'class': None})[1].get('title'),
                 i.find_all('td', {'class': 'text-center'})[1].text,
                 i.find_all('td', {'class': 'text-center'})[-1].text,
                 i.find_all('td', {'class': 'text-center'})[-3].text
                 ) for i in results.select("tr.danger,tr.default,tr.success")]

            list_ = [
                {
                    'magnet': magnet,
                    'name': name,
                    'size': size.replace('i', ''),
                    'downloads': int(downloads),
                    'seeders': int(seeders)
                } for magnet, name, size, downloads, seeders in search_results
            ]

            for idx, torrent in enumerate(list_):
                torrent['hash'] = re.findall(r'btih:(.*?)(?:&|$)', torrent['magnet'])[0]

            filtered_list = source_utils.filter_sources('nyaa', list_, mal_id)

            cache_list, uncashed_list_ = Debrid().torrentCacheCheck(filtered_list)
            cache_list = sorted(cache_list, key=lambda k: k['downloads'], reverse=True)

            uncashed_list = [i for i in uncashed_list_ if i['seeders'] > 0]
            uncashed_list = sorted(uncashed_list, key=lambda k: k['seeders'], reverse=True)

            # Parse sources in parallel for faster processing
            mapfunc = partial(self.parse_nyaa_view, episode=1)
            all_results = utils.parallel_process(cache_list, mapfunc, max_workers=5) if cache_list else []
            if control.getBool('show.uncached') and uncashed_list:
                mapfunc2 = partial(self.parse_nyaa_view, episode=1, cached=False)
                all_results += utils.parallel_process(uncashed_list, mapfunc2, max_workers=5)
            return all_results

    @staticmethod
    def parse_nyaa_view(res, episode, cached=True):
        source = {
            'release_title': res['name'],
            'hash': res['hash'],
            'type': 'torrent',
            'quality': source_utils.getQuality(res['name']),
            'debrid_provider': res.get('debrid_provider'),
            'provider': 'nyaa',
            'episode_re': episode,
            'size': res['size'],
            'byte_size': 0,
            'info': source_utils.getInfo(res['name']),
            'lang': source_utils.getAudio_lang(res['name']),
            'channel': source_utils.getAudio_channel(res['name']),
            'sub': source_utils.getSubtitle_lang(res['name']),
            'cached': cached,
            'seeders': res['seeders']
        }

        match = re.match(r'(\d+).(\d+) (\w+)', res['size'])
        if match:
            source['byte_size'] = source_utils.convert_to_bytes(float(f'{match.group(1)}.{match.group(2)}'), match.group(3))
        if not cached:
            source['magnet'] = res['magnet']
            source['type'] += ' (uncached)'

        return source

    def append_cache_uncached_noduplicates(self):
        # Keep one source per (hash, debrid_provider) so multiple providers can show for the same torrent
        unique = {}
        for source in self.sources:
            key = (source.get('hash'), source.get('debrid_provider'))
            if not key[0]:
                continue
            if key in unique:
                current = unique[key]
                # Compare seeders first; if equal, compare byte_size
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
