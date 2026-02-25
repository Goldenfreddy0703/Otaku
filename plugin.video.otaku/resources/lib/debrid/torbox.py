from resources.lib.ui import source_utils, client, control

from datetime import datetime, timezone


class TorBox:
    def __init__(self):
        self.token = control.getSetting('torbox.token')
        self.autodelete = control.getBool('torbox.autodelete')
        self.BaseUrl = "https://api.torbox.app/v1/api"
        self.OauthTimeStep = 0
        self.OauthTimeout = 0
        self.OauthTotalTimeout = 0

    def headers(self):
        return {'Authorization': f"Bearer {self.token}"}

    def auth(self):
        params = {'app': 'Otaku'}
        r = client.get(f'{self.BaseUrl}/user/auth/device/start', params=params)
        if not r or not r.ok:
            control.ok_dialog(control.ADDON_NAME, 'Failed to connect to TorBox')
            return

        try:
            resp = r.json().get('data', {})
        except (ValueError, KeyError):
            control.ok_dialog(control.ADDON_NAME, 'TorBox API error')
            return

        if not resp:
            control.ok_dialog(control.ADDON_NAME, 'TorBox: Failed to get device code')
            return

        device_code = resp.get('device_code', '')
        user_code = resp.get('code', '')
        verification_url = resp.get('friendly_verification_url') or resp.get('verification_url', 'https://tor.box/link')
        interval = int(resp.get('interval', 5))

        # Calculate expires_in from expires_at timestamp
        expires_at = resp.get('expires_at', '')
        try:
            expires_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            expires_in = max(int((expires_dt - datetime.now(timezone.utc)).total_seconds()), 60)
        except (ValueError, TypeError):
            expires_in = 600

        copied = control.copy2clip(user_code)
        display_dialog = (f"{control.lang(30081).format(control.colorstr(verification_url))}[CR]"
                          f"{control.lang(30082).format(control.colorstr(user_code))}")
        if copied:
            display_dialog = f"{display_dialog}[CR]{control.lang(30083)}"
        control.progressDialog.create(f'{control.ADDON_NAME}: TorBox Auth', display_dialog)
        control.progressDialog.update(100)

        self.OauthTotalTimeout = self.OauthTimeout = expires_in
        self.OauthTimeStep = interval

        auth_done = False
        while not auth_done and self.OauthTimeout > 0:
            self.OauthTimeout -= self.OauthTimeStep
            control.sleep(self.OauthTimeStep * 1000)
            auth_done = self.auth_loop(device_code)
        control.progressDialog.close()

        if auth_done:
            self.status()

    def auth_loop(self, device_code):
        if control.progressDialog.iscanceled():
            self.OauthTimeout = 0
            return False
        control.progressDialog.update(int(self.OauthTimeout / self.OauthTotalTimeout * 100))
        data = {'device_code': device_code}
        r = client.post(f'{self.BaseUrl}/user/auth/device/token', json_data=data)
        if r and r.ok:
            try:
                result = r.json()
                resp = result.get('data', {})
                if isinstance(resp, str):
                    # data is the token string directly
                    self.token = resp
                    control.setSetting('torbox.token', self.token)
                    return True
                elif isinstance(resp, dict) and resp:
                    token = resp.get('access_token') or resp.get('token') or resp.get('api_token') or resp.get('auth_token')
                    if token:
                        self.token = token
                        control.setSetting('torbox.token', self.token)
                        return True
            except (ValueError, KeyError):
                pass
        return False

    def status(self):
        r = client.get(f'{self.BaseUrl}/user/me', headers=self.headers())
        user_info = r.json()['data'] if r else None
        if user_info:
            control.setSetting('torbox.username', user_info['email'])
            if user_info['plan'] == 0:
                control.setSetting('torbox.auth.status', 'Free')
                control.ok_dialog(f'{control.ADDON_NAME}: TorBox', control.lang(30085))
            elif user_info['plan'] == 1:
                control.setSetting('torbox.auth.status', 'Essential')
            elif user_info['plan'] == 3:
                control.setSetting('torbox.auth.status', 'Standard')
            elif user_info['plan'] == 2:
                control.setSetting('torbox.auth.status', 'Pro')
            control.ok_dialog(control.ADDON_NAME, f'TorBox {control.lang(30084)}')
        return user_info is not None

    def refreshToken(self):
        pass

    def hash_check(self, hash_list):
        hashes = ','.join(hash_list)
        url = f'{self.BaseUrl}/torrents/checkcached'
        params = {
            'hash': hashes,
            'format': 'list'
        }
        r = client.get(url, headers=self.headers(), params=params)
        return r.json()['data'] if r else None

    def addMagnet(self, magnet):
        url = f'{self.BaseUrl}/torrents/createtorrent'
        data = {
            'magnet': magnet
        }
        r = client.post(url, headers=self.headers(), data=data)
        return r.json()['data'] if r else None

    def delete_torrent(self, torrent_id):
        url = f'{self.BaseUrl}/torrents/controltorrent'
        data = {
            'torrent_id': torrent_id,
            'operation': 'delete'
        }
        r = client.post(url, headers=self.headers(), json_data=data)
        return r.json()['data'] if r else None

    def list_torrents(self):
        url = f'{self.BaseUrl}/torrents/mylist'
        r = client.get(url, headers=self.headers())
        return r.json()['data'] if r else None

    def get_torrent_info(self, torrent_id):
        url = f'{self.BaseUrl}/torrents/mylist'
        params = {'id': torrent_id, 'bypass_cache': 'true'}
        r = client.get(url, headers=self.headers(), params=params)
        return r.json()['data'] if r else None

    def request_dl_link(self, torrent_id, file_id=-1):
        url = f'{self.BaseUrl}/torrents/requestdl'
        params = {
            'token': self.token,
            'torrent_id': torrent_id
        }
        if file_id >= 0:
            params['file_id'] = file_id
        r = client.get(url, params=params)
        return r.json()['data'] if r else None

    def resolve_single_magnet(self, hash_, magnet, episode, pack_select):
        torrent = self.addMagnet(magnet)
        if not torrent or 'torrent_id' not in torrent:
            return None
        torrent_id = torrent['torrent_id']
        torrent_info = self.get_torrent_info(torrent_id)
        if not torrent_info or 'files' not in torrent_info:
            self.delete_torrent(torrent_id)
            return None
        folder_details = [{'fileId': x['id'], 'path': x['name']} for x in torrent_info['files']]

        if episode:
            selected_file = source_utils.get_best_match('path', folder_details, str(episode), pack_select)
            if selected_file and selected_file['fileId'] is not None:
                stream_link = self.request_dl_link(torrent_id, selected_file['fileId'])
                if self.autodelete:
                    self.delete_torrent(torrent_id)
                return stream_link
        self.delete_torrent(torrent_id)

    def resolve_hoster(self, source):
        return self.request_dl_link(source['folder_id'], source['file']['id'])

    @staticmethod
    def resolve_cloud(source, pack_select):
        if source['hash']:
            best_match = source_utils.get_best_match('short_name', source['hash'], source['episode'], pack_select)
            if not best_match or not best_match['short_name']:
                return
            for f_index, torrent_file in enumerate(source['hash']):
                if torrent_file['short_name'] == best_match['short_name']:
                    return {'folder_id': source['id'], 'file': source['hash'][f_index]}

    def resolve_uncached_source(self, source, runinbackground, runinforground, pack_select):
        heading = f'{control.ADDON_NAME}: Cache Resolver'
        if runinforground:
            control.progressDialog.create(heading, "Caching Progress")
        stream_link = None
        magnet = source['magnet']
        torrent = self.addMagnet(magnet)
        if not torrent or 'torrent_id' not in torrent:
            control.log('TorBox addMagnet failed - no valid response', 'warning')
            if runinforground:
                control.progressDialog.close()
            return None
        torrent_id = torrent['torrent_id']
        torrent_info = self.get_torrent_info(torrent_id)
        if not torrent_info:
            self.delete_torrent(torrent_id)
            if runinforground:
                control.progressDialog.close()
            return None
        status = torrent_info.get('download_state', 'error')

        if runinbackground:
            control.notify(heading, "The source is downloading to your cloud")
            return

        progress = 0
        while status not in ['completed', 'error']:
            if runinforground and (control.progressDialog.iscanceled() or control.wait_for_abort(5)):
                break
            torrent_info = self.get_torrent_info(torrent_id)
            if not torrent_info:
                status = 'error'
                break
            status = torrent_info.get('download_state', 'error')
            progress = torrent_info.get('progress', 0) * 100
            peers = torrent_info.get('peers', 0)
            download_speed = torrent_info.get('download_speed', 0)
            if runinforground:
                f_body = (f"Status: {status}[CR]"
                          f"Progress: {round(progress, 2)} %[CR]"
                          f"Peers: {peers}[CR]"
                          f"Download Speed: {source_utils.get_size(download_speed)}")
                control.progressDialog.update(int(progress), f_body)

        if status == 'completed':
            control.ok_dialog(heading, "This file has been added to your Cloud")
            folder_details = [{'fileId': x['id'], 'path': x['name']} for x in torrent_info['files']]
            selected_file = source_utils.get_best_match('path', folder_details, source['episode_re'], pack_select)
            if selected_file and selected_file['fileId'] is not None:
                stream_link = self.request_dl_link(torrent_id, selected_file['fileId'])
                if self.autodelete:
                    self.delete_torrent(torrent_id)
            else:
                stream_link = self.request_dl_link(torrent_id)
                if self.autodelete:
                    self.delete_torrent(torrent_id)
            if self.autodelete:
                self.delete_torrent(torrent_id)
        else:
            self.delete_torrent(torrent_id)
        if runinforground:
            control.progressDialog.close()
        return stream_link
