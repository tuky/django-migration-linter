# -*- coding: utf-8 -*-
# Generated by Django 1.11.18 on 2019-04-14 15:00
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app_rename_table', '0001_initial'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='A',
            new_name='B',
        ),
    ]