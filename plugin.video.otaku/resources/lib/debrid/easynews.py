# Easynews (Usenet) — search + resolve. HTTP Basic auth; no OAuth/pin flow.
import base64
import re
from urllib.parse import quote

from resources.lib.ui import client, control

_VIDEO_EXTENSIONS = (
    'm4v,3g2,3gp,nsv,tp,ts,ty,pls,rm,rmvb,mpd,ifo,mov,qt,divx,xvid,bivx,vob,nrg,img,iso,udf,pva,wmv,asf,asx,ogm,m2v,avi,bin,dat,mpg,mpeg,mp4,mkv,'
    'mk3d,avc,vp3,svq3,nuv,viv,dv,fli,flv,wpl,xspf,vdr,dvr-ms,xsp,mts,m2t,m2ts,evo,ogv,sdp,avs,rec,url,pxml,vc1,h264,rcv,rss,mpls,mpl,webm,bdmv,bdm,wtv,trp,f4v,pvr,disc'
)
_SEARCH_PARAMS = {
    'st': 'adv', 'sb': 1, 'fex': _VIDEO_EXTENSIONS, 'fty[]': 'VIDEO', 'spamf': 1, 'u': '1', 'gx': 1, 'pno': 1, 'sS': 3,
    's1': 'relevance', 's1d': '-', 's2': 'dsize', 's2d': '-', 's3': 'dtime', 's3d': '-', 'pby': 350,
}
_TIMEOUT = 20.0
_UNRESTRICT_TIMEOUT = 60


class Easynews:
    """Easynews members API (search + download URL finalize)."""

    def __init__(self):
        self.base_url = 'https://members.easynews.com'
        self.search_link = '/2.0/search/solr-search/advanced'
        self.username = control.getSetting('easynews.user') or ''
        self.password = control.getSetting('easynews.password') or ''
        self.moderation = 1 if control.getBool('easynews.moderation') else 0

    def _auth_headers(self):
        raw = f'{self.username}:{self.password}'.encode('utf-8')
        token = base64.b64encode(raw).decode('ascii')
        return {'Authorization': f'Basic {token}'}

    def search(self, query):
        if not self.username or not self.password:
            return []
        params = dict(_SEARCH_PARAMS)
        params['safeO'] = self.moderation
        params['gps'] = query
        url = self.base_url + self.search_link
        try:
            r = client.get(url, headers=self._auth_headers(), params=params, timeout=int(_TIMEOUT))
            if not r or not r.ok:
                return []
            data = r.json()
        except (ValueError, TypeError, AttributeError) as e:
            control.log(f'Easynews search JSON error: {e}', 'warning')
            return []
        except Exception as e:
            control.log(f'Easynews search failed: {e}', 'error')
            return []
        return self._process_files(data) if isinstance(data, dict) else []

    def _process_files(self, files):
        down_url = files.get('downURL')
        dl_farm = files.get('dlFarm')
        dl_port = files.get('dlPort')
        rows = files.get('data', [])
        if not (down_url and dl_farm and dl_port and rows):
            return []

        out = []
        for item in rows:
            try:
                post_hash, _sz, post_title, ext, duration = item['0'], item['4'], item['10'], item['11'], item['14']
                language = item.get('alangs') or ''
                if 'type' in item and item['type'].upper() != 'VIDEO':
                    continue
                if item.get('virus'):
                    continue
                if re.match(r'^\d+s', duration) or re.match(r'^[0-5]m', duration):
                    continue
                path = '/%s/%s/%s%s/%s%s' % (dl_farm, dl_port, post_hash, ext, post_title, ext)
                url_dl = down_url + quote(path)
                display_name = post_title + ext if ext.startswith('.') else '%s.%s' % (post_title, ext)
                out.append({
                    'url_dl': url_dl,
                    'name': display_name,
                    'rawSize': int(item.get('rawSize', 0)),
                    'language': language,
                })
            except Exception as e:
                control.log(f'Easynews row parse: {e}', 'warning')
        return out

    def unrestrict_link(self, url_dl):
        """Follow Easynews download URL with auth; return final stream URL (same pattern as POV)."""
        if not url_dl or not self.username or not self.password:
            return None
        try:
            # limit=1024 → read up to 1024 KiB (enough to settle redirects); extended output carries final URL.
            result = client.request(
                url_dl,
                headers=self._auth_headers(),
                timeout=int(_UNRESTRICT_TIMEOUT),
                limit=1024,
                output='extended',
                use_session=True,
            )
            if not result or not isinstance(result, tuple) or len(result) < 6:
                return None
            content, status_code, _resp_headers, _req_headers, _cookie, response_url = result
            try:
                code = int(status_code)
            except (TypeError, ValueError):
                code = 0
            if code >= 400:
                control.log(f'Easynews resolve HTTP {code}', 'warning')
                return None
            if content and response_url:
                return response_url
        except Exception as e:
            control.log(f'Easynews resolve failed: {e}', 'error')
        return None

    def resolve_single_magnet(self, hash_, magnet, episode, pack_select, filename=None):
        return None

    def resolve_cloud(self, source, pack_select):
        return None

    def resolve_hoster(self, magnet, episode, pack_select):
        return None

    def resolve_uncached_source(self, source, runinbackground, runinforground, pack_select):
        control.ok_dialog(control.ADDON_NAME, control.lang(30477))
        return None

    def verify_login(self):
        """Lightweight authenticated search; returns True if HTTP 200 and JSON body."""
        user = control.getSetting('easynews.user') or ''
        pwd = control.getSetting('easynews.password') or ''
        if not user or not pwd:
            return False
        self.username = user
        self.password = pwd
        params = dict(_SEARCH_PARAMS)
        params['safeO'] = 1 if control.getBool('easynews.moderation') else 0
        params['gps'] = 'a'
        url = self.base_url + self.search_link
        try:
            r = client.get(url, headers=self._auth_headers(), params=params, timeout=15)
            if not r or not r.ok:
                return False
            data = r.json()
            return isinstance(data, dict)
        except Exception:
            return False

    def auth(self):
        """No OAuth: confirm username/password against Easynews search API and set auth.status."""
        user = control.getSetting('easynews.user') or ''
        pwd = control.getSetting('easynews.password') or ''
        if not user or not pwd:
            control.setSetting('easynews.auth.status', '')
            control.ok_dialog(control.ADDON_NAME, control.lang(30482))
            return
        if self.verify_login():
            control.setSetting('easynews.auth.status', control.lang(30479))
            control.ok_dialog(control.ADDON_NAME, f'Easynews: {control.lang(30084)}')
        else:
            control.setSetting('easynews.auth.status', control.lang(30483))
            control.ok_dialog(f'{control.ADDON_NAME}: Easynews', control.lang(30483))
