#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Guessit Name Parser
"""
import guessit

from guessit.api import default_api
from sickbeard.name_parser.rules.rules import rules


class GuessitNameParser(object):
    """
    Guessit Name Parser
    """

    expected_titles = {
        # guessit doesn't add dots for this show
        '11.22.63',

        # guessit gets confused because of the numbers (only in some special cases)
        # (?<![^/\\]) means -> it matches nothing but path separators  (negative lookbehind)
        r're:(?<![^/\\])12 Monkeys\b',
        r're:(?<![^/\\])60 Minutes\b',
        r're:(?<![^/\\])Star Trek DS9\b',
        r're:(?<![^/\\])The 100\b',

        # https://github.com/guessit-io/guessit/issues/298
        # guessit identifies as website
        r're:(?<![^/\\])\w+ Net\b',

        # guessit confuses Pan with language Panjabi
        r're:\bPan de Peace\b!',

        # guessit gives: "subtitle_language": "Oromo"  and it skips the title
        r're:(?<![^/\\])Storm Chasers\b',
    }

    # release group exception list
    expected_groups = {
        # https://github.com/guessit-io/guessit/issues/297
        # guessit blacklists parts of the name for the following groups
        r're:\bbyEMP\b',
        r're:\bELITETORRENT\b',
        r're:\bF4ST3R\b',
        r're:\bF4ST\b',
        r're:\bJIVE\b',
        r're:\bNovaRip\b',
        r're:\bPARTiCLE\b',
        r're:\bPOURMOi\b',
        r're:\bRipPourBox\b',
        r're:\bRiPRG\b',
        r're:\bTV2LAX9\b',

        # https://github.com/guessit-io/guessit/issues/296
        # guessit uses these endings as safe sub-domains
        r're:\bAF$',
        r're:\bAR$',
        r're:\bCS$',
        r're:\bDR$',
        r're:\bMC$',
        r're:\bNA$',
        r're:\bNL$',
        r're:\bTL$',
        r're:\bYT$',
        r're:\bZT$',

        # in conjunction with rule: SpanishNewpctReleaseName
        r're:\bNEWPCT\b',
    }

    def guess(self, name, show_type=None):
        """
        Given a release name, it guesses the episode information

        :param name: the release name
        :type name: str
        :param show_type: None, regular or anime
        :type show_type: str
        :return: the guessed properties
        :rtype: dict
        """
        options = dict(type='episode', implicit=True, expected_title=self.expected_titles, show_type=show_type,
                       expected_group=self.expected_groups, episode_prefer_number=show_type == 'anime')
        return guessit.guessit(name, options=options)

    def parse(self, name, show_type=None):
        """
        Same as self.guess(..) method but returns a dictionary with keys and values according to ParseResult
        :param name:
        :param show_type:
        :return:
        """
        guess = self.guess(name, show_type=show_type)

        result = {
            'original_name': name,
            'series_name': guess.get('extended_title') or guess.get('title'),
            'season_number': guess.get('season'),
            'release_group': guess.get('release_group'),
            'air_date': guess.get('date'),
            'version': guess.get('version', -1),
            'extra_info': ' '.join(ensure_list(guess.get('other'))) if guess.get('other') else None,
            'episode_numbers': ensure_list(guess.get('episode')),
            'ab_episode_numbers': ensure_list(guess.get('absolute_episode'))
        }

        return result


def ensure_list(value):
    return sorted(value) if isinstance(value, list) else [value] if value is not None else []


default_api.rebulk.rebulk(rules())
parser = GuessitNameParser()
