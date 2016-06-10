#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Processors
"""
import copy
import re
from rebulk.processors import POST_PROCESS
from rebulk.rebulk import Rebulk
from rebulk.rules import Rule, AppendMatch, RemoveMatch, RenameMatch


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
        titles = matches.tagged('expected')

        to_remove = []
        to_append = []

        for title in titles:
            # If title.value is not in the expected list, it's a regex
            if title.value not in context.get('expected_title'):
                # Remove all dots from the title
                new_title = copy.copy(title)  # IMPORTANT - never change the value. Better to remove and add it
                new_title.value = title.value.replace('.', ' ')  # TODO: improve this
                to_remove.append(title)
                to_append.append(new_title)

        return to_remove, to_append


class CreateExtendedTitle(Rule):
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

    def when(self, matches, context):
        """
        :param matches:
        :type matches: rebulk.match.Matches
        :param context:
        :type context: dict
        :return:
        """
        # film_title might contain the correct title due to this bug:
        # https://github.com/guessit-io/guessit/issues/294
        # TODO: Remove file_title when this bug is fixed
        extended_title = matches.named('film_title', index=0) or matches.named('title', index=0)
        if not extended_title:
            return

        after_title = matches.next(extended_title, index=0)

        # only if there's a country or year
        if after_title and after_title.name in ('country', 'year'):
            next_match = matches.next(after_title, index=0)
            # Only add country or year if the next match is season, episode or date
            if next_match and next_match.name in ('season', 'episode', 'date'):
                extended_title = copy.copy(extended_title)
                extended_title.name = 'extended_title'
                extended_title.value = extended_title.value + ' ' + re.sub(r'\W*', '', str(after_title.raw))
                extended_title.end = after_title.end
                extended_title.raw_end = after_title.raw_end
                return extended_title


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
    priority = POST_PROCESS + 2
    consequence = [RemoveMatch, AppendMatch]

    def when(self, matches, context):
        """
        :param matches:
        :type matches: rebulk.match.Matches
        :param context:
        :type context: dict
        :return:
        """
        if context.get('show_type') != 'regular' and matches.tagged('anime'):
            season = matches.named('season', index=0)
            if season:
                title = matches.previous(season, index=-1)
                episode_title = matches.next(season, index=0)

                # the previous match before the season is the series name and
                # the match after season is episode title and episode title is a number
                if title and episode_title and title.name == 'title' and episode_title.name == 'episode_title' \
                        and episode_title.value.isdigit() and season.parent and season.parent.private:
                    to_remove = []
                    to_append = []

                    # adjust title to append the series name.
                    # Only the season.parent contains the S prefix in its value
                    new_title = copy.copy(title)
                    new_title.value = ' '.join([title.value, season.parent.value])
                    new_title.end = season.end
                    to_remove.append(title)
                    to_remove.append(season)
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
    Medusa rule: If it's an anime, use absolute episode numbers

    e.g.: [Group].Show.Name.S2.-.19.[1080p]

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
    priority = POST_PROCESS - 1
    consequence = [RemoveMatch, AppendMatch]

    def when(self, matches, context):
        # only for shows that seems to be animes
        if context.get('show_type') != 'regular' and matches.tagged('anime') and matches.tagged('weak-duplicate'):
            season = matches.named('season', index=0)
            episode = matches.named('episode', index=0)
            # there should be season and episode and the episode should start right after the season and both raw values
            # should be digit
            if season and episode and season.end == episode.start and season.raw.isdigit() and episode.raw.isdigit():
                # then make them an absolute episode:
                absolute_episode = copy.copy(episode)
                absolute_episode.name = 'absolute_episode'
                absolute_episode.value = int(episode.raw)  # episode raw contains the season and the episode
                to_remove = [season, episode]
                to_append = [absolute_episode]
                return to_remove, to_append


class AbsoluteEpisodeNumbers(Rule):
    """
    Medusa absolute episode numbers rule

    e.g.: [Group].Show.Name.S2.-.19.[1080p]

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
    consequence = RenameMatch('absolute_episode')
    non_words_re = re.compile(r'\W')
    episode_words = ('e', 'episode', 'ep')

    def when(self, matches, context):
        # if it seems to be anime and it doesn't have season
        if context.get('show_type') != 'regular' and not matches.named('season'):
            episodes = matches.named('episode')
            to_rename = []
            for episode in episodes:
                # And there's no episode count
                if matches.named('episode_count'):
                    # Some.Show.1of8..Title.x264.AAC.Group
                    # not absolute episode
                    return

                previous = matches.previous(episode, index=-1)
                # And it's not part of an episode range (previous is not an episode)
                if previous and previous.name != 'episode':
                    hole = matches.holes(start=previous.end, end=episode.start, index=0)
                    # and the hole is not an 'episode' word (e.g.: e, ep, episode)
                    if hole and self.non_words_re.sub('', hole.value).lower() in self.episode_words:
                        # Some.Show.E07.1080p.HDTV.x265-GROUP
                        # Some.Show.Episode.10.Some.Title.720p
                        # not absolute episode
                        return
                to_rename.append(episode)

            return to_rename


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

    def when(self, matches, context):
        seasons = matches.named('season')
        # bug happens when there are 2 seasons and no episode
        if seasons and len(seasons) == 2 and not matches.named('episode'):
            next_match = matches.next(seasons[-1], index=0)
            # guessit gets confused when the next match is x264 or x265
            if next_match and next_match.name == 'video_codec' and next_match.value in ('h264', 'h265'):
                # rename the second season to episode
                episode = seasons[1]
                return episode


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
    consequence = [RemoveMatch, RenameMatch('season')]

    def when(self, matches, context):
        episode = matches.named('episode', index=0)
        if episode:
            season = matches.previous(episode, index=-1)
            if season and season.name == 'alternative_title' and season.value.lower() == 'season':
                return season, episode


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
    problematic_words = {
        'bs666', 'ccs3', 'qqss44',
    }

    def when(self, matches, context):
        seasons = matches.named('season')
        # only when there are 2 seasons
        if seasons and len(seasons) == 2:
            last_season = seasons[-1]
            previous = matches.previous(last_season, index=-1)
            # there's only 1 hole before the season
            if previous:
                holes = matches.holes(start=previous.end, end=last_season.start)
                if len(holes) == 1:
                    to_remove = []
                    to_append = []
                    prefix = previous.value if previous.name == 'release_group' else ''
                    correct_release_group = prefix + holes[0].raw + last_season.raw
                    # and this hole is part of the problematic words
                    for word in self.problematic_words:
                        if word in correct_release_group.lower():
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
    consequence = AppendMatch
    range_separator = ('-', '-s', '.to.s')

    def when(self, matches, context):
        seasons = matches.named('season')
        # only when there are 2 seasons
        if seasons and len(seasons) == 2:
            start_season = seasons[0]
            end_season = seasons[-1]
            # and first season is lesser than the second and the difference is not too big
            if 1 < end_season.value - start_season.value < 30:
                season_separator = matches.input_string[start_season.end:end_season.start]
                # and they are separated by a 'range separator'
                if season_separator.lower() in self.range_separator:
                    to_append = []
                    # then create the missing numbers
                    for i in range(start_season.value + 1, end_season.value):
                        new_season = copy.copy(start_season)
                        new_season.value = i
                        to_append.append(new_season)

                    return to_append


class FixEpisodeRangeDetection(Rule):
    """
    Work-around for https://github.com/guessit-io/guessit/issues/287
    TODO: Remove when this bug is fixed

    e.g.: show name s01-s04

    guessit -t episode "show name s01-s04"

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
    consequence = AppendMatch

    def when(self, matches, context):
        episodes = matches.named('episode')
        # only when there are 2 episodes
        if episodes and len(episodes) == 2:
            start_episode = episodes[0]
            end_episode = episodes[-1]
            # and first episode is lesser than the second and the difference is not too big
            if 1 < end_episode.value - start_episode.value < 30:
                holes = matches.holes(start=start_episode.end, end=end_episode.start)
                if len(holes) == 1:
                    hole = holes[0]
                    # and they are separated by a 'range separator'
                    if hole.value.lower() in ('-', '-e'):
                        to_append = []
                        # then create the missing numbers
                        for i in range(start_episode.value + 1, end_episode.value):
                            new_season = copy.copy(start_episode)
                            new_season.value = i
                            to_append.append(new_season)

                        return to_append


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
    priority = POST_PROCESS - 100
    consequence = [RemoveMatch, AppendMatch]
    regexes = [
        # [word], (word), {word}
        re.compile(r'\W*[\[\(\{].+[\}\)\]]\W*$', flags=re.IGNORECASE),

        # https://github.com/guessit-io/guessit/issues/299
        # 200MB, 1GB
        re.compile(r'(\W*\b\d+[mg]b\b\W*)', flags=re.IGNORECASE),

        # https://github.com/guessit-io/guessit/issues/301
        # vol255+101
        re.compile(r'\.vol\d+\+\d+', flags=re.IGNORECASE),

        # https://github.com/guessit-io/guessit/issues/300
        # ReEnc, Re-Enc
        re.compile(r'\W*\bre\-?enc\b\W*', flags=re.IGNORECASE),

        # NLSubs-word
        re.compile(r'\W*\b([A-Z]{2})(subs)\b\W*', flags=re.IGNORECASE),

        # word.rar, word.gz
        re.compile(r'\.((rar)|(gz)|(\d+))$', flags=re.IGNORECASE),

        # WORD.rartv, WORD.ettv
        re.compile(r'(?<=[A-Z0-9]{3})\.([a-z]+)$', flags=re.IGNORECASE),

        # https://github.com/guessit-io/guessit/issues/302
        # INTERNAL
        re.compile(r'\W*\b((INTERNAL)|(Obfuscated)|(VTV)|(SD)|(AVC))\b\W*', flags=re.IGNORECASE),

        # ...word
        re.compile(r'^\W+', flags=re.IGNORECASE),

        # word[.
        re.compile(r'\W+$', flags=re.IGNORECASE),
    ]

    def when(self, matches, context):
        release_groups = matches.named('release_group')
        to_remove = []
        to_append = []
        for release_group in release_groups:
            value = release_group.value
            for regex in self.regexes:
                value = regex.sub('', value)
                if not value:
                    break

            if not value:
                to_remove.append(release_group)
            if release_group.value != value:
                new_release_group = copy.copy(release_group)
                new_release_group.value = value
                to_remove.append(release_group)
                to_append.append(new_release_group)

        return to_remove, to_append


def rules():
    """
    Builder for rebulk object.
    :return: Created Rebulk object
    :rtype: Rebulk
    """
    return Rebulk().rules(FixSeasonNotDetected, FixWrongSeasonAndReleaseGroup, FixSeasonEpisodeDetection,
                          FixSeasonRangeDetection, FixEpisodeRangeDetection, AnimeWithSeasonAbsoluteEpisodeNumbers,
                          AnimeAbsoluteEpisodeNumbers, AbsoluteEpisodeNumbers, PartsAsEpisodeNumbers,
                          ExpectedTitlePostProcessor, CreateExtendedTitle, ReleaseGroupPostProcessor)
