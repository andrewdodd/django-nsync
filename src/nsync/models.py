from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class ExternalSystem(models.Model):
    """
    Computer systems that integration occurs against
    """
    name = models.CharField(
        blank=False,
        db_index=True,
        help_text="""A short name, used by software applications
                     to locate this particular External System.
                  """,
        max_length=30,
        unique=True,
    )
    description = models.CharField(
        blank=True,
        help_text='A human readable name for this External System.',
        max_length=80,
    )

    class Meta:
        verbose_name = 'External System'

    def __str__(self):
        return self.description if self.description else self.name


class ExternalKeyMapping(models.Model):
    """
    Key Mappings for objects in our system to objects in external systems
    """
    content_type = models.ForeignKey(
        ContentType,
        help_text='The type of object that is mapped to the external system.',
        on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    external_system = models.ForeignKey(ExternalSystem, on_delete=models.CASCADE)
    external_key = models.CharField(
        blank=False,
        help_text='The key of the internal object in the external system.',
        max_length=80,
    )

    class Meta:
        index_together = ('external_system', 'external_key')
        unique_together = ('external_system', 'external_key')
        verbose_name = 'External Key Mapping'

    def __str__(self):
        return '{}:{}-{}:{}'.format(
            self.external_system.name,
            self.external_key,
            self.content_type.model_class().__name__,
            self.object_id)
