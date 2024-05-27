import itertools
import json
import time

from resources.lib.ui import control, database
from resources.lib.WatchlistFlavor.WatchlistFlavorBase import WatchlistFlavorBase
from resources.lib.indexers.simkl import SIMKLAPI
from six.moves import urllib_parse


class KitsuWLF(WatchlistFlavorBase):
    _URL = "https://kitsu.io/api"
    _TITLE = "Kitsu"
    _NAME = "kitsu"
    _IMAGE = "kitsu.png"
    _mapping = None

    def __headers(self):
        headers = {
            'Content-Type': 'application/vnd.api+json',
            'Accept': 'application/vnd.api+json',
            'Authorization': 'Bearer {0}'.format(self._token)
        }
        return headers

    def login(self):
        params = {
            "grant_type": "password",
            "username": self._auth_var,
            "password": self._password
        }
        resp = self._post_request(self._URL + '/oauth/token', json=params)

        data = json.loads(resp)
        self._token = data.get('access_token')
        if not self._token:
            return

        resp2 = self._get_request(self._URL + '/edge/users', headers=self.__headers(), params={'filter[self]': True})
        data2 = json.loads(resp2)["data"][0]

        login_data = {
            'username': data2["attributes"]["name"],
            'userid': data2['id'],
            'token': data['access_token'],
            'refresh': data['refresh_token'],
            'expiry': str(int(time.time()) + int(data['expires_in']))
        }
        return login_data

    def refresh_token(self):
        params = {
            "grant_type": "refresh_token",
            "refresh_token": control.getSetting('kitsu.refresh')
        }
        resp = self._post_request(self._URL + '/oauth/token', json=params)

        if not resp:
            return

        data = json.loads(resp)
        control.setSetting('kitsu.token', data['access_token'])
        control.setSetting('kitsu.refresh', data['refresh_token'])
        control.setSetting('kitsu.expiry', str(int(time.time()) + int(data['expires_in'])))

    def _handle_paging(self, hasNextPage, base_url, page):
        if not hasNextPage:
            return []
        next_page = page + 1
        name = "Next Page (%d)" % next_page
        parsed = urllib_parse.urlparse(hasNextPage)
        offset = urllib_parse.parse_qs(parsed.query)['page[offset]'][0]
        return self._parse_view({'name': name, 'url': '{0}/{1}/{2}'.format(base_url, offset, next_page), 'image': 'next.png', 'info': {}, 'fanart': 'next.png'})

    def __get_sort(self):
        sort_types = {
            "Date Updated": "-progressed_at",
            "Progress": "-progress",
            "Title": "anime.titles." + self.__get_title_lang(),
        }
        return sort_types[self._sort]

    def __get_title_lang(self):
        title_langs = {
            "Canonical": "canonical",
            "English": "en",
            "Romanized": "en_jp",
        }
        return title_langs[self._title_lang]

    def watchlist(self):
        statuses = [
            ("Next Up", "current?next_up=true"),
            ("Currently Watching", "current"),
            ("Want to Watch", "planned"),
            ("Completed", "completed"),
            ("On Hold", "on_hold"),
            ("Dropped", "dropped")
        ]
        all_results = map(self._base_watchlist_status_view, statuses)
        all_results = list(itertools.chain(*all_results))
        return all_results

    def _base_watchlist_status_view(self, res):
        base = {
            "name": res[0],
            "url": 'watchlist_status_type/%s/%s' % (self._NAME, res[1]),
            "image": '{0}.png'.format(res[0].lower()),
            'info': {}
        }
        return self._parse_view(base)

    @staticmethod
    def action_statuses():
        actions = [
            ("Add to Currently Watching", "current"),
            ("Add to Want to Watch", "planned"),
            ("Add to Completed", "completed"),
            ("Add to On Hold", "on_hold"),
            ("Add to Dropped", "dropped"),
            ("Set Score", "set_score"),
            ("Delete", "DELETE")
        ]
        return actions

    def get_watchlist_status(self, status, next_up, offset=0, page=1):
        url = self._URL + '/edge/library-entries'
        params = {
            "fields[anime]": "titles,canonicalTitle,posterImage,episodeCount,synopsis,episodeLength,subtype,averageRating,ageRating,youtubeVideoId",
            "filter[user_id]": self._user_id,
            "filter[kind]": "anime",
            "filter[status]": status,
            "include": "anime,anime.mappings,anime.mappings.item",
            "page[limit]": "50",
            "page[offset]": offset,
            "sort": self.__get_sort(),
        }
        return self._process_watchlist_view(url, params, next_up, 'watchlist_status_type_pages/kitsu/{0}'.format(status), page)

    def _process_watchlist_view(self, url, params, next_up, base_plugin_url, page):
        result = self._get_request(url, headers=self.__headers(), params=params)
        result = json.loads(result)
        _list = result["data"]

        if not result.get('included'):
            result['included'] = []

        el = result["included"][:len(_list)]
        self._mapping = [x for x in result['included'] if x['type'] == 'mappings']

        # Get the user's preferred sort order from the settings
        sort_order = control.getSetting('kitsu.order')

        if next_up:
            all_results = map(self._base_next_up_view, _list, el) if sort_order == '0' else map(self._base_next_up_view, reversed(_list), reversed(el))
        else:
            all_results = map(self._base_watchlist_view, _list, el) if sort_order == '0' else map(self._base_watchlist_view, reversed(_list), reversed(el))

        all_results = list(itertools.chain(*all_results))

        all_results += self._handle_paging(result['links'].get('next'), base_plugin_url, page)
        return all_results

    def _base_watchlist_view(self, res, eres):
        kitsu_id = eres['id']
        anilist_id = ''
        mal_id = self._mapping_mal(kitsu_id)

        info = {
            'plot': eres['attributes'].get('synopsis'),
            'title': eres["attributes"]["titles"].get(self.__get_title_lang(), eres["attributes"]['canonicalTitle']),
            'mpaa': eres['attributes']['ageRating'],
            'trailer': 'plugin://plugin.video.youtube/play/?video_id={0}'.format(eres['attributes']['youtubeVideoId']),
            'mediatype': 'tvshow'
        }

        if eres['attributes']['episodeCount'] != 0 and res["attributes"]["progress"] == eres['attributes']['episodeCount']:
            info['playcount'] = 1

        try:
            info['duration'] = eres['attributes']['episodeLength'] * 60
        except TypeError:
            pass

        try:
            info['rating'] = float(eres['attributes']['averageRating']) / 10
        except TypeError:
            pass

        poster_image = eres["attributes"]['posterImage']
        base = {
            "name": '%s - %d/%d' % (eres["attributes"]["titles"].get(self.__get_title_lang(), eres["attributes"]['canonicalTitle']),
                                    res["attributes"]['progress'],
                                    eres["attributes"].get('episodeCount', 0) if eres["attributes"]['episodeCount'] else 0),
            "url": 'watchlist_to_ep/{0}/{1}/{2}/{3}'.format(anilist_id, mal_id, kitsu_id, res["attributes"]["progress"]),
            "image": poster_image.get('large', poster_image['original']),
            "info": info
        }

        if eres['attributes']['subtype'] == 'movie' and eres['attributes']['episodeCount'] == 1:
            base['url'] = 'play_movie/{0}/{1}/{2}'.format(anilist_id, mal_id, kitsu_id)
            base['info']['mediatype'] = 'movie'
            return self._parse_view(base, False)

        return self._parse_view(base)

    def _base_next_up_view(self, res, eres):
        kitsu_id = eres['id']
        mal_id = self._mapping_mal(kitsu_id)

        progress = res["attributes"]['progress']
        next_up = progress + 1
        anime_title = eres["attributes"]["titles"].get(self.__get_title_lang(), eres["attributes"]['canonicalTitle'])
        episode_count = eres["attributes"]['episodeCount'] if eres["attributes"]['episodeCount'] else 0
        title = '%s - %d/%d' % (anime_title, next_up, episode_count)
        poster = image = eres["attributes"]['posterImage'].get('large', eres["attributes"]['posterImage']['original'])
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
            'tvshowtitle': anime_title,
            'plot': plot,
            'mediatype': 'episode',
            'aired': aired
        }

        base = {
            "name": title,
            "url": 'watchlist_to_ep/{0}/{1}/{2}/{3}'.format(anilist_id, mal_id, kitsu_id, res["attributes"]["progress"]),
            "image": image,
            "info": info,
            "fanart": image,
            "poster": poster
        }

        if next_up_meta:
            base['url'] = url
            return self._parse_view(base, False)

        if eres['attributes']['subtype'] == 'movie' and eres['attributes']['episodeCount'] == 1:
            base['url'] = 'play_movie/{0}/{1}/{2}'.format(anilist_id, mal_id, kitsu_id)
            base['info']['mediatype'] = 'movie'
            return self._parse_view(base, False)

        return self._parse_view(base)

    def _mapping_mal(self, kitsu_id):
        mal_id = ''
        for i in self._mapping:
            if i['attributes']['externalSite'] == 'myanimelist/anime':
                if i['relationships']['item']['data']['id'] == kitsu_id:
                    mal_id = i['attributes']['externalId']
                    break
        if not mal_id:
            ids = SIMKLAPI().get_mapping_ids('kitsu', kitsu_id)
            mal_id = ids['mal']
            database.add_mapping_id(ids['anilist'], 'mal_id', mal_id)
        return mal_id

    def get_library_entries(self, kitsu_id):
        url = self._URL + '/edge/library-entries'
        params = {
            "filter[user_id]": self._user_id,
            "filter[anime_id]": kitsu_id
        }
        r = self._get_request(url, headers=self.__headers(), params=params)
        r = json.loads(r)
        return r

    def get_watchlist_anime_entry(self, anilist_id):
        kitsu_id = self._get_mapping_id(anilist_id, 'kitsu_id')
        if not kitsu_id:
            return False

        result = self.get_library_entries(kitsu_id)
        try:
            item_dict = result['data'][0]['attributes']
        except IndexError:
            return {}
        anime_entry = {
            'eps_watched': item_dict['progress'],
            'status': item_dict['status'],
            'score': item_dict['ratingTwenty']
        }
        return anime_entry

    def update_list_status(self, anilist_id, status):
        kitsu_id = self._get_mapping_id(anilist_id, 'kitsu_id')
        if not kitsu_id:
            return False

        r = self.get_library_entries(kitsu_id)
        if len(r['data']) == 0:
            data = {
                "data": {
                    "type": "libraryEntries",
                    "attributes": {
                        'status': status
                    },
                    "relationships": {
                        "user": {
                            "data": {
                                "id": self._user_id,
                                "type": "users"
                            }
                        },
                        "anime": {
                            "data": {
                                "id": kitsu_id,
                                "type": "anime"
                            }
                        }
                    }
                }
            }
            r = self._post_request(self._URL + '/edge/library-entries', headers=self.__headers(), json=data)
            return r != ''
        animeid = int(r['data'][0]['id'])
        data = {
            'data': {
                'id': animeid,
                'type': 'libraryEntries',
                'attributes': {
                    'status': status
                }
            }
        }
        r = self._patch_request('{0}/edge/library-entries/{1}'.format(self._URL, animeid), headers=self.__headers(), json=data)
        return r != ''

    def update_num_episodes(self, anilist_id, episode):
        kitsu_id = self._get_mapping_id(anilist_id, 'kitsu_id')
        if not kitsu_id:
            return False

        r = self.get_library_entries(kitsu_id)
        if len(r['data']) == 0:
            data = {
                "data": {
                    "type": "libraryEntries",
                    "attributes": {
                        'status': 'current',
                        'progress': int(episode)
                    },
                    "relationships": {
                        "user": {
                            "data": {
                                "id": self._user_id,
                                "type": "users"
                            }
                        },
                        "anime": {
                            "data": {
                                "id": kitsu_id,
                                "type": "anime"
                            }
                        }
                    }
                }
            }
            r = self._post_request(self._URL + '/edge/library-entries', headers=self.__headers(), json=data)
            return r != ''

        animeid = int(r['data'][0]['id'])

        data = {
            'data': {
                'id': animeid,
                'type': 'libraryEntries',
                'attributes': {
                    'progress': int(episode)}
            }
        }
        r = self._patch_request('{0}/edge/library-entries/{1}'.format(self._URL, animeid), headers=self.__headers(), json=data)
        return r != ''

    def update_score(self, anilist_id, score):
        kitsu_id = self._get_mapping_id(anilist_id, 'kitsu_id')
        if not kitsu_id:
            return False

        score = int(score / 10 * 20)
        if score == 0:
            score = None
        r = self.get_library_entries(kitsu_id)
        if len(r['data']) == 0:
            data = {
                "data": {
                    "type": "libraryEntries",
                    "attributes": {
                        'ratingTwenty': score
                    },
                    "relationships": {
                        "user": {
                            "data": {
                                "id": self._user_id,
                                "type": "users"
                            }
                        },
                        "anime": {
                            "data": {
                                "id": kitsu_id,
                                "type": "anime"
                            }
                        }
                    }
                }
            }
            r = self._post_request(self._URL + '/edge/library-entries', headers=self.__headers(), json=data)
            return r != ''

        animeid = int(r['data'][0]['id'])
        data = {
            'data': {
                'id': animeid,
                'type': 'libraryEntries',
                'attributes': {
                    'ratingTwenty': score
                }
            }
        }
        r = self._patch_request('{0}/edge/library-entries/{1}'.format(self._URL, animeid), headers=self.__headers(), json=data)
        return r != ''

    def delete_anime(self, anilist_id):
        kitsu_id = self._get_mapping_id(anilist_id, 'kitsu_id')
        if not kitsu_id:
            return False

        r = self.get_library_entries(kitsu_id)

        data = r['data']
        if data:
            animeid = data[0]['id']
        else:
            return True

        r = self._delete_request('{0}/edge/library-entries/{1}'.format(self._URL, animeid), headers=self.__headers())
        return r != ''
