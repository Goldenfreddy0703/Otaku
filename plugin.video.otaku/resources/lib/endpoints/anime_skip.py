from resources.lib.ui import client, database

api_info = database.get_info('Anime-Skip') or {}
client_id = api_info.get('client_id', '')
base_url = "https://api.anime-skip.com/graphql"

headers = {
    "X-Client-ID": client_id
}


def get_episode_ids(anilist_id, episode):
    query = '''
    query($service: ExternalService!, $serviceId: String!) {
        findShowsByExternalId(service: $service, serviceId: $serviceId) {
            episodes {
                id
                number
            }
        }
    }
'''
    variables = {
        'service': 'ANILIST',
        'serviceId': anilist_id
    }

    response = client.post(base_url, headers=headers, json_data={'query': query, 'variables': variables})
    if response and response.ok:
        try:
            data = response.json()
            res = data.get('data', {}).get('findShowsByExternalId', [])
            id_list = []
            for resx in res:
                for x in resx.get('episodes', []):
                    if x.get('number') and int(x['number']) == episode:
                        id_list.append(x['id'])
            return id_list
        except (ValueError, KeyError, TypeError) as e:
            from resources.lib.ui import control
            control.log(f'Anime-Skip API error: {str(e)}', 'error')
    return []


def get_time_stamps(id_list):
    query = '''
        query($episodeId: ID!) {
            findTimestampsByEpisodeId(episodeId: $episodeId) {
                at
                type {
                    name
                }
            }
        }
    '''

    variables = {}
    for x in range(len(id_list)):
        variables['episodeId'] = id_list[x]
        response = client.post(base_url, headers=headers, json_data={'query': query, 'variables': variables})
        if response and response.ok:
            try:
                data = response.json()
                res = data.get('data', {}).get('findTimestampsByEpisodeId', [])
                if res:
                    return res
            except (ValueError, KeyError, TypeError) as e:
                from resources.lib.ui import control
                control.log(f'Anime-Skip timestamp API error: {str(e)}', 'error')
                continue
    return []


def convert_time_stamps(time_stamp, intro, outro):
    if not time_stamp:
        return
    skip_times = {}
    for skip in time_stamp:
        skip_type = skip.get('type', {}).get('name')
        skip_at = skip.get('at')
        if not skip_type or skip_at is None:
            continue
        if intro:
            if skip_type in ['Intro', 'Branding', 'New Intro']:
                skip_times['intro'] = {'start': skip_at}
            elif skip_times.get('intro') and not skip_times['intro'].get('end') and skip_type == 'Canon':
                skip_times['intro']['end'] = skip_at
        if outro:
            if skip_type in ['Credits', 'Mixed Credits']:
                skip_times['outro'] = {'start': skip_at}
            elif skip_times.get('outro') and skip_type == 'Preview':
                skip_times['outro']['end'] = skip_at
    return skip_times
