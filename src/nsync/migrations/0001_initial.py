# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExternalKeyMapping',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', primary_key=True, auto_created=True)),
                ('object_id', models.PositiveIntegerField()),
                ('external_key', models.CharField(max_length=80, help_text='The key of the internal object in the external system.')),
                ('content_type', models.ForeignKey(to='contenttypes.ContentType', help_text='The type of object that is mapped to the external system.', on_delete=models.CASCADE)),
            ],
            options={
                'verbose_name': 'External Key Mapping',
            },
        ),
        migrations.CreateModel(
            name='ExternalSystem',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', primary_key=True, auto_created=True)),
                ('name', models.CharField(unique=True, db_index=True, max_length=30, help_text='A short name, used by software applications\n                     to locate this particular External System.\n                  ')),
                ('description', models.CharField(blank=True, max_length=80, help_text='A human readable name for this External System.')),
            ],
            options={
                'verbose_name': 'External System',
            },
        ),
        migrations.AddField(
            model_name='externalkeymapping',
            name='external_system',
            field=models.ForeignKey(to='nsync.ExternalSystem', on_delete=models.CASCADE),
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
