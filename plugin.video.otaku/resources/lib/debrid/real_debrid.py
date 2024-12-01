import json
import time
from resources.lib.ui import source_utils
from resources.lib.ui import control, client


class RealDebrid:
    def __init__(self):
        self.ClientID = control.getSetting('rd.client_id')
        if self.ClientID == '':
            self.ClientID = 'X245A4XAIBGVM'
        self.OauthUrl = 'https://api.real-debrid.com/oauth/v2/'
        self.DeviceCodeUrl = "device/code?%s"
        self.DeviceCredUrl = "device/credentials?%s"
        self.TokenUrl = "token"
        self.token = control.getSetting('rd.auth')
        self.refresh = control.getSetting('rd.refresh')
        self.DeviceCode = ''
        self.ClientSecret = control.getSetting('rd.secret')
        self.OauthTimeout = 0
        self.OauthTimeStep = 0
        self.BaseUrl = "https://api.real-debrid.com/rest/1.0/"

    def auth_loop(self):
        if control.progressDialog.iscanceled():
            control.progressDialog.close()
            self.OauthTimeout = 0
            return
        time.sleep(self.OauthTimeStep)
        url = "client_id=%s&code=%s" % (self.ClientID, self.DeviceCode)
        url = self.OauthUrl + self.DeviceCredUrl % url
        response = client.request(url, error=True)
        response = json.loads(response)
        if 'error' in response:
            return
        else:
            try:
                control.progressDialog.close()
                control.setSetting('rd.client_id', response['client_id'])
                control.setSetting('rd.secret', response['client_secret'])
                self.ClientSecret = response['client_secret']
                self.ClientID = response['client_id']
            except:
                control.ok_dialog(control.ADDON_NAME, control.lang(30105))
            return

    def auth(self):
        self.ClientSecret = ''
        self.ClientID = 'X245A4XAIBGVM'
        url = ("client_id=%s&new_credentials=yes" % self.ClientID)
        url = self.OauthUrl + self.DeviceCodeUrl % url
        response = json.loads(client.request(url))
        control.copy2clip(response['user_code'])
        control.progressDialog.create('Real-Debrid Auth')
        control.progressDialog.update(
            -1,
            control.lang(30100).format(control.colorString('https://real-debrid.com/device')) + '[CR]'
            + control.lang(30101).format(control.colorString(response['user_code'])) + '[CR]'
            + control.lang(30102)
        )
        self.OauthTimeout = int(response['expires_in'])
        self.OauthTimeStep = int(response['interval'])
        self.DeviceCode = response['device_code']

        while self.ClientSecret == '' and self.OauthTimeout > 0:
            control.sleep(self.OauthTimeStep * 1000)
            self.OauthTimeout -= self.OauthTimeStep
            self.auth_loop()

        if self.ClientSecret:
            self.token_request()
            user_information = self.get_url('https://api.real-debrid.com/rest/1.0/user')
            if user_information['type'] != 'premium':
                control.ok_dialog(control.ADDON_NAME, control.lang(30104))

    def token_request(self):
        if self.ClientSecret == '':
            return

        postData = {'client_id': self.ClientID,
                    'client_secret': self.ClientSecret,
                    'code': self.DeviceCode,
                    'grant_type': 'http://oauth.net/grant_type/device/1.0'}

        url = self.OauthUrl + self.TokenUrl
        response = client.request(url, post=postData)
        response = json.loads(response)
        control.setSetting('rd.auth', response['access_token'])
        control.setSetting('rd.refresh', response['refresh_token'])
        self.token = response['access_token']
        self.refresh = response['refresh_token']
        control.setSetting('rd.expiry', str(time.time() + int(response['expires_in'])))
        username = self.get_url('https://api.real-debrid.com/rest/1.0/user')['username']
        control.setSetting('rd.username', username)
        control.ok_dialog(control.ADDON_NAME, 'Real Debrid ' + control.lang(30103))

    def refreshToken(self):
        postData = {'grant_type': 'http://oauth.net/grant_type/device/1.0',
                    'code': self.refresh,
                    'client_secret': self.ClientSecret,
                    'client_id': self.ClientID
                    }
        url = self.OauthUrl + 'token'
        response = client.request(url, post=postData, error=True)
        response = json.loads(response)
        if 'access_token' in response:
            self.token = response['access_token']
        else:
            pass
        if 'refresh_token' in response:
            self.refresh = response['refresh_token']
            control.setSetting('rd.auth', self.token)
            control.setSetting('rd.refresh', self.refresh)
            control.setSetting('rd.expiry', str(time.time() + int(response['expires_in'])))
        # control.log('Real Debrid Token Refreshed')
        ###############################################
        # To be FINISHED FINISH ME
        ###############################################

    def post_url(self, url, postData, fail_check=False):
        headers = {
            'Authorization': 'Bearer {}'.format(self.token)
        }
        response = client.request(url, post=postData, headers=headers, timeout=5, error=True)
        if 'bad_token' in response or 'Bad Request' in response:
            if not fail_check:
                self.refreshToken()
                response = self.post_url(url, postData, fail_check=True)
        try:
            return json.loads(response)
        except:
            return response

    def get_url(self, url, fail_check=False):
        headers = {
            'Authorization': 'Bearer {}'.format(self.token)
        }

        response = client.request(url, headers=headers, timeout=10, error=True)
        if 'bad_token' in response or 'Bad Request' in response:
            if not fail_check:
                self.refreshToken()
                response = self.get_url(url, fail_check=True)

        try:
            return json.loads(response)
        except:
            return response

    def addMagnet(self, magnet):
        postData = {'magnet': magnet}
        url = 'https://api.real-debrid.com/rest/1.0/torrents/addMagnet'
        response = self.post_url(url, postData)
        torrent_id = response.get('id')
        if torrent_id:
            torrent_info = self.torrentInfo(torrent_id)
            status = torrent_info.get('status')
            if status not in ['downloaded', 'waiting_files_selection']:
                self.deleteTorrent(torrent_id)
                return
            return response

    def list_torrents(self):
        url = "https://api.real-debrid.com/rest/1.0/torrents"
        response = self.get_url(url)
        return response

    def torrentInfo(self, id):
        url = "https://api.real-debrid.com/rest/1.0/torrents/info/%s" % id
        return self.get_url(url)

    def torrentSelect(self, torrentID, fileID):
        url = "https://api.real-debrid.com/rest/1.0/torrents/selectFiles/%s" % torrentID
        postData = {'files': fileID}
        return self.post_url(url, postData)

    def resolve_hoster(self, link):
        url = 'https://api.real-debrid.com/rest/1.0/unrestrict/link'
        postData = {'link': link}
        response = self.post_url(url, postData)
        try:
            return response['download']
        except:
            return None

    def deleteTorrent(self, id):
        headers = {
            'Authorization': 'Bearer {}'.format(self.token)
        }
        url = "https://api.real-debrid.com/rest/1.0/torrents/delete/%s" % (id)
        client.request(url, headers=headers, timeout=5, method='DELETE')

    def resolve_single_magnet(self, hash_, magnet, episode='', pack_select=False):
        try:
            key_list = 'all'

            torrent = self.addMagnet(magnet)
            if not torrent:
                return

            self.torrentSelect(torrent['id'], key_list)

            files = self.torrentInfo(torrent['id'])
            selected_files = [(idx, i) for idx, i in enumerate([i for i in files['files'] if i['selected'] == 1])]

            if pack_select:
                best_match = source_utils.get_best_match('path', [i[1] for i in selected_files], episode, pack_select)
                if best_match:
                    try:
                        file_index = [i[0] for i in selected_files if i[1]['path'] == best_match['path']][0]
                        link = files['links'][file_index]
                        stream_link = self.resolve_hoster(link)
                    except IndexError:
                        stream_link = None
                else:
                    stream_link = None

            elif len(selected_files) == 1:
                stream_link = self.resolve_hoster(files['links'][0])

            elif len(selected_files) >= 5:
                try:
                    best_match = source_utils.get_best_match('path', [i[1] for i in selected_files], episode)
                    file_index = [i[0] for i in selected_files if i[1]['path'] == best_match['path']][0]
                    link = files['links'][file_index]
                    stream_link = self.resolve_hoster(link)
                except:
                    stream_link = None

            else:
                selected_files = sorted(selected_files, key=lambda x: x[1]['bytes'], reverse=True)
                stream_link = self.resolve_hoster(files['links'][selected_files[0][0]])

            self.deleteTorrent(torrent['id'])

            return stream_link
        except:
            import traceback
            traceback.print_exc()
