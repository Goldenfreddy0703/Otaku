import pickle
import datetime
import random

from functools import partial
from resources.lib.ui import database, utils, control, client
from resources.lib import indexers


class SIMKLAPI:
    def __init__(self):
        api_info = database.get_info('Simkl')
        self.ClientID = api_info['client_id']
        self.baseUrl = "https://api.simkl.com"
        self.imagePath = "https://wsrv.nl/?url=https://simkl.in/episodes/%s_w.webp"

    def parse_episode_view(self, res, mal_id, season, poster, fanart, clearart, clearlogo, eps_watched, update_time, tvshowtitle, dub_data, filler_data, episodes=None):
        if indexers.should_hide_unaired_episode(res.get('date', '')):
            return None
        kodi_meta = pickle.loads(database.get_show(mal_id)['kodi_meta'])
        episode = int(res['episode'])
        url = f"{mal_id}/{episode}"
        title = res.get('title')
        if not title:
            title = f'Episode {episode}'
        image = self.imagePath % res['img'] if res.get('img') else poster
        info = {
            'UniqueIDs': {
                'mal_id': str(mal_id),
                **database.get_unique_ids(mal_id, 'mal_id')
            },
            'plot': res.get('description', 'No plot available'),
            'title': title,
            'season': season,
            'episode': episode,
            'tvshowtitle': tvshowtitle,
            'mediatype': 'episode',
            'status': kodi_meta.get('status'),
            'genre': kodi_meta.get('genre'),
            'country': kodi_meta.get('country'),
            'cast': kodi_meta.get('cast'),
            'studio': kodi_meta.get('studio'),
            'rating': kodi_meta.get('rating'),
            'mpaa': kodi_meta.get('mpaa'),
        }

        if eps_watched and int(eps_watched) >= episode:
            info['playcount'] = 1

        info['aired'] = control.safe_call(lambda: res['date'][:10])

        filler = control.safe_call(lambda: filler_data[episode - 1], default='')

        parsed = indexers.update_database(mal_id, update_time, res, url, image, info, season, episode, episodes, title, fanart, poster, clearart, clearlogo, dub_data, filler)
        return parsed

    def process_episode_view(self, mal_id, poster, fanart, clearart, clearlogo, eps_watched, tvshowtitle, dub_data, filler_data):
        update_time = datetime.date.today().isoformat()
        result = self.get_anime_info(mal_id)
        if not result:
            return []

        title_list = [name['name'] for name in result.get('alt_titles', [])]
        season = utils.get_season(title_list, mal_id)
        result_meta = self.get_episode_meta(mal_id)

        result_ep = [x for x in result_meta if x['type'] == 'episode']
        # kodi_episodes = kodi_meta['episodes']
        # if kodi_episodes:
        #     control.print(f"Kodi Episodes: {kodi_episodes}, SIMKL Episodes: {len(result_ep)}")
        #     if len(result_ep) != kodi_episodes:
        #         return []

        mapfunc = partial(self.parse_episode_view, mal_id=mal_id, season=season, poster=poster, fanart=fanart, clearart=clearart, clearlogo=clearlogo, eps_watched=eps_watched, update_time=update_time, tvshowtitle=tvshowtitle, dub_data=dub_data, filler_data=filler_data)
        # Parallelize episode parsing for faster processing
        all_results = utils.parallel_process(result_ep, mapfunc, max_workers=8)
        all_results = [r for r in all_results if r is not None]

        if control.getBool('override.meta.api') and control.getBool('override.meta.notify'):
            control.notify("SIMKL", f'{tvshowtitle} Added to Database', icon=poster)
        return all_results

    def append_episodes(self, mal_id, episodes, eps_watched, poster, fanart, clearart, clearlogo, tvshowtitle, dub_data=None):
        update_time, diff = indexers.get_diff(episodes[-1])
        if diff >= control.getInt('interface.check.updates'):
            result_meta = self.get_episode_meta(mal_id)
            result_ep = [x for x in result_meta if x['type'] == 'episode']
            season = episodes[0]['season']
            mapfunc2 = partial(self.parse_episode_view, mal_id=mal_id, season=season, poster=poster, fanart=fanart, clearart=clearart, clearlogo=clearlogo, eps_watched=eps_watched, update_time=update_time, tvshowtitle=tvshowtitle, dub_data=dub_data, filler_data=None, episodes=episodes)
            # Parallelize episode parsing
            all_results = utils.parallel_process(result_ep, mapfunc2, max_workers=8)
            all_results = [r for r in all_results if r is not None]
            if control.getBool('override.meta.api') and control.getBool('override.meta.notify'):
                control.notify("SIMKL Appended", f'{tvshowtitle} Appended to Database', icon=poster)
        else:
            mapfunc1 = partial(indexers.parse_episodes, eps_watched=eps_watched, dub_data=dub_data)
            # Parallelize episode parsing
            all_results = utils.parallel_process(episodes, mapfunc1, max_workers=8)
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
            flavor = WatchlistFlavor.get_first_enabled_flavor()
            if flavor:
                data = flavor.get_watchlist_anime_entry(mal_id)
                if data.get('eps_watched'):
                    eps_watched = kodi_meta['eps_watched'] = data['eps_watched']
                    database.update_kodi_meta(mal_id, kodi_meta)
        episodes = database.get_episode_list(mal_id)
        dub_data = indexers.process_dub(mal_id, kodi_meta['ename']) if control.getBool('jz.dub') else None
        if episodes:
            if kodi_meta['status'] not in ["FINISHED", "Finished Airing"]:
                return self.append_episodes(mal_id, episodes, eps_watched, poster, fanart, clearart, clearlogo, tvshowtitle, dub_data)
            return indexers.process_episodes(episodes, eps_watched, dub_data)
        if kodi_meta['episodes'] is None or kodi_meta['episodes'] > 99:
            from resources.lib.endpoints import anime_filler
            filler_data = anime_filler.get_data(kodi_meta['ename'])
        else:
            filler_data = None
        return self.process_episode_view(mal_id, poster, fanart, clearart, clearlogo, eps_watched, tvshowtitle, dub_data, filler_data)

    def get_anime_info(self, mal_id):
        show_ids = database.get_show(mal_id)
        if not (simkl_id := show_ids['simkl_id']):
            simkl_id = self.get_id('mal', mal_id)
            database.add_mapping_id(mal_id, 'simkl_id', simkl_id)

        params = {
            'extended': 'full',
            'client_id': self.ClientID
        }
        response = client.get(f'{self.baseUrl}/anime/{simkl_id}', params=params)
        if response:
            return response.json()
        return {}

    def get_episode_meta(self, mal_id):
        show_ids = database.get_show(mal_id)
        simkl_id = show_ids['simkl_id']
        if not simkl_id:
            mal_id = show_ids['mal_id']
            simkl_id = self.get_id('mal', mal_id)
            database.add_mapping_id(mal_id, 'simkl_id', simkl_id)
        params = {
            'extended': 'full',
            'client_id': self.ClientID
        }
        response = client.get(f'{self.baseUrl}/anime/episodes/{simkl_id}', params=params)
        if response:
            return response.json()
        return {}

    def get_id(self, send_id, anime_id):
        params = {
            send_id: anime_id,
            "client_id": self.ClientID,
        }
        response = client.get(f'{self.baseUrl}/search/id', params=params)
        if response:
            r = response.json()
            if r:
                anime_id = r[0]['ids']['simkl']
                return anime_id

    def get_mapping_ids_from_simkl(self, anime_id, send_id):
        # Query local database for all available IDs
        meta_ids = database.get_mappings(anime_id, send_id)
        if meta_ids:
            return meta_ids  # Return the full mapping dictionary
        # Fallback to SIMKL API if not found
        simkl_id = self.get_id(send_id, anime_id)
        params = {
            'extended': 'full',
            'client_id': self.ClientID
        }
        response = client.get(f'{self.baseUrl}/anime/{simkl_id}', params=params)
        if response:
            r = response.json()
            if 'ids' in r:
                return r['ids']
            else:
                control.log(f"SIMKLAPI.get_unique_ids: 'ids' not found in response for anime_id {anime_id}", 'warning')
        return {}
