from django.core.exceptions import (
    MultipleObjectsReturned,
    ObjectDoesNotExist,
    FieldDoesNotExist)
from django.contrib.contenttypes.fields import ContentType

from .models import ExternalKeyMapping

from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class ModelAction:
    REFERRED_TO_DELIMITER = '=>'

    def __init__(self, model, match_field_name, fields={}):
        if model is None:
            raise ValueError('model cannot be None')
        if not match_field_name:
            raise ValueError('match_field_name({}) must be not "empty"'.format(
                match_field_name))
        if match_field_name not in fields:
            raise ValueError('match_field_name({}) must be in fields'.format(
                match_field_name))

        self.model = model
        self.match_field_name = match_field_name
        self.fields = fields

    def __str__(self):
        return 'Action {} - Model:{} - MatchField:{} - Fields:{}'.format(
            self.__class__,
            self.model,
            self.match_field_name,
            self.fields)

    @property
    def type(self):
        return ''

    def find_objects(self):
        filter_by = {self.match_field_name: self.fields[self.match_field_name]}
        return self.model.objects.filter(**filter_by)

    def execute(self):
        pass

    def update_from_fields(self, object, force=False):
        # we need to support referential attributes, so look for them
        # as we iterate and store them for later

        # We store the referential attributes as a dict of dicts, this way
        # filtering against many fields is possible
        referential_attributes = defaultdict(dict)
        for attribute, value in self.fields.items():
            if self.REFERRED_TO_DELIMITER in attribute:
                ref_attr = attribute.split(self.REFERRED_TO_DELIMITER)
                referential_attributes[ref_attr[0]][ref_attr[1]] = value
            else:
                if not force:
                    current_value = getattr(object, attribute, None)
                    if not (current_value is None or current_value is ''):
                        continue
                setattr(object, attribute, value)

        for attribute, get_by in referential_attributes.items():
            try:
                (field, field_model, direct,  m2m) = \
                    object._meta.get_field_by_name(attribute)
                if direct and field.related_model:
                    if not force:
                        current_value = getattr(object, attribute, None)
                        if current_value is not None:
                            continue

                    try:
                        target = field.related_model.objects.get(**get_by)
                        setattr(object, attribute, target)
                    except ObjectDoesNotExist as e:
                        logger.info('Referred to object not found')
                    except MultipleObjectsReturned as e:
                        logger.info(
                            'Referred to object points to multiple objects')
            except FieldDoesNotExist as e:
                logger.debug('Field does not exist', e)


class CreateModelAction(ModelAction):
    def execute(self):
        if self.find_objects().exists():
            # already exists, return None
            return self.find_objects().get()

        obj = self.model()
        # NB: Create uses force to override defaults
        self.update_from_fields(obj, True)
        obj.save()
        return obj

    @property
    def type(self):
        return 'create'


class UpdateModelAction(ModelAction):
    def __init__(self, model, match_field_name, fields={}, force_update=False):
        super(UpdateModelAction, self).__init__(
            model, match_field_name, fields)
        self.force_update = force_update

    @property
    def type(self):
        return 'update'

    def execute(self):
        try:
            obj = self.find_objects().get()
            self.update_from_fields(obj, self.force_update)
            obj.save()

            return obj
        except ObjectDoesNotExist:
            return None


class DeleteIfOnlyReferenceModelAction(ModelAction):
    """This action only deletes the pointed to object if the key mapping
       corresponding to 'this' external key it the only one"""
    def __init__(self, external_system, external_key, delete_action):
        self.delete_action = delete_action
        self.external_key = external_key
        self.external_system = external_system

    @property
    def type(self):
        return self.delete_action.type

    def execute(self):
        try:
            obj = self.delete_action.find_objects().get()

            key_mapping = ExternalKeyMapping.objects.get(
                object_id=obj.id,
                content_type=ContentType.objects.get_for_model(
                    self.delete_action.model),
                external_key=self.external_key)

            if key_mapping.external_system == self.external_system:
                self.delete_action.execute()
            else:
                # The key mapping is not 'this' systems key mapping
                pass
        except MultipleObjectsReturned:
            # There are multiple key mappings, we shouldn't delete the object
            return
        except ObjectDoesNotExist:
            return


class DeleteModelAction(ModelAction):
    @property
    def type(self):
        return 'delete'

    def execute(self):
        self.find_objects().delete()


class AlignExternalReferenceAction:
    def __init__(self, external_system, model, external_key, action):
        self.external_system = external_system
        self.external_key = external_key
        self.model = model
        self.action = action

    @property
    def type(self):
        return self.action.type

    def execute(self):
        model_obj = self.action.execute()

        if model_obj:
            try:
                mapping = ExternalKeyMapping.objects.get(
                    external_system=self.external_system,
                    external_key=self.external_key)
            except ExternalKeyMapping.DoesNotExist:
                mapping = ExternalKeyMapping(
                    external_system=self.external_system,
                    external_key=self.external_key)
            mapping.content_type = ContentType.objects.get_for_model(
                self.model)
            mapping.content_object = model_obj
            mapping.object_id = model_obj.id
            mapping.save()

        return model_obj


class DeleteExternalReferenceAction:
    def __init__(self, external_system, external_key):
        self.external_system = external_system
        self.external_key = external_key

    @property
    def type(self):
        return 'delete'

    def execute(self):
        ExternalKeyMapping.objects.filter(
            external_system=self.external_system,
            external_key=self.external_key).delete()


class ActionsBuilder:
    def __init__(self, model, external_system=None):
        self.model = model
        self.external_system = external_system

    def is_externally_mappable(self, external_key):
        if self.external_system is None:
            return False

        if external_key is None:
            return False

        if not isinstance(external_key, str):
            return False

        return external_key.strip() is not ''

    def build(self, sync_actions, match_field_name, external_system_key,
              fields):
        actions = []

        if sync_actions.is_impotent():
            actions.append(ModelAction(self.model, match_field_name, fields))

        if sync_actions.delete:
            action = DeleteModelAction(self.model, match_field_name, fields)
            if self.is_externally_mappable(external_system_key):
                if not sync_actions.force:
                    action = DeleteIfOnlyReferenceModelAction(
                        self.external_system, external_system_key, action)
                actions.append(action)
                actions.append(DeleteExternalReferenceAction(
                    self.external_system, external_system_key))
            elif sync_actions.force:
                actions.append(action)

        if sync_actions.create:
            action = CreateModelAction(self.model, match_field_name, fields)
            if self.is_externally_mappable(external_system_key):
                action = AlignExternalReferenceAction(self.external_system,
                                                      self.model,
                                                      external_system_key,
                                                      action)
            actions.append(action)
        if sync_actions.update:
            action = UpdateModelAction(self.model, match_field_name,
                                       fields, sync_actions.force)
            if self.is_externally_mappable(external_system_key):
                action = AlignExternalReferenceAction(self.external_system,
                                                      self.model,
                                                      external_system_key,
                                                      action)

            actions.append(action)

        return actions


class CsvActionsBuilder(ActionsBuilder):
    action_flags_label = 'action_flags'
    match_field_name_label = 'match_field_name'
    external_key_label = 'external_key'

    def from_dict(self, raw_values):
        if not raw_values:
            return []

        action_flags = raw_values.pop(self.action_flags_label)
        match_field_name = raw_values.pop(self.match_field_name_label)
        external_system_key = raw_values.pop(self.external_key_label, None)

        sync_actions = CsvSyncActionsDecoder.decode(action_flags)

        return self.build(sync_actions, match_field_name,
                          external_system_key, raw_values)


class SyncActions:
    def __init__(self, create=False, update=False, delete=False, force=False):
        if delete and create:
            raise ValueError("Cannot delete AND create")
        if delete and update:
            raise ValueError("Cannot delete AND update")

        self.create = create
        self.update = update
        self.delete = delete
        self.force = force

    def __str__(self):
        return "SyncActions {}{}{}{}".format(
            'c' if self.create else '',
            'u' if self.update else '',
            'd' if self.delete else '',
            '*' if self.force else '')

    def is_impotent(self):
        return not (self.create or self.update or self.delete)


class CsvSyncActionsEncoder:
    @staticmethod
    def encode(sync_actions):
        return '{}{}{}{}'.format(
            'c' if sync_actions.create else '',
            'u' if sync_actions.update else '',
            'd' if sync_actions.delete else '',
            '*' if sync_actions.force else '')


class CsvSyncActionsDecoder:
    @staticmethod
    def decode(action_flags):
        create = False
        update = False
        delete = False
        force = False

        if action_flags:
            try:
                create = 'C' in action_flags or 'c' in action_flags
                update = 'U' in action_flags or 'u' in action_flags
                delete = 'D' in action_flags or 'd' in action_flags
                force = '*' in action_flags
            except TypeError:
                # not iterable
                pass

        return SyncActions(create, update, delete, force)
