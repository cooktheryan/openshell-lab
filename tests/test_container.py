from pathlib import Path
import re
import unittest


ROOT = Path(__file__).parents[1]
CONTAINER = ROOT / "container"


class ContainerArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        lock = CONTAINER / "base-image.lock"
        containerfile = CONTAINER / "Containerfile"
        if not lock.is_file() or not containerfile.is_file():
            raise AssertionError("container lock or Containerfile is missing")
        cls.lock = dict(
            line.split("=", 1)
            for line in lock.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")
        )
        cls.containerfile = containerfile.read_text(encoding="utf-8")

    def test_base_is_stable_version_and_immutable_digest(self):
        self.assertRegex(self.lock["tag"], r"^0\.3\.[0-9]+$")
        self.assertRegex(self.lock["digest"], r"^sha256:[0-9a-f]{64}$")
        self.assertNotIn("dev", self.lock["tag"])
        self.assertNotEqual("latest", self.lock["tag"])
        reference = f'{self.lock["name"]}@{self.lock["digest"]}'
        self.assertIn(f"FROM {reference}", self.containerfile)

    def test_lock_records_provenance(self):
        self.assertEqual("amd64", self.lock["architecture"])
        self.assertTrue(self.lock["created"].endswith("Z"))
        self.assertIn("resolved_at", self.lock)

    def test_image_declares_numeric_nonroot_user_and_bounded_app_location(self):
        self.assertRegex(self.containerfile, r"(?m)^USER 1500:1500$")
        self.assertIn("/opt/openshell-lab", self.containerfile)
        copy_lines = [
            line for line in self.containerfile.splitlines() if line.startswith("COPY ")
        ]
        self.assertTrue(copy_lines)
        self.assertTrue(all("/var/www/html" not in line for line in copy_lines))
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", self.containerfile)

    def test_image_does_not_copy_credentials(self):
        lowered = self.containerfile.lower()
        for forbidden in (".env", "credentials", "id_rsa", "api_key", "*.pem"):
            self.assertNotIn(forbidden, lowered)

    def test_resolver_rejects_mutable_and_development_tags(self):
        resolver = (CONTAINER / "resolve-base.sh").read_text(encoding="utf-8")
        self.assertIn("skopeo inspect", resolver)
        self.assertIn("0\\.3\\.[0-9]", resolver)
        self.assertNotRegex(resolver, re.compile(r"inspect.*:latest"))


if __name__ == "__main__":
    unittest.main()
