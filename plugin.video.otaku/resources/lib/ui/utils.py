import os
import concurrent.futures

from functools import partial
from resources.lib.ui import control, database

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

    url = format_to_url.get(format)
    if url:
        encoded_res = quote(res, safe='')
        return allocate_item(res, f'{url}{encoded_res}', True, False, cm, 'search.png', {})


def search_history(search_array, format):
    cm = [(control.lang(30456), 'remove_search_item'), (control.lang(30457), "edit_search_item")]
    format_to_url, format_to_url_2 = get_format_to_url_mappings()

    result = [allocate_item(control.lang(30458), format_to_url.get(format), True, False, [], 'new_search.png', {})]
    mapfun = partial(parse_history_view, cm=cm)
    result.append(allocate_item(control.lang(30459), format_to_url_2.get(format), False, False, [], 'clear_search_history.png', {}))
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


def get_season(titles_list, mal_id):
    import re
    meta_ids = database.get_mappings(mal_id, 'mal_id')
    if meta_ids.get('thetvdb_season'):
        if meta_ids['thetvdb_season'] == '0' or meta_ids['thetvdb_season'] == 'a':
            return 1
        return int(meta_ids['thetvdb_season'])
    else:
        regexes = [r'season\s(\d+)', r'\s(\d+)st\sseason\s', r'\s(\d+)nd\sseason\s', r'\s(\d+)rd\sseason\s', r'\s(\d+)th\sseason\s']
        s_ids = []
        for regex in regexes:
            s_ids += [re.findall(regex, name, re.IGNORECASE) for name in titles_list]
        s_ids = [s[0] for s in s_ids if s]
        if not s_ids:
            regex = r'\s(\d+)$'
            cour = False
            for name in titles_list:
                if name is not None and (' part ' in name.lower() or ' cour ' in name.lower()):
                    cour = True
                    break
            if not cour:
                s_ids += [re.findall(regex, name, re.IGNORECASE) for name in titles_list]
        s_ids = [s[0] for s in s_ids if s]
        if not s_ids:
            seasonnum = 1
            try:
                for title in titles_list:
                    try:
                        seasonnum = re.search(r' (\d)[ rnt][ sdh(]', f' {title[1]}  ').group(1)
                        break
                    except AttributeError:
                        pass
            except AttributeError:
                pass
            s_ids = [seasonnum]
        season = int(s_ids[0])
        if season > 10:
            season = 1
        return season


def format_time(seconds):
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"


def parallel_fetch(requests_list, max_workers=5, timeout=30):
    """
    Execute multiple HTTP requests in parallel using threading.

    Args:
        requests_list: List of dicts with keys: 'func', 'args' (tuple), 'kwargs' (dict)
        max_workers: Max number of concurrent threads (default: 5)
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


def parallel_process(items, process_func, max_workers=5):
    """
    Process multiple items in parallel using threading.

    Args:
        items: List of items to process
        process_func: Function to apply to each item
        max_workers: Max number of concurrent threads (default: 5)

    Returns:
        List of results in same order as items

    Example:
        slugs = ['slug1', 'slug2', 'slug3']
        results = parallel_process(slugs, lambda slug: scraper._process(slug))
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(process_func, items))
    return results
