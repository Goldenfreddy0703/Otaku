from resources.lib.ui import client, control, database
import xml.etree.ElementTree as ET

api_info = database.get_info('AniDB')
client_name = api_info['client_id']
base_url = 'http://api.anidb.net:9001/httpapi'

params = {
    'request': 'anime',
    'client': client_name,
    'clientver': 1,
    'protover': 1
}


def get_episode_meta(anidb_id):
    params['aid'] = anidb_id
    r = client.get(base_url, params=params)
    episode_meta = {}
    if r:
        root = control.safe_call(ET.fromstring, r.text, log_msg='AniDB XML parse error')
        if not root:
            return episode_meta
        # namespaces = {'xml': 'http://www.w3.org/XML/1998/namespace'}
        for episode in root.findall('.//episode'):
            episode_num = episode.find('epno').text
            anidb_id = episode.get('id')
            # en_title = episode.find("title[@xml:lang='en']", namespaces).text if episode.find("title[@xml:lang='en']", namespaces) is not None else None
            # xjat_title = episode.find("title[@xml:lang='x-jat']", namespaces).text if episode.find("title[@xml:lang='x-jat']", namespaces) is not None else None
            # airdate = episode.find('airdate').text if episode.find('airdate') is not None else None
            # length = episode.find('length').text if episode.find('length') is not None else None
            # votes = episode.find('rating').get('votes') if episode.find('rating') is not None else None
            # rating = episode.find('rating').text if episode.find('rating') is not None else None
            # summary = episode.find('summary').text if episode.find('summary') is not None else None

            episode_meta[episode_num] = {
                'anidb_id': anidb_id
                # 'en_title': en_title,
                # 'xjat_title': xjat_title,
                # 'airdate': airdate,
                # 'length': length,
                # 'votes': votes,
                # 'rating': rating,
                # 'summary': summary
            }

    return episode_meta
