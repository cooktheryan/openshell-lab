import unittest

try:
    from openshell_lab import lab4_policy
except ImportError:
    lab4_policy = None


def effective_policy(network_marker=None):
    policy = {
        "version": 1,
        "filesystem_policy": {
            "include_workdir": False,
            "read_only": [
                "/usr",
                "/lib64",
                "/etc",
                "/proc",
                "/dev/urandom",
                "/opt/openshell-lab",
            ],
            "read_write": ["/tmp", "/dev/null"],
        },
        "landlock": {"compatibility": "hard_requirement"},
        "process": {"run_as_user": "1500", "run_as_group": "1500"},
    }
    if network_marker is not None:
        policy["network_policies"] = network_marker
    return {"status": "effective", "policy": policy}


class Lab4EffectivePolicyTests(unittest.TestCase):
    def require_validator(self):
        self.assertIsNotNone(
            lab4_policy,
            "openshell_lab.lab4_policy must validate remote effective policy",
        )
        return lab4_policy

    def test_omitted_empty_network_map_is_accepted_as_default_deny(self):
        self.require_validator().validate_effective_policy(effective_policy())

    def test_explicit_empty_network_map_is_accepted(self):
        self.require_validator().validate_effective_policy(effective_policy({}))

    def test_any_effective_ordinary_network_grant_is_rejected(self):
        document = effective_policy(
            {"unexpected": {"endpoints": [{"host": "example.com"}]}}
        )
        with self.assertRaisesRegex(ValueError, "ordinary network"):
            self.require_validator().validate_effective_policy(document)

    def test_any_additional_read_only_path_is_rejected(self):
        document = effective_policy()
        document["policy"]["filesystem_policy"]["read_only"].append(
            "/run/secrets"
        )
        with self.assertRaisesRegex(ValueError, "read-only paths"):
            self.require_validator().validate_effective_policy(document)


if __name__ == "__main__":
    unittest.main()
