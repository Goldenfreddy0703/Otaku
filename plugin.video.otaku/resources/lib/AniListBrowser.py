import ast
import json
import pickle
import random
import re
import os

from bs4 import BeautifulSoup
from functools import partial
from resources.lib.ui import database, get_meta, utils, control, client
from resources.lib.ui.BrowserBase import BrowserBase
from resources.lib.ui.divide_flavors import div_flavor
from concurrent.futures import ThreadPoolExecutor


class AniListBrowser(BrowserBase):
    _BASE_URL = "https://graphql.anilist.co"
    _ANILIST_DETAILS_CACHE: dict[int, dict] = {}

    def __init__(self):
        self.title_lang = ["romaji", 'english'][control.getInt("titlelanguage")]
        self.perpage = control.getInt('interface.perpage.general.anilist')
        self.year_type = control.getInt('contentyear.menu') if control.getBool('contentyear.bool') else 0
        self.season_type = control.getInt('contentseason.menu') if control.getBool('contentseason.bool') else -1
        self.format_in_type = ['TV', 'MOVIE', 'TV_SHORT', 'SPECIAL', 'OVA', 'ONA', 'MUSIC'][control.getInt('contentformat.menu')] if control.getBool('contentformat.bool') else ''
        self.status = ['RELEASING', 'FINISHED', 'NOT_YET_RELEASED', 'CANCELLED'][control.getInt('contentstatus.menu.anilist')] if control.getBool('contentstatus.bool') else ''
        self.countryOfOrigin_type = ['JP', 'KR', 'CN', 'TW'][control.getInt('contentorigin.menu')] if control.getBool('contentorigin.bool') else ''
        self.genre = self.load_genres_from_json() if control.getBool('contentgenre.bool') else ''
        self.tag = self.load_tags_from_json() if control.getBool('contentgenre.bool') else ''

        if self.genre == ('',):
            self.genre = ''

        if self.tag == ('',):
            self.tag = ''

    def load_genres_from_json(self):
        if os.path.exists(control.genre_json):
            with open(control.genre_json, 'r') as f:
                settings = json.load(f)
                return tuple(settings.get('selected_genres_anilist', []))
        return ()

    def load_tags_from_json(self):
        if os.path.exists(control.genre_json):
            with open(control.genre_json, 'r') as f:
                settings = json.load(f)
                return tuple(settings.get('selected_tags', []))
        return ()

    def get_season_year(self, period='current'):
        import datetime
        date = datetime.datetime.today()
        year = date.year
        month = date.month
        seasons = ['WINTER', 'SPRING', 'SUMMER', 'FALL']

        if self.year_type:
            if 1916 < self.year_type <= year + 1:
                year = self.year_type
            else:
                control.notify(control.ADDON_NAME, "Invalid year. Please select a year between 1916 and {0}.".format(year + 1))
                return None, None

        if self.season_type > -1:
            season_id = self.season_type
        else:
            season_id = int((month - 1) / 3)

        if period == "next":
            season = seasons[(season_id + 1) % 4]
            if season == 'WINTER':
                year += 1
        elif period == "last":
            season = seasons[(season_id - 1) % 4]
            if season == 'FALL' and month <= 3:
                year -= 1
        else:
            season = seasons[season_id]

        return season, year

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
        
        # Fetch calendar data from animeschedule.net
        episodes = animeschedule.get_airing_calendar(exclude_donghua=True)
        
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
        if os.path.exists(control.anilist_calendar_json):
            with open(control.anilist_calendar_json, 'r') as f:
                return json.load(f)
        return None

    def set_cached_data(self, data):
        with open(control.anilist_calendar_json, 'w') as f:
            json.dump(data, f)

    def get_airing_last_season(self, page, format, prefix=None):
        season, year = self.get_season_year('last')
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'season': season,
            'year': f'{year}%',
            'sort': "TRENDING_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        if self.genre:
            variables['includedGenres'] = self.genre

        if self.tag:
            variables['includedTags'] = self.tag

        airing = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "airing_last_season?page=%d"
        return self.process_anilist_view(airing, base_plugin_url, page)

    def get_airing_this_season(self, page, format, prefix=None):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'season': season,
            'year': f'{year}%',
            'sort': "POPULARITY_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        if self.genre:
            variables['includedGenres'] = self.genre

        if self.tag:
            variables['includedTags'] = self.tag

        airing = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "airing_this_season?page=%d"
        return self.process_anilist_view(airing, base_plugin_url, page)

    def get_airing_next_season(self, page, format, prefix=None):
        season, year = self.get_season_year('next')
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'season': season,
            'year': f'{year}%',
            'sort': "POPULARITY_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        if self.genre:
            variables['includedGenres'] = self.genre

        if self.tag:
            variables['includedTags'] = self.tag

        airing = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "airing_next_season?page=%d"
        return self.process_anilist_view(airing, base_plugin_url, page)

    def get_trending_last_year(self, page, format, prefix=None):
        season, year = self.get_season_year('')
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'year': f'{year - 1}%',
            'sort': "TRENDING_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        if self.genre:
            variables['includedGenres'] = self.genre

        if self.tag:
            variables['includedTags'] = self.tag

        trending = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "trending_last_year?page=%d"
        return self.process_anilist_view(trending, base_plugin_url, page)

    def get_trending_this_year(self, page, format, prefix=None):
        season, year = self.get_season_year('')
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'year': f'{year}%',
            'sort': "TRENDING_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        if self.genre:
            variables['includedGenres'] = self.genre

        if self.tag:
            variables['includedTags'] = self.tag

        trending = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "trending_this_year?page=%d"
        return self.process_anilist_view(trending, base_plugin_url, page)

    def get_trending_last_season(self, page, format, prefix=None):
        season, year = self.get_season_year('last')
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'season': season,
            'year': f'{year}%',
            'sort': "TRENDING_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        if self.genre:
            variables['includedGenres'] = self.genre

        if self.tag:
            variables['includedTags'] = self.tag

        trending = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "trending_last_season?page=%d"
        return self.process_anilist_view(trending, base_plugin_url, page)

    def get_trending_this_season(self, page, format, prefix=None):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'season': season,
            'year': f'{year}%',
            'sort': "TRENDING_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        if self.genre:
            variables['includedGenres'] = self.genre

        if self.tag:
            variables['includedTags'] = self.tag

        trending = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "trending_this_season?page=%d"
        return self.process_anilist_view(trending, base_plugin_url, page)

    def get_all_time_trending(self, page, format, prefix=None):
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'sort': "TRENDING_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        if self.genre:
            variables['includedGenres'] = self.genre

        if self.tag:
            variables['includedTags'] = self.tag

        trending = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "all_time_trending?page=%d"
        return self.process_anilist_view(trending, base_plugin_url, page)

    def get_popular_last_year(self, page, format, prefix=None):
        season, year = self.get_season_year('')
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'year': f'{year - 1}%',
            'sort': "POPULARITY_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        if self.genre:
            variables['includedGenres'] = self.genre

        if self.tag:
            variables['includedTags'] = self.tag

        popular = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "popular_last_year?page=%d"
        return self.process_anilist_view(popular, base_plugin_url, page)

    def get_popular_this_year(self, page, format, prefix=None):
        season, year = self.get_season_year('')
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'year': f'{year}%',
            'sort': "POPULARITY_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        if self.genre:
            variables['includedGenres'] = self.genre

        if self.tag:
            variables['includedTags'] = self.tag

        popular = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "popular_this_year?page=%d"
        return self.process_anilist_view(popular, base_plugin_url, page)

    def get_popular_last_season(self, page, format, prefix=None):
        season, year = self.get_season_year('last')
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'season': season,
            'year': f'{year}%',
            'sort': "POPULARITY_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        if self.genre:
            variables['includedGenres'] = self.genre

        if self.tag:
            variables['includedTags'] = self.tag

        popular = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "popular_last_season?page=%d"
        return self.process_anilist_view(popular, base_plugin_url, page)

    def get_popular_this_season(self, page, format, prefix=None):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'season': season,
            'year': f'{year}%',
            'sort': "POPULARITY_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        if self.genre:
            variables['includedGenres'] = self.genre

        if self.tag:
            variables['includedTags'] = self.tag

        popular = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "popular_this_season?page=%d"
        return self.process_anilist_view(popular, base_plugin_url, page)

    def get_all_time_popular(self, page, format, prefix=None):
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'sort': "POPULARITY_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        if self.genre:
            variables['includedGenres'] = self.genre

        if self.tag:
            variables['includedTags'] = self.tag

        popular = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "all_time_popular?page=%d"
        return self.process_anilist_view(popular, base_plugin_url, page)

    def get_voted_last_year(self, page, format, prefix=None):
        season, year = self.get_season_year('')
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'year': f'{year - 1}%',
            'sort': "SCORE_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        if self.genre:
            variables['includedGenres'] = self.genre

        if self.tag:
            variables['includedTags'] = self.tag

        voted = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "voted_last_year?page=%d"
        return self.process_anilist_view(voted, base_plugin_url, page)

    def get_voted_this_year(self, page, format, prefix=None):
        season, year = self.get_season_year('')
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'year': f'{year}%',
            'sort': "SCORE_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        if self.genre:
            variables['includedGenres'] = self.genre

        if self.tag:
            variables['includedTags'] = self.tag

        voted = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "voted_this_year?page=%d"
        return self.process_anilist_view(voted, base_plugin_url, page)

    def get_voted_last_season(self, page, format, prefix=None):
        season, year = self.get_season_year('last')
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'season': season,
            'year': f'{year}%',
            'sort': "SCORE_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        if self.genre:
            variables['includedGenres'] = self.genre

        if self.tag:
            variables['includedTags'] = self.tag

        voted = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "voted_last_season?page=%d"
        return self.process_anilist_view(voted, base_plugin_url, page)

    def get_voted_this_season(self, page, format, prefix=None):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'season': season,
            'year': f'{year}%',
            'sort': "SCORE_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        if self.genre:
            variables['includedGenres'] = self.genre

        if self.tag:
            variables['includedTags'] = self.tag

        voted = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "voted_this_season?page=%d"
        return self.process_anilist_view(voted, base_plugin_url, page)

    def get_all_time_voted(self, page, format, prefix=None):
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'sort': "SCORE_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        if self.genre:
            variables['includedGenres'] = self.genre

        if self.tag:
            variables['includedTags'] = self.tag

        voted = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "all_time_voted?page=%d"
        return self.process_anilist_view(voted, base_plugin_url, page)

    def get_favourites_last_year(self, page, format, prefix=None):
        season, year = self.get_season_year('')
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'year': f'{year - 1}%',
            'sort': "FAVOURITES_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        if self.genre:
            variables['includedGenres'] = self.genre

        if self.tag:
            variables['includedTags'] = self.tag

        favourites = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "favourites_last_year?page=%d"
        return self.process_anilist_view(favourites, base_plugin_url, page)

    def get_favourites_this_year(self, page, format, prefix=None):
        season, year = self.get_season_year('')
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'year': f'{year}%',
            'sort': "FAVOURITES_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        if self.genre:
            variables['includedGenres'] = self.genre

        if self.tag:
            variables['includedTags'] = self.tag

        favourites = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "favourites_this_year?page=%d"
        return self.process_anilist_view(favourites, base_plugin_url, page)

    def get_favourites_last_season(self, page, format, prefix=None):
        season, year = self.get_season_year('last')
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'season': season,
            'year': f'{year}%',
            'sort': "FAVOURITES_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        if self.genre:
            variables['includedGenres'] = self.genre

        if self.tag:
            variables['includedTags'] = self.tag

        favourites = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "favourites_last_season?page=%d"
        return self.process_anilist_view(favourites, base_plugin_url, page)

    def get_favourites_this_season(self, page, format, prefix=None):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'season': season,
            'year': f'{year}%',
            'sort': "FAVOURITES_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        if self.genre:
            variables['includedGenres'] = self.genre

        if self.tag:
            variables['includedTags'] = self.tag

        favourites = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "favourites_this_season?page=%d"
        return self.process_anilist_view(favourites, base_plugin_url, page)

    def get_all_time_favourites(self, page, format, prefix=None):
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'sort': "FAVOURITES_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        if self.genre:
            variables['includedGenres'] = self.genre

        if self.tag:
            variables['includedTags'] = self.tag

        favourites = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "all_time_favourites?page=%d"
        return self.process_anilist_view(favourites, base_plugin_url, page)

    def get_top_100(self, page, format, prefix=None):
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'sort': "SCORE_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        if self.genre:
            variables['includedGenres'] = self.genre

        if self.tag:
            variables['includedTags'] = self.tag

        top_100 = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "top_100?page=%d"
        return self.process_anilist_view(top_100, base_plugin_url, page)

    def get_genre_action(self, page, format, prefix=None):
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'includedGenres': "Action",
            'sort': "POPULARITY_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        genre = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_action?page=%d"
        return self.process_anilist_view(genre, base_plugin_url, page)

    def get_genre_adventure(self, page, format, prefix=None):
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'includedGenres': "Adventure",
            'sort': "POPULARITY_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        genre = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_adventure?page=%d"
        return self.process_anilist_view(genre, base_plugin_url, page)

    def get_genre_comedy(self, page, format, prefix=None):
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'includedGenres': "Comedy",
            'sort': "POPULARITY_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        genre = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_comedy?page=%d"
        return self.process_anilist_view(genre, base_plugin_url, page)

    def get_genre_drama(self, page, format, prefix=None):
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'includedGenres': "Drama",
            'sort': "POPULARITY_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        genre = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_drama?page=%d"
        return self.process_anilist_view(genre, base_plugin_url, page)

    def get_genre_ecchi(self, page, format, prefix=None):
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'includedGenres': "Ecchi",
            'sort': "POPULARITY_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        genre = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_ecchi?page=%d"
        return self.process_anilist_view(genre, base_plugin_url, page)

    def get_genre_fantasy(self, page, format, prefix=None):
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'includedGenres': "Fantasy",
            'sort': "POPULARITY_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        genre = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_fantasy?page=%d"
        return self.process_anilist_view(genre, base_plugin_url, page)

    def get_genre_hentai(self, page, format, prefix=None):
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'includedGenres': "Hentai",
            'sort': "POPULARITY_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        genre = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_hentai?page=%d"
        return self.process_anilist_view(genre, base_plugin_url, page)

    def get_genre_horror(self, page, format, prefix=None):
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'includedGenres': "Horror",
            'sort': "POPULARITY_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        genre = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_horror?page=%d"
        return self.process_anilist_view(genre, base_plugin_url, page)

    def get_genre_shoujo(self, page, format, prefix=None):
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'includedGenres': "Shoujo",
            'sort': "POPULARITY_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        genre = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_shoujo?page=%d"
        return self.process_anilist_view(genre, base_plugin_url, page)

    def get_genre_mecha(self, page, format, prefix=None):
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'includedGenres': "Mecha",
            'sort': "POPULARITY_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        genre = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_mecha?page=%d"
        return self.process_anilist_view(genre, base_plugin_url, page)

    def get_genre_music(self, page, format, prefix=None):
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'includedGenres': "Music",
            'sort': "POPULARITY_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        genre = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_music?page=%d"
        return self.process_anilist_view(genre, base_plugin_url, page)

    def get_genre_mystery(self, page, format, prefix=None):
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'includedGenres': "Mystery",
            'sort': "POPULARITY_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        genre = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_mystery?page=%d"
        return self.process_anilist_view(genre, base_plugin_url, page)

    def get_genre_psychological(self, page, format, prefix=None):
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'includedGenres': "Psychological",
            'sort': "POPULARITY_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        genre = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_psychological?page=%d"
        return self.process_anilist_view(genre, base_plugin_url, page)

    def get_genre_romance(self, page, format, prefix=None):
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'includedGenres': "Romance",
            'sort': "POPULARITY_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        genre = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_romance?page=%d"
        return self.process_anilist_view(genre, base_plugin_url, page)

    def get_genre_sci_fi(self, page, format, prefix=None):
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'includedGenres': "Sci-Fi",
            'sort': "POPULARITY_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        genre = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_sci_fi?page=%d"
        return self.process_anilist_view(genre, base_plugin_url, page)

    def get_genre_slice_of_life(self, page, format, prefix=None):
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'includedGenres': "Slice of Life",
            'sort': "POPULARITY_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        genre = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_slice_of_life?page=%d"
        return self.process_anilist_view(genre, base_plugin_url, page)

    def get_genre_sports(self, page, format, prefix=None):
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'includedGenres': "Sports",
            'sort': "POPULARITY_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        genre = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_sports?page=%d"
        return self.process_anilist_view(genre, base_plugin_url, page)

    def get_genre_supernatural(self, page, format, prefix=None):
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'includedGenres': "Supernatural",
            'sort': "POPULARITY_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        genre = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_supernatural?page=%d"
        return self.process_anilist_view(genre, base_plugin_url, page)

    def get_genre_thriller(self, page, format, prefix=None):
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': "ANIME",
            'includedGenres': "Thriller",
            'sort': "POPULARITY_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        genre = database.get(self.get_base_res, 24, variables)
        base_plugin_url = f"{prefix}?page=%d" if prefix else "genre_thriller?page=%d"
        return self.process_anilist_view(genre, base_plugin_url, page)

    def get_search(self, query, page, format, prefix=None):
        variables = {
            'page': page,
            'perpage': self.perpage,
            'search': query,
            'sort': "SEARCH_MATCH",
            'type': "ANIME"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        search = self.get_search_res(variables)
        if control.getBool('search.adult'):
            variables['isAdult'] = True
            search_adult = self.get_search_res(variables)
            for i in search_adult["ANIME"]:
                i['title']['english'] = f'{i["title"]["english"]} - {control.colorstr("Adult", "red")}'
            search['ANIME'] += search_adult['ANIME']
        base_plugin_url = f"{prefix}/{query}?page=%d" if prefix else f"search_anime/{query}?page=%d"
        return self.process_anilist_view(search, base_plugin_url, page)

    def get_recommendations(self, mal_id, page):
        variables = {
            'page': page,
            'perPage': self.perpage,
            'idMal': mal_id
        }
        recommendations = database.get(self.get_recommendations_res, 24, variables)
        return self.process_recommendations_view(recommendations, f'find_recommendations/{mal_id}?page=%d', page)

    def get_relations(self, mal_id):
        variables = {
            'idMal': mal_id
        }
        relations = database.get(self.get_relations_res, 24, variables)
        return self.process_relations_view(relations)

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

            watch_order_list = []
            for idmal in mal_ids:
                variables = {
                    'idMal': int(idmal),
                    'type': "ANIME"
                }

                anilist_item = database.get(self.get_anilist_res_with_mal_id, 24, variables)
                if anilist_item is not None:
                    watch_order_list.append(anilist_item)

        return self.process_watch_order_view(watch_order_list)

    def get_anime(self, mal_id):
        variables = {
            'idMal': mal_id,
            'type': "ANIME"
        }
        anilist_res = database.get(self.get_anilist_res, 24, variables)
        return self.process_res(anilist_res)

    def get_base_res(self, variables):
        query = '''
        query (
            $page: Int=1,
            $perpage: Int=20,
            $type: MediaType,
            $isAdult: Boolean = false,
            $format: [MediaFormat],
            $countryOfOrigin: CountryCode,
            $season: MediaSeason,
            $includedGenres: [String],
            $includedTags: [String],
            $year: String,
            $status: MediaStatus,
            $sort: [MediaSort] = [POPULARITY_DESC, SCORE_DESC]
        ) {
            Page (page: $page, perPage: $perpage) {
                pageInfo {
                    hasNextPage
                }
                ANIME: media (
                    format_in: $format,
                    type: $type,
                    genre_in: $includedGenres,
                    tag_in: $includedTags,
                    season: $season,
                    startDate_like: $year,
                    sort: $sort,
                    status: $status,
                    isAdult: $isAdult,
                    countryOfOrigin: $countryOfOrigin
                ) {
                    id
                    idMal
                    title {
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
                    description
                    synonyms
                    format
                    episodes
                    status
                    genres
                    duration
                    countryOfOrigin
                    averageScore
                    stats {
                        scoreDistribution {
                            score
                            amount
                        }
                    }
                    trailer {
                        id
                        site
                    }
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
                }
            }
        }
        '''

        response = client.post(self._BASE_URL, json_data={'query': query, 'variables': variables})
        results = response.json()

        if "errors" in results.keys():
            return

        json_res = results.get('data', {}).get('Page')

        if control.getBool('general.malposters'):
            try:
                for anime in json_res['ANIME']:
                    anilist_id = anime['id']
                    mal_mapping = database.get_mappings(anilist_id, 'anilist_id')
                    if mal_mapping and 'mal_picture' in mal_mapping:
                        mal_picture = mal_mapping['mal_picture']
                        mal_picture_url = mal_picture.rsplit('.', 1)[0] + 'l.' + mal_picture.rsplit('.', 1)[1]
                        mal_picture_url = 'https://cdn.myanimelist.net/images/anime/' + mal_picture_url
                        anime['coverImage']['extraLarge'] = mal_picture_url
            except Exception:
                pass

        if json_res:
            return json_res

    def get_search_res(self, variables):
        query = '''
        query (
            $page: Int=1,
            $perpage: Int=20
            $type: MediaType,
            $isAdult: Boolean = false,
            $format: [MediaFormat],
            $search: String,
            $sort: [MediaSort] = [SCORE_DESC, POPULARITY_DESC]
        ) {
            Page (page: $page, perPage: $perpage) {
                pageInfo {
                    hasNextPage
                }
                ANIME: media (
                    format_in: $format,
                    type: $type,
                    search: $search,
                    sort: $sort,
                    isAdult: $isAdult
                ) {
                    id
                    idMal
                    title {
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
                    description
                    synonyms
                    format
                    episodes
                    status
                    genres
                    duration
                    countryOfOrigin
                    averageScore
                    stats {
                        scoreDistribution {
                            score
                            amount
                        }
                    }
                    trailer {
                        id
                        site
                    }
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
                }
            }
        }
        '''

        response = client.post(self._BASE_URL, json_data={'query': query, 'variables': variables})
        results = response.json()

        if "errors" in results.keys():
            return

        json_res = results.get('data', {}).get('Page')

        if control.getBool('general.malposters'):
            try:
                for anime in json_res['ANIME']:
                    anilist_id = anime['id']
                    mal_mapping = database.get_mappings(anilist_id, 'anilist_id')
                    if mal_mapping and 'mal_picture' in mal_mapping:
                        mal_picture = mal_mapping['mal_picture']
                        mal_picture_url = mal_picture.rsplit('.', 1)[0] + 'l.' + mal_picture.rsplit('.', 1)[1]
                        mal_picture_url = 'https://cdn.myanimelist.net/images/anime/' + mal_picture_url
                        anime['coverImage']['extraLarge'] = mal_picture_url
            except Exception:
                pass

        if json_res:
            return json_res

    def get_recommendations_res(self, variables):
        query = '''
        query ($idMal: Int, $page: Int, $perpage: Int=20) {
          Media(idMal: $idMal, type: ANIME) {
            id
            recommendations(page: $page, perPage: $perpage, sort: [RATING_DESC, ID]) {
              pageInfo {
                hasNextPage
              }
              edges {
                node {
                  id
                  rating
                  mediaRecommendation {
                    id
                    idMal
                    title {
                      romaji
                      english
                    }
                    genres
                    averageScore
                    description(asHtml: false)
                    coverImage {
                      extraLarge
                    }
                    bannerImage
                    startDate {
                      year
                      month
                      day
                    }
                    format
                    episodes
                    duration
                    status
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
                    characters (perPage: 10) {
                      edges {
                        node {
                          name {
                            full
                            native
                            userPreferred
                          }
                        }
                        voiceActors(language: JAPANESE) {
                          id
                          name {
                            full
                            native
                            userPreferred
                          }
                          image {
                            large
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        '''

        response = client.post(self._BASE_URL, json_data={'query': query, 'variables': variables})
        results = response.json()

        if "errors" in results.keys():
            return

        json_res = results.get('data', {}).get('Media', {}).get('recommendations')

        if control.getBool('general.malposters'):
            try:
                for recommendation in json_res['edges']:
                    anime = recommendation['node']['mediaRecommendation']
                    anilist_id = anime['id']
                    mal_mapping = database.get_mappings(anilist_id, 'anilist_id')
                    if mal_mapping and 'mal_picture' in mal_mapping:
                        mal_picture = mal_mapping['mal_picture']
                        mal_picture_url = mal_picture.rsplit('.', 1)[0] + 'l.' + mal_picture.rsplit('.', 1)[1]
                        mal_picture_url = 'https://cdn.myanimelist.net/images/anime/' + mal_picture_url
                        anime['coverImage']['extraLarge'] = mal_picture_url
            except Exception:
                pass

        if json_res:
            return json_res

    def get_relations_res(self, variables):
        query = '''
        query ($idMal: Int) {
          Media(idMal: $idMal, type: ANIME) {
            relations {
              edges {
                relationType
                node {
                  id
                  idMal
                  title {
                    romaji
                    english
                  }
                  genres
                  averageScore
                  description(asHtml: false)
                  coverImage {
                    extraLarge
                  }
                  bannerImage
                  startDate {
                    year
                    month
                    day
                  }
                  format
                  episodes
                  duration
                  status
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
                  characters (perPage: 10) {
                    edges {
                      node {
                        name {
                          full
                          native
                          userPreferred
                        }
                      }
                      voiceActors(language: JAPANESE) {
                        id
                        name {
                          full
                          native
                          userPreferred
                        }
                        image {
                          large
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        '''

        response = client.post(self._BASE_URL, json_data={'query': query, 'variables': variables})
        results = response.json()

        if "errors" in results.keys():
            return

        json_res = results.get('data', {}).get('Media', {}).get('relations')

        if control.getBool('general.malposters'):
            try:
                for relation in json_res['edges']:
                    anime = relation['node']
                    anilist_id = anime['id']
                    mal_mapping = database.get_mappings(anilist_id, 'anilist_id')
                    if mal_mapping and 'mal_picture' in mal_mapping:
                        mal_picture = mal_mapping['mal_picture']
                        mal_picture_url = mal_picture.rsplit('.', 1)[0] + 'l.' + mal_picture.rsplit('.', 1)[1]
                        mal_picture_url = 'https://cdn.myanimelist.net/images/anime/' + mal_picture_url
                        anime['coverImage']['extraLarge'] = mal_picture_url
            except Exception:
                pass

        if json_res:
            return json_res

    def get_anilist_res(self, variables):
        query = '''
        query($idMal: Int, $type: MediaType){
            Media(idMal: $idMal, type: $type) {
                id
                idMal
                title {
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
                description
                synonyms
                format
                episodes
                status
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
                stats {
                    scoreDistribution {
                        score
                        amount
                    }
                }
            }
        }
        '''

        response = client.post(self._BASE_URL, json_data={'query': query, 'variables': variables})
        results = response.json()

        if "errors" in results.keys():
            return

        json_res = results.get('data', {}).get('Media')

        if json_res:
            return json_res

    def get_airing_calendar_res(self, variables, page=1):
        query = '''
        query (
                $weekStart: Int,
                $weekEnd: Int,
                $page: Int,
        ){
            Page(page: $page) {
                pageInfo {
                        hasNextPage
                        total
                }

                airingSchedules(
                        airingAt_greater: $weekStart
                        airingAt_lesser: $weekEnd
                ) {
                    id
                    episode
                    airingAt
                    media {
                        id
                        idMal
                        title {
                                romaji
                                userPreferred
                                english
                        }
                        description
                        countryOfOrigin
                        genres
                        averageScore
                        isAdult
                        rankings {
                                rank
                                type
                                season
                        }
                        coverImage {
                                extraLarge
                        }
                        bannerImage
                    }
                }
            }
        }
        '''

        response = client.post(self._BASE_URL, json_data={'query': query, 'variables': variables})
        results = response.json()

        if "errors" in results.keys():
            return

        json_res = results.get('data', {}).get('Page')

        if json_res:
            return json_res

    def get_anilist_res_with_mal_id(self, variables):
        query = '''
        query($idMal: Int, $type: MediaType){Media(idMal: $idMal, type: $type) {
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
            description
            synonyms
            format
            episodes
            status
            genres
            duration
            countryOfOrigin
            averageScore
            stats {
                scoreDistribution {
                    score
                    amount
                }
            }
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
            }
        }
        '''
        response = client.post(self._BASE_URL, json_data={'query': query, 'variables': variables})
        results = response.json()

        if "errors" in results.keys():
            return

        json_res = results.get('data', {}).get('Media')

        if json_res:
            return json_res

    def process_anilist_view(self, json_res, base_plugin_url, page):
        hasNextPage = json_res['pageInfo']['hasNextPage']
        get_meta.collect_meta(json_res['ANIME'])
        mapfunc = partial(self.base_anilist_view, completed=self.open_completed())
        all_results = list(filter(lambda x: True if x else False, map(mapfunc, json_res['ANIME'])))
        all_results += self.handle_paging(hasNextPage, base_plugin_url, page)
        return all_results

    def process_recommendations_view(self, json_res, base_plugin_url, page):
        hasNextPage = json_res['pageInfo']['hasNextPage']
        res = [edge['node']['mediaRecommendation'] for edge in json_res['edges'] if edge['node']['mediaRecommendation']]
        get_meta.collect_meta(res)
        mapfunc = partial(self.base_anilist_view, completed=self.open_completed())
        all_results = list(filter(lambda x: True if x else False, map(mapfunc, res)))
        all_results += self.handle_paging(hasNextPage, base_plugin_url, page)
        return all_results

    def process_relations_view(self, json_res):
        res = []
        for edge in json_res['edges']:
            if edge['relationType'] != 'ADAPTATION':
                tnode = edge['node']
                tnode['relationType'] = edge['relationType']
                res.append(tnode)
        get_meta.collect_meta(res)
        mapfunc = partial(self.base_anilist_view, completed=self.open_completed())
        all_results = list(filter(lambda x: True if x else False, map(mapfunc, res)))
        return all_results

    def process_watch_order_view(self, json_res):
        res = json_res
        get_meta.collect_meta(res)
        mapfunc = partial(self.base_anilist_view, completed=self.open_completed())
        all_results = list(filter(lambda x: True if x else False, map(mapfunc, res)))
        return all_results

    def get_anilist_data_batch(self, anilist_ids):
        """Batch fetch AniList data (averageScore, popularity) for calendar."""
        if not anilist_ids:
            return {}
        
        # AniList GraphQL allows up to ~50 IDs per query, so batch them
        batch_size = 50
        anilist_data = {}
        
        for i in range(0, len(anilist_ids), batch_size):
            batch_ids = anilist_ids[i:i + batch_size]
            
            query = '''
            query ($ids: [Int]) {
                Page(perPage: 50) {
                    media(id_in: $ids, type: ANIME) {
                        id
                        idMal
                        averageScore
                        popularity
                    }
                }
            }
            '''
            
            variables = {'ids': batch_ids}
            try:
                response = client.post(self._BASE_URL, json_data={'query': query, 'variables': variables})
                if response:
                    data = response.json()
                    if data and 'data' in data and 'Page' in data['data']:
                        for anime in data['data']['Page']['media']:
                            if anime and anime.get('id'):
                                anilist_data[anime['id']] = {
                                    'averageScore': anime.get('averageScore'),
                                    'popularity': anime.get('popularity')
                                }
            except Exception as e:
                control.log(f"[AniList Calendar] Error fetching AniList data batch: {e}", "error")
        
        return anilist_data
    
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
        import time
        filter_json = [x for x in json_res['airingSchedules'] if x['media']['isAdult'] is False]
        ts = int(time.time())
        mapfunc = partial(self.base_airing_view, ts=ts)
        all_results = list(map(mapfunc, filter_json))
        return all_results

    def process_res(self, res):
        self.database_update_show(res)
        get_meta.collect_meta([res])
        return database.get_show(res['idMal'])

    @div_flavor
    def base_anilist_view(self, res, completed=None, mal_dub=None):
        if not completed:
            completed = {}
        anilist_id = res['id']
        mal_id = res.get('idMal')

        if not mal_id:
            return

        if not database.get_show(mal_id):
            self.database_update_show(res)

        show_meta = database.get_show_meta(mal_id)
        kodi_meta = pickle.loads(show_meta.get('art')) if show_meta else {}

        title = res['title'][self.title_lang] or res['title']['romaji']

        if res.get('relationType'):
            title += ' [I]%s[/I]' % control.colorstr(res['relationType'], 'limegreen')

        if desc := res.get('description'):
            desc = desc.replace('<i>', '[I]').replace('</i>', '[/I]')
            desc = desc.replace('<b>', '[B]').replace('</b>', '[/B]')
            desc = desc.replace('<br>', '[CR]')
            desc = desc.replace('\n', '')

        info = {
            'UniqueIDs': {
                'anilist_id': str(anilist_id),
                'mal_id': str(mal_id),
                **database.get_unique_ids(anilist_id, 'anilist_id'),
                **database.get_unique_ids(mal_id, 'mal_id')
            },
            'genre': res.get('genres'),
            'title': title,
            'plot': desc,
            'status': res.get('status'),
            'mediatype': 'tvshow',
            'country': [res.get('countryOfOrigin', '')]
        }

        if completed.get(str(mal_id)):
            info['playcount'] = 1

        try:
            start_date = res.get('startDate')
            info['premiered'] = '{}-{:02}-{:02}'.format(start_date['year'], start_date['month'], start_date['day'])
            info['year'] = start_date['year']
        except TypeError:
            pass

        try:
            cast = []
            for i, x in enumerate(res['characters']['edges']):
                role = x['node']['name']['userPreferred']
                actor = x['voiceActors'][0]['name']['userPreferred']
                actor_hs = x['voiceActors'][0]['image']['large']
                cast.append({'name': actor, 'role': role, 'thumbnail': actor_hs, 'index': i})
            info['cast'] = cast
        except IndexError:
            pass

        info['studio'] = [x['node'].get('name') for x in res['studios']['edges']]

        try:
            info['rating'] = {'score': res.get('averageScore') / 10.0}
            if res.get('stats') and res['stats'].get('scoreDistribution'):
                total_votes = sum([score['amount'] for score in res['stats']['scoreDistribution']])
                info['rating']['votes'] = total_votes
        except TypeError:
            pass

        try:
            info['duration'] = res['duration'] * 60
        except TypeError:
            pass

        try:
            if res['trailer']['site'] == 'youtube':
                info['trailer'] = f"plugin://plugin.video.youtube/play/?video_id={res['trailer']['id']}"
            else:
                info['trailer'] = f"plugin://plugin.video.dailymotion_com/?url={res['trailer']['id']}&mode=playVideo"
        except (KeyError, TypeError):
            pass

        dub = True if mal_dub and mal_dub.get(str(mal_id)) else False

        image = res['coverImage']['extraLarge']
        base = {
            "name": title,
            "url": f'animes/{mal_id}/',
            "image": image,
            "poster": image,
            'fanart': kodi_meta['fanart'] if kodi_meta.get('fanart') else image,
            "banner": res.get('bannerImage'),
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
        import datetime

        mal_id = res['media']['idMal']
        if not mal_id:
            return

        airingAt = datetime.datetime.fromtimestamp(res['airingAt'])
        airingAt_day = airingAt.strftime('%A')
        airingAt_time = airingAt.strftime('%I:%M %p')
        airing_status = 'airing' if res['airingAt'] > ts else 'aired'
        rank = None
        rankings = res['media']['rankings']
        if rankings and rankings[-1]['season']:
            rank = rankings[-1]['rank']
        genres = res['media']['genres']
        if genres:
            genres = ' | '.join(genres[:3])
        else:
            genres = 'Genres Not Found'
        title = res['media']['title'][self.title_lang]
        if not title:
            title = res['media']['title']['userPreferred']

        base = {
            'release_title': title,
            'poster': res['media']['coverImage']['extraLarge'],
            'ep_title': '{} {} {}'.format(res['episode'], airing_status, airingAt_day),
            'ep_airingAt': airingAt_time,
            'airing_day': airingAt_day,
            'averageScore': res['media']['averageScore'],
            'rank': rank,
            'plot': res['media']['description'].replace('<br><br>', '[CR]').replace('<br>', '').replace('<i>', '[I]').replace('</i>', '[/I]') if res['media']['description'] else res['media']['description'],
            'genres': genres,
            'id': res['media']['idMal']
        }

        return base

    def database_update_show(self, res):
        mal_id = res.get('idMal')

        if not mal_id:
            return

        try:
            start_date = res['startDate']
            start_date = '{}-{:02}-{:02}'.format(start_date['year'], start_date['month'], start_date['day'])
        except TypeError:
            start_date = None

        try:
            duration = res['duration'] * 60
        except (KeyError, TypeError):
            duration = 0

        title_userPreferred = res['title'][self.title_lang] or res['title']['romaji']

        name = res['title']['romaji']
        ename = res['title']['english']
        titles = f"({name})|({ename})"

        if desc := res.get('description'):
            desc = desc.replace('<i>', '[I]').replace('</i>', '[/I]')
            desc = desc.replace('<b>', '[B]').replace('</b>', '[/B]')
            desc = desc.replace('<br>', '[CR]')
            desc = desc.replace('\n', '')

        kodi_meta = {
            'name': name,
            'ename': ename,
            'title_userPreferred': title_userPreferred,
            'start_date': start_date,
            'query': titles,
            'episodes': res['episodes'],
            'poster': res['coverImage']['extraLarge'],
            'status': res.get('status'),
            'format': res.get('format', ''),
            'plot': desc,
            'duration': duration,
            'genre': res.get('genres'),
            'country': [res.get('countryOfOrigin', '')],
        }

        try:
            start_date = res.get('startDate')
            kodi_meta['premiered'] = '{}-{:02}-{:02}'.format(start_date['year'], start_date['month'], start_date['day'])
            kodi_meta['year'] = start_date['year']
        except TypeError:
            pass

        try:
            cast = []
            for i, x in enumerate(res['characters']['edges']):
                role = x['node']['name']['userPreferred']
                actor = x['voiceActors'][0]['name']['userPreferred']
                actor_hs = x['voiceActors'][0]['image']['large']
                cast.append({'name': actor, 'role': role, 'thumbnail': actor_hs, 'index': i})
            kodi_meta['cast'] = cast
        except IndexError:
            pass

        kodi_meta['studio'] = [x['node'].get('name') for x in res['studios']['edges']]

        try:
            kodi_meta['rating'] = {'score': res.get('averageScore') / 10.0}
            if res.get('stats') and res['stats'].get('scoreDistribution'):
                total_votes = sum([score['amount'] for score in res['stats']['scoreDistribution']])
                kodi_meta['rating']['votes'] = total_votes
        except TypeError:
            pass

        try:
            if res['trailer']['site'] == 'youtube':
                kodi_meta['trailer'] = f"plugin://plugin.video.youtube/play/?video_id={res['trailer']['id']}"
            else:
                kodi_meta['trailer'] = f"plugin://plugin.video.dailymotion_com/?url={res['trailer']['id']}&mode=playVideo"
        except (KeyError, TypeError):
            pass

        database.update_show(mal_id, pickle.dumps(kodi_meta))

    def get_genres(self, page, format):
        query = '''
        query {
            genres: GenreCollection,
            tags: MediaTagCollection {
                name
                isAdult
            }
        }
        '''

        response = client.post(self._BASE_URL, json_data={'query': query})
        results = response.json()
        if not results:
            # genres_list = ['Action', 'Adventure', 'Comedy', 'Drama', 'Ecchi', 'Fantasy', 'Hentai', "Horror", 'Mahou Shoujo', 'Mecha', 'Music', 'Mystery', 'Psychological', 'Romance', 'Sci-Fi', 'Slice of Life', 'Sports', 'Supernatural', 'Thriller']
            genres_list = ['error']
        else:
            genres_list = results['data']['genres']
        # if 'Hentai' in genres_list:
        #     genres_list.remove('Hentai')
        try:
            tags_list = [x['name'] for x in results['data']['tags'] if not x['isAdult']]
        except KeyError:
            tags_list = []
        multiselect = control.multiselect_dialog(control.lang(30940), genres_list + tags_list, preselect=[])
        if not multiselect:
            return []
        genre_display_list = []
        tag_display_list = []
        for selection in multiselect:
            if selection < len(genres_list):
                genre_display_list.append(genres_list[selection])
            else:
                tag_display_list.append(tags_list[selection - len(genres_list)])
        return self.genres_payload(genre_display_list, tag_display_list, page, format)

    def genres_payload(self, genre_list, tag_list, page, format, prefix=None):
        query = '''
        query (
            $page: Int=1,
            $perpage: Int=20,
            $type: MediaType,
            $isAdult: Boolean = false,
            $format: [MediaFormat],
            $countryOfOrigin: CountryCode,
            $season: MediaSeason,
            $status: MediaStatus,
            $genre_in: [String],
            $tag_in: [String],
            $sort: [MediaSort] = [POPULARITY_DESC]
        ) {
            Page (page: $page, perPage: $perpage) {
                pageInfo {
                    hasNextPage
                }
                ANIME: media (
                    format_in: $format,
                    type: $type,
                    genre_in: $genre_in,
                    tag_in: $tag_in,
                    season: $season,
                    status: $status,
                    isAdult: $isAdult,
                    countryOfOrigin: $countryOfOrigin,
                    sort: $sort
                ) {
                    id
                    idMal
                    title {
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
                    description
                    synonyms
                    format
                    episodes
                    status
                    genres
                    duration
                    isAdult
                    countryOfOrigin
                    averageScore
                    stats {
                        scoreDistribution {
                            score
                            amount
                        }
                    }
                    trailer {
                        id
                        site
                    }
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
                }
            }
        }
        '''

        if not isinstance(genre_list, list):
            genre_list = ast.literal_eval(genre_list)
        if not isinstance(tag_list, list):
            tag_list = ast.literal_eval(tag_list)

        variables = {
            'page': page,
            'perPage': self.perpage,
            'type': "ANIME",
            'genre_in': genre_list if genre_list else None,
            'tag_in': tag_list if tag_list else None,
            'isAdult': 'Hentai' in genre_list,
            'sort': "POPULARITY_DESC"
        }

        if format:
            variables['format'] = format

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

        if format:
            variables['format'] = format

        try:
            from resources.lib import Main
            prefix = Main.plugin_url.split('/', 1)[0]
            base_plugin_url = f"{prefix}/{genre_list}/{tag_list}?page=%d"
        except Exception:
            base_plugin_url = f"genres/{genre_list}/{tag_list}?page=%d"

        return self.process_genre_view(query, variables, base_plugin_url, page)

    def process_genre_view(self, query, variables, base_plugin_url, page):
        response = client.post(self._BASE_URL, json_data={'query': query, 'variables': variables})
        results = response.json()
        anime_res = results['data']['Page']['ANIME']
        hasNextPage = results['data']['Page']['pageInfo']['hasNextPage']

        genre_filter = variables.get('genre_in')
        if genre_filter and isinstance(genre_filter, (list, tuple)) and len(genre_filter) > 1:
            genre_set = set(genre_filter)
            anime_res = [a for a in anime_res if genre_set.issubset(set(a.get('genres', [])))]

        if control.getBool('general.malposters'):
            try:
                for anime in anime_res:
                    anilist_id = anime['id']
                    mal_mapping = database.get_mappings(anilist_id, 'anilist_id')
                    if mal_mapping and 'mal_picture' in mal_mapping:
                        mal_picture = mal_mapping['mal_picture']
                        mal_picture_url = mal_picture.rsplit('.', 1)[0] + 'l.' + mal_picture.rsplit('.', 1)[1]
                        mal_picture_url = 'https://cdn.myanimelist.net/images/anime/' + mal_picture_url
                        anime['coverImage']['extraLarge'] = mal_picture_url
            except Exception:
                pass

        mapfunc = partial(self.base_anilist_view, completed=self.open_completed())
        get_meta.collect_meta(anime_res)
        all_results = list(map(mapfunc, anime_res))
        all_results += self.handle_paging(hasNextPage, base_plugin_url, page)
        return all_results

    def update_genre_settings(self):
        query = '''
        query {
            genres: GenreCollection,
            tags: MediaTagCollection {
                name
                isAdult
            }
        }
        '''

        response = client.post(self._BASE_URL, json_data={'query': query})
        results = response.json()
        if not results:
            genres_list = ['Action', 'Adventure', 'Comedy', 'Drama', 'Ecchi', 'Fantasy', 'Hentai', "Horror", 'Mahou Shoujo', 'Mecha', 'Music', 'Mystery', 'Psychological', 'Romance', 'Sci-Fi', 'Slice of Life', 'Sports', 'Supernatural', 'Thriller']
        else:
            genres_list = results['data']['genres']

        try:
            tags_list = [x['name'] for x in results['data']['tags'] if not x['isAdult']]
        except KeyError:
            tags_list = []

        multiselect = control.multiselect_dialog(control.lang(30940), genres_list + tags_list, preselect=[])
        if not multiselect:
            return [], []

        selected_genres_anilist = []
        selected_tags = []
        selected_genres_mal = []

        for selection in multiselect:
            if selection < len(genres_list):
                selected_genre = genres_list[selection]
                selected_genres_anilist.append(selected_genre)
            else:
                selected_tag = tags_list[selection - len(genres_list)]
                selected_tags.append(selected_tag)

        return selected_genres_mal, selected_genres_anilist, selected_tags

    @staticmethod
    def _safe_get_title(media: dict, pref_lang: str) -> str:
        title_obj = (media or {}).get("title") or {}
        return title_obj.get(pref_lang) or title_obj.get("romaji") or title_obj.get("english") or ""

    def _anilist_fetch_media(self, anilist_id: int) -> dict | None:
        """Fetch AniList Media once with in-memory cache."""
        if anilist_id in self._ANILIST_DETAILS_CACHE:
            return self._ANILIST_DETAILS_CACHE[anilist_id]
        try:
            res = self.get_anime_details(anilist_id)
            if res and "data" in res and "Media" in res["data"]:
                media = res["data"]["Media"]
                self._ANILIST_DETAILS_CACHE[anilist_id] = media
                return media
        except Exception:
            return None
        return None

    def _anilist_fetch_media_batch(self, ids: list[int]) -> dict[int, dict]:
        """Fetch multiple AniList Media in a single GraphQL request to avoid rate limits."""
        if not ids:
            return {}
        # De-duplicate while preserving order
        ids = list(dict.fromkeys([i for i in ids if isinstance(i, int)]))

        query = '''
        query ($ids: [Int]) {
          Page(perPage: 50) {
            media(id_in: $ids, type: ANIME) {
              id
              idMal
              title { romaji english native }
              coverImage { extraLarge large medium color }
              bannerImage
              startDate { year month day }
              endDate { year month day }
              description(asHtml: false)
              synonyms
              format
              episodes
              status
              genres
              duration
              countryOfOrigin
              averageScore
              meanScore
              popularity
              season
              seasonYear
              studios(isMain: true) { nodes { name } }
              nextAiringEpisode { episode airingAt }
              trailer { id site thumbnail }
              stats { scoreDistribution { score amount } }
              characters(perPage: 25, sort: ROLE) {
                edges {
                  role
                  node { id name { userPreferred full native } image { large medium } }
                  voiceActors(language: JAPANESE) {
                    id
                    name { userPreferred }
                    image { large }
                  }
                }
              }
            }
          }
        }
        '''
        variables = {"ids": ids}
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Kodi-Otaku/1.0"
        }
        payload = {'query': query, 'variables': variables}

        for attempt in range(3):
            try:
                resp = client.request(
                    self._BASE_URL,
                    post=payload,
                    jpost=True,
                    headers=headers,
                    timeout=20
                )
            except TypeError:
                resp = client.request(self._BASE_URL, post=payload, jpost=True)
            except Exception as e:
                control.log(f"[AniList batch] request error: {e}", "error")
                resp = None

            if resp:
                try:
                    data = json.loads(resp) if isinstance(resp, str) else resp
                    media_list = (((data.get("data") or {}).get("Page") or {}).get("media")) or []
                    out: dict[int, dict] = {}
                    for m in media_list:
                        # ensure characters.edges exists
                        if "characters" not in m or not isinstance(m["characters"], dict):
                            m["characters"] = {"edges": []}
                        elif "edges" not in m["characters"] or not isinstance(m["characters"]["edges"], list):
                            m["characters"]["edges"] = []
                        # transform studios.nodes to studios.edges
                        if "studios" in m and isinstance(m["studios"], dict):
                            nodes = m["studios"].get("nodes", [])
                            if isinstance(nodes, list):
                                m["studios"]["edges"] = [{"node": node} for node in nodes]
                        out[m.get("id")] = m
                    return out
                except Exception as e:
                    control.log(f"[AniList batch] decode error: {e}", "error")
            time.sleep(0.6 * (attempt + 1))

        control.log("[AniList batch] empty response after retries", "warning")
        return {}

    def _render_paired_anilist(self, pairs: list[tuple[dict, dict]]) -> list[dict]:
        """Render list of (media, episode_dict) using existing AniList pipeline and inject badge."""
        items = [m for (m, _) in pairs]
        if not items:
            return []
        get_meta.collect_meta(items)
        mapfunc = partial(self.base_anilist_view, completed=self.open_completed())

        results: list[dict] = []
        filtered_pairs: list[tuple[dict, dict]] = []

        for media, ep_obj in pairs:
            r = mapfunc(media)
            if r:
                tover = media.get("title_override")
                if tover:
                    try:
                        r["info"]["title"] = tover
                    except Exception:
                        pass
                results.append(r)
                filtered_pairs.append((media, ep_obj))

        # inject badge using exact paired episode to avoid misalignment
        from resources.lib.endpoints import animeschedule as AS
        for r, (_, ep) in zip(results, filtered_pairs):
            badge = AS.as_format_episode_badge(ep)
            plot = r.get("info", {}).get("plot") or ""
            r["info"]["plot"] = f"{badge}\n{plot}" if plot else f"{badge}"

        return results

    def get_recently_aired(self, page=1, format=None, prefix=None):
        """
        Recently aired for the last 7 days from AnimeSchedule,
        sorted latest-first, 24 items per page, excludes Donghua, using AnimeSchedule data only.
        """
        from resources.lib.endpoints import animeschedule as AS

        # 1) Fetch and sort episodes (latest first)
        episodes = AS.get_recently_aired_raw(
            exclude_donghua=True,
            tz=None,
            air="raw"
        )
        if not episodes:
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

    def get_recently_aired_res(self, variables):
        from resources.lib.endpoints import animeschedule as AS

        episodes = AS.get_recently_aired_raw(exclude_donghua=True, tz=None, air="raw")
        if not episodes:
            return []

        page = variables.get("page", 1)
        start_idx = (page - 1) * 24
        end_idx = page * 24
        page_episodes = episodes[start_idx:end_idx]

        routes = [e.get("route") for e in page_episodes if e.get("route")]
        route_map = AS.as_get_anime_by_routes_batch(routes, timeout_per=8, max_workers=8)

        with_ids: list[dict] = []
        for e in page_episodes:
            r = e.get("route")
            det = route_map.get(r) if r else None
            aid = det.get("anilistId") if det else None
            if not aid and det and det.get("malId"):
                mapping = database.get_mappings(det["malId"], "mal_id") or {}
                aid = mapping.get("anilist_id")
            if aid:
                e["anilistId"] = aid
                with_ids.append(e)

        if not with_ids:
            out = []
            if end_idx < len(episodes):
                out += self.handle_paging(True, "recently_aired?page=%d", page)
            return out

        # Batch first, then fallback
        ids = [e["anilistId"] for e in with_ids if isinstance(e.get("anilistId"), int)]
        id_to_media = self._anilist_fetch_media_batch(ids) or {}

        missing = [aid for aid in ids if aid not in id_to_media]
        if missing:
            with ThreadPoolExecutor(max_workers=4) as ex:
                futs = {ex.submit(self._anilist_fetch_media, aid): aid for aid in missing}
                for f in futs:
                    try:
                        media = f.result()
                        if media:
                            id_to_media[futs[f]] = media
                    except Exception:
                        pass

        pairs: list[tuple[dict, dict]] = []
        for e in with_ids:
            media = id_to_media.get(e.get("anilistId"))
            if not media:
                continue
            ep_num = e.get("episodeNumber", 1)
            title = self._safe_get_title(media, self.title_lang)
            media = dict(media)
            media["title_override"] = f"{title} - Episode {ep_num}"
            pairs.append((media, e))

        results = self._render_paired_anilist(pairs)

        if end_idx < len(episodes):
            results += self.handle_paging(True, "recently_aired?page=%d", page)

        return results

    def process_recently_aired_view(self, query, variables, base_plugin_url, page):
        from resources.lib.endpoints import animeschedule as AS

        episodes = AS.get_recently_aired_raw(exclude_donghua=True, tz=None, air="raw")
        if not episodes:
            return []

        start_idx = (page - 1) * 24
        end_idx = page * 24
        page_episodes = episodes[start_idx:end_idx]

        routes = [e.get("route") for e in page_episodes if e.get("route")]
        route_map = AS.as_get_anime_by_routes_batch(routes, timeout_per=8, max_workers=8)

        with_ids: list[dict] = []
        for e in page_episodes:
            r = e.get("route")
            det = route_map.get(r) if r else None
            aid = det.get("anilistId") if det else None
            if not aid and det and det.get("malId"):
                mapping = database.get_mappings(det["malId"], "mal_id") or {}
                aid = mapping.get("anilist_id")
            if aid:
                e["anilistId"] = aid
                with_ids.append(e)

        if not with_ids:
            out = []
            if end_idx < len(episodes):
                out += self.handle_paging(True, "recently_aired?page=%d", page)
            return out

        # Batch first, then fallback
        ids = [e["anilistId"] for e in with_ids if isinstance(e.get("anilistId"), int)]
        id_to_media = self._anilist_fetch_media_batch(ids) or {}

        missing = [aid for aid in ids if aid not in id_to_media]
        if missing:
            with ThreadPoolExecutor(max_workers=4) as ex:
                futs = {ex.submit(self._anilist_fetch_media, aid): aid for aid in missing}
                for f in futs:
                    try:
                        media = f.result()
                        if media:
                            id_to_media[futs[f]] = media
                    except Exception:
                        pass

        pairs: list[tuple[dict, dict]] = []
        for e in with_ids:
            media = id_to_media.get(e.get("anilistId"))
            if not media:
                continue
            ep_num = e.get("episodeNumber", 1)
            title = self._safe_get_title(media, self.title_lang)
            media = dict(media)
            media["title_override"] = f"{title} - Episode {ep_num}"
            pairs.append((media, e))

        results = self._render_paired_anilist(pairs)

        if end_idx < len(episodes):
            results += self.handle_paging(True, "recently_aired?page=%d", page)

        return results

    def get_anime_details(self, anilist_id):
        """
        Fetch detailed anime information from AniList by ID.
        Returns a dict shaped like {"data": {"Media": {...}}} or None on error.
        Includes characters to satisfy downstream views.
        """
        query = '''
        query ($id: Int) {
            Media (id: $id, type: ANIME) {
                id
                idMal
                title {
                    romaji
                    english
                    native
                }
                coverImage {
                    extraLarge
                    large
                    medium
                    color
                }
                bannerImage
                startDate { year month day }
                endDate { year month day }
                description(asHtml: false)
                synonyms
                format
                episodes
                status
                genres
                duration
                countryOfOrigin
                averageScore
                meanScore
                popularity
                season
                seasonYear
                studios(isMain: true) { nodes { name } }
                nextAiringEpisode {
                    episode
                    airingAt
                }
                trailer {
                    id
                    site
                    thumbnail
                }
                stats {
                    scoreDistribution { score amount }
                }
                characters(perPage: 25, sort: ROLE) {
                    edges {
                        role
                        node {
                            id
                            name { userPreferred full native }
                            image { large medium }
                        }
                        voiceActors(language: JAPANESE) {
                            id
                            name { userPreferred }
                            image { large }
                        }
                    }
                }
            }
        }
        '''
        variables = {'id': anilist_id}
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Kodi-Otaku/1.0"
        }

        results = None
        for attempt in range(3):
            try:
                resp = client.request(
                    self._BASE_URL,
                    post={'query': query, 'variables': variables},
                    jpost=True,
                    headers=headers,
                    timeout=15
                )
            except TypeError:
                resp = client.request(self._BASE_URL, post={'query': query, 'variables': variables}, jpost=True)
            except Exception as e:
                control.log(f"[AniList get_anime_details] request error for id={anilist_id}: {e}", "error")
                resp = None

            if resp:
                try:
                    results = json.loads(resp) if isinstance(resp, str) else resp
                except Exception as e:
                    control.log(f"[AniList get_anime_details] JSON decode error for id={anilist_id}: {e}", "error")
                    results = None

                if results and "errors" not in results:
                    media = (results.get('data') or {}).get('Media')
                    if media:
                        if "characters" not in media or not isinstance(media["characters"], dict):
                            media["characters"] = {"edges": []}
                        elif "edges" not in media["characters"] or not isinstance(media["characters"]["edges"], list):
                            media["characters"]["edges"] = []

                        # transform studios.nodes to studios.edges
                        if "studios" in media and isinstance(media["studios"], dict):
                            nodes = media["studios"].get("nodes", [])
                            if isinstance(nodes, list):
                                media["studios"]["edges"] = [{"node": node} for node in nodes]

                        try:
                            if control.getBool('general.malposters') and media.get('coverImage'):
                                mapping = database.get_mappings(anilist_id, 'anilist_id') or {}
                                mal_picture = mapping.get('mal_picture')
                                if mal_picture and isinstance(mal_picture, str) and '.' in mal_picture:
                                    base, ext = mal_picture.rsplit('.', 1)
                                    mal_large = f"https://cdn.myanimelist.net/images/anime/{base}l.{ext}"
                                    media['coverImage']['extraLarge'] = mal_large
                        except Exception:
                            pass

                        return {"data": {"Media": media}}

            time.sleep(0.5 * (attempt + 1))

        control.log(f"[AniList get_anime_details] empty response for id={anilist_id}", "warning")
        return None