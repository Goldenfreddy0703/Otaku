import urllib.parse
from resources.lib.ui import client, control, source_utils


class AllDebrid:
    def __init__(self):
        self.token = control.getSetting('alldebrid.token')
        self.autodelete = control.getBool('alldebrid.autodelete')
        self.agent_identifier = 'Otaku'
        self.base_url = 'https://api.alldebrid.com/v4.1'
        self.cache_check_results = []
        self.OauthTimeStep = 1
        self.OauthTimeout = 0
        self.OauthTotalTimeout = 0

    def auth(self):
        params = {'agent': self.agent_identifier}
        r = client.get(f'{self.base_url}/pin/get', params=params)
        resp = r.json()['data'] if r else {}
        self.OauthTotalTimeout = self.OauthTimeout = int(resp['expires_in'])
        copied = control.copy2clip(resp['pin'])
        display_dialog = (f"{control.lang(30081).format(control.colorstr(resp['base_url']))}[CR]"
                          f"{control.lang(30082).format(control.colorstr(resp['pin']))}")
        if copied:
            display_dialog = f"{display_dialog}[CR]{control.lang(30083)}"
        control.progressDialog.create(f'{control.ADDON_NAME}: Alldebrid Auth', display_dialog)
        control.progressDialog.update(100)

        # Seems the All Debrid servers need some time do something with the pin before polling
        # Polling too early will cause an invalid pin error

        control.sleep(5000)

        auth_done = False
        while not auth_done and self.OauthTimeout > 0:
            self.OauthTimeout -= self.OauthTimeStep
            control.sleep(self.OauthTimeStep * 1000)
            auth_done = self.auth_loop(check=resp['check'], pin=resp['pin'])
        control.progressDialog.close()
        if auth_done:
            self.status()

    def status(self):
        params = {
            'agent': self.agent_identifier,
            'apikey': self.token
        }
        r = client.get(f'{self.base_url}/user', params=params)
        res = r.json()['data'] if r else {}
        user_information = res['user']
        premium = user_information['isPremium']
        control.setSetting('alldebrid.username', user_information['username'])
        control.ok_dialog(control.ADDON_NAME, f'Alldebrid {control.lang(30084)}')
        control.setBool('show.uncached', True)
        control.setBool('uncached.autoruninforground', False)
        control.setBool('uncached.autoruninbackground', False)
        control.setBool('uncached.autoskipuncached', True)
        if not premium:
            control.setSetting('alldebrid.auth.status', 'Expired')
            control.ok_dialog(f'{control.ADDON_NAME}: AllDebrid', control.lang(30085))
        else:
            control.setSetting('alldebrid.auth.status', 'Premium')

    def auth_loop(self, **params):
        if control.progressDialog.iscanceled():
            self.OauthTimeout = 0
            return False
        control.progressDialog.update(int(self.OauthTimeout / self.OauthTotalTimeout * 100))
        params['agent'] = self.agent_identifier
        r = client.get(f'{self.base_url}/pin/check', params=params)
        resp = r.json()['data'] if r else {}
        if resp.get('activated'):
            self.token = resp['apikey']
            control.setSetting('alldebrid.token', self.token)
            return True
        return False

    def addMagnet(self, magnet_hash):
        params = {
            'agent': self.agent_identifier,
            'apikey': self.token,
            'magnets': magnet_hash
        }
        r = client.get(f'{self.base_url}/magnet/upload', params=params)
        return r.json()['data'] if r else None

    def resolve_hoster(self, url):
        params = {
            'agent': self.agent_identifier,
            'apikey': self.token,
            'link': url
        }
        r = client.get(f'{self.base_url}/link/unlock', params=params)
        resolve = r.json()['data'] if r else {}
        return resolve.get('link')

    def magnet_status(self, magnet_id):
        params = {
            'agent': self.agent_identifier,
            'apikey': self.token,
            'id': magnet_id
        }
        r = client.get(f'{self.base_url}/magnet/status', params=params)
        return r.json()['data'] if r else None

    def list_torrents(self):
        params = {
            'agent': self.agent_identifier,
            'apikey': self.token
        }
        r = client.get(f'{self.base_url}/user/links', params=params)
        return r.json()['data'] if r else None

    def link_info(self, link):
        params = {
            'agent': self.agent_identifier,
            'apikey': self.token,
            'link[]': link
        }
        encoded_params = urllib.parse.urlencode(params, doseq=True)
        url = f'{self.base_url}/link/infos?{encoded_params}'
        r = client.get(url)
        return r.json()['data'] if r else None

    def resolve_single_magnet(self, hash_, magnet, episode, pack_select):
        magnet_id = self.addMagnet(magnet)['magnets'][0]['id']
        folder_details = self.magnet_status(magnet_id)['magnets']['files']
        if folder_details[0].get('e'):
            folder_details = folder_details[0].get('e')
        folder_details = [{'link': x['l'], 'path': x['n']} for x in folder_details]

        if episode:
            selected_file = source_utils.get_best_match('path', folder_details, str(episode), pack_select)
            if selected_file is not None:
                resolved_link = self.resolve_hoster(selected_file['link'])
                if self.autodelete:
                    self.delete_magnet(magnet_id)
                return resolved_link

        selected_file = folder_details[0]['link']

        if selected_file is None:
            return

        resolved_link = self.resolve_hoster(selected_file)
        if self.autodelete:
            self.delete_magnet(magnet_id)
        return resolved_link

    def resolve_cloud(self, source, pack_select):
        pass

    def delete_magnet(self, magnet_id):
        params = {
            'agent': self.agent_identifier,
            'apikey': self.token,
            'id': magnet_id
        }
        r = client.get(f'{self.base_url}/magnet/delete', params=params)
        return r and r.ok

    def get_torrent_status(self, magnet):
        """
        Given a magnet link, get magnet status data needed for further resolution.
        Returns a tuple: (magnet_id, status, status_data)
        If the magnet cannot be processed correctly, returns (None, None, None).
        """
        magnet_data = self.addMagnet(magnet)
        if not magnet_data or 'magnets' not in magnet_data or not magnet_data['magnets']:
            control.ok_dialog(control.ADDON_NAME, "BAD LINK")
            return None, None, None

        magnet_id = magnet_data['magnets'][0]['id']
        status_data = self.magnet_status(magnet_id)
        if not status_data or 'magnets' not in status_data:
            self.delete_magnet(magnet_id)
            control.ok_dialog(control.ADDON_NAME, "BAD LINK")
            return None, None, None

        status = status_data['magnets']['status']
        return magnet_id, status, status_data

    def resolve_uncached_source(self, source, runinbackground, runinforground, pack_select):
        heading = f'{control.ADDON_NAME}: Cache Resolver'
        if runinforground:
            control.progressDialog.create(heading, "Caching Progress")
        stream_link = None
        magnet = source['magnet']
        magnet_data = self.addMagnet(magnet)
        magnet_id = magnet_data['magnets'][0]['id']
        magnet_status = self.magnet_status(magnet_id)
        status = magnet_status['magnets']['status']
        folder_details = magnet_status['magnets']['files']
        if folder_details[0].get('e'):
            folder_details = folder_details[0].get('e')
        folder_details = [{'link': x['l'], 'path': x['n']} for x in folder_details]

        if runinbackground:
            control.notify(heading, "The source is downloading to your cloud")
            return

        total_size = 0
        progress = 0
        while status not in ['Ready', 'Error']:
            if runinforground and (control.progressDialog.iscanceled() or control.wait_for_abort(5)):
                break
            magnet_status = self.magnet_status(magnet_id)
            status = magnet_status['magnets']['status']
            total_size = magnet_status['magnets'].get('size', 0)  # Update total_size in the loop
            try:
                downloaded = magnet_status['magnets']['downloaded']
                seeders = magnet_status['magnets'].get('seeders', 0)
                speed = magnet_status['magnets'].get('downloadSpeed', 0)
                if total_size > 0:
                    progress = (downloaded / total_size) * 100
                else:
                    progress = 0
            except TypeError:
                control.log(magnet_status)
            if runinforground:
                f_body = (f"Status: {status}[CR]"
                          f"Progress: {round(progress, 2)} %[CR]"
                          f"Seeders: {seeders}[CR]"
                          f"Speed: {source_utils.get_size(speed)}")
                control.progressDialog.update(int(progress), f_body)

        if status == 'Ready':
            if total_size > 0:
                control.ok_dialog(heading, "This file has been added to your Cloud")
            # Check if there's only one file in the torrent
            if len(folder_details) == 1:
                # If there's just one file, use it directly
                stream_link = self.resolve_hoster(folder_details[0]['link'])
            else:
                # If there are multiple files, use best match algorithm
                selected_file = source_utils.get_best_match('path', folder_details, source['episode_re'], pack_select)

                if not selected_file or not selected_file['path']:
                    self.delete_magnet(magnet_id)
                    return

                stream_link = self.resolve_hoster(selected_file['link'])
            if self.autodelete:
                self.delete_magnet(magnet_id)
        else:
            self.delete_magnet(magnet_id)
        if runinforground:
            control.progressDialog.close()
        return stream_link
