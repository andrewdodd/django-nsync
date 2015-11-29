from django.core.management.base import BaseCommand, CommandError
from django.apps.registry import apps
import os
import csv

from nsync.models import ExternalSystem, ExternalReferenceHandler
from nsync.sync import SyncInfo, SyncRecord
from nsync.actions import CsvSyncActionsDecoder

class Command(BaseCommand):
    help = 'Prints the people'

    def add_arguments(self, parser):
        # Named (optional) argument
        parser.add_argument('sync_root',
                            # type=string, # TODO this should be a readable directory
                            default=None,
                            help='The directory to use for finding sync information')

    def handle(self, *args, **options):
        sync_root = options['sync_root']

        sync_infos = SyncInfoCollector.collect_all_sync_infos(sync_root)

        # TODO - Include test for this ordering
        # Process all 'update or create' actions prior to any deletions, that
        # way if one system deletes the model object it will win
        for info in sync_infos:
            self.apply_updates(info)

        for info in sync_infos:
            self.apply_deletions(info)

    @staticmethod
    def apply_updates(sync_info):
        (external_system, created) = ExternalSystem.objects.get_or_create(label=sync_info.external_system_name)
        print('Applying update sync for:{} - {}'.format(str(external_system), str(sync_info.model._meta.object_name)))

        for non_deleted in sync_info.get_non_deleted():
            ExternalReferenceHandler.create_or_update_for_sync_record(external_system, sync_info.model, non_deleted)

    @staticmethod
    def apply_deletions(sync_info):
        (external_system, created) = ExternalSystem.objects.get_or_create(label=sync_info.external_system_name)
        print('Applying deletions sync for:{} - {}'.format(str(external_system), str(sync_info.model._meta.object_name)))

        for deleted in sync_info.get_deleted():
            ExternalReferenceHandler.delete_for_sync_record(external_system, sync_info.model, deleted)


class SyncRecordCSVFileChecker:
    @staticmethod
    def is_valid(filename):
        if filename is None:
            return False

        if not os.path.exists(filename):
            return False
        
        with open(filename, 'r') as f:
            return any(f.readlines())


class SyncRecordCSVFileHandler:
    mandatory_headers = {'external_key', 'delete_flag', 'match_field_name'}

    def __init__(self, csv_file):
        self.reader = csv.DictReader(csv_file)

    def is_valid(self):
        if len(self.reader.fieldnames) < 4:
            return False

        return self.mandatory_headers.issubset(self.reader.fieldnames)
    
    def get_sync_records(self):
        records = []
        for line in self.reader:
            match_field = line.pop('match_field_name')
            if match_field in self.mandatory_headers:
                pass # TODO introduce logging for this error
            elif match_field not in line.keys():
                pass # TODO introduce logging for this error
            else:
                external_key = line.pop('external_key')
                sync_actions = CsvSyncActionsDecoder.decode(line.pop('delete_flag'))
                records.append(SyncRecord(external_key, sync_actions, match_field, **line))
        return records


class SyncInfoCollector:

    @staticmethod
    def collect_all_sync_info_from_path(path):
        pass
        #>>> temp = os.walk('/tmp/syncroot/')
        #>>> for t in temp:
        #    ...     print(t)
        #    ...
        #    ('/tmp/syncroot/', ['BIO'], [])
        #    ('/tmp/syncroot/BIO', ['siteassets'], [])
        #    ('/tmp/syncroot/BIO/siteassets', [], [])
        #j

    # TODO - Change this to be more funcitonal, rather than imperative
    @staticmethod
    def collect_all_sync_infos(path):
        sync_infos = []

        external_systems = CandidateExternalSystem.obtain_sync_candidates(path)

        for external_system in external_systems:
            current_path = [path, external_system]
            candidate_apps = CandidateApplications.obtain_sync_candidates('/'.join(current_path))

            for app in candidate_apps:
                current_path = [path, external_system, app]
                model_files = CandidateModels.obtain_sync_candidates('/'.join(current_path))

                for model_file in model_files:
                    current_path = [path, external_system, app, model_file]
                    try:
                        model_name = model_file.replace('.csv', '')
                        model = apps.get_model(app, model_name)
                        # Here we have the model, the external system and the CSV file
                        # May as well get the data!
                        file_full_path = '/'.join(current_path)
                        is_file_valid = SyncRecordCSVFileChecker.is_valid(file_full_path)
                        if is_file_valid:
                            with open(file_full_path) as f:
                                processor = SyncRecordCSVFileHandler(f)
                                if processor.is_valid():
                                    records = processor.get_sync_records()
                                    sync_infos.append(SyncInfo(external_system, model, records))
                                else:
                                    pass # TODO introduce logging for this error
                        else:
                            pass # TODO introduce logging for this error

                    except LookupError:
                        pass # TODO introduce logging for this error

        return sync_infos


# http://stackoverflow.com/questions/9234560/find-all-csv-files-in-a-directory-using-python
def find_csv_filenames( path_to_dir, suffix=".csv" ):
    filenames = os.listdir(path_to_dir)
    return [ filename for filename in filenames if filename.endswith( suffix ) ]


# http://stackoverflow.com/questions/800197/get-all-of-the-immediate-subdirectories-in-python
class ImmediateSubdirectories:
    @staticmethod
    def get(a_dir):
        return [name for name in os.listdir(a_dir)
                if os.path.isdir(os.path.join(a_dir, name))]


class CandidateExternalSystem:
    @staticmethod
    def obtain_sync_candidates(path):
        subdirectories = ImmediateSubdirectories.get(path)
        return subdirectories


class CandidateApplications:
    @staticmethod
    def obtain_sync_candidates(path):
        subdirectories = ImmediateSubdirectories.get(path)
        return subdirectories


class CandidateModels:
    @staticmethod
    def obtain_sync_candidates(path):
        csv_files = find_csv_filenames(path)
        return csv_files

