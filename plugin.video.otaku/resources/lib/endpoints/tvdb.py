from resources.lib.ui import client, control, database

api_info = database.get_info('TVDB')
api_key = api_info.get('api_key') if api_info else None
baseUrl = "https://api4.thetvdb.com/v4"
lang = ['eng', 'jpn']
language = ["jpn", 'eng'][control.getInt("titlelanguage")]


def get_auth_token():
    """Get authentication token for TVDB API v4"""
    if not api_key:
        return None

    headers = {'Content-Type': 'application/json'}
    data = {'apikey': api_key}
    response = client.post(f'{baseUrl}/login', json_data=data, headers=headers)

    if response:
        res = response.json()
        return res.get('data', {}).get('token')
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
