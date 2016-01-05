from django.core.management.base import BaseCommand, CommandError
import os
import csv
import argparse
import re
from .utils import (
    ExternalSystemHelper,
    ModelFinder,
    SupportedFileChecker,
    CsvActionFactory)
from nsync.policies import (
    BasicSyncPolicy,
    OrderedSyncPolicy,
    TransactionSyncPolicy
)

(DEFAULT_FILE_REGEX) = (r'(?P<external_system>[a-zA-Z0-9]+)_'
                        r'(?P<app_name>[a-zA-Z0-9]+)_'
                        r'(?P<model_name>[a-zA-Z0-9]+).*\.csv')


class Command(BaseCommand):
    help = 'Sync info from a list of files'

    def add_arguments(self, parser):
        # Mandatory
        parser.add_argument('files', type=argparse.FileType('r'), nargs='+')
        # Optional
        parser.add_argument(
            '--file_name_regex',
            type=str,
            default=DEFAULT_FILE_REGEX,
            help='The regular expression to obtain the system name, app name '
                 'and model name from each file')
        parser.add_argument(
            '--create_external_system',
            type=bool,
            default=True,
            help='If true, the command will create a matching external '
                 'system object if one cannot be found')
        parser.add_argument(
            '--smart_ordering',
            type=bool,
            default=True,
            help='When this option it true, the command will perform all '
                 'Create actions, then Update actions, and finally Delete '
                 'actions. This ensures that if one file creates an object '
                 'but another deletes it, the order that the files are '
                 'provided to the command is not important. Default: True')
        parser.add_argument(
            '--as_transaction',
            type=bool,
            default=True,
            help='Wrap all of the actions in a DB transaction Default:True')

    def handle(self, *args, **options):
        TestableCommand(**options).execute()


class TestableCommand:
    def __init__(self, **options):
        self.files = options['files']
        self.pattern = re.compile(options['file_name_regex'])
        self.create_external_system = options['create_external_system']
        self.ordered = options['smart_ordering']
        self.use_transaction = options['as_transaction']

    def execute(self):
        actions = self.collect_all_actions()

        if self.ordered:
            policy = OrderedSyncPolicy(actions)
        else:
            policy = BasicSyncPolicy(actions)

        if self.use_transaction:
            policy = TransactionSyncPolicy(policy)

        policy.execute()

    def collect_all_actions(self):
        actions = []

        for f in self.files:
            if not SupportedFileChecker.is_valid(f):
                raise CommandError('Unsupported file:{}'.format(f))

            basename = os.path.basename(f.name)
            (system, app, model) = TargetExtractor(self.pattern).extract(
                basename)
            external_system = ExternalSystemHelper.find(
                system, self.create_external_system)
            model = ModelFinder.find(app, model)

            reader = csv.DictReader(f)
            builder = CsvActionFactory(model, external_system)
            for d in reader:
                actions.extend(builder.from_dict(d))
        return actions


class TargetExtractor:
    def __init__(self, pattern):
        self.pattern = pattern

    def extract(self, filename):
        result = self.pattern.match(filename)
        return (result.group('external_system'),
                result.group('app_name'),
                result.group('model_name'))
