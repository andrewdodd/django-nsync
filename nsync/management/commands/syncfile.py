from django.core.management.base import BaseCommand, CommandError
from django.apps.registry import apps
import os
import csv
import argparse

from nsync.models import ExternalSystem, ExternalReferenceHandler
from nsync.sync import SyncInfo, SyncRecord
from nsync.actions import ActionsBuilder

class Command(BaseCommand):
    help = 'Sync info from one file'

    def add_arguments(self, parser):
        # Mandatory
        parser.add_argument('ext_system_name',
                help='The name of the external system to use for storing sync information in relation to')
        parser.add_argument('model_name',
                help='The name of the model to synchronise to')
        parser.add_argument('app_label',
                default=None,
                help='The name of the application the model is part of')
        parser.add_argument('file_name',
                help='The file to synchronise from')
        # Optional
        parser.add_argument('--create_external_system',
                type=bool,
                default=True,
                help='The name of the external system to use for storing sync information in relation to')

    def handle(self, *args, **options):
        external_system = ExternalSystemHelper.find(options['ext_system_name'], options['create_external_system'])
        model = ModelFinder.find(options['app_label'], options['model_name'])

        filename = options['file_name']
        if not os.path.exists(filename):
            raise CommandError("Filename '{}' not found".format(filename))

        with open(filename) as f:
            # TODO - Review - This indirection is only due to issues in getting the 
            # mocks in the tests to work
            SyncFileAction.sync(external_system, model, f)

class SyncFileAction:
    @staticmethod
    def sync(external_system, model, file):
        reader = csv.DictReader(file)
        actions = [ActionsBuilder.from_dict(d) for d in reader]
        BasicSyncPolicy.process_actions(actions)

class BasicSyncPolicy:
    @classmethod
    def process_actions(cls, actions):
        for action in actions:
            action.execute()


# class SyncActionBuilder:
#     def __init__(self):
#         pass
# 
#     @staticmethod
#     def is_valid( d):
#         pass
# 
# class CSVSyncFileActionParser:
# 
#     def __init__(self, action_header='action_flags', match_field_header='match_field_name'):
#         self.action_header = action_header
#         self.match_field_header = match_field_header
# 
#     def is_valid(self):
#         if len(self.reader.fieldnames) < 3:
#             return False
# 
#         return self.mandatory_headers.issubset(self.reader.fieldnames)
#     
#     def get_sync_records(self):
#         records = []
#         for line in self.reader:
#             match_field = line['match_field_name']
#             if match_field in self.mandatory_headers:
#                 pass # TODO introduce logging for this error
#             elif match_field not in line.keys():
#                 pass # TODO introduce logging for this error
#             else:
#                 records.append(SyncRecord(**line))
#         return records
