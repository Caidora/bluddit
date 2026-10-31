import contextlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "deploy.py"
spec = importlib.util.spec_from_file_location("deploy", MODULE)
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "app"
        self.payload = Path(self.temp.name) / "payload"
        self.payload.mkdir()
        self.operation = deploy.Deployment(self.root, self.payload, "example.com", "ops@example.com")

    def test_lock_rejects_overlapping_operations(self):
        other = deploy.Deployment(self.root, self.payload, "example.com", "ops@example.com")
        with self.operation.locked():
            with self.assertRaisesRegex(deploy.DeploymentError, "deployment lock"):
                with other.locked():
                    self.fail("Second operation acquired lock")

    def test_invalid_path_and_domain_rejected_before_mutation(self):
        for path, domain in [("/", "example.com"), ("relative", "example.com"), ("/opt/../etc", "example.com"), ("/opt/bluddit", "https://example.com")]:
            with self.subTest(path=path, domain=domain), self.assertRaises(deploy.DeploymentError):
                deploy.Deployment(Path(path), self.payload, domain, "")

    def test_pull_failure_does_not_start_services_or_advance_current(self):
        calls = []

        def compose(release, *args):
            calls.append(args)
            if args == ("pull",):
                raise deploy.DeploymentError("pull failed")

        with patch.object(self.operation, "compose", side_effect=compose), patch.object(self.operation, "activate") as activate:
            with self.assertRaisesRegex(deploy.DeploymentError, "pull failed"):
                self.operation.rollout(self.root / "release")
        self.assertFalse(any(args[0] == "up" for args in calls))
        activate.assert_not_called()

    def test_unhealthy_release_does_not_advance_successful_reference(self):
        with patch.object(self.operation, "compose"), patch.object(self.operation, "healthy", side_effect=deploy.DeploymentError("unhealthy")), patch.object(self.operation, "activate") as activate:
            with self.assertRaisesRegex(deploy.DeploymentError, "unhealthy"):
                self.operation.rollout(self.root / "release")
            activate.assert_not_called()

    def test_previous_release_and_idempotent_activation(self):
        with self.operation.locked():
            first = self.operation.releases / "first"
            second = self.operation.releases / "second"
            first.mkdir()
            second.mkdir()
            self.operation.activate(first)
            self.operation.activate(second)
            self.operation.activate(second)
            self.assertEqual((self.root / "current").resolve(), second.resolve())
            self.assertEqual((self.root / "previous").resolve(), first.resolve())

    def test_rollback_refuses_different_database_image(self):
        self.root.mkdir()
        old, new = self.root / "old", self.root / "new"
        old.mkdir()
        new.mkdir()
        (old / "manifest.json").write_text(json.dumps({"DB_IMAGE": "old"}))
        (new / "manifest.json").write_text(json.dumps({"DB_IMAGE": "new"}))
        with patch.object(self.operation, "authenticate"), patch.object(self.operation, "resolve_release", return_value=old), patch.object(self.operation, "current", return_value=new), patch.object(self.operation, "rollout") as rollout:
            with self.assertRaisesRegex(deploy.DeploymentError, "compatibility"):
                self.operation.execute("rollback", "target")
            rollout.assert_not_called()

    def test_rollback_cannot_traverse_release_directory(self):
        with self.assertRaisesRegex(deploy.DeploymentError, "Release ID"):
            self.operation.resolve_release("../../etc")

    def test_command_failures_do_not_leak_output_or_arguments(self):
        result = subprocess.CompletedProcess([], 1, b"private-host", b"secret-password")
        with patch.object(subprocess, "run", return_value=result):
            with self.assertRaises(deploy.DeploymentError) as error:
                deploy.run(["docker", "secret-argument"])
        self.assertNotIn("secret", str(error.exception))
        self.assertNotIn("private-host", str(error.exception))

    def test_missing_ssh_configuration_names_missing_secret(self):
        script = MODULE.parent / "scripts/ssh-setup.sh"
        result = subprocess.run(["bash", str(script)], env={"PATH": os.environ["PATH"]}, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing repository secret: DEPLOY_HOST", result.stdout)


if __name__ == "__main__":
    unittest.main()
