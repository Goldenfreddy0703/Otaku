import time

from resources.lib.ui import client, control, database

api_info = database.get_info('TVDB')
api_key = api_info.get('api_key') if api_info else None
baseUrl = "https://api4.thetvdb.com/v4"
lang = ['eng', 'jpn']
language = ["jpn", 'eng'][control.getInt("titlelanguage")]
_AUTH_TOKEN = None
_AUTH_TOKEN_TIME = 0
_AUTH_TOKEN_TTL = 3600


def get_auth_token():
    """Get authentication token for TVDB API v4"""
    global _AUTH_TOKEN, _AUTH_TOKEN_TIME

    now = int(time.time())
    if _AUTH_TOKEN and (now - _AUTH_TOKEN_TIME) < _AUTH_TOKEN_TTL:
        return _AUTH_TOKEN

    if not api_key:
        return None

    headers = {'Content-Type': 'application/json'}
    data = {'apikey': api_key}
    response = client.post(f'{baseUrl}/login', json_data=data, headers=headers)

    if response:
        res = response.json()
        token = res.get('data', {}).get('token')
        if token:
            _AUTH_TOKEN = token
            _AUTH_TOKEN_TIME = now
            return token
    return None


def getArt(meta_ids, mtype, limit=None):
    """Get artwork from TVDB API v4"""
    art = {}
    tvdb_id = meta_ids.get('thetvdb_id')

    if not tvdb_id:
        return art

    # Get authentication token
    token = get_auth_token()
    if not token:
        control.log("TVDB: Failed to authenticate")
        return art

    headers = {'Authorization': f'Bearer {token}'}

    # TVDB v4 - use dedicated artworks endpoint
    if mtype == 'movies':
        response = client.get(f'{baseUrl}/movies/{tvdb_id}/artworks', headers=headers)
    else:
        response = client.get(f'{baseUrl}/series/{tvdb_id}/artworks', headers=headers)

    if not response:
        return art

    res = response.json()
    data = res.get('data', {})

    if not data:
        return art

    # Process artworks - check for 'artworks' key or if data itself is a list
    artworks = data.get('artworks', []) if isinstance(data, dict) else data if isinstance(data, list) else []

    if artworks:
        fanart_images = []
        thumb_images = []
        clearart_images = []
        clearlogo_images = []

        for artwork in artworks:
            artwork_type = artwork.get('type')
            image_url = artwork.get('image')
            artwork_lang = artwork.get('language')

            if not image_url:
                continue

            # Prepend base URL if needed
            if not image_url.startswith('http'):
                image_url = f'https://artworks.thetvdb.com{image_url}'

            # TVDB Artwork Type IDs (from /artwork/types endpoint):
            # Series: 2=Poster, 3=Background, 22=ClearArt, 23=ClearLogo
            # Movie: 14=Poster, 15=Background, 24=ClearArt, 25=ClearLogo

            # Fanart/Background
            if artwork_type in [3, 15]:  # 3=Series Background, 15=Movie Background
                if artwork_lang in lang or not artwork_lang:
                    if limit is None or len(fanart_images) < limit:
                        fanart_images.append(image_url)

            # Posters
            elif artwork_type in [2, 14]:  # 2=Series Poster, 14=Movie Poster
                if artwork_lang in lang or not artwork_lang:
                    if limit is None or len(thumb_images) < limit:
                        thumb_images.append(image_url)

            # Clear Art
            elif artwork_type in [22, 24]:  # 22=Series ClearArt, 24=Movie ClearArt
                if artwork_lang in lang or not artwork_lang:
                    if limit is None or len(clearart_images) < limit:
                        clearart_images.append(image_url)

            # Clear Logo
            elif artwork_type in [23, 25]:  # 23=Series ClearLogo, 25=Movie ClearLogo
                clearlogo_images.append({
                    'url': image_url,
                    'lang': artwork_lang
                })

        # Add to art dict
        if fanart_images:
            art['fanart'] = fanart_images
        if thumb_images:
            art['thumb'] = thumb_images
        if clearart_images:
            art['clearart'] = clearart_images

        # Process clearlogo with language preference
        if clearlogo_images:
            logos = []
            # Try to get logo in preferred language
            try:
                logos.append(next(x['url'] for x in clearlogo_images if x['lang'] == language))
            except StopIteration:
                pass

            # If no preferred language logo, try any language in our list
            if not logos:
                try:
                    logos.append(next(x['url'] for x in clearlogo_images if x['lang'] in lang))
                except StopIteration:
                    pass

            # If still no logo, take first available
            if not logos and clearlogo_images:
                try:
                    logos.append(clearlogo_images[0]['url'])
                except (IndexError, KeyError):
                    pass

            if logos:
                art['clearlogo'] = logos

    return art


def _map_tvdb_langs():
    langs = []
    try:
        import xbmc
        lang_code = xbmc.getLanguage(xbmc.ISO_639_1, region=True)
        if lang_code:
            iso = lang_code.split('_')[0].lower()
            langs.append({'it': 'ita', 'en': 'eng', 'ja': 'jpn'}.get(iso, iso))
    except Exception:
        pass

    langs.extend(['ita', 'eng', 'jpn'])
    seen = set()
    result = []
    for l in langs:
        if l and l not in seen:
            seen.add(l)
            result.append(l)
    return result


def _tvdb_headers():
    token = get_auth_token()
    if not token:
        return None
    return {'Authorization': f'Bearer {token}'}


def _get_tvdb_id(meta_ids):
    if not isinstance(meta_ids, dict):
        return None
    return meta_ids.get('thetvdb_id') or meta_ids.get('tvdb')


def _get_season_id(headers, tvdb_id, season_number):
    response = client.get(f'{baseUrl}/series/{tvdb_id}/extended', headers=headers)
    data = response.json() if response else {}
    seasons = data.get('data', {}).get('seasons') or []
    for season in seasons:
        s_num = season.get('number')
        s_type = season.get('type') or {}
        s_type_name = (s_type.get('name') or s_type.get('type') or '').lower()
        if int(s_num or -1) == int(season_number) and 'aired' in s_type_name:
            return season.get('id')
    for season in seasons:
        if int(season.get('number') or -1) == int(season_number):
            return season.get('id')
    return None


def _get_episode_id(headers, season_id, episode_number):
    response = client.get(f'{baseUrl}/seasons/{season_id}/extended', headers=headers)
    data = response.json() if response else {}
    episodes = data.get('data', {}).get('episodes') or []
    for ep in episodes:
        if int(ep.get('number') or -1) == int(episode_number):
            return ep.get('id')
    return None


def get_episode_localized_meta(meta_ids, season_number, episode_number, preferred_languages=None):
    """
    Return localized episode metadata from TVDB translations.
    """
    tvdb_id = _get_tvdb_id(meta_ids)
    if not tvdb_id or season_number is None or episode_number is None:
        return {}

    headers = _tvdb_headers()
    if not headers:
        return {}

    season_id = _get_season_id(headers, tvdb_id, season_number)
    if not season_id:
        return {}

    episode_id = _get_episode_id(headers, season_id, episode_number)
    if not episode_id:
        return {}

    langs = preferred_languages or _map_tvdb_langs()
    for lang_code in langs:
        response = client.get(f'{baseUrl}/episodes/{episode_id}/translations/{lang_code}', headers=headers)
        data = response.json() if response else {}

        ep_data = data.get('data') or {}
        title = ep_data.get('name')
        plot = ep_data.get('overview')
        if title or plot:
            return {'title': title, 'plot': plot}
    return {}


def get_show_localized_meta(meta_ids, preferred_languages=None):
    """
    Return localized show metadata (title/plot) from TVDB translations.
    """
    tvdb_id = _get_tvdb_id(meta_ids)
    if not tvdb_id:
        return {}

    headers = _tvdb_headers()
    if not headers:
        return {}

    langs = preferred_languages or _map_tvdb_langs()
    for lang_code in langs:
        response = client.get(f'{baseUrl}/series/{tvdb_id}/translations/{lang_code}', headers=headers)
        data = response.json() if response else {}
        show_data = data.get('data') or {}
        title = show_data.get('name')
        plot = show_data.get('overview')
        if title or plot:
            return {'title': title, 'plot': plot}
    return {}
