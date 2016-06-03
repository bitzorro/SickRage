#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Processors
"""
import re
from rebulk.processors import POST_PROCESS
from rebulk.rebulk import Rebulk
from rebulk.rules import CustomRule


class ReleaseGroupPostProcessor(CustomRule):
    """
    Empty rule for ordering post_processing properly.
    """
    priority = POST_PROCESS

    def when(self, matches, context):
        return matches.named('release_group')

    def then(self, matches, when_response, context):  # pragma: no cover
        if when_response:
            match = matches.named('release_group', 0)
            # TODO: use rebulk? make it nicer
            match.value = self.remove_contents_in_groups(match.value)
            match.value = self.remove_media_size(match.value)
            match.value = self.remove_volume_info(match.value)
            match.value = self.remove_reenc(match.value)
            match.value = self.remove_extensions(match.value)
            match.value = self.remove_wrong_suffixes(match.value)
            match.value = self.remove_known_words_word(match.value)
            match.value = self.strip_non_word_at_start_and_end(match.value)
            if not match.value:
                matches.remove(match)

    def remove_contents_in_groups(self, value):
        # [word], (word), {word}
        return re.sub(r'\W*[\[\(\{].+[\}\)\]]\W*$', '', value)

    def remove_media_size(self, value):
        # 200MB, 1GB
        return re.sub(r'(\W*\d+[mg]b\b\W*)', '', value, flags=re.IGNORECASE)

    def remove_volume_info(self, value):
        # vol255+101
        return re.sub(r'\.vol\d+\+\d+', '', value, flags=re.IGNORECASE)

    def remove_reenc(self, value):
        # ReEnc, Re-Enc
        return re.sub(r'\W*\bre\-?enc\b\W*', '', value, flags=re.IGNORECASE)

    def remove_extensions(self, value):
        # word.rar, word.gz
        return re.sub(r'\.(rar)|(gz)$', '', value, flags=re.IGNORECASE)

    def remove_wrong_suffixes(self, value):
        # WORD.rartv, WORD.ettv
        return re.sub(r'(?<=[A-Z0-9]{3})\.([a-z]+)$', '', value)

    def remove_known_words_word(self, value):
        # INTERNAL
        return re.sub(r'\W*\b(INTERNAL)|(Obfuscated)\b\W*', '', value, flags=re.IGNORECASE)

    def strip_non_word_at_start_and_end(self, value):
        # ..word..  ]word.
        value = re.sub(r'^\W+', '', value, flags=re.IGNORECASE)
        return re.sub(r'\W+$', '', value, flags=re.IGNORECASE)

def processors():
    """
    Builder for rebulk object.
    :return: Created Rebulk object
    :rtype: Rebulk
    """
    return Rebulk().rules(ReleaseGroupPostProcessor)
