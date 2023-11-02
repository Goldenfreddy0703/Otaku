import json

from resources.lib.ui import client


def get_tmdb_to_anilist_id_tv(tmdb_id, seasonnum):
    # Convert Tmdb ID to Anilist ID

    url = 'https://tmdb2anilist.slidemovies.org/tv/?id=%s&s=%s' % (tmdb_id, seasonnum)
    r = client.request(url)
    if r:
        r = json.loads(r)
    return r


def get_tmdb_to_anilist_id_movie(tmdb_id):
    # Convert Tmdb ID to Anilist ID

    url = 'https://tmdb2anilist.slidemovies.org/movie/?id=%s' % (tmdb_id)
    params = {
        'tmdb_id': 0,
        'anilist_id': 0,
        'mal_id': 0
    }

    r = client.request(url, params=params)
    if r:
        r = json.loads(r)
    return r