from unittest.mock import MagicMock, call

from django.test import TestCase
from nsync.policies import BasicSyncPolicy, OrderedSyncPolicy


class TestBasicSyncPolicy(TestCase):
    def test_it_calls_execute_for_all_actions(self):
        actions = [MagicMock(), MagicMock(), MagicMock()]
        BasicSyncPolicy(actions).execute()
        for action in actions:
            action.execute.assert_called_once_with()


class TestOrderedSyncPolicy(TestCase):
    def test_it_calls_in_order_create_update_delete(self):
        execute_mock = MagicMock()

        def make_mock(type):
            mock = MagicMock()
            mock.type = type
            return mock

        create_action = make_mock('create')
        update_action = make_mock('update')
        delete_action = make_mock('delete')
        execute_mock.create = create_action
        execute_mock.update = update_action
        execute_mock.delete = delete_action

        OrderedSyncPolicy([
            delete_action,
            create_action,
            update_action]).execute()

        execute_mock.assert_has_calls([
            call.create.execute(),
            call.update.execute(),
            call.delete.execute()])
