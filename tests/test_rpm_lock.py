import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/lib"))
import rpm_lock

SPEC = importlib.util.spec_from_file_location("install_rpm_lock", ROOT / "scripts/install-rpm-lock.py")
INSTALLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALLER)


class RpmLockTests(unittest.TestCase):
    def setUp(self):
        self.lock = rpm_lock.read(ROOT / "artifacts/rpm-lock.json")

    def test_committed_lock_and_bases(self):
        rpm_lock.validate(self.lock)
        rpm_lock.check_bases(self.lock, ROOT)

    def test_rejects_invalid_inputs(self):
        cases = []
        for field, value in (("nevra", "bash-5.1.8-9.el9.x86_64"),
                             ("sha256", "not-a-hash"),
                             ("url", "http://cdn-ubi.redhat.com/package.rpm"),
                             ("url", "https://example.com/package.rpm")):
            lock = copy.deepcopy(self.lock)
            lock["architectures"]["amd64"][0][field] = value
            cases.append(lock)
        lock = copy.deepcopy(self.lock)
        del lock["architectures"]["arm64"]
        cases.append(lock)
        lock = copy.deepcopy(self.lock)
        lock["architectures"]["amd64"] = []
        cases.append(lock)
        lock = copy.deepcopy(self.lock)
        lock["architectures"]["amd64"].append(lock["architectures"]["amd64"][0])
        cases.append(lock)
        lock = copy.deepcopy(self.lock)
        lock["architectures"]["amd64"] = [e for e in lock["architectures"]["amd64"] if not e["nevra"].startswith("bash-")]
        cases.append(lock)
        lock = copy.deepcopy(self.lock)
        lock["architectures"]["amd64"] = lock["architectures"]["arm64"]
        cases.append(lock)
        lock = copy.deepcopy(self.lock)
        lock["reviewed_by"] = "not permitted"
        cases.append(lock)
        for lock in cases:
            with self.subTest(lock=lock), self.assertRaises(ValueError):
                rpm_lock.validate(lock)

    def test_duplicate_json_key(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text('{"schema_version": 1, "schema_version": 1}')
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                rpm_lock.read(path)

    def test_base_pin_drift_in_either_containerfile(self):
        for filename in ("Containerfile", "Containerfile.scap"):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for name in ("Containerfile", "Containerfile.scap"):
                    text = (ROOT / name).read_text()
                    if name == filename:
                        text = text.replace(self.lock["base_images"]["builder"], "different")
                    (root / name).write_text(text)
                with self.assertRaisesRegex(ValueError, "base pin"):
                    rpm_lock.check_bases(self.lock, root)

    def test_render_is_independent_of_object_key_order(self):
        reordered = json.loads(json.dumps(self.lock, sort_keys=False),
                               object_pairs_hook=lambda pairs: dict(reversed(pairs)))
        self.assertEqual(rpm_lock.render(self.lock), rpm_lock.render(reordered))

    def test_tampered_download_stops_before_rpm_or_dnf(self):
        calls = []

        def download(command, **kwargs):
            calls.append(command[0])
            self.assertEqual(command[0], "curl")
            Path(command[command.index("--output") + 1]).write_bytes(b"tampered RPM")

        with tempfile.TemporaryDirectory() as directory, patch("subprocess.run", side_effect=download), patch("subprocess.check_output") as query:
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                INSTALLER.install(self.lock, "amd64", Path(directory) / "root")
            query.assert_not_called()
        self.assertEqual(calls, ["curl"])

    def test_header_identity_is_checked_after_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "package.rpm"
            path.write_bytes(b"test fixture")
            entry = {"nevra": "expected-0:1-1.noarch", "sha256": rpm_lock.digest(path)}
            with patch("subprocess.check_output", return_value="unexpected-0:1-1.noarch"):
                with self.assertRaisesRegex(ValueError, "NEVRA mismatch"):
                    rpm_lock.verify_rpm(path, entry)


if __name__ == "__main__":
    unittest.main()
