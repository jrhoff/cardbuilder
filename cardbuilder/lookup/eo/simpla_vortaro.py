from typing import Dict

import requests

from cardbuilder.input.word import Word
from cardbuilder.lookup.data_source import WebApiDataSource, AggregatingDataSource
from cardbuilder.lookup.lookup_data import LookupData
from cardbuilder.lookup.value import Value

simpla_vortaro_url = 'http://www.simplavortaro.org'

#TODO: finish this class, then write tests
class SimplaVortaro(AggregatingDataSource):
    def lookup_word(self, word: Word, form: str) -> LookupData:
        pass

    def __init__(self):
        self.definition_lookup = SimplaVortaroDefinition()
        self.meta_lookup = SimplaVortaroMeta()


class SimplaVortaroMeta(WebApiDataSource):
    def _query_api(self, word: str) -> str:
        url = simpla_vortaro_url + '/api/v1/trovi/{}'.format(word)
        return requests.get(url).text

    def parse_word_content(self, word: Word, form: str, content: str) -> LookupData:
        pass


class SimplaVortaroDefinition(WebApiDataSource):
    def _query_api(self, word: str) -> str:
        url = simpla_vortaro_url + '/api/v1/vorto/{}'.format(word)
        return requests.get(url).text

    def parse_word_content(self, word: Word, form: str, content: str) -> LookupData:
        pass