import xbmc
import xbmcgui
import pickle
import service
import json

from resources.lib.ui import control, database
from resources.lib.endpoints import aniskip, anime_skip
from resources.lib import indexers


playList = control.playList
player = xbmc.Player

# from resources.lib import MetaBrowser


class WatchlistPlayer(player):
    def __init__(self):
        super(WatchlistPlayer, self).__init__()
        self.player = xbmc.Player()
        self.vtag = None
        self.episode = None
        self.mal_id = None
        self._watchlist_update = None
        self.current_time = 0
        self.updated = False
        self.media_type = None
        self.update_percent = control.getInt('watchlist.update.percent')
        self.resume = None
        self.path = ''
        self.context = False
        self._monitor = None
        self._skip_processed = False

        self.total_time = None
        self.delay_time = control.getInt('skipintro.delay')
        self.skipintro_aniskip_enable = control.getBool('skipintro.aniskip.enable')
        self.skipintro_aniskip_auto = control.getBool('skipintro.aniskip.auto')
        self.skipoutro_aniskip_enable = control.getBool('skipoutro.aniskip.enable')
        self.skipoutro_aniskip_auto = control.getBool('skipoutro.aniskip.auto')

        self.skipintro_aniskip = False
        self.skipoutro_aniskip = False
        self.skipintro_start = control.getInt('skipintro.delay')
        self.skipintro_end = self.skipintro_start + control.getInt('skipintro.duration') * 60
        self.skipoutro_start = 0
        self.skipoutro_end = 0
        self.skipintro_offset = control.getInt('skipintro.aniskip.offset')
        self.skipoutro_offset = control.getInt('skipoutro.aniskip.offset')

        self.preferred_audio = control.getInt('general.audio')
        self.preferred_subtitle_setting = control.getInt('general.subtitles')
        self.preferred_subtitle_type = control.getInt('subtitles.types')
        self.preferred_subtitle_keyword = control.getInt('subtitles.keywords')

    def handle_player(self, mal_id, watchlist_update, episode, resume, path, type, provider, context):
        self.mal_id = mal_id
        self._watchlist_update = watchlist_update
        self.episode = episode
        self.episodes = database.get_episode_list(self.mal_id)
        self.resume = resume
        self.path = path
        self.type = type
        self.provider = provider
        self.context = context

        # Process skip times asynchronously to not block playback
        if not self._skip_processed:
            self._async_process_skip_times()

        # Continue with playback initialization
        self.keepAlive()

    def _async_process_skip_times(self):
        """Process skip times in background to avoid blocking playback"""
        def _process():
            try:
                self.process_embed('aniwave')
                self.process_embed('hianime')
                self.process_aniskip()
                self.process_animeskip()
                self._skip_processed = True
            except Exception as e:
                control.log(f'Error processing skip times: {e}', 'error')

        import threading
        threading.Thread(target=_process, daemon=True).start()

    def onPlayBackStopped(self):
        control.closeAllDialogs()
        playList.clear()
        if self.context and self.path:
            if 10 < self.getWatchedPercent() < 90:
                query = {
                    'jsonrpc': '2.0',
                    'method': 'Files.SetFileDetails',
                    'params': {
                        'file': self.path,
                        'media': 'video',
                        'resume': {
                            'position': self.current_time,
                            'total': self.total_time
                        }
                    },
                    'id': 1
                }
                control.jsonrpc(query)

    def onPlayBackEnded(self):
        control.closeAllDialogs()

    def onPlayBackError(self):
        control.closeAllDialogs()
        playList.clear()

    def build_playlist(self):
        if not control.getBool('playlist.unaired'):
            from resources.lib.AnimeSchedule import get_anime_schedule
            airing_anime = get_anime_schedule(self.mal_id)

            if airing_anime and airing_anime.get('current_episode'):
                episode_count = airing_anime['current_episode']
                self.episodes = self.episodes[:episode_count]

        video_data = indexers.process_episodes(self.episodes, '') if self.episodes else []
        playlist = control.bulk_dir_list(video_data, True)[self.episode:]

        for i, item in enumerate(playlist):
            url, listitem = item[0], item[1]

            # Calculate the actual episode number based on playlist position
            actual_episode_number = self.episode + i + 1
            payload = f"{self.mal_id}/{actual_episode_number}"

            # Add context menu with correct episode number
            context_menu = [
                ('Playback Options', f'RunPlugin(plugin://{control.ADDON_ID}/playback_options/{payload})'),
                ('Marked as Watched [COLOR blue]WatchList[/COLOR]', f'RunPlugin(plugin://{control.ADDON_ID}/marked_as_watched/{payload})')
            ]
            listitem.addContextMenuItems(context_menu)

            control.playList.add(url=url, listitem=listitem)

    def getWatchedPercent(self):
        return (self.current_time / self.total_time) * 100 if self.total_time != 0 else 0

    def onWatchedPercent(self):
        if not self._watchlist_update:
            return

        while self.isPlaying() and not self.updated:
            self.current_time = self.getTime()
            watched_percentage = (self.current_time / self.total_time) * 100 if self.total_time != 0 else 0

            if watched_percentage > self.update_percent:
                any_completed = self._watchlist_update(self.mal_id, self.episode)
                self.updated = True

                # Sync completed watchlists if any flavor was auto-completed
                if any_completed:
                    xbmc.sleep(3000)
                    service.sync_watchlist(True)
                break
            xbmc.sleep(10000)  # Check every 10 seconds instead of 5

    def keepAlive(self):
        # Monitor the Playback with optimized wait
        self._monitor = Monitor()
        for i in range(40):  # Increased attempts but shorter waits
            if self._monitor.playbackerror:
                del self._monitor
                return control.log('playbackerror', 'warning')
            if self.isPlayingVideo() and self.getTotalTime() != 0:
                break
            self._monitor.waitForAbort(0.5)  # Check every 0.5 seconds

        # Check if the player is playing a video
        if not self.isPlayingVideo():
            if self._monitor:
                del self._monitor
            control.log('Failed to start video playback', 'warning')
            return

        # Grab the seek time if available
        if self.resume:
            self.seekTime(self.resume)

        # Grab the video tags
        self.vtag = self.getVideoInfoTag()
        self.media_type = self.vtag.getMediaType()
        self.total_time = int(self.getTotalTime())

        # Continue with the rest of the method after playback is confirmed
        unique_ids = database.get_unique_ids(self.mal_id, 'mal_id')

        # Trakt scrobbling support
        if control.getBool('trakt.enabled'):
            control.clearGlobalProp('script.trakt.ids')
            control.setGlobalProp('script.trakt.ids', json.dumps(unique_ids))

        # Optimized menu refresh logic - only refresh if actually changed
        previous_last_watched = control.getSetting('addon.last_watched')
        current_mal_id = str(self.mal_id)

        if previous_last_watched != current_mal_id:
            control.setSetting('addon.last_watched', current_mal_id)
            control.log(f'Last watched changed from {previous_last_watched} to {current_mal_id}')
            # Add to watch history
            from resources.lib import Main
            Main.save_to_watch_history(self.mal_id)
            # Defer refresh to avoid blocking playback
            control.setGlobalProp('otaku.menu.needs_refresh', 'true')
        else:
            control.log(f'Last watched unchanged ({current_mal_id}) - skipping updates')

        # Continue with audio/subtitle setup which is needed immediately
        if self.type not in ['embed', 'direct']:
            self.setup_audio_and_subtitles()
        elif self.provider in ['aniwave', 'h!anime']:
            self.setup_audio_and_subtitles()

        # Handle different media types
        if self.episodes:
            # Handle playlist building if needed
            if self.media_type == 'episode' and playList.size() == 1:
                self.build_playlist()

            # Handle skip intro functionality
            self._handle_skip_intro()

            # Handle watchlist updates for episodes
            self.onWatchedPercent()

            # Handle outro/playing next functionality
            self._handle_outro_and_playing_next()
        else:
            self.onWatchedPercent()

        # Optimized playback monitoring with longer sleep intervals
        while self.isPlaying():
            self.current_time = int(self.getTime())
            xbmc.sleep(10000)  # Reduced frequency from 5s to 10s

        # Cleanup
        if self._monitor:
            del self._monitor

    def _handle_skip_intro(self):
        """Handle skip intro functionality with fallbacks - optimized"""
        # Only proceed if skip intro dialog is enabled OR auto-skip is enabled
        if not (control.getBool('smartplay.skipintrodialog') or self.skipintro_aniskip_auto):
            return

        # Wait for skip times to be processed (with timeout)
        timeout = 30  # 30 iterations = 3 seconds max
        while not self._skip_processed and timeout > 0:
            xbmc.sleep(100)
            timeout -= 1

        # Determine intro times and whether we have aniskip data
        intro_start = self.skipintro_start if self.skipintro_aniskip else control.getInt('skipintro.delay') or 1
        intro_end = self.skipintro_end if self.skipintro_aniskip else intro_start + (control.getInt('skipintro.duration') * 60)

        if not self.skipintro_aniskip:
            control.log('Using default intro skip times - no aniskip data found')

        # Optimized monitoring - check less frequently
        while self.isPlaying():
            self.current_time = int(self.getTime())
            if self.current_time > intro_end:
                break
            elif self.current_time > intro_start:
                # Auto skip ONLY if enabled AND we have aniskip data
                if self.skipintro_aniskip_auto and self.skipintro_aniskip:
                    self.seekTime(intro_end)
                    control.log(f'Auto-skipped intro: {intro_start}-{intro_end}')
                else:
                    # Show skip intro dialog (works for both aniskip data and default times)
                    PlayerDialogs().show_skip_intro(self.skipintro_aniskip, intro_end)
                break
            xbmc.sleep(2000)  # Check every 2 seconds instead of 1

    def _handle_outro_and_playing_next(self):
        """Handle outro skip and playing next functionality with fallbacks - optimized"""
        # Get user's playing next setting
        playnext_enabled = control.getBool('smartplay.playingnextdialog')
        playnext_time = control.getInt('playingnext.time') if playnext_enabled else 0

        # Proceed if: playnext is enabled OR outro auto-skip is enabled
        if not (playnext_time > 0 or self.skipoutro_aniskip_auto):
            return

        while self.isPlaying():
            self.current_time = int(self.getTime())
            time_remaining = self.total_time - self.current_time

            # Handle auto skip outro (only if we have aniskip data)
            if self.skipoutro_aniskip_auto and self.skipoutro_aniskip and self.current_time >= self.skipoutro_start and self.skipoutro_start > 0:
                if self.skipoutro_end > 0:
                    self.seekTime(self.skipoutro_end)
                    control.log(f'Auto-skipped outro: {self.skipoutro_start}-{self.skipoutro_end}')
                break

            # Handle dialog display
            elif self._should_show_dialog(time_remaining, playnext_time):
                if self.skipoutro_aniskip and not self.skipoutro_aniskip_auto:
                    # Show skip outro dialog
                    PlayerDialogs().display_dialog(True, self.skipoutro_end)
                elif not self.skipoutro_aniskip and playnext_time > 0:
                    # Show regular playing next dialog
                    PlayerDialogs().display_dialog(False, 0)
                break

            xbmc.sleep(5000)  # Check every 5 seconds

    def _should_show_dialog(self, time_remaining, playnext_time):
        """Determine if we should show a dialog - simplified"""
        if self.skipoutro_aniskip and not self.skipoutro_aniskip_auto:
            return self.current_time >= self.skipoutro_start and self.skipoutro_start > 0
        elif not self.skipoutro_aniskip and playnext_time > 0:
            return time_remaining <= playnext_time
        return False

    def setup_audio_and_subtitles(self):
        """Handle audio and subtitle setup"""
        # This contains your existing audio/subtitle setup code from keepAlive
        if not control.getBool('general.kodi_language'):
            query = {
                'jsonrpc': '2.0',
                "method": "Player.GetProperties",
                "params": {
                    "playerid": 1,
                    "properties": ["subtitles", "audiostreams"]
                },
                "id": 1
            }

            audios = ['jpn', 'eng']

            subtitles = [
                "none", "eng", "jpn", "spa", "fre", "ger",
                "ita", "dut", "rus", "por", "kor", "chi",
                "ara", "hin", "tur", "pol", "swe", "nor",
                "dan", "fin"
            ]

            types = [
                "isdefault", "isforced", "isimpaired"
            ]

            keywords = {
                1: 'dialogue',
                2: ['signs', 'songs'],
                3: control.getSetting('subtitles.customkeyword')
            }

            response = control.jsonrpc(query)

            if 'result' in response:
                player_properties = response['result']
                audio_streams = player_properties.get('audiostreams', [])
                subtitle_streams = player_properties.get('subtitles', [])
            else:
                audio_streams = []
                subtitle_streams = []

            preferred_audio_streams = audios[self.preferred_audio]
            preferred_subtitle_lang = subtitles[self.preferred_subtitle_setting]
            preffeded_subtitle_type = types[self.preferred_subtitle_type]
            preffeded_subtitle_keyword = keywords[self.preferred_subtitle_keyword]

            # Set preferred audio stream
            for stream in audio_streams:
                if stream['language'] == preferred_audio_streams:
                    self.setAudioStream(stream['index'])
                    break
            else:
                # If no preferred audio stream is found, set to the default audio stream
                for stream in audio_streams:
                    if stream.get('isdefault', False):
                        self.setAudioStream(stream['index'])
                        break
                else:
                    # If no default audio stream is found, set to the first available audio stream
                    self.setAudioStream(audio_streams[0]['index'])

            # Set preferred subtitle stream
            subtitle_int = None

            # Lowercase preferred keyword(s) like sub_name_lower
            if isinstance(preffeded_subtitle_keyword, list):
                preffeded_subtitle_keyword = [kw.lower() for kw in preffeded_subtitle_keyword if isinstance(kw, str)]
            elif isinstance(preffeded_subtitle_keyword, str):
                preffeded_subtitle_keyword = preffeded_subtitle_keyword.lower()

            # Type and Keyword filtering
            if control.getBool('general.subtitles.keyword') or control.getBool('general.subtitles.type'):
                for index, sub in enumerate(subtitle_streams):

                    # Check for type match
                    if control.getBool('general.subtitles.type'):
                        if sub['language'] == preferred_subtitle_lang:
                            if sub[preffeded_subtitle_type]:
                                subtitle_int = index
                                break

                    # Check for keyword match
                    if control.getBool('general.subtitles.keyword'):
                        if sub['language'] == preferred_subtitle_lang:
                            sub_name_lower = sub['name'].lower()
                            if isinstance(preffeded_subtitle_keyword, list):
                                if any(kw in sub_name_lower for kw in preffeded_subtitle_keyword):
                                    subtitle_int = index
                                    break
                            elif preffeded_subtitle_keyword and preffeded_subtitle_keyword in sub_name_lower:
                                subtitle_int = index
                                break

                # fallback to first of preferred language if no type or keyword match
                if subtitle_int is None:
                    for index, sub in enumerate(subtitle_streams):
                        if sub['language'] == preferred_subtitle_lang:
                            subtitle_int = index
                            break
            else:
                # No type filter or keyword filter, just check for preferred language
                for index, sub in enumerate(subtitle_streams):
                    if sub['language'] == preferred_subtitle_lang:
                        subtitle_int = index
                        break

            if subtitle_int is None:
                # default-subtitle fallback
                for index, sub in enumerate(subtitle_streams):
                    if sub.get('isdefault', False):
                        subtitle_int = index
                        break
                else:
                    # If no default subtitle stream is found, set to the first available subtitle stream
                    subtitle_int = 0

            if subtitle_int is not None:
                self.setSubtitleStream(subtitle_int)

            # Enable and Disable Subtitles based on audio streams
            if len(audio_streams) == 1:
                if "jpn" not in audio_streams:
                    if control.getBool('general.dubsubtitles'):
                        if preferred_subtitle_lang == "none":
                            self.showSubtitles(False)
                        else:
                            self.showSubtitles(True)
                    else:
                        self.showSubtitles(False)

                if "eng" not in audio_streams:
                    if preferred_subtitle_lang == "none":
                        self.showSubtitles(False)
                    else:
                        self.showSubtitles(True)

            if len(audio_streams) > 1:
                if preferred_audio_streams == "eng":
                    if control.getBool('general.dubsubtitles'):
                        if preferred_subtitle_lang == "none":
                            self.showSubtitles(False)
                        else:
                            self.showSubtitles(True)
                    else:
                        self.showSubtitles(False)

                if preferred_audio_streams == "jpn":
                    if preferred_subtitle_lang == "none":
                        self.showSubtitles(False)
                    else:
                        self.showSubtitles(True)

    def process_aniskip(self):
        if self.skipintro_aniskip_enable and not self.skipintro_aniskip:
            skipintro_aniskip_res = aniskip.get_skip_times(self.mal_id, self.episode, 'op')
            if skipintro_aniskip_res:
                skip_times = skipintro_aniskip_res['results'][0]['interval']
                self.skipintro_start = int(skip_times['startTime']) + self.skipintro_offset
                self.skipintro_end = int(skip_times['endTime']) + self.skipintro_offset
                self.skipintro_aniskip = True

        if self.skipoutro_aniskip_enable and not self.skipoutro_aniskip:
            skipoutro_aniskip_res = aniskip.get_skip_times(self.mal_id, self.episode, 'ed')
            if skipoutro_aniskip_res:
                skip_times = skipoutro_aniskip_res['results'][0]['interval']
                self.skipoutro_start = int(skip_times['startTime']) + self.skipoutro_offset
                self.skipoutro_end = int(skip_times['endTime']) + self.skipoutro_offset
                self.skipoutro_aniskip = True

    def process_animeskip(self):
        show_meta = database.get_show_meta(self.mal_id)
        anilist_id = pickle.loads(show_meta['meta_ids'])['anilist_id']

        if (self.skipintro_aniskip_enable and not self.skipintro_aniskip) or (self.skipoutro_aniskip_enable and not self.skipoutro_aniskip):
            skip_times = anime_skip.get_time_stamps(anime_skip.get_episode_ids(str(anilist_id), int(self.episode)))
            intro_start = None
            intro_end = None
            outro_start = None
            outro_end = None
            if skip_times:
                for skip in skip_times:
                    if self.skipintro_aniskip_enable and not self.skipintro_aniskip:
                        if intro_start is None and skip['type']['name'] in ['Intro', 'New Intro', 'Branding']:
                            intro_start = int(skip['at'])
                        elif intro_end is None and intro_start is not None and skip['type']['name'] in ['Canon']:
                            intro_end = int(skip['at'])
                    if self.skipoutro_aniskip_enable and not self.skipoutro_aniskip:
                        if outro_start is None and skip['type']['name'] in ['Credits', 'New Credits']:
                            outro_start = int(skip['at'])
                        elif outro_end is None and outro_start is not None and skip['type']['name'] in ['Canon', 'Preview']:
                            outro_end = int(skip['at'])

            if intro_start is not None and intro_end is not None:
                self.skipintro_start = intro_start + self.skipintro_offset
                self.skipintro_end = intro_end + self.skipintro_offset
                self.skipintro_aniskip = True
            if outro_start is not None and outro_end is not None:
                self.skipoutro_start = int(outro_start) + self.skipoutro_offset
                self.skipoutro_end = int(outro_end) + self.skipoutro_offset
                self.skipoutro_aniskip = True

    def process_embed(self, embed):
        if self.skipintro_aniskip_enable and not self.skipintro_aniskip:
            embed_skipintro_start = control.getInt(f'{embed}.skipintro.start')
            if embed_skipintro_start != -1:
                self.skipintro_start = embed_skipintro_start + self.skipintro_offset
                self.skipintro_end = control.getInt(f'{embed}.skipintro.end') + self.skipintro_offset
                self.skipintro_aniskip = True
        if self.skipoutro_aniskip_enable and not self.skipoutro_aniskip:
            embed_skipoutro_start = control.getInt(f'{embed}.skipoutro.start')
            if embed_skipoutro_start != -1:
                self.skipoutro_start = embed_skipoutro_start + self.skipoutro_offset
                self.skipoutro_end = control.getInt(f'{embed}.skipoutro.end') + self.skipoutro_offset
                self.skipoutro_aniskip = True


class PlayerDialogs(xbmc.Player):
    def __init__(self):
        super(PlayerDialogs, self).__init__()
        self.playing_file = self.getPlayingFile()

    def display_dialog(self, skipoutro_aniskip, skipoutro_end):
        if playList.size() == 0 or playList.getposition() == (playList.size() - 1):
            return
        if self.playing_file != self.getPlayingFile() or not self.isPlayingVideo() or not self._is_video_window_open():
            return
        self._show_playing_next(skipoutro_aniskip, skipoutro_end)

    def _show_playing_next(self, skipoutro_aniskip, skipoutro_end):
        from resources.lib.windows.playing_next import PlayingNext
        args = self._get_next_item_args()
        args['skipoutro_end'] = skipoutro_end
        if skipoutro_aniskip:
            dialog_mapping = {
                0: 'skip_outro_default.xml',
                1: 'skip_outro_ah2.xml',
                2: 'skip_outro_auramod.xml',
                3: 'skip_outro_af.xml',
                4: 'skip_outro_af2.xml',
                5: 'skip_outro_az.xml',
                6: 'skip_outro_tb.xml'
            }

            setting_value = control.getInt('general.dialog')
            xml_file = dialog_mapping.get(setting_value)

            # Call PlayingNext with the retrieved XML file
            if xml_file:
                PlayingNext(xml_file, control.ADDON_PATH, actionArgs=args).doModal()
        else:
            dialog_mapping = {
                0: 'playing_next_default.xml',
                1: 'playing_next_ah2.xml',
                2: 'playing_next_auramod.xml',
                3: 'playing_next_af.xml',
                4: 'playing_next_af2.xml',
                5: 'playing_next_az.xml',
                6: 'playing_next_tb.xml'
            }

            setting_value = control.getInt('general.dialog')
            xml_file = dialog_mapping.get(setting_value)

            # Call PlayingNext with the retrieved XML file
            if xml_file:
                PlayingNext(xml_file, control.ADDON_PATH, actionArgs=args).doModal()

    @staticmethod
    def show_skip_intro(skipintro_aniskip, skipintro_end):
        from resources.lib.windows.skip_intro import SkipIntro
        args = {
            'item_type': 'skip_intro',
            'skipintro_aniskip': skipintro_aniskip,
            'skipintro_end': skipintro_end
        }

        dialog_mapping = {
            0: 'skip_intro_default.xml',
            1: 'skip_intro_ah2.xml',
            2: 'skip_intro_auramod.xml',
            3: 'skip_intro_af.xml',
            4: 'skip_intro_af2.xml',
            5: 'skip_intro_az.xml',
            6: 'skip_intro_tb.xml'
        }

        setting_value = control.getInt('general.dialog')
        xml_file = dialog_mapping.get(setting_value)

        # Call SkipIntro with the retrieved XML file
        if xml_file:
            SkipIntro(xml_file, control.ADDON_PATH, actionArgs=args).doModal()

    @staticmethod
    def _get_next_item_args():
        current_position = playList.getposition()
        _next_info = playList[current_position + 1]
        next_info = {
            'item_type': "playing_next",
            'thumb': [_next_info.getArt('thumb')],
            'name': _next_info.getLabel()
        }
        return next_info

    @staticmethod
    def _is_video_window_open():
        return False if xbmcgui.getCurrentWindowId() != 12005 else True


class Monitor(xbmc.Monitor):
    def __init__(self):
        super().__init__()
        self.playbackerror = False

    def onNotification(self, sender, method, data):
        if method == 'Player.OnStop':
            self.playbackerror = True
