import ast
import datetime
import itertools
import json
import pickle
import random
import time
from functools import partial

import six
import copy

from resources.lib.ui import client, control, database, get_meta, utils
from resources.lib.ui.divide_flavors import div_flavor


class AniListBrowser():
    _URL = "https://graphql.anilist.co"

    def __init__(self, title_key=None):
        if title_key:
            self._TITLE_LANG = self._title_lang(title_key)
        else:
            self._TITLE_LANG = "userPreferred"
        self.format_in_type = ''
        filterEnable = control.getSetting('contentformat.bool') == "true"
        if filterEnable:
            formats = ['TV', 'MOVIE', 'TV_SHORT', 'SPECIAL', 'OVA', 'ONA', 'MUSIC']
            self.format_in_type = formats[int(control.getSetting('contentformat.menu'))]

        elif title_key:
            self._TITLE_LANG = self._title_lang(title_key)
        else:
            self._TITLE_LANG = "userPreferred"
        self.countryOfOrigin_type = ''
        filterEnable = control.getSetting('contentorigin.bool') == "true"
        if filterEnable:
            countries = ['JP', 'KR', 'CN', 'TW']
            self.countryOfOrigin_type = countries[int(control.getSetting('contentorigin.menu'))]

        elif title_key:
            self._TITLE_LANG = self._title_lang(title_key)
        else:
            self._TITLE_LANG = "userPreferred"
        self.licensedBy_type = ''
        filterEnable = control.getSetting('licensedBy.bool') == "true"
        if filterEnable:
            selected_site = control.getSetting('licensedBy.menu')
            self.licensedBy_type = selected_site

        elif title_key:
            self._TITLE_LANG = self._title_lang(title_key)
        else:
            self._TITLE_LANG = "userPreferred"
        self.perPage_type = 20
        filterEnable = control.getSetting('perpage.bool') == 'true'
        if filterEnable:
            self.perPage_type = int(control.getSetting('perpage.menu'))

    def _title_lang(self, title_key):
        title_lang = {
            "40370": "userPreferred",
            "Romaji (Shingeki no Kyojin)": "userPreferred",
            "40371": "english",
            "English (Attack on Titan)": "english"
        }

        return title_lang[title_key]

    def _handle_paging(self, hasNextPage, base_url, page):
        if not hasNextPage:
            return []

        next_page = page + 1
        name = "Next Page (%d)" % (next_page)
        return [utils.allocate_item(name, base_url % next_page, True, 'next.png', fanart='next.png')]

    def get_season_year(self, period='current'):
        date = datetime.datetime.today()
        year = date.year
        month = date.month
        seasons = ['WINTER', 'SPRING', 'SUMMER', 'FALL']
        if period == "next":
            season = seasons[int((month - 1) / 3 + 1) % 4]
            if season == 'WINTER':
                year += 1
        elif period == "last":
            season = seasons[int((month - 1) / 3 - 1) % 4] if month > 3 else 'FALL'
            if season == 'FALL':
                year -= 1
        else:
            season = seasons[int((month - 1) / 3)]
        return [season, year]

    def get_airing_calendar(self, page=1, format_in=''):
        dbargs = {"otaku_reload": control.getGlobalProp("calendarRefresh")}
        control.setGlobalProp("calendarRefresh", False)

        airing = database.get(self._get_airing_calendar, 12, page, self.format_in_type, **dbargs)
        return airing

    def _get_airing_calendar(self, page=1, format_in=''):
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
            popular = self.get_airing_calenda_res(variables, page)
            list_.append(popular)

            if not popular['pageInfo']['hasNextPage']:
                break

            page += 1
            variables['page'] = page

        results = list(map(self._process_airing_view, list_))
        results = list(itertools.chain(*results))
        return results

    def get_airing_anime(self, page=1, format_in=''):
        season, year = self.get_season_year('Aired')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'status': "RELEASING",
            'sort': "POPULARITY_DESC",
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        airing = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(airing, "anilist_airing_anime/%d", page)

    def get_trending_last_year_trending_trending(self, page=1, format_in=''):
        season, year = self.get_season_year('')
        variables = {
            'page': page,
            'type': "ANIME",
            'year': str(year - 1) + '%',
            'sort': "TRENDING_DESC",
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        trending = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(trending, "anilist_trending_last_year_trending_trending/%d", page)

    def get_trending_this_year_trending_trending(self, page=1, format_in=''):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "TRENDING_DESC",
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        trending = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(trending, "anilist_trending_this_year_trending_trending/%d", page)

    def get_trending_last_season_trending(self, page=1, format_in=''):
        season, year = self.get_season_year('last')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "TRENDING_DESC",
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        trending = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(trending, "anilist_trending_last_season_trending/%d", page)

    def get_trending_this_season_trending(self, page=1, format_in=''):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "TRENDING_DESC",
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        trending = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(trending, "anilist_trending_this_season_trending/%d", page)

    def get_all_time_trending_trending(self, page=1, format_in=''):
        season, year = self.get_season_year('time')
        variables = {
            'page': page,
            'type': "ANIME",
            'sort': "TRENDING_DESC",
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        trending = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(trending, "anilist_all_time_trending_trending/%d", page)

    def get_popular_last_year_popular(self, page=1, format_in=''):
        season, year = self.get_season_year('')
        variables = {
            'page': page,
            'type': "ANIME",
            'year': str(year - 1) + '%',
            'sort': "POPULARITY_DESC",
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        popular = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(popular, "anilist_popular_last_year_popular/%d", page)

    def get_popular_this_year_popular(self, page=1, format_in=''):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "POPULARITY_DESC",
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        popular = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(popular, "anilist_popular_this_year_popular/%d", page)

    def get_popular_last_season_popular(self, page=1, format_in=''):
        season, year = self.get_season_year('last')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "POPULARITY_DESC",
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        popular = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(popular, "anilist_popular_last_season_popular/%d", page)

    def get_popular_this_season_popular(self, page=1, format_in=''):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "POPULARITY_DESC",
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        popular = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(popular, "anilist_popular_this_season_popular/%d", page)

    def get_all_time_popular_popular(self, page=1, format_in=''):
        season, year = self.get_season_year('time')
        variables = {
            'page': page,
            'type': "ANIME",
            'sort': "POPULARITY_DESC",
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        popular = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(popular, "anilist_all_time_popular_popular/%d", page)

    def get_voted_last_year_voted(self, page=1, format_in=''):
        season, year = self.get_season_year('')
        variables = {
            'page': page,
            'type': "ANIME",
            'year': str(year - 1) + '%',
            'sort': "FAVOURITES_DESC",
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        voted = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(voted, "anilist_voted_last_year_voted/%d", page)

    def get_voted_this_year_voted(self, page=1, format_in=''):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "FAVOURITES_DESC",
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        voted = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(voted, "anilist_voted_this_year_voted/%d", page)

    def get_voted_last_season_voted(self, page=1, format_in=''):
        season, year = self.get_season_year('last')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "FAVOURITES_DESC",
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        voted = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(voted, "anilist_voted_last_season_voted/%d", page)

    def get_voted_this_season_voted(self, page=1, format_in=''):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "FAVOURITES_DESC",
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        voted = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(voted, "anilist_voted_this_season_voted/%d", page)

    def get_all_time_voted_voted(self, page=1, format_in=''):
        season, year = self.get_season_year('time')
        variables = {
            'page': page,
            'type': "ANIME",
            'sort': "FAVOURITES_DESC",
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        voted = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(voted, "anilist_all_time_voted_voted /%d", page)

    def get_completed_last_year_completed(self, page=1, format_in=''):
        season, year = self.get_season_year('')
        variables = {
            'page': page,
            'type': "ANIME",
            'year': str(year - 1) + '%',
            'status': "FINISHED",
            'sort': "POPULARITY_DESC",
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        completed = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(completed, "anilist_completed_last_year_completed/%d", page)

    def get_completed_this_year_completed(self, page=1, format_in=''):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'type': "ANIME",
            'year': str(year) + '%',
            'status': "FINISHED",
            'sort': "POPULARITY_DESC",
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        completed = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(completed, "anilist_completed_this_year_completed/%d", page)

    def get_completed_last_season_completed(self, page=1, format_in=''):
        season, year = self.get_season_year('last')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'status': "FINISHED",
            'sort': "POPULARITY_DESC",
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        completed = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(completed, "anilist_completed_last_season_completed/%d", page)

    def get_completed_this_season_completed(self, page=1, format_in=''):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'status': "FINISHED",
            'sort': "POPULARITY_DESC",
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        completed = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(completed, "anilist_completed_this_season_completed/%d", page)

    def get_upcoming_last_year_upcoming(self, page=1, format_in=''):
        season, year = self.get_season_year('')
        variables = {
            'page': page,
            'type': "ANIME",
            'year': str(year - 1) + '%',
            'sort': "POPULARITY_DESC",
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        upcoming = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(upcoming, "anilist_upcoming_last_year_upcoming/%d", page)

    def get_upcoming_this_year_upcoming(self, page=1, format_in=''):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'type': "ANIME",
            'year': str(year) + '%',
            'sort': "POPULARITY_DESC",
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        upcoming = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(upcoming, "anilist_upcoming_this_year_upcoming/%d", page)

    def get_upcoming_next_year_upcoming(self, page=1, format_in=''):
        season, year = self.get_season_year('next')
        variables = {
            'page': page,
            'type': "ANIME",
            'year': str(year + 1) + '%',
            'sort': "POPULARITY_DESC",
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        upcoming = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(upcoming, "anilist_upcoming_next_year_upcoming/%d", page)

    def get_upcoming_last_season_upcoming(self, page=1, format_in=''):
        season, year = self.get_season_year('last')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "POPULARITY_DESC",
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        upcoming = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(upcoming, "anilist_upcoming_last_season_upcoming/%d", page)

    def get_upcoming_this_season_upcoming(self, page=1, format_in=''):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "POPULARITY_DESC",
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        upcoming = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(upcoming, "anilist_upcoming_this_season_upcoming/%d", page)

    def get_upcoming_next_season_upcoming(self, page=1, format_in=''):
        season, year = self.get_season_year('next')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "POPULARITY_DESC",
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        upcoming = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(upcoming, "anilist_upcoming_next_season_upcoming/%d", page)

    def get_top_100_anime(self, page=1, format_in=''):
        season, year = self.get_season_year('100')
        variables = {
            'page': page,
            'type': "ANIME",
            'sort': "SCORE_DESC",
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        top_100_anime = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(top_100_anime, "anilist_top_100_anime/%d", page)

    def get_search(self, query, page=1):
        variables = {
            'page': page,
            'search': query,
            'sort': "SEARCH_MATCH",
            'type': "ANIME",
            'isAdult': control.getSetting('search.adult') == "true"
        }

        search = database.get(self.get_search_res, 0.125, variables, page)
        return self._process_anilist_view(search, "search/%s/%%d" % query, page)

    def get_airing_calendar_movie(self, page=1, format_in=''):
        dbargs = {"otaku_reload": control.getGlobalProp("calendarRefresh")}
        control.setGlobalProp("calendarRefresh", False)

        airing = database.get(self._get_airing_calendar, 12, page, self.format_in_type, **dbargs)
        return airing

    def _get_airing_calendar_movie(self, page=1, format_in=''):
        today = datetime.date.today()
        today_ts = int(time.mktime(today.timetuple()))
        weekStart = today_ts - 86400
        weekEnd = today_ts + (86400 * 6)

        variables = {
            'weekStart': weekStart,
            'weekEnd': weekEnd,
            'page': page,
            'format': "MOVIE"
        }

        list_ = []

        for i in range(0, 4):
            popular = self.get_airing_calenda_res(variables, page)
            list_.append(popular)

            if not popular['pageInfo']['hasNextPage']:
                break

            page += 1
            variables['page'] = page

        results = list(map(self._process_airing_view, list_))
        results = list(itertools.chain(*results))
        return results

    def get_airing_anime_movie(self, page=1, format_in=''):
        season, year = self.get_season_year('Aired')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'status': "RELEASING",
            'sort': "POPULARITY_DESC",
            'format': "MOVIE"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        airing = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(airing, "anilist_airing_anime_movie/%d", page)

    def get_trending_last_year_trending_trending_movie(self, page=1, format_in=''):
        season, year = self.get_season_year('')
        variables = {
            'page': page,
            'type': "ANIME",
            'year': str(year - 1) + '%',
            'sort': "TRENDING_DESC",
            'format': "MOVIE"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        trending = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(trending, "anilist_trending_last_year_trending_trending_movie/%d", page)

    def get_trending_this_year_trending_trending_movie(self, page=1, format_in=''):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "TRENDING_DESC",
            'format': "MOVIE"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        trending = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(trending, "anilist_trending_this_year_trending_trending_movie/%d", page)

    def get_trending_last_season_trending_movie(self, page=1, format_in=''):
        season, year = self.get_season_year('last')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "TRENDING_DESC",
            'format': "MOVIE"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        trending = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(trending, "anilist_trending_last_season_trending_movie/%d", page)

    def get_trending_this_season_trending_movie(self, page=1, format_in=''):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "TRENDING_DESC",
            'format': "MOVIE"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        trending = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(trending, "anilist_trending_this_season_trending_movie/%d", page)

    def get_all_time_trending_trending_movie(self, page=1, format_in=''):
        season, year = self.get_season_year('time')
        variables = {
            'page': page,
            'type': "ANIME",
            'sort': "TRENDING_DESC",
            'format': "MOVIE"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        trending = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(trending, "anilist_all_time_trending_trending_movie/%d", page)

    def get_popular_last_year_popular_movie(self, page=1, format_in=''):
        season, year = self.get_season_year('')
        variables = {
            'page': page,
            'type': "ANIME",
            'year': str(year - 1) + '%',
            'sort': "POPULARITY_DESC",
            'format': "MOVIE"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        popular = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(popular, "anilist_popular_last_year_popular_movie/%d", page)

    def get_popular_this_year_popular_movie(self, page=1, format_in=''):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "POPULARITY_DESC",
            'format': "MOVIE"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        popular = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(popular, "anilist_popular_this_year_popular_movie/%d", page)

    def get_popular_last_season_popular_movie(self, page=1, format_in=''):
        season, year = self.get_season_year('last')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "POPULARITY_DESC",
            'format': "MOVIE"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        popular = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(popular, "anilist_popular_last_season_popular_movie/%d", page)

    def get_popular_this_season_popular_movie(self, page=1, format_in=''):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "POPULARITY_DESC",
            'format': "MOVIE"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        popular = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(popular, "anilist_popular_this_season_popular_movie/%d", page)

    def get_all_time_popular_popular_movie(self, page=1, format_in=''):
        season, year = self.get_season_year('time')
        variables = {
            'page': page,
            'type': "ANIME",
            'sort': "POPULARITY_DESC",
            'format': "MOVIE"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        popular = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(popular, "anilist_all_time_popular_popular_movie/%d", page)

    def get_voted_last_year_voted_movie(self, page=1, format_in=''):
        season, year = self.get_season_year('')
        variables = {
            'page': page,
            'type': "ANIME",
            'year': str(year - 1) + '%',
            'sort': "FAVOURITES_DESC",
            'format': "MOVIE"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        voted = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(voted, "anilist_voted_last_year_voted_movie/%d", page)

    def get_voted_this_year_voted_movie(self, page=1, format_in=''):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "FAVOURITES_DESC",
            'format': "MOVIE"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        voted = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(voted, "anilist_voted_this_year_voted_movie/%d", page)

    def get_voted_last_season_voted_movie(self, page=1, format_in=''):
        season, year = self.get_season_year('last')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "FAVOURITES_DESC",
            'format': "MOVIE"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        voted = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(voted, "anilist_voted_last_season_voted_movie/%d", page)

    def get_voted_this_season_voted_movie(self, page=1, format_in=''):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "FAVOURITES_DESC",
            'format': "MOVIE"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        voted = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(voted, "anilist_voted_this_season_voted_movie/%d", page)

    def get_all_time_voted_voted_movie(self, page=1, format_in=''):
        season, year = self.get_season_year('time')
        variables = {
            'page': page,
            'type': "ANIME",
            'sort': "FAVOURITES_DESC",
            'format': "MOVIE"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        voted = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(voted, "anilist_all_time_voted_voted _movie/%d", page)

    def get_completed_last_year_completed_movie(self, page=1, format_in=''):
        season, year = self.get_season_year('')
        variables = {
            'page': page,
            'type': "ANIME",
            'year': str(year - 1) + '%',
            'status': "FINISHED",
            'sort': "POPULARITY_DESC",
            'format': "MOVIE"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        completed = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(completed, "anilist_completed_last_year_completed_movie/%d", page)

    def get_completed_this_year_completed_movie(self, page=1, format_in=''):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'type': "ANIME",
            'year': str(year) + '%',
            'status': "FINISHED",
            'sort': "POPULARITY_DESC",
            'format': "MOVIE"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        completed = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(completed, "anilist_completed_this_year_completed_movie/%d", page)

    def get_completed_last_season_completed_movie(self, page=1, format_in=''):
        season, year = self.get_season_year('last')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'status': "FINISHED",
            'sort': "POPULARITY_DESC",
            'format': "MOVIE"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        completed = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(completed, "anilist_completed_last_season_completed_movie/%d", page)

    def get_completed_this_season_completed_movie(self, page=1, format_in=''):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'status': "FINISHED",
            'sort': "POPULARITY_DESC",
            'format': "MOVIE"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        completed = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(completed, "anilist_completed_this_season_completed_movie/%d", page)

    def get_upcoming_last_year_upcoming_movie(self, page=1, format_in=''):
        season, year = self.get_season_year('')
        variables = {
            'page': page,
            'type': "ANIME",
            'year': str(year - 1) + '%',
            'sort': "POPULARITY_DESC",
            'format': "MOVIE"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        upcoming = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(upcoming, "anilist_upcoming_last_year_upcoming_movie/%d", page)

    def get_upcoming_this_year_upcoming_movie(self, page=1, format_in=''):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'type': "ANIME",
            'year': str(year) + '%',
            'sort': "POPULARITY_DESC",
            'format': "MOVIE"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        upcoming = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(upcoming, "anilist_upcoming_this_year_upcoming_movie/%d", page)

    def get_upcoming_next_year_upcoming_movie(self, page=1, format_in=''):
        season, year = self.get_season_year('next')
        variables = {
            'page': page,
            'type': "ANIME",
            'year': str(year + 1) + '%',
            'sort': "POPULARITY_DESC",
            'format': "MOVIE"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        upcoming = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(upcoming, "anilist_upcoming_next_year_upcoming_movie/%d", page)

    def get_upcoming_last_season_upcoming_movie(self, page=1, format_in=''):
        season, year = self.get_season_year('last')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "POPULARITY_DESC",
            'format': "MOVIE"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        upcoming = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(upcoming, "anilist_upcoming_last_season_upcoming_movie/%d", page)

    def get_upcoming_this_season_upcoming_movie(self, page=1, format_in=''):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "POPULARITY_DESC",
            'format': "MOVIE"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        upcoming = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(upcoming, "anilist_upcoming_this_season_upcoming_movie/%d", page)

    def get_upcoming_next_season_upcoming_movie(self, page=1, format_in=''):
        season, year = self.get_season_year('next')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "POPULARITY_DESC",
            'format': "MOVIE"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        upcoming = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(upcoming, "anilist_upcoming_next_season_upcoming_movie/%d", page)

    def get_top_100_anime_movie(self, page=1, format_in=''):
        season, year = self.get_season_year('100')
        variables = {
            'page': page,
            'type': "ANIME",
            'sort': "SCORE_DESC",
            'format': "MOVIE"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        top_100_anime = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(top_100_anime, "anilist_top_100_anime_movie/%d", page)

    def get_search_movie(self, query, page=1):
        variables = {
            'page': page,
            'search': query,
            'sort': "SEARCH_MATCH",
            'type': "ANIME",
            'isAdult': control.getSetting('search.adult') == "true",
            'format': "MOVIE"
        }

        search = database.get(self.get_search_res, 0.125, variables, page)
        return self._process_anilist_view(search, "search_movie/%s/%%d" % query, page)

    def get_airing_calendar_tv(self, page=1, format_in=''):
        dbargs = {"otaku_reload": control.getGlobalProp("calendarRefresh")}
        control.setGlobalProp("calendarRefresh", False)

        airing = database.get(self._get_airing_calendar, 12, page, self.format_in_type, **dbargs)
        return airing

    def _get_airing_calendar_tv(self, page=1, format_in=''):
        today = datetime.date.today()
        today_ts = int(time.mktime(today.timetuple()))
        weekStart = today_ts - 86400
        weekEnd = today_ts + (86400 * 6)

        variables = {
            'weekStart': weekStart,
            'weekEnd': weekEnd,
            'page': page,
            'format': "TV"
        }

        list_ = []

        for i in range(0, 4):
            popular = self.get_airing_calenda_res(variables, page)
            list_.append(popular)

            if not popular['pageInfo']['hasNextPage']:
                break

            page += 1
            variables['page'] = page

        results = list(map(self._process_airing_view, list_))
        results = list(itertools.chain(*results))
        return results

    def get_airing_anime_tv(self, page=1, format_in=''):
        season, year = self.get_season_year('Aired')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'status': "RELEASING",
            'sort': "POPULARITY_DESC",
            'format': "TV"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        airing = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(airing, "anilist_airing_anime_tv/%d", page)

    def get_trending_last_year_trending_trending_tv(self, page=1, format_in=''):
        season, year = self.get_season_year('')
        variables = {
            'page': page,
            'type': "ANIME",
            'year': str(year - 1) + '%',
            'sort': "TRENDING_DESC",
            'format': "TV"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        trending = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(trending, "anilist_trending_last_year_trending_trending_tv/%d", page)

    def get_trending_this_year_trending_trending_tv(self, page=1, format_in=''):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "TRENDING_DESC",
            'format': "TV"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        trending = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(trending, "anilist_trending_this_year_trending_trending_tv/%d", page)

    def get_trending_last_season_trending_tv(self, page=1, format_in=''):
        season, year = self.get_season_year('last')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "TRENDING_DESC",
            'format': "TV"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        trending = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(trending, "anilist_trending_last_season_trending_tv/%d", page)

    def get_trending_this_season_trending_tv(self, page=1, format_in=''):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "TRENDING_DESC",
            'format': "TV"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        trending = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(trending, "anilist_trending_this_season_trending_tv/%d", page)

    def get_all_time_trending_trending_tv(self, page=1, format_in=''):
        season, year = self.get_season_year('time')
        variables = {
            'page': page,
            'type': "ANIME",
            'sort': "TRENDING_DESC",
            'format': "TV"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        trending = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(trending, "anilist_all_time_trending_trending_tv/%d", page)

    def get_popular_last_year_popular_tv(self, page=1, format_in=''):
        season, year = self.get_season_year('')
        variables = {
            'page': page,
            'type': "ANIME",
            'year': str(year - 1) + '%',
            'sort': "POPULARITY_DESC",
            'format': "TV"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        popular = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(popular, "anilist_popular_last_year_popular_tv/%d", page)

    def get_popular_this_year_popular_tv(self, page=1, format_in=''):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "POPULARITY_DESC",
            'format': "TV"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        popular = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(popular, "anilist_popular_this_year_popular_tv/%d", page)

    def get_popular_last_season_popular_tv(self, page=1, format_in=''):
        season, year = self.get_season_year('last')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "POPULARITY_DESC",
            'format': "TV"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        popular = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(popular, "anilist_popular_last_season_popular_tv/%d", page)

    def get_popular_this_season_popular_tv(self, page=1, format_in=''):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "POPULARITY_DESC",
            'format': "TV"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        popular = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(popular, "anilist_popular_this_season_popular_tv/%d", page)

    def get_all_time_popular_popular_tv(self, page=1, format_in=''):
        season, year = self.get_season_year('time')
        variables = {
            'page': page,
            'type': "ANIME",
            'sort': "POPULARITY_DESC",
            'format': "TV"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        popular = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(popular, "anilist_all_time_popular_popular_tv/%d", page)

    def get_voted_last_year_voted_tv(self, page=1, format_in=''):
        season, year = self.get_season_year('')
        variables = {
            'page': page,
            'type': "ANIME",
            'year': str(year - 1) + '%',
            'sort': "FAVOURITES_DESC",
            'format': "TV"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        voted = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(voted, "anilist_voted_last_year_voted_tv/%d", page)

    def get_voted_this_year_voted_tv(self, page=1, format_in=''):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "FAVOURITES_DESC",
            'format': "TV"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        voted = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(voted, "anilist_voted_this_year_voted_tv/%d", page)

    def get_voted_last_season_voted_tv(self, page=1, format_in=''):
        season, year = self.get_season_year('last')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "FAVOURITES_DESC",
            'format': "TV"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        voted = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(voted, "anilist_voted_last_season_voted_tv/%d", page)

    def get_voted_this_season_voted_tv(self, page=1, format_in=''):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "FAVOURITES_DESC",
            'format': "TV"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        voted = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(voted, "anilist_voted_this_season_voted_tv/%d", page)

    def get_all_time_voted_voted_tv(self, page=1, format_in=''):
        season, year = self.get_season_year('time')
        variables = {
            'page': page,
            'type': "ANIME",
            'sort': "FAVOURITES_DESC",
            'format': "TV"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        voted = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(voted, "anilist_all_time_voted_voted _tv/%d", page)

    def get_completed_last_year_completed_tv(self, page=1, format_in=''):
        season, year = self.get_season_year('')
        variables = {
            'page': page,
            'type': "ANIME",
            'year': str(year - 1) + '%',
            'status': "FINISHED",
            'sort': "POPULARITY_DESC",
            'format': "TV"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        completed = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(completed, "anilist_completed_last_year_completed_tv/%d", page)

    def get_completed_this_year_completed_tv(self, page=1, format_in=''):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'type': "ANIME",
            'year': str(year) + '%',
            'status': "FINISHED",
            'sort': "POPULARITY_DESC",
            'format': "TV"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        completed = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(completed, "anilist_completed_this_year_completed_tv/%d", page)

    def get_completed_last_season_completed_tv(self, page=1, format_in=''):
        season, year = self.get_season_year('last')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'status': "FINISHED",
            'sort': "POPULARITY_DESC",
            'format': "TV"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        completed = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(completed, "anilist_completed_last_season_completed_tv/%d", page)

    def get_completed_this_season_completed_tv(self, page=1, format_in=''):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'status': "FINISHED",
            'sort': "POPULARITY_DESC",
            'format': "TV"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        completed = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(completed, "anilist_completed_this_season_completed_tv/%d", page)

    def get_upcoming_last_year_upcoming_tv(self, page=1, format_in=''):
        season, year = self.get_season_year('')
        variables = {
            'page': page,
            'type': "ANIME",
            'year': str(year - 1) + '%',
            'sort': "POPULARITY_DESC",
            'format': "TV"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        upcoming = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(upcoming, "anilist_upcoming_last_year_upcoming_tv/%d", page)

    def get_upcoming_this_year_upcoming_tv(self, page=1, format_in=''):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'type': "ANIME",
            'year': str(year) + '%',
            'sort': "POPULARITY_DESC",
            'format': "TV"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        upcoming = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(upcoming, "anilist_upcoming_this_year_upcoming_tv/%d", page)

    def get_upcoming_next_year_upcoming_tv(self, page=1, format_in=''):
        season, year = self.get_season_year('next')
        variables = {
            'page': page,
            'type': "ANIME",
            'year': str(year + 1) + '%',
            'sort': "POPULARITY_DESC",
            'format': "TV"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        upcoming = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(upcoming, "anilist_upcoming_next_year_upcoming_tv/%d", page)

    def get_upcoming_last_season_upcoming_tv(self, page=1, format_in=''):
        season, year = self.get_season_year('last')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "POPULARITY_DESC",
            'format': "TV"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        upcoming = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(upcoming, "anilist_upcoming_last_season_upcoming_tv/%d", page)

    def get_upcoming_this_season_upcoming_tv(self, page=1, format_in=''):
        season, year = self.get_season_year('this')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "POPULARITY_DESC",
            'format': "TV"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        upcoming = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(upcoming, "anilist_upcoming_this_season_upcoming_tv/%d", page)

    def get_upcoming_next_season_upcoming_tv(self, page=1, format_in=''):
        season, year = self.get_season_year('next')
        variables = {
            'page': page,
            'type': "ANIME",
            'season': season,
            'year': str(year) + '%',
            'sort': "POPULARITY_DESC",
            'format': "TV"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        upcoming = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(upcoming, "anilist_upcoming_next_season_upcoming_tv/%d", page)

    def get_top_100_anime_tv(self, page=1, format_in=''):
        season, year = self.get_season_year('100')
        variables = {
            'page': page,
            'type': "ANIME",
            'sort': "SCORE_DESC",
            'format': "TV"
        }

        if self.format_in_type:
            variables['format'] = self.format_in_type

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.licensedBy_type:
            variables['licensedBy'] = self.licensedBy_type

        if self.perPage_type:
            variables['perPage'] = self.perPage_type

        top_100_anime = database.get(self.get_base_res, 0.125, variables, page)
        return self._process_anilist_view(top_100_anime, "anilist_top_100_anime_tv/%d", page)

    def get_search_tv(self, query, page=1):
        variables = {
            'page': page,
            'search': query,
            'sort': "SEARCH_MATCH",
            'type': "ANIME",
            'isAdult': control.getSetting('search.adult') == "true",
            'format': "TV"
        }

        search = database.get(self.get_search_res, 0.125, variables, page)
        return self._process_anilist_view(search, "search_tv/%s/%%d" % query, page)

    def get_recommendations(self, anilist_id, page=1):
        variables = {
            'page': page,
            'id': anilist_id
        }

        recommendations = database.get(self.get_recommendations_res, 0.125, variables, page)
        return self._process_recommendations_view(recommendations, "recommendations_next/{}/%d".format(anilist_id), page)

    def get_relations(self, anilist_id):
        variables = {
            'id': anilist_id
        }

        relations = database.get(self.get_relations_res, 0.125, variables)
        return self._process_relations_view(relations, "find_relations/%d")

    def get_watch_order(self, mal_id):
        from resources.lib.indexers import chiaki
        chiaki_list = chiaki.get_watch_order_list(mal_id)
        watch_order_list = []
        for anime in chiaki_list:
            variables = anime['url'].split("/")[1:]
            idmal = int(variables[3])
            variables = {
                'idMal': idmal
            }

            anilist_item = database.get(self.get_watch_order_res, 0.125, variables)
            if anilist_item is not None:
                watch_order_list.append(anilist_item)

        return self._process_watch_order_view(watch_order_list, "watch_order/%d")

    def get_anilist(self, mal_id):
        variables = {
            'id': mal_id,
            'type': "ANIME"
        }

        mal_to_anilist = self.get_anilist_res(variables)
        return self._process_mal_to_anilist(mal_to_anilist)

    def get_mal_to_anilist(self, mal_id):
        variables = {
            'id': mal_id,
            'type': "ANIME"
        }

        mal_to_anilist = self.get_mal_to_anilist_res(variables)
        return self._process_mal_to_anilist(mal_to_anilist)

    def get_airing_calenda_res(self, variables, page=1):
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

        result = client.request(self._URL, post={'query': query, 'variables': variables}, jpost=True)
        results = json.loads(result)

        if "errors" in results.keys():
            return

        json_res = results['data']['Page']
        return json_res

    def get_base_res(self, variables, page=1):
        query = '''
        query (
            $page: Int = 1,
            $perPage: Int,
            $type: MediaType,
            $isAdult: Boolean = false,
            $format:[MediaFormat],
            $countryOfOrigin:CountryCode
            $licensedBy: String,
            $season: MediaSeason,
            $year: String,
            $status: MediaStatus,
            $sort: [MediaSort] = [POPULARITY_DESC, SCORE_DESC]
        ) {
            Page (page: $page, perPage: $perPage) {
                pageInfo {
                    hasNextPage
                }
                ANIME: media (
                    format_in: $format,
                    type: $type,
                    season: $season,
                    startDate_like: $year,
                    sort: $sort,
                    status: $status
                    isAdult: $isAdult
                    countryOfOrigin: $countryOfOrigin
                    licensedBy: $licensedBy
                ) {
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
        }
        '''

        result = client.request(self._URL, post={'query': query, 'variables': variables}, jpost=True)
        results = json.loads(result)

        if "errors" in results.keys():
            return

        json_res = results['data']['Page']
        return json_res

    def get_search_res(self, variables, page=1):
        query = '''
        query (
            $page: Int = 1,
            $type: MediaType,
            $isAdult: Boolean = false,
            $search: String,
            $sort: [MediaSort] = [SCORE_DESC, POPULARITY_DESC],
            $format:[MediaFormat]
        ) {
            Page (page: $page, perPage: 25) {
                pageInfo {
                    hasNextPage
                }
                ANIME: media (
                    type: $type,
                    search: $search,
                    sort: $sort,
                    isAdult: $isAdult,
                    format_in: $format
                ) {
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
        }
        '''

        result = client.request(self._URL, post={'query': query, 'variables': variables}, jpost=True)
        results = json.loads(result)

        if "errors" in results.keys():
            return

        json_res = results['data']['Page']
        return json_res

    def get_recommendations_res(self, variables, page=1):
        query = '''
        query ($id: Int, $page: Int) {
          Media(id: $id, type: ANIME) {
            id
            recommendations(page: $page, perPage: 25, sort: [RATING_DESC, ID]) {
              pageInfo {
                hasNextPage
              }
              edges {
                node {
                  id
                  rating
                  mediaRecommendation {
                    id
                    title {
                      userPreferred
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

        result = client.request(self._URL, post={'query': query, 'variables': variables}, jpost=True)
        results = json.loads(result)

        if "errors" in results.keys():
            return

        json_res = results['data']['Media']['recommendations']
        return json_res

    def get_relations_res(self, variables):
        query = '''
        query ($id: Int) {
          Media(id: $id, type: ANIME) {
            relations {
              edges {
                relationType
                node {
                  id
                  title {
                    userPreferred
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

        result = client.request(self._URL, post={'query': query, 'variables': variables}, jpost=True)
        results = json.loads(result)

        if "errors" in results.keys():
            return

        json_res = results['data']['Media']['relations']
        return json_res

    def get_watch_order_res(self, variables):
        query = '''
            query ($idMal: Int) {
                Media (idMal: $idMal, type: ANIME) {
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
        result = client.request(self._URL, post={'query': query, 'variables': variables}, jpost=True)
        if result is not None:
            results = json.loads(result)
            json_res = results['data']['Media']
            if "errors" in results.keys():
                return
            return json_res
        else:
            return None

    def get_anilist_res(self, variables):
        query = '''
        query($id: Int, $type: MediaType){
            Media(id: $id, type: $type) {
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

        result = client.request(self._URL, post={'query': query, 'variables': variables}, jpost=True)
        results = json.loads(result)

        if "errors" in results.keys():
            return

        json_res = results['data']['Media']
        return json_res

    def get_mal_to_anilist_res(self, variables):
        query = '''
        query($id: Int, $type: MediaType){Media(idMal: $id, type: $type) {
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

        result = client.request(self._URL, post={'query': query, 'variables': variables}, jpost=True)
        results = json.loads(result)

        if "errors" in results.keys():
            return

        json_res = results['data']['Media']
        return json_res

    @div_flavor
    def _process_anilist_view(self, json_res, base_plugin_url, page, dub=False, dubsub_filter=None):
        hasNextPage = json_res['pageInfo']['hasNextPage']

        if dub:
            mapfunc = partial(self._base_anilist_view, mal_dub=dub, dubsub_filter=dubsub_filter)
        else:
            mapfunc = self._base_anilist_view

        _ = get_meta.collect_meta(json_res['ANIME'])
        all_results = map(mapfunc, json_res['ANIME'])
        all_results = list(itertools.chain(*all_results))

        all_results += self._handle_paging(hasNextPage, base_plugin_url, page)
        return all_results

    def _process_airing_view(self, json_res):
        if control.getSetting('contentorigin.bool') == "true":
            filter_json = [x for x in json_res['airingSchedules'] if x['media']['isAdult'] is False
                           and x['media']['countryOfOrigin'] == self.countryOfOrigin_type]
        else:
            filter_json = [x for x in json_res['airingSchedules'] if x['media']['isAdult'] is False]

        ts = int(time.time())
        mapfunc = partial(self._base_airing_view, ts=ts)
        all_results = list(map(mapfunc, filter_json))
        return all_results

    @div_flavor
    def _process_recommendations_view(self, json_res, base_plugin_url, page, dub=False):
        hasNextPage = json_res['pageInfo']['hasNextPage']
        res = [edge['node']['mediaRecommendation'] for edge in json_res['edges']]

        if dub:
            mapfunc = partial(self._base_anilist_view, mal_dub=dub)
        else:
            mapfunc = self._base_anilist_view

        _ = get_meta.collect_meta(res)
        all_results = list(map(mapfunc, res))
        all_results = list(itertools.chain(*all_results))

        all_results += self._handle_paging(hasNextPage, base_plugin_url, page)
        return all_results

    def _process_relations_view(self, json_res, base_plugin_url, dub=False):
        res = []
        for edge in json_res['edges']:
            if edge['relationType'] != 'ADAPTATION':
                tnode = edge['node']
                tnode.update({'relationType': edge['relationType']})
                res.append(tnode)

        if dub:
            mapfunc = partial(self._base_anilist_view, mal_dub=dub)
        else:
            mapfunc = self._base_anilist_view

        all_results = list(map(mapfunc, res))
        all_results = list(itertools.chain(*all_results))

        return all_results

    def _process_watch_order_view(self, json_res, base_plugin_url, dub=False):
        if dub:
            mapfunc = partial(self._base_anilist_view, mal_dub=dub)
        else:
            mapfunc = self._base_anilist_view

        all_results = list(map(mapfunc, json_res))
        all_results = list(itertools.chain(*all_results))

        return all_results

    def _process_mal_to_anilist(self, res):
        # titles = self._get_titles(res)
        # start_date = self._get_start_date(res)
        self._database_update_show(res)
        _ = get_meta.collect_meta([res])

        return database.get_show(str(res['id']))

    def _base_anilist_view(self, res, mal_dub=None, dubsub_filter=None):
        in_database = database.get_show(res['id'])

        if not in_database:
            self._database_update_show(res)

        # remove cached eps for releasing shows every five days so new eps metadata can be shown
        if res.get('status') == 'RELEASING':
            from datetime import date
            ep_list = database.get_episode_list(res['id'])
            if ep_list:
                last_updated = ep_list[0]['last_updated']
                if six.PY2:
                    year, month, day = last_updated.split('-')
                    ldate = date(int(year), int(month), int(day))
                else:
                    ldate = date.fromisoformat(last_updated)
                ldiff = date.today() - ldate
                if ldiff.days > 4:
                    database.remove_episodes(res['id'])

        kodi_meta = {}
        show_meta = database.get_show_meta(res['id'])
        if show_meta:
            kodi_meta.update(pickle.loads(show_meta.get('art')))

        title = res.get('title').get(self._TITLE_LANG)
        if not title:
            title = res.get('title').get('userPreferred')

        if res.get('relationType'):
            title += ' [COLOR limegreen][I]{0}[/I][/COLOR]'.format(res.get('relationType'))

        info = {}

        info['genre'] = res.get('genres')

        desc = res.get('description')
        if desc:
            desc = desc.replace('<i>', '[I]').replace('</i>', '[/I]')
            desc = desc.replace('<b>', '[B]').replace('</b>', '[/B]')
            desc = desc.replace('<br>', '[CR]')
            desc = desc.replace('\n', '')
            info['plot'] = desc
        try:
            info['title'] = title
        except:
            pass
        try:
            info['duration'] = res.get('duration') * 60
        except:
            pass
        try:
            start_date = res.get('startDate')
            info['premiered'] = '{}-{:02}-{:02}'.format(start_date['year'], start_date['month'], start_date['day'])
            info['year'] = start_date['year']
        except:
            pass
        try:
            info['status'] = res.get('status')
        except:
            pass
        info['mediatype'] = 'tvshow'
        info['country'] = res.get('countryOfOrigin', '')

        try:
            cast = []
            cast2 = []
            for x in res.get('characters').get('edges'):
                role = x.get('node').get('name').get('userPreferred')
                actor = x.get('voiceActors')[0].get('name').get('userPreferred')
                actor_hs = x.get('voiceActors')[0].get('image').get('large')
                cast.append((actor, role))
                cast2.append({'name': actor, 'role': role, 'thumbnail': actor_hs})
            info['cast'] = cast
            info['cast2'] = cast2
        except:
            pass
        try:
            info['studio'] = [x.get('node').get('name') for x in res.get('studios').get('edges')]
        except:
            pass

        try:
            info['rating'] = res.get('averageScore') / 10.0
        except:
            pass

        try:
            if res.get('trailer').get('site') == 'youtube':
                info['trailer'] = 'plugin://plugin.video.youtube/play/?video_id={0}'.format(res.get('trailer').get('id'))
            else:
                info['trailer'] = 'plugin://plugin.video.dailymotion_com/?url={0}&mode=playVideo'.format(res.get('trailer').get('id'))
        except:
            pass

        dub = False
        mal_id = str(res.get('idMal', 0))

        if mal_dub and mal_dub.get(mal_id):
            dub = True

        base = {
            "name": title,
            "url": "animes/%s/%s/" % (res['id'], res.get('idMal')),
            "image": res['coverImage']['extraLarge'],
            "poster": res['coverImage']['extraLarge'],
            "fanart": res['coverImage']['extraLarge'],
            "banner": res.get('bannerImage'),
            "info": info,
        }

        if kodi_meta.get('fanart'):
            base['fanart'] = random.choice(kodi_meta.get('fanart'))
        if kodi_meta.get('thumb'):
            base['landscape'] = random.choice(kodi_meta.get('thumb'))
        if kodi_meta.get('clearart'):
            base['clearart'] = random.choice(kodi_meta.get('clearart'))
        if kodi_meta.get('clearlogo'):
            base['clearlogo'] = random.choice(kodi_meta.get('clearlogo'))

        if res['format'] in ['MOVIE', 'ONA'] and res['episodes'] == 1:
            base['url'] = "play_movie/%s/1/" % (res['id'])
            base['info']['mediatype'] = 'movie'
            return self._parse_view(base, False, dub=dub, dubsub_filter=dubsub_filter)

        return self._parse_view(base, dub=dub, dubsub_filter=dubsub_filter)

    def _base_airing_view(self, res, ts):
        airingAt = datetime.datetime.fromtimestamp(res['airingAt'])
        airingAt_day = airingAt.strftime('%A')
        airingAt_time = airingAt.strftime('%I:%M %p')
        airing_status = 'airing' if res['airingAt'] > ts else 'aired'
        rank = None
        rankings = res['media']['rankings']
        if rankings and rankings[-1]['season']:
            rank = rankings[-1]['rank']
        genres = res['media']['genres']
        countryOfOrigin = res['media']['countryOfOrigin']
        if genres:
            genres = ' | '.join(genres[:3])
        title = res['media']['title'][self._TITLE_LANG]
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
            'countryOfOrigin': countryOfOrigin,
            'id': res['media']['id']
        }

        return base

    def _database_update_show(self, res):
        titles = self._get_titles(res)
        start_date = self._get_start_date(res)
        title_userPreferred = res['title'][self._TITLE_LANG]
        if not title_userPreferred:
            title_userPreferred = res['title']['userPreferred']

        kodi_meta = {}
        name = res['title']['romaji']
        name = name.encode('utf-8') if six.PY2 else name
        kodi_meta['name'] = name
        ename = res['title']['english']
        if ename:
            ename = ename.encode('utf-8') if six.PY2 else ename
        kodi_meta['ename'] = ename
        kodi_meta['title_userPreferred'] = title_userPreferred.encode('utf-8') if six.PY2 else title_userPreferred
        kodi_meta['start_date'] = start_date
        kodi_meta['query'] = titles
        kodi_meta['episodes'] = res['episodes']
        kodi_meta['poster'] = res['coverImage']['extraLarge']
        kodi_meta['status'] = res.get('status')
        kodi_meta['format'] = res.get('format')
        kodi_meta['duration'] = res.get('duration')
        if res.get('format') != 'TV':
            if res.get('averageScore'):
                kodi_meta['rating'] = res.get('averageScore') / 10.0
            desc = res.get('description')
            if desc:
                desc = desc.replace('<i>', '[I]').replace('</i>', '[/I]')
                desc = desc.replace('<b>', '[B]').replace('</b>', '[/B]')
                desc = desc.replace('<br>', '[CR]')
                desc = desc.replace('\n', '')
                kodi_meta['plot'] = desc.encode('utf-8') if six.PY2 else desc

        database._update_show(
            res['id'],
            res.get('idMal'),
            pickle.dumps(kodi_meta)
        )

    def _get_titles(self, res):
        # titles = list(set(res['title'].values()))
        # if res['format'] == 'MOVIE':
        #     titles = list(res['title'].values())
        # # titles = [x for x in titles if (all(ord(char) < 128 for char in x) if x else [])][:3]
        # titles = [x.encode('utf-8') if six.PY2 else x for x in titles if x][:3]
        # query_titles = '({})'.format(')|('.join(map(str, titles)))
        name = res['title']['romaji']
        name = name.encode('utf-8') if six.PY2 else name
        ename = res['title']['english']
        if ename:
            ename = ename.encode('utf-8') if six.PY2 else ename
        query_titles = '({0})|({1})'.format(name, ename)
        return query_titles

    def _get_start_date(self, res):
        try:
            start_date = res.get('startDate')
            start_date = '{}-{:02}-{:02}'.format(start_date['year'], start_date['month'], start_date['day'])
        except:
            start_date = 'null'

        return start_date

    @staticmethod
    def _parse_view(base, is_dir=True, dub=False, dubsub_filter=None):
        if dubsub_filter == "Both":
            base['info']['title'] = "%s (Sub)" % base['name']
            if dub:
                parsed_view = [utils.allocate_item(
                    "%s (Sub)" % base["name"],
                    base["url"] + '2',
                    is_dir,
                    image=base["image"],
                    info=base["info"],
                    fanart=base["fanart"],
                    poster=base["image"],
                    landscape=base.get("landscape"),
                    banner=base.get("banner"),
                    clearart=base.get("clearart"),
                    clearlogo=base.get("clearlogo")
                )]

                base2 = copy.deepcopy(base)
                base2['info']['title'] = "%s (Dub)" % base['name']
                parsed_view.append(utils.allocate_item(
                    "%s (Dub)" % base["name"],
                    base["url"] + '0',
                    is_dir,
                    image=base["image"],
                    info=base2["info"],
                    fanart=base["fanart"],
                    poster=base["image"],
                    landscape=base.get("landscape"),
                    banner=base.get("banner"),
                    clearart=base.get("clearart"),
                    clearlogo=base.get("clearlogo")
                ))

            else:
                parsed_view = [utils.allocate_item(
                    "%s (Sub)" % base["name"],
                    base["url"],
                    is_dir=is_dir,
                    image=base["image"],
                    info=base["info"],
                    fanart=base["fanart"],
                    poster=base["image"],
                    landscape=base.get("landscape"),
                    banner=base.get("banner"),
                    clearart=base.get("clearart"),
                    clearlogo=base.get("clearlogo")
                )]
        elif dubsub_filter == 'Dub':
            if dub:
                parsed_view = [utils.allocate_item(
                    "%s" % base["name"],
                    base["url"] + '0',
                    is_dir,
                    image=base["image"],
                    info=base["info"],
                    fanart=base["fanart"],
                    poster=base["image"],
                    landscape=base.get("landscape"),
                    banner=base.get("banner"),
                    clearart=base.get("clearart"),
                    clearlogo=base.get("clearlogo")
                )]
            else:
                parsed_view = []
        else:
            parsed_view = [utils.allocate_item(
                base["name"],
                base["url"],
                is_dir=is_dir,
                image=base["image"],
                info=base["info"],
                fanart=base["fanart"],
                poster=base["image"],
                landscape=base.get("landscape"),
                banner=base.get("banner"),
                clearart=base.get("clearart"),
                clearlogo=base.get("clearlogo")
            )]
        return parsed_view

    def get_genres(self, genre_dialog):
        query = '''
        query {
            genres: GenreCollection,
            tags: MediaTagCollection {
                name
                isAdult
            }
        }
        '''

        result = client.request(self._URL, post={'query': query}, jpost=True)
        results = json.loads(result)['data']
        genres_list = results['genres']

        del genres_list[6]

        tags_list = []
        # tags = filter(lambda x: x['isAdult'] == False, results['tags'])
        tags = [x for x in results['tags'] if x['isAdult'] is False]
        for tag in tags:
            tags_list.append(tag['name'])

        genre_display_list = genres_list + tags_list
        return self._select_genres(genre_dialog, genre_display_list)

    def _select_genres(self, genre_dialog, genre_display_list):
        multiselect = genre_dialog(genre_display_list)

        if not multiselect:
            return []

        genre_list = []
        tag_list = []

        for selection in multiselect:
            if selection <= 17:
                genre_list.append(genre_display_list[selection])
                continue

            tag_list.append(genre_display_list[selection])

        return self._genres_payload(genre_list, tag_list)

    def _genres_payload(self, genre_list, tag_list, page=1):
        query = '''
        query (
            $page: Int,
            $perPage: Int,
            $type: MediaType,
            $isAdult: Boolean = false,
            $includedGenres: [String],
            $includedTags: [String],
            $sort: [MediaSort] = [SCORE_DESC, POPULARITY_DESC]
        ) {
            Page (page: $page, perPage: $perPage) {
                pageInfo {
                    hasNextPage
                }
                ANIME: media (
                    type: $type,
                    genre_in: $includedGenres,
                    tag_in: $includedTags,
                    sort: $sort,
                    isAdult: $isAdult
                ) {
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
                    isAdult
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
        }
        '''

        variables = {
            'page': page,
            'type': "ANIME"
        }

        if genre_list:
            variables["includedGenres"] = genre_list

        if tag_list:
            variables["includedTags"] = tag_list

        return self._process_genre_view(query, variables, "anilist_genres/%s/%s/%%d" % (genre_list, tag_list), page)

    @div_flavor
    def _process_genre_view(self, query, variables, base_plugin_url, page, dub=False, dubsub_filter=None):
        result = client.request(self._URL, post={'query': query, 'variables': variables}, jpost=True)
        results = json.loads(result)

        if "errors" in results.keys():
            return

        anime_res = results['data']['Page']['ANIME']
        hasNextPage = results['data']['Page']['pageInfo']['hasNextPage']

        if dub:
            mapfunc = partial(self._base_anilist_view, mal_dub=dub, dubsub_filter=dubsub_filter)
        else:
            mapfunc = self._base_anilist_view

        _ = get_meta.collect_meta(anime_res)
        all_results = list(map(mapfunc, anime_res))
        all_results = list(itertools.chain(*all_results))

        all_results += self._handle_paging(hasNextPage, base_plugin_url, page)
        return all_results

    def get_genres_page(self, genre_string, tag_string, page):
        return self._genres_payload(ast.literal_eval(genre_string), ast.literal_eval(tag_string), page)

    def get_genres_movie(self, genre_dialog):
        query = '''
        query {
            genres: GenreCollection,
            tags: MediaTagCollection {
                name
                isAdult
            }
        }
        '''

        result = client.request(self._URL, post={'query': query}, jpost=True)
        results = json.loads(result)['data']
        genres_list = results['genres']

        del genres_list[6]

        tags_list = []
        # tags = filter(lambda x: x['isAdult'] == False, results['tags'])
        tags = [x for x in results['tags'] if x['isAdult'] is False]
        for tag in tags:
            tags_list.append(tag['name'])

        genre_display_list = genres_list + tags_list
        return self._select_genres_movie(genre_dialog, genre_display_list)

    def _select_genres_movie(self, genre_dialog, genre_display_list):
        multiselect = genre_dialog(genre_display_list)

        if not multiselect:
            return []

        genre_list = []
        tag_list = []

        for selection in multiselect:
            if selection <= 17:
                genre_list.append(genre_display_list[selection])
                continue

            tag_list.append(genre_display_list[selection])

        return self._genres_payload_movie(genre_list, tag_list)

    def _genres_payload_movie(self, genre_list, tag_list, page=1):
        query = '''
        query (
            $page: Int,
            $perPage: Int,
            $type: MediaType,
            $isAdult: Boolean = false,
            $includedGenres: [String],
            $includedTags: [String],
            $sort: [MediaSort] = [SCORE_DESC, POPULARITY_DESC],
            $format:[MediaFormat]
        ) {
            Page (page: $page, perPage: $perPage) {
                pageInfo {
                    hasNextPage
                }
                ANIME: media (
                    type: $type,
                    genre_in: $includedGenres,
                    tag_in: $includedTags,
                    sort: $sort,
                    isAdult: $isAdult,
                    format_in: $format
                ) {
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
                    isAdult
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
        }
        '''

        variables = {
            'page': page,
            'type': "ANIME",
            'format': "MOVIE"
        }

        if genre_list:
            variables["includedGenres"] = genre_list

        if tag_list:
            variables["includedTags"] = tag_list

        return self._process_genre_view_movie(query, variables, "anilist_genres_movie/%s/%s/%%d" % (genre_list, tag_list), page)

    @div_flavor
    def _process_genre_view_movie(self, query, variables, base_plugin_url, page, dub=False, dubsub_filter=None):
        result = client.request(self._URL, post={'query': query, 'variables': variables}, jpost=True)
        results = json.loads(result)

        if "errors" in results.keys():
            return

        anime_res = results['data']['Page']['ANIME']
        hasNextPage = results['data']['Page']['pageInfo']['hasNextPage']

        if dub:
            mapfunc = partial(self._base_anilist_view, mal_dub=dub, dubsub_filter=dubsub_filter)
        else:
            mapfunc = self._base_anilist_view

        _ = get_meta.collect_meta(anime_res)
        all_results = list(map(mapfunc, anime_res))
        all_results = list(itertools.chain(*all_results))

        all_results += self._handle_paging(hasNextPage, base_plugin_url, page)
        return all_results

    def get_genres_movie_page(self, genre_string, tag_string, page):
        return self._genres_payload(ast.literal_eval(genre_string), ast.literal_eval(tag_string), page)

    def get_genres_tv(self, genre_dialog):
        query = '''
        query {
            genres: GenreCollection,
            tags: MediaTagCollection {
                name
                isAdult
            }
        }
        '''

        result = client.request(self._URL, post={'query': query}, jpost=True)
        results = json.loads(result)['data']
        genres_list = results['genres']

        del genres_list[6]

        tags_list = []
        # tags = filter(lambda x: x['isAdult'] == False, results['tags'])
        tags = [x for x in results['tags'] if x['isAdult'] is False]
        for tag in tags:
            tags_list.append(tag['name'])

        genre_display_list = genres_list + tags_list
        return self._select_genres_tv(genre_dialog, genre_display_list)

    def _select_genres_tv(self, genre_dialog, genre_display_list):
        multiselect = genre_dialog(genre_display_list)

        if not multiselect:
            return []

        genre_list = []
        tag_list = []

        for selection in multiselect:
            if selection <= 17:
                genre_list.append(genre_display_list[selection])
                continue

            tag_list.append(genre_display_list[selection])

        return self._genres_payload_tv(genre_list, tag_list)

    def _genres_payload_tv(self, genre_list, tag_list, page=1):
        query = '''
        query (
            $page: Int,
            $perPage: Int,
            $type: MediaType,
            $isAdult: Boolean = false,
            $includedGenres: [String],
            $includedTags: [String],
            $sort: [MediaSort] = [SCORE_DESC, POPULARITY_DESC],
            $format:[MediaFormat]
        ) {
            Page (page: $page, perPage: $perPage) {
                pageInfo {
                    hasNextPage
                }
                ANIME: media (
                    type: $type,
                    genre_in: $includedGenres,
                    tag_in: $includedTags,
                    sort: $sort,
                    isAdult: $isAdult,
                    format_in: $format
                ) {
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
                    isAdult
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
        }
        '''

        variables = {
            'page': page,
            'type': "ANIME",
            'format': "TV"
        }

        if genre_list:
            variables["includedGenres"] = genre_list

        if tag_list:
            variables["includedTags"] = tag_list

        return self._process_genre_view_tv(query, variables, "anilist_genres_tv/%s/%s/%%d" % (genre_list, tag_list), page)

    @div_flavor
    def _process_genre_view_tv(self, query, variables, base_plugin_url, page, dub=False, dubsub_filter=None):
        result = client.request(self._URL, post={'query': query, 'variables': variables}, jpost=True)
        results = json.loads(result)

        if "errors" in results.keys():
            return

        anime_res = results['data']['Page']['ANIME']
        hasNextPage = results['data']['Page']['pageInfo']['hasNextPage']

        if dub:
            mapfunc = partial(self._base_anilist_view, mal_dub=dub, dubsub_filter=dubsub_filter)
        else:
            mapfunc = self._base_anilist_view

        _ = get_meta.collect_meta(anime_res)
        all_results = list(map(mapfunc, anime_res))
        all_results = list(itertools.chain(*all_results))

        all_results += self._handle_paging(hasNextPage, base_plugin_url, page)
        return all_results

    def get_genres_tv_page(self, genre_string, tag_string, page):
        return self._genres_payload(ast.literal_eval(genre_string), ast.literal_eval(tag_string), page)

    def update_trakt_id(self, anilist_id):
        slug = control.keyboard('Enter Trakt Slug[CR]example, to-your-eternity')
        if slug:
            from resources.lib.indexers.trakt import TRAKTAPI
            from resources.lib.ui.get_meta import update_meta
            show = database.get_show(anilist_id)
            kodi_meta = pickle.loads(show.get('kodi_meta'))
            mtype = 'movies' if kodi_meta.get('format') == 'MOVIE' else 'tv'
            if kodi_meta.get('format') == 'ONA' and kodi_meta.get('episodes') == 1:
                mtype = 'movies'
            slug_type = 'shows' if mtype == 'tv' else mtype
            meta_ids = TRAKTAPI().get_ids_by_slug(slug, slug_type)
            update_meta(anilist_id, meta_ids, mtype)
            database.remove_season(anilist_id)
            database.remove_episodes(anilist_id)
            control.refresh()
        return
