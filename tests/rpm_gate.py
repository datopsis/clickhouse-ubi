"""Run with /usr/bin/python3: exercise real librpm comparison and mocked DNF."""
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from ubi_repoquery import at_least, evr, query
from lib.ubi_repos import configure


class RpmTests(unittest.TestCase):
    def test_epoch_version_release_ordering(self):
        for candidate, fixed, expected in [
            ('2.37.4-28.el9_9', '2.37.4-28.el9_9', True),
            ('2.37.4-28.el9_9.1', '2.37.4-28.el9_9', True),
            ('2.37.4-28.el9_9', '2.37.4-28.el9_9.1', False),
            ('2.37.4-25.el9', '2.37.4-28.el9_9', False),
            ('1:1.0-1', '0:9.0-99', True), ('0:9.0-99', '1:1.0-1', False),
            ('1.0-2', '0:1.0-2', True), ('1.0-10', '1.0-9', True),
            ('1.0~rc1-1', '1.0-1', False), ('1.0^git1-1', '1.0-1', True),
        ]:
            with self.subTest(candidate=candidate, fixed=fixed):
                self.assertEqual(at_least(candidate, fixed), expected)

    def test_unparsable_versions(self):
        for value in ['', 'unspecified', '1.0', '>=1.0-1', '1:2:1.0-1', '1.0-1,1.0-2',
                      '-1', '1.0-', ' 1.0-1', None, 1]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                evr(value)

    def test_dnf_query_filters_arch_and_uses_any_fix_branch(self):
        base = Mock()
        filtered = base.sack.query.return_value.available.return_value.filter
        filtered.return_value = [SimpleNamespace(epoch=0, version='1.0', release='2')]
        result = query(base, {'name': 'sample', 'fixes': ['1.0-3', '1.0-2']}, 'arm64')
        self.assertTrue(result['available'])
        filtered.assert_called_once_with(name='sample', arch=['aarch64', 'noarch'])
        self.assertFalse(query(base, {'name': 'sample', 'fixes': ['1.0-3']}, 'arm64')['available'])
        filtered.return_value = []
        self.assertFalse(query(base, {'name': 'sample', 'fixes': ['1.0-2']}, 'arm64')['available'])
        with self.assertRaises(ValueError):
            query(base, {'name': 'sample', 'fixes': ['1.0-2', 'invalid']}, 'arm64')

    def test_missing_or_disabled_repo_fails(self):
        for enabled in [[], [SimpleNamespace(id='ubi-9-baseos-rpms')]]:
            base = Mock()
            base.conf.substitutions = {}
            base.repos.iter_enabled.return_value = enabled
            with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
                configure(base, tmp, 'amd64')

    def test_repository_errors_and_empty_sacks_fail_closed(self):
        for failure in ['metadata', 'empty', 'gpg']:
            base = Mock()
            base.conf.substitutions = {}
            with tempfile.TemporaryDirectory() as tmp:
                repo_file = Path(tmp) / 'ubi.repo'
                repo_file.write_text('test repo configuration')
                repos = [SimpleNamespace(id='ubi-9-' + name + '-rpms',
                                         repofile=str(repo_file), baseurl=['https://example.invalid'],
                                         mirrorlist='', metalink='', gpgcheck=failure != 'gpg')
                         for name in ['baseos', 'appstream', 'codeready-builder']]
                base.repos.iter_enabled.return_value = repos
                if failure == 'metadata':
                    base.fill_sack.side_effect = RuntimeError('metadata unavailable')
                base.sack.query.return_value.available.return_value.filter.return_value = []
                with self.assertRaises((ValueError, RuntimeError)):
                    configure(base, tmp, 'arm64')
                if failure != 'gpg':
                    self.assertTrue(all(r.skip_if_unavailable is False for r in repos))
                    self.assertTrue(all(r.metadata_expire == 0 for r in repos))



if __name__ == '__main__':
    unittest.main()
