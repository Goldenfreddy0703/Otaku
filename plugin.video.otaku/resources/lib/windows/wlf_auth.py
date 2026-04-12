import pyqrcode
import os

from resources.lib.ui import control
from resources.lib.windows.base_window import BaseWindow


class WatchlistFlavorAuth(BaseWindow):
    def __init__(self, xml_file, location, flavor=None):
        super().__init__(xml_file, location)
        self.flavor = flavor
        self.authorized = False

    def onInit(self):
        qr_path = os.path.join(control.dataPath, 'qr_code.png')
        url = f"https://armkai.vercel.app/api/{self.flavor}"
        copy = control.copy2clip(url)
        if copy:
            self.setProperty('copy2clip', control.lang(30083))
        else:
            self.clearProperty('copy2clip')
        qr = pyqrcode.create(url)
        qr.png(qr_path, scale=20)
        self.setProperty('qr_code', qr_path)
        control.closeBusyDialog()
        self.setFocusId(1000)

    def doModal(self):
        super(WatchlistFlavorAuth, self).doModal()
        return self.authorized

    def onClick(self, controlId):
        if controlId == 1000:
            self.handle_action(7)
        else:
            self.handle_action(controlId)

    def onTouch(self, x, y):
        """Handle touchscreen events"""
        focusedControl = self.getFocusId()
        # Handle touch on button controls (1002 = Authorize, 1003 = Cancel)
        if focusedControl in [1002, 1003]:
            self.handle_action(focusedControl)

    def handle_action(self, actionID):
        if actionID == 1002:
            # Authorize button clicked
            self.set_settings()
        elif actionID == 1003:
            # Cancel button clicked
            self.close()
        elif actionID == 7 and self.getFocusId() == 1002:
            self.set_settings()
        elif actionID == 7 and self.getFocusId() == 1003:
            self.close()

    def onAction(self, action):
        actionID = action.getId()

        if actionID in [92, 10]:
            # BACKSPACE / ESCAPE
            self.close()

        if actionID == 7:
            # ENTER
            self.handle_action(7)

    def set_settings(self):
        res = {}
        if self.flavor == 'anilist':
            res['username'] = self.getControl(1000).getText()
            res['token'] = self.getControl(1001).getText()
        else:
            res['authvar'] = self.getControl(1000).getText()

        for _id, value in list(res.items()):
            control.setSetting('%s.%s' % (self.flavor, _id), value)

        self.authorized = True
        self.close()
