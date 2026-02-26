import time
import random
import pickle

from resources.lib.ui import client, control, database, utils, get_meta
from resources.lib.WatchlistFlavor.WatchlistFlavorBase import WatchlistFlavorBase
from resources.lib.indexers.simkl import SIMKLAPI
from urllib import parse

from resources.lib.ui.divide_flavors import div_flavor


class KitsuWLF(WatchlistFlavorBase):
    _NAME = "kitsu"
    _URL = "https://kitsu.io/api"
    _TITLE = "Kitsu"
    _IMAGE = "kitsu.png"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mapping = []

    def __headers(self):
        headers = {
            'Content-Type': 'application/vnd.api+json',
            'Accept': 'application/vnd.api+json',
            'Authorization': f'Bearer {self.token}'
        }
        return headers

    def get_last_activity_timestamp(self):
        """Check Kitsu user profile's updatedAt to detect remote changes."""
        r = client.get(
            f'{self._URL}/edge/users/{self.user_id}',
            headers=self.__headers(),
            params={'fields[users]': 'updatedAt,statsData'}
        )
        if not r:
            return None
        data = r.json()
        user_data = data.get('data', {}).get('attributes', {})
        updated_at = user_data.get('updatedAt', '')
        return updated_at if updated_at else None

    def login(self):
        params = {
            "grant_type": "password",
            "username": self.auth_var,
            "password": self.password
        }
        resp = client.post(f'{self._URL}/oauth/token', json_data=params)

        if not resp:
            return

        data = resp.json()
        self.token = data['access_token']
        resp2 = client.get(f'{self._URL}/edge/users', headers=self.__headers(), params={'filter[self]': True})
        data2 = resp2.json()["data"][0]

        login_data = {
            'username': data2["attributes"]["name"],
            'userid': data2['id'],
            'token': data['access_token'],
            'refresh': data['refresh_token'],
            'expiry': int(time.time()) + int(data['expires_in'])
        }
        return login_data

    def refresh_token(self):
        params = {
            "grant_type": "refresh_token",
            "refresh_token": control.getSetting('kitsu.refresh')
        }
        resp = client.post(f'{self._URL}/oauth/token', json_data=params)

        if not resp:
            return

        data = resp.json()
        control.setSetting('kitsu.token', data['access_token'])
        control.setSetting('kitsu.refresh', data['refresh_token'])
        control.setInt('kitsu.expiry', int(time.time() + int(data['expires_in'])))

    @staticmethod
    def handle_paging(next_offset, base_url, page):
        if not control.is_addon_visible() and control.getBool('widget.hide.nextpage'):
            return []
        next_page = page + 1
        name = "Next Page (%d)" % next_page
        return [utils.allocate_item(name, f'{base_url}/{next_offset}?page={next_page}', True, False, [], 'next.png', {'plot': name}, fanart='next.png')]

    def __get_sort(self):
        # Mapping:
        # 0: Anime Title -> sort by anime.titles.{language} alphabetically
        # 1: Score -> sort by anime.averageRating descending
        # 2: Progress -> sort by progress descending
        # 3: Last Updated -> sort by progressed_at descending
        # 4: Last Added -> sort by started_at descending
        sort_options = [
            f"anime.titles.{self.__get_title_lang()}",
            "-anime.averageRating",
            "progress",
            "-progressed_at",
            "-started_at",
        ]
        return sort_options[int(self.sort)]

    def __get_title_lang(self):
        title_langs = {
            "english": "en",
            "romaji": "en_jp",
        }
        return title_langs[self.title_lang]

    def watchlist(self):
        statuses = [
            ("Current", "current", 'currently_watching.png'),
            ("Want to Watch", "planned", 'want_to_watch.png'),
            ("Completed", "completed", 'completed.png'),
            ("On Hold", "on_hold", 'on_hold.png'),
            ("Dropped", "dropped", 'dropped.png')
        ]
        return [utils.allocate_item(res[0], f'watchlist_status_type/{self._NAME}/{res[1]}', True, False, [], res[2], {}) for res in statuses]

    @staticmethod
    def action_statuses():
        actions = [
            ("Add to Current", "current"),
            ("Add to Want to Watch", "planned"),
            ("Add to On Hold", "on_hold"),
            ("Add to Completed", "completed"),
            ("Add to Dropped", "dropped"),
            ("Set Score", "set_score"),
            ("Delete", "DELETE")
        ]
        return actions

    def get_watchlist_status(self, status, next_up, offset, page, cache_only=False):
        # Check for remote changes before using cache
        self._should_refresh_cache()

        from resources.lib.ui.database import (
            get_watchlist_cache, save_watchlist_cache,
            is_watchlist_cache_valid, get_watchlist_cache_count
        )

        paging_enabled = control.getBool('interface.watchlist.paging')
        per_page = control.getInt('interface.perpage.watchlist') if paging_enabled else 1000
        offset = int(offset) if offset else 0

        # Check cache validity
        if not is_watchlist_cache_valid(self._NAME, status):
            # Fetch all items from API
            url = f'{self._URL}/edge/library-entries'
            # Note: Don't use fields[anime] sparse fieldset - it breaks relationships needed for mappings
            params = {
                "fields[mappings]": "externalSite,externalId",
                "filter[user_id]": self.user_id,
                "filter[kind]": "anime",
                "filter[status]": status,
                "include": "anime,anime.mappings",
                "page[limit]": 20,
                "page[offset]": 0,
                "sort": self.__get_sort(),
            }

            all_data = []
            all_mappings = {}  # Build mapping dict: kitsu_id -> mal_id
            result = client.get(url, headers=self.__headers(), params=params)
            result = result.json() if result else {}

            if result.get('data'):
                _list = result.get("data", [])
                included = result.get('included', [])

                # Separate anime and mappings from included
                anime_by_id = {x['id']: x for x in included if x['type'] == 'anime'}
                mappings_by_id = {x['id']: x for x in included if x['type'] == 'mappings'}

                # Build kitsu_id -> mal_id lookup dict by checking anime's mapping relationships
                for anime_id, anime in anime_by_id.items():
                    mapping_refs = anime.get('relationships', {}).get('mappings', {}).get('data', [])
                    for ref in mapping_refs:
                        mapping = mappings_by_id.get(ref['id'])
                        if mapping and mapping['attributes']['externalSite'] == 'myanimelist/anime':
                            all_mappings[anime_id] = mapping['attributes']['externalId']
                            break

                # Store items with their anime data
                for item in _list:
                    anime_id = item['relationships']['anime']['data']['id']
                    anime_data = anime_by_id.get(anime_id)
                    all_data.append({
                        'entry': item,
                        'anime': anime_data,
                        'mal_id': all_mappings.get(anime_id, '')
                    })

                # Fetch remaining pages
                while result.get('links', {}).get('next'):
                    result = client.get(result['links']['next'], headers=self.__headers())
                    result = result.json() if result else {}
                    if result.get('data'):
                        _list = result.get("data", [])
                        included = result.get('included', [])

                        anime_by_id = {x['id']: x for x in included if x['type'] == 'anime'}
                        mappings_by_id = {x['id']: x for x in included if x['type'] == 'mappings'}

                        # Build kitsu_id -> mal_id lookup dict by checking anime's mapping relationships
                        for anime_id, anime in anime_by_id.items():
                            mapping_refs = anime.get('relationships', {}).get('mappings', {}).get('data', [])
                            for ref in mapping_refs:
                                mapping = mappings_by_id.get(ref['id'])
                                if mapping and mapping['attributes']['externalSite'] == 'myanimelist/anime':
                                    all_mappings[anime_id] = mapping['attributes']['externalId']
                                    break

                        for item in _list:
                            anime_id = item['relationships']['anime']['data']['id']
                            anime_data = anime_by_id.get(anime_id)
                            all_data.append({
                                'entry': item,
                                'anime': anime_data,
                                'mal_id': all_mappings.get(anime_id, '')
                            })

            # Apply ordering before saving to cache
            if all_data and int(self.order) == 1:
                all_data.reverse()

            if all_data:
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

        return self.process_watchlist_view(items, next_up, f'watchlist_status_type_pages/kitsu/{status}', page, offset, per_page, total_count, paging_enabled)

    def process_watchlist_view(self, items, next_up, base_plugin_url, page, offset, per_page, total_count, paging_enabled):
        if not items:
            return []

        # Handle Next Up separately - it needs special episode-level processing
        if next_up:
            return self._process_next_up_view(items, base_plugin_url, page, offset, per_page, total_count, paging_enabled)

        # Collect all MAL IDs from pre-computed cache data
        mal_ids = [item.get('mal_id') for item in items if item.get('mal_id')]
        mal_id_dicts = [{'mal_id': mid} for mid in mal_ids]
        get_meta.collect_meta(mal_id_dicts)

        # Fetch AniList data for current page items only (fast for small batches)
        try:
            from resources.lib.endpoints.anilist import Anilist
            anilist_data = Anilist().get_enrichment_for_mal_ids(mal_ids)
        except Exception:
            anilist_data = []

        # Build AniList lookup by MAL ID
        anilist_by_mal_id = {str(item.get('idMal')): item for item in anilist_data if item.get('idMal')}

        # Pass AniList data to view functions
        def viewfunc(cache_item):
            res = cache_item['entry']
            eres = cache_item['anime']
            if not eres:
                return None
            mal_id = str(cache_item.get('mal_id', ''))
            anilist_item = anilist_by_mal_id.get(mal_id)
            return self._base_watchlist_view(res, eres, mal_id=mal_id, anilist_res=anilist_item)

        all_results = [r for r in [viewfunc(item) for item in items] if r is not None]

        # Handle paging
        if paging_enabled and per_page > 0:
            next_offset = offset + per_page
            if next_offset < total_count:
                all_results += self.handle_paging(next_offset, base_plugin_url, page)

        return all_results

    def _process_next_up_view(self, items, base_plugin_url, page, offset, per_page, total_count, paging_enabled):
        """
        Process Next Up episodes - Episode-driven list of next unwatched episodes.

        Next Up Rules:
        - All anime in Current list are included
        - Shows with 0 progress show Episode 1 as next up
        - Only the immediate next unwatched episode is shown per anime
        - Sorted by last watched activity
        - Only aired episodes are included (if playlist.unaired is disabled)
        - Completed shows are excluded
        - Format: "Show Name 01x13 - Episode Title"
        """
        # Filter: Shows that have a valid next episode to watch
        # Includes shows with 0 progress (Episode 1 is their next up)
        filtered_items = []
        for cache_item in items:
            res = cache_item['entry']
            eres = cache_item['anime']
            if not eres:
                continue
            progress = res["attributes"].get('progress') or 0
            total_eps = eres["attributes"].get('episodeCount') or 0

            # Skip if show is completed (all episodes watched)
            # total_eps == 0 means unknown/ongoing, so include it
            if total_eps > 0 and progress >= total_eps:
                continue

            filtered_items.append(cache_item)

        if not filtered_items:
            return []

        # Collect all MAL IDs from pre-computed cache data
        mal_ids = [item.get('mal_id') for item in filtered_items if item.get('mal_id')]
        mal_id_dicts = [{'mal_id': mid} for mid in mal_ids]
        get_meta.collect_meta(mal_id_dicts)

        # Fetch AniList data for current page items only
        try:
            from resources.lib.endpoints.anilist import Anilist
            anilist_data = Anilist().get_enrichment_for_mal_ids(mal_ids)
        except Exception:
            anilist_data = []

        # Build AniList lookup by MAL ID
        anilist_by_mal_id = {str(item.get('idMal')): item for item in anilist_data if item.get('idMal')}

        # Process each anime to build next up episode items
        def process_next_up_item(cache_item):
            try:
                res = cache_item['entry']
                eres = cache_item['anime']
                mal_id = str(cache_item.get('mal_id', ''))
                anilist_item = anilist_by_mal_id.get(mal_id)
                return self._build_next_up_episode(res, eres, mal_id=mal_id, anilist_res=anilist_item)
            except Exception as e:
                control.log(f"Error processing Next Up for Kitsu: {str(e)}", level='warning')
                return None

        # Process items in parallel
        all_results = utils.parallel_process(filtered_items, process_next_up_item, max_workers=5)
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
        url = f'watchlist_status_type_pages/kitsu/current/{next_offset}?page={next_page}&next_up=true'
        return [utils.allocate_item(name, url, True, False, [], 'next.png', {'plot': name}, fanart='next.png')]

    def _build_next_up_episode(self, res, eres, mal_id=None, anilist_res=None):
        """Build a Next Up episode item by extracting Kitsu data and using the shared builder."""
        kitsu_id = eres['id']
        if not mal_id:
            mal_id = self.mapping_mal(kitsu_id)

        progress = res["attributes"].get('progress') or 0
        total_eps = eres["attributes"].get('episodeCount') or 0

        # Get show title
        show_title = eres["attributes"]["titles"].get(self.__get_title_lang(), eres["attributes"].get('canonicalTitle', ''))
        if not show_title and anilist_res:
            show_title = anilist_res.get('title', {}).get(self.title_lang) or anilist_res.get('title', {}).get('romaji') or ''

        # Poster from Kitsu
        poster_image = eres["attributes"].get('posterImage', {})
        poster = poster_image.get('large', poster_image.get('original')) if poster_image else None
        if not poster and anilist_res and anilist_res.get('coverImage'):
            poster = anilist_res['coverImage'].get('extraLarge') or anilist_res['coverImage'].get('large')

        # Rating from Kitsu (0-100 scale → 0-10)
        average_score = None
        try:
            rating = float(eres['attributes'].get('averageRating', 0))
            if rating:
                average_score = rating / 10
        except (TypeError, ValueError):
            pass

        # Duration from Kitsu (minutes → seconds)
        duration = None
        try:
            ep_len = eres['attributes'].get('episodeLength')
            if ep_len:
                duration = ep_len * 60
        except (TypeError, ValueError):
            pass

        # Trailer from Kitsu
        trailer = None
        if eres['attributes'].get('youtubeVideoId'):
            trailer = f"plugin://plugin.video.youtube/play/?video_id={eres['attributes']['youtubeVideoId']}"

        # MPAA from Kitsu
        mpaa = eres['attributes'].get('ageRating')

        # Start with Kitsu-specific data
        data = {
            'mal_id': mal_id,
            'kitsu_id': kitsu_id,
            'progress': progress,
            'show_title': show_title,
            'total_eps': total_eps,
            'poster': poster,
            'is_movie': eres['attributes'].get('subtype') == 'movie' and total_eps == 1,
            'average_score': average_score,
            'duration': duration,
            'trailer': trailer,
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
    def _base_watchlist_view(self, res, eres, mal_dub=None, mal_id=None, anilist_res=None):
        kitsu_id = eres['id']
        if not mal_id:
            mal_id = self.mapping_mal(kitsu_id)

        if not mal_id:
            control.log(f"Mal ID not found for {kitsu_id}", level='warning')

        dub = True if mal_dub and mal_dub.get(str(mal_id)) else False

        # Title logic: prefer Kitsu, fallback to AniList
        title = eres["attributes"]["titles"].get(self.__get_title_lang(), eres["attributes"]['canonicalTitle'])
        if not title and anilist_res:
            title = anilist_res.get('title', {}).get(self.title_lang) or anilist_res.get('title', {}).get('romaji') or title
        if title is None:
            title = ''

        # Add relation info (if available)
        if anilist_res and anilist_res.get('relationType'):
            title += ' [I]%s[/I]' % control.colorstr(anilist_res['relationType'], 'limegreen')

        # Plot/synopsis
        plot = eres['attributes'].get('synopsis')
        if not plot and anilist_res and anilist_res.get('description'):
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
        duration = control.safe_call(lambda: eres['attributes']['episodeLength'] * 60)
        if not duration and anilist_res and anilist_res.get('duration'):
            duration = anilist_res.get('duration') * 60 if isinstance(anilist_res.get('duration'), int) else anilist_res.get('duration')

        # Country
        country = None
        if anilist_res:
            country = [anilist_res.get('countryOfOrigin', '')]

        # Rating/score
        info_rating = None
        try:
            rating = float(eres['attributes']['averageRating'])
            if rating:
                info_rating = {'score': rating / 10}
        except (TypeError, ValueError):
            pass
        if not info_rating and anilist_res and anilist_res.get('averageScore'):
            info_rating = {'score': anilist_res.get('averageScore') / 10.0}
            if anilist_res.get('stats') and anilist_res['stats'].get('scoreDistribution'):
                total_votes = sum([score['amount'] for score in anilist_res['stats']['scoreDistribution']])
                info_rating['votes'] = total_votes

        # Trailer
        trailer = None
        if eres['attributes'].get('youtubeVideoId'):
            trailer = f"plugin://plugin.video.youtube/play/?video_id={eres['attributes']['youtubeVideoId']}"
        elif anilist_res and anilist_res.get('trailer'):
            try:
                if anilist_res['trailer']['site'] == 'youtube':
                    trailer = f"plugin://plugin.video.youtube/play/?video_id={anilist_res['trailer']['id']}"
                else:
                    trailer = f"plugin://plugin.video.dailymotion_com/?url={anilist_res['trailer']['id']}&mode=playVideo"
            except (KeyError, TypeError):
                pass

        # Playcount
        playcount = None
        if eres['attributes']['episodeCount'] != 0 and res["attributes"]["progress"] == eres['attributes']['episodeCount']:
            playcount = 1

        # Premiered/year
        premiered = None
        year = None
        start_date = None
        if anilist_res and anilist_res.get('startDate'):
            start_date = anilist_res.get('startDate')
        if start_date:
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
        info_unique_ids = {
            'kitsu_id': str(kitsu_id),
            'mal_id': str(mal_id),
            **database.get_unique_ids(kitsu_id, 'kitsu_id'),
            **database.get_unique_ids(mal_id, 'mal_id')
        }
        if anilist_res and anilist_res.get('id'):
            info_unique_ids['anilist_id'] = str(anilist_res['id'])
            info_unique_ids.update(database.get_unique_ids(anilist_res['id'], 'anilist_id'))

        # Art/Images
        show_meta = database.get_show_meta(mal_id)
        kodi_meta = pickle.loads(show_meta.get('art')) if show_meta else {}
        poster_image = eres["attributes"]['posterImage']
        image = poster_image.get('large', poster_image['original'])
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
            'UniqueIDs': info_unique_ids,
            'plot': plot,
            'title': title,
            'mpaa': eres['attributes']['ageRating'],
            'trailer': trailer,
            'mediatype': 'tvshow',
            'genre': genre,
            'studio': studio,
            'status': status,
            'duration': duration,
            'country': country,
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
        if anilist_res and anilist_res.get('countryOfOrigin'):
            info['mpaa'] = anilist_res.get('countryOfOrigin')

        base = {
            "name": '%s - %d/%d' % (title, res["attributes"]["progress"], eres["attributes"].get('episodeCount', 0) if eres["attributes"]['episodeCount'] else 0),
            "url": f'watchlist_to_ep/{mal_id}/{res["attributes"]["progress"]}',
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

        if eres['attributes']['subtype'] == 'movie' and eres['attributes']['episodeCount'] == 1:
            base['url'] = f'play_movie/{mal_id}/'
            base['info']['mediatype'] = 'movie'
            return utils.parse_view(base, False, True, dub)
        return utils.parse_view(base, True, False, dub)

    def mapping_mal(self, kitsu_id):
        mal_id = ''
        for i in self.mapping:
            if i['attributes']['externalSite'] == 'myanimelist/anime':
                if i['relationships']['item']['data']['id'] == kitsu_id:
                    mal_id = i['attributes']['externalId']
                    break
        if not mal_id:
            ids = SIMKLAPI().get_mapping_ids_from_simkl(kitsu_id, 'kitsu_id')
            mal_id = ids.get('mal', '')
            if mal_id:
                database.add_mapping_id(mal_id, 'mal_id', mal_id)
        return mal_id

    def get_library_entries(self, kitsu_id):
        params = {
            "filter[user_id]": self.user_id,
            "filter[anime_id]": kitsu_id
        }
        r = client.get(f'{self._URL}/edge/library-entries', headers=self.__headers(), params=params)
        r = r.json() if r else {}
        return r

    def get_watchlist_anime_entry(self, mal_id):
        kitsu_id = self._get_mapping_id(mal_id, 'kitsu_id')
        if not kitsu_id:
            return {}

        params = {
            "filter[user_id]": self.user_id,
            "filter[anime_id]": kitsu_id,
            "include": "anime"
        }
        result = client.get(f'{self._URL}/edge/library-entries', headers=self.__headers(), params=params)
        result = result.json() if result else {}
        item_dict = control.safe_call(lambda: result['data'][0]['attributes'])
        if not item_dict:
            return {}

        # Get total episodes from included anime data
        total_episodes = None
        for included in result.get('included', []):
            if included.get('type') == 'anime':
                total_episodes = included.get('attributes', {}).get('episodeCount')
                break

        anime_entry = {
            'eps_watched': item_dict['progress'],
            'status': item_dict['status'],
            'score': item_dict['ratingTwenty'],
            'total_episodes': total_episodes
        }
        return anime_entry

    def save_completed(self):
        data = self.get_user_anime_list('completed')
        completed = {}
        for dat in data:
            mal_id = self.mapping_mal(dat['relationships']['anime']['data']['id'])
            completed[str(mal_id)] = dat['attributes']['progress']
        return completed

    def get_user_anime_list(self, status):
        url = f'{self._URL}/edge/library-entries'
        params = {
            "filter[user_id]": self.user_id,
            "filter[kind]": "anime",
            "filter[status]": status,
            "page[limit]": "500",
            "include": "anime,anime.mappings,anime.mappings.item",
        }
        r = client.get(url, headers=self.__headers(), params=params)
        res = r.json() if r else {}
        paging = res.get('links', {})
        data = res.get('data', [])
        while paging.get('next'):
            r = client.get(paging['next'], headers=self.__headers())
            res = r.json() if r else {}
            paging = res.get('links', {})
            data += res.get('data', [])
        return data

    def update_list_status(self, mal_id, status):
        from resources.lib.ui.database import clear_watchlist_cache
        kitsu_id = self._get_mapping_id(mal_id, 'kitsu_id')
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
                                "id": self.user_id,
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
            r = client.post(f'{self._URL}/edge/library-entries', headers=self.__headers(), json_data=data)
            if r and r.ok:
                clear_watchlist_cache(self._NAME)  # Clear all statuses since item moved
            return r and r.ok
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
        r = client.patch(f'{self._URL}/edge/library-entries/{animeid}', headers=self.__headers(), json_data=data)
        if r and r.ok:
            clear_watchlist_cache(self._NAME)  # Clear all statuses since item moved
        return r and r.ok

    def update_num_episodes(self, mal_id, episode):
        from resources.lib.ui.database import clear_watchlist_cache
        kitsu_id = self._get_mapping_id(mal_id, 'kitsu_id')
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
                                "id": self.user_id,
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
            r = client.post(f'{self._URL}/edge/library-entries', headers=self.__headers(), json_data=data)
            if r and r.ok:
                clear_watchlist_cache(self._NAME)  # Clear cache to reflect progress
            return r and r.ok

        animeid = int(r['data'][0]['id'])

        data = {
            'data': {
                'id': animeid,
                'type': 'libraryEntries',
                'attributes': {
                    'status': 'current',
                    'progress': int(episode)
                }
            }
        }
        r = client.patch(f'{self._URL}/edge/library-entries/{animeid}', headers=self.__headers(), json_data=data)
        if r and r.ok:
            clear_watchlist_cache(self._NAME)  # Clear cache to reflect progress
        return r and r.ok

    def update_score(self, mal_id, score):
        from resources.lib.ui.database import clear_watchlist_cache
        kitsu_id = self._get_mapping_id(mal_id, 'kitsu_id')
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
                                "id": self.user_id,
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
            r = client.post(f'{self._URL}/edge/library-entries', headers=self.__headers(), json_data=data)
            if r and r.ok:
                clear_watchlist_cache(self._NAME)  # Clear cache to reflect score
            return r and r.ok

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
        r = client.patch(f'{self._URL}/edge/library-entries/{animeid}', headers=self.__headers(), json_data=data)
        if r and r.ok:
            clear_watchlist_cache(self._NAME)  # Clear cache to reflect score
        return r and r.ok

    def delete_anime(self, mal_id):
        from resources.lib.ui.database import clear_watchlist_cache
        kitsu_id = self._get_mapping_id(mal_id, 'kitsu_id')
        if not kitsu_id:
            return False

        r = self.get_library_entries(kitsu_id)
        data = r['data']
        if data:
            animeid = data[0]['id']
        else:
            return True

        r = client.delete(f'{self._URL}/edge/library-entries/{animeid}', headers=self.__headers())
        if r and r.ok:
            clear_watchlist_cache(self._NAME)  # Clear cache after deletion
        return r and r.ok
