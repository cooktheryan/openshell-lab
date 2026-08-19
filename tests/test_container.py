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
        entries = [
            line.split("=", 1)
            for line in lock.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")
        ]
        keys = [key for key, _value in entries]
        if len(keys) != len(set(keys)) or any(not key or not value for key, value in entries):
            raise AssertionError("container lock contains duplicate or empty entries")
        cls.lock = dict(entries)
        cls.containerfile = containerfile.read_text(encoding="utf-8")

    def test_base_is_stable_version_and_immutable_digest(self):
        self.assertRegex(self.lock["tag"], r"^0\.3\.[0-9]+$")
        self.assertRegex(self.lock["digest"], r"^sha256:[0-9a-f]{64}$")
        self.assertNotIn("dev", self.lock["tag"])
        self.assertNotEqual("latest", self.lock["tag"])
        reference = f'{self.lock["name"]}@{self.lock["digest"]}'
        first_instruction = next(
            line for line in self.containerfile.splitlines() if line and not line.startswith("#")
        )
        self.assertEqual(f"FROM {reference}", first_instruction)

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
        self.assertEqual(
            ["COPY --chown=1500:1500 src/openshell_lab /opt/openshell-lab/openshell_lab"],
            copy_lines,
        )
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", self.containerfile)
        install = re.search(r"RUN dnf install -y ([^&]+)", self.containerfile)
        self.assertIsNotNone(install)
        packages = install.group(1).replace("\\", " ").split()
        self.assertEqual(["python3", "shadow-utils"], packages)

    def test_image_does_not_copy_credentials(self):
        lowered = self.containerfile.lower()
        for forbidden in (".env", "credentials", "id_rsa", "api_key", "*.pem"):
            self.assertNotIn(forbidden, lowered)

    def test_resolver_rejects_mutable_and_development_tags(self):
        resolver = (CONTAINER / "resolve-base.sh").read_text(encoding="utf-8")
        self.assertIn("skopeo inspect", resolver)
        self.assertIn("0\\.3\\.[0-9]", resolver)
        self.assertNotRegex(resolver, re.compile(r"inspect.*:latest"))

    def test_resolver_paginates_and_cleans_temporary_lock(self):
        resolver = (CONTAINER / "resolve-base.sh").read_text(encoding="utf-8")
        self.assertIn("has_additional", resolver)
        self.assertIn("page=$page", resolver)
        self.assertIn("trap 'rm -f -- \"$temporary\"' EXIT", resolver)


if __name__ == "__main__":
    unittest.main()
