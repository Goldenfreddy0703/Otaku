# -*- coding: utf-8 -*-

import time
import json
from six.moves import urllib_parse
from resources.lib.ui import source_utils, control, database, client


class Premiumize:

    def __init__(self):
        self.client_id = "855400527"
        # self.client_secret = ""
        self.headers = {
            'Authorization': 'Bearer {}'.format(control.getSetting('premiumize.token'))
        }

    def auth(self):
        data = {'client_id': self.client_id, 'response_type': 'device_code'}
        token = client.request('https://www.premiumize.me/token', post=data)
        token = json.loads(token)
        expiry = token['expires_in']
        token_ttl = token['expires_in']
        token_interval = token['interval']
        poll_again = True
        success = False
        control.copy2clip(token['user_code'])
        control.progressDialog.create(
            control.ADDON_NAME,
            control.lang(30100).format(control.colorString(token['verification_uri'])) + '[CR]'
            + control.lang(30101).format(control.colorString(token['user_code'])) + '[CR]'
            + control.lang(30102)
        )
        control.progressDialog.update(0)

        while poll_again and not token_ttl <= 0 and not control.progressDialog.iscanceled():
            time.sleep(token_interval)
            token_ttl -= int(token_interval)
            poll_again, success = self.poll_token(token['device_code'])
            progress_percent = 100 - int((float((expiry - token_ttl) / expiry) * 100))
            control.progressDialog.update(progress_percent)

        control.progressDialog.close()

        if success:
            control.ok_dialog(control.ADDON_NAME, 'Premiumize ' + control.lang(30103))

    def poll_token(self, device_code):
        data = {'client_id': self.client_id, 'code': device_code, 'grant_type': 'device_code'}
        token = client.request('https://www.premiumize.me/token', post=data, error=True)
        control.log('token is %s' % repr(token), level='info')
        token = json.loads(token)

        if 'error' in token:
            if token['error'] == "access_denied":
                return False, False
            return True, False

        control.setSetting('premiumize.token', token['access_token'])
        self.headers['Authorization'] = 'Bearer {}'.format(token['access_token'])

        account_info = self.account_info()
        control.setSetting('premiumize.username', account_info['customer_id'])

        return False, True

    def get_url(self, url):
        if self.headers['Authorization'] == 'Bearer ':
            return None
        url = "https://www.premiumize.me/api{}".format(url)
        req = client.request(url, timeout=10, headers=self.headers, error=True)
        return json.loads(req)

    def post_url(self, url, data):
        if self.headers['Authorization'] == 'Bearer ':
            return None
        url = "https://www.premiumize.me/api{}".format(url)
        req = client.request(url, headers=self.headers, post=data, timeout=10, error=True)
        return json.loads(req)

    def account_info(self):
        url = "/account/info"
        response = self.get_url(url)
        return response

    def list_folder(self, folderID):
        url = "/folder/list"
        postData = {'id': folderID} if folderID else ''
        response = self.post_url(url, postData)
        return response['content']

    def list_folder_all(self, folderID):
        url = "/item/listall"
        response = self.get_url(url)
        return response['files']

    def hash_check(self, hashList):
        url = '/cache/check'
        # postData = {'items[]': hashList}
        hashString = '&'.join(['items[]=' + x for x in hashList])
        # response = self.post_url(url, postData)
        response = self.get_url('{0}?{1}'.format(url, urllib_parse.quote(hashString, '=&')))
        return response

    def item_details(self, itemID):
        url = "/item/details"
        postData = {'id': itemID}
        return self.post_url(url, postData)

    def create_transfer(self, src, folderID=0):
        postData = {'src': src, 'folder_id': folderID}
        url = "/transfer/create"
        return self.post_url(url, postData)

    def direct_download(self, src):
        postData = {'src': src}
        url = '/transfer/directdl'
        return self.post_url(url, postData)

    def list_transfers(self):
        url = "/transfer/list"
        postData = {}
        return self.post_url(url, postData)

    def delete_transfer(self, id):
        url = "/transfer/delete"
        postData = {'id': id}
        return self.post_url(url, postData)

    def get_used_space(self):
        info = self.account_info()
        used_space = int(((info['space_used'] / 1024) / 1024) / 1024)
        return used_space

    def hosterCacheCheck(self, source_list):
        post_data = {'items[]': source_list}
        return self.post_url('/cache/check', data=post_data)

    def updateRelevantHosters(self):
        hoster_list = database.get(self.post_url, 1, '/services/list', {})
        return hoster_list

    def resolve_hoster(self, source):

        directLink = self.direct_download(source)
        if directLink['status'] == 'success':
            stream_link = directLink['location']
        else:
            stream_link = None

        return stream_link

    def folder_streams(self, folderID):

        files = self.list_folder(folderID)
        returnFiles = []
        for i in files:
            if i['type'] == 'file':
                if i['transcode_status'] == 'finished':
                    returnFiles.append({'name': i['name'], 'link': i['stream_link'], 'type': 'file'})
                else:
                    for extension in source_utils.COMMON_VIDEO_EXTENSIONS:
                        if i['link'].endswith(extension):
                            returnFiles.append({'name': i['name'], 'link': i['link'], 'type': 'file'})
                            break
        return returnFiles

    def internal_folders(self, folderID):
        folders = self.list_folder(folderID)
        returnFolders = []
        for i in folders:
            if i['type'] == 'folder':
                returnFolders.append({'name': i['name'], 'id': i['id'], 'type': 'folder'})
        return returnFolders

    def resolve_single_magnet(self, hash_, magnet, episode=''):

        folder_details = self.direct_download(magnet)['content']
        folder_details = sorted(folder_details, key=lambda i: int(i['size']), reverse=True)
        folder_details = [i for i in folder_details if source_utils.is_file_ext_valid(i['link'])]

        filter_list = [i for i in folder_details]

        if len(filter_list) == 1:
            stream_link = self._fetch_transcode_or_standard(filter_list[0])
            self._handle_add_to_cloud(magnet)
            return stream_link

        elif len(filter_list) >= 5:
            identified_file = source_utils.get_best_match('path', folder_details, episode)

            stream_link = self._fetch_transcode_or_standard(identified_file)
            return stream_link

        filter_list = [tfile for tfile in folder_details if 'sample' not in tfile['path'].lower()]

        if len(filter_list) == 1:
            stream_link = self._fetch_transcode_or_standard(filter_list[0])
            self._handle_add_to_cloud(magnet)
            return stream_link

    def resolve_magnet(self, magnet, args, torrent, pack_select):

        if 'showInfo' not in args:
            return self._single_magnet_resolve(magnet, args)

        try:

            folder_details = self.direct_download(magnet)['content']

            if pack_select is not False and pack_select is not None:
                return self.user_select(folder_details)

            folder_details = source_utils.clear_extras_by_string(args, 'extras', folder_details)
            folder_details = source_utils.clear_extras_by_string(args, 'specials', folder_details)
            folder_details = source_utils.clear_extras_by_string(args, 'featurettes', folder_details)
            folder_details = source_utils.clear_extras_by_string(args, 'deleted scenes', folder_details)
            folder_details = source_utils.clear_extras_by_string(args, 'sample', folder_details)

            folder_details = [i for i in folder_details if source_utils.is_file_ext_valid(i['link'])]

            identified_file = source_utils.get_best_match('path', folder_details, args)

            stream_link = self._fetch_transcode_or_standard(identified_file)

        except:
            import traceback
            traceback.print_exc()
            return

        if stream_link is not None:
            self._handle_add_to_cloud(magnet)

        return stream_link

    def _handle_add_to_cloud(self, magnet):
        pass
        # if tools.getSetting('premiumize.addToCloud') == 'true':
        #     transfer = self.create_transfer(magnet)
        #     database.add_premiumize_transfer(transfer['id'])

    def _fetch_transcode_or_standard(self, file_object):
        # if tools.getSetting('premiumize.transcoded') == 'true' and \
        #         file_object['transcode_status'] == 'finished':
        #     return file_object['stream_link']
        # else:
        return file_object['link']

    def user_select(self, content):
        pass
        # display_list = []
        # for i in content:
        #     if any(i['path'].endswith(ext) for ext in source_utils.COMMON_VIDEO_EXTENSIONS):
        #         display_list.append(i)

        # selection = tools.showDialog.select('{}: {}'.format(tools.addonName, tools.lang(40297)),
        #                                     [i['path'] for i in display_list])
        # if selection == -1:
        #     return None

        # selection = content[selection]

        # if tools.getSetting('premiumize.transcoded') == 'true':
        #     if selection['transcode_status'] == 'finished':

        #         return selection['stream_link']
        #     else:
        #         pass

        # return selection['link']

    def get_hosters(self, hosters):

        host_list = database.get(self.updateRelevantHosters, 1)
        if host_list is None:
            host_list = self.updateRelevantHosters()

        if host_list is not None:
            hosters['premium']['premiumize'] = [(i, i.split('.')[0]) for i in host_list['directdl']]
        else:
            hosters['premium']['premiumize'] = []
