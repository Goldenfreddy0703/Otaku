import re
import pickle

from functools import partial
from bs4 import BeautifulSoup, SoupStrainer
from resources.lib.debrid import Debrid
from resources.lib.ui import database, source_utils, control, client, utils
from resources.lib.ui.BrowserBase import BrowserBase


class Sources(BrowserBase):
    _BASE_URL = 'https://nyaa-si.translate.goog/?_x_tr_sl=es&_x_tr_tl=en&_x_tr_hl=en/' if control.getBool('provider.nyaaalt') else 'https://nyaa.si/'

    _SEASON_MARKER = re.compile(r'(?i)\bs(?:eason)?[ ._-]?\d{1,2}(?!\d)|\b\d{1,2}(?:st|nd|rd|th)[ ._-]+season\b')

    def __init__(self):
        self.media_type = None
        self.cached = []
        self.uncached = []
        self.sources = []
        self.filter_kwargs = {}
        self.absolute_episode = None
        self.season_episode = None

    def get_sources(self, query, mal_id, episode, status, media_type, season=None, part=None, hints=None):
        hints = hints or {}
        self.filter_kwargs = source_utils.filter_kwargs(hints)
        self.absolute_episode = hints.get('absolute_episode')
        self.season_episode = hints.get('season_episode')
        titles = hints.get('titles') or self._parse_query_titles(self._clean_title(query).replace('-', ' '))
        self.media_type = media_type
        if media_type == 'movie':
            return self.get_movie_sources(self._build_title_query(titles), mal_id)

        episode_sources = self.get_episode_sources(titles, mal_id, episode, season, part, status)
        show_sources = self.get_show_sources(self._build_title_query(titles), mal_id, episode, season, part)
        self.sources = episode_sources + show_sources

        short_titles = [title.split(':')[0].strip() for title in titles if ':' in title]
        if not self.sources and short_titles:
            self.sources = self.get_episode_sources(short_titles, mal_id, episode, season, part, status)

        # remove any duplicate sources
        self.append_cache_uncached_noduplicates()
        return {'cached': self.cached, 'uncached': self.uncached}

    @staticmethod
    def season_stripped_query(titles, parts=False):
        """Title query with season markers removed, or None if no title has one."""
        stripped = [utils.strip_season_tokens(title, parts) for title in titles]
        changed = [base for base, title in zip(stripped, titles) if base and base != title]
        return Sources._build_title_query(list(dict.fromkeys(changed))) if changed else None

    def get_episode_sources(self, titles, mal_id, episode, season, part, status):
        show = self._build_title_query(titles)
        season_zfill = str(season).zfill(2) if season else '01'
        episode_zfill = episode.zfill(2)

        # Build all search queries
        search_tasks = []

        # Primary episode search
        episode_terms = f'"- {episode_zfill}"|"S{season_zfill}E{episode_zfill}"'
        if self.absolute_episode:
            episode_terms += f'|"- {str(self.absolute_episode).zfill(2)}"'
        if self.season_episode:
            episode_terms += f'|"S{season_zfill}E{str(self.season_episode).zfill(2)}"'
        query1 = f'{show} {episode_terms}'
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
        # Without "II" in the query, a release with no season could be from any season
        roman = any(utils.has_roman_season(title) for title in titles)
        query4 = self.season_stripped_query(titles) or show
        search_tasks.append({
            'query': query4,
            'params': {'f': '0', 'c': '1_0', 'q': query4.replace(' ', '+')},
            'name': 'additional',
            'needs_season': roman
        })

        # Releases often leave "II" out of the title, and split cours often drop "Part 2" and number on
        if self.season_episode:
            stripped = self.season_stripped_query(titles, parts=True)
            stripped_episode = str(self.season_episode).zfill(2)
            stripped_terms = f'"- {stripped_episode}"|"S{season_zfill}E{stripped_episode}"'
        else:
            stripped = self.season_stripped_query(titles)
            stripped_episode = episode_zfill
            stripped_terms = episode_terms
        if stripped:
            query5 = f'{stripped} {stripped_terms}'
            search_tasks.append({
                'query': query5,
                'params': {'f': '0', 'c': '1_0', 'q': query5.replace(' ', '+'), 's': 'downloads', 'o': 'desc'},
                'name': 'stripped_episode',
                # Without "Part 2" in the query, a plain episode number would also match the first cour
                'episode': stripped_episode,
                'needs_season': roman and not self.season_episode
            })

        # Execute all searches in parallel
        control.log(f"Nyaa: Running {len(search_tasks)} searches in parallel for episode {episode_zfill}")

        def run_search(task):
            try:
                sources = self.process_nyaa_episodes(self._BASE_URL, task['params'], mal_id, task.get('episode', episode_zfill), season_zfill, part)
                if task.get('needs_season'):
                    sources = [source for source in sources if self._SEASON_MARKER.search(source['release_title'])]
                control.log(f"Nyaa: {task['name']} search returned {len(sources)} sources")
                return sources
            except Exception as e:
                control.log(f"Nyaa: {task['name']} search failed: {str(e)}")
                return []

        all_search_results = utils.parallel_process(search_tasks, run_search)

        # Combine all results
        nyaa_sources = []
        for sources in all_search_results:
            nyaa_sources.extend(sources)

        control.log(f"Nyaa: Episode search complete - returning {len(nyaa_sources)} total sources")
        return nyaa_sources

    def get_show_sources(self, show, mal_id, episode, season, part):
        control.log(f"Nyaa: Searching show/batch sources for '{show}'")
        season_zfill = str(season).zfill(2) if season else '01'
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

            filtered_list = source_utils.filter_sources('nyaa', list_, mal_id, int(season_zfill), int(episode_zfill), part, **self.filter_kwargs)

            cache_list, uncashed_list_ = Debrid().torrentCacheCheck(filtered_list, mal_id=mal_id, episode=episode_zfill, media_type=self.media_type)
            cache_list = sorted(cache_list, key=lambda k: k['downloads'], reverse=True)

            uncashed_list = [i for i in uncashed_list_ if i['seeders'] > 0]
            uncashed_list = sorted(uncashed_list, key=lambda k: k['seeders'], reverse=True)

            # Parse sources in parallel for faster processing
            mapfunc = partial(self.parse_nyaa_view, episode=episode_zfill)
            all_results = utils.parallel_process(cache_list, mapfunc) if cache_list else []
            if control.getBool('show.uncached') and uncashed_list:
                mapfunc2 = partial(self.parse_nyaa_view, episode=episode_zfill, cached=False)
                all_results += utils.parallel_process(uncashed_list, mapfunc2)
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

            cache_list, uncashed_list_ = Debrid().torrentCacheCheck(filtered_list, mal_id=mal_id, episode='1', media_type='movie')
            cache_list = sorted(cache_list, key=lambda k: k['downloads'], reverse=True)

            uncashed_list = [i for i in uncashed_list_ if i['seeders'] > 0]
            uncashed_list = sorted(uncashed_list, key=lambda k: k['seeders'], reverse=True)

            # Parse sources in parallel for faster processing
            mapfunc = partial(self.parse_nyaa_view, episode=1)
            all_results = utils.parallel_process(cache_list, mapfunc) if cache_list else []
            if control.getBool('show.uncached') and uncashed_list:
                mapfunc2 = partial(self.parse_nyaa_view, episode=1, cached=False)
                all_results += utils.parallel_process(uncashed_list, mapfunc2)
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
            'info': source_utils.get_release_info(res),
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
