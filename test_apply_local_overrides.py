import unittest
from apply_local_overrides import apply, RULE, HELLOBIKE_ADDED_MITM_HOSTS

BASE = """#!name=test
#!sources=existing+ZenmoFeiShi-Qx-HelloBike(ScriptHub-Loon)
[Rewrite]
^https?:\\/\\/example\\.com reject
^https?:\\/\\/api-htp\\.beizi\\.biz\\/mb\\/sdk0\\/json(?:\\?|$) reject-200
^https?:\\/\\/adservice\\.sigmob\\.cn\\/ad\\/v4 reject-200
[Script]
response if ${url} ~= /^https?:\\/\\/example/ then reject
http-response ^https?:\\/\\/api\\.hellobike\\.com(?::443)?\\/secretkey script-path=http://script.hub/convert/_start_/upstream.js, tag=easybike-ad
http-response ^https?:\\/\\/taxiapi\\.hellobike\\.com\\/api script-path=http://script.hub/convert/_start_/upstream.js, tag=easybike-ad
response if ${url} ~= /^https?:\\/\\/api\\.hellobike\\.com/ then script("https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/hellobike-clean.js") with tag="哈啰净化-接口", requires_body=true
[MITM]
hostname = creditcard.bankcomm.cn, creditcard.bankcomm.com, creditcardapp.bankcomm.cn, creditcardapp.bankcomm.com, api.hellobike.com, taxiapi.hellobike.com, marketingapi.hellobike.com, entertainment.hellobike.com, resource.51downapp.cn, api-htp.beizi.biz, adservice.sigmob.cn, tm.sigmob.cn, mi.gdt.qq.com, v2mi.gdt.qq.com
"""

class LocalOverrideTests(unittest.TestCase):
    def test_removes_pr129_hellobike_integration_and_preserves_existing_hosts(self):
        result = apply(BASE)
        self.assertIn(RULE, result)
        self.assertNotIn("ZenmoFeiShi-Qx-HelloBike(ScriptHub-Loon)", result)
        self.assertNotIn("script.hub/convert", result)
        self.assertNotIn("easybike-ad", result)
        self.assertNotIn("hellobike-clean.js", result)
        self.assertNotIn("api-htp\\\\.beizi", result)
        self.assertNotIn("adservice\\\\.sigmob", result)
        self.assertIn("api.hellobike.com", result)  # existed before PR #129
        for host in HELLOBIKE_ADDED_MITM_HOSTS:
            self.assertNotIn(host, result)
        self.assertIn("creditcardapp.bankcomm.cn", result)
        self.assertEqual(apply(result), result)

    def test_requires_bankcomm_mitm_hosts(self):
        with self.assertRaises(ValueError):
            apply(BASE.replace("creditcard.bankcomm.com, ", ""))

if __name__ == "__main__":
    unittest.main()
