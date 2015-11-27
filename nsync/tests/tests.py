from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist, FieldError
from django.core.management.base import CommandError
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from unittest.mock import MagicMock, patch, ANY
from nsync.models import ExternalSystem, ExternalKeyMapping, ExternalReferenceHandler
from nsync.sync import SyncRecord
from .models import TestPerson, TestHouse


class TestExternalReferenceHandler(TestCase):
    def test_get_or_construct_key_mapping_returns_none_if_record_is_not_externally_mappable(self):
        unmappable_record = MagicMock()
        unmappable_record.is_externally_mappable.return_value = False
        self.assertEqual((None, False), ExternalReferenceHandler.get_or_construct_key_mapping(None, unmappable_record))

    @patch('nsync.models.ExternalKeyMapping')
    def test_get_or_construct_key_mapping_returns_unsaved_external_key_mapping_object_if_not_found(self, ExternalKeyMapping):
        external_system = MagicMock()
        mappable_record = MagicMock()
        mappable_record.is_externally_mappable.return_value = True
        ExternalKeyMapping.DoesNotExist = Exception
        ExternalKeyMapping.objects.get.side_effect = ExternalKeyMapping.DoesNotExist
        key_mapping_mock = MagicMock()
        ExternalKeyMapping.return_value = key_mapping_mock

        key_mapping,constructed = ExternalReferenceHandler.get_or_construct_key_mapping(external_system, mappable_record)
        self.assertTrue(constructed)
        self.assertEqual(key_mapping, key_mapping_mock)
        ExternalKeyMapping.assert_called_with(
                external_system=external_system,
                external_key=mappable_record.external_key)
        # TODO review, probably don't need this assertion
        ExternalKeyMapping.objects.get.assert_called_with(
                external_system=external_system, 
                external_key=mappable_record.external_key)
    
    def test_get_or_construct_key_mapping_returns_existing_if_found(self):
        obj = TestPerson.objects.create()
        existing = ExternalKeyMapping.objects.create(
                external_system=self.external_system,
                external_key='1',
                object_id=obj.id,
                content_object=obj,
                content_type=ContentType.objects.get_for_model(TestPerson))
        self.assertEqual((existing, False), ExternalReferenceHandler.get_or_construct_key_mapping(self.external_system,
                SyncRecord('1', None, 'field', field="")))

    def test_get_model_object_returns_unsaved_empty_object_if_no_match(self):
        model_class = MagicMock()
        model_class.objects.get.side_effect = ObjectDoesNotExist

        (model_obj, contructed) = ExternalReferenceHandler.get_model_object(model_class, "", "")
        model_class.assert_called_with()
        self.assertEqual(model_obj, model_class.return_value)

    def test_get_model_object_raises_exception_if_mulitple_found(self):
        # TODO check this test, it is a bit bad
        model_class = MagicMock()
        model_class.objects.get.side_effect = MultipleObjectsReturned
        with self.assertRaises(MultipleObjectsReturned):
            ExternalReferenceHandler.get_model_object(model_class, '', '')

    def test_get_model_object_calls_with_correct_field_matching_arguments(self):
        model_class = MagicMock()

        ExternalReferenceHandler.get_model_object(model_class, "name", "value")
        model_class.objects.get.assert_called_with(name='value')

    def test_get_model_object_returns_existing_object_on_match(self):
        existing_model = TestPerson.objects.create(first_name='Name')
        self.assertEqual((existing_model, False),
                         ExternalReferenceHandler.get_model_object(
            TestPerson, 'first_name', 'Name'))

    def test_get_model_object_raises_exception_if_model_does_not_have_match_field(self):
        with self.assertRaises(FieldError):
            sync_record = SyncRecord(None, None, 'bogus_field', bogus_field='')
            ExternalReferenceHandler.create_or_update_for_sync_record(ExternalSystem(), TestPerson, sync_record)

    def test_new_model_object_is_created_if_not_already_present(self):
        self.assertEqual(0, TestPerson.objects.count())
        sync_record = SyncRecord(None, None, 'first_name', first_name='')
        ExternalReferenceHandler.create_or_update_for_sync_record(ExternalSystem(), TestPerson, sync_record)

        self.assertEqual(1, TestPerson.objects.count())

    def test_model_object_not_created_if_matching_object_already_present(self):
        TestPerson.objects.create(first_name='Name')
        self.assertEqual(1, TestPerson.objects.count())

        sync_record = SyncRecord(None, None, 'first_name', first_name='Name')
        ExternalReferenceHandler.create_or_update_for_sync_record(ExternalSystem(), TestPerson, sync_record)
        self.assertEqual(1, TestPerson.objects.count())

    def test_new_model_object_has_all_provided_fields(self):
        sync_record = SyncRecord(None, None, 'first_name', 
                first_name='Name', last_name='Last', age=15)
        ExternalReferenceHandler.create_or_update_for_sync_record(ExternalSystem(), TestPerson, sync_record)

        person = TestPerson.objects.first()
        self.assertEqual('Name', person.first_name)
        self.assertEqual('Last', person.last_name)
        self.assertEqual(15, person.age)

    def test_only_provided_fields_are_updated_on_existing_model_object(self):
        TestPerson.objects.create(first_name='Name', last_name='Before', age=15)
        sync_record = SyncRecord(None, None, 'first_name', 
                first_name='Name', last_name='After')
        ExternalReferenceHandler.create_or_update_for_sync_record(ExternalSystem(), TestPerson, sync_record)

        person = TestPerson.objects.first()
        self.assertEqual('Name', person.first_name)
        self.assertEqual('After', person.last_name)
        self.assertEqual(15, person.age)

    def setUp(self):
        self.external_system = ExternalSystem.objects.create(label='Sys')

    def test_key_mapping_is_created_if_mappable_and_not_already_present(self):
        self.assertEqual(0, ExternalKeyMapping.objects.count())
        sync_record = SyncRecord('1', None, 'first_name', first_name='')
        ExternalReferenceHandler.create_or_update_for_sync_record(self.external_system, TestPerson, sync_record)

        self.assertEqual(1, ExternalKeyMapping.objects.count())

    @patch('nsync.models.logger')
    def test_warning_logged_if_existing_mapping_model_does_not_fulfil_matching(self, logger):
        mapped_to_person = TestPerson.objects.create()
        matched_person = TestPerson.objects.create(first_name='Person2')
        existing = ExternalKeyMapping.objects.create(
                external_system=self.external_system,
                external_key='1',
                object_id=mapped_to_person.id,
                content_object=mapped_to_person,
                content_type=ContentType.objects.get_for_model(TestPerson))

        sync_record = SyncRecord('1', None, 'first_name', first_name='Person2')
        ExternalReferenceHandler.create_or_update_for_sync_record(self.external_system, TestPerson, sync_record)
        logger.warning.assert_called_with(ANY)

    @patch('nsync.models.logger')
    def test_related_fields_are_not_touched_if_referred_to_object_does_not_exist(self, logger):
        house = TestHouse.objects.create(address='Bottom of the hill')
        fields = {'address':'Bottom of the hill', 'owner=>last_name':'Jones'}
        sync_record = SyncRecord('1', None, 'address', **fields)
        ExternalReferenceHandler.create_or_update_for_sync_record(
                self.external_system, TestHouse, sync_record)

        house.refresh_from_db()
        self.assertEqual(None, house.owner)
        logger.info.assert_called_with(ANY)

    @patch('nsync.models.logger')
    def test_related_fields_are_not_touched_if_referred_to_object_ambiguous(self, logger):
        TestPerson.objects.create(first_name="Jill", last_name="Jones")
        TestPerson.objects.create(first_name="Jack", last_name="Jones")
        house = TestHouse.objects.create(address='Bottom of the hill')
        fields = {'address':'Bottom of the hill', 'owner=>last_name':'Jones'}
        sync_record = SyncRecord('1', None, 'address', **fields)
        ExternalReferenceHandler.create_or_update_for_sync_record(
                self.external_system, TestHouse, sync_record)

        house.refresh_from_db()
        self.assertEqual(None, house.owner)
        logger.info.assert_called_with(ANY)
        
    def test_related_fields_are_updated_with_referred_to_object(self):
        person = TestPerson.objects.create(first_name="Jill", last_name="Jones")
        house = TestHouse.objects.create(address='Bottom of the hill')
        fields = {'address':'Bottom of the hill', 'owner=>first_name':'Jill'}
        sync_record = SyncRecord('1', None, 'address', **fields)
        ExternalReferenceHandler.create_or_update_for_sync_record(
                self.external_system, TestHouse, sync_record)

        house.refresh_from_db()
        self.assertEqual(person, house.owner)

    def test_related_fields_update_uses_all_available_filters(self):
        person = TestPerson.objects.create(first_name="John", last_name="Johnson")
        TestPerson.objects.create(first_name="Jack", last_name="Johnson")
        TestPerson.objects.create(first_name="John", last_name="Jackson")
        TestPerson.objects.create(first_name="Jack", last_name="Jackson")

        house = TestHouse.objects.create(address='Bottom of the hill')
        fields = {
                'address':'Bottom of the hill', 
                'owner=>first_name':'John',
                'owner=>last_name':'Johnson'}
        sync_record = SyncRecord('1', None, 'address', **fields)
        ExternalReferenceHandler.create_or_update_for_sync_record(
                self.external_system, TestHouse, sync_record)

        house.refresh_from_db()
        self.assertEqual(person, house.owner)
        
