import json
from six.moves import urllib_parse
from resources.lib.ui import client, database
import requests


class ANIFYAPI:
    def __init__(self):
        self.baseUrl = 'https://api.anify.tv/'
        self.apikey = '\x65\x65\x36\x65\x61\x38\x32\x32\x36\x30\x36\x64\x32\x61\x64\x30\x35\x39\x64\x38\x38\x35\x64\x38\x61\x38\x34\x37\x62\x33\x37\x36'
        self.episodesUrl = '/episodes/{id}'
        self.streamUrl = '/sources'

    def _json_request(self, url, params={}):
        if url.startswith('/'):
            url = urllib_parse.urljoin(self.baseUrl, url)
        if not params:
            params = {'apikey': self.apikey}
        elif 'apikey' not in params.keys():
            params.update({'apikey': self.apikey})

        response = requests.get(url)
        print(response)
        
        data = {}
        data = response.json()
        return data

    def _parse_episode_view(self, res, show_id, show_meta, season, poster, fanart, eps_watched, update_time, title_disable):
        return

    def _process_episode_view(self, anilist_id, show_meta, poster, fanart, eps_watched, title_disable=False):
        return

    @staticmethod
    def _parse_episodes(res, show_id, eps_watched, title_disable=False):
        return

    def process_episodes(self, anilist_id, episodes, eps_watched, title_disable=False):
        return

    def get_anilist_meta(self, anilist_id):
        return

    def get_episodes(self, anilist_id, filter_lang):
        return

    def get_sources(self, anilist_id, episode, provider, lang=''):
        sources = []
        episodes = []
        if provider not in ['gogoanime', '9anime', 'animepahe']:
            return sources

        eurl = self.episodesUrl.format(id=anilist_id)
        res = self._json_request(eurl)
        for r in res:
            if r.get('providerId') == provider:
                episodes = r.get('episodes')
                break

        if episodes:
            episodes = sorted(episodes, key=lambda x: x.get('number'))
            if episodes[0].get('number') != 1:
                episode = episodes[0].get('number') - 1 + int(episode)
            eid = [(x.get('id'), x.get('hasDub')) for x in episodes if x.get('number') == int(episode)][0]
            if (lang == 'dub' and eid[1]) or lang == 'sub':
                params = {
                    'providerId': provider,
                    'watchId': eid[0],
                    'episodeNumber': episode,
                    'id': anilist_id,
                    'subType': lang
                }
                sources = self._json_request(self.streamUrl, params)

        return sources
    
    def get_anilist_id_movie(self, provider_id, media_id):
        url = f"/media?providerId={provider_id}&id=/movie/{media_id}"
        params = {'fields': ['mappings']}
        response_data = self._json_request(url, params)

        anilist_id = None
        for mapping in response_data.get('mappings', []):
            if mapping['providerType'] == 'META' and mapping['providerId'] == 'anilist':
                anilist_id = mapping['id']
                break
        return anilist_id  # Return None if no match is found
    
    def get_anilist_id_tv(self, provider_id, media_id):
        url = f"/media?providerId={provider_id}&id=/tv/{media_id}"
        params = {'fields': ['mappings']}
        response_data = self._json_request(url, params)

        anilist_id = None
        for mapping in response_data.get('mappings', []):
            if mapping['providerType'] == 'META' and mapping['providerId'] == 'anilist':
                anilist_id = mapping['id']
                break
        return anilist_id
