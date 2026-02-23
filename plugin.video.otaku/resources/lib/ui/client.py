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

import gzip
import http.client
import io
import json
import random
import re
import ssl
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
import urllib.response
import http.cookiejar
import xbmcvfs

from resources.lib.ui import control

TRANSLATEPATH = xbmcvfs.translatePath
CERT_FILE = TRANSLATEPATH('special://xbmc/system/certs/cacert.pem')
_COOKIE_HEADER = "Cookie"
_HEADER_RE = re.compile(r"^([\w\d-]+?)=(.*?)$")

# Session-like storage for cookies and connection reuse with automatic cleanup
_session_cookies = {}
_session_openers = {}
_session_timestamps = {}
_SESSION_TIMEOUT = 600  # 10 minutes

# In-memory User-Agent cache to avoid settings DB lookups
_cached_useragent = None
_cached_useragent_time = 0
_cached_mobile_useragent = None
_cached_mobile_useragent_time = 0
_USERAGENT_CACHE_TTL = 3600  # 1 hour


def _cleanup_old_sessions():
    """Clean up sessions older than timeout to prevent memory leaks"""
    import time
    current_time = time.time()
    expired_keys = [k for k, v in _session_timestamps.items() if current_time - v > _SESSION_TIMEOUT]
    for key in expired_keys:
        _session_cookies.pop(key, None)
        _session_openers.pop(key, None)
        _session_timestamps.pop(key, None)
    # Also clean up stale keep-alive connections
    _keepalive_pool.cleanup()


# ==================== True HTTP Keep-Alive Connection Pool ====================
import threading as _threading


class _KeepAlivePool:
    """Thread-safe pool of persistent http.client connections keyed by (host, port, scheme).
    Reuses TCP+TLS sockets so repeated requests to the same host skip the handshake."""

    def __init__(self, max_per_host=6, idle_timeout=120):
        self._lock = _threading.Lock()
        self._pool = {}          # key -> list of (conn, last_used_time)
        self._max = max_per_host
        self._idle = idle_timeout
        self._ssl_ctx = None     # lazily created

    def _get_ssl_context(self):
        if self._ssl_ctx is None:
            try:
                self._ssl_ctx = ssl.create_default_context(cafile=CERT_FILE)
            except Exception:
                self._ssl_ctx = ssl.create_default_context()
            self._ssl_ctx.set_alpn_protocols(['http/1.1'])
        return self._ssl_ctx

    def _key(self, parsed):
        return (parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80), parsed.scheme)

    def _make_conn(self, key):
        host, port, scheme = key
        if scheme == 'https':
            conn = http.client.HTTPSConnection(host, port, timeout=20, context=self._get_ssl_context())
        else:
            conn = http.client.HTTPConnection(host, port, timeout=20)
        return conn

    def acquire(self, parsed):
        """Get a live connection from the pool or create a new one."""
        key = self._key(parsed)
        now = time.time()
        with self._lock:
            conns = self._pool.get(key, [])
            while conns:
                conn, ts = conns.pop(0)
                if now - ts < self._idle:
                    return conn
                # Too old, close it
                try:
                    conn.close()
                except Exception:
                    pass
        return self._make_conn(key)

    def release(self, parsed, conn):
        """Return a connection to the pool for reuse."""
        key = self._key(parsed)
        with self._lock:
            conns = self._pool.setdefault(key, [])
            if len(conns) < self._max:
                conns.append((conn, time.time()))
            else:
                try:
                    conn.close()
                except Exception:
                    pass

    def discard(self, parsed, conn):
        """Discard a broken connection."""
        try:
            conn.close()
        except Exception:
            pass

    def cleanup(self):
        """Remove idle connections."""
        now = time.time()
        with self._lock:
            for key in list(self._pool.keys()):
                conns = self._pool[key]
                alive = []
                for conn, ts in conns:
                    if now - ts < self._idle:
                        alive.append((conn, ts))
                    else:
                        try:
                            conn.close()
                        except Exception:
                            pass
                if alive:
                    self._pool[key] = alive
                else:
                    del self._pool[key]


_keepalive_pool = _KeepAlivePool()


def _fast_request(url, headers, post_data=None, method='GET', timeout=20, jpost=False):
    """
    Fast-path HTTP request using keep-alive connection pool.
    Returns (body_bytes, status_code, response_headers_dict, url) or None on error.
    Handles gzip decompression and UTF-8 decoding.
    """
    parsed = urllib.parse.urlparse(url)
    path = parsed.path or '/'
    if parsed.query:
        path = f'{path}?{parsed.query}'

    conn = _keepalive_pool.acquire(parsed)
    try:
        conn.timeout = int(timeout)
        body = None
        if post_data is not None:
            if jpost:
                body = json.dumps(post_data).encode('utf-8')
            elif isinstance(post_data, dict):
                body = urllib.parse.urlencode(post_data).encode('utf-8')
            elif isinstance(post_data, str):
                body = post_data.encode('utf-8')
            elif isinstance(post_data, bytes):
                body = post_data

        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
        status = resp.status
        resp_headers = {h[0]: h[1] for h in resp.getheaders()}

        # Decompress gzip
        if resp_headers.get('Content-Encoding', '').lower() == 'gzip':
            raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()

        # Decode to string
        ct = resp_headers.get('Content-Type', '').lower()
        if any(x in ct for x in ['text', 'json', 'xml', 'html', 'javascript']):
            try:
                result = raw.decode('utf-8')
            except UnicodeDecodeError:
                result = raw.decode('latin-1', errors='ignore')
        else:
            result = raw

        # Return connection to pool if all is well
        _keepalive_pool.release(parsed, conn)
        return result, str(status), resp_headers, url

    except Exception:
        _keepalive_pool.discard(parsed, conn)
        return None


def _get_cached_useragent(mobile=False):
    """Get cached user agent from memory to avoid database lookups"""
    import time
    global _cached_useragent, _cached_useragent_time, _cached_mobile_useragent, _cached_mobile_useragent_time

    current_time = time.time()

    # Check in-memory cache
    if mobile:
        if _cached_mobile_useragent and (current_time - _cached_mobile_useragent_time < _USERAGENT_CACHE_TTL):
            return _cached_mobile_useragent
    else:
        if _cached_useragent and (current_time - _cached_useragent_time < _USERAGENT_CACHE_TTL):
            return _cached_useragent

    # Generate new user agent and cache in memory
    agent = randommobileagent() if mobile else randomagent()

    if mobile:
        _cached_mobile_useragent = agent
        _cached_mobile_useragent_time = current_time
    else:
        _cached_useragent = agent
        _cached_useragent_time = current_time

    return agent


class Response:
    """
    Requests-like Response object to match requests module API

    Attributes:
        text: Response content as string
        content: Response content as bytes
        status_code: HTTP status code
        headers: Response headers dict
        url: Final URL after redirects
        cookies: Response cookies dict
        ok: True if status_code < 400
    """
    def __init__(self, content, status_code=200, headers=None, url='', cookies=None, is_binary=False):
        self._raw_content = content
        self._is_binary = is_binary
        self.status_code = status_code
        self.headers = headers or {}
        self.url = url
        self.cookies = cookies or {}
        self.ok = 200 <= status_code < 400

    @property
    def text(self):
        """Response content as string"""
        if isinstance(self._raw_content, bytes):
            try:
                return self._raw_content.decode('utf-8', errors='ignore')
            except:
                return self._raw_content.decode('latin-1', errors='ignore')
        return self._raw_content or ''

    @property
    def content(self):
        """Response content as bytes"""
        if isinstance(self._raw_content, str):
            return self._raw_content.encode('utf-8', errors='ignore')
        return self._raw_content or b''

    def json(self):
        """Parse response content as JSON"""
        try:
            return json.loads(self.text)
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"Invalid JSON response: {str(e)}")

    def __bool__(self):
        """Allow truthiness check like: if response:"""
        return self._raw_content is not None and self.ok

    def __repr__(self):
        return f"<Response [{self.status_code}]>"


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
        method='',
        use_session=False,
        tls_version=None
):
    try:
        if not url:
            return

        # Clean up old sessions periodically (1 in 20 requests)
        if random.randint(1, 20) == 1:
            _cleanup_old_sessions()

        # Initialize response to None to avoid UnboundLocalError
        response = None

        _headers = {}
        if headers:
            _headers.update(headers)
        if _headers.get('verifypeer', '') == 'false':
            verify = False
            _headers.pop('verifypeer')

        # Parse domain for session management
        uri = urllib.parse.urlparse(url)
        domain = uri.scheme + '://' + uri.netloc

        # === FAST PATH: use keep-alive pool for session requests without special features ===
        _can_fast = (
            use_session
            and proxy is None
            and redirect is not False
            and tls_version is None
            and verify is True
            and output in ('', 'extended')
            and limit is None
        )
        if _can_fast:
            # Build minimal headers
            if params is not None:
                if isinstance(params, dict):
                    params = urllib.parse.urlencode(params)
                url = url + '?' + params

            if 'User-Agent' not in _headers:
                _headers['User-Agent'] = _get_cached_useragent(mobile=mobile)
            if 'Accept-Language' not in _headers:
                _headers['Accept-Language'] = 'en-US,en'
            if 'Accept' not in _headers:
                _headers['Accept'] = '*/*'
            if XHR and 'X-Requested-With' not in _headers:
                _headers['X-Requested-With'] = 'XMLHttpRequest'
            if cookie is not None and 'Cookie' not in _headers:
                if isinstance(cookie, dict):
                    cookie = '; '.join([f'{x}={y}' for x, y in cookie.items()])
                _headers['Cookie'] = cookie
            elif 'Cookie' not in _headers and domain in _session_cookies:
                _headers['Cookie'] = _session_cookies[domain]
            if compression and 'Accept-Encoding' not in _headers:
                _headers['Accept-Encoding'] = 'gzip'
            if referer and 'Referer' not in _headers:
                _headers['Referer'] = referer
            if jpost and 'Content-Type' not in _headers:
                _headers['Content-Type'] = 'application/json'
            # Connection keep-alive header
            _headers['Connection'] = 'keep-alive'

            http_method = method or ('POST' if post is not None else 'GET')
            fast = _fast_request(url, _headers, post_data=post, method=http_method, timeout=timeout, jpost=jpost)

            if fast is not None:
                result, status_code, resp_headers, resp_url = fast
                # Store session cookies if present
                if 'Set-Cookie' in resp_headers:
                    _session_cookies[domain] = resp_headers['Set-Cookie']
                    _session_timestamps[domain] = time.time()

                if output == 'extended':
                    cookie_str = _session_cookies.get(domain, '')
                    return (result, status_code, resp_headers, _headers, cookie_str, resp_url)
                else:
                    return result
            # If fast path failed (connection error), fall through to urllib path
            control.log(f'Fast-path failed for {url}, falling back to urllib')

        handlers = []

        if proxy is not None:
            handlers += [urllib.request.ProxyHandler(
                {'http': '%s' % proxy}), urllib.request.HTTPHandler]
            opener = urllib.request.build_opener(*handlers)
            opener = urllib.request.install_opener(opener)

        if params is not None:
            if isinstance(params, dict):
                params = urllib.parse.urlencode(params)
            url = url + '?' + params

        if output == 'cookie' or output == 'extended' or not close:
            cookies = http.cookiejar.LWPCookieJar()
            handlers += [urllib.request.HTTPHandler(),
                         urllib.request.HTTPSHandler(),
                         urllib.request.HTTPCookieProcessor(cookies)]
            opener = urllib.request.build_opener(*handlers)
            opener = urllib.request.install_opener(opener)

        if output == 'elapsed':
            start_time = time.time() * 1000

        try:
            import platform
            node = platform.uname()[1]
        except BaseException:
            node = ''

        # Enhanced SSL/TLS handling with multiple protocol support (WNT2-style)
        ssl_context_created = False

        # TLS version override for Cloudflare bypass (like WNT2's TLS adapters)
        if tls_version:
            try:
                if tls_version == 'TLSv1_1':
                    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_1)
                elif tls_version == 'TLSv1_2':
                    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
                else:
                    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS)

                ssl_context.check_hostname = False if not verify else True
                ssl_context.verify_mode = ssl.CERT_NONE if not verify else ssl.CERT_REQUIRED
                ssl_context.set_alpn_protocols(['http/1.1'])
                handlers += [urllib.request.HTTPSHandler(context=ssl_context)]
                ssl_context_created = True
                control.log(f"Using TLS version: {tls_version}")
            except Exception as e:
                control.log(f"TLS override failed: {str(e)}")

        if not ssl_context_created:
            if verify is False and sys.version_info >= (2, 7, 12):
                try:
                    ssl_context = ssl._create_unverified_context()
                    ssl._create_default_https_context = ssl._create_unverified_context
                    ssl_context.set_alpn_protocols(['http/1.1'])
                    handlers += [urllib.request.HTTPSHandler(context=ssl_context)]
                    ssl_context_created = True
                except BaseException:
                    pass

            if not ssl_context_created and verify and ((2, 7, 8) < sys.version_info < (2, 7, 12)
                                                       or node == 'XboxOne'):
                try:
                    ssl_context = ssl.create_default_context()
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE
                    ssl_context.set_alpn_protocols(['http/1.1'])
                    handlers += [urllib.request.HTTPSHandler(context=ssl_context)]
                    ssl_context_created = True
                except BaseException:
                    pass
            elif not ssl_context_created:
                try:
                    ssl_context = ssl.create_default_context(cafile=CERT_FILE)
                    ssl_context.set_alpn_protocols(['http/1.1'])
                    handlers += [urllib.request.HTTPSHandler(context=ssl_context)]
                    ssl_context_created = True
                except BaseException:
                    pass

        # Build opener with handlers
        if handlers:
            opener = urllib.request.build_opener(*handlers)
            if use_session:
                # Store opener for session reuse with timestamp
                _session_openers[domain] = opener
                _session_timestamps[domain] = time.time()
            else:
                urllib.request.install_opener(opener)

        if url.startswith('//'):
            url = 'http:' + url

        if 'User-Agent' in _headers:
            pass
        elif mobile:
            _headers['User-Agent'] = _get_cached_useragent(mobile=True)
        else:
            _headers['User-Agent'] = _get_cached_useragent(mobile=False)

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
                cookie = '; '.join(['{0}={1}'.format(x, y) for x, y in cookie.items()])
            _headers['Cookie'] = cookie
        else:
            # Check for session cookies first
            if use_session and domain in _session_cookies:
                _headers['Cookie'] = _session_cookies[domain]
            else:
                cpath = urllib.parse.urlparse(url).netloc
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
            class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
                def http_error_302(self, req, fp, code, msg, headers):
                    infourl = urllib.response.addinfourl(fp, headers, req.full_url)
                    if sys.version_info < (3, 9, 0):
                        infourl.status = code
                        infourl.code = code
                    return infourl
                http_error_300 = http_error_302
                http_error_301 = http_error_302
                http_error_303 = http_error_302
                http_error_307 = http_error_302

            opener = urllib.request.build_opener(NoRedirectHandler())
            urllib.request.install_opener(opener)

        url = byteify(url.replace(' ', '%20'))
        req = urllib.request.Request(url)

        if post is not None:
            if jpost:
                post = json.dumps(post)
                post = post.encode('utf8')
                req = urllib.request.Request(url, post)
                req.add_header('Content-Type', 'application/json')
            else:
                if isinstance(post, dict):
                    post = byteify(post)
                    post = urllib.parse.urlencode(post)
                if len(post) > 0:
                    post = post.encode('utf8')
                    req = urllib.request.Request(url, data=post)
                else:
                    req.get_method = lambda: 'POST'
                    req.has_header = lambda header_name: (
                        header_name == 'Content-type'
                        or urllib.request.Request.has_header(req, header_name)
                    )

        if limit == '0':
            req.get_method = lambda: 'HEAD'

        if method:
            req.get_method = lambda: method

        _add_request_header(req, _headers)

        try:
            # Use session opener if available
            if use_session and domain in _session_openers:
                response = _session_openers[domain].open(req, timeout=int(timeout))
            else:
                response = urllib.request.urlopen(req, timeout=int(timeout))
        except urllib.error.HTTPError as e:
            if error is True:
                response = e
            server = e.info().get('Server')
            if server and 'cloudflare' in server.lower():
                if e.info().get('Content-Encoding', '').lower() == 'gzip':
                    buf = io.BytesIO(e.read())
                    f = gzip.GzipFile(fileobj=buf)
                    result = f.read()
                    f.close()
                else:
                    result = e.read()
                result = result.decode('latin-1', errors='ignore')
                error_code = e.code

                # Enhanced Cloudflare 403 handling with TLS retry (WNT2-style)
                if error_code == 403 and 'cf-alert-error' in result:
                    control.log(f"Cloudflare 403 detected for {url}, trying TLS 1.2 bypass")
                    # Try TLS 1.2 first, then TLS 1.1 (like WNT2's adapter approach)
                    for tls_ver in ['TLSv1_2', 'TLSv1_1']:
                        try:
                            control.log(f"Attempting {tls_ver} bypass")
                            retry_response = request(
                                url,
                                close=close,
                                redirect=redirect,
                                error=True,
                                verify=verify,
                                post=post,
                                headers=_headers,
                                timeout=timeout,
                                tls_version=tls_ver,
                                use_session=use_session
                            )
                            if retry_response:
                                control.log(f"{tls_ver} bypass successful")
                                return retry_response
                        except Exception as retry_error:
                            control.log(f"{tls_ver} bypass failed: {str(retry_error)}")
                            continue

                    # If TLS retries fail, give up
                    control.log("All TLS bypass attempts failed")
                    if not error:
                        return None

                elif any(x == error_code for x in [403, 429, 503]) and any(x in result for x in ['__cf_chl_f_tk', '__cf_chl_jschl_tk__=', '/cdn-cgi/challenge-platform/']):
                    url_parsed = urllib.parse.urlparse(url)
                    netloc = '%s://%s/' % (url_parsed.scheme, url_parsed.netloc)
                    if control.getBool('fs_enable'):
                        cf_cookie, cf_ua = cfcookie().get(netloc, timeout)
                        if cf_cookie is None:
                            control.log('%s has an unsolvable Cloudflare challenge.' % (netloc))
                            if not error:
                                return None
                        _headers['Cookie'] = cf_cookie
                        _headers['User-Agent'] = cf_ua
                        req = urllib.request.Request(url, data=post)
                        _add_request_header(req, _headers)
                        response = urllib.request.urlopen(req, timeout=int(timeout))
                    else:
                        control.log('%s has a Cloudflare challenge.' % (netloc))
                        if not error:
                            return None
                else:
                    if error is True:
                        return result
                    else:
                        return None
            elif server and 'ddos-guard' in server.lower() and e.code == 403:
                url_parsed = urllib.parse.urlparse(url)
                netloc = '%s://%s/' % (url_parsed.scheme, url_parsed.netloc)
                if control.getBool('fs_enable'):
                    ddg_cookie, ddg_ua = ddgcookie().get(netloc, timeout)
                    if ddg_cookie is None:
                        control.log('%s has an unsolvable DDos-Guard challenge.' % (netloc))
                        if not error:
                            return None
                    _headers['Cookie'] = ddg_cookie
                    _headers['User-Agent'] = ddg_ua
                    req = urllib.request.Request(url, data=post)
                    _add_request_header(req, _headers)
                    response = urllib.request.urlopen(req, timeout=int(timeout))
                else:
                    control.log('%s has a DDoS-Guard challenge.' % (netloc))
                    if not error:
                        return None
            elif output == '':
                control.log('Request-HTTPError (%s): %s' % (e.code, url))
                if not error:
                    return None
        except urllib.error.URLError as e:
            if output == '':
                control.log('Request-Error (%s): %s' % (e.reason, url))
            if not error:
                return None
            else:
                # For error=True, return the error for extended output
                response = e

        # Safety check: if response is still None, return None
        if response is None:
            return None

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
            # Smart buffer sizing - check Content-Length header
            try:
                content_length = int(response.headers.get('Content-Length', 0))
                if content_length > 0:
                    # Read exactly what we need (up to 5MB max for safety)
                    buffer_size = min(content_length, 5242880)
                    try:
                        result = response.read(buffer_size)
                    except http.client.IncompleteRead as e:
                        # Handle incomplete read - use partial data if available
                        control.log(f'IncompleteRead: Expected {buffer_size} bytes, got {len(e.partial)} bytes from {url}', 'warning')
                        result = e.partial
                        if not result:
                            # If no partial data, return None to trigger retry
                            return None
                else:
                    # Fallback to 5MB default
                    try:
                        result = response.read(5242880)
                    except http.client.IncompleteRead as e:
                        control.log(f'IncompleteRead: Got {len(e.partial)} bytes from {url}', 'warning')
                        result = e.partial
                        if not result:
                            return None
            except (ValueError, TypeError):
                # Fallback if Content-Length is malformed
                try:
                    result = response.read(5242880)
                except http.client.IncompleteRead as e:
                    control.log(f'IncompleteRead: Got {len(e.partial)} bytes from {url}', 'warning')
                    result = e.partial
                    if not result:
                        return None

        encoding = None
        text_content = False

        if response.headers.get('content-encoding', '').lower() == 'gzip':
            result = gzip.GzipFile(fileobj=io.BytesIO(result)).read()

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
                epattern = epattern.encode('utf8')
                r = re.search(epattern, result, re.IGNORECASE)
                if r:
                    encoding = r.group(1).decode('utf8')
                    break

        if encoding is None:
            r = re.search(b'^#EXT', result, re.IGNORECASE)
            if r:
                encoding = 'utf8'
        if encoding is not None:
            result = result.decode(encoding, errors='ignore')
            text_content = True
        elif text_content and encoding is None:
            # Try UTF-8 first (for modern APIs: JSON/XML from MAL, AniList, etc.)
            # Fall back to latin-1 if UTF-8 fails (for legacy content)
            # This fixes mojibake for Unicode chars like ×, –, …, accented letters, etc.
            try:
                result = result.decode('utf-8')
            except UnicodeDecodeError:
                result = result.decode('latin-1', errors='ignore')
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
        control.log('Request-Error: (%s) => %s' % (str(e), url))
        return


def get(url, headers=None, timeout=20, verify=True, cookies=None, params=None):
    """
    Requests-like GET method that returns a Response object

    Usage:
        response = client.get(url)
        response = client.get(url, params={'key': 'value'})
        print(response.text)  # As string
        print(response.content)  # As bytes
        print(response.status_code)  # HTTP status
        data = response.json()  # Parse JSON
    """
    result = request(url, headers=headers or {}, timeout=timeout, verify=verify, cookie=cookies, params=params, output='extended', use_session=True)

    if result and isinstance(result, tuple) and len(result) >= 5:
        content, status_code, response_headers, request_headers, cookie, response_url = result

        # Determine if content is binary
        content_type = response_headers.get('Content-Type', '').lower()
        is_binary = not any(x in content_type for x in ['text', 'json', 'xml', 'html', 'javascript'])

        # Parse cookies into dict
        cookie_dict = {}
        if cookie:
            for item in cookie.split('; '):
                if '=' in item:
                    key, val = item.split('=', 1)
                    cookie_dict[key] = val

        return Response(
            content=content,
            status_code=int(status_code) if status_code else 200,
            headers=response_headers,
            url=response_url or url,
            cookies=cookie_dict,
            is_binary=is_binary
        )
    elif result:
        # Fallback for simple request
        return Response(content=result, status_code=200, url=url)

    # Return failed response
    return Response(content=None, status_code=0, url=url)


def post(url, data=None, json_data=None, headers=None, timeout=20, verify=True, cookies=None):
    """
    Requests-like POST method that returns a Response object

    Usage:
        response = client.post(url, data={'key': 'value'})
        response = client.post(url, json_data={'key': 'value'})
        print(response.text)
        print(response.status_code)
    """
    if json_data:
        result = request(url, post=json_data, jpost=True, headers=headers or {}, timeout=timeout, verify=verify, cookie=cookies, output='extended', use_session=True)
    else:
        result = request(url, post=data, headers=headers or {}, timeout=timeout, verify=verify, cookie=cookies, output='extended', use_session=True)

    if result and isinstance(result, tuple) and len(result) >= 5:
        content, status_code, response_headers, request_headers, cookie, response_url = result

        # Determine if content is binary
        content_type = response_headers.get('Content-Type', '').lower()
        is_binary = not any(x in content_type for x in ['text', 'json', 'xml', 'html', 'javascript'])

        # Parse cookies into dict
        cookie_dict = {}
        if cookie:
            for item in cookie.split('; '):
                if '=' in item:
                    key, val = item.split('=', 1)
                    cookie_dict[key] = val

        return Response(
            content=content,
            status_code=int(status_code) if status_code else 200,
            headers=response_headers,
            url=response_url or url,
            cookies=cookie_dict,
            is_binary=is_binary
        )
    elif result:
        # Fallback for simple request
        return Response(content=result, status_code=200, url=url)

    # Return failed response
    return Response(content=None, status_code=0, url=url)


def put(url, data=None, json_data=None, headers=None, timeout=20, verify=True, cookies=None):
    """
    Requests-like PUT method that returns a Response object

    Usage:
        response = client.put(url, data={'key': 'value'})
        response = client.put(url, json_data={'key': 'value'})
        print(response.text)
        print(response.status_code)
    """
    if json_data:
        result = request(url, post=json_data, jpost=True, method='PUT', headers=headers or {}, timeout=timeout, verify=verify, cookie=cookies, output='extended', use_session=True)
    else:
        result = request(url, post=data, method='PUT', headers=headers or {}, timeout=timeout, verify=verify, cookie=cookies, output='extended', use_session=True)

    if result and isinstance(result, tuple) and len(result) >= 5:
        content, status_code, response_headers, request_headers, cookie, response_url = result

        # Determine if content is binary
        content_type = response_headers.get('Content-Type', '').lower()
        is_binary = not any(x in content_type for x in ['text', 'json', 'xml', 'html', 'javascript'])

        # Parse cookies into dict
        cookie_dict = {}
        if cookie:
            for item in cookie.split('; '):
                if '=' in item:
                    key, val = item.split('=', 1)
                    cookie_dict[key] = val

        return Response(
            content=content,
            status_code=int(status_code) if status_code else 200,
            headers=response_headers,
            url=response_url or url,
            cookies=cookie_dict,
            is_binary=is_binary
        )
    elif result:
        # Fallback for simple request
        return Response(content=result, status_code=200, url=url)

    # Return failed response
    return Response(content=None, status_code=0, url=url)


def patch(url, data=None, json_data=None, headers=None, timeout=20, verify=True, cookies=None):
    """
    Requests-like PATCH method that returns a Response object

    PATCH is used for partial updates to resources (unlike PUT which replaces entire resource)

    Usage:
        response = client.patch(url, data={'key': 'value'})
        response = client.patch(url, json_data={'key': 'value'})
        print(response.text)
        print(response.status_code)
    """
    if json_data:
        result = request(url, post=json_data, jpost=True, method='PATCH', headers=headers or {}, timeout=timeout, verify=verify, cookie=cookies, output='extended', use_session=True)
    else:
        result = request(url, post=data, method='PATCH', headers=headers or {}, timeout=timeout, verify=verify, cookie=cookies, output='extended', use_session=True)

    if result and isinstance(result, tuple) and len(result) >= 5:
        content, status_code, response_headers, request_headers, cookie, response_url = result

        # Determine if content is binary
        content_type = response_headers.get('Content-Type', '').lower()
        is_binary = not any(x in content_type for x in ['text', 'json', 'xml', 'html', 'javascript'])

        # Parse cookies into dict
        cookie_dict = {}
        if cookie:
            for item in cookie.split('; '):
                if '=' in item:
                    key, val = item.split('=', 1)
                    cookie_dict[key] = val

        return Response(
            content=content,
            status_code=int(status_code) if status_code else 200,
            headers=response_headers,
            url=response_url or url,
            cookies=cookie_dict,
            is_binary=is_binary
        )
    elif result:
        # Fallback for simple request
        return Response(content=result, status_code=200, url=url)

    # Return failed response
    return Response(content=None, status_code=0, url=url)


def delete(url, data=None, json_data=None, headers=None, timeout=20, verify=True, cookies=None):
    """
    Requests-like DELETE method that returns a Response object

    Usage:
        response = client.delete(url)
        response = client.delete(url, headers={'Authorization': 'Bearer token'})
        response = client.delete(url, data={'key': 'value'})
        print(response.status_code)
        if response.ok:
            print("Deleted successfully")
    """
    if json_data:
        result = request(url, post=json_data, jpost=True, method='DELETE', headers=headers or {}, timeout=timeout, verify=verify, cookie=cookies, output='extended', use_session=True)
    elif data:
        result = request(url, post=data, method='DELETE', headers=headers or {}, timeout=timeout, verify=verify, cookie=cookies, output='extended', use_session=True)
    else:
        result = request(url, method='DELETE', headers=headers or {}, timeout=timeout, verify=verify, cookie=cookies, output='extended', use_session=True)

    if result and isinstance(result, tuple) and len(result) >= 5:
        content, status_code, response_headers, request_headers, cookie, response_url = result

        # Determine if content is binary
        content_type = response_headers.get('Content-Type', '').lower()
        is_binary = not any(x in content_type for x in ['text', 'json', 'xml', 'html', 'javascript'])

        # Parse cookies into dict
        cookie_dict = {}
        if cookie:
            for item in cookie.split('; '):
                if '=' in item:
                    key, val = item.split('=', 1)
                    cookie_dict[key] = val

        return Response(
            content=content,
            status_code=int(status_code) if status_code else 200,
            headers=response_headers,
            url=response_url or url,
            cookies=cookie_dict,
            is_binary=is_binary
        )
    elif result:
        # Fallback for simple request
        return Response(content=result, status_code=200, url=url)

    # Return failed response
    return Response(content=None, status_code=0, url=url)


def head(url, headers=None, timeout=20, verify=True, cookies=None, params=None):
    """
    Requests-like HEAD method that returns a Response object
    HEAD requests only fetch headers, not the body (faster for checking if URL exists)

    Usage:
        response = client.head(url)
        response = client.head(url, timeout=5)
        print(response.status_code)  # 200, 404, etc.
        print(response.headers)
        if response.ok:
            print("URL is accessible")
    """
    result = request(url, headers=headers or {}, timeout=timeout, verify=verify, cookie=cookies, params=params, limit='0', output='extended', use_session=True)

    if result and isinstance(result, tuple) and len(result) >= 5:
        content, status_code, response_headers, request_headers, cookie, response_url = result

        # Parse cookies into dict
        cookie_dict = {}
        if cookie:
            for item in cookie.split('; '):
                if '=' in item:
                    key, val = item.split('=', 1)
                    cookie_dict[key] = val

        return Response(
            content='',  # HEAD has no body
            status_code=int(status_code) if status_code else 200,
            headers=response_headers,
            url=response_url or url,
            cookies=cookie_dict,
            is_binary=False
        )
    elif result:
        # Fallback for simple request
        return Response(content='', status_code=200, url=url)

    # Return failed response
    return Response(content=None, status_code=0, url=url)


def session_request(url, method='GET', data=None, headers=None, timeout=20, verify=True):
    """
    Session-based request that maintains cookies across calls (like requests.Session)

    Usage:
        # Cookies will be automatically stored and reused for the same domain
        response1 = client.session_request('https://example.com/login', method='POST', data={'user': 'test'})
        response2 = client.session_request('https://example.com/protected')  # Uses cookies from first request
    """
    uri = urllib.parse.urlparse(url)
    domain = uri.scheme + '://' + uri.netloc

    # Make request with session support
    if method.upper() == 'POST':
        result = request(url, post=data, headers=headers or {}, timeout=timeout, verify=verify, use_session=True, output='extended')
    else:
        result = request(url, headers=headers or {}, timeout=timeout, verify=verify, use_session=True, output='extended')

    if result and isinstance(result, tuple) and len(result) >= 5:
        content, response_code, response_headers, request_headers, cookie, response_url = result
        # Store cookies for this domain
        if cookie:
            _session_cookies[domain] = cookie
        return content
    elif result:
        return result

    return None


def clear_session():
    """Clear all session cookies and openers"""
    global _session_cookies, _session_openers
    _session_cookies.clear()
    _session_openers.clear()
    control.log("Session cache cleared")


class Session:
    """
    Requests-like Session class for persistent cookies and settings

    Usage:
        session = client.Session()
        response = session.get('https://example.com')
        response = session.post('https://example.com/login', data={'user': 'test'})
        session.close()
    """
    def __init__(self):
        self.cookies = {}
        self.headers = {}
        self._domain_cookies = {}

    def get(self, url, headers=None, timeout=20, verify=True):
        """GET request with session cookies"""
        merged_headers = self.headers.copy()
        if headers:
            merged_headers.update(headers)

        # Build cookie string from session cookies
        domain = urllib.parse.urlparse(url).netloc
        cookie_str = None
        if domain in self._domain_cookies:
            cookie_str = '; '.join([f'{k}={v}' for k, v in self._domain_cookies[domain].items()])

        result = request(url, headers=merged_headers, timeout=timeout, verify=verify, cookie=cookie_str, use_session=True, output='extended')

        if result and isinstance(result, tuple) and len(result) >= 5:
            content, status_code, response_headers, request_headers, cookie, response_url = result

            # Store cookies from response
            if cookie:
                if domain not in self._domain_cookies:
                    self._domain_cookies[domain] = {}
                for item in cookie.split('; '):
                    if '=' in item:
                        key, val = item.split('=', 1)
                        self._domain_cookies[domain][key] = val
                        self.cookies[key] = val

            # Determine if content is binary
            content_type = response_headers.get('Content-Type', '').lower()
            is_binary = not any(x in content_type for x in ['text', 'json', 'xml', 'html', 'javascript'])

            return Response(
                content=content,
                status_code=int(status_code) if status_code else 200,
                headers=response_headers,
                url=response_url or url,
                cookies=self._domain_cookies.get(domain, {}),
                is_binary=is_binary
            )
        elif result:
            return Response(content=result, status_code=200, url=url)

        return Response(content=None, status_code=0, url=url)

    def post(self, url, data=None, json_data=None, headers=None, timeout=20, verify=True):
        """POST request with session cookies"""
        merged_headers = self.headers.copy()
        if headers:
            merged_headers.update(headers)

        # Build cookie string from session cookies
        domain = urllib.parse.urlparse(url).netloc
        cookie_str = None
        if domain in self._domain_cookies:
            cookie_str = '; '.join([f'{k}={v}' for k, v in self._domain_cookies[domain].items()])

        if json_data:
            result = request(url, post=json_data, jpost=True, headers=merged_headers, timeout=timeout, verify=verify, cookie=cookie_str, use_session=True, output='extended')
        else:
            result = request(url, post=data, headers=merged_headers, timeout=timeout, verify=verify, cookie=cookie_str, use_session=True, output='extended')

        if result and isinstance(result, tuple) and len(result) >= 5:
            content, status_code, response_headers, request_headers, cookie, response_url = result

            # Store cookies from response
            if cookie:
                if domain not in self._domain_cookies:
                    self._domain_cookies[domain] = {}
                for item in cookie.split('; '):
                    if '=' in item:
                        key, val = item.split('=', 1)
                        self._domain_cookies[domain][key] = val
                        self.cookies[key] = val

            # Determine if content is binary
            content_type = response_headers.get('Content-Type', '').lower()
            is_binary = not any(x in content_type for x in ['text', 'json', 'xml', 'html', 'javascript'])

            return Response(
                content=content,
                status_code=int(status_code) if status_code else 200,
                headers=response_headers,
                url=response_url or url,
                cookies=self._domain_cookies.get(domain, {}),
                is_binary=is_binary
            )
        elif result:
            return Response(content=result, status_code=200, url=url)

        return Response(content=None, status_code=0, url=url)

    def close(self):
        """Close the session and clear cookies"""
        self.cookies.clear()
        self._domain_cookies.clear()


def _basic_request(url, headers=None, post=None, timeout=60, jpost=False, limit=None):
    try:
        request = urllib.request.Request(url)
        if post is not None:
            if jpost:
                post = json.dumps(post)
                post = post.encode('utf8')
                request = urllib.request.Request(url, post)
                request.add_header('Content-Type', 'application/json')
            else:
                if isinstance(post, dict):
                    post = byteify(post)
                    post = urllib.parse.urlencode(post)
                if len(post) > 0:
                    post = post.encode('utf8')
                    request = urllib.request.Request(url, data=post)
                else:
                    request.get_method = lambda: 'POST'
                    request.has_header = lambda header_name: (
                        header_name == 'Content-type'
                        or urllib.request.Request.has_header(request, header_name)
                    )
        if headers is not None:
            _add_request_header(request, headers)
        response = urllib.request.urlopen(request, timeout=timeout)
        return _get_result(response, limit)
    except BaseException:
        return


def _add_request_header(_request, headers):
    try:
        scheme = urllib.parse.urlparse(_request.get_full_url()).scheme
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
        result = gzip.GzipFile(fileobj=io.BytesIO(result)).read()

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
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(ftext)


def retrieve(fname):
    fpath = control.dataPath + fname
    if control.pathExists(fpath):
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
                store(cfdata, urllib.parse.urlparse(netloc).netloc + '.json')
            return (self.cookie, self.ua)
        except Exception as e:
            control.log('%s returned an error. Could not collect tokens - Error: %s.' % (netloc, str(e)))
            return (self.cookie, self.ua)

    def _get_cookie(self, netloc, timeout):
        fs_url = control.getSetting('fs_url')
        fs_timeout = control.getInt('fs_timeout')
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
                store(cfdata, urllib.parse.urlparse(netloc).netloc + '.json')
            return (self.cookie, self.ua)
        except Exception as e:
            control.log('%s returned an error. Could not collect tokens - Error: %s.' % (netloc, str(e)))
            return (self.cookie, self.ua)

    def _get_cookie(self, netloc, timeout):
        fs_url = control.getSetting('fs_url')
        fs_timeout = control.getInt('fs_timeout')
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
    if isinstance(data, list):
        return [byteify(item, ignore_dicts=True) for item in data]
    if isinstance(data, dict) and not ignore_dicts:
        return dict([(byteify(key, ignore_dicts=True), byteify(
            value, ignore_dicts=True)) for key, value in data.items()])
    return data


def strip_cookie_url(url):
    url, headers = _strip_url(url)
    if _COOKIE_HEADER in headers.keys():
        del headers[_COOKIE_HEADER]

    return _url_with_headers(url, headers)


def _url_with_headers(url, headers):
    if not len(headers.keys()):
        return url

    headers_arr = [
        "%s=%s" % (key, urllib.parse.quote_plus(value))
        for key, value in headers.items()
    ]

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
        out_headers[m[0][0]] = urllib.parse.unquote_plus(m[0][1])

    return (target_url, out_headers)
