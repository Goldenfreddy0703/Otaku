import json
import os
import sys

from kodi_six import xbmc, xbmcgui, xbmcplugin
from resources.lib.ui import client, control, utils, database, maintenance
from six.moves import urllib_parse
from resources.lib.indexers import aniskip

HANDLE = control.HANDLE
playList = control.playList
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
        self.resume_time = None
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
        self.update_percent = int(control.getSetting('watchlist.update.percent'))
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

    def handle_player(self, anilist_id, watchlist_update, build_playlist, episode, filter_lang, skip=None, resume_time=None):
        self._anilist_id = anilist_id
        self._watchlist_update = watchlist_update
        self._build_playlist = build_playlist
        self._episode = episode
        self._filter_lang = filter_lang
        self.resume_time = resume_time

        if skip:
            self.skipintro_start_skip_time = skip.get('intro', {}).get('start', 0)
            self.skipintro_end_skip_time = skip.get('intro', {}).get('end', 9999)
            self.skipoutro_start_skip_time = skip.get('outro', {}).get('start', 0)
            self.skipoutro_end_skip_time = skip.get('outro', {}).get('end', 9999)
        else:
            if self.skipintro_aniskip_enable or self.skipoutro_aniskip_enable:
                # process skip times
                self.process_hianime()
                self.process_aniwave()
                self.process_aniskip()

        control.setSetting('skipintro.start.skip.time', str(self.skipintro_start_skip_time))
        control.setSetting('skipintro.end.skip.time', str(self.skipintro_end_skip_time))

        control.setSetting('skipoutro.start.skip.time', str(self.skipoutro_start_skip_time))
        control.setSetting('skipoutro.end.skip.time', str(self.skipoutro_end_skip_time))

        self.keepAlive()

    def process_aniskip(self):
        if self.skipintro_aniskip_enable:
            mal_id = database.get_show(self._anilist_id)['mal_id']
            skipintro_aniskip_res = aniskip.get_skip_times(mal_id, self._episode, 'op')
            if skipintro_aniskip_res:
                skip_times = skipintro_aniskip_res['results'][0]['interval']
                self.skipintro_start_skip_time = int(skip_times['startTime']) + self.skipintro_aniskip_offset
                self.skipintro_end_skip_time = int(skip_times['endTime']) + self.skipintro_aniskip_offset
                self.skipintro_aniskip = True

        if self.skipoutro_aniskip_enable:
            mal_id = database.get_show(self._anilist_id)['mal_id']
            skipoutro_aniskip_res = aniskip.get_skip_times(mal_id, self._episode, 'ed')
            if skipoutro_aniskip_res:
                skip_times = skipoutro_aniskip_res['results'][0]['interval']
                self.skipoutro_start_skip_time = int(skip_times['startTime']) + self.skipoutro_aniskip_offset
                self.skipoutro_end_skip_time = int(skip_times['endTime']) + self.skipoutro_aniskip_offset
                self.skipoutro_aniskip = True

    def process_aniwave(self):
        aniwave_start = int(control.getSetting('aniwave.skipintro.start'))
        aniwave_end = int(control.getSetting('aniwave.skipintro.start'))
        if aniwave_start != -1:
            self.skipintro_start_skip_time = aniwave_start + self.skipintro_aniskip_offset
            self.skipintro_end_skip_time = int(control.getSetting('aniwave.skipintro.end')) + self.skipintro_aniskip_offset
            self.skipintro_aniskip = True
        if aniwave_end != -1:
            self.skipoutro_start_skip_time = aniwave_end + self.skipoutro_aniskip_offset
            self.skipoutro_end_skip_time = int(control.getSetting('aniwave.skipoutro.end')) + self.skipoutro_aniskip_offset
            self.skipoutro_aniskip = True

    def process_hianime(self):
        hianime_start = int(control.getSetting('hianime.skipintro.start'))
        hianime_end = int(control.getSetting('hianime.skipoutro.start'))
        if hianime_start != -1:
            self.skipintro_start_skip_time = hianime_start + self.skipintro_aniskip_offset
            self.skipintro_end_skip_time = int(control.getSetting('hianime.skipintro.end')) + self.skipintro_aniskip_offset
            self.skipintro_aniskip = True
        if hianime_end != -1:
            self.skipoutro_start_skip_time = hianime_end + self.skipoutro_aniskip_offset
            self.skipoutro_end_skip_time = int(control.getSetting('hianime.skipoutro.end')) + self.skipoutro_aniskip_offset
            self.skipoutro_aniskip = True

    def onPlayBackStarted(self):
        if self._build_playlist and playList.size() == 1:
            self._build_playlist(self._anilist_id, self._episode, self._filter_lang)

        current_ = playList.getposition()
        try:
            self.media_type = playList[current_].getVideoInfoTag().getMediaType()
        except:
            self.media_type = ''
        control.setSetting('addon.last_watched', self._anilist_id)

    def onPlayBackStopped(self):
        control.closeAllDialogs()
        playList.clear()

    def onPlayBackError(self):
        control.closeAllDialogs()
        playList.clear()
        sys.exit(1)

    def onPlayBackEnded(self):
        control.closeAllDialogs()

    def getWatchedPercent(self):
        current_position = self.getTime()
        media_length = self.getTotalTime()
        return float(current_position) / float(media_length) * 100 if int(media_length) != 0 else 0

    def onWatchedPercent(self):
        if not self._watchlist_update:
            return

        while self.isPlaying() and not self.updated:
            watched_percentage = self.getWatchedPercent()
            self.current_time = self.getTime()

            if watched_percentage > self.update_percent:
                self._watchlist_update(self._anilist_id, self._episode)
                self.updated = True

                if playList.size() == 0 or playList.getposition() == (playList.size() - 1):
                    maintenance.sync_watchlist(True)

                break
            xbmc.sleep(5000)

    def keepAlive(self):
        for i in range(0, 480):
            if self.isPlayingVideo():
                break
            xbmc.sleep(250)

        control.closeAllDialogs()
        if self.resume_time:
            player().seekTime(self.resume_time)

        if control.getSetting('general.kodi_language') == 'false':
            # Subtitle Preferences
            subtitle_lang = self.getAvailableSubtitleStreams()
            subtitles = [
                "none", "eng", "jpn", "spa", "fre", "ger",
                "ita", "dut", "rus", "por", "kor", "chi",
                "ara", "hin", "tur", "pol", "swe", "nor",
                "dan", "fin"
            ]
            preferred_subtitle_setting = int(control.getSetting('general.subtitles'))

            if 0 <= preferred_subtitle_setting < len(subtitles):
                preferred_subtitle = subtitles[preferred_subtitle_setting]
            else:
                preferred_subtitle = "eng"

            try:
                subtitle_int = subtitle_lang.index(preferred_subtitle)
                self.setSubtitleStream(subtitle_int)
            except ValueError:
                subtitle_int = 0
                self.setSubtitleStream(subtitle_int)

            # Audio Preferences
            audio_lang = self.getAvailableAudioStreams()
            audios = ['jpn', 'eng']
            preferred_audio_setting = int(control.getSetting('general.audio'))

            if 0 <= preferred_audio_setting < len(audios):
                preferred_audio = audios[preferred_audio_setting]

            try:
                audio_int = audio_lang.index(preferred_audio)
                self.setAudioStream(audio_int)
            except ValueError:
                audio_int = 0
                self.setAudioStream(audio_int)

            if len(audio_lang) == 1:
                if "jpn" not in audio_lang:
                    if control.getSetting('general.dubsubtitles') == 'true':
                        if preferred_subtitle == "none":
                            self.showSubtitles(False)
                        else:
                            self.showSubtitles(True)
                    else:
                        self.showSubtitles(False)

                if "eng" not in audio_lang:
                    if preferred_subtitle == "none":
                        self.showSubtitles(False)
                    else:
                        self.showSubtitles(True)

            if len(audio_lang) > 1:
                if preferred_audio == "eng":
                    if control.getSetting('general.dubsubtitles') == 'true':
                        if preferred_subtitle == "none":
                            self.showSubtitles(False)
                        else:
                            self.showSubtitles(True)
                    else:
                        self.showSubtitles(False)

                if preferred_audio == "jpn":
                    if preferred_subtitle == "none":
                        self.showSubtitles(False)
                    else:
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
                    xbmc.sleep(3000)
                    try:
                        current_time = self.player.getTime()
                    except RuntimeError:
                        current_time = 0

                    if current_time < self.skipintro_start_skip_time:
                        xbmc.sleep(250)
                        continue
                    elif current_time < self.skipintro_end_skip_time:
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
            pass
        else:
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
        themes = ['playing_next_default.xml', 'playing_next_ah2.xml', 'playing_next_auramod.xml', 'playing_next_af.xml', 'playing_next_az.xml']
        selected_theme = themes[selected_theme]
        PlayingNext(*(selected_theme, control.ADDON_PATH),
                    actionArgs=self._get_next_item_args()).doModal()

    @staticmethod
    def _show_skip_intro():
        from resources.lib.windows.skip_intro import SkipIntro
        selected_theme = int(control.getSetting('general.dialog'))
        themes = ['skip_intro_default.xml', 'skip_intro_ah2.xml', 'skip_intro_auramod.xml', 'skip_intro_af.xml', 'skip_intro_az.xml']
        selected_theme = themes[selected_theme]
        SkipIntro(*(selected_theme, control.ADDON_PATH),
                  actionArgs={'item_type': 'skip_intro'}).doModal()

    def _show_skip_intro_aniskip(self):
        from resources.lib.windows.skip_intro_aniskip import SkipIntro
        selected_theme = int(control.getSetting('general.dialog'))
        themes = ['skip_intro_default.xml', 'skip_intro_ah2.xml', 'skip_intro_auramod.xml', 'skip_intro_af.xml', 'skip_intro_az.xml']
        selected_theme = themes[selected_theme]
        SkipIntro(*(selected_theme, control.ADDON_PATH),
                  actionArgs={'item_type': 'skip_intro_aniskip'}).doModal()

    def _show_skip_outro_aniskip(self):
        from resources.lib.windows.skip_outro_aniskip import SkipOutro
        selected_theme = int(control.getSetting('general.dialog'))
        themes = ['skip_outro_default.xml', 'skip_outro_ah2.xml', 'skip_outro_auramod.xml', 'skip_outro_af.xml', 'skip_outro_az.xml']
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

    # Check if link is a local file path
    if os.path.isfile(link):
        return {
            "url": link,
            "headers": {},
        }

    url = link
    headers = {}

    if '|' in url:
        url, hdrs = link.split('|')
        headers = dict([item.split('=') for item in hdrs.split('&')])
        for header in headers:
            headers[header] = urllib_parse.unquote_plus(headers[header])

    limit = None if '.m3u8' in url else '0'
    linkInfo = client.request(url, headers=headers, limit=limit, output='extended', error=True)
    if linkInfo[1] not in ['200', '201']:
        raise Exception('could not resolve %s. status_code=%s' %
                        (link, linkInfo[1]))
    return {
        "url": link if '|' in link else linkInfo[5],
        "headers": linkInfo[2],
    }


def play_source(link, anilist_id=None, watchlist_update=None, build_playlist=None, episode=None, filter_lang=None, rescrape=False, source_select=False, subs=None, resume_time=None):
    try:
        skip = None
        if isinstance(link, dict):
            subs = link.get('subs')
            skip = link.get('skip')
            link = link.get('url')
        linkInfo = _prefetch_play_link(link)
        if not linkInfo:
            cancelPlayback()
            return
    except Exception as e:
        cancelPlayback()
        control.ok_dialog('Otaku', str(e))
        return
    if subs is None:
        subs = []

    unique_ids = utils.get_unique_ids(anilist_id)
    item = control.make_listitem(labels={'unique_ids': unique_ids}, path=linkInfo['url'])

    # Trakt scrobbling support
    control.clearGlobalProp('script.trakt.ids')
    control.setGlobalProp('script.trakt.ids', json.dumps(unique_ids))

    if subs:
        utils.del_subs()
        subtitles = []
        if control.getSetting('provider.hianime_region') == 'false':
            languages = [
                "none", "english", "japanese", "spanish", "french", "german",
                "italian", "dutch", "russian", "portuguese", "korean", "chinese",
                "arabic", "hindi", "turkish", "polish", "swedish", "norwegian",
                "danish", "finnish"
            ]
            preferred_language_setting = int(control.getSetting('general.subtitles'))
            language = languages[preferred_language_setting].split(' ')[0].lower()
        else:
            language = xbmc.getLanguage(xbmc.ENGLISH_NAME).split(' ')[0].lower()
        subtitles = [utils.get_sub(x.get('url'), x.get('lang')) for x in subs if language in x.get('lang').lower()]
        if not subtitles:
            subtitles = [utils.get_sub(x.get('url'), x.get('lang')) for x in subs if 'english' in x.get('lang').lower()]
        item.setSubtitles(subtitles)

    if 'Content-Type' in linkInfo['headers'].keys():
        item.setProperty('MimeType', linkInfo['headers']['Content-Type'])
        # Run any mimetype hook
        item = hook_mimetype.trigger(linkInfo['headers']['Content-Type'], item)

    if rescrape or source_select:
        playList.add(linkInfo['url'], item)
        playlist_info = build_playlist(anilist_id, episode, filter_lang)
        episode_info = playlist_info[episode - 1]
        control.update_listitem(item, episode_info['info'])
        item.setArt(episode_info['image'])
        xbmc.Player().play(playList, item)
        watchlistPlayer().handle_player(anilist_id, watchlist_update, None, episode, filter_lang, skip, resume_time)
        return

    xbmcplugin.setResolvedUrl(control.HANDLE, True, item)
    watchlistPlayer().handle_player(anilist_id, watchlist_update, build_playlist, episode, filter_lang, skip)


@hook_mimetype('application/dash+xml')
def _DASH_HOOK(item):
    stream_url = item.getPath()
    import inputstreamhelper
    is_helper = inputstreamhelper.Helper('mpd')
    if is_helper.check_inputstream():
        if control.getKodiVersion() < 19:
            item.setProperty('inputstreamaddon', is_helper.inputstream_addon)
        else:
            item.setProperty('inputstream', is_helper.inputstream_addon)
        if control._kodiver < 20.9:
            item.setProperty('inputstream.adaptive.manifest_type', 'mpd')
        if '|' in stream_url:
            stream_url, headers = stream_url.split('|')
            item.setProperty('inputstream.adaptive.stream_headers', headers)
            if control._kodiver > 19.8:
                item.setProperty('inputstream.adaptive.manifest_headers', headers)
        item.setContentLookup(False)
    else:
        raise Exception("InputStream Adaptive is not supported.")

    return item


@hook_mimetype('application/vnd.apple.mpegurl')
def _HLS_HOOK(item):
    stream_url = item.getPath()
    import inputstreamhelper
    is_helper = inputstreamhelper.Helper('hls')
    if is_helper.check_inputstream():
        if control._kodiver < 19:
            item.setProperty('inputstreamaddon', is_helper.inputstream_addon)
        else:
            item.setProperty('inputstream', is_helper.inputstream_addon)
        if control._kodiver < 20.9:
            item.setProperty('inputstream.adaptive.manifest_type', 'hls')
        if '|' in stream_url:
            stream_url, headers = stream_url.split('|')
            item.setProperty('inputstream.adaptive.stream_headers', headers)
            if control._kodiver > 19.8:
                item.setProperty('inputstream.adaptive.manifest_headers', headers)
    item.setProperty('MimeType', 'application/vnd.apple.mpegurl')
    item.setMimeType('application/vnd.apple.mpegstream_url')
    item.setContentLookup(False)

    return item
