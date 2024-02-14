# -*- coding: utf-8 -*-

"""
    Otaku Add-on

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""


import re
import sys
import six
from six.moves import urllib_request, urllib_parse, urllib_error, urllib_response, http_cookiejar
import gzip
import time
import random
import json
from kodi_six import xbmc, xbmcvfs
from resources.lib.ui import control, database

TRANSLATEPATH = xbmcvfs.translatePath if six.PY3 else xbmc.translatePath
CERT_FILE = TRANSLATEPATH('special://xbmc/system/certs/cacert.pem')
_COOKIE_HEADER = "Cookie"
_HEADER_RE = re.compile(r"^([\w\d-]+?)=(.*?)$")


def request(
        url,
        close=True,
        redirect=True,
        error=False,
        verify=True,
        proxy=None,
        post=None,
        headers={},
        mobile=False,
        XHR=False,
        limit=None,
        referer='',
        cookie=None,
        compression=True,
        output='',
        timeout=20,
        jpost=False,
        params=None,
        method=''
):
    try:
        if not url:
            return
        _headers = {}
        if headers:
            _headers.update(headers)
        if _headers.get('verifypeer', '') == 'false':
            verify = False
            _headers.pop('verifypeer')

        handlers = []

        if proxy is not None:
            handlers += [urllib_request.ProxyHandler(
                {'http': '%s' % proxy}), urllib_request.HTTPHandler]
            opener = urllib_request.build_opener(*handlers)
            opener = urllib_request.install_opener(opener)

        if params is not None:
            if isinstance(params, dict):
                params = urllib_parse.urlencode(params)
            url = url + '?' + params

        if output == 'cookie' or output == 'extended' or not close:
            cookies = http_cookiejar.LWPCookieJar()
            handlers += [urllib_request.HTTPHandler(),
                         urllib_request.HTTPSHandler(),
                         urllib_request.HTTPCookieProcessor(cookies)]
            opener = urllib_request.build_opener(*handlers)
            opener = urllib_request.install_opener(opener)

        if output == 'elapsed':
            start_time = time.time() * 1000

        try:
            import platform
            node = platform.uname()[1]
        except BaseException:
            node = ''

        if verify is False and sys.version_info >= (2, 7, 12):
            try:
                import ssl
                ssl_context = ssl._create_unverified_context()
                ssl._create_default_https_context = ssl._create_unverified_context
                ssl_context.set_alpn_protocols(['http/1.1'])
                handlers += [urllib_request.HTTPSHandler(context=ssl_context)]
                opener = urllib_request.build_opener(*handlers)
                opener = urllib_request.install_opener(opener)
            except BaseException:
                pass

        if verify and ((2, 7, 8) < sys.version_info < (2, 7, 12)
                       or node == 'XboxOne'):
            try:
                import ssl
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                ssl_context.set_alpn_protocols(['http/1.1'])
                handlers += [urllib_request.HTTPSHandler(context=ssl_context)]
                opener = urllib_request.build_opener(*handlers)
                opener = urllib_request.install_opener(opener)
            except BaseException:
                pass
        else:
            try:
                import ssl
                ssl_context = ssl.create_default_context(cafile=CERT_FILE)
                ssl_context.set_alpn_protocols(['http/1.1'])
                handlers += [urllib_request.HTTPSHandler(context=ssl_context)]
                opener = urllib_request.build_opener(*handlers)
                opener = urllib_request.install_opener(opener)
            except BaseException:
                pass

        if url.startswith('//'):
            url = 'http:' + url

        if 'User-Agent' in _headers:
            pass
        elif mobile:
            _headers['User-Agent'] = database.get(randommobileagent, 1)
        else:
            _headers['User-Agent'] = database.get(randomagent, 1)

        if 'Referer' in _headers:
            pass
        elif referer:
            _headers['Referer'] = referer

        if 'Accept-Language' not in _headers:
            _headers['Accept-Language'] = 'en-US,en'

        if 'Accept' not in _headers:
            _headers['Accept'] = '*/*'

        if 'X-Requested-With' in _headers:
            pass
        elif XHR:
            _headers['X-Requested-With'] = 'XMLHttpRequest'

        if 'Cookie' in _headers:
            pass
        elif cookie is not None:
            if isinstance(cookie, dict):
                cookie = '; '.join(['{0}={1}'.format(x, y) for x, y in six.iteritems(cookie)])
            _headers['Cookie'] = cookie
        else:
            cpath = urllib_parse.urlparse(url).netloc
            if control.pathExists(control.dataPath + cpath + '.txt'):
                ccookie = retrieve(cpath + '.txt')
                if ccookie:
                    _headers['Cookie'] = ccookie
            elif control.pathExists(control.dataPath + cpath + '.json'):
                cfhdrs = json.loads(retrieve(cpath + '.json'))
                _headers.update(cfhdrs)

        if 'Accept-Encoding' in _headers:
            pass
        elif compression and limit is None:
            _headers['Accept-Encoding'] = 'gzip'

        if redirect is False:
            class NoRedirectHandler(urllib_request.HTTPRedirectHandler):
                def http_error_302(self, req, fp, code, msg, headers):
                    infourl = urllib_response.addinfourl(fp, headers, req.get_full_url())
                    if sys.version_info < (3, 9, 0):
                        infourl.status = code
                        infourl.code = code
                    return infourl
                http_error_300 = http_error_302
                http_error_301 = http_error_302
                http_error_303 = http_error_302
                http_error_307 = http_error_302

            opener = urllib_request.build_opener(NoRedirectHandler())
            urllib_request.install_opener(opener)

            try:
                del _headers['Referer']
            except BaseException:
                pass

        url = byteify(url.replace(' ', '%20'))
        req = urllib_request.Request(url)

        if post is not None:
            if jpost:
                post = json.dumps(post)
                post = post.encode('utf8') if six.PY3 else post
                req = urllib_request.Request(url, post)
                req.add_header('Content-Type', 'application/json')
            else:
                if isinstance(post, dict):
                    post = byteify(post)
                    post = urllib_parse.urlencode(post)
                if len(post) > 0:
                    post = post.encode('utf8') if six.PY3 else post
                    req = urllib_request.Request(url, data=post)
                else:
                    req.get_method = lambda: 'POST'
                    req.has_header = lambda header_name: (
                        header_name == 'Content-type'
                        or urllib_request.Request.has_header(req, header_name)
                    )

        if limit == '0':
            req.get_method = lambda: 'HEAD'

        if method:
            req.get_method = lambda: method

        _add_request_header(req, _headers)

        try:
            response = urllib_request.urlopen(req, timeout=int(timeout))
        except urllib_error.HTTPError as e:
            if error is True:
                response = e
            server = e.info().getheader('Server') if six.PY2 else e.info().get('Server')
            if server and 'cloudflare' in server.lower():
                if e.info().get('Content-Encoding', '').lower() == 'gzip':
                    buf = six.BytesIO(e.read())
                    f = gzip.GzipFile(fileobj=buf)
                    result = f.read()
                    f.close()
                else:
                    result = e.read()
                result = result.decode('latin-1', errors='ignore') if six.PY3 else result.encode('utf-8')
                error_code = e.code
                if error_code == 403 and 'cf-alert-error' in result:
                    import ssl
                    ctx = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2 if six.PY3 else ssl.PROTOCOL_TLSv1_1)
                    ctx.set_alpn_protocols(['http/1.0', 'http/1.1'])
                    handle = [urllib_request.HTTPSHandler(context=ctx)]
                    opener = urllib_request.build_opener(*handle)
                    try:
                        response = opener.open(req, timeout=30)
                    except:
                        if 'return' in error:
                            # Give up
                            return '{}'
                        else:
                            if not error:
                                return '{}'
                elif any(x == error_code for x in [403, 429, 503]) and any(x in result for x in ['__cf_chl_f_tk', '__cf_chl_jschl_tk__=', '/cdn-cgi/challenge-platform/']):
                    url_parsed = urllib_parse.urlparse(url)
                    netloc = '%s://%s/' % (url_parsed.scheme, url_parsed.netloc)
                    if control.getSetting('fs_enable') == 'true':
                        cf_cookie, cf_ua = cfcookie().get(netloc, timeout)
                        if cf_cookie is None:
                            control.log('%s has an unsolvable Cloudflare challenge.' % (netloc))
                            if not error:
                                return '{}'
                        _headers['Cookie'] = cf_cookie
                        _headers['User-Agent'] = cf_ua
                        req = urllib_request.Request(url, data=post)
                        _add_request_header(req, _headers)
                        response = urllib_request.urlopen(req, timeout=int(timeout))
                    else:
                        control.log('%s has a Cloudflare challenge.' % (netloc))
                        if not error:
                            return '{}'
                else:
                    if error is True:
                        return result
                    else:
                        return '{}'
            elif server and 'ddos-guard' in server.lower() and e.code == 403:
                url_parsed = urllib_parse.urlparse(url)
                netloc = '%s://%s/' % (url_parsed.scheme, url_parsed.netloc)
                if control.getSetting('fs_enable') == 'true':
                    ddg_cookie, ddg_ua = ddgcookie().get(netloc, timeout)
                    if ddg_cookie is None:
                        control.log('%s has an unsolvable DDos-Guard challenge.' % (netloc))
                        if not error:
                            return '{}'
                    _headers['Cookie'] = ddg_cookie
                    _headers['User-Agent'] = ddg_ua
                    req = urllib_request.Request(url, data=post)
                    _add_request_header(req, _headers)
                    response = urllib_request.urlopen(req, timeout=int(timeout))
                else:
                    control.log('%s has a DDoS-Guard challenge.' % (netloc))
                    if not error:
                        return '{}'
            elif output == '':
                control.log('Request-HTTPError (%s): %s' % (response.code, url))
                if not error:
                    return '{}'
        except urllib_error.URLError as e:
            response = e
            if output == '':
                control.log('Request-Error (%s): %s' % (e.reason, url))
                if not error:
                    return '{}'

        if output == 'cookie':
            try:
                result = '; '.join(['%s=%s' % (i.name, i.value)
                                    for i in cookies])
            except BaseException:
                pass
            if close:
                response.close()
            return result

        elif output == 'elapsed':
            result = (time.time() * 1000) - start_time
            if close:
                response.close()
            return int(result)

        elif output == 'geturl':
            result = response.url
            if close:
                response.close()
            return result

        elif output == 'headers':
            result = response.headers
            if close:
                response.close()
            return result

        elif output == 'status_code':
            result = response.code
            if close:
                response.close()
            return result

        elif output == 'chunk':
            try:
                content = int(response.headers['Content-Length'])
            except BaseException:
                content = (2049 * 1024)
            if content < (2048 * 1024):
                return
            result = response.read(16 * 1024)
            if close:
                response.close()
            return result

        elif output == 'file_size':
            try:
                content = int(response.headers['Content-Length'])
            except BaseException:
                content = '0'
            response.close()
            return content

        if limit == '0' or limit == 0:
            result = response.read(1 * 1024)
        elif limit is not None:
            result = response.read(int(limit) * 1024)
        else:
            result = response.read(5242880)

        encoding = None
        text_content = False

        if response.headers.get('content-encoding', '').lower() == 'gzip':
            result = gzip.GzipFile(fileobj=six.BytesIO(result)).read()

        content_type = response.headers.get('content-type', '').lower()

        text_content = any(x in content_type for x in ['text', 'json', 'xml', 'mpegurl'])

        if 'charset=' in content_type:
            encoding = content_type.split('charset=')[-1]

        if 'text/vtt' in content_type or url.endswith('.srt') or url.endswith('.vtt'):
            encoding = 'utf8'

        if encoding is None:
            epatterns = [r'<meta\s+http-equiv="Content-Type"\s+content="(?:.+?);\s+charset=(.+?)"',
                         r'xml\s*version.+encoding="([^"]+)']
            for epattern in epatterns:
                epattern = epattern.encode('utf8') if six.PY3 else epattern
                r = re.search(epattern, result, re.IGNORECASE)
                if r:
                    encoding = r.group(1).decode('utf8') if six.PY3 else r.group(1)
                    break

        if encoding is None:
            r = re.search(b'^#EXT', result, re.IGNORECASE)
            if r:
                encoding = 'utf8'

        if encoding is not None:
            result = result.decode(encoding, errors='ignore')
            text_content = True
        elif text_content and encoding is None:
            result = result.decode('latin-1', errors='ignore') if six.PY3 else result
        else:
            control.log('Unknown Page Encoding')

        if output == 'extended':
            try:
                response_headers = dict(
                    [(item[0].title(), item[1]) for item in list(response.info().items())])
            except BaseException:
                response_headers = response.headers
            response_url = response.url
            response_code = str(response.code)
            try:
                cookie = '; '.join(['%s=%s' % (i.name, i.value)
                                    for i in cookies])
            except BaseException:
                pass

            if close:
                response.close()
            return (result, response_code, response_headers, _headers, cookie, response_url)
        else:
            if close:
                response.close()
            return result
    except Exception as e:
        control.log('Request-Error: (%s) => %s' % (str(e), url), 'info')
        return


def _basic_request(url, headers=None, post=None, timeout=60, jpost=False, limit=None):
    try:
        request = urllib_request.Request(url)
        if post is not None:
            if jpost:
                post = json.dumps(post)
                post = post.encode('utf8') if six.PY3 else post
                request = urllib_request.Request(url, post)
                request.add_header('Content-Type', 'application/json')
            else:
                if isinstance(post, dict):
                    post = byteify(post)
                    post = urllib_parse.urlencode(post)
                if len(post) > 0:
                    post = post.encode('utf8') if six.PY3 else post
                    request = urllib_request.Request(url, data=post)
                else:
                    request.get_method = lambda: 'POST'
                    request.has_header = lambda header_name: (
                        header_name == 'Content-type'
                        or urllib_request.Request.has_header(request, header_name)
                    )
        if headers is not None:
            _add_request_header(request, headers)
        response = urllib_request.urlopen(request, timeout=timeout)
        return _get_result(response, limit)
    except BaseException:
        return


def _add_request_header(_request, headers):
    try:
        if six.PY2:
            scheme = _request.get_type()
            host = _request.get_host()
        else:
            scheme = urllib_parse.urlparse(_request.get_full_url()).scheme
            host = _request.host

        referer = headers.get('Referer', '') or '%s://%s/' % (scheme, host)

        _request.add_unredirected_header('Host', host)
        _request.add_unredirected_header('Referer', referer)
        for key in headers:
            _request.add_header(key, headers[key])
    except BaseException:
        return


def _get_result(response, limit=None):
    if limit == '0':
        result = response.read(224 * 1024)
    elif limit:
        result = response.read(int(limit) * 1024)
    else:
        result = response.read(5242880)

    try:
        encoding = response.info().getheader('Content-Encoding')
    except BaseException:
        encoding = None
    if encoding == 'gzip':
        result = gzip.GzipFile(fileobj=six.BytesIO(result)).read()

    return result


def randomagent():
    _agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.8464.47 Safari/537.36 OPR/117.0.8464.47',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.1938.62',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 17.1.2) AppleWebKit/800.6.25 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/117.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36 Vivaldi/6.2.3105.48',
        'Mozilla/5.0 (MacBook Air; M1 Mac OS X 11_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/604.1',
        'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/117.0',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.21 (KHTML, like Gecko) konqueror/4.14.26 Safari/537.21'
    ]
    return random.choice(_agents)


def randommobileagent():
    _mobagents = [
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
        'Mozilla/5.0 (iPad; CPU OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.4 Mobile/15E148 Safari/604.1',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/116.0.5845.177 Mobile/15E148 Safari/604.1',
        'Mozilla/5.0 (Linux; Android 12; motorola edge (2022)) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.88 Mobile Safari/537.36',
        'Mozilla/5.0 (Linux; Android 13; SAMSUNG SM-A546B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/22.0 Chrome/111.0.5563.116 Mobile Safari/537.3',
        'Mozilla/5.0 (Linux; Android 13; V2302A; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/87.0.4280.141 Mobile Safari/537.36 VivoBrowser/14.5.10.2'
    ]
    return random.choice(_mobagents)


def agent():
    return 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36'


def store(ftext, fname):
    fpath = control.dataPath + fname
    if six.PY2:
        with open(fpath, 'w') as f:
            f.write(ftext)
    else:
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(ftext)


def retrieve(fname):
    fpath = control.dataPath + fname
    if control.pathExists(fpath):
        if six.PY2:
            with open(fpath) as f:
                ftext = f.readlines()
        else:
            with open(fpath, encoding='utf-8') as f:
                ftext = f.readlines()
        return '\n'.join(ftext)
    else:
        return None


class cfcookie:
    def __init__(self):
        self.cookie = None
        self.ua = None

    def get(self, netloc, timeout):
        try:
            self.netloc = netloc
            self.timeout = timeout
            self._get_cookie(netloc, timeout)
            if self.cookie is not None:
                cfdata = json.dumps({'Cookie': self.cookie, 'User-Agent': self.ua})
                store(cfdata, urllib_parse.urlparse(netloc).netloc + '.json')
            return (self.cookie, self.ua)
        except Exception as e:
            control.log('%s returned an error. Could not collect tokens - Error: %s.' % (netloc, str(e)))
            return (self.cookie, self.ua)

    def _get_cookie(self, netloc, timeout):
        fs_url = control.getSetting('fs_url')
        fs_timeout = int(control.getSetting('fs_timeout'))
        if not fs_url.startswith('http'):
            control.log('Sorry, malformed flaresolverr url')
            return
        post = {'cmd': 'request.get',
                'url': netloc,
                'returnOnlyCookies': True,
                'maxTimeout': fs_timeout * 1000}
        resp = _basic_request(fs_url, post=post, jpost=True)
        if resp:
            resp = json.loads(resp)
            soln = resp.get('solution')
            if soln.get('status') < 300:
                cookie = '; '.join(['%s=%s' % (i.get('name'), i.get('value')) for i in soln.get('cookies')])
                if 'cf_clearance' in cookie:
                    self.cookie = cookie
                    self.ua = soln.get('userAgent')
                else:
                    control.log('%s returned %s. Could not collect tokens.' % (netloc, repr(resp)))
        else:
            control.log('%s returned %s.' % (netloc, repr(resp)))


class ddgcookie:
    def __init__(self):
        self.cookie = None
        self.ua = None

    def get(self, netloc, timeout):
        try:
            self.netloc = netloc
            self.timeout = timeout
            self._get_cookie(netloc, timeout)
            if self.cookie is not None:
                cfdata = json.dumps({'Cookie': self.cookie, 'User-Agent': self.ua})
                store(cfdata, urllib_parse.urlparse(netloc).netloc + '.json')
            return (self.cookie, self.ua)
        except Exception as e:
            control.log('%s returned an error. Could not collect tokens - Error: %s.' % (netloc, str(e)))
            return (self.cookie, self.ua)

    def _get_cookie(self, netloc, timeout):
        fs_url = control.getSetting('fs_url')
        fs_timeout = int(control.getSetting('fs_timeout'))
        if not fs_url.startswith('http'):
            control.log('Sorry, malformed flaresolverr url')
            return
        post = {'cmd': 'request.get',
                'url': netloc,
                'returnOnlyCookies': True,
                'maxTimeout': fs_timeout * 1000}
        resp = _basic_request(fs_url, post=post, jpost=True)
        if resp:
            resp = json.loads(resp)
            soln = resp.get('solution')
            if soln.get('status') < 300:
                cookie = '; '.join(['%s=%s' % (i.get('name'), i.get('value')) for i in soln.get('cookies') if 'ddg' in i.get('name')])
                if '__ddg2_' in cookie:
                    self.cookie = cookie
                    self.ua = soln.get('userAgent')
                else:
                    control.log('%s returned %s. Could not collect tokens.' % (netloc, repr(resp)))
        else:
            control.log('%s returned %s.' % (netloc, repr(resp)))


def byteify(data, ignore_dicts=False):
    if isinstance(data, six.text_type) and six.PY2:
        return data.encode('utf-8')
    if isinstance(data, list):
        return [byteify(item, ignore_dicts=True) for item in data]
    if isinstance(data, dict) and not ignore_dicts:
        return dict([(byteify(key, ignore_dicts=True), byteify(
            value, ignore_dicts=True)) for key, value in six.iteritems(data)])
    return data


def strip_cookie_url(url):
    url, headers = _strip_url(url)
    if _COOKIE_HEADER in headers.keys():
        del headers[_COOKIE_HEADER]

    return _url_with_headers(url, headers)


def _url_with_headers(url, headers):
    if not len(headers.keys()):
        return url

    headers_arr = ["%s=%s" % (key, urllib_parse.quote_plus(value)) for key, value in
                   six.iteritems(headers)]

    return "|".join([url] + headers_arr)


def _strip_url(url):
    if url.find('|') == -1:
        return (url, {})

    headers = url.split('|')
    target_url = headers.pop(0)
    out_headers = {}
    for h in headers:
        m = _HEADER_RE.findall(h)
        if not len(m):
            continue

        out_headers[m[0][0]] = urllib_parse.unquote_plus(m[0][1])

    return (target_url, out_headers)
