import pickle
import datetime
import random

from functools import partial
from resources.lib.ui import database, control, client, utils
from resources.lib import indexers


class ANIZIPAPI:
    def __init__(self):
        self.baseUrl = "https://api.ani.zip"

    def get_anime_info(self, mal_id):
        params = {
            'mal_id': mal_id
        }
        response = client.get(f'{self.baseUrl}/mappings', params=params)
        if response:
            return response.json()

    @staticmethod
    def parse_episode_view(res, mal_id, season, poster, fanart, clearart, clearlogo, eps_watched, update_time, tvshowtitle, dub_data, filler_data, episodes=None):
        if indexers.should_hide_unaired_episode(res.get('airDate', '')):
            return None
        kodi_meta = pickle.loads(database.get_show(mal_id)['kodi_meta'])
        episode = int(res['episode'])
        url = f"{mal_id}/{episode}"
        title = res['title']['en']
        if not title:
            title = f'Episode {episode}'
        image = res['image'] if res.get('image') else poster
        info = {
            'UniqueIDs': {
                'mal_id': str(mal_id),
                **database.get_unique_ids(mal_id, 'mal_id')
            },
            'plot': res.get('overview', 'No plot available'),
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
            'mpaa': kodi_meta.get('mpaa'),
        }

        if eps_watched and int(eps_watched) >= episode:
            info['playcount'] = 1

        try:
            info['rating'] = {'score': float(res['rating'])}
        except KeyError:
            pass

        try:
            info['aired'] = res['airDate'][:10]
        except KeyError:
            pass

        try:
            filler = filler_data[episode - 1]
        except (IndexError, TypeError):
            filler = ''

        anidb_ep_id = res.get('anidbEid')

        parsed = indexers.update_database(mal_id, update_time, res, url, image, info, season, episode, episodes, title, fanart, poster, clearart, clearlogo, dub_data, filler, anidb_ep_id)
        return parsed

    def process_episode_view(self, mal_id, poster, fanart, clearart, clearlogo, eps_watched, tvshowtitle, dub_data, filler_data):
        update_time = datetime.date.today().isoformat()
        result = self.get_anime_info(mal_id)
        if not result:
            return []

        result_ep = [result['episodes'][res] for res in result['episodes'] if res.isdigit()]
        # kodi_episodes = kodi_meta['episodes']
        # if kodi_episodes:
        #     control.print(f"Kodi Episodes: {kodi_episodes}, ANIZIP Episodes: {len(result_ep)}")
        #     if len(result_ep) != kodi_episodes:
        #         return []

        if not result_ep:
            return []

        season = result_ep[0].get('seasonNumber', 1)
        mapfunc = partial(self.parse_episode_view, mal_id=mal_id, season=season, poster=poster, fanart=fanart, clearart=clearart, clearlogo=clearlogo, eps_watched=eps_watched, update_time=update_time, tvshowtitle=tvshowtitle, dub_data=dub_data, filler_data=filler_data)
        # Parallelize episode parsing for faster processing
        all_results = utils.parallel_process(result_ep, mapfunc, max_workers=8)
        all_results = [r for r in all_results if r is not None]

        if control.getBool('override.meta.api') and control.getBool('override.meta.notify'):
            control.notify("Anizip", f'{tvshowtitle} Added to Database', icon=poster)
        return all_results

    def append_episodes(self, mal_id, episodes, eps_watched, poster, fanart, clearart, clearlogo, tvshowtitle, dub_data=None):
        update_time, diff = indexers.get_diff(episodes[-1])
        if diff > control.getInt('interface.check.updates'):
            result = self.get_anime_info(mal_id)
            result_ep = [result['episodes'][res] for res in result['episodes'] if res.isdigit()]
            season = episodes[0]['season']
            mapfunc2 = partial(self.parse_episode_view, mal_id=mal_id, season=season, poster=poster, fanart=fanart, clearart=clearart, clearlogo=clearlogo, eps_watched=eps_watched, update_time=update_time, tvshowtitle=tvshowtitle, dub_data=dub_data, filler_data=None, episodes=episodes)
            # Parallelize episode parsing
            all_results = utils.parallel_process(result_ep, mapfunc2, max_workers=8)
            all_results = [r for r in all_results if r is not None]
            if control.getBool('override.meta.api') and control.getBool('override.meta.notify'):
                control.notify("ANIZIP Appended", f'{tvshowtitle} Appended to Database', icon=poster)
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
            flavor = WatchlistFlavor.get_update_flavor()
            if flavor and flavor.flavor_name in control.enabled_watchlists():
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
