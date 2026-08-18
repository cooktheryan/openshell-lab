from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
BOOTSTRAP = ROOT / "infra" / "remote" / "bootstrap-rhel10.sh"


class BootstrapScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not BOOTSTRAP.is_file():
            raise AssertionError(f"missing {BOOTSTRAP}")
        cls.text = BOOTSTRAP.read_text(encoding="utf-8")

    def test_installs_required_rhel_packages(self):
        for package in (
            "podman",
            "curl",
            "httpd",
            "python3",
            "git",
            "jq",
            "policycoreutils-python-utils",
            "firewalld",
        ):
            self.assertIn(package, self.text)
        self.assertIn("dnf", self.text)

    def test_creates_idempotent_private_two_gib_swap(self):
        self.assertIn("/swapfile", self.text)
        self.assertIn("2G", self.text)
        self.assertIn("chmod 0600", self.text)
        self.assertIn("mkswap", self.text)
        self.assertIn("swapon", self.text)
        self.assertIn("/etc/fstab", self.text)

    def test_configures_rootless_podman_and_pins_gateway_driver(self):
        self.assertIn("loginctl enable-linger", self.text)
        self.assertIn("systemctl --user enable --now podman.socket", self.text)
        self.assertIn('compute_drivers = ["podman"]', self.text)
        self.assertIn("gateway.toml", self.text)
        self.assertIn("systemctl --user restart openshell-gateway", self.text)

    def test_uses_official_installer_and_verifies_gateway(self):
        self.assertIn(
            "https://raw.githubusercontent.com/NVIDIA/OpenShell/main/install.sh",
            self.text,
        )
        self.assertIn("openshell status", self.text)
        self.assertIn("openshell whoami", self.text)


if __name__ == "__main__":
    unittest.main()
