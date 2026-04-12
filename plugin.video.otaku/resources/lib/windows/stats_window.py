import xbmcgui


class StatsWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, xml_file, location, *, stats=None, heading=''):
        super().__init__(xml_file, location)
        self.stats = stats or {}
        self.heading = heading

    def run(self):
        self.doModal()

    def onInit(self):
        self._set_properties()

    def _set_properties(self):
        data = self.stats
        self.setProperty('otaku.heading', self.heading)

        # Summary stats
        total = data.get('total', 0)
        summary_keys = ['watching', 'completed', 'on_hold', 'dropped', 'plan_to_watch']
        for key in summary_keys:
            value = data.get(key, 0)
            self.setProperty(f'otaku.stats.{key}', f'{value:,}')

        self.setProperty('otaku.stats.total', f'{total:,}')

        # Score distribution bars
        scores = {s['score']: s for s in data.get('scores', [])}
        max_pct = max((s.get('percentage', 0) for s in scores.values()), default=1) or 1
        for i in range(1, 11):
            s = scores.get(i, {})
            pct = s.get('percentage', 0)
            votes = s.get('votes', 0)
            bar_pct = pct / max_pct * 100 if max_pct > 0 else 0
            self.getControl(4000 + i).setPercent(bar_pct)
            self.setProperty(f'otaku.stats.score{i}.pct', f'{pct}%')
            self.setProperty(f'otaku.stats.score{i}.votes', f'({votes} votes)')

    def onAction(self, action):
        action_id = action.getId()
        if action_id in (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU):
            self.close()

    def onClick(self, control_id):
        if control_id == 3001:
            self.close()
