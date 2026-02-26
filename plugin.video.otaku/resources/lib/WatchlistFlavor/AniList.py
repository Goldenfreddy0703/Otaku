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

    def get_last_activity_timestamp(self):
        """Check AniList Viewer's updatedAt timestamp to detect remote changes."""
        query = '''
        query {
            Viewer {
                updatedAt
                statistics {
                    anime {
                        count
                    }
                }
            }
        }
        '''
        r = client.post(self._URL, headers=self.__headers(), json_data={'query': query})
        if not r:
            return None
        data = r.json()
        viewer = data.get('data', {}).get('Viewer', {})
        updated_at = viewer.get('updatedAt', '')
        anime_count = viewer.get('statistics', {}).get('anime', {}).get('count', 0)
        # Combine timestamp and count so both deletions and updates trigger refresh
        return f"{updated_at}_{anime_count}"

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

    def get_watchlist_status(self, status, next_up, offset, page, cache_only=False):
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
        return self.process_status_view(query, variables, next_up, status, offset, page, cache_only)

    @staticmethod
    def handle_paging(hasmore, base_url, page):
        if not hasmore or not control.is_addon_visible() and control.getBool('widget.hide.nextpage'):
            return []
        next_page = page + 1
        name = "Next Page (%d)" % next_page
        return [utils.allocate_item(name, f'{base_url}?page={next_page}', True, False, [], 'next.png', {'plot': name}, fanart='next.png')]

    def process_status_view(self, query, variables, next_up, status, offset, page, cache_only=False):
        # Check for remote changes before using cache
        self._should_refresh_cache()

        # Handle Next Up separately - it needs special episode-level processing
        if next_up and not cache_only:
            return self._get_next_up_episodes(query, variables, status, offset, page)

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

        # If cache_only, we're done - raw data is cached
        if cache_only:
            return []

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
        all_results = list(map(self.base_watchlist_status_view, entries))
        all_results = [r for r in all_results if r is not None]

        # Add paging if enabled
        if paging_enabled and per_page > 0:
            has_next = (offset + per_page) < total_count
            all_results += self.handle_paging(has_next, f'watchlist_status_type_pages/anilist/{status}/{offset + per_page}', page)

        return all_results

    def _get_next_up_episodes(self, query, variables, status, offset, page):
        """
        Get Next Up episodes - Episode-driven list of next unwatched episodes.

        Next Up Rules:
        - All anime in Current/Watching list are included
        - Shows with 0 progress show Episode 1 as next up
        - Only the immediate next unwatched episode is shown per anime
        - Sorted by last activity (UPDATED_TIME_DESC)
        - Only aired episodes are included (if playlist.unaired is disabled)
        - Completed shows are excluded
        - Format: "Show Name 01x13 - Episode Title"
        """
        from resources.lib.ui.database import (
            get_watchlist_cache, save_watchlist_cache,
            is_watchlist_cache_valid, get_watchlist_cache_count
        )

        paging_enabled = control.getBool('interface.watchlist.paging')
        per_page = control.getInt('interface.perpage.watchlist') if paging_enabled else 1000
        offset = int(offset) if offset else 0

        # Use a separate cache key for next_up to ensure proper sorting
        cache_status = 'next_up'

        if not is_watchlist_cache_valid(self._NAME, cache_status):
            # Force sort by UPDATED_TIME_DESC for Next Up
            next_up_variables = variables.copy()
            next_up_variables['sort'] = 'UPDATED_TIME_DESC'

            r = client.post(self._URL, headers=self.__headers(), json_data={'query': query, 'variables': next_up_variables})
            results = r.json() if r else {}
            lists = results.get('data', {}).get('MediaListCollection', {}).get('lists', [])
            entries = []
            for mlist in lists:
                for entrie in mlist['entries']:
                    if entrie not in entries:
                        entries.append(entrie)

            # Filter: Shows that have a valid next episode to watch
            # Includes shows with 0 progress (Episode 1 is their next up)
            filtered_entries = []
            for entry in entries:
                progress = entry.get('progress') or 0
                total_eps = entry['media'].get('episodes') or 0

                # Skip if show is completed (all episodes watched)
                # total_eps == 0 means unknown/ongoing, so include it
                if total_eps > 0 and progress >= total_eps:
                    continue

                filtered_entries.append(entry)

            if filtered_entries:
                save_watchlist_cache(self._NAME, cache_status, filtered_entries)

        # Get items from cache
        total_count = get_watchlist_cache_count(self._NAME, cache_status)

        if paging_enabled and per_page > 0:
            cached_items = get_watchlist_cache(self._NAME, cache_status, limit=per_page, offset=offset)
        else:
            cached_items = get_watchlist_cache(self._NAME, cache_status)

        if not cached_items:
            return []

        # Deserialize cached items
        entries = [pickle.loads(item['data']) for item in cached_items]
        get_meta.collect_meta(entries)

        # Process each anime to build next up episode items
        def process_next_up_item(entry):
            try:
                return self._build_next_up_episode(entry)
            except Exception as e:
                control.log(f"Error processing Next Up for AniList {entry['media'].get('id')}: {str(e)}", level='warning')
                return None

        # Process items in parallel
        all_results = utils.parallel_process(entries, process_next_up_item, max_workers=5)
        all_results = [r for r in all_results if r is not None]

        # Handle paging
        if paging_enabled and per_page > 0:
            next_offset = offset + per_page
            if next_offset < total_count:
                all_results += self._handle_next_up_paging(next_offset, page)

        return all_results

    def _handle_next_up_paging(self, next_offset, page):
        """Handle paging for Next Up with next_up=true parameter preserved"""
        if not control.is_addon_visible() and control.getBool('widget.hide.nextpage'):
            return []
        next_page = page + 1
        name = "Next Page (%d)" % next_page
        url = f'watchlist_status_type_pages/anilist/CURRENT/{next_offset}?page={next_page}&next_up=true'
        return [utils.allocate_item(name, url, True, False, [], 'next.png', {'plot': name}, fanart='next.png')]

    def _build_next_up_episode(self, entry):
        """Build a Next Up episode item by extracting AniList data and using the shared builder."""
        res = entry['media']
        anilist_id = res['id']
        mal_id = res.get('idMal')
        progress = entry['progress']
        total_eps = res.get('episodes') or 0

        # Get show title
        show_title = res['title'].get(self.title_lang) or res['title'].get('userPreferred') or res['title'].get('romaji', '')

        # Poster
        poster = res['coverImage'].get('extraLarge') if res.get('coverImage') else None

        # AniList-specific: next airing episode number
        next_airing_episode = None
        if res.get('nextAiringEpisode'):
            next_airing_episode = res['nextAiringEpisode'].get('episode')

        # Rating (AniList uses 0-100 scale)
        average_score = res.get('averageScore') / 10.0 if res.get('averageScore') else None

        # Duration (AniList gives minutes, convert to seconds)
        duration = res.get('duration') * 60 if res.get('duration') else None

        # Genres and Studios
        genres = res.get('genres')
        studios = None
        if res.get('studios') and res['studios'].get('edges'):
            studios = [s['node'].get('name') for s in res['studios']['edges']]

        # Characters/Cast
        characters = None
        if res.get('characters') and res['characters'].get('edges'):
            try:
                characters = []
                for i, x in enumerate(res['characters']['edges']):
                    role = x['node']['name']['userPreferred']
                    actor = x['voiceActors'][0]['name']['userPreferred']
                    actor_hs = x['voiceActors'][0]['image'].get('large', '')
                    characters.append({'name': actor, 'role': role, 'thumbnail': actor_hs, 'index': i})
            except (IndexError, KeyError, TypeError):
                characters = None

        # Trailer
        trailer = None
        if res.get('trailer'):
            try:
                if res['trailer']['site'] == 'youtube':
                    trailer = f"plugin://plugin.video.youtube/play/?video_id={res['trailer']['id']}"
                else:
                    trailer = f"plugin://plugin.video.dailymotion_com/?url={res['trailer']['id']}&mode=playVideo"
            except (KeyError, TypeError):
                pass

        # Start date
        start_date = res.get('startDate')
        year = None
        if start_date and start_date.get('year'):
            year = int(start_date['year'])

        data = {
            'mal_id': mal_id,
            'anilist_id': anilist_id,
            'progress': progress,
            'show_title': show_title,
            'total_eps': total_eps,
            'poster': poster,
            'is_movie': res.get('format') == 'MOVIE' and total_eps == 1,
            'next_airing_episode': next_airing_episode,
            'average_score': average_score,
            'duration': duration,
            'genres': genres,
            'studios': studios,
            'status': res.get('status'),
            'country': res.get('countryOfOrigin'),
            'start_date': start_date,
            'year': year,
            'characters': characters,
            'trailer': trailer,
            'mpaa': res.get('countryOfOrigin'),
        }

        return self.build_next_up_item(data)

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

        info['duration'] = control.safe_call(lambda: res.get('duration') * 60)

        try:
            if res['trailer']['site'] == 'youtube':
                info['trailer'] = f"plugin://plugin.video.youtube/play/?video_id={res['trailer']['id']}"
            else:
                info['trailer'] = f"plugin://plugin.video.dailymotion_com/?url={res['trailer']['id']}&mode=playVideo"
        except TypeError:
            pass

        info['rating'] = control.safe_call(lambda: {'score': res.get('averageScore') / 10.0})

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

    def get_watchlist_anime_entry(self, mal_id):
        query = '''
        query ($mediaId: Int) {
            Media (idMal: $mediaId, type: ANIME) {
                id
                episodes
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
            'mediaId': int(mal_id)
        }

        r = client.post(self._URL, headers=self.__headers(), json_data={'query': query, 'variables': variables})
        if not r:
            return {}
        media = r.json().get('data', {}).get('Media') or {}
        if not media:
            return {}
        list_entry = media.get('mediaListEntry') or {}
        anime_entry = {
            'eps_watched': list_entry.get('progress', 0),
            'status': list_entry.get('status', ''),
            'score': list_entry.get('score', 0),
            'total_episodes': media.get('episodes')
        }
        return anime_entry

    def save_completed(self):
        data = self.get_user_anime_list('COMPLETED')
        completed = {}
        for dat in data:
            for entrie in dat['entries']:
                if entrie['media']['episodes']:
                    completed[str(entrie['media']['idMal'])] = int(entrie['media']['episodes'])
        return completed

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
