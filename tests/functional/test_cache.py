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
import unittest

from django.conf import settings
from django.db.migrations import Migration

from tests import fixtures

from django_migration_linter import MigrationLinter, analyse_sql_statements

if sys.version_info >= (3, 3):
    import unittest.mock as mock
else:
    import mock


class CacheTestCase(unittest.TestCase):
    def setUp(self):
        self.test_project_path = os.path.dirname(settings.BASE_DIR)

    @mock.patch(
        "django_migration_linter.MigrationLinter._gather_all_migrations",
        return_value=[
            Migration("0001_create_table", "app_add_not_null_column"),
            Migration("0002_add_new_not_null_field", "app_add_not_null_column"),
        ],
    )
    def test_cache_normal(self, *args):
        linter = MigrationLinter(self.test_project_path)
        linter.old_cache.clear()
        linter.old_cache.save()

        with mock.patch(
            "django_migration_linter.migration_linter.analyse_sql_statements",
            wraps=analyse_sql_statements,
        ) as analyse_sql_statements_mock:
            linter.lint_all_migrations()
            self.assertEqual(analyse_sql_statements_mock.call_count, 2)

        cache = linter.new_cache
        cache.load()

        self.assertEqual(cache["4a3770a405738d457e2d23e17fb1f3aa"]["result"], "OK")
        self.assertEqual(cache["19fd3ea688fc05e2cc2a6e67c0b7aa17"]["result"], "ERR")
        self.assertListEqual(
            cache["19fd3ea688fc05e2cc2a6e67c0b7aa17"]["errors"],
            [
                {
                    "err_msg": "RENAMING tables",
                    "code": "RENAME_TABLE",
                    "table": None,
                    "column": None,
                }
            ],
        )

        # Start the Linter again -> should use cache now.
        linter = MigrationLinter(self.test_project_path)

        with mock.patch(
            "django_migration_linter.migration_linter.analyse_sql_statements",
            wraps=analyse_sql_statements,
        ) as analyse_sql_statements_mock:
            linter.lint_all_migrations()
            analyse_sql_statements_mock.assert_not_called()

        self.assertTrue(linter.has_errors)

    @mock.patch(
        "django_migration_linter.MigrationLinter._gather_all_migrations",
        return_value=[
            Migration("0001_create_table", "app_add_not_null_column"),
            Migration("0002_add_new_not_null_field", "app_add_not_null_column"),
        ],
    )
    def test_cache_different_databases(self, *args):
        linter = MigrationLinter(self.test_project_path, database="mysql")
        linter.old_cache.clear()
        linter.old_cache.save()

        linter = MigrationLinter(self.test_project_path, database="sqlite")
        linter.old_cache.clear()
        linter.old_cache.save()

        with mock.patch(
            "django_migration_linter.migration_linter.analyse_sql_statements",
            wraps=analyse_sql_statements,
        ) as analyse_sql_statements_mock:
            linter.lint_all_migrations()
            self.assertEqual(analyse_sql_statements_mock.call_count, 2)

        cache = linter.new_cache
        cache.load()

        self.assertEqual(cache["4a3770a405738d457e2d23e17fb1f3aa"]["result"], "OK")
        self.assertEqual(cache["19fd3ea688fc05e2cc2a6e67c0b7aa17"]["result"], "ERR")
        self.assertListEqual(
            cache["19fd3ea688fc05e2cc2a6e67c0b7aa17"]["errors"],
            [
                {
                    "err_msg": "RENAMING tables",
                    "code": "RENAME_TABLE",
                    "table": None,
                    "column": None,
                }
            ],
        )

        # Start the Linter again but with different database, should not be the same cache
        linter = MigrationLinter(self.test_project_path, database="mysql")

        with mock.patch(
            "django_migration_linter.migration_linter.analyse_sql_statements",
            wraps=analyse_sql_statements,
        ) as analyse_sql_statements_mock:
            linter.lint_all_migrations()
            self.assertEqual(analyse_sql_statements_mock.call_count, 2)

        cache = linter.new_cache
        cache.load()

        self.assertEqual(cache["4a3770a405738d457e2d23e17fb1f3aa"]["result"], "OK")
        self.assertEqual(cache["19fd3ea688fc05e2cc2a6e67c0b7aa17"]["result"], "ERR")
        self.assertListEqual(
            cache["19fd3ea688fc05e2cc2a6e67c0b7aa17"]["errors"],
            [
                {
                    "err_msg": "NOT NULL constraint on columns",
                    "code": "NOT_NULL",
                    "table": "app_add_not_null_column_a",
                    "column": "new_not_null_field",
                }
            ],
        )

        self.assertTrue(linter.has_errors)

    @mock.patch(
        "django_migration_linter.MigrationLinter._gather_all_migrations",
        return_value=[
            Migration("0001_initial", "app_ignore_migration"),
            Migration("0002_ignore_migration", "app_ignore_migration"),
        ],
    )
    def test_cache_ignored(self, *args):
        linter = MigrationLinter(self.test_project_path, ignore_name_contains="0001")
        linter.old_cache.clear()
        linter.old_cache.save()

        with mock.patch(
            "django_migration_linter.migration_linter.analyse_sql_statements",
            wraps=analyse_sql_statements,
        ) as analyse_sql_statements_mock:
            linter.lint_all_migrations()
            self.assertEqual(analyse_sql_statements_mock.call_count, 1)

        cache = linter.new_cache
        cache.load()

        self.assertEqual(cache["0fab48322ba76570da1a3c193abb77b5"]["result"], "IGNORE")

        # Start the Linter again -> should use cache now.
        linter = MigrationLinter(self.test_project_path)

        with mock.patch(
            "django_migration_linter.migration_linter.analyse_sql_statements",
            wraps=analyse_sql_statements,
        ) as analyse_sql_statements_mock:
            linter.lint_all_migrations()
            self.assertEqual(analyse_sql_statements_mock.call_count, 1)

    @mock.patch(
        "django_migration_linter.MigrationLinter._gather_all_migrations",
        return_value=[
            Migration("0001_create_table", "app_add_not_null_column"),
            Migration("0002_add_new_not_null_field", "app_add_not_null_column"),
        ],
    )
    @unittest.skip("find an easier way to make it work (file modification)")
    def test_cache_modified(self, *args):
        linter = MigrationLinter(self.test_project_path)
        linter.lint_all_migrations()
        cache = linter.old_cache
        cache.load()

        print(cache.keys())
        self.assertEqual(
            "OK",
            cache["348cddc5ae792175237a1d3069341455"]["result"],
            "If this fails, tearDown might have failed to remove "
            "the modification from the migration.",
        )
        self.assertEqual("ERR", cache["223007ccd7b35f565f925f1ccbbe6578"]["result"])
        self.assertListEqual(
            [
                {
                    u"err_msg": u"ALTERING columns (Could be backward compatible. "
                    u"You may ignore this migration.)",
                    u"code": u"ALTER_COLUMN",
                    u"table": u"test_app_a",
                    u"column": None,
                }
            ],
            cache["223007ccd7b35f565f925f1ccbbe6578"]["errors"],
        )

        # Modify migration
        backup_migration_file = self.MIGRATION_FILE + "_backup"
        shutil.copy2(self.MIGRATION_FILE, backup_migration_file)
        with open(self.MIGRATION_FILE, "a") as f:
            f.write("# modification at the end of the file")

        # Start the Linter again -> Cache should look different now
        linter = MigrationLinter(fixtures.ALTER_COLUMN)
        linter.lint_all_migrations()
        cache = linter.new_cache
        cache.load()
        shutil.copy2(backup_migration_file, self.MIGRATION_FILE)
        os.remove(backup_migration_file)

        self.assertNotIn("8589aa107b6da296c4b49cd2681d2230", cache)
        self.assertEqual(cache["fbee628b1ab4bd1c14f8a4b41123e7cf"]["result"], "OK")
