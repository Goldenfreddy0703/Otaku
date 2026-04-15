import time
import xbmcgui
from resources.lib.ui import client, control, source_utils


class EasyDebrid:
    def __init__(self):
        # Try to get the token from settings; if not set, use the provided API key.
        self.token = control.getSetting('easydebrid.token')
        self.base_url = "https://easydebrid.com/api/v1"

    def headers(self):
        return {
            'Authorization': f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def auth(self):
        self.token = control.input_dialog("Enter API KEY for EasyDebrid:", self.token, xbmcgui.INPUT_ALPHANUM)
        control.setSetting('easydebrid.token', self.token)
        auth_done = self.status()
        if not auth_done:
            control.ok_dialog(f'{control.ADDON_NAME}: EasyDebrid Auth', "Invalid API KEY!")

    def status(self):
        url = f"{self.base_url}/user/details"
        # Ensure JSON posting if needed; here we use a GET so no post data
        r = client.get(url, headers=self.headers())
        resp = r.json() if r else {}
        if resp and "id" in resp:
            control.setSetting('easydebrid.username', str(resp.get('id')))
            current_time = int(time.time())
            paid_until = int(resp.get('paid_until', 0))
            auth_status = "Premium" if paid_until > current_time else "Expired"
            control.setSetting('easydebrid.auth.status', auth_status)
            control.ok_dialog(control.ADDON_NAME, f'EasyDebrid {control.lang(30084)}')
        return resp and "id" in resp

    def resolve_hoster(self, endpoint, episode, pack_select):
        """
        Generate a debrid link using /link/generate.
        If pack_select is True and multiple files are returned,
        use source_utils.get_best_match to let the user select the best match.
        """
        url = f"{self.base_url}/link/generate"
        data = {"url": endpoint}
        r = client.post(url, json_data=data, headers=self.headers())
        resp = r.json() if r else {}

        files = resp.get('files')
        if isinstance(files, list) and episode:
            # Always use get_best_match for episode matching
            best_match = source_utils.get_best_match('filename', files, episode, pack_select)
            if best_match and best_match.get('url'):
                return best_match['url']
            # If no match, get_best_match will handle user selection or return empty
            return None
        elif isinstance(files, list) and files and files[0].get('url'):
            # No episode provided, fallback to first file
            return files[0]['url']
        return files or resp

    def lookup_link(self, endpoint):
        """
        Lookup cached state for given magnet URLs.
        Accepts a single magnet URL or a list of URLs.
        """
        if not isinstance(endpoint, list):
            endpoint = [endpoint]
        url = f"{self.base_url}/link/lookup"
        data = {"urls": endpoint}
        r = client.post(url, json_data=data, headers=self.headers())
        resp = r.json() if r else {}
        return resp

    def resolve_single_magnet(self, hash_, magnet, episode, pack_select, filename=None):
        """
        For compatibility with our add-on interface.
        Since EasyDebrid does not support adding a magnet,
        resolve its link by generating a debrid link for the provided magnet URL.
        """
        return self.resolve_hoster(magnet, episode, pack_select)

    def resolve_cloud(self, source, pack_select):
        # EasyDebrid does not support cloud/torrent caching.
        pass

    def resolve_uncached_source(self, source, runinbackground, runinforground, pack_select):
        # Uncached sources are not supported by EasyDebrid.
        control.ok_dialog(control.ADDON_NAME, "EasyDebrid does not support uncached sources.")
        return None
