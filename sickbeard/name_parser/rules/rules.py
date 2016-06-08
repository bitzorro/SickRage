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
    """
    priority = POST_PROCESS
    consequence = [RemoveMatch, AppendMatch]

    def when(self, matches, context):
        titles = matches.tagged('expected')

        to_remove = []
        to_append = []

        for title in titles:
            if title.value not in context.get('expected_title'):
                # IMPORTANT - never change the value. Better to remove and add it
                new_title = copy.copy(title)
                new_title.value = title.value.replace('.', ' ')  # TODO: improve this
                to_remove.append(title)
                to_append.append(new_title)

        return to_remove, to_append


class CreateExtendedTitle(Rule):
    """
    ExtendedTitle: 'extended_title' - post processor to add country or year to the existing title.
    """
    priority = POST_PROCESS
    consequence = AppendMatch

    def when(self, matches, context):
        # film_title might contain the correct title due to this bug:
        # https://github.com/guessit-io/guessit/issues/294
        extended_title = matches.named('film_title', index=0) or matches.named('title', index=0)
        if not extended_title:
            return

        extended_title = copy.copy(extended_title)
        extended_title.name = 'extended_title'

        after_title = matches.next(extended_title, index=0)

        if after_title and after_title.name in ('country', 'year'):
            next_match = matches.next(after_title, index=0)
            # Only add country or year if the next match is season, episode or date
            if next_match and next_match.name in ('season', 'episode', 'date'):
                extended_title.value = extended_title.value + ' ' + re.sub(r'\W*', '', str(after_title.raw))
                extended_title.end = after_title.end
                extended_title.raw_end = after_title.raw_end

        return extended_title


class AnimeAbsoluteEpisodeNumbers(Rule):
    """
    Medusa: If it's an anime, use absolute episode numbers
    """
    priority = POST_PROCESS - 1
    consequence = [RemoveMatch, AppendMatch]

    def when(self, matches, context):
        if context.get('show_type') != 'regular' and matches.tagged('anime') and matches.tagged('weak-duplicate'):
            season = matches.named('season', index=0)
            episode = matches.named('episode', index=0)
            if season and episode and season.end == episode.start and season.raw.isdigit() and episode.raw.isdigit():
                absolute_episode = copy.copy(episode)
                absolute_episode.name = 'absolute_episode'
                absolute_episode.value = int(episode.raw)
                to_remove = [season, episode]
                to_append = [absolute_episode]
                return to_remove, to_append


class AbsoluteEpisodeNumbers(Rule):
    """
    Medusa absolute episode numbers rule
    """
    priority = POST_PROCESS
    consequence = RenameMatch('absolute_episode')
    non_words_re = re.compile(r'\W')
    episode_words = ('e', 'episode', 'ep')

    def when(self, matches, context):
        if context.get('show_type') != 'regular' and not matches.named('season'):
            episodes = matches.named('episode')
            to_rename = []
            for episode in episodes:
                if matches.named('episode_count'):
                    # Some.Show.1of8..Title.x264.AAC.Group
                    # not absolute episode
                    continue

                previous = matches.previous(episode, index=-1)
                if previous:
                    hole = matches.holes(start=previous.end, end=episode.start, index=0)
                    if hole and self.non_words_re.sub('', hole.value).lower() in self.episode_words:
                        # Some.Show.E07.1080p.HDTV.x265-GROUP
                        # Some.Show.Episode.10.Some.Title.720p
                        # not absolute episode
                        continue
                to_rename.append(episode)

            return to_rename


class PartsAsEpisodeNumbers(Rule):
    """
    Medusa rule: Show.Name.Part.3.720p.HDTV.x264-Group

    Part should become the episode
    """
    priority = POST_PROCESS
    consequence = RenameMatch('episode')

    def when(self, matches, context):
        if not matches.named('season') and not matches.named('episode'):
            return matches.named('part')


class FixSeasonEpisodeDetection(Rule):
    """
    Work-around for https://github.com/guessit-io/guessit/issues/295
    """
    priority = POST_PROCESS
    consequence = RenameMatch('episode')

    def when(self, matches, context):
        seasons = matches.named('season')
        if seasons and len(seasons) == 2 and not matches.named('episode'):
            next_match = matches.next(seasons[-1], index=0)
            # guessit gets confused when the next match is x264 or x265
            if next_match and next_match.name == 'video_codec' and next_match.value in ('h264', 'h265'):
                episode = seasons[1]
                return episode  # to be renamed to episode


class FixSeasonNotDetected(Rule):
    """
    Work-around for https://github.com/guessit-io/guessit/issues/306
    # Show.Name.-.Season.3.-.720p.BluRay.-.x264.-.Group
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

    # Show.Name.S06E04.1080i.HDTV.DD5.1.H264.BS666.rartv
    """
    priority = POST_PROCESS
    consequence = [RemoveMatch, AppendMatch]
    problematic_words = {
        'bs666', 'ccs3', 'qqss44',
    }

    def when(self, matches, context):
        seasons = matches.named('season')
        if seasons and len(seasons) == 2:
            last_season = seasons[-1]
            previous = matches.previous(last_season, index=-1)
            if previous:
                holes = matches.holes(start=previous.end, end=last_season.start)
                if len(holes) == 1:
                    to_remove = []
                    to_append = []
                    prefix = previous.value if previous.name == 'release_group' else ''
                    correct_release_group = prefix + holes[0].raw + last_season.raw
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
    """
    priority = POST_PROCESS
    consequence = AppendMatch
    range_separator = ('-', '-s', '.to.s')

    def when(self, matches, context):
        seasons = matches.named('season')
        if seasons and len(seasons) == 2:
            start_season = seasons[0]
            end_season = seasons[-1]
            if 1 < end_season.value - start_season.value < 30:
                season_separator = matches.input_string[start_season.end:end_season.start]
                if season_separator.lower() in self.range_separator:
                    to_append = []
                    for i in range(start_season.value + 1, end_season.value):
                        new_season = copy.copy(start_season)
                        new_season.value = i
                        to_append.append(new_season)

                    return to_append


class FixEpisodeRangeDetection(Rule):
    """
    Work-around for https://github.com/guessit-io/guessit/issues/287
    """
    priority = POST_PROCESS
    consequence = AppendMatch

    def when(self, matches, context):
        episodes = matches.named('episode')
        if episodes and len(episodes) == 2:
            start_episode = episodes[0]
            end_episode = episodes[-1]
            if 1 < end_episode.value - start_episode.value < 30:
                holes = matches.holes(start=start_episode.end, end=end_episode.start)
                if len(holes) == 1:
                    hole = holes[0]
                    if hole.value.lower() in ('-', '-e'):
                        to_append = []
                        for i in range(start_episode.value + 1, end_episode.value):
                            new_season = copy.copy(start_episode)
                            new_season.value = i
                            to_append.append(new_season)

                        return to_append


class ReleaseGroupPostProcessor(Rule):
    """
    Release Group post processor
    """
    priority = POST_PROCESS
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

        # word.rar, word.gz
        re.compile(r'\.((rar)|(gz)|(\d+))$', flags=re.IGNORECASE),

        # WORD.rartv, WORD.ettv
        re.compile(r'(?<=[A-Z0-9]{3})\.([a-z]+)$', flags=re.IGNORECASE),

        # NLSubs-word
        re.compile(r'\W*\b([A-Z]{2})(subs)\b\W*', flags=re.IGNORECASE),

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
                          FixSeasonRangeDetection, FixEpisodeRangeDetection, AnimeAbsoluteEpisodeNumbers,
                          AbsoluteEpisodeNumbers, PartsAsEpisodeNumbers, ExpectedTitlePostProcessor,
                          CreateExtendedTitle, ReleaseGroupPostProcessor)
