# coding=utf-8
# Author: Nic Wolfe <nic@wolfeden.ca>
# URL: http://code.google.com/p/sickbeard/
#
# This file is part of SickRage.
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

import time
import datetime
import itertools
import traceback
import sickbeard
from sickbeard import db
from sickbeard import logger
from sickbeard.rssfeeds import getFeed
from sickbeard import show_name_helpers
from sickrage.helper.exceptions import AuthException, ex
from sickrage.show.Show import Show
from sickbeard.name_parser.parser import NameParser, InvalidNameException, InvalidShowException


class CacheDBConnection(db.DBConnection):
    def __init__(self, providerName):
        db.DBConnection.__init__(self, 'cache.db')

        # Create the table if it's not already there
        try:
            if not self.hasTable(providerName):
                logger.log(u"Creating cache table for provider {}".format(providerName), logger.DEBUG)
                self.action(
                    "CREATE TABLE [" + providerName + "] (name TEXT, season NUMERIC, episodes TEXT, indexerid NUMERIC, url TEXT, time NUMERIC, quality NUMERIC, release_group TEXT)")
            else:
                sql_results = self.select("SELECT url, COUNT(url) AS count FROM [" + providerName + "] GROUP BY url HAVING count > 1")

                for cur_dupe in sql_results:
                    self.action("DELETE FROM [" + providerName + "] WHERE url = ?", [cur_dupe["url"]])

            # remove wrong old index
            self.action("DROP INDEX IF EXISTS idx_url")

            # add unique index to prevent further dupes from happening if one does not exist
            logger.log(u"Creating UNIQUE URL index for {}".format(providerName), logger.DEBUG)
            self.action("CREATE UNIQUE INDEX IF NOT EXISTS idx_url_" + providerName + " ON [" + providerName + "] (url)")

            # add release_group column to table if missing
            if not self.hasColumn(providerName, 'release_group'):
                self.addColumn(providerName, 'release_group', "TEXT", "")

            # add version column to table if missing
            if not self.hasColumn(providerName, 'version'):
                self.addColumn(providerName, 'version', "NUMERIC", "-1")

            # add seeders column to table if missing
            if not self.hasColumn(providerName, 'seeders'):
                self.addColumn(providerName, 'seeders', "NUMERIC", "-1")

            # add leechers column to table if missing
            if not self.hasColumn(providerName, 'leechers'):
                self.addColumn(providerName, 'leechers', "NUMERIC", "-1")

            # add size column to table if missing
            if not self.hasColumn(providerName, 'size'):
                self.addColumn(providerName, 'size', "NUMERIC", "-1")

            # add pubdate column to table if missing
            if not self.hasColumn(providerName, 'pubdate'):
                self.addColumn(providerName, 'pubdate', "NUMERIC", "")

            # add hash column to table if missing
            if not self.hasColumn(providerName, 'hash'):
                self.addColumn(providerName, 'hash', "NUMERIC", "")

        except Exception as e:
            if str(e) != "table [" + providerName + "] already exists":
                raise

        # Create the table if it's not already there
        try:
            if not self.hasTable('lastUpdate'):
                self.action("CREATE TABLE lastUpdate (provider TEXT, time NUMERIC)")
        except Exception as e:
            logger.log(u"Error while searching " + self.provider.name + ", skipping: " + repr(e), logger.DEBUG)
            logger.log(traceback.format_exc(), logger.DEBUG)
            if str(e) != "table lastUpdate already exists":
                raise


class TVCache(object):
    def __init__(self, provider, **kwargs):
        self.provider = provider
        self.providerID = self.provider.get_id()
        self.providerDB = None
        self.minTime = kwargs.pop(u'min_time', 10)
        self.search_params = kwargs.pop(u'search_params', dict(RSS=['']))

    def _getDB(self):
        # init provider database if not done already
        if not self.providerDB:
            self.providerDB = CacheDBConnection(self.providerID)

        return self.providerDB

    def _clearCache(self):
        """
        Performs requalar cache cleaning as required
        """
        # if cache trimming is enabled
        if sickbeard.CACHE_TRIMMING:
            # trim items older than MAX_CACHE_AGE days
            self.trim_cache(days=sickbeard.MAX_CACHE_AGE)

    def trim_cache(self, days=None):
        """
        Remove old items from cache

        :param days: Number of days to retain
        """
        if days:
            now = int(time.time())  # current timestamp
            retention_period = now - (days * 86400)
            logger.log(u'Removing cache entries older than {x} days from {provider}'.format
                       (x=days, provider=self.providerID))
            cache_db_con = self._getDB()
            cache_db_con.action(
                b'DELETE FROM [{provider}] '
                b'WHERE time < ? '.format(provider=self.providerID),
                [retention_period]
            )

    def _get_title_and_url(self, item):
        return self.provider._get_title_and_url(item)  # pylint:disable=protected-access

    def _get_result_info(self, item):
        return self.provider._get_result_info(item)

    def _get_size(self, item):
        return self.provider._get_size(item)

    def _get_pubdate(self, item):
        """
        Return publish date of the item. If provider doesnt
        have _get_pubdate function this will be used
        """
        return self.provider._get_pubdate(item)

    def _get_hash(self, item):
        """
        Return hash of the item. If provider doesnt
        have _get_hash function this will be used
        """
        return self.provider._get_hash(item)

    def _getRSSData(self):
        return {u'entries': self.provider.search(self.search_params)} if self.search_params else None

    def _checkAuth(self, data):  # pylint:disable=unused-argument, no-self-use
        return True

    def _checkItemAuth(self, title, url):  # pylint:disable=unused-argument, no-self-use
        return True

    def updateCache(self):
        # check if we should update
        if not self.shouldUpdate():
            return

        try:
            data = self._getRSSData()
            if self._checkAuth(data):
                # clear cache
                self._clearCache()

                # set updated
                self.setLastUpdate()

                cl = []
                for item in data['entries'] or []:
                    ci = self._parseItem(item)
                    if ci is not None:
                        cl.append(ci)

                cache_db_con = self._getDB()
                if cl:
                    cache_db_con.mass_action(cl)

        except AuthException as e:
            logger.log(u"Authentication error: " + ex(e), logger.ERROR)
        except Exception as e:
            logger.log(u"Error while searching " + self.provider.name + ", skipping: " + repr(e), logger.DEBUG)

    def update_cache_manual_search(self, manual_data=None):

        try:
            cl = []
            for item in manual_data:
                logger.log(u"Adding to cache item found in manual search: {}".format(item.name), logger.DEBUG)
                ci = self._addCacheEntry(item.name, item.url, item.seeders, item.leechers, item.size, item.pubdate, item.hash)
                if ci is not None:
                    cl.append(ci)
        except Exception as e:
            logger.log(u"Error while adding to cache item found in manual seach for provider " + self.provider.name + ", skipping: " + repr(e), logger.WARNING)

        results = []
        cache_db_con = self._getDB()
        if cl:
            logger.log("Mass updating cache table with manual results for provider: {}".format(self.provider.name), logger.DEBUG)
            results = cache_db_con.mass_action(cl)

        return any(results)

    def getRSSFeed(self, url, params=None):
        if self.provider.login():
            return getFeed(url, params=params, request_hook=self.provider.get_url)
        return {'entries': []}

    @staticmethod
    def _translateTitle(title):
        return u'' + title.replace(' ', '.')

    @staticmethod
    def _translateLinkURL(url):
        return url.replace('&amp;', '&')

    def _parseItem(self, item):
        title, url = self._get_title_and_url(item)
        seeders, leechers = self._get_result_info(item)
        size = self._get_size(item)
        pubdate = self._get_pubdate(item)
        hash = self._get_hash(item)

        self._checkItemAuth(title, url)

        if title and url:
            title = self._translateTitle(title)
            url = self._translateLinkURL(url)

            # logger.log(u"Attempting to add item to cache: " + title, logger.DEBUG)
            return self._addCacheEntry(title, url, seeders, leechers, size, pubdate, hash)

        else:
            logger.log(
                u"The data returned from the " + self.provider.name + " feed is incomplete, this result is unusable",
                logger.DEBUG)

        return False

    def _getLastUpdate(self):
        cache_db_con = self._getDB()
        sql_results = cache_db_con.select("SELECT time FROM lastUpdate WHERE provider = ?", [self.providerID])

        if sql_results:
            lastTime = int(sql_results[0]["time"])
            if lastTime > int(time.mktime(datetime.datetime.today().timetuple())):
                lastTime = 0
        else:
            lastTime = 0

        return datetime.datetime.fromtimestamp(lastTime)

    def _getLastSearch(self):
        cache_db_con = self._getDB()
        sql_results = cache_db_con.select("SELECT time FROM lastSearch WHERE provider = ?", [self.providerID])

        if sql_results:
            lastTime = int(sql_results[0]["time"])
            if lastTime > int(time.mktime(datetime.datetime.today().timetuple())):
                lastTime = 0
        else:
            lastTime = 0

        return datetime.datetime.fromtimestamp(lastTime)

    def setLastUpdate(self, toDate=None):
        if not toDate:
            toDate = datetime.datetime.today()

        cache_db_con = self._getDB()
        cache_db_con.upsert(
            "lastUpdate",
            {'time': int(time.mktime(toDate.timetuple()))},
            {'provider': self.providerID}
        )

    def setLastSearch(self, toDate=None):
        if not toDate:
            toDate = datetime.datetime.today()

        cache_db_con = self._getDB()
        cache_db_con.upsert(
            "lastSearch",
            {'time': int(time.mktime(toDate.timetuple()))},
            {'provider': self.providerID}
        )

    lastUpdate = property(_getLastUpdate)
    lastSearch = property(_getLastSearch)

    def shouldUpdate(self):
        # if we've updated recently then skip the update
        if datetime.datetime.today() - self.lastUpdate < datetime.timedelta(minutes=self.minTime):
            logger.log(u"Last update was too soon, using old cache: " + str(self.lastUpdate) + ". Updated less then " + str(self.minTime) + " minutes ago", logger.DEBUG)
            return False

        return True

    def shouldClearCache(self):
        # # if daily search hasn't used our previous results yet then don't clear the cache
        # if self.lastUpdate > self.lastSearch:
        #     return False

        return False

    def _addCacheEntry(self, name, url, seeders, leechers, size, pubdate, hash):

        try:
            parse_result = NameParser().parse(name)
        except (InvalidNameException, InvalidShowException) as error:
            logger.log(u"{}".format(error), logger.DEBUG)
            return None

        if not parse_result or not parse_result.series_name:
            return None

        # if we made it this far then lets add the parsed result to cache for usager later on
        season = parse_result.season_number if parse_result.season_number is not None else 1
        episodes = parse_result.episode_numbers

        if season is not None and episodes is not None:
            # store episodes as a seperated string
            episodeText = "|" + "|".join({str(episode) for episode in episodes if episode}) + "|"

            # get the current timestamp
            curTimestamp = int(time.mktime(datetime.datetime.today().timetuple()))

            # get quality of release
            quality = parse_result.quality

            assert isinstance(name, unicode)

            # get release group
            release_group = parse_result.release_group

            # get version
            version = parse_result.version

            logger.log(u"Added RSS item: [" + name + "] to cache: [" + self.providerID + "]", logger.DEBUG)

            return [
                "INSERT OR REPLACE INTO [" + self.providerID + "] (name, season, episodes, indexerid, url, time, quality, release_group, version, seeders, leechers, size, pubdate, hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [name, season, episodeText, parse_result.show.indexerid, url, curTimestamp, quality, release_group, version, seeders, leechers, size, pubdate, hash]]

    def searchCache(self, episode, forced_search=False, downCurQuality=False):
        neededEps = self.findNeededEpisodes(episode, forced_search, downCurQuality)
        return neededEps[episode] if episode in neededEps else []

    def listPropers(self, date=None):
        cache_db_con = self._getDB()
        sql = "SELECT * FROM [" + self.providerID + "] WHERE name LIKE '%.PROPER.%' OR name LIKE '%.REPACK.%'"

        if date is not None:
            sql += " AND time >= " + str(int(time.mktime(date.timetuple())))

        propers_results = cache_db_con.select(sql)
        return [x for x in propers_results if x['indexerid']]

    def findNeededEpisodes(self, episode, forced_search=False, downCurQuality=False):  # pylint:disable=too-many-locals, too-many-branches
        neededEps = {}
        cl = []

        cache_db_con = self._getDB()
        if not episode:
            sql_results = cache_db_con.select("SELECT * FROM [" + self.providerID + "]")
        elif not isinstance(episode, list):
            sql_results = cache_db_con.select(
                "SELECT * FROM [" + self.providerID + "] WHERE indexerid = ? AND season = ? AND episodes LIKE ?",
                [episode.show.indexerid, episode.season, "%|" + str(episode.episode) + "|%"])
        else:
            for epObj in episode:
                cl.append([
                    "SELECT * FROM [" + self.providerID + "] WHERE indexerid = ? AND season = ? AND episodes LIKE ? AND quality IN (" + ",".join(
                        [str(x) for x in epObj.wantedQuality]) + ")",
                    [epObj.show.indexerid, epObj.season, "%|" + str(epObj.episode) + "|%"]])

            sql_results = cache_db_con.mass_action(cl, fetchall=True)
            sql_results = list(itertools.chain(*sql_results))

        # for each cache entry
        for curResult in sql_results:
            # ignored/required words, and non-tv junk
            if not show_name_helpers.filterBadReleases(curResult["name"]):
                continue

            # get the show object, or if it's not one of our shows then ignore it
            showObj = Show.find(sickbeard.showList, int(curResult["indexerid"]))
            if not showObj:
                continue

            # skip if provider is anime only and show is not anime
            if self.provider.anime_only and not showObj.is_anime:
                logger.log(u"" + str(showObj.name) + " is not an anime, skiping", logger.DEBUG)
                continue

            # get season and ep data (ignoring multi-eps for now)
            curSeason = int(curResult["season"])
            if curSeason == -1:
                continue

            curEp = curResult["episodes"].split("|")[1]
            if not curEp:
                continue

            curEp = int(curEp)

            curQuality = int(curResult["quality"])
            curReleaseGroup = curResult["release_group"]
            curVersion = curResult["version"]

            # if the show says we want that episode then add it to the list
            if not showObj.wantEpisode(curSeason, curEp, curQuality, forced_search, downCurQuality):
                logger.log(u"Ignoring " + curResult["name"], logger.DEBUG)
                continue

            epObj = showObj.getEpisode(curSeason, curEp)

            # build a result object
            title = curResult["name"]
            url = curResult["url"]

            logger.log(u"Found result " + title + " at " + url)

            result = self.provider.get_result([epObj])
            result.show = showObj
            result.url = url
            result.seeders = curResult["seeders"]
            result.leechers = curResult["leechers"]
            result.size = curResult["size"]
            result.pubdate = curResult["pubdate"]
            result.hash = curResult["hash"]
            result.name = title
            result.quality = curQuality
            result.release_group = curReleaseGroup
            result.version = curVersion
            result.content = None

            # add it to the list
            if epObj not in neededEps:
                neededEps[epObj] = [result]
            else:
                neededEps[epObj].append(result)

        # datetime stamp this search so cache gets cleared
        self.setLastSearch()

        return neededEps
