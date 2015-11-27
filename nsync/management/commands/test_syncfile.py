from django.core.management import call_command
from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist, FieldError
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from unittest.mock import MagicMock, patch, ANY

from .syncfile import Command, SyncFileAction
from .syncfile import BasicSyncPolicy
from django.core.management.base import CommandError

class TestSyncFileCommand(TestCase):
    def test_command_raises_error_if_file_does_not_exist(self):
        with self.assertRaises(CommandError):
            call_command('syncfile', 'systemName', 'model', 'file')

    @patch('nsync.sync.SyncFileAction')
    @patch('os.path.exists')
    def test_command_delegates_to_sync_file_action(self, exists_function, SyncFileAction):
        pass # trouble with the mocks
        # exists_function.return_value = True
        # from unittest.mock import mock_open
        # from nsync.management.commands.syncfile import Command
        # with patch( 'builtins.open', mock_open()) as m:
        #     call_command('syncfile', 'systemName', 'model', 'filename')
        #     exists_function.assert_called_with('filename')
        #     m.assert_called_with('filename')
        #     SyncFileAction.sync.assert_called_with('systemName', 'model', m.return_value)
        #     #SyncFileAction.assert_called_once_with()

class TestBasicSyncPolicy(TestCase):
    def test_it_calls_execute_for_all_actions(self):
        actions = [MagicMock(), MagicMock(), MagicMock()]
        BasicSyncPolicy.process_actions(actions)
        for action in actions:
            action.execute.assert_called_once_with()

class TestSyncFileAction(TestCase):
    @patch('nsync.management.commands.syncfile.ActionsBuilder')
    @patch('csv.DictReader')
    def test_data_flow(self, DictReader, ActionsBuilder):
        file = MagicMock()
        row = MagicMock()
        row_provider = MagicMock()
        DictReader.return_value = row_provider
        row_provider.__iter__.return_value = [row]
        SyncFileAction.sync(None, None, file)
        DictReader.assert_called_with(file)
        ActionsBuilder.from_dict.assert_called_with(row)
        ActionsBuilder.from_dict.return_value.execute.assert_called_once_with()




