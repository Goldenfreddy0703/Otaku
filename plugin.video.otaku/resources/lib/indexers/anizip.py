import json
import pickle
import random
import time

from functools import partial
from resources.lib.ui import utils, database, control, client
from resources.lib.indexers.syncurl import SyncUrl


class ANIZIPAPI:

    def __init__(self):
        self.baseUrl = "https://api.ani.zip/mappings"

    def get_anime_info(self, anilist_id):
        params = {
            'anilist_id': anilist_id
        }
        r = database.get(client.request, 1, self.baseUrl, params=params)
        if r:
            res = json.loads(r)
            return res

    @staticmethod
    def parse_episode_view(res, anilist_id, season, poster, fanart, eps_watched, update_time, tvshowtitle, filter_lang, title_disable):
        episode = int(res.get("episode", res['episode']))

        url = "%s/%s/" % (anilist_id, episode)

        if isinstance(fanart, list):
            fanart = random.choice(fanart)
        if filter_lang:
            url += filter_lang

        title = res['title']['en']
        if not title:
            title = 'Episode {}'.format(episode)

        image = res['image'] if res.get('image') else poster

        info = {
            'plot': res.get('summary'),
            'title': title,
            'season': season,
            'episode': episode,
            'tvshowtitle': tvshowtitle,
            'mediatype': 'episode',
            'rating': float(res.get('rating', 0))
        }
        if eps_watched:
            if int(eps_watched) >= episode:
                info['playcount'] = 1

        try:
            info['aired'] = res['airDate'][:10]
        except KeyError:
            pass

        parsed = utils.allocate_item(title, "play/%s" % url, False, image, info, fanart, poster)
        database._update_episode(anilist_id, season=season, number=res['episode'], update_time=update_time, kodi_meta=parsed)
    
        if title_disable and info.get('playcount') != 1:
            parsed['info']['title'] = 'Episode {}'.format(episode)
            parsed['info']['plot'] = None

        return parsed

    def process_episode_view(self, anilist_id, poster, fanart, eps_watched, tvshowtitle, filter_lang, title_disable):
        from datetime import date
        update_time = date.today().isoformat()

        result = self.get_anime_info(anilist_id)
        if not result:
            return []

        s_id = database.get_tvdb_season(anilist_id)
        if not s_id:
            sync_data = SyncUrl().get_anime_data(anilist_id, 'Anilist')
            s_id = utils.get_season(sync_data[0]) if sync_data else None
        if isinstance(s_id, list) and s_id:
            season = s_id[0]
        elif isinstance(s_id, int):
            season = s_id
        else:
            season = 1

        season = int(season)
        database._update_season(anilist_id, season)

        result_ep = [result['episodes'][res] for res in result['episodes'] if res.isdigit()]

        mapfunc = partial(self.parse_episode_view, anilist_id=anilist_id, season=season, poster=poster, fanart=fanart,
                          eps_watched=eps_watched, filter_lang=filter_lang, update_time=update_time, tvshowtitle=tvshowtitle, title_disable=title_disable)

        all_results = list(map(mapfunc, result_ep))
        if control.getSetting('general.unaired.episodes') == 'true':
            total_ep = result.get('total_episodes', 0)
            empty_ep = []
            for ep in range(len(all_results) + 1, total_ep + 1):
                empty_ep.append({
                    'title': 'Episode {}'.format(ep),
                    'episode': ep,
                    'image': poster
                })
            mapfunc_emp = partial(self.parse_episode_view, anilist_id=anilist_id, season=season, poster=poster,
                                  fanart=fanart, eps_watched=eps_watched, filter_lang=filter_lang, update_time=update_time,
                                  tvshowtitle=tvshowtitle, title_disable=title_disable)
            all_results += list(map(mapfunc_emp, empty_ep))

        return all_results

    def append_episodes(self, anilist_id, episodes, eps_watched, poster, fanart, tvshowtitle, filter_lang, title_disable=False):
        import datetime
        update_time = datetime.date.today().isoformat()

        last_updated = datetime.datetime(*(time.strptime(episodes[0]['last_updated'], "%Y-%m-%d")[0:6]))

        diff = (datetime.datetime.today() - last_updated).days
        if diff > 3:
            result = self.get_anime_info(anilist_id)
            result_ep = [result['episodes'][res] for res in result['episodes'] if res.isdigit()]
        else:
            result_ep = []
        if len(result_ep) > len(episodes):
            season = database.get_season_list(anilist_id)['season']
            mapfunc2 = partial(self.parse_episode_view, anilist_id=anilist_id, season=season, poster=poster, fanart=fanart,
                               eps_watched=eps_watched, update_time=update_time, tvshowtitle=tvshowtitle, filter_lang=filter_lang, title_disable=title_disable)
            all_results = list(map(mapfunc2, result_ep))
        else:
            mapfunc1 = partial(self._parse_episodes, eps_watched=eps_watched, title_disable=title_disable)
            all_results = list(map(mapfunc1, episodes))
        return all_results

    @staticmethod
    def _parse_episodes(res, eps_watched, title_disable):
        parsed = pickle.loads(res['kodi_meta'])

        try:
            if int(eps_watched) >= res['number']:
                parsed['info']['playcount'] = 1
        except:
            pass

        if title_disable and parsed['info'].get('playcount') != 1:
            parsed['info']['title'] = 'Episode %s' % res["number"]
            parsed['info']['plot'] = "None"

        return parsed

    def _process_episodes(self, episodes, eps_watched, title_disable=False):
        mapfunc = partial(self._parse_episodes, eps_watched=eps_watched, title_disable=title_disable)
        all_results = list(map(mapfunc, episodes))
        return all_results

    def get_episodes(self, anilist_id, filter_lang):
        kodi_meta = pickle.loads(database.get_show(anilist_id)['kodi_meta'])
        show_meta = database.get_show_meta(anilist_id)

        if show_meta:
            kodi_meta.update(pickle.loads(show_meta.get('art')))

        fanart = kodi_meta.get('fanart')
        poster = kodi_meta.get('poster')
        tvshowtitle = kodi_meta['title_userPreferred']
        eps_watched = kodi_meta.get('eps_watched')
        episodes = database.get_episode_list(anilist_id)

        tvshowtitle = kodi_meta['title_userPreferred']

        title_disable = control.getSetting('general.spoilers') == 'true'
        if episodes:
            if kodi_meta['status'] != "FINISHED":
                return self.append_episodes(anilist_id, episodes, eps_watched, poster, fanart, tvshowtitle, filter_lang, title_disable), 'episodes'
            return self._process_episodes(episodes, eps_watched, title_disable), 'episodes'
        return self.process_episode_view(anilist_id, poster, fanart, eps_watched, tvshowtitle, filter_lang, title_disable), 'episodes'