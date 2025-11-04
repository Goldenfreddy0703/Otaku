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


class MalBrowser(BrowserBase):
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

    def process_mal_view(self, res, base_plugin_url, page):
        get_meta.collect_meta(res['data'])
        mapfunc = partial(self.base_mal_view, completed=self.open_completed())
        all_results = list(map(mapfunc, res['data']))
        hasNextPage = res['pagination']['has_next_page']
        all_results += self.handle_paging(hasNextPage, base_plugin_url, page)
        return all_results

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
    
    def process_airing_view(self, json_res):
        ts = int(time.time())
        mapfunc = partial(self.base_airing_view, ts=ts)
        all_results = list(map(mapfunc, json_res['data']))
        return all_results

    def process_res(self, res):
        self.database_update_show(res)
        get_meta.collect_meta([res])
        return database.get_show(res['mal_id'])

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
        import time
        from resources.lib.endpoints import animeschedule
        
        # Check cache first (30 minute expiry)
        cached = self.get_cached_data()
        if cached:
            # Handle new dict format with timestamp
            if isinstance(cached, dict) and 'timestamp' in cached:
                cache_time = cached.get('timestamp', 0)
                cache_age = time.time() - cache_time
                if cache_age < 1800:  # 30 minutes
                    return cached.get('results', [])
        
        # Fetch calendar data from animeschedule.net (includes Donghua)
        episodes = animeschedule.get_airing_calendar(exclude_donghua=False)
        
        if not episodes:
            return []
        
        # Process episodes into calendar view
        results = self.process_calendar_view(episodes)
        
        # Cache the results
        self.set_cached_data({
            'timestamp': time.time(),
            'results': results
        })
        
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
        res = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime/{mal_id}")
        return self.process_res(res['data'])

    def get_recommendations(self, mal_id, page):
        recommendations = database.get(self.get_base_res, 24, f'{self._BASE_URL}/anime/{mal_id}/recommendations')
        get_meta.collect_meta(recommendations['data'])

        recommendation_res = []
        count = 0
        retry_limit = 3

        for recommendation in recommendations['data']:
            entry = recommendation.get('entry')
            if entry and entry.get('mal_id'):
                retries = 0
                while retries < retry_limit:
                    res_data = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime/{entry['mal_id']}")
                    if res_data is not None and 'data' in res_data:
                        res_data['data']['votes'] = recommendation.get('votes')
                        recommendation_res.append(res_data['data'])
                        break
                    else:
                        retries += 1
                        control.sleep(int(100 * retries))  # Reduced linear backoff

                count += 1
                if count % 3 == 0:
                    control.sleep(1000)  # Ensure we do not exceed 3 requests per second

        mapfunc = partial(self.base_mal_view, completed=self.open_completed())
        all_results = list(map(mapfunc, recommendation_res))
        return all_results

    def get_relations(self, mal_id):
        relations = database.get(self.get_base_res, 24, f'{self._BASE_URL}/anime/{mal_id}/relations')
        meta_ids = [{'mal_id': entry['mal_id']} for relation in relations['data'] for entry in relation['entry']]
        get_meta.collect_meta(meta_ids)

        relation_res = []
        count = 0
        retry_limit = 3

        for relation in relations['data']:
            for entry in relation['entry']:
                if entry['type'] == 'anime':
                    retries = 0
                    while retries < retry_limit:
                        res_data = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime/{entry['mal_id']}")
                        if res_data is not None and 'data' in res_data:
                            res_data['data']['relation'] = relation['relation']
                            relation_res.append(res_data['data'])
                            break
                        else:
                            retries += 1
                            control.sleep(int(100 * retries))  # Reduced linear backoff

                    count += 1
                    if count % 3 == 0:
                        control.sleep(1000)  # Ensure we do not exceed 3 requests per second

        mapfunc = partial(self.base_mal_view, completed=self.open_completed())
        all_results = list(map(mapfunc, relation_res))
        return all_results

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
                    mal_item = database.get(self.get_base_res, 24, f'{self._BASE_URL}/anime/{idmal}')

                    if mal_item is not None and 'data' in mal_item:
                        watch_order_list.append(mal_item['data'])
                        break
                    else:
                        retries += 1
                        control.sleep(int(100 * retries))  # Reduced linear backoff

                count += 1
                if count % 3 == 0:
                    control.sleep(1000)  # Ensure we do not exceed 3 requests per second

        mapfunc = partial(self.base_mal_view, completed=self.open_completed())
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

        search = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}/{query}?page=%d" if prefix else f"search_anime/{query}?page=%d"
        return self.process_mal_view(search, base_plugin_url, page)

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

        airing = database.get(self.get_base_res, 24, f"{self._BASE_URL}/seasons/{year}/{season}", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "airing_last_season?page=%d"
        return self.process_mal_view(airing, base_plugin_url, page)

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

        airing = database.get(self.get_base_res, 24, f"{self._BASE_URL}/seasons/{year}/{season}", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "airing_this_season?page=%d"
        return self.process_mal_view(airing, base_plugin_url, page)

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

        airing = database.get(self.get_base_res, 24, f"{self._BASE_URL}/seasons/{year}/{season}", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "airing_next_season?page=%d"
        return self.process_mal_view(airing, base_plugin_url, page)

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

        trending = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "trending_last_year?page=%d"
        return self.process_mal_view(trending, base_plugin_url, page)

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

        trending = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "trending_this_year?page=%d"
        return self.process_mal_view(trending, base_plugin_url, page)

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

        trending = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "trending_last_season?page=%d"
        return self.process_mal_view(trending, base_plugin_url, page)

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

        trending = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "trending_this_season?page=%d"
        return self.process_mal_view(trending, base_plugin_url, page)

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

        trending = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "all_time_trending?page=%d"
        return self.process_mal_view(trending, base_plugin_url, page)

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

        popular = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "popular_last_year?page=%d"
        return self.process_mal_view(popular, base_plugin_url, page)

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

        popular = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "popular_this_year?page=%d"
        return self.process_mal_view(popular, base_plugin_url, page)

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

        popular = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "popular_last_season?page=%d"
        return self.process_mal_view(popular, base_plugin_url, page)

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

        popular = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "popular_this_season?page=%d"
        return self.process_mal_view(popular, base_plugin_url, page)

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

        popular = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "all_time_popular?page=%d"
        return self.process_mal_view(popular, base_plugin_url, page)

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

        voted = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "voted_last_year?page=%d"
        return self.process_mal_view(voted, base_plugin_url, page)

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

        voted = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "voted_this_year?page=%d"
        return self.process_mal_view(voted, base_plugin_url, page)

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

        voted = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "voted_last_season?page=%d"
        return self.process_mal_view(voted, base_plugin_url, page)

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

        voted = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "voted_this_season?page=%d"
        return self.process_mal_view(voted, base_plugin_url, page)

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

        voted = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "all_time_voted?page=%d"
        return self.process_mal_view(voted, base_plugin_url, page)

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

        favourites = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "favourites_last_year?page=%d"
        return self.process_mal_view(favourites, base_plugin_url, page)

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

        favourites = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "favourites_this_year?page=%d"
        return self.process_mal_view(favourites, base_plugin_url, page)

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

        favourites = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "favourites_last_season?page=%d"
        return self.process_mal_view(favourites, base_plugin_url, page)

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

        favourites = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "favourites_this_season?page=%d"
        return self.process_mal_view(favourites, base_plugin_url, page)

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

        favourites = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "all_time_favourites?page=%d"
        return self.process_mal_view(favourites, base_plugin_url, page)

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

        top_100 = database.get(self.get_base_res, 24, f"{self._BASE_URL}/top/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "top_100?page=%d"
        return self.process_mal_view(top_100, base_plugin_url, page)

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

        genre = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_action?page=%d"
        return self.process_mal_view(genre, base_plugin_url, page)

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

        genre = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_adventure?page=%d"
        return self.process_mal_view(genre, base_plugin_url, page)

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

        genre = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_comedy?page=%d"
        return self.process_mal_view(genre, base_plugin_url, page)

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

        genre = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_drama?page=%d"
        return self.process_mal_view(genre, base_plugin_url, page)

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

        genre = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_ecchi?page=%d"
        return self.process_mal_view(genre, base_plugin_url, page)

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

        genre = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_fantasy?page=%d"
        return self.process_mal_view(genre, base_plugin_url, page)

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

        genre = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_hentai?page=%d"
        return self.process_mal_view(genre, base_plugin_url, page)

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

        genre = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_horror?page=%d"
        return self.process_mal_view(genre, base_plugin_url, page)

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

        genre = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_shoujo?page=%d"
        return self.process_mal_view(genre, base_plugin_url, page)

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

        genre = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_mecha?page=%d"
        return self.process_mal_view(genre, base_plugin_url, page)

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

        genre = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_music?page=%d"
        return self.process_mal_view(genre, base_plugin_url, page)

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

        genre = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_mystery?page=%d"
        return self.process_mal_view(genre, base_plugin_url, page)

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

        genre = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_psychological?page=%d"
        return self.process_mal_view(genre, base_plugin_url, page)

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

        genre = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_romance?page=%d"
        return self.process_mal_view(genre, base_plugin_url, page)

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

        genre = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_sci_fi?page=%d"
        return self.process_mal_view(genre, base_plugin_url, page)

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

        genre = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_slice_of_life?page=%d"
        return self.process_mal_view(genre, base_plugin_url, page)

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

        genre = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_sports?page=%d"
        return self.process_mal_view(genre, base_plugin_url, page)

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

        genre = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_supernatural?page=%d"
        return self.process_mal_view(genre, base_plugin_url, page)

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

        genre = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_thriller?page=%d"
        return self.process_mal_view(genre, base_plugin_url, page)

    @staticmethod
    def get_base_res(url, params=None):
        r = client.get(url, params=params)
        if r:
            return r.json()

    def get_airing_calendar_res(self, day, page=1):
        url = f'{self._BASE_URL}/schedules?kids=false&sfw=false&limit=25&page={page}&filter={day}'
        results = self.get_base_res(url)
        return results

    # @div_flavor
    # def recommendation_relation_view(self, res, completed=None, mal_dub=None):
    #     if res.get('entry'):
    #         res = res['entry']
    #     if not completed:
    #         completed = {}

    #     mal_id = res['mal_id']
    #     meta_ids = database.get_mappings(mal_id, 'mal_id')

    #     title = res['title']
    #     if res.get('relation'):
    #         title += ' [I]%s[/I]' % control.colorstr(res['relation'], 'limegreen')

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

    #     dub = True if mal_dub and mal_dub.get(str(res.get('idMal'))) else False

    #     image = res['images']['webp']['large_image_url'] if res.get('images') else None

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
        res = database.get(self.get_base_res, 24, f'{self._BASE_URL}/genres/anime')

        genre = res['data']
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

        genres = database.get(self.get_base_res, 24, f'{self._BASE_URL}/anime', params)

        try:
            from resources.lib import Main
            prefix = Main.plugin_url.split('/', 1)[0]
            base_plugin_url = f"{prefix}/{genre_list}/{tag_list}?page=%d"
        except Exception:
            base_plugin_url = f"genres/{genre_list}/{tag_list}?page=%d"

        return self.process_mal_view(genres, base_plugin_url, page)

    @div_flavor
    def base_mal_view(self, res, completed=None, mal_dub=None):
        if not completed:
            completed = {}

        mal_id = res['mal_id']

        if not database.get_show(mal_id):
            self.database_update_show(res)

        show_meta = database.get_show_meta(mal_id)
        kodi_meta = pickle.loads(show_meta.get('art')) if show_meta else {}

        title = res[self.title_lang] or res['title']
        rating = res.get('rating')
        if rating == 'Rx - Hentai':
            title += ' - ' + control.colorstr("Adult", 'red')
        if res.get('relation'):
            title += ' [I]%s[/I]' % control.colorstr(res['relation'], 'limegreen')

        info = {
            'UniqueIDs': {
                'mal_id': str(mal_id),
                **database.get_unique_ids(mal_id, 'mal_id')
            },
            'title': title,
            'plot': res.get('synopsis'),
            'mpaa': rating,
            'duration': self.duration_to_seconds(res.get('duration')),
            'genre': [x['name'] for x in res.get('genres', [])],
            'studio': [x['name'] for x in res.get('studios', [])],
            'status': res.get('status'),
            'mediatype': 'tvshow'
        }

        if completed.get(str(mal_id)):
            info['playcount'] = 1

        try:
            start_date = res['aired']['from']
            info['premiered'] = start_date[:10]
            info['year'] = res.get('year', int(start_date[:3]))
        except TypeError:
            pass

        if isinstance(res.get('score'), float):
            info['rating'] = {'score': res['score']}
            if isinstance(res.get('scored_by'), int):
                info['rating']['votes'] = res['scored_by']

        if res.get('trailer'):
            info['trailer'] = f"plugin://plugin.video.youtube/play/?video_id={res['trailer']['youtube_id']}"

        dub = True if mal_dub and mal_dub.get(str(mal_id)) else False

        image = res['images']['webp']['large_image_url']
        base = {
            "name": title,
            "url": f'animes/{mal_id}/',
            "image": image,
            "poster": image,
            'fanart': kodi_meta['fanart'] if kodi_meta.get('fanart') else image,
            "banner": image,
            "info": info
        }

        if kodi_meta.get('thumb'):
            base['landscape'] = random.choice(kodi_meta['thumb'])
        if kodi_meta.get('clearart'):
            base['clearart'] = random.choice(kodi_meta['clearart'])
        if kodi_meta.get('clearlogo'):
            base['clearlogo'] = random.choice(kodi_meta['clearlogo'])

        if res['episodes'] == 1:
            base['url'] = f'play_movie/{mal_id}/'
            base['info']['mediatype'] = 'movie'
            return utils.parse_view(base, False, True, dub)
        return utils.parse_view(base, True, False, dub)

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
        
        # Fallback to other image fields if imageVersionRoute not available
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
            # First convert specific tags to Kodi format
            description = description.replace('<br><br>', '[CR]').replace('<br>', '').replace('<i>', '[I]').replace('</i>', '[/I]').replace('<b>', '[B]').replace('</b>', '[/B]')
            # Then strip all remaining HTML tags (including span with attributes)
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
        # AnimeSchedule provides: stats.averageScore (0-100), stats.trackedRating (rank)
        average_score = 0
        rank = 0
        
        stats = anime.get('stats', {})
        if isinstance(stats, dict):
            # averageScore is already 0-100 scale from AnimeSchedule
            if stats.get('averageScore') is not None:
                average_score = round(float(stats['averageScore']))
            # trackedRating is the rank
            if stats.get('trackedRating') is not None:
                rank = stats['trackedRating']
        
        base = {
            'release_title': title,
            'poster': poster or '',
            'ep_title': '{} {} {}{}'.format(episode_num, airing_status, airingAt_day, air_type_str),
            'ep_airingAt': airingAt_time,
            'airing_day': airingAt_day,
            'averageScore': average_score,
            'score': average_score,  # Alias for compatibility
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
            desc = re.sub(r'<[^>]+>', '', desc)  # Strip HTML tags
        
        # Format episode badge
        badge = animeschedule.as_format_episode_badge(ep)
        plot = f"{badge}\n{desc}" if desc else badge
        
        # Get score and rank from AnimeSchedule stats
        rating = None
        stats = anime.get('stats', {})
        if isinstance(stats, dict) and stats.get('averageScore'):
            score = round(float(stats['averageScore'])) / 10.0  # Convert 0-100 to 0-10
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
    
    def base_airing_view(self, res, ts):
        airingAt = datetime.datetime.fromisoformat(res['aired']['from'].replace('Z', '+00:00'))
        airingAt_day = airingAt.strftime('%A')
        airingAt_time = airingAt.strftime('%I:%M %p')
        airing_status = 'airing' if airingAt.timestamp() > ts else 'aired'
        simkl_rank = None
        genres = [genre['name'] for genre in res['genres']]
        if genres:
            genres = ' | '.join(genres[:3])
        else:
            genres = 'Genres Not Found'
        title = res['title']
        episode = res.get('episode', 'N/A')
        rating = res['score']

        # Find Simkl entry
        simkl_entry = Simkl().fetch_and_find_simkl_entry(res['mal_id'])
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
            'poster': res['images']['jpg']['image_url'],
            'ep_title': '{} {} {}'.format(episode, airing_status, airingAt_day),
            'ep_airingAt': airingAt_time,
            'airing_day': airingAt_day,
            'rating': score,
            'simkl_rank': simkl_rank,
            'plot': res['synopsis'].replace('<br><br>', '[CR]').replace('<br>', '').replace('<i>', '[I]').replace('</i>', '[/I]') if res['synopsis'] else res['synopsis'],
            'genres': genres,
            'id': res['mal_id']
        }

        return base

    def database_update_show(self, res):
        mal_id = res['mal_id']

        try:
            start_date = res['aired']['from']
        except TypeError:
            start_date = None

        title_userPreferred = res[self.title_lang] or res['title']

        name = res['title']
        ename = res['title_english']
        titles = f"({name})|({ename})"

        kodi_meta = {
            'name': name,
            'ename': ename,
            'title_userPreferred': title_userPreferred,
            'start_date': start_date,
            'query': titles,
            'episodes': res['episodes'],
            'poster': res['images']['webp']['large_image_url'],
            'status': res.get('status'),
            'format': res.get('type'),
            'plot': res.get('synopsis'),
            'duration': self.duration_to_seconds(res.get('duration')),
            'genre': [x['name'] for x in res.get('genres', [])],
            'studio': [x['name'] for x in res.get('studios', [])],
            'mpaa': res.get('rating'),
        }

        try:
            start_date = res['aired']['from']
            kodi_meta['premiered'] = start_date[:10]
            kodi_meta['year'] = res.get('year', int(start_date[:3]))
        except TypeError:
            pass

        if isinstance(res.get('score'), float):
            kodi_meta['rating'] = {'score': res['score']}
            if isinstance(res.get('scored_by'), int):
                kodi_meta['rating']['votes'] = res['scored_by']

        if res.get('trailer'):
            kodi_meta['trailer'] = f"plugin://plugin.video.youtube/play/?video_id={res['trailer']['youtube_id']}"

        database.update_show(mal_id, pickle.dumps(kodi_meta))

    def update_genre_settings(self):
        res = database.get(self.get_base_res, 24, f'{self._BASE_URL}/genres/anime')

        genre = res['data']
        genres_list = [x['name'] for x in genre]

        multiselect = control.multiselect_dialog(control.lang(30940), genres_list, preselect=[])
        if not multiselect:
            return []

        selected_genres_mal = [str(genre[selection]['mal_id']) for selection in multiselect if selection < len(genres_list)]

        selected_genres_anilist = []

        selected_tags = []

        return selected_genres_mal, selected_genres_anilist, selected_tags

    def get_recently_aired(self, page=1, format=None, prefix=None):
        """
        Recently aired (RAW) for the last 7 days from AnimeSchedule,
        sorted latest-first, exactly 24 items per page, using AnimeSchedule data only.
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

        # 2) Page window (24/page) over the raw episode list
        per_page = 24
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        if start_idx >= len(episodes):
            out = []
            base_url = f"{prefix}?page=%d" if prefix else "recently_aired?page=%d"
            return out + self.handle_paging(False, base_url, page)
        page_eps_raw = episodes[start_idx:end_idx]

        # 3) Resolve AnimeSchedule routes -> anime objects to get MAL IDs
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
            
            # Use helper method to build item from AnimeSchedule data only
            item = self.base_recently_aired_view(ep, a, mal_id)
            items.append(item)
            
            if len(items) >= per_page:
                break

        # If some in the page lacked malId, try to pull forward from remaining episodes
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