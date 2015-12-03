import re
import tempfile
from unittest.mock import MagicMock, patch

from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from nsync.models import ExternalKeyMapping, ExternalSystem
from tests.models import TestHouse
from nsync.management.commands.syncfiles import TestableCommand, TargetExtractor, DEFAULT_FILE_REGEX


class TestSyncFilesCommand(TestCase):
    def test_command_raises_error_if_file_list_is_empty(self):
        with self.assertRaises(CommandError):
            call_command('syncfiles')

    def test_command_raises_error_if_regex_does_not_compile(self):
        f = tempfile.NamedTemporaryFile()
        import sre_constants
        with self.assertRaises(sre_constants.error):
            call_command('syncfiles', f.name, file_name_regex='(((')

    def xtest_test(self):
        f1 = tempfile.NamedTemporaryFile(mode='w', prefix='Temp_tests_TestHouse_', suffix='.csv')
        f2 = tempfile.NamedTemporaryFile()
        f3 = tempfile.NamedTemporaryFile()

        call_command('syncfiles', f1.name, f2.name, f3.name)


class TestTestableCommand(TestCase):
    @patch('nsync.management.commands.syncfile.CsvActionsBuilder')
    @patch('csv.DictReader')
    def xtest_data_flow(self, DictReader, ActionsBuilder):
        file = MagicMock()
        row = MagicMock()
        row_provider = MagicMock()
        DictReader.return_value = row_provider
        row_provider.__iter__.return_value = [row]
        model_mock = MagicMock()
        external_system_mock = MagicMock()
        action_mock = MagicMock()
        ActionsBuilder.return_value.from_dict.return_value = [action_mock]
        TestableCommand.sync(external_system_mock, model_mock, file)
        DictReader.assert_called_with(file)
        ActionsBuilder.assert_called_with(model_mock, external_system_mock)

        ActionsBuilder.return_value.from_dict.assert_called_with(row)
        action_mock.execute.assert_called_once_with()


class TestTargetExtractor(TestCase):
    def setUp(self):
        self.sut = TargetExtractor(re.compile(DEFAULT_FILE_REGEX))

    def test_it_extracts_the_correct_strings_from_the_filename(self):
        self.assertEquals(('System', 'App', 'Model'), self.sut.extract('System_App_Model.csv'))
        self.assertEquals(('System', 'App', 'Model'), self.sut.extract('System_App_Model_1234.csv'))
        self.assertEquals(('ABCabc123', 'App', 'Model'), self.sut.extract('ABCabc123_App_Model.csv'))


class TestSyncSingleFileIntegrationTests(TestCase):
    def test_create_and_update(self):
        house1 = TestHouse.objects.create(address='House1')
        house2 = TestHouse.objects.create(address='House2')
        house3 = TestHouse.objects.create(address='House3', country='Belgium')
        house4 = TestHouse.objects.create(address='House4', country='Belgium')

        csv_file_obj = tempfile.NamedTemporaryFile(mode='w', prefix='TestSystem_tests_TestHouse_', suffix='.csv')
        csv_file_obj.writelines([
            'action_flags,match_field_name,address,country\n',
            'c,address,House1,Australia\n',  # Should have no effect
            'u,address,House2,Australia\n',  # Should update country
            'u,address,House3,Australia\n',  # Should have no effect
            'u*,address,House4,Australia\n',  # Should update country
            'c,address,House5,Australia\n',  # Should create new house
        ])
        csv_file_obj.seek(0)

        call_command('syncfiles', csv_file_obj.name)

        for house in [house1, house2, house3, house4]:
            house.refresh_from_db()

        self.assertEqual(5, TestHouse.objects.count())
        self.assertEqual('', house1.country)
        self.assertEqual('Australia', house2.country)
        self.assertEqual('Belgium', house3.country)
        self.assertEqual('Australia', house4.country)
        house5 = TestHouse.objects.get(address='House5')
        self.assertEqual('Australia', house5.country)

    def test_delete(self):
        house1 = TestHouse.objects.create(address='House1')
        house2 = TestHouse.objects.create(address='House2')

        csv_file_obj = tempfile.NamedTemporaryFile(mode='w', prefix='TestSystem_tests_TestHouse_', suffix='.csv')
        csv_file_obj.writelines([
            'action_flags,match_field_name,address,country\n',
            'd,address,House1,Australia\n',  # Should have no effect
            'd*,address,House2,Australia\n',  # Should delete
        ])
        csv_file_obj.seek(0)

        call_command('syncfiles', csv_file_obj.name)

        house1.refresh_from_db()
        self.assertEqual('', house1.country)

        with self.assertRaises(Exception):
            house2.refresh_from_db()

    def test_create_and_update_with_external_refs(self):
        house1 = TestHouse.objects.create(address='House1')
        house2 = TestHouse.objects.create(address='House2')

        external_system = ExternalSystem.objects.create(name='TestSystem')

        house2mapping = ExternalKeyMapping.objects.create(
            content_type=ContentType.objects.get_for_model(TestHouse),
            external_system=external_system,
            external_key='House2Key',
            object_id=0)

        csv_file_obj = tempfile.NamedTemporaryFile(mode='w', prefix='TestSystem_tests_TestHouse_', suffix='.csv')
        csv_file_obj.writelines([
            'external_key,action_flags,match_field_name,address\n',
            'House1Key,c,address,House1\n',  # Should create a key mapping
            'House2Key,u,address,House2\n',  # Should update existing mapping
            'House3Key,c,address,House3\n',  # Should create new house and mapping
        ])
        csv_file_obj.seek(0)

        call_command('syncfiles', csv_file_obj.name)

        for object in [house1, house2, house2mapping]:
            object.refresh_from_db()

        self.assertEqual(3, ExternalKeyMapping.objects.count())
        self.assertEqual(house2mapping.object_id, house2.id)

    def test_delete_with_external_refs(self):
        TestHouse.objects.create(address='House1')
        house2 = TestHouse.objects.create(address='House2')
        house3 = TestHouse.objects.create(address='House3')
        house4 = TestHouse.objects.create(address='House4')

        external_system = ExternalSystem.objects.create(name='TestSystem', description='TestSystem')
        different_external_system = ExternalSystem.objects.create(name='DifferentSystem', description='DifferentSystem')

        ExternalKeyMapping.objects.create(
            content_type=ContentType.objects.get_for_model(TestHouse),
            external_system=external_system,
            external_key='House2Key',
            object_id=house2.id)

        ExternalKeyMapping.objects.create(
            content_type=ContentType.objects.get_for_model(TestHouse),
            external_system=different_external_system,
            external_key='House3Key',
            object_id=house3.id)

        ExternalKeyMapping.objects.create(
            content_type=ContentType.objects.get_for_model(TestHouse),
            external_system=different_external_system,
            external_key='House4Key',
            object_id=house4.id)

        csv_file_obj = tempfile.NamedTemporaryFile(mode='w', prefix='TestSystem_tests_TestHouse_', suffix='.csv')
        csv_file_obj.writelines([
            'external_key,action_flags,match_field_name,address\n',
            'House1Key,d,address,House1\n',  # Should do nothing, as this does not have the final mapping
            'House2Key,d,address,House2\n',  # Should delete, as this IS the final mapping
            'House3Key,d,address,House3\n',  # Should do nothing, as there is another mapping
            'House4Key,d*,address,House4\n',  # Should delete object but leave mapping, as it is forced
        ])
        csv_file_obj.seek(0)

        call_command('syncfiles', csv_file_obj.name)

        self.assertTrue(TestHouse.objects.filter(address='House1').exists())
        self.assertFalse(TestHouse.objects.filter(address='House2').exists())
        self.assertTrue(TestHouse.objects.filter(address='House3').exists())
        self.assertFalse(TestHouse.objects.filter(address='House4').exists())

        self.assertFalse(ExternalKeyMapping.objects.filter(external_key='House1Key').exists())
        self.assertFalse(ExternalKeyMapping.objects.filter(external_key='House2Key').exists())
        self.assertTrue(ExternalKeyMapping.objects.filter(external_key='House3Key').exists())
        self.assertTrue(ExternalKeyMapping.objects.filter(external_key='House4Key').exists())

    def test_it_does_all_creates_before_deletes(self):

        file1 = tempfile.NamedTemporaryFile(mode='w', prefix='TestSystem1_tests_TestHouse_', suffix='.csv')
        file1.writelines([
            'action_flags,match_field_name,address,country\n',
            'd*,address,House1,Australia\n',  # Should delete
        ])
        file1.seek(0)

        file2 = tempfile.NamedTemporaryFile(mode='w', prefix='TestSystem2_tests_TestHouse_', suffix='.csv')
        file2.writelines([
            'action_flags,match_field_name,address,country\n',
            'c,address,House1,Australia\n',  # Should attempt to create, but should be undone by delete above
        ])
        file2.seek(0)
        call_command('syncfiles', file1.name, file2.name)

        self.assertEqual(0, TestHouse.objects.count())
