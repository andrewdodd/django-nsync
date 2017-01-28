from unittest.mock import MagicMock, patch, ANY

from django.contrib.contenttypes.fields import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.db.models.query_utils import Q
from django.test import TestCase
from nsync.actions import (
    CreateModelAction,
    UpdateModelAction,
    DeleteModelAction,
    CreateModelWithReferenceAction,
    UpdateModelWithReferenceAction,
    DeleteExternalReferenceAction,
    DeleteIfOnlyReferenceModelAction,
    SyncActions,
    ActionFactory,
    ObjectSelector,
    ModelAction)
from nsync.models import ExternalSystem, ExternalKeyMapping

from tests.models import TestPerson, TestHouse, TestBuilder


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

# http://jamescooke.info/comparing-django-q-objects.html
class QTestMixin(object):

    def assertQEqual(self, left, right):
        """
        Assert `Q` objects are equal by ensuring that their
        unicode outputs are equal (crappy but good enough)
        """
        self.assertIsInstance(left, Q)
        self.assertIsInstance(right, Q)
        left_u = str(left)
        right_u = str(right)
        self.assertEqual(left_u, right_u)


class TestObjectSelector(TestCase, QTestMixin):
    def setUp(self):
        self.fields = { 'field' + str(i): 'value' + str(i) for i in range(1,6)}

    def test_it_raises_an_error_if_match_on_field_not_in_available_fields(self):
        with self.assertRaises(ValueError):
            ObjectSelector(['field'], {'' :'value'})

    def test_it_does_not_raise_error_for_pipe_character(self):
        ObjectSelector(['|'], {'' :'value'})

    def test_it_does_not_raise_error_for_ampersand_character(self):
        ObjectSelector(['&'], {'' :'value'})

    def test_it_does_not_raise_error_for_tilde_character(self):
        ObjectSelector(['~'], {'' :'value'})

    def test_it_supports_a_single_get_by_field(self):
        sut = ObjectSelector(['field1'], self.fields)
        result = sut.get_by()
        self.assertQEqual(Q(field1='value1'), result)

    def test_get_by_returns_an_AND_filter_by_default(self):
        sut = ObjectSelector(['field1', 'field2'], self.fields)
        result = sut.get_by()
        self.assertQEqual(Q(field1='value1') & Q(field2='value2'), result)

    def test_it_supports_postfix_style_AND_filter_by(self):
        sut = ObjectSelector(['field1', 'field2', '&'], self.fields)
        result = sut.get_by()
        self.assertQEqual(Q(field1='value1') & Q(field2='value2'), result)

    def test_it_supports_postfix_style_OR_filter_by(self):
        sut = ObjectSelector(['field1', 'field2', '|'], self.fields)
        result = sut.get_by()
        self.assertQEqual(Q(field1='value1') | Q(field2='value2'), result)

    def test_it_supports_postfix_style_NOT_filter_by(self):
        sut = ObjectSelector(['field1', '~'], self.fields)
        result = sut.get_by()
        self.assertQEqual(~Q(field1='value1'), result)

    def test_it_supports_postfix_style_filter_by_options_extended(self):
        sut = ObjectSelector(['field1', 'field2', '&', 'field3', '~', 'field4', '&', '|'], self.fields)
        result = sut.get_by()
        self.assertQEqual((Q(field1='value1') & Q(field2='value2')) |
                              (~Q(field3='value3') & Q(field4='value4')), result)

    def test_it_raises_an_error_if_insufficient_operands_for_AND(self):
        with self.assertRaises(ValueError):
            sut = ObjectSelector(['field1', '&'], self.fields)
            result = sut.get_by()

    def test_it_raises_an_error_if_insufficient_operands_for_OR(self):
        with self.assertRaises(ValueError):
            sut = ObjectSelector(['field1', '|'], self.fields)
            result = sut.get_by()

    def test_it_raises_an_error_if_insufficient_operands_for_NOT(self):
        with self.assertRaises(ValueError):
            sut = ObjectSelector(['~'], self.fields)
            result = sut.get_by()

    def test_it_raises_an_error_if_insufficient_operators(self):
        with self.assertRaises(ValueError):
            sut = ObjectSelector(['field1', 'field2', 'field3', '&'], self.fields)
            result = sut.get_by()


class TestModelAction(TestCase):
    # http://stackoverflow.com/questions/899067/how-should-i-verify-a-log-message-when-testing-python-code-under-nose/20553331#20553331
    @classmethod
    def setUpClass(cls):
        super(TestModelAction, cls).setUpClass()
        # Assuming you follow Python's logging module's documentation's
        # recommendation about naming your module's logs after the module's
        # __name__,the following getLogger call should fetch the same logger
        # you use in the foo module
        import logging
        import nsync
        from tests.test_utils import MockLoggingHandler
        logger = logging.getLogger(nsync.actions.__name__)
        cls._logger_handler = MockLoggingHandler(level='DEBUG')
        logger.addHandler(cls._logger_handler)
        cls.logger_messages = cls._logger_handler.messages

    def setUp(self):
        super(TestModelAction, self).setUp()
        self._logger_handler.reset() # So each test is independent

    def test_it_has_custom_string_format(self):
        sut = ModelAction(TestPerson, ['match_field'], {'match_field':'value'})
        result = str(sut)
        self.assertIn("ModelAction", result)
        self.assertIn("Model:TestPerson", result)
        self.assertIn("MatchFields:['match_field']", result)
        self.assertIn("Fields:{'match_field': 'value'}", result)

    def test_creating_without_a_model_raises_error(self):
        with self.assertRaises(ValueError):
            ModelAction(None, None)

    # TODO - Perhaps update this to look for the attribute on the class?
    def test_it_raises_an_error_if_match_on_is_empty(self):
        """
        Test that an error is raises if an empty match_on value is provided,
        even if the fields dict has a matching key
        """
        with self.assertRaises(ValueError):
            ModelAction(ANY, [], {'': 'value'})

    def test_it_raises_error_if_any_match_on_not_in_fields(self):
        with self.assertRaises(ValueError):
            ModelAction(ANY, 
                    ['matchingfield', 'missingfield'], 
                    {'matchingfield': 'value'})

    def test_it_attempts_to_find_through_the_provided_model_class(self):
        model = MagicMock()
        found_object = ModelAction(model, ['matchfield'],
                                   {'matchfield': 'value'}).get_object()
        self.assertEqual(found_object, model.objects.get.return_value)

    def test_it_attempts_to_find_with_all_matchfields(self):
        model = MagicMock()
        found_object = ModelAction(
            model,
            ['matchfield1', 'matchfield2'],
            {'matchfield1': 'value1', 'matchfield2': 'value2'}).get_object()
        self.assertEqual(str(Q(matchfield1='value1') & Q(matchfield2='value2')),
                         str(model.objects.get.call_args[0][0]))
        self.assertEqual(found_object, model.objects.get.return_value)

    def test_it_builds_OR_Q_object_if_last_token_is_pipe(self):
        model = MagicMock()
        found_object = ModelAction(
            model,
            ['matchfield1', 'matchfield2', '|'],
            {'matchfield1': 'value1', 'matchfield2': 'value2'}).get_object()
        self.assertEqual(str(Q(matchfield1='value1') | Q(matchfield2='value2')),
                         str(model.objects.get.call_args[0][0]))
        self.assertEqual(found_object, model.objects.get.return_value)

    def test_it_finds_an_object_with_alternative_options(self):
        model = MagicMock()
        found_object = ModelAction(
            model,
            ['matchfield1', 'matchfield2', '|'],
            {'matchfield1': 'value1', 'matchfield2': 'value2'}).get_object()
        self.assertEqual(str(Q(matchfield1='value1') | Q(matchfield2='value2')),
                         str(model.objects.get.call_args[0][0]))
        self.assertEqual(found_object, model.objects.get.return_value)
        john = TestPerson.objects.create(first_name='John', last_name='Smith')
        jill = TestPerson.objects.create(first_name='Jill', last_name='Smyth')

        john = ModelAction(TestPerson,
                ['first_name', 'last_name', '|'],
                {'first_name': '', 'last_name': 'Smith'}).get_object()
        jill = ModelAction(TestPerson,
                ['first_name', 'last_name', '|'],
                {'first_name': 'Jill', 'last_name': ''}).get_object()

        self.assertEqual('Smith', john.last_name)
        self.assertEqual('Smyth', jill.last_name)


    def test_update_from_fields_changes_values_on_object(self):
        john = TestPerson(first_name='John')
        ModelAction(TestPerson, ['last_name'],
                    {'last_name': 'Smith'}).update_from_fields(john)
        self.assertEqual('Smith', john.last_name)

    def test_update_from_uses_none_if_field_is_nullable_and_value_is_empty_string(self):
        house = TestHouse.objects.create(address='Bottom of the hill')
        fields = {'address': 'Bottom of the hill', 'built': ''}

        sut = ModelAction(TestHouse, ['address'], fields)
        sut.update_from_fields(house)
        house.save()
        house.refresh_from_db()
        self.assertEqual(house.built, None)

    def test_update_from_fields_updates_related_fields(self):
        person = TestPerson.objects.create(first_name="Jill",
                                           last_name="Jones")
        house = TestHouse.objects.create(address='Bottom of the hill')
        fields = {'address': 'Bottom of the hill', 'owner=>first_name': 'Jill'}

        sut = ModelAction(TestHouse, ['address'], fields)
        sut.update_from_fields(house)
        self.assertEqual(person, house.owner)

    def test_update_from_fields_updates_related_fields_from_opposite_direction(self):
        person = TestPerson.objects.create(first_name="Jill",
                                           last_name="Jones")
        house = TestHouse.objects.create(address='Bottom of the hill')
        fields = {'first_name': 'Jill', 'houses=>address': 'Bottom of the hill'}

        sut = ModelAction(TestPerson, ['first_name'], fields)
        sut.update_from_fields(person)
        self.assertEqual(house, person.houses.get())

    def test_error_is_logged_if_field_not_on_object(self):
        house = TestHouse.objects.create(address='Bottom of the hill')
        fields = {'address': 'Bottom of the hill', 'buyer=>last_name': 'Jones'}

        sut = ModelAction(TestHouse, ['address'], fields)
        sut.update_from_fields(house)

        for msg in self.logger_messages['warning']:
            self.assertIn('buyer', msg)

    def test_related_fields_not_touched_if_referred_to_object_does_not_exist(
            self):
        house = TestHouse.objects.create(address='Bottom of the hill')
        fields = {'address': 'Bottom of the hill', 'owner=>last_name': 'Jones'}

        sut = ModelAction(TestHouse, ['address'], fields)
        sut.update_from_fields(house)
        self.assertEqual(None, house.owner)

        for msg in self.logger_messages['warning']:
            self.assertIn('Could not find TestPerson', msg)
            self.assertIn(str({'last_name': 'Jones'}), msg)

    def test_related_fields_are_not_touched_if_referred_to_object_ambiguous(
            self):
        TestPerson.objects.create(first_name="Jill", last_name="Jones")
        TestPerson.objects.create(first_name="Jack", last_name="Jones")
        house = TestHouse.objects.create(address='Bottom of the hill')
        fields = {'address': 'Bottom of the hill', 'owner=>last_name': 'Jones'}
        sut = ModelAction(TestHouse, ['address'], fields)
        sut.update_from_fields(house)
        self.assertEqual(None, house.owner)

        for msg in self.logger_messages['warning']:
            self.assertIn('Found multiple TestPerson objects', msg)
            self.assertIn(str({'last_name': 'Jones'}), msg)


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
        sut = ModelAction(TestHouse, ['address'], fields)
        sut.update_from_fields(house)
        self.assertEqual(person, house.owner)

    def test_related_fields_update_does_not_use_filters_with_values_as_empty_strings(self):
        """
            This effectively prevents over-specification, and allows files
            to be constructed with "or" style relations
        """
        jill = TestPerson.objects.create(first_name="Jill", last_name="Hill")
        jack = TestPerson.objects.create(first_name="Jack", last_name="Shack")
        house = TestHouse.objects.create(address='Bottom of the hill')

        fields = {
            'address': 'Bottom of the hill',
            'owner=>first_name': '',
            'owner=>last_name': 'Shack'}
        sut = ModelAction(TestHouse, ['address'], fields)
        sut.update_from_fields(house, True)
        self.assertEqual(jack, house.owner)

        fields = {
            'address': 'Bottom of the hill',
            'owner=>first_name': 'Jill',
            'owner=>last_name': ''}
        sut = ModelAction(TestHouse, ['address'], fields)
        sut.update_from_fields(house, True)
        self.assertEqual(jill, house.owner)

    def test_update_from_fields_does_not_update_values_that_are_not_empty(
            self):
        john = TestPerson(first_name='John', last_name='Smith')
        ModelAction(TestPerson, ['last_name'],
                    {'last_name': 'Jackson'}).update_from_fields(john)
        self.assertEqual('Smith', john.last_name)

    def test_update_from_fields_always_updates_fields_when_forced(
            self):
        john = TestPerson(first_name='John', last_name='Smith')
        ModelAction(TestPerson, ['last_name'],
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
        sut = ModelAction(TestHouse, ['address'], fields)
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
        sut = ModelAction(TestHouse, ['address'], fields)
        sut.update_from_fields(house, True)
        self.assertEqual(jack, house.owner)

    def test_it_does_not_update_many_to_many_fields_with_simple_referred_to_delimiter(self):
        bob = TestBuilder.objects.create(first_name="Bob", last_name="The Builder")
        house = TestHouse.objects.create(address='Bottom of the hill')

        fields = {
            'first_name': 'Bob',
            'buildings=>address': 'Bottom of the hill',
            }
        sut = ModelAction(TestBuilder, ['first_name'], fields)
        sut.update_from_fields(house, True)
        self.assertNotIn(house, bob.buildings.all())

    def test_it_adds_elements_to_many_to_many_with_plus_referred_to_delimiter(self):
        bob = TestBuilder.objects.create(first_name="Bob", last_name="The Builder")
        house = TestHouse.objects.create(address='Bottom of the hill')

        fields = {
            'first_name': 'Bob',
            'buildings=>+address': 'Bottom of the hill',
            }
        sut = ModelAction(TestBuilder, ['first_name'], fields)

        sut.update_from_fields(bob, True)
        self.assertIn(house, bob.buildings.all())

    def test_it_adds_elements_to_many_to_many_from_opposite_direction(self):
        bob = TestBuilder.objects.create(first_name="Bob", last_name="The Builder")
        house = TestHouse.objects.create(address='Bottom of the hill')

        fields = {
            'address': 'Bottom of the hill',
            'builders=>+first_name': 'Bob',
            }
        sut = ModelAction(TestBuilder, ['address'], fields)

        sut.update_from_fields(house, True)
        self.assertIn(bob, house.builders.all())


    def test_it_removes_elements_from_many_to_many_with_minus_referred_to_delimiter(self):
        house = TestHouse.objects.create(address='Bottom of the hill')
        bob = TestBuilder.objects.create(first_name="Bob", last_name="The Builder")
        bob.buildings.add(house)
        bob.save()

        fields = {
            'first_name': 'Bob',
            'buildings=>-address': 'Bottom of the hill',
            }
        sut = ModelAction(TestBuilder, ['first_name'], fields)
        sut.update_from_fields(bob, True)
        self.assertNotIn(house, bob.buildings.all())

    def test_it_replaces_all_elements_in_many_to_many_with_equals_referred_to_delimiter(self):
        house1 = TestHouse.objects.create(address='Bottom of the hill')
        house2 = TestHouse.objects.create(address='Top of the hill')
        bob = TestBuilder.objects.create(first_name="Bob", last_name="The Builder")
        bob.buildings.add(house1)
        bob.save()

        fields = {
            'first_name': 'Bob',
            'buildings=>=address': 'Top of the hill',
            }
        sut = ModelAction(TestBuilder, ['first_name'], fields)
        sut.update_from_fields(bob, True)
        self.assertNotIn(house1, bob.buildings.all())
        self.assertIn(house2, bob.buildings.all())

    def test_it_uses_all_related_fields_to_find_targets_for_many_to_many_fields(self):
        house1 = TestHouse.objects.create(address='Bottom of the hill', country='Australia')
        house2 = TestHouse.objects.create(address='Bottom of the hill', country='Belgium')
        bob = TestBuilder.objects.create(first_name="Bob", last_name="The Builder")
        bob.buildings.add(house1)
        bob.save()

        fields = {
            'first_name': 'Bob',
            'buildings=>=address': 'Bottom of the hill',
            'buildings=>=country': 'Belgium',
            }
        sut = ModelAction(TestBuilder, ['first_name'], fields)
        sut.update_from_fields(bob, True)
        self.assertNotIn(house1, bob.buildings.all())
        self.assertIn(house2, bob.buildings.all())

    def test_it_logs_an_error_if_action_type_for_many_to_many_referred_fields_is_unknown(self):
        bob = TestBuilder.objects.create(first_name="Bob", last_name="The Builder")

        fields = {
            'first_name': 'Bob',
            'buildings=>*address': 'Bottom of the hill',
            }

        sut = ModelAction(TestBuilder, ['first_name'], fields)
        sut.update_from_fields(bob, True)

        for msg in self.logger_messages['warning']:
            self.assertIn('Unknown action type', msg)

    def test_it_logs_an_error_if_action_type_for_many_to_many_referred_fields_is_dissimilar(self):
        bob = TestBuilder.objects.create(first_name="Bob", last_name="The Builder")

        fields = {
            'first_name': 'Bob',
            'buildings=>+address': 'Bottom of the hill',
            'buildings=>=country': 'Belgium',
            }

        sut = ModelAction(TestBuilder, ['first_name'], fields)
        sut.update_from_fields(bob, True)

        for msg in self.logger_messages['warning']:
            self.assertIn('Dissimilar action types', msg)


class TestActionFactory(TestCase):
    def setUp(self):
        self.model = MagicMock()
        self.sut = ActionFactory(self.model)

    @patch('nsync.actions.ModelAction')
    def test_it_creates_a_base_model_action_if_no_action_flags_are_included(
            self, ModelAction):
        result = self.sut.build(SyncActions(), ['field'], None, {'field': ''})
        ModelAction.assert_called_with(self.model, ['field'], {'field': ''})
        self.assertIn(ModelAction.return_value, result)

    @patch('nsync.actions.CreateModelAction')
    def test_it_calls_create_action_with_correct_parameters(self,
                                                            TargetActionClass):
        result = self.sut.build(SyncActions(create=True), ['field'], ANY,
                                {'field': ''})
        TargetActionClass.assert_called_with(self.model, ['field'],
                                             {'field': ''})
        self.assertIn(TargetActionClass.return_value, result)

    @patch('nsync.actions.UpdateModelAction')
    def test_it_calls_update_action_with_correct_parameters(self,
                                                            TargetActionClass):
        for actions in [SyncActions(update=True, force=False),
                        SyncActions(update=True, force=True)]:
            result = self.sut.build(actions, ['field'], ANY, {'field': ''})
            TargetActionClass.assert_called_with(self.model, ['field'],
                                                 {'field': ''}, actions.force)
            self.assertIn(TargetActionClass.return_value, result)

    @patch('nsync.actions.DeleteModelAction')
    def test_it_calls_delete_action_with_correct_parameters(self,
                                                            TargetActionClass):
        result = self.sut.build(SyncActions(delete=True, force=True), ['field'],
                                ANY, {'field': ''})
        TargetActionClass.assert_called_with(self.model, ['field'],
                                             {'field': ''})
        self.assertIn(TargetActionClass.return_value, result)

    def test_delete_action_not_built_if_unforced_and_not_externally_mappable(
            self):
        """
        If there is no external mapping AND the delete is not forced,
        then the usual 'DeleteIfOnlyReferenceModelAction' will not actually
        do anything anyway, so test that no actions are built.
        """
        result = self.sut.build(SyncActions(delete=True), ['field'], ANY,
                                {'field': ''})
        self.assertEqual([], result)

    def test_it_creates_two_actions_if_create_and_update_flags_are_included(
            self):
        result = self.sut.build(SyncActions(create=True, update=True), ['field'],
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

    @patch('nsync.actions.CreateModelWithReferenceAction')
    def test_it_builds_a_create_with_external_action_if_externally_mappable(
            self, builtAction):
        external_system_mock = MagicMock()
        model_mock = MagicMock()
        sut = ActionFactory(model_mock, external_system_mock)
        result = sut.build(SyncActions(create=True), ['field'], 'external_key',
                           {'field': 'value'})
        builtAction.assert_called_with(
            external_system_mock, model_mock,
            'external_key', ['field'], {'field': 'value'})
        self.assertIn(builtAction.return_value, result)

    @patch('nsync.actions.UpdateModelWithReferenceAction')
    def test_it_builds_an_update_with_external_action_if_externally_mappable(
            self, builtAction):
        external_system_mock = MagicMock()
        model_mock = MagicMock()
        sut = ActionFactory(model_mock, external_system_mock)
        result = sut.build(SyncActions(update=True), ['field'], 'external_key',
                           {'field': 'value'})
        builtAction.assert_called_with(
            external_system_mock, model_mock,
            'external_key', ['field'], {'field': 'value'}, False)
        self.assertIn(builtAction.return_value, result)

    @patch('nsync.actions.DeleteExternalReferenceAction')
    def test_it_creates_delete_external_reference_if_externally_mappable(
            self, DeleteExternalReferenceAction):
        external_system_mock = MagicMock()
        model_mock = MagicMock()
        sut = ActionFactory(model_mock, external_system_mock)
        result = sut.build(SyncActions(delete=True), ['field'], 'external_key',
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
        result = sut.build(SyncActions(delete=True, force=True), ['field'],
                           'external_key', {'field': 'value'})
        DeleteModelAction.assert_called_with(model_mock, ['field'],
                                             {'field': 'value'})
        self.assertIn(DeleteModelAction.return_value, result)

    @patch('nsync.actions.DeleteIfOnlyReferenceModelAction')
    @patch('nsync.actions.DeleteModelAction')
    def test_it_wraps_delete_action_if_externally_mappable(
            self, DeleteModelAction, DeleteIfOnlyReferenceModelAction):
        external_system_mock = MagicMock()
        model_mock = MagicMock()
        sut = ActionFactory(model_mock, external_system_mock)
        result = sut.build(SyncActions(delete=True), ['field'], 'external_key',
                           {'field': 'value'})
        DeleteModelAction.assert_called_with(model_mock, ['field'],
                                             {'field': 'value'})
        DeleteIfOnlyReferenceModelAction.assert_called_with(
            external_system_mock,
            'external_key',
            DeleteModelAction.return_value)
        self.assertIn(DeleteIfOnlyReferenceModelAction.return_value, result)


class TestCreateModelAction(TestCase):
    def test_it_creates_an_object(self):
        sut = CreateModelAction(TestPerson, ['first_name'],
                                {'first_name': 'John', 'last_name': 'Smith'})
        sut.execute()
        self.assertEqual(1, TestPerson.objects.count())

    def test_it_returns_the_created_object(self):
        sut = CreateModelAction(TestPerson, ['first_name'],
                                {'first_name': 'John', 'last_name': 'Smith'})
        result = sut.execute()
        self.assertEqual(TestPerson.objects.first(), result)

    def test_it_does_not_create_if_matching_object_exists(self):
        TestPerson.objects.create(first_name='John', last_name='Smith')
        sut = CreateModelAction(TestPerson, ['first_name'],
                                {'first_name': 'John', 'last_name': 'Smith'})
        sut.execute()
        self.assertEqual(1, TestPerson.objects.count())

    def test_it_does_not_modify_existing_object_if_object_already_exists(self):
        TestPerson.objects.create(first_name='John', last_name='Jackson')
        sut = CreateModelAction(TestPerson, ['first_name'],
                                {'first_name': 'John', 'last_name': 'Smith'})
        sut.execute()
        self.assertEqual(1, TestPerson.objects.count())
        self.assertEquals('Jackson', TestPerson.objects.first().last_name)

    def test_it_returns_the_object_even_if_it_did_not_create_it(self):
        john = TestPerson.objects.create(first_name='John', last_name='Smith')
        sut = CreateModelAction(TestPerson, ['first_name'],
                                {'first_name': 'John', 'last_name': 'Smith'})
        result = sut.execute()
        self.assertEqual(john, result)

    def test_it_uses_all_included_fields_and_overrides_defaults(
            self):
        sut = CreateModelAction(
            TestPerson,
            ['first_name'],
            {'first_name': 'John', 'last_name': 'Smith', 'age': 30,
             'hair_colour': 'None, he bald!'})
        result = sut.execute()
        self.assertEqual('John', result.first_name)
        self.assertEqual('Smith', result.last_name)
        self.assertEqual(30, result.age)
        self.assertEqual('None, he bald!', result.hair_colour)


class TestCreateModelWithReferenceAction(TestCase):
    """
    These tests try to cover off the following matrix of behaviour:
    +---------------+---------------------+----------------------------------------+
    | Model object  |   External Link     | Behaviour / Outcome desired            |
    +---------------+---------------------+----------------------------------------+
    |               |                     | The standard case. The model object    |
    |      No       |      No             | should be created, and if successful   |
    |               |                     | an external linkage object should be   |
    |               |                     |  created to point to it.               |
    +------------------------------------------------------------------------------+
    |               |                     | Object already exists case. An         |
    |    Exists     |      No             | external linkage object is created     |
    |               |                     | and pointed at the existing object.    |
    +------------------------------------------------------------------------------+
    |               |                     | A previously made object was deleted.  |
    |     No        |     Exists          | Create the model object and update     |
    |               |                     | the linkage object to point at it.     |
    +------------------------------------------------------------------------------+
    |   Exists      | Exists, points  to  | Already pointing to matching / created |
    |               |  matching object    | object. Do nothing. NOT TESTED         |
    +------------------------------------------------------------------------------+
    |               | Exists but points   | Pointing to a non-matching object. Do  |
    |   Exists      | to some 'other'     | nothing but potentially log/warn of    |
    |               | object              | the discrepancy                        |
    +---------------+---------------------+----------------------------------------+
    """
    def setUp(self):
        self.external_system = ExternalSystem.objects.create(name='System')

    def test_it_creates_the_model_object(self):
        sut = CreateModelWithReferenceAction(
            self.external_system,
            TestPerson, 'PersonJohn', ['first_name'],
            {'first_name': 'John', 'last_name': 'Smith'})
        sut.execute()
        self.assertEqual(1, TestPerson.objects.count())

    def test_it_creates_the_reference(self):
        sut = CreateModelWithReferenceAction(
            self.external_system,
            TestPerson, 'PersonJohn', ['first_name'],
            {'first_name': 'John', 'last_name': 'Smith'})
        sut.execute()
        self.assertEqual(1, ExternalKeyMapping.objects.count())

    def test_it_creates_the_reference_if_the_model_object_already_exists(self):
        john = TestPerson.objects.create(first_name='John')
        sut = CreateModelWithReferenceAction(
            self.external_system,
            TestPerson, 'PersonJohn', ['first_name'],
            {'first_name': 'John', 'last_name': 'Smith'})
        sut.execute()
        self.assertEqual(1, TestPerson.objects.count())
        self.assertEqual(1, ExternalKeyMapping.objects.count())
        self.assertEqual(john, ExternalKeyMapping.objects.first().content_object)

    def test_it_updates_the_reference_if_the_model_does_not_exist(self):
        mapping = ExternalKeyMapping.objects.create(
            external_system=self.external_system,
            external_key='PersonJohn',
            content_type=ContentType.objects.get_for_model(TestPerson),
            object_id=0)
        sut = CreateModelWithReferenceAction(
            self.external_system,
            TestPerson, 'PersonJohn', ['first_name'],
            {'first_name': 'John', 'last_name': 'Smith'})
        sut.execute()
        self.assertEqual(1, ExternalKeyMapping.objects.count())
        mapping.refresh_from_db()
        self.assertNotEqual(None, mapping.content_object)

    def test_it_does_not_create_model_object_if_reference_is_linked_to_model(self):
        """
        A model object should not be created if an external key mapping
        exists, even if the mapping and the match fields do not agree.
        """
        # create a reference & model objet
        CreateModelWithReferenceAction(
            self.external_system,
            TestPerson, 'PersonJohn', ['first_name'],
            {'first_name': 'John', 'last_name': 'Smith'}).execute()

        # Attempt to create another object with different data but same external key
        CreateModelWithReferenceAction(
            self.external_system,
            TestPerson, 'PersonJohn', ['first_name'],
            {'first_name': 'David', 'last_name': 'Jones'}).execute()

        linked_person = ExternalKeyMapping.objects.first().content_object
        self.assertEqual('John', linked_person.first_name)
        self.assertEqual('Smith', linked_person.last_name)
        self.assertEqual(1, TestPerson.objects.count())
        self.assertEqual(1, ExternalKeyMapping.objects.count())


class TestUpdateModelAction(TestCase):
    def test_it_returns_the_object_even_if_nothing_updated(self):
        john = TestPerson.objects.create(first_name='John')
        sut = UpdateModelAction(TestPerson, ['first_name'],
                                {'first_name': 'John'})
        result = sut.execute()
        self.assertEquals(john, result)

    def test_it_returns_nothing_if_object_does_not_exist(self):
        sut = UpdateModelAction(TestPerson, ['first_name'],
                                {'first_name': 'John', 'last_name': 'Smith'})
        result = sut.execute()
        self.assertIsNone(result)

    def test_it_updates_model_with_new_values(self):
        john = TestPerson.objects.create(first_name='John')
        self.assertEqual('', john.last_name)

        sut = UpdateModelAction(TestPerson, ['first_name'],
                                {'first_name': 'John', 'last_name': 'Smith'})
        sut.execute()
        john.refresh_from_db()
        self.assertEquals('Smith', john.last_name)

    # TODO Review this behaviour?
    def test_including_extra_parameters_has_no_effect(self):
        john = TestPerson.objects.create(first_name='John')
        sut = UpdateModelAction(
            TestPerson,
            ['first_name'],
            {'first_name': 'John',
             'totally_never_going_to_be_a_field': 'Smith'})
        result = sut.execute()
        self.assertEquals(john, result)

    def test_it_forces_updates_when_configured(self):
        john = TestPerson.objects.create(first_name='John', last_name='Smith')
        sut = UpdateModelAction(TestPerson, ['first_name'],
                                {'first_name': 'John', 'last_name': 'Jackson'},
                                True)
        sut.execute()
        john.refresh_from_db()
        self.assertEquals('Jackson', john.last_name)


class TestUpdateModelWithReferenceAction(TestCase):
    """
    These tests try to cover off the following matrix of behaviour:
    +---------------+---------------------+----------------------------------------+
    | Model object  |   External Link     | Behaviour / Outcome desired            |
    +---------------+---------------------+----------------------------------------+
    |      No       |      No             | Do nothing. No effect for update       |
    +------------------------------------------------------------------------------+
    |               |                     | Do normal update.                      |
    |    Exists     |      No             | Create linkage object.                 |
    +------------------------------------------------------------------------------+
    |               |                     | !!! Should probably not happen !!!     |
    |     No        |     Exists          | Do nothing.                            |
    |               |                     | (Possibly remove link?)                |
    +------------------------------------------------------------------------------+
    |   Exists      | Exists, points  to  | Do normal update.                      |
    |               |  matching object    | NOT TESTED                             |
    +------------------------------------------------------------------------------+
    |               | Exists but points   | This case is tricky.                   |
    |   Exists      | to some 'other'     | Do the update normally, obeying force  |
    |               | object              | option.                                |
    |               |                     | IF there is also a matching object (   |
    |               |                     | that is not the linked object), not    |
    |               |                     | sure what to do, for now delete the    |
    |               |                     | non-linked object.                     |
    +---------------+---------------------+----------------------------------------+
    """
    def setUp(self):
        self.external_system = ExternalSystem.objects.create(name='System')
        self.update_john = UpdateModelWithReferenceAction(
            self.external_system,
            TestPerson, 'PersonJohn', ['first_name'],
            {'first_name': 'John', 'last_name': 'Smith'},
            True)

    def test_it_does_not_create_a_reference_if_object_does_not_exist(self):
        self.update_john.execute()
        self.assertEqual(0, ExternalKeyMapping.objects.count())

    def test_it_updates_the_object(self):
        john = TestPerson.objects.create(first_name='John')
        self.update_john.execute()
        john.refresh_from_db()
        self.assertEqual(john.first_name, 'John')
        self.assertEqual(john.last_name, 'Smith')

    def test_it_creates_the_reference_if_the_model_object_already_exists(self):
        john = TestPerson.objects.create(first_name='John')
        self.update_john.execute()
        self.assertEqual(1, ExternalKeyMapping.objects.count())
        mapping = ExternalKeyMapping.objects.first()
        self.assertEqual(self.external_system, mapping.external_system)
        self.assertEqual('PersonJohn', mapping.external_key)
        self.assertEqual(john, mapping.content_object)

    def test_it_updates_the_linked_object(self):
        """
        Tests that even if the match field does not 'match', the already
        pointed to object is updated.
        """
        person = TestPerson.objects.create(first_name='Not John')
        mapping = ExternalKeyMapping.objects.create(
            external_system=self.external_system,
            external_key='PersonJohn',
            content_type = ContentType.objects.get_for_model(
                TestPerson),
            content_object = person,
            object_id = person.id)

        self.update_john.execute()
        person.refresh_from_db()
        self.assertEqual(person.first_name, 'John')
        self.assertEqual(person.last_name, 'Smith')

    def test_it_removes_the_matched_object_if_there_is_a_linked_object(self):
        """
        Tests that if there is a 'linked' object to update, it removes any
        'matched' objects in the process.
        In this test, the "John Jackson" person should be deleted and the 
        "Not John" person should be updated to be "John Smith"
        """
        matched_person = TestPerson.objects.create(first_name='John',
                                                   last_name='Jackson')
        linked_person = TestPerson.objects.create(first_name='Not John')
        mapping = ExternalKeyMapping.objects.create(
            external_system=self.external_system,
            external_key='PersonJohn',
            content_type = ContentType.objects.get_for_model(
                TestPerson),
            content_object = linked_person,
            object_id = linked_person.id)

        self.update_john.execute()
        self.assertEqual(1, TestPerson.objects.count())
        person = TestPerson.objects.first()
        self.assertEqual(person.first_name, 'John')
        self.assertEqual(person.last_name, 'Smith')

    def test_it_only_deletes_the_matched_object_if_it_is_not_the_linked_object(self):
        """
        Tests that if there are both a linked and matched object (which is the
        standard case!!!), the matched_object is only removed if it is actually
        a different object.
        """
        person = TestPerson.objects.create(first_name='John',
                                                   last_name='Jackson')
        house = TestHouse.objects.create(address='Bottom of the hill',
                                         owner=person)
        mapping = ExternalKeyMapping.objects.create(
            external_system=self.external_system,
            external_key='PersonJohn',
            content_type = ContentType.objects.get_for_model(
                TestPerson),
            content_object = person,
            object_id = person.id)

        with patch.object(self.update_john, 'get_object') as get_object:
            get_object.return_value.return_value = person
            with patch.object(person, 'delete') as delete:
                self.update_john.execute()
                delete.assert_not_called()


class TestDeleteModelAction(TestCase):
    def test_no_objects_are_deleted_if_none_are_matched(self):
        john = TestPerson.objects.create(first_name='John')
        DeleteModelAction(TestPerson, ['first_name'],
                          {'first_name': 'A non-matching name'}).execute()
        self.assertIn(john, TestPerson.objects.all())

    def test_only_objects_with_matching_fields_are_deleted(self):
        TestPerson.objects.create(first_name='John')
        TestPerson.objects.create(first_name='Jack')
        TestPerson.objects.create(first_name='Jill')
        self.assertEqual(3, TestPerson.objects.count())

        DeleteModelAction(TestPerson, ['first_name'],
                          {'first_name': 'Jack'}).execute()
        self.assertFalse(TestPerson.objects.filter(first_name='Jack').exists())


class TestDeleteIfOnlyReferenceModelAction(TestCase):
    def setUp(self):
        self.external_system = ExternalSystem.objects.create(name='System')

    def test_it_does_nothing_if_object_does_not_exist(self):
        delete_action = MagicMock()
        delete_action.get_object.side_effect = ObjectDoesNotExist
        DeleteIfOnlyReferenceModelAction(ANY, ANY, delete_action).execute()
        delete_action.get_object.assert_called_with()
        self.assertFalse(delete_action.execute.called)

    def test_it_does_nothing_if_no_key_mapping_is_found(
            self):
        john = TestPerson.objects.create(first_name='John')
        delete_action = MagicMock()
        delete_action.model = TestPerson
        delete_action.get_object.return_value = john
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
        delete_action.get_object.return_value = john
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
        delete_action.get_object.return_value = john
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
        delete_action.get_object.return_value = john
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


class TestActionTypes(TestCase):
    def test_model_action_returns_empty_string_for_type(self):
        self.assertEquals('', ModelAction(ANY, ['field'], {'field': ''}).type)

    def test_create_model_action_returns_correct_type_string(self):
        self.assertEquals('create',
                          CreateModelAction(ANY, ['field'], {'field': ''}).type)

    def test_update_model_action_returns_correct_type_string(self):
        self.assertEquals('update',
                          UpdateModelAction(ANY, ['field'], {'field': ''}).type)

    def test_delete_model_action_returns_correct_type_string(self):
        self.assertEquals('delete',
                          DeleteModelAction(ANY, ['field'], {'field': ''}).type)

    def test_delete_if_only_reference_model_action_returns_wrapped_action_type(
            self):
        delete_action = MagicMock()
        sut = DeleteIfOnlyReferenceModelAction(ANY, ANY, delete_action)
        self.assertEqual(delete_action.type, sut.type)

    def test_delete_external_reference_action_returns_correct_type_string(
            self):
        self.assertEquals('delete',
                          DeleteExternalReferenceAction(ANY, ANY).type)

        
