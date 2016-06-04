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
            title = matches.tagged('expected', 0)
            if title.value not in context.get('expected_title'):
                # TODO: improve this
                title.value = title.value.replace('.', ' ')


class ExtendedTitlePostProcessor(CustomRule):
    """
    ExtendedTitle post processor to add country or year to the existing title
    """
    priority = POST_PROCESS

    def when(self, matches, context):
        return (matches.named('country') or matches.named('year')) and \
               (matches.named('title') or matches.named('film_title')) and \
               (matches.tagged('SxxExx'))

    def then(self, matches, when_response, context):  # pragma: no cover
        if when_response:
            extended_title = matches.named('film_title', 0) or matches.named('title', 0)
            episode = matches.tagged('SxxExx', 0)
            for key in ['country', 'year']:
                key_match = matches.named(key, 0)
                if not key_match or extended_title.end != key_match.start:
                    continue
                delta = episode.start - key_match.end
                if 0 <= delta <= 3:
                    extended_title = copy.copy(extended_title)
                    extended_title.name = 'extended_title'
                    extended_title.value = extended_title.value + ' ' + re.sub(r'\W*', '', str(key_match.raw))
                    extended_title.end = key_match.end
                    extended_title.raw_end = key_match.raw_end
                    matches.append(extended_title)
                    break


class ReleaseGroupPostProcessor(CustomRule):
    """
    Release Group post processor
    """
    priority = POST_PROCESS
    regexes = [
        # [word], (word), {word}
        re.compile(r'\W*[\[\(\{].+[\}\)\]]\W*$', flags=re.IGNORECASE),

        # 200MB, 1GB
        re.compile(r'(\W*\d+[mg]b\b\W*)', flags=re.IGNORECASE),

        # vol255+101
        re.compile(r'\.vol\d+\+\d+', flags=re.IGNORECASE),

        # ReEnc, Re-Enc
        re.compile(r'\W*\bre\-?enc\b\W*', flags=re.IGNORECASE),

        # word.rar, word.gz
        re.compile(r'\.((rar)|(gz)|(\d+))$', flags=re.IGNORECASE),

        # WORD.rartv, WORD.ettv
        re.compile(r'(?<=[A-Z0-9]{3})\.([a-z]+)$', flags=re.IGNORECASE),

        # NLSubs-word
        re.compile(r'\W*\b([A-Z]{2})(subs)\b\W*', flags=re.IGNORECASE),

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
            match = matches.named('release_group', 0)
            # TODO: use rebulk? make it nicer
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
    return Rebulk().rules(ExpectedTitlePostProcessor, ExtendedTitlePostProcessor, ReleaseGroupPostProcessor)
