import os
import json

from resources.lib.windows.base_window import BaseWindow
from resources.lib.ui import control

# Define available sort methods
SORT_METHODS = ['none', 'source type', 'debrid provider', 'audio', 'subtitles', 'resolution', 'size', 'seeders', 'audio channels']

# Define sort options for each category
SORT_OPTIONS = {
    'sortmethod': SORT_METHODS,
    'none': [],
    "source type": ['files', 'cloud', 'torrent', 'hoster', 'embeds', "none"],
    "debrid provider": ['Real-Debrid', 'Premiumize', 'Alldebrid', 'Debrid-Link', 'Torbox', 'EasyDebrid', 'Easynews', 'none'],
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
    'debrid provider.7': 6,  # Easynews
    'debrid provider.8': 7,  # none
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
    'debrid provider.7': 6,  # Easynews
    'debrid provider.8': 7,  # none
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
    'debrid provider.7': 6,  # Easynews
    'debrid provider.8': 7,  # none
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
    'debrid provider.7': 6,  # Easynews
    'debrid provider.8': 7,  # none
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
    'debrid provider.7': 6,  # Easynews
    'debrid provider.8': 7,  # none
    'audio.1': 0,  # multi-audio
    'audio.2': 1,  # dual-audio
    'audio.3': 4,  # none
    'audio.4': 4,  # none
    'audio.5': 4,  # none
    'subtitles.1': 0,  # multi-subs
    'subtitles.2': 1,  # none
}


def load_sort_options():
    """Merge JSON on disk with defaults (Seren-style), so new keys keep working."""
    path = os.path.join(control.dataPath, 'sort_options.json')
    merged = dict(default_sort_options)
    try:
        with open(path) as f:
            merged.update(json.load(f))
    except FileNotFoundError:
        pass
    return merged


sort_options = load_sort_options()


def _setting_category(setting_key):
    """'source type.2' -> 'source type'; 'sortmethod.1' -> 'sortmethod'."""
    return setting_key.rsplit('.', 1)[0]


def _source_type_bucket(source):
    t = source.get('type') or ''
    if t == 'local':
        return 'files'
    if t == 'cloud':
        return 'cloud'
    if t in ('torrent', 'torrent (uncached)'):
        return 'torrent'
    if t == 'hoster':
        return 'hoster'
    if t in ('direct', 'embed'):
        return 'embeds'
    return 'none'


def _source_type_priorities(opts):
    labels = SORT_OPTIONS['source type']
    pri = {}
    for i in range(1, len(labels) + 1):
        key = f'source type.{i}'
        if key not in opts:
            continue
        label = labels[opts[key]]
        pri[label] = -i
    return pri


_DEBRID_UI_TO_CANONICAL = {
    'Real-Debrid': 'Real-Debrid',
    'Premiumize': 'Premiumize',
    'Alldebrid': 'Alldebrid',
    'Debrid-Link': 'Debrid-Link',
    'Torbox': 'TorBox',
    'EasyDebrid': 'EasyDebrid',
    'Easynews': 'Easynews',
}


def _normalize_debrid_provider(value):
    if value is None:
        return ''
    v = str(value).strip()
    return _DEBRID_UI_TO_CANONICAL.get(v, _DEBRID_UI_TO_CANONICAL.get(v.title(), v))


def _debrid_priorities(opts):
    labels = SORT_OPTIONS['debrid provider']
    pri = {}
    for i in range(1, len(labels) + 1):
        key = f'debrid provider.{i}'
        if key not in opts:
            continue
        label = labels[opts[key]]
        if label == 'none':
            continue
        canon = _DEBRID_UI_TO_CANONICAL.get(label, label)
        pri[canon] = -i
    return pri


def _audio_priorities(opts):
    labels = SORT_OPTIONS['audio']
    pri = {}
    for i in range(1, len(labels) + 1):
        key = f'audio.{i}'
        if key not in opts:
            continue
        lang_val = audio[opts[key]]
        if lang_val == 'none':
            continue
        pri[lang_val] = -i
    return pri


def _subtitle_priorities(opts):
    labels = SORT_OPTIONS['subtitles']
    pri = {}
    for i in range(1, len(labels) + 1):
        key = f'subtitles.{i}'
        if key not in opts:
            continue
        sub_val = subtitles[opts[key]]
        if sub_val == 'none':
            continue
        pri[sub_val] = -i
    return pri


def _quality_key(source):
    q = source.get('quality')
    return int(q) if q is not None else 0


def _size_key(source):
    bs = source.get('byte_size')
    if bs is None or not isinstance(bs, (int, float)):
        return 0.0
    return float(bs)


def _seeders_key(source):
    s = source.get('seeders')
    if s is None or not isinstance(s, (int, float)):
        return -1.0
    return float(s)


def _audio_channels_key(source):
    c = source.get('channel', 3)
    return {2: 3, 1: 2, 0: 1}.get(c, 0)


def _build_sort_key_tuples(opts):
    """
    Seren-style tuple sort: each key returns a value where *higher* is better.
    First 'none' sort row ends the chain (matching Seren's SourceSorter); rows
    below it are ignored so priority order stays explicit in the UI.
    """
    tuples = []
    for level in range(1, 10):
        midx = int(opts.get(f'sortmethod.{level}', 0))
        name = SORT_METHODS[midx]
        if name == 'none':
            break
        reverse = bool(opts.get(f'sortmethod.{level}.reverse', False))

        if name == 'source type':
            pri = _source_type_priorities(opts)
            tuples.append((lambda s, p=pri: p.get(_source_type_bucket(s), -99), reverse))
        elif name == 'debrid provider':
            pri = _debrid_priorities(opts)
            tuples.append((lambda s, p=pri: p.get(_normalize_debrid_provider(s.get('debrid_provider')), -99), reverse))
        elif name == 'audio':
            pri = _audio_priorities(opts)
            tuples.append((lambda s, p=pri: p.get(s.get('lang'), -99), reverse))
        elif name == 'subtitles':
            pri = _subtitle_priorities(opts)
            tuples.append((lambda s, p=pri: p.get(s.get('sub'), -99), reverse))
        elif name == 'resolution':
            tuples.append((_quality_key, reverse))
        elif name == 'size':
            tuples.append((_size_key, reverse))
        elif name == 'seeders':
            tuples.append((_seeders_key, reverse))
        elif name == 'audio channels':
            tuples.append((_audio_channels_key, reverse))
    return tuples


def sort_sources_list(sources_list, sort_options_dict=None):
    """
    Sort streams like Seren: stable tie-break on title, then one multi-key descending sort.
    Always reads fresh JSON unless sort_options_dict is passed.
    """
    if not sources_list:
        return []
    opts = sort_options_dict if sort_options_dict is not None else load_sort_options()
    tuples = _build_sort_key_tuples(opts)
    if not tuples:
        return sources_list
    ordered = sorted(sources_list, key=lambda s: (s.get('release_title') or '').lower())
    return sorted(
        ordered,
        key=lambda s, t=tuples: tuple(-fn(s) if rev else fn(s) for fn, rev in t),
        reverse=True,
    )


class SortSelect(BaseWindow):
    def __init__(self, xml_file, location):
        super().__init__(xml_file, location)
        self.max_level = 8
        self.sort_options = load_sort_options()

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
        global sort_options
        if preset == 0:
            sort_options = dict(default_sub_options)
        elif preset == 1:
            sort_options = dict(default_dub_options)
        elif preset == 2:
            sort_options = dict(default_multi_audio_options)
        elif preset == 3:
            sort_options = dict(default_multi_sub_options)
        else:
            return
        with open(os.path.join(control.dataPath, 'sort_options.json'), 'w') as file:
            json.dump(sort_options, file)

    def handle_action(self, control_id):
        if control_id == 9001:   # close
            self.close()
        elif control_id == 9002:  # save
            self.save_settings()
            control.ok_dialog(control.ADDON_NAME, 'Saved Sort Configuration')
        elif control_id == 9003:  # set default
            self.sort_options = dict(default_sort_options)
            self.save_settings()
            self.close()
            control.execute('RunPlugin(plugin://plugin.video.otaku/sort_select)')
        elif control_id == 9004:  # set Sub Preset
            self.sort_options = dict(default_sub_options)
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
            self.sort_options = dict(default_dub_options)
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
            self.sort_options = dict(default_multi_audio_options)
            yesno = control.yesno_dialog(control.ADDON_NAME, "Warning: This Preset is for people who are searching for anime in foreign audio languages other than Japanese or English. Continue?")
            if yesno:
                control.setInt('general.source', 1)
                self.save_settings()
                self.close()
                control.execute('RunPlugin(plugin://plugin.video.otaku/sort_select)')
                control.sleep(1000)
                control.ok_dialog(control.ADDON_NAME, 'Saved Sort Configuration')
        elif control_id == 9007:  # set Multi-Sub Preset
            self.sort_options = dict(default_multi_sub_options)
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
        for x in range(1, 9):
            for j in range(8):
                self.clearProperty(f'sortmethod.{x}.label.{j}')
                self.clearProperty(f'sortmethod.{x}.label.{j}.last')

    def handle_reverse(self, level):
        sort_method_key = f'sortmethod.{level}'
        setting = f"{sort_method_key}.reverse"
        self.sort_options[setting] = not self.sort_options[setting]
        self.setProperty(setting, str(self.sort_options[setting]))

    def cycle_info(self, level, idx):
        sort_method = f"sortmethod.{level}"
        method = SORT_METHODS[self.sort_options[sort_method]]
        setting = sort_method if idx == 0 else f'{method}.{idx}'
        current = self.sort_options[setting]
        category = _setting_category(setting)
        new = (current + 1) % len(SORT_OPTIONS[category])
        self.sort_options[setting] = new

    def populate_all_lists(self):
        self.max_level = 8
        self.reset_properties()
        for control_id in (1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000):
            self.populate_list(int(control_id / 1000))
        self.setProperty('max_level', str(self.max_level))

    def populate_list(self, level):
        sort_method_key = f'sortmethod.{level}'
        try:
            midx = int(self.sort_options[sort_method_key])
        except (KeyError, TypeError, ValueError):
            midx = 0
        method = SORT_METHODS[midx]
        options = SORT_OPTIONS[method]
        loops = len(options) + 1

        last_skip = False
        for idx in range(loops):
            if last_skip:
                continue
            if self.max_level < level:
                continue

            label_prop = f'sortmethod.{level}.label.{idx}'

            if idx == 0:
                self.setProperty(label_prop, method)
                if method == 'none':
                    self.max_level = level
                if method == 'none' or loops == 1:
                    self.setProperty(f'{label_prop}.last', 'True')
                else:
                    self.clearProperty(f'{label_prop}.last')
            else:
                if not options:
                    continue
                label = options[self.sort_options[f'{method}.{idx}']]
                self.setProperty(label_prop, label)
                if label == 'none' and method in (
                    'source type',
                    'debrid provider',
                    'audio',
                    'subtitles',
                ):
                    last_skip = True
                    self.setProperty(f'{label_prop}.last', 'True')
                elif idx == loops - 1:
                    self.setProperty(f'{label_prop}.last', 'True')
                else:
                    self.clearProperty(f'{label_prop}.last')

        slug = method.replace(' ', '_')
        self.setProperty(f'{sort_method_key}.slug', slug)
        self.setProperty(
            f'{sort_method_key}.reverse',
            str(self.sort_options.get(f'{sort_method_key}.reverse', False)),
        )
        self.setProperty(sort_method_key, method)

    def save_settings(self):
        global sort_options
        with open(os.path.join(control.dataPath, 'sort_options.json'), 'w') as file:
            json.dump(self.sort_options, file)
        sort_options = dict(self.sort_options)
