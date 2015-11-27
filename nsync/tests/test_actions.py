from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist, FieldError
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import CommandError
from django.test import TestCase
from unittest.mock import MagicMock, patch, ANY
from nsync.sync import SyncRecord, EncodedSyncActions, SyncInfo, ExternalSystemHelper, ModelFinder,\
 SyncError, SyncFileAction, ActionsBuilder, ModelAction
from nsync.sync import CreateModelAction

class TestModelAction(TestCase):
    def test_creating_without_a_model_raises_error(self):
        with self.assertRaises(ValueError):
            ModelAction(None, None)

    # TODO - Perhaps update this to look for the attribute on the class?
    def test_it_raises_an_error_if_matchfieldname_is_blank_even_if_blank_is_a_field_key(self):
        with self.assertRaises(ValueError):
            ModelAction(ANY, '', {'':'value'})
            
    def test_creating_with_matchfieldname_not_in_fields_raises_error(self):
        with self.assertRaises(ValueError):
            ModelAction(ANY, 'matchfield', {'otherField':'value'})
            
    def test_it_attempts_to_find_through_the_provided_model_class(self):
        model = MagicMock()
        found_object = ModelAction(model, 'matchfield', {'matchfield':'value'}).find_objects()
        model.objects.filter.assert_called_once_with(matchfield='value')
        self.assertEqual(found_object, model.objects.filter.return_value)
            

class TestActionsBuilder(TestCase):
    def setUp(self):
        self.model = MagicMock()
        self.sut = ActionsBuilder(self.model)

        self.dict_with_defaults = {
                'action_flags': EncodedSyncActions().encode(),
                'match_field_name': 'field1',
                'field1': ''}

    def test_returns_an_empty_list_if_no_actions_in_input(self):
        self.assertEqual([], self.sut.from_dict(None))

    def test_it_raises_an_error_if_the_action_flag_key_is_not_in_values(self):
        with self.assertRaises(KeyError):
            self.sut.from_dict({'not_matched':'value'})

    def test_it_raises_an_error_if_the_match_field_key_is_not_in_values(self):
        with self.assertRaises(KeyError):
            self.sut.from_dict({'action_flags':''})

    def xtest_it_can_be_constructed_with_a_different_action_flag_key(self):
        pass # feature creep, not needed now

    def test_it_looks_for_external_key(self):
        pass # perhaps return to this?

    @patch('nsync.sync.ModelAction')
    def test_it_creates_a_base_model_action_if_no_action_flags_are_included(self, ModelAction):
        result = self.sut.from_dict(self.dict_with_defaults)
        ModelAction.assert_called_with(self.model, 'field1', {'field1': ''})
        self.assertIn(ModelAction.return_value, result)

    @patch('nsync.sync.DeleteModelAction')
    @patch('nsync.sync.UpdateModelAction')
    @patch('nsync.sync.CreateModelAction')
    def test_it_calls_the_correct_action_class_for_each_type(self, CreateModelAction, UpdateModelAction, DeleteModelAction):
        def assert_for_target_class(TargetActionClass):
            TargetActionClass.assert_called_with(self.model, 'field1', {'field1': ''})
            self.assertIn(TargetActionClass.return_value, result)

        test_inputs = [
                (EncodedSyncActions(create=True).encode(), CreateModelAction),
                (EncodedSyncActions(update=True).encode(), UpdateModelAction),
                (EncodedSyncActions(delete=True).encode(), DeleteModelAction)]

        for test_input in test_inputs:
            input_values = dict(self.dict_with_defaults)
            input_values['action_flags']= test_input[0]
            result = self.sut.from_dict(input_values)
            assert_for_target_class(test_input[1])

    def test_it_creates_two_actions_if_create_and_update_action_flags_are_included(self):
        self.dict_with_defaults['action_flags'] = EncodedSyncActions(create=True, update=True).encode()
        result = self.sut.from_dict(self.dict_with_defaults)
        self.assertEqual(2, len(result))


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

class TestEncodedSyncActions(TestCase):
    def test_sync_actions_raises_error_if_action_includes_create_and_delete(self):
        with self.assertRaises(ValueError):
            EncodedSyncActions(create=True, delete=True)

    def test_sync_actions_raises_error_if_action_includes_update_and_delete(self):
        with self.assertRaises(ValueError):
            EncodedSyncActions(update=True, delete=True)

    def test_it_encodes_as_expected(self):
        self.assertEqual('c', EncodedSyncActions(create=True).encode())
        self.assertEqual('u', EncodedSyncActions(update=True).encode())
        self.assertEqual('u*', EncodedSyncActions(update=True, force=True).encode())
        self.assertEqual('d', EncodedSyncActions(delete=True).encode())
        self.assertEqual('d*', EncodedSyncActions(delete=True, force=True).encode())

    def test_it_is_case_insensitive_when_decoding(self):
        self.assertTrue(EncodedSyncActions.decode('c').create)
        self.assertTrue(EncodedSyncActions.decode('C').create)
        self.assertTrue(EncodedSyncActions.decode('u').update)
        self.assertTrue(EncodedSyncActions.decode('U').update)
        self.assertTrue(EncodedSyncActions.decode('d').delete)
        self.assertTrue(EncodedSyncActions.decode('D').delete)

    def test_parse_actions_returns_impotent_object_if_no_actions_provided(self):
        pass #self.assertTrue(EncodedSyncActions.parse_actions('').is_impotent())

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

