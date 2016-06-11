# coding=utf-8
"""
Guessit name parser tests
"""
import os
import unittest
import yaml

from guessit.yamlutils import OrderedDictYAMLLoader
from nose_parameterized import parameterized
from sickbeard.name_parser.guessit_parser import parser


__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))


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
        options = expected.pop('options', {})
        actual = parser.guess(release_name, show_type=options.get('show_type'))
        actual = {k: v for k, v in actual.iteritems()}

        def format(param):
            if isinstance(param, list):
                result = []
                for p in param:
                    result.append(str(p))
                return result

            return str(param)

        if 'country' in actual:
            actual['country'] = format(actual['country'])
        if 'language' in actual:
            actual['language'] = format(actual['language'])
        if 'subtitle_language' in actual:
            actual['subtitle_language'] = format(actual['subtitle_language'])

        expected['release_name'] = release_name
        actual['release_name'] = release_name

        if expected.get('disabled'):
            print('Skipping {scenario}: {release_name}'.format(scenario=scenario_name, release_name=release_name))
        else:
            print('Testing {scenario}: {release_name}'.format(scenario=scenario_name, release_name=release_name))
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
