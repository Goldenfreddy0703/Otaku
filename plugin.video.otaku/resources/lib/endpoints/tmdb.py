from resources.lib.ui import client, database, control

api_info = database.get_info('TMDB')
apiKey = api_info['api_key']
baseUrl = "https://api.themoviedb.org/3/"
thumbPath = "https://image.tmdb.org/t/p/w500"
backgroundPath = "https://image.tmdb.org/t/p/original"


def getArt(meta_ids, mtype, limit=None):
    art = {}
    mid = meta_ids.get('themoviedb_id')
    if mid is None:
        tvdb = meta_ids.get('thetvdb_id')
        if tvdb:
            params = {
                'external_source': 'tvdb_id',
                "api_key": apiKey
            }
            response = client.get(f'{baseUrl}find/{tvdb}', params=params)
            res = response.json() if response else {}
            res = res.get('tv_results')
            if res:
                mid = res[0].get('id')

    if mid:
        params = {
            'include_image_language': 'en,ja,null',
            "api_key": apiKey
        }
        response = client.get(f'{baseUrl}{mtype[0:5]}/{mid}/images', params=params)
        res = response.json() if response else {}

        if res:
            # Backdrops are for fanart (wide 16:9 background images)
            if res.get('backdrops'):
                backdrops = res['backdrops'][:limit] if limit else res['backdrops']
                items = [backgroundPath + item['file_path'] for item in backdrops if item.get('file_path')]
                art['fanart'] = items

            # Posters are for thumbnails (portrait images)
            if res.get('posters'):
                posters = res['posters'][:limit] if limit else res['posters']
                items = [thumbPath + item['file_path'] for item in posters if item.get('file_path')]
                art['thumb'] = items

            # Logos are clearlogos (transparent PNG title/logo images)
            if res.get('logos'):
                logos = res['logos'][:limit] if limit else res['logos']
                items = [backgroundPath + item["file_path"] for item in logos if item.get('file_path')]
                art['clearlogo'] = items
    return art


def get_episode_titles(tmdb_id, season_number, episode_number):
    params = {
        'include_image_language': 'en,ja,null',
        "api_key": apiKey
    }
    response = client.get(f'{baseUrl}tv/{tmdb_id}/season/{season_number}/episode/{episode_number}/translations', params=params)
    res = response.json() if response else {}

    # Extract English name, fallback to Japanese if not found
    translations = res.get('translations', [])
    for t in translations:
        if t.get('iso_639_1') == 'en':
            data = t.get('data', {})
            name = data.get('name')
            if name:
                return [name]
    for t in translations:
        if t.get('iso_639_1') == 'ja':
            data = t.get('data', {})
            name = data.get('name')
            if name:
                return [name]
    return []


def _resolve_tmdb_id(meta_ids):
    if not isinstance(meta_ids, dict):
        return None

    mid = meta_ids.get('themoviedb_id') or meta_ids.get('tmdb')
    if mid:
        return mid

    tvdb = meta_ids.get('thetvdb_id') or meta_ids.get('tvdb')
    if not tvdb:
        return None

    params = {
        'external_source': 'tvdb_id',
        "api_key": apiKey
    }
    response = client.get(f'{baseUrl}find/{tvdb}', params=params)
    res = response.json() if response else {}
    tv_results = res.get('tv_results') or []
    if tv_results:
        return tv_results[0].get('id')
    return None


def _get_preferred_languages():
    langs = []
    try:
        import xbmc
        lang = xbmc.getLanguage(xbmc.ISO_639_1, region=True)
        if lang:
            lang = lang.replace('_', '-')
            parts = [x for x in lang.split('-') if x]
            if len(parts) >= 2:
                langs.append(f"{parts[0].lower()}-{parts[1].upper()}")
            elif len(parts) == 1:
                langs.append(parts[0].lower())
    except Exception:
        pass

    langs.extend(['it-IT', 'en-US', 'ja-JP'])

    seen = set()
    result = []
    for lang in langs:
        if lang not in seen:
            seen.add(lang)
            result.append(lang)
    return result


def _select_translation(translations, preferred_languages):
    if not translations:
        return {}

    def _match(lang_code, country_code=None):
        if country_code:
            for tr in translations:
                if tr.get('iso_639_1') == lang_code and tr.get('iso_3166_1') == country_code:
                    return tr.get('data') or {}
        for tr in translations:
            if tr.get('iso_639_1') == lang_code:
                return tr.get('data') or {}
        return {}

    for language in preferred_languages:
        normalized = language.replace('_', '-')
        parts = [x for x in normalized.split('-') if x]
        lang_code = parts[0].lower() if parts else ''
        country_code = parts[1].upper() if len(parts) > 1 else None
        if not lang_code:
            continue
        data = _match(lang_code, country_code)
        if data.get('name') or data.get('overview'):
            return data
    return {}


def get_episode_localized_meta(meta_ids, season_number, episode_number, preferred_languages=None):
    """
    Return localized episode metadata from TMDB translations.
    """
    tmdb_id = _resolve_tmdb_id(meta_ids)
    if not tmdb_id or season_number is None or episode_number is None:
        return {}

    languages = preferred_languages or _get_preferred_languages()

    # First try direct localized episode endpoint (often more complete than /translations)
    for lang in languages:
        params = {
            "api_key": apiKey,
            "language": lang
        }
        response = client.get(
            f'{baseUrl}tv/{tmdb_id}/season/{season_number}/episode/{episode_number}',
            params=params
        )
        data = {}
        if response and response.content:
            try:
                data = response.json()
            except Exception:
                data = {}
        elif response and response.text:
            try:
                data = response.json()
            except Exception:
                data = {}

        title = data.get('name')
        plot = data.get('overview')
        if title or plot:
            return {'title': title, 'plot': plot}

    # Fallback to translations endpoint
    params = {"api_key": apiKey}
    response = client.get(
        f'{baseUrl}tv/{tmdb_id}/season/{season_number}/episode/{episode_number}/translations',
        params=params
    )
    res = response.json() if response else {}
    translations = res.get('translations', [])
    data = _select_translation(translations, languages)
    if data:
        return {
            'title': data.get('name'),
            'plot': data.get('overview')
        }
    return {}


def get_show_localized_meta(meta_ids, preferred_languages=None):
    """
    Return localized show metadata (title/plot) from TMDB.
    """
    tmdb_id = _resolve_tmdb_id(meta_ids)
    if not tmdb_id:
        return {}

    languages = preferred_languages or _get_preferred_languages()
    for lang in languages:
        params = {
            "api_key": apiKey,
            "language": lang
        }
        response = client.get(f'{baseUrl}tv/{tmdb_id}', params=params)
        data = response.json() if response else {}
        title = data.get('name')
        plot = data.get('overview')
        if title or plot:
            return {'title': title, 'plot': plot}
    return {}
