# -*- coding: utf-8 -*-
__metaclass__ = type

from kodi_six import xbmc
from resources.lib.ui import control
from resources.lib.windows.get_sources_window import GetSources as DisplayWindow


class CancelProcess(Exception):
    pass


def getSourcesHelper(actionArgs):
    if control.getSetting('general.dialog') == '4':
        sources_window = Sources(*('get_sources_az.xml', control.ADDON_PATH),
                                 actionArgs={'func': 'null'})
    else:
        sources_window = Sources(*('get_sources.xml', control.ADDON_PATH),
                                 actionArgs={'func': 'null'})

    sources = sources_window.doModal()
    try:
        del sources_window
    except:
        pass
    return sources


class Sources(DisplayWindow):
    def __init__(self, xml_file, location, actionArgs=None):
        try:
            super(Sources, self).__init__(xml_file, location, actionArgs)
        except:
            self.args = actionArgs
            self.canceled = False

        self.torrent_threads = []
        self.hoster_threads = []
        self.torrentProviders = []
        self.hosterProviders = []
        self.language = 'en'
        self.torrentCacheSources = {}
        self.hosterSources = {}
        self.cloud_files = []
        self.local_files = []
        self.remainingProviders = []
        self.allTorrents = {}
        self.hosterDomains = {}
        self.torrents_qual_len = [0, 0, 0, 0]
        self.hosters_qual_len = [0, 0, 0, 0]
        self.trakt_id = ''
        self.silent = False
        self.return_data = (None, None, None)
        self.basic_windows = True
        self.progress = 1
        self.duplicates_amount = 0
        self.domain_list = []
        self.display_style = 0
        self.background_dialog = None
        self.running_providers = []

        self.line1 = ''
        self.line2 = ''
        self.line3 = ''

        self.host_domains = []
        self.host_names = []

    def getSources(self, args):
        try:
            # Extract arguments from url

            self.setProperty('process_started', 'true')
            self.progress = 50

            try:
                self.setProgress()
                self.setText("4K: %s | 1080: %s | 720: %s | SD: %s" % (
                    control.colorString(self.torrents_qual_len[0] + self.hosters_qual_len[0]),
                    control.colorString(self.torrents_qual_len[1] + self.hosters_qual_len[1]),
                    control.colorString(self.torrents_qual_len[2] + self.hosters_qual_len[2]),
                    control.colorString(self.torrents_qual_len[3] + self.hosters_qual_len[3]),
                ))

            except:
                import traceback
                traceback.print_exc()

            xbmc.sleep(5000)
            self.close()

        except:
            self.close()
            import traceback
            traceback.print_exc()
