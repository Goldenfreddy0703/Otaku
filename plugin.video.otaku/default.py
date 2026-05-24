# -*- coding: utf-8 -*-
"""
    Otaku Add-on

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import sys

from resources.lib.ui import control
from resources.lib.ui.router import router_process


if control.ADDON_VERSION != control.getSetting('version'):
    if control.getInt('showchangelog') == 0:
        import service
        service.getChangeLog()
    control.setSetting('version', control.ADDON_VERSION)

if __name__ == "__main__":
    from resources.lib import Main  # noQA
    plugin_url = control.get_plugin_url(sys.argv[0])
    plugin_params = control.get_plugin_params(sys.argv[2])
    router_process(plugin_url, plugin_params)
    control.log(f'Finished Running: {plugin_url=} {plugin_params=}')
