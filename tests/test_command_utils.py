from unittest.mock import MagicMock, patch

from django.core.management.base import CommandError
from django.test import TestCase
from nsync.actions import SyncActions
from nsync.management.commands.utils import (
    ExternalSystemHelper,
    ModelFinder,
    SupportedFileChecker,
    CsvSyncActionsDecoder,
    CsvSyncActionsEncoder,
    CsvActionFactory)


class TestExternalSystemHelper(TestCase):
    def test_find_raises_error_if_external_system_name_is_blank(self):
        with self.assertRaises(CommandError):
            ExternalSystemHelper.find('')

    def test_find_raises_error_if_external_system_not_found(self):
        with self.assertRaises(CommandError):
            ExternalSystemHelper.find('systemName', False)

    @patch('nsync.management.commands.utils.ExternalSystem')
    def test_find_creates_external_system_if_not_found_and_create_is_true(
            self, ExternalSystem):
        ExternalSystem.DoesNotExist = Exception
        ExternalSystem.objects.get.side_effect = ExternalSystem.DoesNotExist
        ExternalSystemHelper.find('systemName', True)
        ExternalSystem.objects.create.assert_called_with(
            name='systemName', description='systemName')


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
        from tests.models import TestPerson
        result = ModelFinder.find('tests', 'TestPerson')
        self.assertEqual(result, TestPerson)


class TestSupportedFileChecker(TestCase):
    def test_it_thinks_none_file_is_not_valid(self):
        self.assertFalse(SupportedFileChecker.is_valid(None))


class TestCsvSyncActionsEncoder(TestCase):
    def test_it_encodes_as_expected(self):
        self.assertEqual('c', CsvSyncActionsEncoder.encode(
            SyncActions(create=True)))
        self.assertEqual('u', CsvSyncActionsEncoder.encode(
            SyncActions(update=True)))
        self.assertEqual('u*', CsvSyncActionsEncoder.encode(
            SyncActions(update=True, force=True)))
        self.assertEqual('d', CsvSyncActionsEncoder.encode(
            SyncActions(delete=True)))
        self.assertEqual('d*', CsvSyncActionsEncoder.encode(
            SyncActions(delete=True, force=True)))


class TestCsvSyncActionsDecoder(TestCase):
    def test_it_is_case_insensitive_when_decoding(self):
        self.assertTrue(CsvSyncActionsDecoder.decode('c').create)
        self.assertTrue(CsvSyncActionsDecoder.decode('C').create)
        self.assertTrue(CsvSyncActionsDecoder.decode('u').update)
        self.assertTrue(CsvSyncActionsDecoder.decode('U').update)
        self.assertTrue(CsvSyncActionsDecoder.decode('d').delete)
        self.assertTrue(CsvSyncActionsDecoder.decode('D').delete)

    def test_it_produces_object_with_no_actions_if_input_invalid(self):
        result = CsvSyncActionsDecoder.decode(123)
        self.assertFalse(result.create)
        self.assertFalse(result.update)
        self.assertFalse(result.delete)
        self.assertFalse(result.force)


class TestCsvActionFactory(TestCase):
    def setUp(self):
        self.model = MagicMock()
        self.sut = CsvActionFactory(self.model)

    @patch('nsync.management.commands.utils.CsvSyncActionsDecoder')
    def test_from_dict_maps_to_build_correctly(self, ActionDecoder):
        action_flags_mock = MagicMock()
        match_on_mock = MagicMock()
        external_key_mock = MagicMock()

        with patch.object(self.sut, 'build') as build_method:
            result = self.sut.from_dict({
                'action_flags': action_flags_mock,
                'match_on': match_on_mock,
                'external_key': external_key_mock,
                'other_key': 'value'})
            ActionDecoder.decode.assert_called_with(action_flags_mock)
            match_on_mock.split.assert_called_with(
                CsvActionFactory.match_on_delimiter)
            build_method.assert_called_with(
                ActionDecoder.decode.return_value,
                match_on_mock.split.return_value,
                external_key_mock,
                {'other_key': 'value'})
            self.assertEqual(build_method.return_value, result)

    def test_returns_an_empty_list_if_no_actions_in_input(self):
        self.assertEqual([], self.sut.from_dict(None))

    def test_it_raises_an_error_if_the_action_flag_key_is_not_in_values(self):
        with self.assertRaises(KeyError):
            self.sut.from_dict({'not_matched': 'value'})

    def test_it_raises_an_error_if_the_match_field_key_is_not_in_values(self):
        with self.assertRaises(KeyError):
            self.sut.from_dict({'action_flags': ''})
