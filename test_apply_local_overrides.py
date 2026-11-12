import unittest
from apply_local_overrides import apply, RULE, HELLOBIKE_RULES, HELLOBIKE_MITM_HOSTS

BASE = """#!name=test
[Script]
response if ${url} ~= /^https?:\\/\\/example\\.com/ then reject
[MITM]
hostname = creditcard.bankcomm.cn, creditcard.bankcomm.com, creditcardapp.bankcomm.cn, creditcardapp.bankcomm.com
"""

class LocalOverrideTests(unittest.TestCase):
    def test_adds_rule_once_and_preserves_mitm(self):
        result = apply(BASE)
        self.assertIn(RULE, result)
        self.assertIn("creditcardapp.bankcomm.cn", result)
        self.assertEqual(apply(result), result)

    def test_adds_hellobike_rules_and_required_mitm_hosts(self):
        result = apply(BASE)
        for rule in HELLOBIKE_RULES:
            self.assertIn(rule, result)
        for host in HELLOBIKE_MITM_HOSTS:
            self.assertIn(host, result)
        self.assertEqual(apply(result), result)

    def test_requires_target_mitm_hosts(self):
        with self.assertRaises(ValueError):
            apply(BASE.replace("creditcard.bankcomm.com, ", ""))

if __name__ == "__main__":
    unittest.main()
