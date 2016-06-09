# coding=utf-8
"""
Guessit name parser tests
"""
import os
import unittest
import yaml

from nose_parameterized import parameterized
from sickbeard.name_parser.guessit_parser import parser


current_folder = os.path.dirname(os.path.realpath(__file__))


class GuessitTests(unittest.TestCase):
    files = {
        'tvshows': 'tvshows.yml',
    }

    properties = {
        'original_name': None,
        'series_name': None,
        'season_number': None,
        'release_group': None,
        'air_date': None,
        'version': -1,
        'extra_info': None,
        'episode_numbers': [],
        'ab_episode_numbers': [],
    }

    parameters = []
    for scenario_name, file_name in files.iteritems():
        with open(os.path.join(current_folder, 'datasets', file_name), 'r') as stream:
            data = yaml.safe_load(stream)

        for release_name, release_values in data.iteritems():
            expected = dict(properties)
            expected.update(release_values)
            expected['original_name'] = release_name
            parameters.append([scenario_name, release_name, expected])

    @parameterized.expand(parameters)
    def test_guess(self, scenario_name, release_name, expected):
        actual = parser.guess(release_name)
        print('Testing {scenario_name}: {release_name}'.format(scenario_name=scenario_name, release_name=release_name))
        self.assertEqual(expected, actual)
