import re
import time
import random
import pickle

from resources.lib.ui import utils, client, control, get_meta, database
from resources.lib.WatchlistFlavor.WatchlistFlavorBase import WatchlistFlavorBase
from resources.lib.ui.divide_flavors import div_flavor


class MyAnimeListWLF(WatchlistFlavorBase):
    _NAME = "mal"
    _URL = "https://api.myanimelist.net/v2"
    _TITLE = "MyAnimeList"
    _IMAGE = "myanimelist.png"

    def __headers(self):
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        return headers

    def get_last_activity_timestamp(self):
        """Check MAL user profile's anime statistics to detect remote changes."""
        r = client.get(
            f'{self._URL}/users/@me',
            headers=self.__headers(),
            params={'fields': 'anime_statistics'}
        )
        if not r:
            return None
        data = r.json()
        stats = data.get('anime_statistics', {})
        # Build a composite key from counts across all statuses
        # Any add/delete/move will change at least one of these
        parts = [
            str(stats.get('num_items_watching', 0)),
            str(stats.get('num_items_completed', 0)),
            str(stats.get('num_items_on_hold', 0)),
            str(stats.get('num_items_dropped', 0)),
            str(stats.get('num_items_plan_to_watch', 0)),
            str(stats.get('num_items', 0)),
            str(stats.get('num_episodes', 0)),
        ]
        return '_'.join(parts)

    def login(self):
        from urllib import parse
        parsed = parse.urlparse(self.auth_var)
        params = dict(parse.parse_qsl(parsed.query))
        code = params.get('code')
        code_verifier = params.get('state')

        oauth_url = 'https://myanimelist.net/v1/oauth2/token'
        api_info = database.get_info('MyAnimeList')
        client_id = api_info['client_id']

        data = {
            'client_id': client_id,
            'code': code,
            'code_verifier': code_verifier,
            'grant_type': 'authorization_code'
        }
        r = client.post(oauth_url, data=data)
        if not r:
            return
        res = r.json()

        self.token = res['access_token']
        user = client.get(f'{self._URL}/users/@me', headers=self.__headers(), params={'fields': 'name'})
        user = user.json()

        login_data = {
            'token': res['access_token'],
            'refresh': res['refresh_token'],
            'expiry': int(time.time()) + int(res['expires_in']),
            'username': user['name']
        }
        return login_data

    @staticmethod
    def refresh_token():
        oauth_url = 'https://myanimelist.net/v1/oauth2/token'
        api_info = database.get_info('MyAnimeList')
        client_id = api_info['client_id']

        data = {
            'client_id': client_id,
            'grant_type': 'refresh_token',
            'refresh_token': control.getSetting('mal.refresh')
        }
        r = client.post(oauth_url, data=data)
        if not r:
            return
        res = r.json()
        control.setSetting('mal.token', res['access_token'])
        control.setSetting('mal.refresh', res['refresh_token'])
        control.setInt('mal.expiry', int(time.time()) + int(res['expires_in']))

    @staticmethod
    def handle_paging(next_offset, base_url, page):
        if not control.is_addon_visible() and control.getBool('widget.hide.nextpage'):
            return []
        next_page = page + 1
        name = "Next Page (%d)" % next_page
        return [utils.allocate_item(name, f'{base_url}/{next_offset}?page={next_page}', True, False, [], 'next.png', {'plot': name}, fanart='next.png')]

    def __get_sort(self):
        sort_types = ['anime_title', 'list_score', "", 'list_updated_at', 'anime_start_date']
        return sort_types[int(self.sort)]

    def watchlist(self):
        statuses = [
            ("Currently Watching", "watching", 'currently_watching.png'),
            ("Completed", "completed", 'completed.png'),
            ("On Hold", "on_hold", 'on_hold.png'),
            ("Dropped", "dropped", 'dropped.png'),
            ("Plan to Watch", "plan_to_watch", 'want_to_watch.png'),
            ("All Anime", "", 'all_anime.png')
        ]
        return [utils.allocate_item(res[0], f'watchlist_status_type/{self._NAME}/{res[1]}', True, False, [], res[2], {}) for res in statuses]

    @staticmethod
    def action_statuses():
        actions = [
            ("Add to On Currently Watching", "watching"),
            ("Add to Completed", "completed"),
            ("Add to On Hold", "on_hold"),
            ("Add to Dropped", "dropped"),
            ("Add to Plan to Watch", "plan_to_watch"),
            ("Set Score", "set_score"),
            ("Delete", "DELETE")
        ]
        return actions

    def get_watchlist_status(self, status, next_up, offset, page, cache_only=False):
        # Check for remote changes before using cache
        self._should_refresh_cache()

        # Handle Next Up separately - it needs special episode-level processing
        if next_up and not cache_only:
            return self._get_next_up_episodes(offset, page)

        from resources.lib.ui.database import (
            get_watchlist_cache, save_watchlist_cache,
            is_watchlist_cache_valid, get_watchlist_cache_count
        )

        paging_enabled = control.getBool('interface.watchlist.paging')
        per_page = control.getInt('interface.perpage.watchlist') if paging_enabled else 1000
        offset = int(offset) if offset else 0

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

        # Check cache validity
        if not is_watchlist_cache_valid(self._NAME, status):
            # Fetch all items from API (use high limit to get all)
            params = {
                "status": status,
                "sort": self.__get_sort(),
                "limit": 1000,
                "offset": 0,
                "fields": ','.join(fields),
                "nsfw": True
            }
            url = f'{self._URL}/users/@me/animelist'
            all_data = []
            
            r = client.get(url, headers=self.__headers(), params=params)
            results = r.json() if r else {}
            all_data.extend(results.get('data', []))
            
            # Fetch remaining pages
            while results.get('paging', {}).get('next'):
                r = client.get(results['paging']['next'], headers=self.__headers())
                results = r.json() if r else {}
                all_data.extend(results.get('data', []))
            
            # Apply sorting before saving to cache
            if all_data:
                # If sorting by anime_title and language is english, sort manually by english title.
                if self.__get_sort() == 'anime_title' and self.title_lang == 'english':
                    all_data.sort(key=lambda item: (item['node'].get('alternative_titles', {}).get('en') or item['node'].get('title', '')).lower())

                # If sorting by progress, sort manually by progress:
                if int(self.sort) == 2:
                    all_data.sort(key=lambda item: item['list_status']['num_episodes_watched'])

                # If order is descending, reverse the order.
                if int(self.order) == 1:
                    all_data.reverse()

                save_watchlist_cache(self._NAME, status, all_data)

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
        items = [pickle.loads(item['data']) for item in cached_items]

        return self._process_status_view(items, f'watchlist_status_type_pages/mal/{status}', page, offset, per_page, total_count, paging_enabled)

    def _process_status_view(self, items, base_plugin_url, page, offset, per_page, total_count, paging_enabled):
        if not items:
            return []

        # Fetch AniList data for current page items only (fast for small batches)
        mal_ids = [item['node']['id'] for item in items]
        mal_id_dicts = [{'mal_id': mid} for mid in mal_ids]
        get_meta.collect_meta(mal_id_dicts)

        try:
            from resources.lib.endpoints.anilist import Anilist
            anilist_data = Anilist().get_enrichment_for_mal_ids(mal_ids)
        except Exception:
            anilist_data = []

        # Build AniList lookup by MAL ID
        anilist_by_mal_id = {item.get('idMal'): item for item in anilist_data if item.get('idMal')}

        # Pass AniList data to view functions
        def viewfunc(res):
            mal_id = res['node']['id']
            anilist_item = anilist_by_mal_id.get(mal_id)
            return self._base_watchlist_status_view(res, anilist_res=anilist_item)

        all_results = list(map(viewfunc, items))

        # Handle paging
        if paging_enabled and per_page > 0:
            next_offset = offset + per_page
            if next_offset < total_count:
                all_results += self.handle_paging(next_offset, base_plugin_url, page)

        return all_results

    def _get_next_up_episodes(self, offset, page):
        """
        Get Next Up episodes - Episode-driven list of next unwatched episodes.
        
        Next Up Rules:
        - All anime in Watching list are included
        - Shows with 0 progress show Episode 1 as next up
        - Only the immediate next unwatched episode is shown per anime
        - Sorted by last watched activity (list_updated_at)
        - Only aired episodes are included (if playlist.unaired is disabled)
        - Completed shows are excluded
        - Format: "Show Name 01x13 - Episode Title"
        """
        from resources.lib.ui.database import (
            get_watchlist_cache, save_watchlist_cache,
            is_watchlist_cache_valid, get_watchlist_cache_count
        )

        status = 'watching'
        paging_enabled = control.getBool('interface.watchlist.paging')
        per_page = control.getInt('interface.perpage.watchlist') if paging_enabled else 1000
        offset = int(offset) if offset else 0

        fields = [
            'alternative_titles',
            'list_status{updated_at}',
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

        # Use a separate cache key for next_up to ensure proper sorting by updated_at
        cache_status = 'next_up'
        
        if not is_watchlist_cache_valid(self._NAME, cache_status):
            # Fetch all "watching" items sorted by last updated (most recently watched first)
            params = {
                "status": status,
                "sort": "list_updated_at",  # Sort by last activity for Next Up
                "limit": 1000,
                "offset": 0,
                "fields": ','.join(fields),
                "nsfw": True
            }
            url = f'{self._URL}/users/@me/animelist'
            all_data = []
            
            r = client.get(url, headers=self.__headers(), params=params)
            results = r.json() if r else {}
            all_data.extend(results.get('data', []))
            
            # Fetch remaining pages
            while results.get('paging', {}).get('next'):
                r = client.get(results['paging']['next'], headers=self.__headers())
                results = r.json() if r else {}
                all_data.extend(results.get('data', []))

            # Filter: Shows that have a valid next episode to watch
            # Includes shows with 0 progress (Episode 1 is their next up)
            filtered_data = []
            for item in all_data:
                eps_watched = item['list_status'].get('num_episodes_watched') or 0
                total_eps = item['node'].get('num_episodes') or 0
                
                # Skip if show is completed (all episodes watched)
                # total_eps == 0 means unknown/ongoing, so include it
                if total_eps > 0 and eps_watched >= total_eps:
                    continue
                
                filtered_data.append(item)

            # Sort by updated_at (most recent first) - this is already done by API but ensure it
            filtered_data.sort(
                key=lambda x: x['list_status'].get('updated_at') or '',
                reverse=True
            )

            if filtered_data:
                save_watchlist_cache(self._NAME, cache_status, filtered_data)

        # Get items from cache
        total_count = get_watchlist_cache_count(self._NAME, cache_status)

        if paging_enabled and per_page > 0:
            cached_items = get_watchlist_cache(self._NAME, cache_status, limit=per_page, offset=offset)
        else:
            cached_items = get_watchlist_cache(self._NAME, cache_status)

        if not cached_items:
            return []

        # Deserialize cached items
        items = [pickle.loads(item['data']) for item in cached_items]

        # Collect metadata for all MAL IDs
        mal_ids = [item['node']['id'] for item in items]
        mal_id_dicts = [{'mal_id': mid} for mid in mal_ids]
        get_meta.collect_meta(mal_id_dicts)

        # Fetch AniList data for additional metadata
        try:
            from resources.lib.endpoints.anilist import Anilist
            anilist_data = Anilist().get_enrichment_for_mal_ids(mal_ids)
        except Exception:
            anilist_data = []

        anilist_by_mal_id = {item.get('idMal'): item for item in anilist_data if item.get('idMal')}

        # Process each anime to build next up episode items
        def process_next_up_item(item):
            try:
                return self._build_next_up_episode(item, anilist_by_mal_id)
            except Exception as e:
                control.log(f"Error processing Next Up for {item['node'].get('id')}: {str(e)}", level='warning')
                return None

        # Process items in parallel using existing utility
        all_results = utils.parallel_process(items, process_next_up_item, max_workers=5)
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
        url = f'watchlist_status_type_pages/mal/watching/{next_offset}?page={next_page}&next_up=true'
        return [utils.allocate_item(name, url, True, False, [], 'next.png', {'plot': name}, fanart='next.png')]

    def _build_next_up_episode(self, item, anilist_by_mal_id):
        """Build a Next Up episode item by extracting MAL data and using the shared builder."""
        mal_id = item['node']['id']
        anilist_res = anilist_by_mal_id.get(mal_id)
        progress = item['list_status'].get('num_episodes_watched') or 0
        total_eps = item['node'].get('num_episodes') or 0

        # Get show title
        show_title = item['node'].get('title', '')
        if self.title_lang == 'english':
            show_title = item['node'].get('alternative_titles', {}).get('en') or show_title
        if not show_title and anilist_res:
            show_title = anilist_res.get('title', {}).get(self.title_lang) or anilist_res.get('title', {}).get('romaji') or show_title

        # Poster from MAL
        poster = item['node'].get('main_picture', {}).get('large') or item['node'].get('main_picture', {}).get('medium')
        if not poster and anilist_res and anilist_res.get('coverImage'):
            poster = anilist_res['coverImage'].get('extraLarge') or anilist_res['coverImage'].get('large')

        # Rating from MAL (already 0-10 scale)
        average_score = item['node'].get('mean')

        # Duration from MAL (already in seconds)
        duration = item['node'].get('average_episode_duration')

        # Genres from MAL
        genres = [g.get('name') for g in item['node'].get('genres', [])] if item['node'].get('genres') else None

        # Studios from MAL
        studios = [s.get('name') for s in item['node'].get('studios', [])] if item['node'].get('studios') else None

        # Status from MAL
        status = item['node'].get('status')

        # Start date from MAL (can be string like "2024-01-15" or dict)
        start_date = item['node'].get('start_date')
        year = None
        if start_date:
            if isinstance(start_date, str):
                try:
                    year = int(start_date[:4])
                except (ValueError, TypeError):
                    pass
            elif isinstance(start_date, dict) and start_date.get('year'):
                year = int(start_date['year'])

        # MPAA from MAL
        mpaa = item['node'].get('rating')

        # Start with MAL-specific data
        data = {
            'mal_id': mal_id,
            'progress': progress,
            'show_title': show_title,
            'total_eps': total_eps,
            'poster': poster,
            'is_movie': item['node'].get('media_type') == 'movie' and total_eps == 1,
            'average_score': average_score,
            'duration': duration,
            'genres': genres,
            'studios': studios,
            'status': status,
            'start_date': start_date,
            'year': year,
            'mpaa': mpaa,
        }

        # Enrich with AniList data (overrides None values)
        if anilist_res:
            enrichment = self._extract_anilist_enrichment(anilist_res)
            for key, val in enrichment.items():
                if val is not None and data.get(key) is None:
                    data[key] = val

        return self.build_next_up_item(data)

    @div_flavor
    def _base_watchlist_status_view(self, res, mal_dub=None, anilist_res=None):
        mal_id = res['node']['id']
        if not mal_id:
            control.log(f"Mal ID not found for {mal_id}", level='warning')

        dub = True if mal_dub and mal_dub.get(str(mal_id)) else False

        # Title logic: prefer MAL, fallback to AniList
        title = res['node'].get('title')
        if self.title_lang == 'english':
            title = res['node']['alternative_titles'].get('en') or title
        if not title and anilist_res:
            title = anilist_res.get('title', {}).get(self.title_lang) or anilist_res.get('title', {}).get('romaji') or title
        if title is None:
            title = ''

        # Add relation info (if available)
        if anilist_res and anilist_res.get('relationType'):
            title += ' [I]%s[/I]' % control.colorstr(anilist_res['relationType'], 'limegreen')

        # Plot/synopsis
        plot = res['node'].get('synopsis')
        if not plot and anilist_res and anilist_res.get('description'):
            desc = anilist_res['description']
            desc = desc.replace('<i>', '[I]').replace('</i>', '[/I]')
            desc = desc.replace('<b>', '[B]').replace('</b>', '[/B]')
            desc = desc.replace('<br>', '[CR]')
            desc = desc.replace('\n', '')
            plot = desc

        # Genres
        genre = [x.get('name') for x in res['node'].get('genres', [])]
        if (not genre or not genre) and anilist_res:
            genre = anilist_res.get('genres')

        # Studios
        studio = [x.get('name') for x in res['node'].get('studios', [])]
        if (not studio or not studio) and anilist_res and anilist_res.get('studios'):
            # AniList studios may be list or dict
            if isinstance(anilist_res['studios'], list):
                studio = [s.get('name') for s in anilist_res['studios']] or studio
            elif isinstance(anilist_res['studios'], dict) and 'edges' in anilist_res['studios']:
                studio = [s['node'].get('name') for s in anilist_res['studios']['edges']] or studio

        # Status
        status = res['node'].get('status')
        if not status and anilist_res:
            status = anilist_res.get('status')

        # Duration
        duration = res['node'].get('average_episode_duration')
        if not duration and anilist_res and anilist_res.get('duration'):
            duration = anilist_res.get('duration') * 60 if isinstance(anilist_res.get('duration'), int) else anilist_res.get('duration')

        # Country
        country = None
        if anilist_res:
            country = [anilist_res.get('countryOfOrigin', '')]

        # Rating/score
        rating = res['node'].get('mean')
        info_rating = None
        if isinstance(rating, (float, int)) and rating:
            info_rating = {'score': rating}
        elif anilist_res and anilist_res.get('averageScore'):
            info_rating = {'score': anilist_res.get('averageScore') / 10.0}
            if anilist_res.get('stats') and anilist_res['stats'].get('scoreDistribution'):
                total_votes = sum([score['amount'] for score in anilist_res['stats']['scoreDistribution']])
                info_rating['votes'] = total_votes

        # Trailer
        trailer = None
        if anilist_res and anilist_res.get('trailer'):
            try:
                if anilist_res['trailer']['site'] == 'youtube':
                    trailer = f"plugin://plugin.video.youtube/play/?video_id={anilist_res['trailer']['id']}"
                else:
                    trailer = f"plugin://plugin.video.dailymotion_com/?url={anilist_res['trailer']['id']}&mode=playVideo"
            except (KeyError, TypeError):
                pass

        # Playcount
        eps_watched = res['list_status']["num_episodes_watched"]
        eps = res['node']["num_episodes"]
        playcount = None
        if eps_watched == eps and eps != 0:
            playcount = 1

        # Premiered/year
        start_date = res['node'].get('start_date')
        premiered = None
        year = None
        if not start_date and anilist_res and anilist_res.get('startDate'):
            start_date = anilist_res.get('startDate')
        if start_date:
            if isinstance(start_date, dict):
                premiered = '{}-{:02}-{:02}'.format(
                    int(start_date.get('year', 0) or 0),
                    int(start_date.get('month', 1) or 1),
                    int(start_date.get('day', 1) or 1)
                )
                year = int(start_date.get('year', 0) or 0) if start_date.get('year') is not None else None
            else:
                premiered = str(start_date)
                try:
                    year = int(str(start_date)[:4])
                except Exception:
                    pass

        # Cast
        cast = None
        if anilist_res and anilist_res.get('characters'):
            try:
                cast = []
                for i, x in enumerate(anilist_res['characters'].get('edges', [])):
                    role = x['node']['name']['userPreferred']
                    actor = x['voiceActors'][0]['name']['userPreferred']
                    actor_hs = x['voiceActors'][0]['image']['large']
                    cast.append({'name': actor, 'role': role, 'thumbnail': actor_hs, 'index': i})
            except (IndexError, KeyError, TypeError):
                pass

        # UniqueIDs
        unique_ids = {'mal_id': str(mal_id)}
        if anilist_res and anilist_res.get('id'):
            unique_ids['anilist_id'] = str(anilist_res['id'])
            unique_ids.update(database.get_unique_ids(anilist_res['id'], 'anilist_id'))
        unique_ids.update(database.get_unique_ids(mal_id, 'mal_id'))

        # Art/Images
        show_meta = database.get_show_meta(mal_id)
        kodi_meta = pickle.loads(show_meta.get('art')) if show_meta else {}
        image = res['node']['main_picture'].get('large', res['node']['main_picture']['medium']) if res['node'].get('main_picture') else None
        poster = image
        fanart = kodi_meta.get('fanart', image)
        # AniList fallback for missing images
        if anilist_res and anilist_res.get('coverImage'):
            if not image:
                image = anilist_res['coverImage'].get('extraLarge')
            if not poster:
                poster = anilist_res['coverImage'].get('extraLarge')
            if not fanart:
                fanart = anilist_res['coverImage'].get('extraLarge')

        info = {
            'UniqueIDs': unique_ids,
            'title': title,           # Title
            'plot': plot,             # Plot/Synopsis
            'genre': genre,           # Genres
            'studio': studio,         # Studios
            'status': status,         # Status
            'duration': duration,     # Duration
            'country': country,       # Country
            'mediatype': 'tvshow',
        }
        if info_rating:
            info['rating'] = info_rating
        if playcount:
            info['playcount'] = playcount
        if premiered:
            info['premiered'] = premiered
        if year:
            info['year'] = year
        if cast:
            info['cast'] = cast
        if trailer:
            info['trailer'] = trailer
        if anilist_res and anilist_res.get('countryOfOrigin'):
            info['mpaa'] = anilist_res.get('countryOfOrigin')
        elif res['node'].get('rating'):
            info['mpaa'] = res['node'].get('rating')

        base = {
            "name": f"{title} - {eps_watched}/{eps}",
            "url": f'watchlist_to_ep/{mal_id}/{eps_watched}',
            "image": image,
            "poster": poster,
            'fanart': fanart,
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

        # Movie logic
        if res['node']['media_type'] == 'movie' and eps == 1:
            base['url'] = f'play_movie/{mal_id}/'
            base['info']['mediatype'] = 'movie'
            return utils.parse_view(base, False, True, dub)
        return utils.parse_view(base, True, False, dub)

    def get_watchlist_anime_entry(self, mal_id):
        params = {
            "fields": 'my_list_status,num_episodes'
        }

        url = f'{self._URL}/anime/{mal_id}'
        r = client.get(url, headers=self.__headers(), params=params)
        data = r.json() if r else {}
        results = data.get('my_list_status', {})
        if not results:
            return {}
        anime_entry = {
            'eps_watched': results['num_episodes_watched'],
            'status': results['status'],
            'score': results['score'],
            'total_episodes': data.get('num_episodes')
        }
        return anime_entry

    def save_completed(self):
        data = self.get_user_anime_list('completed')
        completed_ids = {}
        for dat in data:
            mal_id = dat['node']['id']
            try:
                completed_ids[str(mal_id)] = int(dat['node']['num_episodes'])
            except KeyError:
                pass
        return completed_ids

    def get_user_anime_list(self, status):
        fields = [
            'list_status',
            'num_episodes',
            'status'
        ]
        params = {
            'status': status,
            "nsfw": True,
            'limit': 1000,
            "fields": ','.join(fields)
        }
        r = client.get(f'{self._URL}/users/@me/animelist', headers=self.__headers(), params=params)
        res = r.json() if r else {}
        paging = res.get('paging', {})
        data = res.get('data', [])
        while paging.get('next'):
            r = client.get(paging['next'], headers=self.__headers())
            res = r.json() if r else {}
            paging = res.get('paging', {})
            data += res.get('data', [])
        return data

    def update_list_status(self, mal_id, status):
        from resources.lib.ui.database import clear_watchlist_cache
        data = {
            "status": status,
        }
        r = client.put(f'{self._URL}/anime/{mal_id}/my_list_status', headers=self.__headers(), data=data)
        if r and r.ok:
            clear_watchlist_cache(self._NAME)  # Clear all statuses since item moved
        return r and r.ok

    def update_num_episodes(self, mal_id, episode):
        from resources.lib.ui.database import clear_watchlist_cache
        data = {
            'num_watched_episodes': int(episode)
        }
        r = client.put(f'{self._URL}/anime/{mal_id}/my_list_status', headers=self.__headers(), data=data)
        if r and r.ok:
            clear_watchlist_cache(self._NAME)  # Clear cache to reflect progress
        return r and r.ok

    def update_score(self, mal_id, score):
        from resources.lib.ui.database import clear_watchlist_cache
        data = {
            "score": score,
        }
        r = client.put(f'{self._URL}/anime/{mal_id}/my_list_status', headers=self.__headers(), data=data)
        if r and r.ok:
            clear_watchlist_cache(self._NAME)  # Clear cache to reflect score
        return r and r.ok

    def delete_anime(self, mal_id):
        from resources.lib.ui.database import clear_watchlist_cache
        r = client.delete(f'{self._URL}/anime/{mal_id}/my_list_status', headers=self.__headers())
        if r and r.ok:
            clear_watchlist_cache(self._NAME)  # Clear cache after deletion
        return r and r.ok
