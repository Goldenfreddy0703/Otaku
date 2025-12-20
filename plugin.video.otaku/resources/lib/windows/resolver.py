import xbmcgui
import xbmcplugin
import xbmc
import urllib.parse

from resources.lib.WatchlistIntegration import watchlist_update_episode
from resources.lib.debrid import all_debrid, debrid_link, premiumize, real_debrid, torbox, easydebrid
from resources.lib.ui import client, control, source_utils, player
from resources.lib.windows.base_window import BaseWindow

control.sys.path.append(control.dataPath)


class hook_mimetype:
    __MIME_HOOKS = {}

    @classmethod
    def trigger(cls, mimetype, item):
        if mimetype in cls.__MIME_HOOKS.keys():
            return cls.__MIME_HOOKS[mimetype](item)
        return item

    def __init__(self, mimetype):
        self._type = mimetype

    def __call__(self, func):
        assert self._type not in self.__MIME_HOOKS.keys()
        self.__MIME_HOOKS[self._type] = func
        return func


class Resolver(BaseWindow):
    def __init__(self, xml_file, location, actionArgs=None, source_select=False):
        super().__init__(xml_file, location, actionArgs=actionArgs)
        self.return_data = {
            'link': None,
            'linkinfo': None,
            'source': None
        }
        self.canceled = False
        self.sources = None
        self.args = None
        self.image = {}
        self.resolvers = {
            'Alldebrid': all_debrid.AllDebrid,
            'Debrid-Link': debrid_link.DebridLink,
            'Premiumize': premiumize.Premiumize,
            'Real-Debrid': real_debrid.RealDebrid,
            'TorBox': torbox.TorBox,
            'EasyDebrid': easydebrid.EasyDebrid
        }
        self.source_select = source_select
        self.pack_select = False
        self.mal_id = actionArgs['mal_id']
        # self.season = database.get_episode(self.mal_id)['season']
        self.episode = int(actionArgs.get('episode', 1))
        self.play = actionArgs.get('play')
        self.source_select_close = actionArgs.get('close')
        self.resume = actionArgs.get('resume')
        self.context = actionArgs.get('context')
        self.silent = actionArgs.get('silent')
        self.params = actionArgs.get('params', {})
        self.autoruninbackground = control.getBool('uncached.autoruninbackground')
        self.autoruninforground = control.getBool('uncached.autoruninforground')
        self.autoskipuncached = control.getBool('uncached.autoskipuncached')
        self.abort = False

        # if self.season:
        #     control.setStr('resolve_season', str(self.season))

        # if self.source_select:
        #     control.setSetting('last_played_source', str(None))

    def onInit(self):
        self.sources = self.reorder_sources(self.sources)
        self.resolve(self.sources)

    def reorder_sources(self, sources):
        import re
        if len(sources) > 1 and not self.source_select:
            lp = control.getSetting('last_played_source') or ''
            # remove any [HASH] blocks (e.g. [E5A85899])
            lp = re.sub(r'\[[0-9A-Fa-f]{8,}\]', '', lp).strip()

            ep = str(self.episode)
            L = len(ep)

            # 1) Precompute all offsets where exactly L digits occur in a row
            digit_positions = [
                i for i in range(len(lp) - L + 1)
                if lp[i:i + L].isdigit()
            ]

            for idx, source in enumerate(sources):
                # embed/direct-style
                if source['type'] in ['embed', 'direct']:
                    key = source['provider'] + " " + " ".join(map(str, source['info']))
                    if key == lp:
                        sources[0], sources[idx] = sources[idx], sources[0]
                        break

                # torrent-style
                elif source['type'] in ['torrent', 'torrent (uncached)', 'cloud', 'hoster', 'local']:
                    rel = str(source['release_title'])
                    # strip hashes from the release title too
                    rel = re.sub(r'\[[0-9A-Fa-f]{8,}\]', '', rel).strip()

                    # 2) exact match fallback
                    if rel == lp:
                        sources[0], sources[idx] = sources[idx], sources[0]
                        break

                    # 3) try each digit-run position
                    for pos in digit_positions:
                        if rel.startswith(lp[:pos]) and rel.endswith(lp[pos + L:]):
                            sources[0], sources[idx] = sources[idx], sources[0]
                            idx = None
                            break
                    if idx is None:
                        break

        return sources

    def resolve(self, sources):
        """Optimized resolve with reduced property updates"""
        for i in sources:
            self.return_data['source'] = i
            if self.canceled:
                break

            # Batch property updates
            self._update_source_properties(i)

            if 'uncached' in i['type']:
                if not self.autoskipuncached:
                    self.return_data['link'] = self.resolve_uncache(i)
                else:
                    stream_link = self.resolve_uncache(i)
                    if stream_link:
                        self.return_data['link'] = stream_link
                        break

            if i['type'] in ['torrent', 'cloud', 'hoster']:
                if i['type'] == 'cloud' and i['debrid_provider'] == 'Alldebrid':
                    stream_link = i['hash']
                else:
                    stream_link = self.resolve_source(self.resolvers[i['debrid_provider']], i)
                if stream_link:
                    self.return_data['link'] = stream_link
                    break

            elif i['type'] == 'direct':
                stream_link = i['hash']
                if stream_link:
                    self.return_data['link'] = stream_link
                    if i.get('subs'):
                        self.return_data['sub'] = i['subs']
                    break

            elif i['type'] == 'embed':
                from resources.lib.ui import embed_extractor
                stream_link = embed_extractor.load_video_from_url(i['hash'])
                if stream_link:
                    self.return_data['link'] = stream_link
                    break

            elif i['type'] == 'local':
                stream_link = i['hash']
                self.return_data = {
                    'source': i,
                    'url': stream_link,
                    'local': True,
                    'headers': {}
                }
                break

        if self.return_data.get('local'):
            self.return_data['linkinfo'] = self.return_data
        else:
            self.return_data['linkinfo'] = self.prefetch_play_link(self.return_data['link'])

        if not self.return_data['linkinfo']:
            self.return_data = False

        if self.play and isinstance(self.return_data, dict):
            self._handle_playback()
        else:
            self.close()

    def _update_source_properties(self, source):
        """Batch update source properties to reduce overhead"""
        debrid_provider = source.get('debrid_provider', 'None').replace('_', ' ')
        self.setProperty('debrid_provider', debrid_provider)
        self.setProperty('source_provider', source['provider'])
        self.setProperty('release_title', str(source['release_title']))
        self.setProperty('source_resolution', source_utils.res[source['quality']])
        self.setProperty('source_info', " ".join(source['info']))
        self.setProperty('source_type', source['type'])

    def _handle_playback(self):
        """Separate playback handling to reduce resolve() complexity"""
        if self.source_select_close:
            self.source_select_close()

        linkInfo = self.return_data['linkinfo']
        item = xbmcgui.ListItem(path=linkInfo['url'], offscreen=True)

        # Handle subtitles
        if self.return_data.get('sub'):
            from resources.lib.ui import embed_extractor
            embed_extractor.del_subs()
            subtitles = []
            for sub in self.return_data['sub']:
                sub_url = sub.get('url')
                sub_lang = sub.get('lang')
                subtitles.append(embed_extractor.get_sub(sub_url, sub_lang))
            item.setSubtitles(subtitles)

        # Handle mimetype - hooks will configure InputStream Adaptive for HLS/DASH
        if linkInfo['headers'].get('Content-Type'):
            item.setProperty('MimeType', linkInfo['headers']['Content-Type'])
            item = hook_mimetype.trigger(linkInfo['headers']['Content-Type'], item)

        if self.params.get('image'):
            self.image = self.params.get('image', {})

        # Get the clean URL from item (hooks may have stripped headers)
        stream_url = item.getPath()

        # Set art and tags
        if self.context:
            control.set_videotags(item, self.params)
            art = self._build_art_dict(use_params=True)
            item.setArt(art)
            control.playList.clear()
            control.playList.add(stream_url, item)
            xbmc.Player().play(control.playList, item)
        else:
            if self.params.get('info'):
                control.set_videotags(item, self.params['info'])
            else:
                control.set_videotags(item, self.params)
            art = self._build_art_dict(use_params=False)
            item.setArt(art)
            xbmcplugin.setResolvedUrl(control.HANDLE, True, item)

        # Monitor playback start
        monitor = Monitor()
        for _ in range(30):
            if monitor.waitForAbort(1) or monitor.playbackerror or monitor.abortRequested():
                xbmcplugin.setResolvedUrl(control.HANDLE, False, item)
                control.playList.clear()
                self.abort = True
                break
            if monitor.playing:
                break
        else:
            control.log('no xbmc playing source found; Continuing code', level='warning')
        del monitor

        self.close()

        if not self.abort:
            player.WatchlistPlayer().handle_player(
                self.mal_id,
                watchlist_update_episode,
                self.episode,
                self.resume,
                self.params.get('path', ''),
                self.return_data['source']['type'] if 'type' in self.return_data['source'] else '',
                self.return_data['source']['provider'] if 'provider' in self.return_data['source'] else '',
                self.context
            )

    def _build_art_dict(self, use_params=False):
        """Build art dictionary efficiently"""
        if use_params:
            return {
                'icon': self.params.get('icon') or self.image.get('icon') or '',
                'thumb': self.params.get('thumb') or self.image.get('thumb') or '',
                'fanart': self.params.get('fanart') or self.image.get('fanart') or '',
                'landscape': self.params.get('landscape') or self.image.get('landscape') or '',
                'banner': self.params.get('banner') or self.image.get('banner') or '',
                'clearart': self.params.get('clearart') or self.image.get('clearart') or '',
                'clearlogo': self.params.get('clearlogo') or self.image.get('clearlogo') or '',
                'tvshow.poster': self.params.get('tvshow.poster') or self.params.get('poster') or '',
            }
        else:
            fanart = self.image.get('fanart')
            if isinstance(fanart, list) and fanart:
                fanart = fanart[0]
            return {
                'icon': self.image.get('icon') or '',
                'thumb': self.image.get('thumb') or '',
                'fanart': fanart or '',
                'landscape': self.image.get('landscape') or '',
                'banner': self.image.get('banner') or '',
                'clearart': self.image.get('clearart') or '',
                'clearlogo': self.image.get('clearlogo') or '',
                'tvshow.poster': self.image.get('poster') or self.params.get('poster') or '',
            }

    def resolve_source(self, api, source):
        """Improved resolve_source with better error handling for Premiumize"""
        try:
            api = api()
            hash_ = source['hash']
            magnet = f"magnet:?xt=urn:btih:{hash_}"
            stream_link = {}

            if source['type'] == 'torrent':
                stream_link = api.resolve_single_magnet(hash_, magnet, source['episode_re'], self.pack_select)
            elif source['type'] == 'cloud':
                hash_ = api.resolve_cloud(source, self.pack_select)
                if hash_:
                    stream_link = api.resolve_hoster(hash_)
            elif source['type'] == 'hoster':
                # Get the hoster links from EasyDebrid
                hoster_response = api.resolve_hoster(magnet, source['episode_re'], self.pack_select)
                if hoster_response:
                    stream_link = hoster_response

            return stream_link
        except Exception as e:
            control.log(f"Error resolving source with {source.get('debrid_provider', 'Unknown')}: {str(e)}", 'error')
            return None

    @staticmethod
    def prefetch_play_link(link):
        if not link:
            return
        url = link
        headers = {}
        if '|' in url:
            url, hdrs = url.split('|')
            headers = dict([item.split('=') for item in hdrs.split('&')])
            for header in headers:
                headers[header] = urllib.parse.unquote_plus(headers[header])

        # If flaresolverr is enabled, fetch cookies to bypass Cloudflare
        if control.getBool('fs_enable'):
            from resources.lib.ui.client import cfcookie
            cookie_obj = cfcookie()
            cookie, ua = cookie_obj.get(url, control.getInt('fs_timeout'))
            if cookie:
                headers["Cookie"] = cookie
                headers["User-Agent"] = ua

        response = client.get(url, headers=headers)
        if not response or str(response.status_code) not in ['200', '201']:
            status = response.status_code if response else 'failed'
            raise Exception('could not resolve %s. status_code=%s' %
                            (link, status))
        resp_headers = dict(response.headers)
        if 'Content-Type' not in resp_headers.keys():
            if 'Content-Length' not in resp_headers.keys():
                resp_headers.update({'Content-Type': 'video/MP2T'})
            elif '.m3u8' in url:
                resp_headers.update({'Content-Type': 'application/vnd.apple.mpegurl'})
        elif resp_headers['Content-Type'] == 'application/octet-stream' and '.m3u8' in url:
            resp_headers.update({'Content-Type': 'application/vnd.apple.mpegurl'})
        return {
            "url": link if '|' in link else response.url,
            "headers": resp_headers,
        }

    def resolve_uncache(self, source):
        heading = f'{control.ADDON_NAME}: Cache Resolver'
        status = None
        api = self.resolvers[source['debrid_provider']]()
        f_string = (f"[I]{source['release_title']}[/I][CR]"
                    f"[CR]"
                    f"This source is not cached. Would you like to cache it now?")

        if source['debrid_provider'] in ['Alldebrid', 'Real-Debrid', 'Debrid-Link']:
            # Get an instance of the debrid API and check torrent status early.
            torrent_status = api.get_torrent_status(source['magnet'])
            # torrent_status returns (torrent_id, status, torrent_info)
            if torrent_status is None or torrent_status[0] is None:
                # Torrent selection failed.
                return

            torrent_id, status, torrent_info = torrent_status
            if source['debrid_provider'] == 'Alldebrid':
                api.delete_magnet(torrent_id)
            elif source['debrid_provider'] == 'Real-Debrid':
                api.deleteTorrent(torrent_id)

        # If the file is already cached, bypass any prompting.
        if status in ['downloaded', 'Ready']:
            runbackground = False
            runinforground = False
        else:
            # Not yet cached: decide based on settings or prompt the user.
            if self.autoruninbackground:
                runbackground = True
                runinforground = False
            elif self.autoruninforground:
                runbackground = False
                runinforground = True
            elif self.autoskipuncached:
                # Auto-skip uncached: simply return nothing.
                return
            else:
                yesnocustom = control.yesnocustom_dialog(
                    heading, f_string, "Cancel", "Run in Background", "Run in Foreground",
                    defaultbutton=xbmcgui.DLG_YESNO_YES_BTN
                )
                if yesnocustom == -1 or yesnocustom == 2:
                    self.canceled = True
                    return
                runbackground = (yesnocustom == 0)
                runinforground = (yesnocustom == 1)

        try:
            resolved_cache = api.resolve_uncached_source(source, runbackground, runinforground, self.pack_select)
        except Exception as e:
            control.progressDialog.close()
            import traceback
            control.ok_dialog(control.ADDON_NAME, f'Error: {e}')
            control.log(traceback.format_exc(), level='error')
            return

        best_match = control.getBool('best_match')

        if not resolved_cache or not self.autoskipuncached:
            self.canceled = True

        if not best_match and self.autoskipuncached:
            self.canceled = False

        return resolved_cache

    def doModal(self, sources, args, pack_select):
        if sources:
            # Reorder sources first.
            self.sources = self.reorder_sources(sources)
            self.args = args
            # Now assign pack_select after the sources are reordered.
            self.pack_select = pack_select
            self.setProperty('release_title', str(self.sources[0]['release_title']))
            self.setProperty('debrid_provider', self.sources[0].get('debrid_provider', 'None').replace('_', ' '))
            self.setProperty('source_provider', self.sources[0]['provider'])
            self.setProperty('source_resolution', source_utils.res[self.sources[0]['quality']])
            self.setProperty('source_info', " ".join(self.sources[0]['info']))
            self.setProperty('source_type', self.sources[0]['type'])
            self.setProperty('source_size', self.sources[0]['size'])
            self.setProperty('source_seeders', str(self.sources[0].get('seeders', '')))

            if self.sources[0]['type'] in ['embed', 'direct']:
                control.setSetting('last_played_source', str(self.sources[0]['provider']) + " " + " ".join(map(str, self.sources[0]['info'])))
            else:
                control.setSetting('last_played_source', str(self.sources[0]['release_title']))

            if self.silent:
                if self.source_select_close:
                    self.source_select_close()
                self.resolve(self.sources)
            else:
                super(Resolver, self).doModal()

        return self.return_data

    def onAction(self, action):
        actionID = action.getId()

        if actionID in [92, 10]:
            # BACKSPACE / ESCAPE
            self.canceled = True
            self.close()


class Monitor(xbmc.Monitor):
    def __init__(self):
        super().__init__()
        self.playbackerror = False
        self.playing = False

    def onNotification(self, sender, method, data):
        if method == 'Player.OnAVStart':
            self.playing = True
        elif method == 'Player.OnStop':
            self.playbackerror = True
        # else:
        #     control.log(f'{method} | {data}')


@hook_mimetype('application/dash+xml')
def _DASH_HOOK(item):
    if control.getBool('inputstreamadaptive.enabled'):
        stream_url = item.getPath()
        import inputstreamhelper
        is_helper = inputstreamhelper.Helper('mpd')
        if is_helper.check_inputstream():
            item.setProperty('inputstream', is_helper.inputstream_addon)
            if control.kodi_version < 20.9:
                item.setProperty('inputstream.adaptive.manifest_type', 'mpd')
                item.setContentLookup(False)
            if '|' in stream_url:
                stream_url, headers = stream_url.split('|')
                item.setPath(stream_url)  # Set clean URL without headers
                item.setProperty('inputstream.adaptive.stream_headers', headers)
                item.setProperty('inputstream.adaptive.manifest_headers', headers)
                if control.kodi_version > 21.8:
                    item.setProperty('inputstream.adaptive.common_headers', headers)
                else:
                    item.setProperty('inputstream.adaptive.stream_params', headers)
        else:
            raise Exception("InputStream Adaptive is not supported.")
    return item


@hook_mimetype('application/vnd.apple.mpegurl')
def _HLS_HOOK(item):
    if control.getBool('inputstreamadaptive.enabled'):
        stream_url = item.getPath()
        import inputstreamhelper
        is_helper = inputstreamhelper.Helper('hls')
        if is_helper.check_inputstream():
            item.setProperty('inputstream', is_helper.inputstream_addon)
            if control.kodi_version < 20.9:
                item.setProperty('inputstream.adaptive.manifest_type', 'hls')
                item.setProperty('MimeType', 'application/vnd.apple.mpegurl')
                item.setMimeType('application/vnd.apple.mpegstream_url')
                item.setContentLookup(False)
            if '|' in stream_url:
                stream_url, headers = stream_url.split('|')
                item.setPath(stream_url)  # Set clean URL without headers
                item.setProperty('inputstream.adaptive.stream_headers', headers)
                item.setProperty('inputstream.adaptive.manifest_headers', headers)
                # For HLS AES-128 encrypted streams, license_key is used for key file requests
                item.setProperty('inputstream.adaptive.license_key', '|' + headers + '||R{SSM}')
                if control.kodi_version > 21.8:
                    item.setProperty('inputstream.adaptive.common_headers', headers)
                else:
                    item.setProperty('inputstream.adaptive.stream_params', headers)

    return item


@hook_mimetype('video/MP2T')
def _HLS2_HOOK(item):
    if control.getBool('inputstreamadaptive.enabled'):
        stream_url = item.getPath()
        import inputstreamhelper
        is_helper = inputstreamhelper.Helper('hls')
        if is_helper.check_inputstream():
            item.setProperty('inputstream', is_helper.inputstream_addon)
            if control.kodi_version < 20.9:
                item.setProperty('inputstream.adaptive.manifest_type', 'hls')
                item.setProperty('MimeType', 'application/vnd.apple.mpegurl')
                item.setMimeType('application/vnd.apple.mpegstream_url')
                item.setContentLookup(False)
            if '|' in stream_url:
                stream_url, headers = stream_url.split('|')
                item.setPath(stream_url)  # Set clean URL without headers
                item.setProperty('inputstream.adaptive.stream_headers', headers)
                item.setProperty('inputstream.adaptive.manifest_headers', headers)
                # For HLS AES-128 encrypted streams, license_key is used for key file requests
                item.setProperty('inputstream.adaptive.license_key', '|' + headers + '||R{SSM}')
                if control.kodi_version > 21.8:
                    item.setProperty('inputstream.adaptive.common_headers', headers)
                else:
                    item.setProperty('inputstream.adaptive.stream_params', headers)

    return item
