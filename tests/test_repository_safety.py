import contextlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import check_repository_safety as safety


class RepositorySafetyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.git('init', '-q')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], stderr=subprocess.PIPE)

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def test_private_paths_and_public_inputs(self):
        for name in ['.env', '.env.production', 'deploy/site.env', 'docs/private/runbook.md',
                     'instance/live.json', 'archive.sql.gz', 'copy.dump', 'cert.p12',
                     'data.db-wal', '.claude/worktrees/task/a.py', 'deploy/site.conf',
                     'docs/deployment-history.md', 'docs/task-production-deployment.md']:
            with self.subTest(name=name):
                self.assertTrue(safety.forbidden_path(name))
        for name in ['.env.example', '.env.production.example', 'migrations/0001_initial.sql',
                     'deploy/nginx.conf.example', 'docs/operations.md', 'static/app.js',
                     'frontend/package-lock.json', 'static/season-data/s18/champions.json']:
            with self.subTest(name=name):
                self.assertFalse(safety.forbidden_path(name))

    def test_index_not_working_copy_is_checked(self):
        self.write('运维 notes.md', 'Server: ' + '45.67.89.12')
        self.git('add', '.')
        self.write('运维 notes.md', 'Server: example.com')
        self.assertIn(('运维 notes.md', 1, 'non-example-ipv4'), safety.check(self.root))
        self.assertEqual([], safety.check(self.root, worktree=True))

    def test_unstaged_secret_does_not_change_index_result(self):
        self.write('config.md', 'Public instructions')
        self.git('add', '.')
        self.write('config.md', 'Server: ' + '45.67.89.12')
        self.assertEqual([], safety.check(self.root))
        self.assertTrue(safety.check(self.root, worktree=True))

    def test_worktree_finds_nonignored_new_files(self):
        self.write('new.md', 'Server: ' + '45.67.89.12')
        self.assertEqual([], safety.check(self.root))
        self.assertTrue(safety.check(self.root, worktree=True))

    def test_ignored_local_files_are_not_read_but_force_added_files_fail(self):
        self.write('.gitignore', '.env*\nprivate/\n')
        self.write('.env.production', 'PRIVATE=not-real')
        self.write('private/notes.md', 'Server: ' + '45.67.89.12')
        self.git('add', '.gitignore')
        self.assertEqual([], safety.check(self.root, worktree=True))
        self.git('add', '-f', '.env.production')
        self.assertIn(('.env.production', 0, 'private-or-generated-file'), safety.check(self.root))
        self.assertTrue(safety.check(self.root, worktree=True))

    def test_staged_removal_keeps_private_copy_without_failing(self):
        self.write('.env', 'PRIVATE=not-real')
        self.git('add', '.env')
        self.git('rm', '--cached', '--', '.env')
        self.assertTrue((self.root / '.env').exists())
        self.assertEqual([], safety.check(self.root))

    def test_secret_rules_apply_to_tests_too(self):
        key = '-----BEGIN ' + 'OPENSSH PRIVATE KEY-----'
        token = 'ghp_' + 'a' * 36
        url = 'postgresql://user:' + 'not-a-real-secret' + '@database.example.com/db'
        found = safety.scan_content('tests/fixture.py', '\n'.join([key, token, url]).encode())
        self.assertEqual([(1, 'private-key'), (2, 'access-token'), (3, 'credential-url')], found)

    def test_examples_and_vector_numbers_are_not_server_addresses(self):
        self.assertEqual([], safety.scan_content('docs/operations.md',
            b'https://203.0.113.5 http://127.0.0.1:5000 192.0.2.1 198.51.100.2\n'
            b'postgresql://user:replace-with-password@database.example.com/db'))
        vector = b'/* https://example.com */ const path="M13.88.7.71";'
        self.assertEqual([], safety.scan_content('static/vendor/icons.js', vector))

    def test_url_host_in_code_is_checked(self):
        url = 'url="https://' + '45.67.89.12' + '/api"'
        self.assertEqual([(1, 'non-example-ipv4')], safety.scan_content('config.py', url.encode()))

    def test_symlink_index_entry_is_not_followed(self):
        self.write('target.txt', 'example')
        oid = self.git('hash-object', '-w', 'target.txt').decode().strip()
        self.git('update-index', '--add', '--cacheinfo', f'120000,{oid},link')
        self.assertIn(('link', 0, 'unmerged-or-nonregular-entry'), safety.check(self.root))

    def test_output_never_prints_matched_values(self):
        secret = 'not-a-real-' + 'secret-for-output-test'
        self.write('config.txt', 'postgresql://user:' + secret + '@database.example.com/db')
        self.git('add', '.')
        output = io.StringIO()
        with patch.object(safety, 'ROOT', self.root), contextlib.redirect_stdout(output):
            self.assertEqual(1, safety.main([]))
        self.assertNotIn(secret, output.getvalue())
        self.assertIn('config.txt:1: credential-url', output.getvalue())

    def test_repository_ignore_policy_preserves_public_inputs(self):
        self.write('.gitignore', (safety.ROOT / '.gitignore').read_text(encoding='utf-8'))
        blocked = ['.env.production', 'private/operations.md', 'backups/release.dump',
                   'copy.tar.gz', 'docs/deployment-history.md', 'deploy/site.service',
                   '.ssh/config', 'archive.sqlite-wal']
        public = ['.env.example', '.env.production.example', 'migrations/0001_initial.sql',
                  'deploy/jcc.service.example', 'static/app.js', 'docs/operations.md']
        result = subprocess.run(['git', '-C', str(self.root), 'check-ignore', '-z', '--stdin'],
                                input=('\0'.join(blocked + public) + '\0').encode('utf-8'),
                                capture_output=True, check=True)
        self.assertEqual(set(blocked), set(result.stdout.decode('utf-8').rstrip('\0').split('\0')))

    def test_git_failure_blocks_publication(self):
        output = io.StringIO()
        with patch.object(safety, 'ROOT', self.root / 'missing'), contextlib.redirect_stdout(output):
            self.assertEqual(2, safety.main([]))


if __name__ == '__main__':
    unittest.main()
