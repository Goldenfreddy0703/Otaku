from xbmcgui import WindowXMLDialog


class TextViewerXML(WindowXMLDialog):
    def __init__(self, xmlFilename: str, scriptPath: str, *args, **kwargs):
        super().__init__(xmlFilename, scriptPath)
        self.heading = kwargs.get('heading')
        self.migration_text = kwargs.get('migration_text')
        self.instructions_text = kwargs.get('instructions_text')
        self.changelog_text = kwargs.get('changelog_text')
        self.news_text = kwargs.get('news_text')
        self.actioned = None

    def run(self):
        self.doModal()
        self.clearProperties()

    def onInit(self):
        self.set_properties()
        self.setFocusId(2060)

    def onClick(self, controlID):
        self.handle_action(controlID)

    def handle_action(self, controlID):
        if controlID in [2060, 1941]:  # Handle scrollbar actions
            self.actioned = True
            self.close()

    def onAction(self, action):
        actionID = action.getId()

        if actionID in [92, 10]:
            # BACKSPACE / ESCAPE
            self.close()

        if actionID == 7:
            # ENTER
            self.handle_action(actionID)

    def set_properties(self):
        self.setProperty('otaku.news_text', self.news_text)
        self.setProperty('otaku.changelog_text', self.changelog_text)
        self.setProperty('otaku.text', self.instructions_text)
        self.setProperty('otaku.text', self.migration_text)
        self.setProperty('otaku.heading', self.heading)
