from hashlib import sha256
from os import mkdir, remove
from os.path import exists, join
from shutil import rmtree
from typing import Dict, Union, List, Optional

import genanki
import requests

from cardbuilder.resolution.card_data import CardData
from cardbuilder.resolution.resolver import Resolver
from cardbuilder.common.fieldnames import Fieldname
from cardbuilder.lookup.value import ListConvertibleValue, Value, StringValue
from cardbuilder.exceptions import CardBuilderException


class AkpgResolver(Resolver):

    media_temp_directory = 'ankitemp'

    @staticmethod
    def media_download_postprocessor(value: Union[Value, str]) -> str:
        # Anki only supports one media value per field
        if isinstance(value, StringValue):
            value = value.val
        if isinstance(value, ListConvertibleValue):
            value = value.to_list()[0]
        elif not isinstance(value, str):
            raise CardBuilderException('Anki media postprocessing input value must be '
                                       'either StringValue, ListConvertibleValue or str')

        filename = value.split('/')[-1]
        if not exists(AkpgResolver.media_temp_directory):
            mkdir(AkpgResolver.media_temp_directory)

        r = requests.get(value)
        with open(join(AkpgResolver.media_temp_directory, filename), 'wb') as f:
            f.write(r.content)

        return filename

    @staticmethod
    def linebreak_postprocessing(value: Union[Value, str]) -> str:
        if isinstance(value, Value):
            return value.to_output_string().replace('\n', '<br/>')
        elif isinstance(value, str):
            return value.replace('\n', '<br/>')
        else:
            raise CardBuilderException('Anki linebreak postprocessing input value must be either Value or str')

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
            fields = (rf.value if rf.source_name != Fieldname.AUDIO else '[sound:{}]'.format(rf.value)
                      for rf in row.fields)
            fields = [x if len(x) > 0 else ' ' for x in fields]  # Anki sometimes doesn't like empty fields
            deck.add_note(genanki.Note(model=model, fields=fields))

        package = genanki.Package(deck)
        if next((rf for rf in sample_row.fields if rf.source_name == Fieldname.AUDIO), None) is not None:
            if not exists(self.media_temp_directory):
                raise CardBuilderException('Field with audio source found but no temporary media directory found')

            package.media_files = [join(self.media_temp_directory, next(rf for rf in row.fields
                                                                        if rf.source_name == Fieldname.AUDIO).value)
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
