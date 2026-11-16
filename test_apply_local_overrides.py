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

    def test_preserves_mitm_for_non_hellobike_script_reference(self):
        trigger = r"http-response ^https?:\\/\\/mi\\.gdt\\.qq\\.com\\/gdt_mview script-path=https://example.invalid/ad.js, tag=base-ad"
        base = BASE.replace("[Script]", "[Script]\n" + trigger)
        result = apply(base)
        mitm = result.split("[MITM]", 1)[1]
        self.assertIn("mi.gdt.qq.com", mitm)
        self.assertIn(trigger, result)
        self.assertNotIn("adservice.sigmob.cn", mitm)

    def test_scopes_yyting_request_rule_to_known_hosts(self):
        # Exercise the exact single-backslash URL escaping found in allAdRewrite.plugin.
        broad = r"request if ${url} ~= /^https?:\/\/.*\/yyting\/advertclient\/ClientAdvertList.action/ then reject(404)"
        base = BASE.replace("[Rewrite]", "[Rewrite]\n" + broad)
        result = apply(base)
        rewrite = result.split("[Rewrite]", 1)[1].split("[Script]", 1)[0]
        self.assertNotIn(broad, rewrite)
        self.assertIn(r"^https?:\/\/118\.178\.214\.118\/yyting\/advertclient\/ClientAdvertList\.action", rewrite)
        self.assertIn(r"^https?:\/\/dapis\.mting\.info\/yyting\/advertclient\/ClientAdvertList\.action", rewrite)
        self.assertEqual(apply(result), result)

    def test_scopes_yyting_when_upstream_uses_repeated_slash_escapes(self):
        broad = r"request if ${url} ~= /^https?:\\\\/\\\\/.*\\\\/yyting\\\\/advertclient\\\\/ClientAdvertList.action/ then reject(404)"
        base = BASE.replace("[Rewrite]", "[Rewrite]\n" + broad)
        result = apply(base)
        rewrite = result.split("[Rewrite]", 1)[1].split("[Script]", 1)[0]
        self.assertNotIn(broad, rewrite)
        self.assertIn(r"^https?:\/\/118\.178\.214\.118\/yyting\/advertclient\/ClientAdvertList\.action", rewrite)
        self.assertIn(r"^https?:\/\/dapis\.mting\.info\/yyting\/advertclient\/ClientAdvertList\.action", rewrite)
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

    def test_merges_jq_actions_without_splitting_internal_pipe_operators(self):
        from apply_local_overrides import merge_adjacent_response_json_rewrites
        prefix = "response if ${url} ~= /api/ then "
        first = prefix + 'response.json.delete("data.header")'
        jq = prefix + "response.json.jq('.data.rows |= map(select(.type == \"card\")) | .data.banner')"
        third = prefix + 'response.json.delete("data.footer")'
        result, count = merge_adjacent_response_json_rewrites([first, jq, third])
        self.assertEqual(count, 1)
        self.assertEqual(len(result), 1)
        self.assertIn("response.json.delete", result[0])
        self.assertIn(".data.rows |= map(select(.type == \"card\")) | .data.banner", result[0])
        self.assertEqual(merge_adjacent_response_json_rewrites(result)[1], 0)

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

    def test_removes_only_lkcoffee_member_exchange_forced_success_rewrites(self):
        legacy = r'^https?:\\/\\/m\\.lkcoffee\\.com\\/ecapi\\/resource\\/m\\/member\\/exchange\\/page response-body-replace-regex \\{.+\\} {"status":"SUCCESS"}'
        modern = r'response if ${url} ~= /^https?:\\/\\/m\\.lkcoffee\\.com\\/ecapi\\/resource\\/m\\/member\\/exchange\\/page/ then response.body.replace(/\\{.+\\}/, \'{"status":"SUCCESS"}\')'
        keep = r'^https?:\\/\\/capi\\.lkcoffee\\.com\\/resource\\/m\\/sys\\/app\\/adposNew reject-dict'
        base = BASE.replace("[Rewrite]", "[Rewrite]\n" + legacy + "\n" + modern + "\n" + keep)
        result = apply(base)
        rewrite = result.split("[Rewrite]", 1)[1].split("[Script]", 1)[0]
        self.assertNotIn(legacy, rewrite)
        self.assertNotIn(modern, rewrite)
        self.assertIn(keep, rewrite)
        self.assertEqual(apply(result), result)

    def test_fails_closed_when_lkcoffee_member_exchange_rule_changes(self):
        changed = r'response if ${url} ~= /^https?:\\/\\/m\\.lkcoffee\\.com\\/ecapi\\/resource\\/m\\/member\\/exchange\\/page/ then response.body.replace(/message/, "hidden")'
        base = BASE.replace("[Rewrite]", "[Rewrite]\n" + changed)
        with self.assertRaisesRegex(ValueError, "member-exchange response rule changed"):
            apply(base)

    def test_converts_only_guiderank_special_sale_random_body_to_json_delete(self):
        target = r'^https?:\\/\\/zone\\.guiderank-app\\.com\\/guiderank-web\\/app\\/common\\/getInitData response-body-replace-regex SpecialSalePageMidTabConfig random_body'
        keep = r'^https?:\\/\\/zone\\.guiderank-app\\.com\\/guiderank-web\\/app\\/specialSale\\/pageRecommendedItems reject-dict'
        result = apply(BASE.replace("[Rewrite]", "[Rewrite]\n" + target + "\n" + keep))
        rewrite = result.split("[Rewrite]", 1)[1].split("[Script]", 1)[0]
        expected = target.replace("response-body-replace-regex SpecialSalePageMidTabConfig random_body", "response-body-json-del data.SpecialSalePageMidTabConfig")
        self.assertIn(expected, rewrite)
        self.assertIn(keep, rewrite)
        self.assertNotIn("random_body", rewrite)
        self.assertEqual(apply(result), result)

    def test_fails_closed_when_guiderank_special_sale_rule_changes(self):
        changed = r'^https?:\\/\\/zone\\.guiderank-app\\.com\\/guiderank-web\\/app\\/common\\/getInitData response-body-replace-regex data random_body'
        with self.assertRaisesRegex(ValueError, "Guiderank SpecialSalePageMidTabConfig rule changed"):
            apply(BASE.replace("[Rewrite]", "[Rewrite]\n" + changed))

    def test_converts_duoduo_grocery_newdetails_suspension_to_native_json_delete(self):
        from apply_local_overrides import DDQX_NEWDETAILS_NATIVE_RULE
        legacy = r'^https?:\/\/maicai\.api\.ddxq\.mobi\/homeApi\/newDetails response-body-replace-regex suspension random_body'
        modern = r'response if ${url} ~= /^https?:\/\/maicai\.api\.ddxq\.mobi\/homeApi\/newDetails/ then response.body.replace(/suspension/, "fmz200")'
        keep = r'^https?:\/\/maicai\.api\.ddxq\.mobi\/homeApi\/getHomeAdPop reject-dict'
        fixture = BASE.replace("[Rewrite]", "[Rewrite]\n" + legacy + "\n" + modern + "\n" + keep)
        result = apply(fixture)
        rewrite = result.split("[Rewrite]", 1)[1].split("[Script]", 1)[0]
        self.assertNotIn(legacy, rewrite)
        self.assertNotIn(modern, rewrite)
        self.assertIn(DDQX_NEWDETAILS_NATIVE_RULE, rewrite)
        self.assertEqual(rewrite.count("response.json.delete(\"data.suspension\")"), 1)
        self.assertIn(keep, rewrite)
        self.assertEqual(apply(result), result)

    def test_fails_closed_when_duoduo_grocery_newdetails_rule_changes(self):
        changed = r'response if ${url} ~= /^https?:\/\/maicai\.api\.ddxq\.mobi\/homeApi\/newDetails/ then response.body.replace(/data/, "hidden")'
        fixture = BASE.replace("[Rewrite]", "[Rewrite]\n" + changed)
        with self.assertRaisesRegex(ValueError, "Duoduo Grocery newDetails suspension rule changed"):
            apply(fixture)

    def test_replaces_guiderank_homepage_script_with_native_batch_json_delete(self):
        from apply_local_overrides import GUIDERANK_HOMEPAGE_SCRIPT_TRIGGER, GUIDERANK_HOMEPAGE_NATIVE_RULE
        fixture = BASE.replace("[Script]", "[Script]\n" + GUIDERANK_HOMEPAGE_SCRIPT_TRIGGER)
        result = apply(fixture)
        rewrite = result.split("[Rewrite]", 1)[1].split("[Script]", 1)[0]
        script = result.split("[Script]", 1)[1].split("[MITM]", 1)[0]
        self.assertIn(GUIDERANK_HOMEPAGE_NATIVE_RULE, rewrite)
        self.assertNotIn("guiderank.js", script)
        self.assertNotIn("getHomePageV", script)
        for path in ("data.countdownBanner", "data.newEvaluations", "data.freeToPayBannerPhotoUrl", "data.groupBuyingList", "data.multiCountdownBanner", "data.banners", "data.multiPlatformBanner", "data.specialSaleBannerPhotoUrl", "data.guide90Evaluation", "data.insurancePromotions"):
            self.assertIn(path, GUIDERANK_HOMEPAGE_NATIVE_RULE)
        self.assertEqual(apply(result), result)

    def test_fails_closed_when_guiderank_homepage_script_trigger_changes(self):
        from apply_local_overrides import GUIDERANK_HOMEPAGE_SCRIPT_TRIGGER
        changed = GUIDERANK_HOMEPAGE_SCRIPT_TRIGGER.replace("requires-body=true", "requires-body=false")
        fixture = BASE.replace("[Script]", "[Script]\n" + changed)
        with self.assertRaisesRegex(ValueError, "Guiderank homepage script trigger changed"):
            apply(fixture)

    def test_preserves_other_guiderank_script_triggers(self):
        from apply_local_overrides import GUIDERANK_HOMEPAGE_SCRIPT_TRIGGER
        other = r"http-response ^https?:\/\/zone\.guiderank-app\.com\/guiderank-web\/app\/home\/other script-path=https://example.invalid/other.js,tag=OTHER,requires-body=true"
        fixture = BASE.replace("[Script]", "[Script]\n" + GUIDERANK_HOMEPAGE_SCRIPT_TRIGGER + "\n" + other)
        result = apply(fixture)
        self.assertIn(other, result)
        self.assertNotIn("guiderank.js", result)

    def test_requires_bankcomm_mitm_hosts(self):
        with self.assertRaises(ValueError):
            apply(BASE.replace("creditcard.bankcomm.com, ", ""))


    def test_replaces_gaoding_resource_scripts_with_exact_native_json_deletes(self):
        from apply_local_overrides import (
            GAODING_TEMPLATE_SCRIPT_TRIGGER, GAODING_MINE_SCRIPT_TRIGGER,
            GAODING_NATIVE_RULES,
        )
        unrelated = r"http-response ^https?:\\/\\/www\\.gaoding\\.com\\/api\\/v1\\/account script-path=https://example.invalid/account.js,tag=ACCOUNT"
        fixture = BASE.replace(
            "[Script]",
            "[Script]\n" + GAODING_TEMPLATE_SCRIPT_TRIGGER + "\n"
            + GAODING_MINE_SCRIPT_TRIGGER + "\n" + unrelated,
        )
        result = apply(fixture)
        rewrite = result.split("[Rewrite]", 1)[1].split("[Script]", 1)[0]
        script = result.split("[Script]", 1)[1].split("[MITM]", 1)[0]
        for rule in GAODING_NATIVE_RULES:
            self.assertIn(rule, rewrite)
        self.assertNotIn("gaoding.js", script)
        self.assertIn(unrelated, script)
        self.assertIn("pits[0].delivery_materials", GAODING_NATIVE_RULES[0])
        self.assertIn("pits[2].delivery_materials", GAODING_NATIVE_RULES[1])
        self.assertEqual(apply(result), result)

    def test_fails_closed_when_gaoding_resource_script_trigger_changes(self):
        from apply_local_overrides import GAODING_TEMPLATE_SCRIPT_TRIGGER
        changed = GAODING_TEMPLATE_SCRIPT_TRIGGER.replace("requires-body=true", "requires-body=false")
        fixture = BASE.replace("[Script]", "[Script]\n" + changed)
        with self.assertRaisesRegex(ValueError, "Gaoding resource script trigger changed"):
            apply(fixture)

    def test_fails_closed_on_duplicate_gaoding_resource_script_trigger(self):
        from apply_local_overrides import GAODING_TEMPLATE_SCRIPT_TRIGGER
        fixture = BASE.replace("[Script]", "[Script]\n" + GAODING_TEMPLATE_SCRIPT_TRIGGER
                               + "\n" + GAODING_TEMPLATE_SCRIPT_TRIGGER)
        with self.assertRaisesRegex(ValueError, "duplicate Gaoding resource script triggers"):
            apply(fixture)


    def test_consolidates_pdd_homepage_scripts_and_preserves_unrelated_scripts(self):
        from apply_local_overrides import (
            PDD_RSTORE_HOMEPAGE_TRIGGER, PDD_LOCAL_HOMEPAGE_TRIGGER,
            PDD_ISHOWSHU_HOMEPAGE_TRIGGER,
        )
        unrelated = 'response if \${url} ~= /api.example.com/ then script("https://example.invalid/keep.js")'
        fixture = BASE.replace(
            "[Script]",
            "[Script]\n" + PDD_RSTORE_HOMEPAGE_TRIGGER + "\n"
            + PDD_ISHOWSHU_HOMEPAGE_TRIGGER + "\n" + unrelated,
        )
        result = apply(fixture)
        script = result.split("[Script]", 1)[1].split("[MITM]", 1)[0]
        self.assertEqual(script.count(PDD_LOCAL_HOMEPAGE_TRIGGER), 1)
        self.assertNotIn(PDD_RSTORE_HOMEPAGE_TRIGGER, script)
        self.assertNotIn(PDD_ISHOWSHU_HOMEPAGE_TRIGGER, script)
        self.assertIn(unrelated, script)
        self.assertEqual(apply(result), result)

    def test_pdd_homepage_consolidation_fails_closed_on_trigger_drift(self):
        from apply_local_overrides import PDD_ISHOWSHU_HOMEPAGE_TRIGGER
        changed = PDD_ISHOWSHU_HOMEPAGE_TRIGGER.replace("requires-body = true", "requires-body = false")
        fixture = BASE.replace("[Script]", "[Script]\n" + changed)
        with self.assertRaisesRegex(ValueError, "Pinduoduo homepage script trigger changed"):
            apply(fixture)

    def test_pdd_homepage_consolidation_requires_canonical_trigger(self):
        from apply_local_overrides import PDD_ISHOWSHU_HOMEPAGE_TRIGGER
        fixture = BASE.replace("[Script]", "[Script]\n" + PDD_ISHOWSHU_HOMEPAGE_TRIGGER)
        with self.assertRaisesRegex(ValueError, "Pinduoduo canonical homepage script inventory changed"):
            apply(fixture)

    def test_pdd_homepage_consolidation_rejects_duplicate_triggers(self):
        from apply_local_overrides import PDD_RSTORE_HOMEPAGE_TRIGGER, PDD_ISHOWSHU_HOMEPAGE_TRIGGER
        fixture = BASE.replace(
            "[Script]",
            "[Script]\n" + PDD_RSTORE_HOMEPAGE_TRIGGER + "\n"
            + PDD_RSTORE_HOMEPAGE_TRIGGER + "\n" + PDD_ISHOWSHU_HOMEPAGE_TRIGGER,
        )
        with self.assertRaisesRegex(ValueError, "duplicate Pinduoduo homepage script trigger"):
            apply(fixture)

    def test_consolidates_pdd_splash_variants_to_one_case_insensitive_rule(self):
        from apply_local_overrides import (
            PDD_SPLASH_OLD_CANONICAL_RULE, PDD_SPLASH_CANONICAL_RULE,
            PDD_SPLASH_REDUNDANT_RULES, consolidate_pdd_splash_rules,
        )
        fixture = [
            PDD_SPLASH_OLD_CANONICAL_RULE, *PDD_SPLASH_REDUNDANT_RULES,
            "request if ${url} ~= /^https?:\/\/api\.pinduoduo\.com\/api\/other/ then reject(404)",
        ]
        result, removed = consolidate_pdd_splash_rules(fixture)
        self.assertEqual(removed, 3)
        self.assertEqual(result.count(PDD_SPLASH_CANONICAL_RULE), 1)
        self.assertEqual(result[-1], fixture[-1])
        self.assertEqual(consolidate_pdd_splash_rules(result)[1], 0)

    def test_pdd_splash_consolidation_fails_closed_on_unknown_or_duplicate_matchers(self):
        from apply_local_overrides import (
            PDD_SPLASH_OLD_CANONICAL_RULE, PDD_SPLASH_REDUNDANT_RULES,
            consolidate_pdd_splash_rules,
        )
        with self.assertRaisesRegex(ValueError, "unknown Pinduoduo splash matcher"):
            consolidate_pdd_splash_rules([PDD_SPLASH_OLD_CANONICAL_RULE, "request /cappuccino/splash-new reject"])
        with self.assertRaisesRegex(ValueError, "inventory changed or duplicated"):
            consolidate_pdd_splash_rules([PDD_SPLASH_OLD_CANONICAL_RULE, PDD_SPLASH_OLD_CANONICAL_RULE])
        with self.assertRaisesRegex(ValueError, "inventory changed or duplicated"):
            consolidate_pdd_splash_rules([PDD_SPLASH_OLD_CANONICAL_RULE, PDD_SPLASH_REDUNDANT_RULES[0], PDD_SPLASH_REDUNDANT_RULES[0]])

    def test_removes_only_pdd_feed_asset_rules_shadowed_by_same_action(self):
        from apply_local_overrides import (
            PDD_FEED_ASSET_CANONICAL_RULES, PDD_FEED_ASSET_REDUNDANT_RULES,
            remove_redundant_pdd_feed_asset_rules,
        )
        unrelated = "request if ${url} ~= /^https?:\/\/images\.pinduoduo\.com\/product/ then reject(404)"
        fixture = [*PDD_FEED_ASSET_CANONICAL_RULES, *PDD_FEED_ASSET_REDUNDANT_RULES, unrelated]
        result, removed = remove_redundant_pdd_feed_asset_rules(fixture)
        self.assertEqual(removed, 4)
        for rule in PDD_FEED_ASSET_CANONICAL_RULES:
            self.assertIn(rule, result)
        self.assertIn(unrelated, result)
        self.assertEqual(remove_redundant_pdd_feed_asset_rules(result)[1], 0)

    def test_pdd_feed_cleanup_requires_covering_rules_and_rejects_duplicate_rows(self):
        from apply_local_overrides import (
            PDD_FEED_ASSET_REDUNDANT_RULES, remove_redundant_pdd_feed_asset_rules,
        )
        with self.assertRaisesRegex(ValueError, "covering rule missing"):
            remove_redundant_pdd_feed_asset_rules([PDD_FEED_ASSET_REDUNDANT_RULES[0]])
        with self.assertRaisesRegex(ValueError, "duplicate Pinduoduo feed asset rule"):
            remove_redundant_pdd_feed_asset_rules([PDD_FEED_ASSET_REDUNDANT_RULES[0]] * 2)

    def test_removes_pdd_oak_script_only_when_native_cleaner_exists(self):
        from apply_local_overrides import (
            PDD_OAK_REDUNDANT_SCRIPT_TRIGGER, PDD_OAK_NATIVE_RESPONSE_RULE,
            remove_redundant_pdd_oak_script_trigger,
        )
        fixture = ["[Rewrite]", PDD_OAK_NATIVE_RESPONSE_RULE, "[Script]",
                   PDD_OAK_REDUNDANT_SCRIPT_TRIGGER, "[MITM]"]
        result, removed = remove_redundant_pdd_oak_script_trigger(fixture)
        self.assertEqual(removed, 1)
        self.assertNotIn(PDD_OAK_REDUNDANT_SCRIPT_TRIGGER, result)
        self.assertIn(PDD_OAK_NATIVE_RESPONSE_RULE, result)
        self.assertEqual(remove_redundant_pdd_oak_script_trigger(result)[1], 0)

    def test_pdd_oak_script_is_preserved_if_native_cleaner_is_missing(self):
        from apply_local_overrides import (
            PDD_OAK_REDUNDANT_SCRIPT_TRIGGER, remove_redundant_pdd_oak_script_trigger,
        )
        with self.assertRaisesRegex(ValueError, "native response cleaner missing"):
            remove_redundant_pdd_oak_script_trigger(["[Script]", PDD_OAK_REDUNDANT_SCRIPT_TRIGGER])

    def test_removes_duplicate_taobao_splash_scripts_and_keeps_canonical_rstore_triggers(self):
        from apply_local_overrides import (
            TAOBAO_CANONICAL_SCRIPT_TRIGGERS, TAOBAO_REDUNDANT_SCRIPT_TRIGGERS,
        )
        fixture = BASE.replace(
            "[Script]",
            "[Script]\n" + "\n".join(TAOBAO_CANONICAL_SCRIPT_TRIGGERS)
            + "\n" + "\n".join(TAOBAO_REDUNDANT_SCRIPT_TRIGGERS)
            + '\nresponse if ${url} ~= /api.example.com/ then script("https://example.invalid/keep.js")',
        )
        result = apply(fixture)
        script = result.split("[Script]", 1)[1].split("[MITM]", 1)[0]
        for trigger in TAOBAO_CANONICAL_SCRIPT_TRIGGERS:
            self.assertEqual(script.count(trigger), 1)
        for trigger in TAOBAO_REDUNDANT_SCRIPT_TRIGGERS:
            self.assertNotIn(trigger, script)
        self.assertIn("https://example.invalid/keep.js", script)
        self.assertEqual(apply(result), result)

    def test_fails_closed_when_a_taobao_duplicate_trigger_drifts(self):
        from apply_local_overrides import TAOBAO_REDUNDANT_SCRIPT_TRIGGERS
        changed = TAOBAO_REDUNDANT_SCRIPT_TRIGGERS[0].replace("requires_body=true", "requires_body=false")
        fixture = BASE.replace("[Script]", "[Script]\n" + changed)
        with self.assertRaisesRegex(ValueError, "Taobao splash script trigger changed"):
            apply(fixture)

    def test_fails_closed_when_taobao_trigger_inventory_is_incomplete(self):
        from apply_local_overrides import TAOBAO_CANONICAL_SCRIPT_TRIGGERS, TAOBAO_REDUNDANT_SCRIPT_TRIGGERS
        fixture = BASE.replace("[Script]", "[Script]\n" + "\n".join(TAOBAO_CANONICAL_SCRIPT_TRIGGERS) + "\n" + TAOBAO_REDUNDANT_SCRIPT_TRIGGERS[0])
        with self.assertRaisesRegex(ValueError, "Taobao splash script trigger inventory changed"):
            apply(fixture)

    def test_fails_closed_on_duplicate_taobao_script_trigger(self):
        from apply_local_overrides import TAOBAO_REDUNDANT_SCRIPT_TRIGGERS
        duplicate = TAOBAO_REDUNDANT_SCRIPT_TRIGGERS[0]
        fixture = BASE.replace("[Script]", "[Script]\n" + duplicate + "\n" + duplicate)
        with self.assertRaisesRegex(ValueError, "duplicate redundant Taobao script trigger"):
            apply(fixture)



    def test_removes_only_duplicate_didi_usercenter_fmz_script(self):
        from apply_local_overrides import (
            DIDI_USERCENTER_CANONICAL_TRIGGER, DIDI_USERCENTER_REDUNDANT_TRIGGER,
        )
        unrelated = 'response if ${url} ~= /common.diditaxi.com.cn/common/v5/ then script("https://example.invalid/miniapp.js")'
        fixture = BASE.replace(
            "[Script]",
            "[Script]\n" + DIDI_USERCENTER_CANONICAL_TRIGGER
            + "\n" + DIDI_USERCENTER_REDUNDANT_TRIGGER
            + "\n" + unrelated,
        )
        result = apply(fixture)
        script = result.split("[Script]", 1)[1].split("[MITM]", 1)[0]
        self.assertEqual(script.count(DIDI_USERCENTER_CANONICAL_TRIGGER), 1)
        self.assertNotIn(DIDI_USERCENTER_REDUNDANT_TRIGGER, script)
        self.assertIn(unrelated, script)
        self.assertEqual(apply(result), result)

    def test_fails_closed_when_didi_usercenter_trigger_drifts(self):
        from apply_local_overrides import DIDI_USERCENTER_REDUNDANT_TRIGGER
        changed = DIDI_USERCENTER_REDUNDANT_TRIGGER.replace("requires_body=true", "requires_body=false")
        fixture = BASE.replace("[Script]", "[Script]\n" + changed)
        with self.assertRaisesRegex(ValueError, "Didi user-center script trigger changed"):
            apply(fixture)

    def test_fails_closed_when_didi_usercenter_canonical_trigger_is_missing(self):
        from apply_local_overrides import DIDI_USERCENTER_REDUNDANT_TRIGGER
        fixture = BASE.replace("[Script]", "[Script]\n" + DIDI_USERCENTER_REDUNDANT_TRIGGER)
        with self.assertRaisesRegex(ValueError, "Didi user-center canonical trigger inventory changed"):
            apply(fixture)

    def test_fails_closed_on_duplicate_didi_usercenter_fmz_trigger(self):
        from apply_local_overrides import (
            DIDI_USERCENTER_CANONICAL_TRIGGER, DIDI_USERCENTER_REDUNDANT_TRIGGER,
        )
        fixture = BASE.replace(
            "[Script]",
            "[Script]\n" + DIDI_USERCENTER_CANONICAL_TRIGGER
            + "\n" + DIDI_USERCENTER_REDUNDANT_TRIGGER
            + "\n" + DIDI_USERCENTER_REDUNDANT_TRIGGER,
        )
        with self.assertRaisesRegex(ValueError, "duplicate Didi user-center FMZ trigger"):
            apply(fixture)



    def test_taobao_deduplication_accepts_single_backslash_generated_plugin_escapes(self):
        from apply_local_overrides import (
            TAOBAO_CANONICAL_SCRIPT_TRIGGERS, TAOBAO_REDUNDANT_SCRIPT_TRIGGERS,
        )
        single_escape = lambda trigger: trigger.replace("\\\\\\\\", "\\\\")
        triggers = tuple(single_escape(item) for item in (
            *TAOBAO_CANONICAL_SCRIPT_TRIGGERS, *TAOBAO_REDUNDANT_SCRIPT_TRIGGERS,
        ))
        fixture = BASE.replace("[Script]", "[Script]\n" + "\n".join(triggers))
        result = apply(fixture)
        script = result.split("[Script]", 1)[1].split("[MITM]", 1)[0]
        for trigger in triggers[:len(TAOBAO_CANONICAL_SCRIPT_TRIGGERS)]:
            self.assertIn(trigger, script)
        for trigger in triggers[len(TAOBAO_CANONICAL_SCRIPT_TRIGGERS):]:
            self.assertNotIn(trigger, script)
        self.assertEqual(apply(result), result)





    def test_removes_legacy_amap_scripts_only_when_modern_handlers_exist(self):
        from apply_local_overrides import remove_redundant_amap_legacy_scripts
        legacy = "http-response ^https://m5.amap.com/ws/aos/perception/publicTravel/beforeNavi? script-path=https://github.com/ishowshu/qx/raw/main/script/amap.js"
        canonical = 'response if ${url} ~= /^https:\\/\\/m5\\.amap\\.com\\/ws\\/aos\\/perception\\/publicTravel\\/beforeNavi\\?/i then script("https://example.invalid/rucu6_amap.js")'
        unrelated = "http-response ^https://example.invalid/ad script-path=https://example.invalid/ad.js"
        result, removed = remove_redundant_amap_legacy_scripts(
            ["[Script]", legacy, "[Rewrite]", canonical, "[Script]", unrelated],
            expected_count=1,
        )
        self.assertEqual(removed, 1)
        self.assertNotIn(legacy, result)
        self.assertIn(canonical, result)
        self.assertIn(unrelated, result)

    def test_fails_closed_on_unknown_amap_legacy_script_endpoint(self):
        from apply_local_overrides import remove_redundant_amap_legacy_scripts
        unknown = "http-response ^https://m5.amap.com/ws/unknown/ad script-path=https://example.invalid/amap.js"
        with self.assertRaisesRegex(ValueError, "unknown Amap legacy response script endpoint"):
            remove_redundant_amap_legacy_scripts(["[Script]", unknown], expected_count=1)

    def test_fails_closed_when_amap_canonical_handler_is_missing(self):
        from apply_local_overrides import remove_redundant_amap_legacy_scripts
        legacy = "http-response ^https://m5.amap.com/ws/aos/perception/publicTravel/beforeNavi? script-path=https://example.invalid/amap.js"
        with self.assertRaisesRegex(ValueError, "canonical response handler missing or duplicated"):
            remove_redundant_amap_legacy_scripts(["[Script]", legacy], expected_count=1)

    def test_generated_plugin_has_no_legacy_amap_scripts_and_keeps_native_handlers(self):
        from pathlib import Path
        from apply_local_overrides import remove_redundant_amap_legacy_scripts
        plugin = Path(__file__).parent / "allAdRewrite.plugin"
        original = plugin.read_text(encoding="utf-8")
        result, removed = remove_redundant_amap_legacy_scripts(original.splitlines(), expected_count=0)
        self.assertEqual(removed, 0)
        self.assertNotIn("Res/Scripts/AntiAd/amap.js", result)
        self.assertNotIn("ishowshu/qx/raw/refs/heads/main/script/amap.js", result)
        self.assertIn("sources/amap/rucu6_amap.js", "\n".join(result))
        self.assertIn("marketingOperationStructured", "\n".join(result))

    def test_removes_unconditional_baidumap_ad_trigger_when_gated_equivalent_exists(self):
        from apply_local_overrides import BAIDUMAP_LEGACY_SCRIPT_RULE, remove_redundant_baidumap_script
        legacy, gated, _ = BAIDUMAP_LEGACY_SCRIPT_RULE
        unrelated = "http-response https://example.invalid/ script-path=other.js"
        result, removed = remove_redundant_baidumap_script([legacy, gated, unrelated])
        self.assertEqual(removed, 1)
        self.assertNotIn(legacy, result)
        self.assertIn(gated, result)
        self.assertIn(unrelated, result)
        self.assertEqual(remove_redundant_baidumap_script(result)[1], 0)

    def test_fails_closed_when_baidumap_gated_ad_trigger_is_missing(self):
        from apply_local_overrides import BAIDUMAP_LEGACY_SCRIPT_RULE, remove_redundant_baidumap_script
        legacy, _, _ = BAIDUMAP_LEGACY_SCRIPT_RULE
        with self.assertRaisesRegex(ValueError, "gated script trigger missing or changed"):
            remove_redundant_baidumap_script([legacy])

    def test_fails_closed_on_duplicate_baidumap_ad_triggers(self):
        from apply_local_overrides import BAIDUMAP_LEGACY_SCRIPT_RULE, remove_redundant_baidumap_script
        legacy, gated, _ = BAIDUMAP_LEGACY_SCRIPT_RULE
        with self.assertRaisesRegex(ValueError, "duplicate legacy"):
            remove_redundant_baidumap_script([legacy, legacy, gated])
        with self.assertRaisesRegex(ValueError, "duplicate gated"):
            remove_redundant_baidumap_script([legacy, gated, gated])

    def test_generated_plugin_keeps_only_gated_baidumap_ad_trigger(self):
        from pathlib import Path
        from apply_local_overrides import BAIDUMAP_LEGACY_SCRIPT_RULE
        plugin = Path(__file__).parent / "allAdRewrite.plugin"
        result = apply(plugin.read_text(encoding="utf-8"))
        legacy, gated, _ = BAIDUMAP_LEGACY_SCRIPT_RULE
        self.assertNotIn(legacy, result)
        self.assertIn(gated, result)

    def test_removes_unconditional_dianping_triggers_when_gated_equivalents_exist(self):
        from apply_local_overrides import DIANPING_LEGACY_SCRIPT_RULES, remove_redundant_dianping_scripts
        legacy1, gated1, _ = DIANPING_LEGACY_SCRIPT_RULES[0]
        legacy2, gated2, _ = DIANPING_LEGACY_SCRIPT_RULES[1]
        unrelated = "http-response https://example.invalid/ script-path=other.js"
        result, removed = remove_redundant_dianping_scripts([legacy1, legacy2, gated1, gated2, unrelated])
        self.assertEqual(removed, 2)
        self.assertNotIn(legacy1, result)
        self.assertNotIn(legacy2, result)
        self.assertIn(gated1, result)
        self.assertIn(gated2, result)
        self.assertIn(unrelated, result)
        self.assertEqual(remove_redundant_dianping_scripts(result)[1], 0)

    def test_fails_closed_when_dianping_gated_trigger_is_missing(self):
        from apply_local_overrides import DIANPING_LEGACY_SCRIPT_RULES, remove_redundant_dianping_scripts
        legacy, _, _ = DIANPING_LEGACY_SCRIPT_RULES[0]
        with self.assertRaisesRegex(ValueError, "gated script trigger missing or changed"):
            remove_redundant_dianping_scripts([legacy])

    def test_fails_closed_on_duplicate_dianping_triggers(self):
        from apply_local_overrides import DIANPING_LEGACY_SCRIPT_RULES, remove_redundant_dianping_scripts
        legacy, gated, _ = DIANPING_LEGACY_SCRIPT_RULES[0]
        with self.assertRaisesRegex(ValueError, "duplicate legacy"):
            remove_redundant_dianping_scripts([legacy, legacy, gated])
        with self.assertRaisesRegex(ValueError, "duplicate gated"):
            remove_redundant_dianping_scripts([legacy, gated, gated])

    def test_generated_plugin_uses_only_switch_gated_dianping_triggers(self):
        from pathlib import Path
        from apply_local_overrides import DIANPING_LEGACY_SCRIPT_RULES
        plugin = Path(__file__).parent / "allAdRewrite.plugin"
        result = apply(plugin.read_text(encoding="utf-8"))
        for legacy, gated, _ in DIANPING_LEGACY_SCRIPT_RULES:
            self.assertNotIn(legacy, result)
            self.assertIn(gated, result)


    def test_consolidates_didi_core_and_usercenter_rules_and_removes_noop_scripts(self):
        from apply_local_overrides import (
            DIDI_CORE_LEGACY_SCRIPT, DIDI_USERCENTER_LEGACY_SCRIPT,
            DIDI_OTA_KEEP_SCRIPT, DIDI_PRESALE_KEEP_SCRIPT,
            DIDI_CORE_LEGACY_JSON_RULE, DIDI_CORE_NATIVE_RULE_CURRENT, DIDI_CORE_NATIVE_RULE,
            DIDI_USERCENTER_LAYOUT_LEGACY_JSON_RULE, DIDI_USERCENTER_LAYOUT_NATIVE_PREFIX,
            DIDIADS_COMMON_V5_SCRIPT, DIDIADS_NOOP_SCRIPT_RULES,
            apply_didi_script_and_homepage_cleanup,
        )
        fixture = [
            "[Argument]", "[Rule]", "[Rewrite]",
            DIDI_CORE_LEGACY_JSON_RULE, DIDI_CORE_NATIVE_RULE_CURRENT,
            DIDI_USERCENTER_LAYOUT_LEGACY_JSON_RULE, DIDI_USERCENTER_LAYOUT_NATIVE_PREFIX + "[]",
            "[Script]", DIDI_CORE_LEGACY_SCRIPT, DIDI_USERCENTER_LEGACY_SCRIPT,
            *DIDIADS_NOOP_SCRIPT_RULES, DIDIADS_COMMON_V5_SCRIPT,
            DIDI_OTA_KEEP_SCRIPT, DIDI_PRESALE_KEEP_SCRIPT, "[MITM]",
        ]
        result, removed = apply_didi_script_and_homepage_cleanup(fixture)
        self.assertEqual(removed, len(DIDIADS_NOOP_SCRIPT_RULES))
        self.assertIn(DIDI_CORE_NATIVE_RULE, result)
        self.assertNotIn(DIDI_CORE_NATIVE_RULE_CURRENT, result)
        self.assertNotIn(DIDI_CORE_LEGACY_JSON_RULE, result)
        self.assertNotIn(DIDI_USERCENTER_LAYOUT_LEGACY_JSON_RULE, result)
        self.assertNotIn(DIDI_CORE_LEGACY_SCRIPT, result)
        self.assertNotIn(DIDI_USERCENTER_LEGACY_SCRIPT, result)
        self.assertIn(DIDIADS_COMMON_V5_SCRIPT, result)
        self.assertIn(DIDI_OTA_KEEP_SCRIPT, result)
        self.assertIn(DIDI_PRESALE_KEEP_SCRIPT, result)
        for legacy in DIDIADS_NOOP_SCRIPT_RULES:
            self.assertNotIn(legacy, result)
        second, second_removed = apply_didi_script_and_homepage_cleanup(result)
        self.assertEqual(second, result)
        self.assertEqual(second_removed, 0)

    def test_fails_closed_when_didiads_noop_trigger_drifts(self):
        from apply_local_overrides import (
            DIDIADS_NOOP_SCRIPT_RULES, DIDIADS_COMMON_V5_SCRIPT,
            DIDI_OTA_KEEP_SCRIPT, DIDI_PRESALE_KEEP_SCRIPT,
            apply_didi_script_and_homepage_cleanup,
        )
        from apply_local_overrides import DIDI_CORE_NATIVE_RULE_CURRENT, DIDI_USERCENTER_LAYOUT_NATIVE_PREFIX
        fixture = [
            "[Argument]", "[Rule]", "[Rewrite]",
            DIDI_CORE_NATIVE_RULE_CURRENT, DIDI_USERCENTER_LAYOUT_NATIVE_PREFIX + "[]",
            "[Script]", DIDIADS_NOOP_SCRIPT_RULES[0].replace('tag="滴滴出行"', 'tag="changed"'),
            DIDIADS_COMMON_V5_SCRIPT, DIDI_OTA_KEEP_SCRIPT, DIDI_PRESALE_KEEP_SCRIPT, "[MITM]",
        ]
        with self.assertRaisesRegex(ValueError, "no-op script trigger drifted"):
            apply_didi_script_and_homepage_cleanup(fixture)

    def test_fails_closed_when_didiads_common_v5_trigger_is_missing(self):
        from apply_local_overrides import (
            DIDI_CORE_NATIVE_RULE, DIDI_USERCENTER_LAYOUT_NATIVE_PREFIX,
            DIDIADS_NOOP_SCRIPT_RULES, DIDI_OTA_KEEP_SCRIPT, DIDI_PRESALE_KEEP_SCRIPT,
            apply_didi_script_and_homepage_cleanup,
        )
        fixture = [
            "[Argument]", "[Rule]", "[Rewrite]", DIDI_CORE_NATIVE_RULE,
            DIDI_USERCENTER_LAYOUT_NATIVE_PREFIX + "[]", "[Script]",
            *DIDIADS_NOOP_SCRIPT_RULES, DIDI_OTA_KEEP_SCRIPT, DIDI_PRESALE_KEEP_SCRIPT, "[MITM]",
        ]
        with self.assertRaisesRegex(ValueError, "common/v5 canonical script trigger missing"):
            apply_didi_script_and_homepage_cleanup(fixture)

    def test_fails_closed_when_didi_core_or_usercenter_native_rule_is_missing(self):
        from apply_local_overrides import (
            DIDI_CORE_LEGACY_SCRIPT, DIDI_USERCENTER_LEGACY_SCRIPT,
            DIDI_OTA_KEEP_SCRIPT, DIDI_PRESALE_KEEP_SCRIPT,
            DIDI_USERCENTER_LAYOUT_NATIVE_PREFIX, DIDIADS_COMMON_V5_SCRIPT,
            apply_didi_script_and_homepage_cleanup,
        )
        fixture = [
            "[Argument]", "[Rule]", "[Rewrite]", DIDI_USERCENTER_LAYOUT_NATIVE_PREFIX + "[]",
            "[Script]", DIDI_CORE_LEGACY_SCRIPT, DIDI_USERCENTER_LEGACY_SCRIPT,
            DIDIADS_COMMON_V5_SCRIPT, DIDI_OTA_KEEP_SCRIPT, DIDI_PRESALE_KEEP_SCRIPT, "[MITM]",
        ]
        with self.assertRaisesRegex(ValueError, "core homepage native rule inventory changed"):
            apply_didi_script_and_homepage_cleanup(fixture)

    def test_generated_plugin_keeps_only_live_didi_scripts_and_native_homepage_cleaners(self):
        from pathlib import Path
        from apply_local_overrides import (
            DIDI_CORE_LEGACY_SCRIPT, DIDI_USERCENTER_LEGACY_SCRIPT,
            DIDI_OTA_KEEP_SCRIPT, DIDI_PRESALE_KEEP_SCRIPT,
            DIDI_CORE_LEGACY_JSON_RULE, DIDI_CORE_NATIVE_RULE,
            DIDI_USERCENTER_LAYOUT_LEGACY_JSON_RULE,
            DIDIADS_COMMON_V5_SCRIPT, DIDIADS_NOOP_SCRIPT_RULES,
            DIDI_HOME_FAST_LEGACY_REJECT, apply,
        )
        plugin = Path(__file__).parent / "allAdRewrite.plugin"
        result = apply(plugin.read_text(encoding="utf-8"))
        self.assertNotIn(DIDI_CORE_LEGACY_SCRIPT, result)
        self.assertNotIn(DIDI_USERCENTER_LEGACY_SCRIPT, result)
        self.assertNotIn(DIDI_CORE_LEGACY_JSON_RULE, result)
        self.assertNotIn(DIDI_USERCENTER_LAYOUT_LEGACY_JSON_RULE, result)
        self.assertNotIn(DIDI_HOME_FAST_LEGACY_REJECT, result)
        self.assertIn(DIDI_CORE_NATIVE_RULE, result)
        self.assertIn(DIDIADS_COMMON_V5_SCRIPT, result)
        self.assertIn(DIDI_OTA_KEEP_SCRIPT, result)
        self.assertIn(DIDI_PRESALE_KEEP_SCRIPT, result)
        for legacy in DIDIADS_NOOP_SCRIPT_RULES:
            self.assertNotIn(legacy, result)

    def test_removes_didi_core_homepage_reject_when_field_cleaner_exists(self):
        from apply_local_overrides import (
            DIDI_HOME_CORE_LEGACY_REJECT, DIDI_HOME_CORE_RESPONSE_PREFIX,
            remove_didi_homepage_rejects_shadowing_field_cleaners,
        )
        response = DIDI_HOME_CORE_RESPONSE_PREFIX + '".data.order_cards.nav_list_card.data |= map(select(.nav_id == \\"bike\\"))")'
        unrelated = r"^https:\\/\\/conf\\.diditaxi\\.com\\.cn\\/dynamic\\/conf reject-dict"
        result, removed = remove_didi_homepage_rejects_shadowing_field_cleaners(
            [DIDI_HOME_CORE_LEGACY_REJECT, unrelated, response]
        )
        self.assertEqual(removed, 1)
        self.assertNotIn(DIDI_HOME_CORE_LEGACY_REJECT, result)
        self.assertIn(unrelated, result)
        self.assertIn(response, result)
        self.assertEqual(remove_didi_homepage_rejects_shadowing_field_cleaners(result)[1], 0)

    def test_fails_closed_when_didi_core_homepage_cleaner_is_missing(self):
        from apply_local_overrides import (
            DIDI_HOME_CORE_LEGACY_REJECT,
            remove_didi_homepage_rejects_shadowing_field_cleaners,
        )
        with self.assertRaisesRegex(ValueError, "core field-level response cleaner"):
            remove_didi_homepage_rejects_shadowing_field_cleaners([DIDI_HOME_CORE_LEGACY_REJECT])

    def test_generated_plugin_preserves_didi_core_field_cleaner_without_whole_endpoint_reject(self):
        from pathlib import Path
        from apply_local_overrides import DIDI_HOME_CORE_LEGACY_REJECT, DIDI_HOME_CORE_RESPONSE_PREFIX
        plugin = Path(__file__).parent / "allAdRewrite.plugin"
        result = apply(plugin.read_text(encoding="utf-8"))
        self.assertNotIn(DIDI_HOME_CORE_LEGACY_REJECT, result)
        self.assertIn(DIDI_HOME_CORE_RESPONSE_PREFIX, result)

    def test_removes_didi_whole_homepage_rejects_when_field_cleaners_exist(self):
        from apply_local_overrides import (
            DIDI_HOME_SLOW_LEGACY_REJECT, DIDI_HOME_FAST_LEGACY_REJECT,
            DIDI_HOME_SLOW_RESPONSE_PREFIX, DIDI_HOME_FAST_RESPONSE_PREFIX,
            remove_didi_homepage_rejects_shadowing_field_cleaners,
        )
        slow_response = DIDI_HOME_SLOW_RESPONSE_PREFIX + '["data.order_cards.new_loss_banner_card"])'
        fast_response = DIDI_HOME_FAST_RESPONSE_PREFIX + '["data.order_cards"])'
        unrelated = r"^https:\/\/conf\.diditaxi\.com\.cn\/dynamic\/conf reject-dict"
        fixture = [
            DIDI_HOME_SLOW_LEGACY_REJECT, DIDI_HOME_FAST_LEGACY_REJECT,
            unrelated, slow_response, fast_response,
        ]
        result, removed = remove_didi_homepage_rejects_shadowing_field_cleaners(fixture)
        self.assertEqual(removed, 2)
        self.assertNotIn(DIDI_HOME_SLOW_LEGACY_REJECT, result)
        self.assertNotIn(DIDI_HOME_FAST_LEGACY_REJECT, result)
        self.assertIn(unrelated, result)
        self.assertIn(slow_response, result)
        self.assertIn(fast_response, result)
        self.assertEqual(remove_didi_homepage_rejects_shadowing_field_cleaners(result)[1], 0)

    def test_preserves_didi_homepage_reject_if_field_cleaner_is_missing(self):
        from apply_local_overrides import (
            DIDI_HOME_FAST_LEGACY_REJECT,
            remove_didi_homepage_rejects_shadowing_field_cleaners,
        )
        with self.assertRaisesRegex(ValueError, "field-level response cleaner inventory changed"):
            remove_didi_homepage_rejects_shadowing_field_cleaners([DIDI_HOME_FAST_LEGACY_REJECT])

    def test_fails_closed_when_didi_homepage_legacy_reject_drifts(self):
        from apply_local_overrides import (
            DIDI_HOME_SLOW_RESPONSE_PREFIX,
            remove_didi_homepage_rejects_shadowing_field_cleaners,
        )
        drifted = r"^https?:\/\/conf\.diditaxi\.com\.cn\/homepage\/v\d\/other\/slow reject"
        response = DIDI_HOME_SLOW_RESPONSE_PREFIX + '["data.banner"])'
        with self.assertRaisesRegex(ValueError, "legacy reject changed"):
            remove_didi_homepage_rejects_shadowing_field_cleaners([drifted, response])

    def test_fails_closed_on_duplicate_didi_homepage_legacy_reject(self):
        from apply_local_overrides import (
            DIDI_HOME_FAST_LEGACY_REJECT, DIDI_HOME_FAST_RESPONSE_PREFIX,
            remove_didi_homepage_rejects_shadowing_field_cleaners,
        )
        response = DIDI_HOME_FAST_RESPONSE_PREFIX + '["data.banner"])'
        with self.assertRaisesRegex(ValueError, "duplicate Didi homepage fast"):
            remove_didi_homepage_rejects_shadowing_field_cleaners(
                [DIDI_HOME_FAST_LEGACY_REJECT, DIDI_HOME_FAST_LEGACY_REJECT, response]
            )

    def test_generated_plugin_does_not_reject_didi_homepage_before_field_cleaning(self):
        from pathlib import Path
        from apply_local_overrides import (
            DIDI_HOME_SLOW_LEGACY_REJECT, DIDI_HOME_FAST_LEGACY_REJECT,
            DIDI_HOME_SLOW_RESPONSE_PREFIX, DIDI_HOME_FAST_RESPONSE_PREFIX,
        )
        plugin = Path(__file__).parent / "allAdRewrite.plugin"
        original = plugin.read_text(encoding="utf-8")
        result = apply(original)
        self.assertNotIn(DIDI_HOME_SLOW_LEGACY_REJECT, result)
        self.assertNotIn(DIDI_HOME_FAST_LEGACY_REJECT, result)
        self.assertIn(DIDI_HOME_SLOW_RESPONSE_PREFIX, result)
        self.assertIn(DIDI_HOME_FAST_RESPONSE_PREFIX, result)
        self.assertIn(r"^https:\/\/ct\.xiaojukeji\.com\/agent\/v3\/feeds reject-dict", result)



if __name__ == "__main__":
    unittest.main()
