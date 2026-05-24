import ast
import datetime
import json
import os
import pickle
import random
import re

from bs4 import BeautifulSoup
from functools import partial

from resources.lib.ui import database, control, client, utils, get_meta
from resources.lib.ui.BrowserBase import BrowserBase
from resources.lib.ui.divide_flavors import div_flavor

_MAL_GENRE_PRESETS = (
    ('action', '1'),
    ('adventure', '2'),
    ('comedy', '4'),
    ('drama', '8'),
    ('ecchi', '9'),
    ('fantasy', '10'),
    ('hentai', '12'),
    ('horror', '14'),
    ('shoujo', '25'),
    ('mecha', '18'),
    ('music', '19'),
    ('mystery', '7'),
    ('psychological', '40'),
    ('romance', '22'),
    ('sci_fi', '24'),
    ('slice_of_life', '36'),
    ('sports', '30'),
    ('supernatural', '37'),
    ('thriller', '41'),
)


class MalBrowser(BrowserBase):
    _BASE_URL = "https://api.jikan.moe/v4"

    _IX_YEAR_START = 2
    _IX_YEAR_END = 3
    _IX_SEASON_START = 4
    _IX_SEASON_END = 5
    _IX_LAST_SEASON_START = 6
    _IX_LAST_SEASON_END = 7
    _IX_LAST_YEAR_START = 8
    _IX_LAST_YEAR_END = 9

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
                return ', '.join(genres)
        return ''

    def process_mal_view(self, res, base_plugin_url, page):
        data = res.get('data') or []
        get_meta.collect_meta(data)
        mapfunc = partial(self.base_mal_view, completed=self.open_completed())
        all_results = list(map(mapfunc, data))
        has_next = res.get('pagination', {}).get('has_next_page', False)
        all_results += self.handle_paging(has_next, base_plugin_url, page)
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

        season = None
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

        season_start_date = season_start_dates[season]
        season_end_date = season_end_dates[season]

        year_start_date = datetime.date(year, 1, 1)
        year_end_date = datetime.date(year, 12, 31)

        last_season_index = (seasons.index(season) - 1) % 4
        last_season = seasons[last_season_index]
        last_season_year = year if last_season != 'FALL' or month > 3 else year - 1
        season_start_date_last = season_start_dates[last_season].replace(year=last_season_year)
        season_end_date_last = season_end_dates[last_season].replace(year=last_season_year)

        year_start_date_last = datetime.date(year - 1, 1, 1)
        year_end_date_last = datetime.date(year - 1, 12, 31)

        next_season_index = (seasons.index(season) + 1) % 4
        next_season = seasons[next_season_index]
        next_season_year = year if next_season != 'WINTER' else year + 1
        season_start_date_next = season_start_dates[next_season].replace(year=next_season_year)
        season_end_date_next = season_end_dates[next_season].replace(year=next_season_year)

        year_start_date_next = datetime.date(year + 1, 1, 1)
        year_end_date_next = datetime.date(year + 1, 12, 31)

        return (season, year, year_start_date, year_end_date, season_start_date, season_end_date,
                season_start_date_last, season_end_date_last, year_start_date_last, year_end_date_last,
                season_start_date_next, season_end_date_next, year_start_date_next, year_end_date_next)

    def _plugin_page_url(self, prefix, route_slug):
        return f"{prefix}?page=%d" if prefix else f"{route_slug}?page=%d"

    def _apply_season_format_params(self, params, format_val):
        if format_val:
            params['filter'] = format_val
        elif self.format_in_type:
            params['filter'] = self.format_in_type

    def _apply_anime_type_params(self, params, format_val):
        if format_val:
            params['type'] = format_val
        elif self.format_in_type:
            params['type'] = self.format_in_type

    def _apply_content_filters(self, params):
        if self.status:
            params['status'] = self.status
        if self.rating:
            params['rating'] = self.rating
        if self.genre:
            params['genres'] = self.genre

    def _browse_mal_anime_list(self, page, format, prefix, route_slug, extra_params=None, relax_on_empty=False):
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
        }
        if extra_params:
            params.update(extra_params)
        self._apply_anime_type_params(params, format)
        self._apply_content_filters(params)
        mal_res = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        if relax_on_empty and not mal_res.get('data'):
            # Jikan interprets multiple genres as strict AND; retry ranked pages without it.
            genres = params.get('genres')
            if isinstance(genres, str) and ',' in genres:
                params_relaxed = dict(params)
                params_relaxed.pop('genres', None)
                mal_res_relaxed = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params_relaxed)
                if mal_res_relaxed and mal_res_relaxed.get('data'):
                    mal_res = mal_res_relaxed
        return self.process_mal_view(mal_res, self._plugin_page_url(prefix, route_slug), page)

    def _date_extra_from_bounds(self, sy, mode):
        if mode == 'last_year':
            return {'start_date': sy[self._IX_LAST_YEAR_START], 'end_date': sy[self._IX_LAST_YEAR_END]}
        if mode == 'this_year':
            return {'start_date': sy[self._IX_YEAR_START], 'end_date': sy[self._IX_YEAR_END]}
        if mode == 'last_season':
            return {'start_date': sy[self._IX_LAST_SEASON_START], 'end_date': sy[self._IX_LAST_SEASON_END]}
        if mode == 'this_season':
            return {'start_date': sy[self._IX_SEASON_START], 'end_date': sy[self._IX_SEASON_END]}
        return {}

    @staticmethod
    def _normalize_date_params(params):
        normalized = {}
        for key, value in params.items():
            if value in (None, ''):
                continue
            if hasattr(value, 'isoformat'):
                normalized[key] = value.isoformat()
            else:
                normalized[key] = value
        return normalized

    def _ranked_mal_list(self, page, format, prefix, route_slug, order_by, sort, date_mode=None):
        sy = self.get_season_year('')
        extra = {'order_by': order_by, 'sort': sort}
        if date_mode:
            extra.update(self._date_extra_from_bounds(sy, date_mode))
        extra = self._normalize_date_params(extra)
        return self._browse_mal_anime_list(page, format, prefix, route_slug, extra, relax_on_empty=True)

    def _browse_season_airing(self, page, format, prefix, route_slug, period):
        season, year, _, _, _, _, _, _, _, _, _, _, _, _ = self.get_season_year(period)
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
        }
        self._apply_season_format_params(params, format)
        airing = database.get(self.get_base_res, 24, f"{self._BASE_URL}/seasons/{year}/{season}", params)
        return self.process_mal_view(airing, self._plugin_page_url(prefix, route_slug), page)

    def _browse_genre_preset(self, page, format, prefix, route_slug, mal_genre_id):
        # Fixed MAL genre id — do not merge saved multi-genre settings into `genres`.
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
            'order_by': 'members',
            'genres': mal_genre_id,
            'sort': 'desc',
        }
        self._apply_anime_type_params(params, format)
        if self.status:
            params['status'] = self.status
        if self.rating:
            params['rating'] = self.rating
        mal_res = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        return self.process_mal_view(mal_res, self._plugin_page_url(prefix, route_slug), page)

    def _fetch_mal_anime_data(self, mal_id, retry_limit=3):
        retries = 0
        while retries < retry_limit:
            res_data = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime/{mal_id}")
            if res_data is not None and 'data' in res_data:
                return res_data['data']
            retries += 1
            control.sleep(int(100 * retries))
        return None

    def _maybe_throttle_burst(self, count):
        if count % 3 == 0:
            control.sleep(1000)

    def get_anime(self, mal_id):
        res = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime/{mal_id}")
        return self.process_res(res['data'])

    def get_recommendations(self, mal_id, page):
        recommendations = database.get(self.get_base_res, 24, f'{self._BASE_URL}/anime/{mal_id}/recommendations')
        get_meta.collect_meta(recommendations['data'])

        recommendation_res = []
        count = 0
        for recommendation in recommendations['data']:
            entry = recommendation.get('entry')
            if entry and entry.get('mal_id'):
                data = self._fetch_mal_anime_data(entry['mal_id'])
                if data is not None:
                    data['votes'] = recommendation.get('votes')
                    recommendation_res.append(data)
                count += 1
                self._maybe_throttle_burst(count)

        mapfunc = partial(self.base_mal_view, completed=self.open_completed())
        return list(map(mapfunc, recommendation_res))

    def get_relations(self, mal_id):
        relations = database.get(self.get_base_res, 24, f'{self._BASE_URL}/anime/{mal_id}/relations')
        meta_ids = [{'mal_id': entry['mal_id']} for relation in relations['data'] for entry in relation['entry']]
        get_meta.collect_meta(meta_ids)

        relation_res = []
        count = 0
        for relation in relations['data']:
            for entry in relation['entry']:
                if entry['type'] == 'anime':
                    data = self._fetch_mal_anime_data(entry['mal_id'])
                    if data is not None:
                        data['relation'] = relation['relation']
                        relation_res.append(data)
                    count += 1
                    self._maybe_throttle_burst(count)

        mapfunc = partial(self.base_mal_view, completed=self.open_completed())
        return list(map(mapfunc, relation_res))

    def get_watch_order(self, mal_id):
        url = 'https://chiaki.site/?/tools/watch_order/id/{}'.format(mal_id)
        response = client.get(url)
        soup = BeautifulSoup(response.text, 'html.parser') if response else None

        anime_info = soup.find('tr', {'data-id': str(mal_id)}) if soup else None
        watch_order_list = []
        if anime_info is not None:
            mal_links = soup.find_all('a', href=re.compile(r'https://myanimelist\.net/anime/\d+'))
            mal_ids = []
            for link in mal_links:
                m = re.search(r'\d+', link['href'])
                if m:
                    mal_ids.append(m.group())
            get_meta.collect_meta([{'mal_id': mid} for mid in mal_ids])

            for idx, idmal in enumerate(mal_ids):
                data = self._fetch_mal_anime_data(idmal)
                if data is not None:
                    watch_order_list.append(data)
                if (idx + 1) % 3 == 0:
                    control.sleep(1000)

        mapfunc = partial(self.base_mal_view, completed=self.open_completed())
        return list(map(mapfunc, watch_order_list))

    def _fetch_jikan_reviews_json(self, mal_id, page):
        try:
            mid = int(mal_id)
        except (TypeError, ValueError):
            return None
        params = {
            'page': page,
            'preliminary': 'true',
            'spoilers': 'true',
        }
        res = database.get(self.get_base_res, 24, f'{self._BASE_URL}/anime/{mid}/reviews', params)
        if not res or not isinstance(res, dict):
            return None
        return res

    def refetch_reviews_page(self, mal_id, page):
        res = self._fetch_jikan_reviews_json(mal_id, page)
        if res is None:
            return None
        return res.get('data') or []

    def get_reviews_page(self, mal_id, page, path, eps_watched):
        res = self._fetch_jikan_reviews_json(mal_id, page)
        if res is None:
            return None
        reviews = res.get('data') or []
        pagination = res.get('pagination') or {}
        has_next = pagination.get('has_next_page', False)
        items = []
        for idx, review in enumerate(reviews):
            user = review.get('user', {})
            username = user.get('username', 'Anonymous')
            sraw = review.get('score', '?')
            if isinstance(sraw, str) and '/' in sraw:
                score_show = sraw
            else:
                score_show = f'{sraw}/10'
            tags = review.get('tags', [])
            tag_str = tags[0] if tags else ''
            date = review.get('date', '')[:10]
            is_spoiler = review.get('is_spoiler', False)
            is_preliminary = review.get('is_preliminary', False)
            spoiler_tag = ' [COLOR red][Spoiler][/COLOR]' if is_spoiler else ''
            preliminary_tag = ' [COLOR yellow][Preliminary][/COLOR]' if is_preliminary else ''
            title = f"[COLOR deepskyblue]{username}[/COLOR] - {score_show} [COLOR orange][{tag_str}][/COLOR]{spoiler_tag}{preliminary_tag}  ({date})"
            preview = review.get('review', '')[:200].replace('\n', ' ') + '...'
            info = {
                'title': title,
                'plot': preview,
                'mediatype': 'video',
            }
            art_url = user.get('images', {}).get('jpg', {}).get('image_url') or control.OTAKU_LOGO3_PATH
            items.append(utils.allocate_item(
                title,
                f'view_review/{mal_id}/{idx}/',
                False, False,
                [],
                art_url,
                info,
                fanart=art_url,
                poster=art_url,
            ))
        if has_next:
            next_title = f'[COLOR deepskyblue]>>> {control.lang(30464)} (Page {page + 1}) >>>[/COLOR]'
            next_url = f'anime_reviews/{path}/{mal_id}/{eps_watched}?page={page + 1}'
            items.append(utils.allocate_item(next_title, next_url, True, False, [], 'next.png', {'plot': next_title}, fanart='next.png'))
        return {'items': items, 'reviews': reviews}

    def get_statistics_payload(self, mal_id):
        try:
            mid = int(mal_id)
        except (TypeError, ValueError):
            return None
        res = database.get(self.get_base_res, 24, f'{self._BASE_URL}/anime/{mid}/statistics')
        if not res or not isinstance(res, dict):
            return None
        data = res.get('data')
        if not data:
            return None
        return data

    def get_search(self, query, page, format, prefix=None):
        params = {
            "q": query,
            "page": page,
            "limit": self.perpage,
            'sfw': self.adult
        }
        if format:
            params['type'] = format
        elif self.format_in_type:
            params['type'] = self.format_in_type

        search = database.get(self.get_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}/{query}?page=%d" if prefix else f"search_anime/{query}?page=%d"
        return self.process_mal_view(search, base_plugin_url, page)

    def get_airing_last_season(self, page, format, prefix=None):
        return self._browse_season_airing(page, format, prefix, 'airing_last_season', 'last')

    def get_airing_this_season(self, page, format, prefix=None):
        return self._browse_season_airing(page, format, prefix, 'airing_this_season', 'this')

    def get_airing_next_season(self, page, format, prefix=None):
        return self._browse_season_airing(page, format, prefix, 'airing_next_season', 'next')

    def get_trending_last_year(self, page, format, prefix=None):
        return self._ranked_mal_list(page, format, prefix, 'trending_last_year', 'members', 'desc', 'last_year')

    def get_trending_this_year(self, page, format, prefix=None):
        return self._ranked_mal_list(page, format, prefix, 'trending_this_year', 'members', 'desc', 'this_year')

    def get_trending_last_season(self, page, format, prefix=None):
        return self._ranked_mal_list(page, format, prefix, 'trending_last_season', 'members', 'desc', 'last_season')

    def get_trending_this_season(self, page, format, prefix=None):
        return self._ranked_mal_list(page, format, prefix, 'trending_this_season', 'members', 'desc', 'this_season')

    def get_all_time_trending(self, page, format, prefix=None):
        return self._ranked_mal_list(page, format, prefix, 'all_time_trending', 'members', 'desc')

    def get_popular_last_year(self, page, format, prefix=None):
        return self._ranked_mal_list(page, format, prefix, 'popular_last_year', 'popularity', 'asc', 'last_year')

    def get_popular_this_year(self, page, format, prefix=None):
        return self._ranked_mal_list(page, format, prefix, 'popular_this_year', 'popularity', 'asc', 'this_year')

    def get_popular_last_season(self, page, format, prefix=None):
        return self._ranked_mal_list(page, format, prefix, 'popular_last_season', 'popularity', 'asc', 'last_season')

    def get_popular_this_season(self, page, format, prefix=None):
        return self._ranked_mal_list(page, format, prefix, 'popular_this_season', 'popularity', 'asc', 'this_season')

    def get_all_time_popular(self, page, format, prefix=None):
        return self._ranked_mal_list(page, format, prefix, 'all_time_popular', 'popularity', 'asc')

    def get_voted_last_year(self, page, format, prefix=None):
        return self._ranked_mal_list(page, format, prefix, 'voted_last_year', 'score', 'desc', 'last_year')

    def get_voted_this_year(self, page, format, prefix=None):
        return self._ranked_mal_list(page, format, prefix, 'voted_this_year', 'score', 'desc', 'this_year')

    def get_voted_last_season(self, page, format, prefix=None):
        return self._ranked_mal_list(page, format, prefix, 'voted_last_season', 'score', 'desc', 'last_season')

    def get_voted_this_season(self, page, format, prefix=None):
        return self._ranked_mal_list(page, format, prefix, 'voted_this_season', 'score', 'desc', 'this_season')

    def get_all_time_voted(self, page, format, prefix=None):
        return self._ranked_mal_list(page, format, prefix, 'all_time_voted', 'score', 'desc')

    def get_favourites_last_year(self, page, format, prefix=None):
        return self._ranked_mal_list(page, format, prefix, 'favourites_last_year', 'favorites', 'desc', 'last_year')

    def get_favourites_this_year(self, page, format, prefix=None):
        return self._ranked_mal_list(page, format, prefix, 'favourites_this_year', 'favorites', 'desc', 'this_year')

    def get_favourites_last_season(self, page, format, prefix=None):
        return self._ranked_mal_list(page, format, prefix, 'favourites_last_season', 'favorites', 'desc', 'last_season')

    def get_favourites_this_season(self, page, format, prefix=None):
        return self._ranked_mal_list(page, format, prefix, 'favourites_this_season', 'favorites', 'desc', 'this_season')

    def get_all_time_favourites(self, page, format, prefix=None):
        return self._ranked_mal_list(page, format, prefix, 'all_time_favourites', 'favorites', 'desc')

    def get_top_100(self, page, format, prefix=None):
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
        }
        self._apply_anime_type_params(params, format)
        self._apply_content_filters(params)
        top_100 = database.get(self.get_base_res, 24, f"{self._BASE_URL}/top/anime", params)
        return self.process_mal_view(top_100, self._plugin_page_url(prefix, 'top_100'), page)

    @staticmethod
    def get_base_res(url, params=None):
        r = client.get(url, params=params)
        if r:
            return r.json()

    def get_genres(self, page, format):
        res = database.get(self.get_base_res, 24, f'{self._BASE_URL}/genres/anime')

        genre = res['data']
        genres_list = [x['name'] for x in genre]
        multiselect = control.multiselect_dialog(control.lang(30040), genres_list, preselect=[])
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
        elif self.format_in_type:
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
            info['year'] = res.get('year', int(start_date[:4]))
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
            "info": info
        }

        base['banner'] = kodi_meta.get('banner', image)
        if kodi_meta.get('thumb'):
            thumb = kodi_meta['thumb']
            base['landscape'] = random.choice(thumb) if isinstance(thumb, list) else thumb
        if kodi_meta.get('clearart'):
            clearart = kodi_meta['clearart']
            base['clearart'] = random.choice(clearart) if isinstance(clearart, list) else clearart
        if kodi_meta.get('clearlogo'):
            clearlogo = kodi_meta['clearlogo']
            base['clearlogo'] = random.choice(clearlogo) if isinstance(clearlogo, list) else clearlogo

        if res['episodes'] == 1:
            base['url'] = f'play_movie/{mal_id}/'
            base['info']['mediatype'] = 'movie'
            return utils.parse_view(base, False, True, dub)
        return utils.parse_view(base, True, False, dub)

    def database_update_show(self, res):
        mal_id = res['mal_id']

        start_date = control.safe_call(lambda: res['aired']['from'])

        title_userPreferred = res[self.title_lang] or res['title']

        name = res['title']
        ename = res['title_english']
        if name and ename:
            titles = f"({name})|({ename})"
        elif name:
            titles = f"({name})"
        elif ename:
            titles = f"({ename})"
        else:
            titles = ''

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
            kodi_meta['year'] = res.get('year', int(start_date[:4]))
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

        multiselect = control.multiselect_dialog(control.lang(30040), genres_list, preselect=[])
        if not multiselect:
            return []

        selected_genres_mal = [str(genre[selection]['mal_id']) for selection in multiselect if selection < len(genres_list)]

        selected_genres_anilist = []

        selected_tags = []

        return selected_genres_mal, selected_genres_anilist, selected_tags


def _install_genre_methods():
    for slug, gid in _MAL_GENRE_PRESETS:
        def make_genre(_slug, _gid):
            def method(self, page, format, prefix=None):
                return self._browse_genre_preset(page, format, prefix, f'genre_{_slug}', _gid)
            method.__name__ = f'get_genre_{_slug}'
            method.__doc__ = f'Browse anime with MAL genre preset {_slug} (id {_gid}).'
            return method
        setattr(MalBrowser, f'get_genre_{slug}', make_genre(slug, gid))


_install_genre_methods()
