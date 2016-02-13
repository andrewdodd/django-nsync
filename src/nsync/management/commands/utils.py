from django.core.management.base import CommandError  # TODO replace error
from django.apps.registry import apps
import csv

from nsync.models import ExternalSystem
from nsync.actions import ActionFactory, SyncActions


class SupportedFileChecker:
    @staticmethod
    def is_valid(file):
        return file is not None


class ModelFinder:
    @staticmethod
    def find(app_label, model_name):
        if not app_label:
            raise CommandError('Invalid app label "{}"'.format(app_label))

        if not model_name:
            raise CommandError('Invalid model name "{}"'.format(model_name))

        return apps.get_model(app_label, model_name)


class ExternalSystemHelper:
    @staticmethod
    def find(name, create=True):
        if not name:
            raise CommandError('Invalid external system name "{}"'.format(
                name))

        try:
            return ExternalSystem.objects.get(name=name)
        except ExternalSystem.DoesNotExist:
            if create:
                return ExternalSystem.objects.create(name=name,
                                                     description=name)
            else:
                raise CommandError('ExternalSystem "{}" not found'.format(
                    name))


class CsvActionFactory(ActionFactory):
    action_flags_label = 'action_flags'
    external_key_label = 'external_key'
    match_on_label = 'match_on'
    match_on_delimiter = ' '

    def from_dict(self, raw_values):
        if not raw_values:
            return []

        action_flags = raw_values.pop(self.action_flags_label)
        match_on = raw_values.pop(self.match_on_label)
        match_on = match_on.split(
            self.match_on_delimiter)
        external_system_key = raw_values.pop(self.external_key_label, None)

        sync_actions = CsvSyncActionsDecoder.decode(action_flags)

        return self.build(sync_actions, match_on,
                          external_system_key, raw_values)


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
