from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist, FieldError
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import CommandError
from django.test import TestCase
from unittest.mock import MagicMock, patch, ANY
from nsync.sync import SyncRecord, SyncInfo, ExternalSystemHelper, ModelFinder,\
 SyncError, SyncFileAction
from nsync.actions import CreateModelAction, ActionsBuilder, ModelAction, EncodedSyncActions


class TestExternalSystemHelper(TestCase):
    def test_find_raises_error_if_external_system_name_is_blank(self):
        with self.assertRaises(CommandError):
            ExternalSystemHelper.find('')

    def test_find_raises_error_if_external_system_not_found_when_create_disabled(self):
        with self.assertRaises(CommandError):
            ExternalSystemHelper.find('systemName', False)

    @patch('nsync.sync.ExternalSystem')
    def test_find_creates_external_system_if_not_found_and_create_is_true(self, ExternalSystem):
        ExternalSystem.DoesNotExist = Exception
        ExternalSystem.objects.get.side_effect = ExternalSystem.DoesNotExist
        ExternalSystemHelper.find('systemName', True)
        ExternalSystem.objects.create.assert_called_with(name='systemName')

class TestModelFinder(TestCase):
    def test_find_raises_error_if_app_label_is_blank(self):
        with self.assertRaises(CommandError):
            ModelFinder.find('', 'model')

    def test_find_raises_error_if_model_name_is_blank(self):
        with self.assertRaises(CommandError):
            ModelFinder.find('nsync', '')

    def test_it_raises_an_error_if_the_model_cannot_be_found(self):
        with self.assertRaises(LookupError):
            ModelFinder.find('fakeApp', 'missingModel')

    def test_it_returns_the_model_if_found(self):
        from nsync.tests.models import TestPerson
        result = ModelFinder.find('tests', 'TestPerson')
        self.assertEqual(result, TestPerson)


class TestSupportedFileChecker(TestCase):
    def test_csv_file_with_headers_is_valid(self):
        pass

class TestSyncFileAction(TestCase):
    def test_it_raises_error_if_file_unsupported(self):
        with self.assertRaises(SyncError):
            SyncFileAction(ANY, ANY, ANY).sync()

class TestSyncRecord(TestCase):
    def test_sync_record_is_not_externally_mappable_with_falsy_external_key(self):
        self.assertFalse(SyncRecord(None, EncodedSyncActions(), "field", field='').is_externally_mappable())
        self.assertFalse(SyncRecord('', EncodedSyncActions(), "field", field='').is_externally_mappable())
        self.assertFalse(SyncRecord([], EncodedSyncActions(), "field", field='').is_externally_mappable())

    def test_sync_record_raises_error_if_match_field_name_is_none(self):
        with self.assertRaises(ValueError):
            SyncRecord(ANY, EncodedSyncActions(), None)

    def test_sync_record_raises_error_if_match_field_name_is_not_in_fields(self):
        with self.assertRaises(ValueError):
            SyncRecord(ANY, EncodedSyncActions(), "Field")

    def test_not_externally_mappable_if_no_external_key(self):
        self.assertFalse(SyncRecord(None, EncodedSyncActions(), 'field', field='').is_externally_mappable())

class TestSyncInfo(TestCase):
    create_or_update = EncodedSyncActions(True, True, False)
    delete = EncodedSyncActions(False, False, True)

    def test_get_deleted_returns_records_for_deletion(self):
        
        new_record = SyncRecord(None, self.create_or_update, 'field', field='new record')
        removed_record = SyncRecord(None, self.delete, 'field', field='removed record')

        subject = SyncInfo(None, None, [new_record, removed_record])

        self.assertIs(len(subject.get_all_records()), 2)
        self.assertIs(len(subject.get_deleted()), 1)
        self.assertEqual(removed_record, subject.get_deleted()[0])
        
    def test_get_non_deleted_returns_records_for_deletion(self):
        new_record = SyncRecord(None, self.create_or_update, 'field', field='new record')
        removed_record = SyncRecord(None, self.delete, 'field', field='removed record')
        
        subject = SyncInfo(None, None, [new_record, removed_record])

        self.assertIs(len(subject.get_all_records()), 2)
        self.assertIs(len(subject.get_non_deleted()), 1)
        self.assertEqual(new_record, subject.get_non_deleted()[0])

