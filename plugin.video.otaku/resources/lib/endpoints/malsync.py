from resources.lib.ui import client

baseUrl = 'https://api.malsync.moe'


def get_slugs(mal_id, site=''):
    slugs = []
    if site in ['Gogoanime', 'Zoro', 'animepahe']:
        response = client.get(f'{baseUrl}/mal/anime/{mal_id}')
        if response:
            resp = response.json().get('Sites', {}).get(site)
            if resp:
                for key in resp.keys():
                    slugs.append(resp[key].get('url'))
    return slugs


def get_title(mal_id, site=''):
    if site in ['Gogoanime', 'Zoro', 'animepahe']:
        response = client.get(f'{baseUrl}/mal/anime/{mal_id}')
        if response:
            resp = response.json().get('Sites', {}).get(site)
            if resp:
                for key in resp.keys():
                    title = resp[key].get('title')
                    if title:
                        return title
    return None
