import datetime
import json
import pickle
import random

from resources.lib import pages
from resources.lib.indexers import simkl, trakt, consumet, enime
from resources.lib.ui import client, control, database, utils
from resources.lib.ui.BrowserBase import BrowserBase


class OtakuBrowser(BrowserBase):

    def _parse_history_view(self, res):
        name = res
        return utils.allocate_item(name, "search/%s/1" % name, True)

    def search_history(self, search_array):
        result = list(map(self._parse_history_view, search_array))
        result.insert(0, utils.allocate_item("New Search", "search", True, 'new_search.png'))
        result.insert(len(result), utils.allocate_item("Clear Search History...", "clear_history", True, 'clear_search_history.png'))
        return result

    def _parse_history_view_movie(self, res):
        name = res
        return utils.allocate_item(name, "search_movie/%s/1" % name, True)

    def search_history_movie(self, search_array):
        result = list(map(self._parse_history_view_movie, search_array))
        result.insert(0, utils.allocate_item("New Search", "search_movie", True, 'new_search.png'))
        result.insert(len(result), utils.allocate_item("Clear Search History...", "clear_history_movie", True, 'clear_search_history.png'))
        return result

    def _parse_history_view_tv(self, res):
        name = res
        return utils.allocate_item(name, "search_tv/%s/1" % name, True)

    def search_history_tv(self, search_array):
        result = list(map(self._parse_history_view_tv, search_array))
        result.insert(0, utils.allocate_item("New Search", "search_tv", True, 'new_search.png'))
        result.insert(len(result), utils.allocate_item("Clear Search History...", "clear_history_tv", True, 'clear_search_history.png'))
        return result

    def get_backup(self, anilist_id, source):
        show = database.get_show(anilist_id)
        mal_id = show['mal_id']

        if not mal_id:
            mal_id = self.get_mal_id(anilist_id)
            database.add_mapping_id(anilist_id, 'mal_id', str(mal_id))

        result = client.request("https://arm2.vercel.app/api/kaito-b?type=myanimelist&id={}".format(mal_id))
        if result:
            result = json.loads(result)
            result = result.get('Pages', {}).get(source, {})
        return result

    def get_mal_id(self, anilist_id):
        arm_resp = client.request("https://armkai.vercel.app/api/search?type=anilist&id={}".format(anilist_id))
        arm_resp = json.loads(arm_resp)
        mal_id = arm_resp["mal"]
        return mal_id

    def search_trakt_shows(self, anilist_id):
        shows = trakt.TRAKTAPI().search_trakt_shows(anilist_id)
        return shows

    def get_trakt_episodes(self, show_id, season, page=1):
        return trakt.TRAKTAPI().get_trakt_episodes(show_id, season)

    def get_anime_trakt(self, anilist_id, db_correction=False, filter_lang=None):
        anime = trakt.TRAKTAPI().get_anime(anilist_id, db_correction)

        if anime and filter_lang:
            anime1 = anime[0][0] if isinstance(anime[0], tuple) else anime[0]
            for i in anime1:
                i['url'] += filter_lang

        if not anime:
            anime = self.get_anime_simkl(anilist_id, filter_lang)

        return anime

    def get_anime_simkl(self, anilist_id, params):
        return simkl.SIMKLAPI().get_anime(anilist_id, params)

    def get_anime_init(self, anilist_id, filter_lang=None):
        show = database.get_show(anilist_id)
        if not show:
            from resources.lib.AniListBrowser import AniListBrowser
            show = AniListBrowser().get_anilist(anilist_id)

        # show_meta = database.get_show_meta(anilist_id)
        # if not show_meta:
        #     kodi_meta = pickle.loads(show['kodi_meta'])
        #     name = kodi_meta['ename'] or kodi_meta['name']
        #     mtype = 'movie' if kodi_meta.get('format') == 'MOVIE' else 'tv'
        #     trakt_id = trakt.TRAKTAPI().get_trakt_id(name, mtype=mtype)
        #     if trakt_id:
        #         database.add_meta_ids(anilist_id, trakt_id)
        # else:
        #     trakt_id = pickle.loads(show_meta.get('meta_ids'))

        # kodi_meta = pickle.loads(show.get('kodi_meta'))
        # title = kodi_meta.get('ename') or kodi_meta.get('name')
        # p = re.search(r'(?:part|cour)\s*\d', title, re.I)
        # if not trakt_id or p:
        # if not trakt_id:
        override_ep = control.getSetting("override.episode.bool")
        if override_ep:
            selected_api = control.getSetting("override.episode.menu")
            if selected_api == "Consumet":
                data = consumet.CONSUMETAPI().get_episodes(anilist_id, filter_lang=filter_lang)
            elif selected_api == "Enime":
                data = enime.ENIMEAPI().get_episodes(anilist_id, filter_lang=filter_lang)
            elif selected_api == "Simkl":
                data = self.get_anime_simkl(anilist_id, filter_lang)
            else:
                data = ([], 'episodes')
        else:
            data = ([], 'episodes')
            # if show_meta:
            data = consumet.CONSUMETAPI().get_episodes(anilist_id, filter_lang=filter_lang)

            if not data[0]:
                data = enime.ENIMEAPI().get_episodes(anilist_id, filter_lang=filter_lang)

            if not data[0]:
                data = self.get_anime_simkl(anilist_id, filter_lang)

        return data

    def get_episodeList(self, show_id, pass_idx, filter_lang=None, rescrape=False, source_select=False):
        show = database.get_show(show_id)
        episodes = database.get_episode_list(int(show_id))

        if episodes:
            if show['simkl_id']:
                items = simkl.SIMKLAPI().get_episodes(show_id)
            else:
                items = consumet.CONSUMETAPI()._process_episodes(show_id, episodes, '')
            if not items:
                items = enime.ENIMEAPI()._process_episodes(show_id, episodes, '')
        else:
            items = consumet.CONSUMETAPI()._process_episodes(show_id, episodes, '')
            if not items:
                items = enime.ENIMEAPI()._process_episodes(show_id, episodes, '')

        if rescrape or source_select:
            return items

        # items = [i for i in items if self.is_aired(i['info'])]
        show_meta = database.get_show_meta(show_id)
        show_art = pickle.loads(show_meta.get('art'))
        eitems = []
        for i in items:
            if self.is_aired(i['info']):
                addl_art = {}
                if show_art.get('clearart'):
                    addl_art.update({'clearart': random.choice(show_art['clearart'])})
                if show_art.get('clearlogo'):
                    addl_art.update({'clearlogo': random.choice(show_art['clearlogo'])})
                i['image'].update(addl_art)
                eitems.append(i)

        playlist = control.bulk_draw_items(eitems)[pass_idx:]
        if len(playlist) > int(control.getSetting('general.playlist_length')):
            playlist = playlist[:int(control.getSetting('general.playlist_length'))]

        for i in playlist:
            url = i[0]

            if filter_lang:
                url += filter_lang

            control.playList.add(url=url, listitem=i[1])

    def is_aired(self, info):
        try:
            try:
                air_date = info['aired']
                if air_date == '':
                    return True
            except:
                air_date = info.get('premiered')
            if not air_date:
                return False
            if int(air_date[:4]) < 2022:
                return True

            todays_date = datetime.datetime.today().strftime('%Y-%m-%d')

            if air_date > todays_date:
                return False
            else:
                return True
        except:
            import traceback
            traceback.print_exc()
            # Assume an item is not aired if we do not have any information on it or fail to identify
            return False

    def get_sources(self, anilist_id, episode, filter_lang, media_type, rescrape=False):
        show = database.get_show(anilist_id)
        kodi_meta = pickle.loads(show['kodi_meta'])
        actionArgs = {
            'query': kodi_meta['query'],
            'anilist_id': anilist_id,
            'episode': episode,
            'status': kodi_meta['status'],
            'filter_lang': filter_lang,
            'media_type': media_type,
            'rescrape': rescrape,
            'get_backup': self.get_backup,
            'duration': kodi_meta['duration']
        }
        sources = pages.getSourcesHelper(actionArgs)
        return sources
