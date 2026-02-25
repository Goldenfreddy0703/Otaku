from resources.lib.ui import client, database

api_info = database.get_info('TMDB') or {}
apiKey = api_info.get('api_key', '')
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
            try:
                res = response.json() if response else {}
            except (ValueError, AttributeError):
                res = {}
            res = res.get('tv_results')
            if res:
                mid = res[0].get('id')

    if mid:
        params = {
            'include_image_language': 'en,ja,null',
            "api_key": apiKey
        }
        response = client.get(f'{baseUrl}{mtype[0:5]}/{mid}/images', params=params)
        try:
            res = response.json() if response else {}
        except (ValueError, AttributeError):
            res = {}

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


def searchByTitle(title, mtype):
    """Search TMDB by title and return the discovered TMDB ID, or None."""
    if not title:
        return None
    search_type = 'movie' if mtype == 'movies' else 'tv'
    params = {
        'query': title,
        'api_key': apiKey
    }
    try:
        response = client.get(f'{baseUrl}search/{search_type}', params=params)
        res = response.json() if response else {}
        results = res.get('results', [])
        if results:
            return results[0].get('id')
    except Exception:
        pass
    return None


def get_episode_titles(tmdb_id, season_number, episode_number):
    params = {
        'include_image_language': 'en,ja,null',
        "api_key": apiKey
    }
    response = client.get(f'{baseUrl}tv/{tmdb_id}/season/{season_number}/episode/{episode_number}/translations', params=params)
    try:
        res = response.json() if response else {}
    except (ValueError, AttributeError):
        res = {}

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
