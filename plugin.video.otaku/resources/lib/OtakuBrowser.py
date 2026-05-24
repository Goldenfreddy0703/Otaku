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

# MAL genre id for preset genre menu entries (Jikan /genres/anime uses same ids)
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


class OtakuBrowser(BrowserBase):
    _BASE_URL = "https://api.jikan.moe/v4"

    # Indices returned by get_season_year()
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

    @staticmethod
    def _flatten_mal_data_items(mal_res):
        """Normalize direct items and nested/list 'entry' shapes (e.g. relations)."""
        mal_items_flat = []
        mal_ids = []
        for item in mal_res.get('data', []):
            if 'mal_id' in item:
                mal_ids.append(item['mal_id'])
                mal_items_flat.append(item)
            elif 'entry' in item:
                entries = item['entry']
                if isinstance(entries, list):
                    for entry in entries:
                        if 'mal_id' in entry:
                            mal_ids.append(entry['mal_id'])
                            merged = dict(entry)
                            if 'relation' in item:
                                merged['relation'] = item['relation']
                            mal_items_flat.append(merged)
                elif isinstance(entries, dict) and 'mal_id' in entries:
                    mal_ids.append(entries['mal_id'])
                    merged = dict(entries)
                    if 'relation' in item:
                        merged['relation'] = item['relation']
                    mal_items_flat.append(merged)
        return mal_ids, mal_items_flat

    def process_otaku_view(self, mal_res, base_plugin_url, page):
        mal_ids, mal_items_flat = self._flatten_mal_data_items(mal_res)

        anilist_res = self.get_anilist_base_res(mal_ids)
        get_meta.collect_meta(mal_items_flat)
        get_meta.collect_meta(anilist_res)
        anilist_by_mal_id = {item['idMal']: item for item in anilist_res if 'idMal' in item}

        def mapfunc(mal_item):
            mal_id = mal_item.get('mal_id')
            anilist_item = anilist_by_mal_id.get(mal_id)
            return self.base_otaku_view(mal_item, anilist_item, completed=self.open_completed())

        all_results = [mapfunc(mal_item) for mal_item in mal_items_flat]
        if 'pagination' in mal_res:
            has_next = mal_res['pagination'].get('has_next_page', False)
            all_results += self.handle_paging(has_next, base_plugin_url, page)
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

    def _browse_anime_list(self, page, format, prefix, route_slug, extra_params=None, relax_on_empty=False):
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
        }
        if extra_params:
            params.update(extra_params)
        self._apply_anime_type_params(params, format)
        self._apply_content_filters(params)
        mal_res = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        if relax_on_empty and mal_res and not mal_res.get('data'):
            # Jikan treats multiple genre ids as a strict AND filter.
            # For ranked pages this can easily return 0 items; retry without multi-genre filter.
            genres = params.get('genres')
            if isinstance(genres, str) and ',' in genres:
                params_relaxed = dict(params)
                params_relaxed.pop('genres', None)
                mal_res_relaxed = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params_relaxed)
                if mal_res_relaxed and mal_res_relaxed.get('data'):
                    mal_res = mal_res_relaxed
        return self.process_otaku_view(mal_res, self._plugin_page_url(prefix, route_slug), page)

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

    def _ranked_anime_list(self, page, format, prefix, route_slug, order_by, sort, date_mode=None):
        sy = self.get_season_year('')
        extra = {'order_by': order_by, 'sort': sort}
        if date_mode:
            extra.update(self._date_extra_from_bounds(sy, date_mode))
        extra = self._normalize_date_params(extra)
        return self._browse_anime_list(page, format, prefix, route_slug, extra, relax_on_empty=True)

    def _browse_season_airing(self, page, format, prefix, route_slug, period):
        season, year, _, _, _, _, _, _, _, _, _, _, _, _ = self.get_season_year(period)
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
        }
        self._apply_season_format_params(params, format)
        airing = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/seasons/{year}/{season}", params)
        return self.process_otaku_view(airing, self._plugin_page_url(prefix, route_slug), page)

    def _browse_genre_preset(self, page, format, prefix, route_slug, mal_genre_id):
        # Preset genre menus use a fixed MAL genre id; do not merge saved multi-genre settings.
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
        mal_res = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        return self.process_otaku_view(mal_res, self._plugin_page_url(prefix, route_slug), page)

    def get_anime(self, mal_id):
        mal_res = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime/{mal_id}")
        return self.process_res(mal_res['data'])

    def get_recommendations(self, mal_id, page, prefix=None):
        recommendations = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime/{mal_id}/recommendations")
        base_plugin_url = f"{prefix}?page=%d" if prefix else "recommendations?page=%d"
        return self.process_otaku_view(recommendations, base_plugin_url, page)

    def get_relations(self, mal_id, page=1, prefix=None):
        relations = database.get(self.get_mal_base_res, 24, f'{self._BASE_URL}/anime/{mal_id}/relations')
        for item in relations.get('data', []):
            if 'entry' in item and isinstance(item['entry'], list):
                item['entry'] = [entry for entry in item['entry'] if entry.get('type', '').lower() == 'anime']
        base_plugin_url = f"{prefix}?page=%d" if prefix else "relations?page=%d"
        return self.process_otaku_view(relations, base_plugin_url, page)

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

            retry_limit = 3
            for idx, idmal in enumerate(mal_ids):
                retries = 0
                while retries < retry_limit:
                    mal_item = database.get(self.get_mal_base_res, 24, f'{self._BASE_URL}/anime/{idmal}')
                    if mal_item is not None and 'data' in mal_item:
                        watch_order_list.append(mal_item['data'])
                        break
                    retries += 1
                    control.sleep(int(100 * retries))
                if (idx + 1) % 3 == 0:
                    control.sleep(1000)

        mapfunc = partial(self.base_otaku_view, completed=self.open_completed())
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
        res = database.get(self.get_mal_base_res, 24, f'{self._BASE_URL}/anime/{mid}/reviews', params)
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
        res = database.get(self.get_mal_base_res, 24, f'{self._BASE_URL}/anime/{mid}/statistics')
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

        search = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/anime", params)
        base_plugin_url = f"{prefix}/{query}?page=%d" if prefix else f"search_anime/{query}?page=%d"
        return self.process_otaku_view(search, base_plugin_url, page)

    def get_airing_last_season(self, page, format, prefix=None):
        return self._browse_season_airing(page, format, prefix, 'airing_last_season', 'last')

    def get_airing_this_season(self, page, format, prefix=None):
        return self._browse_season_airing(page, format, prefix, 'airing_this_season', 'this')

    def get_airing_next_season(self, page, format, prefix=None):
        return self._browse_season_airing(page, format, prefix, 'airing_next_season', 'next')

    def get_trending_last_year(self, page, format, prefix=None):
        return self._ranked_anime_list(page, format, prefix, 'trending_last_year', 'members', 'desc', 'last_year')

    def get_trending_this_year(self, page, format, prefix=None):
        return self._ranked_anime_list(page, format, prefix, 'trending_this_year', 'members', 'desc', 'this_year')

    def get_trending_last_season(self, page, format, prefix=None):
        return self._ranked_anime_list(page, format, prefix, 'trending_last_season', 'members', 'desc', 'last_season')

    def get_trending_this_season(self, page, format, prefix=None):
        return self._ranked_anime_list(page, format, prefix, 'trending_this_season', 'members', 'desc', 'this_season')

    def get_all_time_trending(self, page, format, prefix=None):
        return self._ranked_anime_list(page, format, prefix, 'all_time_trending', 'members', 'desc')

    def get_popular_last_year(self, page, format, prefix=None):
        return self._ranked_anime_list(page, format, prefix, 'popular_last_year', 'popularity', 'asc', 'last_year')

    def get_popular_this_year(self, page, format, prefix=None):
        return self._ranked_anime_list(page, format, prefix, 'popular_this_year', 'popularity', 'asc', 'this_year')

    def get_popular_last_season(self, page, format, prefix=None):
        return self._ranked_anime_list(page, format, prefix, 'popular_last_season', 'popularity', 'asc', 'last_season')

    def get_popular_this_season(self, page, format, prefix=None):
        return self._ranked_anime_list(page, format, prefix, 'popular_this_season', 'popularity', 'asc', 'this_season')

    def get_all_time_popular(self, page, format, prefix=None):
        return self._ranked_anime_list(page, format, prefix, 'all_time_popular', 'popularity', 'asc')

    def get_voted_last_year(self, page, format, prefix=None):
        return self._ranked_anime_list(page, format, prefix, 'voted_last_year', 'score', 'desc', 'last_year')

    def get_voted_this_year(self, page, format, prefix=None):
        return self._ranked_anime_list(page, format, prefix, 'voted_this_year', 'score', 'desc', 'this_year')

    def get_voted_last_season(self, page, format, prefix=None):
        return self._ranked_anime_list(page, format, prefix, 'voted_last_season', 'score', 'desc', 'last_season')

    def get_voted_this_season(self, page, format, prefix=None):
        return self._ranked_anime_list(page, format, prefix, 'voted_this_season', 'score', 'desc', 'this_season')

    def get_all_time_voted(self, page, format, prefix=None):
        return self._ranked_anime_list(page, format, prefix, 'all_time_voted', 'score', 'desc')

    def get_favourites_last_year(self, page, format, prefix=None):
        return self._ranked_anime_list(page, format, prefix, 'favourites_last_year', 'favorites', 'desc', 'last_year')

    def get_favourites_this_year(self, page, format, prefix=None):
        return self._ranked_anime_list(page, format, prefix, 'favourites_this_year', 'favorites', 'desc', 'this_year')

    def get_favourites_last_season(self, page, format, prefix=None):
        return self._ranked_anime_list(page, format, prefix, 'favourites_last_season', 'favorites', 'desc', 'last_season')

    def get_favourites_this_season(self, page, format, prefix=None):
        return self._ranked_anime_list(page, format, prefix, 'favourites_this_season', 'favorites', 'desc', 'this_season')

    def get_all_time_favourites(self, page, format, prefix=None):
        return self._ranked_anime_list(page, format, prefix, 'all_time_favourites', 'favorites', 'desc')

    def get_top_100(self, page, format, prefix=None):
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult,
        }
        self._apply_anime_type_params(params, format)
        self._apply_content_filters(params)
        top_100 = database.get(self.get_mal_base_res, 24, f"{self._BASE_URL}/top/anime", params)
        return self.process_otaku_view(top_100, self._plugin_page_url(prefix, 'top_100'), page)

    @staticmethod
    def get_mal_base_res(url, params=None):
        for attempt in range(3):
            r = client.get(url, params=params)
            if r:
                return r.json()
            if attempt < 2:
                control.sleep(1000 * (attempt + 1))
        control.log(f'Jikan request failed: {url}', level='warning')

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

        variables = {"page": 1, "malIds": mal_ids, "type": media_type}
        result = client.post(_ANILIST_BASE_URL, json_data={'query': query, 'variables': variables})
        if not result:
            return []
        results = result.json()
        # AniList often returns "data": null; .get("data", {}) still yields None when the key exists.
        page_data = ((results or {}).get('data') or {}).get('Page') or {}
        all_media = page_data.get('media') or []
        has_next = (page_data.get('pageInfo') or {}).get('hasNextPage', False)

        if not has_next:
            return all_media

        def fetch_page(page_num):
            try:
                vars = {"page": page_num, "malIds": mal_ids, "type": media_type}
                resp = client.post(_ANILIST_BASE_URL, json_data={'query': query, 'variables': vars})
                if resp:
                    resp_json = resp.json()
                    return (((resp_json or {}).get('data') or {}).get('Page') or {}).get('media') or []
                return []
            except Exception as e:
                control.log(f"AniList: Failed to fetch page {page_num}: {str(e)}")
                return []

        max_pages = min(5, len(mal_ids) // 50 + 2)

        page_numbers = list(range(2, max_pages + 1))
        all_page_results = utils.parallel_process(page_numbers, fetch_page)

        for page_media in all_page_results:
            if page_media:
                all_media.extend(page_media)
            else:
                break

        control.log(f"AniList: Fetched {len(all_media)} media items total")
        return all_media

    def get_genres(self, page, format):
        mal_res = database.get(self.get_mal_base_res, 24, f'{self._BASE_URL}/genres/anime')

        genre = mal_res['data']
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

        mal_id = mal_res.get('mal_id') if mal_res else (anilist_res.get('idMal') if anilist_res else None)
        anilist_id = anilist_res.get('id') if anilist_res else None

        self.database_update_show(mal_res, anilist_res)

        show_meta = database.get_show_meta(mal_id)
        kodi_meta = pickle.loads(show_meta.get('art')) if show_meta else {}

        title = None
        if mal_res:
            title = mal_res.get('name') or mal_res.get(self.title_lang) or mal_res.get('title')
        if not title and anilist_res:
            title = anilist_res['title'].get(self.title_lang) or anilist_res['title'].get('romaji')
        if title is None:
            title = ''

        if mal_res and mal_res.get('relation'):
            title += ' [I]%s[/I]' % control.colorstr(mal_res['relation'], 'limegreen')
        elif anilist_res and anilist_res.get('relationType'):
            title += ' [I]%s[/I]' % control.colorstr(anilist_res['relationType'], 'limegreen')

        plot = mal_res.get('synopsis') if mal_res and mal_res.get('synopsis') else None
        if not plot and anilist_res and anilist_res.get('description'):
            desc = anilist_res['description']
            desc = desc.replace('<i>', '[I]').replace('</i>', '[/I]')
            desc = desc.replace('<b>', '[B]').replace('</b>', '[/B]')
            desc = desc.replace('<br>', '[CR]')
            desc = desc.replace('\n', '')
            plot = desc

        genre = [x['name'] for x in mal_res.get('genres', [])] if mal_res else None
        if not genre and anilist_res:
            genre = anilist_res.get('genres')

        studio = [x['name'] for x in mal_res.get('studios', [])] if mal_res else None
        if not studio and anilist_res:
            studio = [x['node'].get('name') for x in anilist_res['studios']['edges']]

        status = mal_res.get('status') if mal_res else None
        if not status and anilist_res:
            status = anilist_res.get('status')

        duration = self.duration_to_seconds(mal_res.get('duration')) if mal_res and mal_res.get('duration') else None
        if not duration and anilist_res and anilist_res.get('duration'):
            duration = anilist_res['duration'] * 60

        country = None
        if anilist_res:
            country = [anilist_res.get('countryOfOrigin', '')]

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

        playcount = None
        if completed and completed.get(str(mal_id)):
            playcount = 1

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

        dub = True if mal_dub and mal_dub.get(str(mal_id)) else False

        image = None
        poster = None
        fanart = None

        if mal_res and mal_res.get('images'):
            image = mal_res['images']['webp'].get('large_image_url')
            poster = image
            fanart = kodi_meta['fanart'] if kodi_meta.get('fanart') else image
        if not image and anilist_res and anilist_res.get('coverImage'):
            image = anilist_res['coverImage'].get('extraLarge')
        if not poster and anilist_res and anilist_res.get('coverImage'):
            poster = anilist_res['coverImage'].get('extraLarge')
        if not fanart and anilist_res and anilist_res.get('coverImage'):
            fanart = anilist_res['coverImage'].get('extraLarge')

        base = {
            "name": title,
            "url": f'animes/{mal_id}/',
            "image": image,
            "poster": poster,
            'fanart': fanart,
            "info": info
        }

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

        episodes = mal_res.get('episodes') or (anilist_res.get('episodes') if anilist_res else None)

        if episodes == 1:
            base['url'] = f'play_movie/{mal_id}/'
            base['info']['mediatype'] = 'movie'
            return utils.parse_view(base, False, True, dub)
        return utils.parse_view(base, True, False, dub)

    def database_update_show(self, mal_res=None, anilist_res=None):
        """
        Combines MAL and AniList data for database update.
        Uses MAL as primary, fills missing fields from AniList if available.
        """
        mal_id = None
        if mal_res and 'mal_id' in mal_res:
            mal_id = mal_res['mal_id']
        elif anilist_res and 'idMal' in anilist_res:
            mal_id = anilist_res['idMal']
        if not mal_id:
            return

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
        if name and ename:
            titles = f"({name})|({ename})"
        elif name:
            titles = f"({name})"
        elif ename:
            titles = f"({ename})"
        else:
            titles = ''

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

        episodes = mal_res.get('episodes') if mal_res and 'episodes' in mal_res else (anilist_res.get('episodes') if anilist_res and 'episodes' in anilist_res else None)

        poster = None
        if mal_res and mal_res.get('images') and mal_res['images'].get('webp'):
            poster = mal_res['images']['webp'].get('large_image_url')
        if not poster and anilist_res and anilist_res.get('coverImage'):
            poster = anilist_res['coverImage'].get('extraLarge')

        status = mal_res.get('status') if mal_res and 'status' in mal_res else (anilist_res.get('status') if anilist_res and 'status' in anilist_res else None)

        format_ = mal_res.get('type') if mal_res and 'type' in mal_res else (anilist_res.get('format') if anilist_res and 'format' in anilist_res else '')

        plot = mal_res.get('synopsis') if mal_res and 'synopsis' in mal_res else None
        if not plot and anilist_res and anilist_res.get('description'):
            desc = anilist_res['description']
            desc = desc.replace('<i>', '[I]').replace('</i>', '[/I]')
            desc = desc.replace('<b>', '[B]').replace('</b>', '[/B]')
            desc = desc.replace('<br>', '[CR]')
            desc = desc.replace('\n', '')
            plot = desc

        duration = self.duration_to_seconds(mal_res.get('duration')) if mal_res and 'duration' in mal_res else None
        if not duration and anilist_res and 'duration' in anilist_res and anilist_res['duration'] is not None:
            duration = anilist_res['duration'] * 60

        genre = [x['name'] for x in mal_res.get('genres', [])] if mal_res else None
        if not genre and anilist_res:
            genre = anilist_res.get('genres')

        studio = [x['name'] for x in mal_res.get('studios', [])] if mal_res else None
        if not studio and anilist_res and anilist_res.get('studios'):
            studio = [x['node'].get('name') for x in anilist_res['studios']['edges']]

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

        multiselect = control.multiselect_dialog(control.lang(30040), genres_list, preselect=[])
        if not multiselect:
            return []

        selected_genres_mal = [str(genre[selection]['mal_id']) for selection in multiselect if selection < len(genres_list)]

        selected_genres_anilist = []

        selected_tags = []

        return selected_genres_mal, selected_genres_anilist, selected_tags


def _install_genre_methods():
    """Attach get_genre_* methods expected by Main._draw_genre_page (one-liners)."""
    for slug, gid in _MAL_GENRE_PRESETS:
        def make_genre(_slug, _gid):
            def method(self, page, format, prefix=None):
                return self._browse_genre_preset(page, format, prefix, f'genre_{_slug}', _gid)
            method.__name__ = f'get_genre_{_slug}'
            method.__doc__ = f'Browse anime with MAL genre preset {_slug} (id {_gid}).'
            return method
        setattr(OtakuBrowser, f'get_genre_{slug}', make_genre(slug, gid))


_install_genre_methods()
