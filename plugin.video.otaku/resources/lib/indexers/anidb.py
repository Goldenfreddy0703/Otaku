import pickle
import datetime
import xml.etree.ElementTree as ET
import random

from functools import partial
from resources.lib.ui import client, database, control, utils
from resources.lib import indexers


class ANIDBAPI:
    def __init__(self):
        api_info = database.get_info('AniDB')
        self.client_name = api_info['client_id']
        self.base_url = 'http://api.anidb.net:9001/httpapi'

    def get_anidb_id(self, mal_id):
        meta_ids = database.get_mappings(mal_id, 'mal_id')
        return meta_ids.get('anidb_id')

    def get_episode_meta(self, mal_id):
        import time
        anidb_id = self.get_anidb_id(mal_id)
        # Use Kodi settings for persistent rate limiting
        last_request = control.getInt('anidb_last_request')
        now = int(time.time())
        if last_request > 0:
            elapsed = now - last_request
            if elapsed < 4:
                time.sleep(4 - elapsed)
        params = {
            'request': 'anime',
            'client': self.client_name,
            'clientver': 1,
            'protover': 1,
            'aid': anidb_id
        }
        response = client.get(self.base_url, params=params)
        control.setInt('anidb_last_request', int(time.time()))
        alt_titles = []
        episodes = []
        if response:
            root = ET.fromstring(response.text)
            # Parse the <titles> element for alternative titles.
            titles_elem = root.find('titles')
            if titles_elem is not None:
                for title in titles_elem.findall('title'):
                    if title.text:
                        alt_titles.append({'name': title.text})
            # Parse episodes.
            for ep in root.findall('.//episode'):
                epno_text = ep.find('epno').text
                if epno_text is None:
                    continue
                try:
                    episode_num = int(epno_text)
                except ValueError:
                    continue
                # Get the English title if available; fallback to default.
                title_elem = ep.find("title[@{http://www.w3.org/XML/1998/namespace}lang='en']")
                title_val = title_elem.text if title_elem is not None else f"Episode {episode_num}"
                # Within your get_episode_meta function, in the episode parsing loop:
                rating_elem = ep.find('rating')
                if rating_elem is not None:
                    rating_val = rating_elem.text
                    votes_val = rating_elem.get('votes')
                else:
                    rating_val = None
                    votes_val = None
                episodes.append({
                    'type': 'episode',
                    'episode': episode_num,
                    'anidb_id': ep.get('id'),
                    'title': title_val,
                    'airdate': ep.find('airdate').text if ep.find('airdate') is not None else '',
                    'summary': ep.find('summary').text if ep.find('summary') is not None else '',
                    'rating': rating_val,
                    'votes': votes_val,
                })
        return {'alt_titles': alt_titles, 'episodes': episodes}

    @staticmethod
    def parse_episode_view(res, mal_id, season, poster, fanart, clearart, clearlogo, eps_watched, update_time, tvshowtitle, dub_data, filler_data, episodes=None):
        if indexers.should_hide_unaired_episode(res.get('airdate', '')):
            return None
        kodi_meta = pickle.loads(database.get_show(mal_id)['kodi_meta'])
        episode = res['episode']
        url = f"{mal_id}/{episode}"
        title = res.get('title', f"Episode {episode}")
        image = poster  # AniDB does not provide an image URL so fallback to poster.
        info = {
            'UniqueIDs': {
                'mal_id': str(mal_id),
                **database.get_unique_ids(mal_id, 'mal_id')
            },
            'plot': res.get('summary', 'No plot available'),
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

        score = res.get('rating')
        votes = res.get('votes')
        info['rating'] = {
            'score': float(score) if score else 0,
            'votes': int(votes) if votes else 0,
        }

        if eps_watched and int(eps_watched) >= episode:
            info['playcount'] = 1

        if res.get('airdate'):
            info['aired'] = control.safe_call(lambda: res.get('airdate')[:10])

        filler = control.safe_call(lambda: filler_data[episode - 1], default='')

        anidb_ep_id = res.get('anidb_id')

        parsed = indexers.update_database(mal_id, update_time, res, url, image, info, season, episode, episodes, title, fanart, poster, clearart, clearlogo, dub_data, filler, anidb_ep_id)
        return parsed

    def process_episode_view(self, mal_id, poster, fanart, clearart, clearlogo, eps_watched, tvshowtitle, dub_data, filler_data):
        anidb_id = self.get_anidb_id(mal_id)
        if not anidb_id:
            return []

        update_time = datetime.date.today().isoformat()
        result = self.get_episode_meta(mal_id)
        # Ensure we have episodes to process.
        if not result or not result['episodes']:
            return []

        # Use alt_titles parsed from XML to build a list of names.
        title_list = [name['name'] for name in result.get('alt_titles', [])]
        season = utils.get_season(title_list, mal_id)

        result_ep = result['episodes']
        mapfunc = partial(self.parse_episode_view, mal_id=mal_id, season=season, poster=poster, fanart=fanart, clearart=clearart, clearlogo=clearlogo, eps_watched=eps_watched, update_time=update_time, tvshowtitle=tvshowtitle, dub_data=dub_data, filler_data=filler_data)
        # Parallelize episode parsing for faster processing
        all_results = utils.parallel_process(result_ep, mapfunc, max_workers=8)
        all_results = [r for r in all_results if r is not None]
        all_results = sorted(all_results, key=lambda x: x['info']['episode'])

        if control.getBool('override.meta.api') and control.getBool('override.meta.notify'):
            control.notify("AniDB", f'{tvshowtitle} Added to Database', icon=poster)
        return all_results

    def append_episodes(self, mal_id, episodes, eps_watched, poster, fanart, clearart, clearlogo, tvshowtitle, dub_data=None, filler_data=None):
        anidb_id = self.get_anidb_id(mal_id)
        if not anidb_id:
            return []

        update_time, diff = indexers.get_diff(episodes[-1])
        if diff > control.getInt('interface.check.updates'):
            result = self.get_episode_meta(mal_id)
            season = episodes[0]['season']
            mapfunc2 = partial(self.parse_episode_view, mal_id=mal_id, season=season, poster=poster, fanart=fanart, clearart=clearart, clearlogo=clearlogo, eps_watched=eps_watched, update_time=update_time, tvshowtitle=tvshowtitle, dub_data=dub_data, filler_data=filler_data, episodes=episodes)
            # Parallelize episode parsing
            all_results = utils.parallel_process(result['episodes'], mapfunc2, max_workers=8)
            all_results = [r for r in all_results if r is not None]
            if control.getBool('override.meta.api') and control.getBool('override.meta.notify'):
                control.notify("AniDB", f'{tvshowtitle} Appended to Database', icon=poster)
        else:
            mapfunc1 = partial(indexers.parse_episodes, eps_watched=eps_watched, dub_data=dub_data)
            # Parallelize episode parsing
            all_results = utils.parallel_process(episodes, mapfunc1, max_workers=8)
        return all_results

    def get_episodes(self, mal_id, show_meta):
        anidb_id = self.get_anidb_id(mal_id)
        if not anidb_id:
            return []

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
