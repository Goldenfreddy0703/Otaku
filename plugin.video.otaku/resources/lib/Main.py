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

    Large modules: route handlers, compact menu tables, browser lists, playback, tools,
    and programmatic UI menu registration live in this file for a single import surface.
"""

import pickle
import json
import ast
import sys
import random

from resources.lib import MetaBrowser
from resources.lib.ui import control, database, utils
from resources.lib.ui.router import Route, multi_route
from resources.lib.WatchlistIntegration import add_watchlist

BROWSER = MetaBrowser.BROWSER
plugin_url = control.get_plugin_url(sys.argv[0])

# --- Browser list routes (mal/otaku vs AniList format codes) ------------------
_MAL_OTAKU_APIS = frozenset(('mal', 'otaku'))

_BROWSER_ROUTE_SUFFIXES = ('tv_show', 'movie', 'tv_short', 'special', 'ova', 'ona', 'music')

_FORMAT_PAIR_BY_SUFFIX = {
    'tv_show': ('tv', 'TV'),
    'movie': ('movie', 'MOVIE'),
    'tv_short': ('tv_special', 'TV_SHORT'),
    'special': ('special', 'SPECIAL'),
    'ova': ('ova', 'OVA'),
    'ona': ('ona', 'ONA'),
    'music': ('music', 'MUSIC'),
}


def _browser_list_route_paths(prefix):
    return (prefix,) + tuple('%s_%s' % (prefix, s) for s in _BROWSER_ROUTE_SUFFIXES)


def _wildcard_browser_paths(prefix):
    """Paths like ``marked_as_watched/*``, ``marked_as_watched_tv_show/*``, …"""
    return tuple('%s/*' % p for p in _browser_list_route_paths(prefix))


_GENRES_WILDCARD_PREFIXES = (
    'genres', 'genres_tv_show', 'genres_movie', 'genres_tv_short',
    'genres_special', 'genres_ova', 'genres_ona', 'genres_music',
)


def _suffix_route_mapping(route_prefix):
    return {
        '%s_%s' % (route_prefix, suf): _FORMAT_PAIR_BY_SUFFIX[suf]
        for suf in _BROWSER_ROUTE_SUFFIXES
    }


def _resolve_browser_format(route_prefix):
    base_key = plugin_url.split('?', 1)[0]
    pair = _suffix_route_mapping(route_prefix).get(base_key)
    if not pair:
        return None
    return pair[0] if control.getStr('browser.api') in _MAL_OTAKU_APIS else pair[1]


def _draw_browser_page(browser_method, route_prefix, params):
    page = int(params.get('page', 1))
    fmt = _resolve_browser_format(route_prefix)
    prefix = plugin_url.split('?', 1)[0]
    method = getattr(BROWSER, browser_method)
    items = method(page, fmt, prefix)
    control.draw_items(items, 'tvshows')
    control.schedule_next_page_prefetch(
        items,
        lambda p=page + 1, f=fmt, pr=prefix, m=method: m(p, f, pr))


def _draw_genre_page(route_prefix, params):
    _draw_browser_page('get_genre_' + route_prefix[6:], route_prefix, params)


# --- Menu route definitions (compact tables: labels, paths, artwork) ----------
_CATEGORY_SUFFIX = {
    'movies': '_movie',
    'tv_shows': '_tv_show',
    'tv_shorts': '_tv_short',
    'specials': '_special',
    'ovas': '_ova',
    'onas': '_ona',
    'music': '_music',
}

_CATEGORY_ROWS = (
    (30002, 'airing_last_season', 'airing_anime.png'),
    (30003, 'airing_this_season', 'airing_anime.png'),
    (30004, 'airing_next_season', 'airing_anime.png'),
    (30012, 'trending', 'trending.png'),
    (30013, 'popular', 'popular.png'),
    (30014, 'voted', 'voted.png'),
    (30015, 'favourites', 'favourites.png'),
    (30016, 'top_100', 'top_100_anime.png'),
    (30017, 'genres', 'genres_&_tags.png'),
    (30018, 'search_history', 'search.png'),
)


def _category_format_menu(suffix):
    rows = []
    for lid, stem, icon in _CATEGORY_ROWS:
        rows.append((control.lang(lid), '%s%s' % (stem, suffix), icon, {}))
    return rows


def _stem_menu(stems, suffix, icon):
    out = []
    for lid, path_stem in stems:
        out.append((control.lang(lid), '%s%s' % (path_stem, suffix), icon, {}))
    return out


_TRENDING_STEMS = (
    (30020, 'trending_last_year'),
    (30021, 'trending_this_year'),
    (30022, 'trending_last_season'),
    (30023, 'trending_this_season'),
    (30024, 'all_time_trending'),
)

_POPULAR_STEMS = (
    (30025, 'popular_last_year'),
    (30026, 'popular_this_year'),
    (30027, 'popular_last_season'),
    (30028, 'popular_this_season'),
    (30029, 'all_time_popular'),
)

_VOTED_STEMS = (
    (30030, 'voted_last_year'),
    (30031, 'voted_this_year'),
    (30032, 'voted_last_season'),
    (30033, 'voted_this_season'),
    (30034, 'all_time_voted'),
)

_FAV_STEMS = (
    (30035, 'favourites_last_year'),
    (30036, 'favourites_this_year'),
    (30037, 'favourites_last_season'),
    (30038, 'favourites_this_season'),
    (30039, 'all_time_favourites'),
)

_FORMAT_SUFFIXES = (
    ('', ''),
    ('_movie', '_movie'),
    ('_tv_show', '_tv_show'),
    ('_tv_short', '_tv_short'),
    ('_special', '_special'),
    ('_ova', '_ova'),
    ('_ona', '_ona'),
    ('_music', '_music'),
)


def _genre_menu(menu_key, suffix):
    rows = [(control.lang(30040), '%s//' % menu_key, 'genre_multi.png', {})]
    for lid, stem, icon in _GENRE_ROWS:
        rows.append((control.lang(lid), '%s%s' % (stem, suffix), icon, {}))
    return rows


_GENRE_ROWS = (
    (30041, 'genre_action', 'genre_action.png'),
    (30042, 'genre_adventure', 'genre_adventure.png'),
    (30043, 'genre_comedy', 'genre_comedy.png'),
    (30044, 'genre_drama', 'genre_drama.png'),
    (30045, 'genre_ecchi', 'genre_ecchi.png'),
    (30046, 'genre_fantasy', 'genre_fantasy.png'),
    (30047, 'genre_hentai', 'genre_hentai.png'),
    (30048, 'genre_horror', 'genre_horror.png'),
    (30049, 'genre_shoujo', 'genre_shoujo.png'),
    (30050, 'genre_mecha', 'genre_mecha.png'),
    (30051, 'genre_music', 'genre_music.png'),
    (30052, 'genre_mystery', 'genre_mystery.png'),
    (30053, 'genre_psychological', 'genre_psychological.png'),
    (30054, 'genre_romance', 'genre_romance.png'),
    (30055, 'genre_sci_fi', 'genre_sci-fi.png'),
    (30056, 'genre_slice_of_life', 'genre_slice_of_life.png'),
    (30057, 'genre_sports', 'genre_sports.png'),
    (30058, 'genre_supernatural', 'genre_supernatural.png'),
    (30059, 'genre_thriller', 'genre_thriller.png'),
)

_GENRE_MENU_KEYS = (
    ('genres', ''),
    ('genres_movie', '_movie'),
    ('genres_tv_show', '_tv_show'),
    ('genres_tv_short', '_tv_short'),
    ('genres_special', '_special'),
    ('genres_ova', '_ova'),
    ('genres_ona', '_ona'),
    ('genres_music', '_music'),
)


def _main_menu():
    return [
        (control.lang(30001), "airing_calendar", 'airing_anime_calendar.png', {}),
        (control.lang(30002), "airing_last_season", 'airing_anime.png', {}),
        (control.lang(30003), "airing_this_season", 'airing_anime.png', {}),
        (control.lang(30004), "airing_next_season", 'airing_anime.png', {}),
        (control.lang(30005), "movies", 'movies.png', {}),
        (control.lang(30006), "tv_shows", 'tv_shows.png', {}),
        (control.lang(30007), "tv_shorts", 'tv_shorts.png', {}),
        (control.lang(30008), "specials", 'specials.png', {}),
        (control.lang(30009), "ovas", 'ovas.png', {}),
        (control.lang(30010), "onas", 'onas.png', {}),
        (control.lang(30011), "music", 'music.png', {}),
        (control.lang(30012), "trending", 'trending.png', {}),
        (control.lang(30013), "popular", 'popular.png', {}),
        (control.lang(30014), "voted", 'voted.png', {}),
        (control.lang(30015), "favourites", 'favourites.png', {}),
        (control.lang(30016), "top_100", 'top_100_anime.png', {}),
        (control.lang(30017), "genres", 'genres_&_tags.png', {}),
        (control.lang(30018), "search", 'search.png', {}),
        (control.lang(30019), "tools", 'tools.png', {}),
    ]


def _search_menu():
    kinds = ('anime', 'movie', 'tv_show', 'tv_short', 'special', 'ova', 'ona', 'music')
    lids = range(30060, 30068)
    return [(control.lang(lid), 'search_history_%s' % k, 'search.png', {}) for lid, k in zip(lids, kinds)]


def _tools_menu():
    tools = (
        (30069, 'setup_wizard', 'tools.png'),
        (30070, 'change_log', 'changelog.png'),
        (30071, 'settings', 'open_settings_menu.png'),
        (30072, 'clear_cache', 'clear_cache.png'),
        (30073, 'clear_search_history', 'clear_search_history.png'),
        (30074, 'clear_watch_history', 'clear_watch_history.png'),
        (30075, 'rebuild_database', 'rebuild_database.png'),
        (30076, 'wipe_addon_data', 'wipe_addon_data.png'),
        (30077, 'completed_sync', 'sync_completed.png'),
        (30078, 'download_manager', 'download_manager.png'),
        (30079, 'sort_select', 'sort_select.png'),
        (30080, 'clear_selected_fanart', 'wipe_addon_data.png'),
    )
    return [(control.lang(lid), path, icon, {}) for lid, path, icon in tools]


def _build_menu_registry():
    reg = {'main': _main_menu, 'search': _search_menu, 'tools': _tools_menu}

    for mk, suf in _CATEGORY_SUFFIX.items():
        reg[mk] = (lambda s=suf: _category_format_menu(s))

    for key_part, suf in _FORMAT_SUFFIXES:
        reg['trending%s' % key_part] = (
            lambda s=suf: _stem_menu(_TRENDING_STEMS, s, 'trending.png')
        )
        reg['popular%s' % key_part] = (
            lambda s=suf: _stem_menu(_POPULAR_STEMS, s, 'popular.png')
        )
        reg['voted%s' % key_part] = (
            lambda s=suf: _stem_menu(_VOTED_STEMS, s, 'voted.png')
        )
        reg['favourites%s' % key_part] = (
            lambda s=suf: _stem_menu(_FAV_STEMS, s, 'favourites.png')
        )

    for mkey, gsuf in _GENRE_MENU_KEYS:
        reg[mkey] = (lambda k=mkey, g=gsuf: _genre_menu(k, g))

    return reg


_MENU_REGISTRY = None


def get_menu_items(menu_type):
    global _MENU_REGISTRY
    if _MENU_REGISTRY is None:
        _MENU_REGISTRY = _build_menu_registry()
    builder = _MENU_REGISTRY.get(menu_type)
    return builder() if builder else []


def add_next_up(items):
    """Add Next Up menu item if enabled in watchlist settings."""
    if control.getBool('watchlist.update.enabled') and control.getBool('nextup.enabled'):
        items.append((control.lang(30451), "next_up", 'next_up.png', {}))
    return items


def add_last_watched(items):
    # # Check if last watched feature is enabled
    # if not control.getBool("interface.show_last_watched"):
    #     return items

    mal_id = control.getSetting("addon.last_watched")
    try:
        kodi_meta = pickle.loads(database.get_show(mal_id)['kodi_meta'])

        # Get extended artwork from shows_meta table
        show_meta = database.get_show_meta(mal_id)
        art = {}
        if show_meta and show_meta.get('art'):
            art = pickle.loads(show_meta['art'])

        last_watched = "%s: [I]%s[/I]" % (control.lang(30000), kodi_meta['title_userPreferred'])
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

        # Merge artwork from shows_meta into kodi_meta for the tuple
        # This way the menu processing code can access the extended artwork
        artwork_meta = dict(kodi_meta)
        artwork_meta['poster'] = art.get('poster') or kodi_meta.get('poster', '')
        artwork_meta['fanart'] = art.get('fanart', '')
        artwork_meta['thumb'] = art.get('thumb', '')
        artwork_meta['banner'] = art.get('banner', '')
        artwork_meta['clearlogo'] = art.get('clearlogo', '')
        artwork_meta['clearart'] = art.get('clearart', '')
        artwork_meta['landscape'] = art.get('landscape', '')

        # Return tuple with special marker for last_watched items
        items.append(('LAST_WATCHED_ITEM', last_watched, url, artwork_meta.get('poster', ''), info, artwork_meta))

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
            history_title = control.lang(30068)

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

        # Get extended artwork from shows_meta table
        show_meta = database.get_show_meta(mal_id)
        art = {}
        if show_meta and show_meta.get('art'):
            art = pickle.loads(show_meta['art'])

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
            # Artwork - use art dict from shows_meta, fallback to kodi_meta
            'poster': art.get('poster') or kodi_meta.get('poster', ''),
            'tvshow.poster': art.get('poster') or kodi_meta.get('poster', ''),
            'icon': art.get('poster') or kodi_meta.get('poster', ''),
            'thumb': art.get('thumb', ''),
            'fanart': art.get('fanart', ''),
            'landscape': art.get('landscape', ''),
            'banner': art.get('banner', ''),
            'clearart': art.get('clearart', ''),
            'clearlogo': art.get('clearlogo', '')
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


def draw_anime_reviews_listing(mal_id, page, path, eps_watched):
    """Build reviews listing via BROWSER (Jikan on mal/otaku, AniList on anilist)."""
    result = BROWSER.get_reviews_page(str(mal_id), int(page), path, eps_watched)
    if result is None:
        control.notify(control.ADDON_NAME, control.lang(30461))
        control.draw_items([], 'addons')
        return
    reviews = result.get('reviews') or []
    if not reviews:
        control.notify(control.ADDON_NAME, control.lang(30461))
        control.draw_items([], 'addons')
        return
    control.setGlobalProp('otaku.reviews.cache', json.dumps(reviews))
    control.setGlobalProp('otaku.reviews.mal_id', str(mal_id))
    control.setGlobalProp('otaku.reviews.page', str(page))
    items = result.get('items') or []
    control.draw_items(items, 'addons')
    next_p = int(page) + 1
    control.schedule_next_page_prefetch(
        items,
        lambda mid=str(mal_id), p=next_p, pt=path, ew=eps_watched: BROWSER.get_reviews_page(mid, p, pt, ew))


def open_anime_statistics(mal_id):
    data = BROWSER.get_statistics_payload(str(mal_id))
    if not data:
        control.notify(control.ADDON_NAME, control.lang(30463))
        return
    from resources.lib.windows.stats_window import StatsWindow
    window = StatsWindow('anime_statistics.xml', control.ADDON_PATH, stats=data, heading='[B]Anime Statistics[/B]')
    window.run()


@Route('animes/*')
def ANIMES_PAGE(payload, params):
    mal_id, eps_watched = payload.rsplit("/")
    anime_general, content = MetaBrowser.get_anime_init(mal_id)
    control.draw_items(anime_general, content)


@Route('find_recommendations/*')
def FIND_RECOMMENDATIONS(payload, params):
    path, mal_id, eps_watched = payload.rsplit("/")
    page = int(params.get('page', 1))
    items = BROWSER.get_recommendations(mal_id, page)
    control.draw_items(items, 'tvshows')
    control.schedule_next_page_prefetch(
        items,
        lambda mid=mal_id, p=page + 1: BROWSER.get_recommendations(mid, p))


@Route('find_relations/*')
def FIND_RELATIONS(payload, params):
    path, mal_id, eps_watched = payload.rsplit("/")
    control.draw_items(BROWSER.get_relations(mal_id), 'tvshows')


@Route('watch_order/*')
def WATCH_ORDER(payload, params):
    path, mal_id, eps_watched = payload.rsplit("/")
    control.draw_items(BROWSER.get_watch_order(mal_id), 'tvshows')


@Route('anime_reviews/*')
def ANIME_REVIEWS(payload, params):
    parts = payload.strip('/').split('/')
    if len(parts) >= 3:
        path, mal_id, eps_watched = parts[-3], parts[-2], parts[-1]
    elif len(parts) == 2:
        path, mal_id = parts
        eps_watched = '0'
    else:
        control.notify(control.ADDON_NAME, control.lang(30461))
        control.draw_items([], 'addons')
        return
    page = int(params.get('page', 1))
    draw_anime_reviews_listing(mal_id, page, path, eps_watched)


@Route('view_review/*')
def VIEW_REVIEW(payload, params):
    import json as json_mod
    parts = payload.strip('/').split('/')
    mal_id = parts[0]
    review_idx = int(parts[1])
    cached = control.getGlobalProp('otaku.reviews.cache')
    if not cached:
        page = int(control.getGlobalProp('otaku.reviews.page') or 1)
        reviews = BROWSER.refetch_reviews_page(mal_id, page)
        if reviews is None:
            control.notify(control.ADDON_NAME, control.lang(30461))
            return
        if not reviews:
            control.notify(control.ADDON_NAME, control.lang(30461))
            return
    else:
        reviews = json_mod.loads(cached)
    if review_idx >= len(reviews):
        control.notify(control.ADDON_NAME, control.lang(30461))
        return
    review = reviews[review_idx]
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
    is_preliminary = review.get('is_preliminary', False)
    is_spoiler = review.get('is_spoiler', False)
    reactions = review.get('reactions') or {}
    flags = []
    if is_preliminary:
        flags.append('Preliminary')
    if is_spoiler:
        flags.append('Spoiler')
    flag_str = f"  |  [{', '.join(flags)}]" if flags else ''
    header = f"By: {username}  |  Score: {score_show}  |  {tag_str}  |  {date}{flag_str}"
    reaction_line = f"Reactions - Nice: {reactions.get('nice', 0)} | Love it: {reactions.get('love_it', 0)} | Funny: {reactions.get('funny', 0)} | Informative: {reactions.get('informative', 0)} | Well Written: {reactions.get('well_written', 0)} | Creative: {reactions.get('creative', 0)}"
    separator = '-' * 60
    body = review.get('review', 'No review text available.')
    full_text = f"{header}\n{reaction_line}\n{separator}\n\n{body}"
    control.textviewer_dialog(f"Review by {username}", full_text)


@Route('anime_statistics/*')
def ANIME_STATISTICS(payload, params):
    parts = payload.strip('/').split('/')
    if len(parts) >= 3:
        mal_id = parts[-2]
    elif len(parts) == 2:
        mal_id = parts[-1]
    else:
        control.notify(control.ADDON_NAME, control.lang(30463))
        return
    open_anime_statistics(mal_id)


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

                # Handle fanart (may be a list)
                fanart = entry.get('fanart', '')
                if isinstance(fanart, list) and fanart:
                    fanart = random.choice(fanart)

                # Handle banner with fallback to poster
                banner = entry.get('banner', '')
                if isinstance(banner, list) and banner:
                    banner = random.choice(banner)
                if not banner:
                    banner = entry.get('poster', '')

                base = {
                    'name': title,
                    'url': f'animes/{mal_id}/',
                    'image': entry.get('poster', ''),
                    'poster': entry.get('poster', ''),
                    'fanart': fanart,
                    'banner': banner,
                    'info': info
                }

                if entry.get('thumb'):
                    thumb = entry['thumb']
                    base['landscape'] = random.choice(thumb) if isinstance(thumb, list) else thumb
                if entry.get('clearart'):
                    clearart = entry['clearart']
                    base['clearart'] = random.choice(clearart) if isinstance(clearart, list) else clearart
                if entry.get('clearlogo'):
                    clearlogo = entry['clearlogo']
                    base['clearlogo'] = random.choice(clearlogo) if isinstance(clearlogo, list) else clearlogo

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


@Route('source_filter')
def SOURCE_FILTER(payload, params):
    """Open the filter selection dialog"""
    from resources.lib.windows.filter_select import FilterSelect
    try:
        window = FilterSelect("filter_select.xml", control.ADDON_PATH)
        window.doModal()
    finally:
        del window


@Route('airing_calendar')
def AIRING_CALENDAR(payload: str, params: dict):
    # Get enriched calendar data from AnimeSchedule
    from resources.lib.AnimeSchedule import AnimeScheduleCalendar
    scheduler = AnimeScheduleCalendar()
    calendar_data = scheduler.get_calendar_data(types=['sub', 'dub', 'raw'])

    if calendar_data:
        # Format data for Anichart display
        formatted_calendar = scheduler.format_for_anichart(calendar_data)

        from resources.lib.windows.anichart import Anichart
        Anichart('anichart.xml', control.ADDON_PATH, calendar=formatted_calendar).doModal()
    control.exit_code()


@multi_route(*_browser_list_route_paths('airing_last_season'))
def AIRING_LAST_SEASON(payload, params):
    _draw_browser_page('get_airing_last_season', 'airing_last_season', params)


@multi_route(*_browser_list_route_paths('airing_this_season'))
def AIRING_THIS_SEASON(payload, params):
    _draw_browser_page('get_airing_this_season', 'airing_this_season', params)


@multi_route(*_browser_list_route_paths('airing_next_season'))
def AIRING_NEXT_SEASON(payload, params):
    _draw_browser_page('get_airing_next_season', 'airing_next_season', params)


@multi_route(*_browser_list_route_paths('trending_last_year'))
def TRENDING_LAST_YEAR(payload, params):
    _draw_browser_page('get_trending_last_year', 'trending_last_year', params)


@multi_route(*_browser_list_route_paths('trending_this_year'))
def TRENDING_THIS_YEAR(payload, params):
    _draw_browser_page('get_trending_this_year', 'trending_this_year', params)


@multi_route(*_browser_list_route_paths('trending_last_season'))
def TRENDING_LAST_SEASON(payload, params):
    _draw_browser_page('get_trending_last_season', 'trending_last_season', params)


@multi_route(*_browser_list_route_paths('trending_this_season'))
def TRENDING_THIS_SEASON(payload, params):
    _draw_browser_page('get_trending_this_season', 'trending_this_season', params)


@multi_route(*_browser_list_route_paths('all_time_trending'))
def ALL_TIME_TRENDING(payload, params):
    _draw_browser_page('get_all_time_trending', 'all_time_trending', params)


@multi_route(*_browser_list_route_paths('popular_last_year'))
def POPULAR_LAST_YEAR(payload, params):
    _draw_browser_page('get_popular_last_year', 'popular_last_year', params)


@multi_route(*_browser_list_route_paths('popular_this_year'))
def POPULAR_THIS_YEAR(payload, params):
    _draw_browser_page('get_popular_this_year', 'popular_this_year', params)


@multi_route(*_browser_list_route_paths('popular_last_season'))
def POPULAR_LAST_SEASON(payload, params):
    _draw_browser_page('get_popular_last_season', 'popular_last_season', params)


@multi_route(*_browser_list_route_paths('popular_this_season'))
def POPULAR_THIS_SEASON(payload, params):
    _draw_browser_page('get_popular_this_season', 'popular_this_season', params)


@multi_route(*_browser_list_route_paths('all_time_popular'))
def ALL_TIME_POPULAR(payload, params):
    _draw_browser_page('get_all_time_popular', 'all_time_popular', params)


@multi_route(*_browser_list_route_paths('voted_last_year'))
def VOTED_LAST_YEAR(payload, params):
    _draw_browser_page('get_voted_last_year', 'voted_last_year', params)


@multi_route(*_browser_list_route_paths('voted_this_year'))
def VOTED_THIS_YEAR(payload, params):
    _draw_browser_page('get_voted_this_year', 'voted_this_year', params)


@multi_route(*_browser_list_route_paths('voted_last_season'))
def VOTED_LAST_SEASON(payload, params):
    _draw_browser_page('get_voted_last_season', 'voted_last_season', params)


@multi_route(*_browser_list_route_paths('voted_this_season'))
def VOTED_THIS_SEASON(payload, params):
    _draw_browser_page('get_voted_this_season', 'voted_this_season', params)


@multi_route(*_browser_list_route_paths('all_time_voted'))
def ALL_TIME_VOTED(payload, params):
    _draw_browser_page('get_all_time_voted', 'all_time_voted', params)


@multi_route(*_browser_list_route_paths('favourites_last_year'))
def FAVOURITES_LAST_YEAR(payload, params):
    _draw_browser_page('get_favourites_last_year', 'favourites_last_year', params)


@multi_route(*_browser_list_route_paths('favourites_this_year'))
def FAVOURITES_THIS_YEAR(payload, params):
    _draw_browser_page('get_favourites_this_year', 'favourites_this_year', params)


@multi_route(*_browser_list_route_paths('favourites_last_season'))
def FAVOURITES_LAST_SEASON(payload, params):
    _draw_browser_page('get_favourites_last_season', 'favourites_last_season', params)


@multi_route(*_browser_list_route_paths('favourites_this_season'))
def FAVOURITES_THIS_SEASON(payload, params):
    _draw_browser_page('get_favourites_this_season', 'favourites_this_season', params)


@multi_route(*_browser_list_route_paths('all_time_favourites'))
def ALL_TIME_FAVOURITES(payload, params):
    _draw_browser_page('get_all_time_favourites', 'all_time_favourites', params)


@multi_route(*_browser_list_route_paths('top_100'))
def TOP_100(payload, params):
    _draw_browser_page('get_top_100', 'top_100', params)



@multi_route(*[p + '/*' for p in _GENRES_WILDCARD_PREFIXES])
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
        format = mapping[base_key][0] if control.getStr('browser.api') in _MAL_OTAKU_APIS else mapping[base_key][1]
    if genres or tags:
        prefix = plugin_url.split('/', 1)[0]
        items = BROWSER.genres_payload(genres, tags, page, format, prefix)
        control.draw_items(items, 'tvshows')
        control.schedule_next_page_prefetch(
            items,
            lambda g=genres, t=tags, p=page + 1, fmt=format, pr=prefix: BROWSER.genres_payload(g, t, p, fmt, pr))
    else:
        items = BROWSER.get_genres(page, format)
        control.draw_items(items, 'tvshows')
        control.schedule_next_page_prefetch(
            items,
            lambda p=page + 1, fmt=format: BROWSER.get_genres(p, fmt))


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


@multi_route(*_browser_list_route_paths('genre_action'))
def GENRE_ACTION(payload, params):
    _draw_genre_page('genre_action', params)


@multi_route(*_browser_list_route_paths('genre_adventure'))
def GENRE_ADVENTURE(payload, params):
    _draw_genre_page('genre_adventure', params)


@multi_route(*_browser_list_route_paths('genre_comedy'))
def GENRE_COMEDY(payload, params):
    _draw_genre_page('genre_comedy', params)


@multi_route(*_browser_list_route_paths('genre_drama'))
def GENRE_DRAMA(payload, params):
    _draw_genre_page('genre_drama', params)


@multi_route(*_browser_list_route_paths('genre_ecchi'))
def GENRE_ECCHI(payload, params):
    _draw_genre_page('genre_ecchi', params)


@multi_route(*_browser_list_route_paths('genre_fantasy'))
def GENRE_FANTASY(payload, params):
    _draw_genre_page('genre_fantasy', params)


@multi_route(*_browser_list_route_paths('genre_hentai'))
def GENRE_HENTAI(payload, params):
    _draw_genre_page('genre_hentai', params)


@multi_route(*_browser_list_route_paths('genre_horror'))
def GENRE_HORROR(payload, params):
    _draw_genre_page('genre_horror', params)


@multi_route(*_browser_list_route_paths('genre_shoujo'))
def GENRE_SHOUJO(payload, params):
    _draw_genre_page('genre_shoujo', params)


@multi_route(*_browser_list_route_paths('genre_mecha'))
def GENRE_MECHA(payload, params):
    _draw_genre_page('genre_mecha', params)


@multi_route(*_browser_list_route_paths('genre_music'))
def GENRE_MUSIC(payload, params):
    _draw_genre_page('genre_music', params)


@multi_route(*_browser_list_route_paths('genre_mystery'))
def GENRE_MYSTERY(payload, params):
    _draw_genre_page('genre_mystery', params)


@multi_route(*_browser_list_route_paths('genre_psychological'))
def GENRE_PSYCHOLOGICAL(payload, params):
    _draw_genre_page('genre_psychological', params)


@multi_route(*_browser_list_route_paths('genre_romance'))
def GENRE_ROMANCE(payload, params):
    _draw_genre_page('genre_romance', params)


@multi_route(*_browser_list_route_paths('genre_sci_fi'))
def GENRE_SCI_FI(payload, params):
    _draw_genre_page('genre_sci_fi', params)


@multi_route(*_browser_list_route_paths('genre_slice_of_life'))
def GENRE_SLICE_OF_LIFE(payload, params):
    _draw_genre_page('genre_slice_of_life', params)


@multi_route(*_browser_list_route_paths('genre_sports'))
def GENRE_SPORTS(payload, params):
    _draw_genre_page('genre_sports', params)


@multi_route(*_browser_list_route_paths('genre_supernatural'))
def GENRE_SUPERNATURAL(payload, params):
    _draw_genre_page('genre_supernatural', params)


@multi_route(*_browser_list_route_paths('genre_thriller'))
def GENRE_THRILLER(payload, params):
    _draw_genre_page('genre_thriller', params)



# search_<api>/ URL prefix, internal type id, (mal_pair, anilist_pair)
_SEARCH_ROUTE_META = (
    ('search_anime/', 'anime', ('', '')),
    ('search_tv_show/', 'tv_show', ('tv', 'TV')),
    ('search_movie/', 'movie', ('movie', 'MOVIE')),
    ('search_tv_short/', 'tv_short', ('tv_special', 'TV_SHORT')),
    ('search_special/', 'special', ('special', 'SPECIAL')),
    ('search_ova/', 'ova', ('ova', 'OVA')),
    ('search_ona/', 'ona', ('ona', 'ONA')),
    ('search_music/', 'music', ('music', 'MUSIC')),
)


def get_search_config():
    search_types = [row[0] for row in _SEARCH_ROUTE_META]
    types = {row[0]: row[1] for row in _SEARCH_ROUTE_META}
    mappings = {row[0]: row[2] for row in _SEARCH_ROUTE_META}
    formats = {'search_history_%s' % row[1]: row[1] for row in _SEARCH_ROUTE_META}
    return search_types, types, mappings, formats


_SEARCH_HISTORY_ROUTE_NAMES = tuple('search_history_%s' % row[1] for row in _SEARCH_ROUTE_META)
# Kodi router wildcard routes: ``search_anime/*`` matches URLs under ``search_anime/…``
_SEARCH_WILDCARD_ROUTES = tuple(row[0][:-1] + '/*' for row in _SEARCH_ROUTE_META)

_CLEAR_SEARCH_HISTORY_ROUTES = (
    'clear_search_history',
    'clear_search_history_anime',
    'clear_search_history_movie',
    'clear_search_history_tv_show',
    'clear_search_history_tv_short',
    'clear_search_history_special',
    'clear_search_history_ova',
    'clear_search_history_ona',
    'clear_search_history_music',
)
_CLEAR_SEARCH_HISTORY_MAP = {'clear_search_history': 'all'}
_CLEAR_SEARCH_HISTORY_MAP.update(
    {'clear_search_history_%s' % row[1]: row[1] for row in _SEARCH_ROUTE_META}
)


@multi_route(*_SEARCH_HISTORY_ROUTE_NAMES)
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
                query = control.keyboard(control.lang(30018), decoded_item)
                if query and query != decoded_item:
                    database.remove_search(table=format, value=decoded_item)
                    control.sleep(500)
                    database.addSearchHistory(query, format)
                found = True
    if not found:
        control.notify(control.ADDON_NAME, "Failed to edit search item", time=3000)
    control.refresh()
    control.exit_code()


@multi_route(*_SEARCH_WILDCARD_ROUTES)
def SEARCH(payload, params):
    from urllib.parse import unquote
    _, types, mappings, _ = get_search_config()

    type = None
    format = None

    for key in types:
        if plugin_url.startswith(key):
            type = types[key]
            break

    for key in mappings:
        if plugin_url.startswith(key):
            format = mappings[key][0] if control.getStr('browser.api') in _MAL_OTAKU_APIS else mappings[key][1]
            break

    query = unquote(payload) if payload else payload
    page = int(params.get('page', 1))
    if not query:
        query = control.keyboard(control.lang(30018))
        if not query:
            return control.draw_items([], 'tvshows')
        if control.getInt('searchhistory') == 0:
            database.addSearchHistory(query, type)
    prefix = plugin_url.split('/', 1)[0]
    items = BROWSER.get_search(query, page, format, prefix)
    control.draw_items(items, 'tvshows')
    control.schedule_next_page_prefetch(
        items,
        lambda q=query, p=page + 1, fmt=format, pr=prefix: BROWSER.get_search(q, p, fmt, pr))


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
        if not episode_data:
            MetaBrowser.get_anime_init(mal_id)
            episode_data = database.get_episode(mal_id, episode)
        if episode_data:
            params = pickle.loads(episode_data['kodi_meta'])
        else:
            # Fallback: build minimal params from show database
            # This ensures metadata is available even for episodes not yet indexed
            show_meta = database.get_show(mal_id)
            if show_meta:
                kodi_meta = pickle.loads(show_meta['kodi_meta'])
                show_art = database.get_show_meta(mal_id)
                art = pickle.loads(show_art['art']) if show_art and show_art.get('art') else {}
                params = {
                    'info': {
                        'title': f"{kodi_meta.get('title_userPreferred', '')} - Episode {episode}",
                        'tvshowtitle': kodi_meta.get('title_userPreferred', ''),
                        'episode': int(episode),
                        'plot': kodi_meta.get('plot', ''),
                        'mediatype': 'episode',
                        'UniqueIDs': {'mal_id': str(mal_id), **database.get_unique_ids(mal_id, 'mal_id')},
                    },
                    'image': {
                        'poster': art.get('poster') or kodi_meta.get('poster', ''),
                        'fanart': art.get('fanart', ''),
                        'icon': art.get('poster') or kodi_meta.get('poster', ''),
                        'thumb': art.get('thumb', ''),
                    },
                    'path': params.get('path', ''),
                }

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
        from resources.lib.OtakuBrowser import OtakuBrowser
        OtakuBrowser().get_anime_data(mal_id)
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
            control.log("No fuzzy or direct match for Jikan episode titles against TMDB titles.")
    return None  # No match found


@multi_route(*_wildcard_browser_paths('marked_as_watched'))
def MARKED_AS_WATCHED(payload, params):
    from resources.lib.WatchlistIntegration import watchlist_update_episode
    import service

    payload_list = payload.split("/")
    if len(payload_list) == 2 and payload_list[1]:
        mal_id, episode = payload_list
    else:
        mal_id = payload_list[0] if payload_list else ""
        episode = 1

    any_completed = watchlist_update_episode(mal_id, episode)
    if any_completed:
        control.sleep(3000)
        service.sync_watchlist(True)

    # Build notification showing updated watchlists
    enabled = control.enabled_watchlists()
    flavor_labels = {'anilist': 'AniList', 'kitsu': 'Kitsu', 'mal': 'MAL', 'simkl': 'Simkl'}
    updated_names = ', '.join([flavor_labels.get(f, f.capitalize()) for f in enabled]) if enabled else 'No Watchlist'

    if len(payload_list) == 2 and payload_list[1]:
        control.notify(control.ADDON_NAME, f'Episode #{episode} was Marked as Watched in {updated_names}')
        control.execute(f'ActivateWindow(Videos,plugin://{control.ADDON_ID}/watchlist_to_ep/{mal_id}/{episode})')
    else:
        show = database.get_show(mal_id)
        title = ''
        if show:
            kodi_meta = pickle.loads(show['kodi_meta'])
            title = kodi_meta.get('title_userPreferred', '')
        control.notify(control.ADDON_NAME, f'{title} was Marked as Watched in {updated_names}')
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
    elif payload == 'easynews':
        from resources.lib.debrid.easynews import Easynews
        Easynews().auth()


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


def _maybe_refresh_main_menu(log_msg):
    if control.getGlobalProp('otaku.menu.needs_refresh') == 'true':
        control.clearGlobalProp('otaku.menu.needs_refresh')
        control.log(log_msg)


def _collect_category_menu_items(menu_items_key, settings_key, extra_key_suffix):
    enabled_items = []
    enabled_items = add_watchlist(enabled_items)
    enabled_ids = control.getStringList(settings_key)
    if "last_watched%s" % extra_key_suffix in enabled_ids:
        enabled_items = add_last_watched(enabled_items)
    if "watch_history%s" % extra_key_suffix in enabled_ids:
        enabled_items = add_watch_history(enabled_items)
    if "next_up%s" % extra_key_suffix in enabled_ids:
        enabled_items = add_next_up(enabled_items)
    for item in get_menu_items(menu_items_key):
        if item[1] in enabled_ids:
            enabled_items.append(item)
    return enabled_items


def _finalize_menu_list_items(menu_items):
    processed = []
    for item in menu_items:
        if len(item) == 6 and item[0] == 'LAST_WATCHED_ITEM':
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
            if kodi_meta.get('thumb'):
                thumb = kodi_meta['thumb']
                base['landscape'] = random.choice(thumb) if isinstance(thumb, list) else thumb
            if kodi_meta.get('clearart'):
                clearart = kodi_meta['clearart']
                base['clearart'] = random.choice(clearart) if isinstance(clearart, list) else clearart
            if kodi_meta.get('clearlogo'):
                clearlogo = kodi_meta['clearlogo']
                base['clearlogo'] = random.choice(clearlogo) if isinstance(clearlogo, list) else clearlogo
            episodes = kodi_meta.get('episodes', 0)
            if episodes == 1:
                processed.append(utils.parse_view(base, False, True, False))
            else:
                processed.append(utils.parse_view(base, True, False, False))
        else:
            name, url, image, info = item
            processed.append(utils.allocate_item(name, url, True, False, [], image, info))
    return processed


def _draw_category_main_menu(menu_items_key, settings_key, extra_key_suffix, refresh_log_msg):
    _maybe_refresh_main_menu(refresh_log_msg)
    enabled = _collect_category_menu_items(menu_items_key, settings_key, extra_key_suffix)
    processed = _finalize_menu_list_items(enabled)
    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items(processed, view_type)


def _draw_filtered_submenu(menu_items_key, settings_key):
    items = get_menu_items(menu_items_key)
    enabled_ids = control.getStringList(settings_key)
    enabled = [item for item in items if item[1] in enabled_ids]
    view_type = 'addons' if control.getBool('interface.content_type') else ''
    control.draw_items(
        [utils.allocate_item(name, url, True, False, [], image, info) for name, url, image, info in enabled],
        view_type,
    )


# --- UI route registration (main menu + filtered submenus) --------------------
# (url route, handler __name__, menu key, settings id, last_watched suffix, refresh log message)
_CATEGORY_MAIN_MENU_ROUTES = (
    ('', 'LIST_MENU', 'main', 'menu.mainmenu.config', '', 'Menu refresh flag detected - rebuilding menu items'),
    ('movies', 'MOVIES_MENU', 'movies', 'movie.mainmenu.config', '_movie', 'Movie menu refresh flag detected - rebuilding menu items'),
    ('tv_shows', 'TV_SHOWS_MENU', 'tv_shows', 'tv_show.mainmenu.config', '_tv_show', 'TV shows menu refresh flag detected - rebuilding menu items'),
    ('tv_shorts', 'TV_SHORTS_MENU', 'tv_shorts', 'tv_short.mainmenu.config', '_tv_short', 'TV shorts menu refresh flag detected - rebuilding menu items'),
    ('specials', 'SPECIALS_MENU', 'specials', 'special.mainmenu.config', '_special', 'Specials menu refresh flag detected - rebuilding menu items'),
    ('ovas', 'OVAS_MENU', 'ovas', 'ova.mainmenu.config', '_ova', 'OVAs menu refresh flag detected - rebuilding menu items'),
    ('onas', 'ONAS_MENU', 'onas', 'ona.mainmenu.config', '_ona', 'ONAs menu refresh flag detected - rebuilding menu items'),
    ('music', 'MUSIC_MENU', 'music', 'music.mainmenu.config', '_music', 'Music menu refresh flag detected - rebuilding menu items'),
)

_FILTERED_SUBMENU_ROUTES = (
    ('trending', 'TRENDING_MENU', 'trending', 'menu.submenu.config'),
    ('trending_movie', 'TRENDING_MOVIE_MENU', 'trending_movie', 'movie.submenu.config'),
    ('trending_tv_show', 'TRENDING_TV_SHOW_MENU', 'trending_tv_show', 'tv_show.submenu.config'),
    ('trending_tv_short', 'TRENDING_TV_SHORT_MENU', 'trending_tv_short', 'tv_short.submenu.config'),
    ('trending_special', 'TRENDING_SPECIAL_MENU', 'trending_special', 'special.submenu.config'),
    ('trending_ova', 'TRENDING_OVA_MENU', 'trending_ova', 'ova.submenu.config'),
    ('trending_ona', 'TRENDING_ONA_MENU', 'trending_ona', 'ona.submenu.config'),
    ('trending_music', 'TRENDING_MUSIC_MENU', 'trending_music', 'music.submenu.config'),
    ('popular', 'POPULAR_MENU', 'popular', 'menu.submenu.config'),
    ('popular_movie', 'POPULAR_MOVIE_MENU', 'popular_movie', 'movie.submenu.config'),
    ('popular_tv_show', 'POPULAR_TV_SHOW_MENU', 'popular_tv_show', 'tv_show.submenu.config'),
    ('popular_tv_short', 'POPULAR_TV_SHORT_MENU', 'popular_tv_short', 'tv_short.submenu.config'),
    ('popular_special', 'POPULAR_SPECIAL_MENU', 'popular_special', 'special.submenu.config'),
    ('popular_ova', 'POPULAR_OVA_MENU', 'popular_ova', 'ova.submenu.config'),
    ('popular_ona', 'POPULAR_ONA_MENU', 'popular_ona', 'ona.submenu.config'),
    ('popular_music', 'POPULAR_MUSIC_MENU', 'popular_music', 'music.submenu.config'),
    ('voted', 'VOTED_MENU', 'voted', 'menu.submenu.config'),
    ('voted_movie', 'VOTED_MOVIE_MENU', 'voted_movie', 'movie.submenu.config'),
    ('voted_tv_show', 'VOTED_TV_SHOW_MENU', 'voted_tv_show', 'tv_show.submenu.config'),
    ('voted_tv_short', 'VOTED_TV_SHORT_MENU', 'voted_tv_short', 'tv_short.submenu.config'),
    ('voted_special', 'VOTED_SPECIAL_MENU', 'voted_special', 'special.submenu.config'),
    ('voted_ova', 'VOTED_OVA_MENU', 'voted_ova', 'ova.submenu.config'),
    ('voted_ona', 'VOTED_ONA_MENU', 'voted_ona', 'ona.submenu.config'),
    ('voted_music', 'VOTED_MUSIC_MENU', 'voted_music', 'music.submenu.config'),
    ('favourites', 'FAVOURITES_MENU', 'favourites', 'menu.submenu.config'),
    ('favourites_movie', 'FAVOURITES_MOVIE_MENU', 'favourites_movie', 'movie.submenu.config'),
    ('favourites_tv_show', 'FAVOURITES_TV_SHOW_MENU', 'favourites_tv_show', 'tv_show.submenu.config'),
    ('favourites_tv_short', 'FAVOURITES_TV_SHORT_MENU', 'favourites_tv_short', 'tv_short.submenu.config'),
    ('favourites_special', 'FAVOURITES_SPECIAL_MENU', 'favourites_special', 'special.submenu.config'),
    ('favourites_ova', 'FAVOURITES_OVA_MENU', 'favourites_ova', 'ova.submenu.config'),
    ('favourites_ona', 'FAVOURITES_ONA_MENU', 'favourites_ona', 'ona.submenu.config'),
    ('favourites_music', 'FAVOURITES_MUSIC_MENU', 'favourites_music', 'music.submenu.config'),
    ('genres', 'GENRES_MENU', 'genres', 'menu.genres.config'),
    ('genres_movie', 'GENRE_MOVIE_MENU', 'genres_movie', 'movie.genres.config'),
    ('genres_tv_show', 'GENRE_TV_SHOW_MENU', 'genres_tv_show', 'tv_show.genres.config'),
    ('genres_tv_short', 'GENRE_TV_SHORT_MENU', 'genres_tv_short', 'tv_short.genres.config'),
    ('genres_special', 'GENRE_SPECIAL_MENU', 'genres_special', 'special.genres.config'),
    ('genres_ova', 'GENRE_OVA_MENU', 'genres_ova', 'ova.genres.config'),
    ('genres_ona', 'GENRE_ONA_MENU', 'genres_ona', 'ona.genres.config'),
    ('genres_music', 'GENRE_MUSIC_MENU', 'genres_music', 'music.genres.config'),
)


def _register_ui_menu_routes():
    """Wire LIST_MENU / submenus; exposes Main.LIST_MENU etc. for compatibility."""
    mod = sys.modules[__name__]
    for route, fname, mkey, cfg, suf, log in _CATEGORY_MAIN_MENU_ROUTES:
        def cat_handler(payload, params, mk=mkey, sk=cfg, sx=suf, lg=log):
            _draw_category_main_menu(mk, sk, sx, lg)
        cat_handler.__name__ = fname
        cat_handler.__qualname__ = fname
        setattr(mod, fname, cat_handler)
        Route(route)(cat_handler)

    for route, fname, mkey, cfg in _FILTERED_SUBMENU_ROUTES:
        def sub_handler(payload, params, mk=mkey, sk=cfg):
            _draw_filtered_submenu(mk, sk)
        sub_handler.__name__ = fname
        sub_handler.__qualname__ = fname
        setattr(mod, fname, sub_handler)
        Route(route)(sub_handler)


_register_ui_menu_routes()


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


@multi_route(*_CLEAR_SEARCH_HISTORY_ROUTES)
def CLEAR_SEARCH_HISTORY(payload, params):
    format = _CLEAR_SEARCH_HISTORY_MAP.get(plugin_url)

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
        confirm = control.yesno_dialog(control.ADDON_NAME, control.lang(30091))
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
        confirm = control.yesno_dialog(control.ADDON_NAME, control.lang(30089))
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
        control.setStringList('menu.mainmenu.config', ['last_watched', 'watch_history', 'next_up', 'airing_calendar', 'airing_last_season', 'airing_this_season', 'airing_next_season', 'movies', 'tv_shows', 'tv_shorts', 'specials', 'ovas', 'onas', 'music', 'trending', 'popular', 'voted', 'favourites', 'top_100', 'genres', 'search', 'tools'])

    # No selected
    elif choice == 0:
        control.setStringList('menu.mainmenu.config', ['last_watched', 'watch_history', 'next_up', 'airing_calendar', 'airing_last_season', 'airing_this_season', 'airing_next_season', 'trending', 'popular', 'voted', 'favourites', 'top_100', 'genres', 'search', 'tools'])

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
