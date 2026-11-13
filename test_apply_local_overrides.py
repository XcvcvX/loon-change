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

    def test_removes_soul_https_rule_only_after_covering_http_rule(self):
        from apply_local_overrides import SOUL_TEENAGER_CONFIG_BROAD_RULE, SOUL_TEENAGER_CONFIG_HTTPS_RULE
        broad = SOUL_TEENAGER_CONFIG_BROAD_RULE
        narrow = SOUL_TEENAGER_CONFIG_HTTPS_RULE
        similar = narrow.replace("reject-dict", "reject")
        base = BASE.replace("[Rewrite]", "[Rewrite]\n" + broad + "\n" + narrow + "\n" + similar)
        result = apply(base)
        rewrite = result.split("[Rewrite]", 1)[1].split("[Script]", 1)[0]
        self.assertEqual(sum(item.strip() == broad for item in rewrite.splitlines()), 1)
        self.assertEqual(sum(item.strip() == narrow for item in rewrite.splitlines()), 0)
        self.assertEqual(sum(item.strip() == similar for item in rewrite.splitlines()), 1)
        self.assertEqual(apply(result), result)

    def test_preserves_soul_https_rule_if_broader_rule_comes_later(self):
        from apply_local_overrides import SOUL_TEENAGER_CONFIG_BROAD_RULE, SOUL_TEENAGER_CONFIG_HTTPS_RULE
        base = BASE.replace("[Rewrite]", "[Rewrite]\n" + SOUL_TEENAGER_CONFIG_HTTPS_RULE + "\n" + SOUL_TEENAGER_CONFIG_BROAD_RULE)
        result = apply(base)
        rewrite = result.split("[Rewrite]", 1)[1].split("[Script]", 1)[0]
        self.assertEqual(sum(item.strip() == SOUL_TEENAGER_CONFIG_HTTPS_RULE for item in rewrite.splitlines()), 1)


    def test_removes_peopleapp_rules_shadowed_by_earlier_legacy_rejects(self):
        from apply_local_overrides import (
            PEOPLEAPP_HOME_AD_BROAD_RULE, PEOPLEAPP_HOME_AD_SHADOW_RULE,
            PEOPLEAPP_IMAGE_AD_BROAD_RULE, PEOPLEAPP_IMAGE_AD_SHADOW_RULE,
        )
        expected_home_shadow = r"request if ${url} ~= /^https?:\/\/app\.peopleapp\.com\/Api\/\d+\/HomeApi\/(adv|getAdvertImage)/ then reject(404)"
        expected_image_shadow = r"request if ${url} ~= /^https?:\/\/adstatic\.peopleapp\.com\/upload\/AppLoad\/.*\.(jpg|png)/ then reject(200)"
        self.assertEqual(PEOPLEAPP_HOME_AD_SHADOW_RULE, expected_home_shadow)
        self.assertEqual(PEOPLEAPP_IMAGE_AD_SHADOW_RULE, expected_image_shadow)
        base = BASE.replace(
            "[Rewrite]",
            "[Rewrite]\n" + PEOPLEAPP_HOME_AD_BROAD_RULE + "\n" + expected_home_shadow
            + "\n" + PEOPLEAPP_IMAGE_AD_BROAD_RULE + "\n" + expected_image_shadow
        )
        result = apply(base)
        rewrite = result.split("[Rewrite]", 1)[1].split("[Script]", 1)[0]
        self.assertEqual(sum(x.strip() == PEOPLEAPP_HOME_AD_BROAD_RULE for x in rewrite.splitlines()), 1)
        self.assertEqual(sum(x.strip() == PEOPLEAPP_HOME_AD_SHADOW_RULE for x in rewrite.splitlines()), 0)
        self.assertEqual(sum(x.strip() == PEOPLEAPP_IMAGE_AD_BROAD_RULE for x in rewrite.splitlines()), 1)
        self.assertEqual(sum(x.strip() == PEOPLEAPP_IMAGE_AD_SHADOW_RULE for x in rewrite.splitlines()), 0)
        self.assertEqual(apply(result), result)

    def test_preserves_peopleapp_shadow_rules_when_legacy_guard_is_missing_or_later(self):
        from apply_local_overrides import PEOPLEAPP_HOME_AD_BROAD_RULE, PEOPLEAPP_HOME_AD_SHADOW_RULE
        without_broad = BASE.replace("[Rewrite]", "[Rewrite]\n" + PEOPLEAPP_HOME_AD_SHADOW_RULE)
        result = apply(without_broad)
        self.assertIn(PEOPLEAPP_HOME_AD_SHADOW_RULE, result)
        reversed_order = BASE.replace("[Rewrite]", "[Rewrite]\n" + PEOPLEAPP_HOME_AD_SHADOW_RULE + "\n" + PEOPLEAPP_HOME_AD_BROAD_RULE)
        result = apply(reversed_order)
        self.assertIn(PEOPLEAPP_HOME_AD_SHADOW_RULE, result)


    def test_removes_only_later_terminal_block_action_variants(self):
        from apply_local_overrides import SHADOWED_TERMINAL_BLOCK_RULE_PAIRS
        expected = (
            (r"^https:\/\/acs\.m\.taobao\.com\/gw\/mtop\.taobao\.idlecommerce\.splash\.ads reject-dict", r"^https:\/\/acs\.m\.taobao\.com\/gw\/mtop\.taobao\.idlecommerce\.splash\.ads reject-200"),
            (r"^https:\/\/guide-acs\.m\.taobao\.com\/gw\/mtop\.taobao\.wireless\.home\.splash\.awesome\.get reject-dict", r"^https:\/\/guide-acs\.m\.taobao\.com\/gw\/mtop\.taobao\.wireless\.home\.splash\.awesome\.get reject-200"),
            (r"^https?:\/\/(bdsp-x|dsp-x)\.jd\.com\/adx\/ reject-200", r"^https?:\/\/(bdsp-x|dsp-x)\.jd\.com\/adx\/ reject"),
            (r"^https?:\/\/axxd\.xmseeyouyima\.com\/.*getad\? reject", r"^https?:\/\/axxd\.xmseeyouyima\.com\/.*getad\? reject-dict"),
            (r"^https?:\/\/axxd\.xmseeyouyima\.com\/ad reject", r"^https?:\/\/axxd\.xmseeyouyima\.com\/ad reject-dict"),
            (r"^https?:\/\/c\.m\.163\.com\/nc\/gl\/ reject", r"^https?:\/\/c\.m\.163\.com\/nc\/gl\/ reject-200"),
            (r"^https?:\/\/cdn1\.mbs\.boc\.cn\/ubas-mgateway-static\/images\/theme\/ reject-200", r"^https?:\/\/cdn1\.mbs\.boc\.cn\/ubas-mgateway-static\/images\/theme\/ reject-dict"),
            (r"^https?:\/\/mbs\.boc\.cn\/ubas-mgateway-static\/images\/theme\/ reject-200", r"^https?:\/\/mbs\.boc\.cn\/ubas-mgateway-static\/images\/theme\/ reject-dict"),
            (r"^https?:\/\/support\.you\.163\.com\/xhr\/boot\/getBootMedia reject", r"^https?:\/\/support\.you\.163\.com\/xhr\/boot\/getBootMedia reject-200"),
            (r"^https?:\/\/us\.l\.qq\.com\/exapp reject-200", r"^https?:\/\/us\.l\.qq\.com\/exapp reject"),
            (r"^https?:\/\/x\.seeyouyima\.com\/adx\/staticstics\? reject", r"^https?:\/\/x\.seeyouyima\.com\/adx\/staticstics\? reject-200"),
            (r"request if ${url} ~= /^https:\/\/acs\.m\.taobao\.com\/gw\/mtop\.taobao\.idle\.home\.welcome/i then reject_dict(200)", r"request if ${url} ~= /^https:\/\/acs\.m\.taobao\.com\/gw\/mtop\.taobao\.idle\.home\.welcome/i then reject(404)"),
            (r"request if ${url} ~= /^https?:\/\/adx-cn\.anythinktech\.com\/bid/ then reject_dict(200)", r"request if ${url} ~= /^https?:\/\/adx-cn\.anythinktech\.com\/bid/ then reject(200)"),
            (r"request if ${url} ~= /^https?:\/\/mime\.baidu\.com\/v5\/start_screen_ads\/list/ then reject(404)", r"request if ${url} ~= /^https?:\/\/mime\.baidu\.com\/v5\/start_screen_ads\/list/ then reject_dict(200)"),
    ("request if ${url} ~= /^https?:\\/\\/182\\.92\\.244\\.70\\/d\\/json/ then reject(404)", "request if ${url} ~= /^https?:\\/\\/182\\.92\\.244\\.70\\/d\\/json/ then reject_dict(200)"),
    ("request if ${url} ~= /^https?:\\/\\/acs\\.m\\.taobao\\.com\\/gw\\/mtop\\.etao\\.noah\\.query\\/.+tao_splash/ then reject(404)", "request if ${url} ~= /^https?:\\/\\/acs\\.m\\.taobao\\.com\\/gw\\/mtop\\.etao\\.noah\\.query\\/.+tao_splash/ then reject_dict(200)"),
    ("request if ${url} ~= /^https?:\\/\\/acs\\.m\\.taobao\\.com\\/gw\\/mtop\\.alimama\\.etao\\.config\\.query\\/.+?etao_advertise/ then reject(404)", "request if ${url} ~= /^https?:\\/\\/acs\\.m\\.taobao\\.com\\/gw\\/mtop\\.alimama\\.etao\\.config\\.query\\/.+?etao_advertise/ then reject_dict(200)"),
    ("request if ${url} ~= /^https?:\\/\\/api\\.douban\\.com\\/v\\d\\/app_ads\\// then reject(404)", "request if ${url} ~= /^https?:\\/\\/api\\.douban\\.com\\/v\\d\\/app_ads\\// then reject_dict(200)"),
    ("request if ${url} ~= /^https?:\\/\\/go\\.babytree\\.com\\/go_tool\\/api\\/feeding_record\\/get_home_banner_info/ then reject(404)", "request if ${url} ~= /^https?:\\/\\/go\\.babytree\\.com\\/go_tool\\/api\\/feeding_record\\/get_home_banner_info/ then reject_dict(200)"),
    ("request if ${url} ~= /^https?:\\/\\/p\\.kuaidi100\\.com\\/advertisement\\// then reject(404)", "request if ${url} ~= /^https?:\\/\\/p\\.kuaidi100\\.com\\/advertisement\\// then reject_dict(200)"),
    ("request if ${url} ~= /^https?:\\/\\/api\\.jr\\.mi\\.com\\/jr\\/api\\/playScreen/ then reject(404)", "request if ${url} ~= /^https?:\\/\\/api\\.jr\\.mi\\.com\\/jr\\/api\\/playScreen/ then reject(200)"),
        )
        self.assertEqual(SHADOWED_TERMINAL_BLOCK_RULE_PAIRS, expected)
        fixture_rules = "\n".join(line for pair in expected for line in pair)
        base = BASE.replace("[Rewrite]", "[Rewrite]\n" + fixture_rules)
        result = apply(base)
        rewrite = result.split("[Rewrite]", 1)[1].split("[Script]", 1)[0]
        for guard, shadow in expected:
            self.assertIn(guard, rewrite)
            self.assertNotIn(shadow, {item.strip() for item in rewrite.splitlines()})
        self.assertEqual(apply(result), result)


    def test_preserves_163_case_insensitive_variant_because_it_expands_match_scope(self):
        broad = r"request if ${url} ~= /^https?:\\/\\/appconf\\.mail\\.163\\.com\\/mailmaster\\/api\\/http\\/urlConfig\\.do$/ then reject(404)"
        case_insensitive = r"request if ${url} ~= /^https?:\\/\\/appconf\\.mail\\.163\\.com\\/mailmaster\\/api\\/http\\/urlConfig\\.do$/i then reject_dict(200)"
        base = BASE.replace("[Rewrite]", "[Rewrite]\n" + broad + "\n" + case_insensitive)
        result = apply(base)
        rewrite = result.split("[Rewrite]", 1)[1].split("[Script]", 1)[0]
        self.assertIn(broad, rewrite)
        self.assertIn(case_insensitive, rewrite)

    def test_preserves_terminal_variant_if_it_precedes_its_guard(self):
        from apply_local_overrides import SHADOWED_TERMINAL_BLOCK_RULE_PAIRS
        guard, shadow = SHADOWED_TERMINAL_BLOCK_RULE_PAIRS[0]
        base = BASE.replace("[Rewrite]", "[Rewrite]\n" + shadow + "\n" + guard)
        result = apply(base)
        rewrite = result.split("[Rewrite]", 1)[1].split("[Script]", 1)[0]
        self.assertIn(guard, rewrite)
        self.assertIn(shadow, rewrite)


    def test_removes_only_the_duplicate_path_in_exact_pdd_homepage_delete_rule(self):
        from apply_local_overrides import (
            PDD_HOMEPAGE_DELETE_DUPLICATE_RULE, PDD_HOMEPAGE_DELETE_DEDUPED_RULE,
            remove_duplicate_pdd_homepage_delete_path,
        )
        result, removed = remove_duplicate_pdd_homepage_delete_path([PDD_HOMEPAGE_DELETE_DUPLICATE_RULE])
        self.assertEqual(removed, 1)
        self.assertEqual(result, [PDD_HOMEPAGE_DELETE_DEDUPED_RULE])
        self.assertEqual(result[0].count("result.dy_module.irregular_banner_dy"), 1)
        self.assertIn("result.icon_set", result[0])
        self.assertIn("result.search_bar_hot_query", result[0])
        self.assertEqual(remove_duplicate_pdd_homepage_delete_path(result)[1], 0)

    def test_preserves_pdd_homepage_rule_when_exact_source_text_changes(self):
        from apply_local_overrides import (
            PDD_HOMEPAGE_DELETE_DUPLICATE_RULE, remove_duplicate_pdd_homepage_delete_path,
        )
        for fixture in (
            [PDD_HOMEPAGE_DELETE_DUPLICATE_RULE.replace("result.icon_set", "result.icon_set_v2")],
            [PDD_HOMEPAGE_DELETE_DUPLICATE_RULE, PDD_HOMEPAGE_DELETE_DUPLICATE_RULE],
        ):
            result, removed = remove_duplicate_pdd_homepage_delete_path(fixture)
            self.assertEqual(removed, 0)
            self.assertEqual(result, list(fixture))

    def test_removes_dache_core_icon_from_later_filter_only_after_explicit_delete(self):
        from apply_local_overrides import (
            DACHE_CORE_ICON_DELETE_GUARD, DACHE_CORE_ICON_FILTER_RULE,
            remove_redundant_dache_core_icon_filter,
        )
        expected_guard = r'response if ${url} ~= /^https:\/\/api\.udache\.com\/gulfstream\/porsche\/v\d\/dache_homepage_layout\?/i then response.json.delete("data.instances.dache_main_core_icon")'
        expected_filter = r'response if ${url} ~= /^https:\/\/api\.udache\.com\/gulfstream\/porsche\/v\d\/dache_homepage_layout\?/i then response.json.jq(".data |= (.instances |= (to_entries | map(select(.key | test(\"feed_back_|dache_main_member|order_container_|dache_main_core_icon|dache_main_card_\"))) | from_entries))")'
        self.assertEqual(DACHE_CORE_ICON_DELETE_GUARD, expected_guard)
        self.assertEqual(DACHE_CORE_ICON_FILTER_RULE, expected_filter)
        result, removed = remove_redundant_dache_core_icon_filter([expected_guard, expected_filter])
        self.assertEqual(removed, 1)
        self.assertIn("order_container_|dache_main_card_", result[1])
        self.assertNotIn("dache_main_core_icon", result[1])
        self.assertEqual(remove_redundant_dache_core_icon_filter(result)[1], 0)

    def test_preserves_dache_filter_when_delete_guard_is_missing_or_later(self):
        from apply_local_overrides import DACHE_CORE_ICON_DELETE_GUARD, DACHE_CORE_ICON_FILTER_RULE, remove_redundant_dache_core_icon_filter
        for fixture in ([DACHE_CORE_ICON_FILTER_RULE], [DACHE_CORE_ICON_FILTER_RULE, DACHE_CORE_ICON_DELETE_GUARD]):
            result, removed = remove_redundant_dache_core_icon_filter(fixture)
            self.assertEqual(removed, 0)
            self.assertEqual(result, list(fixture))

    def test_merges_didi_fast_homepage_json_deletes_without_losing_paths(self):
        from apply_local_overrides import (
            DIDI_FAST_HOME_DELETE_FIRST, DIDI_FAST_HOME_DELETE_SECOND,
            merge_didi_fast_homepage_json_deletes,
        )
        result, count = merge_didi_fast_homepage_json_deletes([
            DIDI_FAST_HOME_DELETE_FIRST,
            'response if ${url} ~= /^https:\\/\\/other\\.example\\/x/i then response.json.delete("data.other")',
            DIDI_FAST_HOME_DELETE_SECOND,
        ])
        self.assertEqual(count, 1)
        self.assertEqual(len(result), 2)
        self.assertIn("data.disorder_cards.communicate_card", result[0])
        self.assertIn("data.disorder_cards.guess_card", result[0])
        self.assertIn("data.disorder_cards.scene_list_card", result[0])
        self.assertEqual(merge_didi_fast_homepage_json_deletes(result)[1], 0)

    def test_preserves_didi_rules_when_order_or_same_matcher_intervening_rule_changes(self):
        from apply_local_overrides import (
            DIDI_FAST_HOME_DELETE_FIRST, DIDI_FAST_HOME_DELETE_SECOND,
            DIDI_FAST_HOME_MATCHER_PREFIX, merge_didi_fast_homepage_json_deletes,
        )
        reversed_rules = [DIDI_FAST_HOME_DELETE_SECOND, DIDI_FAST_HOME_DELETE_FIRST]
        self.assertEqual(merge_didi_fast_homepage_json_deletes(reversed_rules), (reversed_rules, 0))
        intervening = [DIDI_FAST_HOME_DELETE_FIRST, DIDI_FAST_HOME_MATCHER_PREFIX + 'response.json.delete("data.extra")', DIDI_FAST_HOME_DELETE_SECOND]
        self.assertEqual(merge_didi_fast_homepage_json_deletes(intervening), (intervening, 0))
        missing_guard = [DIDI_FAST_HOME_DELETE_SECOND]
        self.assertEqual(merge_didi_fast_homepage_json_deletes(missing_guard), (missing_guard, 0))

    def test_requires_bankcomm_mitm_hosts(self):
        with self.assertRaises(ValueError):
            apply(BASE.replace("creditcard.bankcomm.com, ", ""))

if __name__ == "__main__":
    unittest.main()
