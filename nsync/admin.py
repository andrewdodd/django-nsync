from django import forms
from django.contrib import admin

from .models import ExternalSystem
from .models import ExternalKeyMapping

import logging

logger = logging.getLogger(__name__)

@admin.register(ExternalSystem)
class ExternalSystemAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'label')

@admin.register(ExternalKeyMapping)
class ExternalKeyMappingAdmin(admin.ModelAdmin):
    fieldsets = (
            ('Internal Object', {
                'fields': ('content_type', 'object_id', )
            }),
            ('External Mapping', {
                'fields': ('external_system', 'external_key')
            }),
        ) 

#admin.site.register(ExternalKeyMapping)
#admin.site.register(ExternalSystem)

