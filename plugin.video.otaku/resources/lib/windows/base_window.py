__metaclass__ = type

# import os
import pickle
from resources.lib.ui import control, database
import random


class BaseWindow(control.xmlWindow):

    def __init__(self, xml_file, location, actionArgs=None):

        try:
            super(BaseWindow, self).__init__(xml_file, location)
        except:
            control.xmlWindow().__init__()

        control.closeBusyDialog()
        self.canceled = False
        self._title_lang = control.title_lang(control.getSetting("general.titlelanguage"))
        self.setProperty('otaku.logo', control.OTAKU_LOGO_PATH)
        self.setProperty('otaku.fanart', control.OTAKU_FANART_PATH)
        self.setProperty('settings.color', 'deepskyblue')
        # self.setProperty('test.pattern', os.path.join(control.IMAGES_PATH, 'test_pattern.png'))

        if actionArgs is None:
            return

        if actionArgs.get('anilist_id'):
            self.item_information = pickle.loads(database.get_show(actionArgs['anilist_id'])['kodi_meta'])
            show_meta = database.get_show_meta(actionArgs['anilist_id'])
            if show_meta:
                self.item_information.update(pickle.loads(show_meta.get('art')))
        elif actionArgs.get('playnext'):
            self.item_information = actionArgs
        else:
            self.item_information = {}

        self.setProperty('item.ids.%s_id' % 1, str('gh'))

        thumb = self.item_information.get('thumb')
        if thumb and isinstance(thumb, list):
            thumb = random.choice(thumb)

        fanart = self.item_information.get('fanart')
        clearlogo = self.item_information.get('clearlogo', control.OTAKU_LOGO2_PATH)

        if not actionArgs.get('playnext') and not fanart:
            fanart = control.OTAKU_FANART_PATH

        if isinstance(fanart, list) and len(fanart) > 0:
            fanart = control.OTAKU_FANART_PATH if control.getSetting('scraping.fanart') == 'true' else random.choice(fanart)
        if isinstance(clearlogo, list) and len(clearlogo) > 0:
            clearlogo = control.OTAKU_LOGO2_PATH if control.getSetting('scraping.clearlogo') == 'true' else random.choice(clearlogo)

        self.setProperty('item.art.thumb', thumb if thumb else fanart)
        self.setProperty('item.art.poster', self.item_information.get('poster'))
        self.setProperty('item.art.fanart', fanart)
        self.setProperty('item.art.clearlogo', clearlogo if clearlogo else control.OTAKU_LOGO2_PATH)
        self.setProperty('item.art.logo', clearlogo if clearlogo else control.OTAKU_LOGO_PATH)
        self.setProperty('item.info.title', self.item_information.get('name'))
        if self.item_information.get('format') == 'MOVIE':
            self.setProperty('item.info.plot', self.item_information.get('plot'))
            self.setProperty('item.info.rating', str(self.item_information.get('rating')))
            if self._title_lang == 'english':
                title = self.item_information.get('ename') or self.item_information.get('title_userPreferred')
            else:
                title = self.item_information.get('name')
            self.setProperty('item.info.title', title)

        # self.item_information['info'] = tools.clean_air_dates(self.item_information['info'])
        # year, month, day = self.item_information['info'].get('aired', '0000-00-00').split('-')

        # self.setProperty('item.info.aired.year', '2018')
        # self.setProperty('item.info.aired.month', '01')
        # self.setProperty('item.info.aired.day', '01')

        # try:
        #     if 'aired' in self.item_information['info']:
        #         aired_date = self.item_information['info']['aired']
        #         aired_date = tools.datetime_workaround(aired_date)
        #         aired_date = aired_date.strftime(tools.get_region('dateshort'))
        #         self.item_information['info']['aired'] = aired_date

        #     if 'premiered' in self.item_information['info']:
        #         premiered = self.item_information['info']['premiered']
        #         premiered = tools.datetime_workaround(premiered)
        #         premiered = premiered.strftime(tools.get_region('dateshort'))
        #         self.item_information['info']['premiered'] = premiered
        # except:
        #     pass

        # value = 'TBA'
        # try:
        #     self.setProperty('item.info.%s' % 1, str('fdf'))
        # except UnicodeEncodeError:
        #     self.setProperty('item.info.%s' % 1, 'fdf')
