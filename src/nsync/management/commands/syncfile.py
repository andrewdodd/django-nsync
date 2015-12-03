from django.core.management.base import BaseCommand, CommandError
import os
import csv

from nsync.sync import ExternalSystemHelper, ModelFinder
from nsync.actions import CsvActionsBuilder
from nsync.policies import BasicSyncPolicy, TransactionSyncPolicy


class Command(BaseCommand):
    help = 'Sync info from one file'

    def add_arguments(self, parser):
        # Mandatory
        parser.add_argument(
            'ext_system_name',
            help='The name of the external system to use for storing '
                 'sync information in relation to')
        parser.add_argument(
            'app_label',
            default=None,
            help='The name of the application the model is part of')
        parser.add_argument(
            'model_name',
            help='The name of the model to synchronise to')
        parser.add_argument(
            'file_name',
            help='The file to synchronise from')
        # Optional
        parser.add_argument(
            '--create_external_system',
            type=bool,
            default=True,
            help='The name of the external system to use for storing '
                 'sync information in relation to')

    def handle(self, *args, **options):
        external_system = ExternalSystemHelper.find(
            options['ext_system_name'], options['create_external_system'])
        model = ModelFinder.find(options['app_label'], options['model_name'])

        filename = options['file_name']
        if not os.path.exists(filename):
            raise CommandError("Filename '{}' not found".format(filename))

        with open(filename) as f:
            # TODO - Review - This indirection is only due to issues in
            # getting the mocks in the tests to work
            SyncFileAction.sync(external_system, model, f)


class SyncFileAction:
    @staticmethod
    def sync(external_system, model, file):
        reader = csv.DictReader(file)
        builder = CsvActionsBuilder(model, external_system)
        actions = []
        for d in reader:
            actions.extend(builder.from_dict(d))

        TransactionSyncPolicy(BasicSyncPolicy(actions)).execute()
