#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Properties: This section contains additional properties to be guessed by guessit
"""

import re

from guessit.rules.common import dash
from rebulk.rebulk import Rebulk


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
    rebulk.regex('B[RD]-?Mux', value='BluRay')
    rebulk.regex('DVD-?Mux', value='DVD')
    rebulk.regex('WEB-?Mux', 'DL-?WEB-?Mux', 'WEB-?DL-?Mux', 'DL-?Mux', value='WEB-DL')
    rebulk.regex('WEB-?DL-?Rip', value='WEBRip')

    return rebulk
