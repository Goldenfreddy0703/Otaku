import json
from resources.lib.ui import control, client, source_utils

class Torbox:
    def __init__(self):
        self.apikey = control.getSetting('tb.apikey')
        self.headers = {
            'Authorization': 'Bearer {}'.format(self.apikey)
        }
        
    def get_url(self, url):
        if self.headers['Authorization'] == 'Bearer ':
            return None
        url = 'https://api.torbox.app/v1/api{}'.format(url)
        req = client.request(url, timeout=10, headers=self.headers, error=True, method='GET')
        return json.loads(req)
    
    def post_url(self, url, data, jpost = False):
        if self.headers['Authorization'] == 'Bearer ':
            return None
        url = 'https://api.torbox.app/v1/api{}'.format(url)
        req = client.request(url, headers=self.headers, post=data, error=True, method='POST', jpost=jpost)
        return json.loads(req)

    
    def hash_check(self, hashList):
        url = '/torrents/checkcached?format=list{}'
        hashes = ','.join(hashList)
        response = self.get_url(url.format('&hash=' + hashes))
        response['data'] = list(map(lambda x: x['hash'], response['data']))
        return response
    
    def add_magnet(self, magnet):
        url = '/torrents/createtorrent'
        response = self.post_url(url, { 'magnet': magnet })
        return response['data']
    
    def remove_torrent(self, torrentId):
        url = '/torrents/controltorrent'
        data = {
            'torrent_id': str(torrentId),
            'operation': 'delete'
        }
        response = self.post_url(url, data, True)
        return response
    
    def list_torrents(self):
        url = '/torrents/mylist'
        response = self.get_url(url)
        return response['data']
    
    def get_torrent_info(self, torrentId):
        url = '/torrents/mylist?id={}'.format(torrentId)
        response = self.get_url(url)
        return response['data']

    def request_dl_link(self, torrentId, fileId=-1):
        url = '/torrents/requestdl?token={token}&torrent_id={torrentId}'.format(
            token = self.apikey, torrentId = torrentId
        )

        if fileId >= 0:
            url = url + '&file_id=' + str(fileId)

        response = self.get_url(url)
        return response['data']

    def resolve_single_magnet(self, hash_, magnet, episode='', pack_select=False):
        torrent = self.add_magnet(magnet)
        torrentId = torrent['torrent_id']
        info = self.get_torrent_info(torrentId)
        folder_details = info['files']
        folder_details = [{ 'fileId': x['id'], 'path': x['name'] } for x in folder_details]
        
        if episode or pack_select:
            selected_file = source_utils.get_best_match('path', folder_details, episode, pack_select)
            if selected_file and selected_file['fileId'] is not None:
                stream_link = self.request_dl_link(torrentId, selected_file['fileId'])
                self.remove_torrent(torrentId)
                return stream_link
            
        selected_file = folder_details[0]
        if selected_file is None:
            return
        
        stream_link = self.request_dl_link(torrentId, selected_file['fileId'])
        self.remove_torrent(torrentId)
        return stream_link
