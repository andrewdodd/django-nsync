from django.core.management.base import BaseCommand, CommandError
from django.apps.registry import apps
import os
import csv

from nsync.models import ExternalSystem


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
                return ExternalSystem.objects.create(name=name, description=name)
            else:
                raise CommandError("ExternalSystem '{}' not found".format(name))


