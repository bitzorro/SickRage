#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Properties: This section contains additional properties to be guessed by guessit
"""

import re

from guessit.rules.common import dash
from rebulk.processors import POST_PROCESS
from rebulk.rebulk import Rebulk
from rebulk.rules import Rule, RemoveMatch


def additional_format():
    """
    Guessit issue: https://github.com/guessit-io/guessit/issues/307
    TODO: Remove it when fixed.

    Additional WEBDLRip
    :return:
    """
    rebulk = Rebulk().regex_defaults(flags=re.IGNORECASE, abbreviations=[dash])
    rebulk.defaults(name='format')
    rebulk.regex('HDTV-?Mux', value='HDTV')
    rebulk.regex('B[RD]-?Mux', 'Blu-?ray-?Mux', value='BluRay')
    rebulk.regex('DVD-?Mux', value='DVD')
    rebulk.regex('WEB-?Mux', 'DL-?WEB-?Mux', 'WEB-?DL-?Mux', 'DL-?Mux', value='WEB-DL')
    rebulk.regex('WEB-?DL-?Rip', value='WEBRip')
    rebulk.regex('WEB-?Cap', value='WEBCap')
    rebulk.regex('DSR', 'DS-?Rip', 'SAT-?Rip', 'DTH-?Rip', value='DSRip')
    rebulk.regex('LDTV', value='TV')
    rebulk.regex('DVD-?2', value='DVD')

    return rebulk
