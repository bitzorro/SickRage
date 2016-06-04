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


class ReleaseGroupPostProcessor(CustomRule):
    """
    Release Group post processor
    """
    priority = POST_PROCESS
    regexes = [
        # [word], (word), {word}
        re.compile(r'\W*[\[\(\{].+[\}\)\]]\W*$', flags=re.IGNORECASE),

        # 200MB, 1GB
        re.compile(r'(\W*\b\d+[mg]b\b\W*)', flags=re.IGNORECASE),

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
    return Rebulk().rules(ExpectedTitlePostProcessor, ExtendedTitlePostProcessor, ReleaseGroupPostProcessor)
