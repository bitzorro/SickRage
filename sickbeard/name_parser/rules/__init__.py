#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Guessit customization
"""
from guessit.api import default_api
from sickbeard.name_parser.rules.properties import additional_format
from sickbeard.name_parser.rules.rules import rules


default_api.rebulk.rebulk(additional_format())
default_api.rebulk.rebulk(rules())
