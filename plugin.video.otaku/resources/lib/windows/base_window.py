import pickle
import random
import xbmcgui

from resources.lib.ui import control, database

# Session-based cache for artwork selections to avoid repeated random.choice() calls
_artwork_cache = {}


class BaseWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, xml_file, location, actionArgs=None):
        super().__init__(xml_file, location)

        control.closeBusyDialog()

        # Early exit for skip_intro to avoid unnecessary processing
        if actionArgs is None or actionArgs.get('item_type') == 'skip_intro':
            return

        # Cache mal_id for reuse
        self._mal_id = actionArgs.get('mal_id')
        item_type = actionArgs.get('item_type')

        # Initialize item_information
        if self._mal_id:
            show_data = database.get_show(self._mal_id)
            if show_data:
                self.item_information = pickle.loads(show_data['kodi_meta'])
                show_meta = database.get_show_meta(self._mal_id)
                if show_meta:
                    self.item_information.update(pickle.loads(show_meta.get('art')))
            else:
                self.item_information = {}
        elif item_type == 'playing_next':
            self.item_information = actionArgs
        else:
            self.item_information = {}

        # Set properties efficiently
        self._set_window_properties()

    def _set_window_properties(self):
        """Set window properties in a single method to reduce overhead"""
        # Handle thumb with caching
        thumb = self.item_information.get('thumb')
        if thumb:
            if isinstance(thumb, list):
                cache_key = f"thumb_{self._mal_id}"
                if cache_key in _artwork_cache:
                    thumb = _artwork_cache[cache_key]
                else:
                    thumb = random.choice(thumb)
                    _artwork_cache[cache_key] = thumb
            self.setProperty('item.art.thumb', thumb)

        # Handle fanart with new artwork.fanart setting and caching
        artwork_fanart_enabled = control.getBool('artwork.fanart')
        fanart = self.item_information.get('fanart')
        if not fanart or not artwork_fanart_enabled:
            fanart = control.OTAKU_FANART
        else:
            if isinstance(fanart, list):
                if control.getBool('context.otaku.fanartselect') and self._mal_id:
                    cache_key = f"fanart_{self._mal_id}"
                    if cache_key in _artwork_cache:
                        fanart = _artwork_cache[cache_key]
                    else:
                        # Get fanart selection using string lists
                        mal_ids = control.getStringList('fanart.mal_ids')
                        fanart_selections = control.getStringList('fanart.selections')
                        mal_id_str = str(self._mal_id)

                        try:
                            index = mal_ids.index(mal_id_str)
                            fanart_select = fanart_selections[index] if index < len(fanart_selections) else ''
                            fanart = fanart_select if fanart_select else random.choice(fanart)
                        except (ValueError, IndexError):
                            fanart = random.choice(fanart)
                        _artwork_cache[cache_key] = fanart
                else:
                    cache_key = f"fanart_{self._mal_id}"
                    if cache_key in _artwork_cache:
                        fanart = _artwork_cache[cache_key]
                    else:
                        fanart = random.choice(fanart)
                        _artwork_cache[cache_key] = fanart
            # If fanart is already a string (pre-selected), use it directly

        # Handle clearlogo with new artwork.clearlogo setting
        artwork_clearlogo_enabled = control.getBool('artwork.clearlogo')
        clearlogo = self.item_information.get('clearlogo', control.OTAKU_LOGO2_PATH)
        if not artwork_clearlogo_enabled:
            clearlogo = control.OTAKU_LOGO2_PATH
        elif isinstance(clearlogo, list):
            # This shouldn't happen with new code, but handle legacy data
            cache_key = f"clearlogo_{self._mal_id}"
            if cache_key in _artwork_cache:
                clearlogo = _artwork_cache[cache_key]
            else:
                clearlogo = random.choice(clearlogo)
                _artwork_cache[cache_key] = clearlogo
        # If clearlogo is already a string (pre-selected), use it directly

        # Set properties in batch
        if self.item_information.get('format') not in ['MOVIE', 'Movie']:
            self.setProperty('item.art.fanart', fanart)

        self.setProperty('item.art.poster', self.item_information.get('poster'))
        self.setProperty('item.art.clearlogo', clearlogo)
        self.setProperty('item.info.title', self.item_information.get('name'))

        # Movie-specific properties
        if self.item_information.get('format') in ['MOVIE', 'Movie']:
            self.setProperty('item.info.plot', self.item_information.get('plot'))
            self.setProperty('item.info.rating', str(self.item_information.get('rating')))
            self.setProperty('item.info.title', self.item_information.get('title_userPreferred'))

    def getControlList(self, control_id):
        """Get and check the control for the ControlList type.

        :param control_id: Control id to get and check for ControlList
        :type control_id: int
        :return: The checked control
        :rtype: xbmcgui.ControlList
        """
        try:
            ctrl = self.getControl(control_id)
        except RuntimeError as e:
            control.log(f'Control does not exist {control_id}', 'error')
            control.log(str(e), 'error')
            raise
        if not isinstance(ctrl, xbmcgui.ControlList):
            raise AttributeError(f"Control with Id {control_id} should be of type ControlList")
        return ctrl

    def close(self):
        """Override close to ensure cleanup"""
        # Clear references to prevent memory leaks
        self.item_information = None
        super().close()
