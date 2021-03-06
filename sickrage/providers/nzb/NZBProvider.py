# coding=utf-8
# This file is part of SickRage.
#

# Git: https://github.com/PyMedusa/SickRage.git
#
# SickRage is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SickRage is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with SickRage. If not, see <http://www.gnu.org/licenses/>.

import sickbeard

from sickbeard import logger
from sickbeard.classes import NZBSearchResult
from sickrage.helper.common import try_int

from sickrage.providers.GenericProvider import GenericProvider


class NZBProvider(GenericProvider):
    def __init__(self, name):
        GenericProvider.__init__(self, name)

        self.provider_type = GenericProvider.NZB

    def is_active(self):
        return bool(sickbeard.USE_NZBS) and self.is_enabled()

    def _get_result(self, episodes):
        return NZBSearchResult(episodes)

    def _get_size(self, item):
        try:
            size = item.get('links')[1].get('length', -1)
        except (AttributeError, IndexError, TypeError):
            size = -1
        return try_int(size, -1)

    def _get_result_info(self, item):
        # Get seeders/leechers for Torznab
        seeders = item.get('seeders', -1)
        leechers = item.get('leechers', -1)
        return try_int(seeders, -1), try_int(leechers, -1)

    def _get_storage_dir(self):
        return sickbeard.NZB_DIR

    def _get_pubdate(self, item):
        """
        Return publish date of the item.
        """
        return item.get('pubdate')
