# -*- coding: utf-8 -*-

import time
from resources.lib.ui import control
from resources.lib.windows.base_window import BaseWindow
from resources.lib.windows.resolver import Resolver
from resources.lib.ui import database
from resources.lib.indexers import simkl
from resources.lib import OtakuBrowser as browser

class SourceSelect(BaseWindow):

    def __init__(self, xml_file, location, actionArgs=None, sources=None, anilist_id=None, rescrape=None, **kwargs):
        super(SourceSelect, self).__init__(xml_file, location, actionArgs=actionArgs)
        self.actionArgs = actionArgs
        self.sources = sources
        self.anilist_id = anilist_id
        self.rescrape = rescrape
        self.position = -1
        self.canceled = False
        self.display_list = None
        self.last_action = 0
        control.closeBusyDialog()
        self.stream_link = None
        anime_init = browser.OtakuBrowser().get_anime_init(actionArgs.get('anilist_id'), filter_lang=None)
        episode = int(actionArgs.get('episode'))
        if episode != '':
            seasonNum = anime_init[0][episode-1].get('info').get('season')
            episodeNum = anime_init[0][episode-1].get('info').get('episode')
            self.setProperty('item.info.season', str(seasonNum))
            self.setProperty('item.info.episode', str(episodeNum))
            self.setProperty('item.art.poster', anime_init[0][episode-1].get('image').get('poster'))
            self.setProperty('item.art.thumb', anime_init[0][episode-1].get('image').get('thumb'))
            self.setProperty('item.art.fanart', anime_init[0][episode-1].get('image').get('fanart'))
            self.setProperty('item.info.title', anime_init[0][episode-1].get('info').get('title'))
            self.setProperty('item.info.aired', anime_init[0][episode-1].get('info').get('aired'))
            self.setProperty('item.info.plot', anime_init[0][episode-1].get('info').get('plot'))
            try:
                year, month, day = anime_init[0][episode-1].get('info').get('aired', '0000-00-00').split('-')
            except:
                year =''
            self.setProperty('item.info.year', year)

    def onInit(self):
        
        self.display_list = self.getControl(1000)
        menu_items = []
        for idx, i in enumerate(self.sources):
            if not i:
                continue
            menu_item = control.menuItem(label='%s' % i['release_title'])
            for info in list(i.keys()):
                try:
                    value = i[info]
                    if type(value) == list:
                        value = [str(k) for k in value]
                        value = ' '.join(sorted(value))
                    # if info == 'size':
                    #     value = control.source_size_display(value)
                    menu_item.setProperty(info, str(value).replace('_', ' '))
                except UnicodeEncodeError:
                    menu_item.setProperty(info, i[info])

            menu_items.append(menu_item)
            self.display_list.addItem(menu_item)

        self.setFocusId(1000)

    def doModal(self):
        super(SourceSelect, self).doModal()
        return self.stream_link

    # def onClick(self, controlId):

    #     if controlId == 1000:
    #         self.handle_action(7)

    def handle_action(self, actionID):
        if (time.time() - self.last_action) < .5:
            return

        if actionID == 7 and self.getFocusId() == 1000:
            self.position = self.display_list.getSelectedPosition()
            self.resolve_item()

        if actionID == 92 or id == 10:
            self.stream_link = False
            self.close()

        self.last_action = time.time()

    def onAction(self, action):
        actionID = action.getId()

        if actionID in [7, 92, 10]:
            self.handle_action(actionID)

    def info_list_to_sorted_dict(self, info_list):
        info = {}

        info_struct = {
            'videocodec': {
                'AVC': ['x264', 'x 264', 'h264', 'h 264', 'avc'],
                'HEVC': ['x265', 'x 265', 'h265', 'h 265', 'hevc'],
                'XviD': ['xvid'],
                'DivX': ['divx'],
                'WMV': ['wmv']
            },
            'audiocodec': {
                'AAC': ['aac'],
                'DTS': ['dts'],
                'HD-MA': ['hd ma', 'hdma'],
                'ATMOS': ['atmos'],
                'TRUEHD': ['truehd', 'true hd'],
                'DD+': ['ddp', 'dd+', 'eac3'],
                'DD': [' dd ', 'dd2', 'dd5', 'dd7', ' ac3'],
                'MP3': ['mp3'],
                'WMA': [' wma ']
            },

            'audiochannels': {
                '2.0': ['2 0 ', '2 0ch', '2ch'],
                '5.1': ['5 1 ', '5 1ch', '6ch'],
                '7.1': ['7 1 ', '7 1ch', '8ch']
            }

        }

        for property in list(info_struct.keys()):
            for codec in list(info_struct[property].keys()):
                if codec in info_list:
                    info[property] = codec
                    break
        return info

    def resolve_item(self):
        if control.getSetting('general.autotrynext') == 'true':
            sources = self.sources[self.position:]
        else:
            sources = [self.sources[self.position]]

        if self.rescrape:
            selected_source = self.sources[self.position]
            selected_source['name'] = selected_source['release_title']
            database.addTorrentList(self.anilist_id, [selected_source], 2)

        resolver = Resolver(*('resolver.xml', control.ADDON_PATH), actionArgs=self.actionArgs)

        self.stream_link = resolver.doModal(sources, {}, False)

        if self.stream_link is None:
            return
        else:
            self.close()