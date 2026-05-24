import pickle
import datetime
import time
import random
import threading

from functools import partial
from resources.lib.ui import utils, database, client, control
from resources.lib import indexers


class JikanAPI:
    _rate_lock = threading.Lock()
    _request_timestamps = []

    def __init__(self):
        self.baseUrl = "https://api.jikan.moe/v4"

    @classmethod
    def _throttle_3req_per_second(cls):
        """Global Jikan guard: max 3 requests over any 1 second window."""
        while True:
            wait_for = 0
            with cls._rate_lock:
                now = time.monotonic()
                cls._request_timestamps = [t for t in cls._request_timestamps if (now - t) < 1.0]
                if len(cls._request_timestamps) < 3:
                    cls._request_timestamps.append(now)
                    return
                wait_for = max(0.0, 1.0 - (now - cls._request_timestamps[0]))
            if wait_for > 0:
                time.sleep(wait_for + 0.01)

    def get_anime_info(self, mal_id):
        response = client.get(f'{self.baseUrl}/anime/{mal_id}')
        if response:
            return response.json()['data']

    def get_anime_synopsis(self, mal_id):
        """Return synopsis/background for a MAL anime ID."""
        try:
            self._throttle_3req_per_second()
            data = self.get_anime_info(mal_id)
            if not data:
                return None
            return data.get('synopsis') or data.get('background') or None
        except Exception:
            return None

    def get_episode_meta(self, mal_id):
        url = f'{self.baseUrl}/anime/{mal_id}/episodes'
        response = client.get(url)
        if not response:
            return []

        res = response.json()
        res_data = res['data']

        # If only one page, return immediately
        if not res['pagination']['has_next_page']:
            return res_data

        # Fetch all pages in batches to respect Jikan's 3 req/sec rate limit
        last_page = res['pagination']['last_visible_page']
        control.log(f"Jikan: Fetching {last_page} pages of episodes (3 req/sec limit)")

        def fetch_page(page_num):
            try:
                params = {'page': page_num}
                page_response = client.get(url, params=params)
                if page_response:
                    return page_response.json()['data']
                return []
            except Exception as e:
                control.log(f"Jikan: Failed to fetch page {page_num}: {str(e)}")
                return []

        # Split remaining pages into batches of 3 to respect rate limit
        page_numbers = list(range(2, last_page + 1))
        batches = [page_numbers[i:i + 3] for i in range(0, len(page_numbers), 3)]

        all_page_results = []
        for i, batch in enumerate(batches):
            if i > 0:
                time.sleep(1.1)  # Wait 1.1 seconds between batches (safe margin)

            # Fetch 3 pages in parallel (respects 3 req/sec limit)
            batch_results = utils.parallel_process(batch, fetch_page)
            all_page_results.extend(batch_results)

        # Combine all results
        for page_data in all_page_results:
            res_data.extend(page_data)

        control.log(f"Jikan: Fetched {len(res_data)} episodes total")
        return res_data

    @staticmethod
    def parse_episode_view(res, mal_id, season, poster, fanart, clearart, clearlogo, eps_watched, update_time, tvshowtitle, dub_data, filler_data, episodes=None):
        if indexers.should_hide_unaired_episode(res.get('aired', '')):
            return None
        kodi_meta = pickle.loads(database.get_show(mal_id)['kodi_meta'])
        episode = res['mal_id']
        url = f"{mal_id}/{episode}"
        title = res.get('title')
        if not title:
            title = res["episode"]
        image = res['images']['jpg']['image_url'] if res.get('images') else poster
        info = {
            'UniqueIDs': {
                'mal_id': str(mal_id),
                **database.get_unique_ids(mal_id, 'mal_id')
            },
            'title': title,
            'season': season,
            'episode': episode,
            'plot': 'No plot available',
            'tvshowtitle': tvshowtitle,
            'mediatype': 'episode',
            'status': kodi_meta.get('status'),
            'genre': kodi_meta.get('genre'),
            'country': kodi_meta.get('country'),
            'cast': kodi_meta.get('cast'),
            'studio': kodi_meta.get('studio'),
            'mpaa': kodi_meta.get('mpaa'),
        }

        if eps_watched and int(eps_watched) >= episode:
            info['playcount'] = 1

        info['rating'] = control.safe_call(lambda: {'score': float(res['score'])})

        info['aired'] = control.safe_call(lambda: res['aired'][:10])

        filler = control.safe_call(lambda: filler_data[episode - 1], default='')

        parsed = indexers.update_database(mal_id, update_time, res, url, image, info, season, episode, episodes, title, fanart, poster, clearart, clearlogo, dub_data, filler)
        return parsed

    def process_episode_view(self, mal_id, poster, fanart, clearart, clearlogo, eps_watched, tvshowtitle, dub_data, filler_data):
        update_time = datetime.date.today().isoformat()
        result = self.get_anime_info(mal_id)
        if not result:
            return []

        title_list = [name['title'] for name in result['titles']]
        season = utils.get_season(title_list, mal_id)

        result_ep = self.get_episode_meta(mal_id)
        # kodi_episodes = kodi_meta['episodes']
        # if kodi_episodes:
        #     control.print(f"Kodi Episodes: {kodi_episodes}, Jikan Episodes: {len(result_ep)}")
        #     if len(result_ep) != kodi_episodes:
        #         return []

        mapfunc = partial(self.parse_episode_view, mal_id=mal_id, season=season, poster=poster, fanart=fanart, clearart=clearart, clearlogo=clearlogo, eps_watched=eps_watched, update_time=update_time, tvshowtitle=tvshowtitle, dub_data=dub_data, filler_data=filler_data)
        # Parallelize episode parsing for faster processing
        all_results = utils.parallel_process(result_ep, mapfunc)
        all_results = [r for r in all_results if r is not None]
        all_results = sorted(all_results, key=lambda x: x['info']['episode'])

        if control.getBool('override.meta.api') and control.getBool('override.meta.notify'):
            control.notify("Jikanmoe", f'{tvshowtitle} Added to Database', icon=poster)
        return all_results

    def append_episodes(self, mal_id, episodes, eps_watched, poster, fanart, clearart, clearlogo, tvshowtitle, filler_data=None, dub_data=None):
        update_time, diff = indexers.get_diff(episodes[-1])
        if diff > control.getInt('interface.check.updates'):
            result = self.get_episode_meta(mal_id)
            season = episodes[0]['season']
            mapfunc2 = partial(self.parse_episode_view, mal_id=mal_id, season=season, poster=poster, fanart=fanart, clearart=clearart, clearlogo=clearlogo, eps_watched=eps_watched, update_time=update_time, tvshowtitle=tvshowtitle, dub_data=dub_data, filler_data=filler_data, episodes=episodes)
            # Parallelize episode parsing
            all_results = utils.parallel_process(result, mapfunc2)
            all_results = [r for r in all_results if r is not None]
            if control.getBool('override.meta.api') and control.getBool('override.meta.notify'):
                control.notify("Jikanmoe", f'{tvshowtitle} Appended to Database', icon=poster)
        else:
            mapfunc1 = partial(indexers.parse_episodes, eps_watched=eps_watched, dub_data=dub_data)
            # Parallelize episode parsing
            all_results = utils.parallel_process(episodes, mapfunc1)
        return all_results

    def get_episodes(self, mal_id, show_meta):
        kodi_meta = pickle.loads(database.get_show(mal_id)['kodi_meta'])
        kodi_meta.update(pickle.loads(show_meta['art']))
        fanart = kodi_meta.get('fanart')
        poster = kodi_meta.get('poster')
        # Handle clearart - support both string (new) and list (legacy) formats
        clearart = kodi_meta.get('clearart', '')
        if isinstance(clearart, list):
            clearart = random.choice(clearart) if clearart else ''
        # Handle clearlogo - support both string (new) and list (legacy) formats
        clearlogo = kodi_meta.get('clearlogo', '')
        if isinstance(clearlogo, list):
            clearlogo = random.choice(clearlogo) if clearlogo else ''
        tvshowtitle = kodi_meta['title_userPreferred']
        if not (eps_watched := kodi_meta.get('eps_watched')) and control.getBool('interface.watchlist.data'):
            from resources.lib.WatchlistFlavor import WatchlistFlavor
            merged = WatchlistFlavor.get_merged_watchlist_eps_watched(mal_id)
            if merged is not None:
                eps_watched = kodi_meta['eps_watched'] = merged
                database.update_kodi_meta(mal_id, kodi_meta)
        episodes = database.get_episode_list(mal_id)
        dub_data = indexers.process_dub(mal_id, kodi_meta['ename']) if control.getBool('jz.dub') else None
        if episodes:
            if kodi_meta['status'] not in ["FINISHED", "Finished Airing"]:
                from resources.lib.endpoints import anime_filler
                filler_data = anime_filler.get_data(kodi_meta['ename'])
                return self.append_episodes(mal_id, episodes, eps_watched, poster, fanart, clearart, clearlogo, tvshowtitle, filler_data, dub_data)
            return indexers.process_episodes(episodes, eps_watched, dub_data)

        if kodi_meta['episodes'] is None or kodi_meta['episodes'] > 99:
            from resources.lib.endpoints import anime_filler
            filler_data = anime_filler.get_data(kodi_meta['ename'])
        else:
            filler_data = None
        return self.process_episode_view(mal_id, poster, fanart, clearart, clearlogo, eps_watched, tvshowtitle, dub_data, filler_data)

    def get_anime(self, filter_type, page):
        perpage = 25
        params = {
            "limit": perpage,
            "page": page,
            "filter": filter_type
        }
        response = client.get(f'{self.baseUrl}/top/anime', params=params)
        if response:
            return response.json()
