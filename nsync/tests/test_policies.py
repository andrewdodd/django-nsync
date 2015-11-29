
from django.test import TestCase
from unittest.mock import MagicMock, patch, ANY

from nsync.policies import BasicSyncPolicy


class TestBasicSyncPolicy(TestCase):
    def test_it_calls_execute_for_all_actions(self):
        actions = [MagicMock(), MagicMock(), MagicMock()]
        BasicSyncPolicy(actions).execute()
        for action in actions:
            action.execute.assert_called_once_with()
