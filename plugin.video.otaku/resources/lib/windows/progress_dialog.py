import xbmcgui


class Progress_dialog(xbmcgui.WindowXMLDialog):
    def __init__(self, xml, path, *args, **kwargs):
        super().__init__(xml, path)
        config = kwargs.get('config', {})
        self.heading = config.get('heading', '')
        self.text = config.get('text', '')
        self.qr_code = config.get('qr_code', '')
        self.percent = config.get('percent', 0)
        self._cancelled = False

    def onInit(self):
        self.getControl(3002).setLabel(self.heading)
        self.getControl(3005).setLabel(self.text)
        self.setProperty('qr_code', self.qr_code)
        self.getControl(3003).setPercent(self.percent)

    def onAction(self, action):
        actionID = action.getId()
        if actionID in [92, 10]:
            # BACKSPACE / ESCAPE
            self._cancelled = True
            self.close()

    def onClick(self, controlId):
        if controlId == 4001:  # Cancel button ID
            self._cancelled = True
            self.close()

    def update(self, percent=None, text=None):
        if percent is not None:
            self.getControl(3003).setPercent(percent)
        if text is not None:
            self.getControl(3005).setLabel(text)

    def iscanceled(self):
        return self._cancelled
