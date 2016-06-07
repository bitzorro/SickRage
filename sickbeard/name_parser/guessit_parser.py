#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Guessit Name Parser
"""
import guessit

from guessit.api import default_api
from sickbeard.name_parser.rules.rules import rules


class GuessitNameParser(object):

    expected_titles = {
        # guessit doesn't add dots for this show
        '11.22.63',

        # guessit gets confused because of the numbers (only in some special cases)
        r're:^12 Monkeys\b',
        r're:^60 Minutes\b',
        r're:^Star Trek DS9\b',
        r're:^The 100\b',

        # https://github.com/guessit-io/guessit/issues/298
        # guessit identifies as website
        r're:^Dark Net\b',

        # TODO: needs investigation...
        r're:^Storm Chasers\b',
    }

    # release group exception list
    expected_groups = {
        # https://github.com/guessit-io/guessit/issues/297
        # guessit blacklists parts of the name for the following groups
        r're:\bbyEMP\b',
        r're:\bELITETORRENT\b',
        r're:\bF4ST3R\b',
        r're:\bF4ST\b',
        r're:\bGOLF68\b',
        r're:\bJIVE\b',
        r're:\bNF69\b',
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
    }

    def guess(self, name):
        """
        Given a release name, it guesses the episode information

        :param name: the release name
        :type name: str
        :return: the guessed properties
        :rtype: dict
        """
        options = dict(type='episode', implicit=True, expected_title=self.expected_titles,
                       expected_group=self.expected_groups)
        guess = guessit.guessit(name, options=options)

        result = {
            'original_name': name,
            'series_name': guess.get('extended_title'),
            'season_number': guess.get('season'),
            'release_group': guess.get('release_group'),
            'air_date': guess.get('date'),
            'version': guess.get('version'),
            'extra_info': ' '.join(_list(guess.get('other'), default=[])),
            'episode_numbers': _list(guess.get('episode')),
            'ab_episode_numbers': _list(guess.get('absolute_episode'))
        }

        return result


def _list(value, default=None):
    return sorted(value) if isinstance(value, list) else [value] if value is not None else default


default_api.rebulk.rebulk(rules())
parser = GuessitNameParser()
