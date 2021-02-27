from typing import Dict, Set, Union, List

import requests
from pykakasi import kakasi

from cardbuilder.common.fieldnames import WORD, PART_OF_SPEECH, READING, WRITINGS, DETAILED_READING, DEFINITIONS, \
    RAW_DATA
from cardbuilder.common.util import is_hiragana
from cardbuilder.data_sources import DataSource, Value, StringValue, StringListValue
from cardbuilder import WordLookupException
from cardbuilder.data_sources.value import DefinitionsWithPOSValue


class Jisho(DataSource):

    def __init__(self, accept_reading_match=True, accept_non_match=False):
        self._exact_matched = set()
        self._reading_matched = set()
        self._non_matched = set()
        self.readings = kakasi()
        self.accept_reading_match = accept_reading_match
        self.accept_non_match = accept_non_match

    def _to_katakana_reading(self, word: str) -> str:
        return ''.join(x['kana'] for x in self.readings.convert(word))

    def _readings_in_result(self, jisho_result: Dict) -> Set[str]:
        return {self._to_katakana_reading(x['reading']) for x in jisho_result['japanese'] if 'reading' in x}

    def _to_romaji_reading(self, word: str) -> str:
        return ''.join(x['hepburn'] for x in self.readings.convert(word))

    def _detailed_reading(self, word: str) -> str:
        reading_components = sorted((comp for comp in self.readings.convert(word)),
                                    key=lambda comp: word.index(comp['orig']))

        if ''.join(x['orig'] for x in reading_components) != word:
            raise WordLookupException('Reading component originals did not equal original word for {}'.format(word))

        output_str = ''
        for comp in reading_components:
            if comp['hira'] == comp['orig']:
                # hiragana component
                output_str += comp['hira']
            else:
                okurigana = ''.join(c for c in comp['orig'] if is_hiragana(c))
                if len(okurigana) > 0:
                    ruby = comp['hira'][:-len(okurigana)]
                    kanji = comp['orig'][:-len(okurigana)]
                else:
                    ruby = comp['hira']
                    kanji = comp['orig']

                if len(output_str) > 0:
                    output_str += ' '  # don't let previous okurigana merge with new kanji for reading assignment
                output_str += '{}[{}]{}'.format(kanji, ruby, okurigana)

        return output_str.strip()

    def lookup_word(self, word: str) -> Dict[str, Value]:
        url = 'https://jisho.org/api/v1/search/words?keyword={}'.format(word)
        json = requests.get(url).json()['data']
        match = next((x for x in json if x['slug'] == word), None)
        if match:
            self._exact_matched.add(word)

        reading = self._to_katakana_reading(word)
        if match is None and self.accept_reading_match:
            match = next((x for x in json if reading in self._readings_in_result(x)), None)
            self._reading_matched.add(word)

        if match is None and self.accept_non_match:
            match = next(iter(json))

        if match is None:
            raise WordLookupException('Could not find a match for {} in Jisho'.format(word))

        # delete senses that are just romaji readings
        romaji = self._to_romaji_reading(word)

        definitions_with_pos = [
            (sense['english_definitions'], sense['parts_of_speech'][0] if 'parts_of_speech' in sense else None)
            for sense in match['senses'] if romaji not in {dfn.lower() for dfn in sense['english_definitions']}
        ]

        writing_candidates = list({x['word'] for x in match['japanese'] if 'word' in x})  # set for unique, then list
        detailed_reading = self._detailed_reading(word)

        definitions_value = DefinitionsWithPOSValue(definitions_with_pos)
        return {
            PART_OF_SPEECH: StringValue(definitions_value.definitions_with_pos[0][1]),
            DEFINITIONS: definitions_value,
            READING: StringValue(reading),
            WRITINGS: StringListValue(writing_candidates),
            DETAILED_READING: StringValue(detailed_reading),
            RAW_DATA: match
        }