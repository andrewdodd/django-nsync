import unittest
from unittest.mock import MagicMock, PropertyMock
from django.test import TestCase
import fake_filesystem_unittest
import io
import tempfile

from nsync.management.commands.performsync import ImmediateSubdirectories, CandidateExternalSystem, SyncRecordCSVFileChecker, SyncRecordCSVFileHandler, SyncInfo, \
    SyncRecord

SYNC_ROOT = "/tmp/syncroot"

class TestSyncRecordCSVFileChecker(unittest.TestCase):
    def test_that_no_file_is_invalid(self):

        self.assertFalse(SyncRecordCSVFileChecker.is_valid(None))
    def test_that_missing_file_is_invalid(self):
        self.assertFalse(SyncRecordCSVFileChecker.is_valid('invalid/file/path'))

    def test_that_empty_file_is_invalid(self):
        with tempfile.NamedTemporaryFile() as empty_file:
            self.assertFalse(SyncRecordCSVFileChecker.is_valid(empty_file.name))

    def test_that_file_with_at_least_one_line_is_valid(self):
        with tempfile.NamedTemporaryFile() as temp:
            temp.write(b"Anything")
            temp.flush()
            self.assertTrue(SyncRecordCSVFileChecker.is_valid(temp.name))


class TestSyncRecordCSVFileHandler(unittest.TestCase):
    def test_that_file_without_mandatory_headers_is_invalid(self):
        csv_file_obj = io.StringIO('header1,header2,header3,header4')
        subject = SyncRecordCSVFileHandler(csv_file_obj)
        self.assertFalse(subject.is_valid())

    def test_that_file_without_at_least_4_columns_is_invalid(self):
        csv_file_obj = io.StringIO('external_key,delete_flag,match_field_name')
        subject = SyncRecordCSVFileHandler(csv_file_obj)
        self.assertFalse(subject.is_valid())

    def test_that_file_with_correct_headers_is_valid(self):
        csv_file_obj = io.StringIO('external_key,delete_flag,match_field_name,field1')
        subject = SyncRecordCSVFileHandler(csv_file_obj)
        self.assertTrue(subject.is_valid())

    def test_get_sync_records_tolerates_no_data(self):
        csv_file_obj = io.StringIO('external_key,delete_flag,match_field_name,field1\n')
        sync_records = SyncRecordCSVFileHandler(csv_file_obj).get_sync_records()
        self.assertEqual([], sync_records)

    def test_that_returned_objects_have_all_headers(self):
        headers = SyncRecordCSVFileHandler.mandatory_headers.union({'field1'})
        csv_file_obj = io.StringIO()
        csv_file_obj.writelines([
            'external_key,delete_flag,match_field_name,field1\n',
            'key value,,field1,\n'
            ])
        csv_file_obj.seek(0)

        sync_records = SyncRecordCSVFileHandler(csv_file_obj).get_sync_records()

        self.assertIs(len(sync_records), 1)
        sync_record = sync_records[0]
        self.assertTrue('field1' in sync_record.fields.keys())
        
    def test_that_objects_are_omitted_if_match_field_name_matches_a_mandatory_header(self):
        headers = SyncRecordCSVFileHandler.mandatory_headers.union({'field1'})
        csv_file_obj = io.StringIO()
        csv_file_obj.writelines([
            'external_key,delete_flag,match_field_name,field1\n',
            'key value,,external_key,\n'
            ])
        csv_file_obj.seek(0)

        sync_records = SyncRecordCSVFileHandler(csv_file_obj).get_sync_records()
        self.assertIs(len(sync_records), 0)

    def test_that_objects_with_invalid_match_field_name_are_omitted(self):
        headers = SyncRecordCSVFileHandler.mandatory_headers.union({'field1'})
        csv_file_obj = io.StringIO()
        csv_file_obj.writelines([
            'external_key,delete_flag,match_field_name,field1\n',
            'key value,,does_not_match,\n'
            ])
        csv_file_obj.seek(0)

        sync_records = SyncRecordCSVFileHandler(csv_file_obj).get_sync_records()
        self.assertIs(len(sync_records), 0)

class TestImmediateSubdirectories(fake_filesystem_unittest.TestCase):
    def setUp(self):
        self.setUpPyfakefs()
        self.fs.CreateDirectory(SYNC_ROOT)

    def test_that_subdirectories_are_returned(self):
        self.fs.CreateDirectory(SYNC_ROOT + "/Subdirectory")

        systems = ImmediateSubdirectories.get(SYNC_ROOT)
        assert len(systems) == 1

    def test_that_files_are_not_included(self):
        self.fs.CreateDirectory(SYNC_ROOT + "/Subdirectory")
        self.fs.CreateFile(SYNC_ROOT + "/FileName.txt")

        systems = ImmediateSubdirectories.get(SYNC_ROOT)
        assert len(systems) == 1
        
    def test_that_subdirectories_returned_as_candidates_in_alphabetic_order(self):
        self.fs.CreateDirectory(SYNC_ROOT + "/FirstSubdirectory")
        self.fs.CreateDirectory(SYNC_ROOT + "/FinalSubdirectory")

        systems = ImmediateSubdirectories.get(SYNC_ROOT)
        assert len(systems) == 2
        self.assertEqual(systems[0], "FinalSubdirectory")
        self.assertEqual(systems[1], "FirstSubdirectory")


class TestCandidateExternalSystem(fake_filesystem_unittest.TestCase):
    def setUp(self):
        self.setUpPyfakefs()
        self.fs.CreateDirectory(SYNC_ROOT)

    def test_that_subdirectories_returned_as_candidates_in_alphabetic_order(self):
        self.fs.CreateDirectory(SYNC_ROOT + "/FirstSystem")
        self.fs.CreateDirectory(SYNC_ROOT + "/FinalSystem")

        systems = CandidateExternalSystem.obtain_sync_candidates(SYNC_ROOT)
        assert len(systems) == 2
        self.assertEqual(systems[0], "FinalSystem")
        self.assertEqual(systems[1], "FirstSystem")

    def test_that_returned_candidates_obey_special_ordering(self):
        pass


