from django.core.exceptions import (
    MultipleObjectsReturned,
    ObjectDoesNotExist,
    FieldDoesNotExist)
from django.contrib.contenttypes.fields import ContentType
from .models import ExternalKeyMapping
from collections import defaultdict
import logging

"""
NSync actions for updating Django models

This module contains the available actions for performing synchronisations.
These include the basic Create / Update / Delete for model object, as well
as the actions for managing the ExternalKeyMapping objects, to record the
identification keys used by external systems for internal objects.

It is recommended to use the ActionFactory.build() method to create actions
from raw input.
"""

logger = logging.getLogger(__name__)


class ModelAction:
    """
    The base action, which performs makes no modifications to objects.

    This class consolidates the some of the validity checking and the logic
    for finding the target objects.
    """
    REFERRED_TO_DELIMITER = '=>'

    def __init__(self, model, match_field_name, fields={}):
        """
        Create a base action.

        :param model:
        :param match_field_name:
        :param fields:
        :return:
        """
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
        """Finds all objects that match the provided matching information"""
        filter_by = {self.match_field_name: self.fields[self.match_field_name]}
        return self.model.objects.filter(**filter_by)

    def execute(self):
        """Does nothing"""
        pass

    def update_from_fields(self, object, force=False):
        """
        Update the provided object with the fields.

        This is implemented in a consolidated place, as both Create and
        Update style actions require the functionality.

        :param object: the object to update
        :param force (bool): (Optional) Whether the update should only
        affect 'empty' fields. Default: False
        :return:
        """
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
                field = object._meta.get_field(attribute)
                # For migration advice of the get_field_by_name() call see [1]
                # [1]: https://docs.djangoproject.com/en/1.9/ref/models/meta/#migrating-old-meta-api

                if (not field.auto_created or field.concrete) \
                        and field.related_model:
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
    """
    Action to create a model object if it does not exist.

    Note, this will not create another object if a matching one is
    found, nor will it update a matched object.
    """

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
    """
    Action to update the fields of a model object, but not create an
    object.
    """

    def __init__(self, model, match_field_name, fields={}, force_update=False):
        """
        Create an Update action to be executed in the future.

        :param model (class): The model to update against
        :param match_field_name (str): The name of a model attribute/field
        to use to find the object to update. This must be a key in the
        provided fields.
        :param fields(dict): The set of fields to update, with the values to
        update them to.
        :param force_update(bool): (Optional) Whether the update should be
        forced or only affect 'empty' fields. Default:False
        :return: The updated object (if a matching object is found) or None.
        """
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
    """
    This action only deletes the pointed to object if the key mapping
    corresponding to 'this' external key it the only one

    I.e. if there are two references from different external systems to the
    same object, then the object will not be deleted.
    """

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
        """Forcibly delete any objects found by the
        ModelAction.find_objects() method."""
        self.find_objects().delete()


class AlignExternalReferenceAction:
    """
    A model action to create or update an ExternalKeyMapping object for the
    corresponding model object.

    This creates or updates (if it already exists) an ExternalKeyMapping object
    that is linked to the object returned by the action it is built with.
    """

    def __init__(self, external_system, model, external_key, action):
        """
        Create an alignment action that can be executed in the future.

        :param external_system (model object): The external system to create or
            update the reference for.
        :param model (class): The model class the reference should be created
            or updated for.
        :param external_key (str): The reference value from the external
            system (i.e. the 'id' that the external system uses to refer to the
            model object).
        :param action (ModelAction): The action that will be peformed and that
            will provide the model object to create the reference to.
        :return: The model object provided by the action
        """
        self.external_system = external_system
        self.external_key = external_key
        self.model = model
        self.action = action

    @property
    def type(self):
        return self.action.type

    def execute(self):
        """
        Executes the provided action and then creates or updates an
        ExternalKeyMapping to point to the result of the action (if the
        action returned a model object)
        :return:
        """
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
    """
    A model action to remove the ExternalKeyMapping object for a model object.
    """

    def __init__(self, external_system, external_key):
        self.external_system = external_system
        self.external_key = external_key

    @property
    def type(self):
        return 'delete'

    def execute(self):
        """
        Deletes all ExternalKeyMapping objects that match the provided external
        system and external key.
        :return: Nothing
        """
        ExternalKeyMapping.objects.filter(
            external_system=self.external_system,
            external_key=self.external_key).delete()


class ActionFactory:
    """
    A factory for producing the most appropriate (set of) ModelAction objects.

    The factory takes care of creating the correct actions in the instances
    where it is a little complicated. In particular, when there are unforced
    delete actions.

    In the case of unforced delete actions, the builder will create a
    DeleteIfOnlyReferenceModelAction. This action will only delete the
    underlying model if there is a single link to the object to be deleted
    AND it is a link from the same system.

     Example 1:

       1. Starting State
       -----------------
       ExtSys 1 - Mapping 1 (Id: 123) --+
                                        |
                                        v
                            Model Object (Person: John)
                                        ^
                                        |
       ExtSys 2 - Mapping 1 (Id: AABB) -+


       2. DeleteIfOnlyReferenceModelAction(ExtSys 2, AABB, DeleteAction(John))
       -----------------------------------------------------------------------
        Although there was a 'delete John' action, it was not performed
        because there is another system with a link to John.

     Example 2:

       1. Starting State
       -----------------
       ExtSys 1 - Mapping 1 (Id: 123) --+
                                        |
                                        v
                            Model Object (Person: John)

       2. DeleteIfOnlyReferenceModelAction(ExtSys 2, AABB, DeleteAction(John))
       -----------------------------------------------------------------------
        Although there was only a single reference, it is not for ExtSys 2,
        hence the delete is not performed.

    The builder will also include a DeleteExternalReferenceAction if the
    provided action is 'externally mappable'. These will always be executed
    and will ensure that the reference objects will be removed by their
    respective sync systems (and that if they all work correctly the last
    one will be able to delete the object).
    """

    def __init__(self, model, external_system=None):
        """
        Create an actions factory for a given Django Model.

        :param model: The model to use for the actions
        :param external_system: (Optional) The external system object to
            create links against
        :return: A new actions factory
        """
        self.model = model
        self.external_system = external_system

    def is_externally_mappable(self, external_key):
        """
        Check if the an 'external system mapping' could be created for the
        provided key.
        :param external_key:
        :return:
        """
        if self.external_system is None:
            return False

        if external_key is None:
            return False

        if not isinstance(external_key, str):
            return False

        return external_key.strip() is not ''

    def build(self, sync_actions, match_field_name, external_system_key,
              fields):
        """
        Builds the list of actions to satisfy the provided information.

        This includes correctly building any actions required to keep the
        external system references correctly up to date.

        :param sync_actions:
        :param match_field_name:
        :param external_system_key:
        :param fields:
        :return:
        """
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


class SyncActions:
    """
    A holder object for the actions that can be requested against a model
    object concurrently.
    """

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
