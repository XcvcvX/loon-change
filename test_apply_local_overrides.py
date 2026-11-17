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

    def test_consolidates_starplucker_config_into_one_jq_parse(self):
        from apply_local_overrides import (
            STARPLUCKER_DOUBLE_JQ_RULE, STARPLUCKER_SINGLE_JQ_RULE,
            consolidate_starplucker_config_jq,
        )
        result, changed = consolidate_starplucker_config_jq([STARPLUCKER_DOUBLE_JQ_RULE])
        self.assertEqual(changed, 1)
        self.assertEqual(result, [STARPLUCKER_SINGLE_JQ_RULE])
        self.assertEqual(result[0].count("response.json.jq("), 1)
        self.assertIn("del(.search_suggestions)? |", result[0])

    def test_consolidates_upstream_split_starplucker_jq_rules_after_adjacent_merge(self):
        from apply_local_overrides import (
            STARPLUCKER_DOUBLE_JQ_RULE, STARPLUCKER_SINGLE_JQ_RULE,
            consolidate_starplucker_config_jq, merge_adjacent_response_json_rewrites,
        )
        prefix, pipeline = STARPLUCKER_DOUBLE_JQ_RULE.split(" then ", 1)
        first_action, second_action = pipeline.split(" | ", 1)
        first, second = prefix + " then " + first_action, prefix + " then " + second_action
        # The upstream converter emits the two actions as separate same-URL rules.
        merged, merge_count = merge_adjacent_response_json_rewrites([first, second])
        self.assertEqual(merge_count, 1)
        self.assertEqual(merged, [STARPLUCKER_DOUBLE_JQ_RULE])
        result, changed = consolidate_starplucker_config_jq(merged)
        self.assertEqual(changed, 1)
        self.assertEqual(result, [STARPLUCKER_SINGLE_JQ_RULE])
        self.assertEqual(result[0].count("response.json.jq("), 1)

    def test_starplucker_consolidation_fails_closed_on_rule_drift_or_duplicates(self):
        from apply_local_overrides import STARPLUCKER_DOUBLE_JQ_RULE, consolidate_starplucker_config_jq
        with self.assertRaisesRegex(ValueError, "StarPlucker config jq rule changed"):
            consolidate_starplucker_config_jq([STARPLUCKER_DOUBLE_JQ_RULE, STARPLUCKER_DOUBLE_JQ_RULE])
        changed = STARPLUCKER_DOUBLE_JQ_RULE.replace("search_suggestions", "search_suggestion")
        with self.assertRaisesRegex(ValueError, "StarPlucker config jq rule changed"):
            consolidate_starplucker_config_jq([changed])



    def test_scopes_taobao_ossgw_block_to_ad_creatives_only(self):
        from apply_local_overrides import (
            TAOBAO_OSS_BROAD_DOMAIN_RULE,
            TAOBAO_OSS_LEGACY_CREATIVE_RULE,
            TAOBAO_OSS_SCOPED_CREATIVE_RULE,
        )
        base = """#!name=test
[Rule]
DOMAIN,ossgw.alicdn.com,REJECT
DOMAIN,ut.taobao.com,REJECT
[Rewrite]
^https?:\\/\\/ossgw.alicdn.com\\/creatives-assets\\/image\\/ reject-200
^https?:\\/\\/acs\\.m\\.taobao\\.com\\/gw\\/mtop\\.film\\.mtopadvertiseapi\\.queryadvertise reject-dict
[Script]
[MITM]
hostname = ossgw.alicdn.com, acs.m.taobao.com, creditcard.bankcomm.cn, creditcard.bankcomm.com, creditcardapp.bankcomm.cn, creditcardapp.bankcomm.com
"""
        result = apply(base)
        rule_section = result.split("[Rule]", 1)[1].split("[Rewrite]", 1)[0]
        rewrite_section = result.split("[Rewrite]", 1)[1].split("[Script]", 1)[0]
        self.assertNotIn(TAOBAO_OSS_BROAD_DOMAIN_RULE, rule_section)
        self.assertNotIn(TAOBAO_OSS_LEGACY_CREATIVE_RULE, rewrite_section)
        self.assertEqual(rewrite_section.count(TAOBAO_OSS_SCOPED_CREATIVE_RULE), 1)
        self.assertIn("DOMAIN,ut.taobao.com,REJECT", rule_section)
        self.assertIn("acs\\.m\\.taobao", rewrite_section)
        self.assertIn("ossgw.alicdn.com", result.split("[MITM]", 1)[1])
        self.assertEqual(apply(result), result)

    def test_taobao_oss_scope_rejects_broad_rule_without_path_replacement(self):
        base = """#!name=test
[Rule]
DOMAIN,ossgw.alicdn.com,REJECT
[Rewrite]
^https?:\\/\\/other\\.example reject
[Script]
[MITM]
hostname = ossgw.alicdn.com, creditcard.bankcomm.cn, creditcard.bankcomm.com, creditcardapp.bankcomm.cn, creditcardapp.bankcomm.com
"""
        with self.assertRaises(ValueError):
            apply(base)

    def test_taobao_oss_scope_rejects_unreviewed_domain_rule_variant(self):
        base = """#!name=test
[Rule]
DOMAIN-SUFFIX,ossgw.alicdn.com,REJECT
[Rewrite]
^https?:\\/\\/ossgw.alicdn.com\\/creatives-assets\\/image\\/ reject-200
[Script]
[MITM]
hostname = ossgw.alicdn.com, creditcard.bankcomm.cn, creditcard.bankcomm.com, creditcardapp.bankcomm.cn, creditcardapp.bankcomm.com
"""
        with self.assertRaises(ValueError):
            apply(base)

    def test_taobao_oss_scope_requires_existing_mitm_hostname(self):
        base = """#!name=test
[Rule]
DOMAIN,ossgw.alicdn.com,REJECT
[Rewrite]
^https?:\\/\\/ossgw.alicdn.com\\/creatives-assets\\/image\\/ reject-200
[Script]
[MITM]
hostname = acs.m.taobao.com, creditcard.bankcomm.cn, creditcard.bankcomm.com, creditcardapp.bankcomm.cn, creditcardapp.bankcomm.com
"""
        with self.assertRaises(ValueError):
            apply(base)

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
        from apply_local_overrides import (
            DDQX_NEWDETAILS_NATIVE_RULE, replace_ddqx_newdetails_body_rewrites,
        )
        legacy = r'^https?:\/\/maicai\.api\.ddxq\.mobi\/homeApi\/newDetails response-body-replace-regex suspension random_body'
        modern = r'response if ${url} ~= /^https?:\/\/maicai\.api\.ddxq\.mobi\/homeApi\/newDetails/ then response.body.replace(/suspension/, "fmz200")'
        keep = r'^https?:\/\/maicai\.api\.ddxq\.mobi\/homeApi\/getHomeAdPop reject-dict'
        result, converted = replace_ddqx_newdetails_body_rewrites(["[Rewrite]", legacy, modern, keep])
        self.assertEqual(converted, 2)
        self.assertNotIn(legacy, result)
        self.assertNotIn(modern, result)
        self.assertIn(DDQX_NEWDETAILS_NATIVE_RULE, result)
        self.assertIn(keep, result)

    def test_preserves_unknown_duoduo_grocery_newdetails_rule_without_partial_conversion(self):
        from apply_local_overrides import (
            DDQX_NEWDETAILS_MATCHER, DDQX_NEWDETAILS_LEGACY_ACTION,
            DDQX_NEWDETAILS_MODERN_ACTION, DDQX_NEWDETAILS_NATIVE_RULE,
        )
        legacy = DDQX_NEWDETAILS_MATCHER + " " + DDQX_NEWDETAILS_LEGACY_ACTION
        modern = DDQX_NEWDETAILS_MATCHER + " " + DDQX_NEWDETAILS_MODERN_ACTION
        changed = r'response if ${url} ~= /^https?:\/\/maicai\.api\.ddxq\.mobi\/homeApi\/newDetails/ then response.body.replace(/data/, "hidden")'
        fixture = BASE.replace("[Rewrite]", "[Rewrite]\n" + legacy + "\n" + modern + "\n" + changed)
        result = apply(fixture)
        rewrite = result.split("[Rewrite]", 1)[1].split("[Script]", 1)[0]
        self.assertIn(changed, rewrite)
        self.assertIn(legacy, rewrite)
        self.assertIn(modern, rewrite)
        self.assertNotIn(DDQX_NEWDETAILS_NATIVE_RULE, rewrite)

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
        unrelated = 'response if ${url} ~= /api.example.com/ then script("https://example.invalid/keep.js")'
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

    def test_consolidates_current_romeo_ishowshu_response_script_trigger(self):
        from apply_local_overrides import (
            PDD_RSTORE_HOMEPAGE_TRIGGER, PDD_LOCAL_HOMEPAGE_TRIGGER,
            PDD_ISHOWSHU_HOMEPAGE_TRIGGER, consolidate_pdd_homepage_script,
        )
        fixture = [
            "[Script]", PDD_RSTORE_HOMEPAGE_TRIGGER,
            PDD_ISHOWSHU_HOMEPAGE_TRIGGER, "[MITM]",
        ]
        result, removed = consolidate_pdd_homepage_script(fixture)
        self.assertEqual(removed, 2)
        self.assertEqual(result.count(PDD_LOCAL_HOMEPAGE_TRIGGER), 1)
        self.assertNotIn(PDD_ISHOWSHU_HOMEPAGE_TRIGGER, result)

    def test_consolidates_commit_pinned_romeo_ishowshu_pdd_trigger(self):
        from apply_local_overrides import (
            PDD_RSTORE_HOMEPAGE_TRIGGER, PDD_LOCAL_HOMEPAGE_TRIGGER,
            PDD_ISHOWSHU_HOMEPAGE_TRIGGER, consolidate_pdd_homepage_script,
        )
        pinned = PDD_ISHOWSHU_HOMEPAGE_TRIGGER.replace(
            "https://github.com/ifflagged/Romeo/raw/main/",
            "https://raw.githubusercontent.com/ifflagged/Romeo/" + "d" * 40 + "/",
        )
        fixture = ["[Script]", PDD_RSTORE_HOMEPAGE_TRIGGER, pinned, "[MITM]"]
        result, removed = consolidate_pdd_homepage_script(fixture)
        self.assertEqual(removed, 2)
        self.assertEqual(result.count(PDD_LOCAL_HOMEPAGE_TRIGGER), 1)
        self.assertNotIn(pinned, result)
        self.assertEqual(consolidate_pdd_homepage_script(result)[1], 0)

    def test_accepts_exact_legacy_ishowshu_pdd_trigger(self):
        from apply_local_overrides import (
            PDD_RSTORE_HOMEPAGE_TRIGGER, PDD_LOCAL_HOMEPAGE_TRIGGER,
            PDD_ISHOWSHU_HOMEPAGE_LEGACY_TRIGGER, consolidate_pdd_homepage_script,
        )
        fixture = [
            "[Script]", PDD_RSTORE_HOMEPAGE_TRIGGER,
            PDD_ISHOWSHU_HOMEPAGE_LEGACY_TRIGGER, "[MITM]",
        ]
        result, removed = consolidate_pdd_homepage_script(fixture)
        self.assertEqual(removed, 2)
        self.assertEqual(result.count(PDD_LOCAL_HOMEPAGE_TRIGGER), 1)

    def test_native_pdd_homepage_response_rewrite_is_not_a_script_trigger(self):
        from apply_local_overrides import consolidate_pdd_homepage_script
        native = 'response if ${url} ~= /^https:\\/\\/api\\.pinduoduo\\.com\\/api\\/alexa\\/homepage\\?/i then response.json.delete("result.icon_set")'
        fixture = ["[Script]", native, "[MITM]"]
        result, removed = consolidate_pdd_homepage_script(fixture)
        self.assertEqual(removed, 0)
        self.assertEqual(result, fixture)

    def test_normalizes_repository_relative_pdd_script_path(self):
        from apply_local_overrides import (
            PDD_LOCAL_HOMEPAGE_RELATIVE_TRIGGER, PDD_LOCAL_HOMEPAGE_TRIGGER,
            consolidate_pdd_homepage_script,
        )
        fixture = ["[Script]", PDD_LOCAL_HOMEPAGE_RELATIVE_TRIGGER, "[MITM]"]
        result, removed = consolidate_pdd_homepage_script(fixture)
        self.assertEqual(removed, 0)
        self.assertEqual(result, ["[Script]", PDD_LOCAL_HOMEPAGE_TRIGGER, "[MITM]"])

    def test_pdd_homepage_consolidation_fails_closed_on_trigger_drift(self):
        from apply_local_overrides import PDD_ISHOWSHU_HOMEPAGE_TRIGGER
        changed = PDD_ISHOWSHU_HOMEPAGE_TRIGGER.replace("requires_body=true", "requires_body=false")
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

    def test_consolidates_only_duplicate_pdd_splash_404_and_preserves_distinct_actions(self):
        from apply_local_overrides import (
            PDD_SPLASH_OLD_CANONICAL_RULE, PDD_SPLASH_CANONICAL_RULE,
            PDD_SPLASH_DUPLICATE_404_RULE, PDD_SPLASH_DISTINCT_ACTION_RULES,
            consolidate_pdd_splash_rules,
        )
        unrelated = "request if ${url} ~= /^https?:\\/\\/api\\.pinduoduo\\.com\\/api\\/other/ then reject(404)"
        fixture = [
            PDD_SPLASH_OLD_CANONICAL_RULE, PDD_SPLASH_DUPLICATE_404_RULE,
            *PDD_SPLASH_DISTINCT_ACTION_RULES, unrelated,
        ]
        result, removed = consolidate_pdd_splash_rules(fixture)
        self.assertEqual(removed, 1)
        self.assertEqual(result.count(PDD_SPLASH_CANONICAL_RULE), 1)
        for action_rule in PDD_SPLASH_DISTINCT_ACTION_RULES:
            self.assertIn(action_rule, result)
        self.assertIn(unrelated, result)
        self.assertEqual(consolidate_pdd_splash_rules(result)[1], 0)

    def test_pdd_splash_consolidation_preserves_unknown_or_incomplete_inventory(self):
        from apply_local_overrides import (
            PDD_SPLASH_OLD_CANONICAL_RULE, PDD_SPLASH_DUPLICATE_404_RULE,
            PDD_SPLASH_DISTINCT_ACTION_RULES, consolidate_pdd_splash_rules,
        )
        baseline = [PDD_SPLASH_OLD_CANONICAL_RULE, *PDD_SPLASH_DISTINCT_ACTION_RULES]
        unknown = [*baseline, "request /cappuccino/splash-new reject"]
        preserved, changed = consolidate_pdd_splash_rules(unknown)
        self.assertEqual(changed, 0)
        self.assertEqual(preserved, unknown)
        incomplete = [PDD_SPLASH_OLD_CANONICAL_RULE]
        preserved, changed = consolidate_pdd_splash_rules(incomplete)
        self.assertEqual(changed, 0)
        self.assertEqual(preserved, incomplete)
        with self.assertRaisesRegex(ValueError, "duplicate known matchers"):
            consolidate_pdd_splash_rules([*baseline, PDD_SPLASH_OLD_CANONICAL_RULE])
        with self.assertRaisesRegex(ValueError, "duplicate known matchers"):
            consolidate_pdd_splash_rules([*baseline, PDD_SPLASH_DUPLICATE_404_RULE, PDD_SPLASH_DUPLICATE_404_RULE])

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

    def test_removes_only_taobao_homepage_feed_rules_covered_by_same_action(self):
        from apply_local_overrides import (
            TAOBAO_FLIGGY_HTTP_COVER, TAOBAO_FLIGGY_HTTPS_COVER,
            TAOBAO_FLIGGY_HTTPS_REDUNDANT, TAOBAO_CAINIAO_FLYAD_COVER,
            TAOBAO_CAINIAO_FLYAD_REDUNDANT, TAOBAO_HOME_HTTP_COVER,
            TAOBAO_HOME_HTTPS_COVER, TAOBAO_HOME_HTTPS_SUBSET,
            TAOBAO_HOME_SPLASH_SUBSET, remove_redundant_taobao_rewrite_rules,
        )
        unrelated = r"^https?:\/\/guide-acs\.m\.taobao\.com\/gw\/mtop\.taobao\.wireless\.home\.config reject-dict"
        fixture = [
            "[Rewrite]", TAOBAO_FLIGGY_HTTP_COVER, TAOBAO_FLIGGY_HTTPS_COVER,
            TAOBAO_FLIGGY_HTTPS_REDUNDANT, TAOBAO_CAINIAO_FLYAD_COVER,
            TAOBAO_CAINIAO_FLYAD_REDUNDANT, TAOBAO_HOME_HTTP_COVER,
            TAOBAO_HOME_HTTPS_COVER, TAOBAO_HOME_HTTPS_SUBSET,
            TAOBAO_HOME_SPLASH_SUBSET, unrelated, "[Script]",
        ]
        result, removed = remove_redundant_taobao_rewrite_rules(fixture)
        self.assertEqual(removed, 4)
        for rule in (TAOBAO_FLIGGY_HTTP_COVER, TAOBAO_FLIGGY_HTTPS_COVER,
                     TAOBAO_CAINIAO_FLYAD_COVER, TAOBAO_HOME_HTTP_COVER,
                     TAOBAO_HOME_HTTPS_COVER, unrelated):
            self.assertIn(rule, result)
        for rule in (TAOBAO_FLIGGY_HTTPS_REDUNDANT, TAOBAO_CAINIAO_FLYAD_REDUNDANT,
                     TAOBAO_HOME_HTTPS_SUBSET, TAOBAO_HOME_SPLASH_SUBSET):
            self.assertNotIn(rule, result)
        self.assertEqual(remove_redundant_taobao_rewrite_rules(result)[1], 0)

    def test_taobao_rewrite_cleanup_fails_closed_on_drift_or_missing_cover(self):
        from apply_local_overrides import (
            TAOBAO_FLIGGY_HTTPS_REDUNDANT, TAOBAO_CAINIAO_FLYAD_REDUNDANT,
            TAOBAO_HOME_HTTPS_SUBSET, remove_redundant_taobao_rewrite_rules,
        )
        with self.assertRaisesRegex(ValueError, "inventory changed"):
            remove_redundant_taobao_rewrite_rules([
                "[Rewrite]", TAOBAO_FLIGGY_HTTPS_REDUNDANT.replace("predict", "predict_v2")
            ])
        with self.assertRaisesRegex(ValueError, "covering rewrite missing"):
            remove_redundant_taobao_rewrite_rules(["[Rewrite]", TAOBAO_CAINIAO_FLYAD_REDUNDANT])
        with self.assertRaisesRegex(ValueError, "covering rewrite missing"):
            remove_redundant_taobao_rewrite_rules(["[Rewrite]", TAOBAO_HOME_HTTPS_SUBSET])

    def test_taobao_rewrite_cleanup_rejects_duplicate_known_rules(self):
        from apply_local_overrides import (
            TAOBAO_FLIGGY_HTTP_COVER, TAOBAO_FLIGGY_HTTPS_COVER,
            TAOBAO_FLIGGY_HTTPS_REDUNDANT, remove_redundant_taobao_rewrite_rules,
        )
        with self.assertRaisesRegex(ValueError, "duplicate Taobao homepage/feed rewrite"):
            remove_redundant_taobao_rewrite_rules([
                "[Rewrite]", TAOBAO_FLIGGY_HTTP_COVER, TAOBAO_FLIGGY_HTTPS_COVER,
                TAOBAO_FLIGGY_HTTPS_REDUNDANT, TAOBAO_FLIGGY_HTTPS_REDUNDANT,
            ])

    def test_consolidates_goofish_scripts_to_one_local_trigger_per_endpoint(self):
        from apply_local_overrides import (
            GOOFISH_CANONICAL_SCRIPT_TRIGGERS, GOOFISH_REDUNDANT_SCRIPT_TRIGGERS,
            consolidate_goofish_script_triggers,
        )
        unrelated = 'response if ${url} ~= /example.com/ then script("https://example.invalid/keep.js")'
        fixture = ["[Script]", *GOOFISH_REDUNDANT_SCRIPT_TRIGGERS, unrelated, "[MITM]"]
        result, removed = consolidate_goofish_script_triggers(fixture)
        self.assertEqual(removed, len(GOOFISH_REDUNDANT_SCRIPT_TRIGGERS))
        script = result[result.index("[Script]") + 1:result.index("[MITM]")]
        for trigger in GOOFISH_CANONICAL_SCRIPT_TRIGGERS:
            self.assertEqual(script.count(trigger), 1)
        for trigger in GOOFISH_REDUNDANT_SCRIPT_TRIGGERS:
            self.assertNotIn(trigger, script)
        self.assertIn(unrelated, script)
        self.assertEqual(consolidate_goofish_script_triggers(result)[1], 0)

    def test_consolidates_mixed_goofish_canonical_and_current_upstream_subset(self):
        from apply_local_overrides import (
            GOOFISH_CANONICAL_SCRIPT_TRIGGERS, GOOFISH_REDUNDANT_SCRIPT_TRIGGERS,
            consolidate_goofish_script_triggers,
        )
        upstream_subset = GOOFISH_REDUNDANT_SCRIPT_TRIGGERS[:10]
        fixture = ["[Script]", *GOOFISH_CANONICAL_SCRIPT_TRIGGERS,
                   *upstream_subset, "[MITM]"]
        result, removed = consolidate_goofish_script_triggers(fixture)
        self.assertEqual(removed, len(upstream_subset))
        script = result[result.index("[Script]") + 1:result.index("[MITM]")]
        for trigger in GOOFISH_CANONICAL_SCRIPT_TRIGGERS:
            self.assertEqual(script.count(trigger), 1)
        for trigger in upstream_subset:
            self.assertNotIn(trigger, script)
        self.assertEqual(consolidate_goofish_script_triggers(result)[1], 0)

    def test_rebuilds_goofish_canonical_set_from_known_partial_upstream_inventory(self):
        from apply_local_overrides import (
            GOOFISH_CANONICAL_SCRIPT_TRIGGERS, GOOFISH_REDUNDANT_SCRIPT_TRIGGERS,
            consolidate_goofish_script_triggers,
        )
        upstream_subset = GOOFISH_REDUNDANT_SCRIPT_TRIGGERS[:10]
        result, removed = consolidate_goofish_script_triggers(
            ["[Script]", *upstream_subset, "[MITM]"]
        )
        self.assertEqual(removed, len(upstream_subset))
        script = result[result.index("[Script]") + 1:result.index("[MITM]")]
        self.assertEqual(list(script), list(GOOFISH_CANONICAL_SCRIPT_TRIGGERS))

    def test_removes_current_romeo_hosted_goofish_duplicate_trigger(self):
        from apply_local_overrides import (
            GOOFISH_CANONICAL_SCRIPT_TRIGGERS,
            GOOFISH_REDUNDANT_SCRIPT_TRIGGERS,
            consolidate_goofish_script_triggers,
        )
        romeo_trigger = next(
            item for item in GOOFISH_REDUNDANT_SCRIPT_TRIGGERS
            if "ifflagged/Romeo/raw/main/Modules/JavaScript/ishowshu/goofish/" in item
        )
        fixture = ["[Script]", *GOOFISH_CANONICAL_SCRIPT_TRIGGERS, romeo_trigger, "[MITM]"]
        result, removed = consolidate_goofish_script_triggers(fixture)
        self.assertEqual(removed, 1)
        script = result[result.index("[Script]") + 1:result.index("[MITM]")]
        self.assertEqual(list(script), list(GOOFISH_CANONICAL_SCRIPT_TRIGGERS))
        self.assertEqual(consolidate_goofish_script_triggers(result)[1], 0)

    def test_removes_commit_pinned_romeo_goofish_script_duplicate(self):
        from apply_local_overrides import (
            GOOFISH_CANONICAL_SCRIPT_TRIGGERS,
            GOOFISH_REDUNDANT_SCRIPT_TRIGGERS,
            consolidate_goofish_script_triggers,
        )
        source = next(
            item for item in GOOFISH_REDUNDANT_SCRIPT_TRIGGERS
            if "ifflagged/Romeo/raw/main/Modules/JavaScript/ishowshu/goofish/" in item
        )
        pinned = source.replace(
            "https://github.com/ifflagged/Romeo/raw/main/",
            "https://raw.githubusercontent.com/ifflagged/Romeo/" + "b" * 40 + "/",
        )
        fixture = ["[Script]", *GOOFISH_CANONICAL_SCRIPT_TRIGGERS, pinned, "[MITM]"]
        result, removed = consolidate_goofish_script_triggers(fixture)
        self.assertEqual(removed, 1)
        script = result[result.index("[Script]") + 1:result.index("[MITM]")]
        self.assertEqual(list(script), list(GOOFISH_CANONICAL_SCRIPT_TRIGGERS))
        self.assertEqual(consolidate_goofish_script_triggers(result)[1], 0)

    def test_normalizes_repository_relative_goofish_script_paths(self):
        from apply_local_overrides import (
            GOOFISH_CANONICAL_SCRIPT_TRIGGERS, consolidate_goofish_script_triggers,
        )
        relative = [
            trigger.replace(
                "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/xianyu/goofish.js",
                "scripts/xianyu/goofish.js",
            )
            for trigger in GOOFISH_CANONICAL_SCRIPT_TRIGGERS
        ]
        fixture = ["[Script]", *relative, "[MITM]"]
        result, removed = consolidate_goofish_script_triggers(fixture)
        self.assertEqual(removed, 0)
        script = result[result.index("[Script]") + 1:result.index("[MITM]")]
        for trigger in GOOFISH_CANONICAL_SCRIPT_TRIGGERS:
            self.assertIn(trigger, script)
        self.assertFalse(any("script-path=scripts/xianyu/goofish.js" in line for line in script))

    def test_goofish_script_consolidation_fails_closed_on_drift_missing_or_duplicate_triggers(self):
        from apply_local_overrides import (
            GOOFISH_REDUNDANT_SCRIPT_TRIGGERS, consolidate_goofish_script_triggers,
        )
        changed = GOOFISH_REDUNDANT_SCRIPT_TRIGGERS[0].replace("requires-body=true", "requires-body=false")
        with self.assertRaisesRegex(ValueError, "inventory changed"):
            consolidate_goofish_script_triggers(["[Script]", *GOOFISH_REDUNDANT_SCRIPT_TRIGGERS[1:], changed])
        from apply_local_overrides import GOOFISH_CANONICAL_SCRIPT_TRIGGERS
        with self.assertRaisesRegex(ValueError, "canonical trigger inventory incomplete"):
            consolidate_goofish_script_triggers(["[Script]", *GOOFISH_CANONICAL_SCRIPT_TRIGGERS[:-1]])
        with self.assertRaisesRegex(ValueError, "duplicate redundant Goofish"):
            consolidate_goofish_script_triggers(["[Script]", *GOOFISH_REDUNDANT_SCRIPT_TRIGGERS,
                                                 GOOFISH_REDUNDANT_SCRIPT_TRIGGERS[0]])

    def test_removes_only_xianyu_legacy_json_and_strict_subset_rules(self):
        from apply_local_overrides import (
            XIAN_YU_REWRITE_PAIRS, XIAN_YU_REQUEST_SUBSET_PAIRS,
            remove_redundant_xianyu_rewrite_rules,
        )
        unrelated = r"^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idle\.trade\.order\.render\/ response-body-json-jq 'del(.data.unrelated)'"
        fixture = ["[Rewrite]"]
        for redundant, canonical in (*XIAN_YU_REWRITE_PAIRS, *XIAN_YU_REQUEST_SUBSET_PAIRS):
            fixture.extend([redundant, canonical])
        fixture.extend([unrelated, "[Script]"])
        result, removed = remove_redundant_xianyu_rewrite_rules(fixture)
        self.assertEqual(removed, len(XIAN_YU_REWRITE_PAIRS) + len(XIAN_YU_REQUEST_SUBSET_PAIRS))
        for redundant, canonical in (*XIAN_YU_REWRITE_PAIRS, *XIAN_YU_REQUEST_SUBSET_PAIRS):
            self.assertIn(canonical, result)
            self.assertNotIn(redundant, result)
        self.assertIn(unrelated, result)
        self.assertEqual(remove_redundant_xianyu_rewrite_rules(result)[1], 0)

    def test_xianyu_rewrite_cleanup_fails_closed_on_drift_missing_cover_or_duplicate(self):
        from apply_local_overrides import (
            XIAN_YU_REWRITE_PAIRS, XIAN_YU_REQUEST_SUBSET_PAIRS,
            remove_redundant_xianyu_rewrite_rules,
        )
        redundant, canonical = XIAN_YU_REWRITE_PAIRS[0]
        with self.assertRaisesRegex(ValueError, "inventory changed"):
            remove_redundant_xianyu_rewrite_rules(["[Rewrite]", redundant.replace("del(.data)", "del(.data.foo)")])
        with self.assertRaisesRegex(ValueError, "covering rewrite missing"):
            remove_redundant_xianyu_rewrite_rules(["[Rewrite]", redundant])
        redundant, canonical = XIAN_YU_REQUEST_SUBSET_PAIRS[0]
        with self.assertRaisesRegex(ValueError, "covering rewrite missing"):
            remove_redundant_xianyu_rewrite_rules(["[Rewrite]", redundant])
        with self.assertRaisesRegex(ValueError, "duplicate Xianyu rewrite"):
            remove_redundant_xianyu_rewrite_rules(["[Rewrite]", redundant, redundant, canonical])

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

    def test_removes_romeo_pinned_kelee_taobao_script_as_reviewed_duplicate(self):
        from apply_local_overrides import TAOBAO_CANONICAL_SCRIPT_TRIGGERS, TAOBAO_REDUNDANT_SCRIPT_TRIGGERS
        commit = "a" * 40
        romeo_url = (
            "https://raw.githubusercontent.com/ifflagged/Romeo/" + commit
            + "/Modules/JavaScript/Kelee/Taobao_remove_ads/kelee.one_Taobao_remove_ads.js"
        )
        romeo_triggers = [
            trigger.replace(
                "https://raw.githubusercontent.com/zmjde/loon-plugins/main/JS/Taobao/Taobao_remove_ads.js",
                romeo_url,
            )
            for trigger in TAOBAO_REDUNDANT_SCRIPT_TRIGGERS[4:6]
        ]
        other_redundant = (
            list(TAOBAO_REDUNDANT_SCRIPT_TRIGGERS[:4])
            + list(TAOBAO_REDUNDANT_SCRIPT_TRIGGERS[6:])
        )
        fixture = BASE.replace(
            "[Script]",
            "[Script]\n" + "\n".join(TAOBAO_CANONICAL_SCRIPT_TRIGGERS)
            + "\n" + "\n".join(other_redundant + romeo_triggers),
        )
        result = apply(fixture)
        script = result.split("[Script]", 1)[1].split("[MITM]", 1)[0]
        for trigger in TAOBAO_CANONICAL_SCRIPT_TRIGGERS:
            self.assertEqual(script.count(trigger), 1)
        for trigger in romeo_triggers:
            self.assertNotIn(trigger, script)
        self.assertEqual(apply(result), result)

    def test_fails_closed_on_unrecognized_romeo_taobao_asset_path(self):
        from apply_local_overrides import TAOBAO_REDUNDANT_SCRIPT_TRIGGERS
        changed = TAOBAO_REDUNDANT_SCRIPT_TRIGGERS[4].replace(
            "https://raw.githubusercontent.com/zmjde/loon-plugins/main/JS/Taobao/Taobao_remove_ads.js",
            "https://raw.githubusercontent.com/ifflagged/Romeo/not-a-commit/Modules/JavaScript/Kelee/Taobao_remove_ads/kelee.one_Taobao_remove_ads.js",
        )
        fixture = BASE.replace("[Script]", "[Script]\n" + changed)
        with self.assertRaisesRegex(ValueError, "Taobao splash script trigger changed"):
            apply(fixture)

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

    def test_removes_current_didi_usercenter_fmz_script_switch_template(self):
        from apply_local_overrides import (
            DIDI_USERCENTER_CANONICAL_TRIGGER,
            DIDI_USERCENTER_REDUNDANT_TRIGGER_CURRENT,
        )
        fixture = BASE.replace(
            "[Script]",
            "[Script]\n" + DIDI_USERCENTER_CANONICAL_TRIGGER
            + "\n" + DIDI_USERCENTER_REDUNDANT_TRIGGER_CURRENT,
        )
        result = apply(fixture)
        script = result.split("[Script]", 1)[1].split("[MITM]", 1)[0]
        self.assertEqual(script.count(DIDI_USERCENTER_CANONICAL_TRIGGER), 1)
        self.assertNotIn(DIDI_USERCENTER_REDUNDANT_TRIGGER_CURRENT, script)
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
        single_escape = lambda trigger: trigger.replace("\\\\\\", "\\")
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

    def test_fails_closed_on_duplicate_amap_legacy_script(self):
        from apply_local_overrides import remove_redundant_amap_legacy_scripts
        legacy = "http-response ^https://m5.amap.com/ws/aos/perception/publicTravel/beforeNavi? script-path=https://github.com/ishowshu/qx/raw/main/script/amap.js"
        with self.assertRaisesRegex(ValueError, "duplicate Amap legacy response script trigger"):
            remove_redundant_amap_legacy_scripts(["[Script]", legacy, legacy])

    def test_fails_closed_on_unknown_amap_legacy_script_endpoint(self):
        from apply_local_overrides import remove_redundant_amap_legacy_scripts
        unknown = "http-response ^https://m5.amap.com/ws/unknown/ad script-path=https://example.invalid/amap.js"
        with self.assertRaisesRegex(ValueError, "unknown Amap legacy response script endpoint"):
            remove_redundant_amap_legacy_scripts(["[Script]", unknown], expected_count=1)

    def test_preserves_amap_legacy_script_when_native_handler_is_missing(self):
        from apply_local_overrides import remove_redundant_amap_legacy_scripts
        legacy = "http-response ^https://m5.amap.com/ws/aos/perception/publicTravel/beforeNavi? script-path=https://example.invalid/amap.js"
        result, removed = remove_redundant_amap_legacy_scripts(["[Script]", legacy], expected_count=1)
        self.assertEqual(removed, 0)
        self.assertIn(legacy, result)


    def test_preserves_amap_legacy_script_when_native_handler_is_ambiguous(self):
        from apply_local_overrides import remove_redundant_amap_legacy_scripts
        legacy = "http-response ^https://m5.amap.com/ws/aos/perception/publicTravel/beforeNavi? script-path=https://example.invalid/amap.js"
        canonical = 'response if ${url} ~= /^https:\\/\\/m5\\.amap\\.com\\/ws\\/aos\\/perception\\/publicTravel\\/beforeNavi\\?/i then script("https://example.invalid/rucu6_amap.js")'
        result, removed = remove_redundant_amap_legacy_scripts(
            ["[Script]", legacy, canonical, canonical], expected_count=1
        )
        self.assertEqual(removed, 0)
        self.assertIn(legacy, result)

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

    def test_preserves_baidumap_legacy_trigger_when_gated_twin_is_absent(self):
        from apply_local_overrides import BAIDUMAP_LEGACY_SCRIPT_RULE, remove_redundant_baidumap_script
        legacy, _, _ = BAIDUMAP_LEGACY_SCRIPT_RULE
        result, removed = remove_redundant_baidumap_script([legacy])
        self.assertEqual(removed, 0)
        self.assertEqual(result, [legacy])

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

    def test_preserves_dianping_legacy_trigger_when_gated_twin_is_absent(self):
        from apply_local_overrides import DIANPING_LEGACY_SCRIPT_RULES, remove_redundant_dianping_scripts
        legacy, _, _ = DIANPING_LEGACY_SCRIPT_RULES[0]
        result, removed = remove_redundant_dianping_scripts([legacy])
        self.assertEqual(removed, 0)
        self.assertEqual(result, [legacy])

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

    def test_accepts_interpolated_didiads_switches(self):
        from apply_local_overrides import (
            DIDI_CORE_NATIVE_RULE, DIDI_USERCENTER_LAYOUT_NATIVE_PREFIX,
            DIDI_OTA_KEEP_SCRIPT, DIDI_PRESALE_KEEP_SCRIPT,
            DIDIADS_COMMON_V5_SCRIPT, DIDIADS_NOOP_SCRIPT_RULES,
            apply_didi_script_and_homepage_cleanup,
        )
        noops = [
            rule.replace("enable=didiiuxk_enable", "enable=${didiiuxk_enable}")
            for rule in DIDIADS_NOOP_SCRIPT_RULES
        ]
        common = DIDIADS_COMMON_V5_SCRIPT.replace(
            "enable=didiiuxk_enable", "enable=${didiiuxk_enable}"
        )
        fixture = [
            "[Argument]", "[Rule]", "[Rewrite]", DIDI_CORE_NATIVE_RULE,
            DIDI_USERCENTER_LAYOUT_NATIVE_PREFIX + "[]", "[Script]",
            *noops, common, DIDI_OTA_KEEP_SCRIPT, DIDI_PRESALE_KEEP_SCRIPT, "[MITM]",
        ]
        result, removed = apply_didi_script_and_homepage_cleanup(fixture)
        self.assertEqual(removed, len(DIDIADS_NOOP_SCRIPT_RULES))
        self.assertIn(common, result)
        for rule in noops:
            self.assertNotIn(rule, result)

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
        response = DIDI_HOME_CORE_RESPONSE_PREFIX + '".data.order_cards.nav_list_card.data |= map(select(.nav_id == "bike"))")'
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



class JingdongRuleScopeTests(unittest.TestCase):
    def setUp(self):
        from apply_local_overrides import JD_KEYWORD_SCOPE_RULES, JD_SUFFIX_SCOPE_RULES
        self.keyword_rules = list(JD_KEYWORD_SCOPE_RULES.values())
        self.suffix_rules = list(JD_SUFFIX_SCOPE_RULES.values())
        self.base = """#!name=test
[Rule]
%s
%s
DOMAIN-KEYWORD,unrelated.example,REJECT
[Rewrite]
^https?:\\/\\/example\\.com reject
[Script]
[MITM]
hostname = creditcard.bankcomm.cn, creditcard.bankcomm.com, creditcardapp.bankcomm.cn, creditcardapp.bankcomm.com
""" % ("\n".join(self.keyword_rules), "\n".join(self.suffix_rules))

    def test_removes_only_jd_keyword_shadows_and_preserves_suffix_coverage(self):
        result = apply(self.base)
        rule_section = result.split("[Rule]", 1)[1].split("[Rewrite]", 1)[0]
        for rule in self.keyword_rules:
            self.assertNotIn(rule, rule_section)
        for rule in self.suffix_rules:
            self.assertEqual(rule_section.count(rule), 1)
        self.assertIn("DOMAIN-KEYWORD,unrelated.example,REJECT", rule_section)
        self.assertEqual(apply(result), result)

    def test_rejects_partial_jd_keyword_inventory(self):
        partial = self.base.replace(self.keyword_rules[0] + "\n", "")
        with self.assertRaisesRegex(ValueError, "inventory is partial"):
            apply(partial)

    def test_rejects_missing_exact_suffix_cover(self):
        missing = self.base.replace(self.suffix_rules[0] + "\n", "")
        with self.assertRaisesRegex(ValueError, "DOMAIN-SUFFIX covers"):
            apply(missing)

    def test_rejects_changed_action_and_duplicate_keyword_rules(self):
        changed = self.base.replace(self.keyword_rules[0], self.keyword_rules[0].replace(",REJECT", ",DIRECT"))
        with self.assertRaisesRegex(ValueError, "rule changed"):
            apply(changed)
        duplicate = self.base.replace(self.keyword_rules[0] + "\n", self.keyword_rules[0] + "\n" + self.keyword_rules[0] + "\n")
        with self.assertRaisesRegex(ValueError, "duplicate Jingdong"):
            apply(duplicate)


class JingdongScriptConsolidationTests(unittest.TestCase):
    def setUp(self):
        from apply_local_overrides import (
            JD_RSTORE_LEGACY_TRIGGER, JD_FMZ_LEGACY_TRIGGER,
        )
        self.rstore = JD_RSTORE_LEGACY_TRIGGER
        self.fmz = JD_FMZ_LEGACY_TRIGGER
        self.base = """#!name=jd-test
[Rewrite]
^https?:\\/\\/example\\.com reject
[Script]
""" + self.rstore + "\n" + self.fmz + """
[MITM]
hostname = creditcard.bankcomm.cn, creditcard.bankcomm.com, creditcardapp.bankcomm.cn, creditcardapp.bankcomm.com
"""

    def test_consolidates_duplicate_jd_work_and_preserves_optional_switch(self):
        from apply_local_overrides import JD_CANONICAL_TRIGGER, JD_OPTIONAL_WELCOME_TRIGGER
        result = apply(self.base)
        self.assertNotIn(self.rstore, result)
        self.assertNotIn(self.fmz, result)
        self.assertEqual(result.count(JD_CANONICAL_TRIGGER), 1)
        self.assertEqual(result.count(JD_OPTIONAL_WELCOME_TRIGGER), 1)
        self.assertIn("scripts/jingdong/jd.js", result)
        self.assertNotIn("jd-welcome.js", result)
        self.assertIn("{${jkds_enable}}", result)
        self.assertEqual(apply(result), result)

    def test_accepts_current_jingdong_switch_interpolation_and_preserves_it(self):
        from apply_local_overrides import (
            JD_CANONICAL_TRIGGER, JD_FMZ_LEGACY_TRIGGER_CURRENT,
            JD_OPTIONAL_WELCOME_TRIGGER,
        )
        fixture = self.base.replace(self.fmz, JD_FMZ_LEGACY_TRIGGER_CURRENT)
        result = apply(fixture)
        self.assertNotIn(JD_FMZ_LEGACY_TRIGGER_CURRENT, result)
        self.assertIn(JD_CANONICAL_TRIGGER, result)
        self.assertIn(JD_OPTIONAL_WELCOME_TRIGGER, result)
        self.assertIn("{${jkds_enable}}", JD_OPTIONAL_WELCOME_TRIGGER)
        self.assertEqual(apply(result), result)

    def test_fails_closed_when_either_legacy_trigger_drifts_or_is_missing(self):
        drifted = self.base.replace("tag=JD,requires-body=true", "tag=JD-DRIFT,requires-body=true")
        with self.assertRaisesRegex(ValueError, "Jingdong legacy trigger inventory changed"):
            apply(drifted)
        missing = self.base.replace(self.fmz + "\n", "")
        with self.assertRaisesRegex(ValueError, "Jingdong legacy trigger inventory changed"):
            apply(missing)

    def test_fails_closed_on_duplicate_or_mixed_jd_triggers(self):
        duplicate = self.base.replace(self.fmz, self.fmz + "\n" + self.fmz)
        with self.assertRaisesRegex(ValueError, "Jingdong legacy trigger inventory changed"):
            apply(duplicate)
        from apply_local_overrides import JD_CANONICAL_TRIGGER
        mixed = self.base.replace(self.fmz, self.fmz + "\n" + JD_CANONICAL_TRIGGER)
        with self.assertRaisesRegex(ValueError, "Jingdong script trigger inventory is mixed"):
            apply(mixed)

    def test_local_jd_scripts_preserve_endpoint_coverage_and_safe_parse(self):
        from pathlib import Path
        root = Path(__file__).parent / "scripts/jingdong"
        base_script = (root / "jd.js").read_text(encoding="utf-8")
        welcome_script = (root / "jd-welcome.js").read_text(encoding="utf-8")
        for marker in (
            "functionId=start", "functionId=welcomeHome",
            "functionId=readCustomSurfaceList", "functionId=deliverLayer",
            "functionId=orderTrackBusiness", "functionId=getTabHomeInfo",
            "functionId=myOrderInfo", "functionId=personinfoBusiness",
            "PERSON_INFO_BUSINESS_MID_EXCLUDE", "WELCOME_HOME_TYPE_INCLUDE",
            "CUSTOM_SURFACE_NAME_INCLUDE", "welcomeExtraEnabled",
            "WELCOME_HOME_EXTRA_EXCLUDE", "$argument", "jkds_enable", "JSON.parse(body)",
            "$done({ body: JSON.stringify(obj) })",
        ):
            self.assertIn(marker, base_script)
        self.assertIn("catch (_)", base_script)
        from apply_local_overrides import JD_CANONICAL_TRIGGER, JD_OPTIONAL_WELCOME_TRIGGER
        self.assertNotIn("welcomeHome", JD_CANONICAL_TRIGGER)
        self.assertIn("functionId=welcomeHome", JD_OPTIONAL_WELCOME_TRIGGER)
        self.assertIn("{${jkds_enable}}", JD_OPTIONAL_WELCOME_TRIGGER)
        self.assertIn("scripts/jingdong/jd.js", JD_OPTIONAL_WELCOME_TRIGGER)
        self.assertNotIn("jd-welcome.js", JD_OPTIONAL_WELCOME_TRIGGER)
        for marker in (
            "bottomXview", "float", "photoCeiling", "ruleFloat",
            "searchIcon", "topRotate", "tabBarAtmosphere",
        ):
            self.assertIn(marker, welcome_script)
        self.assertIn("catch (_)", welcome_script)
        for script in (base_script, welcome_script):
            self.assertNotIn("fetch(", script)
            self.assertNotIn("XMLHttpRequest", script)





class ZhihuResponseScriptConsolidationTests(unittest.TestCase):
    def test_consolidates_12_exact_triggers_to_five_tag_preserving_matchers(self):
        from apply_local_overrides import ZHIHU_RESPONSE_CANONICAL_TRIGGERS, ZHIHU_RESPONSE_LEGACY_TRIGGERS, consolidate_zhihu_response_scripts
        fixture = [
            "[Script]", *sorted(ZHIHU_RESPONSE_LEGACY_TRIGGERS),
            r"""http-response ^https:\/\/api\.example\.com script-path=https://example.invalid/keep.js""",
            "[MITM]", "hostname = api.zhihu.com",
        ]
        result, removed = consolidate_zhihu_response_scripts(fixture)
        self.assertEqual(removed, 7)
        self.assertEqual(sum(line in ZHIHU_RESPONSE_CANONICAL_TRIGGERS for line in result), 5)
        self.assertTrue(any("example.invalid/keep.js" in line for line in result))
        self.assertFalse(any("Scripts/zhihu/zhihu.js" in line and line not in ZHIHU_RESPONSE_CANONICAL_TRIGGERS for line in result))
        again, second_removed = consolidate_zhihu_response_scripts(result)
        self.assertEqual(second_removed, 0)
        self.assertEqual(again, result)

    def test_canonical_zhihu_matchers_cover_all_original_endpoints(self):
        import re
        from apply_local_overrides import ZHIHU_RESPONSE_CANONICAL_TRIGGERS
        urls = [
            "https://api.zhihu.com/answers/v2/123",
            "https://page-info.zhihu.com/articles/v2/456",
            "https://api.zhihu.com/commercial_api/app_float_layer",
            "https://api.zhihu.com/feed/render/tab/config?x=1",
            "https://api.zhihu.com/moments_v3",
            "https://api.zhihu.com/topstory/hot-lists/total",
            "https://api.zhihu.com/topstory/recommend",
            "https://api.zhihu.com/v2/topstory/hot-lists/everyone-seeing?x=1",
            "https://api.zhihu.com/root/tab",
            "https://api.zhihu.com/bazaar/vip_tab/header?x=1",
            "https://api.zhihu.com/next-bff",
            "https://api.zhihu.com/questions/123/answers",
            "https://www.zhihu.com/api/v4/articles/123/recommendations?",
            "https://appcloud2.zhihu.com/v3/config",
            "https://m-cloud.zhihu.com/api/cloud/config/all?x=1",
        ]
        patterns = []
        for trigger in ZHIHU_RESPONSE_CANONICAL_TRIGGERS:
            raw = trigger.split(" ~= ", 1)[1].split(" then script(", 1)[0]
            end = raw.rfind("/")
            patterns.append(re.compile(raw[1:end], re.I if raw[end + 1:] == "i" else 0))
        self.assertTrue(all(any(pattern.search(url) for pattern in patterns) for url in urls))

    def test_preserves_partial_zhihu_inventory_and_rejects_duplicates_or_drift(self):
        from apply_local_overrides import ZHIHU_RESPONSE_LEGACY_TRIGGERS, consolidate_zhihu_response_scripts
        base = sorted(ZHIHU_RESPONSE_LEGACY_TRIGGERS)
        partial = ["[Script]", *base[:-1]]
        result, removed = consolidate_zhihu_response_scripts(partial)
        self.assertEqual(removed, 0)
        self.assertEqual(result, partial)
        with self.assertRaisesRegex(ValueError, "duplicate triggers"):
            consolidate_zhihu_response_scripts(["[Script]", *base, base[0]])
        drifted = ["[Script]", *base[:-1], base[-1].replace("requires_body=true", "requires_body=false")]
        with self.assertRaisesRegex(ValueError, "unknown trigger"):
            consolidate_zhihu_response_scripts(drifted)

    def test_consolidates_zhihu_inventory_with_interpolated_switches(self):
        from apply_local_overrides import (
            ZHIHU_RESPONSE_LEGACY_TRIGGERS,
            ZHIHU_RESPONSE_CANONICAL_TRIGGERS,
            consolidate_zhihu_response_scripts,
        )
        fixture = ["[Script]"] + [
            trigger.replace("enable=vihu_enable", "enable=${vihu_enable}")
            for trigger in ZHIHU_RESPONSE_LEGACY_TRIGGERS
        ] + ["[MITM]"]
        result, removed = consolidate_zhihu_response_scripts(fixture)
        self.assertEqual(removed, len(ZHIHU_RESPONSE_LEGACY_TRIGGERS) - len(ZHIHU_RESPONSE_CANONICAL_TRIGGERS))
        script = result[result.index("[Script]") + 1:result.index("[MITM]")]
        self.assertEqual(len(script), len(ZHIHU_RESPONSE_CANONICAL_TRIGGERS))
        self.assertTrue(all("enable=$" + "{" in line for line in script))
        self.assertEqual(consolidate_zhihu_response_scripts(result)[1], 0)

class SoulScriptConsolidationTests(unittest.TestCase):
    def test_consolidates_all_exact_soul_triggers_into_two_case_safe_matchers(self):
        from apply_local_overrides import SOUL_CANONICAL_TRIGGERS, SOUL_LEGACY_TRIGGERS, consolidate_soul_scripts
        fixture = [
            "[Script]", *sorted(SOUL_LEGACY_TRIGGERS),
            r"""http-response ^https:\/\/api\.example\.com script-path=https://example.invalid/keep.js""",
            "[MITM]", "hostname = api-pay.soulapp.cn",
        ]
        result, removed = consolidate_soul_scripts(fixture)
        self.assertEqual(removed, 14)
        self.assertEqual(sum(line in SOUL_CANONICAL_TRIGGERS for line in result), 2)
        self.assertTrue(any("example.invalid/keep.js" in line for line in result))
        self.assertFalse(any("Scripts/soul/soul_ads.js" in line and line not in SOUL_CANONICAL_TRIGGERS for line in result))
        again, second_removed = consolidate_soul_scripts(result)
        self.assertEqual(second_removed, 0)
        self.assertEqual(again, result)

    def test_accepts_interpolated_switch_and_preserves_it_in_canonical_triggers(self):
        from apply_local_overrides import (
            SOUL_CANONICAL_TRIGGERS, SOUL_LEGACY_TRIGGERS, consolidate_soul_scripts,
        )
        fixture = [
            "[Script]",
            *[item.replace("enable=soul_enable", "enable=${soul_enable}")
              for item in SOUL_LEGACY_TRIGGERS],
            "[MITM]",
        ]
        result, removed = consolidate_soul_scripts(fixture)
        self.assertEqual(removed, len(SOUL_LEGACY_TRIGGERS))
        for trigger in SOUL_CANONICAL_TRIGGERS:
            self.assertIn(trigger.replace("enable=soul_enable", "enable=${soul_enable}"), result)
        self.assertEqual(consolidate_soul_scripts(result), (result, 0))

    def test_fails_closed_on_missing_duplicate_or_drifted_soul_trigger(self):
        from apply_local_overrides import SOUL_LEGACY_TRIGGERS, consolidate_soul_scripts
        base = sorted(SOUL_LEGACY_TRIGGERS)
        missing = ["[Script]", *base[:-1]]
        with self.assertRaisesRegex(ValueError, "Soul script trigger inventory changed"):
            consolidate_soul_scripts(missing)
        duplicate = ["[Script]", *base, base[0]]
        with self.assertRaisesRegex(ValueError, "Soul script trigger inventory changed"):
            consolidate_soul_scripts(duplicate)
        drifted = ["[Script]", *base[:-1], base[-1].replace("timeout=60", "timeout=30")]
        with self.assertRaisesRegex(ValueError, "Soul script trigger inventory changed"):
            consolidate_soul_scripts(drifted)

    def test_preserves_absent_or_already_consolidated_soul_inventory(self):
        from apply_local_overrides import SOUL_CANONICAL_TRIGGERS, consolidate_soul_scripts
        self.assertEqual(consolidate_soul_scripts(["[Script]", "http-response ^https:\/\/example.com script-path=https://other.invalid/a.js"]), (["[Script]", "http-response ^https:\/\/example.com script-path=https://other.invalid/a.js"], 0))
        canonical = ["[Script]", *SOUL_CANONICAL_TRIGGERS]
        self.assertEqual(consolidate_soul_scripts(canonical), (canonical, 0))


class MeituanScriptConsolidationTests(unittest.TestCase):
    def setUp(self):
        from apply_local_overrides import MEITUAN_LEGACY_TRIGGERS
        self.triggers = MEITUAN_LEGACY_TRIGGERS
        self.base = """#!name=meituan-test
[Rewrite]
^https?:\\/\\/example\\.com reject
[Script]
""" + "\n".join(self.triggers) + """
[MITM]
hostname = creditcard.bankcomm.cn, creditcard.bankcomm.com, creditcardapp.bankcomm.cn, creditcardapp.bankcomm.com
"""

    def test_consolidates_all_meituan_scripts_to_one_exact_local_trigger(self):
        from apply_local_overrides import MEITUAN_CANONICAL_TRIGGER
        result = apply(self.base)
        for trigger in self.triggers:
            self.assertNotIn(trigger, result)
        self.assertEqual(result.count(MEITUAN_CANONICAL_TRIGGER), 1)
        self.assertIn("scripts/meituan/meituan.js", result)
        self.assertEqual(apply(result), result)

    def test_rebuilds_full_local_meituan_union_from_exact_rstore_only_upstream_subset(self):
        from apply_local_overrides import MEITUAN_CANONICAL_TRIGGER
        fixture = self.base.replace(
            "\n".join(self.triggers),
            "\n".join(self.triggers[:3]),
        )
        result = apply(fixture)
        self.assertEqual(result.count(MEITUAN_CANONICAL_TRIGGER), 1)
        for trigger in self.triggers:
            self.assertNotIn(trigger, result)
        self.assertEqual(apply(result), result)

    def test_fails_closed_on_missing_drifted_or_duplicate_meituan_trigger(self):
        missing = self.base.replace(self.triggers[0] + "\n", "")
        with self.assertRaisesRegex(ValueError, "Meituan script trigger inventory changed"):
            apply(missing)
        drifted = self.base.replace("tag=MEITUAN,requires-body=true", "tag=MEITUAN-DRIFT,requires-body=true")
        with self.assertRaisesRegex(ValueError, "Meituan script trigger inventory changed"):
            apply(drifted)
        duplicate = self.base.replace(self.triggers[0], self.triggers[0] + "\n" + self.triggers[0])
        with self.assertRaisesRegex(ValueError, "Meituan script trigger inventory changed"):
            apply(duplicate)

    def test_fails_closed_on_unknown_or_mixed_meituan_trigger(self):
        unknown = self.base.replace(self.triggers[0], self.triggers[0] + "\n" +
            "http-response ^https?:\\\\/\\\\/new\\.meituan\\.com\\/ad script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/meituan.js,tag=NEW")
        with self.assertRaisesRegex(ValueError, "Meituan script trigger inventory changed"):
            apply(unknown)
        from apply_local_overrides import MEITUAN_CANONICAL_TRIGGER
        mixed = self.base.replace(self.triggers[0], self.triggers[0] + "\n" + MEITUAN_CANONICAL_TRIGGER)
        with self.assertRaisesRegex(ValueError, "Meituan script trigger inventory changed"):
            apply(mixed)

    def test_local_meituan_script_and_combined_matcher_cover_reviewed_endpoints(self):
        from pathlib import Path
        from apply_local_overrides import MEITUAN_CANONICAL_TRIGGER
        script = (Path(__file__).parent / "scripts/meituan/meituan.js").read_text(encoding="utf-8")
        for marker in (
            r"p\d\.meituan\.net", "cleanTabArea", "cleanFeed",
            "cleanMine", "cleanDefaultWord", "cleanHotRecommend",
            "cleanAiSkill", "clearArea", "cleanMiniProgram",
            "topBannerArea", "startupPicArea", "oneCentBuy",
            "JSON.parse(body)", "$done({ body: JSON.stringify(obj) })",
        ):
            self.assertIn(marker, script)
        for marker in (
            r"tabbar\/all\/query", r"index\/aggregate", "personalcenter_2154",
            "gwc_feed1_2265", "mt-personalcenter", "assistify",
            "shoppingCartEntry", "startupPicture",
        ):
            self.assertIn(marker, MEITUAN_CANONICAL_TRIGGER)
        self.assertIn("catch (_)", script)
        self.assertNotIn("fetch(", script)
        self.assertNotIn("XMLHttpRequest", script)





class DouyinTncDirectSafetyTests(unittest.TestCase):
    def setUp(self):
        from apply_local_overrides import DOUYIN_TNC_REJECT_RULES, DOUYIN_TNC_DIRECT_RULE
        self.rejects = list(DOUYIN_TNC_REJECT_RULES)
        self.direct = DOUYIN_TNC_DIRECT_RULE
        self.base = ["[Rule]", *self.rejects, "DOMAIN-SUFFIX,pangolin-sdk-toutiao.com,REJECT",
                     self.direct, "[Rewrite]", "^https://example.com/ad reject", "[MITM]"]

    def test_removes_only_conflicting_tnc_rejects_and_keeps_direct_guard(self):
        from apply_local_overrides import remove_douyin_tnc_conflicting_rejects
        result, removed = remove_douyin_tnc_conflicting_rejects(self.base)
        self.assertEqual(removed, 4)
        for rule in self.rejects:
            self.assertNotIn(rule, result)
        self.assertEqual(result.count(self.direct), 1)
        self.assertIn("DOMAIN-SUFFIX,pangolin-sdk-toutiao.com,REJECT", result)
        self.assertEqual(remove_douyin_tnc_conflicting_rejects(result), (result, 0))

    def test_fails_closed_on_partial_duplicate_or_unknown_tnc_reject_inventory(self):
        from apply_local_overrides import remove_douyin_tnc_conflicting_rejects
        partial = [line for line in self.base if line != self.rejects[0]]
        with self.assertRaisesRegex(ValueError, "inventory changed"):
            remove_douyin_tnc_conflicting_rejects(partial)
        rewrite_index = self.base.index("[Rewrite]")
        duplicate = self.base[:rewrite_index] + [self.rejects[0]] + self.base[rewrite_index:]
        with self.assertRaisesRegex(ValueError, "duplicate Douyin TNC"):
            remove_douyin_tnc_conflicting_rejects(duplicate)
        unknown = self.base[:rewrite_index] + ["DOMAIN,tnc3-bjlgy.snssdk.com,REJECT"] + self.base[rewrite_index:]
        with self.assertRaisesRegex(ValueError, "inventory changed"):
            remove_douyin_tnc_conflicting_rejects(unknown)

    def test_requires_the_existing_tnc_direct_guard(self):
        from apply_local_overrides import remove_douyin_tnc_conflicting_rejects
        missing = [line for line in self.base if line != self.direct]
        with self.assertRaisesRegex(ValueError, "missing DIRECT guard"):
            remove_douyin_tnc_conflicting_rejects(missing)

    def test_checked_in_plugin_has_no_tnc_reject_before_direct_guard(self):
        from pathlib import Path
        from apply_local_overrides import DOUYIN_TNC_REJECT_RULES, DOUYIN_TNC_DIRECT_RULE
        plugin = Path(__file__).with_name("allAdRewrite.plugin").read_text(encoding="utf-8")
        for rule in DOUYIN_TNC_REJECT_RULES:
            self.assertNotIn(rule, plugin)
        self.assertEqual(plugin.count(DOUYIN_TNC_DIRECT_RULE), 1)

class DouyinContentCdnScopeTests(unittest.TestCase):
    def setUp(self):
        from apply_local_overrides import DOUYIN_CONTENT_CDN_OVERBLOCKS, DOUYIN_CDN_REQUIRED_AD_PATH_MARKERS
        self.overblocks = list(DOUYIN_CONTENT_CDN_OVERBLOCKS)
        self.markers = list(DOUYIN_CDN_REQUIRED_AD_PATH_MARKERS)
        self.base = ["[Rule]", self.overblocks[0][1], self.overblocks[1][1],
                     "DOMAIN-SUFFIX,pangolin-sdk-toutiao.com,REJECT", "[Rewrite]",
                     *[rule for section, rule in self.overblocks if section == "Rewrite"],
                     r"request if ${url} ~= /^https?:\\/\\/.+\\.(pglstatp-toutiao|pstatp)\\.com\\/(obj|img)\\/(ad-app-package|ad)\\/.+/i then reject(404)",
                     "request if ${url} ~= /^https?:\\/\\/.+\\.pstatp\\.com\\/obj\\/ad-pattern\\/renderer/ then reject(404)",
                     "request if ${url} ~= /^https?:\\/\\/.+\\.snssdk\\.com\\/api\\/ad\\/.+/ then reject(404)",
                     "request if ${url} ~= /^https?:\\/\\/.+\\.pstatp\\.com\\/obj\\/mosaic-legacy\\/.+\\?from\\=ad/ then reject(404)",
                     "request if ${url} ~= /^https?:\\/\\/.*\\.(pglstatp-toutiao|pstatp)\\.com\\/obj\\/ad-pattern\\/renderer/ then reject(404)",
                     "[Script]", "[MITM]"]

    def test_removes_only_content_cdn_overblocks_and_keeps_ad_path_rules(self):
        from apply_local_overrides import remove_douyin_content_cdn_overblocks
        result, removed = remove_douyin_content_cdn_overblocks(self.base)
        self.assertEqual(removed, len(self.overblocks))
        for _, rule in self.overblocks:
            self.assertNotIn(rule, result)
        for marker in self.markers:
            self.assertTrue(any(marker in line.replace(chr(92), "") for line in result))
        self.assertIn("DOMAIN-SUFFIX,pangolin-sdk-toutiao.com,REJECT", result)
        self.assertEqual(remove_douyin_content_cdn_overblocks(result), (result, 0))

    def test_handles_partial_inventory_but_fails_duplicate_or_unknown_origin_rules(self):
        from apply_local_overrides import remove_douyin_content_cdn_overblocks
        partial = [line for line in self.base if line != self.overblocks[0][1]]
        partial_result, partial_removed = remove_douyin_content_cdn_overblocks(partial)
        self.assertEqual(partial_removed, len(self.overblocks) - 1)
        self.assertNotIn(self.overblocks[1][1], partial_result)

        duplicate = self.base[:self.base.index("[Rewrite]")] + [self.overblocks[0][1]] + self.base[self.base.index("[Rewrite]"): ]
        with self.assertRaisesRegex(ValueError, "duplicate Douyin content CDN"):
            remove_douyin_content_cdn_overblocks(duplicate)

        unknown_rule = self.overblocks[2][1].replace(r"p\d", "p9")
        unknown = [unknown_rule if line == self.overblocks[2][1] else line for line in self.base]
        with self.assertRaisesRegex(ValueError, "inventory changed"):
            remove_douyin_content_cdn_overblocks(unknown)

    def test_current_fmz_source_inventory_is_supported(self):
        from apply_local_overrides import DOUYIN_CONTENT_CDN_OVERBLOCKS, remove_douyin_content_cdn_overblocks
        current_rules = [
            DOUYIN_CONTENT_CDN_OVERBLOCKS[0][1],
            DOUYIN_CONTENT_CDN_OVERBLOCKS[1][1],
            DOUYIN_CONTENT_CDN_OVERBLOCKS[2][1],
            DOUYIN_CONTENT_CDN_OVERBLOCKS[3][1],
        ]
        fixture = ["[Rule]", *current_rules[:2], "[Rewrite]", *current_rules[2:],
                   *[line for line in self.base if line.startswith("request if") and "origin" not in line],
                   "[Script]", "[MITM]"]
        result, removed = remove_douyin_content_cdn_overblocks(fixture)
        self.assertEqual(removed, 4)
        for rule in current_rules:
            self.assertNotIn(rule, result)

    def test_removes_double_escaped_equivalent_origin_overblocks(self):
        from apply_local_overrides import remove_douyin_content_cdn_overblocks
        doubled = [
            r"request if ${url} ~= /^https?:\\/\\/p(b)?\\d\\.pstatp\\.com\\/origin/ then reject(404)",
            r"request if ${url} ~= /^https?:\\/\\/p\\d\\.pstatp\\.com\\/origin/i then reject(404)",
            r"request if ${url} ~= /^https?:\\/\\/pb\\d\\.pstatp\\.com\\/origin/i then reject(404)",
        ]
        fixture = ["[Rule]", self.overblocks[0][1], self.overblocks[1][1],
                   "[Rewrite]", *doubled,
                   *[line for line in self.base if line.startswith("request if") and "origin" not in line],
                   "[Script]", "[MITM]"]
        result, removed = remove_douyin_content_cdn_overblocks(fixture)
        self.assertEqual(removed, 5)
        for rule in doubled:
            self.assertNotIn(rule, result)
        for marker in self.markers:
            self.assertTrue(any(marker in line.replace(chr(92), "") for line in result))

    def test_removes_exact_unescaped_pstatp_hostname_overblock_variants(self):
        from apply_local_overrides import remove_douyin_content_cdn_overblocks
        unescaped_dot = [
            r"request if ${url} ~= /^https?:\/\/p(b)?\d\.pstatp\.com\/origin/ then reject(404)",
            r"request if ${url} ~= /^https?:\/\/p\d\.pstatp\.com\/origin/i then reject(404)",
            r"request if ${url} ~= /^https?:\/\/pb\d\.pstatp\.com\/origin/i then reject(404)",
        ]
        unescaped_dot = [rule.replace(r"pstatp\.com", "pstatp.com") for rule in unescaped_dot]
        fixture = ["[Rule]", self.overblocks[0][1], self.overblocks[1][1],
                   "[Rewrite]", *unescaped_dot,
                   *[line for line in self.base if line.startswith("request if") and "origin" not in line],
                   "[Script]", "[MITM]"]
        result, removed = remove_douyin_content_cdn_overblocks(fixture)
        self.assertEqual(removed, 5)
        for rule in unescaped_dot:
            self.assertNotIn(rule, result)
        for marker in self.markers:
            self.assertTrue(any(marker in line.replace(chr(92), "") for line in result))

    def test_checked_in_plugin_snapshot_keeps_ad_paths_without_content_cdn_overblocks(self):
        from pathlib import Path
        from apply_local_overrides import DOUYIN_CONTENT_CDN_OVERBLOCKS, DOUYIN_CDN_REQUIRED_AD_PATH_MARKERS
        plugin = Path(__file__).with_name("allAdRewrite.plugin").read_text(encoding="utf-8")
        for _, rule in DOUYIN_CONTENT_CDN_OVERBLOCKS:
            self.assertNotIn(rule, plugin)
        normalized = plugin.replace(chr(92), "")
        for marker in DOUYIN_CDN_REQUIRED_AD_PATH_MARKERS:
            self.assertIn(marker, normalized)

class DouyinNonAdServiceHostSafetyTests(unittest.TestCase):
    def setUp(self):
        from apply_local_overrides import DOUYIN_NON_AD_SERVICE_HOST_BLOCKS, DOUYIN_AD_HOST_GUARD
        self.targets = list(DOUYIN_NON_AD_SERVICE_HOST_BLOCKS)
        self.ad_guard = DOUYIN_AD_HOST_GUARD
        self.base = ["[Rule]", *self.targets, self.ad_guard, "DOMAIN,unrelated.example,REJECT",
                     "[Rewrite]", "^https://example.com/ad reject", "[MITM]"]

    def test_removes_only_non_ad_service_host_blocks_and_keeps_pangle_ad_guard(self):
        from apply_local_overrides import remove_douyin_non_ad_service_host_blocks
        result, removed = remove_douyin_non_ad_service_host_blocks(self.base)
        self.assertEqual(removed, 4)
        for rule in self.targets:
            self.assertNotIn(rule, result)
        self.assertEqual(result.count(self.ad_guard), 1)
        self.assertIn("DOMAIN,unrelated.example,REJECT", result)
        self.assertEqual(remove_douyin_non_ad_service_host_blocks(result), (result, 0))

    def test_fails_closed_on_partial_duplicate_or_changed_service_host_rules(self):
        from apply_local_overrides import remove_douyin_non_ad_service_host_blocks
        partial = [line for line in self.base if line != self.targets[0]]
        with self.assertRaisesRegex(ValueError, "inventory is partial"):
            remove_douyin_non_ad_service_host_blocks(partial)
        duplicate = self.base[:self.base.index(self.ad_guard)] + [self.targets[0]] + self.base[self.base.index(self.ad_guard):]
        with self.assertRaisesRegex(ValueError, "duplicate Douyin non-ad service"):
            remove_douyin_non_ad_service_host_blocks(duplicate)
        changed = [line.replace(",REJECT", ",DIRECT") if line == self.targets[0] else line for line in self.base]
        with self.assertRaisesRegex(ValueError, "rule changed"):
            remove_douyin_non_ad_service_host_blocks(changed)

    def test_checked_in_plugin_snapshot_allows_service_hosts_and_keeps_ad_guard(self):
        from pathlib import Path
        from apply_local_overrides import DOUYIN_NON_AD_SERVICE_HOST_BLOCKS, DOUYIN_AD_HOST_GUARD
        plugin = Path(__file__).with_name("allAdRewrite.plugin").read_text(encoding="utf-8")
        for rule in DOUYIN_NON_AD_SERVICE_HOST_BLOCKS:
            self.assertNotIn(rule, plugin)
        self.assertEqual(plugin.count(DOUYIN_AD_HOST_GUARD), 1)

class BilibiliCoreServiceScopeTests(unittest.TestCase):
    def setUp(self):
        from apply_local_overrides import BILIBILI_CORE_SERVICE_OVERBLOCKS, BILIBILI_AD_HOST_GUARDS
        self.targets = list(BILIBILI_CORE_SERVICE_OVERBLOCKS)
        self.ad_guards = list(BILIBILI_AD_HOST_GUARDS)
        self.base = ["[Rule]", *[rule for section, rule in self.targets if section == "Rule"],
                     *self.ad_guards, "DOMAIN,unrelated.example,REJECT", "[Rewrite]",
                     *[rule for section, rule in self.targets if section == "Rewrite"],
                     "response if ${url} ~= /^https?:\\/\\/app\\.bilibili\\.com\\/x\\/v2\\/splash\\/show/ then response.json.jq(\".\")",
                     "response if ${url} ~= /^https?:\\/\\/app\\.bilibili\\.com\\/x\\/v2\\/feed\\/index/ then response.json.jq(\".\")",
                     "^https?:\\/\\/api\\.bilibili\\.com\\/pgc\\/activity\\/deliver reject-dict",
                     "[Script]", "[MITM]"]

    def test_removes_only_core_service_overblocks_and_keeps_bili_ad_paths(self):
        from apply_local_overrides import remove_bilibili_core_service_overblocks
        result, removed = remove_bilibili_core_service_overblocks(self.base)
        self.assertEqual(removed, 7)
        for _, rule in self.targets:
            self.assertNotIn(rule, result)
        for guard in self.ad_guards:
            self.assertEqual(result.count(guard), 1)
        self.assertIn("DOMAIN,unrelated.example,REJECT", result)
        self.assertEqual(remove_bilibili_core_service_overblocks(result), (result, 0))

    def test_fails_closed_on_partial_duplicate_or_changed_core_service_inventory(self):
        from apply_local_overrides import remove_bilibili_core_service_overblocks
        partial = [line for line in self.base if line != self.targets[0][1]]
        with self.assertRaisesRegex(ValueError, "inventory is partial"):
            remove_bilibili_core_service_overblocks(partial)
        rule_index = self.base.index(self.ad_guards[0])
        duplicate = self.base[:rule_index] + [self.targets[0][1]] + self.base[rule_index:]
        with self.assertRaisesRegex(ValueError, "duplicate Bilibili core-service"):
            remove_bilibili_core_service_overblocks(duplicate)
        changed = [line.replace(",REJECT", ",DIRECT") if line == self.targets[0][1] else line for line in self.base]
        with self.assertRaisesRegex(ValueError, "API host rule changed"):
            remove_bilibili_core_service_overblocks(changed)

    def test_checked_in_plugin_snapshot_allows_core_services_and_keeps_ad_rules(self):
        from pathlib import Path
        from apply_local_overrides import BILIBILI_CORE_SERVICE_OVERBLOCKS, BILIBILI_AD_HOST_GUARDS
        plugin = Path(__file__).with_name("allAdRewrite.plugin").read_text(encoding="utf-8")
        for _, rule in BILIBILI_CORE_SERVICE_OVERBLOCKS:
            self.assertNotIn(rule, plugin)
        for guard in BILIBILI_AD_HOST_GUARDS:
            self.assertEqual(plugin.count(guard), 1)

class BilibiliNonAdFeatureScopeTests(unittest.TestCase):
    def setUp(self):
        from apply_local_overrides import BILIBILI_NON_AD_FEATURE_RULES, BILIBILI_NON_AD_FEATURE_REPLACEMENTS, BILIBILI_AD_PATH_MARKERS
        self.remove_rules = list(BILIBILI_NON_AD_FEATURE_RULES)
        self.replacements = list(BILIBILI_NON_AD_FEATURE_REPLACEMENTS)
        self.markers = list(BILIBILI_AD_PATH_MARKERS)
        self.base = ["[Rule]", "DOMAIN-SUFFIX,ad.bilibili.com,REJECT", "DOMAIN-SUFFIX,adcommon.bilibili.com,REJECT",
                     "[Rewrite]", *self.remove_rules, *[old for old, _ in self.replacements],
                     "response if ${url} ~= /^https?:\\/\\/app\\.bilibili\\.com\\/x\\/v2\\/splash\\/show/ then response.json.jq(\".\")",
                     "response if ${url} ~= /^https?:\\/\\/app\\.bilibili\\.com\\/x\\/v2\\/feed\\/index/ then response.json.jq(\".\")",
                     "^https?:\\/\\/api\\.bilibili\\.com\\/pgc\\/activity\\/deliver reject-dict",
                     "[Script]", "[MITM]"]

    def test_removes_non_ad_mutations_and_keeps_ad_filtering(self):
        from apply_local_overrides import normalize_bilibili_non_ad_feature_overrides
        result, changed = normalize_bilibili_non_ad_feature_overrides(self.base)
        self.assertEqual(changed, len(self.remove_rules) + len(self.replacements))
        for rule in self.remove_rules:
            self.assertNotIn(rule, result)
        for _, new in self.replacements:
            self.assertEqual(result.count(new), 1)
        normalized = "\n".join(line.replace(chr(92), "") for line in result)
        for marker in self.markers:
            self.assertIn(marker, normalized)
        self.assertEqual(normalize_bilibili_non_ad_feature_overrides(result), (result, 0))

    def test_allows_upstream_pruned_known_non_ad_rows_but_fails_closed_on_duplicates_or_drift(self):
        from apply_local_overrides import normalize_bilibili_non_ad_feature_overrides
        partial = [line for line in self.base if line != self.remove_rules[0]]
        result, changed_count = normalize_bilibili_non_ad_feature_overrides(partial)
        self.assertEqual(changed_count, len(self.remove_rules) - 1 + len(self.replacements))
        self.assertNotIn(self.remove_rules[0], result)
        self.assertEqual(normalize_bilibili_non_ad_feature_overrides(result), (result, 0))
        duplicate = self.base[:self.base.index("[Script]")] + [self.remove_rules[0]] + self.base[self.base.index("[Script]"): ]
        with self.assertRaisesRegex(ValueError, "duplicate Bilibili non-ad feature"):
            normalize_bilibili_non_ad_feature_overrides(duplicate)
        changed = [line.replace("9005270400000", "9000000000000") if "due_date" in line else line for line in self.base]
        with self.assertRaisesRegex(ValueError, "rule changed"):
            normalize_bilibili_non_ad_feature_overrides(changed)

    def test_removes_combined_teen_mode_mock_and_grpc_status_override(self):
        from apply_local_overrides import normalize_bilibili_non_ad_feature_overrides
        combined = r'response if ${url} == "https://grpc.biliapi.net/bilibili.app.interface.v1.Teenagers/ModeStatus" then response.body.mock("text", "AAAAABMKEQgCEgl0ZWVuYWdlcnMgAioA", 200, true) | response.header.set("grpc-status", "0")'
        self.assertIn(combined, self.remove_rules)
        result, _ = normalize_bilibili_non_ad_feature_overrides(self.base)
        self.assertNotIn(combined, result)
        self.assertIn("/x/v2/feed/index", "\n".join(result).replace(chr(92), ""))

    def test_removes_combined_search_default_words_mock_and_grpc_status_override(self):
        from apply_local_overrides import normalize_bilibili_non_ad_feature_overrides
        combined = r'response if ${url} == "https://grpc.biliapi.net/bilibili.app.interface.v1.Search/DefaultWords" then response.body.mock("text", "AAAAACEaHeaQnOe0ouinhumikeOAgeeVquWJp+aIlnVw5Li7KAE=", 200, true) | response.header.set("grpc-status", "0")'
        self.assertIn(combined, self.remove_rules)
        result, _ = normalize_bilibili_non_ad_feature_overrides(self.base)
        self.assertNotIn(combined, result)
        self.assertIn("/x/v2/feed/index", "\n".join(result).replace(chr(92), ""))

    def test_removes_native_tracker_configuration_override(self):
        from apply_local_overrides import normalize_bilibili_non_ad_feature_overrides
        tracker_rule = r'response if ${url} ~= /^https:\/\/api\.live\.bilibili\.com\/xlive\/open-interface\/v2\/tracker\/conf\?/ then response.json.jq(`.data.domains = ["wss://tracker.chat.bilibili.com"]`)'
        self.assertIn(tracker_rule, self.remove_rules)
        result, _ = normalize_bilibili_non_ad_feature_overrides(self.base)
        self.assertNotIn(tracker_rule, result)
        self.assertIn("/x/v2/feed/index", "\n".join(result).replace(chr(92), ""))

    def test_removes_native_pd_proxy_tracker_stun_override(self):
        from apply_local_overrides import normalize_bilibili_non_ad_feature_overrides
        tracker_rule = r'response if ${url} ~= /^https:\/\/api\.bilibili\.com\/x\/pd-proxy\/tracker\?/ then response.json.jq(`.data[][]? = "stun.chat.bilibili.com:3478"`)'
        self.assertIn(tracker_rule, self.remove_rules)
        result, _ = normalize_bilibili_non_ad_feature_overrides(self.base)
        self.assertNotIn(tracker_rule, result)
        self.assertIn("/x/v2/feed/index", "\n".join(result).replace(chr(92), ""))

    def test_allows_upstream_pruning_of_the_playback_replacement_pair(self):
        from apply_local_overrides import normalize_bilibili_non_ad_feature_overrides
        old, new = self.replacements[0]
        fixture = [line for line in self.base if line != old and line != new]
        result, changed = normalize_bilibili_non_ad_feature_overrides(fixture)
        self.assertEqual(changed, len(self.remove_rules) + len(self.replacements) - 1)
        self.assertNotIn(old, result)
        self.assertNotIn(new, result)
        self.assertIn("/x/v2/feed/index", "\n".join(result).replace(chr(92), ""))

    def test_narrows_playback_mock_without_the_non_ad_playpause_endpoint(self):
        from apply_local_overrides import normalize_bilibili_non_ad_feature_overrides
        result, changed = normalize_bilibili_non_ad_feature_overrides(self.base)
        self.assertEqual(changed, len(self.remove_rules) + len(self.replacements))
        for old, new in self.replacements:
            self.assertIn(old, self.base)
            self.assertNotIn(old, result)
            self.assertEqual(result.count(new), 1)

    def test_checked_in_plugin_has_no_vip_paywall_or_teen_mode_bypass(self):
        from pathlib import Path
        from apply_local_overrides import BILIBILI_NON_AD_FEATURE_RULES, BILIBILI_NON_AD_FEATURE_REPLACEMENTS
        plugin = Path(__file__).with_name("allAdRewrite.plugin").read_text(encoding="utf-8")
        for rule in BILIBILI_NON_AD_FEATURE_RULES:
            self.assertNotIn(rule, plugin)
        for old, new in BILIBILI_NON_AD_FEATURE_REPLACEMENTS:
            self.assertNotIn(old, plugin)
            self.assertLessEqual(plugin.count(new), 1)
        self.assertNotIn("due_date: 9005270400000", plugin)
        self.assertNotIn("del(.data.payment)", plugin)
        self.assertNotIn("Teenagers\\/ModeStatus", plugin)
        self.assertIn("/x/v2/feed/index", plugin.replace(chr(92), ""))

class DouyinHongguoBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.base = r"""#!name=Douyin-Hongguo-test
[Rule]
DOMAIN,webcast-open.douyin.com,REJECT
DOMAIN-KEYWORD,minigame,REJECT
DOMAIN-SUFFIX,dig.bdurl.net,REJECT
DOMAIN-SUFFIX,pangolin-sdk-toutiao.com,REJECT
DOMAIN-SUFFIX,pglstatp-toutiao.com,REJECT
DOMAIN-KEYWORD,ads0-normal-,REJECT
DOMAIN-KEYWORD,ads5-normal-,REJECT
[Rewrite]
^https?:\/\/webcast-open\.douyin\.com\/webcast\/openapi\/feed\/ reject-dict
request if ${url} ~= /^https:\/\/webcast-open\.douyin\.com\/webcast\/openapi\/feed\/\?/ then reject_dict(200)
response if ${url} ~= /^https?:\/\/webcast-open\.douyin\.com\/webcast\/openapi\/feed\//i then response.body.mock("json", "{}", 200)
response if ${url} ~= /^https:\/\/beta-luna\.douyin\.com\/luna\/card\?/ then response.json.replace("card_items[0].is_show", false)
[Script]
[MITM]
hostname = webcast-open.douyin.com, beta-luna.douyin.com, creditcard.bankcomm.cn, creditcard.bankcomm.com, creditcardapp.bankcomm.cn, creditcardapp.bankcomm.com
"""

    def test_removes_only_httpdns_minigame_and_live_feed_blocks(self):
        result = apply(self.base)
        for removed in (
            "DOMAIN,webcast-open.douyin.com,REJECT",
            "DOMAIN-KEYWORD,minigame,REJECT",
            "DOMAIN-SUFFIX,dig.bdurl.net,REJECT",
            "webcast-open.douyin.com",
            "webcast/openapi/feed",
        ):
            self.assertNotIn(removed, result)
        for retained in (
            "DOMAIN-SUFFIX,pangolin-sdk-toutiao.com,REJECT",
            "DOMAIN-SUFFIX,pglstatp-toutiao.com,REJECT",
            "DOMAIN-KEYWORD,ads0-normal-,REJECT",
            "DOMAIN-KEYWORD,ads5-normal-,REJECT",
            "beta-luna.douyin.com",
            "creditcard.bankcomm.cn",
            "response.json.replace",
        ):
            self.assertIn(retained, result)
        self.assertEqual(apply(result), result)

    def test_allows_upstream_pruning_and_removes_duplicate_known_unsafe_rules(self):
        missing = self.base.replace("DOMAIN-KEYWORD,minigame,REJECT\n", "")
        missing_result = apply(missing)
        self.assertNotIn("DOMAIN-KEYWORD,minigame,REJECT", missing_result)
        self.assertNotIn("webcast-open.douyin.com", missing_result)

        duplicate = self.base.replace(
            "DOMAIN-SUFFIX,dig.bdurl.net,REJECT",
            "DOMAIN-SUFFIX,dig.bdurl.net,REJECT\nDOMAIN-SUFFIX,dig.bdurl.net,REJECT",
        )
        duplicate_result = apply(duplicate)
        self.assertNotIn("DOMAIN-SUFFIX,dig.bdurl.net,REJECT", duplicate_result)
        self.assertNotIn("webcast-open.douyin.com", duplicate_result)

    def test_fails_closed_on_drifted_unsafe_rule_inventory(self):
        drifted = self.base.replace(
            "DOMAIN-KEYWORD,minigame,REJECT",
            "DOMAIN-KEYWORD,minigame,REJECT(404)",
        )
        with self.assertRaisesRegex(ValueError, "Douyin/Hongguo safety inventory changed"):
            apply(drifted)

    def test_optional_romeo_live_feed_response_mock_is_removed_but_not_required(self):
        optional = r'response if ${url} ~= /^https?:\/\/webcast-open\.douyin\.com\/webcast\/openapi\/feed\//i then response.body.mock("json", "{}", 200)'
        result = apply(self.base)
        self.assertNotIn(optional, result)
        without_optional = self.base.replace(optional + "\n", "")
        self.assertEqual(apply(without_optional), result)
        duplicated = self.base.replace(optional, optional + "\n" + optional)
        duplicate_result = apply(duplicated)
        self.assertNotIn(optional, duplicate_result)

    def test_fails_closed_on_unknown_live_feed_rule_but_allows_missing_host(self):
        unknown = self.base.replace(
            "DOMAIN,webcast-open.douyin.com,REJECT",
            "DOMAIN,webcast-open.douyin.com,REJECT\nDOMAIN-SUFFIX,webcast-open.douyin.com,REJECT",
        )
        with self.assertRaisesRegex(ValueError, "Douyin/Hongguo safety inventory changed"):
            apply(unknown)
        missing_host = self.base.replace("webcast-open.douyin.com, ", "")
        missing_result = apply(missing_host)
        self.assertNotIn("webcast-open.douyin.com", missing_result)







class KugouJin10RewriteDedupTests(unittest.TestCase):
    def setUp(self):
        self.rules = ["^https?:\\/\\/fx\\.service\\.kugou\\.com\\/mfx-kugoulive\\/ad\\/ reject-dict","^https?:\\/\\/gateway(retry)?\\.kugou\\.com\\/adp\\/ad\\/ reject-dict","^https?:\\/\\/gateway(retry)?\\.kugou\\.com\\/ads\\.gateway\\/ reject-dict","^https?:\\/\\/gateway(retry)?\\.kugou\\.com\\/v\\d\\/feeds\\/follow_feed_fallback reject-dict","^https?:\\/\\/gateway(retry)?\\.kugou\\.com\\/mstc\\/musicsymbol\\/v\\d\\/system\\/profile reject-dict","^https?:\\/\\/gateway(retry)?\\.kugou\\.com\\/searchnofocus\\/v\\d\\/search_no_focus_word reject-dict","^https?:\\/\\/gateway(retry)?\\.kugou\\.com\\/adp\\/bubble\\/v\\d\\/song_play reject-dict","^https?:\\/\\/gateway(retry)?\\.kugou\\.com\\/singerdiscuss\\/v\\d\\/entrance\\/comment reject-dict","^https?:\\/\\/gateway(retry)?\\.kugou\\.com\\/r\\/v\\d\\/general\\/putin\\/midad reject-dict","^https?:\\/\\/gateway(retry)?\\.kugou\\.com\\/ocean\\/v\\d\\/sound\\/banner reject-dict","^https?:\\/\\/gzacshow\\.kugou\\.com\\/mfx-rt-show\\/cdn\\/mo\\/show\\/headline reject-dict","^https?:\\/\\/m1fxgroup\\.kugou\\.com\\/fxsing\\/yqc\\/alongInfo\\/getUserAlongInfo reject-dict","^https?:\\/\\/hwstore\\.kugou\\.com\\/v\\d\\/get_store_data reject-dict","^https?:\\/\\/ep\\.kugou\\.com\\/v\\d\\/album_shop\\/get_entrance_info reject-dict","^https:\\/\\/fx\\.service\\.kugou\\.com\\/mfx-kugoulive\\/ad\\/ reject-dict","^https:\\/\\/gateway(retry)?\\.kugou\\.com\\/adp\\/ad\\/ reject-dict","^https:\\/\\/gateway(retry)?\\.kugou\\.com\\/ads\\.gateway\\/ reject-dict","^https:\\/\\/gateway(retry)?\\.kugou\\.com\\/v\\d\\/feeds\\/follow_feed_fallback reject-dict","^https:\\/\\/gateway(retry)?\\.kugou\\.com\\/mstc\\/musicsymbol\\/v\\d\\/system\\/profile reject-dict","^https:\\/\\/gateway(retry)?\\.kugou\\.com\\/searchnofocus\\/v\\d\\/search_no_focus_word reject-dict","^https:\\/\\/gateway(retry)?\\.kugou\\.com\\/adp\\/bubble\\/v\\d\\/song_play reject-dict","^https:\\/\\/gateway(retry)?\\.kugou\\.com\\/singerdiscuss\\/v\\d\\/entrance\\/comment reject-dict","^https:\\/\\/gateway(retry)?\\.kugou\\.com\\/r\\/v\\d\\/general\\/putin\\/midad reject-dict","^https:\\/\\/gateway(retry)?\\.kugou\\.com\\/ocean\\/v\\d\\/sound\\/banner reject-dict","^https:\\/\\/gzacshow\\.kugou\\.com\\/mfx-rt-show\\/cdn\\/mo\\/show\\/headline reject-dict","^https:\\/\\/m1fxgroup\\.kugou\\.com\\/fxsing\\/yqc\\/alongInfo\\/getUserAlongInfo reject-dict","^https:\\/\\/hwstore\\.kugou\\.com\\/v\\d\\/get_store_data reject-dict","^https:\\/\\/ep\\.kugou\\.com\\/v\\d\\/album_shop\\/get_entrance_info reject-dict","^https?:\\/\\/gzacshow\\.kugou\\.com\\/mfanxing-home\\/cdn\\/room\\/index\\/list_v reject-dict","^https?:\\/\\/gzacshow\\.kugou\\.com\\/mfanxing-home\\/cdn\\/room\\/index\\/list_v2 reject-dict","^https:\\/\\/jad-api\\.jin10\\.com\\/ad reject-dict","request if ${url} ~= /^https?:\\/\\/jad-api\\.jin10\\.com\\/ad/ then reject(404)","^https:\\/\\/common-open-api\\.jin10\\.com\\/configuration\\/getById\\?id=1493$ reject-dict","^https:\\/\\/search-open-api\\.jin10\\.com\\/search\\/getHotWords$ reject-dict"]
        self.base = ("#!name=Kugou-Jin10-test\n[Rule]\n[Rewrite]\n" +
                     "\n".join(self.rules) +
                     "\n[Script]\n[MITM]\nhostname = gateway.kugou.com, "
                     "gzacshow.kugou.com, jad-api.jin10.com, common-open-api.jin10.com, "
                     "search-open-api.jin10.com, creditcard.bankcomm.cn, "
                     "creditcard.bankcomm.com, creditcardapp.bankcomm.cn, "
                     "creditcardapp.bankcomm.com\n")

    def test_removes_only_redundant_https_subsets_and_unreachable_jin10_response(self):
        result = apply(self.base)
        for rule in self.rules[:14]:
            self.assertIn(rule, result)  # broad HTTP+HTTPS matcher remains
        for rule in self.rules[14:28]:
            self.assertNotIn(rule, result)  # HTTPS-only subset removed
        self.assertNotIn("^https?:\\/\\/gzacshow\\.kugou\\.com\\/mfanxing-home\\/cdn\\/room\\/index\\/list_v reject-dict", result)
        self.assertIn("^https?:\\/\\/gzacshow\\.kugou\\.com\\/mfanxing-home\\/cdn\\/room\\/index\\/list_v2 reject-dict", result)
        self.assertNotIn("^https:\\/\\/jad-api\\.jin10\\.com\\/ad reject-dict", result)
        self.assertIn("request if ${url} ~= /^https?:\\/\\/jad-api\\.jin10\\.com\\/ad/ then reject(404)", result)
        for rule in ["^https:\\/\\/common-open-api\\.jin10\\.com\\/configuration\\/getById\\?id=1493$ reject-dict","^https:\\/\\/search-open-api\\.jin10\\.com\\/search\\/getHotWords$ reject-dict"]:
            self.assertIn(rule, result)
        self.assertEqual(apply(result), result)

    def test_fails_closed_on_missing_or_drifted_inventory(self):
        missing = self.base.replace(self.rules[14] + "\n", "", 1)
        with self.assertRaisesRegex(ValueError, "Kugou/Jin10 rewrite inventory changed"):
            apply(missing)
        drifted = self.base.replace(self.rules[14], self.rules[14].replace("reject-dict", "reject-200"), 1)
        with self.assertRaisesRegex(ValueError, "Kugou/Jin10 rewrite inventory changed"):
            apply(drifted)



class PeopleAppHomepageAdDedupTests(unittest.TestCase):
    def test_removes_only_the_exact_duplicate_and_is_idempotent(self):
        from apply_local_overrides import PEOPLEAPP_HOME_AD_DUPLICATE_RULES, remove_duplicate_peopleapp_home_ad_rules
        first, duplicate = PEOPLEAPP_HOME_AD_DUPLICATE_RULES
        unrelated = r"request if ${url} ~= /^https?:\\/\\/stat\\.peopleapp\\.com\\// then reject(404)"
        result, removed = remove_duplicate_peopleapp_home_ad_rules([first, duplicate, unrelated])
        self.assertEqual(removed, 1)
        self.assertEqual(result, [first, unrelated])
        result2, removed2 = remove_duplicate_peopleapp_home_ad_rules(result)
        self.assertEqual(removed2, 0)
        self.assertEqual(result2, result)

    def test_preserves_lone_or_unknown_rules_and_fails_closed_on_duplicate(self):
        from apply_local_overrides import PEOPLEAPP_HOME_AD_DUPLICATE_RULES, remove_duplicate_peopleapp_home_ad_rules
        first, duplicate = PEOPLEAPP_HOME_AD_DUPLICATE_RULES
        self.assertEqual(remove_duplicate_peopleapp_home_ad_rules([first]), ([first], 0))
        self.assertEqual(remove_duplicate_peopleapp_home_ad_rules([duplicate]), ([duplicate], 0))
        with self.assertRaisesRegex(ValueError, "duplicate PeopleApp"):
            remove_duplicate_peopleapp_home_ad_rules([first, first, duplicate])
        drifted = duplicate.replace("reject(404)", "reject_dict(200)")
        self.assertEqual(remove_duplicate_peopleapp_home_ad_rules([first, drifted]), ([first, drifted], 0))
        unknown = r"request if \${url} ~= /^https?:\\/\\/app\\.peopleapp\\.com\\/Api\\/\\d+\\/HomeApi\\/(adv|getAdvertImage)/ then reject(403)"
        self.assertEqual(remove_duplicate_peopleapp_home_ad_rules([first, unknown]), ([first, unknown], 0))
        result, removed = remove_duplicate_peopleapp_home_ad_rules([first, duplicate, unknown])
        self.assertEqual(removed, 1)
        self.assertEqual(result, [first, unknown])



class ZhihuRequestShadowRuleCleanupTests(unittest.TestCase):
    def setUp(self):
        from apply_local_overrides import ZHIHU_REQUEST_SHADOW_PAIRS
        self.pairs = ZHIHU_REQUEST_SHADOW_PAIRS
        self.base = (
            "#!name=Zhihu-request-test\n[Rule]\n[Rewrite]\n"
            + "\n".join(item for pair in self.pairs for item in pair[:2])
            + "\n^https?:\\/\\/api\\.zhihu\\.com\\/ad reject-dict\n"
            + "[Script]\n[MITM]\nhostname = api.zhihu.com, zhuanlan.zhihu.com, "
            "zhstatic.zhihu.com, creditcard.bankcomm.cn, creditcard.bankcomm.com, "
            "creditcardapp.bankcomm.cn, creditcardapp.bankcomm.com\n"
        )

    def test_removes_only_same_action_https_subsets_and_is_idempotent(self):
        result = apply(self.base)
        for redundant, canonical, _marker in self.pairs:
            self.assertNotIn(redundant, result)
            self.assertEqual(result.count(canonical), 1)
        self.assertIn("ad reject-dict", result)
        self.assertEqual(apply(result), result)

    def test_preserves_missing_cover_and_unknown_but_rejects_duplicates(self):
        from apply_local_overrides import remove_redundant_zhihu_request_rules
        redundant, canonical, _marker = self.pairs[0]
        preserved, removed = remove_redundant_zhihu_request_rules([redundant])
        self.assertEqual(removed, 0)
        self.assertEqual(preserved, [redundant])

        with self.assertRaisesRegex(ValueError, "duplicate Zhihu request blocker"):
            remove_redundant_zhihu_request_rules([redundant, redundant])

        drifted_line = redundant.replace("reject(404)", "reject_dict(200)")
        preserved, _ = remove_redundant_zhihu_request_rules([drifted_line])
        self.assertEqual(preserved, [drifted_line])

        unknown_line = redundant.replace("reject(404)", "reject(403)")
        preserved, removed = remove_redundant_zhihu_request_rules([redundant, canonical, unknown_line])
        self.assertEqual(removed, 1)
        self.assertIn(canonical, preserved)
        self.assertIn(unknown_line, preserved)


class ZhihuMultiActionRewriteConsolidationTests(unittest.TestCase):
    def setUp(self):
        from apply_local_overrides import (
            ZHIHU_ANSWER_DELETE_REWRITE,
            ZHIHU_ANSWER_CARD_REWRITE,
            ZHIHU_ANSWER_COMBINED_REWRITE,
            ZHIHU_TOPSTORY_COMPONENTS_REWRITE,
            ZHIHU_TOPSTORY_RING_REWRITE,
            ZHIHU_TOPSTORY_COMBINED_REWRITE,
        )
        self.original = (
            ZHIHU_ANSWER_DELETE_REWRITE,
            ZHIHU_ANSWER_CARD_REWRITE,
            ZHIHU_TOPSTORY_COMPONENTS_REWRITE,
            ZHIHU_TOPSTORY_RING_REWRITE,
        )
        self.combined = (
            ZHIHU_ANSWER_COMBINED_REWRITE,
            ZHIHU_TOPSTORY_COMBINED_REWRITE,
        )
        self.base = (
            "#!name=Zhihu-test\n[Rule]\n[Rewrite]\n"
            "^https:\\/\\/api\\.zhihu\\.com\\/commercial_api\\/ reject-dict\n"
            + "\n".join(self.original)
            + "\n[Script]\n[MITM]\nhostname = api.zhihu.com, page-info.zhihu.com, "
            "creditcard.bankcomm.cn, creditcard.bankcomm.com, "
            "creditcardapp.bankcomm.cn, creditcardapp.bankcomm.com\n"
        )

    def test_coalesces_exact_zhihu_operations_without_changing_matchers_or_other_rules(self):
        result = apply(self.base)
        for rule in self.original:
            self.assertNotIn(rule, result)
        for rule in self.combined:
            self.assertEqual(result.count(rule), 1)
            self.assertIn(rule, result)
        self.assertIn("commercial_api", result)
        self.assertEqual(apply(result), result)

    def test_fails_closed_on_missing_drifted_duplicate_or_unknown_same_matcher_rule(self):
        missing = self.base.replace(self.original[0] + "\n", "", 1)
        with self.assertRaisesRegex(ValueError, "Zhihu multi-action rewrite inventory changed"):
            apply(missing)

        drifted = self.base.replace(self.original[1], self.original[1].replace('!= "card"', '!= "ad"'), 1)
        with self.assertRaisesRegex(ValueError, "Zhihu multi-action rewrite inventory changed"):
            apply(drifted)

        duplicate = self.base.replace(self.original[0], self.original[0] + "\n" + self.original[0], 1)
        with self.assertRaisesRegex(ValueError, "Zhihu multi-action rewrite inventory changed"):
            apply(duplicate)

        unknown = self.base.replace(
            self.original[0],
            self.original[0] + "\n" +
            r"^https:\/\/(api|page-info)(?:\.zhihu)?\.com\/answers\/v\d\/\d+(?:\?.*)?$ response-body-json-jq '.new_field |= empty'",
            1,
        )
        with self.assertRaisesRegex(ValueError, "Zhihu same-matcher response rewrite changed"):
            apply(unknown)






class RRTVNativeAdRewriteTests(unittest.TestCase):
    def setUp(self):
        from apply_local_overrides import (
            RRTV_SOURCE_TRIGGERS,
            RRTV_NON_AD_SOURCE_TRIGGERS,
            RRTV_HOME_AD_SOURCE_TRIGGER,
            RRTV_GETALL_AD_SOURCE_TRIGGER,
            RRTV_HOME_NATIVE_REWRITE,
            RRTV_GETALL_NATIVE_REWRITE,
        )
        self.source = RRTV_SOURCE_TRIGGERS
        self.non_ad = RRTV_NON_AD_SOURCE_TRIGGERS
        self.ad_source = (RRTV_HOME_AD_SOURCE_TRIGGER, RRTV_GETALL_AD_SOURCE_TRIGGER)
        self.native = (RRTV_HOME_NATIVE_REWRITE, RRTV_GETALL_NATIVE_REWRITE)
        self.base = (
            "#!name=rrtv-native-test\n[Argument]\nrfrfuipk_enable = switch,true,false,tag=RRTV\n"
            "[Rewrite]\n^https:\\/\\/unrelated\\.example\\/keep reject\n"
            "[Script]\n" + "\n".join(self.source) +
            "\nresponse if ${url} ~= /^https:\\/\\/example\\.com\\/keep/ then script(\"keep.js\")\n"
            "[MITM]\nhostname = api.rr.tv, example.com, creditcard.bankcomm.cn, creditcard.bankcomm.com, "
            "creditcardapp.bankcomm.cn, creditcardapp.bankcomm.com\n"
        )

    def test_replaces_only_two_ad_triggers_with_native_rewrites(self):
        result = apply(self.base)
        for source in self.source:
            self.assertNotIn(source, result)
        for rule in self.native:
            self.assertEqual(result.count(rule), 1)
            self.assertIn("${rfrfuipk_enable} == true", rule)
            self.assertIn("response.json.jq", rule)
            self.assertIn("try", rule)
            self.assertIn("catch $original", rule)
        for source in self.non_ad:
            self.assertNotIn(source, result)
        self.assertIn("rfrfuipk_enable = switch,true,false,tag=RRTV", result)
        self.assertIn('script("keep.js")', result)
        self.assertIn("^https:\\/\\/unrelated\\.example\\/keep reject", result)
        self.assertEqual(apply(result), result)

    def test_current_blockads_plugin_source_variants_are_replaced(self):
        from apply_local_overrides import RRTV_BLOCKADS_SOURCE_TRIGGERS
        current_base = (
            "#!name=rrtv-current-blockads-test\n[Argument]\nrfrfuipk_enable = switch,true,false,tag=RRTV\n"
            "[Rewrite]\n[Script]\n" + "\n".join(RRTV_BLOCKADS_SOURCE_TRIGGERS) +
            "\n[MITM]\nhostname = api.rr.tv, creditcard.bankcomm.cn, creditcard.bankcomm.com, "
            "creditcardapp.bankcomm.cn, creditcardapp.bankcomm.com\n"
        )
        result = apply(current_base)
        self.assertNotIn("rrtv_json.js", result)
        for rule in self.native:
            self.assertEqual(result.count(rule), 1)
        self.assertEqual(apply(result), result)

    def test_raw_upstream_source_variants_are_also_replaced(self):
        from apply_local_overrides import RRTV_RAW_SOURCE_TRIGGERS
        raw_base = (
            "#!name=rrtv-raw-native-test\n[Argument]\nrfrfuipk_enable = switch,true,false,tag=RRTV\n"
            "[Rewrite]\n[Script]\n" + "\n".join(RRTV_RAW_SOURCE_TRIGGERS) +
            "\n[MITM]\nhostname = api.rr.tv, creditcard.bankcomm.cn, creditcard.bankcomm.com, "
            "creditcardapp.bankcomm.cn, creditcardapp.bankcomm.com\n"
        )
        result = apply(raw_base)
        self.assertNotIn("rrtv_json.js", result)
        for rule in self.native:
            self.assertEqual(result.count(rule), 1)
        self.assertEqual(apply(result), result)

    def test_allows_independently_missing_source_triggers(self):
        partial = self.base.replace(self.non_ad[0] + "\n", "", 1)
        result = apply(partial)
        self.assertEqual(result.count(self.native[0]), 1)
        self.assertEqual(result.count(self.native[1]), 1)
        self.assertEqual(apply(result), result)

        no_home = self.base.replace(self.ad_source[0] + "\n", "", 1)
        no_home_result = apply(no_home)
        self.assertEqual(no_home_result.count(self.native[0]), 0)
        self.assertEqual(no_home_result.count(self.native[1]), 1)

    def test_fails_closed_on_duplicates_mixed_state_and_unknown_matchers(self):
        duplicate = self.base.replace(self.source[0], self.source[0] + "\n" + self.source[0], 1)
        with self.assertRaisesRegex(ValueError, "duplicate RRTV response script trigger"):
            apply(duplicate)

        mixed = self.base.replace("[Script]", self.native[0] + "\n[Script]", 1)
        with self.assertRaisesRegex(ValueError, "mixed RRTV script/native rule state"):
            apply(mixed)

        unknown_script = self.base.replace(
            self.source[0],
            self.source[0] + "\n" +
            r"""response if ${url} ~= /^https:\/\/api\.rr\.tv\/unknown/i then script("rrtv_json.js") with enable=rfrfuipk_enable, requires_body=true""",
            1,
        )
        with self.assertRaisesRegex(ValueError, "unknown RRTV script matcher"):
            apply(unknown_script)

        unknown_rewrite = self.base.replace(
            "[Script]",
            r"""response if ${url} ~= /^https:\/\/api\.rr\.tv\/ad\/getAll/i then response.json.delete("data.unreviewed")""" + "\n[Script]",
            1,
        )
        with self.assertRaisesRegex(ValueError, "unknown RRTV native JSON action"):
            apply(unknown_rewrite)

    def test_checked_in_plugin_snapshot_applies_to_native_ad_only_rules(self):
        from pathlib import Path
        plugin = Path(__file__).with_name("allAdRewrite.plugin").read_text(encoding="utf-8")
        result = apply(plugin)
        self.assertNotIn("rrtv_json.js", result)
        for rule in self.native:
            self.assertEqual(result.count(rule), 1)


class ResponseJsonDeleteBatchTests(unittest.TestCase):
    def setUp(self):
        from apply_local_overrides import (
            KUAISHOU_STARTUP_SPLIT_DELETE_REWRITE,
            KUAISHOU_STARTUP_BATCHED_DELETE_REWRITE,
            XIMALAYA_FOOTBALL_SPLIT_DELETE_REWRITE,
            XIMALAYA_FOOTBALL_BATCHED_DELETE_REWRITE,
            XIMALAYA_PLAYPAGE_SPLIT_DELETE_REWRITE,
            XIMALAYA_PLAYPAGE_BATCHED_DELETE_REWRITE,
        )
        self.original = (
            KUAISHOU_STARTUP_SPLIT_DELETE_REWRITE,
            XIMALAYA_FOOTBALL_SPLIT_DELETE_REWRITE,
            XIMALAYA_PLAYPAGE_SPLIT_DELETE_REWRITE,
        )
        self.batched = (
            KUAISHOU_STARTUP_BATCHED_DELETE_REWRITE,
            XIMALAYA_FOOTBALL_BATCHED_DELETE_REWRITE,
            XIMALAYA_PLAYPAGE_BATCHED_DELETE_REWRITE,
        )
        self.base = (
            "#!name=response-delete-batch-test\n[Rule]\n[Rewrite]\n"
            + "\n".join(self.original)
            + "\n^https:\\/\\/unrelated\\.example\\/keep reject\n"
            + "[Script]\n[MITM]\nhostname = apissl.gifshow.com, mobile.ximalaya.com, "
            "mobwsa.ximalaya.com, unrelated.example, creditcard.bankcomm.cn, creditcard.bankcomm.com, "
            "creditcardapp.bankcomm.cn, creditcardapp.bankcomm.com\n"
        )

    def test_batches_only_the_exact_delete_operations_and_is_idempotent(self):
        result = apply(self.base)
        for rule in self.original:
            self.assertNotIn(rule, result)
        for rule in self.batched:
            self.assertEqual(result.count(rule), 1)
        self.assertIn("^https:\\/\\/unrelated\\.example\\/keep reject", result)
        self.assertEqual(apply(result), result)

    def test_allows_partial_upstream_output_but_rejects_duplicate_batched_output(self):
        result = apply(self.base)
        duplicate = result.replace(self.batched[0], self.batched[0] + "\n" + self.batched[0], 1)
        with self.assertRaisesRegex(ValueError, "Response JSON delete batch inventory changed"):
            apply(duplicate)

        partial = result.replace(self.batched[1] + "\n", "", 1)
        partial_result = apply(partial)
        self.assertEqual(partial_result.count(self.batched[0]), 1)
        self.assertEqual(partial_result.count(self.batched[1]), 0)
        self.assertEqual(partial_result.count(self.batched[2]), 1)
        self.assertEqual(apply(partial_result), partial_result)

    def test_allows_missing_source_group_but_fails_closed_on_duplicate_or_drift(self):
        missing = self.base.replace(self.original[0] + "\n", "", 1)
        missing_result = apply(missing)
        self.assertEqual(missing_result.count(self.batched[0]), 0)
        self.assertEqual(missing_result.count(self.batched[1]), 1)
        self.assertEqual(missing_result.count(self.batched[2]), 1)

        duplicate = self.base.replace(self.original[1], self.original[1] + "\n" + self.original[1], 1)
        with self.assertRaisesRegex(ValueError, "Response JSON delete batch inventory changed"):
            apply(duplicate)

        drifted_rule = self.original[2].replace("defaultResource", "default_resource")
        drifted = self.base.replace(self.original[2], drifted_rule, 1)
        drifted_result = apply(drifted)
        self.assertIn(drifted_rule, drifted_result)
        self.assertNotIn(self.batched[2], drifted_result)
        self.assertEqual(drifted_result.count(self.batched[0]), 1)
        self.assertEqual(drifted_result.count(self.batched[1]), 1)

    def test_fails_closed_on_unknown_same_matcher_response_action(self):
        unknown = self.base.replace(
            self.original[0],
            self.original[0] + "\n" +
            r"""response if ${url} ~= /^https:\/\/(apissl|az2-api(-js|-idc)?)\.(gifshow|ksapisrv)\.com\/rest\/system\/startup\?/ then response.json.delete("newAdField")""",
            1,
        )
        with self.assertRaisesRegex(ValueError, "Same-matcher response JSON delete changed"):
            apply(unknown)


class XimalayaHomepageJsonConsolidationTests(unittest.TestCase):
    def setUp(self):
        from apply_local_overrides import (
            XIMALAYA_HOME_DELETE_REWRITE,
            XIMALAYA_HOME_ENTRANCE_REWRITE,
            XIMALAYA_HOME_COMBINED_REWRITE,
        )
        self.original = (XIMALAYA_HOME_DELETE_REWRITE, XIMALAYA_HOME_ENTRANCE_REWRITE)
        self.combined = XIMALAYA_HOME_COMBINED_REWRITE
        self.base = (
            "#!name=Ximalaya-test\n[Rule]\n[Rewrite]\n"
            + "\n".join(self.original)
            + "\n[Script]\n[MITM]\nhostname = mobile.ximalaya.com, "
            "mobilehera.ximalaya.com, mobwsa.ximalaya.com, "
            "creditcard.bankcomm.cn, creditcard.bankcomm.com, "
            "creditcardapp.bankcomm.cn, creditcardapp.bankcomm.com\n"
        )

    def test_combines_exact_homepage_transforms_and_preserves_other_sections(self):
        result = apply(self.base)
        for rule in self.original:
            self.assertNotIn(rule, result)
        self.assertEqual(result.count(self.combined), 1)
        self.assertIn(self.combined, result)
        self.assertIn("[Rule]", result)
        self.assertIn("[Script]", result)
        self.assertIn("creditcard.bankcomm.cn", result)
        self.assertEqual(apply(result), result)

    def test_fails_closed_on_missing_duplicate_drift_or_unknown_homepage_action(self):
        missing = self.base.replace(self.original[0] + "\n", "", 1)
        with self.assertRaisesRegex(ValueError, "Ximalaya homepage rewrite inventory changed"):
            apply(missing)

        drifted = self.base.replace(self.original[1], self.original[1].replace("全部服务", "VIP"), 1)
        with self.assertRaisesRegex(ValueError, "Ximalaya homepage rewrite inventory changed"):
            apply(drifted)

        duplicate = self.base.replace(self.original[0], self.original[0] + "\n" + self.original[0], 1)
        with self.assertRaisesRegex(ValueError, "Ximalaya homepage rewrite inventory changed"):
            apply(duplicate)

        unknown = self.base.replace(
            self.original[0],
            self.original[0] + "\n" +
            r"""response if ${url} ~= /^https:\/\/(mobile|mobilehera|mobwsa)\.ximalaya\.com\/mobile-user\/v\d\/homePage\// then response.json.jq(\`.newField = null\`)""",
            1,
        )
        with self.assertRaisesRegex(ValueError, "Ximalaya homepage response rewrite changed"):
            apply(unknown)






class WeChatUnblockScriptConsolidationTests(unittest.TestCase):
    def test_removes_only_exact_zpiglet_duplicate_and_preserves_rucu6_variant(self):
        from apply_local_overrides import (
            WECHAT_UNBLOCK_URL_CANONICAL_TRIGGER,
            WECHAT_UNBLOCK_URL_REDUNDANT_TRIGGER,
            WECHAT_UNBLOCK_URL_DISTINCT_TRIGGER,
            consolidate_wechat_unblock_url_scripts,
        )
        unrelated = 'response if ${url} ~= /^https:\\/\\/example\\.com/ then script("https://example.invalid/keep.js")'
        fixture = ["[Script]", WECHAT_UNBLOCK_URL_REDUNDANT_TRIGGER,
                   WECHAT_UNBLOCK_URL_CANONICAL_TRIGGER, WECHAT_UNBLOCK_URL_DISTINCT_TRIGGER,
                   unrelated, "[MITM]"]
        result, removed = consolidate_wechat_unblock_url_scripts(fixture)
        self.assertEqual(removed, 1)
        self.assertNotIn(WECHAT_UNBLOCK_URL_REDUNDANT_TRIGGER, result)
        self.assertEqual(result.count(WECHAT_UNBLOCK_URL_CANONICAL_TRIGGER), 1)
        self.assertEqual(result.count(WECHAT_UNBLOCK_URL_DISTINCT_TRIGGER), 1)
        self.assertIn(unrelated, result)
        result2, removed2 = consolidate_wechat_unblock_url_scripts(result)
        self.assertEqual((result2, removed2), (result, 0))

    def test_removes_exact_duplicate_with_loon_variable_interpolation(self):
        from apply_local_overrides import (
            WECHAT_UNBLOCK_URL_CANONICAL_TRIGGER,
            WECHAT_UNBLOCK_URL_REDUNDANT_TRIGGER,
            WECHAT_UNBLOCK_URL_DISTINCT_TRIGGER,
            consolidate_wechat_unblock_url_scripts,
        )
        interpolated = WECHAT_UNBLOCK_URL_REDUNDANT_TRIGGER.replace(
            "enable=lmjpxmvi_enable", "enable=${lmjpxmvi_enable}"
        )
        fixture = ["[Script]", WECHAT_UNBLOCK_URL_CANONICAL_TRIGGER,
                   interpolated, WECHAT_UNBLOCK_URL_DISTINCT_TRIGGER]
        result, removed = consolidate_wechat_unblock_url_scripts(fixture)
        self.assertEqual(removed, 1)
        self.assertNotIn(interpolated, result)
        self.assertIn(WECHAT_UNBLOCK_URL_CANONICAL_TRIGGER, result)
        self.assertIn(WECHAT_UNBLOCK_URL_DISTINCT_TRIGGER, result)

    def test_preserves_already_consolidated_or_absent_inventory(self):
        from apply_local_overrides import (
            WECHAT_UNBLOCK_URL_CANONICAL_TRIGGER,
            WECHAT_UNBLOCK_URL_DISTINCT_TRIGGER,
            consolidate_wechat_unblock_url_scripts,
        )
        clean = ["[Script]", WECHAT_UNBLOCK_URL_CANONICAL_TRIGGER,
                 WECHAT_UNBLOCK_URL_DISTINCT_TRIGGER]
        self.assertEqual(consolidate_wechat_unblock_url_scripts(clean), (clean, 0))
        absent = ["[Script]", "[MITM]"]
        self.assertEqual(consolidate_wechat_unblock_url_scripts(absent), (absent, 0))

    def test_fails_closed_on_duplicates_missing_or_drifted_triggers(self):
        from apply_local_overrides import (
            WECHAT_UNBLOCK_URL_CANONICAL_TRIGGER,
            WECHAT_UNBLOCK_URL_REDUNDANT_TRIGGER,
            WECHAT_UNBLOCK_URL_DISTINCT_TRIGGER,
            consolidate_wechat_unblock_url_scripts,
        )
        with self.assertRaisesRegex(ValueError, "duplicate WeChat"):
            consolidate_wechat_unblock_url_scripts(
                ["[Script]", WECHAT_UNBLOCK_URL_CANONICAL_TRIGGER,
                 WECHAT_UNBLOCK_URL_CANONICAL_TRIGGER]
            )
        with self.assertRaisesRegex(ValueError, "inventory incomplete"):
            consolidate_wechat_unblock_url_scripts(
                ["[Script]", WECHAT_UNBLOCK_URL_CANONICAL_TRIGGER,
                 WECHAT_UNBLOCK_URL_REDUNDANT_TRIGGER]
            )
        drifted = WECHAT_UNBLOCK_URL_REDUNDANT_TRIGGER.replace("requires_body=true", "requires_body=false")
        with self.assertRaisesRegex(ValueError, "trigger changed"):
            consolidate_wechat_unblock_url_scripts(
                ["[Script]", WECHAT_UNBLOCK_URL_CANONICAL_TRIGGER,
                 WECHAT_UNBLOCK_URL_DISTINCT_TRIGGER, drifted]
            )



class JingdongCoreServiceDomainScopeTests(unittest.TestCase):
    def setUp(self):
        from apply_local_overrides import JD_CORE_SERVICE_BLOCKS
        self.targets = list(JD_CORE_SERVICE_BLOCKS.values())
        self.base = ["[Rule]", *self.targets, "DOMAIN,unrelated.example,REJECT",
                     "[Rewrite]", "^https://example.com/ad reject", "[MITM]"]

    def test_removes_only_three_known_core_service_host_blocks_and_is_idempotent(self):
        from apply_local_overrides import remove_jd_core_service_domain_blocks
        result, removed = remove_jd_core_service_domain_blocks(self.base)
        self.assertEqual(removed, 3)
        for rule in self.targets:
            self.assertNotIn(rule, result)
        self.assertIn("DOMAIN,unrelated.example,REJECT", result)
        self.assertIn("^https://example.com/ad reject", result)
        self.assertEqual(remove_jd_core_service_domain_blocks(result), (result, 0))

    def test_fails_closed_on_partial_duplicate_or_changed_core_service_inventory(self):
        from apply_local_overrides import remove_jd_core_service_domain_blocks
        with self.assertRaisesRegex(ValueError, "inventory is partial"):
            remove_jd_core_service_domain_blocks(["[Rule]", *self.targets[:-1]])
        duplicate = ["[Rule]", *self.targets, self.targets[0]]
        with self.assertRaisesRegex(ValueError, "duplicate JD core service"):
            remove_jd_core_service_domain_blocks(duplicate)
        drifted = [line.replace(",REJECT", ",DIRECT") if line == self.targets[0] else line for line in self.base]
        with self.assertRaisesRegex(ValueError, "rule changed"):
            remove_jd_core_service_domain_blocks(drifted)

    def test_preserves_distinct_jd_domain_keyword_rule_while_removing_exact_host_overblocks(self):
        from apply_local_overrides import remove_jd_core_service_domain_blocks
        keyword_rule = "DOMAIN-KEYWORD,mapi.m.jd.com,REJECT"
        result, removed = remove_jd_core_service_domain_blocks(
            ["[Rule]", *self.targets, keyword_rule, "DOMAIN,unrelated.example,REJECT"]
        )
        self.assertEqual(removed, 3)
        self.assertIn(keyword_rule, result)
        self.assertIn("DOMAIN,unrelated.example,REJECT", result)
        self.assertEqual(remove_jd_core_service_domain_blocks(result), (result, 0))

    def test_checked_in_plugin_snapshot_does_not_block_core_jd_hosts(self):
        from pathlib import Path
        from apply_local_overrides import JD_CORE_SERVICE_BLOCKS
        plugin = Path(__file__).with_name("allAdRewrite.plugin").read_text(encoding="utf-8")
        for rule in JD_CORE_SERVICE_BLOCKS.values():
            self.assertNotIn(rule, plugin)

class PinduoduoImageCdnScopeTests(unittest.TestCase):
    def setUp(self):
        from apply_local_overrides import PDD_IMAGE_CDN_BROAD_BLOCK, PDD_IMAGE_CDN_AD_PATH_RULES
        self.broad = PDD_IMAGE_CDN_BROAD_BLOCK
        self.paths = list(PDD_IMAGE_CDN_AD_PATH_RULES)
        self.base = [
            "[Rule]", self.broad, "DOMAIN,unrelated.example,REJECT",
            "[Rewrite]", *self.paths, "[Script]",
            "[MITM]", "hostname = images.pinduoduo.com, api.pinduoduo.com",
        ]

    def test_checked_in_plugin_snapshot_keeps_product_image_cdn_and_only_ad_path_blocks(self):
        from pathlib import Path
        from apply_local_overrides import (
            PDD_IMAGE_CDN_HOST, PDD_IMAGE_CDN_BROAD_BLOCK, PDD_IMAGE_CDN_AD_PATH_RULES,
        )
        plugin = Path(__file__).with_name("allAdRewrite.plugin").read_text(encoding="utf-8")
        self.assertNotIn(PDD_IMAGE_CDN_BROAD_BLOCK, plugin)
        self.assertNotIn("DOMAIN-SUFFIX," + PDD_IMAGE_CDN_HOST + ",REJECT", plugin)
        self.assertNotIn("DOMAIN-KEYWORD," + PDD_IMAGE_CDN_HOST + ",REJECT", plugin)
        path_counts = [plugin.count(rule) for rule in PDD_IMAGE_CDN_AD_PATH_RULES]
        self.assertIn(path_counts, ([0, 0], [1, 1]))
        mitm = plugin.split("[MITM]", 1)[1]
        self.assertIn(PDD_IMAGE_CDN_HOST, mitm)

    def test_mitm_only_image_cdn_host_without_broad_rule_is_a_noop(self):
        from apply_local_overrides import scope_pdd_image_cdn_ad_rules
        fixture = ["[Rewrite]", "[MITM]", "hostname = images.pinduoduo.com"]
        result, removed = scope_pdd_image_cdn_ad_rules(fixture)
        self.assertEqual((result, removed), (fixture, 0))

    def test_partial_ad_path_inventory_without_broad_reject_is_a_noop(self):
        from apply_local_overrides import PDD_IMAGE_CDN_AD_PATH_RULES, scope_pdd_image_cdn_ad_rules
        fixture = ["[Rewrite]", PDD_IMAGE_CDN_AD_PATH_RULES[0], "[MITM]", "hostname = images.pinduoduo.com"]
        result, removed = scope_pdd_image_cdn_ad_rules(fixture)
        self.assertEqual((result, removed), (fixture, 0))

    def test_removes_only_broad_image_cdn_block_and_keeps_ad_paths_and_mitm(self):
        from apply_local_overrides import scope_pdd_image_cdn_ad_rules
        result, removed = scope_pdd_image_cdn_ad_rules(self.base)
        self.assertEqual(removed, 1)
        rule_section = result[result.index("[Rule]") + 1:result.index("[Rewrite]")]
        self.assertNotIn(self.broad, rule_section)
        self.assertIn("DOMAIN,unrelated.example,REJECT", rule_section)
        for rule in self.paths:
            self.assertEqual(result.count(rule), 1)
        self.assertIn("images.pinduoduo.com", result[result.index("[MITM]") + 1])
        result2, removed2 = scope_pdd_image_cdn_ad_rules(result)
        self.assertEqual((result2, removed2), (result, 0))

    def test_missing_scoped_rule_is_restored_from_reviewed_upstream_pair(self):
        from apply_local_overrides import scope_pdd_image_cdn_ad_rules
        missing_path = [line for line in self.base if line != self.paths[0]]
        result, removed = scope_pdd_image_cdn_ad_rules(missing_path)
        self.assertEqual(removed, 1)
        for rule in self.paths:
            self.assertIn(rule, result)
        self.assertNotIn(self.broad, result)

    def test_requires_existing_mitm_before_removing_broad_block(self):
        from apply_local_overrides import scope_pdd_image_cdn_ad_rules
        missing_mitm = [line.replace("images.pinduoduo.com, ", "") for line in self.base]
        with self.assertRaisesRegex(ValueError, "requires its existing MITM"):
            scope_pdd_image_cdn_ad_rules(missing_mitm)

    def test_rejects_unknown_pdd_image_rewrite_when_broad_block_exists(self):
        from apply_local_overrides import scope_pdd_image_cdn_ad_rules
        unknown = r"request if ${url} ~= /^https?:\/\/images\.pinduoduo\.com\/unknown-ad\// then reject(200)"
        fixture = ["[Rule]", self.broad, "[Rewrite]", *self.paths, unknown,
                   "[MITM]", "hostname = images.pinduoduo.com"]
        with self.assertRaisesRegex(ValueError, "ad-path Rewrite inventory changed"):
            scope_pdd_image_cdn_ad_rules(fixture)

    def test_rejects_duplicate_or_changed_host_wide_domain_rules(self):
        from apply_local_overrides import scope_pdd_image_cdn_ad_rules
        duplicate = ["[Rule]", self.broad, self.broad, "[Rewrite]", *self.paths,
                    "[MITM]", "hostname = images.pinduoduo.com"]
        with self.assertRaisesRegex(ValueError, "duplicate PDD images CDN broad"):
            scope_pdd_image_cdn_ad_rules(duplicate)
        variant = [line.replace(self.broad, "DOMAIN-SUFFIX,images.pinduoduo.com,REJECT") for line in self.base]
        with self.assertRaisesRegex(ValueError, "domain rule changed"):
            scope_pdd_image_cdn_ad_rules(variant)

class PinduoduoOrderEndpointSafetyTests(unittest.TestCase):
    def setUp(self):
        from apply_local_overrides import PDD_ORDER_ENDPOINT_BLOCKS_TO_PRESERVE
        self.targets = PDD_ORDER_ENDPOINT_BLOCKS_TO_PRESERVE
        self.recommendation = (
            r"^https?:\\/\\/api\\.pinduoduo\\.com\\/api\\/caterham\\/v3\\/query\\/my_order_group reject-dict"
        )
        self.shipping_cleanup = (
            r"response if ${url} ~= /^https:\\/\\/api\\.pinduoduo\\.com\\/order\\//i "
            r"then response.json.delete([\"marketing_banner_vo\", \"shipping.banner_above_recommend\"])"
        )
        self.order_growth_cleanup = (
            r"response if ${url} ~= /^https:\\/\\/api\\.pinduoduo\\.com\\/api\\/aristotle\\/order_list_v4\\?/i "
            r"then response.json.jq(\".orders |= map(.order_buttons |= map(del(.order_growth_tip)))\")"
        )

    def test_removes_known_order_request_variants_and_preserves_ad_field_cleanup(self):
        from apply_local_overrides import remove_pdd_order_endpoint_blocks
        fixture = ["[Rewrite]", *self.targets, self.recommendation,
                   self.shipping_cleanup, self.order_growth_cleanup, "[Script]"]
        result, removed = remove_pdd_order_endpoint_blocks(fixture)
        self.assertEqual(removed, len(self.targets))
        for item in self.targets:
            self.assertNotIn(item, result)
        self.assertIn(self.recommendation, result)
        self.assertIn(self.shipping_cleanup, result)
        self.assertIn(self.order_growth_cleanup, result)
        result2, removed2 = remove_pdd_order_endpoint_blocks(result)
        self.assertEqual((result2, removed2), (result, 0))

    def test_allows_upstream_pruning_and_duplicate_known_order_rules_but_rejects_drift(self):
        from apply_local_overrides import remove_pdd_order_endpoint_blocks
        missing = ["[Rewrite]", *self.targets[:-1]]
        result, removed = remove_pdd_order_endpoint_blocks(missing)
        self.assertEqual(removed, len(self.targets) - 1)
        self.assertEqual(result, ["[Rewrite]"])

        duplicate = ["[Rewrite]", *self.targets, self.targets[0]]
        result, removed = remove_pdd_order_endpoint_blocks(duplicate)
        self.assertEqual(removed, len(self.targets) + 1)
        self.assertEqual(result, ["[Rewrite]"])

        drifted = self.targets[0].replace("reject_dict(200)", "reject(404)")
        with self.assertRaisesRegex(ValueError, "rule changed"):
            remove_pdd_order_endpoint_blocks(["[Rewrite]", *self.targets[1:], drifted])


class TuhuDuplicateResponseScriptTests(unittest.TestCase):
    def setUp(self):
        from apply_local_overrides import (
            TUHU_SCRIPT_CANONICAL_TRIGGERS, TUHU_SCRIPT_LEGACY_TRIGGERS,
        )
        self.canonical = TUHU_SCRIPT_CANONICAL_TRIGGERS
        self.legacy = TUHU_SCRIPT_LEGACY_TRIGGERS
        self.unrelated = r'response if ${url} ~= /^https?:\\/\\/example\\.com\\/api/ then script("https://example.invalid/keep.js")'
        self.fixture = [
            "[Script]", *self.legacy, *self.canonical, self.unrelated,
            "[Rewrite]", "^https?:\\\\/\\\\/gateway\\\\.tuhu\\\\.cn\\\\/unrelated reject(404)",
            "[MITM]", "hostname = gateway.tuhu.cn, unrelated.example",
        ]

    def test_removes_three_duplicate_legacy_triggers_and_keeps_case_insensitive_canonical(self):
        from apply_local_overrides import remove_duplicate_tuhu_scripts
        result, removed = remove_duplicate_tuhu_scripts(self.fixture)
        self.assertEqual(removed, 3)
        for item in self.legacy:
            self.assertNotIn(item, result)
        for item in self.canonical:
            self.assertEqual(result.count(item), 1)
        self.assertIn(self.unrelated, result)
        self.assertIn("^https?:\\\\/\\\\/gateway\\\\.tuhu\\\\.cn\\\\/unrelated reject(404)", result)
        self.assertEqual(remove_duplicate_tuhu_scripts(result), (result, 0))

    def test_preserves_already_consolidated_inventory(self):
        from apply_local_overrides import remove_duplicate_tuhu_scripts
        clean = ["[Script]", *self.canonical, "[MITM]"]
        self.assertEqual(remove_duplicate_tuhu_scripts(clean), (clean, 0))

    def test_fails_closed_on_missing_canonical_duplicate_or_unknown_variant(self):
        from apply_local_overrides import remove_duplicate_tuhu_scripts
        missing = [line for line in self.fixture if line != self.canonical[1]]
        with self.assertRaisesRegex(ValueError, "canonical script inventory incomplete"):
            remove_duplicate_tuhu_scripts(missing)

        duplicate = ["[Script]", *self.canonical, self.canonical[0]]
        with self.assertRaisesRegex(ValueError, "duplicate canonical Tuhu"):
            remove_duplicate_tuhu_scripts(duplicate)

        drifted = self.canonical[0].replace("getCmsModuleList", "changedEndpoint")
        with self.assertRaisesRegex(ValueError, "inventory changed"):
            remove_duplicate_tuhu_scripts(["[Script]", *self.canonical[1:], drifted])

    def test_checked_in_plugin_snapshot_has_only_the_three_canonical_triggers(self):
        from pathlib import Path
        from apply_local_overrides import TUHU_SCRIPT_CANONICAL_TRIGGERS, TUHU_SCRIPT_LEGACY_TRIGGERS
        plugin = Path(__file__).with_name("allAdRewrite.plugin").read_text(encoding="utf-8")
        for item in TUHU_SCRIPT_LEGACY_TRIGGERS:
            self.assertNotIn(item, plugin)
        for item in TUHU_SCRIPT_CANONICAL_TRIGGERS:
            self.assertEqual(plugin.count(item), 1)


class CnftpDuplicateScriptTests(unittest.TestCase):
    def setUp(self):
        from apply_local_overrides import (
            CNFTP_DUPLICATE_KEEP_SOURCE_TRIGGERS,
            CNFTP_DUPLICATE_KEEP_TRIGGERS,
            CNFTP_DUPLICATE_REMOVE_TRIGGERS,
        )
        self.keep_source = CNFTP_DUPLICATE_KEEP_SOURCE_TRIGGERS
        self.keep = CNFTP_DUPLICATE_KEEP_TRIGGERS
        self.remove = CNFTP_DUPLICATE_REMOVE_TRIGGERS
        self.unrelated = 'response if ${url} ~= /^https?:\\/\\/example\\.com\\/api/ then script("https://example.invalid/keep.js")'
        self.fixture = [
            "[Script]", *self.remove, *self.keep_source, self.unrelated,
            "[Rewrite]", "^https?:\\\\/\\\\/api.iqiyi.com\\\\/unrelated reject(404)",
            "[MITM]", "hostname = cards.iqiyi.com, me.bz.mgtv.com, acs.youku.com",
        ]

    def test_removes_26_duplicates_and_keeps_26_single_processing_handlers(self):
        from apply_local_overrides import remove_duplicate_cnftp_scripts
        result, removed = remove_duplicate_cnftp_scripts(self.fixture)
        self.assertEqual(removed, 26)
        for item in self.remove:
            self.assertNotIn(item, result)
        for item in self.keep_source:
            if item not in self.keep:
                self.assertNotIn(item, result)
        for item in self.keep:
            self.assertEqual(result.count(item), 1)
        self.assertIn(self.unrelated, result)
        self.assertIn("^https?:\\\\/\\\\/api.iqiyi.com\\\\/unrelated reject(404)", result)
        self.assertEqual(remove_duplicate_cnftp_scripts(result), (result, 0))

    def test_preserves_already_consolidated_inventory(self):
        from apply_local_overrides import remove_duplicate_cnftp_scripts
        clean = ["[Script]", *self.keep, "[MITM]"]
        self.assertEqual(remove_duplicate_cnftp_scripts(clean), (clean, 0))

    def test_preserves_final_inventory_with_combined_iqiyi_home_matcher(self):
        from apply_local_overrides import (
            CNFTP_IQIYI_HOME_COMBINED_TRIGGER,
            CNFTP_NON_AD_REMOVE_TRIGGERS,
            remove_duplicate_cnftp_scripts,
        )
        retained = [item for item in self.keep[4:] if item not in CNFTP_NON_AD_REMOVE_TRIGGERS]
        clean = ["[Script]", CNFTP_IQIYI_HOME_COMBINED_TRIGGER, *retained, "[MITM]"]
        self.assertEqual(remove_duplicate_cnftp_scripts(clean), (clean, 0))

    def test_fails_closed_on_missing_duplicate_duplicate_kept_or_unknown_variant(self):
        from apply_local_overrides import remove_duplicate_cnftp_scripts
        missing = [line for line in self.fixture if line != self.remove[0]]
        with self.assertRaisesRegex(ValueError, "legacy video trigger inventory incomplete"):
            remove_duplicate_cnftp_scripts(missing)

        duplicate = ["[Script]", *self.remove, *self.keep_source, self.keep_source[0]]
        with self.assertRaisesRegex(ValueError, "duplicate retained video source"):
            remove_duplicate_cnftp_scripts(duplicate)

        unknown = self.keep_source[0].replace("cnftp.js", "cnftp-next.js")
        with self.assertRaisesRegex(ValueError, "inventory changed"):
            remove_duplicate_cnftp_scripts(["[Script]", *self.remove, *self.keep_source[1:], unknown])


    def test_consolidates_four_same_action_iqiyi_home_matchers_without_scope_expansion(self):
        import re
        from apply_local_overrides import (
            CNFTP_IQIYI_HOME_COMBINED_TRIGGER,
            CNFTP_IQIYI_HOME_SOURCE_TRIGGERS,
            consolidate_cnftp_iqiyi_home_triggers,
        )
        fixture = ["[Script]", *self.keep, self.unrelated, "[MITM]"]
        result, removed = consolidate_cnftp_iqiyi_home_triggers(fixture)
        self.assertEqual(removed, 3)
        self.assertEqual(result.count(CNFTP_IQIYI_HOME_COMBINED_TRIGGER), 1)
        for source in CNFTP_IQIYI_HOME_SOURCE_TRIGGERS:
            self.assertNotIn(source, result)
        self.assertIn(self.unrelated, result)
        pattern = CNFTP_IQIYI_HOME_COMBINED_TRIGGER.split("~= /", 1)[1].split("/i then", 1)[0]
        positives = [
            "https://1.2.3.4/3f1/cards.iqiyi.com/views_home/3.0/qy_home?x=1",
            "https://1.2.3.4/3f1/cards.iqiyi.com/waterfall/3.0/feed?x=1",
            "https://access.if.iqiyi.com/3f1/cards.iqiyi.com/views_category/3.0/category_home?x=1",
            "https://access.if.iqiyi.com/3f1/cards.iqiyi.com/views_home/3.0/qy_home?x=1",
            "https://cards.iqiyi.com/views_category/3.0/category_home?x=1",
            "https://cards.iqiyi.com/views_category/3.0/categorylib_content?x=1",
            "https://cards.iqiyi.com/views_category/3.0/film_hybrid?x=1",
            "https://cards.iqiyi.com/views_home/3.0/qy_home?x=1",
            "https://cards.iqiyi.com/waterfall/3.0/feed?x=1",
        ]
        negatives = [
            "https://cards.iqiyi.com/views_category/3.0/unknown?x=1",
            "https://evilcards.iqiyi.com/views_home/3.0/qy_home?x=1",
            "https://cards.iqiyi.com/views_plt/3.0/player_tabs_v2?x=1",
        ]
        for url in positives:
            self.assertIsNotNone(re.search(pattern, url, re.I), url)
        for url in negatives:
            self.assertIsNone(re.search(pattern, url, re.I), url)
        again, second_removed = consolidate_cnftp_iqiyi_home_triggers(result)
        self.assertEqual(second_removed, 0)
        self.assertEqual(again, result)

    def test_fails_closed_on_missing_duplicate_or_drifted_iqiyi_home_matcher(self):
        from apply_local_overrides import consolidate_cnftp_iqiyi_home_triggers
        fixture = ["[Script]", *self.keep, "[MITM]"]
        missing = [line for line in fixture if line != self.keep[0]]
        with self.assertRaisesRegex(ValueError, "inventory incomplete"):
            consolidate_cnftp_iqiyi_home_triggers(missing)
        duplicate = ["[Script]", *self.keep, self.keep[0], "[MITM]"]
        with self.assertRaisesRegex(ValueError, "duplicate iQIYI"):
            consolidate_cnftp_iqiyi_home_triggers(duplicate)
        unknown = self.keep[0].replace("qy_home", "qy_home_v2")
        with self.assertRaisesRegex(ValueError, "inventory incomplete"):
            consolidate_cnftp_iqiyi_home_triggers(["[Script]", *self.keep[1:], unknown, "[MITM]"])

    def test_checked_in_plugin_snapshot_has_only_the_selected_handlers(self):
        from pathlib import Path
        from apply_local_overrides import (
            CNFTP_DUPLICATE_KEEP_TRIGGERS,
            CNFTP_DUPLICATE_REMOVE_TRIGGERS,
            CNFTP_IQIYI_HOME_COMBINED_TRIGGER,
            CNFTP_NON_AD_REMOVE_TRIGGERS,
        )
        plugin = Path(__file__).with_name("allAdRewrite.plugin").read_text(encoding="utf-8")
        for item in CNFTP_DUPLICATE_REMOVE_TRIGGERS:
            self.assertNotIn(item, plugin)
        self.assertEqual(plugin.count(CNFTP_IQIYI_HOME_COMBINED_TRIGGER), 1)
        for item in CNFTP_DUPLICATE_KEEP_TRIGGERS[4:]:
            if item in CNFTP_NON_AD_REMOVE_TRIGGERS:
                self.assertNotIn(item, plugin)
            else:
                self.assertEqual(plugin.count(item), 1)



class CnftpNonAdTriggerPruningTests(unittest.TestCase):
    def setUp(self):
        from apply_local_overrides import CNFTP_NON_AD_REMOVE_TRIGGERS, CNFTP_DUPLICATE_KEEP_TRIGGERS
        self.targets = CNFTP_NON_AD_REMOVE_TRIGGERS
        self.ad_keep = CNFTP_DUPLICATE_KEEP_TRIGGERS[4]
        self.base = [
            "[Script]", *self.targets, self.ad_keep,
            "[MITM]", "hostname = iface2.iqiyi.com, search.video.iqiyi.com, acs.youku.com",
        ]

    def test_removes_six_non_ad_triggers_and_preserves_ad_trigger(self):
        from apply_local_overrides import remove_cnftp_non_ad_triggers
        result, removed = remove_cnftp_non_ad_triggers(self.base)
        self.assertEqual(removed, 6)
        for item in self.targets:
            self.assertNotIn(item, result)
        self.assertIn(self.ad_keep, result)
        self.assertEqual(remove_cnftp_non_ad_triggers(result), (result, 0))

    def test_allows_independently_missing_upstream_triggers(self):
        from apply_local_overrides import remove_cnftp_non_ad_triggers
        partial = [line for line in self.base if line != self.targets[0]]
        result, removed = remove_cnftp_non_ad_triggers(partial)
        self.assertEqual(removed, 5)
        self.assertNotIn(self.targets[1], result)
        self.assertIn(self.ad_keep, result)

    def test_fails_closed_on_duplicate_or_unknown_same_matcher(self):
        from apply_local_overrides import remove_cnftp_non_ad_triggers
        duplicate = ["[Script]", *self.targets, self.targets[0], "[MITM]"]
        with self.assertRaisesRegex(ValueError, "duplicate CNFTP non-ad trigger"):
            remove_cnftp_non_ad_triggers(duplicate)

        unknown = self.base.copy()
        index = unknown.index(self.targets[0])
        unknown.insert(index + 1, self.targets[0].replace("getMyMenus", "getMyMenusV2"))
        with self.assertRaisesRegex(ValueError, "matcher changed"):
            remove_cnftp_non_ad_triggers(unknown)

    def test_current_blockads_source_variants_are_supported(self):
        from apply_local_overrides import (
            CNFTP_BLOCKADS_SOURCE_TRIGGERS,
            CNFTP_NON_AD_REMOVE_TRIGGERS,
            CNFTP_IQIYI_HOME_COMBINED_TRIGGER,
            normalize_cnftp_trigger_line,
            apply,
        )
        current_base = (
            "#!name=current-blockads-cnftp-test\n[Argument]\naiqiyi_enable = switch,true,false,tag=IQIYI\n"
            "youku_enable = switch,true,false,tag=YOUKU\n[Rewrite]\n[Script]\n" +
            "\n".join(CNFTP_BLOCKADS_SOURCE_TRIGGERS) +
            "\n[MITM]\nhostname = iface2.iqiyi.com, search.video.iqiyi.com, acs.youku.com, "
            "creditcard.bankcomm.cn, creditcard.bankcomm.com, creditcardapp.bankcomm.cn, "
            "creditcardapp.bankcomm.com\n"
        )
        result = apply(current_base)
        normalized_result = {normalize_cnftp_trigger_line(line) for line in result.splitlines()}
        for item in CNFTP_NON_AD_REMOVE_TRIGGERS:
            self.assertNotIn(normalize_cnftp_trigger_line(item), normalized_result)
        self.assertIn(CNFTP_IQIYI_HOME_COMBINED_TRIGGER, result)
        self.assertEqual(apply(result), result)

    def test_checked_in_plugin_applies_non_ad_pruning_without_losing_ad_handlers(self):
        from pathlib import Path
        from apply_local_overrides import apply
        plugin = Path(__file__).with_name("allAdRewrite.plugin").read_text(encoding="utf-8")
        result = apply(plugin)
        for item in self.targets:
            self.assertNotIn(item, result)
        self.assertIn(self.ad_keep, result)


class Dushu365NonAdTriggerPruningTests(unittest.TestCase):
    def setUp(self):
        from apply_local_overrides import (
            DUSHU365_NON_AD_REMOVE_TRIGGERS,
            DUSHU365_AD_AND_UNCERTAIN_KEEP_TRIGGERS,
        )
        self.remove = DUSHU365_NON_AD_REMOVE_TRIGGERS
        self.keep = DUSHU365_AD_AND_UNCERTAIN_KEEP_TRIGGERS
        self.fixture = ["[Script]", *self.remove, *self.keep, "[MITM]", "hostname = g.dushu365.com"]

    def test_removes_four_layout_only_triggers_and_preserves_ad_and_uncertain_entries(self):
        from apply_local_overrides import remove_dushu365_non_ad_triggers
        result, removed = remove_dushu365_non_ad_triggers(self.fixture)
        self.assertEqual(removed, 4)
        for item in self.remove:
            self.assertNotIn(item, result)
        for item in self.keep:
            self.assertEqual(result.count(item), 1)
        self.assertEqual(remove_dushu365_non_ad_triggers(result), (result, 0))

    def test_allows_independently_removed_upstream_entries(self):
        from apply_local_overrides import remove_dushu365_non_ad_triggers
        partial = [line for line in self.fixture if line != self.remove[0] and line != self.keep[0]]
        result, removed = remove_dushu365_non_ad_triggers(partial)
        self.assertEqual(removed, 3)
        self.assertNotIn(self.remove[0], result)
        self.assertNotIn(self.keep[0], result)
        for item in self.keep[1:]:
            self.assertIn(item, result)

    def test_fails_closed_on_duplicates_unknown_same_script_or_section_drift(self):
        from apply_local_overrides import remove_dushu365_non_ad_triggers
        duplicate = ["[Script]", *self.remove, *self.keep, self.remove[0], "[MITM]"]
        with self.assertRaisesRegex(ValueError, "duplicate Dushu365"):
            remove_dushu365_non_ad_triggers(duplicate)

        unknown = self.fixture.copy()
        index = unknown.index(self.keep[0])
        unknown.insert(index + 1, self.keep[0].replace("DUSHU365-2", "DUSHU365-2-UNKNOWN"))
        with self.assertRaisesRegex(ValueError, "inventory changed"):
            remove_dushu365_non_ad_triggers(unknown)

        moved = ["[Rewrite]", self.remove[0], "[Script]", *self.keep, "[MITM]"]
        with self.assertRaisesRegex(ValueError, "outside Script"):
            remove_dushu365_non_ad_triggers(moved)

    def test_checked_in_plugin_keeps_only_the_five_reviewed_entries(self):
        from pathlib import Path
        from apply_local_overrides import (
            DUSHU365_NON_AD_REMOVE_TRIGGERS,
            DUSHU365_AD_AND_UNCERTAIN_KEEP_TRIGGERS,
            apply,
        )
        plugin = Path(__file__).with_name("allAdRewrite.plugin").read_text(encoding="utf-8")
        result = apply(plugin)
        for item in DUSHU365_NON_AD_REMOVE_TRIGGERS:
            self.assertNotIn(item, result)
        for item in DUSHU365_AD_AND_UNCERTAIN_KEEP_TRIGGERS:
            self.assertEqual(result.count(item), 1)


class SameSourceResponseScriptDedupTests(unittest.TestCase):
    def setUp(self):
        from apply_local_overrides import (
            SAME_SOURCE_DUPLICATE_KEEP_TRIGGERS, SAME_SOURCE_DUPLICATE_REMOVE_TRIGGERS,
        )
        self.keep = SAME_SOURCE_DUPLICATE_KEEP_TRIGGERS
        self.remove = SAME_SOURCE_DUPLICATE_REMOVE_TRIGGERS
        self.unrelated = 'response if ${url} ~= /^https?:\\/\\/example\\.com\\/api/ then script("https://example.invalid/keep.js")'
        self.fixture = [
            "[Script]", *self.remove, *self.keep, self.unrelated,
            "[Rewrite]", "^https?:\\\\/\\\\/creditcardapp.bankcomm.com\\\\/unrelated reject(404)",
            "[MITM]", "hostname = g.alicdn.com, creditcardapp.bankcomm.com, maicai.api.ddxq.mobi",
        ]

    def test_removes_12_same_script_duplicates_and_keeps_canonical_entries(self):
        from apply_local_overrides import remove_same_source_duplicate_response_scripts
        result, removed = remove_same_source_duplicate_response_scripts(self.fixture)
        self.assertEqual(removed, 12)
        for item in self.remove:
            self.assertNotIn(item, result)
        for item in self.keep:
            self.assertEqual(result.count(item), 1)
        self.assertIn(self.unrelated, result)
        self.assertIn("^https?:\\\\/\\\\/creditcardapp.bankcomm.com\\\\/unrelated reject(404)", result)
        self.assertEqual(remove_same_source_duplicate_response_scripts(result), (result, 0))

    def test_accepts_interpolated_switch_variant_without_changing_the_rule(self):
        from apply_local_overrides import remove_same_source_duplicate_response_scripts
        source = next(item for item in self.keep if "bilimanhua_enable" in item)
        current = source.replace("enable=bilimanhua_enable", "enable=${bilimanhua_enable}")
        fixture = ["[Script]", *self.remove, *[
            current if item == source else item for item in self.keep
        ], "[MITM]"]
        result, removed = remove_same_source_duplicate_response_scripts(fixture)
        self.assertEqual(removed, len(self.remove))
        self.assertIn(current, result)
        self.assertNotIn(source, result)
        self.assertEqual(remove_same_source_duplicate_response_scripts(result), (result, 0))

    def test_preserves_already_consolidated_inventory(self):
        from apply_local_overrides import remove_same_source_duplicate_response_scripts
        clean = ["[Script]", *self.keep, "[MITM]"]
        self.assertEqual(remove_same_source_duplicate_response_scripts(clean), (clean, 0))

    def test_fails_closed_on_missing_duplicate_or_unknown_variant(self):
        from apply_local_overrides import remove_same_source_duplicate_response_scripts
        missing = [line for line in self.fixture if line != self.remove[0]]
        with self.assertRaisesRegex(ValueError, "inventory incomplete"):
            remove_same_source_duplicate_response_scripts(missing)

        duplicate = ["[Script]", *self.remove, *self.keep, self.keep[0]]
        with self.assertRaisesRegex(ValueError, "duplicate same-source retained"):
            remove_same_source_duplicate_response_scripts(duplicate)

        unknown = next(item for item in self.keep if "o2o-ad" in item).replace("o2o-ad", "o2o-ad-v2")
        with self.assertRaisesRegex(ValueError, "inventory changed"):
            remove_same_source_duplicate_response_scripts(["[Script]", *self.remove, *self.keep[1:], unknown])

    def test_checked_in_plugin_snapshot_has_only_the_canonical_entries(self):
        from pathlib import Path
        from apply_local_overrides import SAME_SOURCE_DUPLICATE_KEEP_TRIGGERS, SAME_SOURCE_DUPLICATE_REMOVE_TRIGGERS
        plugin = Path(__file__).with_name("allAdRewrite.plugin").read_text(encoding="utf-8")
        for item in SAME_SOURCE_DUPLICATE_REMOVE_TRIGGERS:
            self.assertNotIn(item, plugin)
        for item in SAME_SOURCE_DUPLICATE_KEEP_TRIGGERS:
            self.assertEqual(plugin.count(item), 1)


class IdenticalScriptResponseDedupTests(unittest.TestCase):
    def setUp(self):
        from apply_local_overrides import (
            IDENTICAL_SCRIPT_KEEP_SOURCE_TRIGGERS,
            IDENTICAL_SCRIPT_KEEP_TRIGGERS,
            IDENTICAL_SCRIPT_REMOVE_TRIGGERS,
            IDENTICAL_SCRIPT_TRANSFORMS,
        )
        self.keep_source = IDENTICAL_SCRIPT_KEEP_SOURCE_TRIGGERS
        self.keep = IDENTICAL_SCRIPT_KEEP_TRIGGERS
        self.remove = IDENTICAL_SCRIPT_REMOVE_TRIGGERS
        self.transforms = IDENTICAL_SCRIPT_TRANSFORMS
        self.unrelated = 'response if ${url} ~= /^https?:\\/\\/example\\.com\\/api/ then script("https://example.invalid/keep.js")'
        self.fixture = [
            "[Script]", *self.remove, *self.keep_source, self.unrelated,
            "[Rewrite]", "^https?:\\\\/\\\\/api.rr.tv\\\\/unrelated reject(404)",
            "[MITM]", "hostname = api.rr.tv, api-a.soulapp.cn, gql.reddit.com",
        ]

    def test_removes_17_duplicates_and_keeps_24_single_handlers(self):
        from apply_local_overrides import remove_identical_script_response_duplicates
        result, removed = remove_identical_script_response_duplicates(self.fixture)
        self.assertEqual(removed, 17)
        for item in self.remove:
            self.assertNotIn(item, result)
        for item in self.keep_source:
            expected = self.transforms.get(item, item)
            self.assertEqual(result.count(expected), 1)
        self.assertIn(self.unrelated, result)
        self.assertIn("^https?:\\\\/\\\\/api.rr.tv\\\\/unrelated reject(404)", result)
        self.assertEqual(remove_identical_script_response_duplicates(result), (result, 0))

    def test_accepts_interpolated_switch_and_preserves_it_in_canonical_output(self):
        from apply_local_overrides import remove_identical_script_response_duplicates
        source = next(item for item in self.keep_source if "rfrfuipk_enable" in item)
        current = source.replace("enable=rfrfuipk_enable", "enable=${rfrfuipk_enable}")
        fixture = [
            "[Script]", *self.remove,
            *[current if item == source else item for item in self.keep_source],
            "[MITM]",
        ]
        result, removed = remove_identical_script_response_duplicates(fixture)
        self.assertEqual(removed, len(self.remove))
        expected = self.transforms.get(source, source).replace(
            "enable=rfrfuipk_enable", "enable=${rfrfuipk_enable}"
        )
        self.assertIn(expected, result)
        self.assertEqual(remove_identical_script_response_duplicates(result), (result, 0))

    def test_preserves_already_consolidated_inventory(self):
        from apply_local_overrides import remove_identical_script_response_duplicates
        clean = ["[Script]", *self.keep, "[MITM]"]
        self.assertEqual(remove_identical_script_response_duplicates(clean), (clean, 0))

    def test_fails_closed_on_missing_duplicate_or_unknown_variant(self):
        from apply_local_overrides import remove_identical_script_response_duplicates
        missing = [line for line in self.fixture if line != self.remove[0]]
        with self.assertRaisesRegex(ValueError, "legacy identical-script inventory incomplete"):
            remove_identical_script_response_duplicates(missing)

        duplicate = ["[Script]", *self.remove, *self.keep_source, self.keep_source[0]]
        with self.assertRaisesRegex(ValueError, "duplicate retained identical-script"):
            remove_identical_script_response_duplicates(duplicate)

        unknown = self.keep_source[0].replace("rrtv_json.js", "rrtv-next.js")
        with self.assertRaisesRegex(ValueError, "inventory changed"):
            remove_identical_script_response_duplicates(["[Script]", *self.remove, *self.keep_source[1:], unknown])

    def test_preserves_native_rrtv_ad_rewrites_with_remaining_soul_reddit_handlers(self):
        from apply_local_overrides import (
            RRTV_NATIVE_REWRITES,
            IDENTICAL_SCRIPT_CURRENT_CANONICAL_TRIGGERS,
            remove_identical_script_response_duplicates,
        )
        clean = [
            "[Rewrite]", *RRTV_NATIVE_REWRITES,
            "[Script]", *IDENTICAL_SCRIPT_CURRENT_CANONICAL_TRIGGERS[9:],
            "[MITM]",
        ]
        self.assertEqual(remove_identical_script_response_duplicates(clean), (clean, 0))

    def test_checked_in_plugin_snapshot_has_only_the_canonical_handlers(self):
        from pathlib import Path
        from apply_local_overrides import (
            IDENTICAL_SCRIPT_CURRENT_CANONICAL_TRIGGERS,
            IDENTICAL_SCRIPT_REMOVE_TRIGGERS,
            RRTV_NATIVE_REWRITES,
        )
        plugin = Path(__file__).with_name("allAdRewrite.plugin").read_text(encoding="utf-8")
        for item in IDENTICAL_SCRIPT_REMOVE_TRIGGERS:
            self.assertNotIn(item, plugin)
        for item in IDENTICAL_SCRIPT_CURRENT_CANONICAL_TRIGGERS[9:]:
            self.assertEqual(plugin.count(item), 1)
        for item in RRTV_NATIVE_REWRITES:
            self.assertEqual(plugin.count(item), 1)


class MoreResponseScriptDedupTests(unittest.TestCase):
    def setUp(self):
        from apply_local_overrides import (
            MORE_RESPONSE_KEEP_SOURCE_TRIGGERS, MORE_RESPONSE_KEEP_TRIGGERS,
            MORE_RESPONSE_REMOVE_TRIGGERS, MORE_RESPONSE_TRANSFORMS,
        )
        self.keep_source = MORE_RESPONSE_KEEP_SOURCE_TRIGGERS
        self.keep = MORE_RESPONSE_KEEP_TRIGGERS
        self.remove = MORE_RESPONSE_REMOVE_TRIGGERS
        self.transforms = MORE_RESPONSE_TRANSFORMS
        self.unrelated = 'response if ${url} ~= /^https?:\\/\\/example\\.com\\/api/ then script("https://example.invalid/keep.js")'
        self.fixture = [
            "[Script]", *self.remove, *self.keep_source, self.unrelated,
            "[Rewrite]", "^https?:\\\\/\\\\/api.rr.tv\\\\/unrelated reject(404)",
            "[MITM]", "hostname = kuwo.cn, napi.ithome.com, cn-acs.m.cainiao.com",
        ]

    def test_removes_11_duplicates_and_keeps_13_single_handlers(self):
        from apply_local_overrides import remove_more_duplicate_response_scripts
        result, removed = remove_more_duplicate_response_scripts(self.fixture)
        self.assertEqual(removed, 11)
        for item in self.remove:
            self.assertNotIn(item, result)
        for item in self.keep_source:
            expected = self.transforms.get(item, item)
            self.assertEqual(result.count(expected), 1)
        self.assertIn(self.unrelated, result)
        self.assertEqual(remove_more_duplicate_response_scripts(result), (result, 0))

    def test_accepts_interpolated_switch_and_preserves_it_in_response_output(self):
        from apply_local_overrides import remove_more_duplicate_response_scripts
        source = next(item for item in self.keep_source if "kuwoybyt_enable" in item)
        current = source.replace("enable=kuwoybyt_enable", "enable=${kuwoybyt_enable}")
        fixture = [
            "[Script]", *self.remove,
            *[current if item == source else item for item in self.keep_source],
            "[MITM]",
        ]
        result, removed = remove_more_duplicate_response_scripts(fixture)
        self.assertEqual(removed, len(self.remove))
        expected = self.transforms.get(source, source).replace(
            "enable=kuwoybyt_enable", "enable=${kuwoybyt_enable}"
        )
        self.assertIn(expected, result)
        self.assertEqual(remove_more_duplicate_response_scripts(result), (result, 0))

    def test_removes_duplicate_with_interpolated_switch(self):
        from apply_local_overrides import remove_more_duplicate_response_scripts
        source = next(item for item in self.remove if "quda_enable" in item)
        current = source.replace("enable=quda_enable", "enable=${quda_enable}")
        fixture = [
            "[Script]",
            *[current if item == source else item for item in self.remove],
            *self.keep_source,
            "[MITM]",
        ]
        result, removed = remove_more_duplicate_response_scripts(fixture)
        self.assertEqual(removed, len(self.remove))
        self.assertNotIn(current, result)
        self.assertEqual(remove_more_duplicate_response_scripts(result), (result, 0))

    def test_preserves_already_consolidated_inventory(self):
        from apply_local_overrides import remove_more_duplicate_response_scripts
        clean = ["[Script]", *self.keep, "[MITM]"]
        self.assertEqual(remove_more_duplicate_response_scripts(clean), (clean, 0))

    def test_fails_closed_on_missing_duplicate_or_unknown_variant(self):
        from apply_local_overrides import remove_more_duplicate_response_scripts
        missing = [line for line in self.fixture if line != self.remove[0]]
        with self.assertRaisesRegex(ValueError, "legacy response inventory incomplete"):
            remove_more_duplicate_response_scripts(missing)

        duplicate = ["[Script]", *self.remove, *self.keep_source, self.keep_source[0]]
        with self.assertRaisesRegex(ValueError, "duplicate retained response source"):
            remove_more_duplicate_response_scripts(duplicate)

        unknown = self.keep_source[0].replace("kuwo.js", "kuwo-next.js")
        with self.assertRaisesRegex(ValueError, "inventory changed"):
            remove_more_duplicate_response_scripts(["[Script]", *self.remove, *self.keep_source[1:], unknown])

    def test_checked_in_plugin_snapshot_has_only_the_canonical_handlers(self):
        from pathlib import Path
        from apply_local_overrides import MORE_RESPONSE_KEEP_TRIGGERS, MORE_RESPONSE_REMOVE_TRIGGERS
        plugin = Path(__file__).with_name("allAdRewrite.plugin").read_text(encoding="utf-8")
        for item in MORE_RESPONSE_REMOVE_TRIGGERS:
            self.assertNotIn(item, plugin)
        for item in MORE_RESPONSE_KEEP_TRIGGERS:
            self.assertEqual(plugin.count(item), 1)



    def test_xiaohongshu_native_ad_rewrites_replace_duplicate_body_scripts(self):
        from apply_local_overrides import XHS_SCRIPT_TRIGGER_LINES, XHS_HOMEFEED_NATIVE_OLD_RULE, XHS_V4_VIDEO_AD_ONLY_RULE, optimize_xiaohongshu_response_cost
        fixture = [
            "[Argument]", "xhs_enable = switch,true,false,tag=小红书-脚本开关",
            "[Rewrite]",
            r"""^https?:\/\/ci\.xiaohongshu\.com\/system_config\/watermark reject-img""",
            r"""request if ${url} ~= /^https?:\/\/ci\.(xiaohongshu|rnote)\.com\/system_config\/watermark/ then reject_img(200)""",
            r"""^https:\/\/(?:edith|rec|www)\.xiaohongshu\.com\/api\/sns\/v1\/note\/imagefeed response-body-json-jq 'disable_watermark video_download'""",
            r"""^https:\/\/(?:edith|rec|www)\.xiaohongshu\.com\/api\/sns\/v2\/note\/feed response-body-json-jq 'disable_watermark video_download'""",
            r"""^https:\/\/(?:edith|rec|www)\.xiaohongshu\.com\/api\/sns\/v3\/note\/videofeed response-body-json-jq 'disable_watermark video_download'""",
            r"""^https:\/\/(?:edith|rec|www)\.xiaohongshu\.com\/api\/sns\/v4\/note\/videofeed response-body-json-jq 'disable_watermark video_download model_type has("ad")'""",
            r"""^https:\/\/edith\.xiaohongshu\.com\/api\/sns\/v5\/note\/comment\/list response-body-json-jq 'comment_type media_source_type'""",
            r"""^https:\/\/edith\.xiaohongshu\.com\/api\/sns\/v\d+\/system_service\/config response-body-json-jq 'del(.data.splash)'""",
            "[Script]", *sorted(XHS_SCRIPT_TRIGGER_LINES),
            r"""http-response ^https:\/\/api\.example\.com script-path=https://example.invalid/keep.js""",
            "[MITM]", "hostname = edith.xiaohongshu.com",
        ]
        result, removed = optimize_xiaohongshu_response_cost(fixture)
        self.assertEqual(removed, 23)
        self.assertFalse(any("xiaohongshu" in line.lower() and ("script-path=" in line or 'script("' in line) for line in result))
        self.assertNotIn("disable_watermark", "\n".join(result))
        self.assertNotIn("video_download", "\n".join(result))
        self.assertNotIn("comment_type", "\n".join(result))
        self.assertIn(XHS_V4_VIDEO_AD_ONLY_RULE, result)
        self.assertIn('has("ad")', XHS_V4_VIDEO_AD_ONLY_RULE)
        self.assertFalse(any("videofeed" in line and "v3" in line for line in result))
        self.assertTrue(any("system_service" in line for line in result))
        self.assertTrue(any("example.invalid/keep.js" in line for line in result))
        again, second_removed = optimize_xiaohongshu_response_cost(result)
        self.assertEqual(second_removed, 0)
        self.assertEqual(again, result)


    def test_xiaohongshu_cleanup_accepts_one_reviewed_upstream_pruned_watermark_rule(self):
        from apply_local_overrides import XHS_SCRIPT_TRIGGER_LINES, XHS_V4_VIDEO_AD_ONLY_RULE, optimize_xiaohongshu_response_cost
        fixture = [
            "[Argument]", "xhs_enable = switch,true,false,tag=小红书-脚本开关",
            "[Rewrite]",
            r"""^https?:\/\/ci\.xiaohongshu\.com\/system_config\/watermark reject-img""",
            r"""request if ${url} ~= /^https?:\/\/ci\.(xiaohongshu|rnote)\.com\/system_config\/watermark/ then reject_img(200)""",
            r"""^https:\/\/(?:edith|rec|www)\.xiaohongshu\.com\/api\/sns\/v1\/note\/imagefeed response-body-json-jq 'disable_watermark video_download'""",
            r"""^https:\/\/(?:edith|rec|www)\.xiaohongshu\.com\/api\/sns\/v2\/note\/feed response-body-json-jq 'disable_watermark video_download'""",
            r"""^https:\/\/(?:edith|rec|www)\.xiaohongshu\.com\/api\/sns\/v3\/note\/videofeed response-body-json-jq 'disable_watermark video_download'""",
            r"""^https:\/\/(?:edith|rec|www)\.xiaohongshu\.com\/api\/sns\/v4\/note\/videofeed response-body-json-jq 'disable_watermark video_download model_type has("ad")'""",
            r"""^https:\/\/edith\.xiaohongshu\.com\/api\/sns\/v5\/note\/comment\/list response-body-json-jq 'comment_type media_source_type'""",
            r"""^https:\/\/edith\.xiaohongshu\.com\/api\/sns\/v\d+\/system_service\/config response-body-json-jq 'del(.data.splash)'""",
            "[Script]", *sorted(XHS_SCRIPT_TRIGGER_LINES),
            r"""http-response ^https:\/\/api\.example\.com script-path=https://example.invalid/keep.js""",
            "[MITM]", "hostname = edith.xiaohongshu.com",
        ]
        result, removed = optimize_xiaohongshu_response_cost(fixture)
        self.assertEqual(removed, 23)
        self.assertIn(XHS_V4_VIDEO_AD_ONLY_RULE, result)
        self.assertTrue(any("example.invalid/keep.js" in line for line in result))
        self.assertFalse(any("xiaohongshu" in line.lower() and ("script-path=" in line or 'script("' in line) for line in result))
        self.assertFalse(any("/system_config/watermark" in line for line in result))
        again, second_removed = optimize_xiaohongshu_response_cost(result)
        self.assertEqual(second_removed, 0)
        self.assertEqual(again, result)

    def test_xiaohongshu_cleanup_fails_closed_on_unknown_watermark_rule_variant(self):
        from apply_local_overrides import XHS_SCRIPT_TRIGGER_LINES, optimize_xiaohongshu_response_cost
        fixture = [
            "[Argument]", "xhs_enable = switch,true,false,tag=小红书-脚本开关",
            "[Rewrite]",
            r"""^https?:\/\/ci\.xiaohongshu\.com\/system_config\/watermark reject-img""",
            r"""request if ${url} ~= /^https?:\/\/ci\.(xiaohongshu|rnote)\.com\/system_config\/watermark/ then reject_img(200)""",
            r"""^https?:\/\/ci\.xiaohongshu\.com\/system_config\/watermark-extra reject-img""",
            r"""^https:\/\/(?:edith|rec|www)\.xiaohongshu\.com\/api\/sns\/v1\/note\/imagefeed response-body-json-jq 'disable_watermark video_download'""",
            r"""^https:\/\/(?:edith|rec|www)\.xiaohongshu\.com\/api\/sns\/v2\/note\/feed response-body-json-jq 'disable_watermark video_download'""",
            r"""^https:\/\/(?:edith|rec|www)\.xiaohongshu\.com\/api\/sns\/v3\/note\/videofeed response-body-json-jq 'disable_watermark video_download'""",
            r"""^https:\/\/(?:edith|rec|www)\.xiaohongshu\.com\/api\/sns\/v4\/note\/videofeed response-body-json-jq 'disable_watermark video_download model_type has("ad")'""",
            r"""^https:\/\/edith\.xiaohongshu\.com\/api\/sns\/v5\/note\/comment\/list response-body-json-jq 'comment_type media_source_type'""",
            "[Script]", *sorted(XHS_SCRIPT_TRIGGER_LINES),
            "[MITM]", "hostname = edith.xiaohongshu.com",
        ]
        result, removed = optimize_xiaohongshu_response_cost(fixture)
        self.assertEqual(removed, 0)
        self.assertEqual(result, fixture)

    def test_xiaohongshu_cleanup_fails_closed_on_trigger_drift(self):
        from apply_local_overrides import XHS_SCRIPT_TRIGGER_LINES, optimize_xiaohongshu_response_cost
        triggers = list(sorted(XHS_SCRIPT_TRIGGER_LINES))
        triggers[0] = triggers[0].replace("requires-body=true", "requires-body=false")
        fixture = [
            "[Argument]", "xhs_enable = switch,true,false,tag=小红书-脚本开关",
            "[Rewrite]",
            r"""^https:\/\/(?:edith|rec|www)\.xiaohongshu\.com\/api\/sns\/v1\/note\/imagefeed response-body-json-jq 'disable_watermark video_download'""",
            r"""^https:\/\/(?:edith|rec|www)\.xiaohongshu\.com\/api\/sns\/v2\/note\/feed response-body-json-jq 'disable_watermark video_download'""",
            r"""^https:\/\/(?:edith|rec|www)\.xiaohongshu\.com\/api\/sns\/v3\/note\/videofeed response-body-json-jq 'disable_watermark video_download model_type has("ad")'""",
            r"""^https:\/\/(?:edith|rec|www)\.xiaohongshu\.com\/api\/sns\/v4\/note\/videofeed response-body-json-jq 'disable_watermark video_download model_type has("ad")'""",
            r"""^https:\/\/edith\.xiaohongshu\.com\/api\/sns\/v5\/note\/comment\/list response-body-json-jq 'comment_type media_source_type'""",
            r"""^https:\/\/ci\.xiaohongshu\.com\/system_config\/watermark reject-img""",
            r"""^https:\/\/ci\.xiaohongshu\.com\/system_config\/watermark reject-img""",
            "[Script]", *triggers, "[MITM]", "hostname = edith.xiaohongshu.com",
        ]
        result, removed = optimize_xiaohongshu_response_cost(fixture)
        self.assertEqual(removed, 0)
        self.assertEqual(result, fixture)

    def test_xiaohongshu_cleanup_requires_both_native_video_ad_filters(self):
        from apply_local_overrides import XHS_SCRIPT_TRIGGER_LINES, optimize_xiaohongshu_response_cost
        fixture = [
            "[Argument]", "xhs_enable = switch,true,false,tag=小红书-脚本开关",
            "[Rewrite]",
            r"""^https:\/\/(?:edith|rec|www)\.xiaohongshu\.com\/api\/sns\/v1\/note\/imagefeed response-body-json-jq 'disable_watermark video_download'""",
            r"""^https:\/\/(?:edith|rec|www)\.xiaohongshu\.com\/api\/sns\/v2\/note\/feed response-body-json-jq 'disable_watermark video_download'""",
            r"""^https:\/\/(?:edith|rec|www)\.xiaohongshu\.com\/api\/sns\/v3\/note\/videofeed response-body-json-jq 'disable_watermark video_download model_type has("ad")'""",
            r"""^https:\/\/(?:edith|rec|www)\.xiaohongshu\.com\/api\/sns\/v5\/note\/videofeed response-body-json-jq 'disable_watermark video_download model_type has("ad")'""",
            r"""^https:\/\/edith\.xiaohongshu\.com\/api\/sns\/v5\/note\/comment\/list response-body-json-jq 'comment_type media_source_type'""",
            r"""^https:\/\/ci\.xiaohongshu\.com\/system_config\/watermark reject-img""",
            r"""^https:\/\/ci\.xiaohongshu\.com\/system_config\/watermark reject-img""",
            "[Script]", *sorted(XHS_SCRIPT_TRIGGER_LINES), "[MITM]", "hostname = edith.xiaohongshu.com",
        ]
        result, removed = optimize_xiaohongshu_response_cost(fixture)
        self.assertEqual(removed, 0)
        self.assertEqual(result, fixture)




class WeiboNonAdResponseTriggerTests(unittest.TestCase):
    def test_checked_in_snapshot_matches_optimized_weibo_trigger_inventory(self):
        from pathlib import Path
        from apply_local_overrides import WEIBO_OPTIMIZED_SCRIPT_TRIGGER_LINES, WEIBO_PUSH_ACTIVE_TRIGGER
        plugin = Path(__file__).with_name("allAdRewrite.plugin").read_text(encoding="utf-8")
        section = ""
        weibo = []
        for line in plugin.splitlines():
            value = line.strip()
            if value.startswith("[") and value.endswith("]"):
                section = value[1:-1]
            elif section == "Script" and "weibo.js" in value.lower():
                weibo.append(value)
        self.assertEqual(len(weibo), 15)
        self.assertEqual(set(weibo), WEIBO_OPTIMIZED_SCRIPT_TRIGGER_LINES)
        self.assertIn(WEIBO_PUSH_ACTIVE_TRIGGER, weibo)


    def _fixture(self):
        from apply_local_overrides import WEIBO_SCRIPT_TRIGGER_LINES
        return [
            "[Script]",
            *sorted(WEIBO_SCRIPT_TRIGGER_LINES),
            r"""http-response ^https:\/\/api\.example\.com\/keep script-path=https://example.invalid/keep.js""",
            "[Rewrite]",
            r"""^https:\/\/api\.example\.com\/ad response-body-json-jq '.data=[]'""",
        ]

    def test_removes_only_non_ad_weibo_triggers_and_narrows_mixed_home_matcher(self):
        from apply_local_overrides import (
            WEIBO_NON_AD_TRIGGER_LINES, WEIBO_PUSH_ACTIVE_TRIGGER,
            remove_weibo_non_ad_response_triggers,
        )
        fixture = self._fixture()
        result, changed = remove_weibo_non_ad_response_triggers(fixture)
        self.assertEqual(changed, 5)
        weibo = [
            line.strip() for line in result
            if "weibo.js" in line.lower()
        ]
        self.assertEqual(len(weibo), 15)
        self.assertIn(WEIBO_PUSH_ACTIVE_TRIGGER, weibo)
        self.assertFalse(any(line in WEIBO_NON_AD_TRIGGER_LINES for line in weibo))
        self.assertTrue(any("example.invalid/keep.js" in line for line in result))
        self.assertIn(r"""^https:\/\/api\.example\.com\/ad response-body-json-jq '.data=[]'""", result)
        again, second_changed = remove_weibo_non_ad_response_triggers(result)
        self.assertEqual(second_changed, 0)
        self.assertEqual(again, result)

    def test_fails_closed_on_weibo_trigger_drift_or_duplicate(self):
        from apply_local_overrides import remove_weibo_non_ad_response_triggers
        fixture = self._fixture()
        drifted = list(fixture)
        index = next(i for i, line in enumerate(drifted) if "friendships" in line)
        drifted[index] = drifted[index].replace("create|destroy", "create|remove")
        result, changed = remove_weibo_non_ad_response_triggers(drifted)
        self.assertEqual(changed, 0)
        self.assertEqual(result, drifted)

        duplicated = self._fixture()
        index = next(i for i, line in enumerate(duplicated) if "friendships" in line)
        rewrite_index = duplicated.index("[Rewrite]")
        duplicated.insert(rewrite_index, duplicated[index])
        result, changed = remove_weibo_non_ad_response_triggers(duplicated)
        self.assertEqual(changed, 0)
        self.assertEqual(result, duplicated)



class StarPluckerIdempotenceTests(unittest.TestCase):
    def test_already_consolidated_starplucker_rule_is_a_safe_noop(self):
        from apply_local_overrides import (
            STARPLUCKER_SINGLE_JQ_RULE, consolidate_starplucker_config_jq,
        )
        fixture = ["[Rewrite]", STARPLUCKER_SINGLE_JQ_RULE, "[MITM]", "hostname = starplucker.cyapi.cn"]
        result, changed = consolidate_starplucker_config_jq(fixture)
        self.assertEqual(changed, 0)
        self.assertEqual(result, fixture)


class SmzdmHomepageScriptOptimizationTests(unittest.TestCase):
    def test_removes_only_duplicate_fmz_homepage_dispatch_when_rstore_handler_exists(self):
        from apply_local_overrides import (
            SMZDM_FMZ_HOME_TRIGGER, SMZDM_RSTORE_HOME_TRIGGER,
            remove_redundant_smzdm_homepage_script_trigger,
        )
        fixture = [
            "[Script]",
            SMZDM_RSTORE_HOME_TRIGGER,
            SMZDM_FMZ_HOME_TRIGGER,
            "response if ${url} ~= /^https?:\\/\\/homepage-api\\.smzdm\\.com\\/v3\\/home\\/other/i then script(\"https://example.invalid/other.js\") with requires_body=true",
            "[MITM]",
            "hostname = homepage-api.smzdm.com",
        ]
        result, changed = remove_redundant_smzdm_homepage_script_trigger(fixture)
        self.assertEqual(changed, 1)
        self.assertIn(SMZDM_RSTORE_HOME_TRIGGER, result)
        self.assertNotIn(SMZDM_FMZ_HOME_TRIGGER, result)
        self.assertTrue(any("other.js" in line for line in result))
        again, second_changed = remove_redundant_smzdm_homepage_script_trigger(result)
        self.assertEqual(second_changed, 0)
        self.assertEqual(again, result)

    def test_removes_interpolated_fmz_homepage_dispatch_when_rstore_handler_exists(self):
        from apply_local_overrides import (
            SMZDM_FMZ_HOME_TRIGGER, SMZDM_RSTORE_HOME_TRIGGER,
            remove_redundant_smzdm_homepage_script_trigger,
        )
        fmz = SMZDM_FMZ_HOME_TRIGGER.replace("enable=smzdm_enable", "enable=${smzdm_enable}")
        fixture = ["[Script]", SMZDM_RSTORE_HOME_TRIGGER, fmz, "[MITM]"]
        result, changed = remove_redundant_smzdm_homepage_script_trigger(fixture)
        self.assertEqual(changed, 1)
        self.assertNotIn(fmz, result)
        self.assertIn(SMZDM_RSTORE_HOME_TRIGGER, result)

    def test_removes_interpolated_fmz_ad_triggers_when_rstore_covers_them(self):
        from apply_local_overrides import (
            SMZDM_FMZ_ADS_DUPLICATE_PAIRS,
            remove_redundant_smzdm_ads_script_triggers,
        )
        fixture = ["[Script]"]
        for _, rstore, fmz in SMZDM_FMZ_ADS_DUPLICATE_PAIRS:
            fixture.extend([rstore, fmz.replace("enable=smzdm_enable", "enable=${smzdm_enable}")])
        result, removed = remove_redundant_smzdm_ads_script_triggers(fixture)
        self.assertEqual(removed, len(SMZDM_FMZ_ADS_DUPLICATE_PAIRS))
        self.assertFalse(any("smzdm_ads.js" in line for line in result))

    def test_preserves_fmz_homepage_dispatch_without_rstore_cover(self):
        from apply_local_overrides import (
            SMZDM_FMZ_HOME_TRIGGER, remove_redundant_smzdm_homepage_script_trigger,
        )
        fixture = ["[Script]", SMZDM_FMZ_HOME_TRIGGER, "[MITM]", "hostname = homepage-api.smzdm.com"]
        result, changed = remove_redundant_smzdm_homepage_script_trigger(fixture)
        self.assertEqual(changed, 0)
        self.assertEqual(result, fixture)

    def test_fails_closed_on_unreviewed_smzdm_homepage_trigger_variants(self):
        from apply_local_overrides import (
            SMZDM_FMZ_HOME_TRIGGER, SMZDM_RSTORE_HOME_TRIGGER,
            remove_redundant_smzdm_homepage_script_trigger,
        )
        drifted = [
            "[Script]", SMZDM_RSTORE_HOME_TRIGGER,
            SMZDM_FMZ_HOME_TRIGGER.replace("v3", "v4"),
            "[MITM]", "hostname = homepage-api.smzdm.com",
        ]
        with self.assertRaisesRegex(ValueError, "SMZDM homepage FMZ trigger inventory changed"):
            remove_redundant_smzdm_homepage_script_trigger(drifted)

        duplicated = [
            "[Script]", SMZDM_RSTORE_HOME_TRIGGER,
            SMZDM_FMZ_HOME_TRIGGER, SMZDM_FMZ_HOME_TRIGGER,
            "[MITM]", "hostname = homepage-api.smzdm.com",
        ]
        with self.assertRaisesRegex(ValueError, "SMZDM homepage FMZ trigger inventory changed"):
            remove_redundant_smzdm_homepage_script_trigger(duplicated)


class SmzdmCoveredAdScriptOptimizationTests(unittest.TestCase):
    def test_removes_three_fmz_ad_triggers_covered_by_rstore(self):
        from apply_local_overrides import (
            SMZDM_FMZ_ADS_DUPLICATE_PAIRS,
            remove_redundant_smzdm_ads_script_triggers,
        )
        fixture = ["[Script]"]
        for _, rstore, fmz in SMZDM_FMZ_ADS_DUPLICATE_PAIRS:
            fixture.extend([rstore, fmz])
        # The list_v10 FMZ trigger is intentionally retained: its R-Store matcher
        # is not proven to cover this exact version/query shape.
        list_v10 = (
            r'response if ${url} ~= /^https?:\/\/s-api\.smzdm\.com\/sou\/list_v10\?/i '
            r'then script("https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/smzdm/smzdm_ads.js") '
            r'with enable=smzdm_enable, tag="什么值得买去广告", timeout=60, requires_body=true'
        )
        fixture.append(list_v10)
        fixture.extend(["[MITM]", "hostname = haojia.m.smzdm.com, haojia-api.smzdm.com, s-api.smzdm.com"])
        result, changed = remove_redundant_smzdm_ads_script_triggers(fixture)
        self.assertEqual(changed, 3)
        for _, rstore, fmz in SMZDM_FMZ_ADS_DUPLICATE_PAIRS:
            self.assertIn(rstore, result)
            self.assertNotIn(fmz, result)
        self.assertIn(list_v10, result)
        again, second_changed = remove_redundant_smzdm_ads_script_triggers(result)
        self.assertEqual(second_changed, 0)
        self.assertEqual(again, result)

    def test_preserves_fmz_ad_trigger_when_rstore_cover_is_missing(self):
        from apply_local_overrides import (
            SMZDM_FMZ_ADS_DUPLICATE_PAIRS, remove_redundant_smzdm_ads_script_triggers,
        )
        _, _, fmz = SMZDM_FMZ_ADS_DUPLICATE_PAIRS[0]
        fixture = ["[Script]", fmz, "[MITM]", "hostname = haojia.m.smzdm.com"]
        result, changed = remove_redundant_smzdm_ads_script_triggers(fixture)
        self.assertEqual(changed, 0)
        self.assertEqual(result, fixture)

    def test_fails_closed_on_unreviewed_fmz_ad_trigger_variant(self):
        from apply_local_overrides import (
            SMZDM_FMZ_ADS_DUPLICATE_PAIRS, remove_redundant_smzdm_ads_script_triggers,
        )
        _, rstore, fmz = SMZDM_FMZ_ADS_DUPLICATE_PAIRS[0]
        drifted = ["[Script]", rstore, fmz.replace("timeout=60", "timeout=30"), "[MITM]"]
        with self.assertRaisesRegex(ValueError, "SMZDM FMZ ad trigger inventory changed"):
            remove_redundant_smzdm_ads_script_triggers(drifted)


class WechatAppletNativeMigrationTests(unittest.TestCase):
    def test_migrates_only_five_simple_applet_handlers_to_native_rules(self):
        from apply_local_overrides import (
            WECHAT_APPLET_NATIVE_MIGRATIONS, migrate_wechat_applet_simple_endpoints,
        )
        fixture = ["[Rewrite]", "response if keep.example then response.json.delete('keep')", "[Script]"]
        for _, _, trigger, _ in WECHAT_APPLET_NATIVE_MIGRATIONS:
            fixture.append(trigger)
        fixture.extend([
            r"http-response ^https?:\/\/miniapp\.sexytea2013\.com\/cms\/slot\/queryByCodes\?codes=INDEX_TOP_BANNER script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/wechatApplet.js,tag=SEXYTEA,requires-body=true",
            "[MITM]",
            "hostname = wechat-api-dj.mstand.cn, coco-com.e.verystar.net, htwkop.xiaojukeji.com, minifm.maxxipoint.com, mapi.xiaotucc.com, miniapp.sexytea2013.com",
        ])
        result, changed = migrate_wechat_applet_simple_endpoints(fixture)
        self.assertEqual(changed, 5)
        for _, _, trigger, replacement in WECHAT_APPLET_NATIVE_MIGRATIONS:
            self.assertNotIn(trigger, result)
            replacements = replacement if isinstance(replacement, tuple) else (replacement,)
            for rule in replacements:
                self.assertIn(rule, result)
        self.assertTrue(any("keep.example" in line for line in result))
        self.assertTrue(any("SEXYTEA" in line for line in result))
        self.assertEqual(sum(1 for line in result if line.startswith("response if") and "mapi" in line), 2)
        again, second_changed = migrate_wechat_applet_simple_endpoints(result)
        self.assertEqual(second_changed, 0)
        self.assertEqual(again, result)

    def test_noops_when_no_known_applet_script_trigger_exists(self):
        from apply_local_overrides import migrate_wechat_applet_simple_endpoints
        fixture = ["[Rewrite]", "[Script]", "http-response ^https?:\\/\\/unknown.example/ script-path=https://example.invalid/a.js", "[MITM]"]
        result, changed = migrate_wechat_applet_simple_endpoints(fixture)
        self.assertEqual(changed, 0)
        self.assertEqual(result, fixture)

    def test_fails_closed_on_unknown_applet_trigger_variant(self):
        from apply_local_overrides import (
            WECHAT_APPLET_NATIVE_MIGRATIONS, migrate_wechat_applet_simple_endpoints,
        )
        trigger = WECHAT_APPLET_NATIVE_MIGRATIONS[0][2]
        drifted = trigger.replace("tag=MSTAND", "tag=MSTAND2")
        fixture = ["[Rewrite]", "[Script]", drifted, "[MITM]"]
        with self.assertRaisesRegex(ValueError, "WeChat applet trigger inventory changed"):
            migrate_wechat_applet_simple_endpoints(fixture)


class WeiboNativeMigrationTests(unittest.TestCase):
    def test_migrates_five_simple_weibo_branches_and_preserves_complex_triggers(self):
        from apply_local_overrides import WEIBO_NATIVE_MIGRATIONS, migrate_weibo_simple_endpoints
        fixture = ["[Rewrite]", "[Script]"]
        for _, _, trigger, _ in WEIBO_NATIVE_MIGRATIONS:
            fixture.append(trigger)
        complex_trigger = (
            r"http-response ^https?:\/\/api\.weibo\.cn\/2\/comments\/build_comments\? "
            r"script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js,tag=WEIBO-4,requires-body=true"
        )
        fixture.extend([complex_trigger, "[MITM]", "hostname = api.weibo.cn, bootpreload.uve.weibo.com, wbapp.uve.weibo.com, new.vip.weibo.cn"])
        result, changed = migrate_weibo_simple_endpoints(fixture)
        self.assertEqual(changed, 5)
        for _, _, trigger, replacement in WEIBO_NATIVE_MIGRATIONS:
            self.assertNotIn(trigger, result)
            self.assertIn(replacement, result)
        self.assertIn(complex_trigger, result)
        self.assertEqual(sum(1 for line in result if line.startswith("response if") and "weibo" in line), 5)
        again, second_changed = migrate_weibo_simple_endpoints(result)
        self.assertEqual(second_changed, 0)
        self.assertEqual(again, result)

    def test_noops_when_no_known_weibo_script_trigger_exists(self):
        from apply_local_overrides import migrate_weibo_simple_endpoints
        fixture = ["[Rewrite]", "[Script]", "http-response ^https?:\\/\\/unknown.example/ script-path=https://example.invalid/weibo.js", "[MITM]"]
        result, changed = migrate_weibo_simple_endpoints(fixture)
        self.assertEqual(changed, 0)
        self.assertEqual(result, fixture)

    def test_fails_closed_on_unreviewed_weibo_trigger_variant(self):
        from apply_local_overrides import WEIBO_NATIVE_MIGRATIONS, migrate_weibo_simple_endpoints
        trigger = WEIBO_NATIVE_MIGRATIONS[0][2]
        drifted = trigger.replace("tag=WEIBO-13", "tag=WEIBO-13-NEW")
        fixture = ["[Rewrite]", "[Script]", drifted, "[MITM]"]
        with self.assertRaisesRegex(ValueError, "Weibo trigger inventory changed"):
            migrate_weibo_simple_endpoints(fixture)


class BilibiliProtobufDuplicateTriggerTests(unittest.TestCase):
    def test_narrows_four_duplicate_binary_triggers_and_keeps_mainlist(self):
        from apply_local_overrides import (
            BILIBILI_PROTOBUF_DUPLICATE_PAIRS, narrow_duplicate_bilibili_protobuf_triggers,
        )
        fmz_trigger = (
            r'response if ${url} ~= /^https?:\/\/(?:grpc\.biliapi\.net|app\.bilibili\.com)\/bilibili\.(?:app\.(?:dynamic\.v2\.Dynamic\/DynAll|view(unite)?\.v1\.View\/View)|community\.service\.dm\.v1\.DM\/DmView|polymer\.app\.search\.v1\.Search\/SearchAll)$/i '
            r'then script("https://raw.githubusercontent.com/kokoryh/Sparkle/refs/heads/master/dist/bilibili.protobuf.response.js") with tag="bilibili.protobuf", requires_body=true'
        )
        mainlist = (
            r"http-response ^https?:\/\/(?:app\.bilibili\.com|grpc\.biliapi\.net)\/bilibili\.main\.community\.reply\.v\d\.Reply\/MainList "
            r"script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliProtoA.js,tag=BAICIZHAN-5,requires-body=true,binary-body-mode=true"
        )
        fixture = ["[Rewrite]", "[Script]", fmz_trigger]
        for _, original, _ in BILIBILI_PROTOBUF_DUPLICATE_PAIRS:
            fixture.append(original)
        fixture.extend([mainlist, "[MITM]", "hostname = grpc.biliapi.net, app.bilibili.com"])
        result, changed = narrow_duplicate_bilibili_protobuf_triggers(fixture)
        self.assertEqual(changed, 4)
        for _, original, narrowed in BILIBILI_PROTOBUF_DUPLICATE_PAIRS:
            self.assertNotIn(original, result)
            self.assertIn(narrowed, result)
        self.assertIn(mainlist, result)
        mainlist_pattern = re.compile(mainlist.split(" script-path=")[0].removeprefix("http-response "))
        self.assertIsNotNone(mainlist_pattern.search("https://grpc.biliapi.net/bilibili.main.community.reply.v1.Reply/MainList"))
        self.assertIsNotNone(mainlist_pattern.search("https://app.bilibili.com/bilibili.main.community.reply.v9.Reply/MainList"))
        import re
        expected_boundaries = {
            "DynAll": ("/bilibili.app.dynamic.v1.Dynamic/DynAll", "/bilibili.app.dynamic.v2.Dynamic/DynAll", "/bilibili.app.dynamic.v9.Dynamic/DynAll"),
            "viewunite": ("/bilibili.app.view.v1.View/View", "/bilibili.app.viewunite.v2.View/View", "/bilibili.app.viewunite.v9.View/View"),
            "DmView": ("/bilibili.community.service.dm.v1.DM/DmView", "/bilibili.community.service.dm.v2.DM/DmView", "/bilibili.community.service.dm.v9.DM/DmView"),
            "SearchAll": ("/bilibili.polymer.app.search.v1.Search/SearchAll", "/bilibili.polymer.app.search.v2.Search/SearchAll", "/bilibili.polymer.app.search.v9.Search/SearchAll"),
        }
        for marker, original, narrowed in BILIBILI_PROTOBUF_DUPLICATE_PAIRS:
            pattern = re.compile(narrowed.split(" script-path=")[0].removeprefix("http-response "))
            v1, v2, v9 = expected_boundaries[marker]
            self.assertEqual(bool(pattern.search("https://app.bilibili.com" + v1)), marker in ("DynAll",))
            self.assertEqual(bool(pattern.search("https://app.bilibili.com" + v2)), marker != "DynAll")
            self.assertTrue(pattern.search("https://grpc.biliapi.net" + v9))
        again, second_changed = narrow_duplicate_bilibili_protobuf_triggers(result)
        self.assertEqual(second_changed, 0)
        self.assertEqual(again, result)

    def test_preserves_broad_rstore_triggers_when_sparkle_cover_is_absent(self):
        from apply_local_overrides import (
            BILIBILI_PROTOBUF_DUPLICATE_PAIRS, narrow_duplicate_bilibili_protobuf_triggers,
        )
        from apply_local_overrides import BILIBILI_PROTOBUF_NON_DUPLICATE_TRIGGER
        fixture = ["[Script]"] + [original for _, original, _ in BILIBILI_PROTOBUF_DUPLICATE_PAIRS] + [BILIBILI_PROTOBUF_NON_DUPLICATE_TRIGGER, "[MITM]"]
        result, changed = narrow_duplicate_bilibili_protobuf_triggers(fixture)
        self.assertEqual(changed, 0)
        self.assertEqual(result, fixture)

    def test_fails_closed_on_unreviewed_protobuf_trigger_or_sparkle_coverage(self):
        from apply_local_overrides import (
            BILIBILI_PROTOBUF_DUPLICATE_PAIRS, narrow_duplicate_bilibili_protobuf_triggers,
        )
        fmz_trigger = (
            r'response if ${url} ~= /^https?:\/\/(?:grpc\.biliapi\.net|app\.bilibili\.com)\/bilibili\.(?:app\.(?:dynamic\.v2\.Dynamic\/DynAll|view(unite)?\.v1\.View\/View)|community\.service\.dm\.v1\.DM\/DmView|polymer\.app\.search\.v1\.Search\/SearchAll)$/i '
            r'then script("https://raw.githubusercontent.com/kokoryh/Sparkle/refs/heads/master/dist/bilibili.protobuf.response.js") with tag="bilibili.protobuf", requires_body=true'
        )
        original = BILIBILI_PROTOBUF_DUPLICATE_PAIRS[0][1]
        drifted = original.replace("tag=BAICIZHAN", "tag=BAICIZHAN-CHANGED")
        with self.assertRaisesRegex(ValueError, "R-Store protobuf trigger variant changed"):
            narrow_duplicate_bilibili_protobuf_triggers(["[Script]", fmz_trigger, drifted, "[MITM]"])

        bad_fmz = fmz_trigger.replace(r"dynamic\.v2", r"dynamic\.v3")
        with self.assertRaisesRegex(ValueError, "Sparkle protobuf endpoint coverage changed"):
            narrow_duplicate_bilibili_protobuf_triggers(["[Script]", bad_fmz, original, "[MITM]"])


class XiaohongshuNativeDuplicateTriggerTests(unittest.TestCase):
    def _fixture(self):
        from apply_local_overrides import XHS_SCRIPT_TRIGGER_LINES, XHS_HOMEFEED_NATIVE_OLD_RULE
        rstore_tags = {"XIAOHONGSHU", "XIAOHONGSHU-2", "XIAOHONGSHU-3", "XIAOHONGSHU-4", "XIAOHONGSHU-5", "XIAOHONGSHU-6", "XIAOHONGSHU-8"}
        scripts = [
            line for line in XHS_SCRIPT_TRIGGER_LINES
            if any(("tag=" + tag + ",") in line for tag in rstore_tags)
            or ('tag="小红书搜索页"' in line and any(marker in line.replace(chr(92), "") for marker in (
                "/search/(banner|hot)_list", "/search/(hint|trending)", "/search/notes"
            )))
        ]
        rewrites = [
            r"^https:\/\/edith\.xiaohongshu\.com\/api\/sns\/v\d\/note\/widgets response-body-json-jq '. as $o | try . catch $o'",
            r"^https:\/\/edith\.xiaohongshu\.com\/api\/sns\/v\d\/search\/banner_list$ response-body-json-jq '. as $o | try . catch $o'",
            r"^https:\/\/edith\.xiaohongshu\.com\/api\/sns\/v\d\/search\/hot_list$ response-body-json-jq '. as $o | try . catch $o'",
            r"^https:\/\/edith\.xiaohongshu\.com\/api\/sns\/v\d\/search\/hint response-body-json-jq '. as $o | try . catch $o'",
            r"^https:\/\/edith\.xiaohongshu\.com\/api\/sns\/v\d\/search\/trending\? response-body-json-jq '. as $o | try . catch $o'",
            r"^https:\/\/(?:edith|so)\.xiaohongshu\.com\/api\/sns\/v\d+\/search\/notes\? response-body-json-jq '. as $o | try . catch $o'",
            r"^https:\/\/edith\.xiaohongshu\.com\/api\/sns\/v\d\/system_service\/config\? response-body-json-jq '. as $o | try . catch $o'",
            r"^https:\/\/(?:edith|rec)\.xiaohongshu\.com\/api\/sns\/v\d+\/followfeed\? response-body-json-jq '. as $o | try (if (.data|type)==\"object\" then (if ((.data.items|type)==\"array\") then .data.items|=map(select(if type==\"object\" then (.recommend_reason!=\"recommend_user\") else false end)) else . end) else . end) catch $o'",
            r"^https:\/\/(?:edith|rec)\.xiaohongshu\.com\/api\/sns\/v2\/user\/followings\/followfeed response-body-json-jq '. as $o | try (if (.data|type)==\"object\" then (if ((.data.items|type)==\"array\") then .data.items|=map(select(if type==\"object\" then (.recommend_reason==\"friend_post\") else false end)) else . end) else . end) catch $o'",
            XHS_HOMEFEED_NATIVE_OLD_RULE,
        ]
        scripts = [line.replace("enable=xhs_enable", "enable=${xhs_enable}") for line in scripts]
        return ["[Rewrite]", *rewrites, "[Script]", *sorted(scripts), "[MITM]"]

    def test_removes_only_native_covered_rstore_search_and_widget_scripts(self):
        from apply_local_overrides import narrow_xiaohongshu_native_response_duplicates
        fixture = self._fixture()
        result, changed = narrow_xiaohongshu_native_response_duplicates(fixture)
        self.assertEqual(changed, 11)
        removed_tags = ("XIAOHONGSHU", "XIAOHONGSHU-3", "XIAOHONGSHU-4", "XIAOHONGSHU-5", "XIAOHONGSHU-6")
        self.assertFalse(any(any(("tag=" + tag + ",") in line for tag in removed_tags) for line in result))
        from apply_local_overrides import XHS_NARROWED_TRIGGER_LINES
        for narrowed in XHS_NARROWED_TRIGGER_LINES.values():
            self.assertIn(narrowed, result)
        import re
        user_follow = re.compile(XHS_NARROWED_TRIGGER_LINES["XIAOHONGSHU-2"].split(" script-path=")[0].removeprefix("http-response "))
        self.assertIsNotNone(user_follow.search("https://edith.xiaohongshu.com/api/sns/v1/user/followings/followfeed"))
        self.assertIsNone(user_follow.search("https://edith.xiaohongshu.com/api/sns/v2/user/followings/followfeed"))
        self.assertIsNotNone(user_follow.search("https://edith.xiaohongshu.com/api/sns/v3/user/followings/followfeed"))
        self.assertIsNotNone(user_follow.search("https://edith.xiaohongshu.com/api/sns/v10/user/followings/followfeed"))
        mixed_feed = re.compile(XHS_NARROWED_TRIGGER_LINES["XIAOHONGSHU-8"].split(" script-path=")[0].removeprefix("http-response "))
        self.assertIsNone(mixed_feed.search("https://edith.xiaohongshu.com/api/sns/v2/homefeed?"))
        self.assertIsNone(mixed_feed.search("https://rec.xiaohongshu.com/api/sns/v2/homefeed?"))
        self.assertIsNotNone(mixed_feed.search("https://www.xiaohongshu.com/api/sns/v2/homefeed?"))
        self.assertIsNotNone(mixed_feed.search("https://www.xiaohongshu.com/api/sns/v2/followfeed?"))
        self.assertIsNone(mixed_feed.search("https://edith.xiaohongshu.com/api/sns/v2/followfeed?"))
        self.assertIsNone(mixed_feed.search("https://rec.xiaohongshu.com/api/sns/v2/followfeed?"))
        from apply_local_overrides import XHS_HOMEFEED_NATIVE_RULE, XHS_HOMEFEED_NATIVE_OLD_RULE
        self.assertIn(XHS_HOMEFEED_NATIVE_RULE, result)
        self.assertFalse(any(line == XHS_HOMEFEED_NATIVE_OLD_RULE for line in result))
        from apply_local_overrides import XHS_HOMEFEED_NATIVE_RULE
        self.assertIn(XHS_HOMEFEED_NATIVE_RULE, result)
        self.assertFalse(any(line == XHS_HOMEFEED_NATIVE_OLD_RULE for line in result))
        fmz = [line for line in result if 'tag="小红书搜索页"' in line]
        self.assertEqual(len(fmz), 3)
        self.assertTrue(all(r"\.rnote\.com" in line for line in fmz))
        self.assertFalse(any(r"(xiaohongshu|rnote)" in line for line in fmz))
        again, second_changed = narrow_xiaohongshu_native_response_duplicates(result)
        self.assertEqual(second_changed, 0)
        self.assertEqual(again, result)

    def test_fails_closed_when_native_search_coverage_is_missing(self):
        from apply_local_overrides import narrow_xiaohongshu_native_response_duplicates
        fixture = self._fixture()
        fixture = [line for line in fixture if "/search/hot_list" not in line.replace(chr(92), "") or "response-body-json-jq" not in line]
        with self.assertRaisesRegex(ValueError, "native JSON coverage missing or duplicated"):
            narrow_xiaohongshu_native_response_duplicates(fixture)

    def test_fails_closed_on_changed_fmz_host_matcher(self):
        from apply_local_overrides import narrow_xiaohongshu_native_response_duplicates
        fixture = self._fixture()
        for i, line in enumerate(fixture):
            if 'tag="小红书搜索页"' in line and "/search/notes" in line.replace(chr(92), ""):
                fixture[i] = line.replace(r"(so|edith)\.(xiaohongshu|rnote)\.com", r"edith\.(xiaohongshu|rnote)\.com")
                break
        with self.assertRaisesRegex(ValueError, "FMZ search trigger inventory changed"):
            narrow_xiaohongshu_native_response_duplicates(fixture)


class XiaohongshuV3VideoNativeDedupTests(unittest.TestCase):
    def _fixture(self):
        from apply_local_overrides import XHS_SCRIPT_TRIGGER_LINES
        rstore = next(line for line in XHS_SCRIPT_TRIGGER_LINES if "tag=XIAOHONGSHU-7," in line)
        fmz = next(
            line for line in XHS_SCRIPT_TRIGGER_LINES
            if line.startswith("response if")
            and 'tag="小红书图片视频水印"' in line
            and "v2/note/feed" in line.replace(chr(92), "")
            and "v3/note/videofeed" in line.replace(chr(92), "")
        )
        native = (
            r"^https:\/\/(?:edith|rec|www)\.xiaohongshu\.com\/api\/sns\/v3\/note\/videofeed "
            r"response-body-json-jq 'function_switch .disable_save=false .disable_watermark=true "
            r".disable_weibo_cover=true video_download'"
        )
        return ["[Rewrite]", native, "[Script]", rstore, fmz, "[MITM]"]

    def test_narrows_only_native_covered_v3_video_scripts(self):
        from apply_local_overrides import (
            XHS_V3_VIDEO_RSTORE_NARROWED_TRIGGER,
            XHS_V3_VIDEO_FMZ_NARROWED_TRIGGER,
            narrow_xiaohongshu_v3_video_native_duplicates,
        )
        import re
        fixture = self._fixture()
        result, changed = narrow_xiaohongshu_v3_video_native_duplicates(fixture)
        self.assertEqual(changed, 2)
        self.assertIn(XHS_V3_VIDEO_RSTORE_NARROWED_TRIGGER, result)
        self.assertIn(XHS_V3_VIDEO_FMZ_NARROWED_TRIGGER, result)
        rstore = re.compile(XHS_V3_VIDEO_RSTORE_NARROWED_TRIGGER.split(" script-path=")[0].removeprefix("http-response "))
        self.assertIsNone(rstore.search("https://edith.xiaohongshu.com/api/sns/v3/note/videofeed"))
        self.assertIsNone(rstore.search("https://edith.xiaohongshu.com/api/sns/v4/note/videofeed"))
        self.assertIsNone(rstore.search("https://edith.xiaohongshu.com/api/sns/v5/note/videofeed"))
        self.assertIsNone(rstore.search("https://www.xiaohongshu.com/api/sns/v1/note/imagefeed"))
        self.assertIsNone(rstore.search("https://rec.xiaohongshu.com/api/sns/v2/note/feed"))
        self.assertIsNone(rstore.search("https://edith.xiaohongshu.com/api/sns/v10/note/video/save"))
        self.assertIsNone(rstore.search("https://edith.xiaohongshu.com/api/sns/v2/note/live_photo/save"))
        self.assertIsNotNone(rstore.search("https://edith.xiaohongshu.com/api/sns/v3/note/feed"))
        self.assertIsNotNone(rstore.search("https://edith.xiaohongshu.com/api/sns/v11/note/video/save"))
        self.assertIsNotNone(rstore.search("https://edith.xiaohongshu.com/api/sns/v1/note/video/save"))
        fmz = re.compile(r"^https?://(?:(?:edith|rec|www)\.(?:xiaohongshu|rnote)\.com/api/sns/v2/note/feed\?|(?:edith|rec|www)\.rnote\.com/api/sns/v3/note/videofeed\?)")
        self.assertIsNotNone(fmz.search("https://edith.xiaohongshu.com/api/sns/v2/note/feed?"))
        self.assertIsNotNone(fmz.search("https://edith.rnote.com/api/sns/v2/note/feed?"))
        self.assertIsNotNone(fmz.search("https://rec.rnote.com/api/sns/v3/note/videofeed?"))
        self.assertIsNone(fmz.search("https://rec.xiaohongshu.com/api/sns/v3/note/videofeed?"))
        again, second_changed = narrow_xiaohongshu_v3_video_native_duplicates(result)
        self.assertEqual(second_changed, 0)
        self.assertEqual(again, result)

    def test_fails_closed_without_native_v3_video_coverage(self):
        from apply_local_overrides import narrow_xiaohongshu_v3_video_native_duplicates
        fixture = self._fixture()
        fixture = [line for line in fixture if "v3/note/videofeed" not in line.replace(chr(92), "")]
        with self.assertRaisesRegex(ValueError, "native JSON coverage missing or duplicated"):
            narrow_xiaohongshu_v3_video_native_duplicates(fixture)

    def test_fails_closed_when_native_v3_video_loses_a_required_operation(self):
        from apply_local_overrides import narrow_xiaohongshu_v3_video_native_duplicates
        fixture = self._fixture()
        fixture[1] = fixture[1].replace("function_switch", "other_switch")
        with self.assertRaisesRegex(ValueError, "no longer covers script behavior"):
            narrow_xiaohongshu_v3_video_native_duplicates(fixture)



class XiaohongshuV4AndCommentMigrationTests(unittest.TestCase):
    def _fixture(self):
        from apply_local_overrides import (
            XHS_FMZ_COMMENT_LIST_TRIGGER, XHS_FMZ_V4_TRIGGER,
            XHS_RSTORE_COMMENT_TRIGGER, XHS_V3_VIDEO_RSTORE_NARROWED_TRIGGER,
            XHS_SCRIPT_TRIGGER_LINES,
        )
        rstore_download = next(line for line in XHS_SCRIPT_TRIGGER_LINES if "tag=XIAOHONGSHU-11," in line)
        fmz_download = next(
            line for line in XHS_SCRIPT_TRIGGER_LINES
            if "v1/interaction/comment/video/download" in line.replace(chr(92), "")
        )
        v4_native = (
            r"^https:\/\/(?:edith|rec|www)\.xiaohongshu\.com\/api\/sns\/v4\/note\/videofeed "
            r"response-body-json-jq 'function_switch disable_save disable_watermark video_download has(\"ad\")'"
        )
        comment_native = (
            r"^https:\/\/edith\.xiaohongshu\.com\/api\/sns\/v\d+\/note\/comment\/list "
            r"response-body-json-jq 'comment_type media_source_type'"
        )
        return [
            "[Rewrite]", v4_native, comment_native,
            "[Script]", XHS_V3_VIDEO_RSTORE_NARROWED_TRIGGER,
            XHS_RSTORE_COMMENT_TRIGGER, XHS_FMZ_V4_TRIGGER,
            XHS_FMZ_COMMENT_LIST_TRIGGER, rstore_download, fmz_download,
            "[MITM]",
        ]

    def test_migrates_v4_filter_into_cached_script_and_removes_duplicate_comment_jq(self):
        from apply_local_overrides import (
            XHS_FMZ_V4_LOCAL_TRIGGER, XHS_FMZ_COMMENT_LIST_TRIGGER,
            XHS_RSTORE_COMMENT_TRIGGER_NARROWED,
            migrate_xiaohongshu_v4_and_comment_processing,
        )
        import re
        fixture = self._fixture()
        result, changed = migrate_xiaohongshu_v4_and_comment_processing(fixture)
        self.assertEqual(changed, 4)
        self.assertIn(XHS_FMZ_V4_LOCAL_TRIGGER, result)
        self.assertIn(XHS_FMZ_COMMENT_LIST_TRIGGER, result)
        self.assertIn(XHS_RSTORE_COMMENT_TRIGGER_NARROWED, result)
        self.assertFalse(any("v4/note/videofeed" in line.replace(chr(92), "") and "response-body-json-jq" in line for line in result))
        self.assertFalse(any("/note/comment/list" in line.replace(chr(92), "") and "response-body-json-jq" in line for line in result))
        self.assertTrue(any("tag=XIAOHONGSHU-11," in line for line in result))
        self.assertTrue(any("v1/interaction/comment/video/download" in line.replace(chr(92), "") for line in result))

        comment = re.compile(XHS_RSTORE_COMMENT_TRIGGER_NARROWED.split(" script-path=")[0].removeprefix("http-response "))
        self.assertIsNotNone(comment.search("https://edith.xiaohongshu.com/api/sns/v3/note/comment/list?"))
        self.assertIsNone(comment.search("https://edith.xiaohongshu.com/api/sns/v3/note/comment/sub_comments?"))
        self.assertIsNone(comment.search("https://edith.xiaohongshu.com/api/sns/v5/note/comment/list?"))
        self.assertIsNotNone(comment.search("https://edith.xiaohongshu.com/api/sns/v5/note/comment/sub_comments?"))
        self.assertIsNotNone(comment.search("https://edith.xiaohongshu.com/api/sns/v10/note/comment/list?"))

        again, second_changed = migrate_xiaohongshu_v4_and_comment_processing(result)
        self.assertEqual(second_changed, 0)
        self.assertEqual(again, result)

    def test_fails_closed_on_v4_native_behavior_or_comment_version_drift(self):
        from apply_local_overrides import migrate_xiaohongshu_v4_and_comment_processing
        fixture = self._fixture()
        drifted = [line.replace("function_switch", "unknown_switch") if "v4/note/videofeed" in line else line for line in fixture]
        with self.assertRaisesRegex(ValueError, "v4 native behavior changed"):
            migrate_xiaohongshu_v4_and_comment_processing(drifted)

        no_fmz_comment = [line for line in fixture if "v5/note/comment/list" not in line.replace(chr(92), "")]
        with self.assertRaisesRegex(ValueError, "FMZ comment-version coverage missing"):
            migrate_xiaohongshu_v4_and_comment_processing(no_fmz_comment)

    def test_local_v4_script_contains_the_merged_ad_filter_and_keeps_cache_paths(self):
        from pathlib import Path
        script = (Path(__file__).parent / "scripts" / "xiaohongshu" / "xiaohongshu-v4.js").read_text(encoding="utf-8")
        self.assertIn('item.model_type === "note"', script)
        self.assertIn('Object.prototype.hasOwnProperty.call(item, "ad")', script)
        self.assertIn('$.setdata(JSON.stringify(videoData), "redBookVideoFeed")', script)
        self.assertIn('/v10/note/video/save', script)




if __name__ == "__main__":
    unittest.main()


class PinduoduoOrderEndpointVariantTests(unittest.TestCase):
    def test_removes_exact_known_order_blocks_without_query_delimiter(self):
        from apply_local_overrides import remove_pdd_order_endpoint_blocks
        known = [
            r"request if ${url} ~= /^https:\/\/api\.pinduoduo\.com\/api\/aristotle\/unrated_order_for_unreceived_tab/i then reject_dict(200)",
            r"request if ${url} ~= /^https:\/\/api\.pinduoduo\.com\/api\/aristotle\/query_order_list_tabs_element/i then reject_dict(200)",
            r"request if ${url} ~= /^https:\/\/api\.pinduoduo\.com\/api\/caterham\/v3\/query\/order_express_group/i then reject_dict(200)",
        ]
        fixture = ["[Rewrite]", *known, "[Script]"]
        result, removed = remove_pdd_order_endpoint_blocks(fixture)
        self.assertEqual(removed, 3)
        self.assertEqual(result, ["[Rewrite]", "[Script]"])
        self.assertEqual(remove_pdd_order_endpoint_blocks(result)[1], 0)

    def test_unknown_pdd_order_endpoint_variant_still_fails_closed(self):
        from apply_local_overrides import remove_pdd_order_endpoint_blocks
        unknown = r"request if ${url} ~= /^https:\/\/api\.pinduoduo\.com\/api\/aristotle\/query_order_list_tabs_element_v2/i then reject_dict(200)"
        with self.assertRaisesRegex(ValueError, "refusing unreviewed removal"):
            remove_pdd_order_endpoint_blocks(["[Rewrite]", unknown])



def _build_amap_unoptimized_fixture():
    from pathlib import Path
    plugin = Path(__file__).parent / "allAdRewrite.plugin"
    lines = plugin.read_text(encoding="utf-8").splitlines()
    markers = (
        "/ws/aos/perception/publictravel/beforenavi",
        "/ws/bus/plan/integrate",
        "/ws/shield/search/nearbyrec_smart",
        "/ws/promotion-web/resource",
    )
    for index, line in enumerate(lines):
        normalized = line.replace(chr(92), "").lower()
        if "/res/scripts/antiad/amap.js" in normalized and any(m in normalized for m in markers):
            lines[index] = line.replace("m[0-46-9]", "m" + chr(92) + "d")
    romeo = "https://raw.githubusercontent.com/ifflagged/Romeo/f056c091074a4c29ad0289d7d31f39d47a4ea3d1/Modules/JavaScript/ishowshu/amap/ishowshu_amap.js"
    duplicates = [
        r'response if ${url} ~= /^https:\/\/m5\.amap\.com\/ws\/aos\/perception\/publicTravel\/beforeNavi\?/i then script("' + romeo + r'") with tag="amap", timeout=60, requires_body=true',
        r'response if ${url} ~= /^https:\/\/m5\.amap\.com\/ws\/shield\/search\/nearbyrec_smart\?/i then script("' + romeo + r'") with tag="amap", timeout=60, requires_body=true',
        r'response if ${url} ~= /^https:\/\/m5-zb\.amap\.com\/ws\/promotion-web\/resource(\/home)?\?/i then script("' + romeo + r'") with tag="amap", timeout=60, requires_body=true',
        r'response if ${url} ~= /^https:\/\/m5\.amap\.com\/ws\/faas\/amap-navigation\/(card-service-plan-home|main-page)/i then script("' + romeo + r'") with tag="amap", timeout=60, requires_body=true',
    ]
    mitm_index = next(i for i, line in enumerate(lines) if line.strip() == "[MITM]")
    lines[mitm_index:mitm_index] = duplicates
    return lines


class BilibiliJsonNativeCoverageTests(unittest.TestCase):
    def test_narrows_only_native_covered_triggers_and_expands_native_filters(self):
        from apply_local_overrides import (
            BILIBILI_JSON_TRIGGER_PAIRS, BILIBILI_NATIVE_PREREQUISITE_MARKERS,
            BILIBILI_NATIVE_RULE_REPLACEMENTS, optimize_bilibili_json_native_coverage,
        )
        fmz_live = (
            r'response if ${url} ~= /^https?:\/\/api\.live\.bilibili\.com\/xlive\/(app-interface\/v2\/index\/feed|app-room\/v1\/index\/getInfoBy(Room|User))\?/i '
            r'then script("https://raw.githubusercontent.com/kokoryh/Sparkle/refs/heads/master/dist/bilibili.json.js") with tag="bilibili.live", requires_body=true'
        )
        account_trigger = (
            r"http-response ^https:\/\/app\.bilibili\.com\/x\/v\d\/account\/(?:mine(\/ipad)?|myinfo)\? "
            r"script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliJson.js,tag=BAICIZHAN-12,requires-body=true"
        )
        pgc_trigger = (
            r"http-response ^https:\/\/api\.bilibili\.com\/pgc\/page\/(?:bangumi|cinema\/tab\?) "
            r"script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliJson.js,tag=BAICIZHAN-7,requires-body=true"
        )
        skin_trigger = (
            r"http-response ^https:\/\/app\.bilibili\.com\/x\/resource\/show\/skin\? "
            r"script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliJson.js,tag=BAICIZHAN-13,requires-body=true"
        )
        sparkle_mine_rule = (
            r'response if ${url} ~= /^https:\\/\\/app\\.bilibili\\.com\\/x\\/v2\\/account\\/mine\\?/ '
            r'then response.json.jq_file("https://raw.githubusercontent.com/kokoryh/Sparkle/refs/heads/master/jq/bilibili.mine.jq")'
        )
        fixture = ["[Rewrite]"]
        fixture.extend(BILIBILI_NATIVE_PREREQUISITE_MARKERS)
        fixture.extend(original for original, _ in BILIBILI_NATIVE_RULE_REPLACEMENTS)
        fixture.append(sparkle_mine_rule)
        fixture.append("[Script]")
        fixture.append(fmz_live)
        fixture.extend(original for _, original, _ in BILIBILI_JSON_TRIGGER_PAIRS)
        fixture.extend([pgc_trigger, account_trigger, skin_trigger, "[MITM]", "hostname = api.live.bilibili.com, app.bilibili.com"])
        result, changed = optimize_bilibili_json_native_coverage(fixture)
        self.assertEqual(changed, 7)
        for _, original, narrowed in BILIBILI_JSON_TRIGGER_PAIRS:
            self.assertNotIn(original, result)
            self.assertIn(narrowed, result)
        for original, updated in BILIBILI_NATIVE_RULE_REPLACEMENTS:
            self.assertNotIn(original, result)
            self.assertIn(updated, result)
        self.assertIn(account_trigger, result)
        self.assertIn(sparkle_mine_rule, result)  # Not equivalent to BAICIZHAN-12; retain both safely.
        splash_matcher = next(line for line in result if "tag=BAICIZHAN-11" in line)
        import re
        splash_pattern = re.compile(splash_matcher.split(" script-path=")[0].removeprefix("http-response "))
        self.assertIsNotNone(splash_pattern.search("https://app.bilibili.com/x/v3/splash/show?"))
        self.assertIsNotNone(splash_pattern.search("https://app.bilibili.com/x/v2/splash/brand/list?"))
        self.assertIsNone(splash_pattern.search("https://app.bilibili.com/x/v2/splash/show?"))
        self.assertIsNone(splash_pattern.search("https://app.bilibili.com/x/v2/splash/list?"))
        again, second_changed = optimize_bilibili_json_native_coverage(result)
        self.assertEqual(second_changed, 0)
        self.assertEqual(again, result)

    def test_noops_when_no_rstore_bilibili_json_script_is_present(self):
        from apply_local_overrides import optimize_bilibili_json_native_coverage
        fixture = ["[Rewrite]", "response if unrelated then response.body.mock(404)", "[Script]", "[MITM]"]
        result, changed = optimize_bilibili_json_native_coverage(fixture)
        self.assertEqual(changed, 0)
        self.assertEqual(result, fixture)

    def test_fails_closed_when_native_or_sparkle_coverage_changes(self):
        from apply_local_overrides import (
            BILIBILI_JSON_TRIGGER_PAIRS, BILIBILI_NATIVE_PREREQUISITE_MARKERS,
            BILIBILI_NATIVE_RULE_REPLACEMENTS, optimize_bilibili_json_native_coverage,
        )
        fmz_live = (
            r'response if ${url} ~= /^https?:\/\/api\.live\.bilibili\.com\/xlive\/(app-interface\/v2\/index\/feed|app-room\/v1\/index\/getInfoBy(Room|User))\?/i '
            r'then script("https://raw.githubusercontent.com/kokoryh/Sparkle/refs/heads/master/dist/bilibili.json.js") with tag="bilibili.live", requires_body=true'
        )
        pgc_trigger = (
            r"http-response ^https:\/\/api\.bilibili\.com\/pgc\/page\/(?:bangumi|cinema\/tab\?) "
            r"script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliJson.js,tag=BAICIZHAN-7,requires-body=true"
        )
        account_trigger = (
            r"http-response ^https:\/\/app\.bilibili\.com\/x\/v\d\/account\/(?:mine(\/ipad)?|myinfo)\? "
            r"script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliJson.js,tag=BAICIZHAN-12,requires-body=true"
        )
        skin_trigger = (
            r"http-response ^https:\/\/app\.bilibili\.com\/x\/resource\/show\/skin\? "
            r"script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliJson.js,tag=BAICIZHAN-13,requires-body=true"
        )
        fixture = ["[Rewrite]", *BILIBILI_NATIVE_PREREQUISITE_MARKERS,
                   *(old for old, _ in BILIBILI_NATIVE_RULE_REPLACEMENTS),
                   "[Script]", fmz_live,
                   *(old for _, old, _ in BILIBILI_JSON_TRIGGER_PAIRS),
                   pgc_trigger, account_trigger, skin_trigger, "[MITM]"]
        changed_trigger = BILIBILI_JSON_TRIGGER_PAIRS[0][1].replace("tag=BAICIZHAN-8", "tag=BAICIZHAN-8-NEW")
        drifted = [changed_trigger if line == BILIBILI_JSON_TRIGGER_PAIRS[0][1] else line for line in fixture]
        with self.assertRaisesRegex(ValueError, "trigger variant changed"):
            optimize_bilibili_json_native_coverage(drifted)

        bad_fmz = fmz_live.replace(r"app-room\/v1", r"app-room\/v3")
        bad_fmz_fixture = [bad_fmz if line == fmz_live else line for line in fixture]
        with self.assertRaisesRegex(ValueError, "live JSON native coverage changed"):
            optimize_bilibili_json_native_coverage(bad_fmz_fixture)

        missing_native = [line for line in fixture if line != BILIBILI_NATIVE_RULE_REPLACEMENTS[0][0]]
        with self.assertRaisesRegex(ValueError, "native response rule changed"):
            optimize_bilibili_json_native_coverage(missing_native)



    def test_amap_response_script_overlap_cleanup_preserves_coverage_and_reduces_body_scripts(self):
        from pathlib import Path
        from apply_local_overrides import (
            apply, AMAP_VERSIONED_RSTORE_SCRIPT_MARKERS,
            AMAP_ISHOWSHU_REDUNDANT_SCRIPT_MARKERS,
            optimize_amap_response_script_overlaps,
        )
        plugin = Path(__file__).parent / "allAdRewrite.plugin"
        original = plugin.read_text(encoding="utf-8")
        fixture = _build_amap_unoptimized_fixture()
        result, removed = optimize_amap_response_script_overlaps(fixture)
        self.assertEqual(removed, 4)
        script = "\n".join(result).split("[Script]", 1)[1].split("[MITM]", 1)[0]
        for marker in AMAP_ISHOWSHU_REDUNDANT_SCRIPT_MARKERS:
            self.assertFalse(any(
                marker in line.replace(chr(92), "").lower() and "ishowshu_amap.js" in line.lower()
                for line in script.splitlines()
            ), marker)
        # Bus-plan iShowshu is intentionally retained: it additionally removes
        # hkfRecommendPlans, which the native rewrite does not cover.
        self.assertTrue(any(
            "/ws/bus/plan/integrate" in line.replace(chr(92), "").lower() and "ishowshu_amap.js" in line.lower()
            for line in script.splitlines()
        ))
        for marker in AMAP_VERSIONED_RSTORE_SCRIPT_MARKERS:
            rows = [
                line for line in script.splitlines()
                if marker in line.replace(chr(92), "").lower() and "/res/scripts/antiad/amap.js" in line.lower()
            ]
            self.assertEqual(len(rows), 1, marker)
            self.assertIn("m[0-46-9]", rows[0], marker)
            self.assertNotRegex(rows[0], r"m\\+d")
        self.assertIn("sources/amap/rucu6_amap.js", script)
        second, second_removed = optimize_amap_response_script_overlaps(result)
        self.assertEqual(second, result)
        self.assertEqual(second_removed, 0)
        generated = apply(original)
        self.assertEqual(generated, apply(generated))

    def test_amap_overlap_cleanup_preserves_original_when_canonical_cover_is_missing(self):
        from pathlib import Path
        from apply_local_overrides import (
            AMAP_ISHOWSHU_REDUNDANT_SCRIPT_MARKERS,
            optimize_amap_response_script_overlaps,
        )
        plugin = Path(__file__).parent / "allAdRewrite.plugin"
        lines = _build_amap_unoptimized_fixture()
        before_marker = AMAP_ISHOWSHU_REDUNDANT_SCRIPT_MARKERS[0]
        without_native = [
            line for line in lines
            if not (before_marker in line.replace(chr(92), "").lower() and "response.json.jq(" in line)
        ]
        preserved, _ = optimize_amap_response_script_overlaps(without_native)
        preserved_script = "\n".join(preserved).split("[Script]", 1)[1].split("[MITM]", 1)[0]
        self.assertTrue(any(
            before_marker in line.replace(chr(92), "").lower() and "ishowshu_amap.js" in line.lower()
            for line in preserved_script.splitlines()
        ))
        nearby_marker = AMAP_ISHOWSHU_REDUNDANT_SCRIPT_MARKERS[1]
        without_local = [
            line for line in lines
            if not (nearby_marker in line.replace(chr(92), "").lower() and "sources/amap/rucu6_amap.js" in line.lower())
        ]
        preserved, _ = optimize_amap_response_script_overlaps(without_local)
        preserved_script = "\n".join(preserved).split("[Script]", 1)[1].split("[MITM]", 1)[0]
        self.assertTrue(any(
            nearby_marker in line.replace(chr(92), "").lower() and "ishowshu_amap.js" in line.lower()
            for line in preserved_script.splitlines()
        ))

    def test_amap_overlap_cleanup_rejects_ambiguous_duplicate_canonical_handlers(self):
        from apply_local_overrides import (
            AMAP_ISHOWSHU_REDUNDANT_SCRIPT_MARKERS,
            optimize_amap_response_script_overlaps,
        )
        marker = AMAP_ISHOWSHU_REDUNDANT_SCRIPT_MARKERS[1]
        canonical = (
            'response if ${url} ~= /^https:\\/\\/m5\\.amap\\.com\\/ws\\/shield\\/search\\/nearbyrec_smart\\?/i '
            'then script("https://raw.githubusercontent.com/XcvcvX/loon-change/main/sources/amap/rucu6_amap.js") '
            'with tag="local", requires_body=true'
        )
        fixture = [
            "[Rewrite]",
            "[Script]",
            canonical,
            canonical,
            "[MITM]",
        ]
        with self.assertRaisesRegex(ValueError, "duplicate canonical local Amap trigger"):
            optimize_amap_response_script_overlaps(fixture)


class PinduoduoHomepageNativeConsolidationTests(unittest.TestCase):
    def setUp(self):
        from pathlib import Path
        self.plugin = Path(__file__).parent / "allAdRewrite.plugin"
        self.lines = self.plugin.read_text(encoding="utf-8").splitlines()

    def test_replaces_split_native_and_script_homepage_processing_with_one_jq_pass(self):
        from apply_local_overrides import (
            PDD_HOMEPAGE_NATIVE_JQ_RULE,
            consolidate_pdd_homepage_native_response,
        )
        from apply_local_overrides import PDD_HOMEPAGE_NATIVE_JQ_RULE, PDD_LOCAL_HOMEPAGE_TRIGGER
        fixture = ["[Rewrite]", PDD_HOMEPAGE_NATIVE_JQ_RULE, "[Script]", PDD_LOCAL_HOMEPAGE_TRIGGER, "[MITM]"]
        result, removed = consolidate_pdd_homepage_native_response(fixture)
        self.assertEqual(removed, 1)
        self.assertIn(PDD_HOMEPAGE_NATIVE_JQ_RULE, result)
        self.assertFalse(any("scripts/pinduoduo/pdd-homepage.js" in line for line in result))
        self.assertEqual(consolidate_pdd_homepage_native_response(result), (result, 0))

    def test_pdd_native_jq_covers_the_merged_script_behavior(self):
        from pathlib import Path
        from apply_local_overrides import PDD_HOMEPAGE_NATIVE_JQ_RULE
        script = (Path(__file__).parent / "scripts/pinduoduo/pdd-homepage.js").read_text(encoding="utf-8")
        for marker in (
            "delete result.dy_module.irregular_banner_dy",
            "delete result.icon_set",
            "delete result.search_bar_hot_query",
            "allowedTitles",
            "allowedLinks",
            "result.all_top_opts = []",
            "removedModules",
            "result.module_order",
        ):
            self.assertIn(marker, script)
        for marker in (
            "result.dy_module.irregular_banner_dy",
            "result.icon_set",
            "result.search_bar_hot_query",
            ".result.bottom_tabs",
            ".result.buffer_bottom_tabs",
            ".result.all_top_opts? |=",
            ".result.module_order",
        ):
            self.assertIn(marker, PDD_HOMEPAGE_NATIVE_JQ_RULE)
        self.assertEqual(PDD_HOMEPAGE_NATIVE_JQ_RULE.count("response.json.jq("), 1)
        self.assertNotIn("response.json.delete(", PDD_HOMEPAGE_NATIVE_JQ_RULE)


    def test_pdd_homepage_jq_filter_compiles_and_matches_expected_semantics(self):
        import json
        import shutil
        import subprocess
        from apply_local_overrides import PDD_HOMEPAGE_NATIVE_JQ_RULE
        if not shutil.which("jq"):
            self.skipTest("jq CLI is unavailable")
        expression = PDD_HOMEPAGE_NATIVE_JQ_RULE.split('response.json.jq("', 1)[1].rsplit('")', 1)[0]
        expression = expression.replace(chr(92) + '"', '"')
        sample = {
            "result": {
                "dy_module": {"irregular_banner_dy": {}, "keep": True},
                "icon_set": {},
                "search_bar_hot_query": [],
                "bottom_tabs": [
                    {"title": "首页", "link": "index.html"},
                    {"title": "多多视频", "link": "video.html"},
                    {"title": "聊天", "link": "chat_list.html"},
                    {"title": "个人中心", "link": "personal.html"},
                    {"title": "错误标题", "link": "chat_list.html"},
                ],
                "buffer_bottom_tabs": [
                    {"link": "personal.html"}, {"link": "video.html"}
                ],
                "all_top_opts": [{"image": "ad"}],
                "module_order": [
                    {"module_name": "ad_module"},
                    {"module_name": "goods"},
                    None,
                ],
            }
        }
        result = subprocess.run(
            ["jq", expression],
            input=json.dumps(sample, ensure_ascii=False),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        data = output["result"]
        self.assertNotIn("irregular_banner_dy", data["dy_module"])
        self.assertNotIn("icon_set", data)
        self.assertNotIn("search_bar_hot_query", data)
        self.assertEqual([x["title"] for x in data["bottom_tabs"]], ["首页", "聊天", "个人中心"])
        self.assertEqual(data["buffer_bottom_tabs"], [{"link": "personal.html"}])
        self.assertEqual(data["all_top_opts"], [])
        self.assertEqual(data["module_order"], [{"module_name": "goods"}])

    def test_pdd_homepage_native_rule_is_preserved_without_local_script_trigger(self):
        from apply_local_overrides import consolidate_pdd_homepage_native_response
        without_script = [
            line for line in self.lines
            if "scripts/pinduoduo/pdd-homepage.js" not in line
        ]
        result, removed = consolidate_pdd_homepage_native_response(without_script)
        self.assertEqual(removed, 0)
        self.assertEqual(result, without_script)

    def test_pdd_homepage_native_rule_fails_closed_on_drift_or_duplicates(self):
        from apply_local_overrides import consolidate_pdd_homepage_native_response
        from apply_local_overrides import PDD_HOMEPAGE_NATIVE_JQ_RULE, PDD_LOCAL_HOMEPAGE_TRIGGER
        fixture = ["[Rewrite]", PDD_HOMEPAGE_NATIVE_JQ_RULE, "[Script]", PDD_LOCAL_HOMEPAGE_TRIGGER, "[MITM]"]
        changed = [
            line.replace("result.all_top_opts", "result.all_top_options")
            if "alexa" in line and "response.json.jq" in line else line
            for line in fixture
        ]
        with self.assertRaisesRegex(ValueError, "Pinduoduo homepage native rule changed"):
            consolidate_pdd_homepage_native_response(changed)
        duplicate = list(fixture)
        native = PDD_HOMEPAGE_NATIVE_JQ_RULE
        script_index = next(i for i, line in enumerate(duplicate) if line.strip() == "[Script]")
        duplicate.insert(script_index, native)
        with self.assertRaisesRegex(ValueError, "duplicate Pinduoduo homepage native response rule"):
            consolidate_pdd_homepage_native_response(duplicate)

