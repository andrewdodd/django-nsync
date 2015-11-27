from django.core.management.base import BaseCommand, CommandError
from django.apps.registry import apps
import os
import csv

from nsync.models import ExternalSystem, ExternalReferenceHandler


class SyncError(Exception):
    pass

class SyncFileAction:
    def __init__(self, external_system, model, file_obj):
        self.external_system = external_system
        self.model = model
        self.file = file_obj

    def sync(self):
        raise SyncError()

class SupportedFileChecker:
    @staticmethod
    def is_valid(file):
        if file is None:
            return False

        is_valid = csv.Sniffer().has_header(file.read(1024))
        file.seek(0)
        return is_valid
        

class ModelFinder:
    @staticmethod
    def find(app_label, model_name):
        if not app_label:
            raise CommandError("Invalid app label '{}'".format(app_label))
        
        if not model_name:
            raise CommandError("Invalid model name '{}'".format(model_name))
        
        return apps.get_model(app_label, model_name)


class ExternalSystemHelper:
    @staticmethod
    def find(name, create=True):
        if not name:
            raise CommandError("Invalid external system name '{}'".format(name))
        
        try:
            return ExternalSystem.objects.get(name=name)
        except ExternalSystem.DoesNotExist:
            if create:
                return ExternalSystem.objects.create(name=name)
            else:
                raise CommandError("ExternalSystem '{}' not found".format(name))


#def __init__(self, external_key, sync_actions, match_field_name, **kwargs):
#    if not match_field_name:
#        raise ValueError("Match field should be a valid string")
#    if match_field_name not in kwargs:
#        raise ValueError("Match field must be one of the kwargs provided")

#    self.external_key = external_key
#    self.match_field_name = match_field_name
#    self.fields = kwargs
#    self.sync_actions = sync_actions

#def is_externally_mappable(self):
#    return self.external_key
#
#def is_delete_record(self):
#    return self.sync_actions.delete

class ModelAction:
    def __init__(self, model, match_field_name, fields={}):
        if model is None:
            raise ValueError('model cannot be None')
        if not match_field_name:
            raise ValueError('match_field_name({}) must be not "empty"'.format(match_field_name))
        if match_field_name not in fields:
            raise ValueError('match_field_name({}) must be in fields'.format(match_field_name))

        self.model = model
        self.match_field_name = match_field_name
        self.fields = fields

    def __str__(self):
        return "Action {} - Model:{} - MatchField:{} - Fields:{}".format(
                self.__class__,
                self.model,
                self.match_field_name,
                self.fields)

    def find_objects(self):
        filter_by = {self.match_field_name: self.fields[self.match_field_name]}
        return self.model.objects.filter(**filter_by)
        

class CreateModelAction(ModelAction):
    pass
class UpdateModelAction(ModelAction):
    pass
class DeleteModelAction(ModelAction):
    pass

class ActionsBuilder:
    action_flags_label = 'action_flags'
    match_field_name_label = 'match_field_name'
    external_key_label = 'external_key'

    def __init__(self, model):
        self.model = model

    def from_dict(self, raw_values):
        if not raw_values:
            return []

        action_flags = raw_values.pop(self.action_flags_label)
        match_field_name = raw_values.pop(self.match_field_name_label)
        external_system_key = raw_values.pop(self.external_key_label, None)

        actions = []

        encoded_actions = EncodedSyncActions.decode(action_flags)

        if encoded_actions.create:
            actions.append(CreateModelAction(self.model, match_field_name, raw_values))
        if encoded_actions.update:
            actions.append(UpdateModelAction(self.model, match_field_name, raw_values))
        if encoded_actions.delete:
            actions.append(DeleteModelAction(self.model, match_field_name, raw_values))

        if not actions:
            actions.append(ModelAction(self.model, match_field_name, raw_values))


        return actions
        #actions = []
        #
        #encoded_actions = EncodedSyncActions.parse_actions(d.pop('action_flags'))

        #if encoded_actions.create:
        #    actions.append(CreateAction(d.pop('match_field_name'), d))

        #return actions

class EncodedSyncActions:
    def __init__(self, create=False, update=False, delete=False, force=False):
        if delete and create:
            raise ValueError("Cannot delete AND create")
        if delete and update:
            raise ValueError("Cannot delete AND update")

        self.create = create
        self.update = update
        self.delete = delete
        self.force = force

    def encode(self):
        return "{}{}{}{}".format(
                'c' if self.create else '', 
                'u' if self.update else '',
                'd' if self.delete else '',
                '*' if self.force else '')

    def __str__(self):
        return "SyncActions {}".format(self.encode())

        def is_impotent(self):
            return not (self.create or self.update or self.delete)

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
                pass # not iterable

        return EncodedSyncActions(create, update, delete, force)


class SyncRecord:
    def __init__(self, external_key, sync_actions, match_field_name, **kwargs):
        if not match_field_name:
            raise ValueError("Match field should be a valid string")
        if match_field_name not in kwargs:
            raise ValueError("Match field must be one of the kwargs provided")

        self.external_key = external_key
        self.match_field_name = match_field_name
        self.fields = kwargs
        self.sync_actions = sync_actions

    def is_externally_mappable(self):
        return self.external_key
    
    def is_delete_record(self):
        return self.sync_actions.delete

class SyncInfo:
    def __init__(self, external_system_name, model, sync_records):
        self.external_system_name = external_system_name
        self.model = model
        self.sync_records = sync_records

    def __str__(self):
        return "SyncInfo {} - {} - {}".format(
                self.external_system_name, 
                self.model, 
                len(self.sync_records))

    def get_all_records(self):
        return self.sync_records

    def get_non_deleted(self):
        return [record for record in self.sync_records if not record.is_delete_record()]

    def get_deleted(self):
        return [record for record in self.sync_records if record.is_delete_record()]

