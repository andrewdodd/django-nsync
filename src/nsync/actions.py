from django import VERSION
from django.core.exceptions import (
    MultipleObjectsReturned,
    ObjectDoesNotExist,
    FieldDoesNotExist)
from django.contrib.contenttypes.fields import ContentType
from django.db.models.query_utils import Q
from .models import ExternalKeyMapping
from collections import defaultdict
import logging
from .logging import StyleAdapter

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
logger.addHandler(logging.NullHandler()) # http://pieces.openpolitics.com/2012/04/python-logging-best-practices/
logger = StyleAdapter(logger)

def set_value_to_remote(object, attribute, value):
    target_attr = getattr(object, attribute)
    if object._meta.get_field(attribute).one_to_one:
        if VERSION[0] == 1 and VERSION[1] < 9:
            target_attr = value
        else:
            target_attr.set(value)
    else:
        target_attr.add(value)

class DissimilarActionTypesError(Exception):

    def __init__(self, action_type1, action_type2, field_name, model_name):
        self.action_types = [action_type1, action_type2]
        self.field_name = field_name
        self.model_name = model_name

    def __str__(self):
        return 'Dissimilar action types[{}] for many-to-many field {} on model {}'.format(
            ','.join(self.action_types),
            self.field_name,
            self.model_name)

class UnknownActionType(Exception):

    def __init__(self, action_type,field_name, model_name):
        self.action_type = action_type
        self.field_name = field_name
        self.model_name = model_name

    def __str__(self):
        return 'Unknown action type[{}] for many-to-many field {} on model {}'.format(
            self.action_type,
            self.field_name,
            self.model_name)

class ObjectSelector:
    OPERATORS = set(['|', '&', '~'])

    def __init__(self, match_on, available_fields):
        for field_name in match_on:
            if field_name in self.OPERATORS:
                continue

            if field_name not in available_fields:
                raise ValueError(
                    'field_name({}) must be in fields({})'.format(
                        field_name, available_fields))

        self.match_on = match_on
        self.fields = available_fields

    def get_by(self):
        def build_selector(match):
            return Q(**{match: self.fields[match]})

        # if no operators present, then just AND all of the match_ons
        if len(self.OPERATORS.intersection(self.match_on)) == 0:
            match = self.match_on[0]
            q = build_selector(match)
            for match in self.match_on[1:]:
                q = q & build_selector(match)

            return q

        # process post-fix operator string
        stack = []
        for match in self.match_on:
            if match in self.OPERATORS:
                if match is '~':
                    if len(stack) < 1:
                        raise ValueError('Insufficient operands for operator:{}', match)

                    stack.append(~stack.pop())
                    continue

                if len(stack) < 2:
                    raise ValueError('Insufficient operands for operator:{}', match)

                # remove the operands from the stack in reverse order 
                # (preserves left-to-right reading)
                operand2 = stack.pop()
                operand1 = stack.pop()

                if match == '|':
                    stack.append(operand1 | operand2)
                elif match == '&':
                    stack.append(operand1 & operand2)
                else:
                    pass
            else:
                stack.append(build_selector(match))

        if len(stack) != 1:
            raise ValueError('Insufficient operators, stack:{}', stack)

        return stack[0]


class ModelAction:
    """
    The base action, which performs makes no modifications to objects.

    This class consolidates the some of the validity checking and the logic
    for finding the target objects.
    """
    REFERRED_TO_DELIMITER = '=>'

    def __init__(self, model, match_on, fields={}):
        """
        Create a base action.

        :param model:
        :param match_on:
        :param fields:
        :return:
        """
        if model is None:
            raise ValueError('model cannot be None')
        if not match_on:
            raise ValueError('match_on({}) must be not "empty"'.format(
                match_on))

        match_on = ObjectSelector(match_on, fields)

        self.model = model
        self.match_on = match_on
        self.fields = fields

    def __str__(self):
        return '{} - Model:{} - MatchFields:{} - Fields:{}'.format(
            self.__class__.__name__,
            self.model.__name__,
            self.match_on.match_on,
            self.fields)

    @property
    def type(self):
        return ''

    def get_object(self):
        """Finds the object that matches the provided matching information"""
        return self.model.objects.get(self.match_on.get_by())

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
            if self.REFERRED_TO_DELIMITER in attribute and value != '':
                ref_attr = attribute.split(self.REFERRED_TO_DELIMITER)
                referential_attributes[ref_attr[0]][ref_attr[1]] = value
            else:
                if not force:
                    current_value = getattr(object, attribute, None)
                    if not (current_value is None or current_value is ''):
                        continue
                try:
                    if object._meta.get_field(attribute).null:
                        value = None if value == '' else value
                except FieldDoesNotExist:
                    pass
                setattr(object, attribute, value)

        for attribute, get_by in referential_attributes.items():
            try:
                field = object._meta.get_field(attribute)
                # For migration advice of the get_field_by_name() call see [1]
                # [1]: https://docs.djangoproject.com/en/1.9/ref/models/meta/#migrating-old-meta-api

                if field.related_model:
                    if field.concrete:
                        own_attribute = field.name
                        get_current_value = getattr
                        set_value = setattr
                    else:
                        own_attribute = field.get_accessor_name()
                        def get_value_from_remote(object, attribute, default):
                            try:
                                return getattr(object, attribute).get()
                            except:
                                return default
                        get_current_value = get_value_from_remote
                        set_value = set_value_to_remote

                    if not force:
                        current_value = get_current_value(object, own_attribute, None)
                        if current_value is not None:
                            continue

                    try:
                        if field.many_to_many:
                            action_type = None
                            get_by_exact = {}
                            for k,v in get_by.items():
                                if action_type is None:
                                    action_type = k[0]
                                elif action_type != k[0]:
                                    raise DissimilarActionTypesError(
                                        action_type, k[0], field.verbose_name,
                                        object.__class__.__name__)
                                get_by_exact[k[1:]] = v

                            if action_type not in '+-=':
                                raise UnknownActionType(action_type, 
                                    field.verbose_name,
                                    object.__class__.__name__)

                            target = field.related_model.objects.get(**get_by_exact)

                            if action_type is '+':
                                getattr(object, own_attribute).add(target)
                            elif action_type is '-':
                                getattr(object, own_attribute).remove(target)
                            elif action_type is '=':
                                attr = getattr(object, own_attribute)
                                # Django 1.9 impl  => getattr(object, own_attribute).set([target])
                                attr.clear()
                                for t in set([target]):
                                    attr.add(t)

                        else:
                            target = field.related_model.objects.get(**get_by)
                            set_value(object, own_attribute, target)
                            logger.debug(object)

                    except ObjectDoesNotExist as e:
                        logger.warning(
                            'Could not find {} with {} for {}[{}].{}',
                            field.related_model.__name__,
                            get_by,
                            object.__class__.__name__,
                            object,
                            field.verbose_name)
                    except MultipleObjectsReturned as e:
                        logger.warning(
                            'Found multiple {} objects with {} for {}[{}].{}',
                            field.related_model.__name__,
                            get_by,
                            object.__class__.__name__,
                            object,
                            field.verbose_name)
            except FieldDoesNotExist as e:
                logger.warning( 'Attibute "{}" does not exist on {}[{}]',
                    attribute,
                    object.__class__.__name__,
                    object)

            except DissimilarActionTypesError as e:
                logger.warning('{}', e)

            except UnknownActionType as e:
                logger.warning('{}', e)


class CreateModelAction(ModelAction):
    """
    Action to create a model object if it does not exist.

    Note, this will not create another object if a matching one is
    found, nor will it update a matched object.
    """

    def execute(self):
        try:
            return self.get_object()
        except ObjectDoesNotExist as e:
            pass
        except MultipleObjectsReturned as e:
            logger.warning('Mulitple objects found - {} Error:{}', str(self), e)
            return None


        obj=self.model()
        # NB: Create uses force to override defaults
        self.update_from_fields(obj, True)
        obj.save()
        return obj

    @property
    def type(self):
        return 'create'


class CreateModelWithReferenceAction(CreateModelAction):
    """
    Action to create a model object if it does not exist, and to create or
    update an external reference to the object.
    """

    def __init__(self, external_system, model,
                 external_key, match_on, fields={}):
        """

        :param external_system (model object): The external system to create or
            update the reference for.
        :param external_key (str): The reference value from the external
            system (i.e. the 'id' that the external system uses to refer to the
            model object).
        :param model (class): See definition on super class
        :param match_on (list): See definition on super class
        :param fields(dict): See definition on super class
        :return: The model object provided by the action
        """
        super(CreateModelWithReferenceAction, self).__init__(
            model, match_on, fields)
        self.external_system=external_system
        self.external_key=external_key

    def execute(self):
        try:
            mapping=ExternalKeyMapping.objects.get(
                external_system=self.external_system,
                external_key=self.external_key)
        except ExternalKeyMapping.DoesNotExist:
            mapping=ExternalKeyMapping(
                external_system=self.external_system,
                external_key=self.external_key)

        model_obj=mapping.content_object
        if model_obj is None:
            model_obj=super(CreateModelWithReferenceAction, self).execute()

        if model_obj:
            mapping.content_type=ContentType.objects.get_for_model(
                self.model)
            mapping.content_object=model_obj
            mapping.object_id=model_obj.id
            mapping.save()
        return model_obj


from django.db import IntegrityError, transaction
class UpdateModelAction(ModelAction):
    """
    Action to update the fields of a model object, but not create an
    object.
    """

    def __init__(self, model, match_on, fields={}, force_update=False):
        """
        Create an Update action to be executed in the future.

        :param model (class): The model to update against
        :param match_on (list): A list of names of model attributes/fields
            to use to find the object to update. They must be a key in the
            provided fields.
        :param fields(dict): The set of fields to update, with the values to
            update them to.
        :param force_update(bool): (Optional) Whether the update should be
            forced or only affect 'empty' fields. Default:False
        :return: The updated object (if a matching object is found) or None.
        """
        super(UpdateModelAction, self).__init__(
            model, match_on, fields)
        self.force_update=force_update

    @property
    def type(self):
        return 'update'

    def execute(self):
        try:
            obj=self.get_object()
            self.update_from_fields(obj, self.force_update)

            with transaction.atomic():
                obj.save()

            return obj
        except ObjectDoesNotExist:
            return None
        except MultipleObjectsReturned as e:
            logger.warning('Mulitple objects found - {} Error:{}', str(self), e)
            return None
        except IntegrityError as e:
            logger.warning('Integrity issue - {} Error:{}', str(self), e)
            return None

class UpdateModelWithReferenceAction(UpdateModelAction):
    """
    Action to create a model object if it does not exist, and to create or
    update an external reference to the object.
    """

    def __init__(self, external_system, model, external_key, match_on,
                 fields={}, force_update=False):
        """

        :param external_system (model object): The external system to create or
            update the reference for.
        :param external_key (str): The reference value from the external
            system (i.e. the 'id' that the external system uses to refer to the
            model object).

        :param model (class): See definition on super class
        :param match_on (list): See definition on super class
        :param fields(dict): See definition on super class
        :return: The updated object (if an object is found) or None.
        """
        super(UpdateModelWithReferenceAction, self).__init__(
            model, match_on, fields, force_update)
        self.external_system=external_system
        self.external_key=external_key

    def execute(self):
        try:
            mapping=ExternalKeyMapping.objects.get(
                external_system=self.external_system,
                external_key=self.external_key)
        except ExternalKeyMapping.DoesNotExist:
            mapping=ExternalKeyMapping(
                external_system=self.external_system,
                external_key=self.external_key)

        linked_object=mapping.content_object

        matched_object=None
        try:
            matched_object=self.get_object()
        except ObjectDoesNotExist:
            pass
        except MultipleObjectsReturned as e:
            logger.warning('Mulitple objects found - {} Error:{}', str(self), e)
            return None

        # If both matched and linked objects exist but are different,
        # get rid of the matched one
        if matched_object and linked_object and (matched_object != 
                                                 linked_object):
            matched_object.delete()

        # Choose the most appropriate object to update
        if linked_object:
            model_obj=linked_object
        elif matched_object:
            model_obj=matched_object
        else:
            # No object to update
            return None

        if model_obj:
            self.update_from_fields(model_obj, self.force_update)
            try:
                with transaction.atomic():
                    model_obj.save()
            except IntegrityError as e:
                logger.warning('Integrity issue - {} Error:{}', str(self), e)
                return None

        if model_obj:
            mapping.content_type=ContentType.objects.get_for_model(
                self.model)
            mapping.content_object=model_obj
            mapping.object_id=model_obj.id
            mapping.save()

        return model_obj


class DeleteIfOnlyReferenceModelAction(ModelAction):
    """
    This action only deletes the pointed to object if the key mapping
    corresponding to 'this' external key it the only one

    I.e. if there are two references from different external systems to the
    same object, then the object will not be deleted.
    """

    def __init__(self, external_system, external_key, delete_action):
        self.delete_action=delete_action
        self.external_key=external_key
        self.external_system=external_system

    @property
    def type(self):
        return self.delete_action.type

    def execute(self):
        try:
            obj=self.delete_action.get_object()

            key_mapping=ExternalKeyMapping.objects.get(
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
            # There are multiple key mappings or multiple target objects, we shouldn't delete the object
            return
        except ObjectDoesNotExist:
            return


class DeleteModelAction(ModelAction):

    @property
    def type(self):
        return 'delete'

    def execute(self):
        """Forcibly delete any objects found by the
        ModelAction.get_object() method."""
        try:
            self.get_object().delete()
        except ObjectDoesNotExist:
            pass
        except MultipleObjectsReturned as e:
            logger.warning('Mulitple objects found - {} Error:{}', str(self), e)
            return None


class DeleteExternalReferenceAction:
    """
    A model action to remove the ExternalKeyMapping object for a model object.
    """

    def __init__(self, external_system, external_key):
        self.external_system=external_system
        self.external_key=external_key

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
        self.model=model
        self.external_system=external_system

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

    def build(self, sync_actions, match_on, external_system_key,
              fields):
        """
        Builds the list of actions to satisfy the provided information.

        This includes correctly building any actions required to keep the
        external system references correctly up to date.

        :param sync_actions:
        :param match_on:
        :param external_system_key:
        :param fields:
        :return:
        """
        actions=[]

        if sync_actions.is_impotent():
            actions.append(ModelAction(self.model, match_on, fields))

        if sync_actions.delete:
            action=DeleteModelAction(self.model, match_on, fields)
            if self.is_externally_mappable(external_system_key):
                if not sync_actions.force:
                    action=DeleteIfOnlyReferenceModelAction(
                        self.external_system, external_system_key, action)
                actions.append(action)
                actions.append(DeleteExternalReferenceAction(
                    self.external_system, external_system_key))
            elif sync_actions.force:
                actions.append(action)

        if sync_actions.create:
            if self.is_externally_mappable(external_system_key):
                action=CreateModelWithReferenceAction(self.external_system,
                                                        self.model,
                                                        external_system_key,
                                                        match_on,
                                                        fields)
            else:
                action=CreateModelAction(self.model, match_on, fields)
            actions.append(action)
        if sync_actions.update:
            if self.is_externally_mappable(external_system_key):
                action=UpdateModelWithReferenceAction(self.external_system,
                                                        self.model,
                                                        external_system_key,
                                                        match_on,
                                                        fields,
                                                        sync_actions.force)
            else:
                action=UpdateModelAction(self.model, match_on,
                                           fields, sync_actions.force)

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

        self.create=create
        self.update=update
        self.delete=delete
        self.force=force

    def __str__(self):
        return "SyncActions {}{}{}{}".format(
            'c' if self.create else '',
            'u' if self.update else '',
            'd' if self.delete else '',
            '*' if self.force else '')

    def is_impotent(self):
        return not (self.create or self.update or self.delete)

