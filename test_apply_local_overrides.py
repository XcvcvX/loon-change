import unittest
from apply_local_overrides import (
    apply, RULE, HELLOBIKE_JS, HELLOBIKE_REWRITE_RULES,
    HELLOBIKE_SCRIPT_RULES, HELLOBIKE_MITM_HOSTS,
)

BASE = """#!name=test
#!sources=existing
[Rewrite]
^https?:\\/\\/example\\.com reject
[Script]
response if ${url} ~= /^https?:\\/\\/example\\.com/ then reject
response if ${url} ~= /^https?:\\/\\/api\\.hellobike\\.com/ then script("https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/hellobike-clean.js") with tag="哈啰净化-接口", requires_body=true
[MITM]
hostname = creditcard.bankcomm.cn, creditcard.bankcomm.com, creditcardapp.bankcomm.cn, creditcardapp.bankcomm.com
"""

class LocalOverrideTests(unittest.TestCase):
    def test_adds_bankcomm_rule_once_and_preserves_mitm(self):
        result = apply(BASE)
        self.assertIn(RULE, result)
        self.assertIn("creditcardapp.bankcomm.cn", result)
        self.assertEqual(apply(result), result)

    def test_replaces_legacy_hellobike_with_script_hub_conversion(self):
        result = apply(BASE)
        self.assertNotIn("scripts/hellobike-clean.js", result)
        self.assertNotIn("哈啰净化-接口", result)
        self.assertNotIn("action=static&ms=1&version=css_page_2@0", result)
        for rule in HELLOBIKE_REWRITE_RULES:
            self.assertIn(rule, result.split("[Rewrite]", 1)[1].split("[Script]", 1)[0])
        for rule in HELLOBIKE_SCRIPT_RULES:
            self.assertIn(rule, result.split("[Script]", 1)[1].split("[MITM]", 1)[0])
        self.assertIn("wrap_response=true&headers=", HELLOBIKE_JS)
        self.assertIn("ZenmoFeiShi-Qx-HelloBike(ScriptHub-Loon)", result)
        self.assertIn("type=qx-script&target=loon-script", HELLOBIKE_JS)
        taxi_rule = next(rule for rule in HELLOBIKE_SCRIPT_RULES if "taxiapi" in rule)
        self.assertIn('${request.method} == "POST"', taxi_rule)
        self.assertIn("${request.header['action']} == \"hitch.driver.journeyList\"", taxi_rule)
        self.assertNotIn("http-response ^https:", taxi_rule)
        for host in HELLOBIKE_MITM_HOSTS:
            self.assertIn(host, result)
        self.assertEqual(apply(result), result)

    def test_requires_bankcomm_mitm_hosts(self):
        with self.assertRaises(ValueError):
            apply(BASE.replace("creditcard.bankcomm.com, ", ""))

if __name__ == "__main__":
    unittest.main()
