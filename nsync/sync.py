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

