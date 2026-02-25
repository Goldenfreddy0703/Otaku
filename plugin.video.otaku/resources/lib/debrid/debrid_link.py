import time
from resources.lib.ui import client, control, source_utils, database


class DebridLink:
    def __init__(self):
        api_info = database.get_info('Debrid-Link')
        self.ClientID = api_info['client_id']
        self.USER_AGENT = 'Otaku'
        self.token = control.getSetting('debridlink.token')
        self.refresh = control.getSetting('debridlink.refresh')
        self.autodelete = control.getBool('debridlink.autodelete')
        self.api_url = "https://debrid-link.fr/api/v2"
        self.cache_check_results = {}
        self.DeviceCode = ''
        self.OauthTimeStep = 0
        self.OauthTimeout = 0
        self.OauthTotalTimeout = 0

    def headers(self):
        return {'User-Agent': self.USER_AGENT, 'Authorization': f"Bearer {self.token}"}

    def auth_loop(self):
        if control.progressDialog.iscanceled():
            control.progressDialog.close()
            self.OauthTimeout = 0
            return False
        control.progressDialog.update(int(self.OauthTimeout / self.OauthTotalTimeout * 100))
        url = f"{self.api_url[:-3]}/oauth/token"
        data = {
            'client_id': self.ClientID,
            'code': self.DeviceCode,
            'grant_type': 'urn:ietf:params:oauth:grant-type:device_code'
        }
        r = client.post(url, data=data, headers={'User-Agent': self.USER_AGENT})
        if r:
            response = r.json()
            control.progressDialog.close()
            self.token = response.get('access_token')
            self.refresh = response.get('refresh_token')
            control.setSetting('debridlink.token', self.token)
            control.setSetting('debridlink.refresh', self.refresh)
            control.setInt('debridlink.expiry', int(time.time()) + int(response['expires_in']))
            return True

    def auth(self):
        url = '{0}/oauth/device/code'.format(self.api_url[:-3])
        data = {'client_id': self.ClientID, 'scope': 'get.post.delete.seedbox get.account'}
        r = client.post(url, data=data, headers={'User-Agent': self.USER_AGENT})
        if r:
            resp = r.json()
            self.OauthTotalTimeout = self.OauthTimeout = resp['expires_in']
            self.OauthTimeStep = resp['interval']
            self.DeviceCode = resp['device_code']

            copied = control.copy2clip(resp.get('user_code'))
            display_dialog = (
                f"{control.lang(30081).format(control.colorstr(resp['verification_url']))}[CR]"
                f"{control.lang(30082).format(control.colorstr(resp['user_code']))}"
            )
            if copied:
                display_dialog = f"{display_dialog}[CR]{control.lang(30083)}"
            control.progressDialog.create(f'{control.ADDON_NAME}: Debrid-Link Auth', display_dialog)
            control.progressDialog.update(100)
            auth_done = False
            while not auth_done and self.OauthTimeout > 0:
                self.OauthTimeout -= self.OauthTimeStep
                control.sleep(self.OauthTimeStep * 1000)
                auth_done = self.auth_loop()
            if auth_done:
                self.status()

    def status(self):
        url = f"{self.api_url[:-3]}/account/infos"
        response = client.get(url, headers=self.headers())
        if not response:
            control.ok_dialog(control.ADDON_NAME, 'Failed to get Debrid-Link user info')
            return
        response = response.json()
        if 'value' not in response:
            control.ok_dialog(control.ADDON_NAME, 'Failed to get Debrid-Link user info')
            return
        username = response['value']['pseudo']
        premium = response['value']['premiumLeft'] > 0
        control.setSetting('debridlink.username', username)
        control.ok_dialog(control.ADDON_NAME, f'Debrid-Link {control.lang(30084)}')
        control.setBool('show.uncached', True)
        control.setBool('uncached.autoruninforground', False)
        control.setBool('uncached.autoruninbackground', False)
        control.setBool('uncached.autoskipuncached', True)
        if not premium:
            control.setSetting('debridlink.auth.status', 'Expired')
            control.ok_dialog(f'{control.ADDON_NAME}: Debrid-Link', control.lang(30085))
        else:
            control.setSetting('debridlink.auth.status', 'Premium')

    def refreshToken(self):
        postData = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh,
            'client_id': self.ClientID
        }
        url = f"{self.api_url[:-3]}/oauth/token"
        response = client.post(url, data=postData, headers={'User-Agent': self.USER_AGENT})
        if not response:
            return
        response = response.json()
        if response.get('access_token'):
            self.token = response['access_token']
            control.setSetting('debridlink.token', self.token)
            control.setInt('debridlink.expiry', int(time.time()) + response['expires_in'])

    def addMagnet(self, magnet):
        postData = {
            'url': magnet,
            'async': 'true'
        }
        url = f"{self.api_url}/seedbox/add"
        r = client.post(url, data=postData, headers=self.headers())
        return r.json().get('value') if r else None

    def resolve_single_magnet(self, hash_, magnet, episode, pack_select):
        magnet_data = self.addMagnet(magnet)
        if not magnet_data or 'files' not in magnet_data:
            return None
        files = magnet_data['files']
        folder_details = [{'link': x['downloadUrl'], 'path': x['name']} for x in files]
        if episode:
            selected_file = source_utils.get_best_match('path', folder_details, episode, pack_select)
            if selected_file is not None:
                return selected_file['link']

        sources = [(item.get('size'), item.get('downloadUrl'))for item in files if any(item.get('name').lower().endswith(x) for x in ['avi', 'mp4', 'mkv'])]

        selected_file = max(sources)[1]
        if selected_file is None:
            return
        return selected_file

    def get_torrent_status(self, magnet):
        """
        Given a magnet link, get torrent data needed for further resolution.
        Returns a tuple: (torrent_id, status, torrent_info)
        If the torrent cannot be selected, returns (None, None, None).
        """
        magnet_data = self.addMagnet(magnet)
        if not magnet_data or not magnet_data['id']:
            control.ok_dialog(control.ADDON_NAME, "BAD LINK")
            return None, None, None
        status = magnet_data.get('downloadPercent') == 100
        return magnet, status, magnet_data

    def magnet_status(self, magnet_id):
        url = f'{self.api_url}/seedbox/{magnet_id}/infos'
        r = client.get(url, headers=self.headers())
        return r.json()['value'] if r else None

    def resolve_uncached_source(self, source, runinbackground, runinforground, pack_select):
        heading = f'{control.ADDON_NAME}: Cache Resolver'
        if runinforground:
            control.progressDialog.create(heading, "Caching Progress")
        stream_link = None
        magnet = source['magnet']
        magnet_data = self.addMagnet(magnet)
        if not magnet_data or 'id' not in magnet_data:
            if runinforground:
                control.progressDialog.close()
            return None
        magnet_id = magnet_data['id']
        magnet_status = self.magnet_status(magnet_id)
        if not magnet_status:
            if runinforground:
                control.progressDialog.close()
            return None
        while magnet_status.get('downloadPercent') < 100.0:
            if runinforground and (control.progressDialog.iscanceled() or control.wait_for_abort(5)):
                break
            magnet_status = self.magnet_status(magnet_id)
            if not magnet_status:
                break
            status = magnet_status.get('name')
            progress = magnet_status.get('downloadPercent')
            speed = magnet_status.get('downloadSpeed')
            seeders = magnet_status.get('peersConnected')

            if runinforground:
                f_body = (f"Status: {status}[CR]"
                          f"Progress: {round(progress, 2)} %[CR]"
                          f"Seeders: {seeders}[CR]"
                          f"Speed: {source_utils.get_size(speed)}")
                control.progressDialog.update(int(progress), f_body)
            control.sleep(5000)

        if magnet_status.get('downloadPercent') == 100.0:
            folder_details = [{'link': x.get('downloadUrl'), 'path': x.get('name').split('/')[-1]} for x in magnet_status.get('files')]
            if len(folder_details) == 1:
                stream_link = folder_details[0]['link']
            else:
                selected_file = source_utils.get_best_match('path', folder_details, source['episode_re'], pack_select)
                if not selected_file or not selected_file['path']:
                    self.delete_magnet(magnet_id)
                    return
                stream_link = selected_file['link']
        else:
            self.delete_magnet(magnet_id)
        if runinforground:
            control.progressDialog.close()
        return stream_link

    @staticmethod
    def resolve_cloud(source, pack_select):
        pass
