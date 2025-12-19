import random
import pickle

from resources.lib.ui import utils, client, control, get_meta, database
from resources.lib.WatchlistFlavor.WatchlistFlavorBase import WatchlistFlavorBase
from resources.lib.ui.divide_flavors import div_flavor


class AniListWLF(WatchlistFlavorBase):
    _NAME = "anilist"
    _URL = "https://graphql.anilist.co"
    _TITLE = "AniList"
    _IMAGE = "anilist.png"

    def __headers(self):
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        return headers

    def login(self):
        query = '''
        query ($name: String) {
            User(name: $name) {
                id
            }
        }
        '''

        variables = {
            "name": self.username
        }

        r = client.post(self._URL, headers=self.__headers(), json_data={'query': query, 'variables': variables})
        results = r.json() if r else None
        if results is None:
            control.setSetting('anilist.token', '')
            control.setSetting('anilist.username', '')
            return
        userId = results['data']['User']['id']
        login_data = {
            'userid': str(userId)
        }
        return login_data

    def __get_sort(self):
        sort_types = [None, None, 'PROGRESS', 'UPDATED_TIME_DESC', 'ADDED_TIME_DESC']
        return sort_types[int(self.sort)]

    def watchlist(self):
        statuses = [
            ("Next Up", "CURRENT?next_up=true", 'next_up.png'),
            ("Current", "CURRENT", 'currently_watching.png'),
            ("Rewatching", "REPEATING", 'rewatching.png'),
            ("Plan to Watch", "PLANNING", 'want_to_watch.png'),
            ("Paused", "PAUSED", 'on_hold.png'),
            ("Completed", "COMPLETED", 'completed.png'),
            ("Dropped", "DROPPED", 'dropped.png')
        ]
        return [utils.allocate_item(res[0], f'watchlist_status_type/{self._NAME}/{res[1]}', True, False, [], res[2], {}) for res in statuses]

    def _base_watchlist_view(self, res):
        url = f'watchlist_status_type/{self._NAME}/{res[1]}'
        return [utils.allocate_item(res[0], url, True, False, [], f'{res[0].lower()}.png', {})]

    @staticmethod
    def action_statuses():
        actions = [
            ("Add to Current", "CURRENT"),
            ("Add to Rewatching", "REPEATING"),
            ("Add to Planning", "PLANNING"),
            ("Add to Paused", "PAUSED"),
            ("Add to Completed", "COMPLETED"),
            ("Add to Dropped", "DROPPED"),
            ("Set Score", "set_score"),
            ("Delete", "DELETE")
        ]
        return actions

    def get_watchlist_status(self, status, next_up, offset, page):
        query = '''
        query ($userId: Int, $userName: String, $status: MediaListStatus, $type: MediaType, $sort: [MediaListSort], $forceSingleCompletedList: Boolean) {
            MediaListCollection(userId: $userId, userName: $userName, status: $status, type: $type, sort: $sort, forceSingleCompletedList: $forceSingleCompletedList) {
                lists {
                    entries {
                        ...mediaListEntry
                        }
                    }
                }
            }

        fragment mediaListEntry on MediaList {
            id
            mediaId
            status
            progress
            media {
                id
                idMal
                title {
                    userPreferred,
                    romaji,
                    english
                }
                coverImage {
                    extraLarge
                }
                bannerImage
                startDate {
                    year,
                    month,
                    day
                }
                nextAiringEpisode {
                    episode,
                    airingAt
                }
                description
                synonyms
                format
                status
                episodes
                genres
                duration
                countryOfOrigin
                averageScore
                characters (
                    page: 1,
                    sort: ROLE,
                    perPage: 10,
                ) {
                    edges {
                        node {
                            name {
                                userPreferred
                            }
                        }
                        voiceActors (language: JAPANESE) {
                            name {
                                userPreferred
                            }
                            image {
                                large
                            }
                        }
                    }
                }
                studios {
                    edges {
                        node {
                            name
                        }
                    }
                }
                trailer {
                    id
                    site
                }
            }
        }
        '''

        variables = {
            'userId': int(self.user_id),
            'username': self.username,
            'status': status,
            'type': 'ANIME',
            'sort': self.__get_sort(),
            'forceSingleCompletedList': False
        }
        return self.process_status_view(query, variables, next_up, status, offset, page)

    @staticmethod
    def handle_paging(hasmore, base_url, page):
        if not hasmore or not control.is_addon_visible() and control.getBool('widget.hide.nextpage'):
            return []
        next_page = page + 1
        name = "Next Page (%d)" % next_page
        return [utils.allocate_item(name, f'{base_url}?page={next_page}', True, False, [], 'next.png', {'plot': name}, fanart='next.png')]

    def process_status_view(self, query, variables, next_up, status, offset, page):
        from resources.lib.ui.database import (
            get_watchlist_cache, save_watchlist_cache,
            is_watchlist_cache_valid, get_watchlist_cache_count
        )

        paging_enabled = control.getBool('interface.watchlist.paging')
        per_page = control.getInt('interface.perpage.watchlist') if paging_enabled else 0
        offset = int(offset) if offset else 0

        # Check cache validity
        if not is_watchlist_cache_valid(self._NAME, status):
            # Fetch all items from API and cache them
            r = client.post(self._URL, headers=self.__headers(), json_data={'query': query, 'variables': variables})
            results = r.json() if r else {}
            lists = results.get('data', {}).get('MediaListCollection', {}).get('lists', [])
            entries = []
            for mlist in lists:
                for entrie in mlist['entries']:
                    if entrie not in entries:
                        entries.append(entrie)
            if entries:
                save_watchlist_cache(self._NAME, status, entries)

        # Get items from cache
        total_count = get_watchlist_cache_count(self._NAME, status)

        if paging_enabled and per_page > 0:
            cached_items = get_watchlist_cache(self._NAME, status, limit=per_page, offset=offset)
        else:
            cached_items = get_watchlist_cache(self._NAME, status)

        if not cached_items:
            return []

        # Deserialize cached items
        entries = [pickle.loads(item['data']) for item in cached_items]
        get_meta.collect_meta(entries)

        # If sorting by title, sort manually alphabetically.
        if int(self.sort) == 0:
            entries.sort(key=lambda entry: (entry['media']['title'].get(self.title_lang) or "").lower())

        # If sorting by score, sort manually by score.
        if int(self.sort) == 1:
            entries.sort(key=lambda entry: entry['media'].get('averageScore') or 0, reverse=True)

        # If order is descending, reverse the order.
        if int(self.order) == 1:
            entries.reverse()

        # Map to views
        all_results = list(map(self._base_next_up_view, entries)) if next_up else list(map(self.base_watchlist_status_view, entries))
        all_results = [r for r in all_results if r is not None]

        # Add paging if enabled
        if paging_enabled and per_page > 0:
            has_next = (offset + per_page) < total_count
            all_results += self.handle_paging(has_next, f'watchlist_status_type_pages/anilist/{status}/{offset + per_page}', page)

        return all_results

    @div_flavor
    def base_watchlist_status_view(self, res, mal_dub=None):
        progress = res['progress']
        res = res['media']
        anilist_id = res['id']
        mal_id = res.get('idMal')

        if not mal_id:
            control.log(f"Mal ID not found for {anilist_id}", level='warning')

        dub = True if mal_dub and mal_dub.get(str(mal_id)) else False

        title = res['title'].get(self.title_lang) or res['title'].get('userPreferred')

        info = {
            'UniqueIDs': {
                'anilist_id': str(anilist_id),
                'mal_id': str(mal_id),
                **database.get_unique_ids(anilist_id, 'anilist_id'),
                **database.get_unique_ids(mal_id, 'mal_id')
            },
            'title': title,
            'genre': res.get('genres'),
            'status': res.get('status'),
            'mediatype': 'tvshow',
            'country': [res.get('countryOfOrigin', '')],
            'studio': [x['node'].get('name') for x in res['studios'].get('edges')]
        }

        if res['episodes'] != 0 and progress == res['episodes']:
            info['playcount'] = 1

        try:
            info['duration'] = res.get('duration') * 60
        except TypeError:
            pass

        try:
            if res['trailer']['site'] == 'youtube':
                info['trailer'] = f"plugin://plugin.video.youtube/play/?video_id={res['trailer']['id']}"
            else:
                info['trailer'] = f"plugin://plugin.video.dailymotion_com/?url={res['trailer']['id']}&mode=playVideo"
        except TypeError:
            pass

        try:
            info['rating'] = {'score': res.get('averageScore') / 10.0}
        except TypeError:
            pass

        desc = res.get('description')
        if desc:
            desc = desc.replace('<i>', '[I]').replace('</i>', '[/I]')
            desc = desc.replace('<b>', '[B]').replace('</b>', '[/B]')
            desc = desc.replace('<br>', '[CR]')
            desc = desc.replace('\n', '')
            info['plot'] = desc

        try:
            start_date = res.get('startDate')
            info['aired'] = '{}-{:02}-{:02}'.format(start_date['year'], start_date['month'], start_date['day'])
        except TypeError:
            pass

        cast = []
        try:
            for i, x in enumerate(res['characters']['edges']):
                role = x['node']['name']['userPreferred']
                actor = x['voiceActors'][0]['name']['userPreferred']
                actor_hs = x['voiceActors'][0]['image'].get('large')
                cast.append({'name': actor, 'role': role, 'thumbnail': actor_hs, 'index': i})
                info['cast'] = cast
        except IndexError:
            pass

        show_meta = database.get_show_meta(mal_id)
        kodi_meta = pickle.loads(show_meta.get('art')) if show_meta else {}
        image = res['coverImage']['extraLarge']
        base = {
            "name": '%s - %d/%d' % (title, progress, res['episodes'] if res['episodes'] else 0),
            "url": f'watchlist_to_ep/{mal_id}/{progress}',
            "image": image,
            "poster": image,
            'fanart': kodi_meta['fanart'] if kodi_meta.get('fanart') else image,
            "info": info
        }

        # Pull all artwork from kodi_meta (already respects settings and is pre-selected)
        if kodi_meta.get('banner'):
            base['banner'] = kodi_meta['banner']
        if kodi_meta.get('thumb'):
            thumb = kodi_meta['thumb']
            base['landscape'] = random.choice(thumb) if isinstance(thumb, list) else thumb
        if kodi_meta.get('clearart'):
            clearart = kodi_meta['clearart']
            base['clearart'] = random.choice(clearart) if isinstance(clearart, list) else clearart
        if kodi_meta.get('clearlogo'):
            clearlogo = kodi_meta['clearlogo']
            base['clearlogo'] = random.choice(clearlogo) if isinstance(clearlogo, list) else clearlogo

        if res['format'] == 'MOVIE' and res['episodes'] == 1:
            base['url'] = f'play_movie/{mal_id}/'
            base['info']['mediatype'] = 'movie'
            return utils.parse_view(base, False, True, dub)
        return utils.parse_view(base, True, False, dub)

    @div_flavor
    def _base_next_up_view(self, res, mal_dub=None):
        progress = res['progress']
        res = res['media']

        anilist_id = res['id']
        mal_id = res.get('idMal')
        dub = True if mal_dub and mal_dub.get(str(mal_id)) else False

        next_up = progress + 1
        episode_count = res['episodes'] if res['episodes'] else 0

        if not control.getBool('playlist.unaired'):
            from resources.lib.AnimeSchedule import get_anime_schedule
            airing_anime = get_anime_schedule(mal_id)

            if airing_anime and airing_anime.get('current_episode'):
                episode_count = airing_anime['current_episode']

        base_title = res['title'].get(self.title_lang) or res['title'].get('userPreferred')
        title = f"{base_title} - {next_up}/{episode_count}"
        poster = image = res['coverImage']['extraLarge']

        if (0 < episode_count < next_up) or (res['nextAiringEpisode'] and next_up == res['nextAiringEpisode']['episode']):
            return None

        if mal_id:
            mal_id, next_up_meta, show = self._get_next_up_meta(mal_id, progress)
        else:
            next_up_meta = None
        if next_up_meta:
            if next_up_meta.get('title'):
                title = f"{title} - {next_up_meta['title']}"
            if next_up_meta.get('image'):
                image = next_up_meta['image']
            plot = next_up_meta.get('plot')
            aired = next_up_meta.get('aired')
        else:
            plot = aired = None

        info = {
            'UniqueIDs': {
                'anilist_id': str(anilist_id),
                'mal_id': str(mal_id),
                **database.get_unique_ids(anilist_id, 'anilist_id'),
                **database.get_unique_ids(mal_id, 'mal_id')
            },
            'episode': next_up,
            'title': title,
            'tvshowtitle': res['title']['userPreferred'],
            'plot': plot,
            'genre': res.get('genres'),
            'mediatype': 'episode',
            'aired': aired
        }

        base = {
            "name": title,
            "url": f"watchlist_to_ep/{mal_id}/{progress}",
            "image": image,
            "info": info,
            "fanart": image,
            "poster": poster
        }

        show_meta = database.get_show_meta(mal_id)
        if show_meta:
            art = pickle.loads(show_meta['art'])
            if art.get('fanart'):
                base['fanart'] = art['fanart']
            # Pull all artwork from kodi_meta (already respects settings and is pre-selected)
            if art.get('banner'):
                base['banner'] = art['banner']
            if art.get('thumb'):
                thumb = art['thumb']
                base['landscape'] = random.choice(thumb) if isinstance(thumb, list) else thumb
            if art.get('clearart'):
                clearart = art['clearart']
                base['clearart'] = random.choice(clearart) if isinstance(clearart, list) else clearart
            if art.get('clearlogo'):
                clearlogo = art['clearlogo']
                base['clearlogo'] = random.choice(clearlogo) if isinstance(clearlogo, list) else clearlogo

        if res['format'] == 'MOVIE' and res['episodes'] == 1:
            base['url'] = f"play_movie/{mal_id}/"
            base['info']['mediatype'] = 'movie'
            return utils.parse_view(base, False, True, dub)
        if next_up_meta:
            base['url'] = f"play/{mal_id}/{next_up}"
            return utils.parse_view(base, False, True, dub)
        return utils.parse_view(base, True, False, dub)

    def get_watchlist_anime_entry(self, mal_id):
        query = '''
        query ($mediaId: Int) {
            Media (idMal: $mediaId) {
                id
                mediaListEntry {
                    id
                    mediaId
                    status
                    score
                    progress
                    user {
                        id
                        name
                    }
                }
            }
        }
        '''

        variables = {
            'mediaId': mal_id
        }

        r = client.post(self._URL, headers=self.__headers(), json_data={'query': query, 'variables': variables})
        results = r.json()['data']['Media']['mediaListEntry'] if r else {}
        if not results:
            return {}
        anime_entry = {
            'eps_watched': results.get('progress'),
            'status': results['status'],
            'score': results['score']
        }
        return anime_entry

    def save_completed(self):
        import json
        data = self.get_user_anime_list('COMPLETED')
        completed = {}
        for dat in data:
            for entrie in dat['entries']:
                if entrie['media']['episodes']:
                    completed[str(entrie['media']['idMal'])] = int(entrie['media']['episodes'])
        with open(control.completed_json, 'w') as file:
            json.dump(completed, file)

    def get_user_anime_list(self, status):
        query = '''
        query ($userId: Int, $userName: String, $status: MediaListStatus, $type: MediaType, $sort: [MediaListSort]) {
            MediaListCollection(userId: $userId, userName: $userName, status: $status, type: $type, sort: $sort) {
                lists {
                    entries {
                        id
                        mediaId
                        progress
                        media {
                            id
                            idMal
                            episodes
                        }
                    }
                }
            }
        }
        '''

        variables = {
            'userId': int(self.user_id),
            'username': self.username,
            'status': status,
            'type': 'ANIME',
            'sort': self.__get_sort()
        }
        r = client.post(self._URL, headers=self.__headers(), json_data={'query': query, 'variables': variables})
        results = r.json() if r else {}
        return results['data']['MediaListCollection']['lists'] if 'data' in results else []

    def get_watchlist_anime_info(self, anilist_id):
        query = '''
        query ($mediaId: Int) {
            Media (id: $mediaId) {
                id
                mediaListEntry {
                    id
                    mediaId
                    status
                    score
                    progress
                }
            }
        }
        '''

        variables = {
            'mediaId': anilist_id
        }

        r = client.post(self._URL, headers=self.__headers(), json_data={'query': query, 'variables': variables})
        results = r.json() if r else {}
        return results

    def update_list_status(self, mal_id, status):
        from resources.lib.ui.database import clear_watchlist_cache
        anilist_id = self._get_mapping_id(mal_id, 'anilist_id')
        if not anilist_id:
            return False
        query = '''
        mutation ($mediaId: Int, $status: MediaListStatus) {
            SaveMediaListEntry (mediaId: $mediaId, status: $status) {
                id
                status
            }
        }
        '''

        variables = {
            'mediaId': int(anilist_id),
            'status': status
        }

        r = client.post(self._URL, headers=self.__headers(), json_data={'query': query, 'variables': variables})
        if r and r.ok:
            clear_watchlist_cache(self._NAME)  # Clear all statuses since item moved
        return r and r.ok

    def update_num_episodes(self, mal_id, episode):
        from resources.lib.ui.database import clear_watchlist_cache
        anilist_id = self._get_mapping_id(mal_id, 'anilist_id')
        if not anilist_id:
            return False
        query = '''
        mutation ($mediaId: Int, $progress : Int, $status: MediaListStatus) {
            SaveMediaListEntry (mediaId: $mediaId, progress: $progress, status: $status) {
                id
                progress
                status
            }
        }
        '''

        variables = {
            'mediaId': int(anilist_id),
            'progress': int(episode)
        }

        r = client.post(self._URL, headers=self.__headers(), json_data={'query': query, 'variables': variables})
        if r and r.ok:
            clear_watchlist_cache(self._NAME)  # Clear cache to reflect progress
        return r and r.ok

    def update_score(self, mal_id, score):
        from resources.lib.ui.database import clear_watchlist_cache
        anilist_id = self._get_mapping_id(mal_id, 'anilist_id')
        if not anilist_id:
            return False
        query = '''
        mutation ($mediaId: Int, $score: Float) {
            SaveMediaListEntry (mediaId: $mediaId, score: $score) {
                id
                score
            }
        }
        '''

        variables = {
            'mediaId': int(anilist_id),
            'score': float(score)
        }

        r = client.post(self._URL, headers=self.__headers(), json_data={'query': query, 'variables': variables})
        if r and r.ok:
            clear_watchlist_cache(self._NAME)  # Clear cache to reflect score
        return r and r.ok

    def delete_anime(self, mal_id):
        from resources.lib.ui.database import clear_watchlist_cache
        anilist_id = self._get_mapping_id(mal_id, 'anilist_id')
        if not anilist_id:
            return False
        media_entry = self.get_watchlist_anime_info(anilist_id)['data']['Media']['mediaListEntry']
        if media_entry:
            list_id = media_entry['id']
        else:
            return True
        query = '''
        mutation ($id: Int) {
            DeleteMediaListEntry (id: $id) {
                deleted
            }
        }
        '''

        variables = {
            'id': int(list_id)
        }
        r = client.post(self._URL, headers=self.__headers(), json_data={'query': query, 'variables': variables})
        if r and r.ok:
            clear_watchlist_cache(self._NAME)  # Clear cache after deletion
        return r and r.ok
