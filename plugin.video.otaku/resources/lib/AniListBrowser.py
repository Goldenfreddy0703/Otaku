import ast
import datetime
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

# Route slug -> AniList GenreCollection name (preset menus; not merged with saved genre filters)
_ANILIST_GENRE_PRESETS = (
    ('action', 'Action'),
    ('adventure', 'Adventure'),
    ('comedy', 'Comedy'),
    ('drama', 'Drama'),
    ('ecchi', 'Ecchi'),
    ('fantasy', 'Fantasy'),
    ('hentai', 'Hentai'),
    ('horror', 'Horror'),
    ('shoujo', 'Shoujo'),
    ('mecha', 'Mecha'),
    ('music', 'Music'),
    ('mystery', 'Mystery'),
    ('psychological', 'Psychological'),
    ('romance', 'Romance'),
    ('sci_fi', 'Sci-Fi'),
    ('slice_of_life', 'Slice of Life'),
    ('sports', 'Sports'),
    ('supernatural', 'Supernatural'),
    ('thriller', 'Thriller'),
)


def _apply_mal_picture_to_anime(anime):
    """Replace cover with MAL CDN image when a mapping exists (setting general.malposters)."""
    if not anime or not control.getBool('general.malposters'):
        return
    try:
        anilist_id = anime['id']
        mal_mapping = database.get_mappings(anilist_id, 'anilist_id')
        if mal_mapping and 'mal_picture' in mal_mapping:
            mal_picture = mal_mapping['mal_picture']
            mal_picture_url = mal_picture.rsplit('.', 1)[0] + 'l.' + mal_picture.rsplit('.', 1)[1]
            mal_picture_url = 'https://cdn.myanimelist.net/images/anime/' + mal_picture_url
            anime['coverImage']['extraLarge'] = mal_picture_url
    except Exception:
        pass


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


    def _plugin_page_url(self, prefix, route_slug):
        return f"{prefix}?page=%d" if prefix else f"{route_slug}?page=%d"

    @staticmethod
    def _coerce_anilist_media_format(fmt):
        """GraphQL format_in expects [MediaFormat], not a single enum string."""
        if isinstance(fmt, list):
            return fmt
        return [fmt]

    def _apply_common_list_variables(self, variables, format):
        if format:
            variables['format'] = self._coerce_anilist_media_format(format)
        elif self.format_in_type:
            variables['format'] = self._coerce_anilist_media_format(self.format_in_type)
        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type
        if self.status:
            variables['status'] = self.status
        if self.genre:
            variables['includedGenres'] = self.genre
        if self.tag:
            variables['includedTags'] = self.tag

    def _fetch_page_and_process(self, variables, prefix, route_slug, page, format):
        self._apply_common_list_variables(variables, format)
        data = database.get(self.get_base_res, 24, variables)
        return self.process_anilist_view(data, self._plugin_page_url(prefix, route_slug), page)

    def _browse_season_airing(self, page, format, prefix, route_slug, period, sort):
        season, year = self.get_season_year(period)
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': 'ANIME',
            'season': season,
            'year': f'{year}%',
            'sort': sort,
        }
        return self._fetch_page_and_process(variables, prefix, route_slug, page, format)

    def _ranked_media_list(self, page, format, prefix, route_slug, sort, period_mode='all_time'):
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': 'ANIME',
            'sort': sort,
        }
        if period_mode == 'last_year':
            _, year = self.get_season_year('')
            variables['year'] = f'{year - 1}%'
        elif period_mode == 'this_year':
            _, year = self.get_season_year('')
            variables['year'] = f'{year}%'
        elif period_mode == 'last_season':
            season, year = self.get_season_year('last')
            variables['season'] = season
            variables['year'] = f'{year}%'
        elif period_mode == 'this_season':
            season, year = self.get_season_year('this')
            variables['season'] = season
            variables['year'] = f'{year}%'
        elif period_mode != 'all_time':
            raise ValueError(period_mode)
        return self._fetch_page_and_process(variables, prefix, route_slug, page, format)

    def _browse_genre_preset(self, page, format, prefix, route_slug, genre_name):
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': 'ANIME',
            'includedGenres': genre_name,
            'sort': 'POPULARITY_DESC',
        }
        if format:
            variables['format'] = self._coerce_anilist_media_format(format)
        elif self.format_in_type:
            variables['format'] = self._coerce_anilist_media_format(self.format_in_type)
        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type
        if self.status:
            variables['status'] = self.status
        data = database.get(self.get_base_res, 24, variables)
        return self.process_anilist_view(data, self._plugin_page_url(prefix, route_slug), page)

    def get_airing_last_season(self, page, format, prefix=None):
        return self._browse_season_airing(page, format, prefix, 'airing_last_season', 'last', 'TRENDING_DESC')

    def get_airing_this_season(self, page, format, prefix=None):
        return self._browse_season_airing(page, format, prefix, 'airing_this_season', 'this', 'POPULARITY_DESC')

    def get_airing_next_season(self, page, format, prefix=None):
        return self._browse_season_airing(page, format, prefix, 'airing_next_season', 'next', 'POPULARITY_DESC')

    def get_trending_last_year(self, page, format, prefix=None):
        return self._ranked_media_list(page, format, prefix, 'trending_last_year', 'TRENDING_DESC', 'last_year')

    def get_trending_this_year(self, page, format, prefix=None):
        return self._ranked_media_list(page, format, prefix, 'trending_this_year', 'TRENDING_DESC', 'this_year')

    def get_trending_last_season(self, page, format, prefix=None):
        return self._ranked_media_list(page, format, prefix, 'trending_last_season', 'TRENDING_DESC', 'last_season')

    def get_trending_this_season(self, page, format, prefix=None):
        return self._ranked_media_list(page, format, prefix, 'trending_this_season', 'TRENDING_DESC', 'this_season')

    def get_all_time_trending(self, page, format, prefix=None):
        return self._ranked_media_list(page, format, prefix, 'all_time_trending', 'TRENDING_DESC', 'all_time')

    def get_popular_last_year(self, page, format, prefix=None):
        return self._ranked_media_list(page, format, prefix, 'popular_last_year', 'POPULARITY_DESC', 'last_year')

    def get_popular_this_year(self, page, format, prefix=None):
        return self._ranked_media_list(page, format, prefix, 'popular_this_year', 'POPULARITY_DESC', 'this_year')

    def get_popular_last_season(self, page, format, prefix=None):
        return self._ranked_media_list(page, format, prefix, 'popular_last_season', 'POPULARITY_DESC', 'last_season')

    def get_popular_this_season(self, page, format, prefix=None):
        return self._ranked_media_list(page, format, prefix, 'popular_this_season', 'POPULARITY_DESC', 'this_season')

    def get_all_time_popular(self, page, format, prefix=None):
        return self._ranked_media_list(page, format, prefix, 'all_time_popular', 'POPULARITY_DESC', 'all_time')

    def get_voted_last_year(self, page, format, prefix=None):
        return self._ranked_media_list(page, format, prefix, 'voted_last_year', 'SCORE_DESC', 'last_year')

    def get_voted_this_year(self, page, format, prefix=None):
        return self._ranked_media_list(page, format, prefix, 'voted_this_year', 'SCORE_DESC', 'this_year')

    def get_voted_last_season(self, page, format, prefix=None):
        return self._ranked_media_list(page, format, prefix, 'voted_last_season', 'SCORE_DESC', 'last_season')

    def get_voted_this_season(self, page, format, prefix=None):
        return self._ranked_media_list(page, format, prefix, 'voted_this_season', 'SCORE_DESC', 'this_season')

    def get_all_time_voted(self, page, format, prefix=None):
        return self._ranked_media_list(page, format, prefix, 'all_time_voted', 'SCORE_DESC', 'all_time')

    def get_favourites_last_year(self, page, format, prefix=None):
        return self._ranked_media_list(page, format, prefix, 'favourites_last_year', 'FAVOURITES_DESC', 'last_year')

    def get_favourites_this_year(self, page, format, prefix=None):
        return self._ranked_media_list(page, format, prefix, 'favourites_this_year', 'FAVOURITES_DESC', 'this_year')

    def get_favourites_last_season(self, page, format, prefix=None):
        return self._ranked_media_list(page, format, prefix, 'favourites_last_season', 'FAVOURITES_DESC', 'last_season')

    def get_favourites_this_season(self, page, format, prefix=None):
        return self._ranked_media_list(page, format, prefix, 'favourites_this_season', 'FAVOURITES_DESC', 'this_season')

    def get_all_time_favourites(self, page, format, prefix=None):
        return self._ranked_media_list(page, format, prefix, 'all_time_favourites', 'FAVOURITES_DESC', 'all_time')

    def get_top_100(self, page, format, prefix=None):
        variables = {
            'page': page,
            'perpage': self.perpage,
            'type': 'ANIME',
            'sort': 'SCORE_DESC',
        }
        return self._fetch_page_and_process(variables, prefix, 'top_100', page, format)

    def get_search(self, query, page, format, prefix=None):
        variables = {
            'page': page,
            'perpage': self.perpage,
            'search': query,
            'sort': "SEARCH_MATCH",
            'type': "ANIME"
        }

        if format:
            variables['format'] = self._coerce_anilist_media_format(format)
        elif self.format_in_type:
            variables['format'] = self._coerce_anilist_media_format(self.format_in_type)

        search = self.get_search_res(variables)
        if not search:
            search = {'ANIME': [], 'pageInfo': {'hasNextPage': False}}
        if control.getBool('search.adult'):
            variables['isAdult'] = True
            search_adult = self.get_search_res(variables)
            if search_adult and search_adult.get('ANIME'):
                for i in search_adult['ANIME']:
                    i['title']['english'] = f'{i["title"]["english"]} - {control.colorstr("Adult", "red")}'
                search['ANIME'] = (search.get('ANIME') or []) + search_adult['ANIME']
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
            mal_links = soup.find_all('a', href=re.compile(r'https://myanimelist\.net/anime/\d+'))
            mal_ids = []
            for link in mal_links:
                m = re.search(r'\d+', link['href'])
                if m:
                    mal_ids.append(m.group())
            for idmal in mal_ids:
                variables = {
                    'idMal': int(idmal),
                    'type': "ANIME"
                }

                anilist_item = database.get(self.get_anilist_res_with_mal_id, 24, variables)
                if anilist_item is not None:
                    watch_order_list.append(anilist_item)

        return self.process_watch_order_view(watch_order_list)

    @staticmethod
    def _normalize_anilist_review_node(node):
        user = node.get('user') or {}
        name = user.get('name') or 'Anonymous'
        avatar = (user.get('avatar') or {}).get('large') or control.OTAKU_LOGO3_PATH
        body = node.get('body') or node.get('summary') or ''
        body = re.sub(r'<br\s*/?>', '\n', body, flags=re.I)
        body = re.sub(r'<[^>]+>', '', body)
        rating = node.get('rating')
        tag_list = [str(rating)] if rating else []
        created = node.get('createdAt')
        if isinstance(created, int):
            date_short = datetime.datetime.utcfromtimestamp(created).strftime('%Y-%m-%d')
        else:
            created_text = str(created or '')
            date_short = created_text[:10] if len(created_text) >= 10 else created_text
        score = node.get('score')
        if score is None:
            score_disp = '?'
        elif isinstance(score, int) and score > 10:
            score_disp = f'{score}/100'
        else:
            score_disp = score
        return {
            'user': {'username': name, 'images': {'jpg': {'image_url': avatar}}},
            'score': score_disp,
            'tags': tag_list,
            'date': date_short,
            'is_spoiler': False,
            'is_preliminary': False,
            'reactions': {
                'nice': 0, 'love_it': 0, 'funny': 0, 'informative': 0,
                'well_written': 0, 'creative': 0,
            },
            'review': body,
        }

    def get_media_reviews_res(self, variables):
        query = '''
        query ($idMal: Int, $page: Int, $perPage: Int) {
          Media(idMal: $idMal, type: ANIME) {
            reviews(page: $page, perPage: $perPage, sort: [ID_DESC]) {
              pageInfo {
                hasNextPage
                currentPage
              }
              edges {
                node {
                  summary
                  body
                  score
                  rating
                  createdAt
                  user {
                    name
                    avatar {
                      large
                    }
                  }
                }
              }
            }
          }
        }
        '''
        response = client.post(self._BASE_URL, json_data={'query': query, 'variables': variables})
        if not response:
            return None
        results = response.json()
        if not results or results.get('errors'):
            return None
        return results.get('data', {}).get('Media')

    def get_media_stats_res(self, variables):
        query = '''
        query ($idMal: Int) {
          Media(idMal: $idMal, type: ANIME) {
            stats {
              statusDistribution {
                status
                amount
              }
              scoreDistribution {
                score
                amount
              }
            }
          }
        }
        '''
        response = client.post(self._BASE_URL, json_data={'query': query, 'variables': variables})
        if not response:
            return None
        results = response.json()
        if not results or results.get('errors'):
            return None
        media = results.get('data', {}).get('Media')
        if not media:
            return None
        return media.get('stats')

    def _map_anilist_stats_to_stats_window(self, stats):
        if not stats:
            return None
        status_distribution = stats.get('statusDistribution') or []
        sums = {'watching': 0, 'completed': 0, 'on_hold': 0, 'dropped': 0, 'plan_to_watch': 0}
        status_key = {
            'CURRENT': 'watching',
            'PLANNING': 'plan_to_watch',
            'COMPLETED': 'completed',
            'DROPPED': 'dropped',
            'PAUSED': 'on_hold',
        }
        for row in status_distribution:
            st = row.get('status')
            amt = int(row.get('amount') or 0)
            key = status_key.get(st)
            if key:
                sums[key] += amt
        total = sum(sums.values())
        score_dist = stats.get('scoreDistribution') or []
        buckets = {i: {'score': i, 'votes': 0, 'percentage': 0.0} for i in range(1, 11)}
        for entry in score_dist:
            s = entry.get('score')
            if s is None:
                continue
            try:
                si = int(s)
            except (TypeError, ValueError):
                continue
            amt = int(entry.get('amount') or 0)
            if si % 10 == 0 and 10 <= si <= 100:
                bin_idx = si // 10
            elif 1 <= si <= 10:
                bin_idx = si
            else:
                bin_idx = max(1, min(10, (si + 9) // 10))
            buckets[bin_idx]['votes'] += amt
        total_score_votes = sum(buckets[i]['votes'] for i in range(1, 11))
        for i in range(1, 11):
            v = buckets[i]['votes']
            buckets[i]['percentage'] = round((v / total_score_votes) * 100, 1) if total_score_votes else 0.0
        scores_list = [buckets[i] for i in range(1, 11)]
        return {
            'watching': sums['watching'],
            'completed': sums['completed'],
            'on_hold': sums['on_hold'],
            'dropped': sums['dropped'],
            'plan_to_watch': sums['plan_to_watch'],
            'total': total,
            'scores': scores_list,
        }

    def refetch_reviews_page(self, mal_id, page):
        try:
            mid = int(mal_id)
        except (TypeError, ValueError):
            return None
        per_page = min(max(self.perpage, 1), 50)
        variables = {'idMal': mid, 'page': page, 'perPage': per_page}
        media = database.get(self.get_media_reviews_res, 24, variables)
        if not media:
            return None
        rev = media.get('reviews') or {}
        edges = rev.get('edges') or []
        nodes = [e.get('node') for e in edges if e.get('node')]
        return [self._normalize_anilist_review_node(n) for n in nodes]

    def get_reviews_page(self, mal_id, page, path, eps_watched):
        try:
            mid = int(mal_id)
        except (TypeError, ValueError):
            return None
        per_page = min(max(self.perpage, 1), 50)
        variables = {'idMal': mid, 'page': page, 'perPage': per_page}
        media = database.get(self.get_media_reviews_res, 24, variables)
        if not media:
            return None
        rev = media.get('reviews') or {}
        edges = rev.get('edges') or []
        nodes = [e.get('node') for e in edges if e.get('node')]
        reviews = [self._normalize_anilist_review_node(n) for n in nodes]
        page_info = rev.get('pageInfo') or {}
        has_next = page_info.get('hasNextPage', False)
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
            date = (review.get('date') or '')[:10]
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
        variables = {'idMal': mid}
        raw_stats = database.get(self.get_media_stats_res, 24, variables)
        if not raw_stats:
            return None
        return self._map_anilist_stats_to_stats_window(raw_stats)

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

        if json_res and json_res.get('ANIME'):
            for anime in json_res['ANIME']:
                _apply_mal_picture_to_anime(anime)

        if json_res:
            return json_res

    def get_search_res(self, variables):
        query = '''
        query (
            $page: Int=1,
            $perpage: Int=20,
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

        if json_res and json_res.get('ANIME'):
            for anime in json_res['ANIME']:
                _apply_mal_picture_to_anime(anime)

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

        if json_res and json_res.get('edges'):
            for recommendation in json_res['edges']:
                anime = recommendation.get('node', {}).get('mediaRecommendation')
                if anime:
                    _apply_mal_picture_to_anime(anime)

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

        if json_res and json_res.get('edges'):
            for relation in json_res['edges']:
                _apply_mal_picture_to_anime(relation.get('node'))

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
        if not json_res or not json_res.get('ANIME'):
            return []
        has_next = json_res.get('pageInfo', {}).get('hasNextPage', False)
        get_meta.collect_meta(json_res['ANIME'])
        mapfunc = partial(self.base_anilist_view, completed=self.open_completed())
        all_results = [x for x in map(mapfunc, json_res['ANIME']) if x]
        all_results += self.handle_paging(has_next, base_plugin_url, page)
        return all_results

    def process_recommendations_view(self, json_res, base_plugin_url, page):
        if not json_res or not json_res.get('edges'):
            return []
        has_next = json_res.get('pageInfo', {}).get('hasNextPage', False)
        res = [edge['node']['mediaRecommendation'] for edge in json_res['edges'] if edge['node'].get('mediaRecommendation')]
        get_meta.collect_meta(res)
        mapfunc = partial(self.base_anilist_view, completed=self.open_completed())
        all_results = [x for x in map(mapfunc, res) if x]
        all_results += self.handle_paging(has_next, base_plugin_url, page)
        return all_results

    def process_relations_view(self, json_res):
        if not json_res or not json_res.get('edges'):
            return []
        res = []
        for edge in json_res['edges']:
            if edge['relationType'] != 'ADAPTATION':
                tnode = edge['node']
                tnode['relationType'] = edge['relationType']
                res.append(tnode)
        get_meta.collect_meta(res)
        mapfunc = partial(self.base_anilist_view, completed=self.open_completed())
        return [x for x in map(mapfunc, res) if x]

    def process_watch_order_view(self, json_res):
        res = json_res or []
        get_meta.collect_meta(res)
        mapfunc = partial(self.base_anilist_view, completed=self.open_completed())
        return [x for x in map(mapfunc, res) if x]

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

        info['duration'] = control.safe_call(lambda: res['duration'] * 60)

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
        if res['episodes'] == 1:
            base['url'] = f'play_movie/{mal_id}/'
            base['info']['mediatype'] = 'movie'
            return utils.parse_view(base, False, True, dub)
        return utils.parse_view(base, True, False, dub)

    def database_update_show(self, res):
        mal_id = res.get('idMal')

        if not mal_id:
            return

        start_date = control.safe_call(lambda: '{}-{:02}-{:02}'.format(res['startDate']['year'], res['startDate']['month'], res['startDate']['day']))

        duration = control.safe_call(lambda: res['duration'] * 60, default=0)

        title_userPreferred = res['title'][self.title_lang] or res['title']['romaji']

        name = res['title']['romaji']
        ename = res['title']['english']
        if name and ename:
            titles = f"({name})|({ename})"
        elif name:
            titles = f"({name})"
        elif ename:
            titles = f"({ename})"
        else:
            titles = ''

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
        tags_list = control.safe_call(lambda: [x['name'] for x in results['data']['tags'] if not x['isAdult']], default=[])
        multiselect = control.multiselect_dialog(control.lang(30040), genres_list + tags_list, preselect=[])
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
            variables['format'] = self._coerce_anilist_media_format(format)
        elif self.format_in_type:
            variables['format'] = self._coerce_anilist_media_format(self.format_in_type)

        if self.countryOfOrigin_type:
            variables['countryOfOrigin'] = self.countryOfOrigin_type

        if self.status:
            variables['status'] = self.status

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

        for anime in anime_res:
            _apply_mal_picture_to_anime(anime)

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

        tags_list = control.safe_call(lambda: [x['name'] for x in results['data']['tags'] if not x['isAdult']], default=[])

        multiselect = control.multiselect_dialog(control.lang(30040), genres_list + tags_list, preselect=[])
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


def _install_anilist_genre_methods():
    for slug, genre_name in _ANILIST_GENRE_PRESETS:
        def make_genre(_slug, _name):
            def method(self, page, format, prefix=None):
                return self._browse_genre_preset(page, format, prefix, f'genre_{_slug}', _name)
            method.__name__ = f'get_genre_{_slug}'
            method.__doc__ = f'Browse anime by AniList genre preset {_name}.'
            return method
        setattr(AniListBrowser, f'get_genre_{slug}', make_genre(slug, genre_name))


_install_anilist_genre_methods()
