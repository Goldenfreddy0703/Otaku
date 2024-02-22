import itertools
import json
import re
import time

from resources.lib.ui import control, database
from resources.lib.WatchlistFlavor.WatchlistFlavorBase import WatchlistFlavorBase
from six.moves import urllib_parse


class MyAnimeListWLF(WatchlistFlavorBase):
    _URL = "https://api.myanimelist.net/v2"
    _TITLE = "MyAnimeList"
    _NAME = "mal"
    _IMAGE = "myanimelist.png"

    def __headers(self):
        headers = {
            'Authorization': 'Bearer {0}'.format(self._token),
        }
        return headers

    def login(self):
        parsed = urllib_parse.urlparse(self._auth_var)
        params = dict(urllib_parse.parse_qsl(parsed.query))
        code = params.get('code')
        code_verifier = params.get('state')

        oauth_url = 'https://myanimelist.net/v1/oauth2/token'
        data = {
            'client_id': 'a8d85a4106b259b8c9470011ce2f76bc',
            'code': code,
            'code_verifier': code_verifier,
            'grant_type': 'authorization_code'
        }
        r = self._get_request(oauth_url, data=data)
        if not r:
            return
        res = json.loads(r)

        self._token = res['access_token']
        user = self._get_request(self._URL + '/users/@me', headers=self.__headers(), params={'fields': 'name'})
        user = json.loads(user)

        login_data = {
            'token': res['access_token'],
            'refresh': res['refresh_token'],
            'expiry': str(int(time.time()) + int(res['expires_in'])),
            'username': user['name']
        }
        return login_data

    def refresh_token(self):
        oauth_url = 'https://myanimelist.net/v1/oauth2/token'
        data = {
            'client_id': 'a8d85a4106b259b8c9470011ce2f76bc',
            'grant_type': 'refresh_token',
            'refresh_token': control.getSetting('mal.refresh')
        }
        r = self._get_request(oauth_url, data=data)
        res = json.loads(r)
        control.setSetting('mal.token', res['access_token'])
        control.setSetting('mal.refresh', res['refresh_token'])
        control.setSetting('mal.expiry', str(int(time.time()) + int(res['expires_in'])))

    def _handle_paging(self, hasNextPage, base_url, page):
        if not hasNextPage:
            return []
        next_page = page + 1
        name = "Next Page (%d)" % next_page
        offset = (re.compile("offset=(.+?)&").findall(hasNextPage))[0]
        return self._parse_view({'name': name, 'url': '{0}/{1}/{2}'.format(base_url, offset, next_page), 'image': 'next.png', 'info': {}, 'fanart': 'next.png'})

    def __get_sort(self):
        sort_types = {
            "Anime Title": "anime_title",
            "Last Updated": "list_updated_at",
            "Anime Start Date": "anime_start_date",
            "List Score": "list_score"
        }
        return sort_types[self._sort]

    def watchlist(self):
        statuses = [
            ("Next Up", "watching?next_up=true"),
            ("Currently Watching", "watching"),
            ("Completed", "completed"),
            ("On Hold", "on_hold"),
            ("Dropped", "dropped"),
            ("Plan to Watch", "plan_to_watch"),
            ("All Anime", "")
        ]
        all_results = map(self._base_watchlist_view, statuses)
        all_results = list(itertools.chain(*all_results))
        return all_results

    def _base_watchlist_view(self, res):
        base = {
            "name": res[0],
            "url": 'watchlist_status_type/%s/%s' % (self._NAME, res[1]),
            "image": '%s.png' % res[0].lower(),
            "info": {}
        }
        return self._parse_view(base)

    @staticmethod
    def action_statuses():
        actions = [
            ("Add to Currently Watching", "watching"),
            ("Add to Completed", "completed"),
            ("Add to On Hold", "on_hold"),
            ("Add to Dropped", "dropped"),
            ("Add to Plan to Watch", "plan_to_watch"),
            ("Set Score", "set_score"),
            ("Delete", "DELETE")
        ]
        return actions

    def get_watchlist_status(self, status, next_up, offset=0, page=1):
        fields = [
            'alternative_titles',
            'list_status',
            'num_episodes',
            'synopsis',
            'mean',
            'rating',
            'genres',
            'studios',
            'start_date',
            'average_episode_duration',
            'media_type',
            'status'
        ]
        params = {
            "status": status,
            "sort": self.__get_sort(),
            "limit": 100,
            "offset": offset,
            "fields": ','.join(fields),
            "nsfw": 'true'
        }
        url = self._URL + '/users/@me/animelist'
        return self._process_status_view(url, params, next_up, 'watchlist_status_type_pages/mal/{0}'.format(status), page)

    def _process_status_view(self, url, params, next_up, base_plugin_url, page):
        r = self._get_request(url, headers=self.__headers(), params=params)
        if r:
            results = json.loads(r)
        else:
            if control.getSetting('mal.hidenotif') == 'false':
                control.ok_dialog(control.ADDON_NAME, "Can't connect MyAnimeList 'API'")
                return []

        if next_up:
            all_results = filter(lambda x: True if x else False, map(self._base_next_up_view, results['data']))
        else:
            all_results = map(self._base_watchlist_status_view, results['data'])
        all_results = list(itertools.chain(*all_results))

        all_results += self._handle_paging(results['paging'].get('next'), base_plugin_url, page)
        return all_results

    def _base_watchlist_status_view(self, res):
        mal_id = res['node']['id']
        anilist_id = ''
        kitsu_id = ''

        show = database.get_show_mal(mal_id)
        if show:
            anilist_id = show.get('anilist_id')
            kitsu_id = show.get('kitsu_id')

        title = res['node'].get('title')
        if self._title_lang == 'english':
            title = res['node']['alternative_titles'].get('en') or title

        info = {
            'title': title,
            'plot': res['node']['synopsis'],
            'rating': res['node'].get('mean'),
            'duration': res['node']['average_episode_duration'],
            'genre': [x.get('name') for x in res['node']['genres']],
            'status': res['node']['status'],
            'mpaa': res['node'].get('rating'),
            'mediatype': 'tvshow',
            'studio': [x.get('name') for x in res['node']['studios']],
        }

        try:
            start_date = res['node']['start_date']
            info['premiered'] = start_date
            info['year'] = int(start_date[:4])
        except KeyError:
            pass

        if res['node']["num_episodes"] != 0 and res['list_status']["num_episodes_watched"] == res['node']["num_episodes"]:
            info['playcount'] = 1

        base = {
            "name": '%s - %d/%d' % (title, res['list_status']["num_episodes_watched"], res['node']["num_episodes"]),
            "url": 'watchlist_to_ep/{0}/{1}/{2}/{3}'.format(anilist_id, mal_id, kitsu_id, res["list_status"]["num_episodes_watched"]),
            "image": res['node']['main_picture'].get('large', res['node']['main_picture']['medium']),
            "info": info
        }

        if res['node']['media_type'] == 'movie' and res['node']["num_episodes"] == 1:
            base['url'] = 'play_movie/{0}/{1}/{2}'.format(anilist_id, mal_id, kitsu_id)
            base['info']['mediatype'] = 'movie'
            return self._parse_view(base, False)
        return self._parse_view(base)

    def _base_next_up_view(self, res):
        mal_id = res['node']['id']
        kitsu_id = ''

        progress = res['list_status']["num_episodes_watched"]
        next_up = progress + 1
        episode_count = res['node']["num_episodes"]

        if 0 < episode_count < next_up:
            return None

        base_title = res['node'].get('title')
        if self._title_lang == 'english':
            base_title = res['node']['alternative_titles'].get('en') or base_title

        title = '%s - %s/%s' % (base_title, next_up, episode_count)
        poster = image = res['node']['main_picture'].get('large', res['node']['main_picture']['medium'])
        plot = aired = None
        anilist_id, next_up_meta, show = self._get_next_up_meta(mal_id, int(progress))
        if next_up_meta:
            url = 'play/%d/%d/' % (anilist_id, next_up)
            if next_up_meta.get('title'):
                title = '%s - %s' % (title, next_up_meta['title'])
            if next_up_meta.get('image'):
                image = next_up_meta['image']
            plot = next_up_meta.get('plot')
            aired = next_up_meta.get('aired')

        info = {
            'episode': next_up,
            'title': title,
            'tvshowtitle': base_title,
            'duration': res['node']['average_episode_duration'],
            'plot': plot,
            'mediatype': 'episode',
            'aired': aired
        }

        base = {
            "name": title,
            "url": 'watchlist_to_ep/{0}/{1}/{2}/{3}'.format(anilist_id, mal_id, kitsu_id, res["list_status"]["num_episodes_watched"]),
            "image": image,
            "info": info,
            "fanart": image,
            "poster": poster
        }

        if res['node']['media_type'] == 'movie' and res['node']["num_episodes"] == 1:
            base['url'] = 'play_movie/{0}/{1}/{2}'.format(anilist_id, mal_id, kitsu_id)
            base['info']['mediatype'] = 'movie'
            return self._parse_view(base, False)

        if next_up_meta:
            base['url'] = url
            return self._parse_view(base, False)

        return self._parse_view(base)

    def get_watchlist_anime_entry(self, anilist_id):
        mal_id = self._get_mapping_id(anilist_id, 'mal_id')

        if not mal_id:
            return

        params = {
            "fields": 'my_list_status'
        }

        url = '{0}/anime/{1}'.format(self._URL, mal_id)
        r = self._get_request(url, headers=self.__headers(), params=params)
        results = json.loads(r)['my_list_status']
        if not results:
            return {}
        anime_entry = {
            'eps_watched': results['num_episodes_watched'],
            'status': results['status'],
            'score': results['score']
        }
        return anime_entry

    def update_list_status(self, anilist_id, status):
        mal_id = self._get_mapping_id(anilist_id, 'mal_id')
        if not mal_id:
            return False
        data = {
            "status": status,
        }
        r = self._put_request('{0}/anime/{1}/my_list_status'.format(self._URL, mal_id), headers=self.__headers(), data=data)
        return r != ''

    def update_num_episodes(self, anilist_id, episode):
        mal_id = self._get_mapping_id(anilist_id, 'mal_id')
        if not mal_id:
            return False
        data = {
            'num_watched_episodes': int(episode)
        }
        r = self._put_request('{0}/anime/{1}/my_list_status'.format(self._URL, mal_id), headers=self.__headers(), data=data)
        return r != ''

    def update_score(self, anilist_id, score):
        mal_id = self._get_mapping_id(anilist_id, 'mal_id')
        if not mal_id:
            return False
        data = {
            "score": score,
        }
        r = self._put_request('{0}/anime/{1}/my_list_status'.format(self._URL, mal_id), headers=self.__headers(), data=data)
        return r != ''

    def delete_anime(self, anilist_id):
        mal_id = self._get_mapping_id(anilist_id, 'mal_id')
        if not mal_id:
            return False
        r = self._delete_request('{0}/anime/{1}/my_list_status'.format(self._URL, mal_id), headers=self.__headers())
        return r != ''
