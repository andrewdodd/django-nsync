import re
import tempfile
from unittest.mock import MagicMock, patch

from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from nsync.management.commands.syncfiles import TestableCommand, \
    TargetExtractor, DEFAULT_FILE_REGEX
from nsync.models import ExternalKeyMapping, ExternalSystem

from tests.models import TestHouse


class TestIntegrations(TestCase):
    def setUp(self):
        self.external_system = ExternalSystem.objects.create(name='System')

    def test_forced_update_changes_match_fields_if_external_mapping_already_exists(self):
        # Setup the objects
        csv_file_obj = tempfile.NamedTemporaryFile(
            mode='w', prefix='TestSystem_tests_TestHouse_', suffix='.csv')
        csv_file_obj.writelines([
            'external_key,action_flags,match_on,address,country\n',
            'ExternalId1,c,address,House1,Australia\n',  # Will create the house
        ])
        csv_file_obj.seek(0)

        call_command('syncfiles', csv_file_obj.name)

        # Validate the objects
        self.assertEqual(1, TestHouse.objects.count())
        self.assertEqual(1, ExternalKeyMapping.objects.count())
        house = TestHouse.objects.first()
        mapping = ExternalKeyMapping.objects.first()
        self.assertEqual(house, mapping.content_object) 
        self.assertEqual(house.address, 'House1')
        self.assertEqual(house.country, 'Australia')

        # Build the forced update
        csv_file_obj = tempfile.NamedTemporaryFile(
            mode='w', prefix='TestSystem_tests_TestHouse_', suffix='.csv')
        csv_file_obj.writelines([
            'external_key,action_flags,match_on,address,country\n',
            'ExternalId1,u*,address,A new address,A different country\n',  # Will update the house
        ])
        csv_file_obj.seek(0)

        call_command('syncfiles', csv_file_obj.name)

        # Validate the objects
        mapping.refresh_from_db()
        house.refresh_from_db()

        self.assertEqual(mapping, ExternalKeyMapping.objects.first())
        self.assertEqual(1, TestHouse.objects.count())
        self.assertEqual(1, ExternalKeyMapping.objects.count())
        self.assertEqual(house, mapping.content_object) 
        self.assertEqual(house.address, 'A new address')
        self.assertEqual(house.country, 'A different country')

    def test_multiple_match_fields_select_correct_object(self):
        house1 = TestHouse.objects.create(address='BigHouse',   country='BigCountry')
        house2 = TestHouse.objects.create(address='SmallHouse', country='BigCountry')
        house3 = TestHouse.objects.create(address='BigHouse',   country='SmallCountry')
        house4 = TestHouse.objects.create(address='SmallHouse', country='SmallCountry')

        csv_file_obj = tempfile.NamedTemporaryFile(mode='w')
        csv_file_obj.writelines([
            'action_flags,match_on,address,country,floors\n',
            'cu*,address country,BigHouse,BigCountry,1\n',
            'cu*,address country,SmallHouse,BigCountry,2\n',
            'cu*,address country,BigHouse,SmallCountry,3\n',
            'cu*,address country,SmallHouse,SmallCountry,4\n',
        ])
        csv_file_obj.seek(0)

        call_command('syncfile', 'TestSystem', 'tests', 'TestHouse',
                     csv_file_obj.name)

        for object in [house1, house2, house3, house4]:
            object.refresh_from_db()

        self.assertEqual(1, house1.floors)
        self.assertEqual(2, house2.floors)
        self.assertEqual(3, house3.floors)
        self.assertEqual(4, house4.floors)

    def test_ORd_match_fields_select_correct_object(self):
        house1 = TestHouse.objects.create(address='OnlyAddress')
        house2 = TestHouse.objects.create(country='OnlyCountry')
        house3 = TestHouse.objects.create(address='BothAddress',   country='BothCountry')

        csv_file_obj = tempfile.NamedTemporaryFile(mode='w')
        csv_file_obj.writelines([
            'action_flags,match_on,address,country,floors\n',
            'cu*,address country |,OnlyAddress,,1\n',
            'cu*,address country |,,OnlyCountry,2\n',
            'cu*,address country |,BothAddress,BothCountry,3\n',
        ])
        csv_file_obj.seek(0)

        call_command('syncfile', 'TestSystem', 'tests', 'TestHouse',
                     csv_file_obj.name)

        for object in [house1, house2, house3]:
            object.refresh_from_db()

        self.assertEqual(1, house1.floors)
        self.assertEqual(2, house2.floors)
        self.assertEqual(3, house3.floors)

