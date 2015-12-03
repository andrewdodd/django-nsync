from unittest.mock import patch

from django.core.management.base import CommandError
from django.test import TestCase

from nsync.sync import ExternalSystemHelper, ModelFinder


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
        ExternalSystem.objects.create.assert_called_with(name='systemName', description='systemName')


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
    def test_csv_file_with_headers_is_valid(self):
        pass
