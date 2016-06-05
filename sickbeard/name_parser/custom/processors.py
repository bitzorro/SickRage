#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Processors
"""
import copy
import re
from rebulk.processors import POST_PROCESS
from rebulk.rebulk import Rebulk
from rebulk.rules import CustomRule


class ExpectedTitlePostProcessor(CustomRule):
    """
    Expected title post processor to replace dots with spaces (needed when expected title is a regex)
    """
    priority = POST_PROCESS

    def when(self, matches, context):
        return matches.tagged('expected')

    def then(self, matches, when_response, context):  # pragma: no cover
        if when_response:
            title = matches.tagged('expected', index=0)
            if title.value not in context.get('expected_title'):
                # TODO: improve this
                title.value = title.value.replace('.', ' ')


class ExtendedTitlePostProcessor(CustomRule):
    """
    ExtendedTitle post processor to add country or year to the existing title
    """
    priority = POST_PROCESS

    # film_title might contain the correct title due to this bug: https://github.com/guessit-io/guessit/issues/294
    def when(self, matches, context):
        return (matches.named('country') or matches.named('year')) and \
               (matches.named('title') or matches.named('film_title')) and \
               (matches.named('season') or matches.named('episode') or matches.named('date'))

    def then(self, matches, when_response, context):  # pragma: no cover
        if when_response:
            extended_title = matches.named('film_title', index=0) or matches.named('title', index=0)
            after_title = matches.next(extended_title, index=0)
            if after_title and after_title.name in ('country', 'year'):
                next_match = matches.next(after_title, index=0)
                # Only add country or year if the next match is season, episode or date
                if next_match and next_match.name in ('season', 'episode', 'date'):
                    extended_title = copy.copy(extended_title)
                    extended_title.name = 'extended_title'
                    extended_title.value = extended_title.value + ' ' + re.sub(r'\W*', '', str(after_title.raw))
                    extended_title.end = after_title.end
                    extended_title.raw_end = after_title.raw_end
                    matches.append(extended_title)


class AnimeAbsoluteEpisodeNumbers(CustomRule):
    """
    If it's an anime, use absolute episode numbers
    """
    priority = POST_PROCESS

    def when(self, matches, context):
        return matches.tagged('anime') and matches.tagged('weak-duplicate') and matches.named('episode') and \
               matches.named('season')

    def then(self, matches, when_response, context):  # pragma: no cover
        if when_response:
            season = matches.named('season', index=0)
            episode = matches.named('episode', index=0)
            if season.end == episode.start and season.raw.isdigit() and episode.raw.isdigit():
                episode.start = season.start
                episode.value = int(episode.raw)
                matches.remove(season)


class FixSeasonEpisodeDetection(CustomRule):
    """
    Work-around for https://github.com/guessit-io/guessit/issues/295
    """
    priority = POST_PROCESS

    def when(self, matches, context):
        return matches.named('season') and matches.named('video_codec') and not matches.named('episode')

    def then(self, matches, when_response, context):  # pragma: no cover
        if when_response:
            seasons = matches.named('season')
            next_match = matches.next(seasons[-1], index=0)
            # guessit gest confused when the next match is x264 or x265
            if len(seasons) == 2 and next_match.name == 'video_codec' and next_match.value in ('h264', 'h265'):
                episode = seasons[1]
                episode.name = 'episode'


class FixWrongSeasonAndReleaseGroup(CustomRule):
    """
    Work-around for https://github.com/guessit-io/guessit/issues/303
    """
    priority = POST_PROCESS
    problematic_words = {
        'bs666', 'ccs3', 'qqss44',
    }

    def when(self, matches, context):
        return matches.named('season') and matches.named('release_group')

    def then(self, matches, when_response, context):  # pragma: no cover
        if when_response:
            seasons = matches.named('season')
            if len(seasons) == 2:
                last_season = seasons[-1]
                previous_match = matches.previous(last_season, index=-1)
                if previous_match.name == 'release_group':
                    holes = matches.holes(start=previous_match.end, end=last_season.start)
                    if len(holes) == 1:
                        hole = holes[0]
                        correct_release_group = previous_match.value + hole.raw + last_season.raw
                        if correct_release_group.lower() in self.problematic_words:
                            previous_match.value = correct_release_group
                            matches.remove(last_season)


class FixSeasonRangeDetection(CustomRule):
    """
    Work-around for https://github.com/guessit-io/guessit/issues/287
    """
    priority = POST_PROCESS

    def when(self, matches, context):
        return matches.named('season')

    def then(self, matches, when_response, context):  # pragma: no cover
        if when_response:
            seasons = matches.named('season')
            if len(seasons) == 2:
                start_season = seasons[0]
                end_season = seasons[-1]
                if 1 < end_season.value - start_season.value < 30:
                    holes = matches.holes(start=start_season.end, end=end_season.start)
                    if len(holes) == 1:
                        hole = holes[0]
                        if hole.value.lower() in ('-', '-s'):
                            for i in range(start_season.value + 1, end_season.value):
                                new_season = copy.copy(start_season)
                                new_season.value = i
                                matches.append(new_season)


class FixEpisodeRangeDetection(CustomRule):
    """
    Work-around for https://github.com/guessit-io/guessit/issues/287
    """
    priority = POST_PROCESS

    def when(self, matches, context):
        return matches.named('episode')

    def then(self, matches, when_response, context):  # pragma: no cover
        if when_response:
            episodes = matches.named('episode')
            if len(episodes) == 2:
                start_episode = episodes[0]
                end_episode = episodes[-1]
                if 1 < end_episode.value - start_episode.value < 30:
                    holes = matches.holes(start=start_episode.end, end=end_episode.start)
                    if len(holes) == 1:
                        hole = holes[0]
                        if hole.value.lower() in ('-', '-e'):
                            for i in range(start_episode.value + 1, end_episode.value):
                                new_season = copy.copy(start_episode)
                                new_season.value = i
                                matches.append(new_season)


class ReleaseGroupPostProcessor(CustomRule):
    """
    Release Group post processor
    """
    priority = POST_PROCESS
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
        return matches.named('release_group')

    def then(self, matches, when_response, context):  # pragma: no cover
        if when_response:
            match = matches.named('release_group', index=0)
            for regex in self.regexes:
                match.value = regex.sub('', match.value)
                if not match.value:
                    break

            if not match.value:
                matches.remove(match)


def processors():
    """
    Builder for rebulk object.
    :return: Created Rebulk object
    :rtype: Rebulk
    """
    return Rebulk().rules(FixWrongSeasonAndReleaseGroup, FixSeasonEpisodeDetection, FixSeasonRangeDetection,
                          FixEpisodeRangeDetection, AnimeAbsoluteEpisodeNumbers, ExpectedTitlePostProcessor,
                          ExtendedTitlePostProcessor, ReleaseGroupPostProcessor)
