from django.contrib.contenttypes.fields import ContentType
from django.test import TestCase
from nsync.models import ExternalSystem, ExternalKeyMapping

from tests.models import TestPerson


class TestExternalSystem(TestCase):
    def test_it_uses_name_for_string(self):
        self.assertEqual('SystemName', str(ExternalSystem(name='SystemName')))

    def test_it_returns_the_description_instead_of_name_if_available(
            self):
        sut = ExternalSystem(name='SystemName',
                             description='SystemDescription')
        self.assertEqual('SystemDescription', str(sut))


class TestExternalKeyMapping(TestCase):
    def setUp(self):
        self.external_system = ExternalSystem.objects.create(
            name='ExternalSystemName')

    def test_it_returns_as_useful_string(self):
        john = TestPerson.objects.create(first_name='John')
        content_type = ContentType.objects.get_for_model(TestPerson)
        sut = ExternalKeyMapping(
            external_system=self.external_system,
            external_key='Person123',
            content_type=content_type,
            content_object=john,
            object_id=john.id)

        result = str(sut)
        self.assertIn('ExternalSystemName', result)
        self.assertIn('Person123', result)
        self.assertIn(content_type.model_class().__name__, result)
        self.assertIn(str(john.id), result)
