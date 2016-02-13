import tempfile
from unittest.mock import MagicMock, patch

from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from nsync.management.commands.syncfile import SyncFileAction
from nsync.models import ExternalKeyMapping, ExternalSystem

from tests.models import TestHouse


class TestSyncFileCommand(TestCase):
    def test_command_raises_error_if_file_does_not_exist(self):
        with self.assertRaises(CommandError):
            call_command('syncfile', 'systemName', 'tests', 'TestPerson',
                         'file')


class TestSyncFileAction(TestCase):
    @patch('nsync.management.commands.syncfile.CsvActionFactory')
    @patch('csv.DictReader')
    def test_data_flow(self, DictReader, CsvActionFactory):
        file = MagicMock()
        row = MagicMock()
        row_provider = MagicMock()
        DictReader.return_value = row_provider
        row_provider.__iter__.return_value = [row]
        model_mock = MagicMock()
        external_system_mock = MagicMock()
        action_mock = MagicMock()
        CsvActionFactory.return_value.from_dict.return_value = [action_mock]
        SyncFileAction.sync(external_system_mock, model_mock, file, False)
        DictReader.assert_called_with(file)
        CsvActionFactory.assert_called_with(model_mock, external_system_mock)

        CsvActionFactory.return_value.from_dict.assert_called_with(row)
        action_mock.execute.assert_called_once_with()

    @patch('nsync.management.commands.syncfile.TransactionSyncPolicy')
    @patch('nsync.management.commands.syncfile.BasicSyncPolicy')
    @patch('nsync.management.commands.syncfile.CsvActionFactory')
    def test_it_wraps_the_basic_policy_in_a_transaction_policy_if_configured(
            self, CsvActionFactory,
            BasicSyncPolicy, TransactionSyncPolicy):
        SyncFileAction.sync(MagicMock(), MagicMock(), MagicMock(), True)
        TransactionSyncPolicy.assert_called_with(BasicSyncPolicy.return_value)
        TransactionSyncPolicy.return_value.execute.assert_called_once_with()


class TestSyncSingleFileIntegrationTests(TestCase):
    def test_create_and_update(self):
        house1 = TestHouse.objects.create(address='House1')
        house2 = TestHouse.objects.create(address='House2')
        house3 = TestHouse.objects.create(address='House3', country='Belgium')
        house4 = TestHouse.objects.create(address='House4', country='Belgium')

        csv_file_obj = tempfile.NamedTemporaryFile(mode='w')
        csv_file_obj.writelines([
            'action_flags,match_on,address,country\n',
            'c,address,House1,Australia\n',  # Should have no effect
            'u,address,House2,Australia\n',  # Should update country
            'u,address,House3,Australia\n',  # Should have no effect
            'u*,address,House4,Australia\n',  # Should update country
            'c,address,House5,Australia\n',  # Should create new house
        ])
        csv_file_obj.seek(0)

        call_command('syncfile', 'TestSystem', 'tests', 'TestHouse',
                     csv_file_obj.name)

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

        csv_file_obj = tempfile.NamedTemporaryFile(mode='w')
        csv_file_obj.writelines([
            'action_flags,match_on,address,country\n',
            'd,address,House1,Australia\n',  # Should have no effect
            'd*,address,House2,Australia\n',  # Should delete
        ])
        csv_file_obj.seek(0)

        call_command('syncfile', 'TestSystem', 'tests', 'TestHouse',
                     csv_file_obj.name)

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

        csv_file_obj = tempfile.NamedTemporaryFile(mode='w')
        csv_file_obj.writelines([
            'external_key,action_flags,match_on,address\n',
            'House1Key,c,address,House1\n',  # Should create a key mapping
            'House2Key,u,address,House2\n',  # Should update existing mapping
            'House3Key,c,address,House3\n',
            # Should create new house and mapping
        ])
        csv_file_obj.seek(0)

        call_command('syncfile', 'TestSystem', 'tests', 'TestHouse',
                     csv_file_obj.name)

        for object in [house1, house2, house2mapping]:
            object.refresh_from_db()

        self.assertEqual(3, ExternalKeyMapping.objects.count())
        self.assertEqual(house2mapping.object_id, house2.id)

    def test_delete_with_external_refs(self):
        TestHouse.objects.create(address='House1')
        house2 = TestHouse.objects.create(address='House2')
        house3 = TestHouse.objects.create(address='House3')
        house4 = TestHouse.objects.create(address='House4')

        external_system = ExternalSystem.objects.create(
            name='TestSystem', description='TestSystem')
        different_external_system = ExternalSystem.objects.create(
            name='DifferentSystem', description='DifferentSystem')

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

        csv_file_obj = tempfile.NamedTemporaryFile(mode='w')
        csv_file_obj.writelines([
            'external_key,action_flags,match_on,address\n',
            'House1Key,d,address,House1\n',
            # Should do nothing, as this does not have the final mapping
            'House2Key,d,address,House2\n',
            # Should delete, as this IS the final mapping
            'House3Key,d,address,House3\n',
            # Should do nothing, as there is another mapping
            'House4Key,d*,address,House4\n',
            # Should delete object but leave mapping, as it is forced
        ])
        csv_file_obj.seek(0)

        call_command('syncfile', 'TestSystem', 'tests', 'TestHouse',
                     csv_file_obj.name)

        self.assertTrue(TestHouse.objects.filter(address='House1').exists())
        self.assertFalse(TestHouse.objects.filter(address='House2').exists())
        self.assertTrue(TestHouse.objects.filter(address='House3').exists())
        self.assertFalse(TestHouse.objects.filter(address='House4').exists())

        self.assertFalse(ExternalKeyMapping.objects.filter(
            external_key='House1Key').exists())
        self.assertFalse(ExternalKeyMapping.objects.filter(
            external_key='House2Key').exists())
        self.assertTrue(ExternalKeyMapping.objects.filter(
            external_key='House3Key').exists())
        self.assertTrue(ExternalKeyMapping.objects.filter(
            external_key='House4Key').exists())
