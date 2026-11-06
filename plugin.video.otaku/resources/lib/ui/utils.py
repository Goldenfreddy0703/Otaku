"""utils.py - List-Item Allocation & Search History
==================================================
Helpers for creating Kodi directory items, managing search history,
detecting season numbers, and running parallel operations.

Sections
--------
Item Allocation   - allocate_item, parse_view, artwork path cache
Search History    - search_history, parse_history_view, URL mappings
Season Detection  - get_season, resolve_season, get_source_context
Parallel Helpers  - parallel_fetch, parallel_process
"""

import os
import re
import concurrent.futures

from functools import partial
from resources.lib.ui import control, database


# ═══════════════════════════════════════════════════════════════════════════
#  Item Allocation & Artwork Cache
# ═══════════════════════════════════════════════════════════════════════════

# Cache for artwork file paths to avoid repeated os.path.exists() calls
_artwork_path_cache = {}


def _get_artwork_path(filename):
    """Get artwork path with caching to reduce disk I/O"""
    if filename in _artwork_path_cache:
        return _artwork_path_cache[filename]

    genre_path = os.path.join(control.OTAKU_GENRE_PATH, filename)
    art_path = os.path.join(control.OTAKU_ICONS_PATH, filename)
    result = genre_path if os.path.exists(genre_path) else art_path
    _artwork_path_cache[filename] = result
    return result


def allocate_item(name, url, isfolder, isplayable, cm, image='', info=None, fanart=None, poster=None, landscape=None, banner=None, clearart=None, clearlogo=None):
    if image and '/' not in image:
        image = _get_artwork_path(image)
    if fanart and not isinstance(fanart, list) and '/' not in fanart:
        fanart = _get_artwork_path(fanart)
    if poster and '/' not in poster:
        poster = _get_artwork_path(poster)
    return {
        'isfolder': isfolder,
        'isplayable': isplayable,
        'name': name,
        'url': url,
        'info': info,
        'cm': cm,
        'image': {
            'poster': poster,
            'icon': image,
            'thumb': image,
            'fanart': fanart,
            'landscape': landscape,
            'banner': banner,
            'clearart': clearart,
            'clearlogo': clearlogo
        }
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Search History & URL Mappings
# ═══════════════════════════════════════════════════════════════════════════

def get_format_to_url_mappings():
    format_to_url = {
        'anime': 'search_anime/',
        'tv_show': 'search_tv_show/',
        'movie': 'search_movie/',
        'tv_short': 'search_tv_short/',
        'special': 'search_special/',
        'ova': 'search_ova/',
        'ona': 'search_ona/',
        'music': 'search_music/'
    }

    format_to_url_2 = {
        'anime': 'clear_search_history_anime',
        'tv_show': 'clear_search_history_tv_show',
        'movie': 'clear_search_history_movie',
        'tv_short': 'clear_search_history_tv_short',
        'special': 'clear_search_history_special',
        'ova': 'clear_search_history_ova',
        'ona': 'clear_search_history_ona',
        'music': 'clear_search_history_music'
    }

    return format_to_url, format_to_url_2


def parse_history_view(res, cm):
    from urllib.parse import quote
    format = control.getSetting('format')
    format_to_url, _ = get_format_to_url_mappings()

    url = format_to_url.get(format) or format_to_url['anime']
    encoded_res = quote(res, safe='')
    return allocate_item(res, f'{url}{encoded_res}', True, False, cm, 'search.png', {})


def search_history(search_array, format):
    cm = [('Remove from Item', 'remove_search_item'), ("Edit Search Item...", "edit_search_item")]
    format_to_url, format_to_url_2 = get_format_to_url_mappings()

    result = [allocate_item("New Search", format_to_url.get(format), True, False, [], 'new_search.png', {})]
    mapfun = partial(parse_history_view, cm=cm)
    result.append(allocate_item("Clear Search History...", format_to_url_2.get(format), False, False, [], 'clear_search_history.png', {}))
    result += list(map(mapfun, search_array))
    return result


def parse_view(base, isfolder, isplayable, dub=False):
    if control.getBool('divflavors.showdub') and dub:
        base['name'] += ' [COLOR blue](Dub)[/COLOR]'
        base['info']['title'] = base['name']
    poster = base.get("poster") or base["image"]
    parsed_view = allocate_item(base["name"], base["url"], isfolder, isplayable, [], base["image"], base["info"], fanart=base.get("fanart"), poster=poster, landscape=base.get("landscape"), banner=base.get("banner"), clearart=base.get("clearart"), clearlogo=base.get("clearlogo"))
    if control.getBool('divflavors.dubonly') and not dub:
        parsed_view = None
    return parsed_view


# ═══════════════════════════════════════════════════════════════════════════
#  Season Detection
# ═══════════════════════════════════════════════════════════════════════════

_CJK_NUMERALS = '一二三四五六七八九十'
_SEASON_PATTERNS = (
    r'season[\s._-]*(\d{1,2})\b',                        # Season 2, Season2
    r'\b(\d{1,2})(?:st|nd|rd|th)[\s._-]+season\b',        # 2nd Season
    r'(?<![a-z0-9])s(\d{1,2})(?![a-z0-9])',                # S2, S02
    r'第\s*(\d{1,2})\s*[期季]',                           # 第2期
    rf'第\s*([{_CJK_NUMERALS}])\s*[期季]',                 # 第二季
)


def _mapped_season(mal_id):
    meta_ids = database.get_mappings(mal_id, 'mal_id')
    thetvdb_season = meta_ids.get('thetvdb_season') if meta_ids else None
    if thetvdb_season:
        if thetvdb_season == '0' or thetvdb_season == 'a':
            return 1
        return int(thetvdb_season)
    return None


def _parse_season(titles_list):
    """Read a season from titles. Returns (season, source).

    source is 'title' for an explicit season marker, or 'default' when nothing
    trustworthy was found, including a bare trailing number ("Kaiju No. 8").
    """
    titles = [title for title in titles_list if title]
    for pattern in _SEASON_PATTERNS:
        for title in titles:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                value = match.group(1)
                season = _CJK_NUMERALS.index(value) + 1 if value in _CJK_NUMERALS else int(value)
                if 1 <= season <= 10:
                    return season, 'title'

    if not any(' part ' in title.lower() or ' cour ' in title.lower() for title in titles):
        for title in titles:
            match = re.search(r'\s(\d+)$', title)
            if match and 1 <= int(match.group(1)) <= 10:
                return int(match.group(1)), 'default'
    return 1, 'default'


def get_season(titles_list, mal_id):
    mapped = _mapped_season(mal_id)
    if mapped is not None:
        return mapped
    return _parse_season(titles_list)[0]


def _fetch_anizip_summary(mal_id):
    from resources.lib.indexers import anizip
    try:
        data = anizip.ANIZIPAPI().get_anime_info(mal_id)
    except Exception as e:
        control.log(f'ani.zip lookup failed for {mal_id}: {e}', 'warning')
        return None
    if not data:
        return None

    episodes = data.get('episodes') or {}
    numbers = sorted(int(number) for number in episodes if number.isdigit())
    first = episodes[str(numbers[0])] if numbers else {}
    season = first.get('seasonNumber')
    episode_number = first.get('episodeNumber')
    absolute_number = first.get('absoluteEpisodeNumber')
    offset = 0
    if isinstance(episode_number, int) and isinstance(absolute_number, int) and absolute_number > episode_number:
        offset = absolute_number - episode_number

    return {
        'season': season if isinstance(season, int) and season > 0 else None,
        'offset': offset,
    }


def get_anizip_summary(mal_id):
    return database.get(_fetch_anizip_summary, 24, mal_id, key='anizip_summary') or {}


def resolve_season(titles_list, mal_id):
    """Best known season for a show. Returns (season, source).

    source says how far the value can be trusted: 'mapping' and 'anizip' are
    TVDB-backed, 'title' is an explicit season marker in a title, and 'default'
    means nothing was found, so it must not be used to reject releases.
    """
    mapped = _mapped_season(mal_id)
    if mapped is not None:
        return mapped, 'mapping'
    anizip_season = get_anizip_summary(mal_id).get('season')
    if anizip_season:
        return anizip_season, 'anizip'
    return _parse_season(titles_list)


def get_source_context(mal_id, kodi_meta, stored_season, episode):
    """Season and filter hints for a scrape. Returns (season, hints).

    Runs on every scrape, so a season stored wrongly in the past corrects itself.
    """
    season, source = resolve_season([kodi_meta.get('name'), kodi_meta.get('ename')], mal_id)
    if source == 'default' and stored_season and stored_season > 1:
        # The indexer saw more titles than are stored here
        season, source = stored_season, 'title'
    if stored_season and stored_season != season and source != 'default':
        control.log(f'Correcting stored season {stored_season} -> {season} for {mal_id} ({source})')
        database.update_show_season(mal_id, season)

    summary = get_anizip_summary(mal_id)
    offset = summary.get('offset')
    return season, {
        'season_source': source,
        'absolute_episode': int(episode) + offset if offset else None,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Parallel Helpers
# ═══════════════════════════════════════════════════════════════════════════

def format_time(seconds):
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"


def parallel_fetch(requests_list, max_workers=None, timeout=30):
    """
    Execute multiple HTTP requests in parallel using threading.

    Args:
        requests_list: List of dicts with keys: 'func', 'args' (tuple), 'kwargs' (dict)
        max_workers: Max number of concurrent threads (default: control.max_threads)
        timeout: Timeout for all requests combined (default: 30s, set to None for no timeout)

    Returns:
        List of results in same order as requests_list

    Example:
        requests = [
            {'func': client.get, 'args': (url1,), 'kwargs': {'headers': headers}},
            {'func': client.get, 'args': (url2,), 'kwargs': {'timeout': 10}}
        ]
        results = parallel_fetch(requests)
    """
    if max_workers is None:
        max_workers = control.max_threads

    def execute_request(request):
        try:
            func = request['func']
            args = request.get('args', ())
            kwargs = request.get('kwargs', {})
            return func(*args, **kwargs)
        except Exception as e:
            control.log(f"Parallel request error: {str(e)}")
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks and maintain order with a dict mapping futures to original index
        future_to_index = {executor.submit(execute_request, req): idx for idx, req in enumerate(requests_list)}

        # Create a results list to maintain order
        results = [None] * len(requests_list)

        # Collect results as they complete (true parallel execution)
        # No timeout on as_completed since individual requests might take a while
        for future in concurrent.futures.as_completed(future_to_index):
            idx = future_to_index[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                control.log(f"Parallel request failed: {str(e)}")
                results[idx] = None

    return results


def parallel_process(items, process_func, max_workers=None):
    """
    Process multiple items in parallel using threading.

    Args:
        items: List of items to process
        process_func: Function to apply to each item
        max_workers: Max number of concurrent threads (default: control.max_threads)

    Returns:
        List of results in same order as items

    Example:
        slugs = ['slug1', 'slug2', 'slug3']
        results = parallel_process(slugs, lambda slug: scraper._process(slug))
    """
    if max_workers is None:
        max_workers = control.max_threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(process_func, items))
    return results
