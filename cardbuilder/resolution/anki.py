from os import mkdir, remove
from os.path import exists, join
from shutil import rmtree
from typing import Dict, List, Optional
import re

import genanki
import requests

from cardbuilder.lookup.value import SingleValue, Value, MultiListValue, MultiValue
from cardbuilder.resolution.card_data import CardData
from cardbuilder.resolution.printer import Printer
from cardbuilder.resolution.resolver import Resolver
from cardbuilder.common.fieldnames import Fieldname
from cardbuilder.exceptions import CardBuilderException

anki_audio_field_regex = re.compile(r'\[sound:.+\]')


class AnkiAudioDownloadPrinter(Printer):

    def __call__(self, value: Value) -> str:
        if isinstance(value, SingleValue):
            url = value.get_data()
        elif isinstance(value, MultiValue):
            url = value.get_data()[0][0].get_data()
        else:
            raise CardBuilderException('{} can only print SingleValues or MultiValues'.format(
                AnkiAudioDownloadPrinter.__name__))

        filename = url.split('/')[-1]
        if not exists(AkpgResolver.media_temp_directory):
            mkdir(AkpgResolver.media_temp_directory)

        r = requests.get(url)
        with open(join(AkpgResolver.media_temp_directory, filename), 'wb') as f:
            f.write(r.content)

        return '[sound:{}]'.format(filename)


class AkpgResolver(Resolver):

    media_temp_directory = 'ankitemp'
    linebreak = '<br/>'

    default_templates = [{
                              'name': 'Dummy Card',
                              'qfmt': 'This is a dummy card. Please update card types associated with this note.',
                              'afmt': 'This is a dummy card. Please update card types associated with this note.',
                          }]

    @staticmethod
    def _str_to_id(s: str) -> int:
        # determnistic hash between 1 << 30 and 1 << 31
        range_floor = 1 << 30
        range_ceil = 1 << 31
        return (abs(hash(s)) % (range_ceil - range_floor + 1)) + range_floor

    def set_note_name(self, name: str, templates: Optional[List[Dict[str, str]]], css: str = ''):
        if templates is not None:
            for template in templates:
                for attr in ['name', 'qfmt', 'afmt']:
                    if attr not in template:
                        raise CardBuilderException('Template missing required field {}'.format(attr))
            self.templates = templates
        else:
            self.templates = self.default_templates

        self.css = css
        self.note_name = name

    def _output_file(self, rows: List[CardData], name: str):
        sample_row = rows[0]
        output_filename = name.lower().replace(' ', '_')

        templates = self.templates if hasattr(self, 'templates') else self.default_templates
        css = self.css if hasattr(self, 'css') else ''
        note_name = self.note_name if hasattr(self, 'note_name') else 'cardbuilder default'

        model = genanki.Model(self._str_to_id(note_name), note_name,
                              fields=[
                                  {'name': f.name} for f in sample_row.fields
                              ],
                              templates=templates,
                              css=css)

        deck = genanki.Deck(self._str_to_id(name), name)
        for row in rows:
            fields = [x.value if len(x.value) > 0 else ' ' for x in row.fields]  # Anki sometimes doesn't like empty fields
            deck.add_note(genanki.Note(model=model, fields=fields))

        package = genanki.Package(deck)
        if next((rf for rf in sample_row.fields if rf.source_name == Fieldname.AUDIO), None) is not None:
            if not exists(self.media_temp_directory):
                raise CardBuilderException('Field with audio source found but no temporary media directory found')

            package.media_files = [join(self.media_temp_directory,
                                        next(rf for rf in row.fields
                                             if anki_audio_field_regex.match(rf.value)).value[7:-1])
                                   for row in rows]

            for file in package.media_files:
                if not exists(file):
                    raise CardBuilderException('Supplied Anki media file {} not found'.format(file))

        final_out_name = '{}.apkg'.format(output_filename)
        if exists(output_filename):
            remove(output_filename)
        package.write_to_file(final_out_name)

        # this has to come last because the directory needs to exist when we write out the anki file
        if exists(self.media_temp_directory):
            rmtree(self.media_temp_directory)

        return final_out_name
