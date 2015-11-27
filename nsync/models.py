from collections import defaultdict

from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist, FieldDoesNotExist
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

import logging

logger = logging.getLogger(__name__)

class ExternalSystem(models.Model):
    """
    Computer systems that integration occurs against
    """
    label = models.CharField(
        blank = False,
        db_index = True,
        help_text = """A short label, used by software applications 
                       to locate this particular External System.
                    """,
        max_length = 30,
        unique = True,
    )
    name = models.CharField(
        blank = True,
        help_text = 'A human readable name for this External System.', 
        max_length = 80,
    )

    class Meta:
        verbose_name = 'External System'

    def __str__(self):
        return self.name if self.name else self.label


class ExternalKeyMapping(models.Model):
    """
    Key Mappings for objects in our system to objects in external systems
    """
    # limit = models.Q(app_label = 'siteassets', model = 'person') | \
    #         models.Q(app_label = 'siteassets', model = 'equipment')
    content_type = models.ForeignKey(ContentType,
        help_text = 'The type of object that is mapped to the external system.',
        # limit_choices_to = limit
    )
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    external_system = models.ForeignKey(ExternalSystem)
    external_key = models.CharField(
        blank = False,
        help_text = 'The key of the internal object in the external system.',
        max_length = 80,
    )

    class Meta:
        index_together = ('external_system', 'external_key')
        unique_together = ('external_system', 'external_key')
        verbose_name = 'External Key Mapping'

    def __str__(self):
        return "%s:%s" % (self.external_system.label, self.external_key)


class ExternalReferenceHandler:
    REFERRED_TO_DELIMITER = '=>'

    @staticmethod
    def get_or_construct_key_mapping(external_system, record):
        if not record.is_externally_mappable():
            return (None, False)

        try:
            existing = ExternalKeyMapping.objects.get(
                external_system=external_system,
                external_key=record.external_key)
            return (existing, False)
        except ExternalKeyMapping.DoesNotExist:
            return (ExternalKeyMapping(
                        external_system=external_system,
                        external_key=record.external_key),
                        True)
        except MultipleObjectsReturned as e:
            # TODO log this error
            raise

    @staticmethod
    def get_model_object(model_cls, match_field_name, match_field_value):
        try:
            model_obj = model_cls.objects.get(**{match_field_name:match_field_value})
            return (model_obj, False)
        except ObjectDoesNotExist as e:
            return (model_cls(), True)
        except MultipleObjectsReturned as e:
            # TODO log this error
            raise

    @staticmethod
    def create_or_update_for_sync_record(external_system, model, record):
        (model_obj, model_constructed) = ExternalReferenceHandler.get_model_object(model,
                record.match_field_name,
                record.fields[record.match_field_name])

        # do the updating
        referential_attributes = defaultdict(dict)
        for attr, value in record.fields.items():
            if ExternalReferenceHandler.REFERRED_TO_DELIMITER in attr:
                split_attr = attr.split(ExternalReferenceHandler.REFERRED_TO_DELIMITER)
                referential_attributes[split_attr[0]][split_attr[1]] = value
            else:
                setattr(model_obj, attr, value)

        for attr, get_by in referential_attributes.items():
            try:
                (field, field_model, direct,  m2m) = model_obj._meta.get_field_by_name(attr)
                if direct and field.related_model:
                    try:
                        target = field.related_model.objects.get(**get_by)
                        setattr(model_obj, attr, target)
                    except ObjectDoesNotExist as e:
                        logger.info('Referred to object not found')
                    except MultipleObjectsReturned as e:
                        logger.info('Referred to object points to multiple objects')
            except FieldDoesNotExist as e:
                pass




        model_obj.save()

        if record.is_externally_mappable():
            (key_mapping, constructed) = ExternalReferenceHandler.get_or_construct_key_mapping(external_system, record)
            if not constructed:
                if key_mapping.object_id != model_obj.id:
                    logger.warning('Existing external key mapping points to model object id:{} vs this model object id:{}'.format(
                        key_mapping.object_id, model_obj.id
                    ))
                    logger.debug('This could be due to different systems having different delete_flags for the object   ')

            key_mapping.content_type = ContentType.objects.get_for_model(model)
            key_mapping.content_object = model_obj
            key_mapping.object_id = model_obj.id
            key_mapping.save()

    def delete_for_sync_record(external_system, model, record):
        if not record.delete:
            logger.error("A record not marked for deletion was passed?")
            return

        (model_obj, model_constructed) = ExternalReferenceHandler.get_model_object(model,
                record.match_field_name,
                record.fields[record.match_field_name])

        if not model_constructed:
            model_obj.delete()

        (key_mapping, key_mapping_constructed) = ExternalReferenceHandler.get_or_construct_key_mapping(external_system, record)
        if not key_mapping_constructed:
            key_mapping.delete()

