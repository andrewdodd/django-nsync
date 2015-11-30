# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExternalKeyMapping',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, serialize=False, verbose_name='ID')),
                ('object_id', models.PositiveIntegerField()),
                ('external_key', models.CharField(max_length=80, help_text='The key of the internal object in the external system.')),
                ('content_type', models.ForeignKey(help_text='The type of object that is mapped to the external system.', to='contenttypes.ContentType')),
            ],
            options={
                'verbose_name': 'External Key Mapping',
            },
        ),
        migrations.CreateModel(
            name='ExternalSystem',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(help_text='A short label, used by software applications \n                       to locate this particular External System.\n                    ', max_length=30, db_index=True, unique=True)),
                ('name', models.CharField(max_length=80, help_text='A human readable name for this External System.', blank=True)),
            ],
            options={
                'verbose_name': 'External System',
            },
        ),
        migrations.AddField(
            model_name='externalkeymapping',
            name='external_system',
            field=models.ForeignKey(to='nsync.ExternalSystem'),
        ),
        migrations.AlterUniqueTogether(
            name='externalkeymapping',
            unique_together=set([('external_system', 'external_key')]),
        ),
        migrations.AlterIndexTogether(
            name='externalkeymapping',
            index_together=set([('external_system', 'external_key')]),
        ),
    ]
