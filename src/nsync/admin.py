from django import forms
from django.contrib import admin

from .models import ExternalSystem
from .models import ExternalKeyMapping


class ExternalSystemAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')


class ExternalKeyMappingAdmin(admin.ModelAdmin):
    fieldsets = (
            ('Internal Object', {
                'fields': ('content_type', 'object_id', )
            }),
            ('External Mapping', {
                'fields': ('external_system', 'external_key')
            }),
        ) 

