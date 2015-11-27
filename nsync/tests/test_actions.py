from django.test import TestCase
from unittest.mock import MagicMock, patch, ANY
from nsync.actions import EncodedSyncActions, ActionsBuilder, ModelAction
from nsync.actions import CreateModelAction, UpdateModelAction, DeleteModelAction

from nsync.tests.models import TestPerson

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

    @patch('nsync.actions.EncodedSyncActions')
    def test_from_dict_maps_to_build_correctly(self, EncodedSyncActions):
        action_flags_mock = MagicMock()
        match_field_name_mock = MagicMock()
        external_key_mock = MagicMock()
        
        with patch.object(self.sut, 'build') as build_method:
            result = self.sut.from_dict({
                'action_flags': action_flags_mock,
                'match_field_name': match_field_name_mock,
                'external_key': external_key_mock,
                'other_key': 'value'
                })
            EncodedSyncActions.decode.assert_called_with(action_flags_mock)
            build_method.assert_called_with(
                    EncodedSyncActions.decode.return_value,
                    match_field_name_mock,
                    external_key_mock,
                    {'other_key': 'value'})
            self.assertEqual(build_method.return_value, result)

    def test_returns_an_empty_list_if_no_actions_in_input(self):
        self.assertEqual([], self.sut.from_dict(None))

    def test_it_raises_an_error_if_the_action_flag_key_is_not_in_values(self):
        with self.assertRaises(KeyError):
            self.sut.from_dict({'not_matched':'value'})

    def test_it_raises_an_error_if_the_match_field_key_is_not_in_values(self):
        with self.assertRaises(KeyError):
            self.sut.from_dict({'action_flags':''})

    @patch('nsync.actions.ModelAction')
    def test_it_creates_a_base_model_action_if_no_action_flags_are_included(self, ModelAction):
        result = self.sut.build(EncodedSyncActions(), 'field1', None, {'field1': ''})
        ModelAction.assert_called_with(self.model, 'field1', {'field1': ''})
        self.assertIn(ModelAction.return_value, result)

    @patch('nsync.actions.DeleteModelAction')
    @patch('nsync.actions.UpdateModelAction')
    @patch('nsync.actions.CreateModelAction')
    def test_it_calls_the_correct_action_class_for_each_type(self, CreateModelAction, UpdateModelAction, DeleteModelAction):
        def assert_for_target_class(TargetActionClass):
            TargetActionClass.assert_called_with(self.model, 'field1', {'field1': ''})
            self.assertIn(TargetActionClass.return_value, result)

        test_inputs = [
                (EncodedSyncActions(create=True), CreateModelAction),
                (EncodedSyncActions(update=True), UpdateModelAction),
                (EncodedSyncActions(delete=True), DeleteModelAction)]

        for (encoded_action, resulting_action) in test_inputs:
            result = self.sut.build(encoded_action, 'field1', ANY, {'field1': ''})
            assert_for_target_class(resulting_action)

    def test_it_creates_two_actions_if_create_and_update_action_flags_are_included(self):
        self.dict_with_defaults['action_flags'] = EncodedSyncActions(create=True, update=True).encode()
        result = self.sut.from_dict(self.dict_with_defaults)
        self.assertEqual(2, len(result))


class TestCreateModelAction(TestCase):
    def test_it_creates_an_object(self):
        sut = CreateModelAction(TestPerson, 'first_name', {'first_name': 'John', 'last_name': 'Smith'})
        sut.execute()
        self.assertEqual(1, TestPerson.objects.count())

    def test_it_returns_the_created_object(self):
        sut = CreateModelAction(TestPerson, 'first_name', {'first_name': 'John', 'last_name': 'Smith'})
        result = sut.execute()
        self.assertEqual(TestPerson.objects.first(), result)

    def test_it_does_not_create_if_object_already_exists(self):
        TestPerson.objects.create(first_name='John', last_name='Smith')
        sut = CreateModelAction(TestPerson, 'first_name', {'first_name': 'John', 'last_name': 'Smith'})
        sut.execute()
        self.assertEqual(1, TestPerson.objects.count())

    def test_it_does_not_modify_existing_object_if_object_already_exists(self):
        TestPerson.objects.create(first_name='John', last_name='Jackson')
        sut = CreateModelAction(TestPerson, 'first_name', {'first_name': 'John', 'last_name': 'Smith'})
        sut.execute()
        self.assertEqual(1, TestPerson.objects.count())
        self.assertEquals('Jackson', TestPerson.objects.first().last_name)

    def test_it_does_not_return_the_object_if_it_did_not_create_it(self):
        TestPerson.objects.create(first_name='John', last_name='Smith')
        sut = CreateModelAction(TestPerson, 'first_name', {'first_name': 'John', 'last_name': 'Smith'})
        result = sut.execute()
        self.assertIsNone(result)

    def test_it_creates_an_object_with_all_included_fields(self):
        sut = CreateModelAction(TestPerson, 'first_name', 
                {'first_name': 'John', 'last_name': 'Smith', 'age': 30})
        result = sut.execute()
        self.assertEqual('John', result.first_name)
        self.assertEqual('Smith', result.last_name)
        self.assertEqual(30, result.age)
     

class TestUpdateModelAction(TestCase):
    def test_it_returns_the_object_even_if_nothing_updated(self):
        john = TestPerson.objects.create(first_name='John')
        sut = UpdateModelAction(TestPerson, 'first_name', {'first_name': 'John'})
        result = sut.execute()
        self.assertEquals(john, result)

    def test_it_returns_nothing_if_object_does_not_exist(self):
        sut = UpdateModelAction(TestPerson, 'first_name', {'first_name': 'John', 'last_name': 'Smith'})
        result = sut.execute()
        self.assertIsNone(result)

    def test_it_updates_model_with_new_values(self):
        john = TestPerson.objects.create(first_name='John')
        self.assertEqual('', john.last_name)

        sut = UpdateModelAction(TestPerson, 'first_name', {'first_name': 'John', 'last_name': 'Smith'})
        sut.execute()
        john.refresh_from_db()
        self.assertEquals('Smith', john.last_name)

    # TODO Review this behaviour?
    def test_including_extra_parameters_has_no_effect(self):
        john = TestPerson.objects.create(first_name='John')
        sut = UpdateModelAction(TestPerson, 'first_name', 
                {'first_name': 'John', 'totally_never_going_to_be_a_field': 'Smith'})
        result = sut.execute()
        self.assertEquals(john, result)


class TestDeleteModelAction(TestCase):
    def test_no_objects_are_deleted_if_none_are_matched(self):
        john = TestPerson.objects.create(first_name='John')
        DeleteModelAction(TestPerson, 'first_name', {'first_name': 'A non-matching name'}).execute()
        self.assertIn(john, TestPerson.objects.all())

    def test_only_objects_with_matching_fields_are_deleted(self):
        TestPerson.objects.create(first_name='John')
        TestPerson.objects.create(first_name='Jack')
        TestPerson.objects.create(first_name='Jill')
        self.assertEqual(3, TestPerson.objects.count())

        DeleteModelAction(TestPerson, 'first_name', {'first_name': 'Jack'}).execute()
        self.assertFalse(TestPerson.objects.filter(first_name='Jack').exists())

