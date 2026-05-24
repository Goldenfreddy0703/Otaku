from resources.lib.ui import client

baseUrl = 'https://api.malsync.moe'

_SITE_KEYS = frozenset(['Gogoanime', 'Zoro', 'animepahe'])


def fetch_mal_anime(mal_id):
    """Single MAL Sync API fetch. Returns decoded JSON or None."""
    response = client.get(f'{baseUrl}/mal/anime/{mal_id}')
    if not response or not response.ok:
        return None
    try:
        return response.json()
    except (ValueError, TypeError):
        return None


def get_slugs(mal_id, site='', mal_data=None):
    slugs = []
    if site in _SITE_KEYS:
        data = mal_data if mal_data is not None else fetch_mal_anime(mal_id)
        if not data:
            return slugs
        resp = data.get('Sites', {}).get(site)
        if resp:
            for key in resp.keys():
                slugs.append(resp[key].get('url'))
    return slugs


def get_title(mal_id, site='', mal_data=None):
    if site in _SITE_KEYS:
        data = mal_data if mal_data is not None else fetch_mal_anime(mal_id)
        if not data:
            return None
        resp = data.get('Sites', {}).get(site)
        if resp:
            for key in resp.keys():
                title = resp[key].get('title')
                if title:
                    return title
    return None


def get_label_title(mal_id, site='animepahe', mal_data=None):
    """
    Label for UI / release_title: prefer site-specific title if present,
    else MAL Sync root title (same JSON as Sites). No extra HTTP when mal_data is passed.
    """
    data = mal_data if mal_data is not None else fetch_mal_anime(mal_id)
    if not data:
        return None
    if site in _SITE_KEYS:
        site_entries = data.get('Sites', {}).get(site) or {}
        for key in site_entries.keys():
            t = site_entries[key].get('title')
            if t:
                return t
    return data.get('title')
