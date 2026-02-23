import pickle
import random

from resources.lib.ui import utils, database, client, control, get_meta
from resources.lib.WatchlistFlavor.WatchlistFlavorBase import WatchlistFlavorBase
from resources.lib.ui.divide_flavors import div_flavor


class SimklWLF(WatchlistFlavorBase):
    _NAME = 'simkl'
    _URL = 'https://api.simkl.com'
    _TITLE = 'Simkl'
    _NAME = 'simkl'
    _IMAGE = "simkl.png"

    api_info = database.get_info('Simkl')
    client_id = api_info['client_id']

    def __headers(self):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f'Bearer {self.token}',
            "simkl-api-key": self.client_id
        }
        return headers

    def login(self):
        params = {
            'client_id': self.client_id,
        }

        r = client.get(f'{self._URL}/oauth/pin', params=params)
        device_code = r.json() if r else {}

        copied = control.copy2clip(device_code["user_code"])
        display_dialog = (f"{control.lang(30081).format(control.colorstr('https://simkl.com/pin'))}[CR]"
                          f"{control.lang(30082).format(control.colorstr(device_code['user_code']))}")
        if copied:
            display_dialog = f"{display_dialog}[CR]{control.lang(30083)}"
        control.progressDialog.create('SIMKL Auth', display_dialog)
        control.progressDialog.update(100)
        inter = int(device_code['expires_in'] / device_code['interval'])
        for i in range(inter):
            if control.progressDialog.iscanceled():
                control.progressDialog.close()
                return
            control.sleep(device_code['interval'] * 1000)

            r = client.get(f'{self._URL}/oauth/pin/{device_code["user_code"]}', params=params)
            r = r.json() if r else {}
            if r.get('result') == 'OK':
                self.token = r['access_token']
                login_data = {'token': self.token}
                r = client.post(f'{self._URL}/users/settings', headers=self.__headers(), json_data={})
                if r:
                    user = r.json()['user']
                    login_data['username'] = user['name']
                return login_data
            new_display_dialog = f"{display_dialog}[CR]Code Valid for {control.colorstr(device_code['expires_in'] - i * device_code['interval'])} Seconds"
            control.progressDialog.update(int((inter - i) / inter * 100), new_display_dialog)

    def watchlist(self):
        statuses = [
            ("Currently Watching", "watching", 'currently_watching.png'),
            ("Completed", "completed", 'completed.png'),
            ("On Hold", "hold", 'on_hold.png'),
            # ("Dropped", "notinteresting", 'on_hold.png'),
            ("Dropped", "dropped", 'dropped.png'),
            ("Plan to Watch", "plantowatch", 'want_to_watch.png'),
            ("All Anime", "ALL", 'all_anime.png')
        ]
        return [utils.allocate_item(res[0], f'watchlist_status_type/{self._NAME}/{res[1]}', True, False, [], res[2], {}) for res in statuses]

    @staticmethod
    def action_statuses():
        actions = [
            ("Add to On Currently Watching", "watching"),
            ("Add to Completed", "completed"),
            ("Add to On Hold", "hold"),
            ("Add to Dropped", "dropped"),
            # ("Add to Dropped", "notinteresting"),
            ("Add to Plan to Watch", "plantowatch"),
            ("Set Score", "set_score"),
            ("Delete", "DELETE")
        ]
        return actions

    def _base_watchlist_view(self, res):
        url = f'watchlist_status_type/{self._NAME}/{res[1]}'
        return [utils.allocate_item(res[0], url, True, False, [], f'{res[0].lower()}.png', {})]

    @staticmethod
    def handle_paging(hasmore, base_url, page):
        if not hasmore or not control.is_addon_visible() and control.getBool('widget.hide.nextpage'):
            return []
        next_page = page + 1
        name = "Next Page (%d)" % next_page
        return [utils.allocate_item(name, f'{base_url}?page={next_page}', True, False, [], 'next.png', {'plot': name}, fanart='next.png')]

    def get_watchlist_status(self, status, next_up, offset, page, cache_only=False):
        # Check for remote changes before using cache
        self._should_refresh_cache()

        # Handle Next Up separately - it needs special episode-level processing
        if next_up and not cache_only:
            return self._get_next_up_episodes(status, offset, page)

        from resources.lib.ui.database import (
            get_watchlist_cache, save_watchlist_cache, 
            is_watchlist_cache_valid, get_watchlist_cache_count
        )
        
        paging_enabled = control.getBool('interface.watchlist.paging')
        per_page = control.getInt('interface.perpage.watchlist') if paging_enabled else 0
        offset = int(offset) if offset else 0

        # Check cache validity
        if not is_watchlist_cache_valid(self._NAME, status):
            # Fetch all items from API and cache them (raw items only)
            results = self.get_all_items(status)
            if results and results.get('anime'):
                save_watchlist_cache(self._NAME, status, results['anime'])
        
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
        import pickle
        items = [pickle.loads(item['data']) for item in cached_items]

        # Get the progress of the item
        def get_progress(item):
            try:
                text = item['name']
                progress_parts = text.rsplit(" - ", 1)
                if len(progress_parts) == 2:
                    current = int(progress_parts[1].split("/")[0])
                else:
                    current = 0
            except Exception:
                current = 0
            return current

        # Fetch AniList data for current page items only (fast for small batches)
        mal_ids = [anime['show']['ids']['mal'] for anime in items if anime['show']['ids'].get('mal')]
        mal_id_dicts = [{'mal_id': mid} for mid in mal_ids]
        get_meta.collect_meta(mal_id_dicts)

        try:
            from resources.lib.endpoints.anilist import Anilist
            anilist_data = Anilist().get_enrichment_for_mal_ids(mal_ids)
        except Exception:
            anilist_data = []

        # Build AniList lookup by MAL ID
        anilist_by_mal_id = {str(item.get('idMal')): item for item in anilist_data if item.get('idMal')}

        # Pass AniList data to view functions
        def viewfunc(res):
            mal_id = str(res['show']['ids'].get('mal'))
            anilist_item = anilist_by_mal_id.get(mal_id)
            return self._base_watchlist_status_view(res, anilist_res=anilist_item)

        all_results = list(filter(None, map(viewfunc, items)))

        # Apply sorting
        if int(self.sort) == 0:  # anime_title
            all_results = sorted(all_results, key=lambda x: x['info']['title'].lower() if x['info'].get('title') else '')
        elif int(self.sort) == 1:    # user_rating
            all_results = sorted(all_results, key=lambda x: x['info'].get('user_rating') or 0, reverse=True)
        elif int(self.sort) == 2:    # progress
            all_results = sorted(all_results, key=get_progress)
        elif int(self.sort) == 3:    # list_updated_at
            all_results = sorted(all_results, key=lambda x: x['info'].get('last_watched') or "0", reverse=True)
        elif int(self.sort) == 4:    # last_added
            all_results.reverse()

        if int(self.order) == 1:
            all_results.reverse()

        # Add paging if enabled
        if paging_enabled and per_page > 0:
            has_next = (offset + per_page) < total_count
            all_results += self.handle_paging(has_next, f'watchlist_status_type_pages/simkl/{status}/{offset + per_page}', page)

        return all_results

    def _get_next_up_episodes(self, status, offset, page):
        """
        Get Next Up episodes - Episode-driven list of next unwatched episodes.

        Next Up Rules:
        - All anime in Watching list are included
        - Shows with 0 progress show Episode 1 as next up
        - Only the immediate next unwatched episode is shown per anime
        - Sorted by last watched activity (last_watched_at)
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
            # Fetch all "watching" items
            results = self.get_all_items('watching')
            all_data = results.get('anime', []) if results else []

            # Filter: Shows that have a valid next episode to watch
            # Includes shows with 0 progress (Episode 1 is their next up)
            filtered_data = []
            for item in all_data:
                eps_watched = item.get('watched_episodes_count') or 0
                total_eps = item.get('total_episodes_count') or 0

                # Skip if show is completed (all episodes watched)
                # total_eps == 0 means unknown/ongoing, so include it
                if total_eps > 0 and eps_watched >= total_eps:
                    continue

                filtered_data.append(item)

            # Sort by last_watched_at (most recent first)
            filtered_data.sort(
                key=lambda x: x.get('last_watched_at') or '',
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
        mal_ids = [anime['show']['ids']['mal'] for anime in items if anime['show']['ids'].get('mal')]
        mal_id_dicts = [{'mal_id': mid} for mid in mal_ids]
        get_meta.collect_meta(mal_id_dicts)

        # Fetch AniList data for additional metadata
        try:
            from resources.lib.endpoints.anilist import Anilist
            anilist_data = Anilist().get_enrichment_for_mal_ids(mal_ids)
        except Exception:
            anilist_data = []

        anilist_by_mal_id = {str(item.get('idMal')): item for item in anilist_data if item.get('idMal')}

        # Process each anime to build next up episode items
        def process_next_up_item(item):
            try:
                mal_id = str(item['show']['ids'].get('mal', ''))
                anilist_item = anilist_by_mal_id.get(mal_id)
                return self._build_next_up_episode(item, anilist_res=anilist_item)
            except Exception as e:
                control.log(f"Error processing Next Up for Simkl: {str(e)}", level='warning')
                return None

        # Process items in parallel
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
        url = f'watchlist_status_type_pages/simkl/watching/{next_offset}?page={next_page}&next_up=true'
        return [utils.allocate_item(name, url, True, False, [], 'next.png', {'plot': name}, fanart='next.png')]

    def _build_next_up_episode(self, res, anilist_res=None):
        """Build a Next Up episode item by extracting Simkl data and using the shared builder."""
        show_ids = res['show']['ids']
        anilist_id = show_ids.get('anilist')
        mal_id = show_ids.get('mal')
        kitsu_id = show_ids.get('kitsu')

        progress = res.get('watched_episodes_count') or 0
        total_eps = res.get('total_episodes_count') or 0

        # Get show title
        show_title = res['show'].get('title', '')

        # Poster from Simkl
        poster = f'https://wsrv.nl/?url=https://simkl.in/posters/{res["show"]["poster"]}_m.jpg' if res['show'].get('poster') else None

        # Year from Simkl
        year = res['show'].get('year')

        # Start with Simkl-specific data
        data = {
            'mal_id': mal_id,
            'anilist_id': anilist_id,
            'kitsu_id': kitsu_id,
            'progress': progress,
            'show_title': show_title,
            'total_eps': total_eps,
            'poster': poster,
            'is_movie': total_eps == 1,
            'year': year,
        }

        # Enrich with AniList data (overrides None values)
        if anilist_res:
            enrichment = self._extract_anilist_enrichment(anilist_res)
            for key, val in enrichment.items():
                if val is not None and data.get(key) is None:
                    data[key] = val
            # AniList title override
            al_title = anilist_res.get('title', {}).get(self.title_lang) or anilist_res.get('title', {}).get('romaji')
            if al_title:
                data['show_title'] = al_title

        return self.build_next_up_item(data)

    @div_flavor
    def _base_watchlist_status_view(self, res, mal_dub=None, anilist_res=None):
        show_ids = res['show']['ids']
        anilist_id = show_ids.get('anilist')
        mal_id = show_ids.get('mal')
        kitsu_id = show_ids.get('kitsu')

        if not mal_id:
            control.log(f"Mal ID not found for {show_ids}", 'warning')

        dub = True if mal_dub and mal_dub.get(str(mal_id)) else False

        show = database.get_show(mal_id)
        kodi_meta = pickle.loads(show['kodi_meta']) if show else {}

        # Title logic: prefer AniList for title_lang support, fallback to Simkl
        title = res['show']['title']
        if anilist_res:
            title = anilist_res.get('title', {}).get(self.title_lang) or anilist_res.get('title', {}).get('romaji') or title
        if title is None:
            title = ''

        # Add relation info (if available)
        if anilist_res and anilist_res.get('relationType'):
            title += ' [I]%s[/I]' % control.colorstr(anilist_res['relationType'], 'limegreen')

        # Plot/synopsis
        plot = None
        if anilist_res and anilist_res.get('description'):
            desc = anilist_res['description']
            desc = desc.replace('<i>', '[I]').replace('</i>', '[/I]')
            desc = desc.replace('<b>', '[B]').replace('</b>', '[/B]')
            desc = desc.replace('<br>', '[CR]')
            desc = desc.replace('\n', '')
            plot = desc

        # Genres
        genre = None
        if anilist_res:
            genre = anilist_res.get('genres')

        # Studios
        studio = None
        if anilist_res and anilist_res.get('studios'):
            if isinstance(anilist_res['studios'], list):
                studio = [s.get('name') for s in anilist_res['studios']]
            elif isinstance(anilist_res['studios'], dict) and 'edges' in anilist_res['studios']:
                studio = [s['node'].get('name') for s in anilist_res['studios']['edges']]

        # Status
        status = None
        if anilist_res:
            status = anilist_res.get('status')

        # Duration
        duration = None
        if anilist_res and anilist_res.get('duration'):
            duration = anilist_res.get('duration') * 60 if isinstance(anilist_res.get('duration'), int) else anilist_res.get('duration')

        # Country
        country = None
        if anilist_res:
            country = [anilist_res.get('countryOfOrigin', '')]

        # Rating/score
        info_rating = None
        if anilist_res and anilist_res.get('averageScore'):
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
        playcount = None
        if res["total_episodes_count"] != 0 and res["watched_episodes_count"] == res["total_episodes_count"]:
            playcount = 1

        # Premiered/year
        premiered = None
        year = None
        if anilist_res and anilist_res.get('startDate'):
            start_date = anilist_res.get('startDate')
            if isinstance(start_date, dict):
                y = int(start_date.get('year', 0) or 0)
                m = int(start_date.get('month', 1) or 1)
                d = int(start_date.get('day', 1) or 1)
                premiered = '{}-{:02}-{:02}'.format(y, m, d)
                year = y if y else None

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
        unique_ids = {
            'anilist_id': str(anilist_id),
            'mal_id': str(mal_id),
            'kitsu_id': str(kitsu_id),
            **database.get_unique_ids(anilist_id, 'anilist_id'),
            **database.get_unique_ids(mal_id, 'mal_id'),
            **database.get_unique_ids(kitsu_id, 'kitsu_id')
        }

        # Art/Images
        image = f'https://wsrv.nl/?url=https://simkl.in/posters/{res["show"]["poster"]}_m.jpg'
        show_meta = database.get_show_meta(mal_id)
        kodi_meta = pickle.loads(show_meta.get('art')) if show_meta else {}
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
            'title': title,
            'plot': plot,
            'genre': genre,
            'studio': studio,
            'status': status,
            'duration': duration,
            'country': country,
            'mediatype': 'tvshow',
            'year': year if year else res['show']['year'],
            'last_watched': res['last_watched_at'],
            'user_rating': res['user_rating']
        }
        if info_rating:
            info['rating'] = info_rating
        if playcount:
            info['playcount'] = playcount
        if premiered:
            info['premiered'] = premiered
        if cast:
            info['cast'] = cast
        if trailer:
            info['trailer'] = trailer

        base = {
            "name": '%s - %d/%d' % (title, res["watched_episodes_count"], res["total_episodes_count"]),
            "url": f'watchlist_to_ep/{mal_id}/{res["watched_episodes_count"]}',
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

        if res["total_episodes_count"] == 1:
            base['url'] = f'play_movie/{mal_id}/'
            base['info']['mediatype'] = 'movie'
            return utils.parse_view(base, False, True, dub)
        return utils.parse_view(base, True, False, dub)

    def get_watchlist_anime_entry(self, mal_id):
        data = [{"mal": int(mal_id)}]
        r = client.post(f'{self._URL}/sync/watched?extended=counters', headers=self.__headers(), json_data=data)
        if not r:
            return {}
        results = r.json()
        if not results or not isinstance(results, list):
            return {}
        item = results[0] if results else {}
        if not item or item.get('result') is not True:
            return {}
        anime_entry = {
            'eps_watched': item.get('episodes_watched', 0),
            'status': item.get('list', ''),
            'score': item.get('user_rating', 0),
            'total_episodes': item.get('episodes_total')
        }
        return anime_entry

    def save_completed(self):
        data = self.get_all_items('completed')
        completed = {}
        for dat in data['anime']:
            completed[str(dat['show']['ids']['mal'])] = dat['total_episodes_count']
        return completed

    def get_all_items(self, status):
        # status values: watching, plantowatch, hold ,completed ,dropped (notinteresting for old api's).
        params = {
            'extended': 'full',
            # 'next_watch_info': 'yes'
        }
        r = client.get(f'{self._URL}/sync/all-items/anime/{status}', headers=self.__headers(), params=params)
        return r.json() if r else {}

    def get_last_activity_timestamp(self):
        """Check Simkl's /sync/activities endpoint for the latest anime list activity."""
        r = client.get(f'{self._URL}/sync/activities', headers=self.__headers())
        if not r:
            return None
        data = r.json()
        anime = data.get('anime', {})
        # Collect all activity timestamps and return the most recent
        timestamps = [
            anime.get('all', ''),
            anime.get('rated_at', ''),
            anime.get('watchlist', ''),
            anime.get('collected_at', ''),
            anime.get('dropped_at', ''),
        ]
        timestamps = [t for t in timestamps if t]
        return max(timestamps) if timestamps else None

    def update_list_status(self, mal_id, status):
        from resources.lib.ui.database import clear_watchlist_cache
        data = {
            "shows": [{
                "to": status,
                "ids": {
                    "mal": mal_id
                }
            }]
        }
        r = client.post(f'{self._URL}/sync/add-to-list', headers=self.__headers(), json_data=data)
        if r:
            r = r.json()
            if not r['not_found']['shows'] or not r['not_found']['shows']:
                clear_watchlist_cache(self._NAME)  # Clear all statuses since item moved
                if status == 'completed' and r.get('added', {}).get('shows', [{}])[0].get('to') == 'watching':
                    return 'watching'
                return True
        return False

    def update_num_episodes(self, mal_id, episode):
        from resources.lib.ui.database import clear_watchlist_cache
        data = {
            "shows": [{
                "ids": {
                    "mal": mal_id
                },
                "episodes": [{'number': i} for i in range(1, int(episode) + 1)]
            }]
        }
        r = client.post(f'{self._URL}/sync/history', headers=self.__headers(), json_data=data)
        if r:
            r = r.json()
            if not r['not_found']['shows'] or not r['not_found']['movies']:
                clear_watchlist_cache(self._NAME)  # Clear cache to reflect progress
                return True
        return False

    def update_score(self, mal_id, score):
        from resources.lib.ui.database import clear_watchlist_cache
        data = {
            "shows": [{
                'rating': score,
                "ids": {
                    "mal": mal_id,
                }
            }]
        }
        url = f"{self._URL}/sync/ratings"
        if score == 0:
            url = f"{url}/remove"

        r = client.post(url, headers=self.__headers(), json_data=data)
        if r:
            r = r.json()
            if not r['not_found']['shows'] or not r['not_found']['movies']:
                clear_watchlist_cache(self._NAME)  # Clear cache to reflect score
                return True
        return False

    def delete_anime(self, mal_id):
        from resources.lib.ui.database import clear_watchlist_cache
        data = {
            "shows": [{
                "ids": {
                    "mal": mal_id
                }
            }]
        }
        r = client.post(f"{self._URL}/sync/history/remove", headers=self.__headers(), json_data=data)
        if r:
            r = r.json()
            if not r['not_found']['shows'] or not r['not_found']['movies']:
                clear_watchlist_cache(self._NAME)  # Clear cache after deletion
                return True
        return False
