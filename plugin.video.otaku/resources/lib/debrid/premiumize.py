import urllib.parse

from resources.lib.ui import source_utils, client, control, database


class Premiumize:
    def __init__(self):
        api_info = database.get_info('Premiumize')
        self.client_id = api_info['client_id']
        self.token = control.getSetting('premiumize.token')
        self.addtocloud = control.getBool('premiumize.addToCloud')
        self.autodelete = control.getBool('premiumize.autodelete')
        self.threshold = control.getInt('premiumize.threshold')
        self.base_url = 'https://www.premiumize.me/api'
        self.OauthTimeStep = 0
        self.OauthTimeout = 0
        self.OauthTotalTimeout = 0

    def headers(self):
        return {'Authorization': f"Bearer {self.token}"}

    def auth(self):
        data = {'client_id': self.client_id, 'response_type': 'device_code'}
        r = client.post('https://www.premiumize.me/token', json_data=data)
        resp = r.json() if r else {}
        self.OauthTotalTimeout = self.OauthTimeout = resp['expires_in']
        self.OauthTimeStep = int(resp['interval'])
        copied = control.copy2clip(resp['user_code'])
        display_dialog = (f"{control.lang(30081).format(control.colorstr(resp['verification_uri']))}[CR]"
                          f"{control.lang(30082).format(control.colorstr(resp['user_code']))}")
        if copied:
            display_dialog = f"{display_dialog}[CR]{control.lang(30083)}"
        control.progressDialog.create(f'{control.ADDON_NAME}: Premiumize Auth', display_dialog)
        control.progressDialog.update(100)

        auth_done = False
        while not auth_done and self.OauthTimeout > 0:
            self.OauthTimeout -= self.OauthTimeStep
            control.sleep(self.OauthTimeStep * 1000)
            auth_done = self.auth_loop(resp['device_code'])
        control.progressDialog.close()

        if auth_done:
            self.status()

    def status(self):
        r = client.get(f'{self.base_url}/account/info', headers=self.headers())
        user_information = r.json() if r else {}
        premium = user_information['premium_until'] > 0
        control.setSetting('premiumize.username', user_information['customer_id'])
        control.ok_dialog(control.ADDON_NAME, f'Premiumize {control.lang(30084)}')
        if not premium:
            control.setSetting('premiumize.auth.status', 'Expired')
            control.ok_dialog(f'{control.ADDON_NAME}: Premiumize', control.lang(30085))
        else:
            control.setSetting('premiumize.auth.status', 'Premium')

    def auth_loop(self, device_code):
        if control.progressDialog.iscanceled():
            self.OauthTimeout = 0
            return False
        control.progressDialog.update(int(self.OauthTimeout / self.OauthTotalTimeout * 100))
        data = {'client_id': self.client_id, 'code': device_code, 'grant_type': 'device_code'}
        r = client.post('https://www.premiumize.me/token', json_data=data)
        token = r.json() if r else {}
        if r and 'access_token' in token:
            self.token = token['access_token']
            control.setSetting('premiumize.token', self.token)
            return True
        else:
            if token.get('error') == 'access_denied':
                self.OauthTimeout = 0
            if token.get('error') == 'slow_down':
                control.sleep(1000)
        return False

    def search_folder(self, query):
        params = {'q': query}
        r = client.get(f'{self.base_url}/folder/search', headers=self.headers(), params=params)
        return r.json()['content'] if r else None

    def list_folder(self, folderid=None):
        params = {'id': folderid} if folderid else None
        r = client.get(f"{self.base_url}/folder/list", headers=self.headers(), params=params)
        return r.json()['content'] if r else None

    def hash_check(self, hashlist):
        params = urllib.parse.urlencode([('items[]', hash) for hash in hashlist])
        url = f'{self.base_url}/cache/check?{params}'
        r = client.get(url, headers=self.headers())
        return r.json() if r else None

    def direct_download(self, src):
        postData = {'src': src}
        r = client.post(f'{self.base_url}/transfer/directdl', headers=self.headers(), data=postData)
        return r.json() if r else None

    def addMagnet(self, src):
        postData = {'src': src}
        r = client.post(f'{self.base_url}/transfer/create', headers=self.headers(), data=postData)
        return r.json() if r else None

    def transfer_list(self):
        r = client.get(f'{self.base_url}/transfer/list', headers=self.headers())
        return r.json()['transfers'] if r else None

    def delete_torrent(self, torrent_id):
        params = {'id': torrent_id}
        r = client.post(f'{self.base_url}/transfer/delete', headers=self.headers(), data=params)
        return r.json() if r else None

    def manage_storage_space(self):
        storage_info = self.get_storage_info()
        used_space_gb = storage_info['space_used'] / (1024 ** 3)
        if used_space_gb > self.threshold:
            oldest_items = self.get_oldest_items()
            for item in oldest_items:
                self.delete_torrent(item['id'])
                used_space_gb -= item['size'] / (1024 ** 3)
                if used_space_gb <= self.threshold:
                    break

    def get_storage_info(self):
        r = client.get(f'{self.base_url}/account/info', headers=self.headers())
        return r.json() if r else None

    def get_oldest_items(self):
        r = client.get(f'{self.base_url}/transfer/list', headers=self.headers())
        transfers = r.json()['transfers'] if r else []
        # Filter out items missing 'created_at' to avoid KeyError
        transfers_with_created = [x for x in transfers if 'created_at' in x]
        return sorted(transfers_with_created, key=lambda x: x['created_at'])

    def add_to_cloud(self, link):
        postData = {'src': link}
        r = client.post(f'{self.base_url}/transfer/create', headers=self.headers(), data=postData)
        response = r.json() if r else {}
        if response.get('status') == 'success':
            control.log(f"Successfully added to cloud: {link}")
        else:
            control.log(f"Failed to add to cloud: {link}", level='error')
        return response

    def resolve_hoster(self, source):
        self.manage_storage_space()
        directLink = self.direct_download(source)
        if not directLink or directLink.get('status') != 'success':
            return None
        if self.addtocloud:
            self.add_to_cloud(directLink.get('location', ''))
        return directLink.get('location')

    def resolve_single_magnet(self, hash_, magnet, episode, pack_select):
        self.manage_storage_space()
        dd_result = self.direct_download(magnet)
        if not dd_result or 'content' not in dd_result:
            return None
        folder_details = dd_result['content']
        folder_details = sorted(folder_details, key=lambda i: int(i['size']), reverse=True)
        folder_details = [i for i in folder_details if source_utils.is_file_ext_valid(i['link'])]
        filter_list = [i for i in folder_details]

        if pack_select:
            identified_file = source_utils.get_best_match('path', folder_details, episode, pack_select)
            stream_link = identified_file.get('link')
        elif len(filter_list) == 1:
            stream_link = filter_list[0]['link']
        elif len(filter_list) >= 1:
            identified_file = source_utils.get_best_match('path', folder_details, episode)
            stream_link = identified_file.get('link')
        else:
            filter_list = [tfile for tfile in folder_details if 'sample' not in tfile['path'].lower()]
            if len(filter_list) == 1:
                stream_link = filter_list[0]['link']

        if stream_link and self.addtocloud:
            self.add_to_cloud(stream_link)
        return stream_link

    def resolve_cloud(self, source, pack_select):
        def get_all_files(folder_id):
            items = self.list_folder(folder_id)
            files = []
            for item in items:
                if item['type'] == 'folder':
                    files.extend(get_all_files(item['id']))
                else:
                    files.append(item)
            return files

        link = None
        if source['torrent_type'] == 'file':
            link = source['hash']
        elif source['torrent_type'] == 'folder':
            all_files = get_all_files(source['id'])
            best_match = source_utils.get_best_match('name', all_files, source['episode'], pack_select)
            if best_match and best_match.get('link'):
                link = best_match['link']
        return link

    def resolve_uncached_source(self, source, runinbackground, runinforground, pack_select):
        heading = f'{control.ADDON_NAME}: Cache Resolver'
        if runinforground:
            control.progressDialog.create(heading, "Caching Progress")
        stream_link = None
        magnet = source['magnet']
        magnet_data = self.addMagnet(magnet)
        if not magnet_data or 'id' not in magnet_data:
            control.log('Premiumize addMagnet failed - no valid response', 'warning')
            if runinforground:
                control.progressDialog.close()
            return None
        transfer_id = magnet_data['id']
        transfer_status = self.transfer_list()
        if not transfer_status:
            if runinforground:
                control.progressDialog.close()
            return None
        status_item = next((item for item in transfer_status if item['id'] == transfer_id), None)
        if not status_item:
            if runinforground:
                control.progressDialog.close()
            return None
        status = status_item['status']

        if runinbackground:
            control.notify(heading, "The source is downloading to your cloud")
            return

        progress = 0
        while status not in ['finished', 'error']:
            if runinforground and (control.progressDialog.iscanceled() or control.wait_for_abort(5)):
                break
            transfer_status = self.transfer_list()
            if not transfer_status:
                status = 'error'
                break
            status_item = next((item for item in transfer_status if item['id'] == transfer_id), None)
            if not status_item:
                status = 'error'
                break
            status = status_item.get('status', 'error')
            progress = status_item.get('progress', 0)
            if progress is not None:
                progress *= 100
            else:
                progress = 100 if status == 'finished' else 0
            if runinforground:
                f_body = (f"Status: {status}[CR]"
                          f"Progress: {round(progress, 2)} %")
                control.progressDialog.update(int(progress), f_body)

        if status == 'finished':
            self.manage_storage_space()
            control.ok_dialog(heading, "This file has been added to your Cloud")
            dd_result = self.direct_download(magnet)
            if not dd_result or 'content' not in dd_result:
                self.delete_torrent(transfer_id)
                if runinforground:
                    control.progressDialog.close()
                return None
            folder_details = dd_result['content']
            folder_details = sorted(folder_details, key=lambda i: int(i['size']), reverse=True)
            folder_details = [i for i in folder_details if source_utils.is_file_ext_valid(i['link'])]
            filter_list = [i for i in folder_details]

            if pack_select:
                identified_file = source_utils.get_best_match('path', folder_details, source['episode_re'], pack_select)
                stream_link = identified_file.get('link')

            elif len(filter_list) == 1:
                stream_link = filter_list[0]['link']

            elif len(filter_list) >= 1:
                identified_file = source_utils.get_best_match('path', folder_details, source['episode_re'])
                stream_link = identified_file.get('link')

            filter_list = [tfile for tfile in folder_details if 'sample' not in tfile['path'].lower()]

            if len(filter_list) == 1:
                stream_link = filter_list[0]['link']

            if stream_link and self.addtocloud:
                self.add_to_cloud(stream_link)
        else:
            self.delete_torrent(transfer_id)
        if runinforground:
            control.progressDialog.close()
        return stream_link
