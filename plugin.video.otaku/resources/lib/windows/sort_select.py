import os
import json

from resources.lib.windows.base_window import BaseWindow
from resources.lib.ui import control
from operator import itemgetter

# Define available sort methods
SORT_METHODS = ['none', 'source type', 'debrid provider', 'audio', 'subtitles', 'resolution', 'size', 'seeders', 'audio channels']

# Define sort options for each category
SORT_OPTIONS = {
    'sortmethod': SORT_METHODS,
    'none': [],
    "source type": ['files', 'cloud', 'torrent', 'hoster', 'embeds', "none"],
    "debrid provider": ['Real-Debrid', 'Premiumize', 'Alldebrid', 'Debrid-Link', 'Torbox', 'EasyDebrid', 'none'],
    "audio": ['multi-audio', 'dual-audio', 'sub', 'dub', 'none'],
    "subtitles": ['multi sub', 'none'],
    "resolution": [],
    "size": [],
    "seeders": [],
    "audio channels": []
}

# Define audio type mapping
audio = [0, 1, 2, 3, 'none']

# Define subtitle type mapping
subtitles = [0, 'none']

# Define debrid provider mapping
debrid_provider = [['Real-Debrid'], ['Premiumize'], ['Alldebrid'], ['Debrid-Link'], ['Torbox'], ['EasyDebrid'], ['none']]

# Define source type mapping
source_type = [['local'], ['cloud'], ['torrent', 'torrent (uncached)'], ['hoster'], ['direct', 'embed'], ['none']]

# Define default sort options
default_sort_options = {
    'sortmethod.1': 1,  # type
    'sortmethod.2': 5,  # resolution
    'sortmethod.3': 2,  # debrid provider
    'sortmethod.4': 3,  # audio
    'sortmethod.5': 4,  # subtitles
    'sortmethod.6': 8,  # audio channels
    'sortmethod.7': 6,  # size
    'sortmethod.8': 0,  # none
    'sortmethod.9': 0,  # none
    'sortmethod.1.reverse': False,
    'sortmethod.2.reverse': False,
    'sortmethod.3.reverse': False,
    'sortmethod.4.reverse': False,
    'sortmethod.5.reverse': False,
    'sortmethod.6.reverse': False,
    'sortmethod.7.reverse': False,
    'sortmethod.8.reverse': False,
    'sortmethod.9.reverse': False,
    'source type.1': 0,  # files
    'source type.2': 1,  # cloud
    'source type.3': 2,  # torrent
    'source type.4': 3,  # hoster
    'source type.5': 4,  # embeds
    'source type.6': 5,  # none
    'debrid provider.1': 0,  # Real-Debrid
    'debrid provider.2': 1,  # Premiumize
    'debrid provider.3': 2,  # Alldebrid
    'debrid provider.4': 3,  # Debrid-Link
    'debrid provider.5': 4,  # Torbox
    'debrid provider.6': 5,  # EasyDebrid
    'debrid provider.7': 6,  # none
    'audio.1': 0,  # multi-audio
    'audio.2': 1,  # dual-audio
    'audio.3': 2,  # sub
    'audio.4': 3,  # dub
    'audio.5': 4,  # none
    'subtitles.1': 0,  # multi-subs
    'subtitles.2': 1,  # none
}

# Define default sub options
default_sub_options = {
    'sortmethod.1': 1,  # type
    'sortmethod.2': 5,  # resolution
    'sortmethod.3': 2,  # debrid provider
    'sortmethod.4': 3,  # audio
    'sortmethod.5': 4,  # subtitles
    'sortmethod.6': 8,  # audio channels
    'sortmethod.7': 6,  # size
    'sortmethod.8': 0,  # none
    'sortmethod.9': 0,  # none
    'sortmethod.1.reverse': False,
    'sortmethod.2.reverse': False,
    'sortmethod.3.reverse': False,
    'sortmethod.4.reverse': False,
    'sortmethod.5.reverse': False,
    'sortmethod.6.reverse': False,
    'sortmethod.7.reverse': False,
    'sortmethod.8.reverse': False,
    'sortmethod.9.reverse': False,
    'source type.1': 0,  # files
    'source type.2': 1,  # cloud
    'source type.3': 2,  # torrent
    'source type.4': 3,  # hoster
    'source type.5': 4,  # embeds
    'source type.6': 5,  # none
    'debrid provider.1': 0,  # Real-Debrid
    'debrid provider.2': 1,  # Premiumize
    'debrid provider.3': 2,  # Alldebrid
    'debrid provider.4': 3,  # Debrid-Link
    'debrid provider.5': 4,  # Torbox
    'debrid provider.6': 5,  # EasyDebrid
    'debrid provider.7': 6,  # none
    'audio.1': 0,  # multi-audio
    'audio.2': 1,  # dual-audio
    'audio.3': 2,  # sub
    'audio.4': 3,  # dub
    'audio.5': 4,  # none
    'subtitles.1': 0,  # multi-subs
    'subtitles.2': 1,  # none
}

# Define default dub options
default_dub_options = {
    'sortmethod.1': 1,  # type
    'sortmethod.2': 5,  # resolution
    'sortmethod.3': 2,  # debrid provider
    'sortmethod.4': 3,  # audio
    'sortmethod.5': 4,  # subtitles
    'sortmethod.6': 8,  # audio channels
    'sortmethod.7': 6,  # size
    'sortmethod.8': 0,  # none
    'sortmethod.9': 0,  # none
    'sortmethod.1.reverse': False,
    'sortmethod.2.reverse': False,
    'sortmethod.3.reverse': False,
    'sortmethod.4.reverse': False,
    'sortmethod.5.reverse': False,
    'sortmethod.6.reverse': False,
    'sortmethod.7.reverse': False,
    'sortmethod.8.reverse': False,
    'sortmethod.9.reverse': False,
    'source type.1': 0,  # files
    'source type.2': 1,  # cloud
    'source type.3': 2,  # torrent
    'source type.4': 3,  # hoster
    'source type.5': 4,  # embeds
    'source type.6': 5,  # none
    'debrid provider.1': 0,  # Real-Debrid
    'debrid provider.2': 1,  # Premiumize
    'debrid provider.3': 2,  # Alldebrid
    'debrid provider.4': 3,  # Debrid-Link
    'debrid provider.5': 4,  # Torbox
    'debrid provider.6': 5,  # EasyDebrid
    'debrid provider.7': 6,  # none
    'audio.1': 0,  # multi-audio
    'audio.2': 1,  # dual-audio
    'audio.3': 3,  # sub
    'audio.4': 2,  # dub
    'audio.5': 4,  # none
    'subtitles.1': 0,  # multi-subs
    'subtitles.2': 1,  # none
}

# Define default multi-audio options
default_multi_audio_options = {
    'sortmethod.1': 1,  # type
    'sortmethod.2': 5,  # resolution
    'sortmethod.3': 2,  # debrid provider
    'sortmethod.4': 3,  # audio
    'sortmethod.5': 4,  # subtitles
    'sortmethod.6': 8,  # audio channels
    'sortmethod.7': 6,  # size
    'sortmethod.8': 0,  # none
    'sortmethod.9': 0,  # none
    'sortmethod.1.reverse': False,
    'sortmethod.2.reverse': False,
    'sortmethod.3.reverse': False,
    'sortmethod.4.reverse': False,
    'sortmethod.5.reverse': False,
    'sortmethod.6.reverse': False,
    'sortmethod.7.reverse': False,
    'sortmethod.8.reverse': False,
    'sortmethod.9.reverse': False,
    'source type.1': 0,  # files
    'source type.2': 1,  # cloud
    'source type.3': 2,  # torrent
    'source type.4': 3,  # hoster
    'source type.5': 4,  # embeds
    'source type.6': 5,  # none
    'debrid provider.1': 0,  # Real-Debrid
    'debrid provider.2': 1,  # Premiumize
    'debrid provider.3': 2,  # Alldebrid
    'debrid provider.4': 3,  # Debrid-Link
    'debrid provider.5': 4,  # Torbox
    'debrid provider.6': 5,  # EasyDebrid
    'debrid provider.7': 6,  # none
    'audio.1': 0,  # multi-audio
    'audio.2': 1,  # dual-audio
    'audio.3': 4,  # none
    'audio.4': 4,  # none
    'audio.5': 4,  # none
    'subtitles.1': 0,  # multi-subs
    'subtitles.2': 1,  # none
}

# Define default multi-sub options
default_multi_sub_options = {
    'sortmethod.1': 1,  # type
    'sortmethod.2': 5,  # resolution
    'sortmethod.3': 2,  # debrid provider
    'sortmethod.4': 4,  # subtitles
    'sortmethod.5': 3,  # audio
    'sortmethod.6': 8,  # audio channels
    'sortmethod.7': 6,  # size
    'sortmethod.8': 0,  # none
    'sortmethod.9': 0,  # none
    'sortmethod.1.reverse': False,
    'sortmethod.2.reverse': False,
    'sortmethod.3.reverse': False,
    'sortmethod.4.reverse': False,
    'sortmethod.5.reverse': False,
    'sortmethod.6.reverse': False,
    'sortmethod.7.reverse': False,
    'sortmethod.8.reverse': False,
    'sortmethod.9.reverse': False,
    'source type.1': 0,  # files
    'source type.2': 1,  # cloud
    'source type.3': 2,  # torrent
    'source type.4': 3,  # hoster
    'source type.5': 4,  # embeds
    'source type.6': 5,  # none
    'debrid provider.1': 0,  # Real-Debrid
    'debrid provider.2': 1,  # Premiumize
    'debrid provider.3': 2,  # Alldebrid
    'debrid provider.4': 3,  # Debrid-Link
    'debrid provider.5': 4,  # Torbox
    'debrid provider.6': 5,  # EasyDebrid
    'debrid provider.7': 6,  # none
    'audio.1': 0,  # multi-audio
    'audio.2': 1,  # dual-audio
    'audio.3': 4,  # none
    'audio.4': 4,  # none
    'audio.5': 4,  # none
    'subtitles.1': 0,  # multi-subs
    'subtitles.2': 1,  # none
}

try:
    with open(os.path.join(control.dataPath, 'sort_options.json')) as f:
        sort_options = json.load(f)
except FileNotFoundError:
    sort_options = default_sort_options


class SortSelect(BaseWindow):
    def __init__(self, xml_file, location):
        super().__init__(xml_file, location)
        self.sort_options = sort_options

    def onInit(self):
        self.populate_all_lists()
        self.setFocusId(9001)

    def onAction(self, action):
        actionID = action.getId()

        if actionID in [92, 10]:
            # BACKSPACE / ESCAPE
            self.close()

    def onClick(self, control_id):
        self.handle_action(control_id)

    @staticmethod
    def auto_action(preset):
        if preset == 0:
            sort_options = default_sub_options
        elif preset == 1:
            sort_options = default_dub_options
        elif preset == 2:
            sort_options = default_multi_audio_options
        elif preset == 3:
            sort_options = default_multi_sub_options
        # Save settings without needing self reference
        with open(os.path.join(control.dataPath, 'sort_options.json'), 'w') as file:
            json.dump(sort_options, file)

    def handle_action(self, control_id):
        if control_id == 9001:   # close
            self.close()
        elif control_id == 9002:  # save
            self.save_settings()
            control.ok_dialog(control.ADDON_NAME, 'Saved Sort Configuration')
        elif control_id == 9003:  # set default
            self.sort_options = default_sort_options
            self.save_settings()
            self.close()
            control.execute('RunPlugin(plugin://plugin.video.otaku/sort_select)')
        elif control_id == 9004:  # set Sub Preset
            self.sort_options = default_sub_options
            yesno = control.yesno_dialog(control.ADDON_NAME, "Warning: This will change your audio and subtitle playback settings including your souce type and customization settings to prioritize content. Continue?")
            if yesno:
                control.setInt('general.audio', 0)
                control.setInt('general.subtitles', 1)
                control.setBool('general.subtitles.keyword', True)
                control.setInt('subtitles.keywords', 1)
                control.setBool('general.dubsubtitles', False)
                control.setInt('general.source', 0)
                control.setBool('divflavors.showdub', False)
                control.setBool('jz.dub', False)
                self.save_settings()
                self.close()
                control.execute('RunPlugin(plugin://plugin.video.otaku/sort_select)')
                control.sleep(1000)
                control.ok_dialog(control.ADDON_NAME, 'Saved Sort Configuration')
        elif control_id == 9005:  # set Dub Preset
            self.sort_options = default_dub_options
            yesno = control.yesno_dialog(control.ADDON_NAME, "Warning: This will change your audio and subtitle playback settings including souce type and customization settings to prioritize content. Continue?")
            if yesno:
                control.setInt('general.audio', 1)
                control.setInt('general.subtitles', 0)
                control.setBool('general.subtitles.keyword', True)
                control.setInt('subtitles.keywords', 2)
                control.setBool('general.dubsubtitles', False)
                control.setInt('general.source', 0)
                control.setBool('divflavors.showdub', True)
                control.setBool('jz.dub', True)
                self.save_settings()
                self.close()
                control.execute('RunPlugin(plugin://plugin.video.otaku/sort_select)')
                control.sleep(1000)
                control.ok_dialog(control.ADDON_NAME, 'Saved Sort Configuration')
        elif control_id == 9006:  # set Multi-Audio Preset
            self.sort_options = default_multi_audio_options
            yesno = control.yesno_dialog(control.ADDON_NAME, "Warning: This Preset is for people who are searching for anime in foreign audio languages other than Japanese or English. Continue?")
            if yesno:
                control.setInt('general.source', 1)
                self.save_settings()
                self.close()
                control.execute('RunPlugin(plugin://plugin.video.otaku/sort_select)')
                control.sleep(1000)
                control.ok_dialog(control.ADDON_NAME, 'Saved Sort Configuration')
        elif control_id == 9007:  # set Multi-Sub Preset
            self.sort_options = default_multi_sub_options
            yesno = control.yesno_dialog(control.ADDON_NAME, "Warning: This Preset is for people who are searching for anime in foreign subtitle languages other than Japanese or English. Continue?")
            if yesno:
                control.setInt('general.source', 1)
                self.save_settings()
                self.close()
                control.execute('RunPlugin(plugin://plugin.video.otaku/sort_select)')
                control.sleep(1000)
                control.ok_dialog(control.ADDON_NAME, 'Saved Sort Configuration')
        elif control_id in [1111, 2222, 3333, 4444, 5555, 6666, 7777, 8888]:
            self.handle_reverse(int(control_id / 1111))
        else:
            self.cycle_info(int(control_id / 1000), (control_id % 1000) - 1)
            self.populate_all_lists()
            self.setFocusId(control_id)

    def reset_properties(self):
        for x in range(9):
            for j in range(7):
                self.clearProperty(f'sortmethod.{x}.label.{j}')

    def handle_reverse(self, level):
        setting = f"sortmethod.{level}.reverse"
        self.sort_options[setting] = not self.sort_options[setting]
        self.setProperty(setting, str(self.sort_options[setting]))

    def cycle_info(self, level, idx):
        sort_method = f"sortmethod.{level}"
        method = SORT_METHODS[self.sort_options[sort_method]]
        setting = sort_method if idx == 0 else f'{method}.{idx}'
        current = self.sort_options[setting]
        category = setting.split('.')[0]
        new = (current + 1) % len(SORT_OPTIONS[category])
        self.sort_options[setting] = new

    def populate_all_lists(self):
        self.reset_properties()
        for control_id in [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000]:
            self.populate_list(int(control_id / 1000))

    def populate_list(self, level):
        sort_method = f"sortmethod.{level}"
        method = SORT_METHODS[self.sort_options[sort_method]]
        options = SORT_OPTIONS[method]
        loops = len(options) + 1
        for idx in range(loops):
            if idx == 0:
                self.setProperty(f'sortmethod.{level}.label.{idx}', method)
            else:
                self.setProperty(f'sortmethod.{level}.label.{idx}', options[self.sort_options[f'{method}.{idx}']])
        self.setProperty(f"{sort_method}.reverse", str(self.sort_options[f"{sort_method}.reverse"]))
        self.setProperty(f"{sort_method}", method)

    def save_settings(self):
        with open(os.path.join(control.dataPath, 'sort_options.json'), 'w') as file:
            json.dump(self.sort_options, file)


def sort_by_none(list_, reverse):
    return list_


def sort_by_resolution(list_, reverse):
    list_.sort(key=itemgetter('quality'), reverse=reverse)
    return list_


def sort_by_size(list_, reverse):
    list_.sort(key=itemgetter('byte_size'), reverse=reverse)
    return list_


def sort_by_seeders(list_, reverse):
    list_.sort(key=itemgetter('seeders'), reverse=reverse)
    return list_


def sort_by_audio_channels(list_, reverse):
    list_.sort(key=itemgetter('channel'), reverse=reverse)
    return list_


def sort_by_debrid_provider(list_, reverse):
    # debrid_order = {provider: index for index, provider in enumerate(SORT_OPTIONS['debrid provider'])}
    # list_.sort(key=lambda x: debrid_order.get(x['debrid_provider'], float('inf')), reverse=reverse)
    for i in range(len(SORT_OPTIONS['debrid provider']), 0, -1):
        list_.sort(key=lambda x: x['debrid_provider'] in debrid_provider[int(sort_options[f'debrid provider.{i}'])], reverse=reverse)
    return list_


def sort_by_source_type(list_, reverse):
    def source_type_key(item):
        if item['type'] == 'torrent':
            return 0
        elif item['type'] == 'torrent (uncached)':
            return 1
        else:
            return 2

    list_.sort(key=source_type_key)
    for i in range(len(SORT_OPTIONS['source type']), 0, -1):
        list_.sort(key=lambda x: x['type'] in source_type[int(sort_options[f'source type.{i}'])], reverse=reverse)
    return list_


def sort_by_audio(list_, reverse):
    for i in range(len(SORT_OPTIONS['audio']), 0, -1):
        list_.sort(key=lambda x: x['lang'] == audio[int(sort_options[f'audio.{i}'])], reverse=reverse)
    return list_


def sort_by_subtitles(list_, reverse):
    for i in range(len(SORT_OPTIONS['subtitles']), 0, -1):
        list_.sort(key=lambda x: x['sub'] == subtitles[int(sort_options[f'subtitles.{i}'])], reverse=reverse)
    return list_
