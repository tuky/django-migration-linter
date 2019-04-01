# Copyright 2019 3YOURMIND GmbH

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os
import shutil
import sys

from django.db.migrations import Migration
from django.test import TestCase

from tests import fixtures

from django_migration_linter import MigrationLinter, Cache, DEFAULT_CACHE_PATH

if sys.version_info >= (3, 3):
    import unittest.mock as mock
else:
    import mock


class CacheTest(TestCase):
    MIGRATION_FILE = os.path.join(fixtures.ALTER_COLUMN_PROJECT, 'test_app', 'migrations', '0001_initial.py')

    def setUp(self):
        self.test_cache_filename = "test_cache_file"
        cache_file = os.path.join(DEFAULT_CACHE_PATH, self.test_cache_filename + '.pickle')
        if os.path.exists(cache_file):
            os.remove(cache_file)

    @mock.patch("django_migration_linter.MigrationLinter._gather_all_migrations",
                return_value=[
                    Migration('0001_create_table', 'app_add_not_null_column'),
                    Migration('0002_add_new_not_null_field', 'app_add_not_null_column')
                ])
    def test_cache_normal(self, *args):
        linter = MigrationLinter(self.test_cache_filename)

        with mock.patch.object(MigrationLinter, 'get_sql', wraps=linter.get_sql) as sql_mock:
            linter.lint_all_migrations()
            self.assertEqual(sql_mock.call_count, 2)

        cache = Cache(
            self.test_cache_filename,
            DEFAULT_CACHE_PATH
        )
        cache.load()

        self.assertEqual(cache['88bc96bd3bb7d4cd1643b56fecb4809a']['result'], 'OK')
        self.assertEqual(cache['fe78506804c41db1d4404bcf5d195698']['result'], 'ERR')
        self.assertListEqual(
            cache['fe78506804c41db1d4404bcf5d195698']['errors'],
            [{'err_msg': 'RENAMING tables', 'code': 'RENAME_TABLE', 'table': None, 'column': None}]
        )

        # Start the Linter again -> should use cache now.
        linter = MigrationLinter(self.test_cache_filename)

        with mock.patch.object(MigrationLinter, 'get_sql', wraps=linter.get_sql) as sql_mock:
            linter.lint_all_migrations()
            self.assertEqual(sql_mock.call_count, 0)

        self.assertTrue(linter.has_errors)

    @mock.patch("django_migration_linter.MigrationLinter._gather_all_migrations",
                return_value=[
                    Migration('0001_initial', 'app_ignore_migration'),
                    Migration('0002_ignore_migration', 'app_ignore_migration')
                ])
    def test_cache_ignored(self, *args):
        linter = MigrationLinter(self.test_cache_filename)

        with mock.patch.object(MigrationLinter, 'get_sql', wraps=linter.get_sql) as sql_mock:
            linter.lint_all_migrations()
            self.assertEqual(sql_mock.call_count, 2)

        cache = Cache(
            self.test_cache_filename,
            DEFAULT_CACHE_PATH
        )
        cache.load()

        self.assertEqual(cache['341ff774d5bcd1a8ccaa37a24569de42']['result'], 'OK')
        self.assertEqual(cache['9643981bb4da34cd878cbfff481e218d']['result'], 'IGNORE')

        # Start the Linter again -> should use cache now.
        linter = MigrationLinter(self.test_cache_filename)

        with mock.patch.object(MigrationLinter, 'get_sql', wraps=linter.get_sql) as sql_mock:
            linter.lint_all_migrations()
            self.assertEqual(sql_mock.call_count, 0)

    def test_cache_ignored_command_line(self):
        cache_file = os.path.join(DEFAULT_CACHE_PATH, 'test_project_ignore_migration.pickle')
        if os.path.exists(cache_file):
            os.remove(cache_file)
        linter = MigrationLinter(fixtures.IGNORE_MIGRATION_PROJECT,
                                 ignore_name_contains='0001')

        with mock.patch.object(MigrationLinter, 'get_sql', wraps=linter.get_sql) as sql_mock:
            linter.lint_all_migrations()
            self.assertEqual(sql_mock.call_count, 1)

        cache = Cache(
            fixtures.IGNORE_MIGRATION_PROJECT,
            DEFAULT_CACHE_PATH
        )
        cache.load()

        self.assertNotIn('63230606af0eccaef7f1f78c537c624c', cache)
        self.assertEqual(cache['5c5ca1780a9f28439c1defc1f32af894']['result'], 'IGNORE')

    def test_cache_modified(self):
        cache_file = os.path.join(DEFAULT_CACHE_PATH, 'test_project_alter_column.pickle')
        if os.path.exists(cache_file):
            os.remove(cache_file)
        linter = MigrationLinter(fixtures.ALTER_COLUMN_PROJECT)
        linter.lint_all_migrations()
        cache = Cache(
            fixtures.ALTER_COLUMN_PROJECT,
            DEFAULT_CACHE_PATH
        )
        cache.load()

        self.assertEqual(cache['8589aa107b6da296c4b49cd2681d2230']['result'], 'OK',
                         'If this fails, tearDown might have failed to remove '
                         'the modification from tests/test_project_fixtures/'
                         'test_project_alter_column/test_app/migrations/0001_initial.py'
                         )
        self.assertEqual(cache['8f54c4a434cfaa9838e8ca12eb988255']['result'], 'ERR')
        self.assertListEqual(
            cache['8f54c4a434cfaa9838e8ca12eb988255']['errors'],
            [{u'err_msg': u'ALTERING columns (Could be backward compatible. '
                          u'You may ignore this migration.)',
              u'code': u'ALTER_COLUMN',
              u'table': u'test_app_a',
              u'column': None}
             ]
        )

        # Modify migration
        backup_migration_file = self.MIGRATION_FILE + "_backup"
        shutil.copy2(self.MIGRATION_FILE, backup_migration_file)
        with open(self.MIGRATION_FILE, "a") as f:
            f.write("# modification at the end of the file")

        # Start the Linter again -> Cache should look different now
        linter = MigrationLinter(fixtures.ALTER_COLUMN_PROJECT)
        linter.lint_all_migrations()
        cache = Cache(
            fixtures.ALTER_COLUMN_PROJECT,
            DEFAULT_CACHE_PATH
        )
        cache.load()
        shutil.copy2(backup_migration_file, self.MIGRATION_FILE)
        os.remove(backup_migration_file)

        self.assertNotIn('8589aa107b6da296c4b49cd2681d2230', cache)
        self.assertEqual(cache['fbee628b1ab4bd1c14f8a4b41123e7cf']['result'], 'OK')
