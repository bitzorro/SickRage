# coding=utf-8
"""
Guessit name parser tests
"""
import os
import sys

__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

sys.path.insert(1, os.path.realpath(os.path.join(__location__, '../lib')))
sys.path.insert(1, os.path.realpath(os.path.join(__location__, '..')))

import unittest
import yaml

from guessit.yamlutils import OrderedDictYAMLLoader
from nose_parameterized import parameterized
from sickbeard.name_parser.guessit_parser import parser


class GuessitTests(unittest.TestCase):
    """
    Guessit Tests :-)
    """
    files = {
        'tvshows': 'tvshows.yml',
    }

    parameters = []
    for scenario_name, file_name in files.iteritems():
        with open(os.path.join(__location__, 'datasets', file_name), 'r') as stream:
            data = yaml.load(stream, OrderedDictYAMLLoader)

        for release_name, expected in data.iteritems():
            expected = {k: v for k, v in expected.iteritems()}
            parameters.append([scenario_name, release_name, expected])

    @parameterized.expand(parameters)
    def test_guess(self, scenario_name, release_name, expected):
        """
        :param scenario_name:
        :type scenario_name: str
        :param release_name: the input release name
        :type release_name: str
        :param expected: the expected guessed dict
        :type expected: dict
        """
        actual = parser.guess(release_name)
        actual = {k: v for k, v in actual.iteritems()}
        if 'country' in actual:
            actual['country'] = str(actual['country'])
        expected['release_name'] = release_name
        actual['release_name'] = release_name
        print('Testing {scenario_name}: {release_name}'.format(scenario_name=scenario_name, release_name=release_name))
        self.assertEqual(expected, actual)

    # for debugging purposes
    #def dump(self, scenario_name, release_name, values):
    #    print('')
    #    print('# {scenario_name}'.format(scenario_name=scenario_name))
    #    print('? {release_name}'.format(release_name=release_name))
    #    start = ':'
    #    for k, v in values.iteritems():
    #        print('{start} {k}: {v}'.format(start=start, k=k, v=v))
    #        start = ' '
