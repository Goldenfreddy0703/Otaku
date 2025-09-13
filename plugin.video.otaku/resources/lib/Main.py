# -*- coding: utf-8 -*-
"""
    Otaku Add-on

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import pickle
import json
import ast
import sys

from resources.lib import MetaBrowser
from resources.lib.ui import control, database, utils
from resources.lib.ui.router import Route
from resources.lib.WatchlistIntegration import add_watchlist

BROWSER = MetaBrowser.BROWSER
plugin_url = control.get_plugin_url(sys.argv[0])


def add_last_watched(items):
    # # Check if last watched feature is enabled
    # if not control.getBool("interface.show_last_watched"):
    #     return items

    mal_id = control.getSetting("addon.last_watched")
    try:
        kodi_meta = pickle.loads(database.get_show(mal_id)['kodi_meta'])
        last_watched = "%s[I]%s[/I]" % (control.lang(30000), kodi_meta['title_userPreferred'])
        info = {
            'UniqueIDs': {
                'mal_id': mal_id,
                **database.get_unique_ids(mal_id, 'mal_id')
            },
            'title': kodi_meta.get('title_userPreferred', ''),
            'plot': kodi_meta.get('plot', ''),
            'mpaa': kodi_meta.get('mpaa', ''),
            'duration': kodi_meta.get('duration', 0),
            'genre': kodi_meta.get('genre', []),
            'studio': kodi_meta.get('studio', []),
            'status': kodi_meta.get('status', ''),
            'mediatype': 'tvshow',
            'rating': kodi_meta.get('rating', {}),
            'cast': kodi_meta.get('cast', []),
            'country': kodi_meta.get('country', []),
            'trailer': kodi_meta.get('trailer', ''),
            'year': kodi_meta.get('year', ''),
            'premiered': kodi_meta.get('premiered', ''),
            'episodes': kodi_meta.get('episodes', 0),
        }

        # Simple movie detection: if episodes == 1, treat as movie
        episodes = kodi_meta.get('episodes', 0)
        if episodes == 1:
            url = f'play_movie/{mal_id}/'
            info['mediatype'] = 'movie'
        else:
            url = f'animes/{mal_id}/'

        # Return tuple with special marker for last_watched items
        items.append(('LAST_WATCHED_ITEM', last_watched, url, kodi_meta.get('poster', ''), info, kodi_meta))

    except TypeError:
        pass

    return items


def add_watch_history(items):
    # # Check if watch history feature is enabled
    # if not control.getBool("interface.show_watch_history"):
    #     return items

    try:
        # Load watch history from JSON file
        if not control.pathExists(control.watch_history_json):
            return items

        with open(control.watch_history_json, 'r', encoding='utf-8') as f:
            history_data = json.load(f)

        # Get the most recent entries (limit to last 10 for menu)
        recent_history = history_data.get('history', [])[:10]

        if recent_history:
            # Add a "Watch History" menu item that shows recent watches
            history_title = "%s[I]%s[/I]" % (control.lang(30001), "Watch History")  # You may need to add this lang string

            # Use a generic anime icon or create a custom one for history
            history_info = {
                'title': 'Watch History',
                'plot': 'View your recently watched anime',
                'mediatype': 'tvshow',
            }

            items.append((history_title, 'watch_history/', 'watch_history.png', history_info))

    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        pass

    return items


def save_to_watch_history(mal_id):
    """Save an anime to watch history"""
    # if not control.getBool("interface.show_watch_history"):
    #     return

    try:
        # Load existing history or create new
        if control.pathExists(control.watch_history_json):
            with open(control.watch_history_json, 'r', encoding='utf-8') as f:
                history_data = json.load(f)
        else:
            history_data = {'history': []}

        # Get anime metadata
        anime_data = database.get_show(mal_id)
        if not anime_data:
            return

        kodi_meta = pickle.loads(anime_data['kodi_meta'])

        # Create history entry with the same info as add_last_watched
        history_entry = {
            'UniqueIDs': {
                'mal_id': mal_id,
                **database.get_unique_ids(mal_id, 'mal_id')
            },
            'title': kodi_meta.get('title_userPreferred', ''),
            'plot': kodi_meta.get('plot', ''),
            'mpaa': kodi_meta.get('mpaa', ''),
            'duration': kodi_meta.get('duration', 0),
            'genre': kodi_meta.get('genre', []),
            'studio': kodi_meta.get('studio', []),
            'status': kodi_meta.get('status', ''),
            'mediatype': 'tvshow',
            'rating': kodi_meta.get('rating', {}),
            'cast': kodi_meta.get('cast', []),
            'country': kodi_meta.get('country', []),
            'trailer': kodi_meta.get('trailer', ''),
            'year': kodi_meta.get('year', ''),
            'premiered': kodi_meta.get('premiered', ''),
            'episodes': kodi_meta.get('episodes', 0),
            # Artwork
            'poster': kodi_meta.get('poster', ''),
            'tvshow.poster': kodi_meta.get('poster', ''),
            'icon': kodi_meta.get('poster', ''),
            'thumb': kodi_meta.get('thumb', ''),
            'fanart': kodi_meta.get('fanart', ''),
            'landscape': kodi_meta.get('landscape', ''),
            'banner': kodi_meta.get('poster', ''),  # Use poster as fallback for banner
            'clearart': kodi_meta.get('clearart', ''),
            'clearlogo': kodi_meta.get('clearlogo', '')
        }

        # Remove any existing entry for this anime to avoid duplicates
        history_data['history'] = [h for h in history_data['history'] if str(h.get('UniqueIDs', {}).get('mal_id')) != str(mal_id)]

        # Add new entry at the beginning
        history_data['history'].insert(0, history_entry)

        # Save back to file
        with open(control.watch_history_json, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, ensure_ascii=False, indent=2)

    except Exception as e:
        control.log(f"Error saving to watch history: {str(e)}", "error")


@Route('animes/*')
def ANIMES_PAGE(payload, params):
    mal_id, eps_watched = payload.rsplit("/")
    anime_general, content = MetaBrowser.get_anime_init(mal_id)
    control.draw_items(anime_general, content)


@Route('find_recommendations/*')
def FIND_RECOMMENDATIONS(payload, params):
    path, mal_id, eps_watched = payload.rsplit("/")
    page = int(params.get('page', 1))
    control.draw_items(BROWSER.get_recommendations(mal_id, page), 'tvshows')


@Route('find_relations/*')
def FIND_RELATIONS(payload, params):
    path, mal_id, eps_watched = payload.rsplit("/")
    control.draw_items(BROWSER.get_relations(mal_id), 'tvshows')


@Route('watch_order/*')
def WATCH_ORDER(payload, params):
    path, mal_id, eps_watched = payload.rsplit("/")
    control.draw_items(BROWSER.get_watch_order(mal_id), 'tvshows')


@Route('watch_history/')
def WATCH_HISTORY(payload, params):
    """Display watch history"""
    try:
        if not control.pathExists(control.watch_history_json):
            control.draw_items([], 'tvshows')
            return

        with open(control.watch_history_json, 'r', encoding='utf-8') as f:
            history_data = json.load(f)

        history_items = []
        for entry in history_data.get('history', []):
            try:
                # Get the mal_id from the correct location
                mal_id = entry['UniqueIDs']['mal_id']

                # Format title
                title = entry.get('title', '')

                info = {
                    'UniqueIDs': entry.get('UniqueIDs', {}),
                    'title': entry.get('title', ''),
                    'plot': entry.get('plot', ''),
                    'mpaa': entry.get('mpaa', ''),
                    'duration': entry.get('duration', 0),
                    'genre': entry.get('genre', []),
                    'studio': entry.get('studio', []),
                    'status': entry.get('status', ''),
                    'mediatype': 'tvshow',  # Default to tvshow
                    'rating': entry.get('rating', {}),
                    'cast': entry.get('cast', []),
                    'country': entry.get('country', []),
                    'trailer': entry.get('trailer', ''),
                    'year': entry.get('year', ''),
                    'premiered': entry.get('premiered', ''),
                    'episodes': entry.get('episodes', 0),
                }

                # Build the base item like MalBrowser does
                base = {
                    'name': title,
                    'url': f'animes/{mal_id}/',
                    'image': entry.get('poster', ''),
                    'poster': entry.get('poster', ''),
                    'fanart': entry.get('fanart', ''),
                    'banner': entry.get('poster', ''),  # Use poster as fallback for banner
                    'info': info
                }

                import random
                if entry.get('thumb'):
                    base['landscape'] = random.choice(entry['thumb'])
                if entry.get('clearart'):
                    base['clearart'] = random.choice(entry['clearart'])
                if entry.get('clearlogo'):
                    base['clearlogo'] = random.choice(entry['clearlogo'])

                # Simple movie detection: if episodes == 1, treat as movie
                episodes = entry.get('episodes', 0)

                if episodes == 1:
                    base['url'] = f'play_movie/{mal_id}/'
                    base['info']['mediatype'] = 'movie'
                    parsed_item = utils.parse_view(base, False, True, False)  # dub = False for now
                else:
                    parsed_item = utils.parse_view(base, True, False, False)   # dub = False for now

                history_items.append(parsed_item)

            except Exception as e:
                control.log(f"Error processing history entry: {str(e)}", "error")
                continue

        control.draw_items(history_items, 'tvshows')

    except Exception as e:
        control.log(f"Error loading watch history: {str(e)}", "error")
        control.draw_items([], 'tvshows')


@Route('airing_calendar')
def AIRING_CALENDAR(payload: str, params: dict):
    page = int(params.get('page', 1))
    calendar = BROWSER.get_airing_calendar(page)
    if calendar:
        from resources.lib.windows.anichart import Anichart
        Anichart('anichart.xml', control.ADDON_PATH, calendar=calendar).doModal()
    control.exit_code()


@Route('airing_last_season')
@Route('airing_last_season_tv_show')
@Route('airing_last_season_movie')
@Route('airing_last_season_tv_short')
@Route('airing_last_season_special')
@Route('airing_last_season_ova')
@Route('airing_last_season_ona')
@Route('airing_last_season_music')
def AIRING_LAST_SEASON(payload, params):
    mapping = {
        'airing_last_season_tv_show': ('tv', 'TV'),
        'airing_last_season_movie': ('movie', 'MOVIE'),
        'airing_last_season_tv_short': ('tv_special', 'TV_SHORT'),
        'airing_last_season_special': ('special', 'SPECIAL'),
        'airing_last_season_ova': ('ova', 'OVA'),
        'airing_last_season_ona': ('ona', 'ONA'),
        'airing_last_season_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_airing_last_season(page, format, prefix), 'tvshows')


@Route('airing_this_season')
@Route('airing_this_season_tv_show')
@Route('airing_this_season_movie')
@Route('airing_this_season_tv_short')
@Route('airing_this_season_special')
@Route('airing_this_season_ova')
@Route('airing_this_season_ona')
@Route('airing_this_season_music')
def AIRING_THIS_SEASON(payload, params):
    mapping = {
        'airing_this_season_tv_show': ('tv', 'TV'),
        'airing_this_season_movie': ('movie', 'MOVIE'),
        'airing_this_season_tv_short': ('tv_special', 'TV_SHORT'),
        'airing_this_season_special': ('special', 'SPECIAL'),
        'airing_this_season_ova': ('ova', 'OVA'),
        'airing_this_season_ona': ('ona', 'ONA'),
        'airing_this_season_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_airing_this_season(page, format, prefix), 'tvshows')


@Route('airing_next_season')
@Route('airing_next_season_tv_show')
@Route('airing_next_season_movie')
@Route('airing_next_season_tv_short')
@Route('airing_next_season_special')
@Route('airing_next_season_ova')
@Route('airing_next_season_ona')
@Route('airing_next_season_music')
def AIRING_NEXT_SEASON(payload, params):
    mapping = {
        'airing_next_season_tv_show': ('tv', 'TV'),
        'airing_next_season_movie': ('movie', 'MOVIE'),
        'airing_next_season_tv_short': ('tv_special', 'TV_SHORT'),
        'airing_next_season_special': ('special', 'SPECIAL'),
        'airing_next_season_ova': ('ova', 'OVA'),
        'airing_next_season_ona': ('ona', 'ONA'),
        'airing_next_season_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_airing_next_season(page, format, prefix), 'tvshows')


@Route('trending_last_year')
@Route('trending_last_year_tv_show')
@Route('trending_last_year_movie')
@Route('trending_last_year_tv_short')
@Route('trending_last_year_special')
@Route('trending_last_year_ova')
@Route('trending_last_year_ona')
@Route('trending_last_year_music')
def TRENDING_LAST_YEAR(payload, params):
    mapping = {
        'trending_last_year_tv_show': ('tv', 'TV'),
        'trending_last_year_movie': ('movie', 'MOVIE'),
        'trending_last_year_tv_short': ('tv_special', 'TV_SHORT'),
        'trending_last_year_special': ('special', 'SPECIAL'),
        'trending_last_year_ova': ('ova', 'OVA'),
        'trending_last_year_ona': ('ona', 'ONA'),
        'trending_last_year_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_trending_last_year(page, format, prefix), 'tvshows')


@Route('trending_this_year')
@Route('trending_this_year_tv_show')
@Route('trending_this_year_movie')
@Route('trending_this_year_tv_short')
@Route('trending_this_year_special')
@Route('trending_this_year_ova')
@Route('trending_this_year_ona')
@Route('trending_this_year_music')
def TRENDING_THIS_YEAR(payload, params):
    mapping = {
        'trending_this_year_tv_show': ('tv', 'TV'),
        'trending_this_year_movie': ('movie', 'MOVIE'),
        'trending_this_year_tv_short': ('tv_special', 'TV_SHORT'),
        'trending_this_year_special': ('special', 'SPECIAL'),
        'trending_this_year_ova': ('ova', 'OVA'),
        'trending_this_year_ona': ('ona', 'ONA'),
        'trending_this_year_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_trending_this_year(page, format, prefix), 'tvshows')


@Route('trending_last_season')
@Route('trending_last_season_tv_show')
@Route('trending_last_season_movie')
@Route('trending_last_season_tv_short')
@Route('trending_last_season_special')
@Route('trending_last_season_ova')
@Route('trending_last_season_ona')
@Route('trending_last_season_music')
def TRENDING_LAST_SEASON(payload, params):
    mapping = {
        'trending_last_season_tv_show': ('tv', 'TV'),
        'trending_last_season_movie': ('movie', 'MOVIE'),
        'trending_last_season_tv_short': ('tv_special', 'TV_SHORT'),
        'trending_last_season_special': ('special', 'SPECIAL'),
        'trending_last_season_ova': ('ova', 'OVA'),
        'trending_last_season_ona': ('ona', 'ONA'),
        'trending_last_season_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_trending_last_season(page, format, prefix), 'tvshows')


@Route('trending_this_season')
@Route('trending_this_season_tv_show')
@Route('trending_this_season_movie')
@Route('trending_this_season_tv_short')
@Route('trending_this_season_special')
@Route('trending_this_season_ova')
@Route('trending_this_season_ona')
@Route('trending_this_season_music')
def TRENDING_THIS_SEASON(payload, params):
    mapping = {
        'trending_this_season_tv_show': ('tv', 'TV'),
        'trending_this_season_movie': ('movie', 'MOVIE'),
        'trending_this_season_tv_short': ('tv_special', 'TV_SHORT'),
        'trending_this_season_special': ('special', 'SPECIAL'),
        'trending_this_season_ova': ('ova', 'OVA'),
        'trending_this_season_ona': ('ona', 'ONA'),
        'trending_this_season_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_trending_this_season(page, format, prefix), 'tvshows')


@Route('all_time_trending')
@Route('all_time_trending_tv_show')
@Route('all_time_trending_movie')
@Route('all_time_trending_tv_short')
@Route('all_time_trending_special')
@Route('all_time_trending_ova')
@Route('all_time_trending_ona')
@Route('all_time_trending_music')
def ALL_TIME_TRENDING(payload, params):
    mapping = {
        'all_time_trending_tv_show': ('tv', 'TV'),
        'all_time_trending_movie': ('movie', 'MOVIE'),
        'all_time_trending_tv_short': ('tv_special', 'TV_SHORT'),
        'all_time_trending_special': ('special', 'SPECIAL'),
        'all_time_trending_ova': ('ova', 'OVA'),
        'all_time_trending_ona': ('ona', 'ONA'),
        'all_time_trending_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_all_time_trending(page, format, prefix), 'tvshows')


@Route('popular_last_year')
@Route('popular_last_year_tv_show')
@Route('popular_last_year_movie')
@Route('popular_last_year_tv_short')
@Route('popular_last_year_special')
@Route('popular_last_year_ova')
@Route('popular_last_year_ona')
@Route('popular_last_year_music')
def POPULAR_LAST_YEAR(payload, params):
    mapping = {
        'popular_last_year_tv_show': ('tv', 'TV'),
        'popular_last_year_movie': ('movie', 'MOVIE'),
        'popular_last_year_tv_short': ('tv_special', 'TV_SHORT'),
        'popular_last_year_special': ('special', 'SPECIAL'),
        'popular_last_year_ova': ('ova', 'OVA'),
        'popular_last_year_ona': ('ona', 'ONA'),
        'popular_last_year_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_popular_last_year(page, format, prefix), 'tvshows')


@Route('popular_this_year')
@Route('popular_this_year_tv_show')
@Route('popular_this_year_movie')
@Route('popular_this_year_tv_short')
@Route('popular_this_year_special')
@Route('popular_this_year_ova')
@Route('popular_this_year_ona')
@Route('popular_this_year_music')
def POPULAR_THIS_YEAR(payload, params):
    mapping = {
        'popular_this_year_tv_show': ('tv', 'TV'),
        'popular_this_year_movie': ('movie', 'MOVIE'),
        'popular_this_year_tv_short': ('tv_special', 'TV_SHORT'),
        'popular_this_year_special': ('special', 'SPECIAL'),
        'popular_this_year_ova': ('ova', 'OVA'),
        'popular_this_year_ona': ('ona', 'ONA'),
        'popular_this_year_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_popular_this_year(page, format, prefix), 'tvshows')


@Route('popular_last_season')
@Route('popular_last_season_tv_show')
@Route('popular_last_season_movie')
@Route('popular_last_season_tv_short')
@Route('popular_last_season_special')
@Route('popular_last_season_ova')
@Route('popular_last_season_ona')
@Route('popular_last_season_music')
def POPULAR_LAST_SEASON(payload, params):
    mapping = {
        'popular_last_season_tv_show': ('tv', 'TV'),
        'popular_last_season_movie': ('movie', 'MOVIE'),
        'popular_last_season_tv_short': ('tv_special', 'TV_SHORT'),
        'popular_last_season_special': ('special', 'SPECIAL'),
        'popular_last_season_ova': ('ova', 'OVA'),
        'popular_last_season_ona': ('ona', 'ONA'),
        'popular_last_season_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_popular_last_season(page, format, prefix), 'tvshows')


@Route('popular_this_season')
@Route('popular_this_season_tv_show')
@Route('popular_this_season_movie')
@Route('popular_this_season_tv_short')
@Route('popular_this_season_special')
@Route('popular_this_season_ova')
@Route('popular_this_season_ona')
@Route('popular_this_season_music')
def POPULAR_THIS_SEASON(payload, params):
    mapping = {
        'popular_this_season_tv_show': ('tv', 'TV'),
        'popular_this_season_movie': ('movie', 'MOVIE'),
        'popular_this_season_tv_short': ('tv_special', 'TV_SHORT'),
        'popular_this_season_special': ('special', 'SPECIAL'),
        'popular_this_season_ova': ('ova', 'OVA'),
        'popular_this_season_ona': ('ona', 'ONA'),
        'popular_this_season_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_popular_this_season(page, format, prefix), 'tvshows')


@Route('all_time_popular')
@Route('all_time_popular_tv_show')
@Route('all_time_popular_movie')
@Route('all_time_popular_tv_short')
@Route('all_time_popular_special')
@Route('all_time_popular_ova')
@Route('all_time_popular_ona')
@Route('all_time_popular_music')
def ALL_TIME_POPULAR(payload, params):
    mapping = {
        'all_time_popular_tv_show': ('tv', 'TV'),
        'all_time_popular_movie': ('movie', 'MOVIE'),
        'all_time_popular_tv_short': ('tv_special', 'TV_SHORT'),
        'all_time_popular_special': ('special', 'SPECIAL'),
        'all_time_popular_ova': ('ova', 'OVA'),
        'all_time_popular_ona': ('ona', 'ONA'),
        'all_time_popular_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_all_time_popular(page, format, prefix), 'tvshows')


@Route('voted_last_year')
@Route('voted_last_year_tv_show')
@Route('voted_last_year_movie')
@Route('voted_last_year_tv_short')
@Route('voted_last_year_special')
@Route('voted_last_year_ova')
@Route('voted_last_year_ona')
@Route('voted_last_year_music')
def VOTED_LAST_YEAR(payload, params):
    mapping = {
        'voted_last_year_tv_show': ('tv', 'TV'),
        'voted_last_year_movie': ('movie', 'MOVIE'),
        'voted_last_year_tv_short': ('tv_special', 'TV_SHORT'),
        'voted_last_year_special': ('special', 'SPECIAL'),
        'voted_last_year_ova': ('ova', 'OVA'),
        'voted_last_year_ona': ('ona', 'ONA'),
        'voted_last_year_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_voted_last_year(page, format, prefix), 'tvshows')


@Route('voted_this_year')
@Route('voted_this_year_tv_show')
@Route('voted_this_year_movie')
@Route('voted_this_year_tv_short')
@Route('voted_this_year_special')
@Route('voted_this_year_ova')
@Route('voted_this_year_ona')
@Route('voted_this_year_music')
def VOTED_THIS_YEAR(payload, params):
    mapping = {
        'voted_this_year_tv_show': ('tv', 'TV'),
        'voted_this_year_movie': ('movie', 'MOVIE'),
        'voted_this_year_tv_short': ('tv_special', 'TV_SHORT'),
        'voted_this_year_special': ('special', 'SPECIAL'),
        'voted_this_year_ova': ('ova', 'OVA'),
        'voted_this_year_ona': ('ona', 'ONA'),
        'voted_this_year_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_voted_this_year(page, format, prefix), 'tvshows')


@Route('voted_last_season')
@Route('voted_last_season_tv_show')
@Route('voted_last_season_movie')
@Route('voted_last_season_tv_short')
@Route('voted_last_season_special')
@Route('voted_last_season_ova')
@Route('voted_last_season_ona')
@Route('voted_last_season_music')
def VOTED_LAST_SEASON(payload, params):
    mapping = {
        'voted_last_season_tv_show': ('tv', 'TV'),
        'voted_last_season_movie': ('movie', 'MOVIE'),
        'voted_last_season_tv_short': ('tv_special', 'TV_SHORT'),
        'voted_last_season_special': ('special', 'SPECIAL'),
        'voted_last_season_ova': ('ova', 'OVA'),
        'voted_last_season_ona': ('ona', 'ONA'),
        'voted_last_season_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_voted_last_season(page, format, prefix), 'tvshows')


@Route('voted_this_season')
@Route('voted_this_season_tv_show')
@Route('voted_this_season_movie')
@Route('voted_this_season_tv_short')
@Route('voted_this_season_special')
@Route('voted_this_season_ova')
@Route('voted_this_season_ona')
@Route('voted_this_season_music')
def VOTED_THIS_SEASON(payload, params):
    mapping = {
        'voted_this_season_tv_show': ('tv', 'TV'),
        'voted_this_season_movie': ('movie', 'MOVIE'),
        'voted_this_season_tv_short': ('tv_special', 'TV_SHORT'),
        'voted_this_season_special': ('special', 'SPECIAL'),
        'voted_this_season_ova': ('ova', 'OVA'),
        'voted_this_season_ona': ('ona', 'ONA'),
        'voted_this_season_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_voted_this_season(page, format, prefix), 'tvshows')


@Route('all_time_voted')
@Route('all_time_voted_tv_show')
@Route('all_time_voted_movie')
@Route('all_time_voted_tv_short')
@Route('all_time_voted_special')
@Route('all_time_voted_ova')
@Route('all_time_voted_ona')
@Route('all_time_voted_music')
def ALL_TIME_VOTED(payload, params):
    mapping = {
        'all_time_voted_tv_show': ('tv', 'TV'),
        'all_time_voted_movie': ('movie', 'MOVIE'),
        'all_time_voted_tv_short': ('tv_special', 'TV_SHORT'),
        'all_time_voted_special': ('special', 'SPECIAL'),
        'all_time_voted_ova': ('ova', 'OVA'),
        'all_time_voted_ona': ('ona', 'ONA'),
        'all_time_voted_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_all_time_voted(page, format, prefix), 'tvshows')


@Route('favourites_last_year')
@Route('favourites_last_year_tv_show')
@Route('favourites_last_year_movie')
@Route('favourites_last_year_tv_short')
@Route('favourites_last_year_special')
@Route('favourites_last_year_ova')
@Route('favourites_last_year_ona')
@Route('favourites_last_year_music')
def FAVOURITES_LAST_YEAR(payload, params):
    mapping = {
        'favourites_last_year_tv_show': ('tv', 'TV'),
        'favourites_last_year_movie': ('movie', 'MOVIE'),
        'favourites_last_year_tv_short': ('tv_special', 'TV_SHORT'),
        'favourites_last_year_special': ('special', 'SPECIAL'),
        'favourites_last_year_ova': ('ova', 'OVA'),
        'favourites_last_year_ona': ('ona', 'ONA'),
        'favourites_last_year_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_favourites_last_year(page, format, prefix), 'tvshows')


@Route('favourites_this_year')
@Route('favourites_this_year_tv_show')
@Route('favourites_this_year_movie')
@Route('favourites_this_year_tv_short')
@Route('favourites_this_year_special')
@Route('favourites_this_year_ova')
@Route('favourites_this_year_ona')
@Route('favourites_this_year_music')
def FAVOURITES_THIS_YEAR(payload, params):
    mapping = {
        'favourites_this_year_tv_show': ('tv', 'TV'),
        'favourites_this_year_movie': ('movie', 'MOVIE'),
        'favourites_this_year_tv_short': ('tv_special', 'TV_SHORT'),
        'favourites_this_year_special': ('special', 'SPECIAL'),
        'favourites_this_year_ova': ('ova', 'OVA'),
        'favourites_this_year_ona': ('ona', 'ONA'),
        'favourites_this_year_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_favourites_this_year(page, format, prefix), 'tvshows')


@Route('favourites_last_season')
@Route('favourites_last_season_tv_show')
@Route('favourites_last_season_movie')
@Route('favourites_last_season_tv_short')
@Route('favourites_last_season_special')
@Route('favourites_last_season_ova')
@Route('favourites_last_season_ona')
@Route('favourites_last_season_music')
def FAVOURITES_LAST_SEASON(payload, params):
    mapping = {
        'favourites_last_season_tv_show': ('tv', 'TV'),
        'favourites_last_season_movie': ('movie', 'MOVIE'),
        'favourites_last_season_tv_short': ('tv_special', 'TV_SHORT'),
        'favourites_last_season_special': ('special', 'SPECIAL'),
        'favourites_last_season_ova': ('ova', 'OVA'),
        'favourites_last_season_ona': ('ona', 'ONA'),
        'favourites_last_season_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_favourites_last_season(page, format, prefix), 'tvshows')


@Route('favourites_this_season')
@Route('favourites_this_season_tv_show')
@Route('favourites_this_season_movie')
@Route('favourites_this_season_tv_short')
@Route('favourites_this_season_special')
@Route('favourites_this_season_ova')
@Route('favourites_this_season_ona')
@Route('favourites_this_season_music')
def FAVOURITES_THIS_SEASON(payload, params):
    mapping = {
        'favourites_this_season_tv_show': ('tv', 'TV'),
        'favourites_this_season_movie': ('movie', 'MOVIE'),
        'favourites_this_season_tv_short': ('tv_special', 'TV_SHORT'),
        'favourites_this_season_special': ('special', 'SPECIAL'),
        'favourites_this_season_ova': ('ova', 'OVA'),
        'favourites_this_season_ona': ('ona', 'ONA'),
        'favourites_this_season_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_favourites_this_season(page, format, prefix), 'tvshows')


@Route('all_time_favourites')
@Route('all_time_favourites_tv_show')
@Route('all_time_favourites_movie')
@Route('all_time_favourites_tv_short')
@Route('all_time_favourites_special')
@Route('all_time_favourites_ova')
@Route('all_time_favourites_ona')
@Route('all_time_favourites_music')
def ALL_TIME_FAVOURITES(payload, params):
    mapping = {
        'all_time_favourites_tv_show': ('tv', 'TV'),
        'all_time_favourites_movie': ('movie', 'MOVIE'),
        'all_time_favourites_tv_short': ('tv_special', 'TV_SHORT'),
        'all_time_favourites_special': ('special', 'SPECIAL'),
        'all_time_favourites_ova': ('ova', 'OVA'),
        'all_time_favourites_ona': ('ona', 'ONA'),
        'all_time_favourites_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_all_time_favourites(page, format, prefix), 'tvshows')


@Route('top_100')
@Route('top_100_tv_show')
@Route('top_100_movie')
@Route('top_100_tv_short')
@Route('top_100_special')
@Route('top_100_ova')
@Route('top_100_ona')
@Route('top_100_music')
def TOP_100(payload, params):
    mapping = {
        'top_100_tv_show': ('tv', 'TV'),
        'top_100_movie': ('movie', 'MOVIE'),
        'top_100_tv_short': ('tv_special', 'TV_SHORT'),
        'top_100_special': ('special', 'SPECIAL'),
        'top_100_ova': ('ova', 'OVA'),
        'top_100_ona': ('ona', 'ONA'),
        'top_100_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_top_100(page, format, prefix), 'tvshows')


@Route('genres/*')
@Route('genres_tv_show/*')
@Route('genres_movie/*')
@Route('genres_tv_short/*')
@Route('genres_special/*')
@Route('genres_ova/*')
@Route('genres_ona/*')
@Route('genres_music/*')
def GENRES(payload, params):
    mapping = {
        'genres_tv_show//': ('tv', 'TV'),
        'genres_movie//': ('movie', 'MOVIE'),
        'genres_tv_short//': ('tv_special', 'TV_SHORT'),
        'genres_special//': ('special', 'SPECIAL'),
        'genres_ova//': ('ova', 'OVA'),
        'genres_ona//': ('ona', 'ONA'),
        'genres_music//': ('music', 'MUSIC')
    }
    genres, tags = payload.rsplit("/")
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('/', 1)[0] + '//'
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    if genres or tags:
        prefix = plugin_url.split('/', 1)[0]
        control.draw_items(BROWSER.genres_payload(genres, tags, page, format, prefix), 'tvshows')
    else:
        control.draw_items(BROWSER.get_genres(page, format), 'tvshows')


@Route('update_genre_settings')
def UPDATE_GENRE_SETTINGS(payload, params):
    try:
        selected_genres_mal, selected_genres_anilist, selected_tags = BROWSER.update_genre_settings()
    except ValueError:
        return  # Break the code if ValueError occurs

    # Create a dictionary to store the settings
    settings = {
        'selected_genres_mal': selected_genres_mal,
        'selected_genres_anilist': selected_genres_anilist,
        'selected_tags': selected_tags
    }

    # Write the settings to a JSON file
    with open(control.genre_json, 'w') as f:
        json.dump(settings, f)


@Route('genre_action')
@Route('genre_action_tv_show')
@Route('genre_action_movie')
@Route('genre_action_tv_short')
@Route('genre_action_special')
@Route('genre_action_ova')
@Route('genre_action_ona')
@Route('genre_action_music')
def GENRE_ACTION(payload, params):
    mapping = {
        'genre_action_tv_show': ('tv', 'TV'),
        'genre_action_movie': ('movie', 'MOVIE'),
        'genre_action_tv_short': ('tv_special', 'TV_SHORT'),
        'genre_action_special': ('special', 'SPECIAL'),
        'genre_action_ova': ('ova', 'OVA'),
        'genre_action_ona': ('ona', 'ONA'),
        'genre_action_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_genre_action(page, format, prefix), 'tvshows')


@Route('genre_adventure')
@Route('genre_adventure_tv_show')
@Route('genre_adventure_movie')
@Route('genre_adventure_tv_short')
@Route('genre_adventure_special')
@Route('genre_adventure_ova')
@Route('genre_adventure_ona')
@Route('genre_adventure_music')
def GENRE_ADVENTURE(payload, params):
    mapping = {
        'genre_adventure_tv_show': ('tv', 'TV'),
        'genre_adventure_movie': ('movie', 'MOVIE'),
        'genre_adventure_tv_short': ('tv_special', 'TV_SHORT'),
        'genre_adventure_special': ('special', 'SPECIAL'),
        'genre_adventure_ova': ('ova', 'OVA'),
        'genre_adventure_ona': ('ona', 'ONA'),
        'genre_adventure_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_genre_adventure(page, format, prefix), 'tvshows')


@Route('genre_comedy')
@Route('genre_comedy_tv_show')
@Route('genre_comedy_movie')
@Route('genre_comedy_tv_short')
@Route('genre_comedy_special')
@Route('genre_comedy_ova')
@Route('genre_comedy_ona')
@Route('genre_comedy_music')
def GENRE_COMEDY(payload, params):
    mapping = {
        'genre_comedy_tv_show': ('tv', 'TV'),
        'genre_comedy_movie': ('movie', 'MOVIE'),
        'genre_comedy_tv_short': ('tv_special', 'TV_SHORT'),
        'genre_comedy_special': ('special', 'SPECIAL'),
        'genre_comedy_ova': ('ova', 'OVA'),
        'genre_comedy_ona': ('ona', 'ONA'),
        'genre_comedy_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_genre_comedy(page, format, prefix), 'tvshows')


@Route('genre_drama')
@Route('genre_drama_tv_show')
@Route('genre_drama_movie')
@Route('genre_drama_tv_short')
@Route('genre_drama_special')
@Route('genre_drama_ova')
@Route('genre_drama_ona')
@Route('genre_drama_music')
def GENRE_DRAMA(payload, params):
    mapping = {
        'genre_drama_tv_show': ('tv', 'TV'),
        'genre_drama_movie': ('movie', 'MOVIE'),
        'genre_drama_tv_short': ('tv_special', 'TV_SHORT'),
        'genre_drama_special': ('special', 'SPECIAL'),
        'genre_drama_ova': ('ova', 'OVA'),
        'genre_drama_ona': ('ona', 'ONA'),
        'genre_drama_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_genre_drama(page, format, prefix), 'tvshows')


@Route('genre_ecchi')
@Route('genre_ecchi_tv_show')
@Route('genre_ecchi_movie')
@Route('genre_ecchi_tv_short')
@Route('genre_ecchi_special')
@Route('genre_ecchi_ova')
@Route('genre_ecchi_ona')
@Route('genre_ecchi_music')
def GENRE_ECCHI(payload, params):
    mapping = {
        'genre_ecchi_tv_show': ('tv', 'TV'),
        'genre_ecchi_movie': ('movie', 'MOVIE'),
        'genre_ecchi_tv_short': ('tv_special', 'TV_SHORT'),
        'genre_ecchi_special': ('special', 'SPECIAL'),
        'genre_ecchi_ova': ('ova', 'OVA'),
        'genre_ecchi_ona': ('ona', 'ONA'),
        'genre_ecchi_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_genre_ecchi(page, format, prefix), 'tvshows')


@Route('genre_fantasy')
@Route('genre_fantasy_tv_show')
@Route('genre_fantasy_movie')
@Route('genre_fantasy_tv_short')
@Route('genre_fantasy_special')
@Route('genre_fantasy_ova')
@Route('genre_fantasy_ona')
@Route('genre_fantasy_music')
def GENRE_FANTASY(payload, params):
    mapping = {
        'genre_fantasy_tv_show': ('tv', 'TV'),
        'genre_fantasy_movie': ('movie', 'MOVIE'),
        'genre_fantasy_tv_short': ('tv_special', 'TV_SHORT'),
        'genre_fantasy_special': ('special', 'SPECIAL'),
        'genre_fantasy_ova': ('ova', 'OVA'),
        'genre_fantasy_ona': ('ona', 'ONA'),
        'genre_fantasy_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_genre_fantasy(page, format, prefix), 'tvshows')


@Route('genre_hentai')
@Route('genre_hentai_tv_show')
@Route('genre_hentai_movie')
@Route('genre_hentai_tv_short')
@Route('genre_hentai_special')
@Route('genre_hentai_ova')
@Route('genre_hentai_ona')
@Route('genre_hentai_music')
def GENRE_HENTAI(payload, params):
    mapping = {
        'genre_hentai_tv_show': ('tv', 'TV'),
        'genre_hentai_movie': ('movie', 'MOVIE'),
        'genre_hentai_tv_short': ('tv_special', 'TV_SHORT'),
        'genre_hentai_special': ('special', 'SPECIAL'),
        'genre_hentai_ova': ('ova', 'OVA'),
        'genre_hentai_ona': ('ona', 'ONA'),
        'genre_hentai_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_genre_hentai(page, format, prefix), 'tvshows')


@Route('genre_horror')
@Route('genre_horror_tv_show')
@Route('genre_horror_movie')
@Route('genre_horror_tv_short')
@Route('genre_horror_special')
@Route('genre_horror_ova')
@Route('genre_horror_ona')
@Route('genre_horror_music')
def GENRE_HORROR(payload, params):
    mapping = {
        'genre_horror_tv_show': ('tv', 'TV'),
        'genre_horror_movie': ('movie', 'MOVIE'),
        'genre_horror_tv_short': ('tv_special', 'TV_SHORT'),
        'genre_horror_special': ('special', 'SPECIAL'),
        'genre_horror_ova': ('ova', 'OVA'),
        'genre_horror_ona': ('ona', 'ONA'),
        'genre_horror_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_genre_horror(page, format, prefix), 'tvshows')


@Route('genre_shoujo')
@Route('genre_shoujo_tv_show')
@Route('genre_shoujo_movie')
@Route('genre_shoujo_tv_short')
@Route('genre_shoujo_special')
@Route('genre_shoujo_ova')
@Route('genre_shoujo_ona')
@Route('genre_shoujo_music')
def GENRE_SHOUJO(payload, params):
    mapping = {
        'genre_shoujo_tv_show': ('tv', 'TV'),
        'genre_shoujo_movie': ('movie', 'MOVIE'),
        'genre_shoujo_tv_short': ('tv_special', 'TV_SHORT'),
        'genre_shoujo_special': ('special', 'SPECIAL'),
        'genre_shoujo_ova': ('ova', 'OVA'),
        'genre_shoujo_ona': ('ona', 'ONA'),
        'genre_shoujo_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_genre_shoujo(page, format, prefix), 'tvshows')


@Route('genre_mecha')
@Route('genre_mecha_tv_show')
@Route('genre_mecha_movie')
@Route('genre_mecha_tv_short')
@Route('genre_mecha_special')
@Route('genre_mecha_ova')
@Route('genre_mecha_ona')
@Route('genre_mecha_music')
def GENRE_MECHA(payload, params):
    mapping = {
        'genre_mecha_tv_show': ('tv', 'TV'),
        'genre_mecha_movie': ('movie', 'MOVIE'),
        'genre_mecha_tv_short': ('tv_special', 'TV_SHORT'),
        'genre_mecha_special': ('special', 'SPECIAL'),
        'genre_mecha_ova': ('ova', 'OVA'),
        'genre_mecha_ona': ('ona', 'ONA'),
        'genre_mecha_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_genre_mecha(page, format, prefix), 'tvshows')


@Route('genre_music')
@Route('genre_music_tv_show')
@Route('genre_music_movie')
@Route('genre_music_tv_short')
@Route('genre_music_special')
@Route('genre_music_ova')
@Route('genre_music_ona')
@Route('genre_music_music')
def GENRE_MUSIC(payload, params):
    mapping = {
        'genre_music_tv_show': ('tv', 'TV'),
        'genre_music_movie': ('movie', 'MOVIE'),
        'genre_music_tv_short': ('tv_special', 'TV_SHORT'),
        'genre_music_special': ('special', 'SPECIAL'),
        'genre_music_ova': ('ova', 'OVA'),
        'genre_music_ona': ('ona', 'ONA'),
        'genre_music_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_genre_music(page, format, prefix), 'tvshows')


@Route('genre_mystery')
@Route('genre_mystery_tv_show')
@Route('genre_mystery_movie')
@Route('genre_mystery_tv_short')
@Route('genre_mystery_special')
@Route('genre_mystery_ova')
@Route('genre_mystery_ona')
@Route('genre_mystery_music')
def GENRE_MYSTERY(payload, params):
    mapping = {
        'genre_mystery_tv_show': ('tv', 'TV'),
        'genre_mystery_movie': ('movie', 'MOVIE'),
        'genre_mystery_tv_short': ('tv_special', 'TV_SHORT'),
        'genre_mystery_special': ('special', 'SPECIAL'),
        'genre_mystery_ova': ('ova', 'OVA'),
        'genre_mystery_ona': ('ona', 'ONA'),
        'genre_mystery_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_genre_mystery(page, format, prefix), 'tvshows')


@Route('genre_psychological')
@Route('genre_psychological_tv_show')
@Route('genre_psychological_movie')
@Route('genre_psychological_tv_short')
@Route('genre_psychological_special')
@Route('genre_psychological_ova')
@Route('genre_psychological_ona')
@Route('genre_psychological_music')
def GENRE_PSYCHOLOGICAL(payload, params):
    mapping = {
        'genre_psychological_tv_show': ('tv', 'TV'),
        'genre_psychological_movie': ('movie', 'MOVIE'),
        'genre_psychological_tv_short': ('tv_special', 'TV_SHORT'),
        'genre_psychological_special': ('special', 'SPECIAL'),
        'genre_psychological_ova': ('ova', 'OVA'),
        'genre_psychological_ona': ('ona', 'ONA'),
        'genre_psychological_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_genre_psychological(page, format, prefix), 'tvshows')


@Route('genre_romance')
@Route('genre_romance_tv_show')
@Route('genre_romance_movie')
@Route('genre_romance_tv_short')
@Route('genre_romance_special')
@Route('genre_romance_ova')
@Route('genre_romance_ona')
@Route('genre_romance_music')
def GENRE_ROMANCE(payload, params):
    mapping = {
        'genre_romance_tv_show': ('tv', 'TV'),
        'genre_romance_movie': ('movie', 'MOVIE'),
        'genre_romance_tv_short': ('tv_special', 'TV_SHORT'),
        'genre_romance_special': ('special', 'SPECIAL'),
        'genre_romance_ova': ('ova', 'OVA'),
        'genre_romance_ona': ('ona', 'ONA'),
        'genre_romance_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_genre_romance(page, format, prefix), 'tvshows')


@Route('genre_sci_fi')
@Route('genre_sci_fi_tv_show')
@Route('genre_sci_fi_movie')
@Route('genre_sci_fi_tv_short')
@Route('genre_sci_fi_special')
@Route('genre_sci_fi_ova')
@Route('genre_sci_fi_ona')
@Route('genre_sci_fi_music')
def GENRE_SCI_FI(payload, params):
    mapping = {
        'genre_sci_fi_tv_show': ('tv', 'TV'),
        'genre_sci_fi_movie': ('movie', 'MOVIE'),
        'genre_sci_fi_tv_short': ('tv_special', 'TV_SHORT'),
        'genre_sci_fi_special': ('special', 'SPECIAL'),
        'genre_sci_fi_ova': ('ova', 'OVA'),
        'genre_sci_fi_ona': ('ona', 'ONA'),
        'genre_sci_fi_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_genre_sci_fi(page, format, prefix), 'tvshows')


@Route('genre_slice_of_life')
@Route('genre_slice_of_life_tv_show')
@Route('genre_slice_of_life_movie')
@Route('genre_slice_of_life_tv_short')
@Route('genre_slice_of_life_special')
@Route('genre_slice_of_life_ova')
@Route('genre_slice_of_life_ona')
@Route('genre_slice_of_life_music')
def GENRE_SLICE_OF_LIFE(payload, params):
    mapping = {
        'genre_slice_of_life_tv_show': ('tv', 'TV'),
        'genre_slice_of_life_movie': ('movie', 'MOVIE'),
        'genre_slice_of_life_tv_short': ('tv_special', 'TV_SHORT'),
        'genre_slice_of_life_special': ('special', 'SPECIAL'),
        'genre_slice_of_life_ova': ('ova', 'OVA'),
        'genre_slice_of_life_ona': ('ona', 'ONA'),
        'genre_slice_of_life_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_genre_slice_of_life(page, format, prefix), 'tvshows')


@Route('genre_sports')
@Route('genre_sports_tv_show')
@Route('genre_sports_movie')
@Route('genre_sports_tv_short')
@Route('genre_sports_special')
@Route('genre_sports_ova')
@Route('genre_sports_ona')
@Route('genre_sports_music')
def GENRE_SPORTS(payload, params):
    mapping = {
        'genre_sports_tv_show': ('tv', 'TV'),
        'genre_sports_movie': ('movie', 'MOVIE'),
        'genre_sports_tv_short': ('tv_special', 'TV_SHORT'),
        'genre_sports_special': ('special', 'SPECIAL'),
        'genre_sports_ova': ('ova', 'OVA'),
        'genre_sports_ona': ('ona', 'ONA'),
        'genre_sports_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_genre_sports(page, format, prefix), 'tvshows')


@Route('genre_supernatural')
@Route('genre_supernatural_tv_show')
@Route('genre_supernatural_movie')
@Route('genre_supernatural_tv_short')
@Route('genre_supernatural_special')
@Route('genre_supernatural_ova')
@Route('genre_supernatural_ona')
@Route('genre_supernatural_music')
def GENRE_SUPERNATURAL(payload, params):
    mapping = {
        'genre_supernatural_tv_show': ('tv', 'TV'),
        'genre_supernatural_movie': ('movie', 'MOVIE'),
        'genre_supernatural_tv_short': ('tv_special', 'TV_SHORT'),
        'genre_supernatural_special': ('special', 'SPECIAL'),
        'genre_supernatural_ova': ('ova', 'OVA'),
        'genre_supernatural_ona': ('ona', 'ONA'),
        'genre_supernatural_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_genre_supernatural(page, format, prefix), 'tvshows')


@Route('genre_thriller')
@Route('genre_thriller_tv_show')
@Route('genre_thriller_movie')
@Route('genre_thriller_tv_short')
@Route('genre_thriller_special')
@Route('genre_thriller_ova')
@Route('genre_thriller_ona')
@Route('genre_thriller_music')
def GENRE_THRILLER(payload, params):
    mapping = {
        'genre_thriller_tv_show': ('tv', 'TV'),
        'genre_thriller_movie': ('movie', 'MOVIE'),
        'genre_thriller_tv_short': ('tv_special', 'TV_SHORT'),
        'genre_thriller_special': ('special', 'SPECIAL'),
        'genre_thriller_ova': ('ova', 'OVA'),
        'genre_thriller_ona': ('ona', 'ONA'),
        'genre_thriller_music': ('music', 'MUSIC')
    }
    page = int(params.get('page', 1))
    format = None
    base_key = plugin_url.split('?', 1)[0]
    if base_key in mapping:
        format = mapping[base_key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mapping[base_key][1]
    prefix = plugin_url.split('?', 1)[0]
    control.draw_items(BROWSER.get_genre_thriller(page, format, prefix), 'tvshows')


def get_search_config():
    search_types = [
        'search_anime/', 'search_tv_show/', 'search_movie/',
        'search_tv_short/', 'search_special/', 'search_ova/',
        'search_ona/', 'search_music/'
    ]

    types = {
        'search_anime/': 'anime',
        'search_tv_show/': 'tv_show',
        'search_movie/': 'movie',
        'search_tv_short/': 'tv_short',
        'search_special/': 'special',
        'search_ova/': 'ova',
        'search_ona/': 'ona',
        'search_music/': 'music'
    }

    mappings = {
        'search_anime/': ('', ''),
        'search_tv_show/': ('tv', 'TV'),
        'search_movie/': ('movie', 'MOVIE'),
        'search_tv_short/': ('tv_special', 'TV_SHORT'),
        'search_special/': ('special', 'SPECIAL'),
        'search_ova/': ('ova', 'OVA'),
        'search_ona/': ('ona', 'ONA'),
        'search_music/': ('music', 'MUSIC')
    }

    formats = {
        'search_history_anime': 'anime',
        'search_history_tv_show': 'tv_show',
        'search_history_movie': 'movie',
        'search_history_tv_short': 'tv_short',
        'search_history_special': 'special',
        'search_history_ova': 'ova',
        'search_history_ona': 'ona',
        'search_history_music': 'music'
    }

    return search_types, types, mappings, formats


@Route('search_history_anime')
@Route('search_history_tv_show')
@Route('search_history_movie')
@Route('search_history_tv_short')
@Route('search_history_special')
@Route('search_history_ova')
@Route('search_history_ona')
@Route('search_history_music')
def SEARCH_HISTORY(payload, params):
    _, _, _, formats = get_search_config()

    if plugin_url in formats:
        format = formats[plugin_url]
        control.setSetting('format', format)
    else:
        format = control.getSetting('format')

    history = database.getSearchHistory(format)
    view_type = 'addons' if control.getBool('interface.content_type') else ''
    if control.getInt('searchhistory') == 0:
        control.draw_items(utils.search_history(history, format), view_type)
    else:
        SEARCH(payload, params)


@Route('remove_search_item/*')
def REMOVE_SEARCH_ITEM(payload, params):
    from urllib.parse import unquote
    search_types, _, _, _ = get_search_config()
    format = control.getSetting('format')
    found = False
    for search_type in search_types:
        if payload.startswith(search_type):
            search_item = payload.split(search_type, 1)[1]
            if search_item:
                decoded_item = unquote(search_item)
                database.remove_search(table=format, value=decoded_item)
                found = True
    if not found:
        control.notify(control.ADDON_NAME, "Failed to remove search item", time=3000)
    control.exit_code()


@Route('edit_search_item/*')
def EDIT_SEARCH_ITEM(payload, params):
    from urllib.parse import unquote
    search_types, _, _, _ = get_search_config()
    format = control.getSetting('format')
    found = False
    for search_type in search_types:
        if payload.startswith(search_type):
            search_item = payload.split(search_type, 1)[1]
            if search_item:
                decoded_item = unquote(search_item)
                query = control.keyboard(control.lang(30918), decoded_item)
                if query and query != decoded_item:
                    database.remove_search(table=format, value=decoded_item)
                    control.sleep(500)
                    database.addSearchHistory(query, format)
                found = True
    if not found:
        control.notify(control.ADDON_NAME, "Failed to edit search item", time=3000)
    control.refresh()
    control.exit_code()


@Route('search_anime/*')
@Route('search_tv_show/*')
@Route('search_movie/*')
@Route('search_tv_short/*')
@Route('search_special/*')
@Route('search_ova/*')
@Route('search_ona/*')
@Route('search_music/*')
def SEARCH(payload, params):
    _, types, mappings, _ = get_search_config()

    type = None
    format = None

    for key in types:
        if plugin_url.startswith(key):
            type = types[key]
            break

    for key in mappings:
        if plugin_url.startswith(key):
            format = mappings[key][0] if control.settingids.browser_api in ['mal', 'otaku'] else mappings[key][1]
            break

    query = payload
    page = int(params.get('page', 1))
    if not query:
        query = control.keyboard(control.lang(30918))
        if not query:
            return control.draw_items([], 'tvshows')
        if control.getInt('searchhistory') == 0:
            database.addSearchHistory(query, type)
    prefix = plugin_url.split('/', 1)[0]
    control.draw_items(BROWSER.get_search(query, page, format, prefix), 'tvshows')


@Route('play/*')
def PLAY(payload, params):
    mal_id, episode = payload.rsplit("/")
    source_select = bool(params.get('source_select'))
    rescrape = bool(params.get('rescrape'))
    last_played = control.getSetting('last_played_source')
    last_watched = control.getSetting('last_watched_series')
    resume = params.get('resume')
    if rating := params.get('rating'):
        params['rating'] = ast.literal_eval(rating)
    params['path'] = f"{control.addon_url(f'play/{payload}')}"

    # Populate params with episode metadata from database if not already present
    # This ensures metadata is available even when playing from Information dialog
    if not params.get('tvshowtitle'):
        episode_data = database.get_episode(mal_id, episode)
        if episode_data:
            params = pickle.loads(episode_data['kodi_meta'])

    if resume:
        resume = float(resume)
        context = control.context_menu([f'Resume from {utils.format_time(resume)}', 'Play from beginning'])
        if context == -1:
            return control.exit_code()
        elif context == 1:
            resume = None

    sources = MetaBrowser.get_sources(mal_id, episode, 'show', rescrape, source_select)
    if sources:
        _mock_args = {"mal_id": mal_id, "episode": episode, 'play': True, 'resume': resume, 'context': rescrape or source_select, 'params': params}

        # SmartPlay Enabled
        if control.getBool('general.smartplay'):
            # Check if the same series is already being watched
            if last_watched == mal_id:
                # If the same series is being watched, check if the last played source is available
                if last_played == "None" or source_select or rescrape:
                    from resources.lib.windows.source_select import SourceSelect
                    if control.getInt('general.dialog') in (5, 6):
                        SourceSelect('source_select_alt.xml', control.ADDON_PATH, actionArgs=_mock_args, sources=sources, rescrape=rescrape).doModal()
                    else:
                        SourceSelect('source_select.xml', control.ADDON_PATH, actionArgs=_mock_args, sources=sources, rescrape=rescrape).doModal()
                else:
                    # If the last played source is available, resolve it directly
                    from resources.lib.windows.resolver import Resolver
                    if control.getInt('general.dialog') in (5, 6):
                        Resolver('resolver_alt.xml', control.ADDON_PATH, actionArgs=_mock_args).doModal(sources, {}, False)
                    else:
                        Resolver('resolver.xml', control.ADDON_PATH, actionArgs=_mock_args).doModal(sources, {}, False)
            else:
                # If a different series is being watched, prompt for source selection and update last watched Series
                control.setSetting('last_watched_series', mal_id)
                from resources.lib.windows.source_select import SourceSelect
                if control.getInt('general.dialog') in (5, 6):
                    SourceSelect('source_select_alt.xml', control.ADDON_PATH, actionArgs=_mock_args, sources=sources, rescrape=rescrape).doModal()
                else:
                    SourceSelect('source_select.xml', control.ADDON_PATH, actionArgs=_mock_args, sources=sources, rescrape=rescrape).doModal()
        # SmartPlay Disabled
        else:
            if control.getInt('general.playstyle.episode') == 1 or source_select or rescrape:
                from resources.lib.windows.source_select import SourceSelect
                if control.getInt('general.dialog') in (5, 6):
                    SourceSelect('source_select_alt.xml', control.ADDON_PATH, actionArgs=_mock_args, sources=sources, rescrape=rescrape).doModal()
                else:
                    SourceSelect('source_select.xml', control.ADDON_PATH, actionArgs=_mock_args, sources=sources, rescrape=rescrape).doModal()
            else:
                from resources.lib.windows.resolver import Resolver
                if control.getInt('general.dialog') in (5, 6):
                    Resolver('resolver_alt.xml', control.ADDON_PATH, actionArgs=_mock_args).doModal(sources, {}, False)
                else:
                    Resolver('resolver.xml', control.ADDON_PATH, actionArgs=_mock_args).doModal(sources, {}, False)
    else:
        control.playList.clear()
    control.exit_code()


@Route('play_movie/*')
def PLAY_MOVIE(payload, params):
    mal_id, eps_watched = payload.rsplit("/")
    source_select = bool(params.get('source_select'))
    rescrape = bool(params.get('rescrape'))
    resume = params.get('resume')
    params['path'] = f"{control.addon_url(f'play_movie/{payload}')}"

    # Populate params with movie metadata from database if not already present
    # This ensures metadata is available even when playing from Information dialog
    if not params.get('name'):
        anime_meta = database.get_show_meta(mal_id)
        anime_data = database.get_show(mal_id)
        kodi_meta = pickle.loads(anime_data['kodi_meta'])

        params = {
            **kodi_meta,
            'info': kodi_meta,  # video info tags
            'image': {  # art fields for UI
                k: (v[0] if isinstance(v, list) else v)
                for k, v in pickle.loads(anime_meta['art']).items()
            }
        }

    if resume:
        resume = float(resume)
        context = control.context_menu([f'Resume from {utils.format_time(resume)}', 'Play from beginning'])
        if context == -1:
            return
        elif context == 1:
            resume = None

    sources = MetaBrowser.get_sources(mal_id, 1, 'movie', rescrape, source_select)
    if sources:
        _mock_args = {'mal_id': mal_id, 'play': True, 'resume': resume, 'context': rescrape or source_select, 'params': params}
        if control.getInt('general.playstyle.movie') == 1 or source_select or rescrape:
            from resources.lib.windows.source_select import SourceSelect
            if control.getInt('general.dialog') in (5, 6):
                SourceSelect('source_select_alt.xml', control.ADDON_PATH, actionArgs=_mock_args, sources=sources, rescrape=rescrape).doModal()
            else:
                SourceSelect('source_select.xml', control.ADDON_PATH, actionArgs=_mock_args, sources=sources, rescrape=rescrape).doModal()
        else:
            from resources.lib.windows.resolver import Resolver
            if control.getInt('general.dialog') in (5, 6):
                Resolver('resolver_alt.xml', control.ADDON_PATH, actionArgs=_mock_args).doModal(sources, {}, False)
            else:
                Resolver('resolver.xml', control.ADDON_PATH, actionArgs=_mock_args).doModal(sources, {}, False)
    else:
        control.playList.clear()
    control.exit_code()


@Route('tmdb_helper')
def TMDB_HELPER(payload, params):
    # --- Extract all relevant parameters from params and actionArgs ---
    import ast
    from resources.lib.OtakuBrowser import OtakuBrowser
    from resources.lib.endpoints import tmdb

    action_args = params.pop('actionArgs', {})
    if isinstance(action_args, str):
        action_args = ast.literal_eval(action_args)
    # Now it's safe to use .get
    item_type = action_args.get('item_type')

    # Extract parameters from action_args
    item_type = action_args.get('item_type')
    tmdb_id = action_args.get('tmdb_id')
    tvdb_id = action_args.get('tvdb_id')
    imdb_id = action_args.get('imdb_id')
    trakt_id = action_args.get('trakt_id')
    season = action_args.get('season')
    episode = action_args.get('episode')

    # Extract source_select from params (default to False)
    source_select = params.pop('source_select', 'false') == 'true'
    params.update({'source_select': source_select})

    # Convert season and episode to int if present
    season_number = int(season) if season is not None else None
    episode_number = int(episode) if episode is not None else None

    # Grab Playstyle settings
    smartplay = control.getBool('general.smartplay')
    playstyle_movie = control.getInt('general.playstyle.movie')
    playstyle_episode = control.getInt('general.playstyle.episode')

    # Disable SmartPlay temporarily
    if smartplay:
        control.setBool('general.smartplay', False)

    # Parms cleanup
    parms = {}

    # Now all parameters are available: item_type, tmdb_id, title_url, season_number, episode_number, source_select
    control.log("Item Type: " + str(item_type))
    control.log("TMDB ID: " + str(tmdb_id))
    control.log("TVDB ID: " + str(tvdb_id))
    control.log("IMDB ID: " + str(imdb_id))
    control.log("Trakt ID: " + str(trakt_id))
    control.log("Season Number: " + str(season_number))
    control.log("Episode Number: " + str(episode_number))
    control.log("Source Select: " + str(source_select))

    if item_type == 'movie':
        mal_id = None
        id_sources = [
            ('themoviedb_id', tmdb_id),
            ('thetvdb_id', tvdb_id),
            ('imdb_id', imdb_id),
            ('trakt_id', trakt_id)
        ]

        for key, value in id_sources:
            if value:
                anime_ids = database.get_mappings(value, key)
                if anime_ids and anime_ids.get('mal_id'):
                    mal_id = anime_ids['mal_id']
                    break

        if mal_id:
            OtakuBrowser().get_anime_data(mal_id)

            if source_select:
                control.setInt('general.playstyle.movie', 1)
            else:
                control.setInt('general.playstyle.movie', 0)

            PLAY_MOVIE(f"{mal_id}/", parms)
            control.sleep(3000)
            control.setInt('general.playstyle.movie', playstyle_movie)
            control.setBool('general.smartplay', smartplay)
            return
        else:
            control.sleep(3000)
            control.setInt('general.playstyle.movie', playstyle_movie)
            control.setBool('general.smartplay', smartplay)
            control.notify(control.ADDON_NAME, 'No MAL ID found from this movie')
            return

    else:
        mal_ids = set()
        id_sources = [
            ('themoviedb_id', tmdb_id),
            ('thetvdb_id', tvdb_id),
            ('imdb_id', imdb_id),
            ('trakt_id', trakt_id)
        ]

        for key, value in id_sources:
            if value:
                mappings = database.get_mal_ids(value, key)  # Now returns a list
                for anime_ids in mappings:
                    if anime_ids and 'mal_id' in anime_ids and anime_ids['mal_id']:
                        if isinstance(anime_ids['mal_id'], list):
                            mal_ids.update(anime_ids['mal_id'])
                        else:
                            mal_ids.add(anime_ids['mal_id'])

        if mal_ids:
            episode_titles = tmdb.get_episode_titles(tmdb_id, season_number, episode_number)
            match = find_episode_by_title(mal_ids, episode_titles)
            if match:
                mal_id = match['mal_id']
                episode_num = match['episode_number']
                matched_title = match['matched_title']
                control.log(f"Matched MAL ID: {mal_id} for Episode {episode_num} titled '{matched_title}'")
                OtakuBrowser().get_anime_data(mal_id)
                MetaBrowser.get_anime_init(mal_id)

                if source_select:
                    control.setInt('general.playstyle.episode', 1)
                else:
                    control.setInt('general.playstyle.episode', 0)

                PLAY(f"{mal_id}/{episode_num}", parms)
                control.sleep(3000)
                control.setInt('general.playstyle.episode', playstyle_episode)
                control.setBool('general.smartplay', smartplay)
                return
            else:
                control.sleep(3000)
                control.setInt('general.playstyle.episode', playstyle_episode)
                control.setBool('general.smartplay', smartplay)
                control.notify(control.ADDON_NAME, 'No MAL ID found from this episode')
                return


def remove_punctuation(s):
    import re
    return re.sub(r'[^\w\s]', '', s)


def find_episode_by_title(mal_ids, episode_titles):
    import time
    from resources.lib.indexers.jikanmoe import JikanAPI
    from resources.lib.ui.source_utils import get_fuzzy_match
    # Split titles on '|' and clean each part
    split_titles = []
    for t in episode_titles:
        if t:
            split_titles.extend([x.strip() for x in t.split('|') if x.strip()])
    # Use shared clean_text for normalization (removes punctuation, preserves spaces)
    from resources.lib.ui.source_utils import clean_text
    cleaned_titles = [clean_text(t) for t in split_titles]
    jikan_api = JikanAPI()
    requests_made = 0
    last_request_time = time.time()
    for mal_id in mal_ids:
        # Rate limit: max 3 requests every 4 seconds, space each request by at least 1.33 seconds
        if requests_made == 3:
            elapsed = time.time() - last_request_time
            if elapsed < 4.0:
                time.sleep(4.0 - elapsed)
            requests_made = 0
            last_request_time = time.time()
        # Space each request by at least 1.33 seconds
        if requests_made > 0:
            time.sleep(1.33)
        # Retry logic for HTTP 429
        retries = 0
        max_retries = 3
        backoff = 2
        while retries <= max_retries:
            try:
                episodes = jikan_api.get_episode_meta(mal_id)
                requests_made += 1
                break
            except Exception as e:
                if hasattr(e, 'response') and getattr(e.response, 'status_code', None) == 429:
                    control.log(f"Jikan API rate limited (429) for mal_id {mal_id}, retrying in {backoff} seconds...")
                    time.sleep(backoff)
                    retries += 1
                    backoff *= 2
                else:
                    control.log(f"Jikan API error for mal_id {mal_id}: {e}")
                    episodes = []
                    break
        else:
            control.log(f"Jikan API failed for mal_id {mal_id} after {max_retries} retries.")
            episodes = []
        # Prepare candidate episode titles from Jikan
        episode_candidates = []
        episode_meta_map = []
        for ep in episodes:
            candidates = [
                ep.get('title', ''),
                ep.get('title_romanji', '')
            ]
            for candidate in candidates:
                if candidate:
                    episode_candidates.append(candidate)
                    episode_meta_map.append((candidate, ep))
        # Use shared clean_text for normalization
        cleaned_candidates = [clean_text(c) for c in episode_candidates]
        # Run fuzzy matching for each cleaned title variant individually
        best_score = -1
        best_idx = None
        for cleaned_query in cleaned_titles:
            match_indices = get_fuzzy_match(cleaned_query, cleaned_candidates)
            if match_indices:
                # get_fuzzy_match returns sorted indices by best match first
                idx = match_indices[0]
                # Optionally, you could get the score from token/sequence matching for more granularity
                # For now, just select the first match
                # If multiple queries match, prefer the one with the highest index (first found)
                if best_idx is None or idx < best_idx:
                    best_idx = idx
        if best_idx is not None:
            best_candidate, best_ep = episode_meta_map[best_idx]
            control.log(f"FUZZY MATCH FOUND: Jikan '{best_candidate}' matched TMDB title (fuzzy).")
            info = {
                'mal_id': mal_id,
                'episode_number': best_ep.get('mal_id'),
                'matched_title': best_candidate,
            }
            return info
        else:
            # Fallback to direct match if fuzzy fails
            for idx, candidate in enumerate(cleaned_candidates):
                if candidate in cleaned_titles:
                    orig_candidate, ep = episode_meta_map[idx]
                    control.log(f"DIRECT MATCH FOUND: Jikan '{orig_candidate}' matched TMDB title.")
                    info = {
                        'mal_id': mal_id,
                        'episode_number': ep.get('mal_id'),
                        'matched_title': orig_candidate,
                    }
                    return info
            control.log(f"No fuzzy or direct match for Jikan episode titles against TMDB titles.")
    return None  # No match found


@Route('marked_as_watched/*')
@Route('marked_as_watched_tv_show/*')
@Route('marked_as_watched_movie/*')
@Route('marked_as_watched_tv_short/*')
@Route('marked_as_watched_special/*')
@Route('marked_as_watched_ova/*')
@Route('marked_as_watched_ona/*')
@Route('marked_as_watched_music/*')
def MARKED_AS_WATCHED(payload, params):
    from resources.lib.WatchlistFlavor import WatchlistFlavor
    from resources.lib.WatchlistIntegration import watchlist_update_episode, set_watchlist_status
    import service

    payload_list = payload.split("/")
    if len(payload_list) == 2 and payload_list[1]:
        mal_id, episode = payload_list
    else:
        mal_id = payload_list[0] if payload_list else ""
        episode = 1

    show = database.get_show(mal_id)
    if show:
        kodi_meta = pickle.loads(show['kodi_meta'])
        status = kodi_meta.get('status')
        episodes = kodi_meta.get('episodes')
        title = kodi_meta.get('title_userPreferred')
        if episode == episodes:
            if status in ['Finished Airing', 'FINISHED']:
                set_watchlist_status(mal_id, 'completed')
                set_watchlist_status(mal_id, 'COMPLETED')
                control.sleep(3000)
                service.sync_watchlist(True)
        else:
            set_watchlist_status(mal_id, 'watching')
            set_watchlist_status(mal_id, 'current')
            set_watchlist_status(mal_id, 'CURRENT')
            control.sleep(3000)
            service.sync_watchlist(True)

    flavor = WatchlistFlavor.get_update_flavor()
    watchlist_update_episode(mal_id, episode)
    if len(payload_list) == 2 and payload_list[1]:
        control.notify(control.ADDON_NAME, f'Episode #{episode} was Marked as Watched in {flavor.flavor_name}')
        control.execute(f'ActivateWindow(Videos,plugin://{control.ADDON_ID}/watchlist_to_ep/{mal_id}/{episode})')
    else:
        control.notify(control.ADDON_NAME, f'{title} was Marked as Watched in {flavor.flavor_name}')
    control.exit_code()


@Route('delete_anime_database/*')
def DELETE_ANIME_DATABASE(payload, params):
    path, mal_id, eps_watched = payload.rsplit("/")
    database.remove_from_database('shows', mal_id)
    database.remove_from_database('episodes', mal_id)
    database.remove_from_database('show_data', mal_id)
    database.remove_from_database('shows_meta', mal_id)
    control.notify(control.ADDON_NAME, 'Removed from database')
    control.exit_code()


@Route('auth/*')
def AUTH(payload, params):
    if payload == 'realdebrid':
        from resources.lib.debrid.real_debrid import RealDebrid
        RealDebrid().auth()
    elif payload == 'alldebrid':
        from resources.lib.debrid.all_debrid import AllDebrid
        AllDebrid().auth()
    elif payload == 'premiumize':
        from resources.lib.debrid.premiumize import Premiumize
        Premiumize().auth()
    elif payload == 'debridlink':
        from resources.lib.debrid.debrid_link import DebridLink
        DebridLink().auth()
    elif payload == 'torbox':
        from resources.lib.debrid.torbox import TorBox
        TorBox().auth()
    elif payload == 'easydebrid':
        from resources.lib.debrid.easydebrid import EasyDebrid
        EasyDebrid().auth()


@Route('refresh/*')
def REFRESH(payload, params):
    if payload == 'realdebrid':
        from resources.lib.debrid.real_debrid import RealDebrid
        RealDebrid().refreshToken()
    elif payload == 'debridlink':
        from resources.lib.debrid.debrid_link import DebridLink
        DebridLink().refreshToken()


@Route('fanart_select/*')
def FANART_SELECT(payload, params):
    path, mal_id, eps_watched = payload.rsplit("/")
    if not (episode := database.get_episode(mal_id)):
        MetaBrowser.get_anime_init(mal_id)
        episode = database.get_episode(mal_id)
    fanart = pickle.loads(episode['kodi_meta'])['image']['fanart'] or []
    fanart_display = fanart + ["None", "Random (Default)"]
    fanart += ["None", ""]
    control.draw_items([utils.allocate_item(f, f'fanart/{mal_id}/{i}', False, False, [], f, {}, fanart=f, landscape=f) for i, f in enumerate(fanart_display)], '')


@Route('fanart/*')
def FANART(payload: str, params: dict):
    mal_id, select = payload.rsplit('/', 1)
    episode = database.get_episode(mal_id)
    fanart = pickle.loads(episode['kodi_meta'])['image']['fanart'] or []
    fanart_display = fanart + ["None", "Random"]
    fanart += ["None", ""]

    # Set fanart selection using string lists
    mal_ids = control.getStringList('fanart.mal_ids')
    fanart_selections = control.getStringList('fanart.selections')
    mal_id_str = str(mal_id)
    fanart_url = fanart[int(select)]

    try:
        # Update existing entry
        index = mal_ids.index(mal_id_str)
        fanart_selections[index] = fanart_url
    except ValueError:
        # Add new entry
        mal_ids.append(mal_id_str)
        fanart_selections.append(fanart_url)

    control.setStringList('fanart.mal_ids', mal_ids)
    control.setStringList('fanart.selections', fanart_selections)
    control.ok_dialog(control.ADDON_NAME, f"Fanart Set to {fanart_display[int(select)]}")


def get_menu_items(menu_type):
    items = {
        'main': [
            (control.lang(30901), "airing_calendar", 'airing_anime_calendar.png', {}),
            (control.lang(30902), "airing_last_season", 'airing_anime.png', {}),
            (control.lang(30903), "airing_this_season", 'airing_anime.png', {}),
            (control.lang(30904), "airing_next_season", 'airing_anime.png', {}),
            (control.lang(30969), "recently_aired_shows", 'airing_anime.png', {}),
            (control.lang(30905), "movies", 'movies.png', {}),
            (control.lang(30906), "tv_shows", 'tv_shows.png', {}),
            (control.lang(30907), "tv_shorts", 'tv_shorts.png', {}),
            (control.lang(30908), "specials", 'specials.png', {}),
            (control.lang(30909), "ovas", 'ovas.png', {}),
            (control.lang(30910), "onas", 'onas.png', {}),
            (control.lang(30911), "music", 'music.png', {}),
            (control.lang(30912), "trending", 'trending.png', {}),
            (control.lang(30913), "popular", 'popular.png', {}),
            (control.lang(30914), "voted", 'voted.png', {}),
            (control.lang(30915), "favourites", 'favourites.png', {}),
            (control.lang(30916), "top_100", 'top_100_anime.png', {}),
            (control.lang(30917), "genres", 'genres_&_tags.png', {}),
            (control.lang(30918), "search", 'search.png', {}),
            (control.lang(30919), "tools", 'tools.png', {}),
        ],
        'movies': [
            (control.lang(30902), "airing_last_season_movie", 'airing_anime.png', {}),
            (control.lang(30903), "airing_this_season_movie", 'airing_anime.png', {}),
            (control.lang(30904), "airing_next_season_movie", 'airing_anime.png', {}),
            (control.lang(30912), "trending_movie", 'trending.png', {}),
            (control.lang(30913), "popular_movie", 'popular.png', {}),
            (control.lang(30914), "voted_movie", 'voted.png', {}),
            (control.lang(30915), "favourites_movie", 'favourites.png', {}),
            (control.lang(30916), "top_100_movie", 'top_100_anime.png', {}),
            (control.lang(30917), "genres_movie", 'genres_&_tags.png', {}),
            (control.lang(30918), "search_history_movie", 'search.png', {}),
        ],
        'tv_shows': [
            (control.lang(30902), "airing_last_season_tv_show", 'airing_anime.png', {}),
            (control.lang(30903), "airing_this_season_tv_show", 'airing_anime.png', {}),
            (control.lang(30904), "airing_next_season_tv_show", 'airing_anime.png', {}),
            (control.lang(30912), "trending_tv_show", 'trending.png', {}),
            (control.lang(30913), "popular_tv_show", 'popular.png', {}),
            (control.lang(30914), "voted_tv_show", 'voted.png', {}),
            (control.lang(30915), "favourites_tv_show", 'favourites.png', {}),
            (control.lang(30916), "top_100_tv_show", 'top_100_anime.png', {}),
            (control.lang(30917), "genres_tv_show", 'genres_&_tags.png', {}),
            (control.lang(30918), "search_history_tv_show", 'search.png', {}),
        ],
        'tv_shorts': [
            (control.lang(30902), "airing_last_season_tv_short", 'airing_anime.png', {}),
            (control.lang(30903), "airing_this_season_tv_short", 'airing_anime.png', {}),
            (control.lang(30904), "airing_next_season_tv_short", 'airing_anime.png', {}),
            (control.lang(30912), "trending_tv_short", 'trending.png', {}),
            (control.lang(30913), "popular_tv_short", 'popular.png', {}),
            (control.lang(30914), "voted_tv_short", 'voted.png', {}),
            (control.lang(30915), "favourites_tv_short", 'favourites.png', {}),
            (control.lang(30916), "top_100_tv_short", 'top_100_anime.png', {}),
            (control.lang(30917), "genres_tv_short", 'genres_&_tags.png', {}),
            (control.lang(30918), "search_history_tv_short", 'search.png', {}),
        ],
        'specials': [
            (control.lang(30902), "airing_last_season_special", 'airing_anime.png', {}),
            (control.lang(30903), "airing_this_season_special", 'airing_anime.png', {}),
            (control.lang(30904), "airing_next_season_special", 'airing_anime.png', {}),
            (control.lang(30912), "trending_special", 'trending.png', {}),
            (control.lang(30913), "popular_special", 'popular.png', {}),
            (control.lang(30914), "voted_special", 'voted.png', {}),
            (control.lang(30915), "favourites_special", 'favourites.png', {}),
            (control.lang(30916), "top_100_special", 'top_100_anime.png', {}),
            (control.lang(30917), "genres_special", 'genres_&_tags.png', {}),
            (control.lang(30918), "search_history_special", 'search.png', {}),
        ],
        'ovas': [
            (control.lang(30902), "airing_last_season_ova", 'airing_anime.png', {}),
            (control.lang(30903), "airing_this_season_ova", 'airing_anime.png', {}),
            (control.lang(30904), "airing_next_season_ova", 'airing_anime.png', {}),
            (control.lang(30912), "trending_ova", 'trending.png', {}),
            (control.lang(30913), "popular_ova", 'popular.png', {}),
            (control.lang(30914), "voted_ova", 'voted.png', {}),
            (control.lang(30915), "favourites_ova", 'favourites.png', {}),
            (control.lang(30916), "top_100_ova", 'top_100_anime.png', {}),
            (control.lang(30917), "genres_ova", 'genres_&_tags.png', {}),
            (control.lang(30918), "search_history_ova", 'search.png', {}),
        ],
        'onas': [
            (control.lang(30902), "airing_last_season_ona", 'airing_anime.png', {}),
            (control.lang(30903), "airing_this_season_ona", 'airing_anime.png', {}),
            (control.lang(30904), "airing_next_season_ona", 'airing_anime.png', {}),
            (control.lang(30912), "trending_ona", 'trending.png', {}),
            (control.lang(30913), "popular_ona", 'popular.png', {}),
            (control.lang(30914), "voted_ona", 'voted.png', {}),
            (control.lang(30915), "favourites_ona", 'favourites.png', {}),
            (control.lang(30916), "top_100_ona", 'top_100_anime.png', {}),
            (control.lang(30917), "genres_ona", 'genres_&_tags.png', {}),
            (control.lang(30918), "search_history_ona", 'search.png', {}),
        ],
        'music': [
            (control.lang(30902), "airing_last_season_music", 'airing_anime.png', {}),
            (control.lang(30903), "airing_this_season_music", 'airing_anime.png', {}),
            (control.lang(30904), "airing_next_season_music", 'airing_anime.png', {}),
            (control.lang(30912), "trending_music", 'trending.png', {}),
            (control.lang(30913), "popular_music", 'popular.png', {}),
            (control.lang(30914), "voted_music", 'voted.png', {}),
            (control.lang(30915), "favourites_music", 'favourites.png', {}),
            (control.lang(30916), "top_100_music", 'top_100_anime.png', {}),
            (control.lang(30917), "genres_music", 'genres_&_tags.png', {}),
            (control.lang(30918), "search_history_music", 'search.png', {}),
        ],
        'trending': [
            (control.lang(30920), "trending_last_year", 'trending.png', {}),
            (control.lang(30921), "trending_this_year", 'trending.png', {}),
            (control.lang(30922), "trending_last_season", 'trending.png', {}),
            (control.lang(30923), "trending_this_season", 'trending.png', {}),
            (control.lang(30924), "all_time_trending", 'trending.png', {}),
        ],
        'trending_movie': [
            (control.lang(30920), "trending_last_year_movie", 'trending.png', {}),
            (control.lang(30921), "trending_this_year_movie", 'trending.png', {}),
            (control.lang(30922), "trending_last_season_movie", 'trending.png', {}),
            (control.lang(30923), "trending_this_season_movie", 'trending.png', {}),
            (control.lang(30924), "all_time_trending_movie", 'trending.png', {}),
        ],
        'trending_tv_show': [
            (control.lang(30920), "trending_last_year_tv_show", 'trending.png', {}),
            (control.lang(30921), "trending_this_year_tv_show", 'trending.png', {}),
            (control.lang(30922), "trending_last_season_tv_show", 'trending.png', {}),
            (control.lang(30923), "trending_this_season_tv_show", 'trending.png', {}),
            (control.lang(30924), "all_time_trending_tv_show", 'trending.png', {}),
        ],
        'trending_tv_short': [
            (control.lang(30920), "trending_last_year_tv_short", 'trending.png', {}),
            (control.lang(30921), "trending_this_year_tv_short", 'trending.png', {}),
            (control.lang(30922), "trending_last_season_tv_short", 'trending.png', {}),
            (control.lang(30923), "trending_this_season_tv_short", 'trending.png', {}),
            (control.lang(30924), "all_time_trending_tv_short", 'trending.png', {}),
        ],
        'trending_special': [
            (control.lang(30920), "trending_last_year_special", 'trending.png', {}),
            (control.lang(30921), "trending_this_year_special", 'trending.png', {}),
            (control.lang(30922), "trending_last_season_special", 'trending.png', {}),
            (control.lang(30923), "trending_this_season_special", 'trending.png', {}),
            (control.lang(30924), "all_time_trending_special", 'trending.png', {}),
        ],
        'trending_ova': [
            (control.lang(30920), "trending_last_year_ova", 'trending.png', {}),
            (control.lang(30921), "trending_this_year_ova", 'trending.png', {}),
            (control.lang(30922), "trending_last_season_ova", 'trending.png', {}),
            (control.lang(30923), "trending_this_season_ova", 'trending.png', {}),
            (control.lang(30924), "all_time_trending_ova", 'trending.png', {}),
        ],
        'trending_ona': [
            (control.lang(30920), "trending_last_year_ona", 'trending.png', {}),
            (control.lang(30921), "trending_this_year_ona", 'trending.png', {}),
            (control.lang(30922), "trending_last_season_ona", 'trending.png', {}),
            (control.lang(30923), "trending_this_season_ona", 'trending.png', {}),
            (control.lang(30924), "all_time_trending_ona", 'trending.png', {}),
        ],
        'trending_music': [
            (control.lang(30920), "trending_last_year_music", 'trending.png', {}),
            (control.lang(30921), "trending_this_year_music", 'trending.png', {}),
            (control.lang(30922), "trending_last_season_music", 'trending.png', {}),
            (control.lang(30923), "trending_this_season_music", 'trending.png', {}),
            (control.lang(30924), "all_time_trending_music", 'trending.png', {}),
        ],
        'popular': [
            (control.lang(30925), "popular_last_year", 'popular.png', {}),
            (control.lang(30926), "popular_this_year", 'popular.png', {}),
            (control.lang(30927), "popular_last_season", 'popular.png', {}),
            (control.lang(30928), "popular_this_season", 'popular.png', {}),
            (control.lang(30929), "all_time_popular", 'popular.png', {}),
        ],
        'popular_movie': [
            (control.lang(30925), "popular_last_year_movie", 'popular.png', {}),
            (control.lang(30926), "popular_this_year_movie", 'popular.png', {}),
            (control.lang(30927), "popular_last_season_movie", 'popular.png', {}),
            (control.lang(30928), "popular_this_season_movie", 'popular.png', {}),
            (control.lang(30929), "all_time_popular_movie", 'popular.png', {}),
        ],
        'popular_tv_show': [
            (control.lang(30925), "popular_last_year_tv_show", 'popular.png', {}),
            (control.lang(30926), "popular_this_year_tv_show", 'popular.png', {}),
            (control.lang(30927), "popular_last_season_tv_show", 'popular.png', {}),
            (control.lang(30928), "popular_this_season_tv_show", 'popular.png', {}),
            (control.lang(30929), "all_time_popular_tv_show", 'popular.png', {}),
        ],
        'popular_tv_short': [
            (control.lang(30925), "popular_last_year_tv_short", 'popular.png', {}),
            (control.lang(30926), "popular_this_year_tv_short", 'popular.png', {}),
            (control.lang(30927), "popular_last_season_tv_short", 'popular.png', {}),
            (control.lang(30928), "popular_this_season_tv_short", 'popular.png', {}),
            (control.lang(30929), "all_time_popular_tv_short", 'popular.png', {}),
        ],
        'popular_special': [
            (control.lang(30925), "popular_last_year_special", 'popular.png', {}),
            (control.lang(30926), "popular_this_year_special", 'popular.png', {}),
            (control.lang(30927), "popular_last_season_special", 'popular.png', {}),
            (control.lang(30928), "popular_this_season_special", 'popular.png', {}),
            (control.lang(30929), "all_time_popular_special", 'popular.png', {}),
        ],
        'popular_ova': [
            (control.lang(30925), "popular_last_year_ova", 'popular.png', {}),
            (control.lang(30926), "popular_this_year_ova", 'popular.png', {}),
            (control.lang(30927), "popular_last_season_ova", 'popular.png', {}),
            (control.lang(30928), "popular_this_season_ova", 'popular.png', {}),
            (control.lang(30929), "all_time_popular_ova", 'popular.png', {}),
        ],
        'popular_ona': [
            (control.lang(30925), "popular_last_year_ona", 'popular.png', {}),
            (control.lang(30926), "popular_this_year_ona", 'popular.png', {}),
            (control.lang(30927), "popular_last_season_ona", 'popular.png', {}),
            (control.lang(30928), "popular_this_season_ona", 'popular.png', {}),
            (control.lang(30929), "all_time_popular_ona", 'popular.png', {}),
        ],
        'popular_music': [
            (control.lang(30925), "popular_last_year_music", 'popular.png', {}),
            (control.lang(30926), "popular_this_year_music", 'popular.png', {}),
            (control.lang(30927), "popular_last_season_music", 'popular.png', {}),
            (control.lang(30928), "popular_this_season_music", 'popular.png', {}),
            (control.lang(30929), "all_time_popular_music", 'popular.png', {}),
        ],
        'voted': [
            (control.lang(30930), "voted_last_year", 'voted.png', {}),
            (control.lang(30931), "voted_this_year", 'voted.png', {}),
            (control.lang(30932), "voted_last_season", 'voted.png', {}),
            (control.lang(30933), "voted_this_season", 'voted.png', {}),
            (control.lang(30934), "all_time_voted", 'voted.png', {}),
        ],
        'voted_movie': [
            (control.lang(30930), "voted_last_year_movie", 'voted.png', {}),
            (control.lang(30931), "voted_this_year_movie", 'voted.png', {}),
            (control.lang(30932), "voted_last_season_movie", 'voted.png', {}),
            (control.lang(30933), "voted_this_season_movie", 'voted.png', {}),
            (control.lang(30934), "all_time_voted_movie", 'voted.png', {}),
        ],
        'voted_tv_show': [
            (control.lang(30930), "voted_last_year_tv_show", 'voted.png', {}),
            (control.lang(30931), "voted_this_year_tv_show", 'voted.png', {}),
            (control.lang(30932), "voted_last_season_tv_show", 'voted.png', {}),
            (control.lang(30933), "voted_this_season_tv_show", 'voted.png', {}),
            (control.lang(30934), "all_time_voted_tv_show", 'voted.png', {}),
        ],
        'voted_tv_short': [
            (control.lang(30930), "voted_last_year_tv_short", 'voted.png', {}),
            (control.lang(30931), "voted_this_year_tv_short", 'voted.png', {}),
            (control.lang(30932), "voted_last_season_tv_short", 'voted.png', {}),
            (control.lang(30933), "voted_this_season_tv_short", 'voted.png', {}),
            (control.lang(30934), "all_time_voted_tv_short", 'voted.png', {}),
        ],
        'voted_special': [
            (control.lang(30930), "voted_last_year_special", 'voted.png', {}),
            (control.lang(30931), "voted_this_year_special", 'voted.png', {}),
            (control.lang(30932), "voted_last_season_special", 'voted.png', {}),
            (control.lang(30933), "voted_this_season_special", 'voted.png', {}),
            (control.lang(30934), "all_time_voted_special", 'voted.png', {}),
        ],
        'voted_ova': [
            (control.lang(30930), "voted_last_year_ova", 'voted.png', {}),
            (control.lang(30931), "voted_this_year_ova", 'voted.png', {}),
            (control.lang(30932), "voted_last_season_ova", 'voted.png', {}),
            (control.lang(30933), "voted_this_season_ova", 'voted.png', {}),
            (control.lang(30934), "all_time_voted_ova", 'voted.png', {}),
        ],
        'voted_ona': [
            (control.lang(30930), "voted_last_year_ona", 'voted.png', {}),
            (control.lang(30931), "voted_this_year_ona", 'voted.png', {}),
            (control.lang(30932), "voted_last_season_ona", 'voted.png', {}),
            (control.lang(30933), "voted_this_season_ona", 'voted.png', {}),
            (control.lang(30934), "all_time_voted_ona", 'voted.png', {}),
        ],
        'voted_music': [
            (control.lang(30930), "voted_last_year_music", 'voted.png', {}),
            (control.lang(30931), "voted_this_year_music", 'voted.png', {}),
            (control.lang(30932), "voted_last_season_music", 'voted.png', {}),
            (control.lang(30933), "voted_this_season_music", 'voted.png', {}),
            (control.lang(30934), "all_time_voted_music", 'voted.png', {}),
        ],
        'favourites': [
            (control.lang(30935), "favourites_last_year", 'favourites.png', {}),
            (control.lang(30936), "favourites_this_year", 'favourites.png', {}),
            (control.lang(30937), "favourites_last_season", 'favourites.png', {}),
            (control.lang(30938), "favourites_this_season", 'favourites.png', {}),
            (control.lang(30939), "all_time_favourites", 'favourites.png', {}),
        ],
        'favourites_movie': [
            (control.lang(30935), "favourites_last_year_movie", 'favourites.png', {}),
            (control.lang(30936), "favourites_this_year_movie", 'favourites.png', {}),
            (control.lang(30937), "favourites_last_season_movie", 'favourites.png', {}),
            (control.lang(30938), "favourites_this_season_movie", 'favourites.png', {}),
            (control.lang(30939), "all_time_favourites_movie", 'favourites.png', {}),
        ],
        'favourites_tv_show': [
            (control.lang(30935), "favourites_last_year_tv_show", 'favourites.png', {}),
            (control.lang(30936), "favourites_this_year_tv_show", 'favourites.png', {}),
            (control.lang(30937), "favourites_last_season_tv_show", 'favourites.png', {}),
            (control.lang(30938), "favourites_this_season_tv_show", 'favourites.png', {}),
            (control.lang(30939), "all_time_favourites_tv_show", 'favourites.png', {}),
        ],
        'favourites_tv_short': [
            (control.lang(30935), "favourites_last_year_tv_short", 'favourites.png', {}),
            (control.lang(30936), "favourites_this_year_tv_short", 'favourites.png', {}),
            (control.lang(30937), "favourites_last_season_tv_short", 'favourites.png', {}),
            (control.lang(30938), "favourites_this_season_tv_short", 'favourites.png', {}),
            (control.lang(30939), "all_time_favourites_tv_short", 'favourites.png', {}),
        ],
        'favourites_special': [
            (control.lang(30935), "favourites_last_year_special", 'favourites.png', {}),
            (control.lang(30936), "favourites_this_year_special", 'favourites.png', {}),
            (control.lang(30937), "favourites_last_season_special", 'favourites.png', {}),
            (control.lang(30938), "favourites_this_season_special", 'favourites.png', {}),
            (control.lang(30939), "all_time_favourites_special", 'favourites.png', {}),
        ],
        'favourites_ova': [
            (control.lang(30935), "favourites_last_year_ova", 'favourites.png', {}),
            (control.lang(30936), "favourites_this_year_ova", 'favourites.png', {}),
            (control.lang(30937), "favourites_last_season_ova", 'favourites.png', {}),
            (control.lang(30938), "favourites_this_season_ova", 'favourites.png', {}),
            (control.lang(30939), "all_time_favourites_ova", 'favourites.png', {}),
        ],
        'favourites_ona': [
            (control.lang(30935), "favourites_last_year_ona", 'favourites.png', {}),
            (control.lang(30936), "favourites_this_year_ona", 'favourites.png', {}),
            (control.lang(30937), "favourites_last_season_ona", 'favourites.png', {}),
            (control.lang(30938), "favourites_this_season_ona", 'favourites.png', {}),
            (control.lang(30939), "all_time_favourites_ona", 'favourites.png', {}),
        ],
        'favourites_music': [
            (control.lang(30935), "favourites_last_year_music", 'favourites.png', {}),
            (control.lang(30936), "favourites_this_year_music", 'favourites.png', {}),
            (control.lang(30937), "favourites_last_season_music", 'favourites.png', {}),
            (control.lang(30938), "favourites_this_season_music", 'favourites.png', {}),
            (control.lang(30939), "all_time_favourites_music", 'favourites.png', {}),
        ],
        'genres': [
            (control.lang(30940), "genres//", 'genre_multi.png', {}),
            (control.lang(30941), "genre_action", 'genre_action.png', {}),
            (control.lang(30942), "genre_adventure", 'genre_adventure.png', {}),
            (control.lang(30943), "genre_comedy", 'genre_comedy.png', {}),
            (control.lang(30944), "genre_drama", 'genre_drama.png', {}),
            (control.lang(30945), "genre_ecchi", 'genre_ecchi.png', {}),
            (control.lang(30946), "genre_fantasy", 'genre_fantasy.png', {}),
            (control.lang(30947), "genre_hentai", 'genre_hentai.png', {}),
            (control.lang(30948), "genre_horror", 'genre_horror.png', {}),
            (control.lang(30949), "genre_shoujo", 'genre_shoujo.png', {}),
            (control.lang(30950), "genre_mecha", 'genre_mecha.png', {}),
            (control.lang(30951), "genre_music", 'genre_music.png', {}),
            (control.lang(30952), "genre_mystery", 'genre_mystery.png', {}),
            (control.lang(30953), "genre_psychological", 'genre_psychological.png', {}),
            (control.lang(30954), "genre_romance", 'genre_romance.png', {}),
            (control.lang(30955), "genre_sci_fi", 'genre_sci-fi.png', {}),
            (control.lang(30956), "genre_slice_of_life", 'genre_slice_of_life.png', {}),
            (control.lang(30957), "genre_sports", 'genre_sports.png', {}),
            (control.lang(30958), "genre_supernatural", 'genre_supernatural.png', {}),
            (control.lang(30959), "genre_thriller", 'genre_thriller.png', {}),
        ],
        'genres_movie': [
            (control.lang(30940), "genres_movie//", 'genre_multi.png', {}),
            (control.lang(30941), "genre_action_movie", 'genre_action.png', {}),
            (control.lang(30942), "genre_adventure_movie", 'genre_adventure.png', {}),
            (control.lang(30943), "genre_comedy_movie", 'genre_comedy.png', {}),
            (control.lang(30944), "genre_drama_movie", 'genre_drama.png', {}),
            (control.lang(30945), "genre_ecchi_movie", 'genre_ecchi.png', {}),
            (control.lang(30946), "genre_fantasy_movie", 'genre_fantasy.png', {}),
            (control.lang(30947), "genre_hentai_movie", 'genre_hentai.png', {}),
            (control.lang(30948), "genre_horror_movie", 'genre_horror.png', {}),
            (control.lang(30949), "genre_shoujo_movie", 'genre_shoujo.png', {}),
            (control.lang(30950), "genre_mecha_movie", 'genre_mecha.png', {}),
            (control.lang(30951), "genre_music_movie", 'genre_music.png', {}),
            (control.lang(30952), "genre_mystery_movie", 'genre_mystery.png', {}),
            (control.lang(30953), "genre_psychological_movie", 'genre_psychological.png', {}),
            (control.lang(30954), "genre_romance_movie", 'genre_romance.png', {}),
            (control.lang(30955), "genre_sci_fi_movie", 'genre_sci-fi.png', {}),
            (control.lang(30956), "genre_slice_of_life_movie", 'genre_slice_of_life.png', {}),
            (control.lang(30957), "genre_sports_movie", 'genre_sports.png', {}),
            (control.lang(30958), "genre_supernatural_movie", 'genre_supernatural.png', {}),
            (control.lang(30959), "genre_thriller_movie", 'genre_thriller.png', {}),
        ],
        'genres_tv_show': [
            (control.lang(30940), "genres_tv_show//", 'genre_multi.png', {}),
            (control.lang(30941), "genre_action_tv_show", 'genre_action.png', {}),
            (control.lang(30942), "genre_adventure_tv_show", 'genre_adventure.png', {}),
            (control.lang(30943), "genre_comedy_tv_show", 'genre_comedy.png', {}),
            (control.lang(30944), "genre_drama_tv_show", 'genre_drama.png', {}),
            (control.lang(30945), "genre_ecchi_tv_show", 'genre_ecchi.png', {}),
            (control.lang(30946), "genre_fantasy_tv_show", 'genre_fantasy.png', {}),
            (control.lang(30947), "genre_hentai_tv_show", 'genre_hentai.png', {}),
            (control.lang(30948), "genre_horror_tv_show", 'genre_horror.png', {}),
            (control.lang(30949), "genre_shoujo_tv_show", 'genre_shoujo.png', {}),
            (control.lang(30950), "genre_mecha_tv_show", 'genre_mecha.png', {}),
            (control.lang(30951), "genre_music_tv_show", 'genre_music.png', {}),
            (control.lang(30952), "genre_mystery_tv_show", 'genre_mystery.png', {}),
            (control.lang(30953), "genre_psychological_tv_show", 'genre_psychological.png', {}),
            (control.lang(30954), "genre_romance_tv_show", 'genre_romance.png', {}),
            (control.lang(30955), "genre_sci_fi_tv_show", 'genre_sci-fi.png', {}),
            (control.lang(30956), "genre_slice_of_life_tv_show", 'genre_slice_of_life.png', {}),
            (control.lang(30957), "genre_sports_tv_show", 'genre_sports.png', {}),
            (control.lang(30958), "genre_supernatural_tv_show", 'genre_supernatural.png', {}),
            (control.lang(30959), "genre_thriller_tv_show", 'genre_thriller.png', {}),
        ],
        'genres_tv_short': [
            (control.lang(30940), "genres_tv_short//", 'genre_multi.png', {}),
            (control.lang(30941), "genre_action_tv_short", 'genre_action.png', {}),
            (control.lang(30942), "genre_adventure_tv_short", 'genre_adventure.png', {}),
            (control.lang(30943), "genre_comedy_tv_short", 'genre_comedy.png', {}),
            (control.lang(30944), "genre_drama_tv_short", 'genre_drama.png', {}),
            (control.lang(30945), "genre_ecchi_tv_short", 'genre_ecchi.png', {}),
            (control.lang(30946), "genre_fantasy_tv_short", 'genre_fantasy.png', {}),
            (control.lang(30947), "genre_hentai_tv_short", 'genre_hentai.png', {}),
            (control.lang(30948), "genre_horror_tv_short", 'genre_horror.png', {}),
            (control.lang(30949), "genre_shoujo_tv_short", 'genre_shoujo.png', {}),
            (control.lang(30950), "genre_mecha_tv_short", 'genre_mecha.png', {}),
            (control.lang(30951), "genre_music_tv_short", 'genre_music.png', {}),
            (control.lang(30952), "genre_mystery_tv_short", 'genre_mystery.png', {}),
            (control.lang(30953), "genre_psychological_tv_short", 'genre_psychological.png', {}),
            (control.lang(30954), "genre_romance_tv_short", 'genre_romance.png', {}),
            (control.lang(30955), "genre_sci_fi_tv_short", 'genre_sci-fi.png', {}),
            (control.lang(30956), "genre_slice_of_life_tv_short", 'genre_slice_of_life.png', {}),
            (control.lang(30957), "genre_sports_tv_short", 'genre_sports.png', {}),
            (control.lang(30958), "genre_supernatural_tv_short", 'genre_supernatural.png', {}),
            (control.lang(30959), "genre_thriller_tv_short", 'genre_thriller.png', {}),
        ],
        'genres_special': [
            (control.lang(30940), "genres_special//", 'genre_multi.png', {}),
            (control.lang(30941), "genre_action_special", 'genre_action.png', {}),
            (control.lang(30942), "genre_adventure_special", 'genre_adventure.png', {}),
            (control.lang(30943), "genre_comedy_special", 'genre_comedy.png', {}),
            (control.lang(30944), "genre_drama_special", 'genre_drama.png', {}),
            (control.lang(30945), "genre_ecchi_special", 'genre_ecchi.png', {}),
            (control.lang(30946), "genre_fantasy_special", 'genre_fantasy.png', {}),
            (control.lang(30947), "genre_hentai_special", 'genre_hentai.png', {}),
            (control.lang(30948), "genre_horror_special", 'genre_horror.png', {}),
            (control.lang(30949), "genre_shoujo_special", 'genre_shoujo.png', {}),
            (control.lang(30950), "genre_mecha_special", 'genre_mecha.png', {}),
            (control.lang(30951), "genre_music_special", 'genre_music.png', {}),
            (control.lang(30952), "genre_mystery_special", 'genre_mystery.png', {}),
            (control.lang(30953), "genre_psychological_special", 'genre_psychological.png', {}),
            (control.lang(30954), "genre_romance_special", 'genre_romance.png', {}),
            (control.lang(30955), "genre_sci_fi_special", 'genre_sci-fi.png', {}),
            (control.lang(30956), "genre_slice_of_life_special", 'genre_slice_of_life.png', {}),
            (control.lang(30957), "genre_sports_special", 'genre_sports.png', {}),
            (control.lang(30958), "genre_supernatural_special", 'genre_supernatural.png', {}),
            (control.lang(30959), "genre_thriller_special", 'genre_thriller.png', {}),
        ],
        'genres_ova': [
            (control.lang(30940), "genres_ova//", 'genre_multi.png', {}),
            (control.lang(30941), "genre_action_ova", 'genre_action.png', {}),
            (control.lang(30942), "genre_adventure_ova", 'genre_adventure.png', {}),
            (control.lang(30943), "genre_comedy_ova", 'genre_comedy.png', {}),
            (control.lang(30944), "genre_drama_ova", 'genre_drama.png', {}),
            (control.lang(30945), "genre_ecchi_ova", 'genre_ecchi.png', {}),
            (control.lang(30946), "genre_fantasy_ova", 'genre_fantasy.png', {}),
            (control.lang(30947), "genre_hentai_ova", 'genre_hentai.png', {}),
            (control.lang(30948), "genre_horror_ova", 'genre_horror.png', {}),
            (control.lang(30949), "genre_shoujo_ova", 'genre_shoujo.png', {}),
            (control.lang(30950), "genre_mecha_ova", 'genre_mecha.png', {}),
            (control.lang(30951), "genre_music_ova", 'genre_music.png', {}),
            (control.lang(30952), "genre_mystery_ova", 'genre_mystery.png', {}),
            (control.lang(30953), "genre_psychological_ova", 'genre_psychological.png', {}),
            (control.lang(30954), "genre_romance_ova", 'genre_romance.png', {}),
            (control.lang(30955), "genre_sci_fi_ova", 'genre_sci-fi.png', {}),
            (control.lang(30956), "genre_slice_of_life_ova", 'genre_slice_of_life.png', {}),
            (control.lang(30957), "genre_sports_ova", 'genre_sports.png', {}),
            (control.lang(30958), "genre_supernatural_ova", 'genre_supernatural.png', {}),
            (control.lang(30959), "genre_thriller_ova", 'genre_thriller.png', {}),
        ],
        'genres_ona': [
            (control.lang(30940), "genres_ona//", 'genre_multi.png', {}),
            (control.lang(30941), "genre_action_ona", 'genre_action.png', {}),
            (control.lang(30942), "genre_adventure_ona", 'genre_adventure.png', {}),
            (control.lang(30943), "genre_comedy_ona", 'genre_comedy.png', {}),
            (control.lang(30944), "genre_drama_ona", 'genre_drama.png', {}),
            (control.lang(30945), "genre_ecchi_ona", 'genre_ecchi.png', {}),
            (control.lang(30946), "genre_fantasy_ona", 'genre_fantasy.png', {}),
            (control.lang(30947), "genre_hentai_ona", 'genre_hentai.png', {}),
            (control.lang(30948), "genre_horror_ona", 'genre_horror.png', {}),
            (control.lang(30949), "genre_shoujo_ona", 'genre_shoujo.png', {}),
            (control.lang(30950), "genre_mecha_ona", 'genre_mecha.png', {}),
            (control.lang(30951), "genre_music_ona", 'genre_music.png', {}),
            (control.lang(30952), "genre_mystery_ona", 'genre_mystery.png', {}),
            (control.lang(30953), "genre_psychological_ona", 'genre_psychological.png', {}),
            (control.lang(30954), "genre_romance_ona", 'genre_romance.png', {}),
            (control.lang(30955), "genre_sci_fi_ona", 'genre_sci-fi.png', {}),
            (control.lang(30956), "genre_slice_of_life_ona", 'genre_slice_of_life.png', {}),
            (control.lang(30957), "genre_sports_ona", 'genre_sports.png', {}),
            (control.lang(30958), "genre_supernatural_ona", 'genre_supernatural.png', {}),
            (control.lang(30959), "genre_thriller_ona", 'genre_thriller.png', {}),
        ],
        'genres_music': [
            (control.lang(30940), "genres_music//", 'genre_multi.png', {}),
            (control.lang(30941), "genre_action_music", 'genre_action.png', {}),
            (control.lang(30942), "genre_adventure_music", 'genre_adventure.png', {}),
            (control.lang(30943), "genre_comedy_music", 'genre_comedy.png', {}),
            (control.lang(30944), "genre_drama_music", 'genre_drama.png', {}),
            (control.lang(30945), "genre_ecchi_music", 'genre_ecchi.png', {}),
            (control.lang(30946), "genre_fantasy_music", 'genre_fantasy.png', {}),
            (control.lang(30947), "genre_hentai_music", 'genre_hentai.png', {}),
            (control.lang(30948), "genre_horror_music", 'genre_horror.png', {}),
            (control.lang(30949), "genre_shoujo_music", 'genre_shoujo.png', {}),
            (control.lang(30950), "genre_mecha_music", 'genre_mecha.png', {}),
            (control.lang(30951), "genre_music_music", 'genre_music.png', {}),
            (control.lang(30952), "genre_mystery_music", 'genre_mystery.png', {}),
            (control.lang(30953), "genre_psychological_music", 'genre_psychological.png', {}),
            (control.lang(30954), "genre_romance_music", 'genre_romance.png', {}),
            (control.lang(30955), "genre_sci_fi_music", 'genre_sci-fi.png', {}),
            (control.lang(30956), "genre_slice_of_life_music", 'genre_slice_of_life.png', {}),
            (control.lang(30957), "genre_sports_music", 'genre_sports.png', {}),
            (control.lang(30958), "genre_supernatural_music", 'genre_supernatural.png', {}),
            (control.lang(30959), "genre_thriller_music", 'genre_thriller.png', {}),
        ],
        'search': [
            (control.lang(30960), "search_history_anime", 'search.png', {}),
            (control.lang(30961), "search_history_movie", 'search.png', {}),
            (control.lang(30962), "search_history_tv_show", 'search.png', {}),
            (control.lang(30963), "search_history_tv_short", 'search.png', {}),
            (control.lang(30964), "search_history_special", 'search.png', {}),
            (control.lang(30965), "search_history_ova", 'search.png', {}),
            (control.lang(30966), "search_history_ona", 'search.png', {}),
            (control.lang(30967), "search_history_music", 'search.png', {}),
        ],
        'tools': [
            (control.lang(30009), "setup_wizard", 'tools.png', {}),
            (control.lang(30010), "change_log", 'changelog.png', {}),
            (control.lang(30011), "settings", 'open_settings_menu.png', {}),
            (control.lang(30012), "clear_cache", 'clear_cache.png', {}),
            (control.lang(30013), "clear_search_history", 'clear_search_history.png', {}),
            (control.lang(30014), "clear_watch_history", 'clear_watch_history.png', {}),
            (control.lang(30015), "rebuild_database", 'rebuild_database.png', {}),
            (control.lang(30016), "wipe_addon_data", 'wipe_addon_data.png', {}),
            (control.lang(30017), "completed_sync", 'sync_completed.png', {}),
            (control.lang(30018), 'download_manager', 'download_manager.png', {}),
            (control.lang(30019), 'sort_select', 'sort_select.png', {}),
            (control.lang(30020), 'clear_selected_fanart', 'wipe_addon_data.png', {}),
        ],
    }
    return items.get(menu_type, [])


@Route('')
def LIST_MENU(payload, params):
    # Check if menu needs refreshing due to recent playback
    if control.getGlobalProp('otaku.menu.needs_refresh') == 'true':
        control.clearGlobalProp('otaku.menu.needs_refresh')
        control.log('Menu refresh flag detected - rebuilding menu items')

    MENU_ITEMS = get_menu_items('main')

    enabled_menu_items = []
    enabled_menu_items = add_watchlist(enabled_menu_items)

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('menu.mainmenu.config')

    if "last_watched" in enabled_ids:
        enabled_menu_items = add_last_watched(enabled_menu_items)

    if "watch_history" in enabled_ids:
        enabled_menu_items = add_watch_history(enabled_menu_items)

    for item in MENU_ITEMS:
        if item[1] in enabled_ids:
            enabled_menu_items.append(item)

    # Process items, handling special last_watched items
    processed_items = []
    for item in enabled_menu_items:
        if len(item) == 6 and item[0] == 'LAST_WATCHED_ITEM':
            # This is a last_watched item - use utils.parse_view
            _, name, url, image, info, kodi_meta = item

            base = {
                'name': name,
                'url': url,
                'image': image,
                'poster': image,
                'fanart': kodi_meta.get('fanart', ''),
                'banner': image,
                'info': info
            }

            # Add artwork
            import random
            if kodi_meta.get('thumb'):
                base['landscape'] = random.choice(kodi_meta['thumb'])
            if kodi_meta.get('clearart'):
                base['clearart'] = random.choice(kodi_meta['clearart'])
            if kodi_meta.get('clearlogo'):
                base['clearlogo'] = random.choice(kodi_meta['clearlogo'])

            # Determine if it's a movie or TV show
            episodes = kodi_meta.get('episodes', 0)
            if episodes == 1:
                processed_items.append(utils.parse_view(base, False, True, False))  # Movie
            else:
                processed_items.append(utils.parse_view(base, True, False, False))   # TV Show
        else:
            # Regular menu item
            name, url, image, info = item
            processed_items.append(utils.allocate_item(name, url, True, False, [], image, info))

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items(processed_items, view_type)


@Route('movies')
def MOVIES_MENU(payload, params):
    # Check if menu needs refreshing due to recent playback
    if control.getGlobalProp('otaku.menu.needs_refresh') == 'true':
        control.clearGlobalProp('otaku.menu.needs_refresh')
        control.log('Movie menu refresh flag detected - rebuilding menu items')

    MOVIES_ITEMS = get_menu_items('movies')

    enabled_movies_items = []
    enabled_movies_items = add_watchlist(enabled_movies_items)

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('movie.mainmenu.config')

    if "last_watched_movie" in enabled_ids:
        enabled_movies_items = add_last_watched(enabled_movies_items)

    if "watch_history_movie" in enabled_ids:
        enabled_movies_items = add_watch_history(enabled_movies_items)

    for item in MOVIES_ITEMS:
        if item[1] in enabled_ids:
            enabled_movies_items.append(item)

    # Process items, handling special last_watched items
    processed_items = []
    for item in enabled_movies_items:
        if len(item) == 6 and item[0] == 'LAST_WATCHED_ITEM':
            # This is a last_watched item - use utils.parse_view
            _, name, url, image, info, kodi_meta = item

            base = {
                'name': name,
                'url': url,
                'image': image,
                'poster': image,
                'fanart': kodi_meta.get('fanart', ''),
                'banner': image,
                'info': info
            }

            # Add artwork
            import random
            if kodi_meta.get('thumb'):
                base['landscape'] = random.choice(kodi_meta['thumb'])
            if kodi_meta.get('clearart'):
                base['clearart'] = random.choice(kodi_meta['clearart'])
            if kodi_meta.get('clearlogo'):
                base['clearlogo'] = random.choice(kodi_meta['clearlogo'])

            # Determine if it's a movie or TV show
            episodes = kodi_meta.get('episodes', 0)
            if episodes == 1:
                processed_items.append(utils.parse_view(base, False, True, False))  # Movie
            else:
                processed_items.append(utils.parse_view(base, True, False, False))   # TV Show
        else:
            # Regular menu item
            name, url, image, info = item
            processed_items.append(utils.allocate_item(name, url, True, False, [], image, info))

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items(processed_items, view_type)


@Route('tv_shows')
def TV_SHOWS_MENU(payload, params):
    # Check if menu needs refreshing due to recent playback
    if control.getGlobalProp('otaku.menu.needs_refresh') == 'true':
        control.clearGlobalProp('otaku.menu.needs_refresh')
        control.log('TV shows menu refresh flag detected - rebuilding menu items')

    TV_SHOWS_ITEMS = get_menu_items('tv_shows')

    enabled_tv_show_items = []
    enabled_tv_show_items = add_watchlist(enabled_tv_show_items)

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('tv_show.mainmenu.config')

    if "last_watched_tv_show" in enabled_ids:
        enabled_tv_show_items = add_last_watched(enabled_tv_show_items)

    if "watch_history_tv_show" in enabled_ids:
        enabled_tv_show_items = add_watch_history(enabled_tv_show_items)

    for item in TV_SHOWS_ITEMS:
        if item[1] in enabled_ids:
            enabled_tv_show_items.append(item)

    # Process items, handling special last_watched items
    processed_items = []
    for item in enabled_tv_show_items:
        if len(item) == 6 and item[0] == 'LAST_WATCHED_ITEM':
            # This is a last_watched item - use utils.parse_view
            _, name, url, image, info, kodi_meta = item

            base = {
                'name': name,
                'url': url,
                'image': image,
                'poster': image,
                'fanart': kodi_meta.get('fanart', ''),
                'banner': image,
                'info': info
            }

            # Add artwork
            import random
            if kodi_meta.get('thumb'):
                base['landscape'] = random.choice(kodi_meta['thumb'])
            if kodi_meta.get('clearart'):
                base['clearart'] = random.choice(kodi_meta['clearart'])
            if kodi_meta.get('clearlogo'):
                base['clearlogo'] = random.choice(kodi_meta['clearlogo'])

            # Determine if it's a movie or TV show
            episodes = kodi_meta.get('episodes', 0)
            if episodes == 1:
                processed_items.append(utils.parse_view(base, False, True, False))  # Movie
            else:
                processed_items.append(utils.parse_view(base, True, False, False))   # TV Show
        else:
            # Regular menu item
            name, url, image, info = item
            processed_items.append(utils.allocate_item(name, url, True, False, [], image, info))

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items(processed_items, view_type)


@Route('tv_shorts')
def TV_SHORTS_MENU(payload, params):
    # Check if menu needs refreshing due to recent playback
    if control.getGlobalProp('otaku.menu.needs_refresh') == 'true':
        control.clearGlobalProp('otaku.menu.needs_refresh')
        control.log('TV shorts menu refresh flag detected - rebuilding menu items')

    TV_SHORTS_ITEMS = get_menu_items('tv_shorts')

    enabled_tv_short_items = []
    enabled_tv_short_items = add_watchlist(enabled_tv_short_items)

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('tv_short.mainmenu.config')

    if "last_watched_tv_short" in enabled_ids:
        enabled_tv_short_items = add_last_watched(enabled_tv_short_items)

    if "watch_history_tv_short" in enabled_ids:
        enabled_tv_short_items = add_watch_history(enabled_tv_short_items)

    for item in TV_SHORTS_ITEMS:
        if item[1] in enabled_ids:
            enabled_tv_short_items.append(item)

    # Process items, handling special last_watched items
    processed_items = []
    for item in enabled_tv_short_items:
        if len(item) == 6 and item[0] == 'LAST_WATCHED_ITEM':
            # This is a last_watched item - use utils.parse_view
            _, name, url, image, info, kodi_meta = item

            base = {
                'name': name,
                'url': url,
                'image': image,
                'poster': image,
                'fanart': kodi_meta.get('fanart', ''),
                'banner': image,
                'info': info
            }

            # Add artwork
            import random
            if kodi_meta.get('thumb'):
                base['landscape'] = random.choice(kodi_meta['thumb'])
            if kodi_meta.get('clearart'):
                base['clearart'] = random.choice(kodi_meta['clearart'])
            if kodi_meta.get('clearlogo'):
                base['clearlogo'] = random.choice(kodi_meta['clearlogo'])

            # Determine if it's a movie or TV show
            episodes = kodi_meta.get('episodes', 0)
            if episodes == 1:
                processed_items.append(utils.parse_view(base, False, True, False))  # Movie
            else:
                processed_items.append(utils.parse_view(base, True, False, False))   # TV Show
        else:
            # Regular menu item
            name, url, image, info = item
            processed_items.append(utils.allocate_item(name, url, True, False, [], image, info))

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items(processed_items, view_type)


@Route('specials')
def SPECIALS_MENU(payload, params):
    # Check if menu needs refreshing due to recent playback
    if control.getGlobalProp('otaku.menu.needs_refresh') == 'true':
        control.clearGlobalProp('otaku.menu.needs_refresh')
        control.log('Specials menu refresh flag detected - rebuilding menu items')

    SPECIALS_ITEMS = get_menu_items('specials')

    enabled_special_items = []
    enabled_special_items = add_watchlist(enabled_special_items)

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('special.mainmenu.config')

    if "last_watched_special" in enabled_ids:
        enabled_special_items = add_last_watched(enabled_special_items)

    if "watch_history_special" in enabled_ids:
        enabled_special_items = add_watch_history(enabled_special_items)

    for item in SPECIALS_ITEMS:
        if item[1] in enabled_ids:
            enabled_special_items.append(item)

    # Process items, handling special last_watched items
    processed_items = []
    for item in enabled_special_items:
        if len(item) == 6 and item[0] == 'LAST_WATCHED_ITEM':
            # This is a last_watched item - use utils.parse_view
            _, name, url, image, info, kodi_meta = item

            base = {
                'name': name,
                'url': url,
                'image': image,
                'poster': image,
                'fanart': kodi_meta.get('fanart', ''),
                'banner': image,
                'info': info
            }

            # Add artwork
            import random
            if kodi_meta.get('thumb'):
                base['landscape'] = random.choice(kodi_meta['thumb'])
            if kodi_meta.get('clearart'):
                base['clearart'] = random.choice(kodi_meta['clearart'])
            if kodi_meta.get('clearlogo'):
                base['clearlogo'] = random.choice(kodi_meta['clearlogo'])

            # Determine if it's a movie or TV show
            episodes = kodi_meta.get('episodes', 0)
            if episodes == 1:
                processed_items.append(utils.parse_view(base, False, True, False))  # Movie
            else:
                processed_items.append(utils.parse_view(base, True, False, False))   # TV Show
        else:
            # Regular menu item
            name, url, image, info = item
            processed_items.append(utils.allocate_item(name, url, True, False, [], image, info))

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items(processed_items, view_type)


@Route('ovas')
def OVAS_MENU(payload, params):
    # Check if menu needs refreshing due to recent playback
    if control.getGlobalProp('otaku.menu.needs_refresh') == 'true':
        control.clearGlobalProp('otaku.menu.needs_refresh')
        control.log('OVAs menu refresh flag detected - rebuilding menu items')

    OVAS_ITEMS = get_menu_items('ovas')

    enabled_ova_items = []
    enabled_ova_items = add_watchlist(enabled_ova_items)

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('ova.mainmenu.config')

    if "last_watched_ova" in enabled_ids:
        enabled_ova_items = add_last_watched(enabled_ova_items)

    if "watch_history_ova" in enabled_ids:
        enabled_ova_items = add_watch_history(enabled_ova_items)

    for item in OVAS_ITEMS:
        if item[1] in enabled_ids:
            enabled_ova_items.append(item)

    # Process items, handling special last_watched items
    processed_items = []
    for item in enabled_ova_items:
        if len(item) == 6 and item[0] == 'LAST_WATCHED_ITEM':
            # This is a last_watched item - use utils.parse_view
            _, name, url, image, info, kodi_meta = item

            base = {
                'name': name,
                'url': url,
                'image': image,
                'poster': image,
                'fanart': kodi_meta.get('fanart', ''),
                'banner': image,
                'info': info
            }

            # Add artwork
            import random
            if kodi_meta.get('thumb'):
                base['landscape'] = random.choice(kodi_meta['thumb'])
            if kodi_meta.get('clearart'):
                base['clearart'] = random.choice(kodi_meta['clearart'])
            if kodi_meta.get('clearlogo'):
                base['clearlogo'] = random.choice(kodi_meta['clearlogo'])

            # Determine if it's a movie or TV show
            episodes = kodi_meta.get('episodes', 0)
            if episodes == 1:
                processed_items.append(utils.parse_view(base, False, True, False))  # Movie
            else:
                processed_items.append(utils.parse_view(base, True, False, False))   # TV Show
        else:
            # Regular menu item
            name, url, image, info = item
            processed_items.append(utils.allocate_item(name, url, True, False, [], image, info))

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items(processed_items, view_type)


@Route('onas')
def ONAS_MENU(payload, params):
    # Check if menu needs refreshing due to recent playback
    if control.getGlobalProp('otaku.menu.needs_refresh') == 'true':
        control.clearGlobalProp('otaku.menu.needs_refresh')
        control.log('ONAs menu refresh flag detected - rebuilding menu items')

    ONAS_ITEMS = get_menu_items('onas')

    enabled_ona_items = []
    enabled_ona_items = add_watchlist(enabled_ona_items)

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('ona.mainmenu.config')

    if "last_watched_ona" in enabled_ids:
        enabled_ona_items = add_last_watched(enabled_ona_items)

    if "watch_history_ona" in enabled_ids:
        enabled_ona_items = add_watch_history(enabled_ona_items)

    for item in ONAS_ITEMS:
        if item[1] in enabled_ids:
            enabled_ona_items.append(item)

    # Process items, handling special last_watched items
    processed_items = []
    for item in enabled_ona_items:
        if len(item) == 6 and item[0] == 'LAST_WATCHED_ITEM':
            # This is a last_watched item - use utils.parse_view
            _, name, url, image, info, kodi_meta = item

            base = {
                'name': name,
                'url': url,
                'image': image,
                'poster': image,
                'fanart': kodi_meta.get('fanart', ''),
                'banner': image,
                'info': info
            }

            # Add artwork
            import random
            if kodi_meta.get('thumb'):
                base['landscape'] = random.choice(kodi_meta['thumb'])
            if kodi_meta.get('clearart'):
                base['clearart'] = random.choice(kodi_meta['clearart'])
            if kodi_meta.get('clearlogo'):
                base['clearlogo'] = random.choice(kodi_meta['clearlogo'])

            # Determine if it's a movie or TV show
            episodes = kodi_meta.get('episodes', 0)
            if episodes == 1:
                processed_items.append(utils.parse_view(base, False, True, False))  # Movie
            else:
                processed_items.append(utils.parse_view(base, True, False, False))   # TV Show
        else:
            # Regular menu item
            name, url, image, info = item
            processed_items.append(utils.allocate_item(name, url, True, False, [], image, info))

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items(processed_items, view_type)


@Route('music')
def MUSIC_MENU(payload, params):
    # Check if menu needs refreshing due to recent playback
    if control.getGlobalProp('otaku.menu.needs_refresh') == 'true':
        control.clearGlobalProp('otaku.menu.needs_refresh')
        control.log('Music menu refresh flag detected - rebuilding menu items')

    MUSIC_ITEMS = get_menu_items('music')

    enabled_music_items = []
    enabled_music_items = add_watchlist(enabled_music_items)

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('music.mainmenu.config')

    if "last_watched_music" in enabled_ids:
        enabled_music_items = add_last_watched(enabled_music_items)

    if "watch_history_music" in enabled_ids:
        enabled_music_items = add_watch_history(enabled_music_items)

    for item in MUSIC_ITEMS:
        if item[1] in enabled_ids:
            enabled_music_items.append(item)

    # Process items, handling special last_watched items
    processed_items = []
    for item in enabled_music_items:
        if len(item) == 6 and item[0] == 'LAST_WATCHED_ITEM':
            # This is a last_watched item - use utils.parse_view
            _, name, url, image, info, kodi_meta = item

            base = {
                'name': name,
                'url': url,
                'image': image,
                'poster': image,
                'fanart': kodi_meta.get('fanart', ''),
                'banner': image,
                'info': info
            }

            # Add artwork
            import random
            if kodi_meta.get('thumb'):
                base['landscape'] = random.choice(kodi_meta['thumb'])
            if kodi_meta.get('clearart'):
                base['clearart'] = random.choice(kodi_meta['clearart'])
            if kodi_meta.get('clearlogo'):
                base['clearlogo'] = random.choice(kodi_meta['clearlogo'])

            # Determine if it's a movie or TV show
            episodes = kodi_meta.get('episodes', 0)
            if episodes == 1:
                processed_items.append(utils.parse_view(base, False, True, False))  # Movie
            else:
                processed_items.append(utils.parse_view(base, True, False, False))   # TV Show
        else:
            # Regular menu item
            name, url, image, info = item
            processed_items.append(utils.allocate_item(name, url, True, False, [], image, info))

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items(processed_items, view_type)


@Route('trending')
def TRENDING_MENU(payload, params):
    TRENDING_ITEMS = get_menu_items('trending')

    enabled_trending_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('menu.submenu.config')

    for item in TRENDING_ITEMS:
        if item[1] in enabled_ids:
            enabled_trending_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_trending_items], view_type)


@Route('trending_movie')
def TRENDING_MOVIE_MENU(payload, params):
    TRENDING_MOVIE_ITEMS = get_menu_items('trending_movie')

    enabled_trending_movie_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('movie.submenu.config')

    for item in TRENDING_MOVIE_ITEMS:
        if item[1] in enabled_ids:
            enabled_trending_movie_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_trending_movie_items], view_type)


@Route('trending_tv_show')
def TRENDING_TV_SHOW_MENU(payload, params):
    TRENDING_TV_SHOW_ITEMS = get_menu_items('trending_tv_show')

    enabled_trending_tv_show_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('tv_show.submenu.config')

    for item in TRENDING_TV_SHOW_ITEMS:
        if item[1] in enabled_ids:
            enabled_trending_tv_show_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_trending_tv_show_items], view_type)


@Route('trending_tv_short')
def TRENDING_TV_SHORT_MENU(payload, params):
    TRENDING_TV_SHORT_ITEMS = get_menu_items('trending_tv_short')

    enabled_trending_tv_short_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('tv_short.submenu.config')

    for item in TRENDING_TV_SHORT_ITEMS:
        if item[1] in enabled_ids:
            enabled_trending_tv_short_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_trending_tv_short_items], view_type)


@Route('trending_special')
def TRENDING_SPECIAL_MENU(payload, params):
    TRENDING_SPECIAL_ITEMS = get_menu_items('trending_special')

    enabled_trending_special_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('special.submenu.config')

    for item in TRENDING_SPECIAL_ITEMS:
        if item[1] in enabled_ids:
            enabled_trending_special_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_trending_special_items], view_type)


@Route('trending_ova')
def TRENDING_OVA_MENU(payload, params):
    TRENDING_OVA_ITEMS = get_menu_items('trending_ova')

    enabled_trending_ova_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('ova.submenu.config')

    for item in TRENDING_OVA_ITEMS:
        if item[1] in enabled_ids:
            enabled_trending_ova_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_trending_ova_items], view_type)


@Route('trending_ona')
def TRENDING_ONA_MENU(payload, params):
    TRENDING_ONA_ITEMS = get_menu_items('trending_ona')

    enabled_trending_ona_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('ona.submenu.config')

    for item in TRENDING_ONA_ITEMS:
        if item[1] in enabled_ids:
            enabled_trending_ona_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_trending_ona_items], view_type)


@Route('trending_music')
def TRENDING_MUSIC_MENU(payload, params):
    TRENDING_MUSIC_ITEMS = get_menu_items('trending_music')

    enabled_trending_music_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('music.submenu.config')

    for item in TRENDING_MUSIC_ITEMS:
        if item[1] in enabled_ids:
            enabled_trending_music_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_trending_music_items], view_type)


@Route('popular')
def POPULAR_MENU(payload, params):
    POPULAR_ITEMS = get_menu_items('popular')

    enabled_popular_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('menu.submenu.config')

    for item in POPULAR_ITEMS:
        if item[1] in enabled_ids:
            enabled_popular_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_popular_items], view_type)


@Route('popular_movie')
def POPULAR_MOVIE_MENU(payload, params):
    POPULAR_MOVIE_ITEMS = get_menu_items('popular_movie')

    enabled_popular_movie_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('movie.submenu.config')

    for item in POPULAR_MOVIE_ITEMS:
        if item[1] in enabled_ids:
            enabled_popular_movie_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_popular_movie_items], view_type)


@Route('popular_tv_show')
def POPULAR_TV_SHOW_MENU(payload, params):
    POPULAR_TV_SHOW_ITEMS = get_menu_items('popular_tv_show')

    enabled_popular_tv_show_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('tv_show.submenu.config')

    for item in POPULAR_TV_SHOW_ITEMS:
        if item[1] in enabled_ids:
            enabled_popular_tv_show_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_popular_tv_show_items], view_type)


@Route('popular_tv_short')
def POPULAR_TV_SHORT_MENU(payload, params):
    POPULAR_TV_SHORT_ITEMS = get_menu_items('popular_tv_short')

    enabled_popular_tv_short_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('tv_short.submenu.config')

    for item in POPULAR_TV_SHORT_ITEMS:
        if item[1] in enabled_ids:
            enabled_popular_tv_short_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_popular_tv_short_items], view_type)


@Route('popular_special')
def POPULAR_SPECIAL_MENU(payload, params):
    POPULAR_SPECIAL_ITEMS = get_menu_items('popular_special')

    enabled_popular_special_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('special.submenu.config')

    for item in POPULAR_SPECIAL_ITEMS:
        if item[1] in enabled_ids:
            enabled_popular_special_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_popular_special_items], view_type)


@Route('popular_ova')
def POPULAR_OVA_MENU(payload, params):
    POPULAR_OVA_ITEMS = get_menu_items('popular_ova')

    enabled_popular_ova_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('ova.submenu.config')

    for item in POPULAR_OVA_ITEMS:
        if item[1] in enabled_ids:
            enabled_popular_ova_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_popular_ova_items], view_type)


@Route('popular_ona')
def POPULAR_ONA_MENU(payload, params):
    POPULAR_ONA_ITEMS = get_menu_items('popular_ona')

    enabled_popular_ona_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('ona.submenu.config')

    for item in POPULAR_ONA_ITEMS:
        if item[1] in enabled_ids:
            enabled_popular_ona_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_popular_ona_items], view_type)


@Route('popular_music')
def POPULAR_MUSIC_MENU(payload, params):
    POPULAR_MUSIC_ITEMS = get_menu_items('popular_music')

    enabled_popular_music_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('music.submenu.config')

    for item in POPULAR_MUSIC_ITEMS:
        if item[1] in enabled_ids:
            enabled_popular_music_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_popular_music_items], view_type)


@Route('voted')
def VOTED_MENU(payload, params):
    VOTED_ITEMS = get_menu_items('voted')

    enabled_voted_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('menu.submenu.config')

    for item in VOTED_ITEMS:
        if item[1] in enabled_ids:
            enabled_voted_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_voted_items], view_type)


@Route('voted_movie')
def VOTED_MOVIE_MENU(payload, params):
    VOTED_MOVIE_ITEMS = get_menu_items('voted_movie')

    enabled_voted_movie_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('movie.submenu.config')

    for item in VOTED_MOVIE_ITEMS:
        if item[1] in enabled_ids:
            enabled_voted_movie_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_voted_movie_items], view_type)


@Route('voted_tv_show')
def VOTED_TV_SHOW_MENU(payload, params):
    VOTED_TV_SHOW_ITEMS = get_menu_items('voted_tv_show')

    enabled_voted_tv_show_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('tv_show.submenu.config')

    for item in VOTED_TV_SHOW_ITEMS:
        if item[1] in enabled_ids:
            enabled_voted_tv_show_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_voted_tv_show_items], view_type)


@Route('voted_tv_short')
def VOTED_TV_SHORT_MENU(payload, params):
    VOTED_TV_SHORT_ITEMS = get_menu_items('voted_tv_short')

    enabled_voted_tv_short_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('tv_short.submenu.config')

    for item in VOTED_TV_SHORT_ITEMS:
        if item[1] in enabled_ids:
            enabled_voted_tv_short_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_voted_tv_short_items], view_type)


@Route('voted_special')
def VOTED_SPECIAL_MENU(payload, params):
    VOTED_SPECIAL_ITEMS = get_menu_items('voted_special')

    enabled_voted_special_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('special.submenu.config')

    for item in VOTED_SPECIAL_ITEMS:
        if item[1] in enabled_ids:
            enabled_voted_special_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_voted_special_items], view_type)


@Route('voted_ova')
def VOTED_OVA_MENU(payload, params):
    VOTED_OVA_ITEMS = get_menu_items('voted_ova')

    enabled_voted_ova_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('ova.submenu.config')

    for item in VOTED_OVA_ITEMS:
        if item[1] in enabled_ids:
            enabled_voted_ova_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_voted_ova_items], view_type)


@Route('voted_ona')
def VOTED_ONA_MENU(payload, params):
    VOTED_ONA_ITEMS = get_menu_items('voted_ona')

    enabled_voted_ona_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('ona.submenu.config')

    for item in VOTED_ONA_ITEMS:
        if item[1] in enabled_ids:
            enabled_voted_ona_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_voted_ona_items], view_type)


@Route('voted_music')
def VOTED_MUSIC_MENU(payload, params):
    VOTED_MUSIC_ITEMS = get_menu_items('voted_music')

    enabled_voted_music_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('music.submenu.config')

    for item in VOTED_MUSIC_ITEMS:
        if item[1] in enabled_ids:
            enabled_voted_music_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_voted_music_items], view_type)


@Route('favourites')
def FAVOURITES_MENU(payload, params):
    FAVOURITES_ITEMS = get_menu_items('favourites')

    enabled_favourites_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('menu.submenu.config')

    for item in FAVOURITES_ITEMS:
        if item[1] in enabled_ids:
            enabled_favourites_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_favourites_items], view_type)


@Route('favourites_movie')
def FAVOURITES_MOVIE_MENU(payload, params):
    FAVOURITES_MOVIE_ITEMS = get_menu_items('favourites_movie')

    enabled_favourites_movie_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('movie.submenu.config')

    for item in FAVOURITES_MOVIE_ITEMS:
        if item[1] in enabled_ids:
            enabled_favourites_movie_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_favourites_movie_items], view_type)


@Route('favourites_tv_show')
def FAVOURITES_TV_SHOW_MENU(payload, params):
    FAVOURITES_TV_SHOW_ITEMS = get_menu_items('favourites_tv_show')

    enabled_favourites_tv_show_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('tv_show.submenu.config')

    for item in FAVOURITES_TV_SHOW_ITEMS:
        if item[1] in enabled_ids:
            enabled_favourites_tv_show_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_favourites_tv_show_items], view_type)


@Route('favourites_tv_short')
def FAVOURITES_TV_SHORT_MENU(payload, params):
    FAVOURITES_TV_SHORT_ITEMS = get_menu_items('favourites_tv_short')

    enabled_favourites_tv_short_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('tv_short.submenu.config')

    for item in FAVOURITES_TV_SHORT_ITEMS:
        if item[1] in enabled_ids:
            enabled_favourites_tv_short_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_favourites_tv_short_items], view_type)


@Route('favourites_special')
def FAVOURITES_SPECIAL_MENU(payload, params):
    FAVOURITES_SPECIAL_ITEMS = get_menu_items('favourites_special')

    enabled_favourites_special_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('special.submenu.config')

    for item in FAVOURITES_SPECIAL_ITEMS:
        if item[1] in enabled_ids:
            enabled_favourites_special_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_favourites_special_items], view_type)


@Route('favourites_ova')
def FAVOURITES_OVA_MENU(payload, params):
    FAVOURITES_OVA_ITEMS = get_menu_items('favourites_ova')

    enabled_favourites_ova_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('ova.submenu.config')

    for item in FAVOURITES_OVA_ITEMS:
        if item[1] in enabled_ids:
            enabled_favourites_ova_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_favourites_ova_items], view_type)


@Route('favourites_ona')
def FAVOURITES_ONA_MENU(payload, params):
    FAVOURITES_ONA_ITEMS = get_menu_items('favourites_ona')

    enabled_favourites_ona_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('ona.submenu.config')

    for item in FAVOURITES_ONA_ITEMS:
        if item[1] in enabled_ids:
            enabled_favourites_ona_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_favourites_ona_items], view_type)


@Route('favourites_music')
def FAVOURITES_MUSIC_MENU(payload, params):
    FAVOURITES_MUSIC_ITEMS = get_menu_items('favourites_music')

    enabled_favourites_music_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('music.submenu.config')

    for item in FAVOURITES_MUSIC_ITEMS:
        if item[1] in enabled_ids:
            enabled_favourites_music_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_favourites_music_items], view_type)


@Route('genres')
def GENRES_MENU(payload, params):
    GENRES_ITEMS = get_menu_items('genres')

    enabled_genres_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('menu.genres.config')

    for item in GENRES_ITEMS:
        if item[1] in enabled_ids:
            enabled_genres_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_genres_items], view_type)


@Route('genres_movie')
def GENRE_MOVIE_MENU(payload, params):
    GENRE_MOVIE_ITEMS = get_menu_items('genres_movie')

    enabled_genre_movie_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('movie.genres.config')

    for item in GENRE_MOVIE_ITEMS:
        if item[1] in enabled_ids:
            enabled_genre_movie_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_genre_movie_items], view_type)


@Route('genres_tv_show')
def GENRE_TV_SHOW_MENU(payload, params):
    GENRE_TV_SHOW_ITEMS = get_menu_items('genres_tv_show')

    enabled_genre_tv_show_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('tv_show.genres.config')

    for item in GENRE_TV_SHOW_ITEMS:
        if item[1] in enabled_ids:
            enabled_genre_tv_show_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_genre_tv_show_items], view_type)


@Route('genres_tv_short')
def GENRE_TV_SHORT_MENU(payload, params):
    GENRE_TV_SHORT_ITEMS = get_menu_items('genres_tv_short')

    enabled_genre_tv_short_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('tv_short.genres.config')

    for item in GENRE_TV_SHORT_ITEMS:
        if item[1] in enabled_ids:
            enabled_genre_tv_short_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_genre_tv_short_items], view_type)


@Route('genres_special')
def GENRE_SPECIAL_MENU(payload, params):
    GENRE_SPECIAL_ITEMS = get_menu_items('genres_special')

    enabled_genre_special_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('special.genres.config')

    for item in GENRE_SPECIAL_ITEMS:
        if item[1] in enabled_ids:
            enabled_genre_special_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_genre_special_items], view_type)


@Route('genres_ova')
def GENRE_OVA_MENU(payload, params):
    GENRE_OVA_ITEMS = get_menu_items('genres_ova')

    enabled_genre_ova_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('ova.genres.config')

    for item in GENRE_OVA_ITEMS:
        if item[1] in enabled_ids:
            enabled_genre_ova_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_genre_ova_items], view_type)


@Route('genres_ona')
def GENRE_ONA_MENU(payload, params):
    GENRE_ONA_ITEMS = get_menu_items('genres_ona')

    enabled_genre_ona_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('ona.genres.config')

    for item in GENRE_ONA_ITEMS:
        if item[1] in enabled_ids:
            enabled_genre_ona_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_genre_ona_items], view_type)


@Route('genres_music')
def GENRE_MUSIC_MENU(payload, params):
    GENRE_MUSIC_ITEMS = get_menu_items('genres_music')

    enabled_genre_music_items = []

    # Retrieve the list from your settings list control
    enabled_ids = control.getStringList('music.genres.config')

    for item in GENRE_MUSIC_ITEMS:
        if item[1] in enabled_ids:
            enabled_genre_music_items.append(item)

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled_genre_music_items], view_type)


@Route('search')
def SEARCH_MENU(payload, params):
    SEARCH_ITEMS = get_menu_items('search')

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in SEARCH_ITEMS], view_type)


@Route('tools')
def TOOLS_MENU(payload, params):
    TOOLS_ITEMS = get_menu_items('tools')

    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items([utils.allocate_item(name, url, False, False, [], image, info) for name, url, image, info in TOOLS_ITEMS], view_type)


# ### Maintenance ###
@Route('settings')
def SETTINGS(payload, params):
    control.ADDON.openSettings()


@Route('change_log')
def CHANGE_LOG(payload, params):
    import service
    service.getChangeLog()


@Route('solver_inst')
def SOLVER_INST(payload, params):
    import service
    service.getInstructions()


@Route('clear_cache')
def CLEAR_CACHE(payload, params):
    control.setSetting('last_played_source', str(None))
    database.cache_clear()


@Route('clear_search_history')
@Route('clear_search_history_anime')
@Route('clear_search_history_movie')
@Route('clear_search_history_tv_show')
@Route('clear_search_history_tv_short')
@Route('clear_search_history_special')
@Route('clear_search_history_ova')
@Route('clear_search_history_ona')
@Route('clear_search_history_music')
def CLEAR_SEARCH_HISTORY(payload, params):
    mapping = {
        'clear_search_history': 'all',
        'clear_search_history_anime': 'anime',
        'clear_search_history_movie': 'movie',
        'clear_search_history_tv_show': 'tv_show',
        'clear_search_history_tv_short': 'tv_short',
        'clear_search_history_special': 'special',
        'clear_search_history_ova': 'ova',
        'clear_search_history_ona': 'ona',
        'clear_search_history_music': 'music'
    }

    format = mapping.get(plugin_url)

    if format == 'all':
        database.clearSearchHistory()
    else:
        database.clearSearchCatagory(format)

    control.refresh()


@Route('clear_watch_history')
def CLEAR_WATCH_HISTORY(payload, params):
    import os
    silent = False

    if not silent:
        confirm = control.yesno_dialog(control.ADDON_NAME, control.lang(30036))
    if confirm == 0:
        return

    if os.path.exists(control.watch_history_json):
        os.remove(control.watch_history_json)
    control.refresh()
    if not silent:
        control.notify(f'{control.ADDON_NAME}: Watch History', 'Watch History Successfully Cleared', sound=False)


@Route('clear_selected_fanart')
def CLEAR_SELECTED_FANART(payload, params):
    silent = False

    if not silent:
        confirm = control.yesno_dialog(control.ADDON_NAME, control.lang(30033))
    if confirm == 0:
        return

    # Clear all fanart selections using string lists
    control.setStringList('fanart.mal_ids', [])
    control.setStringList('fanart.selections', [])
    if not silent:
        control.notify(f'{control.ADDON_NAME}: Fanart', 'Fanart Successfully Cleared', sound=False)


@Route('rebuild_database')
def REBUILD_DATABASE(payload, params):
    from resources.lib.ui.database_sync import SyncDatabase
    SyncDatabase().re_build_database()


@Route('wipe_addon_data')
def WIPE_ADDON_DATA(payload, params):
    control.clear_settings()


@Route('completed_sync')
def COMPLETED_SYNC(payload, params):
    import service
    service.sync_watchlist()


@Route('sort_select')
def SORT_SELECT(payload, params):
    from resources.lib.windows.sort_select import SortSelect
    SortSelect('sort_select.xml', control.ADDON_PATH).doModal()


# @Route('filter_select')
# def FILTER_SELECT(payload, params):
#     from resources.lib.windows.filter_select import FilterSelect
#     FilterSelect(*('filter_select.xml', control.ADDON_PATH)).doModal()


@Route('download_manager')
def DOWNLOAD_MANAGER(payload, params):
    from resources.lib.windows.download_manager import DownloadManager
    DownloadManager('download_manager.xml', control.ADDON_PATH).doModal()


@Route('import_settings')
def IMPORT_SETTINGS(payload, params):
    import os
    import xbmcvfs

    setting_xml = os.path.join(control.dataPath, 'settings.xml')

    # Import
    import_location = control.browse(1, f"{control.ADDON_NAME}: Import Setting", 'files', 'settings.xml')
    if not import_location:
        return control.exit_code()
    if not import_location.endswith('settings.xml'):
        control.ok_dialog(control.ADDON_NAME, "Invalid File!")
    else:
        yesno = control.yesno_dialog(control.ADDON_NAME, "Are you sure you want to replace settings.xml?")
        if yesno:
            if xbmcvfs.delete(setting_xml) and xbmcvfs.copy(import_location, setting_xml):
                control.ok_dialog(control.ADDON_NAME, "Replaced settings.xml")
            else:
                control.ok_dialog(control.ADDON_NAME, "Could Not Import File!")
    return control.exit_code()


@Route('export_settings')
def EXPORT_SETTINGS(payload, params):
    import os
    import xbmcvfs

    setting_xml = os.path.join(control.dataPath, 'settings.xml')

    # Export
    export_location = control.browse(3, f"{control.ADDON_NAME}: Export Setting", 'files')
    if not export_location:
        control.ok_dialog(control.ADDON_NAME, "Please Select Export Location!")
    else:
        yesno = control.yesno_dialog(control.ADDON_NAME, "Are you sure you want to save settings.xml?")
        if yesno:
            if xbmcvfs.copy(setting_xml, os.path.join(export_location, 'settings.xml')):
                control.ok_dialog(control.ADDON_NAME, "Saved settings.xml")
            else:
                control.ok_dialog(control.ADDON_NAME, "Could Not Export File!")
    return control.exit_code()


@Route('inputstreamadaptive')
def INPUTSTREAMADAPTIVE(payload, params):
    import xbmcaddon
    try:
        xbmcaddon.Addon('inputstream.adaptive').openSettings()
    except RuntimeError:
        control.notify(control.ADDON_NAME, "InputStream Adaptive is not installed.")


@Route('inputstreamhelper')
def INPUTSTREAMHELPER(payload, params):
    import xbmcaddon
    import xbmc
    try:
        xbmcaddon.Addon('inputstream.adaptive')
        control.ok_dialog(control.ADDON_NAME, "InputStream Adaptive is already installed.")
    except RuntimeError:
        xbmc.executebuiltin('InstallAddon(inputstream.adaptive)')


@Route('trakt_settings')
def TRAKT_SETTINGS(payload, params):
    import xbmcaddon
    try:
        xbmcaddon.Addon('script.trakt').openSettings()
    except RuntimeError:
        control.notify(control.ADDON_NAME, "Trakt Script is not installed.")


@Route('trakt_script')
def TRAKT_SCRIPT(payload, params):
    import xbmcaddon
    import xbmc
    try:
        xbmcaddon.Addon('script.trakt')
        control.ok_dialog(control.ADDON_NAME, "Trakt Script is already installed.")
    except RuntimeError:
        xbmc.executebuiltin('InstallAddon(script.trakt)')


@Route('playback_options/*')
def PLAYBACK_OPTIONS(payload, params):
    import xbmcgui
    from urllib.parse import urlencode

    # Parse the payload to get mal_id and episode
    if payload and '/' in payload:
        mal_id, episode = payload.split('/', 1)
    else:
        control.log('Invalid payload format', 'error')
        return control.exit_code()

    # Get show information from database to build params
    show = database.get_show(mal_id)
    if show:
        kodi_meta = pickle.loads(show['kodi_meta'])

        # Build params similar to what get_video_info would return
        episode_params = {
            'mal_id': mal_id,
            'episode': episode,
            'title': kodi_meta.get('title_userPreferred', ''),
            'mediatype': 'episode',
            'tvshowtitle': kodi_meta.get('title_userPreferred', ''),
            'plot': kodi_meta.get('plot', ''),
            'year': str(kodi_meta.get('year', '')),
            'premiered': kodi_meta.get('premiered', ''),
            'season': str(kodi_meta.get('season', 1)),
            'aired': kodi_meta.get('aired', ''),
            'rating': kodi_meta.get('rating', {}),
            'resume': params.get('resume', ''),
            # Artwork
            'poster': kodi_meta.get('poster', ''),
            'tvshow.poster': kodi_meta.get('poster', ''),
            'icon': kodi_meta.get('poster', ''),
            'thumb': kodi_meta.get('thumb', ''),
            'fanart': kodi_meta.get('fanart', ''),
            'landscape': kodi_meta.get('landscape', ''),
            'banner': kodi_meta.get('banner', ''),
            'clearart': kodi_meta.get('clearart', ''),
            'clearlogo': kodi_meta.get('clearlogo', '')
        }
    else:
        # Fallback params if show not found in database
        episode_params = {
            'mal_id': mal_id,
            'episode': episode,
            'title': '',
            'mediatype': 'episode',
            'tvshowtitle': '',
            'plot': '',
            'year': '',
            'premiered': '',
            'season': '1',
            'aired': '',
            'rating': {},
            'resume': params.get('resume', ''),
            # Artwork
            'poster': '',
            'tvshow.poster': '',
            'icon': '',
            'thumb': '',
            'fanart': '',
            'landscape': '',
            'banner': '',
            'clearart': '',
            'clearlogo': ''
        }

    # Ask the user which playback option they want to use
    # Here the button labels are:
    # Button 0: "Cancel"   | Button 1: "Rescrape" | Button 2: "Source Select"
    yesnocustom = control.yesnocustom_dialog(
        control.ADDON_NAME + " - Playback Options",
        "Please choose a playback option:",
        "Cancel", "Source Select", "Rescrape",
        defaultbutton=xbmcgui.DLG_YESNO_YES_BTN
    )

    if yesnocustom == 0:
        # Redirect to play route with source_select parameter
        query_params = urlencode({'source_select': 'true', **episode_params})
        control.playList.clear()
        control.execute(f'RunPlugin(plugin://{control.ADDON_ID}/play/{mal_id}/{episode}?{query_params})')

    elif yesnocustom == 1:
        # Redirect to play route with rescrape parameter
        query_params = urlencode({'rescrape': 'true', **episode_params})
        control.playList.clear()
        control.execute(f'RunPlugin(plugin://{control.ADDON_ID}/play/{mal_id}/{episode}?{query_params})')

    elif yesnocustom == 2:
        # User cancelled, exit without doing anything
        pass

    control.exit_code()


@Route('setup_wizard')
def SETUP_WIZARD(payload, params):
    from resources.lib.windows.sort_select import SortSelect
    import xbmcgui
    # Ask the user if they would like to enable search history
    # Here the button labels are:
    # Button 0: "Yes"   | Button 1: "No"
    choice = control.yesno_dialog(
        control.ADDON_NAME,
        "Would you like to enable search history?",
        "No", "Yes",
    )

    # Yes selected
    if choice == 1:
        control.setInt('searchhistory', 0)

    # No selected
    elif choice == 0:
        control.setInt('searchhistory', 1)

    # Ask the user if they would like to show change log every update
    # Here the button labels are:
    # Button 0: "Yes"   | Button 1: "No"
    choice = control.yesno_dialog(
        control.ADDON_NAME,
        "Would you like to show change log every update?",
        "No", "Yes",
    )

    # Yes selected
    if choice == 1:
        control.setInt('showchangelog', 0)

    # No selected
    elif choice == 0:
        control.setInt('showchangelog', 1)

    # Ask the user to select between Romaji or English
    # Here the button labels are:
    # Button 0: "Romaji" | Button 1: "English"
    choice = control.yesno_dialog(
        control.ADDON_NAME,
        "Please choose your preferred Title Language for your Anime Content:",
        "English", "Romaji",
    )

    # Romaji selected
    if choice == 1:
        control.setInt('titlelanguage', 0)

    # English selected
    elif choice == 0:
        control.setInt('titlelanguage', 1)

    # Ask the user to select between Otaku or Mal or Anilist
    # Here the button labels are:
    # Button 0: "Anilist" | Button 1: "Mal" | Button 2: "Otaku"
    choice = control.yesnocustom_dialog(
        control.ADDON_NAME,
        "Please choose where you would like to get your Anime Content from:",
        "Anilist", "Mal", "Otaku",
        defaultbutton=xbmcgui.DLG_YESNO_YES_BTN
    )

    # Otaku selected
    if choice == 1:
        control.setSetting('browser.api', 'otaku')

    # Mal selected
    elif choice == 0:
        control.setSetting('browser.api', 'mal')

    # Anilist selected
    elif choice == 2:
        control.setSetting('browser.api', 'anilist')

        # Ask the user if they would like to replace Anilist Posters with Mal Posters
        # Here the button labels are:
        # Button 0: "Yes"   | Button 1: "No"
        choice = control.yesno_dialog(
            control.ADDON_NAME,
            "Would you like to replace Anilist Posters with Mal Posters?",
            "No", "Yes",
        )

        # Yes selected
        if choice == 1:
            control.setBool('general.malposters', True)

        # No selected
        elif choice == 0:
            control.setBool('general.malposters', False)

    # Ask the user if they would like to have all the menus enabled
    # Here the button labels are:
    # Button 0: "Yes"   | Button 1: "No"
    choice = control.yesno_dialog(
        control.ADDON_NAME,
        "Would you like to have the rest of the menus enabled?\n(Note: This will enabled menus such as Movies, TV Shows, TV Shorts, Specials, OVAs, ONAs, and Music Videos. A restart may be required for the changes to take effect.)",
        "No", "Yes",
    )

    # Yes selected
    if choice == 1:
        control.setStringList('menu.mainmenu.config', ['last_watched', 'watch_history', 'airing_calendar', 'airing_last_season', 'airing_this_season', 'airing_next_season', 'movies', 'tv_shows', 'tv_shorts', 'specials', 'ovas', 'onas', 'music', 'trending', 'popular', 'voted', 'favourites', 'top_100', 'genres', 'search', 'tools'])

    # No selected
    elif choice == 0:
        control.setStringList('menu.mainmenu.config', ['last_watched', 'watch_history', 'airing_calendar', 'airing_last_season', 'airing_this_season', 'airing_next_season', 'trending', 'popular', 'voted', 'favourites', 'top_100', 'genres', 'search', 'tools'])

    # Ask the user to select between Subs or Dubs
    # Here the button labels are:
    # Button 0: "Subs"   | Button 1: "Dubs"   | Button 2 (or -1): "Cancel"
    choice = control.yesno_dialog(
        control.ADDON_NAME,
        "Please choose your preferred language option for playback:",
        "Dubs", "Subs",
    )

    # Subs selected
    if choice == 1:
        control.setInt('general.audio', 0)
        control.setInt('general.subtitles', 1)
        control.setBool('general.subtitles.type', True)
        control.setInt('subtitles.types', 1)
        control.setBool('general.subtitles.keyword', True)
        control.setInt('subtitles.keywords', 1)
        control.setBool('general.dubsubtitles', False)
        control.setInt('general.source', 1)
        control.setBool('divflavors.showdub', False)
        control.setBool('jz.dub', False)
        SortSelect.auto_action(0)
        control.log("Subs settings applied.")
    # Dubs selected
    elif choice == 0:
        control.setInt('general.audio', 1)
        control.setInt('general.subtitles', 0)
        control.setBool('general.subtitles.type', True)
        control.setInt('subtitles.types', 1)
        control.setBool('general.subtitles.keyword', True)
        control.setInt('subtitles.keywords', 2)
        control.setBool('general.dubsubtitles', False)
        control.setInt('general.source', 2)
        control.setBool('divflavors.showdub', True)
        control.setBool('jz.dub', True)
        SortSelect.auto_action(1)
        control.log("Dubs settings applied.")

        # Ask the user if they would like subtitles for dub streams
        # Here the button labels are:
        # Button 0: "Yes"   | Button 1: "No"
        choice = control.yesno_dialog(
            control.ADDON_NAME,
            "Would you like subtitles for dub streams?\n(Note: This may not work for all streams.)",
            "No", "Yes",
        )

        # Yes selected
        if choice == 1:
            control.setBool('general.dubsubtitles', True)
            control.setInt('general.subtitles', 1)
            control.setInt('subtitles.types', 1)
            control.setInt('subtitles.keywords', 1)


@Route('toggleLanguageInvoker')
def TOGGLE_LANGUAGE_INVOKER(payload, params):
    import service
    service.toggle_reuselanguageinvoker()


def _get_advancedsettings_status(element_name):
    """Helper function to get current status of advancedsettings.xml elements"""
    import os
    import xml.etree.ElementTree as ET

    try:
        if os.path.exists(control.kodi_advancedsettings_path):
            tree = ET.parse(control.kodi_advancedsettings_path)
            root = tree.getroot()
            element = root.find(element_name)
            if element is not None:
                return element.text.lower() == 'true'
        return False  # Default to false if not found or file doesn't exist
    except Exception:
        return False


def _update_network_status():
    """Update the status settings to reflect current advancedsettings.xml state"""
    # Get current states
    ipv6_disabled = _get_advancedsettings_status('disableipv6')
    http2_disabled = _get_advancedsettings_status('disablehttp2')

    # Update status settings (remember: disabled=true means the protocol is OFF)
    control.setSetting('ipv6.status', 'Disabled' if ipv6_disabled else 'Enabled')
    control.setSetting('http2.status', 'Disabled' if http2_disabled else 'Enabled')


@Route('toggle_ipv6')
def TOGGLE_IPV6(payload, params):
    """Toggle IPv6 setting in Kodi's advancedsettings.xml"""
    import os
    import xml.etree.ElementTree as ET

    try:
        # Check if advancedsettings.xml exists
        if os.path.exists(control.kodi_advancedsettings_path):
            # Parse existing file
            tree = ET.parse(control.kodi_advancedsettings_path)
            root = tree.getroot()
        else:
            # Create new advancedsettings.xml
            root = ET.Element('advancedsettings')
            tree = ET.ElementTree(root)

        # Find or create disableipv6 element
        disableipv6_elem = root.find('disableipv6')
        if disableipv6_elem is None:
            disableipv6_elem = ET.SubElement(root, 'disableipv6')
            disableipv6_elem.text = 'false'

        # Toggle the value
        current_value = disableipv6_elem.text.lower() == 'true'
        new_value = not current_value
        disableipv6_elem.text = 'true' if new_value else 'false'

        # Write back to file
        tree.write(control.kodi_advancedsettings_path, encoding='utf-8', xml_declaration=True)

        # Update status settings
        _update_network_status()

        # Show notification
        status = "disabled" if new_value else "enabled"
        control.notify(
            title=control.ADDON_NAME,
            text=f"IPv6 {status}. Please restart Kodi for changes to take effect.",
            time=5000
        )

    except Exception as e:
        control.notify(
            title=control.ADDON_NAME,
            text=f"Error toggling IPv6 setting: {str(e)}",
            time=5000
        )
        control.log(f"Error in TOGGLE_IPV6: {str(e)}", level='error')


@Route('toggle_http2')
def TOGGLE_HTTP2(payload, params):
    """Toggle HTTP/2 setting in Kodi's advancedsettings.xml"""
    import os
    import xml.etree.ElementTree as ET

    try:
        # Check if advancedsettings.xml exists
        if os.path.exists(control.kodi_advancedsettings_path):
            # Parse existing file
            tree = ET.parse(control.kodi_advancedsettings_path)
            root = tree.getroot()
        else:
            # Create new advancedsettings.xml
            root = ET.Element('advancedsettings')
            tree = ET.ElementTree(root)

        # Find or create disablehttp2 element
        disablehttp2_elem = root.find('disablehttp2')
        if disablehttp2_elem is None:
            disablehttp2_elem = ET.SubElement(root, 'disablehttp2')
            disablehttp2_elem.text = 'false'

        # Toggle the value
        current_value = disablehttp2_elem.text.lower() == 'true'
        new_value = not current_value
        disablehttp2_elem.text = 'true' if new_value else 'false'

        # Write back to file
        tree.write(control.kodi_advancedsettings_path, encoding='utf-8', xml_declaration=True)

        # Update status settings
        _update_network_status()

        # Show notification
        status = "disabled" if new_value else "enabled"
        control.notify(
            title=control.ADDON_NAME,
            text=f"HTTP/2 {status}. Please restart Kodi for changes to take effect.",
            time=5000
        )

    except Exception as e:
        control.notify(
            title=control.ADDON_NAME,
            text=f"Error toggling HTTP/2 setting: {str(e)}",
            time=5000
        )
        control.log(f"Error in TOGGLE_HTTP2: {str(e)}", level='error')


@Route('update_network_status')
def UPDATE_NETWORK_STATUS(payload, params):
    """Update network status settings when settings are opened"""
    _update_network_status()


@Route('migration_process')
def MIGRATION_PROCESS(payload, params):
    from resources.lib.ui.database_sync import SyncDatabase
    confirm = control.yesno_dialog(control.ADDON_NAME, control.lang(30440))
    if confirm == 0:
        return
    SyncDatabase().migration_process()
