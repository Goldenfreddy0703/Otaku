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


class AniListBrowser(BrowserBase):
    _BASE_URL = "https://graphql.anilist.co"

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
        import datetime
        import time
        import itertools

        anilist_cache = self.get_cached_data()
        if anilist_cache:
            list_ = anilist_cache
        else:
            today = datetime.date.today()
            today_ts = int(time.mktime(today.timetuple()))
            weekStart = today_ts - 86400
            weekEnd = today_ts + (86400 * 6)
            variables = {
                'weekStart': weekStart,
                'weekEnd': weekEnd,
                'page': page
            }

            list_ = []

            for i in range(0, 4):
                popular = self.get_airing_calendar_res(variables, page)
                list_.append(popular)

                if not popular['pageInfo']['hasNextPage']:
                    break

                page += 1
                variables['page'] = page

            self.set_cached_data(anilist_cache)

        results = list(map(self.process_airing_view, list_))
        results = list(itertools.chain(*results))
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
            'type': "ANIME",
            'isAdult': False,
            'format': None,
            'search': query,
            'sort': "SEARCH_MATCH",
            'countryOfOrigin': None,
            'status': None,
            'genre_in': None,
            'tag_in': None,
            'year': None
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
        '''

        response = client.post(self._BASE_URL, json_data={'query': query, 'variables': variables})
        results = response.json()

        if "errors" in results.keys():
            return

        json_res = results.get('data', {}).get('Page')

        if control.getBool('general.malposters'):
            try:
                # Create a dictionary to track unique media items
                unique_media = {}
                for airing in json_res['airingSchedules']:
                    media_id = airing['media']['id']
                    # Only keep the most recent airing for each unique show
                    if media_id not in unique_media or airing['airingAt'] > unique_media[media_id]['airingAt']:
                        unique_media[media_id] = airing
                        anilist_id = media_id
                        mal_mapping = database.get_mappings(anilist_id, 'anilist_id')
                        if mal_mapping and 'mal_picture' in mal_mapping:
                            mal_picture = mal_mapping['mal_picture']
                            mal_picture_url = mal_picture.rsplit('.', 1)[0] + 'l.' + mal_picture.rsplit('.', 1)[1]
                            mal_picture_url = 'https://cdn.myanimelist.net/images/anime/' + mal_picture_url
                            airing['media']['coverImage']['extraLarge'] = mal_picture_url
                
                # Replace the airingSchedules with unique media items sorted by airing time
                json_res['airingSchedules'] = sorted(unique_media.values(), key=lambda x: x['airingAt'], reverse=True)
            except Exception:
                pass

        if json_res:
            # Remove duplicate media entries
            unique_media = {}
            for airing in json_res['airingSchedules']:
                media_id = airing['media']['id']
                if media_id not in unique_media or airing['airingAt'] > unique_media[media_id]['airingAt']:
                    unique_media[media_id] = airing
            
            # Sort by most recent airing time
            json_res['airingSchedules'] = sorted(unique_media.values(), key=lambda x: x['airingAt'], reverse=True)
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
            'country': [res.get('countryOfOrigin', '')]
        }

        if start_date:
            kodi_meta['premiered'] = start_date
            kodi_meta['year'] = int(start_date.split('-')[0])

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
            genres_list = ['Action', 'Adventure', 'Comedy', 'Drama', 'Ecchi', 'Fantasy', 'Hentai', "Horror", 'Mahou Shoujo', 'Mecha', 'Music', 'Mystery', 'Psychological', 'Romance', 'Sci-Fi', 'Slice of Life', 'Sports', 'Supernatural', 'Thriller']
        else:
            genres_list = results['data']['genres']

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

    def get_recently_aired_shows(self, page=1):
        import datetime
        import time
        
        # Get current timestamp
        current_time = int(time.time())
        
        # Calculate time range for recent episodes (last 7 days)
        seven_days_ago = current_time - (7 * 24 * 60 * 60)
        
        # Fetch more items per page to account for filtering
        # We'll fetch 100 items and filter down to 24 quality shows
        variables = {
            'page': page,
            'perPage': 100,  # Fetch more to account for filtering
            'airingAt_greater': seven_days_ago,
            'airingAt_lesser': current_time,
            'sort': 'TIME_DESC'
        }
        
        # Fetch the requested page
        page_result = self.get_recently_aired_shows_res(variables)
        
        # Pass the page number to process_recently_aired_view
        # It will handle filtering and limiting to 24 items
        return self.process_recently_aired_view(page_result, page)

    def get_recently_aired_shows_res(self, variables):
        query = '''
        query (
            $page: Int=1,
            $perPage: Int=100,
            $airingAt_greater: Int,
            $airingAt_lesser: Int,
            $sort: [AiringSort] = [TIME_DESC]
        ) {
            Page (page: $page, perPage: $perPage) {
                pageInfo {
                    hasNextPage
                    total
                }
                airingSchedules (
                    airingAt_greater: $airingAt_greater,
                    airingAt_lesser: $airingAt_lesser,
                    sort: $sort
                ) {
                    id
                    episode
                    airingAt
                    media {
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
                        popularity
                        nextAiringEpisode {
                            episode
                            airingAt
                        }
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
        }
        '''

        result = client.request(self._BASE_URL, post={'query': query, 'variables': variables}, jpost=True)
        results = json.loads(result)

        if "errors" in results.keys():
            return

        json_res = results.get('data', {}).get('Page')

        if control.getBool('general.malposters'):
            try:
                # Create a dictionary to track unique media items
                unique_media = {}
                for airing in json_res['airingSchedules']:
                    media_id = airing['media']['id']
                    # Only keep the most recent airing for each unique show
                    if media_id not in unique_media or airing['airingAt'] > unique_media[media_id]['airingAt']:
                        unique_media[media_id] = airing
                        anilist_id = media_id
                        mal_mapping = database.get_mappings(anilist_id, 'anilist_id')
                        if mal_mapping and 'mal_picture' in mal_mapping:
                            mal_picture = mal_mapping['mal_picture']
                            mal_picture_url = mal_picture.rsplit('.', 1)[0] + 'l.' + mal_picture.rsplit('.', 1)[1]
                            mal_picture_url = 'https://cdn.myanimelist.net/images/anime/' + mal_picture_url
                            airing['media']['coverImage']['extraLarge'] = mal_picture_url
                
                # Replace the airingSchedules with unique media items sorted by airing time
                json_res['airingSchedules'] = sorted(unique_media.values(), key=lambda x: x['airingAt'], reverse=True)
            except Exception:
                pass

        if json_res:
            # Remove duplicate media entries
            unique_media = {}
            for airing in json_res['airingSchedules']:
                media_id = airing['media']['id']
                if media_id not in unique_media or airing['airingAt'] > unique_media[media_id]['airingAt']:
                    unique_media[media_id] = airing
            
            # Sort by most recent airing time
            json_res['airingSchedules'] = sorted(unique_media.values(), key=lambda x: x['airingAt'], reverse=True)
            return json_res

    def process_recently_aired_view(self, json_res, page, target_count=24):
        if not json_res:
            return []
        
        hasNextPage = json_res['pageInfo']['hasNextPage']
        get_meta.collect_meta([x['media'] for x in json_res['airingSchedules']])
        mapfunc = partial(self.base_anilist_view, completed=self.open_completed())
        
        # Filter to only include TV shows and remove duplicates
        seen_ids = set()
        unique_results = []
        
        for schedule in json_res['airingSchedules']:
            media = schedule['media']
            
            # Apply quality filters (OR condition: either good score OR popular)
            average_score = media.get('averageScore', 0) or 0
            popularity = media.get('popularity', 0) or 0
            
            # Skip if both are below thresholds
            if average_score < 65 and popularity < 10000:
                continue
            
            if media['id'] not in seen_ids and media.get('format') in ['TV', 'TV_SHORT', None]:
                result = mapfunc(media)
                if result:
                    # Add episode info to the title if available
                    if 'episode' in schedule and schedule['episode']:
                        result['info']['title'] = f"{result['info']['title']} - Episode {schedule['episode']}"
                    unique_results.append(result)
                    seen_ids.add(media['id'])
                    
                    # Stop if we've reached the target count (24 items per page)
                    if len(unique_results) >= target_count:
                        # If we hit the limit, there might be more items
                        hasNextPage = True
                        break
        
        # Always add pagination
        unique_results += self.handle_paging(hasNextPage, "recently_aired_shows?page=%d", page)
        
        return unique_results