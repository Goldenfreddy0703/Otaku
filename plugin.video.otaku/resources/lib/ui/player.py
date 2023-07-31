import sys

from kodi_six import xbmc, xbmcgui, xbmcplugin
from resources.lib.ui import client, control, utils, database
from six.moves import urllib_parse
from resources.lib.indexers import aniskip

try:
    HANDLE = int(sys.argv[1])
except:
    HANDLE = '1'

playList = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
player = xbmc.Player
progressDialog = xbmcgui.DialogProgress()


class hook_mimetype(object):
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


class watchlistPlayer(xbmc.Player):

    def __init__(self):
        super(watchlistPlayer, self).__init__()
        self.player = xbmc.Player()
        self._filter_lang = None
        self._episode = None
        self._build_playlist = None
        self._anilist_id = None
        self._on_playback_done = None
        self._on_stopped = None
        self._on_percent = None
        self._watchlist_update = None
        self.current_time = 0
        self.updated = False
        self.media_type = None
        # self.AVStarted = False

        self.total_time = None
        self.skipintro_delay_time = int(control.getSetting('skipintro.delay'))
        self.skipintro_aniskip_enable = control.getSetting('skipintro.aniskip.enable') == 'true'
        self.skipoutro_aniskip_enable = control.getSetting('skipoutro.aniskip.enable') == 'true'
        self.skipintro_auto_aniskip = control.getSetting('skipintro.aniskip.auto') == 'true'
        self.skipoutro_auto_aniskip = control.getSetting('skipoutro.aniskip.auto') == 'true'
        self.skipintro_start_skip_time = 0
        self.skipintro_end_skip_time = 9999
        self.skipoutro_start_skip_time = 0
        self.skipoutro_end_skip_time = 9999
        self.skipintro_aniskip_offset = int(control.getSetting('skipintro.aniskip.offset'))
        self.skipoutro_aniskip_offset = int(control.getSetting('skipoutro.aniskip.offset'))

    def handle_player(self, anilist_id, watchlist_update, build_playlist, episode, filter_lang):
        self._anilist_id = anilist_id

        if watchlist_update:
            self._watchlist_update = watchlist_update(anilist_id, episode)

        self._build_playlist = build_playlist
        self._episode = episode
        self._filter_lang = filter_lang

        if self.skipintro_aniskip_enable:
            try:
                mal_id = database.get_show(anilist_id)['mal_id']
            except TypeError:
                mal_id = ''
            skipintro_aniskip_res = aniskip.get_skip_times(mal_id, episode, 'op')

            if skipintro_aniskip_res:
                skip_times = skipintro_aniskip_res['results'][0]['interval']
                self.skipintro_start_skip_time = int(skip_times['startTime']) + int(self.skipintro_aniskip_offset)
                self.skipintro_end_skip_time = int(skip_times['endTime']) + int(self.skipintro_aniskip_offset)

        if self.skipoutro_aniskip_enable:
            try:
                mal_id = database.get_show(anilist_id)['mal_id']
            except TypeError:
                mal_id = ''
            skipoutro_aniskip_res = aniskip.get_skip_times(mal_id, episode, 'ed')

            if skipoutro_aniskip_res:
                skip_times = skipoutro_aniskip_res['results'][0]['interval']
                self.skipoutro_start_skip_time = int(skip_times['startTime']) + int(self.skipoutro_aniskip_offset)
                self.skipoutro_end_skip_time = int(skip_times['endTime']) + int(self.skipoutro_aniskip_offset)

        control.setSetting('skipintro.start.skip.time', str(self.skipintro_start_skip_time))
        control.setSetting('skipintro.end.skip.time', str(self.skipintro_end_skip_time))

        control.setSetting('skipoutro.start.skip.time', str(self.skipoutro_start_skip_time))
        control.setSetting('skipoutro.end.skip.time', str(self.skipoutro_end_skip_time))

        self.keepAlive()

    def onPlayBackStarted(self):
        if self._build_playlist and playList.size() == 1:
            self._build_playlist(self._anilist_id, self._episode, self._filter_lang)

        current_ = playList.getposition()
        try:
            self.media_type = playList[current_].getVideoInfoTag().getMediaType()
        except:
            self.media_type = ''
        control.setSetting('addon.last_watched', self._anilist_id)

    # def onAVStarted(self):
    #     self.AVStarted = True

    # def onAVChange(self):
    #     self.AVStarted = True

    def onPlayBackStopped(self):
        playList.clear()

    # def onPlayBackEnded(self):
    #     pass

    def onPlayBackError(self):
        playList.clear()
        sys.exit(1)

    def getWatchedPercent(self):
        try:
            current_position = self.getTime()
        except:
            current_position = self.current_time

        media_length = self.getTotalTime()
        watched_percent = 0

        if int(media_length) != 0:
            watched_percent = float(current_position) / float(media_length) * 100

        return watched_percent

    def onWatchedPercent(self):
        if not self._watchlist_update:
            return

        while self.isPlaying() and not self.updated:
            try:
                watched_percentage = self.getWatchedPercent()

                try:
                    self.current_time = self.getTime()

                except:
                    import traceback
                    traceback.print_exc()

                if watched_percentage > 80:
                    self._watchlist_update()
                    self.updated = True
                    break

            except:
                import traceback
                traceback.print_exc()
                xbmc.sleep(5000)
                continue

            xbmc.sleep(5000)

        else:
            return

    def keepAlive(self):
        for i in range(0, 480):
            if self.isPlayingVideo():
                break
            xbmc.sleep(250)

        # for i in range(0, 480):
        #     if self.AVStarted:
        #         break

        control.closeAllDialogs()

        if control.getSetting('general.kodi_language') == 'true':
            # do not execute the code block
            pass
        else:
            # Subtitle Preferences
            subtitle_lang = self.getAvailableSubtitleStreams()
            if len(subtitle_lang) > 1:
                subtitles = [
                    "eng", "jpn", "spa", "fre", "ger", "ita",
                    "dut", "rus", "por", "kor", "chi", "ara",
                    "hin", "tur", "pol", "swe", "nor", "dan",
                    "fin"
                ]
                preferred_subtitle = subtitles[int(control.getSetting('general.subtitles'))]

                try:
                    subtitle_int = subtitle_lang.index(preferred_subtitle)
                    self.setSubtitleStream(subtitle_int)
                except ValueError:
                    preferred_subtitle = "eng"
                    try:
                        subtitle_int = subtitle_lang.index(preferred_subtitle)
                        self.setSubtitleStream(subtitle_int)
                    except ValueError:
                        # Handle the ValueError by setting subtitle_int to 0 (first available subtitle stream)
                        subtitle_int = 0

                        self.setSubtitleStream(subtitle_int)

            # Audio Preferences
            audio_lang = self.getAvailableAudioStreams()
            if len(audio_lang) > 1:
                audios = ['jpn', 'eng']
                preferred_audio = audios[int(control.getSetting('general.audio'))]

                try:
                    audio_int = audio_lang.index(preferred_audio)
                except ValueError:
                    # Handle the ValueError by setting audio_int to 0 (play the first audio stream)
                    audio_int = 0

                self.setAudioStream(audio_int)

                if preferred_audio == "eng":
                    self.showSubtitles(False)
                else:
                    self.showSubtitles(True)

        if control.getSetting('general.dubsubtitles') == 'true':
            self.showSubtitles(True)

        if self.media_type == 'movie':
            return self.onWatchedPercent()

        # Skip Intro Code
        if self.skipintro_aniskip_enable:
            while self.isPlaying():
                self.current_time = int(self.getTime())
                if self.skipintro_start_skip_time == 0:
                    break
                elif self.skipintro_auto_aniskip:
                    # Add a delay of 5 seconds before checking for the skipoutro condition
                    xbmc.sleep(3000)
                    try:
                        # Get the current playback time
                        current_time = self.player.getTime()
                    except RuntimeError:
                        # Handle the error gracefully, for example:
                        current_time = 0

                    # Check if we're still in the intro
                    if current_time < self.skipintro_start_skip_time:
                        # If we're before the start skip time, wait and check again
                        xbmc.sleep(250)
                        continue
                    elif current_time < self.skipintro_end_skip_time:
                        # If we're in the intro, seek to the end of the intro
                        self.player.seekTime(self.skipintro_end_skip_time)
                        break
                elif self.skipintro_end_skip_time == 9999:
                    PlayerDialogs()._show_skip_intro_aniskip()
                    break
                elif self.current_time > self.skipintro_start_skip_time:
                    PlayerDialogs()._show_skip_intro_aniskip()
                    break

                xbmc.sleep(250)

        if control.getSetting('skipintro.aniskip.enable') == 'true':
            # do not execute the code block
            pass
        else:
            # execute the code block
            if control.getSetting('smartplay.skipintrodialog') == 'true':
                endpoint = int(control.getSetting('skipintro.time'))
            else:
                endpoint = False

            if endpoint:
                while self.isPlaying():
                    self.current_time = int(self.getTime())
                    if self.current_time > 240:
                        break
                    elif self.current_time >= self.skipintro_delay_time:
                        PlayerDialogs()._show_skip_intro()
                        break
                    xbmc.sleep(250)

        if control.getSetting('skipintro.aniskip.enable') == 'true':
            if self.skipintro_start_skip_time == 0:
                if control.getSetting('smartplay.skipintrodialog') == 'true':
                    endpoint = int(control.getSetting('skipintro.time'))
                else:
                    endpoint = False

                if endpoint:
                    while self.isPlaying():
                        self.current_time = int(self.getTime())
                        if self.current_time > 240:
                            break
                        elif self.current_time >= self.skipintro_delay_time:
                            PlayerDialogs()._show_skip_intro()
                            break
                        xbmc.sleep(250)

        _ = self.onWatchedPercent()

        # Skip Outro Code
        if self.skipoutro_aniskip_enable:
            while self.isPlaying():
                self.current_time = int(self.getTime())
                if self.skipoutro_start_skip_time == 0:
                    break
                elif self.skipoutro_auto_aniskip:
                    # Add a delay of 5 seconds before checking for the skipoutro condition
                    try:
                        # Get the current playback time
                        current_time = self.player.getTime()
                    except RuntimeError:
                        # Handle the error gracefully, for example:
                        current_time = 0

                    # Check if we're still in the outro
                    if current_time < self.skipoutro_start_skip_time:
                        # If we're before the start skip time, wait and check again
                        xbmc.sleep(250)
                        continue
                    elif current_time < self.skipoutro_end_skip_time:
                        # If we're in the outro, seek to the end of the outro
                        self.player.seekTime(self.skipoutro_end_skip_time)
                        break
                elif self.skipoutro_end_skip_time == 9999:
                    PlayerDialogs()._show_skip_outro_aniskip()
                    break
                elif self.current_time > self.skipoutro_start_skip_time:
                    PlayerDialogs()._show_skip_outro_aniskip()
                    break
                elif playList.getposition() == (playList.size() - 1):
                    break

                xbmc.sleep(250)

        _ = self.onWatchedPercent()

        # Play Next Code
        if control.getSetting('skipoutro.aniskip.enable') == 'true':
            # do not execute the code block
            pass
        else:
            # execute the code block
            if control.getSetting('smartplay.playingnextdialog') == 'true':
                endpoint = int(control.getSetting('playingnext.time'))
            else:
                endpoint = False

            if endpoint:
                while self.isPlaying():
                    if int(self.getTotalTime()) - int(self.getTime()) <= endpoint:
                        xbmc.executebuiltin('RunPlugin("plugin://plugin.video.otaku/run_player_dialogs")')
                        break
                    else:
                        xbmc.sleep(5000)

        if control.getSetting('skipoutro.aniskip.enable') == 'true':
            if self.skipoutro_start_skip_time == 0:
                if control.getSetting('smartplay.playingnextdialog') == 'true':
                    endpoint = int(control.getSetting('playingnext.time'))
                else:
                    endpoint = False

                if endpoint:
                    while self.isPlaying():
                        if int(self.getTotalTime()) - int(self.getTime()) <= endpoint:
                            xbmc.executebuiltin('RunPlugin("plugin://plugin.video.otaku/run_player_dialogs")')
                            break
                        else:
                            xbmc.sleep(5000)


class PlayerDialogs(xbmc.Player):

    def __init__(self):
        super(PlayerDialogs, self).__init__()
        self._min_time = 30
        self.playing_file = self.getPlayingFile()

    def display_dialog(self):

        if playList.size() == 0 or playList.getposition() == (playList.size() - 1):
            return

        target = self._show_playing_next

        if self.playing_file != self.getPlayingFile():
            return

        if not self.isPlayingVideo():
            return

        if not self._is_video_window_open():
            return

        target()

    def _show_playing_next(self):
        from resources.lib.windows.playing_next import PlayingNext
        selected_theme = int(control.getSetting('general.dialog'))
        themes = ['playing_next_default.xml', 'playing_next_ah2.xml', 'playing_next_auramod.xml']
        selected_theme = themes[selected_theme]
        PlayingNext(*(selected_theme, control.ADDON_PATH),
                    actionArgs=self._get_next_item_args()).doModal()

    @staticmethod
    def _show_skip_intro():
        from resources.lib.windows.skip_intro import SkipIntro
        selected_theme = int(control.getSetting('general.dialog'))
        themes = ['skip_intro_default.xml', 'skip_intro_ah2.xml', 'skip_intro_auramod.xml']
        selected_theme = themes[selected_theme]
        SkipIntro(*(selected_theme, control.ADDON_PATH),
                  actionArgs={'item_type': 'skip_intro'}).doModal()

    def _show_skip_intro_aniskip(self):
        from resources.lib.windows.skip_intro_aniskip import SkipIntro
        selected_theme = int(control.getSetting('general.dialog'))
        themes = ['skip_intro_default.xml', 'skip_intro_ah2.xml', 'skip_intro_auramod.xml']
        selected_theme = themes[selected_theme]
        SkipIntro(*(selected_theme, control.ADDON_PATH),
                  actionArgs={'item_type': 'skip_intro_aniskip'}).doModal()

    def _show_skip_outro_aniskip(self):
        from resources.lib.windows.skip_outro_aniskip import SkipOutro
        selected_theme = int(control.getSetting('general.dialog'))
        themes = ['skip_outro_default.xml', 'skip_outro_ah2.xml', 'skip_outro_auramod.xml']
        selected_theme = themes[selected_theme]
        SkipOutro(*(selected_theme, control.ADDON_PATH),
                  actionArgs=self._get_next_item_args()).doModal()

    @staticmethod
    def _get_next_item_args():
        current_position = playList.getposition()
        _next_info = playList[current_position + 1]
        next_info = {}
        next_info['thumb'] = _next_info.getArt('thumb')
        next_info['name'] = _next_info.getLabel()
        next_info['playnext'] = True
        return next_info

    @staticmethod
    def _is_video_window_open():

        if xbmcgui.getCurrentWindowId() != 12005:
            return False
        return True


def cancelPlayback():
    playList.clear()
    xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())


def _prefetch_play_link(link):
    if callable(link):
        link = link()

    if not link:
        return None
    url = link
    headers = {}

    if '|' in url:
        url, hdrs = link.split('|')
        headers = dict([item.split('=') for item in hdrs.split('&')])
        for header in headers:
            headers[header] = urllib_parse.unquote_plus(headers[header])

    limit = None if '.m3u8' in url else '0'
    linkInfo = client.request(url, headers=headers, limit=limit, output='extended', error=True)
    if linkInfo[1] != '200':
        raise Exception('could not resolve %s. status_code=%s' %
                        (link, linkInfo[1]))
    return {
        "url": link if '|' in link else linkInfo[5],
        "headers": linkInfo[2],
    }


def play_source(link, anilist_id=None, watchlist_update=None, build_playlist=None, episode=None, filter_lang=None, rescrape=False, source_select=False, subs=[]):
    try:
        if isinstance(link, tuple):
            link, subs = link
        linkInfo = _prefetch_play_link(link)
        if not linkInfo:
            cancelPlayback()
            return
    except Exception as e:
        cancelPlayback()
        control.ok_dialog('Otaku', str(e))
        return

    item = xbmcgui.ListItem(path=linkInfo['url'])
    if subs:
        utils.del_subs()
        subtitles = []
        for sub in subs:
            sub_url = sub.get('url')
            sub_lang = sub.get('lang')
            language = xbmc.getLanguage(xbmc.ENGLISH_NAME).split(' ')[0]
            if language.lower() in sub_lang.lower():
                subtitles.append(utils.get_sub(sub_url, sub_lang))
        item.setSubtitles(subtitles)

    if rescrape or source_select:
        episode_info = build_playlist(anilist_id, '', filter_lang, source_select=source_select, rescrape=rescrape)[episode - 1]
        item.setInfo('video', infoLabels=episode_info['info'])
        item.setArt(episode_info['image'])

    if 'Content-Type' in linkInfo['headers'].keys():
        item.setProperty('MimeType', linkInfo['headers']['Content-Type'])
        # Run any mimetype hook
        item = hook_mimetype.trigger(linkInfo['headers']['Content-Type'], item)

    xbmcplugin.setResolvedUrl(HANDLE, True, item)
    watchlistPlayer().handle_player(anilist_id, watchlist_update, build_playlist, episode, filter_lang)


@hook_mimetype('application/dash+xml')
def _DASH_HOOK(item):
    import inputstreamhelper
    is_helper = inputstreamhelper.Helper('mpd')
    if is_helper.check_inputstream():
        if control.getKodiVersion() < 19:
            item.setProperty('inputstreamaddon', is_helper.inputstream_addon)
        else:
            item.setProperty('inputstream', is_helper.inputstream_addon)
        item.setProperty('inputstream.adaptive.manifest_type', 'mpd')
        item.setContentLookup(False)
    else:
        raise Exception("InputStream Adaptive is not supported.")

    return item


@hook_mimetype('application/vnd.apple.mpegurl')
def _HLS_HOOK(item):
    stream_url = item.getPath()
    import inputstreamhelper
    is_helper = inputstreamhelper.Helper('hls')
    if '|' not in stream_url and is_helper.check_inputstream():
        if control._kodiver < 19:
            item.setProperty('inputstreamaddon', is_helper.inputstream_addon)
        else:
            item.setProperty('inputstream', is_helper.inputstream_addon)
        item.setProperty('inputstream.adaptive.manifest_type', 'hls')
    item.setProperty('MimeType', 'application/vnd.apple.mpegurl')
    item.setMimeType('application/vnd.apple.mpegstream_url')
    item.setContentLookup(False)

    return item
