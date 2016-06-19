#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Rules: This section contains rules that enhances guessit behaviour

Coding guidelines:
For each rule:
  - Provide an explanation
  - An example of the guessit output without it
  - An example of the guessit output with it
  - Each rule should handle only one issue
  - Remember that the input might be a filepath: /Show Name/Season 1/Show Name S01E02.ext
  - Use rule.priority = POST_PROCESSOR (DO NOT change this*)
  - DO NOT use rule.dependency**
  - DO NOT change match.value. Just remove the match and append a new one with the amended value***
  - Try to avoid using `private`, `parent` and `children` matches.
    Their behaviour might change a lot in each new version

Rebulk API is really powerful. It's always good to spend some time reading about it: https://github.com/Toilal/rebulk

The main idea about the rules in this section is to navigate between the `matches` and `holes` and change the matches
according to our needs

* Our rules should run only after all standard and default guessit rules have finished (not before that!).
** Adding several dependencies to our rules will make an implicit execution order. It could be hard to debug. Better to
have a fixed execution order, that's why the rules() method should add the rules in the correct order (explicit).
*** Rebulk API relies on the match.value, if you change them you'll get exceptions
"""
import copy
import re

from guessit.rules.common.comparators import marker_sorted
from guessit.rules.common.formatters import cleanup
from rebulk.processors import POST_PROCESS
from rebulk.rebulk import Rebulk
from rebulk.rules import Rule, AppendMatch, RemoveMatch, RenameMatch


season_range_separator = ('-', '~', '_-_', '_-_s', '-s', '.to.s', '.to.', 'to')


class FixAnimeReleaseGroup(Rule):
    """
    Anime release group is at the beginning and inside square brackets. If this pattern is found at the start of the
    filepart, use it as a release group

    guessit -t episode "[RealGroup].Show.Name.-.462.[720p].[10bit].[SOMEPERSON].[Something]"

    without this fix:
        For: [RealGroup].Show.Name.-.462.[720p].[10bit].[SOMEPERSON].[Something]
        GuessIt found: {
            "title": "Show Name",
            "season": 4,
            "episode": 62,
            "screen_size": "720p",
            "video_profile": "10bit",
            "release_group": "[SOMEPERSON].[Something]",
            "type": "episode"
        }

    with this fix:
        For: [RealGroup].Show.Name.-.462.[720p].[10bit].[SOMEPERSON].[Something]
        GuessIt found: {
            "title": "Show Name",
            "season": 4,
            "episode": 62,
            "screen_size": "720p",
            "video_profile": "10bit",
            "release_group": "RealGroup",
            "type": "episode"
        }
    """
    priority = POST_PROCESS
    consequence = [RemoveMatch, AppendMatch]
    release_group_re = re.compile(r'^\[(?P<release_group>\w+)\]$', flags=re.IGNORECASE)
    blacklist = ('private', 'req')

    def when(self, matches, context):
        """
        :param matches:
        :type matches: rebulk.match.Matches
        :param context:
        :type context: dict
        :return:
        """
        if context.get('show_type') == 'regular':
            return

        fileparts = matches.markers.named('path')
        for filepart in marker_sorted(fileparts, matches):
            # get the group (e.g.: [abc]) at the beginning of this filepart
            group = matches.markers.at_match(filepart, index=0, predicate=lambda marker: marker.name == 'group')

            # if there's no group or there's already a match at this position, skip it...
            if not group or matches.at_match(group):
                continue

            m = self.release_group_re.match(group.raw)
            # if the group matches the anime's release group pattern and it's not blacklisted
            if m and m.group('release_group').lower() not in self.blacklist:
                new_release_group = copy.copy(group)
                new_release_group.marker = None
                new_release_group.name = 'release_group'
                new_release_group.value = m.group('release_group')
                new_release_group.tags = ['anime']

                to_append = new_release_group
                to_remove = matches.named('release_group')

                # remove the old release_group, append the new one
                return to_remove, to_append


class SpanishNewpctReleaseName(Rule):
    """
    This rule is to handle the newpct release name style

    e.g.: Show.Name.-.Temporada.1.720p.HDTV.x264[Cap.102]SPANISH.AUDIO-NEWPCT

    guessit -t episode "Show.Name.-.Temporada.1.720p.HDTV.x264[Cap.102]SPANISH.AUDIO-NEWPCT"

    without this rule:
        For: Show.Name.-.Temporada.1.720p.HDTV.x264[Cap.102]SPANISH.AUDIO-NEWPCT
        GuessIt found: {
            "title": "Show Name",
            "alternative_title": "Temporada",
            "episode": [
                1,
                2
            ],
            "screen_size": "720p",
            "format": "HDTV",
            "video_codec": "h264",
            "season": 1,
            "language": "Spanish",
            "episode_title": "AUDIO-NEWPCT",
            "type": "episode"
        }


    with this rule:
        For: Show.Name.-.Temporada.1.720p.HDTV.x264[Cap.102]SPANISH.AUDIO-NEWPCT
        GuessIt found: {
            "title": "Show Name",
            "season": 1,
            "episode": 2
            "screen_size": "720p",
            "format": "HDTV",
            "video_codec": "h264",
            "language": "Spanish",
            "release_group": "NEWPCT"
            "type": "episode"
        }

    """
    priority = POST_PROCESS
    consequence = [RemoveMatch, AppendMatch]
    season_re = re.compile(r'^tem(p|porada)?\W*\d*$', flags=re.IGNORECASE)
    prefix = '[cap.'
    episode_re = re.compile(r'^\[cap\.(?P<season>\d{1,2})(?P<episode>\d{2})'
                            r'(_((?P<end_season>\d{1,2})(?P<end_episode>\d{2})))?.*\]', flags=re.IGNORECASE)

    def when(self, matches, context):
        """
        :param matches:
        :type matches: rebulk.match.Matches
        :param context:
        :type context: dict
        :return:
        """
        season = matches.named('season', index=0)
        if not season:
            return

        alternative_titles = matches.named('alternative_title', predicate=
                                           lambda match: self.season_re.match(match.value.lower()))
        episode_titles = matches.named('episode_title', predicate=
                                       lambda match: self.season_re.match(match.value.lower()))

        # skip if there isn't an alternative_title or episode_title with the word season in spanish
        if not alternative_titles and not episode_titles:
            return

        fileparts = matches.markers.named('path')
        for filepart in marker_sorted(fileparts, matches):
            # retrieve all groups
            groups = matches.markers.range(filepart.start, filepart.end, predicate=lambda mk: mk.name == 'group')
            for group in groups:
                # then search the season and episode numbers: [Cap.102_103]
                m = self.episode_re.search(group.raw)
                g = m.groupdict() if m else None
                # if found and the season numbers match...
                if not g or int(g['season']) != season.value or (
                        g['end_season'] and int(g['end_season']) != season.value):
                    continue

                if not context.get('show_type'):
                    # fix the show_type as this is not anime
                    context['show_type'] = 'regular'

                to_remove = []
                to_append = []

                # remove the wrong alternative title
                to_remove.extend(alternative_titles)
                # remove the wrong episode title
                to_remove.extend(episode_titles)
                to_remove.extend(matches.named('episode_title', predicate=lambda match: match.value.lower() == 'audio'))
                # remove all episode matches, since we're rebuild them
                to_remove.extend(matches.named('episode'))

                first_ep_num = int(g['episode'])
                last_ep_num = int(g['end_episode']) if g['end_episode'] else first_ep_num
                if 0 <= first_ep_num <= last_ep_num < 100:
                    start_index = group.start + len(g['season']) + len(self.prefix)

                    # rebuild all episode matches
                    for ep_num in range(first_ep_num, last_ep_num + 1):
                        new_episode = copy.copy(season)
                        new_episode.name = 'episode'
                        new_episode.tags = ['newpct']
                        new_episode.value = ep_num
                        if ep_num == first_ep_num:
                            new_episode.start = start_index
                            new_episode.end = new_episode.start + len(g['episode'])
                        elif ep_num != last_ep_num:
                            new_episode.start = start_index + len(g['episode'])
                            new_episode.end = new_episode.start + 1
                        else:
                            new_episode.start = start_index + len(g['episode']) + len(g['end_season']) + 1
                            new_episode.end = new_episode.start + len(g['end_episode'])
                        to_append.append(new_episode)

                return to_remove, to_append


class FixScreenSizeConflict(Rule):
    """
    Certain release names contains a conflicting screen_size (e.g.: 720 without p). It confuses guessit: the guessed
    season and episode needs to be removed.
    Bug: https://github.com/guessit-io/guessit/issues/308

    e.g.: "[SuperGroup].Show.Name.-.06.[720.Hi10p][1F5578AC]"

    guessit -t episode "[SuperGroup].Show.Name.-.06.[720.Hi10p][1F5578AC]"

    without this fix:
        For: [SuperGroup].Show.Name.-.06.[720.Hi10p][1F5578AC]
        GuessIt found: {
            "release_group": "SuperGroup",
            "title": "Show Name",
            "episode": [
                6,
                20
            ],
            "season": 7,
            "screen_size": "720p",
            "video_profile": "10bit",
            "crc32": "1F5578AC",
            "type": "episode"
        }

    with this fix:
        For: [SuperGroup].Show.Name.-.06.[720.Hi10p][1F5578AC]
        GuessIt found: {
            "release_group": "SuperGroup",
            "title": "Show Name",
            "episode": 6,
            "screen_size": "720p",
            "video_profile": "10bit",
            "crc32": "1F5578AC",
            "type": "episode"
        }

    """
    priority = POST_PROCESS
    consequence = RemoveMatch

    def when(self, matches, context):
        """
        :param matches:
        :type matches: rebulk.match.Matches
        :param context:
        :type context: dict
        :return:
        """
        to_remove = []

        screen_sizes = matches.named('screen_size')
        for screen_size in screen_sizes:
            to_remove.extend(matches.at_match(screen_size, predicate=lambda match: match.name in ('season', 'episode')))

        return to_remove


class FixInvalidTitleOrAlternativeTitle(Rule):
    """
    Some release names have season/episode defined twice (relative and absolute), and one of them becomes an
    alternative_title or a suffix in the title. This fix will remove the invalid alternative_title or the
    invalid title's suffix

    e.g.: "Show Name - 313-314 - s16e03-04"

    guessit -t episode "Show Name - 313-314 - s16e03-04"

    without this fix:
        For: Show Name - 313-314 - s16e03-04
        GuessIt found: {
            "title": "Show Name",
            "alternative_title": "313-314",
            "season": 16,
            "episode": [
                3,
                4
            ],
            "type": "episode"
        }


    with this fix:
        For: Show Name - 313-314 - s16e03-04
        GuessIt found: {
            "title": "Show Name",
            "season": 16,
            "absolute_episode": [
                313,
                314
            ],
            "episode": [
                3,
                4
            ],
            "type": "episode"
        }
    """
    priority = POST_PROCESS
    consequence = [RemoveMatch, AppendMatch]
    absolute_re = re.compile(r'([\W|_]*)(?P<absolute_episode_start>\d{3,4})\-(?P<absolute_episode_end>\d{3,4})\W*$')
    properties = ('title', 'alternative_title', 'episode_title')

    def when(self, matches, context):
        """
        :param matches:
        :type matches: rebulk.match.Matches
        :param context:
        :type context: dict
        :return:
        """
        episodes = matches.named('episode')
        if not episodes:
            return

        fileparts = matches.markers.named('path')
        for filepart in marker_sorted(fileparts, matches):
            # retrieve all problematic titles
            problematic_titles = matches.range(filepart.start, filepart.end, predicate=
                                               lambda match: match.name in self.properties)

            to_remove = []
            to_append = []

            for title in problematic_titles:
                m = self.absolute_re.search(title.raw)
                if not m:
                    continue

                # Remove the problematic title
                to_remove.append(title)

                # Remove the title suffix
                new_value = title.raw[0: m.start()]
                if new_value:
                    # Add the correct title
                    new_title = copy.copy(title)
                    new_title.value = cleanup(new_value)
                    new_title.end = m.start()
                    to_append.append(new_title)

                # and add the absolute episode range
                g = m.groupdict()
                absolute_episode_start = int(g['absolute_episode_start'])
                absolute_episode_end = int(g['absolute_episode_end'])
                for i in range(absolute_episode_start, absolute_episode_end + 1):
                    episode = copy.copy(episodes[0])
                    episode.name = 'absolute_episode'
                    episode.value = i
                    if i == absolute_episode_start:
                        episode.start = title.start + m.start('absolute_episode_start')
                        episode.end = title.start + m.end('absolute_episode_start')
                    elif i < absolute_episode_end:
                        episode.start = title.start + m.end('absolute_episode_start')
                        episode.end = title.start + m.start('absolute_episode_end')
                    else:
                        episode.start = title.start + m.start('absolute_episode_end')
                        episode.end = title.start + m.end('absolute_episode_end')
                    to_append.append(episode)

                return to_remove, to_append


class FixWrongTitleDueToFilmTitle(Rule):
    """
    Work-around for https://github.com/guessit-io/guessit/issues/294
    TODO: Remove when this bug is fixed

    e.g.: "Show.Name.S03E16.1080p.WEB-DL.DD5.1.H.264-GOLF68"

    guessit -t episode "Show.Name.S03E16.1080p.WEB-DL.DD5.1.H.264-GOLF68"

    without this fix:
    For: Show.Name.S03E16.1080p.WEB-DL.DD5.1.H.264-GOLF68
        GuessIt found: {
            "film_title": "Show Name",
            "season": 3,
            "episode": 16,
            "screen_size": "1080p",
            "format": "WEB-DL",
            "audio_codec": "DolbyDigital",
            "audio_channels": "5.1",
            "video_codec": "h264",
            "title": "GOL",
            "film": 68,
            "type": "episode"
        }

    with this fix:
        GuessIt found: {
            "title": "Show Name",
            "season": 3,
            "episode": 16,
            "screen_size": "1080p",
            "format": "WEB-DL",
            "audio_codec": "DolbyDigital",
            "audio_channels": "5.1",
            "video_codec": "h264",
            "release_group": "GOLF68",
            "type": "episode"
        }
    """
    priority = POST_PROCESS
    consequence = [RemoveMatch, AppendMatch, RenameMatch('title'), RenameMatch('episode')]
    blacklist = ('special', 'season', 'multi')

    def when(self, matches, context):
        """
        :param matches:
        :type matches: rebulk.match.Matches
        :param context:
        :type context: dict
        :return:
        """
        to_remove = []
        to_append = []
        to_rename = []
        to_rename_ep = []

        fileparts = matches.markers.named('path')
        for filepart in marker_sorted(fileparts, matches):
            film_title = matches.range(filepart.start, filepart.end, index=0, predicate=
                                       lambda match: match.name == 'film_title' and not match.raw.isdigit())
            if film_title:
                title = matches.range(filepart.start, filepart.end,
                                      predicate=lambda match: match.name == 'title', index=0)

                if title:
                    if title.value.lower() in self.blacklist:
                        to_remove.append(title)
                    if title.value.isdigit() and matches.previous(title, predicate=lambda m: m.name == 'episode'):
                        title.value = int(title.value)
                        to_rename_ep.append(title)

                to_rename.append(film_title)

            film = matches.range(filepart.start, filepart.end, predicate=lambda match: match.name == 'film', index=-1)
            if not film or not film.raw.isdigit():
                continue

            previous = matches.previous(film, predicate=lambda match: match.start >= filepart.start, index=0)
            if not previous:
                continue

            to_remove.append(film)
            hole = matches.holes(previous.end, film.start, index=0)
            if not hole or hole.value.lower() != 'f':
                continue

            new_property = copy.copy(previous)
            new_property.value = cleanup(previous.raw + hole.value + film.raw)
            new_property.end = film.end
            if previous.name == 'title':
                new_property.name = 'release_group'
                new_property.tags = []

            if previous.name != 'release_group':
                release_groups = matches.range(filepart.start, filepart.end,
                                               predicate=lambda match: match.name == 'release_group')
                to_remove.extend(release_groups)
            to_remove.append(previous)

            to_append.append(new_property)

        return to_remove, to_append, to_rename, to_rename_ep


class CreateExtendedTitleWithAlternativeTitles(Rule):
    """
    ExtendedTitle: 'extended_title' - post processor to add alternative titles the existing title.

    e.g.: [SuperGroup].Show.Name.-.Still+Name.-.11.[1080p]

    guessit -t episode "[SuperGroup].Show.Name.-.Still+Name.-.11.[1080p]"

    without this rule:
        For: [SuperGroup].Show.Name.-.Still+Name.-.11.[1080p]
        GuessIt found: {
            "release_group": "SuperGroup",
            "title": "Show Name",
            "alternative_title": [
                "Still",
                "Name"
            ],
            "episode": 11,
            "screen_size": "1080p",
            "type": "episode"
        }

    with this rule:
        For: [SuperGroup].Show.Name.-.Still+Name.-.11.[1080p]
        GuessIt found: {
            "release_group": "SuperGroup",
            "title": "Show Name",
            "alternative_title": [
                "Still",
                "Name"
            ],
            "extended_title": "Show Name - Still+Name"
            "episode": 11,
            "screen_size": "1080p",
            "type": "episode"
        }
    """
    priority = POST_PROCESS
    consequence = AppendMatch
    blacklist = ('temporada', 'temp', 'tem')

    def when(self, matches, context):
        """
        :param matches:
        :type matches: rebulk.match.Matches
        :param context:
        :type context: dict
        :return:
        """
        # Do not concatenate the titles if it's not an anime and there are languages
        if not matches.tagged('anime') and matches.named('language'):
            return

        fileparts = matches.markers.named('path')
        for filepart in marker_sorted(fileparts, matches):
            title = matches.range(filepart.start, filepart.end, predicate=lambda match: match.name == 'title', index=0)
            if not title:
                continue

            if matches.range(filepart.start, filepart.end, predicate=
                             lambda match: match.name == 'alternative_title' and match.value.lower() in self.blacklist):
                continue

            alternative_titles = matches.range(filepart.start, filepart.end, predicate=
                                               lambda match: match.name == 'alternative_title')
            if not alternative_titles:
                continue

            previous = title
            extended_title = copy.copy(title)
            extended_title.name = 'extended_title'
            extended_title.value = title.value

            # extended title is the concatenation between title and all alternative titles
            for alternative_title in alternative_titles:
                holes = matches.holes(start=previous.end, end=alternative_title.start)
                # if the separator is a dash, add an extra space before and after
                separators = [' ' + h.value + ' ' if h.value == '-' else h.value for h in holes]
                separator = ' '.join(separators) if separators else ' '
                extended_title.value += separator + alternative_title.value

                previous = alternative_title

            extended_title.end = previous.end
            return extended_title


class CreateExtendedTitleWithCountryOrYear(Rule):
    """
    ExtendedTitle: 'extended_title' - post processor to add country or year to the existing title.

    e.g.: Show.Name.US.S03.720p.BluRay.x264-SuperGroup

    guessit -t episode "Show.Name.US.S03.720p.BluRay.x264-SuperGroup"

    without this rule:
        For: Show.Name.US.S03.720p.BluRay.x264-SuperGroup
        GuessIt found: {
            "title": "Show Name",
            "country": "UNITED STATES",
            "season": 3,
            "screen_size": "720p",
            "format": "BluRay",
            "video_codec": "h264",
            "release_group": "SuperGroup",
            "type": "episode"
        }

    with this rule:
        For: Show.Name.US.S03.720p.BluRay.x264-SuperGroup
        GuessIt found: {
            "title": "Show Name",
            "extended_title": "Show Name US"
            "country": "UNITED STATES",
            "season": 3,
            "screen_size": "720p",
            "format": "BluRay",
            "video_codec": "h264",
            "release_group": "SuperGroup",
            "type": "episode"
        }
    """
    priority = POST_PROCESS
    consequence = AppendMatch
    affected_names = ('country', 'year')

    def when(self, matches, context):
        """
        :param matches:
        :type matches: rebulk.match.Matches
        :param context:
        :type context: dict
        :return:
        """
        fileparts = matches.markers.named('path')
        for filepart in marker_sorted(fileparts, matches):
            title = matches.range(filepart.start, filepart.end, predicate=lambda match: match.name == 'title', index=0)
            if not title:
                continue

            after_title = matches.next(title, index=0, predicate=
                                       lambda match: match.end <= filepart.end and match.name in self.affected_names)

            # only if there's a country or year
            if not after_title:
                continue

            # Only add country or year if the next match is season, episode or date
            next_match = matches.next(after_title, index=0, predicate=
                                      lambda match: match.name in ('season', 'episode', 'date'))
            if next_match:
                extended_title = copy.copy(title)
                extended_title.name = 'extended_title'
                extended_title.value = extended_title.value + ' ' + re.sub(r'\W*', '', str(after_title.raw))
                extended_title.end = after_title.end
                extended_title.raw_end = after_title.raw_end
                return extended_title


class FixWrongTitlesWithCompleteKeyword(Rule):
    """
    Guessit bug: https://github.com/guessit-io/guessit/issues/310

    e.g.: Show.Name.COMPLETE.SERIES.DVDRip.XviD-GROUP

    guessit -t episode "Show.Name.COMPLETE.SERIES.DVDRip.XviD-GROUP"

    without this fix:
        For: Show.Name.COMPLETE.SERIES.DVDRip.XviD-GROUP
        GuessIt found: {
            "title": "Show Name COMPLETE SERIES",
            "format": "DVD",
            "video_codec": "XviD",
            "release_group": "GROUP",
            "type": "episode"
        }

    with this fix:
        For: Show.Name.COMPLETE.SERIES.DVDRip.XviD-GROUP
        GuessIt found: {
            "title": "Show Name",
            "other": "Complete",
            "format": "DVD",
            "video_codec": "XviD",
            "release_group": "GROUP",
            "type": "episode"
        }
    """
    priority = POST_PROCESS
    consequence = [RemoveMatch, AppendMatch]
    complete_re = re.compile(r'\W+complete(\W+(series|season))?\W*$', flags=re.IGNORECASE)

    def when(self, matches, context):
        """
        :param matches:
        :type matches: rebulk.match.Matches
        :param context:
        :type context: dict
        :return:
        """
        to_remove = []
        to_append = []

        titles = []
        titles.extend(matches.named('title'))
        titles.extend(matches.named('alternative_title'))
        titles.extend(matches.named('episode_titles'))

        for title in titles:
            m = self.complete_re.search(title.raw)
            if not m:
                continue

            new_title = copy.copy(title)
            new_title.value = cleanup(title.raw[:m.start()])
            new_title.end = m.start()

            other = copy.copy(title)
            other.name = 'other'
            other.value = 'Complete'
            other.tags = []
            other.start = m.start()
            other.end = m.end()

            to_remove.append(title)
            to_append.append(new_title)
            to_append.append(other)

        return to_remove, to_append


class FixTvChaosUkWorkaround(Rule):
    """
    Medusa adds .hdtv.x264 to tv chaos uk releases. The video_codec might conflict with existing video_codec in the
    original release name.

    e.g.: Show.Name.Season.1.XviD.hdtv.x264

    guessit -t episode "Show.Name.Season.1.XviD.hdtv.x264"

    without this fix:
        For: Show.Name.Season.1.XviD.hdtv.x264
        GuessIt found: {
            "title": "Show Name",
            "season": 1,
            "video_codec": [
                "XviD",
                "h264"
            ],
            "format": "HDTV",
            "type": "episode"
        }

    with this fix:
        For: Show.Name.Season.1.XviD.hdtv.x264
        GuessIt found: {
            "title": "Show Name",
            "season": 1,
            "video_codec": "XviD",
            "format": "HDTV",
            "type": "episode"
        }
    """
    priority = POST_PROCESS
    consequence = RemoveMatch

    def when(self, matches, context):
        """
        :param matches:
        :type matches: rebulk.match.Matches
        :param context:
        :type context: dict
        :return:
        """
        to_remove = []

        fileparts = matches.markers.named('path')
        for filepart in marker_sorted(fileparts, matches):
            video_codecs = matches.range(filepart.start, filepart.end, predicate=
                                         lambda match: match.name == 'video_codec')
            formats = matches.range(filepart.start, filepart.end, predicate=lambda match: match.name == 'format')
            if len(video_codecs) != 2 or len(formats) != 1:
                continue

            m_x264 = video_codecs[-1]
            m_hdtv = matches.previous(m_x264, index=0)

            if m_x264.end != filepart.end or m_x264.value != 'h264' or m_hdtv.name != 'format' \
                    or m_hdtv.value != 'HDTV':
                continue

            to_remove.append(m_x264)

        return to_remove


class FixTitlesContainsNumber(Rule):
    """
    There are shows where the title contains a number and the part after the number is incorrectly detected as
    episode title.

    e.g.: [Group].Show.Name.2.The.Big.Show.-.11.[1080p]

    guessit -t episode "[Group].Show.Name.2.The.Big.Show.-.11.[1080p]"

    without this fix:
        For: [Group].Show.Name.2.The.Big.Show.-.11.[1080p]
        GuessIt found: {
            "release_group": "Group",
            "title": "Show Name",
            "episode_title": "The Big Show",
            "episode": 11,
            "screen_size": "1080p",
            "type": "episode"
        }


    with this fix:
        For: [Group].Show.Name.2.The.Big.Show.-.11.[1080p]
        GuessIt found: {
            "release_group": "Group",
            "title": "Show Name 2 The Big Show",
            "episode": 11,
            "screen_size": "1080p",
            "type": "episode"
        }
    """
    priority = POST_PROCESS
    consequence = [RemoveMatch, AppendMatch]

    def when(self, matches, context):
        """
        :param matches:
        :type matches: rebulk.match.Matches
        :param context:
        :type context: dict
        :return:
        """
        fileparts = matches.markers.named('path')
        for filepart in marker_sorted(fileparts, matches):
            title = matches.range(filepart.start, filepart.end, predicate=lambda match: match.name == 'title', index=0)
            if not title:
                continue

            # and after the title there's an episode_title match...
            episode_title = matches.next(title, index=0, predicate=
                                         lambda match: match.name == 'episode_title' and match.end <= filepart.end)

            if not episode_title:
                continue

            holes = matches.holes(start=title.end, end=episode_title.start)
            number = holes[0] if len(holes) == 1 else None
            # and between the title and episode_title, there's one hole...
            if number and number.raw.isdigit():
                # join all three matches into one new title
                new_title = copy.copy(title)
                new_title.value = ' '.join([new_title.value, number.value, episode_title.value])
                new_title.end = episode_title.end

                # remove the old title and episode title; and append the new title
                return [title, episode_title], [new_title]


class AnimeWithSeasonAbsoluteEpisodeNumbers(Rule):
    """
    There are animes where the title contains the season number.

    Medusa rule:
    - The season should be part of the series name
    - The episode should still use absolute numbering

    e.g.: [Group].Show.Name.S2.-.19.[1080p]

    guessit -t episode "[Group].Show.Name.S2.-.19.[1080p]"

    without this rule:
        For: [Group].Show.Name.S2.-.19.[1080p]
        GuessIt found: {
            "release_group": "Group",
            "title": "Show Name",
            "season": 2,
            "episode_title": "19",
            "screen_size": "1080p",
            "type": "episode"
        }

    with this rule:
        For: [Group].Show.Name.S2.-.19.[1080p]
        GuessIt found: {
            "release_group": "Group",
            "title": "Show Name S2",
            "absolute_episode": "19",
            "screen_size": "1080p",
            "type": "episode"
        }
    """
    priority = POST_PROCESS
    consequence = [RemoveMatch, AppendMatch]

    def when(self, matches, context):
        """
        :param matches:
        :type matches: rebulk.match.Matches
        :param context:
        :type context: dict
        :return:
        """
        if context.get('show_type') == 'regular' or not matches.tagged('anime'):
            return

        fileparts = matches.markers.named('path')
        for filepart in marker_sorted(fileparts, matches):
            seasons = matches.range(filepart.start, filepart.end, predicate=lambda match: match.name == 'season')
            for season in seasons:
                if not season.parent or not season.parent.private:
                    continue

                title = matches.previous(season, index=-1, predicate=
                                         lambda match: match.name == 'title' and match.end <= filepart.end)
                episode_title = matches.next(season, index=0, predicate=
                                             lambda match: (match.name == 'episode_title' and
                                                            match.end <= filepart.end and
                                                            match.value.isdigit()))

                # the previous match before the season is the series name and
                # the match after season is episode title and episode title is a number
                if not title or not episode_title:
                    continue

                to_remove = []
                to_append = []

                # adjust title to append the series name.
                # Only the season.parent contains the S prefix in its value
                new_title = copy.copy(title)
                new_title.value = ' '.join([title.value, season.parent.value])
                new_title.end = season.end

                # other fileparts might have the same season to be removed from the matches
                # e.g.: /Show.Name.S2/[Group].Show.Name.S2.-.19.[1080p]
                to_remove.extend(matches.named('season', predicate=lambda match: match.value == season.value))
                to_remove.append(title)
                to_append.append(new_title)

                # move episode_title to absolute_episode
                absolute_episode = copy.copy(episode_title)
                absolute_episode.name = 'absolute_episode'
                absolute_episode.value = int(episode_title.value)
                to_remove.append(episode_title)
                to_append.append(absolute_episode)
                return to_remove, to_append


class AnimeAbsoluteEpisodeNumbers(Rule):
    """
    Medusa rule: If it's an anime, prefer absolute episode numbers

    e.g.: [Group].Show.Name.-.102.[720p]

    guessit -t episode "[Group].Show.Name.-.102.[720p]"

    without this rule:
        For: [Group].Show.Name.-.102.[720p]
        GuessIt found: {
            "release_group": "Group",
            "title": "Show Name",
            "season": 1,
            "episode": 2,
            "screen_size": "720p",
            "type": "episode"
        }

    with this rule:
        For: [Group].Show.Name.-.102.[720p]
        GuessIt found: {
            "release_group": "Group",
            "title": "Show Name",
            "absolute_episode": 102,
            "screen_size": "720p",
            "type": "episode"
        }
    """
    priority = POST_PROCESS
    consequence = [RemoveMatch, AppendMatch]

    def when(self, matches, context):
        """
        :param matches:
        :type matches: rebulk.match.Matches
        :param context:
        :type context: dict
        :return:
        """
        # only for shows that seems to be animes
        if context.get('show_type') == 'regular' or not matches.tagged('anime') or not matches.tagged('weak-duplicate'):
            return

        fileparts = matches.markers.named('path')
        for filepart in marker_sorted(fileparts, matches):
            season = matches.range(filepart.start, filepart.end, index=0, predicate=
                                   lambda match: match.name == 'season' and match.raw.isdigit())
            episode = matches.next(season, index=0, predicate=
                                   lambda match: (match.name == 'episode' and
                                                  match.end <= filepart.end and
                                                  match.raw.isdigit()))

            # there should be season and episode and the episode should start right after the season and both raw values
            # should be digit
            if season and episode and season.end == episode.start:
                # then make them an absolute episode:
                absolute_episode = copy.copy(episode)
                absolute_episode.name = 'absolute_episode'
                # raw value contains the season and episode altogether
                absolute_episode.value = int(episode.parent.raw if episode.parent else episode.raw)
                to_remove = [season, episode]
                to_append = [absolute_episode]
                return to_remove, to_append


class AbsoluteEpisodeNumbers(Rule):
    """
    Medusa absolute episode numbers rule. For animes without season, prefer absolute numbers.

    e.g.: Show.Name.10.720p

    guessit -t episode "Show.Name.10.720p"

    without this rule:
        For: Show.Name.10.720p
        GuessIt found: {
            "title": "Show Name",
            "episode": 10,
            "screen_size": "720p",
            "type": "episode"
        }

    with this rule:
        For: Show.Name.10.720p
        GuessIt found: {
            "title": "Show Name",
            "absolute_episode": 10,
            "screen_size": "720p",
            "type": "episode"
        }

    """
    priority = POST_PROCESS
    consequence = [RemoveMatch, RenameMatch('absolute_episode')]
    non_words_re = re.compile(r'\W')
    episode_words = ('e', 'episode', 'ep')

    def when(self, matches, context):
        """
        :param matches:
        :type matches: rebulk.match.Matches
        :param context:
        :type context: dict
        :return:
        """
        # if it seems to be anime and it doesn't have season
        if context.get('show_type') != 'regular' and not matches.named('season'):
            episodes = matches.named('episode')
            to_remove = []
            to_rename = []
            for episode in episodes:
                # And there's no episode count
                if matches.named('episode_count'):
                    # Some.Show.1of8..Title.x264.AAC.Group
                    # not absolute episode
                    return

                previous = matches.previous(episode, index=-1)
                if previous:
                    hole = matches.holes(start=previous.end, end=episode.start, index=0)
                    # and the hole is not an 'episode' word (e.g.: e, ep, episode)
                    if previous.name != 'episode':
                        if hole and self.non_words_re.sub('', hole.value).lower() in self.episode_words:
                            # Some.Show.E07.1080p.HDTV.x265-GROUP
                            # Some.Show.Episode.10.Some.Title.720p
                            # not absolute episode
                            return
                    elif hole and hole.value == '.':
                        # [GroupName].Show.Name.-.02.5.(Special).[BD.1080p]
                        # 5 is not absolute, and not an episode BTW
                        to_remove.append(episode)
                        continue

                to_rename.append(episode)

            return to_remove, to_rename


class PartsAsEpisodeNumbers(Rule):
    """
    Medusa rule: Parts are treated as episodes

    e.g.: Show.Name.Part.3.720p.HDTV.x264-Group

    guessit -t episode "Show.Name.Part.3.720p.HDTV.x264-Group"

    without the rule:
        For: Show.Name.Part.3.720p.HDTV.x264-Group
        GuessIt found: {
            "title": "Show Name",
            "part": 3,
            "screen_size": "720p",
            "format": "HDTV",
            "video_codec": "h264",
            "release_group": "Group",
            "type": "episode"
        }

    without the rule:
        For: Show.Name.Part.3.720p.HDTV.x264-Group
        GuessIt found: {
            "title": "Show Name",
            "episode": 3,
            "screen_size": "720p",
            "format": "HDTV",
            "video_codec": "h264",
            "release_group": "Group",
            "type": "episode"
        }
    """
    priority = POST_PROCESS
    consequence = RenameMatch('episode')

    def when(self, matches, context):
        """
        :param matches:
        :type matches: rebulk.match.Matches
        :param context:
        :type context: dict
        :return:
        """
        # only if there's no season and no episode
        if not matches.named('season') and not matches.named('episode'):
            return matches.named('part')


class FixSeasonEpisodeDetection(Rule):
    """
    Work-around for https://github.com/guessit-io/guessit/issues/295
    TODO: Remove when this bug is fixed

    e.g.: "Some.Show.S02E14.X264.1080p.HDTV"

    guessit -t episode "Some.Show.S02E14.X264.1080p.HDTV"

    without the fix:
        For: Some.Show.S02E14.X264.1080p.HDTV
        GuessIt found: {
            "title": "Some Show",
            "season": [
                2,
                14
            ],
            "video_codec": "h264",
            "screen_size": "1080p",
            "format": "HDTV",
            "type": "episode"
        }

    with the fix:
        For: Some.Show.S02E14.X264.1080p.HDTV
        GuessIt found: {
            "title": "Some Show",
            "season": 2,
            "episode": 14,
            "video_codec": "h264",
            "screen_size": "1080p",
            "format": "HDTV",
            "type": "episode"
        }

    """
    priority = POST_PROCESS
    consequence = RenameMatch('episode')
    codec_names = ('h264', 'h265')

    def when(self, matches, context):
        """
        :param matches:
        :type matches: rebulk.match.Matches
        :param context:
        :type context: dict
        :return:
        """
        to_rename = []

        fileparts = matches.markers.named('path')
        for filepart in marker_sorted(fileparts, matches):
            seasons = matches.range(filepart.start, filepart.end, predicate=lambda match: match.name == 'season')
            # bug happens when there are 2 seasons...
            if not seasons or len(seasons) != 2:
                continue

            # ... and no episodes
            if not matches.range(filepart.start, filepart.end, predicate=lambda match: match.name == 'episode'):
                second_season = seasons[-1]
                next_match = matches.range(second_season.end, filepart.end, index=0)
                # guessit gets confused when the next match is x264 or x265
                if next_match and next_match.name == 'video_codec' and next_match.value in self.codec_names:
                    # rename the second season to episode
                    episode = second_season
                    to_rename.append(episode)

        return to_rename


class FixSeasonNotDetected(Rule):
    """
    Work-around for https://github.com/guessit-io/guessit/issues/306
    TODO: Remove file_title when this bug is fixed

    e.g.: Show.Name.-.Season.3.-.720p.BluRay.-.x264.-.Group

    guessit -t episode "Show.Name.-.Season.3.-.720p.BluRay.-.x264.-.Group"

    without this fix:
        For: Show.Name.-.Season.3.-.720p.BluRay.-.x264.-.Group
        GuessIt found: {
            "title": "Show Name",
            "alternative_title": "Season",
            "episode": 3,
            "screen_size": "720p",
            "format": "BluRay",
            "video_codec": "h264",
            "release_group": "Group",
            "type": "episode"
        }

    with this fix:
        For: Show.Name.-.Season.3.-.720p.BluRay.-.x264.-.Group
        GuessIt found: {
            "title": "Show Name",
            "season": 3,
            "screen_size": "720p",
            "format": "BluRay",
            "video_codec": "h264",
            "release_group": "Group",
            "type": "episode"
        }
    """
    priority = POST_PROCESS
    season_re = re.compile(r'\bseason\W*$', flags=re.IGNORECASE)
    consequence = [RemoveMatch, AppendMatch, RenameMatch('season')]

    def when(self, matches, context):
        """
        :param matches:
        :type matches: rebulk.match.Matches
        :param context:
        :type context: dict
        :return:
        """
        fileparts = matches.markers.named('path')
        for filepart in marker_sorted(fileparts, matches):
            episodes = matches.range(filepart.start, filepart.end, predicate=lambda match: match.name == 'episode')
            for episode in episodes:
                previous = matches.previous(episode, index=0)
                m = self.season_re.search(previous.raw) if previous else None
                if not m or matches.holes(previous.end, episode.start, index=0):
                    continue

                to_remove = []
                to_append = []
                to_rename = []

                new_value = cleanup(previous.raw[:m.start()])
                # if there's a new value (e.g.: 'Show Name Season' became 'Show Name'), keep it
                if new_value:
                    new_match = copy.copy(previous)
                    new_match.value = new_value
                    new_match.end = m.start()
                    to_append.append(new_match)

                matches.next(episode, index=0, predicate=lambda match: match.name == 'episode')

                to_remove.append(previous)
                to_rename.append(episode)

                return to_remove, to_append, to_rename


class FixWrongSeasonRangeDetectionDueToEpisode(Rule):
    """
    e.g.: Show.Name.-.Season.1.to.3.-.Mp4.1080p
          Show.Name.-.Season.1-3.-.Mp4.1080p

    guessit -t episode "Show.Name.-.Season.1.to.3.-.Mp4.1080p"

    without this fix:
        For: Show.Name.-.Season.1.to.3.-.Mp4.1080p
        GuessIt found: {
            "title": "Show Name",
            "season": 1,
            "episode_title": "to",
            "episode": 3,
            "container": "MP4",
            "screen_size": "1080p",
            "type": "episode"
        }


    with this fix:
        For: Show.Name.-.Season.1.to.3.-.Mp4.1080p
        GuessIt found: {
            "title": "Show Name",
            "season": [1, 2, 3],
            "container": "MP4",
            "screen_size": "1080p",
            "type": "episode"
        }

    """
    priority = POST_PROCESS
    consequence = [RemoveMatch, AppendMatch, RenameMatch('season')]

    def when(self, matches, context):
        """
        :param matches:
        :type matches: rebulk.match.Matches
        :param context:
        :type context: dict
        :return:
        """
        to_remove = []
        to_append = []
        to_rename = []

        fileparts = matches.markers.named('path')
        for filepart in marker_sorted(fileparts, matches):
            seasons = matches.range(filepart.start, filepart.end, predicate=lambda match: match.name == 'season')
            if len(seasons) != 1:
                continue

            current_season = seasons[0]
            while current_season:
                next_match = matches.next(current_season, index=0, predicate= lambda match:
                                          (match.end <= filepart.end and match.name in ('episode', 'episode_title')))

                if not next_match:
                    break

                if next_match.name == 'episode_title':
                    separator = next_match
                    next_season = matches.next(next_match, index=0, predicate=
                                               lambda match: match.end <= filepart.end and match.name == 'episode')
                elif next_match.name == 'episode':
                    separator = matches.holes(current_season.end, next_match.start, index=0)
                    next_season = next_match

                if not next_season or not separator:
                    break

                if separator.value in ('.', 'and', ',.', '.,', '.,.', ','):
                    to_rename.append(next_season)
                    if separator.name == 'episode_title':
                        to_remove.append(next_match)

                    current_season = next_season
                elif separator.value in season_range_separator:
                    to_rename.append(next_season)
                    if separator.name == 'episode_title':
                        to_remove.append(next_match)

                    # then create the season range
                    for i in range(current_season.value + 1, next_season.value):
                        new_season = copy.copy(current_season)
                        new_season.value = i
                        new_season.start = separator.start
                        new_season.end = separator.end
                        to_append.append(new_season)

                    current_season = next_season
                else:
                    break

        return to_remove, to_append, to_rename


class FixWrongSeasonAndReleaseGroup(Rule):
    """
    Work-around for https://github.com/guessit-io/guessit/issues/303
    TODO: Remove when this bug is fixed

    e.g.: Show.Name.S06E04.1080i.HDTV.DD5.1.H264.BS666.rartv

    guessit -t episode "Show.Name.S06E04.1080i.HDTV.DD5.1.H264.BS666.rartv"

    without this fix:
        For: Show.Name.S06E04.1080i.HDTV.DD5.1.H264.BS666.rartv
        GuessIt found: {
            "title": "Show Name",
            "season": [
                6,
                666
            ],
            "episode": 4,
            "screen_size": "1080i",
            "format": "HDTV",
            "audio_codec": "DolbyDigital",
            "audio_channels": "5.1",
            "video_codec": "h264",
            "release_group": "B",
            "type": "episode"
        }

    with this fix:
        For: Show.Name.S06E04.1080i.HDTV.DD5.1.H264.BS666
        GuessIt found: {
            "title": "Show Name",
            "season": 6,
            "episode": 4,
            "screen_size": "1080i",
            "format": "HDTV",
            "audio_codec": "DolbyDigital",
            "audio_channels": "5.1",
            "video_codec": "h264",
            "release_group": "BS666",
            "type": "episode"
        }

    """
    priority = POST_PROCESS
    consequence = [RemoveMatch, AppendMatch]
    previous_properties = ('video_codec', 'format', 'release_group')

    def when(self, matches, context):
        """
        :param matches:
        :type matches: rebulk.match.Matches
        :param context:
        :type context: dict
        :return:
        """
        to_remove = []
        to_append = []

        fileparts = matches.markers.named('path')
        for filepart in marker_sorted(fileparts, matches):
            seasons = matches.range(filepart.start, filepart.end, predicate=lambda match: match.name == 'season')
            # only when there are 2 seasons
            last_season = seasons[-1] if len(seasons) == 2 else None
            previous = matches.previous(last_season, index=-1) if last_season else None
            if previous and previous.start >= filepart.start:
                holes = matches.holes(start=previous.end, end=last_season.start)
                hole = holes[0] if len(holes) == 1 else None
                # there's only 1 hole before the season
                if not hole:
                    continue

                prefix = previous.value if previous.name == 'release_group' else ''
                correct_release_group = prefix + hole.raw + last_season.raw

                if matches.previous(last_season, predicate=lambda match: match.name in self.previous_properties):
                    new_release_group = copy.copy(previous)
                    new_release_group.value = correct_release_group

                    to_remove.append(last_season)
                    to_remove.append(previous)
                    to_append.append(new_release_group)

        return to_remove, to_append


class FixSeasonRangeDetection(Rule):
    """
    Work-around for https://github.com/guessit-io/guessit/issues/287
    TODO: Remove when this bug is fixed

    e.g.: show name s01-s04

    guessit -t episode "show name s01-s04"

    without this fix:
        For: show name s01-s04
        GuessIt found: {
            "title": "show name",
            "season": [
                1,
                4
            ],
            "type": "episode"
        }

    with this fix:
        For: show name s01-s04
        GuessIt found: {
            "title": "show name",
            "season": [
                1,
                2,
                3,
                4
            ],
            "type": "episode"
        }
    """
    priority = POST_PROCESS
    consequence = [RemoveMatch, AppendMatch]

    def when(self, matches, context):
        """
        :param matches:
        :type matches: rebulk.match.Matches
        :param context:
        :type context: dict
        :return:
        """
        to_remove = []
        to_append = []

        fileparts = matches.markers.named('path')
        for filepart in marker_sorted(fileparts, matches):
            seasons = matches.range(filepart.start, filepart.end, predicate=lambda match: match.name == 'season')
            # only when there are 2 seasons
            start_season = seasons[0] if len(seasons) == 2 else None
            end_season = seasons[-1] if len(seasons) == 2 else None

            # and no episodes on any next fileparts
            if matches.range(filepart.end, predicate=lambda match: match.name == 'episode'):
                continue

            # and first season is lesser than the second and both are between 1 and 99
            if start_season and end_season and 0 < start_season.value < end_season.value < 100:
                season_separator = matches.input_string[start_season.end:end_season.start]
                # and they are separated by a 'season range separator'
                if season_separator.lower() in season_range_separator:
                    episode_title = matches.next(start_season, index=0)
                    if episode_title and episode_title.name == 'episode_title' and episode_title.value.lower() == 'to':
                        to_remove.append(episode_title)

                    # then create the missing numbers
                    for i in range(start_season.value + 1, end_season.value):
                        new_season = copy.copy(start_season)
                        new_season.value = i
                        to_append.append(new_season)

        return to_remove, to_append


class FixEpisodeRangeDetection(Rule):
    """
    Work-around for https://github.com/guessit-io/guessit/issues/287
    TODO: Remove when this bug is fixed

    e.g.: show name s02e01-e04

    guessit -t episode "show name s02e01-e04"

    without this fix:
        For: show name s02e01-e04
        GuessIt found: {
            "title": "show name",
            "season": 2
            "episode": [
                1,
                4
            ],
            "type": "episode"
        }

    with this fix:
        For: show name s02e01-e04
        GuessIt found: {
            "title": "show name",
            "season" 2
            "episode": [
                1,
                2,
                3,
                4
            ],
            "type": "episode"
        }
    """
    priority = POST_PROCESS
    consequence = [AppendMatch, RenameMatch('episode')]

    def when(self, matches, context):
        """
        :param matches:
        :type matches: rebulk.match.Matches
        :param context:
        :type context: dict
        :return:
        """
        to_append = []
        to_rename = []

        fileparts = matches.markers.named('path')
        for filepart in marker_sorted(fileparts, matches):
            episodes = matches.range(filepart.start, filepart.end, predicate=lambda match: match.name == 'episode')

            episode_count = matches.next(episodes[0], index=0) if len(episodes) == 1 else None
            if episode_count and episode_count.name == 'episode_count' and episode_count.end <= filepart.end:
                episodes.append(episode_count)

            # only when there are 2 episodes
            start_episode = episodes[0] if len(episodes) == 2 else None
            end_episode = episodes[-1] if len(episodes) == 2 else None

            # and no episodes on any next fileparts
            if matches.range(filepart.end, predicate=lambda match: match.name == 'episode'):
                continue

            # and first episode is lesser than the second and both are between 1 and 99
            if start_episode and end_episode and 0 < start_episode.value < end_episode.value < 100:
                holes = matches.holes(start=start_episode.end, end=end_episode.start)
                hole = holes[0] if len(holes) == 1 else None
                # and they are separated by a 'range separator'
                if hole and hole.value.lower() in ('-', '-e'):
                    # then create the missing numbers
                    for i in range(start_episode.value + 1, end_episode.value):
                        new_season = copy.copy(start_episode)
                        new_season.value = i
                        to_append.append(new_season)

                    if end_episode.name == 'episode_count':
                        to_rename.append(end_episode)

        return to_append, to_rename


class FixEpisodeRangeWithSeasonDetection(Rule):
    """
    Work-around for https://github.com/guessit-io/guessit/issues/287
    TODO: Remove when this if this scenario is fixed upstream

    e.g.: Show.Name.S01E01-S01E21

    guessit -t episode "Show.Name.S01E01-S01E21"

    without this fix:
        For: Show.Name.S01E01-S01E04
        GuessIt found: {
            "title": "Show Name",
            "season": 1,
            "episode": [
                1,
                4
            ],
            "type": "episode"
        }


    with this fix:
        For: Show.Name.S01E01-S01E04
        GuessIt found: {
            "title": "Show Name",
            "season": 1,
            "episode": [
                1,
                2,
                3,
                4
            ],
            "type": "episode"
        }
    """
    priority = POST_PROCESS
    consequence = [RemoveMatch, AppendMatch]

    def when(self, matches, context):
        """
        :param matches:
        :type matches: rebulk.match.Matches
        :param context:
        :type context: dict
        :return:
        """
        to_remove = []
        to_append = []

        fileparts = matches.markers.named('path')
        for filepart in marker_sorted(fileparts, matches):
            seasons = matches.range(filepart.start, filepart.end, predicate=lambda match: match.name == 'season')
            # only when there are 2 seasons
            start_season = seasons[0] if len(seasons) == 2 else None
            end_season = seasons[-1] if len(seasons) == 2 else None

            # and no episodes on any next fileparts
            if matches.range(filepart.end, predicate=lambda match: match.name == 'episode'):
                continue

            # and first season is lesser than the second and both are between 1 and 99
            if start_season and end_season and start_season.value == end_season.value:
                first_episode = matches.next(start_season, index=0)
                end_episode = matches.next(end_season, index=0)

                if first_episode and end_episode and first_episode.name == end_episode.name == 'episode' \
                        and 0 < first_episode.value < end_episode.value < 100:
                    season_separator = matches.input_string[first_episode.end:end_season.start]
                    # and they are separated by a 'season range separator'
                    if season_separator.lower() in season_range_separator:
                        episode_title = matches.next(start_season, index=0)
                        if episode_title and episode_title.name == 'episode_title' \
                                and episode_title.value.lower() == 'to':
                            to_remove.append(episode_title)

                        # then create the missing numbers
                        for i in range(first_episode.value + 1, end_episode.value):
                            new_episode = copy.copy(first_episode)
                            new_episode.value = i
                            to_append.append(new_episode)

        return to_remove, to_append


class FixWrongEpisodeDetectionInSeasonRange(Rule):
    """
    Work-around for https://github.com/guessit-io/guessit/issues/304
    TODO: Remove when this bug is fixed

    e.g.: "Show.season_1-10.(DVDrip)"

    guessit -t episode "Show.season_1-10.(DVDrip)"

    without the fix:
        For: Show.season_1-10.(DVDrip)
        GuessIt found: {
            "title": "Show",
            "season": [
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9,
                10
            ],
            "episode": 10,
            "format": "DVD",
            "type": "episode"
        }


    with the fix:
        For: Show.season_1-10.(DVDrip)
        GuessIt found: {
            "title": "Show",
            "season": [
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9,
                10
            ],
            "format": "DVD",
            "type": "episode"
        }

    """
    priority = POST_PROCESS
    consequence = RemoveMatch

    def when(self, matches, context):
        """
        :param matches:
        :type matches: rebulk.match.Matches
        :param context:
        :type context: dict
        :return:
        """
        to_remove = []

        fileparts = matches.markers.named('path')
        for filepart in marker_sorted(fileparts, matches):
            seasons = matches.range(filepart.start, filepart.end, predicate=lambda match: match.name == 'season')
            episodes = matches.range(filepart.start, filepart.end, predicate=lambda match: match.name == 'episode')
            # bug happens when there are more than 1 season and exactly 1 episode
            if seasons and episodes and len(seasons) > 1 and len(episodes) == 1:
                episode = episodes[0]
                conflict = matches.at_match(episode, predicate=
                                            lambda match: not match.private and match.name == 'season')
                if conflict:
                    to_remove.append(episode)

        return to_remove


class ExpectedTitlePostProcessor(Rule):
    """
    Expected title post processor to replace dots with spaces (needed when expected title is a regex)

    e.g.: Show.Net.S01E06.720p

    guessit -t episode -T "re:^\w+ Net\b" "Show.Net.S01E06.720p"

    without this rule:
        For: Show.Net.S01E06.720p
        GuessIt found: {
            "title": "Show.Net",
            "season": 1,
            "episode": 6,
            "screen_size": "720p",
            "type": "episode"
        }

    with this rule:
        For: Show.Net.S01E06.720p
        GuessIt found: {
            "title": "Show Net",
            "season": 1,
            "episode": 6,
            "screen_size": "720p",
            "type": "episode"
        }
    """
    priority = POST_PROCESS
    consequence = [RemoveMatch, AppendMatch]

    def when(self, matches, context):
        """
        :param matches:
        :type matches: rebulk.match.Matches
        :param context:
        :type context: dict
        :return:
        """
        # All titles that matches because of a expected title was tagged as 'expected'
        # and title.value is not in the expected list, it's a regex
        titles = matches.tagged('expected', predicate=lambda match: match.value not in context.get('expected_title'))

        to_remove = []
        to_append = []

        for title in titles:
            # Remove all dots from the title
            new_title = copy.copy(title)  # IMPORTANT - never change the value. Better to remove and add it
            new_title.value = cleanup(title.value)
            to_remove.append(title)
            to_append.append(new_title)

        return to_remove, to_append


class FixMultipleTitles(Rule):
    """
    Probably a guessit bug, guessit might return more than one title instead of alternative_titles
    bug: https://github.com/guessit-io/guessit/issues/309

    e.g.: /shows/Show.Name.S01E05.WEBRip.x264-GROUP__gYDfLA/Show.Name.S01E05.WEBRip.x264-GROUP

    guessit -t episode "/shows/Show.Name.S01E05.WEBRip.x264-GROUP__gYDfLA/Show.Name.S01E05.WEBRip.x264-GROUP"

    without this rule:
        For: /shows/Show.Name.S01E05.WEBRip.x264-GROUP__gYDfLA/Show.Name.S01E05.WEBRip.x264-GROUP
        GuessIt found: {
            "title": [
                "Show Name",
                "GROUP gYDfLA"
            ],
            "season": 1,
            "episode": 5,
            "format": "WEBRip",
            "video_codec": "h264",
            "release_group": "GROUP",
            "type": "episode"
        }

    with this rule:
        For: /shows/Show.Name.S01E05.WEBRip.x264-GROUP__gYDfLA/Show.Name.S01E05.WEBRip.x264-GROUP
        GuessIt found: {
            "title": "Show Name",
            "season": 1,
            "episode": 5,
            "format": "WEBRip",
            "video_codec": "h264",
            "release_group": "GROUP",
            "type": "episode"
        }

    """
    priority = POST_PROCESS
    consequence = RemoveMatch

    def when(self, matches, context):
        """
        :param matches:
        :type matches: rebulk.match.Matches
        :param context:
        :type context: dict
        :return:
        """
        # In case of duplicated titles, keep only the first one
        titles = matches.named('title')

        to_remove = titles[1:]

        return to_remove


class ReleaseGroupPostProcessor(Rule):
    """
    Release Group post processor
    Removes invalid parts from the release group property

    e.g.: show name s01-s04

    guessit -t episode "Some.Show.S02E14.1080p.HDTV.X264-GROUP[TRASH]"

    without this post processor:
        For: Some.Show.S02E14.1080p.HDTV.X264-GROUP[TRASH]
        GuessIt found: {
            "title": "Some Show",
            "season": 2,
            "episode": 14,
            "screen_size": "1080p",
            "format": "HDTV",
            "video_codec": "h264",
            "release_group": "GROUP[TRASH]",
            "type": "episode"
        }


    with this post processor:
        For: Some.Show.S02E14.1080p.HDTV.X264-GROUP[TRASH]
        GuessIt found: {
            "title": "Some Show",
            "season": 2,
            "episode": 14,
            "screen_size": "1080p",
            "format": "HDTV",
            "video_codec": "h264",
            "release_group": "GROUP",
            "type": "episode"
        }

    """
    priority = POST_PROCESS
    consequence = [RemoveMatch, AppendMatch]
    regexes = [
        # italian release: drop everything after [CURA]
        re.compile(r'\[CURA\].*$', flags=re.IGNORECASE),

        # [word], (word), {word}
        re.compile(r'(?<=.)\W*[\[\(\{].+[\}\)\]]?\W*$', flags=re.IGNORECASE),

        # https://github.com/guessit-io/guessit/issues/299
        # 200MB, 1GB, 4.2GB, 1.1TB
        re.compile(r'(\W*\b(\d+\.)?\d+[mgt]b\b\W*)', flags=re.IGNORECASE),

        # https://github.com/guessit-io/guessit/issues/301
        # vol255+101
        re.compile(r'\.vol\d+\+\d+', flags=re.IGNORECASE),

        # https://github.com/guessit-io/guessit/issues/300
        # ReEnc, Re-Enc
        re.compile(r'\W*\bre\-?enc\b\W*', flags=re.IGNORECASE),

        # NLSubs-word
        re.compile(r'\W*\b([a-z]{2,3})(subs?)\b\W*', flags=re.IGNORECASE),

        # word.rar, word.gz
        re.compile(r'\.((rar)|(gz)|(\d+))$', flags=re.IGNORECASE),

        # word.rartv, word.ettv
        re.compile(r'(?<=[a-z0-9]{3})\.([a-z]+)$', flags=re.IGNORECASE),

        # word-fansub
        re.compile(r'(?<=[a-z0-9]{3})\-((fan)?sub(s)?)$', flags=re.IGNORECASE),

        # https://github.com/guessit-io/guessit/issues/302
        # INTERNAL
        re.compile(r'\W*\b(internal|obfuscated|vtv|sd|avc|dirfix|dual)\b\W*', flags=re.IGNORECASE),

        # ...word
        re.compile(r'^\W+', flags=re.IGNORECASE),

        # word[.
        re.compile(r'\W+$', flags=re.IGNORECASE),

        re.compile(r'\s+', flags=re.IGNORECASE),
    ]

    def when(self, matches, context):
        """
        :param matches:
        :type matches: rebulk.match.Matches
        :param context:
        :type context: dict
        :return:
        """
        release_groups = matches.named('release_group')
        to_remove = []
        to_append = []
        for release_group in release_groups:
            value = release_group.value
            for regex in self.regexes:
                value = regex.sub(' ', value).strip()
                if not value:
                    break

            if not value:
                to_remove.append(release_group)
            if release_group.value != value:
                new_release_group = copy.copy(release_group)
                new_release_group.value = cleanup(value)
                to_remove.append(release_group)
                to_append.append(new_release_group)

        return to_remove, to_append


def rules():
    """
    Returns all custom rules to be applied to guessit default api.

    IMPORTANT! The order is important.
    Certain rules needs to be executed first, and others should be executed at the end
    DO NOT define priority or dependency in each rule, it can become a mess. Better to just define the correct order
    in this method

    Builder for rebulk object.
    :return: Created Rebulk object
    :rtype: Rebulk
    """
    return Rebulk().rules(
        FixTvChaosUkWorkaround,
        FixAnimeReleaseGroup,
        SpanishNewpctReleaseName,
        FixInvalidTitleOrAlternativeTitle,
        FixScreenSizeConflict,
        FixWrongTitleDueToFilmTitle,
        FixSeasonNotDetected,
        FixWrongSeasonRangeDetectionDueToEpisode,
        FixWrongSeasonAndReleaseGroup,
        FixSeasonEpisodeDetection,
        FixSeasonRangeDetection,
        FixEpisodeRangeDetection,
        FixEpisodeRangeWithSeasonDetection,
        FixWrongEpisodeDetectionInSeasonRange,
        FixTitlesContainsNumber,
        FixWrongTitlesWithCompleteKeyword,
        AnimeWithSeasonAbsoluteEpisodeNumbers,
        AnimeAbsoluteEpisodeNumbers,
        AbsoluteEpisodeNumbers,
        PartsAsEpisodeNumbers,
        ExpectedTitlePostProcessor,
        CreateExtendedTitleWithAlternativeTitles,
        CreateExtendedTitleWithCountryOrYear,
        ReleaseGroupPostProcessor,
        FixMultipleTitles
    )
