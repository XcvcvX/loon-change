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
        self.assertNotIn("api-htp.beizi.biz", result)
        self.assertNotIn("adservice.sigmob.cn", result)
        self.assertIn("api.hellobike.com", result)  # existed before PR #129
        for host in HELLOBIKE_ADDED_MITM_HOSTS:
            self.assertNotIn(host, result)
        self.assertIn("creditcardapp.bankcomm.cn", result)
        self.assertEqual(apply(result), result)

    def test_maidanba_rule_has_valid_single_escaped_url_pattern(self):
        expected = r"^https?:\/\/creditcard\.bankcomm\.(?:cn|com)\/tofimg\/bucket-pj-btss-tfcn-dmz\/OSS-F\/.+/i"
        self.assertIn(expected, RULE)
        self.assertNotIn(r"^https?:\\/\\/", RULE)
        result = apply(BASE)
        script_section = result.split("[Script]", 1)[1].split("[MITM]", 1)[0]
        self.assertIn(RULE, script_section)
        self.assertIn("binary_body_mode=true", RULE)


    def test_pdd_httpdns_ipv4_rule_requires_path_boundary(self):
        base = r"""#!name=test
[Rule]
AND, ((URL-REGEX, "^http:\/\/((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\/d(\d)?"), (USER-AGENT, "*com.xunmeng.pinduoduo*")), REJECT
AND,((URL-REGEX,"^http:\/\/((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\/d(\d)?"),(USER-AGENT,"*com.xunmeng.pinduoduo*")),REJECT
[Rewrite]
^https?:\/\/example\.com reject
[Script]
[MITM]
hostname = creditcard.bankcomm.cn, creditcard.bankcomm.com, creditcardapp.bankcomm.cn, creditcardapp.bankcomm.com
"""
        result = apply(base)
        self.assertEqual(result.count(r"\/d(\d)?(?:\?|$)"), 2)
        self.assertEqual(apply(result), result)

    def test_pdd_httpdns_ipv6_query_boundary_is_preserved_and_repaired(self):
        original = r"""#!name=test
[Rule]
AND, ((URL-REGEX, "^http:\/\/\[[0-9a-fA-F:]+\]\/d(\d)?\?"), (USER-AGENT, "*com.xunmeng.pinduoduo*")), REJECT
[Rewrite]
^https?:\/\/example\.com reject
[Script]
[MITM]
hostname = creditcard.bankcomm.cn, creditcard.bankcomm.com, creditcardapp.bankcomm.cn, creditcardapp.bankcomm.com
"""
        result = apply(original)
        self.assertIn(r"\/d(\d)?\?", result)
        self.assertNotIn(r"\/d(\d)?(?:\?|$)\?", result)
        self.assertEqual(apply(result), result)

        # Repair the exact malformed IPv6 form emitted by the previous override.
        previous_bad = original.replace(r"\/d(\d)?\?", r"\/d(\d)?(?:\?|$)\?")
        repaired = apply(previous_bad)
        self.assertIn(r"\/d(\d)?\?", repaired)
        self.assertNotIn(r"\/d(\d)?(?:\?|$)\?", repaired)

    def test_pdd_httpdns_rule_drift_fails_closed(self):
        marker_line = 'AND, ((URL-REGEX, "changed"), (USER-AGENT, "*com.xunmeng.pinduoduo*")), REJECT'
        base = BASE.replace("[Rewrite]", "[Rule]\n" + marker_line + "\n[Rewrite]")
        with self.assertRaises(ValueError):
            apply(base)


    def test_merges_adjacent_same_condition_response_json_actions_in_order(self):
        first = 'response if ${url} ~= /^https:\\/\\/api\\.example\\.com/ then response.json.delete("data.a")'
        second = 'response if ${url} ~= /^https:\\/\\/api\\.example\\.com/ then response.json.jq(".data.b = []")'
        from apply_local_overrides import merge_adjacent_response_json_rewrites
        result, count = merge_adjacent_response_json_rewrites([first, "", second])
        self.assertEqual(count, 1)
        self.assertEqual(len(result), 1)
        self.assertIn(" | ", result[0])
        self.assertLess(result[0].index("data.a"), result[0].index("data.b"))

    def test_does_not_merge_different_conditions_or_request_actions(self):
        from apply_local_overrides import merge_adjacent_response_json_rewrites
        a = 'response if ${url} ~= /api/ then response.json.delete("data.a")'
        b = 'response if ${url} ~= /other/ then response.json.delete("data.b")'
        result, count = merge_adjacent_response_json_rewrites([a, b])
        self.assertEqual(count, 0)
        self.assertEqual(result, [a, b])

    def test_removes_only_exact_duplicate_soul_teenager_reject_rule(self):
        from apply_local_overrides import SOUL_TEENAGER_CONFIG_DUPLICATE
        duplicate = SOUL_TEENAGER_CONFIG_DUPLICATE
        similar = duplicate.replace("reject-dict", "reject")
        base = BASE.replace("[Rewrite]", "[Rewrite]\\n" + duplicate + "\\n" + duplicate + "\\n" + similar)
        result = apply(base)
        rewrite = result.split("[Rewrite]", 1)[1].split("[Script]", 1)[0]
        self.assertEqual(rewrite.count(duplicate), 1)
        self.assertEqual(rewrite.count(similar), 1)
        self.assertEqual(apply(result), result)

    def test_requires_bankcomm_mitm_hosts(self):
        with self.assertRaises(ValueError):
            apply(BASE.replace("creditcard.bankcomm.com, ", ""))

if __name__ == "__main__":
    unittest.main()
