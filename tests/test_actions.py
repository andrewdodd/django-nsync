from unittest.mock import MagicMock, patch, ANY

from django.contrib.contenttypes.fields import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.test import TestCase
from nsync.actions import (
    CreateModelAction,
    UpdateModelAction,
    DeleteModelAction,
    DeleteExternalReferenceAction,
    AlignExternalReferenceAction,
    DeleteIfOnlyReferenceModelAction,
    SyncActions,
    ActionFactory,
    ModelAction)
from nsync.models import ExternalSystem, ExternalKeyMapping

from tests.models import TestPerson, TestHouse


class TestSyncActions(TestCase):
    def test_sync_actions_raises_error_if_action_includes_create_and_delete(
            self):
        with self.assertRaises(ValueError):
            SyncActions(create=True, delete=True)

    def test_sync_actions_raises_error_if_action_includes_update_and_delete(
            self):
        with self.assertRaises(ValueError):
            SyncActions(update=True, delete=True)

    def test_string_representations_are_correct(self):
        self.assertIn('c', str(SyncActions(create=True)))
        self.assertIn('u', str(SyncActions(update=True)))
        self.assertIn('d', str(SyncActions(delete=True)))
        self.assertIn('cu', str(SyncActions(create=True, update=True)))
        self.assertIn('u*', str(SyncActions(update=True, force=True)))
        self.assertIn('d*', str(SyncActions(delete=True, force=True)))
        self.assertIn('cu*',
                      str(SyncActions(create=True, update=True, force=True)))


class TestModelAction(TestCase):
    def test_creating_without_a_model_raises_error(self):
        with self.assertRaises(ValueError):
            ModelAction(None, None)

    # TODO - Perhaps update this to look for the attribute on the class?
    def test_it_raises_an_error_if_matchfieldname_is_blank(self):
        """
        Test that an error is raises if an empty match_field_name
        value is provided, even if the fields dict has a matching key
        """
        with self.assertRaises(ValueError):
            ModelAction(ANY, '', {'': 'value'})

    def test_creating_with_matchfieldname_not_in_fields_raises_error(self):
        with self.assertRaises(ValueError):
            ModelAction(ANY, 'matchfield', {'otherField': 'value'})

    def test_it_attempts_to_find_through_the_provided_model_class(self):
        model = MagicMock()
        found_object = ModelAction(model, 'matchfield',
                                   {'matchfield': 'value'}).find_objects()
        model.objects.filter.assert_called_once_with(matchfield='value')
        self.assertEqual(found_object, model.objects.filter.return_value)

    def test_update_from_fields_changes_values_on_object(self):
        john = TestPerson(first_name='John')
        ModelAction(TestPerson, 'last_name',
                    {'last_name': 'Smith'}).update_from_fields(john)
        self.assertEqual('Smith', john.last_name)

    def test_update_from_fields_updates_related_fields(self):
        person = TestPerson.objects.create(first_name="Jill",
                                           last_name="Jones")
        house = TestHouse.objects.create(address='Bottom of the hill')
        fields = {'address': 'Bottom of the hill', 'owner=>first_name': 'Jill'}

        sut = ModelAction(TestHouse, 'address', fields)
        sut.update_from_fields(house)
        self.assertEqual(person, house.owner)

    @patch('nsync.actions.logger')
    def test_related_fields_not_touched_if_referred_to_object_does_not_exist(
            self, logger):
        house = TestHouse.objects.create(address='Bottom of the hill')
        fields = {'address': 'Bottom of the hill', 'owner=>last_name': 'Jones'}

        sut = ModelAction(TestHouse, 'address', fields)
        sut.update_from_fields(house)
        self.assertEqual(None, house.owner)
        logger.info.assert_called_with(ANY)

    @patch('nsync.actions.logger')
    def test_related_fields_are_not_touched_if_referred_to_object_ambiguous(
            self, logger):
        TestPerson.objects.create(first_name="Jill", last_name="Jones")
        TestPerson.objects.create(first_name="Jack", last_name="Jones")
        house = TestHouse.objects.create(address='Bottom of the hill')
        fields = {'address': 'Bottom of the hill', 'owner=>last_name': 'Jones'}
        sut = ModelAction(TestHouse, 'address', fields)
        sut.update_from_fields(house)
        self.assertEqual(None, house.owner)
        logger.info.assert_called_with(ANY)

    def test_related_fields_update_uses_all_available_filters(self):
        person = TestPerson.objects.create(first_name="John",
                                           last_name="Johnson")
        TestPerson.objects.create(first_name="Jack", last_name="Johnson")
        TestPerson.objects.create(first_name="John", last_name="Jackson")
        TestPerson.objects.create(first_name="Jack", last_name="Jackson")

        house = TestHouse.objects.create(address='Bottom of the hill')
        fields = {
            'address': 'Bottom of the hill',
            'owner=>first_name': 'John',
            'owner=>last_name': 'Johnson'}
        sut = ModelAction(TestHouse, 'address', fields)
        sut.update_from_fields(house)
        self.assertEqual(person, house.owner)

    def test_update_from_fields_does_not_update_values_that_are_not_empty(
            self):
        john = TestPerson(first_name='John', last_name='Smith')
        ModelAction(TestPerson, 'last_name',
                    {'last_name': 'Jackson'}).update_from_fields(john)
        self.assertEqual('Smith', john.last_name)

    def test_update_from_fields_always_updates_fields_when_forced(
            self):
        john = TestPerson(first_name='John', last_name='Smith')
        ModelAction(TestPerson, 'last_name',
                    {'last_name': 'Jackson'}).update_from_fields(john, True)
        self.assertEqual('Jackson', john.last_name)

    def test_related_fields_update_does_not_update_if_already_assigned(
            self):
        jill = TestPerson.objects.create(first_name="Jill", last_name="Jones")
        jack = TestPerson.objects.create(first_name="Jack", last_name="Jones")
        house = TestHouse.objects.create(address='Bottom of the hill',
                                         owner=jill)

        fields = {
            'address': 'Bottom of the hill',
            'owner=>first_name': 'Jack',
            'owner=>last_name': 'Jones'}
        sut = ModelAction(TestHouse, 'address', fields)
        sut.update_from_fields(house)
        self.assertEqual(jill, house.owner)
        self.assertNotEqual(jack, house.owner)

    def test_related_fields_update_does_update_if_forced(self):
        jill = TestPerson.objects.create(first_name="Jill", last_name="Jones")
        jack = TestPerson.objects.create(first_name="Jack", last_name="Jones")
        house = TestHouse.objects.create(address='Bottom of the hill',
                                         owner=jill)

        fields = {
            'address': 'Bottom of the hill',
            'owner=>first_name': 'Jack',
            'owner=>last_name': 'Jones'}
        sut = ModelAction(TestHouse, 'address', fields)
        sut.update_from_fields(house, True)
        self.assertEqual(jack, house.owner)


class TestActionFactory(TestCase):
    def setUp(self):
        self.model = MagicMock()
        self.sut = ActionFactory(self.model)

    @patch('nsync.actions.ModelAction')
    def test_it_creates_a_base_model_action_if_no_action_flags_are_included(
            self, ModelAction):
        result = self.sut.build(SyncActions(), 'field1', None, {'field1': ''})
        ModelAction.assert_called_with(self.model, 'field1', {'field1': ''})
        self.assertIn(ModelAction.return_value, result)

    @patch('nsync.actions.CreateModelAction')
    def test_it_calls_create_action_with_correct_parameters(self,
                                                            TargetActionClass):
        result = self.sut.build(SyncActions(create=True), 'field', ANY,
                                {'field': ''})
        TargetActionClass.assert_called_with(self.model, 'field',
                                             {'field': ''})
        self.assertIn(TargetActionClass.return_value, result)

    @patch('nsync.actions.UpdateModelAction')
    def test_it_calls_update_action_with_correct_parameters(self,
                                                            TargetActionClass):
        for actions in [SyncActions(update=True, force=False),
                        SyncActions(update=True, force=True)]:
            result = self.sut.build(actions, 'field', ANY, {'field': ''})
            TargetActionClass.assert_called_with(self.model, 'field',
                                                 {'field': ''}, actions.force)
            self.assertIn(TargetActionClass.return_value, result)

    @patch('nsync.actions.DeleteModelAction')
    def test_it_calls_delete_action_with_correct_parameters(self,
                                                            TargetActionClass):
        result = self.sut.build(SyncActions(delete=True, force=True), 'field',
                                ANY, {'field': ''})
        TargetActionClass.assert_called_with(self.model, 'field',
                                             {'field': ''})
        self.assertIn(TargetActionClass.return_value, result)

    def test_delete_action_not_built_if_unforced_and_not_externally_mappable(
            self):
        """
        If there is no external mapping AND the delete is not forced,
        then the usual 'DeleteIfOnlyReferenceModelAction' will not actually
        do anything anyway, so test that no actions are built.
        """
        result = self.sut.build(SyncActions(delete=True), 'field', ANY,
                                {'field': ''})
        self.assertEqual([], result)

    def test_it_creates_two_actions_if_create_and_update_flags_are_included(
            self):
        result = self.sut.build(SyncActions(create=True, update=True), 'field',
                                ANY, {'field': ''})
        self.assertEqual(2, len(result))

    def test_it_considers_nothing_externally_mappable_without_external_system(
            self):
        self.assertIs(False, self.sut.is_externally_mappable(''))
        self.assertIs(False, self.sut.is_externally_mappable("a mappable key"))

    def test_it_considers_non_strings_as_not_externally_mappable(self):
        self.assertFalse(ActionFactory(ANY, ANY).is_externally_mappable(None))
        self.assertFalse(ActionFactory(ANY, ANY).is_externally_mappable(0))
        self.assertFalse(ActionFactory(ANY, ANY).is_externally_mappable(1))
        self.assertFalse(ActionFactory(ANY, ANY).is_externally_mappable(ANY))

    def test_it_considers_non_blank_strings_as_externally_mappable(self):
        self.assertTrue(
            ActionFactory(ANY, ANY).is_externally_mappable('a mappable key'))

    @patch('nsync.actions.AlignExternalReferenceAction')
    @patch('nsync.actions.CreateModelAction')
    def test_it_wraps_create_action_if_externally_mappable(
            self, CreateModelAction, AlignExternalReferenceAction):
        external_system_mock = MagicMock()
        model_mock = MagicMock()
        sut = ActionFactory(model_mock, external_system_mock)
        result = sut.build(SyncActions(create=True), 'field', 'external_key',
                           {'field': 'value'})
        AlignExternalReferenceAction.assert_called_with(
            external_system_mock, model_mock,
            'external_key', CreateModelAction.return_value)
        self.assertIn(AlignExternalReferenceAction.return_value, result)
        self.assertNotIn(CreateModelAction.return_value, result)

    @patch('nsync.actions.AlignExternalReferenceAction')
    @patch('nsync.actions.UpdateModelAction')
    def test_it_wraps_update_action_if_externally_mappable(
            self, UpdateModelAction, AlignExternalReferenceAction):
        external_system_mock = MagicMock()
        model_mock = MagicMock()
        sut = ActionFactory(model_mock, external_system_mock)
        result = sut.build(SyncActions(update=True), 'field', 'external_key',
                           {'field': 'value'})
        AlignExternalReferenceAction.assert_called_with(
            external_system_mock, model_mock,
            'external_key', UpdateModelAction.return_value)
        self.assertIn(AlignExternalReferenceAction.return_value, result)
        self.assertNotIn(UpdateModelAction.return_value, result)

    @patch('nsync.actions.DeleteExternalReferenceAction')
    def test_it_creates_delete_external_reference_if_externally_mappable(
            self, DeleteExternalReferenceAction):
        external_system_mock = MagicMock()
        model_mock = MagicMock()
        sut = ActionFactory(model_mock, external_system_mock)
        result = sut.build(SyncActions(delete=True), 'field', 'external_key',
                           {'field': 'value'})
        DeleteExternalReferenceAction.assert_called_with(
            external_system_mock, 'external_key')
        self.assertIn(DeleteExternalReferenceAction.return_value, result)

    @patch('nsync.actions.DeleteModelAction')
    def test_it_creates_delete_action_for_forced_delete_if_externally_mappable(
            self, DeleteModelAction):
        external_system_mock = MagicMock()
        model_mock = MagicMock()
        sut = ActionFactory(model_mock, external_system_mock)
        result = sut.build(SyncActions(delete=True, force=True), 'field',
                           'external_key', {'field': 'value'})
        DeleteModelAction.assert_called_with(model_mock, 'field',
                                             {'field': 'value'})
        self.assertIn(DeleteModelAction.return_value, result)

    @patch('nsync.actions.DeleteIfOnlyReferenceModelAction')
    @patch('nsync.actions.DeleteModelAction')
    def test_it_wraps_delete_action_if_externally_mappable(
            self, DeleteModelAction, DeleteIfOnlyReferenceModelAction):
        external_system_mock = MagicMock()
        model_mock = MagicMock()
        sut = ActionFactory(model_mock, external_system_mock)
        result = sut.build(SyncActions(delete=True), 'field', 'external_key',
                           {'field': 'value'})
        DeleteModelAction.assert_called_with(model_mock, 'field',
                                             {'field': 'value'})
        DeleteIfOnlyReferenceModelAction.assert_called_with(
            external_system_mock,
            'external_key',
            DeleteModelAction.return_value)
        self.assertIn(DeleteIfOnlyReferenceModelAction.return_value, result)


class TestCreateModelAction(TestCase):
    def test_it_creates_an_object(self):
        sut = CreateModelAction(TestPerson, 'first_name',
                                {'first_name': 'John', 'last_name': 'Smith'})
        sut.execute()
        self.assertEqual(1, TestPerson.objects.count())

    def test_it_returns_the_created_object(self):
        sut = CreateModelAction(TestPerson, 'first_name',
                                {'first_name': 'John', 'last_name': 'Smith'})
        result = sut.execute()
        self.assertEqual(TestPerson.objects.first(), result)

    def test_it_does_not_create_if_object_already_exists(self):
        TestPerson.objects.create(first_name='John', last_name='Smith')
        sut = CreateModelAction(TestPerson, 'first_name',
                                {'first_name': 'John', 'last_name': 'Smith'})
        sut.execute()
        self.assertEqual(1, TestPerson.objects.count())

    def test_it_does_not_modify_existing_object_if_object_already_exists(self):
        TestPerson.objects.create(first_name='John', last_name='Jackson')
        sut = CreateModelAction(TestPerson, 'first_name',
                                {'first_name': 'John', 'last_name': 'Smith'})
        sut.execute()
        self.assertEqual(1, TestPerson.objects.count())
        self.assertEquals('Jackson', TestPerson.objects.first().last_name)

    def test_it_does_not_return_the_object_if_it_did_not_create_it(self):
        john = TestPerson.objects.create(first_name='John', last_name='Smith')
        sut = CreateModelAction(TestPerson, 'first_name',
                                {'first_name': 'John', 'last_name': 'Smith'})
        result = sut.execute()
        self.assertEqual(john, result)

    def test_creates_uses_all_included_fields_and_overrides_defaults(
            self):
        sut = CreateModelAction(
            TestPerson,
            'first_name',
            {'first_name': 'John', 'last_name': 'Smith', 'age': 30,
             'hair_colour': 'None, he bald!'})
        result = sut.execute()
        self.assertEqual('John', result.first_name)
        self.assertEqual('Smith', result.last_name)
        self.assertEqual(30, result.age)
        self.assertEqual('None, he bald!', result.hair_colour)


class TestUpdateModelAction(TestCase):
    def test_it_returns_the_object_even_if_nothing_updated(self):
        john = TestPerson.objects.create(first_name='John')
        sut = UpdateModelAction(TestPerson, 'first_name',
                                {'first_name': 'John'})
        result = sut.execute()
        self.assertEquals(john, result)

    def test_it_returns_nothing_if_object_does_not_exist(self):
        sut = UpdateModelAction(TestPerson, 'first_name',
                                {'first_name': 'John', 'last_name': 'Smith'})
        result = sut.execute()
        self.assertIsNone(result)

    def test_it_updates_model_with_new_values(self):
        john = TestPerson.objects.create(first_name='John')
        self.assertEqual('', john.last_name)

        sut = UpdateModelAction(TestPerson, 'first_name',
                                {'first_name': 'John', 'last_name': 'Smith'})
        sut.execute()
        john.refresh_from_db()
        self.assertEquals('Smith', john.last_name)

    # TODO Review this behaviour?
    def test_including_extra_parameters_has_no_effect(self):
        john = TestPerson.objects.create(first_name='John')
        sut = UpdateModelAction(
            TestPerson,
            'first_name',
            {'first_name': 'John',
             'totally_never_going_to_be_a_field': 'Smith'})
        result = sut.execute()
        self.assertEquals(john, result)

    def test_it_forces_updates_when_configured(self):
        john = TestPerson.objects.create(first_name='John', last_name='Smith')
        sut = UpdateModelAction(TestPerson, 'first_name',
                                {'first_name': 'John', 'last_name': 'Jackson'},
                                True)
        sut.execute()
        john.refresh_from_db()
        self.assertEquals('Jackson', john.last_name)


class TestDeleteModelAction(TestCase):
    def test_no_objects_are_deleted_if_none_are_matched(self):
        john = TestPerson.objects.create(first_name='John')
        DeleteModelAction(TestPerson, 'first_name',
                          {'first_name': 'A non-matching name'}).execute()
        self.assertIn(john, TestPerson.objects.all())

    def test_only_objects_with_matching_fields_are_deleted(self):
        TestPerson.objects.create(first_name='John')
        TestPerson.objects.create(first_name='Jack')
        TestPerson.objects.create(first_name='Jill')
        self.assertEqual(3, TestPerson.objects.count())

        DeleteModelAction(TestPerson, 'first_name',
                          {'first_name': 'Jack'}).execute()
        self.assertFalse(TestPerson.objects.filter(first_name='Jack').exists())


class TestDeleteIfOnlyReferenceModelAction(TestCase):
    def setUp(self):
        self.external_system = ExternalSystem.objects.create(name='System')

    def test_it_does_nothing_if_object_does_not_exist(self):
        delete_action = MagicMock()
        delete_action.find_objects.return_value.get.side_effect = \
            ObjectDoesNotExist
        DeleteIfOnlyReferenceModelAction(ANY, ANY, delete_action).execute()
        delete_action.find_objects.assert_called_with()
        delete_action.find_objects.return_value.get.assert_called_with()
        self.assertFalse(delete_action.execute.called)

    def test_it_does_nothing_if_no_key_mapping_is_found(
            self):
        john = TestPerson.objects.create(first_name='John')
        delete_action = MagicMock()
        delete_action.model = TestPerson
        delete_action.find_objects.return_value.get.return_value = john
        DeleteIfOnlyReferenceModelAction(self.external_system, 'SomeKey',
                                         delete_action).execute()
        self.assertFalse(delete_action.execute.called)

    def test_it_calls_delete_action_if_it_is_the_only_key_mapping(self):
        john = TestPerson.objects.create(first_name='John')
        ExternalKeyMapping.objects.create(
            external_system=self.external_system,
            external_key='Person123',
            content_type=ContentType.objects.get_for_model(TestPerson),
            content_object=john,
            object_id=john.id)
        delete_action = MagicMock()
        delete_action.model = TestPerson
        delete_action.find_objects.return_value.get.return_value = john
        DeleteIfOnlyReferenceModelAction(self.external_system, 'Person123',
                                         delete_action).execute()
        delete_action.execute.assert_called_with()

    def test_it_does_not_call_the_delete_action_if_it_is_not_the_key_mapping(
            self):
        john = TestPerson.objects.create(first_name='John')
        ExternalKeyMapping.objects.create(
            external_system=ExternalSystem.objects.create(
                name='AlternateSystem'),
            external_key='Person123',
            content_type=ContentType.objects.get_for_model(TestPerson),
            content_object=john,
            object_id=john.id)
        delete_action = MagicMock()
        delete_action.model = TestPerson
        delete_action.find_objects.return_value.get.return_value = john
        DeleteIfOnlyReferenceModelAction(self.external_system, 'Person123',
                                         delete_action).execute()
        self.assertFalse(delete_action.execute.called)

    def test_it_does_not_call_the_delete_action_if_there_are_other_mappings(
            self):
        john = TestPerson.objects.create(first_name='John')
        ExternalKeyMapping.objects.create(
            external_system=self.external_system,
            external_key='Person123',
            content_type=ContentType.objects.get_for_model(TestPerson),
            content_object=john,
            object_id=john.id)
        ExternalKeyMapping.objects.create(
            external_system=ExternalSystem.objects.create(name='OtherSystem'),
            external_key='Person123',
            content_type=ContentType.objects.get_for_model(TestPerson),
            content_object=john,
            object_id=john.id)
        delete_action = MagicMock()
        delete_action.model = TestPerson
        delete_action.find_objects.return_value.get.return_value = john
        DeleteIfOnlyReferenceModelAction(self.external_system, 'Person123',
                                         delete_action).execute()
        self.assertFalse(delete_action.execute.called)
        delete_action.execute.assert_not_called()  # Works in py3.5


class TestDeleteExternalReferenceAction(TestCase):
    def test_it_deletes_the_matching_external_reference(self):
        external_system = ExternalSystem.objects.create(name='System')
        ExternalKeyMapping.objects.create(
            external_system=external_system,
            external_key='Key1',
            content_type=ContentType.objects.get_for_model(TestPerson),
            object_id=1)
        ExternalKeyMapping.objects.create(
            external_system=external_system,
            external_key='Key2',
            content_type=ContentType.objects.get_for_model(TestPerson),
            object_id=1)
        ExternalKeyMapping.objects.create(
            external_system=external_system,
            external_key='Key3',
            content_type=ContentType.objects.get_for_model(TestPerson),
            object_id=1)
        self.assertEqual(3, ExternalKeyMapping.objects.count())
        DeleteExternalReferenceAction(external_system, 'Key2').execute()
        self.assertEqual(2, ExternalKeyMapping.objects.count())
        self.assertFalse(ExternalKeyMapping.objects.filter(
            external_system=external_system,
            external_key='Key2').exists())


class TestAlignExternalReferenceAction(TestCase):
    def setUp(self):
        self.external_system = ExternalSystem.objects.create(name='System')
        self.john = TestPerson.objects.create(first_name='John')

    def test_it_creates_a_new_key_mapping_if_one_not_found(
            self):
        mock_action = MagicMock()
        mock_action.execute.return_value = self.john

        self.assertEqual(0, ExternalKeyMapping.objects.count())
        sut = AlignExternalReferenceAction(
            self.external_system,
            TestPerson, 'PersonJohn', mock_action)
        sut.execute()

        self.assertEqual(1, ExternalKeyMapping.objects.count())
        mapping = ExternalKeyMapping.objects.first()
        self.assertEqual('PersonJohn', mapping.external_key)
        self.assertEqual(self.john, mapping.content_object)

    def test_it_updates_existing_key_mapping_on_success_of_inner_action(self):
        jill = TestPerson.objects.create(first_name='Jill')
        person_mapping = ExternalKeyMapping.objects.create(
            external_system=self.external_system,
            external_key='Person123',
            content_type=ContentType.objects.get_for_model(TestPerson),
            content_object=jill,
            object_id=jill.id)
        self.assertEqual(1, ExternalKeyMapping.objects.count())
        self.assertEqual(jill, person_mapping.content_object)

        mock_action = MagicMock()
        mock_action.execute.return_value = self.john
        sut = AlignExternalReferenceAction(self.external_system,
                                           TestPerson,
                                           'Person123',
                                           mock_action)
        sut.execute()

        self.assertEqual(1, ExternalKeyMapping.objects.count())
        mapping = ExternalKeyMapping.objects.first()
        self.assertEqual(self.john, mapping.content_object)

    def test_it_does_nothing_if_inner_action_fails(self):
        mock_action = MagicMock()
        mock_action.execute.return_value = None
        sut = AlignExternalReferenceAction(self.external_system,
                                           ANY,
                                           ANY,
                                           mock_action)
        sut.execute()
        mock_action.execute.assert_called_with()
        self.assertEqual(0, ExternalKeyMapping.objects.count())

    @patch('nsync.actions.ExternalKeyMapping')
    def test_it_passes_the_result_of_the_action_back(self, ExternalKeyMapping):
        mock_action = MagicMock()
        sut = AlignExternalReferenceAction(self.external_system,
                                           TestPerson,
                                           ANY,
                                           mock_action)
        result = sut.execute()
        self.assertEqual(mock_action.execute.return_value, result)


class TestActionTypes(TestCase):
    def test_model_action_returns_empty_string_for_type(self):
        self.assertEquals('', ModelAction(ANY, 'field', {'field': ''}).type)

    def test_create_model_action_returns_correct_type_string(self):
        self.assertEquals('create',
                          CreateModelAction(ANY, 'field', {'field': ''}).type)

    def test_update_model_action_returns_correct_type_string(self):
        self.assertEquals('update',
                          UpdateModelAction(ANY, 'field', {'field': ''}).type)

    def test_delete_model_action_returns_correct_type_string(self):
        self.assertEquals('delete',
                          DeleteModelAction(ANY, 'field', {'field': ''}).type)

    def test_delete_if_only_reference_model_action_returns_wrapped_action_type(
            self):
        delete_action = MagicMock()
        sut = DeleteIfOnlyReferenceModelAction(ANY, ANY, delete_action)
        self.assertEqual(delete_action.type, sut.type)

    def test_align_external_reference_action_returns_wrapped_action_type(self):
        action = MagicMock()
        sut = AlignExternalReferenceAction(ANY, ANY, ANY, action)
        self.assertEqual(action.type, sut.type)

    def test_delete_external_reference_action_returns_correct_type_string(
            self):
        self.assertEquals('delete',
                          DeleteExternalReferenceAction(ANY, ANY).type)
