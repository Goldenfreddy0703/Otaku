import time
import json
import random
import pickle
import ast
import re
import os
import datetime

from bs4 import BeautifulSoup
from functools import partial
from resources.lib.endpoints.simkl import Simkl
from resources.lib.ui import database, control, client, utils, get_meta
from resources.lib.ui.BrowserBase import BrowserBase
from resources.lib.ui.divide_flavors import div_flavor


class OtakuBrowser(BrowserBase):
    _BASE_URL = "https://api.jikan.moe/v4"

    def __init__(self):
        self.title_lang = ['title', 'title_english'][control.getInt("titlelanguage")]
        self.perpage = control.getInt('interface.perpage.general.mal')
        self.year_type = control.getInt('contentyear.menu') if control.getBool('contentyear.bool') else 0
        self.season_type = control.getInt('contentseason.menu') if control.getBool('contentseason.bool') else ''
        self.format_in_type = ['tv', 'movie', 'tv_special', 'special', 'ova', 'ona', 'music'][control.getInt('contentformat.menu')] if control.getBool('contentformat.bool') else ''
        self.status = ['airing', 'complete', 'upcoming'][control.getInt('contentstatus.menu.mal')] if control.getBool('contentstatus.bool') else ''
        self.rating = ['g', 'pg', 'pg13', 'r17', 'r', 'rx'][control.getInt('contentrating.menu.mal')] if control.getBool('contentrating.bool') else ''
        self.adult = 'false' if control.getBool('search.adult') else 'true'
        self.genre = self.load_genres_from_json() if control.getBool('contentgenre.bool') else ''

    def load_genres_from_json(self):
        if os.path.exists(control.genre_json):
            with open(control.genre_json, 'r') as f:
                settings = json.load(f)
                genres = settings.get('selected_genres_mal', [])
                return (', '.join(genres))
        return ()

    def process_otaku_view(self, mal_res, base_plugin_url, page):
        # Support direct, nested, and list 'entry' (e.g., relations response)
        mal_items_flat = []
        mal_ids = []
        for item in mal_res.get('data', []):
            if 'mal_id' in item:
                mal_ids.append(item['mal_id'])
                mal_items_flat.append(item)
            elif 'entry' in item:
                # If entry is a list, flatten it
                if isinstance(item['entry'], list):
                    for entry in item['entry']:
                        if 'mal_id' in entry:
                            mal_ids.append(entry['mal_id'])
                            # Merge relation info into entry for context
                            entry_with_relation = dict(entry)
                            if 'relation' in item:
                                entry_with_relation['relation'] = item['relation']
                            mal_items_flat.append(entry_with_relation)
                elif isinstance(item['entry'], dict) and 'mal_id' in item['entry']:
                    mal_ids.append(item['entry']['mal_id'])
                    entry_with_relation = dict(item['entry'])
                    if 'relation' in item:
                        entry_with_relation['relation'] = item['relation']
                    mal_items_flat.append(entry_with_relation)

        anilist_res = self.get_anilist_base_res(mal_ids)
        get_meta.collect_meta(mal_items_flat)
        get_meta.collect_meta(anilist_res)  # anilist_res is now a list
        # Build AniList lookup by MAL ID
        anilist_by_mal_id = {item['idMal']: item for item in anilist_res if 'idMal' in item}

        def mapfunc(mal_item):
            # Extract mal_id from direct item
            mal_id = mal_item.get('mal_id')
            anilist_item = anilist_by_mal_id.get(mal_id)
            return self.base_otaku_view(mal_item, anilist_item, completed=self.open_completed())

        all_results = [mapfunc(mal_item) for mal_item in mal_items_flat]
        # Only handle paging if 'pagination' exists
        hasNextPage = False
        if 'pagination' in mal_res:
            hasNextPage = mal_res['pagination'].get('has_next_page', False)
            all_results += self.handle_paging(hasNextPage, base_plugin_url, page)
        return all_results

    def process_airing_view(self, json_res):
        ts = int(time.time())
        mapfunc = partial(self.base_airing_view, ts=ts)
        all_results = list(map(mapfunc, json_res['data']))
        return all_results

    def process_res(self, mal_res):
        self.database_update_show(mal_res)
        get_meta.collect_meta([mal_res])
        return database.get_show(mal_res['mal_id'])

    def get_anime_data(self, mal_id):
        """
        Fetch full anime data from Jikan API by MAL ID.
        Returns the parsed JSON response or None on error.
        """
        mal_res = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime/{mal_id}")
        data = mal_res.get('data', None)
        mal_id = data['mal_id']
        # Optionally fetch AniList data if needed
        anilist_res = self.get_anilist_base_res([mal_id])
        get_meta.collect_meta([data])
        get_meta.collect_meta(anilist_res)
        return self.database_update_show(data, anilist_res)

    def get_season_year(self, period='current'):
        date = datetime.datetime.today()
        year = date.year
        month = date.month
        seasons = ['WINTER', 'SPRING', 'SUMMER', 'FALL']
        season_start_dates = {
            'WINTER': datetime.date(year, 1, 1),
            'SPRING': datetime.date(year, 4, 1),
            'SUMMER': datetime.date(year, 7, 1),
            'FALL': datetime.date(year, 10, 1)
        }
        season_end_dates = {
            'WINTER': datetime.date(year, 3, 31),
            'SPRING': datetime.date(year, 6, 30),
            'SUMMER': datetime.date(year, 9, 30),
            'FALL': datetime.date(year, 12, 31)
        }

        if self.year_type:
            if 1916 < self.year_type <= year + 1:
                year = self.year_type
            else:
                control.notify(control.ADDON_NAME, "Invalid year. Please select a year between 1916 and {0}.".format(year + 1))
                return None, None, None, None, None, None, None, None, None, None, None, None, None, None

        if self.season_type:
            if 0 <= self.season_type < 4:
                season = seasons[self.season_type]
                if period == "next":
                    next_season_index = (self.season_type + 1) % 4
                    season = seasons[next_season_index]
                    if season == 'WINTER':
                        year += 1
                elif period == "last":
                    last_season_index = (self.season_type - 1) % 4
                    season = seasons[last_season_index]
                    if season == 'FALL' and month <= 3:
                        year -= 1
        else:
            if period == "next":
                season = seasons[int((month - 1) / 3 + 1) % 4]
                if season == 'WINTER':
                    year += 1
            elif period == "last":
                season = seasons[int((month - 1) / 3 - 1) % 4]
                if season == 'FALL' and month <= 3:
                    year -= 1
            else:
                season = seasons[int((month - 1) / 3)]

        # Adjust the start and end dates for this season
        season_start_date = season_start_dates[season]
        season_end_date = season_end_dates[season]

        # Adjust the start and end dates for this year
        year_start_date = datetime.date(year, 1, 1)
        year_end_date = datetime.date(year, 12, 31)

        # Adjust the start and end dates for last season
        last_season_index = (seasons.index(season) - 1) % 4
        last_season = seasons[last_season_index]
        last_season_year = year if last_season != 'FALL' or month > 3 else year - 1
        season_start_date_last = season_start_dates[last_season].replace(year=last_season_year)
        season_end_date_last = season_end_dates[last_season].replace(year=last_season_year)

        # Adjust the start and end dates for last year
        year_start_date_last = datetime.date(year - 1, 1, 1)
        year_end_date_last = datetime.date(year - 1, 12, 31)

        # Adjust the start and end dates for next season
        next_season_index = (seasons.index(season) + 1) % 4
        next_season = seasons[next_season_index]
        next_season_year = year if next_season != 'WINTER' else year + 1
        season_start_date_next = season_start_dates[next_season].replace(year=next_season_year)
        season_end_date_next = season_end_dates[next_season].replace(year=next_season_year)

        # Adjust the start and end dates for next year
        year_start_date_next = datetime.date(year + 1, 1, 1)
        year_end_date_next = datetime.date(year + 1, 12, 31)

        return (season, year, year_start_date, year_end_date, season_start_date, season_end_date,
                season_start_date_last, season_end_date_last, year_start_date_last, year_end_date_last,
                season_start_date_next, season_end_date_next, year_start_date_next, year_end_date_next)

    def get_airing_calendar(self, page=1):
        """Get weekly calendar using AnimeSchedule API."""
        from resources.lib.endpoints import animeschedule
        
        # Fetch calendar episodes from AnimeSchedule (includes Donghua like MalBrowser)
        episodes = animeschedule.get_airing_calendar(
            exclude_donghua=False,
            tz=None,
            air="all"
        )
        if not episodes:
            return []
        
        # Process calendar view using AnimeSchedule data
        results = self.process_calendar_view(episodes)
        return results
    
    def process_calendar_view(self, episodes):
        """Process animeschedule episodes into calendar format."""
        import time
        from resources.lib.endpoints import animeschedule
        
        # Group episodes by route to fetch anime data in batch
        routes = list(set(ep.get('route') for ep in episodes if ep.get('route')))
        anime_data = animeschedule.as_get_anime_by_routes_batch(routes, timeout_per=6, max_workers=16)
        
        # Group episodes by route + episode number to deduplicate
        episode_groups = {}
        for ep in episodes:
            route = ep.get('route')
            ep_num = ep.get('episodeNumber')
            if not route or not ep_num:
                continue
            
            key = (route, ep_num)
            if key not in episode_groups:
                episode_groups[key] = []
            episode_groups[key].append(ep)
        
        results = []
        ts = int(time.time())
        
        # Process each unique anime+episode combination
        for (route, ep_num), ep_list in episode_groups.items():
            anime = anime_data.get(route)
            if not anime:
                continue
            
            mal_id, anilist_id = animeschedule._extract_ids_anywhere(anime)
            if not mal_id:
                continue
            
            # Sort by air date to get the earliest one
            ep_list.sort(key=lambda x: animeschedule._parse_iso(x.get('episodeDate', '')) or '')
            earliest_ep = ep_list[0]
            
            # Collect all air types for this episode
            air_types = []
            for ep in ep_list:
                air_type = (ep.get('airType') or '').capitalize()
                if air_type and air_type not in air_types:
                    air_types.append(air_type)
            
            # Build calendar entry with air types and animeschedule data
            item = self.base_calendar_view(earliest_ep, anime, mal_id, ts, air_types)
            if item:
                results.append(item)
        
        # Sort by day of week (Monday to Sunday)
        weekday_order = {'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6}
        results.sort(key=lambda x: weekday_order.get(x.get('airing_day', 'Monday'), 0))
        
        return results

    def get_cached_data(self):
        if os.path.exists(control.mal_calendar_json):
            with open(control.mal_calendar_json, 'r') as f:
                return json.load(f)
        return None

    def set_cached_data(self, data):
        with open(control.mal_calendar_json, 'w') as f:
            json.dump(data, f)

    def get_anime(self, mal_id):
        mal_res = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime/{mal_id}")
        return self.process_res(mal_res['data'])

    def get_recommendations(self, mal_id, page, prefix=None):
        recommendations = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime/{mal_id}/recommendations")
        base_plugin_url = f"{prefix}?page=%d" if prefix else "recommendations?page=%d"
        return self.process_otaku_view(recommendations, base_plugin_url, page)

    def get_relations(self, mal_id, page=1, prefix=None):
        relations = database.get(self.get_mal_base_res, 24, f'{self._BASE_URL}/anime/{mal_id}/relations')
        # Keep only anime entries in each relation
        for item in relations.get('data', []):
            if 'entry' in item and isinstance(item['entry'], list):
                item['entry'] = [entry for entry in item['entry'] if entry.get('type', '').lower() == 'anime']
        base_plugin_url = f"{prefix}?page=%d" if prefix else "relations?page=%d"
        return self.process_otaku_view(relations, base_plugin_url, page)

    def get_watch_order(self, mal_id):
        url = 'https://chiaki.site/?/tools/watch_order/id/{}'.format(mal_id)
        response = client.get(url)
        if response:
            soup = BeautifulSoup(response.text, 'html.parser')
        else:
            soup = None

        # Find the element with the desired information
        anime_info = soup.find('tr', {'data-id': str(mal_id)})

        watch_order_list = []
        if anime_info is not None:
            # Find all 'a' tags in the entire page with href attributes that match the desired URL pattern
            mal_links = soup.find_all('a', href=re.compile(r'https://myanimelist\.net/anime/\d+'))

            # Extract the MAL IDs from these tags
            mal_ids = [re.search(r'\d+', link['href']).group() for link in mal_links]
            meta_ids = [{'mal_id': mal_id} for mal_id in mal_ids]
            get_meta.collect_meta(meta_ids)

            watch_order_list = []
            count = 0
            retry_limit = 3

            for idmal in mal_ids:
                retries = 0
                while retries < retry_limit:
                    mal_item = database.get(self.get_mal_base_res, 24, f'{self._BASE_URL}/anime/{idmal}')

                    if mal_item is not None and 'data' in mal_item:
                        watch_order_list.append(mal_item['data'])
                        break
                    else:
                        retries += 1
                        control.sleep(int(100 * retries))  # Reduced linear backoff

                count += 1
                if count % 3 == 0:
                    control.sleep(1000)  # Ensure we do not exceed 3 requests per second

        mapfunc = partial(self.base_otaku_view, completed=self.open_completed())
        all_results = list(map(mapfunc, watch_order_list))
        return all_results

    def get_search(self, query, page, format, prefix=None):
        params = {
            "q": query,
            "page": page,
            "limit": self.perpage,
            'sfw': self.adult
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        search = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}/{query}?page=%d" if prefix else f"search_anime/{query}?page=%d"
        return self.process_otaku_view(search, base_plugin_url, page)

    def get_airing_last_season(self, page, format, prefix=None):
        season, year, _, _, _, _, _, _, _, _, _, _, _, _ = self.get_season_year('last')
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
        }

        if format:
            params['filter'] = format

        if self.format_in_type:
            params['filter'] = self.format_in_type

        airing = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/seasons/{year}/{season}", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "airing_last_season?page=%d"
        return self.process_otaku_view(airing, base_plugin_url, page)

    def get_airing_this_season(self, page, format, prefix=None):
        season, year, _, _, _, _, _, _, _, _, _, _, _, _ = self.get_season_year('this')
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult
        }

        if format:
            params['filter'] = format

        if self.format_in_type:
            params['filter'] = self.format_in_type

        airing = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/seasons/{year}/{season}", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "airing_this_season?page=%d"
        return self.process_otaku_view(airing, base_plugin_url, page)

    def get_airing_next_season(self, page, format, prefix=None):
        season, year, _, _, _, _, _, _, _, _, _, _, _, _ = self.get_season_year('next')
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult
        }

        if format:
            params['filter'] = format

        if self.format_in_type:
            params['filter'] = self.format_in_type

        airing = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/seasons/{year}/{season}", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "airing_next_season?page=%d"
        return self.process_otaku_view(airing, base_plugin_url, page)

    def get_trending_last_year(self, page, format, prefix=None):
        _, _, _, _, _, _, _, _, year_start_date_last, year_end_date_last, _, _, _, _ = self.get_season_year('')
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'start_date': year_start_date_last,
            'end_date': year_end_date_last,
            'order_by': 'members',
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        if self.genre:
            params['genres'] = self.genre

        trending = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "trending_last_year?page=%d"
        return self.process_otaku_view(trending, base_plugin_url, page)

    def get_trending_this_year(self, page, format, prefix=None):
        _, _, year_start_date, _, _, _, _, _, _, _, _, _, _, _ = self.get_season_year('')
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'start_date': year_start_date,
            'order_by': 'members',
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        if self.genre:
            params['genres'] = self.genre

        trending = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "trending_this_year?page=%d"
        return self.process_otaku_view(trending, base_plugin_url, page)

    def get_trending_last_season(self, page, format, prefix=None):
        _, _, _, _, _, _, season_start_date_last, season_end_date_last, _, _, _, _, _, _ = self.get_season_year('')
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'start_date': season_start_date_last,
            'end_date': season_end_date_last,
            'order_by': 'members',
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        if self.genre:
            params['genres'] = self.genre

        trending = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "trending_last_season?page=%d"
        return self.process_otaku_view(trending, base_plugin_url, page)

    def get_trending_this_season(self, page, format, prefix=None):
        _, _, _, _, season_start_date, _, _, _, _, _, _, _, _, _ = self.get_season_year('')
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'start_date': season_start_date,
            'order_by': 'members',
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        if self.genre:
            params['genres'] = self.genre

        trending = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "trending_this_season?page=%d"
        return self.process_otaku_view(trending, base_plugin_url, page)

    def get_all_time_trending(self, page, format, prefix=None):
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'order_by': 'members',
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        if self.genre:
            params['genres'] = self.genre

        trending = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "all_time_trending?page=%d"
        return self.process_otaku_view(trending, base_plugin_url, page)

    def get_popular_last_year(self, page, format, prefix=None):
        _, _, _, _, _, _, _, _, year_start_date_last, year_end_date_last, _, _, _, _ = self.get_season_year('')
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'start_date': year_start_date_last,
            'end_date': year_end_date_last,
            'order_by': 'popularity',
            'sort': 'asc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        if self.genre:
            params['genres'] = self.genre

        popular = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "popular_last_year?page=%d"
        return self.process_otaku_view(popular, base_plugin_url, page)

    def get_popular_this_year(self, page, format, prefix=None):
        _, _, year_start_date, _, _, _, _, _, _, _, _, _, _, _ = self.get_season_year('')
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'start_date': year_start_date,
            'order_by': 'popularity',
            'sort': 'asc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        if self.genre:
            params['genres'] = self.genre

        popular = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "popular_this_year?page=%d"
        return self.process_otaku_view(popular, base_plugin_url, page)

    def get_popular_last_season(self, page, format, prefix=None):
        _, _, _, _, _, _, season_start_date_last, season_end_date_last, _, _, _, _, _, _ = self.get_season_year('')
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'start_date': season_start_date_last,
            'end_date': season_end_date_last,
            'order_by': 'popularity',
            'sort': 'asc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        if self.genre:
            params['genres'] = self.genre

        popular = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "popular_last_season?page=%d"
        return self.process_otaku_view(popular, base_plugin_url, page)

    def get_popular_this_season(self, page, format, prefix=None):
        _, _, _, _, season_start_date, _, _, _, _, _, _, _, _, _ = self.get_season_year('')
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'start_date': season_start_date,
            'order_by': 'popularity',
            'sort': 'asc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        if self.genre:
            params['genres'] = self.genre

        popular = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "popular_this_season?page=%d"
        return self.process_otaku_view(popular, base_plugin_url, page)

    def get_all_time_popular(self, page, format, prefix=None):
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'order_by': 'popularity',
            'sort': 'asc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        if self.genre:
            params['genres'] = self.genre

        popular = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "all_time_popular?page=%d"
        return self.process_otaku_view(popular, base_plugin_url, page)

    def get_voted_last_year(self, page, format, prefix=None):
        _, _, _, _, _, _, _, _, year_start_date_last, year_end_date_last, _, _, _, _ = self.get_season_year('')
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'start_date': year_start_date_last,
            'end_date': year_end_date_last,
            'order_by': 'score',
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        if self.genre:
            params['genres'] = self.genre

        voted = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "voted_last_year?page=%d"
        return self.process_otaku_view(voted, base_plugin_url, page)

    def get_voted_this_year(self, page, format, prefix=None):
        _, _, year_start_date, _, _, _, _, _, _, _, _, _, _, _ = self.get_season_year('')
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'start_date': year_start_date,
            'order_by': 'score',
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        if self.genre:
            params['genres'] = self.genre

        voted = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "voted_this_year?page=%d"
        return self.process_otaku_view(voted, base_plugin_url, page)

    def get_voted_last_season(self, page, format, prefix=None):
        _, _, _, _, _, _, season_start_date_last, season_end_date_last, _, _, _, _, _, _ = self.get_season_year('')
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'start_date': season_start_date_last,
            'end_date': season_end_date_last,
            'order_by': 'score',
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        if self.genre:
            params['genres'] = self.genre

        voted = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "voted_last_season?page=%d"
        return self.process_otaku_view(voted, base_plugin_url, page)

    def get_voted_this_season(self, page, format, prefix=None):
        _, _, _, _, season_start_date, _, _, _, _, _, _, _, _, _ = self.get_season_year('')
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'start_date': season_start_date,
            'order_by': 'score',
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        if self.genre:
            params['genres'] = self.genre

        voted = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "voted_this_season?page=%d"
        return self.process_otaku_view(voted, base_plugin_url, page)

    def get_all_time_voted(self, page, format, prefix=None):
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'order_by': 'score',
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        if self.genre:
            params['genres'] = self.genre

        voted = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "all_time_voted?page=%d"
        return self.process_otaku_view(voted, base_plugin_url, page)

    def get_favourites_last_year(self, page, format, prefix=None):
        _, _, _, _, _, _, _, _, year_start_date_last, year_end_date_last, _, _, _, _ = self.get_season_year('')
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'start_date': year_start_date_last,
            'end_date': year_end_date_last,
            'order_by': 'favorites',
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        if self.genre:
            params['genres'] = self.genre

        favourites = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "favourites_last_year?page=%d"
        return self.process_otaku_view(favourites, base_plugin_url, page)

    def get_favourites_this_year(self, page, format, prefix=None):
        _, _, year_start_date, _, _, _, _, _, _, _, _, _, _, _ = self.get_season_year('')
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'start_date': year_start_date,
            'order_by': 'favorites',
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        if self.genre:
            params['genres'] = self.genre

        favourites = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "favourites_this_year?page=%d"
        return self.process_otaku_view(favourites, base_plugin_url, page)

    def get_favourites_last_season(self, page, format, prefix=None):
        _, _, _, _, _, _, season_start_date_last, season_end_date_last, _, _, _, _, _, _ = self.get_season_year('')
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'start_date': season_start_date_last,
            'end_date': season_end_date_last,
            'order_by': 'favorites',
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        if self.genre:
            params['genres'] = self.genre

        favourites = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "favourites_last_season?page=%d"
        return self.process_otaku_view(favourites, base_plugin_url, page)

    def get_favourites_this_season(self, page, format, prefix=None):
        _, _, _, _, season_start_date, _, _, _, _, _, _, _, _, _ = self.get_season_year('')
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'start_date': season_start_date,
            'order_by': 'favorites',
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        if self.genre:
            params['genres'] = self.genre

        favourites = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "favourites_this_season?page=%d"
        return self.process_otaku_view(favourites, base_plugin_url, page)

    def get_all_time_favourites(self, page, format, prefix=None):
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'order_by': 'favorites',
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        if self.genre:
            params['genres'] = self.genre

        favourites = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "all_time_favourites?page=%d"
        return self.process_otaku_view(favourites, base_plugin_url, page)

    def get_top_100(self, page, format, prefix=None):
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        if self.genre:
            params['genres'] = self.genre

        top_100 = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/top/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "top_100?page=%d"
        return self.process_otaku_view(top_100, base_plugin_url, page)

    def get_genre_action(self, page, format, prefix=None):
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'order_by': 'members',
            "genres": "1",
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        genre = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_action?page=%d"
        return self.process_otaku_view(genre, base_plugin_url, page)

    def get_genre_adventure(self, page, format, prefix=None):
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'order_by': 'members',
            "genres": "2",
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        genre = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_adventure?page=%d"
        return self.process_otaku_view(genre, base_plugin_url, page)

    def get_genre_comedy(self, page, format, prefix=None):
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'order_by': 'members',
            "genres": "4",
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        genre = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_comedy?page=%d"
        return self.process_otaku_view(genre, base_plugin_url, page)

    def get_genre_drama(self, page, format, prefix=None):
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'order_by': 'members',
            "genres": "8",
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        genre = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_drama?page=%d"
        return self.process_otaku_view(genre, base_plugin_url, page)

    def get_genre_ecchi(self, page, format, prefix=None):
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'order_by': 'members',
            "genres": "9",
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        genre = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_ecchi?page=%d"
        return self.process_otaku_view(genre, base_plugin_url, page)

    def get_genre_fantasy(self, page, format, prefix=None):
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'order_by': 'members',
            "genres": "10",
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        genre = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_fantasy?page=%d"
        return self.process_otaku_view(genre, base_plugin_url, page)

    def get_genre_hentai(self, page, format, prefix=None):
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'order_by': 'members',
            "genres": "12",
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        genre = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_hentai?page=%d"
        return self.process_otaku_view(genre, base_plugin_url, page)

    def get_genre_horror(self, page, format, prefix=None):
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'order_by': 'members',
            "genres": "14",
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        genre = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_horror?page=%d"
        return self.process_otaku_view(genre, base_plugin_url, page)

    def get_genre_shoujo(self, page, format, prefix=None):
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'order_by': 'members',
            "genres": "25",
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        genre = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_shoujo?page=%d"
        return self.process_otaku_view(genre, base_plugin_url, page)

    def get_genre_mecha(self, page, format, prefix=None):
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'order_by': 'members',
            "genres": "18",
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        genre = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_mecha?page=%d"
        return self.process_otaku_view(genre, base_plugin_url, page)

    def get_genre_music(self, page, format, prefix=None):
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'order_by': 'members',
            "genres": "19",
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        genre = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_music?page=%d"
        return self.process_otaku_view(genre, base_plugin_url, page)

    def get_genre_mystery(self, page, format, prefix=None):
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'order_by': 'members',
            "genres": "7",
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        genre = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_mystery?page=%d"
        return self.process_otaku_view(genre, base_plugin_url, page)

    def get_genre_psychological(self, page, format, prefix=None):
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'order_by': 'members',
            "genres": "40",
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        genre = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_psychological?page=%d"
        return self.process_otaku_view(genre, base_plugin_url, page)

    def get_genre_romance(self, page, format, prefix=None):
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'order_by': 'members',
            "genres": "22",
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        genre = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_romance?page=%d"
        return self.process_otaku_view(genre, base_plugin_url, page)

    def get_genre_sci_fi(self, page, format, prefix=None):
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'order_by': 'members',
            "genres": "24",
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        genre = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_sci_fi?page=%d"
        return self.process_otaku_view(genre, base_plugin_url, page)

    def get_genre_slice_of_life(self, page, format, prefix=None):
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'order_by': 'members',
            "genres": "36",
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        genre = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_slice_of_life?page=%d"
        return self.process_otaku_view(genre, base_plugin_url, page)

    def get_genre_sports(self, page, format, prefix=None):
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'order_by': 'members',
            "genres": "30",
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        genre = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_sports?page=%d"
        return self.process_otaku_view(genre, base_plugin_url, page)

    def get_genre_supernatural(self, page, format, prefix=None):
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'order_by': 'members',
            "genres": "37",
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        genre = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_supernatural?page=%d"
        return self.process_otaku_view(genre, base_plugin_url, page)

    def get_genre_thriller(self, page, format, prefix=None):
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'order_by': 'members',
            "genres": "41",
            'sort': 'desc'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        genre = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_thriller?page=%d"
        return self.process_otaku_view(genre, base_plugin_url, page)

    @staticmethod
    def get_mal_base_res(url, params=None):
        r = client.get(url, params=params)
        if r:
            return r.json()

    @staticmethod
    def get_anilist_base_res(mal_ids, page=1, media_type="ANIME"):
        _ANILIST_BASE_URL = "https://graphql.anilist.co"

        query = '''
        query ($page: Int, $malIds: [Int], $type: MediaType) {
          Page(page: $page) {
            pageInfo {
              hasNextPage
              total
            }
            media(idMal_in: $malIds, type: $type) {
              id
              idMal
              title {
                romaji
                english
              }
              coverImage {
                extraLarge
              }
              bannerImage
              startDate {
                year
                month
                day
              }
              description
              synonyms
              format
              episodes
              status
              genres
              duration
              countryOfOrigin
              averageScore
              characters(
                page: 1
                sort: ROLE
                perPage: 10
              ) {
                edges {
                  node {
                    name {
                      userPreferred
                    }
                  }
                  voiceActors(language: JAPANESE) {
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
              stats {
                scoreDistribution {
                  score
                  amount
                }
              }
            }
          }
        }
        '''

        # Fetch first page to check if pagination needed
        variables = {"page": 1, "malIds": mal_ids, "type": media_type}
        result = client.post(_ANILIST_BASE_URL, json_data={'query': query, 'variables': variables})
        results = result.json()
        page_data = results.get('data', {}).get('Page', {})
        all_media = page_data.get('media', [])
        has_next = page_data.get('pageInfo', {}).get('hasNextPage', False)

        # If only one page, return immediately
        if not has_next:
            return all_media

        # If multiple pages, fetch remaining pages in parallel
        # AniList has no strict rate limit, so we can be more aggressive
        def fetch_page(page_num):
            try:
                vars = {"page": page_num, "malIds": mal_ids, "type": media_type}
                resp = client.post(_ANILIST_BASE_URL, json_data={'query': query, 'variables': vars})
                if resp:
                    resp_json = resp.json()
                    return resp_json.get('data', {}).get('Page', {}).get('media', [])
                return []
            except Exception as e:
                control.log(f"AniList: Failed to fetch page {page_num}: {str(e)}")
                return []

        # Estimate max pages (AniList returns ~50 per page for mal_ids query)
        # Conservative estimate: fetch up to 5 pages in parallel (250 anime)
        max_pages = min(5, len(mal_ids) // 50 + 2)  # +2 for safety margin

        page_numbers = list(range(2, max_pages + 1))
        all_page_results = utils.parallel_process(page_numbers, fetch_page, max_workers=5)

        # Combine all results
        for page_media in all_page_results:
            if page_media:  # Only extend if we got data
                all_media.extend(page_media)
            else:
                break  # Stop if we hit an empty page

        control.log(f"AniList: Fetched {len(all_media)} media items total")
        return all_media

    def get_airing_calendar_res(self, day, page=1):
        url = f'{self._BASE_URL}/schedules?kids=false&sfw=false&limit=25&page={page}&filter={day}'
        results = self.get_mal_base_res(url)
        return results

    # @div_flavor
    # def recommendation_relation_view(self, mal_res, completed=None, mal_dub=None):
    #     if mal_res.get('entry'):
    #         mal_res = mal_res['entry']
    #     if not completed:
    #         completed = {}

    #     mal_id = mal_res['mal_id']
    #     meta_ids = database.get_mappings(mal_id, 'mal_id')

    #     title = mal_res['title']
    #     if mal_res.get('relation'):
    #         title += ' [I]%s[/I]' % control.colorstr(mal_res['relation'], 'limegreen')

    #     info = {
    #         'UniqueIDs': {
    #             'mal_id': str(mal_id),
    #             **database.get_unique_ids(mal_id, 'mal_id')
    #         },
    #         'title': title,
    #         'mediatype': 'tvshow'
    #     }

    #     if completed.get(str(mal_id)):
    #         info['playcount'] = 1

    #     dub = True if mal_dub and mal_dub.get(str(mal_res.get('idMal'))) else False

    #     image = mal_res['images']['webp']['large_image_url'] if mal_res.get('images') else None

    #     base = {
    #         "name": title,
    #         "url": f'animes/{mal_id}/',
    #         "image": image,
    #         "poster": image,
    #         'fanart': image,
    #         "banner": image,
    #         "info": info
    #     }

    #     anime_media_episodes = meta_ids.get('anime_media_episodes', '0')
    #     total_episodes = int(anime_media_episodes.split('-')[-1].strip())

    #     if meta_ids.get('anime_media_type') in ['MOVIE', 'ONA', 'OVA', 'SPECIAL'] and total_episodes == 1:
    #         base['url'] = f'play_movie/{mal_id}/'
    #         base['info']['mediatype'] = 'movie'
    #         return utils.parse_view(base, False, True, dub)
    #     return utils.parse_view(base, True, False, dub)

    def get_genres(self, page, format):
        mal_res = database.get(self.get_mal_base_res, 24, f'{self._BASE_URL}/genres/anime')

        genre = mal_res['data']
        genres_list = []
        for x in genre:
            genres_list.append(x['name'])
        multiselect = control.multiselect_dialog(control.lang(30940), genres_list, preselect=[])
        if not multiselect:
            return []
        genre_display_list = []
        for selection in multiselect:
            if selection < len(genres_list):
                genre_display_list.append(str(genre[selection]['mal_id']))
        return self.genres_payload(genre_display_list, [], page, format)

    def genres_payload(self, genre_list, tag_list, page, format, prefix=None):
        if not isinstance(genre_list, list):
            genre_list = ast.literal_eval(genre_list)

        genre = ','.join(genre_list)
        params = {
            'page': page,
            'limit': self.perpage,
            'genres': genre,
            'sfw': self.adult,
            'order_by': 'popularity'
        }

        if format:
            params['type'] = format

        if self.format_in_type:
            params['type'] = self.format_in_type

        if self.status:
            params['status'] = self.status

        if self.rating:
            params['rating'] = self.rating

        genres = database.get(self.get_mal_base_res, 24, f'{self._BASE_URL}/anime', params)

        try:
            from resources.lib import Main
            prefix = Main.plugin_url.split('/', 1)[0]
            base_plugin_url = f"{prefix}/{genre_list}/{tag_list}?page=%d"
        except Exception:
            base_plugin_url = f"genres/{genre_list}/{tag_list}?page=%d"

        return self.process_otaku_view(genres, base_plugin_url, page)

    @div_flavor
    def base_otaku_view(self, mal_res, anilist_res=None, completed=None, mal_dub=None):
        """
        Combines MAL and AniList data for a single anime entry.
        Uses MAL as primary, fills missing fields from AniList if available.
        """
        if not completed:
            completed = {}

        # Use mal_id from MAL, fallback to AniList if needed
        mal_id = mal_res.get('mal_id') if mal_res else (anilist_res.get('idMal') if anilist_res else None)
        anilist_id = anilist_res.get('id') if anilist_res else None

        # Update database if not present
        self.database_update_show(mal_res, anilist_res)

        show_meta = database.get_show_meta(mal_id)
        kodi_meta = pickle.loads(show_meta.get('art')) if show_meta else {}

        # Title logic: for relations, use 'name' if present, else prefer MAL, fallback to AniList
        title = None
        if mal_res:
            # Use 'name' for relation entries
            title = mal_res.get('name') or mal_res.get(self.title_lang) or mal_res.get('title')
        if not title and anilist_res:
            title = anilist_res['title'].get(self.title_lang) or anilist_res['title'].get('romaji')
        # Ensure title is always a string
        if title is None:
            title = ''

        # Add relation info
        if mal_res and mal_res.get('relation'):
            title += ' [I]%s[/I]' % control.colorstr(mal_res['relation'], 'limegreen')
        elif anilist_res and anilist_res.get('relationType'):
            title += ' [I]%s[/I]' % control.colorstr(anilist_res['relationType'], 'limegreen')

        # Plot/synopsis
        plot = mal_res.get('synopsis') if mal_res and mal_res.get('synopsis') else None
        if not plot and anilist_res and anilist_res.get('description'):
            desc = anilist_res['description']
            desc = desc.replace('<i>', '[I]').replace('</i>', '[/I]')
            desc = desc.replace('<b>', '[B]').replace('</b>', '[/B]')
            desc = desc.replace('<br>', '[CR]')
            desc = desc.replace('\n', '')
            plot = desc

        # Genres
        genre = [x['name'] for x in mal_res.get('genres', [])] if mal_res else None
        if (not genre or not genre) and anilist_res:
            genre = anilist_res.get('genres')

        # Studios
        studio = [x['name'] for x in mal_res.get('studios', [])] if mal_res else None
        if (not studio or not studio) and anilist_res:
            studio = [x['node'].get('name') for x in anilist_res['studios']['edges']]

        # Status
        status = mal_res.get('status') if mal_res else None
        if not status and anilist_res:
            status = anilist_res.get('status')

        # Duration
        duration = self.duration_to_seconds(mal_res.get('duration')) if mal_res and mal_res.get('duration') else None
        if not duration and anilist_res and anilist_res.get('duration'):
            duration = anilist_res['duration'] * 60

        # Country
        country = None
        if anilist_res:
            country = [anilist_res.get('countryOfOrigin', '')]

        # Rating/score
        rating = mal_res.get('rating') if mal_res else None
        info_rating = None
        if mal_res and isinstance(mal_res.get('score'), float):
            info_rating = {'score': mal_res['score']}
            if isinstance(mal_res.get('scored_by'), int):
                info_rating['votes'] = mal_res['scored_by']
        elif anilist_res and anilist_res.get('averageScore'):
            info_rating = {'score': anilist_res.get('averageScore') / 10.0}
            if anilist_res.get('stats') and anilist_res['stats'].get('scoreDistribution'):
                total_votes = sum([score['amount'] for score in anilist_res['stats']['scoreDistribution']])
                info_rating['votes'] = total_votes

        # Trailer
        trailer = None
        if mal_res and mal_res.get('trailer'):
            trailer = f"plugin://plugin.video.youtube/play/?video_id={mal_res['trailer']['youtube_id']}"
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
        if completed and completed.get(str(mal_id)):
            playcount = 1

        # Premiered/year
        premiered = None
        year = None
        if mal_res and mal_res.get('aired') and mal_res['aired'].get('from'):
            start_date = mal_res['aired']['from']
            premiered = start_date[:10]
            year = mal_res.get('year', int(start_date[:4]))
        elif anilist_res and anilist_res.get('startDate'):
            start_date = anilist_res.get('startDate')
            year = start_date.get('year')
            month = start_date.get('month')
            day = start_date.get('day')
            if None not in (year, month, day):
                premiered = '{}-{:02}-{:02}'.format(year, month, day)
            else:
                premiered = ''
            year = start_date['year']

        # Cast
        cast = None
        if anilist_res and anilist_res.get('characters'):
            try:
                cast = []
                for i, x in enumerate(anilist_res['characters']['edges']):
                    role = x['node']['name']['userPreferred']
                    actor = x['voiceActors'][0]['name']['userPreferred']
                    actor_hs = x['voiceActors'][0]['image']['large']
                    cast.append({'name': actor, 'role': role, 'thumbnail': actor_hs, 'index': i})
            except (IndexError, KeyError, TypeError):
                pass

        # UniqueIDs
        unique_ids = {'mal_id': str(mal_id)}
        if anilist_id:
            unique_ids['anilist_id'] = str(anilist_id)
            unique_ids.update(database.get_unique_ids(anilist_id, 'anilist_id'))
        unique_ids.update(database.get_unique_ids(mal_id, 'mal_id'))

        info = {
            'UniqueIDs': unique_ids,
            'title': title,
            'plot': plot,
            'mpaa': rating,
            'duration': duration,
            'genre': genre,
            'studio': studio,
            'status': status,
            'mediatype': 'tvshow',
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
        if trailer:
            info['trailer'] = trailer

        # Dub
        dub = True if mal_dub and mal_dub.get(str(mal_id)) else False

        # Images
        image = None
        poster = None
        banner = None
        fanart = None

        # MAL images
        if mal_res and mal_res.get('images'):
            image = mal_res['images']['webp'].get('large_image_url')
            poster = image
            # MAL does not provide banner, fallback to AniList
            banner = mal_res['images']['webp'].get('banner_image_url') if 'banner_image_url' in mal_res['images']['webp'] else None
            fanart = kodi_meta['fanart'] if kodi_meta.get('fanart') else image
        # AniList fallback for missing images
        if not image and anilist_res and anilist_res.get('coverImage'):
            image = anilist_res['coverImage'].get('extraLarge')
        if not poster and anilist_res and anilist_res.get('coverImage'):
            poster = anilist_res['coverImage'].get('extraLarge')
        if not banner and anilist_res and anilist_res.get('bannerImage'):
            banner = anilist_res.get('bannerImage')
        if not fanart and anilist_res and anilist_res.get('coverImage'):
            fanart = anilist_res['coverImage'].get('extraLarge')

        base = {
            "name": title,
            "url": f'animes/{mal_id}/',
            "image": image,
            "poster": poster,
            'fanart': fanart,
            "banner": banner,
            "info": info
        }

        if kodi_meta.get('thumb'):
            base['landscape'] = random.choice(kodi_meta['thumb'])
        if kodi_meta.get('clearart'):
            base['clearart'] = random.choice(kodi_meta['clearart'])
        if kodi_meta.get('clearlogo'):
            base['clearlogo'] = random.choice(kodi_meta['clearlogo'])

        # Movie/episode logic
        episodes = mal_res.get('episodes') or (anilist_res.get('episodes') if anilist_res else None)

        if episodes == 1:
            base['url'] = f'play_movie/{mal_id}/'
            base['info']['mediatype'] = 'movie'
            return utils.parse_view(base, False, True, dub)
        return utils.parse_view(base, True, False, dub)

    def base_airing_view(self, mal_res, ts):
        airingAt = datetime.datetime.fromisoformat(mal_res['aired']['from'].replace('Z', '+00:00'))
        airingAt_day = airingAt.strftime('%A')
        airingAt_time = airingAt.strftime('%I:%M %p')
        airing_status = 'airing' if airingAt.timestamp() > ts else 'aired'
        simkl_rank = None
        genres = [genre['name'] for genre in mal_res['genres']]
        if genres:
            genres = ' | '.join(genres[:3])
        else:
            genres = 'Genres Not Found'
        title = mal_res['title']
        episode = mal_res.get('episode', 'N/A')
        rating = mal_res['score']

        # Find Simkl entry
        simkl_entry = Simkl().fetch_and_find_simkl_entry(mal_res['mal_id'])
        if simkl_entry:
            episode = simkl_entry['episode']['episode']
            rating = simkl_entry['ratings']['simkl']['rating']
            simkl_rank = simkl_entry['rank']
            airingAt = datetime.datetime.fromisoformat(simkl_entry['date'].replace('Z', '+00:00'))
            airingAt_day = airingAt.strftime('%A')
            airingAt_time = airingAt.strftime('%I:%M %p')
            airing_status = 'airing' if airingAt.timestamp() > ts else 'aired'

        if rating is not None:
            score = f"{rating * 10:.0f}"
        else:
            score = 'N/A'

        base = {
            'release_title': title,
            'poster': mal_res['images']['jpg']['image_url'],
            'ep_title': '{} {} {}'.format(episode, airing_status, airingAt_day),
            'ep_airingAt': airingAt_time,
            'rating': score,
            'simkl_rank': simkl_rank,
            'plot': mal_res['synopsis'].replace('<br><br>', '[CR]').replace('<br>', '').replace('<i>', '[I]').replace('</i>', '[/I]') if mal_res['synopsis'] else mal_res['synopsis'],
            'genres': genres,
            'id': mal_res['mal_id']
        }

        return base
    
    def base_calendar_view(self, ep, anime, mal_id, ts, air_types=None):
        """Build calendar entry from animeschedule episode data."""
        import datetime
        from resources.lib.endpoints import animeschedule
        
        ed = animeschedule._parse_iso(ep.get('episodeDate', ''))
        if not ed:
            return None
        
        if ed.tzinfo:
            airingAt = ed.astimezone()
        else:
            airingAt = ed.replace(tzinfo=datetime.timezone.utc).astimezone()
        
        airingAt_day = airingAt.strftime('%A')
        airingAt_time = airingAt.strftime('%I:%M %p')
        airing_status = 'airing' if airingAt.timestamp() > ts else 'aired'
        
        episode_num = ep.get('episodeNumber', '?')
        
        # Add air type info if available
        air_type_str = ''
        if air_types:
            air_type_str = f" ({', '.join(air_types)})"
        elif ep.get('airType'):
            air_type_str = f" ({ep.get('airType').capitalize()})"
        
        # Get title from anime data
        title_data = anime.get('title')
        if isinstance(title_data, dict):
            title = title_data.get('english') or title_data.get('romaji') or title_data.get('userPreferred') or 'Unknown'
        elif isinstance(title_data, str):
            title = title_data
        else:
            title = anime.get('name', 'Unknown')
        
        # Get poster from animeschedule
        poster = None
        image_route = anime.get('imageVersionRoute')
        if image_route:
            poster = animeschedule.build_image_url(image_route)
        
        if not poster:
            if isinstance(anime.get('image'), str):
                poster = anime.get('image')
            elif isinstance(anime.get('image'), dict):
                poster = anime.get('image', {}).get('large') or anime.get('image', {}).get('medium')
        
        # Get description and clean HTML entities
        description = anime.get('description', '')
        if description:
            import html
            import re
            description = html.unescape(description)
            description = description.replace('<br><br>', '[CR]').replace('<br>', '').replace('<i>', '[I]').replace('</i>', '[/I]').replace('<b>', '[B]').replace('</b>', '[/B]')
            description = re.sub(r'<[^>]+>', '', description)
        
        # Get genres from animeschedule format (list of dicts with 'name' field)
        genres_list = anime.get('genres', [])
        if isinstance(genres_list, list) and genres_list:
            genre_names = []
            for g in genres_list[:3]:
                if isinstance(g, dict):
                    genre_names.append(g.get('name', ''))
                elif isinstance(g, str):
                    genre_names.append(g)
            genres = ' | '.join(filter(None, genre_names)) if genre_names else 'Genres Not Found'
        else:
            genres = 'Genres Not Found'
        
        # Get score and rank from AnimeSchedule stats
        average_score = 0
        rank = 0
        
        stats = anime.get('stats', {})
        if isinstance(stats, dict):
            if stats.get('averageScore') is not None:
                average_score = round(float(stats['averageScore']))
            if stats.get('trackedRating') is not None:
                rank = stats['trackedRating']
        
        base = {
            'release_title': title,
            'poster': poster or '',
            'ep_title': '{} {} {}{}'.format(episode_num, airing_status, airingAt_day, air_type_str),
            'ep_airingAt': airingAt_time,
            'airing_day': airingAt_day,
            'averageScore': average_score,
            'score': average_score,
            'rank': rank,
            'plot': description,
            'genres': genres,
            'id': mal_id,
            '_sort_timestamp': airingAt.timestamp()
        }
        
        return base
    
    def base_recently_aired_view(self, ep, anime, mal_id):
        """Build recently aired item from animeschedule episode data only."""
        import html
        import re
        from resources.lib.endpoints import animeschedule
        
        # Get title from anime data
        title_data = anime.get('title')
        if isinstance(title_data, dict):
            base_title = title_data.get('english') or title_data.get('romaji') or title_data.get('userPreferred') or 'Unknown'
        elif isinstance(title_data, str):
            base_title = title_data
        else:
            base_title = anime.get('name', 'Unknown')
        
        # Build label with episode number
        ep_num = ep.get('episodeNumber', 1)
        label = f"{base_title} - Episode {ep_num}"
        
        # Get poster from animeschedule
        poster = ''
        image_route = anime.get('imageVersionRoute')
        if image_route:
            poster = animeschedule.build_image_url(image_route)
        
        if not poster:
            if isinstance(anime.get('image'), str):
                poster = anime.get('image')
            elif isinstance(anime.get('image'), dict):
                poster = anime.get('image', {}).get('large') or anime.get('image', {}).get('medium') or ''
        
        # Get description and clean HTML
        desc = anime.get('description', '')
        if desc:
            desc = html.unescape(desc)
            desc = desc.replace('<br><br>', '\n').replace('<br>', '\n')
            desc = re.sub(r'<[^>]+>', '', desc)
        
        # Format episode badge
        badge = animeschedule.as_format_episode_badge(ep)
        plot = f"{badge}\n{desc}" if desc else badge
        
        # Get score and rank from AnimeSchedule stats
        rating = None
        stats = anime.get('stats', {})
        if isinstance(stats, dict) and stats.get('averageScore'):
            score = round(float(stats['averageScore'])) / 10.0
            if score > 0:
                rating = {'score': score}
        
        # Get year
        year = anime.get('year')
        year = year if isinstance(year, int) else 0
        
        item = {
            'name': label,
            'url': f'animes/{mal_id}/',
            'image': {
                'poster': poster,
                'icon': poster,
                'thumb': poster,
                'fanart': poster,
                'landscape': None,
                'banner': poster,
                'clearart': None,
                'clearlogo': None
            },
            'info': {
                'title': label,
                'plot': plot,
                'year': year,
                'mediatype': 'tvshow',
            },
            'cm': [],
            'isfolder': True,
            'isplayable': False
        }
        
        if rating:
            item['info']['rating'] = rating
        
        return item
    
    def get_recently_aired(self, page=1, format=None, prefix=None):
        """
        Recently aired for the last 7 days from AnimeSchedule,
        sorted latest-first, 24 items per page, includes Donghua, using AnimeSchedule data only.
        """
        from resources.lib.endpoints import animeschedule as AS

        # 1) Fetch and sort episodes (latest first)
        episodes = AS.get_recently_aired_raw(
            exclude_donghua=False,
            tz=None,
            air="raw",
            include_airing_now=True
        )

        if not isinstance(episodes, list) or not episodes:
            return []

        def _dt(e):
            from datetime import datetime, timezone
            dt = AS._parse_iso(e.get("episodeDate") or "")
            if not dt:
                return datetime.min.replace(tzinfo=timezone.utc)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

        episodes.sort(key=_dt, reverse=True)

        # 2) Page window (24/page)
        per_page = 24
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        if start_idx >= len(episodes):
            out = []
            base_url = f"{prefix}?page=%d" if prefix else "recently_aired?page=%d"
            return out + self.handle_paging(False, base_url, page)
        page_eps_raw = episodes[start_idx:end_idx]

        # 3) Resolve AnimeSchedule routes -> anime objects
        routes = [e.get("route") for e in page_eps_raw if e.get("route")]
        route_map = AS.as_get_anime_by_routes_batch(routes, timeout_per=8, max_workers=8)

        # 4) Build items using only AnimeSchedule data
        seen_mal = set()
        items = []
        for ep in page_eps_raw:
            r = ep.get("route")
            if not r:
                continue
            a = route_map.get(r) or {}
            mal_id = a.get("malId")
            if not mal_id or mal_id in seen_mal:
                continue
            seen_mal.add(mal_id)
            
            item = self.base_recently_aired_view(ep, a, mal_id)
            items.append(item)
            
            if len(items) >= per_page:
                break

        # If some in the page lacked malId, try to pull forward
        if len(items) < per_page:
            for ep in episodes[end_idx:]:
                if len(items) >= per_page:
                    break
                r = ep.get("route")
                if not r:
                    continue
                a = route_map.get(r)
                if a is None:
                    a = AS.as_get_anime_by_route(r, timeout=8)
                if not isinstance(a, dict):
                    continue
                mal_id = a.get("malId")
                if not mal_id or mal_id in seen_mal:
                    continue
                seen_mal.add(mal_id)
                
                item = self.base_recently_aired_view(ep, a, mal_id)
                items.append(item)

        # 5) Pager
        base_url = f"{prefix}?page=%d" if prefix else "recently_aired?page=%d"
        if end_idx < len(episodes):
            items += self.handle_paging(True, base_url, page)
        else:
            items += self.handle_paging(False, base_url, page)

        return items

    def database_update_show(self, mal_res=None, anilist_res=None):
        """
        Combines MAL and AniList data for database update.
        Uses MAL as primary, fills missing fields from AniList if available.
        """
        # Determine mal_id
        mal_id = None
        if mal_res and 'mal_id' in mal_res:
            mal_id = mal_res['mal_id']
        elif anilist_res and 'idMal' in anilist_res:
            mal_id = anilist_res['idMal']
        if not mal_id:
            return

        # Title
        title_userPreferred = None
        name = None
        ename = None
        titles = None
        if mal_res:
            title_userPreferred = mal_res.get(self.title_lang) or mal_res.get('title')
            name = mal_res.get('title')
            ename = mal_res.get('title_english')
        if (not title_userPreferred or not name) and anilist_res:
            title_userPreferred = anilist_res['title'].get(self.title_lang) or anilist_res['title'].get('romaji')
            name = anilist_res['title'].get('romaji')
            ename = anilist_res['title'].get('english')
        titles = f"({name})|({ename})"

        # Start date
        start_date = None
        if mal_res and mal_res.get('aired') and mal_res['aired'].get('from'):
            start_date = mal_res['aired']['from']
        elif anilist_res and anilist_res.get('startDate'):
            sd = anilist_res['startDate']
            year = sd.get('year')
            month = sd.get('month')
            day = sd.get('day')
            if None not in (year, month, day):
                start_date = '{}-{:02}-{:02}'.format(year, month, day)
            else:
                start_date = ''

        # Episodes
        episodes = mal_res.get('episodes') if mal_res and 'episodes' in mal_res else (anilist_res.get('episodes') if anilist_res and 'episodes' in anilist_res else None)

        # Poster
        poster = None
        if mal_res and mal_res.get('images') and mal_res['images'].get('webp'):
            poster = mal_res['images']['webp'].get('large_image_url')
        if not poster and anilist_res and anilist_res.get('coverImage'):
            poster = anilist_res['coverImage'].get('extraLarge')

        # Status
        status = mal_res.get('status') if mal_res and 'status' in mal_res else (anilist_res.get('status') if anilist_res and 'status' in anilist_res else None)

        # Format
        format_ = mal_res.get('type') if mal_res and 'type' in mal_res else (anilist_res.get('format') if anilist_res and 'format' in anilist_res else '')

        # Plot
        plot = mal_res.get('synopsis') if mal_res and 'synopsis' in mal_res else None
        if not plot and anilist_res and anilist_res.get('description'):
            desc = anilist_res['description']
            desc = desc.replace('<i>', '[I]').replace('</i>', '[/I]')
            desc = desc.replace('<b>', '[B]').replace('</b>', '[/B]')
            desc = desc.replace('<br>', '[CR]')
            desc = desc.replace('\n', '')
            plot = desc

        # Duration
        duration = self.duration_to_seconds(mal_res.get('duration')) if mal_res and 'duration' in mal_res else None
        if not duration and anilist_res and 'duration' in anilist_res and anilist_res['duration'] is not None:
            duration = anilist_res['duration'] * 60

        # Genre
        genre = [x['name'] for x in mal_res.get('genres', [])] if mal_res else None
        if (not genre or not genre) and anilist_res:
            genre = anilist_res.get('genres')

        # Studio
        studio = [x['name'] for x in mal_res.get('studios', [])] if mal_res else None
        if (not studio or not studio) and anilist_res and anilist_res.get('studios'):
            studio = [x['node'].get('name') for x in anilist_res['studios']['edges']]

        # MPAA/country
        mpaa = mal_res.get('rating') if mal_res and 'rating' in mal_res else None
        country = [anilist_res.get('countryOfOrigin', '')] if anilist_res and 'countryOfOrigin' in anilist_res else None

        kodi_meta = {
            'name': name,
            'ename': ename,
            'title_userPreferred': title_userPreferred,
            'start_date': start_date,
            'query': titles,
            'episodes': episodes,
            'poster': poster,
            'status': status,
            'format': format_,
            'plot': plot,
            'duration': duration,
            'genre': genre,
            'studio': studio,
            'mpaa': mpaa,
            'country': country,
        }

        # Premiered/year
        try:
            if mal_res and mal_res.get('aired') and mal_res['aired'].get('from'):
                start_date = mal_res['aired']['from']
                kodi_meta['premiered'] = start_date[:10]
                kodi_meta['year'] = mal_res.get('year', int(start_date[:4]))
            elif anilist_res and anilist_res.get('startDate'):
                sd = anilist_res['startDate']
                kodi_meta['premiered'] = '{}-{:02}-{:02}'.format(sd['year'], sd['month'], sd['day'])
                kodi_meta['year'] = sd['year']
        except Exception:
            pass

        # Cast
        try:
            if anilist_res and anilist_res.get('characters'):
                cast = []
                for i, x in enumerate(anilist_res['characters']['edges']):
                    role = x['node']['name']['userPreferred']
                    actor = x['voiceActors'][0]['name']['userPreferred']
                    actor_hs = x['voiceActors'][0]['image']['large']
                    cast.append({'name': actor, 'role': role, 'thumbnail': actor_hs, 'index': i})
                kodi_meta['cast'] = cast
        except Exception:
            pass

        # Rating
        try:
            if mal_res and isinstance(mal_res.get('score'), float):
                kodi_meta['rating'] = {'score': mal_res['score']}
                if isinstance(mal_res.get('scored_by'), int):
                    kodi_meta['rating']['votes'] = mal_res['scored_by']
            elif anilist_res and anilist_res.get('averageScore'):
                kodi_meta['rating'] = {'score': anilist_res.get('averageScore') / 10.0}
                if anilist_res.get('stats') and anilist_res['stats'].get('scoreDistribution'):
                    total_votes = sum([score['amount'] for score in anilist_res['stats']['scoreDistribution']])
                    kodi_meta['rating']['votes'] = total_votes
        except Exception:
            pass

        # Trailer
        try:
            if mal_res and mal_res.get('trailer'):
                kodi_meta['trailer'] = f"plugin://plugin.video.youtube/play/?video_id={mal_res['trailer']['youtube_id']}"
            elif anilist_res and anilist_res.get('trailer'):
                if anilist_res['trailer']['site'] == 'youtube':
                    kodi_meta['trailer'] = f"plugin://plugin.video.youtube/play/?video_id={anilist_res['trailer']['id']}"
                else:
                    kodi_meta['trailer'] = f"plugin://plugin.video.dailymotion_com/?url={anilist_res['trailer']['id']}&mode=playVideo"
        except Exception:
            pass

        database.update_show(mal_id, pickle.dumps(kodi_meta))

    def update_genre_settings(self):
        mal_res = database.get(self.get_mal_base_res, 24, f'{self._BASE_URL}/genres/anime')

        genre = mal_res['data']
        genres_list = [x['name'] for x in genre]

        multiselect = control.multiselect_dialog(control.lang(30940), genres_list, preselect=[])
        if not multiselect:
            return []

        selected_genres_mal = [str(genre[selection]['mal_id']) for selection in multiselect if selection < len(genres_list)]

        selected_genres_anilist = []

        selected_tags = []

        return selected_genres_mal, selected_genres_anilist, selected_tags