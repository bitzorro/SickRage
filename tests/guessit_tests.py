# coding=utf-8
"""
Guessit name parser tests
"""
import os
import sys

sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '../lib')))
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
import yaml

from guessit.yamlutils import OrderedDictYAMLLoader
from nose_parameterized import parameterized
from sickbeard.name_parser.guessit_parser import parser


current_folder = os.path.dirname(os.path.realpath(__file__))


class GuessitTests(unittest.TestCase):
    """
    Guessit Tests :-)
    """
    files = {
        'tvshows': 'tvshows.yml',
    }

    parameters = []
    for scenario_name, file_name in files.iteritems():
        with open(os.path.join(current_folder, 'datasets', file_name), 'r') as stream:
            data = yaml.load(stream, OrderedDictYAMLLoader)

        for release_name, expected in data.iteritems():
            expected = {k: v for k, v in expected.iteritems()}
            parameters.append([scenario_name, release_name, expected])

    @parameterized.expand(parameters)
    def test_guess(self, scenario_name, release_name, expected):
        actual = parser.guess(release_name)
        actual = {k: v for k, v in actual.iteritems()}
        if 'country' in actual:
            actual['country'] = str(actual['country'])
        expected['release_name'] = release_name
        actual['release_name'] = release_name
        print('Testing {scenario_name}: {release_name}'.format(scenario_name=scenario_name, release_name=release_name))
        self.assertEqual(expected, actual)

    # for debugging purposes
    def dump(self, scenario_name, release_name, values):
        print('')
        print('# {scenario_name}'.format(scenario_name=scenario_name))
        print('? {release_name}'.format(release_name=release_name))
        start = ':'
        for k, v in values.iteritems():
            print('{start} {k}: {v}'.format(start=start, k=k, v=v))
            start = ' '
