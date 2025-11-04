import datetime
import re
import time
import json

from bs4 import BeautifulSoup
from resources.lib.ui import client, database, control

base_url = "https://animeschedule.net/api/v3"
dub_list = []

# Load API token from info.db following maintainer's pattern
_api_info = None
_api_token = None
_token_load_attempted = False

def _get_api_token():
    """Load AnimeSchedule API token from info.db with caching."""
    global _api_info, _api_token, _token_load_attempted

    if _token_load_attempted:
        return _api_token

    _token_load_attempted = True

    try:
        _api_info = database.get_info('AnimeSchedule')
        if _api_info:
            # Handle both dict-like and tuple responses
            if isinstance(_api_info, dict):
                token = _api_info.get('client_secret', '').strip()
            else:
                # If it's a tuple/namedtuple, convert to dict
                # Structure: (api_name, api_key, client_id, client_secret, description)
                if len(_api_info) >= 4:
                    token = _api_info[3].strip() if _api_info[3] else ''
                else:
                    token = ''

            if token:
                _api_token = token
                control.log("[AnimeSched] API token loaded successfully", "info")
            else:
                control.log("[AnimeSched] Missing API token. Timetables will not work.", "warning")
        else:
            control.log("[AnimeSched] AnimeSchedule not found in database. Timetables will not work.", "warning")
    except Exception as e:
        control.log(f"[AnimeSched] Error loading API token: {str(e)}", "error")

    return _api_token


def build_image_url(image_version_route):
    """Build full image URL from imageVersionRoute.
    
    Args:
        image_version_route: The route like "anime/jpg/default/gachiakuta-39ad997d70.jpg"
    
    Returns:
        Full URL like "https://img.animeschedule.net/production/assets/public/img/anime/jpg/default/gachiakuta-39ad997d70.jpg"
        Returns None if route is invalid.
    """
    if not image_version_route or not isinstance(image_version_route, str):
        return None
    
    # Remove leading slash if present
    route = image_version_route.lstrip('/')
    if not route:
        return None
    
    return f"https://img.animeschedule.net/production/assets/public/img/{route}"


def attach_image_url(item):
    """Add 'image' field to item dict if imageVersionRoute exists.
    
    Args:
        item: Dictionary that may contain 'imageVersionRoute'
    
    Returns:
        The same item with 'image' field added (modifies in place)
    """
    if not isinstance(item, dict):
        return item
    
    image_route = item.get('imageVersionRoute')
    if image_route:
        image_url = build_image_url(image_route)
        if image_url:
            item['image'] = image_url
    
    return item


def get_route(mal_id):
    params = {
        "mal-ids": mal_id
    }
    response = client.get(f"{base_url}/anime", params=params)
    if response:
        data = response.json()
        return data['anime'][0]['route']
    return ''


def get_dub_time(mal_id):
    show = database.get_show(mal_id)
    route = show['anime_schedule_route']
    if not route:
        route = get_route(mal_id)
        database.update_show(mal_id, show['kodi_meta'], route)
    response = client.get(f'https://animeschedule.net/anime/{route}')
    if response:
        soup = BeautifulSoup(response.text, 'html.parser')
        soup_all = soup.find_all('div', class_='release-time-wrapper')
        for soup in soup_all:
            if 'dub:' in soup.text.lower():
                dub_soup = soup
                dub_text = dub_soup.span.text
                date_time = dub_soup.time.get('datetime')

                if '-' in dub_text:
                    match = re.match(r'Episodes (\d+)-(\d+)', dub_text)
                    ep_begin = int(match.group(1))
                    ep_end = int(match.group(2))
                    for ep_number in range(ep_begin, ep_end):
                        add_to_list(ep_number, date_time)
                else:
                    match = re.match(r'Episode (\d+)', dub_text)
                    ep_number = int(match.group(1))
                    add_to_list(ep_number, date_time)
                return dub_list


def add_to_list(ep_number, date_time):
    dub_time = datetime.datetime.fromtimestamp(time.mktime(time.strptime(date_time[:16], '%Y-%m-%dT%H:%M')))
    dub_time = str(dub_time - datetime.timedelta(hours=5))[:16]
    dub_list.append({"season": 0, "episode": ep_number, "release_time": dub_time})


def _parse_iso(dt_str: str):
    """Parse ISO-8601 with optional offset like +02:00 or Z."""
    if not dt_str:
        return None
    try:
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"
        return datetime.datetime.fromisoformat(dt_str)
    except Exception:
        try:
            core = dt_str.split(".")[0]
            if core.endswith("Z"):
                core = core[:-1] + "+00:00"
            return datetime.datetime.fromisoformat(core)
        except Exception:
            return None


def _iso_week_year(dt_utc):
    iso = dt_utc.isocalendar()
    return iso[0], iso[1]


def _fetch_week(air, tz, year, week, token, timeout=20):
    url = f"{base_url}/timetables/{air}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Kodi-Otaku/1.0",
    }
    params = {"tz": tz}
    if year is not None and week is not None:
        params["year"] = year
        params["week"] = week
    resp = client.request(url, params=params, headers=headers, timeout=timeout)
    if not resp:
        return []
    data = json.loads(resp)
    return data if isinstance(data, list) else data.get("episodes", [])


def get_recently_aired_raw(
    exclude_donghua=False,
    tz=None,
    air="all",  # 'raw' | 'sub' | 'dub' | 'all'
    include_airing_now=True
):
    api_token = _get_api_token()
    if not api_token:
        return []
    
    air = (air or "all").lower()
    if air not in ("raw", "sub", "dub", "all"):
        air = "all"

    if tz is None:
        try:
            from tzlocal import get_localzone_name
            tz = get_localzone_name()
        except Exception:
            tz = "UTC"

    now_utc = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
    start_utc = now_utc - datetime.timedelta(days=6)  # today + previous 6 days

    this_monday_utc = (now_utc - datetime.timedelta(days=now_utc.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    prev_week_anchor = this_monday_utc - datetime.timedelta(days=1)
    y_cur, w_cur = _iso_week_year(now_utc)
    y_prev, w_prev = _iso_week_year(prev_week_anchor)

    episodes = []
    episodes += _fetch_week(air, tz, y_prev, w_prev, api_token)
    episodes += _fetch_week(air, tz, y_cur, w_cur, api_token)

    if not isinstance(episodes, list):
        return []

    ALLOWED_PREFIXES = ("tv", "ona", "ova", "special")
    kept = []

    for ep in episodes:
        ed = _parse_iso(ep.get("episodeDate", ""))
        if not ed:
            continue
        ed_utc = ed.astimezone(datetime.timezone.utc) if ed.tzinfo else ed.replace(tzinfo=datetime.timezone.utc)
        if not (start_utc <= ed_utc <= now_utc):
            continue

        mts = ep.get("mediaTypes") or []
        names = []
        for m in mts:
            if isinstance(m, dict):
                names.append((m.get("route") or m.get("name") or "").lower())
            else:
                names.append(str(m).lower())
        if not any(n.startswith(ALLOWED_PREFIXES) for n in names if isinstance(n, str)):
            continue

        if exclude_donghua and ep.get("donghua", False):
            continue

        st = (ep.get("airingStatus") or "").lower()
        if include_airing_now:
            if st not in ("aired", "airing"):
                continue
        else:
            if st != "aired":
                continue

        kept.append(ep)

    raw_index = {}
    for x in kept:
        if (x.get("airType") or "").lower() == "raw":
            route = x.get("route")
            ed = _parse_iso(x.get("episodeDate") or "")
            if not ed:
                continue
            local_dt = ed.astimezone() if ed.tzinfo else ed.replace(tzinfo=datetime.timezone.utc).astimezone()
            ld = local_dt.date().isoformat()
            raw_index[(route, ld)] = x

    normalized = []
    for x in kept:
        route = x.get("route")
        ed = _parse_iso(x.get("episodeDate") or "")
        if ed:
            local_dt = ed.astimezone() if ed.tzinfo else ed.replace(tzinfo=datetime.timezone.utc).astimezone()
            key = (route, local_dt.date().isoformat())
            raw_twin = raw_index.get(key)
            if raw_twin and isinstance(raw_twin.get("episodeNumber"), int):
                x["episodeNumber"] = raw_twin["episodeNumber"]
        normalized.append(x)

    normalized.sort(key=lambda x: (_parse_iso(x.get("episodeDate", "")) or datetime.datetime.min), reverse=True)
    return normalized


_MAL_RE = re.compile(r"/anime/(\d+)(?:/|$)")
_ANILIST_RE = re.compile(r"/anime/(\d+)(?:/|$)")

_AS_ANIME_CACHE = {}


def _parse_id_from_url(service, url):
    if not url:
        return None
    u = url.strip()
    if not u:
        return None
    if u.startswith("www."):
        u = "https://" + u
    elif u.startswith("myanimelist.net") or u.startswith("anilist.co"):
        u = "https://" + u
    try:
        if service == "mal":
            m = _MAL_RE.search(u)
            return int(m.group(1)) if m else None
        if service == "anilist":
            m = _ANILIST_RE.search(u)
            return int(m.group(1)) if m else None
    except Exception:
        return None
    return None


def _extract_ids_anywhere(anime):
    if not isinstance(anime, dict):
        return (None, None)

    try:
        if "malId" in anime:
            return (int(anime["malId"]), int(anime.get("anilistId")) if anime.get("anilistId") is not None else None)
    except Exception:
        pass

    ids_blob = anime.get("ids") or anime.get("externalIds") or {}
    if isinstance(ids_blob, dict):
        mal_id = ids_blob.get("mal") or ids_blob.get("myanimelist") or ids_blob.get("myAnimeList")
        ani_id = ids_blob.get("anilist") or ids_blob.get("aniList") or ids_blob.get("ani_list")
        try:
            mal_id = int(mal_id) if mal_id is not None else None
        except Exception:
            mal_id = None
        try:
            ani_id = int(ani_id) if ani_id is not None else None
        except Exception:
            ani_id = None
        if mal_id or ani_id:
            return (mal_id, ani_id)

    websites_obj = anime.get("websites")
    if isinstance(websites_obj, dict):
        mal_url = websites_obj.get("mal") or websites_obj.get("myanimelist")
        ani_url = websites_obj.get("aniList") or websites_obj.get("anilist")
        mal_id = _parse_id_from_url("mal", mal_url) if mal_url else None
        ani_id = _parse_id_from_url("anilist", ani_url) if ani_url else None
        if mal_id or ani_id:
            return (mal_id, ani_id)
        streams = websites_obj.get("streams")
        if isinstance(streams, list):
            for s in streams:
                if not isinstance(s, dict):
                    continue
                mid = _parse_id_from_url("mal", s.get("url"))
                aid = _parse_id_from_url("anilist", s.get("url"))
                if mid or aid:
                    return (mid, aid)

    websites_list = anime.get("websites")
    if isinstance(websites_list, list):
        mal_id = None
        ani_id = None
        for w in websites_list:
            if not isinstance(w, dict):
                continue
            name = (w.get("name") or "").lower()
            url = w.get("url") or ""
            if mal_id is None and ("myanimelist" in name or "myanimelist.net" in url):
                mal_id = _parse_id_from_url("mal", url)
            if ani_id is None and ("anilist" in name or "anilist.co" in url):
                ani_id = _parse_id_from_url("anilist", url)
        if mal_id or ani_id:
            return (mal_id, ani_id)

    sources = anime.get("sources") or []
    if isinstance(sources, list):
        mal_id = None
        ani_id = None
        for s in sources:
            if not isinstance(s, dict):
                continue
            name = (s.get("name") or s.get("site") or "").lower()
            sid = s.get("id") or s.get("value") or s.get("externalId")
            try:
                sid_num = int(str(sid))
            except Exception:
                sid_num = None
            if not sid_num:
                continue
            if "myanimelist" in name or name == "mal":
                mal_id = mal_id or sid_num
            if "anilist" in name:
                ani_id = ani_id or sid_num
        if mal_id or ani_id:
            return (mal_id, ani_id)

    return (None, None)

def as_get_anime_by_route(route, timeout=10):
    if not route:
        return None
    if route in _AS_ANIME_CACHE:
        return _AS_ANIME_CACHE[route]
    
    api_token = _get_api_token()
    if not api_token:
        _AS_ANIME_CACHE[route] = {}
        return None

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Accept": "application/json",
        "User-Agent": "Kodi-Otaku/1.0",
    }

    url_primary = f"{base_url}/anime/{route}"
    try:
        resp = client.request(url_primary, headers=headers, timeout=timeout)
        if resp:
            anime = json.loads(resp) if isinstance(resp, str) else resp
            if isinstance(anime, dict):
                mal_id, ani_id = _extract_ids_anywhere(anime)
                if mal_id is not None:
                    anime["malId"] = mal_id
                if ani_id is not None:
                    anime["anilistId"] = ani_id
                _AS_ANIME_CACHE[route] = anime
                return anime
    except Exception:
        pass

    url_fallback = f"{base_url}/anime"
    params = {"routes": route}
    try:
        resp = client.request(url_fallback, params=params, headers=headers, timeout=timeout)
        if resp:
            data = json.loads(resp) if isinstance(resp, str) else resp
            arr = data.get("anime") if isinstance(data, dict) else None
            if isinstance(arr, list) and arr:
                anime = arr[0]
                if isinstance(anime, dict):
                    mal_id, ani_id = _extract_ids_anywhere(anime)
                    if mal_id is not None:
                        anime["malId"] = mal_id
                    if ani_id is not None:
                        anime["anilistId"] = ani_id
                    _AS_ANIME_CACHE[route] = anime
                    return anime
    except Exception:
        pass

    _AS_ANIME_CACHE[route] = {}
    return None


def as_get_anime_by_routes_batch(routes, timeout_per=8, max_workers=8):
    from concurrent.futures import ThreadPoolExecutor, as_completed
    out = {}
    to_fetch = []

    for r in routes:
        if not r:
            continue
        if r in _AS_ANIME_CACHE:
            cached = _AS_ANIME_CACHE[r]
            if cached:
                out[r] = cached
        else:
            to_fetch.append(r)

    if not to_fetch:
        return out

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(as_get_anime_by_route, r, timeout_per): r for r in to_fetch}
        for f in as_completed(futs):
            r = futs[f]
            try:
                res = f.result()
                if isinstance(res, dict) and res:
                    out[r] = res
            except Exception:
                pass

    return out


def get_airing_calendar(
    exclude_donghua=False,
    tz=None,
    air="all",  # 'raw' | 'sub' | 'dub' | 'all'
):
    """
    Fetch weekly airing calendar (7-day window: yesterday to +6 days from today).
    Returns episodes sorted by air date descending (newest first).
    """
    api_token = _get_api_token()
    if not api_token:
        control.log("[AnimeSched Calendar] No API token - returning empty", "warning")
        return []
    
    air = (air or "all").lower()
    if air not in ("raw", "sub", "dub", "all"):
        air = "all"

    if tz is None:
        try:
            from tzlocal import get_localzone_name
            tz = get_localzone_name()
        except Exception:
            tz = "UTC"

    now_utc = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
    start_utc = now_utc - datetime.timedelta(days=1)  # yesterday
    end_utc = now_utc + datetime.timedelta(days=6)    # +6 days from today

    # Determine which weeks to fetch
    this_monday_utc = (now_utc - datetime.timedelta(days=now_utc.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    next_monday_utc = this_monday_utc + datetime.timedelta(days=7)
    
    y_cur, w_cur = _iso_week_year(now_utc)
    y_next, w_next = _iso_week_year(next_monday_utc)

    episodes = []
    episodes += _fetch_week(air, tz, y_cur, w_cur, api_token)
    if (y_next, w_next) != (y_cur, w_cur):
        episodes += _fetch_week(air, tz, y_next, w_next, api_token)

    if not isinstance(episodes, list):
        return []

    ALLOWED_PREFIXES = ("tv", "ona")
    kept = []

    for ep in episodes:
        ed = _parse_iso(ep.get("episodeDate", ""))
        if not ed:
            continue
        ed_utc = ed.astimezone(datetime.timezone.utc) if ed.tzinfo else ed.replace(tzinfo=datetime.timezone.utc)
        if not (start_utc <= ed_utc <= end_utc):
            continue

        mts = ep.get("mediaTypes") or []
        names = []
        for m in mts:
            if isinstance(m, dict):
                names.append((m.get("route") or m.get("name") or "").lower())
            else:
                names.append(str(m).lower())
        if not any(n.startswith(ALLOWED_PREFIXES) for n in names if isinstance(n, str)):
            continue

        if exclude_donghua and ep.get("donghua", False):
            continue

        kept.append(ep)

    # Sort by episode date descending (newest first)
    kept.sort(key=lambda x: (_parse_iso(x.get("episodeDate", "")) or datetime.datetime.min), reverse=True)
    return kept


def as_format_episode_badge(ep):
    n = ep.get("episodeNumber", 1)
    ed = ep.get("episodeDate") or ""
    dt = _parse_iso(ed)
    if not dt:
        return f"Ep {n}"
    if dt.tzinfo:
        local_dt = dt.astimezone()
    else:
        local_dt = dt.replace(tzinfo=datetime.timezone.utc).astimezone()
    when = local_dt.strftime("%m/%d/%Y %I:%M %p")
    return f"Ep {n} ({when})"