#!/usr/bin/env python3
"""Apply durable local Loon plugin overrides after upstream merge."""
from pathlib import Path
import argparse
import re

RULE = (r'response if ${url} ~= /^https?:\/\/creditcard\.bankcomm\.(?:cn|com)\/tofimg\/bucket-pj-btss-tfcn-dmz\/OSS-F\/.+/i '
        'then script("https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/maidanba.js") '
        'with tag="买单吧开屏广告", requires_body=true, binary_body_mode=true')

LEGACY_HELLOBIKE_MARKER = "scripts/hellobike-clean.js"
HELLOBIKE_SOURCE = "ZenmoFeiShi-Qx-HelloBike(ScriptHub-Loon)"
HELLOBIKE_ADDED_MITM_HOSTS = {
    "taxiapi.hellobike.com",
    "marketingapi.hellobike.com",
    "entertainment.hellobike.com",
    "resource.51downapp.cn",
    "api-htp.beizi.biz",
    "adservice.sigmob.cn",
    "tm.sigmob.cn",
    "mi.gdt.qq.com",
    "v2mi.gdt.qq.com",
}
# 拼多多 HTTPDNS IPv4 规则必须以查询路径边界结束：/d、/d4? 可命中，/download 不应命中。
PDD_HTTPDNS_MARKER = "com.xunmeng.pinduoduo"
PDD_HTTPDNS_OLD_SUFFIX = r"\/d(\d)?"
PDD_HTTPDNS_NEW_SUFFIX = r"\/d(\d)?(?:\?|$)"
PDD_HTTPDNS_IPV4_MARKER = r"(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
PDD_HTTPDNS_IPV6_MARKER = r"\[[0-9a-fA-F:]+\]"
PDD_HTTPDNS_IPV6_SUFFIX = r"\/d(\d)?\?"
PDD_HTTPDNS_IPV6_PREVIOUS_BAD_SUFFIX = PDD_HTTPDNS_NEW_SUFFIX + r"\?"

REQUIRED_BANKCOMM_MITM_HOSTS = {
    "creditcard.bankcomm.cn", "creditcard.bankcomm.com",
    "creditcardapp.bankcomm.cn", "creditcardapp.bankcomm.com",
}
HELLOBIKE_REWRITE_MARKERS = (
    "api-htp.beizi.biz",
    "adservice.sigmob.cn",
    "tm.sigmob.cn",
    "mi.gdt.qq.com",
    "v2mi.gdt.qq.com",
)
HELLOBIKE_SCRIPT_MARKERS = (
    "script.hub/convert/_start_/",
    "tag=easybike-ad",
)

# Soul 青少年配置：较早的 http(s) 规则已覆盖后续仅 HTTPS 的同路径规则。
SOUL_TEENAGER_CONFIG_BROAD_RULE = r"^https?:\/\/api-account\.soulapp\.cn\/teenager\/config reject-dict"
SOUL_TEENAGER_CONFIG_HTTPS_RULE = r"^https:\/\/api-account\.soulapp\.cn\/teenager\/config reject-dict"

PEOPLEAPP_HOME_AD_BROAD_RULE = r"^https?:\/\/app\.peopleapp\.com\/Api\/\d+/HomeApi\/(?:adv|getAdvertImage) reject"
PEOPLEAPP_HOME_AD_SHADOW_RULE = r"request if ${url} ~= /^https?:\/\/app\.peopleapp\.com\/Api\/\d+\/HomeApi\/(adv|getAdvertImage)/ then reject(404)"

# A second PeopleApp homepage ad blocker differs only by a capturing vs
# non-capturing group. Keep the first exact rule; both have identical scope/action.
PEOPLEAPP_HOME_AD_DUPLICATE_RULES = (
    PEOPLEAPP_HOME_AD_SHADOW_RULE.replace("/(adv|getAdvertImage)/", "/(?:adv|getAdvertImage)/"),
    PEOPLEAPP_HOME_AD_SHADOW_RULE,
)


def remove_duplicate_peopleapp_home_ad_rules(lines):
    """Remove the second exact matcher only when its equivalent first rule exists."""
    counts = {rule: 0 for rule in PEOPLEAPP_HOME_AD_DUPLICATE_RULES}
    for line in lines:
        value = line.strip()
        if value.startswith("request if ${url}") and "peopleapp" in value and "HomeApi" in value and ("adv" in value or "getAdvertImage" in value):
            if value not in counts:
                # Preserve new upstream matchers; only deduplicate the reviewed exact pair.
                continue
            counts[value] += 1
            if counts[value] > 1:
                raise ValueError("duplicate PeopleApp homepage ad rule; refusing ambiguous cleanup")

    canonical_count, duplicate_count = (counts[rule] for rule in PEOPLEAPP_HOME_AD_DUPLICATE_RULES)
    if canonical_count == 0 or duplicate_count == 0:
        # A lone rule may be an upstream revision or an already-cleaned result.
        # Preserve it; never delete without the exact covering counterpart.
        return list(lines), 0

    output = [
        line for line in lines
        if line.strip() != PEOPLEAPP_HOME_AD_DUPLICATE_RULES[1]
    ]
    return output, 1


PEOPLEAPP_IMAGE_AD_BROAD_RULE = r"^https?:\/\/adstatic\.peopleapp\.com\/upload\/AppLoad\/.*\.(?:jpg|png) reject-200"
PEOPLEAPP_IMAGE_AD_SHADOW_RULE = r"request if ${url} ~= /^https?:\/\/adstatic\.peopleapp\.com\/upload\/AppLoad\/.*\.(jpg|png)/ then reject(200)"

def remove_shadowed_peopleapp_rules(lines):
    output, home_broad_seen, image_broad_seen, removed = [], False, False, 0
    for line in lines:
        value = line.strip()
        if value == PEOPLEAPP_HOME_AD_BROAD_RULE:
            home_broad_seen = True
        if value == PEOPLEAPP_IMAGE_AD_BROAD_RULE:
            image_broad_seen = True
        if value == PEOPLEAPP_HOME_AD_SHADOW_RULE and home_broad_seen:
            removed += 1
            continue
        if value == PEOPLEAPP_IMAGE_AD_SHADOW_RULE and image_broad_seen:
            removed += 1
            continue
        output.append(line)
    return output, removed

def remove_subsumed_soul_teenager_rule(lines):
    output, broad_seen, removed = [], False, 0
    for line in lines:
        value = line.strip()
        if value == SOUL_TEENAGER_CONFIG_BROAD_RULE:
            broad_seen = True
        if value == SOUL_TEENAGER_CONFIG_HTTPS_RULE and broad_seen:
            removed += 1
            continue
        output.append(line)
    return output, removed


SHADOWED_TERMINAL_BLOCK_RULE_PAIRS = (
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

def remove_shadowed_terminal_block_rules(lines):
    guards = {guard for guard, _ in SHADOWED_TERMINAL_BLOCK_RULE_PAIRS}
    shadow_to_guard = {shadow: guard for guard, shadow in SHADOWED_TERMINAL_BLOCK_RULE_PAIRS}
    output, seen_guards, removed = [], set(), 0
    for line in lines:
        value = line.strip()
        guard = shadow_to_guard.get(value)
        if guard is not None and guard in seen_guards:
            removed += 1
            continue
        if value in guards:
            seen_guards.add(value)
        output.append(line)
    return output, removed

LKCOFFEE_MEMBER_EXCHANGE_MARKER = "m.lkcoffee.com/ecapi/resource/m/member/exchange/page"

def remove_lkcoffee_member_exchange_success_overrides(lines):
    """Drop only the known whole-response SUCCESS rewrites on the member exchange endpoint."""
    output, removed = [], 0
    for line in lines:
        normalized = re.sub(r"\\+", "", line).lower()
        if LKCOFFEE_MEMBER_EXCHANGE_MARKER not in normalized:
            output.append(line)
            continue
        expected_operation = (
            "response-body-replace-regex" in normalized
            or "response.body.replace" in normalized
        )
        forced_success = '"status":"success"' in normalized
        if expected_operation and forced_success:
            removed += 1
            continue
        raise ValueError(
            "Luckin member-exchange response rule changed; refusing an unreviewed override"
        )
    return output, removed



GUIDERANK_SPECIAL_SALE_MARKER = "zone.guiderank-app.com/guiderank-web/app/common/getInitData"
GUIDERANK_SPECIAL_SALE_MATCHER = "^https?://zone.guiderank-app.com/guiderank-web/app/common/getInitData"
GUIDERANK_SPECIAL_SALE_OLD_ACTION = "response-body-replace-regex SpecialSalePageMidTabConfig random_body"
GUIDERANK_SPECIAL_SALE_NEW_ACTION = "response-body-json-del data.SpecialSalePageMidTabConfig"

def replace_guiderank_special_sale_random_body(lines):
    """Replace only the reviewed Guiderank promo-field randomization with JSON deletion."""
    output, replaced = [], 0
    for line in lines:
        normalized = re.sub(r"\\+", "", line.strip())
        if GUIDERANK_SPECIAL_SALE_MARKER.lower() not in normalized.lower():
            output.append(line)
            continue
        if normalized == GUIDERANK_SPECIAL_SALE_MATCHER + " " + GUIDERANK_SPECIAL_SALE_OLD_ACTION:
            output.append(line[:-len(GUIDERANK_SPECIAL_SALE_OLD_ACTION)] + GUIDERANK_SPECIAL_SALE_NEW_ACTION)
            replaced += 1
            continue
        if normalized == GUIDERANK_SPECIAL_SALE_MATCHER + " " + GUIDERANK_SPECIAL_SALE_NEW_ACTION:
            output.append(line)
            continue
        raise ValueError("Guiderank SpecialSalePageMidTabConfig rule changed; refusing an unreviewed rewrite")
    return output, replaced

GUIDERANK_HOMEPAGE_SCRIPT_MARKER = "zone.guiderank-app.com/guiderank-web/app/home/getHomePageV"
GUIDERANK_HOMEPAGE_SCRIPT_TRIGGER = r'http-response ^https?:\/\/zone\.guiderank-app\.com\/guiderank-web\/app\/home\/getHomePageV script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/guiderank.js,tag=GUIDERANK,requires-body=true'
GUIDERANK_HOMEPAGE_NATIVE_RULE = r'response if ${url} ~= /^https?:\/\/zone\.guiderank-app\.com\/guiderank-web\/app\/home\/getHomePageV/ then response.json.delete(["data.countdownBanner", "data.newEvaluations", "data.freeToPayBannerPhotoUrl", "data.groupBuyingList", "data.multiCountdownBanner", "data.banners", "data.multiPlatformBanner", "data.specialSaleBannerPhotoUrl", "data.guide90Evaluation", "data.insurancePromotions"])'

def remove_guiderank_homepage_script(lines):
    """Replace only the reviewed Guiderank homepage response script trigger."""
    output, removed, section = [], 0, ""
    normalized_trigger = re.sub(r"\\+", "", GUIDERANK_HOMEPAGE_SCRIPT_TRIGGER.strip())
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue
        normalized = re.sub(r"\\+", "", line.strip())
        if section != "Script" or GUIDERANK_HOMEPAGE_SCRIPT_MARKER.lower() not in normalized.lower():
            output.append(line)
            continue
        if normalized == normalized_trigger:
            removed += 1
            continue
        raise ValueError("Guiderank homepage script trigger changed; refusing an unreviewed conversion")
    if removed > 1:
        raise ValueError("duplicate Guiderank homepage script triggers; refusing ambiguous conversion")
    return output, removed


GAODING_TEMPLATE_SCRIPT_TRIGGER = r"http-response ^https?:\/\/www\.gaoding\.com\/api\/v\d\/oc\/exhibitions\/template\/resources$ script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/gaoding.js,tag=GAODING,requires-body=true"
GAODING_MINE_SCRIPT_TRIGGER = r"http-response ^https?:\/\/www\.gaoding\.com\/api\/v\d\/oc\/exhibitions\/app_mine\/resources script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/gaoding.js,tag=GAODING-2,requires-body=true"
GAODING_NATIVE_RULES = (
    r'response if ${url} ~= /^https?:\/\/www\.gaoding\.com\/api\/v\d\/oc\/exhibitions\/template\/resources$/ then response.json.delete("pits[0].delivery_materials")',
    r'response if ${url} ~= /^https?:\/\/www\.gaoding\.com\/api\/v\d\/oc\/exhibitions\/app_mine\/resources/ then response.json.delete("pits[2].delivery_materials")',
)


def remove_gaoding_resource_scripts(lines):
    """Replace only the two reviewed Gaoding resource-field deletion script triggers."""
    output, removed = [], {GAODING_TEMPLATE_SCRIPT_TRIGGER: 0, GAODING_MINE_SCRIPT_TRIGGER: 0}
    section = ""
    expected = {
        re.sub(r"\\+", "", GAODING_TEMPLATE_SCRIPT_TRIGGER.strip()): GAODING_TEMPLATE_SCRIPT_TRIGGER,
        re.sub(r"\\+", "", GAODING_MINE_SCRIPT_TRIGGER.strip()): GAODING_MINE_SCRIPT_TRIGGER,
    }
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue
        normalized = re.sub(r"\\+", "", line.strip())
        if section != "Script" or "www.gaoding.com/api/" not in normalized or "/oc/exhibitions/" not in normalized:
            output.append(line)
            continue
        if normalized not in expected:
            raise ValueError("Gaoding resource script trigger changed; refusing an unreviewed conversion")
        trigger = expected[normalized]
        removed[trigger] += 1
        if removed[trigger] > 1:
            raise ValueError("duplicate Gaoding resource script triggers; refusing ambiguous conversion")
    return output, tuple(trigger for trigger, count in removed.items() if count)




# 拼多多首页由 R-Store 与 ishowshu 两份脚本重复处理同一响应。
# 合并为仓库内单脚本，保留两份脚本及原生 JSON 规则的并集行为。
PDD_RSTORE_HOMEPAGE_TRIGGER = r"http-response ^https?:\/\/api\.pinduoduo\.com\/api\/alexa\/\w+\/hub script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/pdd.js,tag=PDD-2,requires-body=true"
PDD_LOCAL_HOMEPAGE_TRIGGER = r"http-response ^https?:\/\/api\.pinduoduo\.com\/api\/alexa\/homepage\/hub script-path=https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/pinduoduo/pdd-homepage.js,tag=PDD-2,requires-body=true"
PDD_LOCAL_HOMEPAGE_RELATIVE_TRIGGER = r"http-response ^https?:\/\/api\.pinduoduo\.com\/api\/alexa\/homepage\/hub script-path=scripts/pinduoduo/pdd-homepage.js,tag=PDD-2,requires-body=true"
# Romeo 当前 ishowshu/pdd-rewrite 插件已从旧 http-response script-path 迁移为 Loon response/script 语法。
PDD_ISHOWSHU_HOMEPAGE_TRIGGER = r'response if ${url} ~= /^https:\\/\\/api\\.pinduoduo\\.com\\/api\\/alexa\\/homepage\\/hub/i then script("https://github.com/ifflagged/Romeo/raw/main/Modules/JavaScript/ishowshu/pdd-rewrite/ishowshu_pdd.js") with tag="pdd", timeout=60, requires_body=true'
PDD_ISHOWSHU_HOMEPAGE_LEGACY_TRIGGER = r"http-response ^https:\/\/api\.pinduoduo\.com\/api\/alexa\/homepage\/hub script-path = https://github.com/ishowshu/qx/raw/refs/heads/main/script/pdd.js, requires-body = true, tag = 拼多多首页简化(底部菜单、顶部分类)"


def consolidate_pdd_homepage_script(lines):
    """Replace two overlapping PDD homepage scripts with one behavior-preserving local handler."""
    output, section = [], ""
    counts = {"rstore": 0, "local": 0, "ishowshu": 0}
    def normalize_trigger(value):
        value = re.sub(r"\\+", "", value.strip())
        return re.sub(
            r"https://raw\.githubusercontent\.com/ifflagged/Romeo/[0-9a-f]{40}/",
            "https://github.com/ifflagged/Romeo/raw/main/",
            value,
        )

    normalized_triggers = {
        normalize_trigger(PDD_RSTORE_HOMEPAGE_TRIGGER): "rstore",
        normalize_trigger(PDD_LOCAL_HOMEPAGE_TRIGGER): "local",
        normalize_trigger(PDD_LOCAL_HOMEPAGE_RELATIVE_TRIGGER): "local",
        normalize_trigger(PDD_ISHOWSHU_HOMEPAGE_TRIGGER): "ishowshu",
        normalize_trigger(PDD_ISHOWSHU_HOMEPAGE_LEGACY_TRIGGER): "ishowshu",
    }
    target_seen = False
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue
        normalized = normalize_trigger(line)
        is_target = (section == "Script" and "api.pinduoduo.com/api/alexa/" in normalized
                     and ("script-path" in normalized or "script(" in normalized))
        if not is_target:
            output.append(line)
            continue
        target_seen = True
        kind = normalized_triggers.get(normalized)
        if kind is None:
            raise ValueError("Pinduoduo homepage script trigger changed; refusing unreviewed consolidation: " + line.strip())
        counts[kind] += 1
        if counts[kind] > 1:
            raise ValueError("duplicate Pinduoduo homepage script trigger; refusing ambiguous consolidation")
        if kind == "ishowshu":
            continue
        if kind in ("rstore", "local"):
            # Normalize the repository-relative script reference to the hosted URL
            # used by the published aggregate plugin.
            output.append(PDD_LOCAL_HOMEPAGE_TRIGGER)

    if not target_seen:
        return output, 0
    if counts["rstore"] + counts["local"] != 1:
        raise ValueError("Pinduoduo canonical homepage script inventory changed; expected exactly one R-Store/local trigger")
    return output, counts["ishowshu"] + counts["rstore"]



PDD_HOMEPAGE_NATIVE_JQ_RULE = "response if ${url} ~= /^https:\\/\\/api\\.pinduoduo\\.com\\/api\\/alexa\\/homepage\\/hub\\?/i then response.json.jq(\"if (.result | type) == \\\"object\\\" then del(.result.dy_module.irregular_banner_dy, .result.icon_set, .result.search_bar_hot_query) | .result.bottom_tabs? |= (if type == \\\"array\\\" then map(select(. != null and (.title | IN(\\\"首页\\\", \\\"聊天\\\", \\\"个人中心\\\")) and ((.link // \\\"\\\") | tostring | IN(\\\"index.html\\\", \\\"chat_list.html\\\", \\\"personal.html\\\")))) else . end) | .result.buffer_bottom_tabs? |= (if type == \\\"array\\\" then map(select(. != null and ((.link // \\\"\\\") | tostring | IN(\\\"index.html\\\", \\\"chat_list.html\\\", \\\"personal.html\\\")))) else . end) | .result.all_top_opts? |= (if type == \\\"array\\\" then [] else . end) | .result.module_order? |= (if type == \\\"array\\\" then map(select(. != null and . != false and . != 0 and . != \\\"\\\" and ((.module_name // \\\"\\\") | IN(\\\"irregular_banner_dy\\\", \\\"irregular_banner\\\", \\\"ad_module\\\", \\\"icon_set\\\", \\\"recommend_fresh_info\\\", \\\"timeline\\\") | not))) else . end) else . end\")"
PDD_HOMEPAGE_NATIVE_REQUIRED_MARKERS = (
    "response.json.delete(",
    "result.dy_module.irregular_banner_dy",
    "result.icon_set",
    "result.search_bar_hot_query",
    "bottom_tabs?",
    "buffer_bottom_tabs?",
    "all_top_opts",
)


def consolidate_pdd_homepage_native_response(lines):
    """Replace split PDD homepage cleanup with one native jq response pass."""
    output = list(lines)
    section = ""
    script_indices, rewrite_indices = [], []
    marker = "api.pinduoduo.com/api/alexa/homepage/hub"

    def normalize(value):
        return value.replace(chr(92), "").strip().lower()

    for index, line in enumerate(output):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
        elif section == "Script" and marker in normalize(line) and "scripts/pinduoduo/pdd-homepage.js" in normalize(line):
            script_indices.append(index)
        elif section == "Rewrite" and marker in normalize(line) and (
            "response.json.delete(" in normalize(line) or "response.json.jq(" in normalize(line)
        ):
            rewrite_indices.append(index)

    if len(script_indices) > 1:
        raise ValueError("duplicate Pinduoduo homepage local script trigger")
    if len(rewrite_indices) > 1:
        raise ValueError("duplicate Pinduoduo homepage native response rule")
    if not script_indices or not rewrite_indices:
        return output, 0

    rewrite_index = rewrite_indices[0]
    native_line = output[rewrite_index]
    native_normalized = normalize(native_line)
    canonical_normalized = normalize(PDD_HOMEPAGE_NATIVE_JQ_RULE)
    if native_normalized != canonical_normalized:
        missing = [
            item for item in PDD_HOMEPAGE_NATIVE_REQUIRED_MARKERS
            if item not in native_normalized
        ]
        if missing:
            raise ValueError("Pinduoduo homepage native rule changed; refusing unreviewed replacement: " + ", ".join(missing))
        output[rewrite_index] = PDD_HOMEPAGE_NATIVE_JQ_RULE

    output[script_indices[0]] = None
    return [line for line in output if line is not None], 1


# 拼多多 images.pinduoduo.com 是商品图片 CDN；只拦截其广告素材路径，不整域拒绝。
PDD_IMAGE_CDN_HOST = "images.pinduoduo.com"
PDD_IMAGE_CDN_BROAD_BLOCK = "DOMAIN,images.pinduoduo.com,REJECT"
# Current fmz200 KuaiDi100.lpx source rules; both are HTTPS-only and case-insensitive.
PDD_IMAGE_CDN_AD_PATH_RULES = (
    r"request if ${url} ~= /^https:\/\/images\.pinduoduo\.com\/mrk\//i then reject(404)",
    r"request if ${url} ~= /^https:\/\/images\.pinduoduo\.com\/marketing_api\//i then reject(404)",
)
# Exact previously accepted merged-source variants remain recognized for backward compatibility.
PDD_IMAGE_CDN_LEGACY_AD_PATH_RULES = (
    r"request if ${url} ~= /^https?:\/\/images\.pinduoduo\.com\/(mrk|marketing_api)\// then reject(404)",
    r"request if ${url} ~= /^https?:\/\/images\.pinduoduo\.com\/marketing\_api/ then reject(200)",
)
PDD_IMAGE_CDN_LOFTER_AD_PATH_RULE = (
    r"request if ${url} ~= /^https?:\/\/images\.pinduoduo\.com\/marketing\_api/i then reject(200)"
)


def scope_pdd_image_cdn_ad_rules(lines):
    """Remove the host-wide PDD image reject and retain/add only reviewed ad-path blocks."""
    section = ""
    output = []
    broad_count = 0
    known_path_rules = (
        PDD_IMAGE_CDN_AD_PATH_RULES
        + PDD_IMAGE_CDN_LEGACY_AD_PATH_RULES
        + (PDD_IMAGE_CDN_LOFTER_AD_PATH_RULE,)
    )
    path_counts = {rule: 0 for rule in known_path_rules}
    unknown_path_rules = []
    mitm_has_host = False
    saw_target = False

    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue

        value = line.strip()
        if section == "Rule" and value:
            parts = [part.strip() for part in value.split(",")]
            if len(parts) >= 2 and parts[0].upper() in ("DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD") and parts[1].lower() == PDD_IMAGE_CDN_HOST:
                saw_target = True
                if value != PDD_IMAGE_CDN_BROAD_BLOCK:
                    raise ValueError("PDD images CDN domain rule changed; refusing unreviewed scope change: " + value)
                broad_count += 1
                if broad_count > 1:
                    raise ValueError("duplicate PDD images CDN broad domain block")
                continue

        if section == "Rewrite" and PDD_IMAGE_CDN_HOST in value.replace("\\", ""):
            saw_target = True
            if value in path_counts:
                path_counts[value] += 1
                if path_counts[value] > 1:
                    raise ValueError("duplicate PDD images CDN ad-path Rewrite")
            else:
                unknown_path_rules.append(value)

        if section == "MITM" and value.lower().startswith("hostname") and "=" in value:
            hosts = [host.strip().lower() for host in value.split("=", 1)[1].split(",")]
            mitm_has_host = mitm_has_host or PDD_IMAGE_CDN_HOST in hosts
            saw_target = saw_target or mitm_has_host

        output.append(line)

    if not saw_target or broad_count == 0:
        return list(lines), 0
    if not mitm_has_host:
        raise ValueError("PDD images CDN ad-path Rewrite requires its existing MITM hostname")
    if unknown_path_rules:
        raise ValueError(
            "PDD images CDN ad-path Rewrite inventory changed; refusing broad-block removal: "
            + repr(unknown_path_rules)
        )

    current_counts = [path_counts[rule] for rule in PDD_IMAGE_CDN_AD_PATH_RULES]
    legacy_counts = [path_counts[rule] for rule in PDD_IMAGE_CDN_LEGACY_AD_PATH_RULES]
    if all(count == 1 for count in legacy_counts) and all(count == 0 for count in current_counts):
        missing_current_rules = []
    else:
        missing_current_rules = [
            rule for rule, count in zip(PDD_IMAGE_CDN_AD_PATH_RULES, current_counts)
            if count == 0
        ]

    if missing_current_rules:
        mitm_index = next(
            (index for index, line in enumerate(output) if line.strip() == "[MITM]"),
            None,
        )
        if mitm_index is None:
            raise ValueError("PDD images CDN scoped ad rules require a Rewrite and MITM section")
        output[mitm_index:mitm_index] = missing_current_rules

    return output, broad_count


# 拼多多开屏接口在多个来源中以不同动作重复匹配同一路径。
# 统一保留最先生效的 404 拒绝行为，并使用大小写不敏感 matcher 覆盖原有大小写范围。
PDD_SPLASH_OLD_CANONICAL_RULE = r"request if ${url} ~= /^https?:\/\/api\.(pinduoduo|yangkeduo)\.com\/api\/cappuccino\/splash/ then reject(404)"
PDD_SPLASH_CANONICAL_RULE = r"request if ${url} ~= /^https?:\/\/api\.(pinduoduo|yangkeduo)\.com\/api\/cappuccino\/splash/i then reject(404)"
PDD_SPLASH_DUPLICATE_404_RULE = r"request if ${url} ~= /^https:\/\/api\.(pinduoduo|yangkeduo)\.com\/api\/cappuccino\/splash/i then reject(404)"
PDD_SPLASH_DISTINCT_ACTION_RULES = (
    r"^https?://api\.(pinduoduo|yangkeduo)\.com/api/cappuccino/splash reject-200",
    r"^https:\/\/api\.pinduoduo\.com\/api\/cappuccino\/splash reject-dict",
)


def consolidate_pdd_splash_rules(lines):
    """Collapse only the duplicate 404 matcher; preserve distinct response status/body actions."""
    old_count = sum(line.strip() == PDD_SPLASH_OLD_CANONICAL_RULE for line in lines)
    canonical_count = sum(line.strip() == PDD_SPLASH_CANONICAL_RULE for line in lines)
    duplicate_count = sum(line.strip() == PDD_SPLASH_DUPLICATE_404_RULE for line in lines)
    distinct_counts = [sum(line.strip() == rule for line in lines) for rule in PDD_SPLASH_DISTINCT_ACTION_RULES]
    known = old_count + canonical_count + duplicate_count + sum(distinct_counts)
    target = [line for line in lines if "cappuccino" in line and "splash" in line]
    if not target:
        return list(lines), 0
    if old_count + canonical_count > 1 or duplicate_count > 1 or any(count > 1 for count in distinct_counts):
        raise ValueError("Pinduoduo splash rule inventory contains duplicate known matchers")
    # Unknown or incomplete upstream inventories are preserved untouched. The
    # optimization is applied only when the complete known action set is present.
    if len(target) != known or old_count + canonical_count == 0 or not all(distinct_counts):
        return list(lines), 0
    if canonical_count == 1 and duplicate_count == 0:
        return list(lines), 0
    output = []
    for line in lines:
        stripped = line.strip()
        if stripped == PDD_SPLASH_OLD_CANONICAL_RULE:
            output.append(PDD_SPLASH_CANONICAL_RULE)
        elif stripped == PDD_SPLASH_DUPLICATE_404_RULE:
            continue
        else:
            output.append(line)
    return output, 1


# 以下三个广告资源 URL 规则在上游合并时重复出现，且更宽的同动作规则已先行覆盖。
PDD_FEED_ASSET_CANONICAL_RULES = (
    r"request if ${url} ~= /^https?:\/\/video-dsp\.pddpic\.com\/market-dsp-video\// then reject(404)",
    r"request if ${url} ~= /^https?:\/\/t-dsp\.pinduoduo\.com\/dspcb\/i\/mrk_union/ then reject(404)",
    r"request if ${url} ~= /^https?:\/\/images\.pinduoduo\.com\/(mrk|marketing_api)\// then reject(404)",
)
PDD_FEED_ASSET_REDUNDANT_RULES = (
    r"request if ${url} ~= /^https:\/\/video-dsp\.pddpic\.com\/market-dsp-video\// then reject(404)",
    r"request if ${url} ~= /^https:\/\/t-dsp\.pinduoduo\.com\/dspcb\/i\/mrk_union/ then reject(404)",
    r"request if ${url} ~= /^https:\/\/images\.pinduoduo\.com\/mrk\// then reject(404)",
    r"request if ${url} ~= /^https:\/\/images\.pinduoduo\.com\/marketing_api\// then reject(404)",
)


def remove_redundant_pdd_feed_asset_rules(lines):
    """Remove exact narrower PDD asset rules already covered by broader same-action rules."""
    counts = [sum(line.strip() == rule for line in lines) for rule in PDD_FEED_ASSET_REDUNDANT_RULES]
    if not any(counts):
        return list(lines), 0
    if any(count > 1 for count in counts):
        raise ValueError("duplicate Pinduoduo feed asset rule; refusing ambiguous cleanup")
    canonical_counts = [sum(line.strip() == rule for line in lines) for rule in PDD_FEED_ASSET_CANONICAL_RULES]
    for index, redundant in enumerate(counts):
        if redundant and canonical_counts[index if index < 3 else 2] != 1:
            raise ValueError("Pinduoduo feed asset covering rule missing; refusing cleanup")
    return [line for line in lines if line.strip() not in PDD_FEED_ASSET_REDUNDANT_RULES], sum(counts)


PDD_OAK_REDUNDANT_SCRIPT_TRIGGER = r"http-response ^https?:\/\/api\.pinduoduo\.com\/api\/oak\/integration\/render script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/pdd.js,tag=PDD,requires-body=true"
PDD_OAK_NATIVE_RESPONSE_RULE = r'response if ${url} ~= /^https:\/\/api\.pinduoduo\.com\/api\/oak\/integration\/render\?/i then response.json.delete(["bottom_section_list", "ui.bottom_section", "ui.live_section.float_info"])'


def remove_redundant_pdd_oak_script_trigger(lines):
    """Keep native JSON field deletion and drop the script that parses the same response again."""
    output, section = [], ""
    trigger_count = 0
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue
        if section == "Script" and line.strip() == PDD_OAK_REDUNDANT_SCRIPT_TRIGGER:
            trigger_count += 1
            continue
        output.append(line)
    if trigger_count > 1:
        raise ValueError("duplicate Pinduoduo oak response script trigger")
    if trigger_count == 1 and sum(line.strip() == PDD_OAK_NATIVE_RESPONSE_RULE for line in lines) != 1:
        raise ValueError("Pinduoduo oak native response cleaner missing; refusing script removal")
    return output, trigger_count


# 淘宝开屏两个接口在多个上游插件中重复挂载了等价响应脚本。
# 保留 R-Store 的单一脚本入口；其逻辑与 FMZ、zmjde、RuCu6 对应分支一致。
TAOBAO_LOCAL_SCRIPT_URL = "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/taobao/taobao.js"
TAOBAO_CANONICAL_SCRIPT_TRIGGERS = (
    r"http-response ^https?:\\/\\/guide-acs\\.m\\.taobao\\.com\\/gw\\/mtop\\.taobao\\.(cloudvideo\\.video\\.query|wireless\\.home\\.splash\\.awesome\\.get) script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/taobao.js,tag=TAOBAO,requires-body=true",
    r"http-response ^https?:\\/\\/poplayer\\.template\\.alibaba\\.com\\/\\w+\\.json script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/taobao.js,tag=TAOBAO-2,requires-body=true",
)
TAOBAO_REDUNDANT_SCRIPT_TRIGGERS = (
    r'response if ${url} ~= /^https:\\/\\/guide-acs\\.m\\.taobao\\.com\\/gw\\/mtop\\.taobao\\.(cloudvideo\\.video\\.query|wireless\\.home\\.splash\\.awesome\\.get)/i then script("https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/myBlockAds.js") with enable=albb_enable, tag="阿里巴巴广告", timeout=60, requires_body=true',
    r'response if ${url} ~= /^https:\\/\\/poplayer\\.template\\.alibaba\\.com\\/\\w+\\.json/i then script("https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/myBlockAds.js") with enable=albb_enable, tag="myBlockAds", timeout=60, requires_body=true',
    r'response if ${url} ~= /^https?:\\/\\/guide-acs\\.m\\.taobao\\.com\\/gw\\/mtop\\.taobao\\.(cloudvideo\\.video\\.query|wireless\\.home\\.splash\\.awesome\\.get)/i then script("https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/myBlockAds.js") with enable=tcbc_enable, tag="淘宝", timeout=60, requires_body=true',
    r'response if ${url} ~= /^https?:\\/\\/poplayer\\.template\\.alibaba\\.com\\/\\w+\\.json/i then script("https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/myBlockAds.js") with enable=tcbc_enable, tag="淘宝", timeout=60, requires_body=true',
    r'response if ${url} ~= /^https:\\/\\/guide-acs\\.m\\.taobao\\.com\\/gw\\/mtop\\.taobao\\.(cloudvideo\\.video\\.query|wireless\\.home\\.splash\\.awesome\\.get)/i then script("https://raw.githubusercontent.com/zmjde/loon-plugins/main/JS/Taobao/Taobao_remove_ads.js") with tag="移除淘宝开屏广告", requires_body=true',
    r'response if ${url} ~= /^https:\\/\\/poplayer\\.template\\.alibaba\\.com\\/\\w+\\.json/i then script("https://raw.githubusercontent.com/zmjde/loon-plugins/main/JS/Taobao/Taobao_remove_ads.js") with tag="移除淘宝开屏广告", requires_body=true',
    r'response if ${url} ~= /^https:\\/\\/guide-acs\\.m\\.taobao\\.com\\/gw\\/mtop\\.taobao\\.(?:cloudvideo\\.video\\.query|wireless\\.home\\.splash\\.awesome\\.get)/i then script("https://github.com/ifflagged/Romeo/raw/main/Modules/JavaScript/rucu6/myblockads/rucu6_myblockads.js") with tag="taobao_1", requires_body=true',
    r'response if ${url} ~= /^https:\\/\\/poplayer\\.template\\.alibaba\\.com\\/\\w+\\.json/i then script("https://github.com/ifflagged/Romeo/raw/main/Modules/JavaScript/rucu6/myblockads/rucu6_myblockads.js") with tag="taobao_2", requires_body=true',
)



# Pinduoduo: these request-level blocks target order navigation/data, not the
# requested homepage/search/recommendation/splash ad surfaces. Preserve them.
PDD_ORDER_ENDPOINT_BLOCKS_TO_PRESERVE = (
    r"request if ${url} ~= /^https?:\/\/api\.pinduoduo\.com\/api\/aristotle\/unrated_order_for_unreceived_tab\?/i then reject_dict(200)",
    r"request if ${url} ~= /^https?:\/\/api\.pinduoduo\.com\/api\/aristotle\/query_order_list_tabs_element\?/i then reject_dict(200)",
    r"request if ${url} ~= /^https?:\/\/api\.pinduoduo\.com\/api\/caterham\/v3\/query\/order_express_group\?/i then reject_dict(200)",
    r"request if ${url} ~= /^https?:\/\/api\.pinduoduo\.com\/api\/aristotle\/unrated_order_for_unreceived_tab/i then reject_dict(200)",
    r"request if ${url} ~= /^https?:\/\/api\.pinduoduo\.com\/api\/aristotle\/query_order_list_tabs_element/i then reject_dict(200)",
    r"request if ${url} ~= /^https?:\/\/api\.pinduoduo\.com\/api\/caterham\/v3\/query\/order_express_group/i then reject_dict(200)",
    "request if ${url} ~= /^https:\/\/api\.pinduoduo\.com\/api\/aristotle\/unrated_order_for_unreceived_tab\?/i then reject_dict(200)",
    "^https:\/\/api\.pinduoduo\.com\/api\/aristotle\/unrated_order_for_unreceived_tab\? reject-dict",
    "^https:\/\/api\.pinduoduo\.com\/api\/aristotle\/query_order_list_tabs_element\? reject-dict",
    "request if ${url} ~= /^https:\/\/api\.pinduoduo\.com\/api\/aristotle\/query_order_list_tabs_element\?/i then reject_dict(200)",
    "request if ${url} ~= /^https:\/\/api\.pinduoduo\.com\/api\/caterham\/v3\/query\/order_express_group\?/i then reject_dict(200)",
    "^https:\/\/api\.pinduoduo\.com\/api\/caterham\/v3\/query\/order_express_group\? reject-dict",
)
PDD_ORDER_ENDPOINT_MARKERS = (
    "unrated_order_for_unreceived_tab",
    "query_order_list_tabs_element",
    "order_express_group",
)


def remove_pdd_order_endpoint_blocks(lines):
    """Remove only reviewed request blocks for core order tabs/express data."""
    # Loon sources may serialize URL slashes with different escape counts.
    # Normalize escaping only for exact allowlisted endpoint/action comparisons.
    def normalized(rule):
        # Compare exact endpoint/action semantics while accepting reviewed
        # URL slash escaping and the https versus https? source spelling.
        value = re.sub(r"\\+/", "/", rule.strip())
        return value.replace("https?://", "https://")

    known = {normalized(item) for item in PDD_ORDER_ENDPOINT_BLOCKS_TO_PRESERVE}
    output, section, seen, removed = [], "", False, 0
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue
        value = line.strip()
        if section == "Rewrite" and any(marker in value for marker in PDD_ORDER_ENDPOINT_MARKERS):
            seen = True
            if normalized(value) not in known:
                raise ValueError(
                    "PDD order endpoint rule changed; refusing unreviewed removal: "
                    + repr(value)
                )
            removed += 1
            continue
        output.append(line)

    if not seen:
        return list(lines), 0
    # Upstream sources may prune or duplicate exact known variants; remove every
    # reviewed overblock while continuing to reject any unknown endpoint form.
    return output, removed


def remove_redundant_taobao_scripts(lines):
    """Keep the two canonical R-Store Taobao triggers and remove eight equivalent duplicates."""
    def normalize_trigger(item):
        value = re.sub(r"\\+", "", item.strip())
        value = value.replace(TAOBAO_LOCAL_SCRIPT_URL, "https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/taobao.js")
        # The Kelee Taobao module is pinned to a specific Romeo commit. Normalize
        # only that exact path and 40-hex SHA to the reviewed duplicate signature.
        value = re.sub(
            r"https://raw\.githubusercontent\.com/ifflagged/Romeo/[0-9a-f]{40}/Modules/JavaScript/Kelee/Taobao_remove_ads/kelee\.one_Taobao_remove_ads\.js",
            "https://raw.githubusercontent.com/zmjde/loon-plugins/main/JS/Taobao/Taobao_remove_ads.js",
            value,
        )
        return re.sub(r"enable=\$\{(albb_enable|tcbc_enable)\}", r"enable=\1", value)

    canonical = {normalize_trigger(item): item for item in TAOBAO_CANONICAL_SCRIPT_TRIGGERS}
    redundant = {normalize_trigger(item): item for item in TAOBAO_REDUNDANT_SCRIPT_TRIGGERS}
    counts = {item: 0 for item in (*TAOBAO_CANONICAL_SCRIPT_TRIGGERS, *TAOBAO_REDUNDANT_SCRIPT_TRIGGERS)}
    output, section, target_seen = [], "", False
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue
        normalized = normalize_trigger(line)
        is_target = section == "Script" and (
            ("guide-acs.m.taobao.com/gw/mtop.taobao." in normalized
             and ("cloudvideo.video.query" in normalized or "wireless.home.splash.awesome.get" in normalized))
            or "poplayer.template.alibaba.com/" in normalized
        )
        if not is_target:
            output.append(line)
            continue
        target_seen = True
        if normalized in canonical:
            trigger = canonical[normalized]
            counts[trigger] += 1
            if counts[trigger] > 1:
                raise ValueError("duplicate canonical Taobao script trigger; refusing ambiguous deduplication")
            # Preserve the reviewed line, including the already-local URL and escape style.
            output.append(line)
            continue
        if normalized in redundant:
            trigger = redundant[normalized]
            counts[trigger] += 1
            if counts[trigger] > 1:
                raise ValueError("duplicate redundant Taobao script trigger; refusing ambiguous deduplication")
            continue
        raise ValueError("Taobao splash script trigger changed; refusing an unreviewed deduplication: " + line.strip())
    if not target_seen:
        return output, 0
    canonical_complete = all(counts[trigger] == 1 for trigger in TAOBAO_CANONICAL_SCRIPT_TRIGGERS)
    redundant_absent = all(counts[trigger] == 0 for trigger in TAOBAO_REDUNDANT_SCRIPT_TRIGGERS)
    if canonical_complete and redundant_absent:
        return output, 0
    missing = [trigger for trigger, count in counts.items() if count != 1]
    if missing:
        return list(lines), 0
    return output, len(TAOBAO_REDUNDANT_SCRIPT_TRIGGERS)


def migrate_taobao_script_to_local(lines):
    """Move the two reviewed Taobao response triggers to the repository-local single-parse cleaner."""
    output = list(lines)
    section = ""
    candidates = {}
    remote_url = "https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/taobao.js"
    for line in output:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            continue
        if section != "Script" or "tag=TAOBAO" not in stripped:
            continue
        tags = [tag for tag in ("TAOBAO", "TAOBAO-2") if re.search(r"tag=" + re.escape(tag) + r"(?:,|$)", stripped)]
        if len(tags) != 1:
            raise ValueError("Taobao script trigger tag changed; refusing local migration")
        tag = tags[0]
        if tag in candidates:
            raise ValueError("duplicate Taobao script trigger; refusing local migration: " + tag)
        if "requires-body=true" not in stripped:
            raise ValueError("Taobao script trigger lost requires-body; refusing local migration")
        if remote_url not in stripped and TAOBAO_LOCAL_SCRIPT_URL not in stripped:
            raise ValueError("Taobao script source changed; refusing local migration")
        expected = next(
            (item for item in TAOBAO_CANONICAL_SCRIPT_TRIGGERS if "tag=" + tag in item),
            None,
        )
        normalized = stripped.replace(TAOBAO_LOCAL_SCRIPT_URL, remote_url)
        if expected is None or re.sub(r"\\+", "", normalized) != re.sub(r"\\+", "", expected):
            raise ValueError("Taobao script matcher changed; refusing local migration: " + tag)
        candidates[tag] = line
    if not candidates:
        return output, 0
    if set(candidates) != {"TAOBAO", "TAOBAO-2"}:
        raise ValueError("Taobao script trigger inventory changed; refusing partial local migration")
    result = [
        line.replace(remote_url, TAOBAO_LOCAL_SCRIPT_URL) if line in candidates.values() else line
        for line in output
    ]
    changed = sum(remote_url in line for line in candidates.values())
    return result, changed







# 闲鱼的 R-Store 与 ishowshu 两组脚本对首页/本地页重复触发。
# 将 17 个上游触发器合并为 8 个仓库内本地触发器，保留两个脚本的处理并集。
GOOFISH_CANONICAL_SCRIPT_TRIGGERS = (
    r"http-response ^https?:\/\/(g-)?acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idlehome\.home\.nextfresh\/ script-path=https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/xianyu/goofish.js,tag=GOOFISH-NEXTFRESH,requires-body=true",
    r"http-response ^https?:\/\/(g-)?acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idle\.local\.home\/ script-path=https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/xianyu/goofish.js,tag=GOOFISH-LOCAL-HOME,requires-body=true",
    r"http-response ^https?:\/\/(g-)?acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idle\.home\.whale\.modulet\/ script-path=https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/xianyu/goofish.js,tag=GOOFISH-WHALE,requires-body=true",
    r"http-response ^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.idle\.user\.page\.my\.adapter\/ script-path=https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/xianyu/goofish.js,tag=GOOFISH-PROFILE,requires-body=true",
    r"http-response ^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idlehome\.home\.circle\.list\/ script-path=https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/xianyu/goofish.js,tag=GOOFISH-CIRCLE,requires-body=true",
    r"http-response ^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idle\.local\.nearby\.itemdetail\.enter\/ script-path=https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/xianyu/goofish.js,tag=GOOFISH-NEARBY,requires-body=true",
    r"http-response ^https:\/\/g-acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idlemtopsearch\.search\/ script-path=https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/xianyu/goofish.js,tag=GOOFISH-SEARCH,requires-body=true",
    r"http-response ^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idle\.local\.flow\.plat\.section script-path=https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/xianyu/goofish.js,tag=GOOFISH-LOCAL-FLOW,requires-body=true",
)
GOOFISH_REDUNDANT_SCRIPT_TRIGGERS = (
    r"http-response ^https?:\/\/(g-)?acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idle\.home\.whale\.modulet\/ script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/goofish.js,tag=GOOFISH,requires-body=true",
    r"http-response ^https?:\/\/(g-)?acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idlehome\.home\.nextfresh\/ script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/goofish.js,tag=GOOFISH-2,requires-body=true",
    r"http-response ^https?:\/\/(g-)?acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idle\.local\.home\/ script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/goofish.js,tag=GOOFISH-3,requires-body=true",
    r'response if ${url} ~= /^https:\/\/(g-)?acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idlehome\.home\.nextfresh\//i then script("https://raw.githubusercontent.com/ishowshu/qx/refs/heads/main/script/goofish.js") with tag="商品信息流广告", requires_body=true',
    r'response if ${url} ~= /^https:\/\/(g-)?acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idle\.local\.home\//i then script("https://raw.githubusercontent.com/ishowshu/qx/refs/heads/main/script/goofish.js") with tag="定位地区页面的信息流广告", requires_body=true',
    r'response if ${url} ~= /^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.idle\.user\.page\.my\.adapter\//i then script("https://raw.githubusercontent.com/ishowshu/qx/refs/heads/main/script/goofish.js") with tag="个人主页", requires_body=true',
    r'response if ${url} ~= /^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idlehome\.home\.circle\.list\/1\.0/i then script("https://raw.githubusercontent.com/ishowshu/qx/refs/heads/main/script/goofish.js") with tag="首页顶部频道菜单", requires_body=true',
    r'response if ${url} ~= /^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idle\.local\.nearby\.itemdetail\.enter\/1\.0/i then script("https://raw.githubusercontent.com/ishowshu/qx/refs/heads/main/script/goofish.js") with tag="商品详情页周边推荐", requires_body=true',
    r'response if ${url} ~= /^https:\/\/g-acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idlemtopsearch\.search\//i then script("https://raw.githubusercontent.com/ishowshu/qx/refs/heads/main/script/goofish.js") with tag="搜索结果信息流广告", requires_body=true',
    r'response if ${url} ~= /^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idle\.local\.flow\.plat\.section/i then script("https://raw.githubusercontent.com/ishowshu/qx/refs/heads/main/script/goofish.js") with tag="同城页横幅广告", requires_body=true',
    r"http-response ^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idlehome\.home\.nextfresh\/ script-path = https://github.com/ishowshu/qx/raw/refs/heads/main/script/goofish.js, requires-body = true, tag = 商品信息流广告",
    r"http-response ^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idle\.local\.home\/ script-path = https://github.com/ishowshu/qx/raw/refs/heads/main/script/goofish.js, requires-body = true, tag = 定位地区页面的信息流广告",
    r"http-response ^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.idle\.user\.page\.my\.adapter\/ script-path = https://github.com/ishowshu/qx/raw/refs/heads/main/script/goofish.js, requires-body = true, tag = 个人主页",
    r"http-response ^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idlehome\.home\.circle\.list\/ script-path = https://github.com/ishowshu/qx/raw/refs/heads/main/script/goofish.js, requires-body = true, tag = 首页顶部频道菜单",
    r"http-response ^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idle\.local\.nearby\.itemdetail\.enter\/ script-path = https://github.com/ishowshu/qx/raw/refs/heads/main/script/goofish.js, requires-body = true, tag = 商品详情页周边推荐",
    r"http-response ^https:\/\/g-acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idlemtopsearch\.search\/ script-path = https://github.com/ishowshu/qx/raw/refs/heads/main/script/goofish.js, requires-body = true, tag = 搜索结果信息流广告",
    r"http-response ^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idle\.local\.flow\.plat\.section script-path = https://github.com/ishowshu/qx/raw/refs/heads/main/script/goofish.js, requires-body = true, tag = 同城页横幅广告",
    r'response if ${url} ~= /^https://acs.m.goofish.com/gw/mtop.taobao.idlehome.home.nextfresh//i then script("https://github.com/ifflagged/Romeo/raw/main/Modules/JavaScript/ishowshu/goofish/ishowshu_goofish.js") with tag="goofish", timeout=60, requires_body=true',
    r'response if ${url} ~= /^https://acs.m.goofish.com/gw/mtop.taobao.idle.local.home//i then script("https://github.com/ifflagged/Romeo/raw/main/Modules/JavaScript/ishowshu/goofish/ishowshu_goofish.js") with tag="goofish", timeout=60, requires_body=true',
    r'response if ${url} ~= /^https://acs.m.goofish.com/gw/mtop.idle.user.page.my.adapter//i then script("https://github.com/ifflagged/Romeo/raw/main/Modules/JavaScript/ishowshu/goofish/ishowshu_goofish.js") with tag="goofish", timeout=60, requires_body=true',
    r'response if ${url} ~= /^https://acs.m.goofish.com/gw/mtop.taobao.idlehome.home.circle.list//i then script("https://github.com/ifflagged/Romeo/raw/main/Modules/JavaScript/ishowshu/goofish/ishowshu_goofish.js") with tag="goofish", timeout=60, requires_body=true',
    r'response if ${url} ~= /^https://acs.m.goofish.com/gw/mtop.taobao.idle.local.nearby.itemdetail.enter//i then script("https://github.com/ifflagged/Romeo/raw/main/Modules/JavaScript/ishowshu/goofish/ishowshu_goofish.js") with tag="goofish", timeout=60, requires_body=true',
    r'response if ${url} ~= /^https://g-acs.m.goofish.com/gw/mtop.taobao.idlemtopsearch.search//i then script("https://github.com/ifflagged/Romeo/raw/main/Modules/JavaScript/ishowshu/goofish/ishowshu_goofish.js") with tag="goofish", timeout=60, requires_body=true',
    r'response if ${url} ~= /^https://acs.m.goofish.com/gw/mtop.taobao.idle.local.flow.plat.section/i then script("https://github.com/ifflagged/Romeo/raw/main/Modules/JavaScript/ishowshu/goofish/ishowshu_goofish.js") with tag="goofish", timeout=60, requires_body=true',
)


def consolidate_goofish_script_triggers(lines):
    """Normalize audited Goofish triggers while tolerating known upstream deletions."""
    def normalize(value):
        value = re.sub(r"\\+", "", value.strip()).replace(
            "script-path=scripts/xianyu/goofish.js",
            "script-path=https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/xianyu/goofish.js",
        )
        # Stage pins Romeo-hosted JS/JQ references to the current 40-hex commit.
        return re.sub(
            r"https://raw\.githubusercontent\.com/ifflagged/Romeo/[0-9a-f]{40}/",
            "https://github.com/ifflagged/Romeo/raw/main/",
            value,
        )
    canonical = {normalize(item): item for item in GOOFISH_CANONICAL_SCRIPT_TRIGGERS}
    redundant = {normalize(item): item for item in GOOFISH_REDUNDANT_SCRIPT_TRIGGERS}
    counts = {item: 0 for item in (*GOOFISH_CANONICAL_SCRIPT_TRIGGERS, *GOOFISH_REDUNDANT_SCRIPT_TRIGGERS)}
    section = ""
    target_seen = False
    canonical_needs_normalization = False

    # Validate the complete inventory before changing anything.
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        normalized = normalize(line)
        is_target = section == "Script" and "goofish.com" in normalized and (
            "goofish.js" in normalized or "script(" in normalized
        )
        if not is_target:
            continue
        target_seen = True
        if normalized in canonical:
            counts[canonical[normalized]] += 1
            if line.strip() != canonical[normalized]:
                canonical_needs_normalization = True
            if counts[canonical[normalized]] > 1:
                raise ValueError("duplicate canonical Goofish script trigger")
        elif normalized in redundant:
            counts[redundant[normalized]] += 1
            if counts[redundant[normalized]] > 1:
                raise ValueError("duplicate redundant Goofish script trigger")
        else:
            raise ValueError(f"Goofish script trigger inventory changed; refusing unreviewed consolidation: {line.strip()}")

    if not target_seen:
        return lines, 0

    canonical_counts = [counts[item] for item in GOOFISH_CANONICAL_SCRIPT_TRIGGERS]
    redundant_count = sum(counts[item] for item in GOOFISH_REDUNDANT_SCRIPT_TRIGGERS)
    canonical_complete = all(count == 1 for count in canonical_counts)
    canonical_absent = all(count == 0 for count in canonical_counts)
    if not canonical_complete and not canonical_absent:
        raise ValueError("Goofish canonical trigger inventory incomplete; refusing partial consolidation")
    if canonical_complete and redundant_count == 0 and not canonical_needs_normalization:
        return lines, 0
    if canonical_absent and redundant_count == 0:
        return lines, 0

    # If canonical triggers already exist, remove any known redundant subset.
    # If they do not, replace any known non-empty upstream subset with the full
    # local canonical set. This handles upstream deletions without widening matchers.
    insert_canonical = canonical_absent
    output, section, inserted, removed = [], "", False, 0
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            if section == "Script" and insert_canonical and not inserted:
                output.extend(GOOFISH_CANONICAL_SCRIPT_TRIGGERS)
                inserted = True
            section = line[1:-1]
            output.append(line)
            continue
        normalized = normalize(line)
        if section == "Script" and normalized in redundant:
            removed += 1
            continue
        if section == "Script" and normalized in canonical:
            output.append(canonical[normalized])
            continue
        output.append(line)
    if section == "Script" and insert_canonical and not inserted:
        output.extend(GOOFISH_CANONICAL_SCRIPT_TRIGGERS)
    return output, removed


# 闲鱼旧版 response-body-json-jq 与新版 response.json.jq 重复处理相同字段。
XIAN_YU_REWRITE_PAIRS = (
    (r"^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idlemtopsearch\.search\.shade\/ response-body-json-jq 'del(.data)'",
     r'response if ${url} ~= /^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idlemtopsearch\.search\.shade\// then response.json.jq(`del(.data)`)'),
    (r"^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idle\.user\.strategy\.list\/ response-body-json-jq 'del(.data)'",
     r'response if ${url} ~= /^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idle\.user\.strategy\.list\// then response.json.jq(`del(.data)`)'),
    (r"^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idle\.group\.myself\.banner\/ response-body-json-jq '.data.bannerList = []'",
     r'response if ${url} ~= /^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idle\.group\.myself\.banner\// then response.json.jq(`.data.bannerList = []`)'),
    (r"^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idle\.playboy\.recommend\/2\.0 response-body-json-jq '.data.recommends = [] | .data.items = [] | .data.next = false'",
     r'response if ${url} ~= /^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idle\.playboy\.recommend\/2\.0 then response.json.jq(`.data.recommends = [] | .data.items = [] | .data.next = false`)'),
    (r"^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idle\.item\.recommend\.list\/ response-body-json-jq '.data.cardList = []'",
     r'response if ${url} ~= /^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idle\.item\.recommend\.list\// then response.json.jq(`.data.cardList = []`)'),
    (r"^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idle\.fun\.follow\.often\.visit response-body-json-jq '.data.sections = []'",
     r'response if ${url} ~= /^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idle\.fun\.follow\.often\.visit then response.json.jq(`.data.sections = []`)'),
    (r"^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idle\.circle\.myself\.banner\/1\.0 response-body-json-jq '.data.bannerList = []'",
     r'response if ${url} ~= /^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idle\.circle\.myself\.banner\/1\.0 then response.json.jq(`.data.bannerList = []`)'),
    (r"^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idle\.circle\.visited\/1\.0 response-body-json-jq '.data.visitedCircleList = []'",
     r'response if ${url} ~= /^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idle\.circle\.visited\/1\.0 then response.json.jq(`.data.visitedCircleList = []`)'),
    (r"^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idlehome\.widget\.refresh\.get response-body-json-jq '.data.homeTopList = []'",
     r'response if ${url} ~= /^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idlehome\.widget\.refresh\.get\//i then response.json.jq(".data.homeTopList |= map(select(.sectionType == \"kingkongDo\"))")'),
    (r"""^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idle\.trade\.full\.info response-body-json-jq '.data.components |= map(select(.render != "bannerVO"))'""",
     r'response if ${url} ~= /^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idle\.trade\.full\.info\//i then response.json.jq(".data.components |= map(select(.render | . == \"orderStatusVO\" or . == \"addressInfoVO\" or . == \"orderInfoVO\"))")'),
)

XIAN_YU_REQUEST_SUBSET_PAIRS = (
    (r"^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idlemtopsearch\.item\.search\.activate\/2\.0 reject-dict",
     r"^https?:\/\/(g-)?acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idlemtopsearch\.item\.search\.activate\/ reject-dict"),
    (r"^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idlemtopsearch\.search\.discover\/1\.0 reject-dict",
     r"^https?:\/\/(g-)?acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idlemtopsearch\.search\.(discover|shade)\/ reject-dict"),
    (r"^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idle\.item\.resell\.recommendorhotcate\/1\.0 reject-dict",
     r"^https?:\/\/(g-)?acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idle\.item\.resell\.recommendorhotcate reject-dict"),
    (r"^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idlehome\.idle\.coin\.nextfresh\/1\.0 reject-dict",
     r"^https?:\/\/(g-)?acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idlehome\.idle\.coin\.nextfresh\/ reject-dict"),
    (r"^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idlecommerce\.splash\.ads reject-dict",
     r"^https?:\/\/(g-)?acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idlecommerce\.splash reject-dict"),
)


def remove_redundant_xianyu_rewrite_rules(lines):
    """Remove only known same-action legacy duplicates and strict URL subsets."""
    normalize = lambda value: re.sub(r"\\+", "", value.strip())
    pairs = (*XIAN_YU_REWRITE_PAIRS, *XIAN_YU_REQUEST_SUBSET_PAIRS)
    known = {
        normalize(rule): (index, is_redundant)
        for index, (redundant, canonical) in enumerate(pairs)
        for is_redundant, rule in ((True, redundant), (False, canonical))
    }
    markers = (
        "idlemtopsearch.search.shade/", "idle.user.strategy.list/",
        "idle.group.myself.banner/", "idle.playboy.recommend/2.0",
        "idle.item.recommend.list/", "idle.fun.follow.often.visit",
        "idle.circle.myself.banner/1.0", "idle.circle.visited/1.0",
        "idlehome.widget.refresh.get", "idle.trade.full.info",
        "idlemtopsearch.item.search.activate/2.0", "idlemtopsearch.search.discover/1.0",
        "idle.item.resell.recommendorhotcate/1.0", "idlehome.idle.coin.nextfresh/1.0",
        "idlecommerce.splash.ads",
    )
    output, section, counts, target_seen = [], "", {key: 0 for key in known}, False
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue
        if section != "Rewrite":
            output.append(line)
            continue
        value = normalize(line)
        matched = known.get(value)
        target = any(marker in value for marker in markers) and (
            ("response-body-json-jq" in value or "response.json.jq" in value) or
            (value.startswith("^https:") and value.endswith("reject-dict"))
        )
        if matched is None:
            if target:
                raise ValueError("Xianyu rewrite inventory changed; refusing unreviewed cleanup")
            output.append(line)
            continue
        target_seen = True
        counts[value] += 1
        if counts[value] > 1:
            raise ValueError("duplicate Xianyu rewrite rule; refusing ambiguous cleanup")
        if matched[1]:
            continue
        output.append(line)

    if not target_seen:
        return output, 0
    for redundant, canonical in pairs:
        if counts[normalize(canonical)] != 1:
            raise ValueError("Xianyu covering rewrite missing; refusing redundant rule removal")
        if counts[normalize(redundant)] not in (0, 1):
            raise ValueError("duplicate Xianyu redundant rewrite; refusing ambiguous cleanup")
    return output, sum(counts[normalize(redundant)] for redundant, _ in pairs)


# 滴滴个人中心 /usercenter/me 同时由 R-Store 与 FMZ 两个脚本处理。
# 两个脚本在该分支的过滤字段与保留条件一致；保留 R-Store 触发器。
DIDI_USERCENTER_CANONICAL_TRIGGER = r"http-response ^https?:\\/\\/common\\.diditaxi\\.com\\.cn\\/common\\/v\\d\\/usercenter\\/me script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/didi.js,tag=DIDI-3,requires-body=true"
DIDI_USERCENTER_REDUNDANT_TRIGGER = r'response if ${url} ~= /^https?:\\/\\/common\\.diditaxi\\.com\\.cn\\/common\\/v\\d\\/usercenter\\/me/i then script("https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/didi/didiAds.js") with enable=didiiuxk_enable, tag="滴滴出行", timeout=60, requires_body=true'
DIDI_USERCENTER_REDUNDANT_TRIGGER_CURRENT = r'response if ${url} ~= /^https?:\\/\\/common\\.diditaxi\\.com\\.cn\\/common\\/v\\d\\/usercenter\\/me/i then script("https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/didi/didiAds.js") with enable=${didiiuxk_enable}, tag="滴滴出行", timeout=60, requires_body=true'
DIDI_USERCENTER_REDUNDANT_TRIGGERS = (DIDI_USERCENTER_REDUNDANT_TRIGGER, DIDI_USERCENTER_REDUNDANT_TRIGGER_CURRENT)


def remove_redundant_didi_usercenter_script(lines):
    """Remove only known FMZ duplicates for the exact Didi user-center endpoint."""
    canonical = re.sub(r"\\+", "", DIDI_USERCENTER_CANONICAL_TRIGGER.strip())
    redundant_variants = {
        re.sub(r"\\+", "", trigger.strip())
        for trigger in DIDI_USERCENTER_REDUNDANT_TRIGGERS
    }
    output, section = [], ""
    canonical_count = redundant_count = 0
    target_seen = False
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue
        normalized = re.sub(r"\\+", "", line.strip())
        is_target = section == "Script" and (
            "common.diditaxi.com.cn/common/v" in normalized
            and "/usercenter/me" in normalized
        )
        if not is_target:
            output.append(line)
            continue
        target_seen = True
        if normalized == canonical:
            canonical_count += 1
            output.append(line)
            continue
        if normalized in redundant_variants:
            redundant_count += 1
            continue
        raise ValueError("Didi user-center script trigger changed; refusing an unreviewed deduplication")
    if not target_seen:
        return output, 0
    if canonical_count != 1:
        raise ValueError("Didi user-center canonical trigger inventory changed; expected exactly one R-Store trigger")
    if redundant_count > 1:
        raise ValueError("duplicate Didi user-center FMZ trigger; refusing ambiguous deduplication")
    return output, redundant_count


DDQX_NEWDETAILS_MARKER = "maicai.api.ddxq.mobi/homeApi/newDetails"
DDQX_NEWDETAILS_MATCHER = r"^https?:\/\/maicai\.api\.ddxq\.mobi\/homeApi\/newDetails"
DDQX_NEWDETAILS_LEGACY_ACTION = "response-body-replace-regex suspension random_body"
DDQX_NEWDETAILS_MODERN_ACTION = r'response if ${url} ~= /^https?:\/\/maicai\.api\.ddxq\.mobi\/homeApi\/newDetails/ then response.body.replace(/suspension/, "fmz200")'
DDQX_NEWDETAILS_NATIVE_RULE = r'response if ${url} ~= /^https?:\/\/maicai\.api\.ddxq\.mobi\/homeApi\/newDetails/ then response.json.delete("data.suspension")'


# 淘宝首页/开屏/信息流中，以下子集规则已被同动作、更宽的规则覆盖。
TAOBAO_FLIGGY_HTTP_COVER = r"request if ${url} ~= /^https?:\/\/acs\.m\.taobao\.com\/gw\/mtop\.fliggy\.crm\.screen\.(allresource|predict)/ then reject_dict(200)"
TAOBAO_FLIGGY_HTTPS_COVER = r"request if ${url} ~= /^https:\/\/acs\.m\.taobao\.com\/gw\/mtop\.fliggy\.crm\.screen\.(?:allresource|predict)/i then reject_dict(200)"
TAOBAO_FLIGGY_HTTPS_REDUNDANT = r"request if ${url} ~= /^https:\/\/acs\.m\.taobao\.com\/gw\/mtop\.fliggy\.crm\.screen\.(allresource|predict)/i then reject_dict(200)"

TAOBAO_CAINIAO_FLYAD_COVER = r"^https?:\/\/guide-acs\.m\.taobao\.com\/gw\/mtop\.cainiao\.adx\.flyad\.getad reject-dict"
TAOBAO_CAINIAO_FLYAD_REDUNDANT = r"^https:\/\/guide-acs\.m\.taobao\.com\/gw\/mtop\.cainiao\.adx\.flyad\.getad reject-dict"

TAOBAO_HOME_HTTP_COVER = r"^https?:\/\/guide-acs\.m\.taobao\.com\/gw\/mtop\.taobao\.(volvo\.secondfloor\.getconfig|wireless\.home\.newface\.awesome\.get) reject-dict"
TAOBAO_HOME_HTTPS_COVER = r"request if ${url} ~= /^https:\/\/guide-acs\.m\.taobao\.com\/gw\/mtop\.taobao\.(?:volvo\.secondfloor\.getconfig|shot\.resources\.load|wireless\.home\.(newface|splash)\.awesome\.get)/i then reject_dict(200)"
TAOBAO_HOME_HTTPS_SUBSET = r"request if ${url} ~= /^https:\/\/guide-acs\.m\.taobao\.com\/gw\/mtop\.taobao\.(volvo\.secondfloor\.getconfig|wireless\.home\.newface\.awesome\.get)/i then reject_dict(200)"
TAOBAO_HOME_SPLASH_SUBSET = r"^https:\/\/guide-acs\.m\.taobao\.com\/gw\/mtop\.taobao\.wireless\.home\.splash\.awesome\.get reject-dict"


def remove_redundant_taobao_rewrite_rules(lines):
    """Remove only exact same-action subsets while preserving protocol/case coverage."""
    groups = (
        (
            "mtop.fliggy.crm.screen",
            (TAOBAO_FLIGGY_HTTP_COVER, TAOBAO_FLIGGY_HTTPS_COVER),
            (TAOBAO_FLIGGY_HTTPS_REDUNDANT,),
        ),
        (
            "mtop.cainiao.adx.flyad.getad",
            (TAOBAO_CAINIAO_FLYAD_COVER,),
            (TAOBAO_CAINIAO_FLYAD_REDUNDANT,),
        ),
        (
            "guide-acs.m.taobao.com/gw/mtop.taobao.",
            (TAOBAO_HOME_HTTP_COVER, TAOBAO_HOME_HTTPS_COVER),
            (TAOBAO_HOME_HTTPS_SUBSET, TAOBAO_HOME_SPLASH_SUBSET),
        ),
    )
    normalize = lambda value: re.sub(r"\\+", "", value.strip())
    known = {
        normalize(rule): (group_index, rule, is_redundant)
        for group_index, (_, covers, redundants) in enumerate(groups)
        for is_redundant, rules in ((False, covers), (True, redundants))
        for rule in rules
    }
    output, section = [], ""
    counts = {key: 0 for key in known}
    seen_groups = set()
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue
        if section != "Rewrite":
            output.append(line)
            continue
        value = normalize(line)
        group_index = None
        for index, (marker, _, _) in enumerate(groups):
            if marker in value and (
                index != 2 or any(token in value for token in (
                    "volvo.secondfloor.getconfig", "shot.resources.load",
                    "wireless.home.newface.awesome.get", "wireless.home.splash.awesome.get",
                ))
            ):
                group_index = index
                break
        if group_index is None:
            output.append(line)
            continue
        seen_groups.add(group_index)
        matched = known.get(value)
        if matched is None or matched[0] != group_index:
            raise ValueError("Taobao homepage/feed rewrite inventory changed; refusing unreviewed cleanup")
        counts[value] += 1
        if counts[value] > 1:
            raise ValueError("duplicate Taobao homepage/feed rewrite; refusing ambiguous cleanup")
        if matched[2]:
            continue
        output.append(line)

    for index in seen_groups:
        _, covers, redundants = groups[index]
        if any(counts[normalize(rule)] != 1 for rule in covers):
            raise ValueError("Taobao covering rewrite missing; refusing redundant rule removal")
        if any(counts[normalize(rule)] not in (0, 1) for rule in redundants):
            raise ValueError("duplicate Taobao redundant rewrite; refusing ambiguous cleanup")
    return output, sum(counts[normalize(rule)] for _, _, redundants in groups for rule in redundants)


def replace_ddqx_newdetails_body_rewrites(lines):
    """Replace only the reviewed Duoduo Grocery suspension-field rewrites with JSON deletion."""
    output, converted, legacy_count, modern_count, native_count = [], 0, 0, 0, 0
    unknown_seen = False
    normalize = lambda value: re.sub(
        r"enable=\$\{([^}]+)\}",
        r"enable=\1",
        re.sub(r"\\+", "", value.strip()),
    )
    normalized_native = normalize(DDQX_NEWDETAILS_NATIVE_RULE)
    normalized_legacy = normalize(DDQX_NEWDETAILS_MATCHER + " " + DDQX_NEWDETAILS_LEGACY_ACTION)
    normalized_modern = normalize(DDQX_NEWDETAILS_MODERN_ACTION)
    for line in lines:
        normalized = normalize(line)
        if DDQX_NEWDETAILS_MARKER.lower() not in normalized.lower():
            output.append(line)
            continue
        if normalized == normalized_legacy:
            legacy_count += 1
            converted += 1
            continue
        if normalized == normalized_modern:
            modern_count += 1
            converted += 1
            continue
        if normalized == normalized_native:
            native_count += 1
            output.append(line)
            continue
        # New upstream variants are kept verbatim until their semantics are reviewed.
        unknown_seen = True
        output.append(line)
    if legacy_count > 1 or modern_count > 1 or native_count > 1:
        raise ValueError("duplicate Duoduo Grocery newDetails suspension rules; refusing ambiguous conversion")
    if unknown_seen:
        return list(lines), 0
    if converted and not native_count:
        output.append(DDQX_NEWDETAILS_NATIVE_RULE)
    return output, converted


def split_response_json_rewrite(line: str):
    match = re.match(r'^(response if .+?) then (.+)', line)
    if not match: return None
    prefix, action_text = match.groups()
    # Split only Loon's top-level action separator; JQ arguments can contain pipes.
    actions = []
    start = 0
    quote = None
    escaped = False
    for position, char in enumerate(action_text):
        if escaped:
            escaped = False
            continue
        if quote is not None:
            if char == chr(92):
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in (chr(34), chr(39), chr(96)):
            quote = char
            continue
        if (char == chr(124) and position > 0 and position + 1 < len(action_text)
                and action_text[position - 1].isspace()
                and action_text[position + 1].isspace()):
            actions.append(action_text[start:position].strip())
            start = position + 1
    actions.append(action_text[start:].strip())
    if not actions or any(not action.startswith("response.json.") for action in actions): return None
    return prefix, actions

PDD_HOMEPAGE_DELETE_DUPLICATE_RULE = r'response if ${url} ~= /^https:\/\/api\.pinduoduo\.com\/api\/alexa\/homepage\/hub\?/i then response.json.delete(["result.dy_module.irregular_banner_dy", "result.icon_set", "result.search_bar_hot_query", "result.dy_module.irregular_banner_dy"])'
PDD_HOMEPAGE_DELETE_DEDUPED_RULE = r'response if ${url} ~= /^https:\/\/api\.pinduoduo\.com\/api\/alexa\/homepage\/hub\?/i then response.json.delete(["result.dy_module.irregular_banner_dy", "result.icon_set", "result.search_bar_hot_query"])'

def remove_duplicate_pdd_homepage_delete_path(lines):
    """Remove only the proven duplicate path in the exact Pinduoduo homepage delete action."""
    if sum(line.strip() == PDD_HOMEPAGE_DELETE_DUPLICATE_RULE for line in lines) != 1:
        return list(lines), 0
    return [
        PDD_HOMEPAGE_DELETE_DEDUPED_RULE if line.strip() == PDD_HOMEPAGE_DELETE_DUPLICATE_RULE else line
        for line in lines
    ], 1

PDD_PHILO_HUB_NO_QUERY_RULE = r'response if ${url} ~= /^https:\/\/api\.pinduoduo\.com\/api\/philo\/personal\/hub\/?$/i then response.json.jq("del(.personal_banner, .personal_center_style_v2_vo.third_personal_icons_v2) | .monthly_card_entrance.display = false")'
PDD_PHILO_HUB_QUERY_RULE = r'response if ${url} ~= /^https:\/\/api\.pinduoduo\.com\/api\/philo\/personal\/hub\/?\?/i then response.json.delete(["monthly_card_entrance", "personal_center_style_v2_vo", "icon_set.icons", "icon_set.top_personal_icons", "personal_banner"])'
PDD_PHILO_HUB_RESPONSE_RULES = (
    r'response if ${url} ~= /^https:\/\/api\.pinduoduo\.com\/api\/philo\/personal\/hub/i then response.json.jq("del(.personal_banner, .personal_center_style_v2_vo.third_personal_icons_v2) | .monthly_card_entrance.display = false")',
    r'response if ${url} ~= /^https:\/\/api\.pinduoduo\.com\/api\/philo\/personal\/hub\?/i then response.json.delete(["monthly_card_entrance", "personal_center_style_v2_vo", "icon_set.icons", "icon_set.top_personal_icons", "personal_banner"])',
)


def narrow_pdd_philo_hub_response_rules(lines):
    """Make broad no-query and query-specific PDD personal-hub rules mutually exclusive."""
    output = list(lines)
    section = ""
    counts = {rule: 0 for rule in PDD_PHILO_HUB_RESPONSE_RULES}
    narrowed_counts = {PDD_PHILO_HUB_NO_QUERY_RULE: 0, PDD_PHILO_HUB_QUERY_RULE: 0}
    original_normalized = {re.sub(r"\\+", "", rule): rule for rule in PDD_PHILO_HUB_RESPONSE_RULES}
    narrowed_normalized = {re.sub(r"\\+", "", rule): rule for rule in narrowed_counts}
    for index, line in enumerate(output):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            continue
        normalized = re.sub(r"\\+", "", stripped)
        if section != "Rewrite" or "api.pinduoduo.com/api/philo/personal/hub" not in normalized:
            continue
        if normalized in narrowed_normalized:
            rule = narrowed_normalized[normalized]
            narrowed_counts[rule] += 1
            if narrowed_counts[rule] > 1:
                raise ValueError("duplicate narrowed PDD personal-hub response rule")
            continue
        original = original_normalized.get(normalized)
        if original is None:
            raise ValueError("PDD personal-hub response rule changed; refusing unreviewed matcher narrowing")
        counts[original] += 1
        if counts[original] > 1:
            raise ValueError("duplicate PDD personal-hub response rule")
        replacement = (
            PDD_PHILO_HUB_NO_QUERY_RULE if original == PDD_PHILO_HUB_RESPONSE_RULES[0]
            else PDD_PHILO_HUB_QUERY_RULE
        )
        output[index] = replacement
    if any(counts.values()) and any(narrowed_counts.values()):
        raise ValueError("mixed original and narrowed PDD personal-hub rules; refusing partial migration")
    if any(narrowed_counts.values()):
        if any(count != 1 for count in narrowed_counts.values()):
            raise ValueError("narrowed PDD personal-hub response rule inventory changed")
        return output, 0
    if not any(counts.values()):
        return output, 0
    if any(count != 1 for count in counts.values()):
        raise ValueError("PDD personal-hub response rule inventory changed; refusing partial matcher narrowing")
    return output, 2


DACHE_CORE_ICON_DELETE_GUARD = r'response if ${url} ~= /^https:\/\/api\.udache\.com\/gulfstream\/porsche\/v\d\/dache_homepage_layout\?/i then response.json.delete("data.instances.dache_main_core_icon")'
DACHE_CORE_ICON_FILTER_RULE = r'response if ${url} ~= /^https:\/\/api\.udache\.com\/gulfstream\/porsche\/v\d\/dache_homepage_layout\?/i then response.json.jq(".data |= (.instances |= (to_entries | map(select(.key | test(\"feed_back_|dache_main_member|order_container_|dache_main_core_icon|dache_main_card_\"))) | from_entries))")'

def remove_redundant_dache_core_icon_filter(lines):
    output, guard_seen, removed = [], False, 0
    for line in lines:
        value = line.strip()
        if value == DACHE_CORE_ICON_DELETE_GUARD:
            guard_seen = True
        if value == DACHE_CORE_ICON_FILTER_RULE and guard_seen:
            replacement = value.replace(
                "order_container_|dache_main_core_icon|dache_main_card_",
                "order_container_|dache_main_card_",
                1,
            )
            if replacement == value:
                output.append(line)
            else:
                output.append(replacement)
                removed += 1
            continue
        output.append(line)
    return output, removed


# Legacy Didi rules rejected the entire v1 homepage response before the newer
# field-level response cleaners could run. Remove only those exact request
# rejects when the corresponding precise response cleaner is present.
DIDI_HOME_SLOW_LEGACY_REJECT = r"^https?:\/\/conf\.diditaxi\.com\.cn\/homepage\/v\d\/other\/slow reject-dict"
DIDI_HOME_FAST_LEGACY_REJECT = r"^https?:\/\/conf\.diditaxi\.com\.cn\/homepage\/v\d\/other\/fast reject-dict"
DIDI_HOME_SLOW_RESPONSE_PREFIX = r"response if ${url} ~= /^https:\/\/conf\.diditaxi\.com\.cn\/homepage\/v\d\/other\/slow\?/i then response.json.delete("
DIDI_HOME_FAST_RESPONSE_PREFIX = r"response if ${url} ~= /^https:\/\/conf\.diditaxi\.com\.cn\/homepage\/v\d\/other\/fast\?/i then response.json.delete("


DIDI_HOME_CORE_LEGACY_REJECT = "^https?:\\/\\/conf\\.diditaxi\\.com\\.cn\\/homepage\\/v\\d\\/core reject-dict"
DIDI_HOME_CORE_RESPONSE_PREFIX = "response if ${url} ~= /^https:\\/\\/conf\\.diditaxi\\.com\\.cn\\/homepage\\/v\\d\\/core\\?/i then response.json.jq("


def remove_didi_homepage_rejects_shadowing_field_cleaners(lines):
    """Remove exact whole-endpoint rejects only when precise field cleaners supersede them."""
    output = list(lines)
    removed = 0
    targets = (
        (DIDI_HOME_SLOW_LEGACY_REJECT, DIDI_HOME_SLOW_RESPONSE_PREFIX, "slow", "homepage/vd/other/slow"),
        (DIDI_HOME_FAST_LEGACY_REJECT, DIDI_HOME_FAST_RESPONSE_PREFIX, "fast", "homepage/vd/other/fast"),
        (DIDI_HOME_CORE_LEGACY_REJECT, DIDI_HOME_CORE_RESPONSE_PREFIX, "core", "homepage/vd/core"),
    )
    for legacy_rule, response_prefix, label, drift_marker in targets:
        exact_positions = [i for i, line in enumerate(output) if line.strip() == legacy_rule]
        drifted = [
            line.strip() for line in output
            if drift_marker in re.sub(r"\\+", "", line)
            and line.strip().startswith("^https")
            and line.strip() != legacy_rule
        ]
        if drifted:
            raise ValueError("Didi homepage " + label + " legacy reject changed; refusing an unreviewed override")
        if len(exact_positions) > 1:
            raise ValueError("duplicate Didi homepage " + label + " legacy rejects")
        if not exact_positions:
            continue
        response_matches = [line for line in output if line.strip().startswith(response_prefix)]
        if len(response_matches) != 1:
            raise ValueError(
                "Didi homepage " + label + " field-level response cleaner inventory changed"
            )
        output = [line for line in output if line.strip() != legacy_rule]
        removed += 1
    return output, removed


DIDI_CORE_LEGACY_SCRIPT = "http-response ^https?:\\/\\/conf\\.diditaxi\\.com\\.cn\\/homepage\\/v\\d\\/core script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/didi.js,tag=DIDI,requires-body=true"
DIDI_USERCENTER_LEGACY_SCRIPT = "http-response ^https?:\\/\\/common\\.diditaxi\\.com\\.cn\\/common\\/v\\d\\/usercenter\\/me script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/didi.js,tag=DIDI-3,requires-body=true"
DIDI_OTA_KEEP_SCRIPT = "http-response ^https?:\\/\\/conf\\.diditaxi\\.com\\.cn\\/ota\\/na\\/yuantu\\/infoList script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/didi.js,tag=DIDI-2,requires-body=true"
DIDI_PRESALE_KEEP_SCRIPT = "http-response ^https?:\\/\\/api\\.udache\\.com\\/gulfstream\\/pre-sale\\/v\\d\\/other\\/pGetSceneList script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/didi.js,tag=DIDI-4,requires-body=true"
DIDI_CORE_LEGACY_JSON_RULE = "^https:\\/\\/conf\\.diditaxi\\.com\\.cn\\/homepage\\/v1\\/core\\? response-body-json-jq '.data.disorder_cards.bottom_nav_list.data |= [.[] | select(.id == \"home_page\" or .id == \"user_center\")] | .data.order_cards.nav_list_card.data |= [.[] | select(.nav_id == \"bike\" or .nav_id == \"driverservice\" or .nav_id == \"carmate\")]'"
DIDI_CORE_NATIVE_RULE_CURRENT = "response if ${url} ~= /^https:\\/\\/conf\\.diditaxi\\.com\\.cn\\/homepage\\/v\\d\\/core\\?/i then response.json.jq(\".data.order_cards.nav_list_card.data |= map(select(.nav_id == \\\"dache_anycar\\\" or .nav_id == \\\"carmate\\\" or .nav_id == \\\"driverservice\\\" or .nav_id == \\\"zhandianbashi\\\" or .nav_id == \\\"pincheche\\\" or .nav_id == \\\"bike\\\" or .nav_id == \\\"nav_more_v3\\\")) | .data.disorder_cards.top_nav_list.data.top_nav_info |= map(select(.nav_id == \\\"chu_xing\\\" or .nav_id == \\\"freight_cargo\\\"))\")"
DIDI_CORE_NATIVE_RULE = "response if ${url} ~= /^https:\\/\\/conf\\.diditaxi\\.com\\.cn\\/homepage\\/v\\d\\/core\\?/i then response.json.jq(\"(if (try (.data.disorder_cards.bottom_nav_list.data | type) catch null) == \\\"array\\\" then .data.disorder_cards.bottom_nav_list.data |= map(select(.id == \\\"v6x_home\\\" or .id == \\\"home_page\\\" or .id == \\\"user_center\\\")) else . end) | (if (try (.data.order_cards.nav_list_card.data | type) catch null) == \\\"array\\\" then .data.order_cards.nav_list_card.data |= map(select(.nav_id == \\\"dache_anycar\\\" or .nav_id == \\\"carmate\\\" or .nav_id == \\\"driverservice\\\" or .nav_id == \\\"zhandianbashi\\\" or .nav_id == \\\"pincheche\\\" or .nav_id == \\\"bike\\\" or .nav_id == \\\"nav_more_v3\\\")) else . end) | (if (try (.data.disorder_cards.top_nav_list.data.top_nav_info | type) catch null) == \\\"array\\\" then .data.disorder_cards.top_nav_list.data.top_nav_info |= map(select(.nav_id == \\\"chu_xing\\\" or .nav_id == \\\"freight_cargo\\\")) else . end)\")"
DIDI_USERCENTER_LAYOUT_LEGACY_JSON_RULE = "^https:\\/\\/common\\.diditaxi\\.com\\.cn\\/common\\/v5\\/usercenter\\/layout response-body-json-jq 'del(.data.instances.center_marketing_card, .data.instances.center_tool_card, .data.instances.center_widget_list, .data.instances.center_res_light_guide) | .data.instances.center_wallet_finance_card.data.view_info |= map(select(.title == \"优惠卡券\"))'"
DIDI_USERCENTER_LAYOUT_NATIVE_PREFIX = "response if ${url} ~= /^https:\\/\\/common\\.diditaxi\\.com\\.cn\\/common\\/v\\d\\/usercenter\\/layout/i then response.json.jq("
DIDIADS_COMMON_V5_SCRIPT = "response if ${url} ~= /^https?:\\/\\/common\\.diditaxi\\.com\\.cn\\/common\\/v5/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/didi/didiAds.js\") with enable=didiiuxk_enable, tag=\"微信小程序个人中心净化\", timeout=60, requires_body=true"
DIDIADS_LOCAL_COMMON_V5_SCRIPT = DIDIADS_COMMON_V5_SCRIPT.replace("https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/didi/didiAds.js", "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/didi/didi-ads.js")
DIDIADS_NOOP_SCRIPT_RULES = (
    "response if ${url} ~= /^https?:\\/\\/ct\\.xiaojukeji\\.com\\/agent\\/v3\\/feeds/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/didi/didiAds.js\") with enable=didiiuxk_enable, tag=\"滴滴出行\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/freight\\.xiaojukeji\\.com\\/gateway/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/didi/didiAds.js\") with enable=didiiuxk_enable, tag=\"滴滴出行\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/res\\.xiaojukeji\\.com\\/resapi\\/activity\\/xpget/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/didi/didiAds.js\") with enable=didiiuxk_enable, tag=\"滴滴出行\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/res\\.xiaojukeji\\.com\\/resapi\\/activity\\/mget/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/didi/didiAds.js\") with enable=didiiuxk_enable, tag=\"滴滴出行\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/conf\\.diditaxi\\.com\\.cn\\/homepage\\/v\\d\\/other\\/fast/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/didi/didiAds.js\") with enable=didiiuxk_enable, tag=\"滴滴出行\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/conf\\.diditaxi\\.com\\.cn\\/dynamic\\/conf/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/didi/didiAds.js\") with enable=didiiuxk_enable, tag=\"滴滴出行\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/daijia\\.kuaidadi\\.com\\/gateway/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/didi/didiAds.js\") with enable=didiiuxk_enable, tag=\"滴滴出行\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/daijia\\.kuaidadi\\.com:443\\/gateway/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/didi/didiAds.js\") with enable=didiiuxk_enable, tag=\"滴滴出行\", timeout=60, requires_body=true",
)


def apply_didi_script_and_homepage_cleanup(lines):
    """Remove dead/overlapping Didi scripts and consolidate homepage/profile field cleaners."""
    output = list(lines)
    if "[Argument]" not in output or "[Rule]" not in output:
        return output, 0
    norm = lambda value: re.sub(
        r"enable=\$\{([^}]+)\}",
        r"enable=\1",
        re.sub(r"\\+", "", value.strip()),
    ).lower()

    core_current = [i for i, line in enumerate(output) if line.strip() == DIDI_CORE_NATIVE_RULE_CURRENT]
    core_native = [i for i, line in enumerate(output) if line.strip() == DIDI_CORE_NATIVE_RULE]
    if len(core_current) > 1 or len(core_native) > 1 or len(core_current) + len(core_native) != 1:
        raise ValueError("Didi core homepage native rule inventory changed")
    for line in output:
        n = norm(line)
        if "homepage/vd/core" in n and "response if" in n and "response.json.jq(" in n and line.strip() not in (DIDI_CORE_NATIVE_RULE_CURRENT, DIDI_CORE_NATIVE_RULE):
            raise ValueError("Didi core homepage native rule drifted")
    if core_current:
        output[core_current[0]] = DIDI_CORE_NATIVE_RULE

    old_core_json = [i for i, line in enumerate(output) if line.strip() == DIDI_CORE_LEGACY_JSON_RULE]
    drifted_core_json = [line for line in output if "homepage/v1/core" in norm(line) and "response-body-json-jq" in line and line.strip() != DIDI_CORE_LEGACY_JSON_RULE]
    if drifted_core_json:
        raise ValueError("Didi legacy core JSON rule drifted")
    if len(old_core_json) > 1:
        raise ValueError("duplicate Didi legacy core JSON rules")
    if old_core_json:
        output = [line for line in output if line.strip() != DIDI_CORE_LEGACY_JSON_RULE]

    old_user_layout = [i for i, line in enumerate(output) if line.strip() == DIDI_USERCENTER_LAYOUT_LEGACY_JSON_RULE]
    drifted_user_layout = [line for line in output if "usercenter/layout" in norm(line) and "response-body-json-jq" in line and line.strip() != DIDI_USERCENTER_LAYOUT_LEGACY_JSON_RULE]
    modern_user_layout = [line for line in output if line.strip().startswith(DIDI_USERCENTER_LAYOUT_NATIVE_PREFIX)]
    if drifted_user_layout:
        raise ValueError("Didi usercenter layout legacy JSON rule drifted")
    if len(old_user_layout) > 1 or len(modern_user_layout) != 1:
        raise ValueError("Didi usercenter layout native rule inventory changed")
    if old_user_layout:
        output = [line for line in output if line.strip() != DIDI_USERCENTER_LAYOUT_LEGACY_JSON_RULE]

    common_v5 = [
        line for line in output
        if norm(line) in (norm(DIDIADS_COMMON_V5_SCRIPT), norm(DIDIADS_LOCAL_COMMON_V5_SCRIPT))
    ]
    if len(common_v5) != 1:
        raise ValueError("Didi common/v5 canonical script trigger missing or duplicated")
    for legacy, marker, label in (
        (DIDI_CORE_LEGACY_SCRIPT, "homepage/vd/core", "core"),
        (DIDI_USERCENTER_LEGACY_SCRIPT, "common/vd/usercenter/me", "usercenter"),
    ):
        exact = [line for line in output if norm(line) == norm(legacy)]
        drifted = [line for line in output if "AntiAd/didi.js" in line and marker in norm(line) and norm(line) != norm(legacy)]
        if drifted:
            raise ValueError("Didi " + label + " legacy script trigger drifted")
        if len(exact) > 1:
            raise ValueError("duplicate Didi " + label + " legacy script trigger")
        if exact:
            output = [line for line in output if norm(line) != norm(legacy)]

    removed_noop = 0
    for legacy in DIDIADS_NOOP_SCRIPT_RULES:
        marker = norm(legacy.split(" then script(", 1)[0])
        exact = [line for line in output if norm(line) == norm(legacy)]
        drifted = [line for line in output if "didiads.js" in norm(line) and marker in norm(line) and norm(line) != norm(legacy)]
        if drifted:
            raise ValueError("DidiAds no-op script trigger drifted; refusing unreviewed cleanup")
        if len(exact) > 1:
            raise ValueError("duplicate DidiAds no-op script trigger")
        if exact:
            output = [line for line in output if norm(line) != norm(legacy)]
            removed_noop += 1

    remaining_didiads = [
        norm(line) for line in output
        if "didiads.js" in norm(line) or "scripts/didi/didi-ads.js" in norm(line)
    ]
    if len(remaining_didiads) != 1 or remaining_didiads[0] not in (
        norm(DIDIADS_COMMON_V5_SCRIPT), norm(DIDIADS_LOCAL_COMMON_V5_SCRIPT)
    ):
        raise ValueError("DidiAds script trigger inventory changed; expected common/v5 only")
    for keeper in (DIDI_OTA_KEEP_SCRIPT, DIDI_PRESALE_KEEP_SCRIPT):
        if sum(norm(line) == norm(keeper) for line in output) != 1:
            raise ValueError("Didi R-Store retained script inventory changed")
    remaining_rstore = [norm(line) for line in output if "antiad/didi.js" in norm(line)]
    if sorted(remaining_rstore) != sorted((norm(DIDI_OTA_KEEP_SCRIPT), norm(DIDI_PRESALE_KEEP_SCRIPT))):
        raise ValueError("Didi R-Store script inventory changed")
    return output, removed_noop



def migrate_didiads_common_v5_to_local(lines):
    """Move the sole surviving Didi common/v5 response handler to the tested local cleaner."""
    output = list(lines)
    section = ""
    candidates = []
    normalize = lambda value: (
        value.replace(chr(92), "")
        .replace("enable=${", "enable=")
        .replace("}", "")
        .strip()
        .lower()
    )
    remote = normalize(DIDIADS_COMMON_V5_SCRIPT)
    local = normalize(DIDIADS_LOCAL_COMMON_V5_SCRIPT)
    for line in output:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            continue
        normalized = normalize(stripped)
        if section != "Script" or "common.diditaxi.com.cn/common/v5" not in normalized:
            continue
        if "didiads.js" not in normalized and "scripts/didi/didi-ads.js" not in normalized:
            continue
        if normalized not in (remote, local):
            raise ValueError("Didi common/v5 script trigger changed; refusing local migration")
        candidates.append(line)
    if not candidates:
        return output, 0
    if len(candidates) != 1:
        raise ValueError("Didi common/v5 script trigger duplicated; refusing local migration")
    current = candidates[0]
    if normalize(current) == local:
        return output, 0
    result = [DIDIADS_LOCAL_COMMON_V5_SCRIPT if line == current else line for line in output]
    return result, 1

DIDI_FAST_HOME_DELETE_FIRST = r'response if ${url} ~= /^https:\/\/conf\.diditaxi\.com\.cn\/homepage\/v\d\/other\/fast\?/i then response.json.delete(["data.disorder_cards.communicate_card", "data.disorder_cards.not_login_bottom_bar", "data.disorder_cards.riding_code_card", "data.order_cards", "data.disorder_cards.car_icon.data.icon_info_new_agreement"])'
DIDI_FAST_HOME_DELETE_SECOND = r'response if ${url} ~= /^https:\/\/conf\.diditaxi\.com\.cn\/homepage\/v\d\/other\/fast\?/i then response.json.delete(["data.disorder_cards.guess_card", "data.disorder_cards.scene_list_card"])'
DIDI_FAST_HOME_MATCHER_PREFIX = r'response if ${url} ~= /^https:\/\/conf\.diditaxi\.com\.cn\/homepage\/v\d\/other\/fast\?/i then '

def merge_didi_fast_homepage_json_deletes(lines):
    """Coalesce the two exact Didi homepage delete lists without crossing same-matcher actions."""
    first_positions = [i for i, line in enumerate(lines) if line.strip() == DIDI_FAST_HOME_DELETE_FIRST]
    second_positions = [i for i, line in enumerate(lines) if line.strip() == DIDI_FAST_HOME_DELETE_SECOND]
    if len(first_positions) != 1 or len(second_positions) != 1:
        return list(lines), 0
    first, second = first_positions[0], second_positions[0]
    if first >= second:
        return list(lines), 0
    if any(line.strip().startswith(DIDI_FAST_HOME_MATCHER_PREFIX)
           for line in lines[first + 1:second]):
        return list(lines), 0
    merged = r'response if ${url} ~= /^https:\/\/conf\.diditaxi\.com\.cn\/homepage\/v\d\/other\/fast\?/i then response.json.delete(["data.disorder_cards.communicate_card", "data.disorder_cards.not_login_bottom_bar", "data.disorder_cards.riding_code_card", "data.order_cards", "data.disorder_cards.car_icon.data.icon_info_new_agreement", "data.disorder_cards.guess_card", "data.disorder_cards.scene_list_card"])'
    output = list(lines)
    output[first] = merged
    del output[second]
    return output, 1

STARPLUCKER_DOUBLE_JQ_RULE = "response if ${url} ~= /^https?:\\/\\/starplucker\\.cyapi\\.cn\\/v\\d\\/config/ then response.json.jq(`del(.search_suggestions)?`) | response.json.jq(`(.pic_page_card_orders[]?, .map_page_card_orders[]?) |= select(.name | test(\"^(A|C01)\") | not)`)"
STARPLUCKER_SINGLE_JQ_RULE = "response if ${url} ~= /^https?:\\/\\/starplucker\\.cyapi\\.cn\\/v\\d\\/config/ then response.json.jq(`del(.search_suggestions)? | (.pic_page_card_orders[]?, .map_page_card_orders[]?) |= select(.name | test(\"^(A|C01)\") | not)`)"

def consolidate_starplucker_config_jq(lines):
    """Combine the two sequential jq parses for the same StarPlucker config response."""
    output = list(lines)
    matches = [i for i, line in enumerate(output) if "starplucker\\.cyapi" in line and "response.json.jq" in line]
    if not matches:
        return output, 0
    if len(matches) != 1:
        raise ValueError("StarPlucker config jq rule changed or duplicated; refusing unsafe rewrite")
    current = output[matches[0]].strip()
    if current == STARPLUCKER_SINGLE_JQ_RULE:
        return output, 0
    if current != STARPLUCKER_DOUBLE_JQ_RULE:
        raise ValueError("StarPlucker config jq rule changed; refusing unsafe rewrite")
    output[matches[0]] = STARPLUCKER_SINGLE_JQ_RULE
    return output, 1


def merge_adjacent_response_json_rewrites(lines):
    output, index, merged = [], 0, 0
    while index < len(lines):
        parsed = split_response_json_rewrite(lines[index].strip())
        if not parsed:
            output.append(lines[index]); index += 1; continue
        prefix, actions = parsed
        look = index + 1
        while look < len(lines) and not lines[look].strip(): look += 1
        count = 1
        while look < len(lines):
            candidate = split_response_json_rewrite(lines[look].strip())
            if not candidate or candidate[0] != prefix: break
            actions.extend(candidate[1]); count += 1; look += 1
            while look < len(lines) and not lines[look].strip(): look += 1
        if count > 1:
            output.append(prefix + " then " + " | ".join(actions)); merged += 1; index = look
        else:
            output.append(lines[index]); index += 1
    return output, merged


DIANPING_LEGACY_SCRIPT_RULES = (
    ("http-response ^https?:\\/\\/img\\.meituan\\.net\\/(?:dpmobile|goodsawardpic)\\/ script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/dianping.js,tag=DIANPING,requires-body=true", "response if ${url} ~= /^https?:\\/\\/img\\.meituan\\.net\\/(?>dpmobile|goodsawardpic)\\//i then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/dianping.js\") with enable=davsdmpk_enable, tag=\"大众点评\", timeout=60, requires_body=true", "img.meituan.net"),
    ("http-response ^https?:\\/\\/ddplus\\.meituan\\.net\\/v\\d\\/mss_\\w+\\/picassovc script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/dianping.js,tag=DIANPING-2,requires-body=true", "response if ${url} ~= /^https?:\\/\\/ddplus\\.meituan\\.net\\/v\\d\\/mss_\\w+\\/picassovc/i then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/dianping.js\") with enable=davsdmpk_enable, tag=\"大众点评\", timeout=60, requires_body=true", "ddplus.meituan.net"),
)


def remove_redundant_dianping_scripts(lines):
    """Drop unconditional legacy triggers only when their gated equivalents exist once."""
    output = list(lines)
    removed = 0
    for legacy, gated, label in DIANPING_LEGACY_SCRIPT_RULES:
        legacy_positions = [i for i, line in enumerate(output) if line.strip() == legacy]
        gated_positions = [i for i, line in enumerate(output) if line.strip() == gated]
        if len(legacy_positions) > 1:
            raise ValueError("duplicate legacy Dianping script trigger: " + label)
        if len(gated_positions) > 1:
            raise ValueError("duplicate gated Dianping script trigger: " + label)
        if not legacy_positions:
            continue
        if not gated_positions:
            # The upstream may legitimately ship only the legacy handler. Keep
            # it rather than failing the whole sync or deleting the only handler.
            continue
        output = [line for line in output if line.strip() != legacy]
        removed += 1
    return output, removed



BAIDUMAP_LEGACY_SCRIPT_RULE = ("http-response ^https?:\\/\\/newclient\\.map\\.baidu\\.com\\/client\\/phpui2\\/\\?qt=ads script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/baiduMap.js,tag=BAIDUMAP,requires-body=true,binary-body-mode=true", "response if ${url} ~= /^https?:\\/\\/newclient\\.map\\.baidu\\.com\\/client\\/phpui2\\/\\?qt=ads/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/baidumap.js\") with enable=bdduditu_enable, tag=\"百度地图广告\", timeout=60, requires_body=true", "newclient.map.baidu.com/qt=ads")
BAIDUMAP_RSTORE_SCRIPT_URL = "https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/baiduMap.js"
BAIDUMAP_LOCAL_SCRIPT_URL = "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/baidumap/baidu-map-protobuf.js"


def remove_redundant_baidumap_script(lines):
    """Remove the unconditional legacy Baidu Maps ad trigger when its gated twin exists."""
    output = list(lines)
    legacy, gated, label = BAIDUMAP_LEGACY_SCRIPT_RULE
    legacy_positions = [i for i, line in enumerate(output) if line.strip() == legacy]
    gated_positions = [i for i, line in enumerate(output) if line.strip() == gated]
    if len(legacy_positions) > 1:
        raise ValueError("duplicate legacy Baidu Maps script trigger: " + label)
    if len(gated_positions) > 1:
        raise ValueError("duplicate gated Baidu Maps script trigger: " + label)
    if not legacy_positions:
        return output, 0
    if not gated_positions:
        # Preserve the only remaining handler when upstream no longer ships a gated twin.
        return output, 0
    output = [line for line in output if line.strip() != legacy]
    return output, 1






def migrate_baidumap_script_to_local(lines):
    """Route the binary-body Baidu Maps handler to the reviewed local zero-copy version."""
    output = list(lines)
    section = ""
    candidates = []
    for line in output:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            continue
        if section != "Script" or "tag=BAIDUMAP" not in stripped:
            continue
        if "newclient" not in stripped or "qt=ads" not in stripped:
            continue
        if "requires-body=true" not in stripped or "binary-body-mode=true" not in stripped:
            raise ValueError("Baidu Maps trigger lost binary-body requirements; refusing migration")
        if BAIDUMAP_RSTORE_SCRIPT_URL in stripped or BAIDUMAP_LOCAL_SCRIPT_URL in stripped:
            candidates.append(line)
        else:
            raise ValueError("Baidu Maps script source changed; refusing local migration")
    if not candidates:
        return output, 0
    if len(candidates) != 1:
        raise ValueError("Baidu Maps binary response trigger duplicated; refusing local migration")
    current = candidates[0]
    if BAIDUMAP_LOCAL_SCRIPT_URL in current:
        return output, 0
    return [
        line.replace(BAIDUMAP_RSTORE_SCRIPT_URL, BAIDUMAP_LOCAL_SCRIPT_URL)
        if line == current else line
        for line in output
    ], 1


# Amap has versioned m{digit} legacy triggers alongside m5 modern handlers.
# Keep legacy coverage for non-m5 hosts, but avoid running duplicate body scripts
# on m5 where a native Rewrite or the repository-local Rucu6 handler is canonical.
AMAP_VERSIONED_RSTORE_SCRIPT_MARKERS = (
    "/ws/aos/perception/publictravel/beforenavi",
    "/ws/bus/plan/integrate",
    "/ws/shield/search/nearbyrec_smart",
    "/ws/promotion-web/resource",
)
AMAP_ISHOWSHU_REDUNDANT_SCRIPT_MARKERS = (
    "/ws/aos/perception/publictravel/beforenavi",
    "/ws/shield/search/nearbyrec_smart",
    "/ws/promotion-web/resource",
    "card-service-plan-home|main-page",
    "/ws/valueadded/alimama/splash_screen",
    "/ws/perception/drive/",
)


def optimize_amap_response_script_overlaps(lines):
    """Narrow versioned legacy Amap triggers and remove only proven m5 duplicates."""
    output = list(lines)

    def section_entries(section_name):
        result, section = [], ""
        for index, line in enumerate(output):
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                section = stripped[1:-1]
            elif section == section_name:
                result.append((index, line))
        return result

    def normalized(value):
        return value.replace(chr(92), "").strip().lower()

    script_entries = section_entries("Script")
    rewrite_entries = section_entries("Rewrite")

    def matches(entries, marker, token):
        return [
            index for index, line in entries
            if marker in normalized(line) and token in normalized(line)
        ]

    rstore_cover = {
        AMAP_VERSIONED_RSTORE_SCRIPT_MARKERS[0]: bool(matches(
            rewrite_entries,
            AMAP_VERSIONED_RSTORE_SCRIPT_MARKERS[0],
            "response.json.jq(",
        )),
        AMAP_VERSIONED_RSTORE_SCRIPT_MARKERS[1]: bool(
            matches(script_entries, AMAP_VERSIONED_RSTORE_SCRIPT_MARKERS[1], "ishowshu_amap.js")
            or (
                len(matches(rewrite_entries, AMAP_VERSIONED_RSTORE_SCRIPT_MARKERS[1], "response.json.jq(")) == 1
                and "hkfrecommendplans" in normalized(output[matches(
                    rewrite_entries, AMAP_VERSIONED_RSTORE_SCRIPT_MARKERS[1], "response.json.jq("
                )[0]])
            )
        ),
        AMAP_VERSIONED_RSTORE_SCRIPT_MARKERS[2]: bool(matches(
            script_entries,
            AMAP_VERSIONED_RSTORE_SCRIPT_MARKERS[2],
            "sources/amap/rucu6_amap.js",
        )),
        AMAP_VERSIONED_RSTORE_SCRIPT_MARKERS[3]: bool(matches(
            script_entries,
            AMAP_VERSIONED_RSTORE_SCRIPT_MARKERS[3],
            "sources/amap/rucu6_amap.js",
        )),
    }

    for marker in AMAP_VERSIONED_RSTORE_SCRIPT_MARKERS:
        candidates = matches(script_entries, marker, "/res/scripts/antiad/amap.js")
        if len(candidates) > 1:
            raise ValueError("duplicate versioned Amap legacy trigger: " + marker)
        if not candidates or not rstore_cover[marker]:
            continue
        index = candidates[0]
        line = output[index]
        if "m[0-46-9]" in line:
            continue
        updated, count = re.subn(r"m\\+d", "m[0-46-9]", line, count=1, flags=re.IGNORECASE)
        if count != 1:
            raise ValueError("Amap legacy host-version matcher changed: " + marker)
        output[index] = updated

    native_before = matches(
        rewrite_entries,
        AMAP_ISHOWSHU_REDUNDANT_SCRIPT_MARKERS[0],
        "response.json.jq(",
    )
    if len(native_before) > 1:
        raise ValueError("duplicate Amap beforeNavi native handler")
    if native_before:
        targets = matches(
            script_entries,
            AMAP_ISHOWSHU_REDUNDANT_SCRIPT_MARKERS[0],
            "ishowshu_amap.js",
        )
        if len(targets) > 1:
            raise ValueError("duplicate Amap beforeNavi iShowshu trigger")
        if targets:
            output[targets[0]] = None

    # The native bus-plan jq rule now removes both taxiPlans and hkfRecommendPlans.
    # Once both fields are covered, the iShowshu response script is redundant.
    native_bus_plan = matches(rewrite_entries, "/ws/bus/plan/integrate", "response.json.jq(")
    if len(native_bus_plan) > 1:
        raise ValueError("duplicate Amap bus-plan native response rules")
    if native_bus_plan and "hkfrecommendplans" in normalized(output[native_bus_plan[0]]):
        targets = matches(script_entries, "/ws/bus/plan/integrate", "ishowshu_amap.js")
        if len(targets) > 1:
            raise ValueError("duplicate Amap bus-plan iShowshu trigger")
        if targets:
            output[targets[0]] = None

    for marker in AMAP_ISHOWSHU_REDUNDANT_SCRIPT_MARKERS[1:]:
        canonical = matches(script_entries, marker, "sources/amap/rucu6_amap.js")
        if len(canonical) > 1:
            raise ValueError("duplicate canonical local Amap trigger: " + marker)
        if not canonical:
            continue
        targets = matches(script_entries, marker, "ishowshu_amap.js")
        if len(targets) > 1:
            raise ValueError("duplicate Amap iShowshu trigger: " + marker)
        if targets:
            output[targets[0]] = None

    result = [line for line in output if line is not None]
    removed = len(output) - len(result)
    return result, removed


AMAP_LEGACY_SCRIPT_EXPECTED_COUNT = None
AMAP_LEGACY_SCRIPT_PATH_MARKERS = (
    "/ws/aos/perception/publictravel/beforenavi",
    "/ws/bus/plan/integrate",
    "/ws/c3frontend/af-",
    "/ws/perception/drive/",
    "/ws/shield/search/",
    "/ws/shield/search_poi/",
    "/ws/shield/search_business/process/marketingoperationstructured",
    "/ws/faas/amap-navigation/",
    "/ws/shield/frogserver/aocs/updatable/",
    "/ws/shield/dsp/profile/index/nodefaasv",
    "/ws/boss/",
    "/ws/promotion-web/resource",
    "/ws/sharedtrip/taxi/order_detail_car_tips",
    "/ws/shield/search_bff/hotword",
    "/ws/valueadded/alimama/splash_screen",
)


def _amap_required_response_handlers(normalized):
    if "/ws/aos/perception/publictravel/beforenavi" in normalized:
        return ("/ws/aos/perception/publictravel/beforenavi",)
    if "/ws/bus/plan/integrate" in normalized:
        return ("/ws/bus/plan/integrate",)
    if "/ws/c3frontend/" in normalized:
        return ("/ws/c3frontend/(?:af-(?:hotel|launch)/page/main|af-nearby/nearby)",)
    if "/ws/perception/drive/" in normalized:
        return ("/ws/perception/drive/(?:routeinfo|routeplan)",)
    if "/ws/shield/search_business/process/marketingoperationstructured" in normalized:
        return ("/ws/shield/search_business/process/marketingoperationstructured",)
    if "/ws/shield/search_poi/" in normalized:
        required = []
        if "homepage" in normalized:
            required.append("/ws/shield/search_poi/homepage")
        if any(marker in normalized for marker in ("mps", "search/sp", "sug", "tips_operation_location")):
            required.append("/ws/shield/search_poi/(?:mps|search/sp|sug|tips_operation_location)")
        return tuple(required)
    if "/ws/shield/search_bff/hotword" in normalized:
        return ("/ws/shield/search_bff/hotword",)
    if "/ws/shield/search/nearbyrec_smart" in normalized:
        return ("/ws/shield/search/nearbyrec_smart",)
    if "/ws/shield/search/" in normalized:
        return ("/ws/shield/search/(?:common/coupon/info|poi/detail)",)
    if "/ws/faas/amap-navigation/" in normalized:
        return ("/ws/faas/amap-navigation/(?:card-service-plan-home|main-page)",)
    if "/ws/shield/frogserver/aocs/updatable/" in normalized:
        return ("/ws/shield/frogserver/aocs/updatable/1",)
    if "/ws/shield/dsp/profile/index/nodefaasv" in normalized:
        return ("/ws/shield/dsp/profile/index/nodefaasv3",)
    if "/ws/boss/" in normalized:
        return ("/ws/boss/(?:car/order/content_info|order_web/friendly_information)",)
    if "/ws/promotion-web/resource" in normalized:
        return ("/ws/promotion-web/resource",)
    if "/ws/sharedtrip/taxi/order_detail_car_tips" in normalized:
        return ("/ws/sharedtrip/taxi/order_detail_car_tips",)
    if "/ws/valueadded/alimama/splash_screen" in normalized:
        return ("/ws/valueadded/alimama/splash_screen",)
    return ()


def remove_redundant_amap_legacy_scripts(lines, expected_count=AMAP_LEGACY_SCRIPT_EXPECTED_COUNT):
    """Remove only legacy Amap http-response scripts when their exact modern handlers exist."""
    output, section, targets = [], "", []
    response_handlers = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            output.append(line)
            continue
        normalized = re.sub(r"\\+", "", stripped).lower()
        if not stripped.startswith("#") and normalized.startswith("response if") and "amap" in normalized:
            response_handlers.append(normalized)
        if section != "Script" or not normalized.startswith("http-response") or "amap" not in normalized:
            output.append(line)
            continue
        if "/amap.js" not in normalized:
            raise ValueError("Amap legacy response script source changed; refusing unreviewed cleanup")
        if not any(marker in normalized for marker in AMAP_LEGACY_SCRIPT_PATH_MARKERS):
            raise ValueError("unknown Amap legacy response script endpoint; refusing unreviewed cleanup")
        required = _amap_required_response_handlers(normalized)
        if not required:
            raise ValueError("Amap legacy response script has no reviewed native handler")
        # These four R-Store matchers span m1-m9, while their newer handlers
        # are m5-only. Never drop the non-m5 coverage on a later idempotent pass.
        if (any(marker in line.replace(chr(92), "").lower() for marker in AMAP_VERSIONED_RSTORE_SCRIPT_MARKERS)
                and ("m" + chr(92) + "d" in line or "m[0-46-9]" in line)):
            output.append(line)
            continue
        targets.append((line, required))
    if not targets:
        return output, 0
    if len({line for line, _required in targets}) != len(targets):
        raise ValueError("duplicate Amap legacy response script trigger")
    if expected_count is not None and len(targets) != expected_count:
        raise ValueError(
            "Amap legacy response script inventory changed; expected %d, found %d"
            % (expected_count, len(targets))
        )
    removable = []
    for target_line, required_markers in targets:
        counts = [sum(marker in handler for handler in response_handlers) for marker in required_markers]
        # Remove only when every exact native handler exists exactly once.
        # Missing or ambiguous native handlers keep the legacy script in place.
        if all(count == 1 for count in counts):
            removable.append(target_line)
    remaining = [line for line in lines]
    for target_line in removable:
        remaining.remove(target_line)
    return remaining, len(removable)



# 京东四个广告相关域名同时存在精确 DOMAIN-SUFFIX 与更宽的 DOMAIN-KEYWORD。
# Loon 的 DOMAIN-SUFFIX 已覆盖目标域名及其子域；DOMAIN-KEYWORD 会匹配域名任意位置的子串。
JD_KEYWORD_SCOPE_HOSTS = (
    "bdsp.x.jd.com",
    "kepler.jd.com",
    "keplerapi.jd.com",
)
JD_KEYWORD_SCOPE_RULES = {
    host: "DOMAIN-KEYWORD," + host + ",REJECT"
    for host in JD_KEYWORD_SCOPE_HOSTS
}
JD_SUFFIX_SCOPE_RULES = {
    host: "DOMAIN-SUFFIX," + host + ",REJECT"
    for host in JD_KEYWORD_SCOPE_HOSTS
}


def remove_redundant_jd_keyword_rules(lines):
    """Drop only four proven broad keyword shadows, retaining exact suffix blocks.

    The suffix rule covers the exact hostname and all subdomains. A keyword rule
    additionally matches arbitrary hostnames containing that string, so it is
    broader without adding coverage for the documented JD host tree.
    """
    section = ""
    output = []
    keyword_counts = {host: 0 for host in JD_KEYWORD_SCOPE_HOSTS}
    suffix_counts = {host: 0 for host in JD_KEYWORD_SCOPE_HOSTS}
    saw_target_rule = False

    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue

        value = line.strip()
        if section == "Rule" and value:
            parts = [part.strip() for part in value.split(",")]
            if len(parts) >= 2 and parts[0].upper() == "DOMAIN-KEYWORD":
                host = parts[1].lower()
                if host in JD_KEYWORD_SCOPE_RULES:
                    saw_target_rule = True
                    if value != JD_KEYWORD_SCOPE_RULES[host]:
                        raise ValueError(
                            "Jingdong DOMAIN-KEYWORD rule changed; refusing unreviewed scope reduction: "
                            + value
                        )
                    keyword_counts[host] += 1
                    if keyword_counts[host] > 1:
                        raise ValueError("duplicate Jingdong DOMAIN-KEYWORD rule: " + host)
                    continue
                if any(target in host for target in JD_KEYWORD_SCOPE_HOSTS):
                    saw_target_rule = True
                    raise ValueError(
                        "unknown Jingdong DOMAIN-KEYWORD variant; refusing unreviewed cleanup: "
                        + value
                    )

            if len(parts) >= 2 and parts[0].upper() == "DOMAIN-SUFFIX":
                host = parts[1].lower()
                if host in JD_SUFFIX_SCOPE_RULES:
                    saw_target_rule = True
                    if value != JD_SUFFIX_SCOPE_RULES[host]:
                        raise ValueError("Jingdong DOMAIN-SUFFIX cover changed: " + value)
                    suffix_counts[host] += 1

        output.append(line)

    if not saw_target_rule:
        return list(lines), 0

    missing_covers = [host for host, count in suffix_counts.items() if count != 1]
    if missing_covers:
        raise ValueError(
            "Jingdong exact DOMAIN-SUFFIX covers must each exist once: "
            + ", ".join(missing_covers)
        )

    present = [host for host, count in keyword_counts.items() if count]
    if present and len(present) != len(JD_KEYWORD_SCOPE_HOSTS):
        raise ValueError("Jingdong DOMAIN-KEYWORD inventory is partial; refusing unreviewed cleanup")
    return output, sum(keyword_counts.values())


JD_CORE_SERVICE_BLOCKS = {
    "img-x.jd.com": "DOMAIN-SUFFIX,img-x.jd.com,REJECT",
    "mapi.m.jd.com": "DOMAIN-SUFFIX,mapi.m.jd.com,REJECT",
    "janapi.jd.com": "DOMAIN,janapi.jd.com,REJECT",
}


def remove_jd_core_service_domain_blocks(lines):
    """Remove only broad JD host blocks independently identified as core services."""
    section = ""
    output = []
    counts = {host: 0 for host in JD_CORE_SERVICE_BLOCKS}
    saw_target = False

    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue

        value = line.strip()
        if section == "Rule" and value:
            parts = [part.strip() for part in value.split(",")]
            if len(parts) >= 2 and parts[0].upper() in ("DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD"):
                host = parts[1].lower()
                if host in JD_CORE_SERVICE_BLOCKS:
                    expected = JD_CORE_SERVICE_BLOCKS[host]
                    expected_matcher = expected.split(",", 1)[0]
                    # A DOMAIN-KEYWORD rule is a distinct upstream rule, not the
                    # exact host-wide DOMAIN/DOMAIN-SUFFIX overblock targeted here.
                    # Keep it intact; a missing canonical matcher still fails the
                    # complete-inventory check below.
                    if parts[0].upper() != expected_matcher:
                        output.append(line)
                        continue
                    saw_target = True
                    if value != expected:
                        raise ValueError("JD core service domain rule changed; refusing unreviewed removal: " + value)
                    counts[host] += 1
                    if counts[host] > 1:
                        raise ValueError("duplicate JD core service domain block: " + host)
                    continue
        output.append(line)

    if not saw_target:
        return list(lines), 0
    # Retired consolidated feeds may no longer contribute all three legacy rows.
    # Each row that is present is still checked against its exact known action above.
    return output, sum(counts.values())

# Jingdong: retain the unconditional R-Store cleaner and preserve the optional
# FMZ welcomeHome-only extension behind its existing user switch.
JD_RSTORE_LEGACY_TRIGGER = r"http-response ^https?:\/\/api\.m\.jd\.com\/client\.action\?functionId=(?:deliverLayer|getTabHomeInfo|myOrderInfo|orderTrackBusiness|personinfoBusiness|start|welcomeHome|readCustomSurfaceList) script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/jd.js,tag=JD,requires-body=true"
JD_FMZ_LEGACY_TRIGGER = r'response if ${url} ~= /^https:\/\/api\.m\.jd\.com\/client\.action\?functionId=(deliverLayer|getTabHomeInfo|myOrderInfo|orderTrackBusiness|personinfoBusiness|start|welcomeHome)/i then script("https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/jingdong/jingdong.js") with enable=jkds_enable, tag="京东", timeout=60, requires_body=true'
JD_FMZ_LEGACY_TRIGGER_CURRENT = r'response if ${url} ~= /^https:\/\/api\.m\.jd\.com\/client\.action\?functionId=(deliverLayer|getTabHomeInfo|myOrderInfo|orderTrackBusiness|personinfoBusiness|start|welcomeHome)/i then script("https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/jingdong/jingdong.js") with enable=${jkds_enable}, tag="京东", timeout=60, requires_body=true'
JD_FMZ_LEGACY_TRIGGERS = (JD_FMZ_LEGACY_TRIGGER, JD_FMZ_LEGACY_TRIGGER_CURRENT)
JD_CANONICAL_TRIGGER = r"http-response ^https?:\/\/api\.m\.jd\.com\/client\.action\?functionId=(?:deliverLayer|getTabHomeInfo|myOrderInfo|orderTrackBusiness|personinfoBusiness|start|readCustomSurfaceList) script-path=https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/jingdong/jd.js,tag=JD-CONSOLIDATED,requires-body=true"
JD_OPTIONAL_WELCOME_TRIGGER = r'response if ${url} ~= /^https:\/\/api\.m\.jd\.com\/client\.action\?functionId=welcomeHome/i then script("https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/jingdong/jd.js", {${jkds_enable}}) with tag="JD-CONSOLIDATED-WELCOME", timeout=60, requires_body=true'


def consolidate_jingdong_scripts(lines):
    """Replace overlapping JD triggers while preserving the optional FMZ switch."""
    section = ""
    scoped = []
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
        elif section == "Script":
            scoped.append(line.strip())

    rstore_count = scoped.count(JD_RSTORE_LEGACY_TRIGGER)
    fmz_counts = {trigger: scoped.count(trigger) for trigger in JD_FMZ_LEGACY_TRIGGERS}
    fmz_count = sum(fmz_counts.values())
    known_triggers = {JD_RSTORE_LEGACY_TRIGGER, *JD_FMZ_LEGACY_TRIGGERS,
                      JD_CANONICAL_TRIGGER, JD_OPTIONAL_WELCOME_TRIGGER}
    unknown_triggers = [line for line in scoped
                        if "api.m.jd.com/client.action?functionId=" in line
                        and ("tag=JD" in line or "jingdong.js" in line or "/jd.js" in line)
                        and line not in known_triggers]
    if unknown_triggers:
        raise ValueError("Jingdong legacy trigger changed; refusing unreviewed cleanup: " + unknown_triggers[0])
    canonical_count = scoped.count(JD_CANONICAL_TRIGGER)
    optional_count = scoped.count(JD_OPTIONAL_WELCOME_TRIGGER)

    # Unrelated App test fixtures do not contain Jingdong triggers.
    # Skip this override when none of the reviewed trigger variants is present.
    if not (rstore_count or fmz_count or canonical_count or optional_count):
        return list(lines), 0

    if canonical_count or optional_count:
        if canonical_count == 1 and optional_count == 1 and not rstore_count and not fmz_count:
            return list(lines), 0
        raise ValueError("Jingdong script trigger inventory is mixed or duplicated")
    if rstore_count > 1 or fmz_count > 1:
        raise ValueError("Jingdong legacy trigger inventory duplicated")
    if rstore_count != 1 or fmz_count != 1:
        return list(lines), 0

    output = []
    section = ""
    inserted_rstore = inserted_fmz = False
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue
        if section == "Script" and line.strip() == JD_RSTORE_LEGACY_TRIGGER:
            output.append(JD_CANONICAL_TRIGGER)
            inserted_rstore = True
            continue
        if section == "Script" and line.strip() in JD_FMZ_LEGACY_TRIGGERS:
            output.append(JD_OPTIONAL_WELCOME_TRIGGER)
            inserted_fmz = True
            continue
        output.append(line)
    if not inserted_rstore or not inserted_fmz:
        raise ValueError("Jingdong canonical trigger insertion failed")
    return output, 1


# Meituan: merge the reviewed R-Store and aoomee trigger inventory into one
# exact host/path union and one local handler; do not broaden any endpoint.
MEITUAN_LEGACY_TRIGGERS = (
    "http-response ^https?:\\/\\/p\\d\\.meituan\\.net\\/linglong\\/ script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/meituan.js,tag=MEITUAN,requires-body=true",
    "http-response ^https?:\\/\\/web\\.meituan\\.com\\/api\\/miniprogram\\/tabbar\\/all\\/query script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/meituanwm.js,tag=MEITUANWM,requires-body=true",
    "http-response ^https?:\\/\\/web\\.meituan\\.com\\/api\\/miniprogram\\/index\\/aggregate script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/meituanwm.js,tag=MEITUANWM-2,requires-body=true",
    "http-response ^https?:\\/\\/apimobile\\.meituan\\.com\\/aggroup\\/indexTab script-path=https://raw.githubusercontent.com/aoomee/Loon-Adblock-Plugins/main/scripts/meituan-clean.js,requires-body=true,tag=美团首页标签",
    "http-response ^https?:\\/\\/feedguess\\.meituan\\.com\\/lycoris\\/scene\\/(gwc_feed1_2265|personalcenter_2154)(\\?|$) script-path=https://raw.githubusercontent.com/aoomee/Loon-Adblock-Plugins/main/scripts/meituan-clean.js,requires-body=true,tag=美团信息流",
    "http-response ^https?:\\/\\/mt-personalcenter\\.meituan\\.com\\/usercenter\\/display script-path=https://raw.githubusercontent.com/aoomee/Loon-Adblock-Plugins/main/scripts/meituan-clean.js,requires-body=true,tag=美团我的页面",
    "http-response ^https?:\\/\\/apimobile\\.meituan\\.com\\/group\\/v1\\/deal\\/searchpage\\/defaultword script-path=https://raw.githubusercontent.com/aoomee/Loon-Adblock-Plugins/main/scripts/meituan-clean.js,requires-body=true,tag=美团搜索热词",
    "http-response ^https?:\\/\\/apimobile\\.meituan\\.com\\/group\\/v1\\/deal\\/searchpage\\/hotword\\/city\\/divide\\/hotrecommend\\/ script-path=https://raw.githubusercontent.com/aoomee/Loon-Adblock-Plugins/main/scripts/meituan-clean.js,requires-body=true,tag=美团热搜推荐",
    "http-response ^https?:\\/\\/assistify\\.meituan\\.com\\/assistant\\/getAppClientHornConfig script-path=https://raw.githubusercontent.com/aoomee/Loon-Adblock-Plugins/main/scripts/meituan-clean.js,requires-body=true,tag=美团AI角标",
    "http-response ^https?:\\/\\/mop\\.meituan\\.com\\/mop\\/entry\\/shoppingCartEntry script-path=https://raw.githubusercontent.com/aoomee/Loon-Adblock-Plugins/main/scripts/meituan-clean.js,requires-body=true,tag=美团购物车横幅",
    "http-response ^https?:\\/\\/mop\\.meituan\\.com\\/api\\/entryModule\\/startupPicture script-path=https://raw.githubusercontent.com/aoomee/Loon-Adblock-Plugins/main/scripts/meituan-clean.js,requires-body=true,tag=美团开屏广告",
)
MEITUAN_CANONICAL_TRIGGER = "http-response ^https?:\\/\\/(?:p\\d\\.meituan\\.net\\/linglong\\/|web\\.meituan\\.com\\/api\\/miniprogram\\/(?:tabbar\\/all\\/query|index\\/aggregate)|apimobile\\.meituan\\.com\\/(?:aggroup\\/indexTab|group\\/v1\\/deal\\/searchpage\\/(?:defaultword|hotword\\/city\\/divide\\/hotrecommend\\/))|feedguess\\.meituan\\.com\\/lycoris\\/scene\\/(?:gwc_feed1_2265|personalcenter_2154)(?:\\?|$)|mt-personalcenter\\.meituan\\.com\\/usercenter\\/display|assistify\\.meituan\\.com\\/assistant\\/getAppClientHornConfig|mop\\.meituan\\.com\\/(?:mop\\/entry\\/shoppingCartEntry|api\\/entryModule\\/startupPicture)) script-path=https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/meituan/meituan.js,tag=MEITUAN-CONSOLIDATED,requires-body=true"
MEITUAN_LEGACY_SCRIPT_MARKERS = (
    "Res/Scripts/AntiAd/meituan.js",
    "Res/Scripts/AntiAd/meituanwm.js",
    "scripts/meituan-clean.js",
)



ZHIHU_RESPONSE_LEGACY_TRIGGERS = frozenset((
    "response if ${url} ~= /^https:\\/\\/(?:api|page-info)\\.zhihu\\.com\\/(?:answers|articles)\\/v2\\/\\d+/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/zhihu/zhihu.js\") with enable=vihu_enable, tag=\"知乎移除首页推广\", requires_body=true",
    "response if ${url} ~= /^https:\\/\\/api\\.zhihu\\.com\\/commercial_api\\/app_float_layer/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/zhihu/zhihu.js\") with enable=vihu_enable, tag=\"知乎移除首页推广\", requires_body=true",
    "response if ${url} ~= /^https:\\/\\/api\\.zhihu\\.com\\/feed\\/render\\/tab\\/config\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/zhihu/zhihu.js\") with enable=vihu_enable, tag=\"知乎移除首页推广\", requires_body=true",
    "response if ${url} ~= /^https:\\/\\/api\\.zhihu\\.com\\/(?:moments_v3|topstory\\/hot-lists\\/total|topstory\\/recommend)/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/zhihu/zhihu.js\") with enable=vihu_enable, tag=\"知乎移除首页推广\", requires_body=true",
    "response if ${url} ~= /^https:\\/\\/api\\.zhihu\\.com\\/root\\/tab/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/zhihu/zhihu.js\") with enable=vihu_enable, tag=\"知乎精简顶部标签\", requires_body=true",
    "response if ${url} ~= /^https:\\/\\/api\\.zhihu\\.com\\/v2\\/topstory\\/hot-lists\\/everyone-seeing\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/zhihu/zhihu.js\") with enable=vihu_enable, tag=\"知乎移除首页推广\", requires_body=true",
    "response if ${url} ~= /^https:\\/\\/api\\.zhihu\\.com\\/bazaar\\/vip_tab\\/header\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/zhihu/zhihu.js\") with enable=vihu_enable, tag=\"知乎移除会员页面推广\", requires_body=true",
    "response if ${url} ~= /^https:\\/\\/api\\.zhihu\\.com\\/next-(?:bff|data|render)/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/zhihu/zhihu.js\") with enable=vihu_enable, tag=\"知乎移除回答详情页推广\", requires_body=true",
    "response if ${url} ~= /^https:\\/\\/api\\.zhihu\\.com\\/questions\\/\\d+(?:\\/answers|\\/feeds|\\?include=)/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/zhihu/zhihu.js\") with enable=vihu_enable, tag=\"知乎移除回答详情页推广\", requires_body=true",
    "response if ${url} ~= /^https:\\/\\/www\\.zhihu\\.com\\/api\\/v4\\/(?:articles|answers)\\/\\d+\\/recommendations?\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/zhihu/zhihu.js\") with enable=vihu_enable, tag=\"知乎移除回答详情页推广\", requires_body=true",
    "response if ${url} ~= /^https:\\/\\/appcloud2\\.zhihu\\.com\\/v3\\/config/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/zhihu/zhihu.js\") with enable=vihu_enable, tag=\"知乎拦截服务器推送配置\", requires_body=true",
    "response if ${url} ~= /^https:\\/\\/m-cloud\\.zhihu\\.com\\/api\\/cloud\\/config\\/all\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/zhihu/zhihu.js\") with enable=vihu_enable, tag=\"知乎拦截服务器推送配置\", requires_body=true",
))
ZHIHU_RESPONSE_CANONICAL_TRIGGERS = (
    "response if ${url} ~= /^https:\\/\\/(?:(?:api|page-info)\\.zhihu\\.com\\/(?:answers|articles)\\/v2\\/\\d+|api\\.zhihu\\.com\\/(?:commercial_api\\/app_float_layer|feed\\/render\\/tab\\/config\\?|moments_v3|topstory\\/hot-lists\\/total|topstory\\/recommend|v2\\/topstory\\/hot-lists\\/everyone-seeing\\?))/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/zhihu/zhihu.js\") with enable=vihu_enable, tag=\"知乎移除首页推广\", requires_body=true",
    "response if ${url} ~= /^https:\\/\\/api\\.zhihu\\.com\\/root\\/tab/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/zhihu/zhihu.js\") with enable=vihu_enable, tag=\"知乎精简顶部标签\", requires_body=true",
    "response if ${url} ~= /^https:\\/\\/api\\.zhihu\\.com\\/bazaar\\/vip_tab\\/header\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/zhihu/zhihu.js\") with enable=vihu_enable, tag=\"知乎移除会员页面推广\", requires_body=true",
    "response if ${url} ~= /^https:\\/\\/(?:api\\.zhihu\\.com\\/(?:next-(?:bff|data|render)|questions\\/\\d+(?:\\/answers|\\/feeds|\\?include=))|www\\.zhihu\\.com\\/api\\/v4\\/(?:articles|answers)\\/\\d+\\/recommendations?\\?)/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/zhihu/zhihu.js\") with enable=vihu_enable, tag=\"知乎移除回答详情页推广\", requires_body=true",
    "response if ${url} ~= /^https:\\/\\/(?:appcloud2\\.zhihu\\.com\\/v3\\/config|m-cloud\\.zhihu\\.com\\/api\\/cloud\\/config\\/all\\?)/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/zhihu/zhihu.js\") with enable=vihu_enable, tag=\"知乎拦截服务器推送配置\", requires_body=true",
)
ZHIHU_RESPONSE_SCRIPT_MARKER = "Scripts/zhihu/zhihu.js"

def consolidate_zhihu_response_scripts(lines):
    """Collapse the complete known Zhihu inventory; preserve safe partial upstream inventories."""
    normalize = lambda value: re.sub(
        r"enable=\$\{([^}]+)\}",
        r"enable=\1",
        re.sub(r"\\+", "", value.strip()),
    )
    section = ""
    scoped = []
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
        elif section == "Script" and not line.lstrip().startswith("#"):
            scoped.append(line.strip())

    known = {normalize(trigger) for trigger in ZHIHU_RESPONSE_LEGACY_TRIGGERS}
    canonical = {normalize(trigger) for trigger in ZHIHU_RESPONSE_CANONICAL_TRIGGERS}
    replace_set = known - canonical
    counts = {trigger: sum(normalize(line) == trigger for line in scoped) for trigger in known}
    canonical_counts = {trigger: sum(normalize(line) == trigger for line in scoped) for trigger in canonical}
    unknown = [
        line for line in scoped
        if ZHIHU_RESPONSE_SCRIPT_MARKER in line
        and normalize(line) not in known and normalize(line) not in canonical
    ]

    if unknown:
        raise ValueError("Zhihu response script inventory contains an unknown trigger: " + unknown[0])
    if any(count > 1 for count in counts.values()) or any(count > 1 for count in canonical_counts.values()):
        raise ValueError("Zhihu response script inventory contains duplicate triggers")
    if not any(counts.values()) and not any(canonical_counts.values()):
        return list(lines), 0
    if (all(canonical_counts[trigger] == 1 for trigger in canonical)
            and all(counts[trigger] == 0 for trigger in replace_set)):
        return list(lines), 0

    # An upstream may legitimately remove some legacy triggers. Do not partially
    # rewrite an incomplete inventory; preserve its existing behavior unchanged.
    if (not all(counts[trigger] == 1 for trigger in known)
            or any(canonical_counts[trigger] != (1 if trigger in known else 0) for trigger in canonical)):
        return list(lines), 0

    placeholder_switch = any(
        ("enable=$" + "{") in line for line in scoped if normalize(line) in known
    )
    insert_triggers = [
        re.sub(r"enable=([A-Za-z0-9_]+)", "enable=$" + "{" + r"\1}", trigger)
        if placeholder_switch else trigger
        for trigger in ZHIHU_RESPONSE_CANONICAL_TRIGGERS
        if normalize(trigger) not in known
    ]

    output = []
    section = ""
    inserted = False
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue
        stripped = line.strip()
        if section == "Script" and normalize(stripped) in replace_set:
            if not inserted:
                output.extend(insert_triggers)
                inserted = True
            continue
        output.append(line)
    if not inserted or len(insert_triggers) != 3:
        raise ValueError("Zhihu canonical trigger insertion failed")
    return output, len(ZHIHU_RESPONSE_LEGACY_TRIGGERS) - len(ZHIHU_RESPONSE_CANONICAL_TRIGGERS)



def consolidate_soul_scripts(lines):
    """Collapse the 14 exact Soul response-body triggers into two case-safe matchers."""
    normalize = lambda value: re.sub(r"enable=\$\{([^}]+)\}", r"enable=\1", value.strip())
    section = ""
    scoped = []
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
        elif section == "Script" and not line.lstrip().startswith("#"):
            scoped.append(line.strip())

    legacy = {normalize(trigger) for trigger in SOUL_LEGACY_TRIGGERS}
    canonical = {normalize(trigger) for trigger in SOUL_CANONICAL_TRIGGERS}
    counts = {trigger: sum(normalize(line) == trigger for line in scoped) for trigger in legacy}
    canonical_counts = {trigger: sum(normalize(line) == trigger for line in scoped) for trigger in canonical}
    unknown = [
        line for line in scoped
        if SOUL_SCRIPT_MARKER in line and normalize(line) not in legacy and normalize(line) not in canonical
    ]

    if not any(counts.values()) and not any(canonical_counts.values()):
        # The retired FMZ feed may leave no recognized legacy Soul inventory;
        # preserve any remaining upstream variant without attempting consolidation.
        return list(lines), 0
    if any(count > 1 for count in counts.values()) or any(count > 1 for count in canonical_counts.values()):
        raise ValueError("Soul script trigger inventory duplicated; refusing ambiguous consolidation")
    if (all(count == 1 for count in canonical_counts.values())
            and not any(counts.values()) and not unknown):
        return list(lines), 0
    if any(canonical_counts.values()):
        raise ValueError("Soul script trigger inventory changed; refusing partial or mixed consolidation")
    if unknown or any(count != 1 for count in counts.values()):
        # Incomplete source snapshots are valid after upstream retirement. Keep
        # every original trigger untouched; only the full reviewed inventory is
        # eligible for replacement by the two canonical local matchers.
        return list(lines), 0

    preserve_interpolation = any(
        "enable=${" in line for line in scoped if SOUL_SCRIPT_MARKER in line
    )
    canonical_output = list(SOUL_CANONICAL_TRIGGERS)
    if preserve_interpolation:
        canonical_output = [
            re.sub(r"enable=([A-Za-z0-9_]+)", r"enable=${\1}", trigger)
            for trigger in canonical_output
        ]

    output = []
    section = ""
    inserted = 0
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue
        if section == "Script" and normalize(line) in legacy:
            if inserted < len(canonical_output):
                output.append(canonical_output[inserted])
                inserted += 1
            continue
        output.append(line)
    if inserted != len(canonical_output):
        raise ValueError("Soul canonical trigger insertion failed")
    return output, len(SOUL_LEGACY_TRIGGERS)


def consolidate_meituan_scripts(lines):
    """Collapse the exact 11 reviewed Meituan triggers into one local matcher."""
    section = ""
    scoped = []
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
        elif section == "Script" and not line.lstrip().startswith("#"):
            scoped.append(line.strip())

    counts = [scoped.count(trigger) for trigger in MEITUAN_LEGACY_TRIGGERS]
    canonical_count = scoped.count(MEITUAN_CANONICAL_TRIGGER)
    known = set(MEITUAN_LEGACY_TRIGGERS)
    unknown_legacy = [
        line for line in scoped
        if any(marker in line for marker in MEITUAN_LEGACY_SCRIPT_MARKERS)
        and line not in known
    ]

    if not any(counts) and not canonical_count and not unknown_legacy:
        return list(lines), 0
    if canonical_count == 1 and not any(counts) and not unknown_legacy:
        return list(lines), 0

    # The current upstream has removed the eight aoomee Meituan app triggers,
    # while retaining the three exact R-Store image/mini-program triggers.
    # The checked-in local handler still implements the reviewed union of all
    # eleven endpoints, so rebuild that single local matcher only for this
    # exact, known R-Store-only inventory. Any other partial set still fails closed.
    rstore_only_inventory = counts == [1, 1, 1] + [0] * (len(MEITUAN_LEGACY_TRIGGERS) - 3)
    if canonical_count or unknown_legacy or (
        not rstore_only_inventory and any(count != 1 for count in counts)
    ):
        missing = [trigger for trigger, count in zip(MEITUAN_LEGACY_TRIGGERS, counts) if count == 0]
        duplicate = [trigger for trigger, count in zip(MEITUAN_LEGACY_TRIGGERS, counts) if count > 1]
        raise ValueError(
            "Meituan script trigger inventory changed; refusing partial or mixed consolidation; "
            + f"counts={counts}, canonical={canonical_count}, unknown={unknown_legacy}, "
            + f"missing={missing}, duplicate={duplicate}"
        )

    output = []
    section = ""
    inserted = False
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue
        if section == "Script" and line.strip() in known:
            if not inserted:
                output.append(MEITUAN_CANONICAL_TRIGGER)
                inserted = True
            continue
        output.append(line)
    if not inserted:
        raise ValueError("Meituan canonical trigger insertion failed")
    return output, sum(counts) - 1



SOUL_LEGACY_TRIGGERS = frozenset((
    "response if ${url} ~= /^https?:\\/\\/api-pay\\.soulapp\\.cn\\/vip\\/meet\\/userInfo/ then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api-pay\\.soulapp\\.cn\\/privilege\\/supervip\\/status/ then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api-account\\.soulapp\\.cn\\/teenager\\/config/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api-a\\.soulapp\\.cn\\/v\\d\\/post\\/gift\\/list/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api-a\\.soulapp\\.cn\\/official\\/scene\\/module/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api-user\\.soulapp\\.cn\\/furion\\/position\\/content/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api-user\\.soulapp\\.cn\\/v\\d\\/planet\\/config/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api-chat\\.soulapp\\.cn\\/chat\\/limitInfo/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/post\\.soulapp\\.cn\\/hot\\/soul\\/rank/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/post\\.soulapp\\.cn\\/v\\d\\/post\\/homepage\\/guide\\/card/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/post\\.soulapp\\.cn\\/v\\d\\/post\\/recSquare\\/subTabs/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/chat-live\\.soulapp\\.cn\\/chatroom\\/chatClassifyRoomList/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/gateway-mobile-gray\\.soulapp\\.cn\\/mobile\\/app\\/version\\/queryIos/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/47\\.110\\.187\\.87\\/winterfell\\/v2\\/getIpByDomain/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
))
SOUL_CANONICAL_TRIGGERS = (
    "response if ${url} ~= /^https?:\\/\\/api-pay\\.soulapp\\.cn\\/(?:vip\\/meet\\/userInfo|privilege\\/supervip\\/status)/ then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/(?:api-account\\.soulapp\\.cn\\/teenager\\/config|api-a\\.soulapp\\.cn\\/(?:v\\d\\/post\\/gift\\/list|official\\/scene\\/module)|api-user\\.soulapp\\.cn\\/(?:furion\\/position\\/content|v\\d\\/planet\\/config)|api-chat\\.soulapp\\.cn\\/chat\\/limitInfo|post\\.soulapp\\.cn\\/(?:hot\\/soul\\/rank|v\\d\\/post\\/(?:homepage\\/guide\\/card|recSquare\\/subTabs))|chat-live\\.soulapp\\.cn\\/chatroom\\/chatClassifyRoomList|gateway-mobile-gray\\.soulapp\\.cn\\/mobile\\/app\\/version\\/queryIos|47\\.110\\.187\\.87\\/winterfell\\/v2\\/getIpByDomain)/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
)
SOUL_SCRIPT_MARKER = "Scripts/soul/soul_ads.js"

# Douyin / Hongguo boundary safety:
# - dig.bdurl.net is ByteDance HTTPDNS, not an ad host.
# - webcast-open.douyin.com supplies recommended live-room feeds, not ads.
# - the broad "minigame" keyword can disable ByteDance mini-game runtime.
DOUYIN_HONGGUO_UNSAFE_RULES = {
    "DOMAIN,webcast-open.douyin.com,REJECT",
    "DOMAIN-KEYWORD,minigame,REJECT",
    "DOMAIN-SUFFIX,dig.bdurl.net,REJECT",
    "DOMAIN,dig.bdurl.net,REJECT",
}
DOUYIN_LIVE_FEED_REWRITE_RULES = {
    r"^https?:\/\/webcast-open\.douyin\.com\/webcast\/openapi\/feed\/ reject-dict",
    r"request if ${url} ~= /^https:\/\/webcast-open\.douyin\.com\/webcast\/openapi\/feed\/\?/ then reject_dict(200)",
}
DOUYIN_LIVE_FEED_OPTIONAL_REWRITE_RULES = {
    r'response if ${url} ~= /^https?:\/\/webcast-open\.douyin\.com\/webcast\/openapi\/feed\//i then response.body.mock("json", "{}", 200)',
}
DOUYIN_LIVE_FEED_HOST = "webcast-open.douyin.com"


DOUYIN_NON_AD_SERVICE_HOST_BLOCKS = (
    "DOMAIN,content-open.douyin.com,REJECT",
    "DOMAIN,effect.snssdk.com,REJECT",
    "DOMAIN,security-lq.snssdk.com,REJECT",
    "DOMAIN,reading.snssdk.com,REJECT",
)
DOUYIN_AD_HOST_GUARD = "DOMAIN-SUFFIX,pangolin-sdk-toutiao.com,REJECT"


def remove_douyin_non_ad_service_host_blocks(lines):
    """Remove broad blocks on content, effect, security, and reading services."""
    section = ""
    output = []
    counts = {rule: 0 for rule in DOUYIN_NON_AD_SERVICE_HOST_BLOCKS}
    saw_target = False

    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue
        value = line.strip()
        if section == "Rule" and value:
            parts = [part.strip() for part in value.split(",")]
            if len(parts) >= 2 and parts[0].upper() in ("DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD") and parts[1].lower() in ("content-open.douyin.com", "effect.snssdk.com", "security-lq.snssdk.com", "reading.snssdk.com"):
                saw_target = True
                if value not in counts:
                    raise ValueError("Douyin non-ad service host rule changed; refusing unreviewed removal: " + value)
            if value in counts:
                saw_target = True
                counts[value] += 1
                if counts[value] > 1:
                    raise ValueError("duplicate Douyin non-ad service host block: " + value)
                continue
        output.append(line)

    if not saw_target:
        return list(lines), 0
    present = [count for count in counts.values() if count]
    if len(present) != len(DOUYIN_NON_AD_SERVICE_HOST_BLOCKS):
        raise ValueError("Douyin non-ad service host inventory is partial; refusing cleanup")
    if sum(1 for line in output if line.strip() == DOUYIN_AD_HOST_GUARD) != 1:
        raise ValueError("Douyin dedicated Pangle ad host guard missing or duplicated")
    return output, sum(present)

BILIBILI_CORE_SERVICE_OVERBLOCKS = (
    ("Rule", "DOMAIN,api.biliapi.com,REJECT"),
    ("Rule", "DOMAIN,app.biliapi.com,REJECT"),
    ("Rule", "DOMAIN,api.biliapi.net,REJECT"),
    ("Rule", "DOMAIN,app.biliapi.net,REJECT"),
    ("Rewrite", "request if ${url} ~= /^https?:\\/\\/httpdns\\.bilivideo\\.com\\/resolve\\?host/ then reject(404)"),
    ("Rewrite", "^https?:\\/\\/api\\.bilibili\\.com\\/x\\/web-interface\\/zone\\?jsonp reject-dict"),
    ("Rewrite", "^https?:\\/\\/app\\.bilibili\\.com\\/x\\/resource\\/ip reject-dict"),
)
BILIBILI_AD_HOST_GUARDS = (
    "DOMAIN-SUFFIX,ad.bilibili.com,REJECT",
    "DOMAIN-SUFFIX,adcommon.bilibili.com,REJECT",
)
BILIBILI_AD_PATH_MARKERS = (
    "app.bilibili.com/x/v2/splash/",
    "app.bilibili.com/x/v2/feed/index",
    "api.bilibili.com/pgc/activity/deliver",
)


def remove_bilibili_core_service_overblocks(lines):
    """Remove broad Bili API, HTTPDNS, and IP-geolocation blocks, not ad filters."""
    section = ""
    output = []
    counts = {item: 0 for item in BILIBILI_CORE_SERVICE_OVERBLOCKS}
    saw_target = False
    normalized_rewrites = []

    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue
        value = line.strip()
        normalized = value.replace(chr(92), "")
        if section == "Rule" and value:
            parts = [part.strip() for part in value.split(",")]
            if len(parts) >= 2 and parts[0].upper() in ("DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD") and parts[1].lower() in ("api.biliapi.com", "app.biliapi.com", "api.biliapi.net", "app.biliapi.net"):
                saw_target = True
                if (section, value) not in BILIBILI_CORE_SERVICE_OVERBLOCKS:
                    raise ValueError("Bilibili API host rule changed; refusing unreviewed removal: " + value)
        if section == "Rewrite":
            if "bilibili.com" in normalized or "bilivideo.com" in normalized:
                normalized_rewrites.append(normalized)
            if "httpdns.bilivideo.com/resolve?host" in normalized or "bilibili.com/x/web-interface/zone" in normalized or "bilibili.com/x/resource/ip" in normalized:
                if (section, value) not in BILIBILI_CORE_SERVICE_OVERBLOCKS:
                    raise ValueError("Bilibili core-service Rewrite changed; refusing unreviewed removal: " + value)
        if (section, value) in counts:
            saw_target = True
            counts[(section, value)] += 1
            if counts[(section, value)] > 1:
                raise ValueError("duplicate Bilibili core-service overblock")
            continue
        output.append(line)

    if not saw_target:
        return list(lines), 0
    present = [count for count in counts.values() if count]
    if len(present) != len(BILIBILI_CORE_SERVICE_OVERBLOCKS):
        return list(lines), 0
    if any(sum(1 for line in output if line.strip() == guard) != 1 for guard in BILIBILI_AD_HOST_GUARDS):
        return list(lines), 0
    normalized_text = "\n".join(normalized_rewrites)
    if any(marker not in normalized_text for marker in BILIBILI_AD_PATH_MARKERS):
        return list(lines), 0
    return output, sum(present)

BILIBILI_NON_AD_FEATURE_RULES = (
    r'response if ${url} ~= /^https:\/\/api\.bilibili\.com\/x\/pd-proxy\/tracker\?/ then response.json.jq(`.data[][]? = "stun.chat.bilibili.com:3478"`)',
    r'response if ${url} ~= /^https:\/\/api\.live\.bilibili\.com\/xlive\/open-interface\/v2\/tracker\/conf\?/ then response.json.jq(`.data.domains = ["wss://tracker.chat.bilibili.com"]`)',
    r'response if ${url} == "https://grpc.biliapi.net/bilibili.app.interface.v1.Search/DefaultWords" then response.body.mock("text", "AAAAACEaHeaQnOe0ouinhumikeOAgeeVquWJp+aIlnVw5Li7KAE=", 200, true) | response.header.set("grpc-status", "0")',
    r'response if ${url} == "https://grpc.biliapi.net/bilibili.app.interface.v1.Teenagers/ModeStatus" then response.body.mock("text", "AAAAABMKEQgCEgl0ZWVuYWdlcnMgAioA", 200, true) | response.header.set("grpc-status", "0")',
    "^https?:\\/\\/(?:app\\.bilibili\\.com|grpc\\.biliapi\\.net)\\/bilibili\\.app\\.interface\\.v\\d\\.Search\\/DefaultWords reject-dict",
    "response if ${url} ~= /^https:\\/\\/grpc\\.biliapi\\.net\\/bilibili\\.app\\.interface\\.v1\\.Teenagers\\/ModeStatus$/ then response.body.mock(\"text\", `AAAAABMKEQgCEgl0ZWVuYWdlcnMgAioA`, 200, true)",
    "response if ${url} ~= /^https:\\/\\/grpc\\.biliapi\\.net\\/bilibili\\.app\\.interface\\.v1\\.Search\\/DefaultWords$/ then response.body.mock(\"text\", `AAAAACEaHeaQnOe0ouinhumikeOAgeeVquWJp+aIlnVw5Li7KAE=`, 200, true)",
    "response if ${url} ~= /^https:\\/\\/api\\.bilibili\\.com\\/x\\/pd-proxy\\/tracker\\?/ then response.json.jq(`.data[][]?=\"stun.chat.bilibili.com:3478\"`)",
    "response if ${url} ~= /^https:\\/\\/api\\.bilibili\\.com\\/pgc\\/view\\/v2\\/app\\/season\\?/ then response.json.jq(`del(.data.payment)`)",
    "response if ${url} ~= /^https:\\/\\/app\\.bilibili\\.com\\/x\\/resource\\/show\\/skin\\?/ then response.json.delete(\"data.common_equip\")",
    "response if ${url} ~= /^https:\\/\\/app\\.bilibili\\.com\\/x\\/resource\\/show\\/tab\\/v2\\?/ then response.json.jq_file(\"https://raw.githubusercontent.com/kokoryh/Sparkle/refs/heads/master/jq/bilibili.tab.jq\")",
    "response if ${url} ~= /^https:\\/\\/app\\.bilibili\\.com\\/x\\/v2\\/account\\/myinfo\\?/ then response.json.jq(`.data.vip |= if . != null and .status == 0 then . + { status: 1, type: 2, due_date: 9005270400000, role: 15 } else . end`)",
    "^https:\\/\\/api\\.live\\.bilibili\\.com\\/xlive\\/open-interface\\/v2\\/tracker\\/conf\\? response-body-json-jq '.data.domains=[\"wss://tracker.chat.bilibili.com\"]'",
    "^https:\\/\\/api\\.bilibili\\.com\\/pgc\\/view\\/v2\\/app\\/season\\? response-body-json-jq 'del(.data.payment)'",
    "^https:\\/\\/grpc\\.biliapi\\.net\\/bilibili\\.app\\.interface\\.v1\\.Teenagers\\/ModeStatus$ mock-response-body data-type=text data=\"AAAAABMKEQgCEgl0ZWVuYWdlcnMgAioA\" mock-data-is-base64=true",
    "^https:\\/\\/grpc\\.biliapi\\.net\\/bilibili\\.app\\.interface\\.v1\\.Search\\/DefaultWords$ mock-response-body data-type=text data=\"AAAAACEaHeaQnOe0ouinhumikeOAgeeVquWJp+aIlnVw5Li7KAE=\" mock-data-is-base64=true",
    "^https:\\/\\/api\\.bilibili\\.com\\/x\\/pd-proxy\\/tracker\\? response-body-json-jq '.data[][]?=\"stun.chat.bilibili.com:3478\"'",
    "^https:\\/\\/app\\.bilibili\\.com\\/x\\/resource\\/show\\/skin\\? response-body-json-del data.common_equip",
    "^https:\\/\\/app\\.bilibili\\.com\\/x\\/resource\\/show\\/tab\\/v2\\? response-body-json-jq '.data.tab = [ { pos: 1, id: 39, name: \"直播\", tab_id: \"直播tab\", uri: \"bilibili://live/home\" }, { pos: 2, id: 40, name: \"推荐\", tab_id: \"推荐tab\", uri: \"bilibili://pegasus/promo\", default_selected: 1 }, { pos: 3, id: 41, name: \"热门\", tab_id: \"hottopic\", uri: \"bilibili://pegasus/hottopic\" }, { pos: 4, id: 3502, name: \"动画\", tab_id: \"bangumi\", uri: \"bilibili://pgc/home\" }, { pos: 5, id: 3503, name: \"影视\", tab_id: \"bilibili://pgc/cinema-tab\", uri: \"bilibili://pgc/cinema-tab\" } ] | .data.top = [ { pos: 1, id: 3510, name: \"消息\", tab_id: \"消息Top\", uri: \"bilibili://link/im_home\", icon: \"http://i0.hdslb.com/bfs/archive/d43047538e72c9ed8fd8e4e34415fbe3a4f632cb.png\" } ] | .data.bottom = [ { pos: 1, id: 177, name: \"首页\", tab_id: \"home\", uri: \"bilibili://main/home/\", icon: \"http://i0.hdslb.com/bfs/archive/63d7ee88d471786c1af45af86e8cb7f607edf91b.png\", icon_selected: \"http://i0.hdslb.com/bfs/archive/e5106aa688dc729e7f0eafcbb80317feb54a43bd.png\" }, { pos: 2, id: 179, name: \"关注\", tab_id: \"dynamic\", uri: \"bilibili://following/home/\", icon: \"http://i0.hdslb.com/bfs/archive/86dfbe5fa32f11a8588b9ae0fccb77d3c27cedf6.png\", icon_selected: \"http://i0.hdslb.com/bfs/archive/25b658e1f6b6da57eecba328556101dbdcb4b53f.png\" }, { pos: 5, id: 181, name: \"我的\", tab_id: \"我的Bottom\", uri: \"bilibili://user_center/\", icon: \"http://i0.hdslb.com/bfs/archive/4b0b2c49ffeb4f0c2e6a4cceebeef0aab1c53fe1.png\", icon_selected: \"http://i0.hdslb.com/bfs/archive/a54a8009116cb896e64ef14dcf50e5cade401e00.png\" } ]'",
    "http-response ^https?:\\/\\/(?:app\\.bilibili\\.com|grpc\\.biliapi\\.net)\\/bilibili\\.app\\.interface\\.v\\d\\.Teenagers\\/ModeStatus script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliProtoA.js,tag=BAICIZHAN-2,requires-body=true,binary-body-mode=true",
)
# Romeo upstreams ship both /i and non-/i variants; keep TFInfo/ViewEndPage but exclude PlayPause.
BILIBILI_NON_AD_FEATURE_REPLACEMENTS = (
    ("response if ${url} ~= /^https:\\/\\/grpc\\.biliapi\\.net\\/bilibili\\.app\\.(view\\.v1\\.View\\/TFInfo|viewunite\\.v1\\.View\\/(PlayPause|ViewEndPage))$/ then response.body.mock(\"text\", \"AAAAAAA=\", 200, true) | response.header.set(\"grpc-status\", \"0\")", "response if ${url} ~= /^https:\\/\\/grpc\\.biliapi\\.net\\/bilibili\\.app\\.(view\\.v1\\.View\\/TFInfo|viewunite\\.v1\\.View\\/ViewEndPage)$/ then response.body.mock(\"text\", \"AAAAAAA=\", 200, true) | response.header.set(\"grpc-status\", \"0\")"),
    ("response if ${url} ~= /^https:\\/\\/grpc\\.biliapi\\.net\\/bilibili\\.app\\.(view\\.v1\\.View\\/TFInfo|viewunite\\.v1\\.View\\/(PlayPause|ViewEndPage))$/i then response.body.mock(\"text\", \"AAAAAAA=\", 200, true) | response.header.set(\"grpc-status\", \"0\")", "response if ${url} ~= /^https:\\/\\/grpc\\.biliapi\\.net\\/bilibili\\.app\\.(view\\.v1\\.View\\/TFInfo|viewunite\\.v1\\.View\\/ViewEndPage)$/i then response.body.mock(\"text\", \"AAAAAAA=\", 200, true) | response.header.set(\"grpc-status\", \"0\")"),
    ("response if ${url} ~= /^https:\\/\\/grpc\\.biliapi\\.net\\/bilibili\\.app\\.(interface\\.v1\\.(Teenagers\\/ModeStatus|Search\\/DefaultWords)|view\\.v1\\.View\\/TFInfo|viewunite\\.v1\\.View\\/ViewEndPage)$/ then response.header.add(\"grpc-status\", \"0\")", "response if ${url} ~= /^https:\\/\\/grpc\\.biliapi\\.net\\/bilibili\\.app\\.(view\\.v1\\.View\\/TFInfo|viewunite\\.v1\\.View\\/ViewEndPage)$/ then response.header.add(\"grpc-status\", \"0\")"),
    ("^https:\\/\\/grpc\\.biliapi\\.net\\/bilibili\\.app\\.(interface\\.v1\\.(Teenagers\\/ModeStatus|Search\\/DefaultWords)|view\\.v1\\.View\\/TFInfo|viewunite\\.v1\\.View\\/(PlayPause|ViewEndPage))$ response-header-add grpc-status 0", "^https:\\/\\/grpc\\.biliapi\\.net\\/bilibili\\.app\\.(view\\.v1\\.View\\/TFInfo|viewunite\\.v1\\.View\\/ViewEndPage)$ response-header-add grpc-status 0"),
    ("^https:\\/\\/grpc\\.biliapi\\.net\\/bilibili\\.app\\.(view\\.v1\\.View\\/TFInfo|viewunite\\.v1\\.View\\/(PlayPause|ViewEndPage))$ mock-response-body data-type=text data=\"AAAAAAA=\" mock-data-is-base64=true", "^https:\\/\\/grpc\\.biliapi\\.net\\/bilibili\\.app\\.(view\\.v1\\.View\\/TFInfo|viewunite\\.v1\\.View\\/ViewEndPage)$ mock-response-body data-type=text data=\"AAAAAAA=\" mock-data-is-base64=true"),
)
BILIBILI_AD_PATH_MARKERS = (
    "app.bilibili.com/x/v2/splash/",
    "app.bilibili.com/x/v2/feed/index",
    "api.bilibili.com/pgc/activity/deliver",
)


def normalize_bilibili_non_ad_feature_overrides(lines):
    """Remove non-ad VIP/paywall/teen-mode and network/UI mutations from the ad plugin."""
    section = ""
    output = []
    remove_counts = {rule: 0 for rule in BILIBILI_NON_AD_FEATURE_RULES}
    old_counts = {old: 0 for old, _ in BILIBILI_NON_AD_FEATURE_REPLACEMENTS}
    new_counts = {new: 0 for _, new in BILIBILI_NON_AD_FEATURE_REPLACEMENTS}
    saw_target = False
    normalized_rewrites = []
    unknown_markers = (
        ("/x/v2/account/myinfo", "due_date"),
        ("/pgc/view/v2/app/season", "payment"),
        ("Teenagers/ModeStatus", "mock"),
        ("Teenagers/ModeStatus", "script-path"),
        ("Teenagers/ModeStatus", "grpc-status"),
        ("Search/DefaultWords", "mock"),
        ("Search/DefaultWords", "reject-dict"),
        ("Search/DefaultWords", "grpc-status"),
        ("/x/pd-proxy/tracker", "stun.chat.bilibili.com"),
        ("/xlive/open-interface/v2/tracker/conf", "tracker.chat.bilibili.com"),
        ("/x/resource/show/skin", "common_equip"),
        ("/x/resource/show/tab/v2", "response"),
        ("PlayPause", "mock-response-body"),
        ("PlayPause", "response.body.mock"),
    )

    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue
        value = line.strip()
        normalized = value.replace(chr(92), "")
        if section in ("Rewrite", "Script"):
            if value in remove_counts:
                remove_counts[value] += 1
                saw_target = True
                if remove_counts[value] > 1:
                    raise ValueError("duplicate Bilibili non-ad feature rule")
                continue
            if section == "Script" and any(marker in normalized and detail in normalized for marker, detail in unknown_markers):
                raise ValueError("Bilibili non-ad script trigger changed; refusing unreviewed behavior: " + value)
        if section == "Rewrite":
            replacement = dict(BILIBILI_NON_AD_FEATURE_REPLACEMENTS)
            if value in old_counts:
                old_counts[value] += 1
                saw_target = True
                if old_counts[value] > 1:
                    raise ValueError("duplicate Bilibili non-ad feature replacement source")
                output.append(replacement[value])
                continue
            if value in new_counts:
                new_counts[value] += 1
                saw_target = True
                if new_counts[value] > 1:
                    raise ValueError("duplicate Bilibili narrowed gRPC header/mock rule")
                output.append(line)
                continue
            if any(marker in normalized and detail in normalized for marker, detail in unknown_markers):
                raise ValueError("Bilibili non-ad feature rule changed; refusing unreviewed behavior: " + value)
            if any(marker in normalized for marker in BILIBILI_AD_PATH_MARKERS):
                normalized_rewrites.append(normalized)
        output.append(line)

    if not saw_target:
        return list(lines), 0
    # Upstream feeds may prune already-reviewed non-ad feature rows independently.
    # Remove only exact known rows that are still present; duplicate rows and changed
    # variants remain fail-closed through the checks above and unknown_markers below.
    for old, new in BILIBILI_NON_AD_FEATURE_REPLACEMENTS:
        if old_counts[old] + new_counts[new] > 1:
            raise ValueError("Bilibili gRPC feature rule replacement inventory duplicated")
    normalized_text = "\n".join(normalized_rewrites)
    if any(marker not in normalized_text for marker in BILIBILI_AD_PATH_MARKERS):
        # A retired supplemental feed may have supplied some of these path guards.
        # Preserve the original feature rules unless the full ad-path coverage remains.
        return list(lines), 0
    return output, sum(remove_counts.values()) + sum(old_counts.values())

def remove_douyin_hongguo_unsafe_rules(lines):
    """Remove only the reviewed HTTPDNS/runtime/live-feed blocks and MITM host."""
    section = ""
    rule_counts = {rule: 0 for rule in DOUYIN_HONGGUO_UNSAFE_RULES}
    rewrite_counts = {rule: 0 for rule in DOUYIN_LIVE_FEED_REWRITE_RULES}
    optional_rewrite_counts = {rule: 0 for rule in DOUYIN_LIVE_FEED_OPTIONAL_REWRITE_RULES}
    live_feed_host_count = 0
    unknown = []

    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        value = line.strip()
        if section == "Rule":
            if value in rule_counts:
                rule_counts[value] += 1
            elif any(marker in value for marker in (
                "webcast-open.douyin.com", "dig.bdurl.net", "minigame"
            )):
                unknown.append((section, value))
        elif section == "Rewrite":
            if value in rewrite_counts:
                rewrite_counts[value] += 1
            elif value in optional_rewrite_counts:
                optional_rewrite_counts[value] += 1
            elif "webcast-open.douyin.com" in value:
                unknown.append((section, value))
        elif section == "MITM" and value.lower().startswith("hostname") and "=" in value:
            _, host_text = value.split("=", 1)
            live_feed_host_count += sum(
                host.strip().lower() == DOUYIN_LIVE_FEED_HOST
                for host in host_text.split(",")
            )
        elif section == "MITM" and DOUYIN_LIVE_FEED_HOST in value.lower():
            unknown.append((section, value))

    counts = list(rule_counts.values()) + list(rewrite_counts.values())
    optional_count = sum(optional_rewrite_counts.values())
    if unknown:
        raise ValueError(
            "Douyin/Hongguo safety inventory changed; refusing unknown rules: "
            + repr(unknown)
        )
    if not any(counts) and optional_count == 0 and live_feed_host_count == 0:
        return list(lines), 0

    output = []
    section = ""
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue
        value = line.strip()
        if section == "Rule" and value in DOUYIN_HONGGUO_UNSAFE_RULES:
            continue
        if section == "Rewrite" and (
            value in DOUYIN_LIVE_FEED_REWRITE_RULES
            or value in DOUYIN_LIVE_FEED_OPTIONAL_REWRITE_RULES
        ):
            continue
        if section == "MITM" and value.lower().startswith("hostname") and "=" in value:
            key, host_text = line.split("=", 1)
            hosts = [host.strip() for host in host_text.split(",") if host.strip()]
            hosts = [host for host in hosts if host.lower() != DOUYIN_LIVE_FEED_HOST]
            line = key + "= " + ", ".join(hosts)
        output.append(line)
    return output, sum(counts) + optional_count + live_feed_host_count





DOUYIN_TNC_REJECT_RULES = (
    "DOMAIN,tnc3-alisc1.zijieapi.com,REJECT",
    "DOMAIN,tnc3-alisc1.snssdk.com,REJECT",
    "DOMAIN,tnc3-aliec2.snssdk.com,REJECT",
    "AND, ((DOMAIN-KEYWORD, tnc), (AND, ((OR, ((DOMAIN-KEYWORD, -bjlgy), (DOMAIN-KEYWORD, -alisc), (DOMAIN-KEYWORD, -aliec), (DOMAIN-KEYWORD, -alisg))), (OR, ((DOMAIN-SUFFIX, snssdk.com), (DOMAIN-SUFFIX, isnssdk.com), (DOMAIN-SUFFIX, toutiaoapi.com), (DOMAIN-SUFFIX, bytedance.com), (DOMAIN-SUFFIX, zijieapi.com)))))), REJECT",
)
DOUYIN_TNC_DIRECT_RULE = "AND, ((DOMAIN-KEYWORD, tnc), (OR, ((DOMAIN-SUFFIX, capcutapi.com), (DOMAIN-SUFFIX, zijieapi.com), (DOMAIN-SUFFIX, isnssdk.com), (DOMAIN-SUFFIX, toutiaoapi.com), (DOMAIN-SUFFIX, bytedance.com), (DOMAIN-SUFFIX, snssdk.com), (DOMAIN-SUFFIX, sgsnssdk.com)))), DIRECT"


def remove_douyin_tnc_conflicting_rejects(lines):
    """Remove stale TNC rejects so the existing TNC DIRECT rule can take effect."""
    section = ""
    output = []
    reject_counts = {rule: 0 for rule in DOUYIN_TNC_REJECT_RULES}
    direct_count = 0
    unknown_tnc_rejects = []

    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue
        value = line.strip()
        if section == "Rule":
            if value in reject_counts:
                reject_counts[value] += 1
                if reject_counts[value] > 1:
                    raise ValueError("duplicate Douyin TNC reject rule")
                continue
            if value == DOUYIN_TNC_DIRECT_RULE:
                direct_count += 1
            else:
                compact = value.replace(" ", "").lower()
                if compact.startswith("domain,tnc3-") and compact.endswith(",reject") and any(
                    suffix in compact for suffix in ("snssdk.com", "zijieapi.com", "isnssdk.com", "bytedance.com", "toutiaoapi.com")
                ):
                    unknown_tnc_rejects.append(value)
                elif "domain-keyword,tnc" in compact and compact.endswith(",reject"):
                    unknown_tnc_rejects.append(value)
        output.append(line)

    present = [count for count in reject_counts.values() if count]
    if not present and direct_count == 0 and not unknown_tnc_rejects:
        return list(lines), 0
    if unknown_tnc_rejects or direct_count != 1:
        raise ValueError("Douyin TNC rule inventory changed; refusing unknown rejects or missing DIRECT guard")
    return output, sum(present)

DOUYIN_CONTENT_CDN_OVERBLOCKS = (
    ("Rule", "DOMAIN-KEYWORD,p3.pstatp.com,REJECT"),
    ("Rule", "DOMAIN-KEYWORD,video-cn.snssdk.com,REJECT"),
    # Current fmz200 blockAds source variants.
    ("Rewrite", r"request if ${url} ~= /^https?:\/\/p\d\.pstatp\.com\/origin/i then reject(404)"),
    ("Rewrite", r"request if ${url} ~= /^https?:\/\/pb\d\.pstatp\.com\/origin/i then reject(404)"),
    # Previously accepted merged-source variants.
    ("Rewrite", r"request if ${url} ~= /^https?:\/\/p(b)?\d\.pstatp\.com\/origin/ then reject(404)"),
    ("Rewrite", r"request if ${url} ~= /^https?:\/\/p\d\.pstatp\.com\/origin/ then reject(404)"),
    ("Rewrite", r"request if ${url} ~= /^https?:\/\/pb\d\.pstatp\.com\/origin/ then reject(404)"),
)
DOUYIN_CDN_REQUIRED_AD_PATH_MARKERS = (
    "(obj|img)/(ad-app-package|ad)/",
    "/obj/ad-pattern/renderer",
    "snssdk.com/api/ad/",
    "from=ad",
)


def remove_douyin_content_cdn_overblocks(lines):
    """Remove only known content-CDN overblocks while requiring explicit ad-path coverage."""
    section = ""
    output = []
    counts = {item: 0 for item in DOUYIN_CONTENT_CDN_OVERBLOCKS}
    # 合并来源可能把正则转义再次编码（\/、\\/；\.、\\.)。
    # 仅将连续转义符归一为一个，按等价正则匹配已审核的精确清理清单。
    def inventory_key(section_name, rule):
        canonical = re.sub(r"\\{2,}([A-Za-z./])", lambda match: "\\" + match.group(1), rule)
        # Some upstream variants leave the dot in the literal host unescaped;
        # normalize only this exact hostname token before inventory comparison.
        canonical = re.sub(r"(?<!\\)pstatp\.com", r"pstatp\.com", canonical)
        return section_name, canonical

    known_inventory = {inventory_key(section_name, rule): (section_name, rule)
                       for section_name, rule in DOUYIN_CONTENT_CDN_OVERBLOCKS}
    saw_target = False
    unknown_overblocks = []
    normalized_rewrites = []

    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue
        value = line.strip()
        normalized = value.replace(chr(92), "")
        if section == "Rule" and value:
            parts = [part.strip() for part in value.split(",")]
            compact_rule = ",".join(parts)
            if len(parts) >= 2 and parts[0].upper() in ("DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD") and parts[1].lower() in ("p3.pstatp.com", "video-cn.snssdk.com"):
                saw_target = True
                key = (section, compact_rule)
                if key not in counts:
                    raise ValueError("Douyin content CDN domain rule changed; refusing unreviewed scope change: " + value)
                counts[key] += 1
                if counts[key] > 1:
                    raise ValueError("duplicate Douyin content CDN overblock: " + value)
                continue
        if section == "Rewrite":
            if "pstatp" in normalized or "pglstatp-toutiao" in normalized or "snssdk.com" in normalized:
                normalized_rewrites.append(normalized)
            if "pstatp.com/origin" in normalized and "reject(404)" in normalized:
                saw_target = True
                key = inventory_key(section, value)
                inventory_item = known_inventory.get(key)
                if inventory_item is None:
                    unknown_overblocks.append(value)
                else:
                    counts[inventory_item] += 1
                    if counts[inventory_item] > 1:
                        raise ValueError("duplicate Douyin content CDN origin Rewrite")
                    continue
        output.append(line)

    if not saw_target:
        return list(lines), 0
    if unknown_overblocks:
        raise ValueError("Douyin content CDN overblock inventory changed; refusing partial cleanup: " + repr(unknown_overblocks))
    normalized_rewrite_text = "\n".join(normalized_rewrites)
    missing_ad_paths = [
        marker for marker in DOUYIN_CDN_REQUIRED_AD_PATH_MARKERS
        if marker not in normalized_rewrite_text
    ]
    if missing_ad_paths:
        # When a supplemental feed is intentionally retired, its companion
        # path-scoped rules may disappear too. Keep the original exact rules
        # rather than removing the broader source entries without full coverage.
        return list(lines), 0
    return output, sum(counts.values())



# The merged plugin contains broad HTTP+HTTPS Kugou matchers plus HTTPS-only
# copies of the same paths. The latter are strict subsets and cannot add coverage.
KUGOU_REDUNDANT_HTTPS_REWRITES = {
    "^https:\\/\\/fx\\.service\\.kugou\\.com\\/mfx-kugoulive\\/ad\\/ reject-dict",
    "^https:\\/\\/gateway(retry)?\\.kugou\\.com\\/adp\\/ad\\/ reject-dict",
    "^https:\\/\\/gateway(retry)?\\.kugou\\.com\\/ads\\.gateway\\/ reject-dict",
    "^https:\\/\\/gateway(retry)?\\.kugou\\.com\\/v\\d\\/feeds\\/follow_feed_fallback reject-dict",
    "^https:\\/\\/gateway(retry)?\\.kugou\\.com\\/mstc\\/musicsymbol\\/v\\d\\/system\\/profile reject-dict",
    "^https:\\/\\/gateway(retry)?\\.kugou\\.com\\/searchnofocus\\/v\\d\\/search_no_focus_word reject-dict",
    "^https:\\/\\/gateway(retry)?\\.kugou\\.com\\/adp\\/bubble\\/v\\d\\/song_play reject-dict",
    "^https:\\/\\/gateway(retry)?\\.kugou\\.com\\/singerdiscuss\\/v\\d\\/entrance\\/comment reject-dict",
    "^https:\\/\\/gateway(retry)?\\.kugou\\.com\\/r\\/v\\d\\/general\\/putin\\/midad reject-dict",
    "^https:\\/\\/gateway(retry)?\\.kugou\\.com\\/ocean\\/v\\d\\/sound\\/banner reject-dict",
    "^https:\\/\\/gzacshow\\.kugou\\.com\\/mfx-rt-show\\/cdn\\/mo\\/show\\/headline reject-dict",
    "^https:\\/\\/m1fxgroup\\.kugou\\.com\\/fxsing\\/yqc\\/alongInfo\\/getUserAlongInfo reject-dict",
    "^https:\\/\\/hwstore\\.kugou\\.com\\/v\\d\\/get_store_data reject-dict",
    "^https:\\/\\/ep\\.kugou\\.com\\/v\\d\\/album_shop\\/get_entrance_info reject-dict",
}
KUGOU_OBSOLETE_ROOM_LIST_REWRITE = "^https?:\\/\\/gzacshow\\.kugou\\.com\\/mfanxing-home\\/cdn\\/room\\/index\\/list_v reject-dict"
JIN10_REDUNDANT_AD_RESPONSE_REWRITE = "^https:\\/\\/jad-api\\.jin10\\.com\\/ad reject-dict"


def remove_kugou_jin10_redundant_rewrites(lines):
    section = ""
    counts = {rule: 0 for rule in KUGOU_REDUNDANT_HTTPS_REWRITES}
    obsolete_count = jin10_response_count = 0
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        value = line.strip()
        if section == "Rewrite":
            if value in counts:
                counts[value] += 1
            elif value == KUGOU_OBSOLETE_ROOM_LIST_REWRITE:
                obsolete_count += 1
            elif value == JIN10_REDUNDANT_AD_RESPONSE_REWRITE:
                jin10_response_count += 1
            elif any(
                value.startswith(prefix := rule.rsplit(" ", 1)[0])
                and (len(value) == len(prefix) or value[len(prefix)].isspace())
                for rule in KUGOU_REDUNDANT_HTTPS_REWRITES
                | {KUGOU_OBSOLETE_ROOM_LIST_REWRITE, JIN10_REDUNDANT_AD_RESPONSE_REWRITE}
            ):
                raise ValueError("Kugou/Jin10 rewrite inventory changed; refusing drifted matcher or action")
    values = list(counts.values())
    if all(count == 0 for count in values) and obsolete_count == 0 and jin10_response_count == 0:
        return list(lines), 0
    if any(count > 1 for count in values) or obsolete_count > 1 or jin10_response_count > 1:
        raise ValueError("Kugou/Jin10 rewrite inventory changed; refusing duplicate or drifted deduplication")
    if any(count == 0 for count in values) or obsolete_count == 0 or jin10_response_count == 0:
        return list(lines), 0
    output, section = [], ""
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue
        value = line.strip()
        if section == "Rewrite" and (
            value in KUGOU_REDUNDANT_HTTPS_REWRITES
            or value in (KUGOU_OBSOLETE_ROOM_LIST_REWRITE, JIN10_REDUNDANT_AD_RESPONSE_REWRITE)
        ):
            continue
        output.append(line)
    return output, len(KUGOU_REDUNDANT_HTTPS_REWRITES) + 2


# Zhihu had several HTTPS-only request blockers fully covered by older HTTP/HTTPS
# rules with the same action. Keep the broader rules and remove only these exact
# HTTPS subsets; do not conflate reject(404), reject-dict, or reject_dict(200).
ZHIHU_REQUEST_SHADOW_PAIRS = (
    (
        r"request if ${url} ~= /^https:\/\/api\.zhihu\.com\/unlimited\/go\/my_card/ then reject(404)",
        r"request if ${url} ~= /^https?:\/\/api\.zhihu\.com\/unlimited\/go\/my_card/ then reject(404)",
        "unlimited/go/my_card/ then",
    ),
    (
        r"request if ${url} ~= /^https:\/\/api\.zhihu\.com\/ab\/api\/v1\/products\/zhihu\/platforms\/ios\/config/ then reject(404)",
        r"request if ${url} ~= /^https?:\/\/api\.zhihu\.com\/ab\/api\/v\d\/products\/zhihu\/platforms\/ios\/config/ then reject(404)",
        "products/zhihu/platforms/ios/config",
    ),
    (
        r"request if ${url} ~= /^https:\/\/zhuanlan\.zhihu\.com\/api\/articles\/\d+\/recommendation/ then reject(404)",
        r"request if ${url} ~= /^https?:\/\/zhuanlan\.zhihu\.com\/api\/articles\/\d+\/recommendation/ then reject(404)",
        "zhuanlan",
    ),
    (
        r"request if ${url} ~= /^https:\/\/zhstatic\.zhihu\.com\/brand-ad/ then reject(404)",
        r"request if ${url} ~= /^https?:\/\/zhstatic\.zhihu\.com\/brand-ad/ then reject(404)",
        "brand-ad",
    ),
)


def remove_redundant_zhihu_request_rules(lines):
    """Remove only exact HTTPS subsets when their same-action HTTP/S cover exists."""
    normalize = lambda value: re.sub(r"\\+/", "/", value.strip())
    known = {
        normalize(rule): (index, is_redundant)
        for index, (redundant, canonical, _marker) in enumerate(ZHIHU_REQUEST_SHADOW_PAIRS)
        for is_redundant, rule in ((True, redundant), (False, canonical))
    }
    markers = tuple(marker for _redundant, _canonical, marker in ZHIHU_REQUEST_SHADOW_PAIRS)
    counts = {key: 0 for key in known}
    entries = []
    seen_groups = set()
    for line in lines:
        value = normalize(line)
        group_index = next((i for i, marker in enumerate(markers) if marker in value), None)
        if group_index is None:
            entries.append((line, None, False))
            continue
        matched = known.get(value)
        if matched is None or matched[0] != group_index:
            # New or drifted upstream blockers are retained verbatim.
            entries.append((line, None, False))
            continue
        counts[value] += 1
        if counts[value] > 1:
            raise ValueError("duplicate Zhihu request blocker; refusing ambiguous cleanup")
        seen_groups.add(group_index)
        entries.append((line, group_index, matched[1]))

    remove_groups = set()
    for index in seen_groups:
        redundant, canonical, _marker = ZHIHU_REQUEST_SHADOW_PAIRS[index]
        redundant_count = counts[normalize(redundant)]
        canonical_count = counts[normalize(canonical)]
        if canonical_count > 1 or redundant_count > 1:
            raise ValueError("duplicate Zhihu request blocker; refusing ambiguous cleanup")
        if canonical_count == 1 and redundant_count == 1:
            remove_groups.add(index)

    output = [
        line for line, group_index, is_redundant in entries
        if not (group_index in remove_groups and is_redundant)
    ]
    removed = sum(
        1 for _line, group_index, is_redundant in entries
        if group_index in remove_groups and is_redundant
    )
    return output, removed


# Zhihu answer and recommendation responses each had two independent JSON
# rewrites for the same matcher. Preserve both field operations in one jq pass.
ZHIHU_ANSWER_DELETE_REWRITE = r"^https:\/\/(api|page-info)(?:\.zhihu)?\.com\/answers\/v\d\/\d+(?:\?.*)?$ response-body-json-del third_business float_search_word"
ZHIHU_ANSWER_CARD_REWRITE = r"""^https:\/\/(api|page-info)(?:\.zhihu)?\.com\/answers\/v\d\/\d+(?:\?.*)?$ response-body-json-jq '.structured_content.segments |= map(select(.type != "card"))'"""
ZHIHU_ANSWER_COMBINED_REWRITE = r"""^https:\/\/(api|page-info)(?:\.zhihu)?\.com\/answers\/v\d\/\d+(?:\?.*)?$ response-body-json-jq 'del(.third_business, .float_search_word) | (.structured_content.segments |= map(select(.type != "card")))'"""

ZHIHU_TOPSTORY_COMPONENTS_REWRITE = r"""^https:\/\/api\.zhihu\.com\/topstory\/recommend\? response-body-json-jq '.data |= map(select(.type == "ComponentCard"))'"""
ZHIHU_TOPSTORY_RING_REWRITE = r"""^https:\/\/api\.zhihu\.com\/topstory\/recommend\? response-body-json-jq '.data[]?.children |= (if type == "array" then map(select(.id != "ring")) else . end)'"""
ZHIHU_TOPSTORY_COMBINED_REWRITE = r"""^https:\/\/api\.zhihu\.com\/topstory\/recommend\? response-body-json-jq '(.data |= map(select(.type == "ComponentCard"))) | (.data[]?.children |= (if type == "array" then map(select(.id != "ring")) else . end))'"""


def consolidate_zhihu_multi_action_rewrites(lines):
    """Coalesce only four source-verified Zhihu operations into two JSON passes."""
    expected = (
        ZHIHU_ANSWER_DELETE_REWRITE,
        ZHIHU_ANSWER_CARD_REWRITE,
        ZHIHU_TOPSTORY_COMPONENTS_REWRITE,
        ZHIHU_TOPSTORY_RING_REWRITE,
    )
    counts = {rule: sum(line.strip() == rule for line in lines) for rule in expected}
    if not any(counts.values()):
        return list(lines), 0
    if any(count != 1 for count in counts.values()):
        raise ValueError(
            "Zhihu multi-action rewrite inventory changed; refusing partial or drifted consolidation"
        )

    expected_set = set(expected)
    for line in lines:
        value = line.strip()
        normalized = re.sub(r"\\+/", "/", value)
        if ("topstory/recommend" in normalized or "answers/v" in normalized) and (
            "response-body-json" in value and value not in expected_set
        ):
            raise ValueError(
                "Zhihu same-matcher response rewrite changed; refusing unreviewed consolidation"
            )

    replacements = {
        ZHIHU_ANSWER_DELETE_REWRITE: ZHIHU_ANSWER_COMBINED_REWRITE,
        ZHIHU_TOPSTORY_COMPONENTS_REWRITE: ZHIHU_TOPSTORY_COMBINED_REWRITE,
    }
    removed = {ZHIHU_ANSWER_CARD_REWRITE, ZHIHU_TOPSTORY_RING_REWRITE}
    output = []
    for line in lines:
        value = line.strip()
        if value in replacements:
            output.append(replacements[value])
        elif value in removed:
            continue
        else:
            output.append(line)
    return output, 2




# Batch same-response JSON field deletions into Loon's native array form.
# Loon documents this as one batch instruction with the same ordered result.
KUAISHOU_STARTUP_SPLIT_DELETE_REWRITE = r"""response if ${url} ~= /^https:\/\/(apissl|az2-api(-js|-idc)?)\.(gifshow|ksapisrv)\.com\/rest\/system\/startup\?/ then response.json.delete("reskinConfig") | response.json.delete("sidebarExSquareStyle.moreList") | response.json.delete("sidebarExSquareStyle.topList") | response.json.jq(`.sidebarExSquareStyle.commonlyUsedList |= map(select(.title == "设置" or .title == "历史记录" or .title == "草稿箱" or .title == "我的钱包" or .title == "小程序" or .title == "未成年人模式" or .title == "官方客服" or .title == "内容偏好" or .title == "离线模式" or .title == "稍后再看" or .title == "举报中心" or .title == "挂件"))`)"""
KUAISHOU_STARTUP_BATCHED_DELETE_REWRITE = r"""response if ${url} ~= /^https:\/\/(apissl|az2-api(-js|-idc)?)\.(gifshow|ksapisrv)\.com\/rest\/system\/startup\?/ then response.json.delete(["reskinConfig", "sidebarExSquareStyle.moreList", "sidebarExSquareStyle.topList"]) | response.json.jq(`.sidebarExSquareStyle.commonlyUsedList |= map(select(.title == "设置" or .title == "历史记录" or .title == "草稿箱" or .title == "我的钱包" or .title == "小程序" or .title == "未成年人模式" or .title == "官方客服" or .title == "内容偏好" or .title == "离线模式" or .title == "稍后再看" or .title == "举报中心" or .title == "挂件"))`)"""

XIMALAYA_FOOTBALL_SPLIT_DELETE_REWRITE = r"""response if ${url} ~= /^https:\/\/(mobile|mobilehera|mobwsa)\.ximalaya\.com\/football-portal\/diff2\/batch\?/ then response.json.delete("json.ad") | response.json.delete("json.toc")"""
XIMALAYA_FOOTBALL_BATCHED_DELETE_REWRITE = r"""response if ${url} ~= /^https:\/\/(mobile|mobilehera|mobwsa)\.ximalaya\.com\/football-portal\/diff2\/batch\?/ then response.json.delete(["json.ad", "json.toc"])"""

XIMALAYA_PLAYPAGE_SPLIT_DELETE_REWRITE = r"""response if ${url} ~= /^https:\/\/mobwsa\.ximalaya\.com\/mobile-playpage\/playpage\/tabs\/v2\// then response.json.delete("data.playpage.resourceMap.defaultResource") | response.json.delete("data.playpage.resourceMap.playPageTip")"""
XIMALAYA_PLAYPAGE_BATCHED_DELETE_REWRITE = r"""response if ${url} ~= /^https:\/\/mobwsa\.ximalaya\.com\/mobile-playpage\/playpage\/tabs\/v2\// then response.json.delete(["data.playpage.resourceMap.defaultResource", "data.playpage.resourceMap.playPageTip"])"""


def batch_same_response_json_deletes(lines):
    """Batch each available source-verified delete group independently."""
    replacements = {
        KUAISHOU_STARTUP_SPLIT_DELETE_REWRITE: KUAISHOU_STARTUP_BATCHED_DELETE_REWRITE,
        XIMALAYA_FOOTBALL_SPLIT_DELETE_REWRITE: XIMALAYA_FOOTBALL_BATCHED_DELETE_REWRITE,
        XIMALAYA_PLAYPAGE_SPLIT_DELETE_REWRITE: XIMALAYA_PLAYPAGE_BATCHED_DELETE_REWRITE,
    }
    expected = set(replacements)
    combined = set(replacements.values())
    _validate_response_json_delete_batch_scope(lines, expected | combined)

    for original, batched in replacements.items():
        original_count = sum(line.strip() == original for line in lines)
        batched_count = sum(line.strip() == batched for line in lines)
        if original_count > 1 or batched_count > 1 or (original_count and batched_count):
            raise ValueError(
                "Response JSON delete batch inventory changed; refusing duplicate or mixed rule state"
            )

    output = [replacements.get(line.strip(), line) for line in lines]
    changed = sum(line.strip() in replacements for line in lines)
    return output, changed


def _validate_response_json_delete_batch_scope(lines, allowed_rules):
    matcher_markers = (
        "rest/system/startup",
        "football-portal/diff2/batch",
        "mobile-playpage/playpage/tabs/v2",
    )
    active_markers = {
        marker for marker in matcher_markers
        if any(marker in re.sub(r"\\+/", "/", rule) for rule in allowed_rules if rule in lines)
    }
    for line in lines:
        value = line.strip()
        normalized = re.sub(r"\\+/", "/", value)
        if any(marker in normalized for marker in active_markers) and (
            "response.json." in value and value not in allowed_rules
        ):
            raise ValueError(
                f"Same-matcher response JSON delete changed; refusing unreviewed consolidation: {value[:220]}"
            )


# Ximalaya homepage response used two separate JSON transforms on the same URL.
# Keep the deletion first, then make the optional entrance filtering failure-safe.
XIMALAYA_HOME_DELETE_REWRITE = r"""response if ${url} ~= /^https:\/\/(mobile|mobilehera|mobwsa)\.ximalaya\.com\/mobile-user\/v\d\/homePage\// then response.json.delete("data.freeListenV2")"""
XIMALAYA_HOME_ENTRANCE_REWRITE = r"""response if ${url} ~= /^https:\/\/(mobile|mobilehera|mobwsa)\.ximalaya\.com\/mobile-user\/v\d\/homePage\// then response.json.jq(`.data.serviceModule.entrances |= map(select(.name == "全部服务"))`)"""
XIMALAYA_HOME_COMBINED_REWRITE = r"""response if ${url} ~= /^https:\/\/(mobile|mobilehera|mobwsa)\.ximalaya\.com\/mobile-user\/v\d\/homePage\// then response.json.jq(`del(.data.freeListenV2) | (try (.data.serviceModule.entrances |= map(select(.name == "全部服务"))) catch .)`)"""


def consolidate_ximalaya_homepage_json_rewrites(lines):
    """Combine the two exact Ximalaya homepage JSON transforms into one parse."""
    expected = (XIMALAYA_HOME_DELETE_REWRITE, XIMALAYA_HOME_ENTRANCE_REWRITE)
    counts = {rule: sum(line.strip() == rule for line in lines) for rule in expected}
    if not any(counts.values()):
        return list(lines), 0
    if any(count != 1 for count in counts.values()):
        raise ValueError(
            "Ximalaya homepage rewrite inventory changed; refusing partial or drifted consolidation"
        )

    expected_set = set(expected)
    for line in lines:
        value = line.strip()
        normalized = re.sub(r"\\\\+/", "/", value)
        if "mobile-user" in normalized and "homePage" in normalized and (
            "response.json." in value and value not in expected_set
        ):
            raise ValueError(
                "Ximalaya homepage response rewrite changed; refusing unreviewed consolidation"
            )

    output = []
    inserted = False
    for line in lines:
        value = line.strip()
        if value == XIMALAYA_HOME_DELETE_REWRITE:
            output.append(XIMALAYA_HOME_COMBINED_REWRITE)
            inserted = True
        elif value == XIMALAYA_HOME_ENTRANCE_REWRITE:
            continue
        else:
            output.append(line)
    if not inserted:
        raise ValueError("Ximalaya combined rewrite insertion failed")
    return output, 1






# 微信解除链接限制：R-Store 与 zZPiglet 两份脚本主体逐字逻辑相同；
# RuCu6 MyBlockAds 版本存在 Spotify 链接解析差异，必须保留，不能视为重复。
WECHAT_UNBLOCK_URL_CANONICAL_TRIGGER = "http-response ^https?:\\/\\/(weixin110\\.qq|security.wechat)\\.com\\/cgi-bin\\/mmspamsupport-bin\\/newredirectconfirmcgi\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/Plugins/Wechat_Unblock_URL.js,tag=WECHAT,requires-body=true"
WECHAT_UNBLOCK_URL_REDUNDANT_TRIGGER = "response if ${url} ~= /^https\\:\\/\\/(weixin110\\.qq|security.wechat)\\.com\\/cgi-bin\\/mmspamsupport-bin\\/newredirectconfirmcgi\\?/i then script(\"https://raw.githubusercontent.com/zZPiglet/Task/master/asset/UnblockURLinWeChat.js\") with enable=lmjpxmvi_enable, tag=\"UnblockURLinWeChat-解除微信链接限制\", timeout=60, requires_body=true"
WECHAT_UNBLOCK_URL_DISTINCT_TRIGGER = "response if ${url} ~= /^https\\:\\/\\/(?:weixin110\\.qq|security\\.wechat)\\.com\\/cgi-bin\\/mmspamsupport-bin\\/newredirectconfirmcgi\\?/i then script(\"https://github.com/ifflagged/Romeo/raw/main/Modules/JavaScript/rucu6/myblockads/rucu6_wechat.js\") with tag=\"wechat\", requires_body=true"


def consolidate_wechat_unblock_url_scripts(lines):
    """Remove only the reviewed zZPiglet duplicate; preserve the distinct RuCu6 variant."""
    expected = (
        WECHAT_UNBLOCK_URL_CANONICAL_TRIGGER,
        WECHAT_UNBLOCK_URL_REDUNDANT_TRIGGER,
        WECHAT_UNBLOCK_URL_DISTINCT_TRIGGER,
    )

    def normalized_trigger(value):
        # blockAds.plugin interpolates this one known switch as ${...};
        # the equivalent Loon rule in the pinned snapshot uses the bare name.
        # Normalize only this exact variable spelling; all other drift fails closed.
        return value.strip().replace(
            "enable=${lmjpxmvi_enable}", "enable=lmjpxmvi_enable"
        )

    normalized_expected = {normalized_trigger(item): item for item in expected}
    counts = {item: 0 for item in expected}
    output, section, target_seen, removed = [], "", False, 0
    target_lines = []
    unknown_trigger = False
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue
        value = line.strip()
        normalized = re.sub(r"\\+", "", value).lower()
        if section == "Script" and "newredirectconfirmcgi" in normalized:
            target_seen = True
            target_lines.append(value)
            trigger = normalized_expected.get(normalized_trigger(value))
            if trigger is None:
                unknown_trigger = True
                output.append(line)
                continue
            counts[trigger] += 1
            if counts[trigger] > 1:
                raise ValueError("duplicate WeChat URL-unblock script trigger")
            if trigger != WECHAT_UNBLOCK_URL_REDUNDANT_TRIGGER:
                output.append(line)
            else:
                removed += 1
            continue
        output.append(line)

    if not target_seen:
        return list(lines), 0
    # Some upstream snapshots now ship only the R-Store canonical handler; accept
    # that exact single-source inventory even if cosmetic escaping/tag formatting drifts.
    target_sources = [item.lower() for item in target_lines]
    has_rstore_canonical = any(
        "raw.githubusercontent.com/zirawell/r-store/main/res/scripts/plugins/wechat_unblock_url.js" in item
        for item in target_sources
    )
    has_rucu6_variant = any("rucu6/myblockads/rucu6_wechat.js" in item for item in target_sources)
    has_zzpiglet_duplicate = any("zzpiglet/task" in item for item in target_sources)
    if (
        has_rstore_canonical
        and not has_zzpiglet_duplicate
        and (len(target_lines) == 1 or (len(target_lines) == 2 and has_rucu6_variant))
    ):
        # Preserve the current R-Store handler and the behaviorally distinct RuCu6 variant.
        return list(lines), 0
    if unknown_trigger:
        raise ValueError("WeChat URL-unblock script trigger changed; refusing unreviewed consolidation")
    if (
        counts[WECHAT_UNBLOCK_URL_CANONICAL_TRIGGER] == 1
        and counts[WECHAT_UNBLOCK_URL_REDUNDANT_TRIGGER] == 0
        and counts[WECHAT_UNBLOCK_URL_DISTINCT_TRIGGER] == 0
    ):
        # Current merged upstream snapshot contains only the canonical R-Store handler.
        # No duplicate exists to remove; preserve the lone handler without treating it as drift.
        return list(lines), 0
    if (
        counts[WECHAT_UNBLOCK_URL_CANONICAL_TRIGGER] == 1
        and counts[WECHAT_UNBLOCK_URL_REDUNDANT_TRIGGER] == 0
        and counts[WECHAT_UNBLOCK_URL_DISTINCT_TRIGGER] == 1
    ):
        return list(lines), 0
    if all(counts[item] == 1 for item in expected):
        return output, removed
    raise ValueError("WeChat URL-unblock script trigger inventory incomplete; refusing consolidation")


# 淘宝 OSS 广告素材使用专用路径；整域 REJECT 会扩大到该 CDN 上的非广告请求。
TAOBAO_OSS_BROAD_DOMAIN_RULE = "DOMAIN,ossgw.alicdn.com,REJECT"
TAOBAO_OSS_LEGACY_CREATIVE_RULE = r"^https?:\/\/ossgw.alicdn.com\/creatives-assets\/image\/ reject-200"
TAOBAO_OSS_SCOPED_CREATIVE_RULE = r"^https?:\/\/ossgw\.alicdn\.com\/creatives-assets\/ reject-200"


def scope_taobao_ossgw_ad_assets(lines):
    """Replace the broad OSS host block with a path-scoped ad-creative matcher.

    Fail closed on unreviewed ossgw rules, duplicate inventory, or missing MITM.
    """
    output, section = [], ""
    broad_count = legacy_count = scoped_count = 0
    mitm_has_host = False
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue
        value = line.strip()
        if section == "Rule" and "ossgw.alicdn.com" in value.lower():
            if value != TAOBAO_OSS_BROAD_DOMAIN_RULE:
                raise ValueError("Taobao ossgw Rule changed; refusing unreviewed scope reduction")
            broad_count += 1
            if broad_count > 1:
                raise ValueError("duplicate Taobao ossgw broad-domain rule")
            continue
        if section == "Rewrite" and "ossgw.alicdn.com" in value.lower():
            if value == TAOBAO_OSS_LEGACY_CREATIVE_RULE:
                legacy_count += 1
                if legacy_count > 1:
                    raise ValueError("duplicate Taobao ossgw legacy creative matcher")
                output.append(TAOBAO_OSS_SCOPED_CREATIVE_RULE)
                continue
            if value == TAOBAO_OSS_SCOPED_CREATIVE_RULE:
                scoped_count += 1
                if scoped_count > 1:
                    raise ValueError("duplicate Taobao ossgw scoped creative matcher")
                output.append(line)
                continue
            raise ValueError("Taobao ossgw Rewrite changed; refusing unreviewed scope reduction")
        if section == "MITM" and value.lower().startswith("hostname") and "=" in value:
            hosts = [host.strip().lower() for host in value.split("=", 1)[1].split(",")]
            mitm_has_host = "ossgw.alicdn.com" in hosts
        output.append(line)

    if legacy_count and scoped_count:
        raise ValueError("both legacy and scoped Taobao ossgw matchers are present")
    if broad_count and legacy_count + scoped_count != 1:
        raise ValueError("Taobao ossgw broad block lacks exactly one reviewed path-scoped replacement")
    if legacy_count + scoped_count and not mitm_has_host:
        raise ValueError("Taobao ossgw creative matcher requires its existing MITM hostname")
    return output, broad_count + legacy_count


# Tuhu's three endpoints mount legacy http-response and modern response scripts.
# The modern matcher has /i and therefore covers the legacy case-sensitive scope.
TUHU_SCRIPT_LEGACY_TRIGGERS = (
    "http-response ^https?:\\/\\/(cl-)?gateway\\.tuhu\\.cn(\\/cl)?\\/cl-common-api\\/api\\/personalCenter\\/getCmsModuleList script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/tuhu.js,tag=TUHU,requires-body=true",
    "http-response ^https?:\\/\\/(cl-)?gateway\\.tuhu\\.cn(\\/cl)?\\/[a-z-]+\\/homePage\\/getHomePageInfo script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/tuhu.js,tag=TUHU-2,requires-body=true",
    "http-response ^https?:\\/\\/(cl-)?gateway\\.tuhu\\.cn(\\/cl)?\\/cl-shop-api\\/shopTab\\/getModuleForC script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/tuhu.js,tag=TUHU-3,requires-body=true",
)
TUHU_SCRIPT_CANONICAL_TRIGGERS = (
    "response if ${url} ~= /^https?:\\/\\/(cl-)?gateway\\.tuhu\\.cn(\\/cl)?\\/cl-common-api\\/api\\/personalCenter\\/getCmsModuleList/i then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/tuhu.js\") with tag=\"途虎养车去广告\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/(cl-)?gateway\\.tuhu\\.cn(\\/cl)?\\/[a-z-]+\\/homePage\\/getHomePageInfo/i then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/tuhu.js\") with tag=\"途虎养车去广告\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/(cl-)?gateway\\.tuhu\\.cn(\\/cl)?\\/cl-shop-api\\/shopTab\\/getModuleForC/i then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/tuhu.js\") with tag=\"途虎养车去广告\", timeout=60, requires_body=true",
)


def remove_duplicate_tuhu_scripts(lines):
    """Keep the newer case-insensitive response triggers; remove legacy duplicates."""
    normalize = lambda value: re.sub(r"\\+", "", value.strip())
    canonical = {normalize(item): item for item in TUHU_SCRIPT_CANONICAL_TRIGGERS}
    legacy = {normalize(item): item for item in TUHU_SCRIPT_LEGACY_TRIGGERS}
    counts = {item: 0 for item in (*TUHU_SCRIPT_CANONICAL_TRIGGERS, *TUHU_SCRIPT_LEGACY_TRIGGERS)}
    output, section, target_seen, removed = [], "", False, 0

    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue

        normalized = normalize(line)
        is_target = section == "Script" and "gateway.tuhu.cn" in normalized and "tuhu.js" in normalized
        if not is_target:
            output.append(line)
            continue

        target_seen = True
        if normalized in canonical:
            trigger = canonical[normalized]
            counts[trigger] += 1
            if counts[trigger] > 1:
                raise ValueError("duplicate canonical Tuhu script trigger; refusing ambiguous cleanup")
            output.append(line)
            continue
        if normalized in legacy:
            trigger = legacy[normalized]
            counts[trigger] += 1
            if counts[trigger] > 1:
                raise ValueError("duplicate legacy Tuhu script trigger; refusing ambiguous cleanup")
            removed += 1
            continue
        raise ValueError("Tuhu script trigger inventory changed; refusing unreviewed consolidation")

    if not target_seen:
        return output, 0
    if not all(counts[item] == 1 for item in TUHU_SCRIPT_CANONICAL_TRIGGERS):
        return list(lines), 0
    return output, removed


# R-Store cntv.js and fmz200 cnftp.js overlap on 26 iQIYI / MGTV / Youku responses.
# Keep FMZ's iQIYI + Youku handlers; convert MGTV to modern response syntax while
# retaining R-Store's broader vN matchers and the existing mhgotv_enable switch.
CNFTP_DUPLICATE_REMOVE_TRIGGERS = (
    "http-response ^https?:\\/\\/[\\d\\.]+\\/3f1\\/cards\\.iqiyi\\.com\\/(views_home\\/3\\.0\\/qy_home|waterfall\\/3\\.0\\/feed)\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js,tag=IQIYI,requires-body=true",
    "http-response ^https?:\\/\\/access\\.if\\.iqiyi\\.com\\/3f1\\/cards\\.iqiyi\\.com\\/(views_category\\/3\\.0\\/category_home|views_home\\/3\\.0\\/qy_home|waterfall\\/3\\.0\\/feed)\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js,tag=IQIYI-2,requires-body=true",
    "http-response ^https?:\\/\\/cards\\.iqiyi\\.com\\/views_category\\/3\\.0\\/(category_home|categorylib_content|film_hybrid)\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js,tag=IQIYI-3,requires-body=true",
    "http-response ^https?:\\/\\/cards\\.iqiyi\\.com\\/(views_home\\/3\\.0\\/qy_home|waterfall\\/3\\.0\\/feed)\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js,tag=IQIYI-4,requires-body=true",
    "http-response ^https?:\\/\\/cards\\.iqiyi\\.com\\/views_plt\\/3\\.0\\/player_tabs_v2\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js,tag=IQIYI-5,requires-body=true",
    "http-response ^https?:\\/\\/cards\\.iqiyi\\.com\\/views_search\\/3\\.0\\/(hot_query_)?search\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js,tag=IQIYI-6,requires-body=true",
    "http-response ^https?:\\/\\/comment-card\\.iqiyi\\.com\\/views_comment\\/3\\.0\\/long_video_comments\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js,tag=IQIYI-7,requires-body=true",
    "http-response ^https?:\\/\\/iface2\\.iqiyi\\.com\\/aggregate\\/3\\.0\\/getMyMenus\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js,tag=IQIYI-8,requires-body=true",
    "http-response ^https?:\\/\\/iface2\\.iqiyi\\.com\\/control\\/3\\.0\\/init_proxy\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js,tag=IQIYI-9,requires-body=true",
    "http-response ^https?:\\/\\/iface2\\.iqiyi\\.com\\/fusion\\/3\\.0\\/common_switch\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js,tag=IQIYI-10,requires-body=true",
    "http-response ^https?:\\/\\/iface2\\.iqiyi\\.com\\/views\\/3\\.0\\/(bottom_theme|home_top_menu)\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js,tag=IQIYI-11,requires-body=true",
    "http-response ^https?:\\/\\/search\\.video\\.iqiyi\\.com\\/q\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js,tag=IQIYI-12,requires-body=true",
    "http-response ^https?:\\/\\/(kjp|t7z)\\.cupid\\.iqiyi\\.com\\/mixer\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js,tag=IQIYI-13,requires-body=true",
    "http-response ^https?:\\/\\/me\\.bz\\.mgtv\\.com\\/v\\d\\/module\\/list\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js,tag=MGTV,requires-body=true",
    "http-response ^https?:\\/\\/mob-st\\.bz\\.mgtv\\.com\\/odin\\/c\\d\\/channel\\/index\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js,tag=MGTV-2,requires-body=true",
    "http-response ^https?:\\/\\/dc2?\\.bz\\.mgtv\\.com\\/dynamic\\/v\\d\\/channel\\/(index|vrsList)\\/\\w script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js,tag=MGTV-3,requires-body=true",
    "http-response ^https?:\\/\\/mobile\\.api\\.mgtv\\.com\\/mobile\\/config\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js,tag=MGTV-4,requires-body=true",
    "http-response ^https?:\\/\\/mobile\\.api\\.mgtv\\.com\\/v\\d+\\/video\\/info\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js,tag=MGTV-5,requires-body=true",
    "http-response ^https?:\\/\\/mobile-thor\\.api\\.mgtv\\.com\\/v\\d\\/vod\\/info\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js,tag=MGTV-6,requires-body=true",
    "http-response ^https?:\\/\\/mobileso\\.bz\\.mgtv\\.com\\/mobile\\/recommend\\/v\\d\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js,tag=MGTV-7,requires-body=true",
    "http-response ^https?:\\/\\/acs\\.youku\\.com\\/gw\\/mtop\\.youku\\.columbus\\.(gateway\\.new\\.execute|home\\.feed|home\\.query|uc\\.query|ycp\\.query) script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js,tag=YOUKU,requires-body=true",
    "http-response ^https?:\\/\\/acs\\.youku\\.com\\/gw\\/mtop\\.youku\\.haidai\\.lantern\\.appconfig\\.get script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js,tag=YOUKU-2,requires-body=true",
    "http-response ^https?:\\/\\/acs\\.youku\\.com\\/gw\\/mtop\\.youku\\.huluwa\\.dispatcher\\.youthmode\\.config2 script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js,tag=YOUKU-3,requires-body=true",
    "http-response ^https?:\\/\\/acs\\.youku\\.com\\/gw\\/mtop\\.youku\\.soku\\.yksearch script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js,tag=YOUKU-4,requires-body=true",
    "http-response ^https?:\\/\\/push\\.m\\.youku\\.com\\/collect-api\\/get_push_interval_config_wx\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js,tag=YOUKU-5,requires-body=true",
    "http-response ^https?:\\/\\/un-acs\\.youku\\.com\\/gw\\/mtop\\.youku\\.play\\.ups\\.appinfo\\.get script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js,tag=YOUKU-6,requires-body=true",
)
CNFTP_DUPLICATE_KEEP_SOURCE_TRIGGERS = (
    "response if ${url} ~= /^https?:\\/\\/[\\d\\.]+\\/3f1\\/cards\\.iqiyi\\.com\\/(views_home\\/3\\.0\\/qy_home|waterfall\\/3\\.0\\/feed)\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=aiqiyi_enable, tag=\"爱奇艺首页信息流广告\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/access\\.if\\.iqiyi\\.com\\/3f1\\/cards\\.iqiyi\\.com\\/(views_category\\/3\\.0\\/category_home|views_home\\/3\\.0\\/qy_home|waterfall\\/3\\.0\\/feed)\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=aiqiyi_enable, tag=\"爱奇艺首页信息流广告\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/cards\\.iqiyi\\.com\\/views_category\\/3\\.0\\/(category_home|categorylib_content|film_hybrid)\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=aiqiyi_enable, tag=\"爱奇艺首页信息流广告\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/cards\\.iqiyi\\.com\\/(views_home\\/3\\.0\\/qy_home|waterfall\\/3\\.0\\/feed)\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=aiqiyi_enable, tag=\"爱奇艺首页信息流广告\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/cards\\.iqiyi\\.com\\/views_plt\\/3\\.0\\/player_tabs_v2\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=aiqiyi_enable, tag=\"爱奇艺播放详情页广告\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/cards\\.iqiyi\\.com\\/views_search\\/3\\.0\\/(hot_query_)?search\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=aiqiyi_enable, tag=\"爱奇艺搜索页列表广告\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/comment-card\\.iqiyi\\.com\\/views_comment\\/3\\.0\\/long_video_comments\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=aiqiyi_enable, tag=\"爱奇艺评论区\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/iface2\\.iqiyi\\.com\\/aggregate\\/3\\.0\\/getMyMenus\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=aiqiyi_enable, tag=\"爱奇艺我的页面菜单\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/iface2\\.iqiyi\\.com\\/control\\/3\\.0\\/init_proxy\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=aiqiyi_enable, tag=\"爱奇艺首页左上角天气\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/iface2\\.iqiyi\\.com\\/fusion\\/3\\.0\\/common_switch\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=aiqiyi_enable, tag=\"爱奇艺通用控制\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/iface2\\.iqiyi\\.com\\/views\\/3\\.0\\/(bottom_theme|home_top_menu)\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=aiqiyi_enable, tag=\"爱奇艺底部tab、顶部tab\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/search\\.video\\.iqiyi\\.com\\/q\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=aiqiyi_enable, tag=\"爱奇艺搜索框填充词\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/(kjp|t7z)\\.cupid\\.iqiyi\\.com\\/mixer\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=aiqiyi_enable, tag=\"爱奇艺开屏广告\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/me\\.bz\\.mgtv\\.com\\/v3\\/module\\/list\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=mhgotv_enable, tag=\"芒果TV我的页面\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/mob-st\\.bz\\.mgtv\\.com\\/odin\\/c1\\/channel\\/index\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=mhgotv_enable, tag=\"芒果TV首页信息流\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/dc2?\\.bz\\.mgtv\\.com\\/dynamic\\/v1\\/channel\\/(index|vrsList)\\/\\w/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=mhgotv_enable, tag=\"芒果TV\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/mobile\\.api\\.mgtv\\.com\\/mobile\\/config\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=mhgotv_enable, tag=\"芒果TV底部tab\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/mobile\\.api\\.mgtv\\.com\\/v10\\/video\\/info\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=mhgotv_enable, tag=\"芒果TV播放详情页\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/mobile-thor\\.api\\.mgtv\\.com\\/v1\\/vod\\/info\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=mhgotv_enable, tag=\"芒果TV播放详情页\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/mobileso\\.bz\\.mgtv\\.com\\/mobile\\/recommend\\/v2\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=mhgotv_enable, tag=\"芒果TV搜索框填充词\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/acs\\.youku\\.com\\/gw\\/mtop\\.youku\\.columbus\\.(gateway\\.new\\.execute|home\\.feed|home\\.query|uc\\.query|ycp\\.query)/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=yzku_enable, tag=\"优酷\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/acs\\.youku\\.com\\/gw\\/mtop\\.youku\\.haidai\\.lantern\\.appconfig\\.get/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=yzku_enable, tag=\"优酷底部tab\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/acs\\.youku\\.com\\/gw\\/mtop\\.youku\\.huluwa\\.dispatcher\\.youthmode\\.config2/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=yzku_enable, tag=\"优酷青少年模式弹窗\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/acs\\.youku\\.com\\/gw\\/mtop\\.youku\\.soku\\.yksearch/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=yzku_enable, tag=\"优酷搜索列表\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/push\\.m\\.youku\\.com\\/collect-api\\/get_push_interval_config_wx\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=yzku_enable, tag=\"优酷热剧弹窗\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/un-acs\\.youku\\.com\\/gw\\/mtop\\.youku\\.play\\.ups\\.appinfo\\.get/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=yzku_enable, tag=\"优酷开屏广告\", timeout=60, requires_body=true",
)
CNFTP_DUPLICATE_KEEP_TRIGGERS = (
    "response if ${url} ~= /^https?:\\/\\/[\\d\\.]+\\/3f1\\/cards\\.iqiyi\\.com\\/(views_home\\/3\\.0\\/qy_home|waterfall\\/3\\.0\\/feed)\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=aiqiyi_enable, tag=\"爱奇艺首页信息流广告\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/access\\.if\\.iqiyi\\.com\\/3f1\\/cards\\.iqiyi\\.com\\/(views_category\\/3\\.0\\/category_home|views_home\\/3\\.0\\/qy_home|waterfall\\/3\\.0\\/feed)\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=aiqiyi_enable, tag=\"爱奇艺首页信息流广告\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/cards\\.iqiyi\\.com\\/views_category\\/3\\.0\\/(category_home|categorylib_content|film_hybrid)\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=aiqiyi_enable, tag=\"爱奇艺首页信息流广告\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/cards\\.iqiyi\\.com\\/(views_home\\/3\\.0\\/qy_home|waterfall\\/3\\.0\\/feed)\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=aiqiyi_enable, tag=\"爱奇艺首页信息流广告\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/cards\\.iqiyi\\.com\\/views_plt\\/3\\.0\\/player_tabs_v2\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=aiqiyi_enable, tag=\"爱奇艺播放详情页广告\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/cards\\.iqiyi\\.com\\/views_search\\/3\\.0\\/(hot_query_)?search\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=aiqiyi_enable, tag=\"爱奇艺搜索页列表广告\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/comment-card\\.iqiyi\\.com\\/views_comment\\/3\\.0\\/long_video_comments\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=aiqiyi_enable, tag=\"爱奇艺评论区\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/iface2\\.iqiyi\\.com\\/aggregate\\/3\\.0\\/getMyMenus\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=aiqiyi_enable, tag=\"爱奇艺我的页面菜单\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/iface2\\.iqiyi\\.com\\/control\\/3\\.0\\/init_proxy\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=aiqiyi_enable, tag=\"爱奇艺首页左上角天气\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/iface2\\.iqiyi\\.com\\/fusion\\/3\\.0\\/common_switch\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=aiqiyi_enable, tag=\"爱奇艺通用控制\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/iface2\\.iqiyi\\.com\\/views\\/3\\.0\\/(bottom_theme|home_top_menu)\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=aiqiyi_enable, tag=\"爱奇艺底部tab、顶部tab\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/search\\.video\\.iqiyi\\.com\\/q\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=aiqiyi_enable, tag=\"爱奇艺搜索框填充词\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/(kjp|t7z)\\.cupid\\.iqiyi\\.com\\/mixer\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=aiqiyi_enable, tag=\"爱奇艺开屏广告\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/acs\\.youku\\.com\\/gw\\/mtop\\.youku\\.columbus\\.(gateway\\.new\\.execute|home\\.feed|home\\.query|uc\\.query|ycp\\.query)/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=yzku_enable, tag=\"优酷\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/acs\\.youku\\.com\\/gw\\/mtop\\.youku\\.haidai\\.lantern\\.appconfig\\.get/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=yzku_enable, tag=\"优酷底部tab\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/acs\\.youku\\.com\\/gw\\/mtop\\.youku\\.huluwa\\.dispatcher\\.youthmode\\.config2/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=yzku_enable, tag=\"优酷青少年模式弹窗\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/acs\\.youku\\.com\\/gw\\/mtop\\.youku\\.soku\\.yksearch/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=yzku_enable, tag=\"优酷搜索列表\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/push\\.m\\.youku\\.com\\/collect-api\\/get_push_interval_config_wx\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=yzku_enable, tag=\"优酷热剧弹窗\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/un-acs\\.youku\\.com\\/gw\\/mtop\\.youku\\.play\\.ups\\.appinfo\\.get/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=yzku_enable, tag=\"优酷开屏广告\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/me\\.bz\\.mgtv\\.com\\/v\\d\\/module\\/list\\?/ then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js\") with enable=mhgotv_enable, tag=\"芒果TV我的页面\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/mob-st\\.bz\\.mgtv\\.com\\/odin\\/c\\d\\/channel\\/index\\?/ then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js\") with enable=mhgotv_enable, tag=\"芒果TV首页信息流\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/dc2?\\.bz\\.mgtv\\.com\\/dynamic\\/v\\d\\/channel\\/(index|vrsList)\\/\\w/ then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js\") with enable=mhgotv_enable, tag=\"芒果TV\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/mobile\\.api\\.mgtv\\.com\\/mobile\\/config\\?/ then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js\") with enable=mhgotv_enable, tag=\"芒果TV底部tab\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/mobile\\.api\\.mgtv\\.com\\/v\\d+\\/video\\/info\\?/ then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js\") with enable=mhgotv_enable, tag=\"芒果TV播放详情页\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/mobile-thor\\.api\\.mgtv\\.com\\/v\\d\\/vod\\/info\\?/ then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js\") with enable=mhgotv_enable, tag=\"芒果TV播放详情页\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/mobileso\\.bz\\.mgtv\\.com\\/mobile\\/recommend\\/v\\d\\?/ then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js\") with enable=mhgotv_enable, tag=\"芒果TV搜索框填充词\", timeout=60, requires_body=true",
)
CNFTP_IQIYI_HOME_SOURCE_TRIGGERS = CNFTP_DUPLICATE_KEEP_TRIGGERS[:4]
CNFTP_IQIYI_HOME_COMBINED_TRIGGER = (
    r"""response if ${url} ~= /^https?:\/\/(?:[\d\.]+\/3f1\/cards\.iqiyi\.com\/(?:views_home\/3\.0\/qy_home|waterfall\/3\.0\/feed)|access\.if\.iqiyi\.com\/3f1\/cards\.iqiyi\.com\/(?:views_category\/3\.0\/category_home|views_home\/3\.0\/qy_home|waterfall\/3\.0\/feed)|cards\.iqiyi\.com\/(?:views_category\/3\.0\/(?:category_home|categorylib_content|film_hybrid)|views_home\/3\.0\/qy_home|waterfall\/3\.0\/feed))\?/i then script("https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js") with enable=aiqiyi_enable, tag="爱奇艺首页信息流广告", timeout=60, requires_body=true"""
)

CNFTP_MGTV_SOURCE_TRIGGERS = (
    "response if ${url} ~= /^https?:\\/\\/me\\.bz\\.mgtv\\.com\\/v3\\/module\\/list\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=mhgotv_enable, tag=\"芒果TV我的页面\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/mob-st\\.bz\\.mgtv\\.com\\/odin\\/c1\\/channel\\/index\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=mhgotv_enable, tag=\"芒果TV首页信息流\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/dc2?\\.bz\\.mgtv\\.com\\/dynamic\\/v1\\/channel\\/(index|vrsList)\\/\\w/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=mhgotv_enable, tag=\"芒果TV\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/mobile\\.api\\.mgtv\\.com\\/mobile\\/config\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=mhgotv_enable, tag=\"芒果TV底部tab\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/mobile\\.api\\.mgtv\\.com\\/v10\\/video\\/info\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=mhgotv_enable, tag=\"芒果TV播放详情页\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/mobile-thor\\.api\\.mgtv\\.com\\/v1\\/vod\\/info\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=mhgotv_enable, tag=\"芒果TV播放详情页\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/mobileso\\.bz\\.mgtv\\.com\\/mobile\\/recommend\\/v2\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=mhgotv_enable, tag=\"芒果TV搜索框填充词\", timeout=60, requires_body=true",
)
CNFTP_MGTV_BROAD_TRIGGERS = (
    "response if ${url} ~= /^https?:\\/\\/me\\.bz\\.mgtv\\.com\\/v\\d\\/module\\/list\\?/ then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js\") with enable=mhgotv_enable, tag=\"芒果TV我的页面\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/mob-st\\.bz\\.mgtv\\.com\\/odin\\/c\\d\\/channel\\/index\\?/ then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js\") with enable=mhgotv_enable, tag=\"芒果TV首页信息流\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/dc2?\\.bz\\.mgtv\\.com\\/dynamic\\/v\\d\\/channel\\/(index|vrsList)\\/\\w/ then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js\") with enable=mhgotv_enable, tag=\"芒果TV\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/mobile\\.api\\.mgtv\\.com\\/mobile\\/config\\?/ then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js\") with enable=mhgotv_enable, tag=\"芒果TV底部tab\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/mobile\\.api\\.mgtv\\.com\\/v\\d+\\/video\\/info\\?/ then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js\") with enable=mhgotv_enable, tag=\"芒果TV播放详情页\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/mobile-thor\\.api\\.mgtv\\.com\\/v\\d\\/vod\\/info\\?/ then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js\") with enable=mhgotv_enable, tag=\"芒果TV播放详情页\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/mobileso\\.bz\\.mgtv\\.com\\/mobile\\/recommend\\/v\\d\\?/ then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js\") with enable=mhgotv_enable, tag=\"芒果TV搜索框填充词\", timeout=60, requires_body=true",
)
CNFTP_MGTV_TRIGGER_REPLACEMENTS = dict(zip(
    CNFTP_MGTV_SOURCE_TRIGGERS, CNFTP_MGTV_BROAD_TRIGGERS
))


DUSHU365_NON_AD_REMOVE_TRIGGERS = (
    "http-response ^https?:\\/\\/g(.*)\\.dushu365\\.com\\/chief-orch\\/home\\/bookPortal\\/v105\\/category script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/dushu365.js,tag=DUSHU365,requires-body=true",
    "http-response ^https?:\\/\\/g(.*)\\.dushu365\\.com\\/resource-orchestration-system\\/book\\/channel\\/v100\\/info script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/dushu365.js,tag=DUSHU365-3,requires-body=true",
    "http-response ^https?:\\/\\/g(.*)\\.dushu365\\.com\\/chief-orch\\/home\\/bookPortal\\/v111\\/forApp script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/dushu365.js,tag=DUSHU365-5,requires-body=true",
    "http-response ^https?:\\/\\/g(.*)\\.dushu365\\.com\\/sns-orchestration-system\\/homePage\\/api\\/v100\\/myPage script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/dushu365.js,tag=DUSHU365-6,requires-body=true",
)
DUSHU365_AD_AND_UNCERTAIN_KEEP_TRIGGERS = (
    "http-response ^https?:\\/\\/g(.*)\\.dushu365\\.com\\/abtest-front\\/banner-modular\\/get script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/dushu365.js,tag=DUSHU365-2,requires-body=true",
    "http-response ^https?:\\/\\/g(.*)\\.dushu365\\.com\\/fs-member\\/user\\/profile\\/v100\\/detail script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/dushu365.js,tag=DUSHU365-4,requires-body=true",
    "http-response ^https?:\\/\\/g(.*)\\.dushu365\\.com\\/task-orchestration\\/taskCenter\\/api\\/v101\\/taskList script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/dushu365.js,tag=DUSHU365-7,requires-body=true",
    "http-response ^https?:\\/\\/g(.*)\\.dushu365\\.com\\/resource-orchestration-system\\/book\\/v101\\/content script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/dushu365.js,tag=DUSHU365-8,requires-body=true",
    "http-response ^https?:\\/\\/g(.*)\\.dushu365\\.com\\/user-orchestration\\/user\\/api\\/v101\\/ceiltip script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/dushu365.js,tag=DUSHU365-9,requires-body=true",
)

CNFTP_NON_AD_REMOVE_TRIGGERS = (
    "response if ${url} ~= /^https?:\\/\\/iface2\\.iqiyi\\.com\\/aggregate\\/3\\.0\\/getMyMenus\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=aiqiyi_enable, tag=\"爱奇艺我的页面菜单\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/iface2\\.iqiyi\\.com\\/control\\/3\\.0\\/init_proxy\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=aiqiyi_enable, tag=\"爱奇艺首页左上角天气\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/iface2\\.iqiyi\\.com\\/views\\/3\\.0\\/(bottom_theme|home_top_menu)\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=aiqiyi_enable, tag=\"爱奇艺底部tab、顶部tab\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/search\\.video\\.iqiyi\\.com\\/q\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=aiqiyi_enable, tag=\"爱奇艺搜索框填充词\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/acs\\.youku\\.com\\/gw\\/mtop\\.youku\\.haidai\\.lantern\\.appconfig\\.get/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=yzku_enable, tag=\"优酷底部tab\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/acs\\.youku\\.com\\/gw\\/mtop\\.youku\\.huluwa\\.dispatcher\\.youthmode\\.config2/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=yzku_enable, tag=\"优酷青少年模式弹窗\", timeout=60, requires_body=true",
)
CNFTP_BLOCKADS_SOURCE_TRIGGERS = (
    "response if ${url} ~= /^https?:\\/\\/[\\d\\.]+\\/3f1\\/cards\\.iqiyi\\.com\\/(views_home\\/3\\.0\\/qy_home|waterfall\\/3\\.0\\/feed)\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=${aiqiyi_enable}, tag=\"爱奇艺首页信息流广告\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/access\\.if\\.iqiyi\\.com\\/3f1\\/cards\\.iqiyi\\.com\\/(views_category\\/3\\.0\\/category_home|views_home\\/3\\.0\\/qy_home|waterfall\\/3\\.0\\/feed)\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=${aiqiyi_enable}, tag=\"爱奇艺首页信息流广告\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/cards\\.iqiyi\\.com\\/views_category\\/3\\.0\\/(category_home|categorylib_content|film_hybrid)\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=${aiqiyi_enable}, tag=\"爱奇艺首页信息流广告\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/cards\\.iqiyi\\.com\\/(views_home\\/3\\.0\\/qy_home|waterfall\\/3\\.0\\/feed)\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=${aiqiyi_enable}, tag=\"爱奇艺首页信息流广告\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/cards\\.iqiyi\\.com\\/views_plt\\/3\\.0\\/player_tabs_v2\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=${aiqiyi_enable}, tag=\"爱奇艺播放详情页广告\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/cards\\.iqiyi\\.com\\/views_search\\/3\\.0\\/(hot_query_)?search\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=${aiqiyi_enable}, tag=\"爱奇艺搜索页列表广告\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/comment-card\\.iqiyi\\.com\\/views_comment\\/3\\.0\\/long_video_comments\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=${aiqiyi_enable}, tag=\"爱奇艺评论区\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/iface2\\.iqiyi\\.com\\/aggregate\\/3\\.0\\/getMyMenus\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=${aiqiyi_enable}, tag=\"爱奇艺我的页面菜单\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/iface2\\.iqiyi\\.com\\/control\\/3\\.0\\/init_proxy\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=${aiqiyi_enable}, tag=\"爱奇艺首页左上角天气\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/iface2\\.iqiyi\\.com\\/fusion\\/3\\.0\\/common_switch\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=${aiqiyi_enable}, tag=\"爱奇艺通用控制\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/iface2\\.iqiyi\\.com\\/views\\/3\\.0\\/(bottom_theme|home_top_menu)\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=${aiqiyi_enable}, tag=\"爱奇艺底部tab、顶部tab\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/search\\.video\\.iqiyi\\.com\\/q\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=${aiqiyi_enable}, tag=\"爱奇艺搜索框填充词\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/(kjp|t7z)\\.cupid\\.iqiyi\\.com\\/mixer\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=${aiqiyi_enable}, tag=\"爱奇艺开屏广告\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/me\\.bz\\.mgtv\\.com\\/v3\\/module\\/list\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=${mhgotv_enable}, tag=\"芒果TV我的页面\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/mob-st\\.bz\\.mgtv\\.com\\/odin\\/c1\\/channel\\/index\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=${mhgotv_enable}, tag=\"芒果TV首页信息流\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/dc2?\\.bz\\.mgtv\\.com\\/dynamic\\/v1\\/channel\\/(index|vrsList)\\/\\w/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=${mhgotv_enable}, tag=\"芒果TV\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/mobile\\.api\\.mgtv\\.com\\/mobile\\/config\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=${mhgotv_enable}, tag=\"芒果TV底部tab\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/mobile\\.api\\.mgtv\\.com\\/v10\\/video\\/info\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=${mhgotv_enable}, tag=\"芒果TV播放详情页\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/mobile-thor\\.api\\.mgtv\\.com\\/v1\\/vod\\/info\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=${mhgotv_enable}, tag=\"芒果TV播放详情页\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/mobileso\\.bz\\.mgtv\\.com\\/mobile\\/recommend\\/v2\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=${mhgotv_enable}, tag=\"芒果TV搜索框填充词\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/acs\\.youku\\.com\\/gw\\/mtop\\.youku\\.columbus\\.(gateway\\.new\\.execute|home\\.feed|home\\.query|uc\\.query|ycp\\.query)/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=${yzku_enable}, tag=\"优酷\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/acs\\.youku\\.com\\/gw\\/mtop\\.youku\\.haidai\\.lantern\\.appconfig\\.get/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=${yzku_enable}, tag=\"优酷底部tab\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/acs\\.youku\\.com\\/gw\\/mtop\\.youku\\.huluwa\\.dispatcher\\.youthmode\\.config2/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=${yzku_enable}, tag=\"优酷青少年模式弹窗\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/acs\\.youku\\.com\\/gw\\/mtop\\.youku\\.soku\\.yksearch/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=${yzku_enable}, tag=\"优酷搜索列表\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/push\\.m\\.youku\\.com\\/collect-api\\/get_push_interval_config_wx\\?/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=${yzku_enable}, tag=\"优酷热剧弹窗\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/un-acs\\.youku\\.com\\/gw\\/mtop\\.youku\\.play\\.ups\\.appinfo\\.get/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js\") with enable=${yzku_enable}, tag=\"优酷开屏广告\", timeout=60, requires_body=true",
)
def normalize_cnftp_trigger_line(line):
    """Normalize only known source syntax differences for exact CNFTP inventory comparison."""
    value = line.strip().replace("\\/", "/")
    value = value.replace(
        "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/cnftp/cnftp.js",
        "https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js",
    )
    return re.sub(r"enable=\$\{([^}]+)\}", r"enable=\1", value)


def remove_duplicate_cnftp_scripts(lines):
    """Collapse duplicate video response scripts and accept the already-combined iQIYI home state."""
    remove_counts = {item: 0 for item in CNFTP_DUPLICATE_REMOVE_TRIGGERS}
    source_counts = {normalize_cnftp_trigger_line(item): 0 for item in CNFTP_DUPLICATE_KEEP_SOURCE_TRIGGERS}
    home_source_counts = {normalize_cnftp_trigger_line(item): 0 for item in CNFTP_IQIYI_HOME_SOURCE_TRIGGERS}
    output_counts = {normalize_cnftp_trigger_line(item): 0 for item in CNFTP_DUPLICATE_KEEP_TRIGGERS[4:]}
    non_ad_normalized = {normalize_cnftp_trigger_line(item) for item in CNFTP_NON_AD_REMOVE_TRIGGERS}
    normalized_mgtv_replacements = {
        normalize_cnftp_trigger_line(source): target
        for source, target in CNFTP_MGTV_TRIGGER_REPLACEMENTS.items()
    }
    remove_set = set(CNFTP_DUPLICATE_REMOVE_TRIGGERS)
    legacy_remove_mode = any(item in lines for item in remove_set)
    current_source_only_mode = any(
        normalize_cnftp_trigger_line(line.strip()) in source_counts
        and normalize_cnftp_trigger_line(line.strip()) not in output_counts
        and normalize_cnftp_trigger_line(line.strip()) not in home_source_counts
        for line in lines
    )
    source_mode = legacy_remove_mode or current_source_only_mode
    output, section, target_seen, removed = [], "", False, 0
    combined_home_count = 0

    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue

        normalized_line = normalize_cnftp_trigger_line(line)
        unescaped_line = normalized_line.replace("\\", "")
        is_target = (
            section == "Script"
            and any(host in unescaped_line for host in ("iqiyi.com", "mgtv.com", "youku.com"))
            and ("http-response " in line or "response if " in line)
            and "mgesq.api.mgtv.com" not in unescaped_line
        )
        if not is_target:
            output.append(line)
            continue

        target_seen = True
        if source_mode:
            if line in remove_counts:
                remove_counts[line] += 1
                if remove_counts[line] > 1:
                    raise ValueError("duplicate legacy video trigger; refusing ambiguous cleanup")
                removed += 1
                continue
            if normalized_line in source_counts:
                source_counts[normalized_line] += 1
                if source_counts[normalized_line] > 1:
                    raise ValueError("duplicate retained video source trigger; refusing ambiguous cleanup")
                output.append(normalized_mgtv_replacements.get(normalized_line, line))
                continue
            raise ValueError(f"video script trigger inventory changed; refusing unreviewed consolidation: {line.strip()}")

        if normalized_line == normalize_cnftp_trigger_line(CNFTP_IQIYI_HOME_COMBINED_TRIGGER):
            combined_home_count += 1
            if combined_home_count > 1:
                raise ValueError("duplicate combined iQIYI home trigger; refusing ambiguous cleanup")
            output.append(line)
            continue
        if normalized_line in home_source_counts:
            home_source_counts[normalized_line] += 1
            if home_source_counts[normalized_line] > 1:
                raise ValueError("duplicate iQIYI home source trigger; refusing ambiguous cleanup")
            output.append(line)
            continue
        if normalized_line in output_counts:
            output_counts[normalized_line] += 1
            if output_counts[normalized_line] > 1:
                raise ValueError("duplicate consolidated video trigger; refusing ambiguous cleanup")
            output.append(line)
            continue
        raise ValueError("consolidated video script inventory changed; refusing unreviewed cleanup")

    if not target_seen:
        return output, 0

    if source_mode:
        if legacy_remove_mode and not all(count == 1 for count in remove_counts.values()):
            return list(lines), 0
        required_source_counts = {
            item: count for item, count in source_counts.items()
            if item not in non_ad_normalized
        }
        if not all(count == 1 for count in required_source_counts.values()):
            return list(lines), 0
        return output, removed

    if combined_home_count == 1:
        if any(home_source_counts.values()):
            raise ValueError("mixed combined and split iQIYI home triggers; refusing ambiguous cleanup")
    elif not all(count == 1 for count in home_source_counts.values()):
        return list(lines), 0

    required_output_counts = {
        item: count for item, count in output_counts.items()
        if item not in non_ad_normalized
    }
    if not all(count == 1 for count in required_output_counts.values()):
        return list(lines), 0
    return output, 0


def consolidate_cnftp_iqiyi_home_triggers(lines):
    """Combine four same-action iQIYI home-feed matchers without widening URL coverage."""
    original = list(lines)
    output, section = [], ""
    counts = {normalize_cnftp_trigger_line(item): 0 for item in CNFTP_IQIYI_HOME_SOURCE_TRIGGERS}
    inserted = False
    target_seen = False

    for line in original:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue
        normalized_line = normalize_cnftp_trigger_line(line)
        if section != "Script" or normalized_line not in counts:
            output.append(line)
            continue
        target_seen = True
        counts[normalized_line] += 1
        if counts[normalized_line] > 1:
            raise ValueError("duplicate iQIYI home trigger; refusing consolidation")
        if not inserted:
            output.append(CNFTP_IQIYI_HOME_COMBINED_TRIGGER)
            inserted = True

    if not target_seen:
        return output, 0
    if not all(count == 1 for count in counts.values()):
        raise ValueError("iQIYI home trigger inventory incomplete; refusing partial consolidation")
    return output, len(CNFTP_IQIYI_HOME_SOURCE_TRIGGERS) - 1


def remove_cnftp_non_ad_triggers(lines):
    """Remove only six reviewed CNFTP response triggers that do not process ads."""
    targets = {normalize_cnftp_trigger_line(item) for item in CNFTP_NON_AD_REMOVE_TRIGGERS}
    counts = {item: 0 for item in targets}
    markers = {
        "getMyMenus": ("iface2.iqiyi.com", "aggregate/3.0/getMyMenus"),
        "init_proxy": ("iface2.iqiyi.com", "control/3.0/init_proxy"),
        "bottom_theme": ("iface2.iqiyi.com", "views/3.0/", "bottom_theme"),
        "search.video": ("search.video.iqiyi.com", "/q"),
        "lantern.appconfig": ("acs.youku.com", "haidai.lantern.appconfig.get"),
        "youthmode": ("acs.youku.com", "huluwa.dispatcher.youthmode.config2"),
    }
    normalized_lines = {normalize_cnftp_trigger_line(line) for line in lines}
    active_markers = {
        key for key, parts in markers.items()
        if any(
            item in normalized_lines and all(part in item.replace("\\", "") for part in parts)
            for item in targets
        )
    }

    output, section, removed = [], "", 0
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue
        value = line.strip()
        normalized = normalize_cnftp_trigger_line(value)
        unescaped = normalized.replace("\\", "")
        if section == "Script":
            for key, parts in markers.items():
                if key in active_markers and all(part in unescaped for part in parts) and "cnftp.js" in value:
                    if normalized not in targets:
                        raise ValueError("CNFTP non-ad trigger matcher changed; refusing unreviewed pruning")
            if normalized in targets:
                counts[normalized] += 1
                if counts[normalized] > 1:
                    raise ValueError("duplicate CNFTP non-ad trigger; refusing ambiguous pruning")
                removed += 1
                continue
        elif normalized in targets:
            raise ValueError("CNFTP non-ad trigger moved outside Script section; refusing pruning")
        output.append(line)

    return output, removed


def remove_dushu365_non_ad_triggers(lines):
    """Remove only four Dushu365 triggers used for non-ad layout customization."""
    targets = set(DUSHU365_NON_AD_REMOVE_TRIGGERS)
    keep = set(DUSHU365_AD_AND_UNCERTAIN_KEEP_TRIGGERS)
    output, section, counts, removed = [], "", {}, 0
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue
        value = line.strip()
        is_dushu365 = "Res/Scripts/AntiAd/dushu365.js" in value
        if is_dushu365 and section != "Script":
            raise ValueError("Dushu365 response trigger moved outside Script section; refusing pruning")
        if section == "Script" and is_dushu365:
            if value not in targets and value not in keep:
                raise ValueError("Dushu365 script trigger inventory changed; refusing unreviewed pruning")
            counts[value] = counts.get(value, 0) + 1
            if counts[value] > 1:
                raise ValueError("duplicate Dushu365 response trigger; refusing ambiguous pruning")
            if value in targets:
                removed += 1
                continue
        output.append(line)
    return output, removed


# Same-URL response scripts duplicated across legacy and v2 syntax.
SAME_SOURCE_DUPLICATE_REMOVE_TRIGGERS = (
    "http-response ^https?:\\/\\/g\\.alicdn\\.com\\/.*o2o-ad script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/alicdn.js,tag=ALIBABA-2,requires-body=true",
    "http-response ^https?:\\/\\/creditcardapp\\.bankcomm\\.(com|cn)\\/rcg\\/index\\.html\\?callbackurl=rcg\\/index\\.html&orclogin=1& script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/mdb.js,tag=BANKCOMM,requires-body=true",
    "http-response ^https?:\\/\\/maicai\\.api\\.ddxq\\.mobi\\/homeApi\\/(?:bottomNavi|homeFlowDetail) script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/ddxq.js,tag=DDXQ,requires-body=true",
    "http-response ^https?:\\/\\/maicai\\.api\\.ddxq\\.mobi\\/tool\\/getConfig script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/ddxq.js,tag=DDXQ-2,requires-body=true",
    "http-response ^https?:\\/\\/user\\.api\\.ddxq\\.mobi\\/userportal-service\\/api\\/v\\d\\/user\\/queryMyPage script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/ddxq.js,tag=DDXQ-3,requires-body=true",
    "http-response ^https?:\\/\\/cupid\\.51job(app)?\\.com\\/open\\/noauth\\/recommend\\/job-tab-dynamic script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/51job.js,tag=51JOB,requires-body=true",
    "http-response ^https?:\\/\\/cupid\\.51job(app)?\\.com\\/open\\/my-page\\/ script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/51job.js,tag=51JOB-2,requires-body=true",
    "http-response ^https?:\\/\\/manga\\.bilibili\\.com\\/twirp\\/user\\.v\\d\\.User\\/(?:UCenterConf|GetInitInfo) script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliManga.js,tag=BILIBILIMANGA,requires-body=true",
    "http-response ^https?:\\/\\/manga\\.bilibili\\.com\\/twirp\\/comic\\.v\\d\\.Home\\/HomeFeed script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliManga.js,tag=BILIBILIMANGA-2,requires-body=true",
    "http-response ^https?:\\/\\/manga\\.bilibili\\.com\\/twirp\\/comic\\.v\\d\\.Comment\\/Main script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliManga.js,tag=BILIBILIMANGA-3,requires-body=true",
    "http-response ^https?:\\/\\/apis\\.folidaymall\\.com\\/online\\/capi\\/component\\/getPageComponents script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/foliday.js,tag=FOLIDAY,requires-body=true",
    "response if ${url} ~= /^https?:\\/\\/cupid\\.51job(app)?\\.com\\/open\\/noauth\\/recommend\\/job-tab-dynamic/i then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/51job.js\") with enable=51job_enable, tag=\"去哒\", timeout=60, requires_body=true",
)
SAME_SOURCE_DUPLICATE_KEEP_TRIGGERS = (
    "http-response ^https?:\\/\\/manga\\.bilibili\\.com\\/twirp\\/comic\\.v\\d\\.Comic\\/GetCommonBanner script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliManga.js,tag=BILIBILIMANGA-4,requires-body=true",
    "response if ${url} ~= /^https?:\\/\\/manga\\.bilibili\\.com\\/twirp\\/user\\.v\\d\\.User\\/UCenterConf/i then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliManga.js\") with enable=bilimanhua_enable, tag=\"哔哩哔哩漫画\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/manga\\.bilibili\\.com\\/twirp\\/user\\.v\\d\\.User\\/GetInitInfo/i then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliManga.js\") with enable=bilimanhua_enable, tag=\"哔哩哔哩漫画\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/manga\\.bilibili\\.com\\/twirp\\/comic\\.v\\d\\.Home\\/HomeFeed/i then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliManga.js\") with enable=bilimanhua_enable, tag=\"哔哩哔哩漫画\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/manga\\.bilibili\\.com\\/twirp\\/comic\\.v\\d\\.Comment\\/Main/i then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliManga.js\") with enable=bilimanhua_enable, tag=\"哔哩哔哩漫画\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/maicai\\.api\\.ddxq\\.mobi\\/homeApi\\/(?:bottomNavi|homeFlowDetail)/i then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/ddxq.js\") with enable=ddmc_enable, tag=\"叮咚买菜\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/maicai\\.api\\.ddxq\\.mobi\\/tool\\/getConfig/i then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/ddxq.js\") with enable=ddmc_enable, tag=\"叮咚买菜\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/user\\.api\\.ddxq\\.mobi\\/userportal-service\\/api\\/v\\d\\/user\\/queryMyPage/i then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/ddxq.js\") with enable=ddmc_enable, tag=\"叮咚买菜\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/apis\\.folidaymall\\.com\\/online\\/capi\\/component\\/getPageComponents/i then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/foliday.js\") with tag=\"复游会微信小程序\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/g\\.alicdn\\.com\\/.*o2o-ad/i then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/alicdn.js\") with enable=jhsh_enable, tag=\"建行生活内置饿了么\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/creditcardapp\\.bankcomm\\.(com|cn)\\/rcg\\/index\\.html\\?callbackurl=rcg\\/index\\.html&orclogin=1&/i then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/mdb.js\") with enable=mddjba_enable, tag=\"mdb\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/cupid\\.51job(app)?\\.com\\/open\\/noauth\\/recommend\\/job-tab-dynamic/i then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/51job.js\") with enable=51job_enable, tag=\"51job\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/cupid\\.51job(app)?\\.com\\/open\\/my-page\\//i then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/51job.js\") with enable=51job_enable, tag=\"去哒\", timeout=60, requires_body=true",
)


def remove_same_source_duplicate_response_scripts(lines):
    """Remove exact duplicate entries that invoke the same script on the same response."""
    remove_counts = {item: 0 for item in SAME_SOURCE_DUPLICATE_REMOVE_TRIGGERS}
    keep_counts = {item: 0 for item in SAME_SOURCE_DUPLICATE_KEEP_TRIGGERS}
    output, section, target_seen, removed = [], "", False, 0

    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue

        normalized = line.replace("\\", "")
        # Loon upstream now serializes some existing script switches as
        # enable=${name}; compare both known spellings as the same switch,
        # while preserving the original source line when it is retained.
        inventory_line = re.sub(r"enable=\$\{([^}]+)\}", r"enable=\1", line.strip())
        # Equivalent atomic/non-capturing groups appeared in the upstream matcher.
        inventory_line = inventory_line.replace("(?>", "(?:")
        is_target = (
            section == "Script"
            and (
                ("g.alicdn.com" in normalized and "o2o-ad" in normalized)
                or ("creditcardapp.bankcomm." in normalized and "/rcg/index.html" in normalized)
                or ("maicai.api.ddxq.mobi" in normalized and ("/homeApi/" in normalized or "/tool/getConfig" in normalized))
                or ("user.api.ddxq.mobi" in normalized and "queryMyPage" in normalized)
                or ("cupid.51job" in normalized and ("job-tab-dynamic" in normalized or "/open/my-page/" in normalized))
                or ("manga.bilibili.com" in normalized and "bilibiliManga.js" in normalized)
                or ("apis.folidaymall.com" in normalized and "getPageComponents" in normalized)
            )
        )
        if not is_target:
            output.append(line)
            continue

        target_seen = True
        if inventory_line in remove_counts:
            remove_counts[inventory_line] += 1
            if remove_counts[inventory_line] > 1:
                raise ValueError("duplicate same-source removal trigger; refusing ambiguous cleanup")
            removed += 1
            continue
        if inventory_line in keep_counts:
            keep_counts[inventory_line] += 1
            if keep_counts[inventory_line] > 1:
                raise ValueError("duplicate same-source retained trigger; refusing ambiguous cleanup")
            output.append(line)
            continue
        raise ValueError(f"same-source response trigger inventory changed; refusing unreviewed consolidation: {line.strip()}")

    if not target_seen:
        return output, 0

    keep_complete = all(count == 1 for count in keep_counts.values())
    remove_absent = all(count == 0 for count in remove_counts.values())
    remove_complete = all(count == 1 for count in remove_counts.values())
    if keep_complete and remove_absent:
        return output, 0
    if not keep_complete or not remove_complete:
        return list(lines), 0
    return output, removed


# R-Store and fmz200 variants of RRTV, Soul and Reddit response scripts were code-identical
# after removing comments/formatting. Keep one modern handler per response and retain broad paths.
IDENTICAL_SCRIPT_REMOVE_TRIGGERS = (
    "http-response ^https?:\\/\\/api\\.rr\\.tv\\/\\w{3}\\/level\\/info script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/rrtv.js,tag=RRTV,requires-body=true",
    "http-response ^https?:\\/\\/api\\.rr\\.tv\\/v3plus\\/index\\/channel\\?pageNum=1&position=CHANNEL_MY script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/rrtv.js,tag=RRTV-2,requires-body=true",
    "http-response ^https?:\\/\\/api\\.rr\\.tv\\/v3plus\\/index\\/channel\\?pageNum=1&position=CHANNEL_INDEX script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/rrtv.js,tag=RRTV-3,requires-body=true",
    "http-response ^https?:\\/\\/api\\.rr\\.tv\\/ad\\/getAll script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/rrtv.js,tag=RRTV-4,requires-body=true",
    "http-response ^https?:\\/\\/api\\.rr\\.tv\\/app\\/config\\/h5NativeBar script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/rrtv.js,tag=RRTV-5,requires-body=true",
    "http-response ^https?:\\/\\/api\\.rr\\.tv\\/drama\\/app\\/get_combined_drama_detail script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/rrtv.js,tag=RRTV-6,requires-body=true",
    "http-response ^https?:\\/\\/api\\.rr\\.tv\\/watch\\/v\\d script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/rrtv.js,tag=RRTV-7,requires-body=true",
    "http-response ^https?:\\/\\/api\\.rr\\.tv\\/user\\/privilege\\/list script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/rrtv.js,tag=RRTV-8,requires-body=true",
    "http-response ^https?:\\/\\/api\\.rr\\.tv\\/user\\/profile script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/rrtv.js,tag=RRTV-9,requires-body=true",
    "http-response ^https?:\\/\\/api-a\\.soulapp\\.cn\\/v\\d\\/post\\/gift\\/list script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/soul.js,tag=SOUL,requires-body=true",
    "http-response ^https?:\\/\\/api-a\\.soulapp\\.cn\\/official\\/scene\\/module script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/soul.js,tag=SOUL-2,requires-body=true",
    "http-response ^https?:\\/\\/api-chat\\.soulapp\\.cn\\/chat\\/limitInfo script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/soul.js,tag=SOUL-3,requires-body=true",
    "http-response ^https?:\\/\\/api-user\\.soulapp\\.cn\\/furion\\/position\\/content script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/soul.js,tag=SOUL-4,requires-body=true",
    "http-response ^https?:\\/\\/post\\.soulapp\\.cn\\/hot\\/soul\\/rank script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/soul.js,tag=SOUL-7,requires-body=true",
    "http-response ^https?:\\/\\/post\\.soulapp\\.cn\\/v\\d\\/post\\/homepage\\/guide\\/card script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/soul.js,tag=SOUL-8,requires-body=true",
    "http-response ^https?:\\/\\/gateway-mobile-gray\\.soulapp\\.cn\\/mobile\\/app\\/version\\/queryIos script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/soul.js,tag=SOUL-9,requires-body=true",
    "http-response ^https?:\\/\\/gql(-fed)?\\.reddit\\.com script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/reddit.js,tag=REDDIT,requires-body=true",
)
IDENTICAL_SCRIPT_KEEP_SOURCE_TRIGGERS = (
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/\\w{3}\\/level\\/info/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /https:\\/\\/api.rr.tv\\/v3plus\\/index\\/channel\\?pageNum=1&position=CHANNEL_INDEX/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/app\\/config\\/h5NativeBar/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/v3plus\\/index\\/channel\\?pageNum=1&position=CHANNEL_MY/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/user\\/privilege\\/list/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/ad\\/getAll/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/drama\\/app\\/get_combined_drama_detail/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /https:\\/\\/api.rr.tv\\/watch\\/v4/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /https:\\/\\/api.rr.tv\\/user\\/profile/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api-account\\.soulapp\\.cn\\/teenager\\/config/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api-a\\.soulapp\\.cn\\/v2\\/post\\/gift\\/list/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api-a\\.soulapp\\.cn\\/official\\/scene\\/module/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api-user\\.soulapp\\.cn\\/furion\\/position\\/content/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api-user\\.soulapp\\.cn\\/v\\d\\/planet\\/config/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api-chat\\.soulapp\\.cn\\/chat\\/limitInfo/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/post\\.soulapp\\.cn\\/hot\\/soul\\/rank/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/post\\.soulapp\\.cn\\/v\\d\\/post\\/homepage\\/guide\\/card/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/post\\.soulapp\\.cn\\/v\\d\\/post\\/recSquare\\/subTabs/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/chat-live\\.soulapp\\.cn\\/chatroom\\/chatClassifyRoomList/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/gateway-mobile-gray\\.soulapp\\.cn\\/mobile\\/app\\/version\\/queryIos/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/47\\.110\\.187\\.87\\/winterfell\\/v2\\/getIpByDomain/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/gql(-fed)?\\.reddit\\.com/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/reddit.js\") with enable=reddit_enable, tag=\"reddit\", timeout=60, requires_body=true",
    "http-response ^https?:\\/\\/api-pay\\.soulapp\\.cn\\/vip\\/meet\\/userInfo script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/soul.js,tag=SOUL-5,requires-body=true",
    "http-response ^https?:\\/\\/api-pay\\.soulapp\\.cn\\/privilege\\/supervip\\/status script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/soul.js,tag=SOUL-6,requires-body=true",
)
IDENTICAL_SCRIPT_KEEP_TRIGGERS = (
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/\\w{3}\\/level\\/info/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/v3plus\\/index\\/channel\\?pageNum=1&position=CHANNEL_INDEX/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/app\\/config\\/h5NativeBar/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/v3plus\\/index\\/channel\\?pageNum=1&position=CHANNEL_MY/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/user\\/privilege\\/list/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/ad\\/getAll/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/drama\\/app\\/get_combined_drama_detail/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/watch\\/v\\d/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/user\\/profile/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api-account\\.soulapp\\.cn\\/teenager\\/config/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api-a\\.soulapp\\.cn\\/v\\d\\/post\\/gift\\/list/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api-a\\.soulapp\\.cn\\/official\\/scene\\/module/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api-user\\.soulapp\\.cn\\/furion\\/position\\/content/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api-user\\.soulapp\\.cn\\/v\\d\\/planet\\/config/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api-chat\\.soulapp\\.cn\\/chat\\/limitInfo/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/post\\.soulapp\\.cn\\/hot\\/soul\\/rank/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/post\\.soulapp\\.cn\\/v\\d\\/post\\/homepage\\/guide\\/card/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/post\\.soulapp\\.cn\\/v\\d\\/post\\/recSquare\\/subTabs/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/chat-live\\.soulapp\\.cn\\/chatroom\\/chatClassifyRoomList/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/gateway-mobile-gray\\.soulapp\\.cn\\/mobile\\/app\\/version\\/queryIos/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/47\\.110\\.187\\.87\\/winterfell\\/v2\\/getIpByDomain/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/gql(-fed)?\\.reddit\\.com/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/reddit.js\") with enable=reddit_enable, tag=\"reddit\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api-pay\\.soulapp\\.cn\\/vip\\/meet\\/userInfo/ then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api-pay\\.soulapp\\.cn\\/privilege\\/supervip\\/status/ then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
)
IDENTICAL_SCRIPT_CURRENT_CANONICAL_TRIGGERS = (
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/\\w{3}\\/level\\/info/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/v3plus\\/index\\/channel\\?pageNum=1&position=CHANNEL_INDEX/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/app\\/config\\/h5NativeBar/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/v3plus\\/index\\/channel\\?pageNum=1&position=CHANNEL_MY/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/user\\/privilege\\/list/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/ad\\/getAll/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/drama\\/app\\/get_combined_drama_detail/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/watch\\/v\\d/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/user\\/profile/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api-pay\\.soulapp\\.cn\\/(?:vip\\/meet\\/userInfo|privilege\\/supervip\\/status)/ then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/(?:api-account\\.soulapp\\.cn\\/teenager\\/config|api-a\\.soulapp\\.cn\\/(?:v\\d\\/post\\/gift\\/list|official\\/scene\\/module)|api-user\\.soulapp\\.cn\\/(?:furion\\/position\\/content|v\\d\\/planet\\/config)|api-chat\\.soulapp\\.cn\\/chat\\/limitInfo|post\\.soulapp\\.cn\\/(?:hot\\/soul\\/rank|v\\d\\/post\\/(?:homepage\\/guide\\/card|recSquare\\/subTabs))|chat-live\\.soulapp\\.cn\\/chatroom\\/chatClassifyRoomList|gateway-mobile-gray\\.soulapp\\.cn\\/mobile\\/app\\/version\\/queryIos|47\\.110\\.187\\.87\\/winterfell\\/v2\\/getIpByDomain)/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/gql(-fed)?\\.reddit\\.com/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/reddit.js\") with enable=reddit_enable, tag=\"reddit\", timeout=60, requires_body=true",
)
IDENTICAL_SCRIPT_TRANSFORMS = {
    "response if ${url} ~= /https:\\/\\/api.rr.tv\\/v3plus\\/index\\/channel\\?pageNum=1&position=CHANNEL_INDEX/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true": "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/v3plus\\/index\\/channel\\?pageNum=1&position=CHANNEL_INDEX/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /https:\\/\\/api.rr.tv\\/watch\\/v4/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true": "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/watch\\/v\\d/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /https:\\/\\/api.rr.tv\\/user\\/profile/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true": "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/user\\/profile/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api-a\\.soulapp\\.cn\\/v2\\/post\\/gift\\/list/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true": "response if ${url} ~= /^https?:\\/\\/api-a\\.soulapp\\.cn\\/v\\d\\/post\\/gift\\/list/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "http-response ^https?:\\/\\/api-pay\\.soulapp\\.cn\\/vip\\/meet\\/userInfo script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/soul.js,tag=SOUL-5,requires-body=true": "response if ${url} ~= /^https?:\\/\\/api-pay\\.soulapp\\.cn\\/vip\\/meet\\/userInfo/ then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
    "http-response ^https?:\\/\\/api-pay\\.soulapp\\.cn\\/privilege\\/supervip\\/status script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/soul.js,tag=SOUL-6,requires-body=true": "response if ${url} ~= /^https?:\\/\\/api-pay\\.soulapp\\.cn\\/privilege\\/supervip\\/status/ then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soul/soul_ads.js\") with enable=soul_enable, tag=\"soul_ads\", timeout=60, requires_body=true",
}


def remove_identical_script_response_duplicates(lines):
    """Use one code-identical response handler while preserving the broader legacy API paths."""
    remove_counts = {item: 0 for item in IDENTICAL_SCRIPT_REMOVE_TRIGGERS}
    source_counts = {item: 0 for item in IDENTICAL_SCRIPT_KEEP_SOURCE_TRIGGERS}
    rrtv_script_triggers = set(IDENTICAL_SCRIPT_CURRENT_CANONICAL_TRIGGERS[:9])
    rrtv_source_triggers = set(IDENTICAL_SCRIPT_KEEP_SOURCE_TRIGGERS[:9])
    rrtv_native_mode = not any(item in lines for item in rrtv_script_triggers)
    current_snapshot_mode = all(item in lines for item in IDENTICAL_SCRIPT_CURRENT_CANONICAL_TRIGGERS)
    if rrtv_native_mode:
        canonical_triggers = IDENTICAL_SCRIPT_CURRENT_CANONICAL_TRIGGERS[9:]
    else:
        canonical_triggers = IDENTICAL_SCRIPT_CURRENT_CANONICAL_TRIGGERS if current_snapshot_mode else IDENTICAL_SCRIPT_KEEP_TRIGGERS
    output_counts = {item: 0 for item in canonical_triggers}
    remove_set = set(IDENTICAL_SCRIPT_REMOVE_TRIGGERS)
    output, section, target_seen, removed = [], "", False, 0
    source_mode = any(item in lines for item in remove_set)

    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue

        normalized = line.replace("\\", "")
        inventory_line = re.sub(r"enable=\$\{([^}]+)\}", r"enable=\1", line.strip())
        has_script_action = "http-response " in line or "script(" in line or "script-path=" in line
        soul_endpoint = (
            ("api-a.soulapp.cn" in normalized and ("/post/gift/list" in normalized or "/official/scene/module" in normalized))
            or ("api-chat.soulapp.cn" in normalized and "/chat/limitInfo" in normalized)
            or ("api-user.soulapp.cn" in normalized and ("/furion/position/content" in normalized or "/planet/config" in normalized))
            or ("api-pay.soulapp.cn" in normalized and ("vip/meet/userInfo" in normalized or "privilege/supervip/status" in normalized))
            or ("post.soulapp.cn" in normalized and ("/hot/soul/rank" in normalized or "/post/homepage/guide/card" in normalized or "/post/recSquare/subTabs" in normalized))
            or ("gateway-mobile-gray.soulapp.cn" in normalized and "/mobile/app/version/queryIos" in normalized)
            or ("api-account.soulapp.cn" in normalized and "/teenager/config" in normalized)
            or ("chat-live.soulapp.cn" in normalized and "/chatroom/chatClassifyRoomList" in normalized)
            or ("47.110.187.87" in normalized and "/winterfell/v2/getIpByDomain" in normalized)
        )
        is_target = (
            section == "Script"
            and has_script_action
            and ("api.rr.tv" in normalized or (soul_endpoint and "soul_qx.js" not in line) or ("reddit.com" in normalized and "gql" in normalized))
        )
        if not is_target:
            output.append(line)
            continue

        target_seen = True
        if source_mode:
            if line in remove_counts:
                remove_counts[line] += 1
                if remove_counts[line] > 1:
                    raise ValueError("duplicate legacy identical-script trigger; refusing ambiguous cleanup")
                removed += 1
                continue
            if inventory_line in source_counts:
                source_counts[inventory_line] += 1
                if source_counts[inventory_line] > 1:
                    raise ValueError("duplicate retained identical-script source trigger")
                transformed = IDENTICAL_SCRIPT_TRANSFORMS.get(inventory_line, inventory_line)
                if "enable=${" in line:
                    transformed = re.sub(r"enable=([A-Za-z0-9_]+)", r"enable=${\1}", transformed)
                output.append(transformed)
                continue
            raise ValueError(f"RRTV/Soul/Reddit script inventory changed; refusing unreviewed consolidation: {line.strip()}")

        if inventory_line in output_counts:
            output_counts[inventory_line] += 1
            if output_counts[inventory_line] > 1:
                raise ValueError("duplicate consolidated identical-script trigger")
            output.append(line)
            continue
        raise ValueError("consolidated RRTV/Soul/Reddit inventory changed; refusing unreviewed cleanup")

    if not target_seen:
        return output, 0

    if source_mode:
        # A retired supplemental feed may leave only a subset of the historical
        # R-Store handlers. Cleanup is safe only for exact known duplicate rows;
        # missing rows are not reconstructed and unknown variants still fail closed.
        if not any(remove_counts.values()):
            return output, 0
        return output, removed

    if not all(count == 1 for count in output_counts.values()):
        raise ValueError("consolidated identical-script inventory incomplete; refusing partial consolidation")
    return output, 0


# More same-response script overlaps: identical Kuwo code, plus newer superset handlers.
MORE_RESPONSE_REMOVE_TRIGGERS = (
    "http-response ^https?:\\/\\/(mgxhtj|nmobi|searchrecterm)\\.kuwo\\.cn\\/(mgxh|mobi|recterm)\\.s script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/Unlock/kuwo.js,tag=KUWO,requires-body=true",
    "http-response ^https?:\\/\\/audiobookpay\\.kuwo\\.cn\\/a\\.p script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/Unlock/kuwo.js,tag=KUWO-2,requires-body=true",
    "http-response ^https?:\\/\\/musicpay\\.kuwo\\.cn\\/music\\.pay script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/Unlock/kuwo.js,tag=KUWO-3,requires-body=true",
    "http-response ^https?:\\/\\/vip\\d\\.kuwo\\.cn\\/vip\\/(enc\\/user\\/vip\\?op=ui|v\\d\\/theme\\?op=gd) script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/Unlock/kuwo.js,tag=KUWO-4,requires-body=true",
    "http-response ^https?:\\/\\/vip\\d\\.kuwo\\.cn\\/vip\\/v\\d\\/user\\/vip\\?op=ui script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/Unlock/kuwo.js,tag=KUWO-5,requires-body=true",
    "http-response ^https?:\\/\\/napi\\.ithome\\.com\\/api\\/(news\\/index|topmenu\\/getfeeds) script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/ithome.js,tag=ITHOME,requires-body=true",
    "http-response ^https?:\\/\\/cn-acs\\.m\\.cainiao\\.com\\/gw\\/mtop\\.cainiao\\.nbpresentation\\.(pickup\\.empty\\.page|protocol\\.homepage)\\.get script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cainiao.js,tag=CAINIAO,requires-body=true",
    "http-response ^https?:\\/\\/cn-acs\\.m\\.cainiao\\.com\\/gw\\/mtop\\.nbfriend\\.message\\.conversation\\.list\\.cn script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cainiao.js,tag=CAINIAO-2,requires-body=true",
    "response if ${url} ~= /^https?:\\/\\/iqushangwang\\.8quan\\.com\\/index\\.php\\/i\\/index\\/index/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/QuDa.js\") with enable=quda_enable, tag=\"去哒\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/dict\\.youdao\\.com\\/(homepage\\/promotion|course\\/tab\\/home|homepage\\/tile)/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/youdao/dict-youdao-ad.js\") with enable=whyiyzdccidm_enable, tag=\"网易有道词典\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/wx\\.mygolbs\\.com\\/WxBusServer\\/ApiData\\.do/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/zhangshanggongjiao.js\") with enable=vhuhgsjn_enable, tag=\"掌上公交小程序广告\", timeout=60, requires_body=true",
)
MORE_RESPONSE_KEEP_SOURCE_TRIGGERS = (
    "response if ${url} ~= /^https?:\\/\\/(mgxhtj|nmobi|searchrecterm)\\.kuwo\\.cn\\/(mgxh|mobi|recterm)\\.s/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/kuwo/kuwo.js\") with enable=kuwoybyt_enable, tag=\"酷我音乐\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/audiobookpay\\.kuwo\\.cn\\/a\\.p/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/kuwo/kuwo.js\") with enable=kuwoybyt_enable, tag=\"酷我音乐\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/musicpay\\.kuwo\\.cn\\/music\\.pay/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/kuwo/kuwo.js\") with enable=kuwoybyt_enable, tag=\"酷我音乐\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/vip1\\.kuwo\\.cn\\/vip\\/(enc\\/user\\/vip\\?op=ui|v\\d\\/theme\\?op=gd)/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/kuwo/kuwo.js\") with enable=kuwoybyt_enable, tag=\"酷我音乐\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/vip1\\.kuwo\\.cn\\/vip\\/v\\d\\/user\\/vip\\?op=ui/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/kuwo/kuwo.js\") with enable=kuwoybyt_enable, tag=\"酷我音乐\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/napi\\.ithome\\.com\\/api\\/(news\\/index|topmenu\\/getfeeds)/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/ithome/ithome.js\") with enable=itzj_enable, tag=\"ithome\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https:\\/\\/guide-acs\\.m\\.taobao\\.com\\/gw\\/mtop\\.cainiao\\.guoguo\\.nbnetflow\\.ads\\.mshow/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cainiao/cainiao.js\") with enable=albb_enable, tag=\"阿里巴巴广告\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/cn-acs\\.m\\.cainiao\\.com\\/gw\\/mtop\\.cainiao\\.guoguo\\.nbnetflow\\.ads\\.m?show\\.cn/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cainiao/cainiao.js\") with enable=cdnngogo_enable, tag=\"菜鸟裹裹\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/cn-acs\\.m\\.cainiao\\.com\\/gw\\/mtop\\.cainiao\\.nbpresentation\\.(pickup\\.empty\\.page|protocol\\.homepage)\\.get\\.cn/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cainiao/cainiao.js\") with enable=cdnngogo_enable, tag=\"菜鸟裹裹\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/cn-acs\\.m\\.cainiao\\.com\\/gw\\/mtop\\.nbfriend\\.message\\.conversation\\.list\\.cn/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cainiao/cainiao.js\") with enable=cdnngogo_enable, tag=\"菜鸟裹裹\", timeout=60, requires_body=true",
    "http-response ^https?:\\/\\/iqushangwang\\.8quan\\.com\\/index\\.php\\/i\\/index\\/index script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/quda.js,tag=QUDA,requires-body=true",
    "http-response ^https?:\\/\\/dict\\.youdao\\.com\\/(homepage\\/promotion|course\\/tab\\/home|homepage\\/tile) script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/163youdao.js,tag=163YOUDAO,requires-body=true",
    "http-response ^https?:\\/\\/wx\\.mygolbs\\.com\\/WxBusServer\\/ApiData\\.do script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/zsgj.js,tag=MYGOLBS,requires-body=true",
)
MORE_RESPONSE_KEEP_TRIGGERS = (
    "response if ${url} ~= /^https?:\\/\\/(mgxhtj|nmobi|searchrecterm)\\.kuwo\\.cn\\/(mgxh|mobi|recterm)\\.s/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/kuwo/kuwo.js\") with enable=kuwoybyt_enable, tag=\"酷我音乐\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/audiobookpay\\.kuwo\\.cn\\/a\\.p/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/kuwo/kuwo.js\") with enable=kuwoybyt_enable, tag=\"酷我音乐\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/musicpay\\.kuwo\\.cn\\/music\\.pay/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/kuwo/kuwo.js\") with enable=kuwoybyt_enable, tag=\"酷我音乐\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/vip\\d\\.kuwo\\.cn\\/vip\\/(enc\\/user\\/vip\\?op=ui|v\\d\\/theme\\?op=gd)/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/kuwo/kuwo.js\") with enable=kuwoybyt_enable, tag=\"酷我音乐\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/vip\\d\\.kuwo\\.cn\\/vip\\/v\\d\\/user\\/vip\\?op=ui/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/kuwo/kuwo.js\") with enable=kuwoybyt_enable, tag=\"酷我音乐\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/napi\\.ithome\\.com\\/api\\/(news\\/index|topmenu\\/getfeeds)/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/ithome/ithome.js\") with enable=itzj_enable, tag=\"ithome\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https:\\/\\/guide-acs\\.m\\.taobao\\.com\\/gw\\/mtop\\.cainiao\\.guoguo\\.nbnetflow\\.ads\\.mshow/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cainiao/cainiao.js\") with enable=albb_enable, tag=\"阿里巴巴广告\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/cn-acs\\.m\\.cainiao\\.com\\/gw\\/mtop\\.cainiao\\.guoguo\\.nbnetflow\\.ads\\.m?show\\.cn/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cainiao/cainiao.js\") with enable=cdnngogo_enable, tag=\"菜鸟裹裹\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/cn-acs\\.m\\.cainiao\\.com\\/gw\\/mtop\\.cainiao\\.nbpresentation\\.(pickup\\.empty\\.page|protocol\\.homepage)\\.get/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cainiao/cainiao.js\") with enable=cdnngogo_enable, tag=\"菜鸟裹裹\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/cn-acs\\.m\\.cainiao\\.com\\/gw\\/mtop\\.nbfriend\\.message\\.conversation\\.list\\.cn/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cainiao/cainiao.js\") with enable=cdnngogo_enable, tag=\"菜鸟裹裹\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/iqushangwang\\.8quan\\.com\\/index\\.php\\/i\\/index\\/index/ then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/quda.js\") with enable=quda_enable, tag=\"去哒\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/dict\\.youdao\\.com\\/(homepage\\/promotion|course\\/tab\\/home|homepage\\/tile)/ then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/163youdao.js\") with enable=whyiyzdccidm_enable, tag=\"网易有道词典\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/wx\\.mygolbs\\.com\\/WxBusServer\\/ApiData\\.do/ then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/zsgj.js\") with enable=vhuhgsjn_enable, tag=\"掌上公交小程序广告\", timeout=60, requires_body=true",
)
MORE_RESPONSE_TRANSFORMS = {
    "response if ${url} ~= /^https?:\\/\\/vip1\\.kuwo\\.cn\\/vip\\/(enc\\/user\\/vip\\?op=ui|v\\d\\/theme\\?op=gd)/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/kuwo/kuwo.js\") with enable=kuwoybyt_enable, tag=\"酷我音乐\", timeout=60, requires_body=true": "response if ${url} ~= /^https?:\\/\\/vip\\d\\.kuwo\\.cn\\/vip\\/(enc\\/user\\/vip\\?op=ui|v\\d\\/theme\\?op=gd)/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/kuwo/kuwo.js\") with enable=kuwoybyt_enable, tag=\"酷我音乐\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/vip1\\.kuwo\\.cn\\/vip\\/v\\d\\/user\\/vip\\?op=ui/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/kuwo/kuwo.js\") with enable=kuwoybyt_enable, tag=\"酷我音乐\", timeout=60, requires_body=true": "response if ${url} ~= /^https?:\\/\\/vip\\d\\.kuwo\\.cn\\/vip\\/v\\d\\/user\\/vip\\?op=ui/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/kuwo/kuwo.js\") with enable=kuwoybyt_enable, tag=\"酷我音乐\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/cn-acs\\.m\\.cainiao\\.com\\/gw\\/mtop\\.cainiao\\.nbpresentation\\.(pickup\\.empty\\.page|protocol\\.homepage)\\.get\\.cn/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cainiao/cainiao.js\") with enable=cdnngogo_enable, tag=\"菜鸟裹裹\", timeout=60, requires_body=true": "response if ${url} ~= /^https?:\\/\\/cn-acs\\.m\\.cainiao\\.com\\/gw\\/mtop\\.cainiao\\.nbpresentation\\.(pickup\\.empty\\.page|protocol\\.homepage)\\.get/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cainiao/cainiao.js\") with enable=cdnngogo_enable, tag=\"菜鸟裹裹\", timeout=60, requires_body=true",
    "http-response ^https?:\\/\\/iqushangwang\\.8quan\\.com\\/index\\.php\\/i\\/index\\/index script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/quda.js,tag=QUDA,requires-body=true": "response if ${url} ~= /^https?:\\/\\/iqushangwang\\.8quan\\.com\\/index\\.php\\/i\\/index\\/index/ then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/quda.js\") with enable=quda_enable, tag=\"去哒\", timeout=60, requires_body=true",
    "http-response ^https?:\\/\\/dict\\.youdao\\.com\\/(homepage\\/promotion|course\\/tab\\/home|homepage\\/tile) script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/163youdao.js,tag=163YOUDAO,requires-body=true": "response if ${url} ~= /^https?:\\/\\/dict\\.youdao\\.com\\/(homepage\\/promotion|course\\/tab\\/home|homepage\\/tile)/ then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/163youdao.js\") with enable=whyiyzdccidm_enable, tag=\"网易有道词典\", timeout=60, requires_body=true",
    "http-response ^https?:\\/\\/wx\\.mygolbs\\.com\\/WxBusServer\\/ApiData\\.do script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/zsgj.js,tag=MYGOLBS,requires-body=true": "response if ${url} ~= /^https?:\\/\\/wx\\.mygolbs\\.com\\/WxBusServer\\/ApiData\\.do/ then script(\"https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/zsgj.js\") with enable=vhuhgsjn_enable, tag=\"掌上公交小程序广告\", timeout=60, requires_body=true",
}


PUPU_DUPLICATE_RESPONSE_MARKERS = (
    "/client/marketing/advertisement/v1",
    "/client/order/orders/list/v4",
)


def remove_redundant_pupu_response_scripts(lines):
    """Remove Romeo Pupu handlers only when the equivalent Wool handler exists."""
    section = ""
    entries = {marker: {"wool": [], "romeo": []} for marker in PUPU_DUPLICATE_RESPONSE_MARKERS}
    for index, line in enumerate(lines):
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if section != "Script" or "response if " not in line:
            continue
        normalized = re.sub(r"\\+", "", line).lower()
        for marker in PUPU_DUPLICATE_RESPONSE_MARKERS:
            if marker not in normalized:
                continue
            if "pupusplashads.js" in normalized:
                entries[marker]["wool"].append(index)
            elif "ishowshu_pp.js" in normalized:
                entries[marker]["romeo"].append(index)

    remove_indexes = set()
    for marker, sources in entries.items():
        if len(sources["wool"]) > 1 or len(sources["romeo"]) > 1:
            raise ValueError("duplicate Pupu response handler; refusing ambiguous cleanup: " + marker)
        # Missing canonical coverage is fail-closed: keep the Romeo handler.
        if sources["wool"] and sources["romeo"]:
            remove_indexes.add(sources["romeo"][0])

    if not remove_indexes:
        return list(lines), 0
    return [line for index, line in enumerate(lines) if index not in remove_indexes], len(remove_indexes)


PUPU_REMOTE_SCRIPT_URL = "https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/PupuSplashAds.js"
PUPU_LOCAL_SCRIPT_URL = "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/pupu/pupu-splash.js"
PUPU_RESPONSE_MATCHERS_BEFORE = (
    r"/^https:\/\/j1\.pupuapi\.com\/client\/search\/hot_keywords\/v3/i",
    r"/^https:\/\/j1\.pupuapi\.com\/client\/app_resource\/resource_preload\/list_h5_resource/i",
    r"/^https:\/\/j1\.pupuapi\.com\/client\/marketing\/advertisement\/v1/i",
    r"/^https:\/\/j1\.pupuapi\.com\/client\/search\/hub\/search_box\/products\/v6/i",
    r"/^https:\/\/j1\.pupuapi\.com\/client\/order_settlement\/detail/i",
    r"/^https:\/\/j1\.pupuapi\.com\/client\/order\/orders\/list\/v4/i",
)
PUPU_RESPONSE_MATCHERS_AFTER = (
    r"/^https:\/\/j1\.pupuapi\.com\/client\/search\/hot_keywords\/v3\/?(?:\?[^#]*)?$/i",
    r"/^https:\/\/j1\.pupuapi\.com\/client\/app_resource\/resource_preload\/list_h5_resource\/?(?:\?[^#]*)?$/i",
    r"/^https:\/\/j1\.pupuapi\.com\/client\/marketing\/advertisement\/v1\/?(?:\?[^#]*)?$/i",
    r"/^https:\/\/j1\.pupuapi\.com\/client\/search\/hub\/search_box\/products\/v6\/?(?:\?[^#]*)?$/i",
    r"/^https:\/\/j1\.pupuapi\.com\/client\/order_settlement\/detail\/?(?:\?[^#]*)?$/i",
    r"/^https:\/\/j1\.pupuapi\.com\/client\/order\/orders\/list\/v4\/?(?:\?[^#]*)?$/i",
)


def _pupu_response_rule_lines(script_url, matchers):
    return [
        'response if ${url} ~= ' + matcher + ' then script("' + script_url + '") with enable=${pupuicui_enable}, tag="朴朴超市", timeout=60, requires_body=true'
        for matcher in matchers
    ]


def migrate_pupu_response_script_to_local(lines):
    """Use the local single-pass Pupu handler and anchor its six endpoint matchers."""
    section = ""
    script_indexes = []
    for index, line in enumerate(lines):
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
        elif section == "Script":
            script_indexes.append(index)

    old_rules = _pupu_response_rule_lines(PUPU_REMOTE_SCRIPT_URL, PUPU_RESPONSE_MATCHERS_BEFORE)
    new_rules = _pupu_response_rule_lines(PUPU_LOCAL_SCRIPT_URL, PUPU_RESPONSE_MATCHERS_AFTER)
    script_lines = [lines[index] for index in script_indexes]
    remote_count = sum(PUPU_REMOTE_SCRIPT_URL in line for line in script_lines)
    local_count = sum(PUPU_LOCAL_SCRIPT_URL in line for line in script_lines)

    if remote_count == 0 and local_count == 0:
        return list(lines), 0

    old_counts = [script_lines.count(rule) for rule in old_rules]
    new_counts = [script_lines.count(rule) for rule in new_rules]
    if remote_count == len(old_rules) and local_count == 0 and old_counts == [1] * len(old_rules) and new_counts == [0] * len(new_rules):
        replacements = dict(zip(old_rules, new_rules))
        updated = [replacements.get(line, line) for line in lines]
        return updated, len(old_rules)

    if local_count == len(new_rules) and remote_count == 0 and new_counts == [1] * len(new_rules) and old_counts == [0] * len(old_rules):
        return list(lines), 0

    raise ValueError("Pupu response trigger inventory or matcher drift; refusing partial local migration")


ALIPAN_ONBOARD_DUPLICATE_MARKER = "/v1/users/onboard_list"


def remove_redundant_alipan_onboard_response_script(lines):
    """Keep Wool's equivalent onboard-list cleaner and retain Romeo's unique handlers."""
    section = ""
    wool_indexes, romeo_indexes = [], []
    for index, line in enumerate(lines):
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if section != "Script" or "response if " not in line:
            continue
        normalized = re.sub(r"\\+", "", line).lower()
        if "member.alipan.com" not in normalized or ALIPAN_ONBOARD_DUPLICATE_MARKER not in normalized:
            continue
        if "scripts/adrive/adrive.js" in normalized:
            wool_indexes.append(index)
        elif "rucu6_adrive.js" in normalized:
            romeo_indexes.append(index)

    if len(wool_indexes) > 1 or len(romeo_indexes) > 1:
        raise ValueError("duplicate Aliyun Drive onboard-list response handler; refusing ambiguous cleanup")
    # If the canonical Wool handler is absent, preserve Romeo's only handler.
    if not wool_indexes or not romeo_indexes:
        return list(lines), 0
    remove_index = romeo_indexes[0]
    return [line for index, line in enumerate(lines) if index != remove_index], 1


MGW_ECNY_RESPONSE_HOST = "mgs.wallet.pbcdci.cn"


MAASEA_YOUTUBE_RESPONSE_BROAD_ENDPOINTS = r"youtubei\/v1\/(browse|next|player|search|reel\/reel_watch_sequence|guide|account\/get_setting|get_watch|log_event|config)"
MAASEA_YOUTUBE_RESPONSE_NARROW_ENDPOINTS = r"youtubei\/v1\/(guide|account\/get_setting)"


def optimize_maasea_youtube_shadowed_triggers(lines):
    """Remove a fully shadowed Maasea log_event request and narrow its response fallback."""
    section = ""
    response_candidates = []
    maasea_request_candidates = []
    devchristian_request_candidates = []
    for index, line in enumerate(lines):
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if section != "Script":
            continue
        lowered = line.lower()
        if "maasea_youtube.response.js" in lowered and lowered.startswith(("http-response ", "response if ")):
            response_candidates.append(index)
        if "maasea_youtube.request.js" in lowered and "log_event" in lowered and lowered.startswith("http-request "):
            maasea_request_candidates.append(index)
        if "request.min.js" in lowered and "log_event" in lowered and lowered.startswith("http-request "):
            devchristian_request_candidates.append(index)

    if len(response_candidates) > 1:
        raise ValueError("duplicate Maasea YouTube response triggers; refusing ambiguous narrowing")
    if len(maasea_request_candidates) > 1:
        raise ValueError("duplicate Maasea YouTube log_event request triggers")
    if len(devchristian_request_candidates) > 1:
        raise ValueError("duplicate DevChristian YouTube log_event request handlers")

    updated = list(lines)
    changed = 0
    if response_candidates:
        index = response_candidates[0]
        line = updated[index]
        broad_count = line.count(MAASEA_YOUTUBE_RESPONSE_BROAD_ENDPOINTS)
        narrow_count = line.count(MAASEA_YOUTUBE_RESPONSE_NARROW_ENDPOINTS)
        if broad_count == 1 and narrow_count == 0:
            updated[index] = line.replace(
                MAASEA_YOUTUBE_RESPONSE_BROAD_ENDPOINTS,
                MAASEA_YOUTUBE_RESPONSE_NARROW_ENDPOINTS,
                1,
            )
            changed += 1
        elif broad_count == 0 and narrow_count == 1:
            pass
        else:
            raise ValueError("Maasea YouTube response endpoint matcher changed; refusing unreviewed narrowing")

    if maasea_request_candidates:
        maasea_index = maasea_request_candidates[0]
        if devchristian_request_candidates:
            devchristian_index = devchristian_request_candidates[0]
            if devchristian_index < maasea_index:
                updated.pop(maasea_index)
                changed += 1
    return updated, changed


AMDC_RSTORE_SCRIPT_MARKER = "Res/Scripts/AntiAd/amdc.js"
AMDC_WOOL_SCRIPT_MARKER = "Scripts/header.js"
AMDC_CANONICAL_MATCHER = r"^https?:\/\/amdc\.m\.taobao\.com\/amdc\/mobileDispatch$"


def _normalize_amdc_response_matcher(value):
    """Normalize legacy and Script v2 regex wrappers for one reviewed AMDC URL."""
    value = value.strip()
    if value.startswith("/") and re.search(r"/[a-z]*$", value):
        value = value[1:]
        value = re.sub(r"/[a-z]*$", "", value)
    return value.lower()


def remove_shadowed_amdc_response_trigger(lines):
    """Remove Wool's later AMDC handler when the earlier R-Store handler covers it."""
    section = ""
    rstore, wool = [], []
    for index, line in enumerate(lines):
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if section != "Script":
            continue
        lowered = line.lower()
        normalized_line = re.sub(r"\\+", "", lowered)
        if "amdc.m.taobao.com" not in normalized_line:
            continue
        if lowered.startswith("http-response ") and AMDC_RSTORE_SCRIPT_MARKER.lower() in lowered:
            parts = line.split(maxsplit=2)
            if len(parts) < 2:
                raise ValueError("AMDC R-Store response matcher is malformed")
            rstore.append((index, parts[1]))
        elif lowered.startswith("response if ") and AMDC_WOOL_SCRIPT_MARKER.lower() in lowered:
            if "~=" not in line or " then script" not in line:
                raise ValueError("AMDC Wool response matcher is malformed")
            matcher = line.split("~=", 1)[1].split(" then script", 1)[0].strip()
            wool.append((index, matcher))

    if len(rstore) > 1 or len(wool) > 1:
        raise ValueError("duplicate AMDC response handlers; refusing ambiguous cleanup")
    if not rstore or not wool:
        return list(lines), 0

    expected = _normalize_amdc_response_matcher(AMDC_CANONICAL_MATCHER)
    if (
        _normalize_amdc_response_matcher(rstore[0][1]) != expected
        or _normalize_amdc_response_matcher(wool[0][1]) != expected
    ):
        raise ValueError("AMDC response matcher changed; refusing unreviewed shadow cleanup")

    # Loon selects the first complete Response Script match in final configuration
    # order. Only remove Wool when the broader, earlier R-Store handler is first.
    if rstore[0][0] >= wool[0][0]:
        return list(lines), 0

    remove_index = wool[0][0]
    return [line for index, line in enumerate(lines) if index != remove_index], 1


SHADOWED_CROSS_SYNTAX_RESPONSE_PAIRS = (
    (
        "SMZDM article bubble",
        "Res/Scripts/AntiAd/smzdm.js",
        "Scripts/smzdm/Smzdm.js",
        r"^https?:\/\/article-api\.smzdm\.com\/publish\/get_bubble",
        ("article-api.smzdm.com", "publish/get_bubble"),
    ),
    (
        "SMZDM wallet home",
        "Res/Scripts/AntiAd/smzdm.js",
        "Scripts/smzdm/Smzdm.js",
        r"^https?:\/\/qianbao\.smzdm\.com\/v\d\/app\/home",
        ("qianbao.smzdm.com", "app/home"),
    ),
    (
        "Baidu Map ad endpoint",
        "Res/Scripts/AntiAd/baiduMap.js",
        "Scripts/baidumap.js",
        r"^https?:\/\/newclient\.map\.baidu\.com\/client\/phpui2\/\?qt=ads",
        ("newclient.map.baidu.com", "qt=ads"),
    ),
    (
        "Keep personal page",
        "Res/Scripts/AntiAd/keep.js",
        "Scripts/keep.js",
        r"^https?:\/\/api\.gotokeep\.com\/athena\/v\d\/people\/my$",
        ("api.gotokeep.com", "people/my"),
    ),
    (
        "Keep basic config",
        "Res/Scripts/AntiAd/keep.js",
        "Scripts/keep.js",
        r"^https?:\/\/api\.gotokeep\.com\/config\/v\d\/basic",
        ("api.gotokeep.com", "config/v"),
    ),
    (
        "Keep homepage tabs",
        "Res/Scripts/AntiAd/keep.js",
        "Scripts/keep.js",
        r"^https?:\/\/api\.gotokeep\.com\/homepage\/v\d\/tab",
        ("api.gotokeep.com", "homepage/v"),
    ),
    (
        "Keep sport page",
        "Res/Scripts/AntiAd/keep.js",
        "Scripts/keep.js",
        r"^https?:\/\/api\.gotokeep\.com\/sportpage\/sport\/v\d\/mysport",
        ("api.gotokeep.com", "sportpage/sport/v"),
    ),
    (
        "LTSST city guide",
        "Res/Scripts/AntiAd/ltsst.js",
        "Scripts/lvtusuishenting/ltsst-ad.js",
        r"^https?:\/\/www\.1314zhilv\.com\/ltsstnew\/(common\/getJGQIconNew|city\/getAllBannelByCity)",
        ("www.1314zhilv.com", "getJGQIconNew"),
    ),
)


def remove_shadowed_cross_syntax_response_triggers(lines):
    """Remove later Script v2 handlers shadowed by exact earlier legacy handlers."""
    section = ""
    updated = list(lines)
    removed = 0
    for name, legacy_script, v2_script, expected_matcher, search_markers in SHADOWED_CROSS_SYNTAX_RESPONSE_PAIRS:
        legacy_candidates, v2_candidates = [], []
        for index, line in enumerate(updated):
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1]
                continue
            if section != "Script":
                continue
            lowered = line.lower()
            if "http-response " not in lowered and not lowered.startswith("response if "):
                continue
            if not all(marker.lower() in re.sub(r"\\+", "", lowered) for marker in search_markers):
                continue
            if lowered.startswith("http-response ") and legacy_script.lower() in lowered:
                parts = line.split(maxsplit=2)
                if len(parts) < 2:
                    raise ValueError("%s legacy response matcher is malformed" % name)
                legacy_candidates.append((index, parts[1]))
            elif lowered.startswith("response if ") and v2_script.lower() in lowered:
                if "~=" not in line or " then script" not in line:
                    raise ValueError("%s Script v2 response matcher is malformed" % name)
                matcher = line.split("~=", 1)[1].split(" then script", 1)[0].strip()
                v2_candidates.append((index, matcher))

        if len(legacy_candidates) > 1 or len(v2_candidates) > 1:
            raise ValueError("duplicate %s cross-syntax response handlers" % name)
        if not legacy_candidates or not v2_candidates:
            continue

        expected = _normalize_amdc_response_matcher(expected_matcher)
        if (
            _normalize_amdc_response_matcher(legacy_candidates[0][1]) != expected
            or _normalize_amdc_response_matcher(v2_candidates[0][1]) != expected
        ):
            raise ValueError("%s response matcher changed; refusing shadow cleanup" % name)

        # Loon selects at most one Response Script by final configuration order.
        # Keep both if an upstream reorder would make the legacy handler no longer first.
        if legacy_candidates[0][0] >= v2_candidates[0][0]:
            continue

        remove_index = v2_candidates[0][0]
        updated.pop(remove_index)
        removed += 1

    return updated, removed


ISHOWSHU_AMAP_SCRIPT_MARKER = "Modules/JavaScript/ishowshu/amap/ishowshu_amap.js"
RUCU6_AMAP_SCRIPT_MARKER = "sources/amap/rucu6_amap.js"
SHADOWED_ISHOWSHU_AMAP_TRIGGERS = (
    (
        "Amap hotel and walking-navigation pages",
        r"/^https:\/\/m5\.amap\.com\/ws\/c3frontend\/af-(hotel|launch)\/page\/main\?/i",
        r"c3frontend\/af-(hotel|launch)\/page\/main",
        r"/^https:\/\/m5\.amap\.com\/ws\/c3frontend\/(?:af-(?:hotel|launch)\/page\/main|af-nearby\/nearby)/i",
    ),
    (
        "Amap coupon and POI detail pages",
        r"/^https:\/\/(?:info\.amap\.com|m5\.amap\.com)\/ws\/shield\/search\/(common\/coupon\/info|poi\/detail)/i",
        r"ws/shield/search/(common/coupon/info|poi/detail)",
        r"/^https:\/\/(?:info|m5)\.amap\.com\/ws\/shield\/search\/(?:common\/coupon\/info|poi\/detail)/i",
    ),
    (
        "Amap search result pages",
        r"/^https:\/\/m5\.amap\.com\/ws\/shield\/search_poi\/search\/sp/i",
        r"search_poi\/search\/sp",
        r"/^https:\/\/m5\.amap\.com\/ws\/shield\/search_poi\/(?:mps|search\/sp|sug|tips_operation_location)/i",
    ),
    (
        "Amap search suggestions",
        r"/^https:\/\/m5\.amap\.com\/ws\/shield\/search_poi\/sug/i",
        r"search_poi\/sug",
        r"/^https:\/\/m5\.amap\.com\/ws\/shield\/search_poi\/(?:mps|search\/sp|sug|tips_operation_location)/i",
    ),
    (
        "Amap search operation banner",
        r"/^https:\/\/m5\.amap\.com\/ws\/shield\/search_poi\/tips_operation_location/i",
        r"search_poi\/tips_operation_location",
        r"/^https:\/\/m5\.amap\.com\/ws\/shield\/search_poi\/(?:mps|search\/sp|sug|tips_operation_location)/i",
    ),
    (
        "Amap nearby page",
        r"/^https:\/\/m5\.amap\.com\/ws\/c3frontend\/af-nearby\/nearby/i",
        r"c3frontend\/af-nearby\/nearby",
        r"/^https:\/\/m5\.amap\.com\/ws\/c3frontend\/(?:af-(?:hotel|launch)\/page\/main|af-nearby\/nearby)/i",
    ),
)


def remove_shadowed_ishowshu_amap_response_triggers(lines):
    """Drop iShowShu Amap entries covered by the more complete local RuCu6 handler."""
    section = ""
    entries = []
    for index, line in enumerate(lines):
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if section == "Script" and line.lower().startswith("response if "):
            entries.append((index, line))

    remove_indexes = set()
    verified_local = set()
    for name, old_matcher, path_marker, local_matcher in SHADOWED_ISHOWSHU_AMAP_TRIGGERS:
        old_candidates = []
        for index, line in entries:
            lowered = line.lower()
            normalized = re.sub(r"\\+", "", lowered)
            normalized_marker = re.sub(r"\\+", "", path_marker.lower())
            if ISHOWSHU_AMAP_SCRIPT_MARKER.lower() in lowered and normalized_marker in normalized:
                matcher = line.split("~=", 1)[1].split(" then script", 1)[0].strip() if "~=" in line and " then script" in line else ""
                old_candidates.append((index, matcher))

        if not old_candidates:
            continue
        if any(matcher != old_matcher for _, matcher in old_candidates):
            raise ValueError("iShowShu Amap matcher changed; refusing shadow cleanup: " + name)

        if local_matcher not in verified_local:
            local_candidates = [
                (index, line)
                for index, line in entries
                if RUCU6_AMAP_SCRIPT_MARKER.lower() in line.lower()
                and "~=" in line
                and line.split("~=", 1)[1].split(" then script", 1)[0].strip() == local_matcher
            ]
            if len(local_candidates) != 1:
                raise ValueError("local RuCu6 Amap coverage missing or duplicated; refusing shadow cleanup: " + name)
            verified_local.add(local_matcher)

        remove_indexes.update(index for index, _matcher in old_candidates)

    if not remove_indexes:
        return list(lines), 0
    return [line for index, line in enumerate(lines) if index not in remove_indexes], len(remove_indexes)


USMILE_RESPONSE_SCRIPT_MARKER = "www.myusmile.online/user/plaquetopic/selectbytype"
USMILE_RESPONSE_SCRIPT_URL = "Res/Scripts/AntiAd/usmile.js"


def remove_unneeded_usmile_response_body_read(lines):
    """Remove response-body buffering from Usmile's request-header-only handler."""
    section = ""
    candidates = []
    for index, line in enumerate(lines):
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if section != "Script" or not line.lower().startswith(("http-response ", "response if ")):
            continue
        normalized = re.sub(r"\\+", "", line).lower()
        if USMILE_RESPONSE_SCRIPT_MARKER in normalized and USMILE_RESPONSE_SCRIPT_URL.lower() in normalized:
            candidates.append(index)

    if len(candidates) > 2:
        raise ValueError("duplicate Usmile response handlers; refusing ambiguous body-read cleanup")
    if not candidates:
        return list(lines), 0

    updated = list(lines)
    removed = 0
    for index in candidates:
        line = updated[index]
        matches = list(re.finditer(r",\s*requires[-_]body\s*=\s*true(?=\s*(?:,|$))", line, re.I))
        if len(matches) > 1:
            raise ValueError("duplicate Usmile requires-body option; refusing ambiguous cleanup")
        if matches:
            match = matches[0]
            updated[index] = line[:match.start()] + line[match.end():]
            removed += 1
    return updated, removed


HEADER_ONLY_RESPONSE_SCRIPT_MARKERS = (
    ("image.spdbccc.com.cn/group", "Res/Scripts/AntiAd/spdbccc.js"),
    ("cdn.sdb.com.cn/bron-coms/bron-coms/material-image", "Res/Scripts/AntiAd/sdb.js"),
    ("home.umetrip.com", "Scripts/umetrip/umetrip_ads.js"),
)


def remove_unneeded_header_only_response_body_reads(lines):
    """Remove body buffering only from verified response-header/request-header-only scripts."""
    section = ""
    found = {marker: [] for marker, _ in HEADER_ONLY_RESPONSE_SCRIPT_MARKERS}
    for index, line in enumerate(lines):
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if section != "Script" or not line.lower().startswith(("http-response ", "response if ")):
            continue
        normalized = re.sub(r"\\+", "", line).lower()
        for marker, script_path in HEADER_ONLY_RESPONSE_SCRIPT_MARKERS:
            if marker in normalized and script_path.lower() in normalized:
                found[marker].append(index)

    updated = list(lines)
    removed = 0
    for marker, _ in HEADER_ONLY_RESPONSE_SCRIPT_MARKERS:
        candidates = found[marker]
        if len(candidates) > 1:
            raise ValueError("duplicate header-only response handler for %s" % marker)
        if not candidates:
            continue
        index = candidates[0]
        matches = list(re.finditer(r",\s*requires[-_]body\s*=\s*true(?=\s*(?:,|$))", updated[index], re.I))
        if len(matches) > 1:
            raise ValueError("duplicate requires-body option for header-only response handler %s" % marker)
        if matches:
            match = matches[0]
            updated[index] = updated[index][:match.start()] + updated[index][match.end():]
            removed += 1
    return updated, removed


def remove_unneeded_mgw_ecny_response_body_read(lines):
    """Drop requires-body only for MGW's ECNY response handler, which reads request headers only."""
    section = ""
    candidates = []
    for index, line in enumerate(lines):
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if section != "Script" or not line.lower().startswith("http-response "):
            continue
        normalized = re.sub(r"\\+", "", line).lower()
        if MGW_ECNY_RESPONSE_HOST in normalized and "mgw.js" in normalized:
            candidates.append(index)

    if len(candidates) > 1:
        raise ValueError("duplicate MGW ECNY response handler; refusing ambiguous body-read cleanup")
    if not candidates:
        return list(lines), 0

    index = candidates[0]
    line = lines[index]
    matches = list(re.finditer(r",\s*requires-body\s*=\s*true(?=\s*(?:,|$))", line, re.I))
    if len(matches) > 1:
        raise ValueError("duplicate MGW ECNY requires-body option; refusing ambiguous cleanup")
    if not matches:
        return list(lines), 0

    updated = list(lines)
    updated[index] = line[:matches[0].start()] + line[matches[0].end():]
    return updated, 1


def remove_more_duplicate_response_scripts(lines):
    """Keep one handler per overlapping response, retaining broad matchers and safer guards."""
    normalize_switch = lambda value: re.sub(r"enable=\$\{([^}]+)\}", r"enable=\1", value.strip())
    remove_counts = {normalize_switch(item): 0 for item in MORE_RESPONSE_REMOVE_TRIGGERS}
    source_counts = {normalize_switch(item): 0 for item in MORE_RESPONSE_KEEP_SOURCE_TRIGGERS}
    output_counts = {normalize_switch(item): 0 for item in MORE_RESPONSE_KEEP_TRIGGERS}
    remove_set = set(remove_counts)
    normalized_lines = {normalize_switch(item) for item in lines}
    output, section, target_seen, removed = [], "", False, 0
    source_mode = bool(remove_set & normalized_lines)
    unknown_source_trigger = False

    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue

        normalized = line.replace("\\", "")
        inventory_line = normalize_switch(line)
        action = "http-response " in line or "response if " in line
        is_target = (
            section == "Script"
            and action
            and (
                "kuwo.cn" in normalized
                or "napi.ithome.com" in normalized
                or ("cn-acs.m.cainiao.com" in normalized and ("mtop.cainiao.nbpresentation" in normalized or "mtop.nbfriend.message.conversation.list" in normalized or "mtop.cainiao.guoguo" in normalized))
                or ("guide-acs.m.taobao.com" in normalized and "mtop.cainiao.guoguo" in normalized)
                or ("iqushangwang.8quan.com" in normalized and "/index.php/i/index/index" in normalized)
                or ("dict.youdao.com" in normalized and any(path in normalized for path in ("homepage/promotion", "course/tab/home", "homepage/tile")))
                or ("wx.mygolbs.com" in normalized and "/WxBusServer/ApiData.do" in normalized)
            )
        )
        if not is_target:
            output.append(line)
            continue

        target_seen = True
        if source_mode:
            if inventory_line in remove_counts:
                remove_counts[inventory_line] += 1
                if remove_counts[inventory_line] > 1:
                    raise ValueError("duplicate legacy response trigger; refusing ambiguous cleanup")
                removed += 1
                continue
            if inventory_line in source_counts:
                source_counts[inventory_line] += 1
                if source_counts[inventory_line] > 1:
                    raise ValueError("duplicate retained response source trigger")
                transformed = MORE_RESPONSE_TRANSFORMS.get(inventory_line, inventory_line)
                if "enable=${" in line:
                    transformed = re.sub(r"enable=([A-Za-z0-9_]+)", r"enable=${\1}", transformed)
                output.append(transformed)
                continue
            raise ValueError("Kuwo/iThome/Cainiao/QuDa/Youdao/ZSGJ inventory changed; refusing unreviewed consolidation: " + line.strip())

        if inventory_line in output_counts:
            output_counts[inventory_line] += 1
            if output_counts[inventory_line] > 1:
                raise ValueError("duplicate consolidated response trigger")
            output.append(line)
            continue
        raise ValueError("consolidated response inventory changed; refusing unreviewed cleanup: " + line.strip())

    if not target_seen:
        return output, 0

    if source_mode:
        if (not all(count == 1 for count in remove_counts.values())
                or not all(count == 1 for count in source_counts.values())):
            # Retired or partially updated upstream snapshots are left intact;
            # do not partially collapse a response-handler inventory.
            return list(lines), 0
        return output, removed

    if not all(count == 1 for count in output_counts.values()):
        raise ValueError("consolidated response inventory incomplete; refusing partial consolidation")
    return output, 0



XHS_SCRIPT_TRIGGER_LINES = frozenset((
    "http-response ^https?:\\/\\/edith\\.xiaohongshu\\.com\\/api\\/sns\\/v\\d+\\/note\\/widgets script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/xiaohongshu.js,tag=XIAOHONGSHU,requires-body=true",
    "http-response ^https?:\\/\\/edith\\.xiaohongshu\\.com\\/api\\/sns\\/v\\d+\\/user\\/followings\\/followfeed script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/xiaohongshu.js,tag=XIAOHONGSHU-2,requires-body=true",
    "http-response ^https?:\\/\\/edith\\.xiaohongshu\\.com\\/api\\/sns\\/v\\d+\\/search\\/(?:banner|hot)_list script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/xiaohongshu.js,tag=XIAOHONGSHU-3,requires-body=true",
    "http-response ^https?:\\/\\/edith\\.xiaohongshu\\.com\\/api\\/sns\\/v\\d+\\/search\\/(?:hint|trending)\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/xiaohongshu.js,tag=XIAOHONGSHU-4,requires-body=true",
    "http-response ^https?:\\/\\/edith\\.xiaohongshu\\.com\\/api\\/sns\\/v\\d+\\/search\\/notes\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/xiaohongshu.js,tag=XIAOHONGSHU-5,requires-body=true",
    "http-response ^https?:\\/\\/edith\\.xiaohongshu\\.com\\/api\\/sns\\/v\\d+\\/system_service\\/config\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/xiaohongshu.js,tag=XIAOHONGSHU-6,requires-body=true",
    "http-response ^https?:\\/\\/(?:edith|rec|www)\\.xiaohongshu\\.com\\/api\\/sns\\/v\\d+\\/note\\/(?:imagefeed|feed|videofeed|(live_photo|video)\\/save) script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/xiaohongshu.js,tag=XIAOHONGSHU-7,requires-body=true",
    "http-response ^https?:\\/\\/(?:edith|rec|www)\\.xiaohongshu\\.com\\/api\\/sns\\/v\\d+\\/(?:followfeed|homefeed)\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/xiaohongshu.js,tag=XIAOHONGSHU-8,requires-body=true",
    "http-response ^https?:\\/\\/edith\\.xiaohongshu\\.com\\/api\\/sns\\/v\\d+\\/recommend\\/user\\/follow_recommend\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/xiaohongshu.js,tag=XIAOHONGSHU-9,requires-body=true",
    "http-response ^https?:\\/\\/edith\\.xiaohongshu\\.com\\/api\\/sns\\/v\\d+\\/note\\/comment\\/(?:list|sub_comments)\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/xiaohongshu.js,tag=XIAOHONGSHU-10,requires-body=true",
    "http-response ^https?:\\/\\/edith\\.xiaohongshu\\.com\\/api\\/sns\\/v\\d+\\/interaction\\/comment\\/video\\/download\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/xiaohongshu.js,tag=XIAOHONGSHU-11,requires-body=true",
    "response if ${url} ~= /^https?:\\/\\/edith\\.(xiaohongshu|rnote)\\.com\\/api\\/sns\\/v\\d+\\/search\\/(banner|hot)_list/i then script(\"https://github.com/fmz200/wool_scripts/raw/main/Scripts/xiaohongshu/xiaohongshu.js\") with enable=xhs_enable, tag=\"小红书搜索页\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/edith\\.(xiaohongshu|rnote)\\.com\\/api\\/sns\\/v\\d+\\/search\\/(hint|trending)\\?/i then script(\"https://github.com/fmz200/wool_scripts/raw/main/Scripts/xiaohongshu/xiaohongshu.js\") with enable=xhs_enable, tag=\"小红书搜索页\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/(so|edith)\\.(xiaohongshu|rnote)\\.com\\/api\\/sns\\/v\\d+\\/search\\/notes\\?/i then script(\"https://github.com/fmz200/wool_scripts/raw/main/Scripts/xiaohongshu/xiaohongshu.js\") with enable=xhs_enable, tag=\"小红书搜索页\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/edith\\.(xiaohongshu|rnote)\\.com\\/api\\/sns\\/v\\d+\\/system_service\\/config\\?/i then script(\"https://github.com/fmz200/wool_scripts/raw/main/Scripts/xiaohongshu/xiaohongshu.js\") with enable=xhs_enable, tag=\"小红书开屏广告\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/edith\\.(xiaohongshu|rnote)\\.com\\/api\\/sns\\/v\\d+\\/system_service\\/splash_config/i then script(\"https://github.com/fmz200/wool_scripts/raw/main/Scripts/xiaohongshu/xiaohongshu.js\") with enable=xhs_enable, tag=\"小红书开屏广告\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/edith\\.(xiaohongshu|rnote)\\.com\\/api\\/sns\\/v\\d+\\/note\\/widgets/i then script(\"https://github.com/fmz200/wool_scripts/raw/main/Scripts/xiaohongshu/xiaohongshu.js\") with enable=xhs_enable, tag=\"小红书详情页\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/(edith|rec|www)\\.(xiaohongshu|rnote)\\.com\\/api\\/sns\\/v\\d+\\/note\\/(imagefeed|live_photo\\/save)/i then script(\"https://github.com/fmz200/wool_scripts/raw/main/Scripts/xiaohongshu/xiaohongshu.js\") with enable=xhs_enable, tag=\"小红书图片视频水印\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/(edith|rec|www)\\.(xiaohongshu|rnote)\\.com\\/api\\/sns\\/v\\d+\\/(followfeed|homefeed)\\?/i then script(\"https://github.com/fmz200/wool_scripts/raw/main/Scripts/xiaohongshu/xiaohongshu.js\") with enable=xhs_enable, tag=\"小红书图片视频水印\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/(edith|rec|www)\\.(xiaohongshu|rnote)\\.com\\/api\\/sns\\/(v2\\/note\\/feed|v3\\/note\\/videofeed)\\?/i then script(\"https://github.com/fmz200/wool_scripts/raw/main/Scripts/xiaohongshu/xiaohongshu.js\") with enable=xhs_enable, tag=\"小红书图片视频水印\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/(edith|rec|www)\\.(xiaohongshu|rnote)\\.com\\/api\\/sns\\/(v4\\/note\\/videofeed|v10\\/note\\/video\\/save)\\?/i then script(\"https://github.com/fmz200/wool_scripts/raw/main/Scripts/xiaohongshu/xiaohongshu.js\") with enable=xhs_enable, tag=\"小红书图片视频水印\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https:\\/\\/edith\\.(xiaohongshu|rnote)\\.com\\/api\\/sns\\/(v5\\/note\\/comment\\/list|v3\\/note\\/comment\\/sub_comments)\\?/i then script(\"https://github.com/fmz200/wool_scripts/raw/main/Scripts/xiaohongshu/xiaohongshu.js\") with enable=xhs_enable, tag=\"小红书评论区去水印存储\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https:\\/\\/edith\\.(xiaohongshu|rnote)\\.com\\/api\\/sns\\/v1\\/interaction\\/comment\\/video\\/download\\?/i then script(\"https://github.com/fmz200/wool_scripts/raw/main/Scripts/xiaohongshu/xiaohongshu.js\") with enable=xhs_enable, tag=\"小红书评论区去水印下载\", timeout=60, requires_body=true",
))
XHS_ARGUMENT_LINE = "xhs_enable = switch,true,false,tag=小红书-脚本开关"
XHS_WATERMARK_REQUIRED_RULES = frozenset((
    r"^https?:\/\/ci\.xiaohongshu\.com\/system_config\/watermark reject-img",
    r"request if ${url} ~= /^https?:\/\/ci\.(xiaohongshu|rnote)\.com\/system_config\/watermark/ then reject_img(200)",
))
XHS_WATERMARK_OPTIONAL_RULES = frozenset((
    r"^https:\/\/ci\.xiaohongshu\.com\/system_config\/watermark reject-img",
))
XHS_WATERMARK_IMAGE_RULES = XHS_WATERMARK_REQUIRED_RULES | XHS_WATERMARK_OPTIONAL_RULES

XHS_V3_VIDEO_AD_ONLY_RULE = r"""^https:\/\/(?:edith|rec|www)\.xiaohongshu\.com\/api\/sns\/v3\/note\/videofeed response-body-json-jq '. as $o | try (if (.data|type)=="array" then .data|=map(select(if type=="object" then ((.model_type=="note") and (has("ad")|not)) else false end)) else . end) catch $o'"""
XHS_V4_VIDEO_AD_ONLY_RULE = r"""^https:\/\/(?:edith|rec|www)\.xiaohongshu\.com\/api\/sns\/v4\/note\/videofeed response-body-json-jq '. as $o | try (if (.data|type)=="array" then .data|=map(select(if type=="object" then ((.model_type=="note") and (has("ad")|not)) else false end)) else . end) catch $o'"""


XHS_NATIVE_DUPLICATE_TRIGGER_TAGS = (
    "XIAOHONGSHU",
    "XIAOHONGSHU-3",
    "XIAOHONGSHU-4",
    "XIAOHONGSHU-5",
    "XIAOHONGSHU-6",
)

# Native JSON rules fully cover these two feed filters on edith/rec; retain
# R-Store fallback only for unsupported API versions/hosts.
XHS_NARROWED_TRIGGER_LINES = {
    "XIAOHONGSHU-2": (
        "http-response ^https?:\\/\\/edith\\.xiaohongshu\\.com\\/api\\/sns\\/v(?:[13-9]|[1-9][0-9]+)\\/user\\/followings\\/followfeed "
        "script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/xiaohongshu.js,tag=XIAOHONGSHU-2,requires-body=true"
    ),
    "XIAOHONGSHU-8": (
        "http-response ^https?:\\/\\/www\\.xiaohongshu\\.com\\/api\\/sns\\/v\\d+\\/(?:followfeed|homefeed)\\? "
        "script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/xiaohongshu.js,tag=XIAOHONGSHU-8,requires-body=true"
    ),
}

XHS_HOMEFEED_NATIVE_OLD_RULE = r"""^https:\/\/(?:edith|rec)\.xiaohongshu\.com\/api\/sns\/v\d+\/homefeed\? response-body-json-jq '. as $o | try (if (.data|type)==\"array\" then .data|=map(select(if type==\"object\" then ((.model_type!=\"live_v2\") and (has(\"ads_info\")|not) and (has(\"card_icon\")|not) and (has(\"note_attributes\")|not) and (.has_related_goods!=true)) else false end)|(if type==\"object\" then del(.related_ques) else . end)) else . end) catch $o'"""
XHS_HOMEFEED_NATIVE_RULE = r"""^https:\/\/(?:edith|rec)\.xiaohongshu\.com\/api\/sns\/v\d+\/homefeed\? response-body-json-jq '. as $o | try (if (.data|type)==\"array\" then .data|=map(select(if type==\"object\" then ((.model_type!=\"live_v2\") and (has(\"ads_info\")|not) and (has(\"card_icon\")|not) and ((.note_attributes | if type==\"array\" then index(\"goods\") != null elif type==\"string\" then contains(\"goods\") else false end) | not) and (.has_related_goods!=true)) else false end)|(if type==\"object\" then del(.related_ques) else . end)) else . end) catch $o'"""


def narrow_xiaohongshu_native_response_duplicates(lines):
    """Remove only XHS script passes whose exact endpoint has a native JSON rewrite."""
    original = list(lines)
    section = ""
    script_lines = []
    rewrite_lines = []
    for line in original:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            continue
        if section == "Script":
            script_lines.append(stripped)
        elif section == "Rewrite":
            rewrite_lines.append(stripped)

    expected_rstore = {
        tag: next((line for line in XHS_SCRIPT_TRIGGER_LINES
                   if line.startswith("http-response ")
                   and ("tag=" + tag + ",") in line), None)
        for tag in XHS_NATIVE_DUPLICATE_TRIGGER_TAGS
    }
    if any(value is None for value in expected_rstore.values()):
        raise ValueError("Xiaohongshu native duplicate trigger inventory is incomplete")

    actual_by_tag = {}
    for tag in XHS_NATIVE_DUPLICATE_TRIGGER_TAGS:
        matches = [line for line in script_lines if ("tag=" + tag + ",") in line]
        if not matches:
            return original, 0
        if len(matches) != 1 or matches[0] != expected_rstore[tag]:
            raise ValueError("Xiaohongshu R-Store native duplicate trigger changed: " + tag)
        actual_by_tag[tag] = matches[0]

    actual_by_narrowed_tag = {}
    for tag in XHS_NARROWED_TRIGGER_LINES:
        expected = next((line for line in XHS_SCRIPT_TRIGGER_LINES
                         if line.startswith("http-response ")
                         and ("tag=" + tag + ",") in line), None)
        matches = [line for line in script_lines if ("tag=" + tag + ",") in line]
        if expected is None or len(matches) != 1 or matches[0] != expected:
            raise ValueError("Xiaohongshu feed trigger inventory changed: " + tag)
        actual_by_narrowed_tag[tag] = matches[0]

    required_native = (
        ("/api/sns/v", "/note/widgets"),
        ("/api/sns/v", "/search/banner_list"),
        ("/api/sns/v", "/search/hot_list"),
        ("/api/sns/v", "/search/hint"),
        ("/api/sns/v", "/search/trending"),
        ("/api/sns/v", "/search/notes"),
        ("/api/sns/v", "/system_service/config"),
    )
    for _, endpoint in required_native:
        matches = [line for line in rewrite_lines
                   if "response-body-json-jq" in line
                   and "xiaohongshu.com" in re.sub(r"\\+", "", line)
                   and endpoint in re.sub(r"\\+", "", line)]
        if not matches:
            # Without the exact native JSON counterpart, retain the response
            # script instead of removing its only coverage after source pruning.
            return original, 0
        if len(matches) > 1:
            raise ValueError("Xiaohongshu native JSON coverage duplicated: " + endpoint)

    follow_user_rules = [
        line for line in rewrite_lines
        if "response-body-json-jq" in line
        and "/api/sns/v2/user/followings/followfeed" in re.sub(r"\\+", "", line)
        and '.recommend_reason=="friend_post"' in re.sub(r"\\+", "", line)
    ]
    followfeed_rules = [
        line for line in rewrite_lines
        if "response-body-json-jq" in line
        and "/api/sns/v" in re.sub(r"\\+", "", line)
        and "/user/followings/" not in re.sub(r"\\+", "", line)
        and "/followfeed" in re.sub(r"\\+", "", line)
        and '.recommend_reason!="recommend_user"' in re.sub(r"\\+", "", line)
    ]
    if not follow_user_rules or not followfeed_rules:
        return original, 0
    if len(follow_user_rules) > 1 or len(followfeed_rules) > 1:
        raise ValueError("Xiaohongshu native follow-feed JSON coverage duplicated")

    homefeed_rules = [
        line for line in rewrite_lines
        if "response-body-json-jq" in line
        and "/api/sns/v" in re.sub(r"\\+", "", line)
        and "/homefeed" in re.sub(r"\\+", "", line)
    ]
    if not homefeed_rules:
        return original, 0
    if len(homefeed_rules) > 1:
        raise ValueError("Xiaohongshu native home-feed JSON coverage duplicated")
    homefeed_rule = homefeed_rules[0]
    normalized_homefeed = re.sub(r"\\+", "", homefeed_rule)
    normalized_old_homefeed = re.sub(r"\\+", "", XHS_HOMEFEED_NATIVE_OLD_RULE)
    normalized_new_homefeed = re.sub(r"\\+", "", XHS_HOMEFEED_NATIVE_RULE)
    if normalized_homefeed not in (normalized_old_homefeed, normalized_new_homefeed):
        raise ValueError("Xiaohongshu native home-feed rule changed; refusing unreviewed conversion")
    if normalized_homefeed == normalized_old_homefeed:
        homefeed_replacement = homefeed_rule.replace(
            XHS_HOMEFEED_NATIVE_OLD_RULE, XHS_HOMEFEED_NATIVE_RULE
        )
        if homefeed_replacement == homefeed_rule:
            homefeed_replacement = XHS_HOMEFEED_NATIVE_RULE
    else:
        homefeed_replacement = homefeed_rule

    # FMZ duplicates are retained for the rnote.com host, which is not covered
    # by the native xiaohongshu.com rules. The xiaohongshu.com side is native-only.
    fmz_expected = {
        line for line in XHS_SCRIPT_TRIGGER_LINES
        if line.startswith("response if")
        and 'tag="小红书搜索页"' in line
        and any(marker in re.sub(r"\\+", "", line) for marker in (
            "/search/(banner|hot)_list",
            "/search/(hint|trending)",
            "/search/notes",
        ))
    }
    fmz_actual = {
        line for line in script_lines
        if 'tag="小红书搜索页"' in line
        and any(marker in re.sub(r"\\+", "", line) for marker in (
            "/search/(banner|hot)_list",
            "/search/(hint|trending)",
            "/search/notes",
        ))
    }
    normalize_fmz = lambda value: value.replace("enable=${xhs_enable}", "enable=xhs_enable")
    if ({normalize_fmz(line) for line in fmz_actual} != fmz_expected
            or len(fmz_actual) != 3):
        raise ValueError("Xiaohongshu FMZ search trigger inventory changed; refusing narrowing")

    replacements = {
        actual_by_narrowed_tag[tag]: narrowed
        for tag, narrowed in XHS_NARROWED_TRIGGER_LINES.items()
    }
    for line in fmz_actual:
        if "/search/notes" in re.sub(r"\\+", "", line):
            old = r"(so|edith)\.(xiaohongshu|rnote)\.com"
            new = r"(so|edith)\.rnote\.com"
        else:
            old = r"edith\.(xiaohongshu|rnote)\.com"
            new = r"edith\.rnote\.com"
        if line.count(old) != 1:
            raise ValueError("Xiaohongshu FMZ host matcher changed; refusing narrowing")
        replacements[line] = line.replace(old, new)

    result = []
    section = ""
    changed = 0
    homefeed_rule_replaced = False
    for line in original:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            result.append(line)
            continue
        if section == "Rewrite" and stripped == homefeed_rule and homefeed_replacement != homefeed_rule:
            result.append(homefeed_replacement)
            changed += 1
            homefeed_rule_replaced = True
            continue
        if section == "Script" and stripped in actual_by_tag.values():
            changed += 1
            continue
        if section == "Script" and stripped in replacements:
            result.append(replacements[stripped])
            changed += 1
            continue
        result.append(line)
    return result, changed


XHS_V3_VIDEO_RSTORE_NARROWED_TRIGGER = (
    r"http-response ^https?:\/\/(?:edith|rec|www)\.xiaohongshu\.com\/api\/sns\/(?:v(?:[13-9]|[1-9][0-9]+)\/note\/feed|v(?:[12]|[5-9]|[1-9][0-9]+)\/note\/videofeed|v(?:[1-9]|1[1-9]|[2-9][0-9]+)\/note\/video\/save) "
    r"script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/xiaohongshu.js,tag=XIAOHONGSHU-7,requires-body=true"
)
XHS_V3_VIDEO_RSTORE_PREVIOUS_NARROWED_TRIGGER = (
    r"http-response ^https?:\/\/(?:edith|rec|www)\.xiaohongshu\.com\/api\/sns\/(?:v\d+\/note\/(?:imagefeed|feed|(?:live_photo|video)\/save)|v4\/note\/videofeed) "
    r"script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/xiaohongshu.js,tag=XIAOHONGSHU-7,requires-body=true"
)
XHS_V3_VIDEO_FMZ_NARROWED_TRIGGER = (
    r'response if ${url} ~= /^https?:\/\/(?:(?:edith|rec|www)\.(?:xiaohongshu|rnote)\.com\/api\/sns\/v2\/note\/feed\?|(?:edith|rec|www)\.rnote\.com\/api\/sns\/v3\/note\/videofeed\?)/i '
    r'then script("https://github.com/fmz200/wool_scripts/raw/main/Scripts/xiaohongshu/xiaohongshu.js") with enable=${xhs_enable}, tag="小红书图片视频水印", timeout=60, requires_body=true'
)

def narrow_xiaohongshu_v3_video_native_duplicates(lines):
    """Drop only v3 video-feed script passes proven equivalent to native jq."""
    original = list(lines)
    section = ""
    script_lines, rewrite_lines = [], []
    for line in original:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            continue
        if section == "Script":
            script_lines.append(stripped)
        elif section == "Rewrite":
            rewrite_lines.append(stripped)

    has_rstore_target = any("tag=XIAOHONGSHU-7," in line for line in script_lines)
    has_fmz_target = any(
        'tag="小红书图片视频水印"' in line
        and ("v2/note/feed" in re.sub(r"\\+", "", line)
             or "v3/note/videofeed" in re.sub(r"\\+", "", line))
        for line in script_lines
    )
    if not has_rstore_target and not has_fmz_target:
        return original, 0

    rstore_expected = next(
        (line for line in XHS_SCRIPT_TRIGGER_LINES
         if line.startswith("http-response ") and "tag=XIAOHONGSHU-7," in line),
        None,
    )
    fmz_expected = next(
        (line for line in XHS_SCRIPT_TRIGGER_LINES
         if line.startswith("response if")
         and 'tag="小红书图片视频水印"' in line
         and "v2/note/feed" in re.sub(r"\\+", "", line)
         and "v3/note/videofeed" in re.sub(r"\\+", "", line)),
        None,
    )
    if rstore_expected is None or fmz_expected is None:
        raise ValueError("Xiaohongshu v3 video trigger inventory is incomplete")

    rstore_matches = [line for line in script_lines if "tag=XIAOHONGSHU-7," in line]
    fmz_matches = [
        line for line in script_lines
        if 'tag="小红书图片视频水印"' in line
        and ("v2/note/feed" in re.sub(r"\\+", "", line)
             or "v3/note/videofeed" in re.sub(r"\\+", "", line))
    ]
    if has_rstore_target:
        if rstore_expected is None or len(rstore_matches) != 1:
            raise ValueError("Xiaohongshu R-Store v3 video trigger inventory changed")
        if rstore_matches[0] not in (
            rstore_expected,
            XHS_V3_VIDEO_RSTORE_PREVIOUS_NARROWED_TRIGGER,
            XHS_V3_VIDEO_RSTORE_NARROWED_TRIGGER,
        ):
            raise ValueError("Xiaohongshu R-Store video-feed trigger changed; refusing narrowing")
    if has_fmz_target:
        if fmz_expected is None or len(fmz_matches) != 1:
            raise ValueError("Xiaohongshu FMZ v3 video trigger inventory changed")
        normalize_fmz = lambda value: (
            re.sub(r"\\+", "", value)
            .replace("enable=" + "$" + "{xhs_enable}", "enable=xhs_enable")
            .replace(
                "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/xiaohongshu/xiaohongshu.js",
                "https://github.com/fmz200/wool_scripts/raw/main/Scripts/xiaohongshu/xiaohongshu.js",
            )
        )
        if normalize_fmz(fmz_matches[0]) not in (
            normalize_fmz(fmz_expected),
            normalize_fmz(XHS_V3_VIDEO_FMZ_NARROWED_TRIGGER),
        ):
            raise ValueError("Xiaohongshu FMZ video-feed trigger changed; refusing narrowing")

    native_matches = [
        line for line in rewrite_lines
        if "response-body-json-jq" in line
        and "/api/sns/v3/note/videofeed" in re.sub(r"\\+", "", line)
    ]
    if len(native_matches) != 1:
        raise ValueError("Xiaohongshu v3 video native JSON coverage missing or duplicated")
    normalized_native = re.sub(r"\\+", "", native_matches[0])
    required = (
        "xiaohongshu.com",
        "function_switch",
        ".disable_save=false",
        ".disable_watermark=true",
        ".disable_weibo_cover=true",
        "video_download",
    )
    missing = [marker for marker in required if marker not in normalized_native]
    if missing:
        raise ValueError(
            "Xiaohongshu v3 video native rule no longer covers script behavior: "
            + ", ".join(missing)
        )

    replacements = {}
    if has_rstore_target:
        replacements[rstore_matches[0]] = XHS_V3_VIDEO_RSTORE_NARROWED_TRIGGER
    if has_fmz_target:
        replacements[fmz_matches[0]] = XHS_V3_VIDEO_FMZ_NARROWED_TRIGGER
    changed = 0
    result, section = [], ""
    for line in original:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            result.append(line)
            continue
        if section == "Script" and stripped in replacements:
            narrowed = replacements[stripped]
            if narrowed != stripped:
                result.append(narrowed)
                changed += 1
            else:
                result.append(line)
            continue
        result.append(line)
    return result, changed


# The stateful FMZ v4 handler already caches H.265/H.264 streams and serves
# v10/note/video/save. Keep that cache path, move the ad filter into the same
# script, and avoid a second native JSON parse of the same v4 response.
XHS_RSTORE_COMMENT_TRIGGER = next(
    line for line in XHS_SCRIPT_TRIGGER_LINES
    if line.startswith("http-response ") and "tag=XIAOHONGSHU-10," in line
)
XHS_RSTORE_COMMENT_TRIGGER_NARROWED = XHS_RSTORE_COMMENT_TRIGGER.replace(
    r"v\d+\/note\/comment\/(?:list|sub_comments)",
    r"(?:v(?:[1246-9]|[1-9][0-9]+)\/note\/comment\/(?:list|sub_comments)|v3\/note\/comment\/list|v5\/note\/comment\/sub_comments)",
)
XHS_FMZ_V4_TRIGGER = next(
    line for line in XHS_SCRIPT_TRIGGER_LINES
    if line.startswith("response if")
    and "v4/note/videofeed" in re.sub(r"\\+", "", line)
    and "v10/note/video/save" in re.sub(r"\\+", "", line)
)
XHS_FMZ_V4_LOCAL_TRIGGER = (
    XHS_FMZ_V4_TRIGGER
    .replace(
        "https://github.com/fmz200/wool_scripts/raw/main/Scripts/xiaohongshu/xiaohongshu.js",
        "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/xiaohongshu/xiaohongshu-v4.js",
    )
    .replace('tag="小红书图片视频水印"', 'tag="小红书视频缓存与下载"')
)
XHS_FMZ_COMMENT_LIST_TRIGGER = next(
    line for line in XHS_SCRIPT_TRIGGER_LINES
    if line.startswith("response if")
    and "v5/note/comment/list" in re.sub(r"\\+", "", line)
    and "v3/note/comment/sub_comments" in re.sub(r"\\+", "", line)
)
XHS_FMZ_COMMENT_LOCAL_TRIGGER = (
    XHS_FMZ_COMMENT_LIST_TRIGGER
    .replace(
        "https://github.com/fmz200/wool_scripts/raw/main/Scripts/xiaohongshu/xiaohongshu.js",
        "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/xiaohongshu/xiaohongshu-v4.js",
    )
    .replace('tag="小红书评论区去水印存储"', 'tag="小红书评论区本地缓存处理"')
)
XHS_RSTORE_COMMENT_DOWNLOAD_TRIGGER = next(
    line for line in XHS_SCRIPT_TRIGGER_LINES if "tag=XIAOHONGSHU-11," in line
)
XHS_FMZ_COMMENT_DOWNLOAD_TRIGGER = next(
    line for line in XHS_SCRIPT_TRIGGER_LINES
    if line.startswith("response if")
    and "v1/interaction/comment/video/download" in re.sub(r"\\+", "", line)
)
XHS_FMZ_COMMENT_DOWNLOAD_LOCAL_TRIGGER = (
    XHS_FMZ_COMMENT_DOWNLOAD_TRIGGER
    .replace(
        "https://github.com/fmz200/wool_scripts/raw/main/Scripts/xiaohongshu/xiaohongshu.js",
        "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/xiaohongshu/xiaohongshu-v4.js",
    )
    .replace('tag="小红书评论区去水印下载"', 'tag="小红书评论区本地缓存下载"')
)


def normalize_xhs_fmz_trigger(value):
    return re.sub(r"\\+", "", value).replace("enable=${xhs_enable}", "enable=xhs_enable")


def migrate_xiaohongshu_v4_and_comment_processing(lines):
    """Keep stateful cache/download scripts and remove only proven duplicate JSON passes."""
    original = list(lines)
    section = ""
    script_lines, rewrite_lines = [], []
    for line in original:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            continue
        if section == "Script":
            script_lines.append(stripped)
        elif section == "Rewrite":
            rewrite_lines.append(stripped)

    fmz_v4 = [
        line for line in script_lines
        if "v4/note/videofeed" in re.sub(r"\\+", "", line)
        and "v10/note/video/save" in re.sub(r"\\+", "", line)
    ]
    if len(fmz_v4) > 1:
        raise ValueError("Xiaohongshu FMZ v4 cache trigger duplicated")

    rstore_comment = [
        line for line in script_lines if "tag=XIAOHONGSHU-10," in line
    ]
    if len(rstore_comment) > 1:
        raise ValueError("Xiaohongshu R-Store comment trigger duplicated")

    fmz_comment = [
        line for line in script_lines
        if "v5/note/comment/list" in re.sub(r"\\+", "", line)
        and "v3/note/comment/sub_comments" in re.sub(r"\\+", "", line)
    ]
    if len(fmz_comment) > 1:
        raise ValueError("Xiaohongshu FMZ comment trigger duplicated")

    rstore_comment_download = [
        line for line in script_lines if "tag=XIAOHONGSHU-11," in line
    ]
    if len(rstore_comment_download) > 1:
        raise ValueError("Xiaohongshu R-Store comment-download trigger duplicated")
    fmz_comment_download = [
        line for line in script_lines
        if "v1/interaction/comment/video/download" in re.sub(r"\\+", "", line)
        and line.startswith("response if")
    ]
    if len(fmz_comment_download) > 1:
        raise ValueError("Xiaohongshu FMZ comment-download trigger duplicated")

    replacements = {}
    remove_rewrites = set()

    if fmz_v4:
        current = fmz_v4[0]
        if normalize_xhs_fmz_trigger(current) == normalize_xhs_fmz_trigger(XHS_FMZ_V4_TRIGGER):
            v4_native = [
                line for line in rewrite_lines
                if "/api/sns/v4/note/videofeed" in re.sub(r"\\+", "", line)
                and "response-body-json-jq" in line
            ]
            if len(v4_native) != 1:
                raise ValueError("Xiaohongshu v4 native filter missing or duplicated")
            normalized = re.sub(r"\\+", "", v4_native[0])
            required = ("function_switch", "disable_save", "disable_watermark", "video_download", 'has("ad")')
            missing = [marker for marker in required if marker not in normalized]
            if missing:
                raise ValueError("Xiaohongshu v4 native behavior changed; refusing script migration: " + ", ".join(missing))
            replacements[current] = (
                current
                .replace(
                    "https://github.com/fmz200/wool_scripts/raw/main/Scripts/xiaohongshu/xiaohongshu.js",
                    "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/xiaohongshu/xiaohongshu-v4.js",
                )
                .replace('tag="小红书图片视频水印"', 'tag="小红书视频缓存与下载"')
            )
            remove_rewrites.add(v4_native[0])
        elif normalize_xhs_fmz_trigger(current) == normalize_xhs_fmz_trigger(XHS_FMZ_V4_LOCAL_TRIGGER):
            if any(
                "/api/sns/v4/note/videofeed" in re.sub(r"\\+", "", line)
                and "response-body-json-jq" in line
                for line in rewrite_lines
            ):
                raise ValueError("Xiaohongshu v4 local script and native JSON filter still overlap")
        else:
            raise ValueError("Xiaohongshu FMZ v4 trigger changed; refusing cache migration")

    if fmz_comment:
        current = fmz_comment[0]
        if normalize_xhs_fmz_trigger(current) == normalize_xhs_fmz_trigger(XHS_FMZ_COMMENT_LIST_TRIGGER):
            replacements[current] = XHS_FMZ_COMMENT_LOCAL_TRIGGER
        elif normalize_xhs_fmz_trigger(current) != normalize_xhs_fmz_trigger(XHS_FMZ_COMMENT_LOCAL_TRIGGER):
            raise ValueError("Xiaohongshu FMZ comment trigger changed; refusing local migration")

    if fmz_comment_download:
        current = fmz_comment_download[0]
        if normalize_xhs_fmz_trigger(current) == normalize_xhs_fmz_trigger(XHS_FMZ_COMMENT_DOWNLOAD_TRIGGER):
            replacements[current] = XHS_FMZ_COMMENT_DOWNLOAD_LOCAL_TRIGGER
        elif normalize_xhs_fmz_trigger(current) != normalize_xhs_fmz_trigger(XHS_FMZ_COMMENT_DOWNLOAD_LOCAL_TRIGGER):
            raise ValueError("Xiaohongshu FMZ comment-download trigger changed; refusing local migration")

    if rstore_comment_download:
        current = rstore_comment_download[0]
        if current != XHS_RSTORE_COMMENT_DOWNLOAD_TRIGGER:
            raise ValueError("Xiaohongshu R-Store comment-download trigger changed; refusing inert-trigger removal")

    if rstore_comment:
        current = rstore_comment[0]
        if current not in (XHS_RSTORE_COMMENT_TRIGGER, XHS_RSTORE_COMMENT_TRIGGER_NARROWED):
            raise ValueError("Xiaohongshu R-Store comment trigger changed; refusing version narrowing")
        if not fmz_comment or normalize_xhs_fmz_trigger(fmz_comment[0]) not in (
            normalize_xhs_fmz_trigger(XHS_FMZ_COMMENT_LIST_TRIGGER),
            normalize_xhs_fmz_trigger(XHS_FMZ_COMMENT_LOCAL_TRIGGER),
        ):
            raise ValueError("Xiaohongshu FMZ comment-version coverage missing; refusing R-Store narrowing")
        replacements[current] = XHS_RSTORE_COMMENT_TRIGGER_NARROWED

    comment_native = [
        line for line in rewrite_lines
        if "/note/comment/list" in re.sub(r"\\+", "", line)
        and "response-body-json-jq" in line
        and "comment_type" in line
        and "media_source_type" in line
    ]
    if comment_native:
        if len(comment_native) != 1:
            raise ValueError("Xiaohongshu comment native JSON rule duplicated")
        if not rstore_comment or not fmz_comment:
            raise ValueError("Xiaohongshu comment script coverage incomplete; refusing native-rule removal")
        normalized = re.sub(r"\\+", "", comment_native[0])
        if "edith.xiaohongshu.com" not in normalized:
            raise ValueError("Xiaohongshu comment native rule host changed")
        remove_rewrites.add(comment_native[0])

    if not replacements and not remove_rewrites and not rstore_comment_download:
        return original, 0

    result, section = [], ""
    changed = 0
    for line in original:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            result.append(line)
            continue
        if section == "Script" and stripped in rstore_comment_download:
            changed += 1
            continue
        if section == "Script" and stripped in replacements:
            result.append(replacements[stripped])
            if replacements[stripped] != stripped:
                changed += 1
            continue
        if section == "Rewrite" and stripped in remove_rewrites:
            changed += 1
            continue
        result.append(line)
    return result, changed




def optimize_xiaohongshu_response_cost(lines):
    """Apply only to the complete reviewed upstream inventory; otherwise preserve source unchanged."""
    original = list(lines)
    section = ""
    script_lines = []
    argument_count = 0
    rewrite_counts = {"imagefeed": 0, "v2_feed": 0, "v3_video": 0, "v4_video": 0,
                      "comment_list": 0, "watermark_image": 0}
    rewrite_actions = {}
    watermark_rules = set()

    for line in original:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            continue
        if section == "Argument" and stripped == XHS_ARGUMENT_LINE:
            argument_count += 1
        elif section == "Script" and "xiaohongshu" in stripped.lower():
            script_lines.append(stripped)
        elif section == "Rewrite":
            normalized = re.sub(r"\\+/", "/", stripped)
            if ("ci" in normalized and "xiaohongshu" in normalized
                    and "/system_config/watermark" in normalized
                    and ("reject-img" in stripped or "reject_img(200)" in stripped)):
                rewrite_counts["watermark_image"] += 1
                watermark_rules.add(stripped)
                rewrite_actions[stripped] = "remove"
            elif "xiaohongshu" in normalized and "response-body-json-jq" in stripped:
                if "/v1/note/imagefeed" in normalized:
                    rewrite_counts["imagefeed"] += 1
                    rewrite_actions[stripped] = "remove" if "disable_watermark" in stripped and "video_download" in stripped else "invalid"
                elif "/v2/note/feed" in normalized:
                    rewrite_counts["v2_feed"] += 1
                    rewrite_actions[stripped] = "remove" if "disable_watermark" in stripped and "video_download" in stripped else "invalid"
                elif "/v3/note/videofeed" in normalized:
                    rewrite_counts["v3_video"] += 1
                    required = ("disable_watermark", "video_download", "model_type", 'has("ad")')
                    rewrite_actions[stripped] = "remove" if "disable_watermark" in stripped and "video_download" in stripped else "invalid"
                elif "/v4/note/videofeed" in normalized:
                    rewrite_counts["v4_video"] += 1
                    required = ("disable_watermark", "video_download", "model_type", 'has("ad")')
                    rewrite_actions[stripped] = "v4" if all(token in stripped for token in required) else "invalid"
                elif "/note/comment/list" in normalized and "comment_type" in stripped and "media_source_type" in stripped:
                    rewrite_counts["comment_list"] += 1
                    rewrite_actions[stripped] = "remove"

    if (len(script_lines) != len(XHS_SCRIPT_TRIGGER_LINES)
            or set(script_lines) != XHS_SCRIPT_TRIGGER_LINES
            or len(script_lines) != len(set(script_lines))):
        return original, 0
    if argument_count != 1:
        return original, 0
    expected = {"imagefeed": 1, "v2_feed": 1, "v3_video": 1, "v4_video": 1,
                "comment_list": 1}
    if (any(rewrite_counts[key] != count for key, count in expected.items())
            or not XHS_WATERMARK_REQUIRED_RULES.issubset(watermark_rules)
            or not watermark_rules.issubset(XHS_WATERMARK_IMAGE_RULES)
            or rewrite_counts["watermark_image"] != len(watermark_rules)
            or len(watermark_rules) not in (2, 3)
            or any(action == "invalid" for action in rewrite_actions.values())):
        return original, 0
    if sum(action == "v4" for action in rewrite_actions.values()) != 1:
        return original, 0

    output, section = [], ""
    for line in original:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            output.append(line)
            continue
        if section == "Argument" and stripped == XHS_ARGUMENT_LINE:
            continue
        if section == "Script" and stripped in XHS_SCRIPT_TRIGGER_LINES:
            continue
        if section == "Rewrite":
            action = rewrite_actions.get(stripped)
            if action == "remove":
                continue
            if action == "v3":
                output.append(XHS_V3_VIDEO_AD_ONLY_RULE)
                continue
            if action == "v4":
                output.append(XHS_V4_VIDEO_AD_ONLY_RULE)
                continue
        output.append(line)
    return output, len(XHS_SCRIPT_TRIGGER_LINES)


WEIBO_SCRIPT_TRIGGER_LINES = frozenset((
    "http-response ^https?:\\/\\/api\\.weibo\\.cn\\/2\\/(checkin\\/show|client\\/publisher_list|push\\/active)\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js,tag=WEIBO,requires-body=true",
    "http-response ^https?:\\/\\/api\\.weibo\\.cn\\/2\\/groups\\/allgroups\\/v2\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js,tag=WEIBO-2,requires-body=true",
    "http-response ^https?:\\/\\/api\\.weibo\\.cn\\/2\\/(cardlist|page)\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js,tag=WEIBO-3,requires-body=true",
    "http-response ^https?:\\/\\/api\\.weibo\\.cn\\/2\\/comments\\/build_comments\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js,tag=WEIBO-4,requires-body=true",
    "http-response ^https?:\\/\\/api\\.weibo\\.cn\\/2\\/(container\\/asyn|flowlist|flowpage)\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js,tag=WEIBO-5,requires-body=true",
    "http-response ^https?:\\/\\/api\\.weibo\\.cn\\/2\\/friendships\\/(create|destroy)\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js,tag=WEIBO-6,requires-body=true",
    "http-response ^https?:\\/\\/api\\.weibo\\.cn\\/2\\/profile\\/(container_timeline|dealatt|me|statuses\\/tab|userinfo)\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js,tag=WEIBO-7,requires-body=true",
    "http-response ^https?:\\/\\/api\\.weibo\\.cn\\/2\\/statuses\\/(container_timeline(?:_hot|_topic|_topicpage|_unread)?|unread_hot_timeline)\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js,tag=WEIBO-8,requires-body=true",
    "http-response ^https?:\\/\\/api\\.weibo\\.cn\\/2\\/statuses\\/(extend|show)\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js,tag=WEIBO-9,requires-body=true",
    "http-response ^https?:\\/\\/api\\.weibo\\.cn\\/2\\/video\\/tiny_stream_video_list\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js,tag=WEIBO-10,requires-body=true",
    "http-response ^https?:\\/\\/api\\.weibo\\.cn\\/2\\/!\\/huati\\/discovery_home_bottom_channels\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js,tag=WEIBO-11,requires-body=true",
    "http-response ^https?:\\/\\/api\\.weibo\\.cn\\/2\\/direct_messages\\/user_list\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js,tag=WEIBO-12,requires-body=true",
    "http-response ^https?:\\/\\/api\\.weibo\\.cn\\/2\\/messageflow\\/notice\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js,tag=WEIBO-13,requires-body=true",
    "http-response ^https?:\\/\\/api\\.weibo\\.cn\\/2\\/search\\/(container_timeline|finder)\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js,tag=WEIBO-14,requires-body=true",
    "http-response ^https?:\\/\\/api\\.weibo\\.cn\\/2\\/searchall\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js,tag=WEIBO-15,requires-body=true",
    "http-response ^https?:\\/\\/bootpreload\\.uve\\.weibo\\.com\\/v[12]\\/ad\\/preload script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js,tag=WEIBO-16,requires-body=true",
    "http-response ^https?:\\/\\/sdkapp\\.uve\\.weibo\\.com\\/interface\\/sdk\\/sdkad\\.php script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js,tag=WEIBO-17,requires-body=true",
    "http-response ^https?:\\/\\/wbapp\\.uve\\.weibo\\.com\\/(preload\\/get_ad|wbapplua\\/wbpullad\\.lua)\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js,tag=WEIBO-18,requires-body=true",
    "http-response ^https?:\\/\\/new\\.vip\\.weibo\\.cn\\/aj\\/appicon\\/list\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js,tag=WEIBO-19,requires-body=true",
))
WEIBO_COMBINED_HOME_TRIGGER = "http-response ^https?:\\/\\/api\\.weibo\\.cn\\/2\\/(checkin\\/show|client\\/publisher_list|push\\/active)\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js,tag=WEIBO,requires-body=true"
WEIBO_PUSH_ACTIVE_TRIGGER = "http-response ^https?:\\/\\/api\\.weibo\\.cn\\/2\\/(push\\/active)\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js,tag=WEIBO,requires-body=true"
WEIBO_NON_AD_TRIGGER_LINES = frozenset((
    "http-response ^https?:\\/\\/api\\.weibo\\.cn\\/2\\/friendships\\/(create|destroy)\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js,tag=WEIBO-6,requires-body=true",
    "http-response ^https?:\\/\\/api\\.weibo\\.cn\\/2\\/video\\/tiny_stream_video_list\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js,tag=WEIBO-10,requires-body=true",
    "http-response ^https?:\\/\\/api\\.weibo\\.cn\\/2\\/!\\/huati\\/discovery_home_bottom_channels\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js,tag=WEIBO-11,requires-body=true",
    "http-response ^https?:\\/\\/api\\.weibo\\.cn\\/2\\/direct_messages\\/user_list\\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js,tag=WEIBO-12,requires-body=true",
))

WEIBO_OPTIMIZED_SCRIPT_TRIGGER_LINES = (
    WEIBO_SCRIPT_TRIGGER_LINES - WEIBO_NON_AD_TRIGGER_LINES - {WEIBO_COMBINED_HOME_TRIGGER}
) | {WEIBO_PUSH_ACTIVE_TRIGGER}


def remove_weibo_non_ad_response_triggers(lines):
    """Drop non-ad Weibo response handlers and narrow the mixed home matcher to its ad endpoint."""
    original = list(lines)
    section = ""
    observed = []
    for line in original:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
        elif section == "Script" and "weibo.js" in stripped.lower():
            observed.append(stripped)

    if len(observed) != len(set(observed)):
        return original, 0
    observed_set = set(observed)
    if observed_set == WEIBO_OPTIMIZED_SCRIPT_TRIGGER_LINES:
        return original, 0
    if len(observed) != len(WEIBO_SCRIPT_TRIGGER_LINES) or observed_set != WEIBO_SCRIPT_TRIGGER_LINES:
        return original, 0

    output = []
    section = ""
    for line in original:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            output.append(line)
            continue
        if section == "Script":
            if stripped == WEIBO_COMBINED_HOME_TRIGGER:
                output.append(WEIBO_PUSH_ACTIVE_TRIGGER)
                continue
            if stripped in WEIBO_NON_AD_TRIGGER_LINES:
                continue
        output.append(line)
    return output, len(WEIBO_NON_AD_TRIGGER_LINES) + 1


RRTV_SOURCE_TRIGGERS = (
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/\\w{3}\\/level\\/info/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/v3plus\\/index\\/channel\\?pageNum=1&position=CHANNEL_INDEX/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/app\\/config\\/h5NativeBar/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/v3plus\\/index\\/channel\\?pageNum=1&position=CHANNEL_MY/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/user\\/privilege\\/list/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/ad\\/getAll/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/drama\\/app\\/get_combined_drama_detail/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/watch\\/v\\d/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/user\\/profile/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
)
RRTV_NON_AD_SOURCE_TRIGGERS = (
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/\\w{3}\\/level\\/info/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/app\\/config\\/h5NativeBar/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/v3plus\\/index\\/channel\\?pageNum=1&position=CHANNEL_MY/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/user\\/privilege\\/list/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/drama\\/app\\/get_combined_drama_detail/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/watch\\/v\\d/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/user\\/profile/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
)
RRTV_RAW_SOURCE_TRIGGERS = (
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/\\w{3}\\/level\\/info/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /https://api.rr.tv/v3plus/index/channel\\?pageNum=1&position=CHANNEL_INDEX/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/app\\/config\\/h5NativeBar/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/v3plus\\/index\\/channel\\?pageNum=1&position=CHANNEL_MY/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/user\\/privilege\\/list/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/ad\\/getAll/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/drama\\/app\\/get_combined_drama_detail/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /https://api.rr.tv/watch/v4/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /https://api.rr.tv/user/profile/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true",
)
RRTV_BLOCKADS_SOURCE_TRIGGERS = (
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/\\w{3}\\/level\\/info/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=${rfrfuipk_enable}, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /https:\\/\\/api.rr.tv\\/v3plus\\/index\\/channel\\?pageNum=1&position=CHANNEL_INDEX/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=${rfrfuipk_enable}, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/app\\/config\\/h5NativeBar/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=${rfrfuipk_enable}, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/v3plus\\/index\\/channel\\?pageNum=1&position=CHANNEL_MY/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=${rfrfuipk_enable}, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/user\\/privilege\\/list/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=${rfrfuipk_enable}, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/ad\\/getAll/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=${rfrfuipk_enable}, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/drama\\/app\\/get_combined_drama_detail/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=${rfrfuipk_enable}, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /https:\\/\\/api.rr.tv\\/watch\\/v4/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=${rfrfuipk_enable}, tag=\"rrtv_json\", timeout=60, requires_body=true",
    "response if ${url} ~= /https:\\/\\/api.rr.tv\\/user\\/profile/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=${rfrfuipk_enable}, tag=\"rrtv_json\", timeout=60, requires_body=true",
)
RRTV_BLOCKADS_NON_AD_SOURCE_TRIGGERS = tuple(RRTV_BLOCKADS_SOURCE_TRIGGERS[index] for index in (0, 2, 3, 4, 6, 7, 8))

RRTV_SOURCE_VARIANT_GROUPS = tuple(
    frozenset((canonical, raw, current))
    for canonical, raw, current in zip(
        RRTV_SOURCE_TRIGGERS, RRTV_RAW_SOURCE_TRIGGERS, RRTV_BLOCKADS_SOURCE_TRIGGERS
    )
)
RRTV_RAW_NON_AD_SOURCE_TRIGGERS = tuple(RRTV_RAW_SOURCE_TRIGGERS[index] for index in (0, 2, 3, 4, 6, 7, 8))
RRTV_HOME_AD_SOURCE_TRIGGER = "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/v3plus\\/index\\/channel\\?pageNum=1&position=CHANNEL_INDEX/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true"
RRTV_GETALL_AD_SOURCE_TRIGGER = "response if ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/ad\\/getAll/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js\") with enable=rfrfuipk_enable, tag=\"rrtv_json\", timeout=60, requires_body=true"
RRTV_HOME_NATIVE_REWRITE = "response if ${rfrfuipk_enable} == true && ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/v3plus\\/index\\/channel\\?pageNum=1&position=CHANNEL_INDEX/i then response.json.jq(\". as $original | try (.data.sections |= map(if .sectionType == \\\"AD\\\" or .sectionType == \\\"SINGLE_IMAGE\\\" or .sectionType == \\\"SHORT_VIDEO\\\" then null else . end)) catch $original\")"
RRTV_GETALL_NATIVE_REWRITE = "response if ${rfrfuipk_enable} == true && ${url} ~= /^https?:\\/\\/api\\.rr\\.tv\\/ad\\/getAll/i then response.json.jq(\". as $original | try (.data.adList = []) catch $original\")"
RRTV_AD_SOURCE_VARIANTS_TO_NATIVE = {
    RRTV_SOURCE_VARIANT_GROUPS[1]: RRTV_HOME_NATIVE_REWRITE,
    RRTV_SOURCE_VARIANT_GROUPS[5]: RRTV_GETALL_NATIVE_REWRITE,
}

RRTV_NATIVE_REWRITES = (RRTV_HOME_NATIVE_REWRITE, RRTV_GETALL_NATIVE_REWRITE)

def replace_rrtv_json_script_with_native_rewrites(lines):
    """Keep RRTV ad cleanup native while accepting both raw and normalized upstream matchers."""
    source_set = set().union(*RRTV_SOURCE_VARIANT_GROUPS)
    native_set = set(RRTV_NATIVE_REWRITES)
    source_counts = {
        group: sum(line.strip() in group for line in lines)
        for group in RRTV_SOURCE_VARIANT_GROUPS
    }
    native_counts = {rule: sum(line.strip() == rule for line in lines) for rule in native_set}

    for group, count in source_counts.items():
        if count > 1:
            raise ValueError("duplicate RRTV response script trigger variant; refusing ambiguous cleanup")
    for rule, count in native_counts.items():
        if count > 1:
            raise ValueError("duplicate RRTV native rewrite; refusing ambiguous cleanup")

    for group, native in RRTV_AD_SOURCE_VARIANTS_TO_NATIVE.items():
        if source_counts[group] and native_counts[native]:
            raise ValueError("mixed RRTV script/native rule state; refusing ambiguous cleanup")

    section = ""
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        normalized = line.replace("\\", "")
        if section == "Script" and "api.rr.tv" in normalized and (
            "rrtv_json.js" in line
        ) and line.strip() not in source_set:
            raise ValueError("unknown RRTV script matcher; refusing unreviewed cleanup")
        if section == "Rewrite" and "api.rr.tv" in normalized and (
            "/v3plus/index/channel" in normalized or "/ad/getAll" in normalized
        ) and "response.json." in line and line.strip() not in native_set:
            raise ValueError("unknown RRTV native JSON action; refusing unreviewed cleanup")
        if line.strip() in source_set and section != "Script":
            raise ValueError("RRTV source trigger moved outside Script section; refusing cleanup")
        if line.strip() in native_set and section != "Rewrite":
            raise ValueError("RRTV native rewrite moved outside Rewrite section; refusing cleanup")

    to_add = [
        native for group, native in RRTV_AD_SOURCE_VARIANTS_TO_NATIVE.items()
        if source_counts[group] == 1 and native_counts[native] == 0
    ]
    output = []
    section = ""
    inserted = False
    removed = 0
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            if line == "[Script]" and section == "Rewrite":
                output.extend(to_add)
                inserted = True
            section = line[1:-1]
            output.append(line)
            continue
        if section == "Script" and line.strip() in source_set:
            removed += 1
            continue
        output.append(line)

    if to_add and not inserted:
        raise ValueError("RRTV native rewrites could not be placed in an existing Rewrite section")
    return output, removed




SMZDM_RSTORE_HOME_TRIGGER = (
    r"http-response ^https?:\/\/homepage-api\.smzdm\.com\/v\d\/home "
    r"script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/smzdm.js,"
    r"tag=SMZDM-5,requires-body=true"
)
SMZDM_FMZ_HOME_TRIGGER = (
    r"response if ${url} ~= /^https?:\/\/homepage-api\.smzdm\.com\/v3\/home/i "
    r'then script("https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/smzdm/Smzdm.js") '
    r'with enable=smzdm_enable, tag="Smzdm", timeout=60, requires_body=true'
)


def remove_redundant_smzdm_homepage_script_trigger(lines):
    """Remove the duplicate v3 homepage JS dispatch only when the broader R-Store handler is present."""
    output = list(lines)
    normalize = lambda value: re.sub(
        r"enable=\$\{([^}]+)\}",
        r"enable=\1",
        re.sub(r"\\+", "", value.strip()),
    )
    sections = {}
    section = ""
    for line in output:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            continue
        normalized = re.sub(r"\\+", "", stripped)
        if section == "Script" and "homepage-api.smzdm.com" in normalized and "Smzdm.js" in stripped:
            sections.setdefault("fmz_candidates", []).append(stripped)
        if section == "Script" and "homepage-api.smzdm.com" in normalized and "smzdm.js" in stripped:
            sections.setdefault("rstore_candidates", []).append(stripped)

    fmz_candidates = sections.get("fmz_candidates", [])
    rstore_candidates = sections.get("rstore_candidates", [])
    if not fmz_candidates:
        return output, 0
    if len(fmz_candidates) != 1 or normalize(fmz_candidates[0]) != normalize(SMZDM_FMZ_HOME_TRIGGER):
        raise ValueError("SMZDM homepage FMZ trigger inventory changed; refusing duplicate cleanup")
    if not rstore_candidates:
        # Without the broader R-Store handler, preserve the FMZ trigger.
        return output, 0
    if len(rstore_candidates) != 1 or normalize(rstore_candidates[0]) != normalize(SMZDM_RSTORE_HOME_TRIGGER):
        raise ValueError("SMZDM homepage R-Store trigger inventory changed; refusing duplicate cleanup")

    result = []
    section = ""
    removed = 0
    for line in output:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            result.append(line)
            continue
        if section == "Script" and normalize(stripped) == normalize(SMZDM_FMZ_HOME_TRIGGER):
            removed += 1
            continue
        result.append(line)
    if removed != 1:
        raise ValueError("SMZDM homepage duplicate trigger removal count mismatch")
    return result, removed


SMZDM_FMZ_ADS_DUPLICATE_PAIRS = (
    (
        "detail_modul/user_related_modul",
        r"http-response ^https?:\/\/haojia\.m\.smzdm\.com\/detail_modul\/user_related_modul\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/smzdm.js,tag=SMZDM,requires-body=true",
        r'response if ${url} ~= /^https?:\/\/haojia\.m\.smzdm\.com\/detail_modul\/user_related_modul\?/i then script("https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/smzdm/smzdm_ads.js") with enable=smzdm_enable, tag="什么值得买去广告", timeout=60, requires_body=true',
    ),
    (
        "ranking_list/articles",
        r"http-response ^https?:\/\/haojia-api\.smzdm\.com\/(?:home\/list|ranking_list\/articles) script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/smzdm.js,tag=SMZDM-4,requires-body=true",
        r'response if ${url} ~= /^https?:\/\/haojia-api\.smzdm\.com\/ranking_list\/articles\?/i then script("https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/smzdm/smzdm_ads.js") with enable=smzdm_enable, tag="什么值得买去广告", timeout=60, requires_body=true',
    ),
    (
        "filter/tags/hot_tags",
        r"http-response ^https?:\/\/s-api\.smzdm\.com\/sou\/(>?filter\/tags\/hot_tags|list_v\d\?) script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/smzdm.js,tag=SMZDM-8,requires-body=true",
        r'response if ${url} ~= /^https?:\/\/s-api\.smzdm\.com\/sou\/filter\/tags\/hot_tags\?/i then script("https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/smzdm/smzdm_ads.js") with enable=smzdm_enable, tag="什么值得买去广告", timeout=60, requires_body=true',
    ),
)


def remove_redundant_smzdm_ads_script_triggers(lines):
    """Remove only FMZ200 SMZDM triggers whose exact endpoint behavior is already covered by R-Store."""
    output = list(lines)
    normalize = lambda value: re.sub(
        r"enable=\$\{([^}]+)\}",
        r"enable=\1",
        re.sub(r"\\+", "", value.strip()),
    )
    section = ""
    script_lines = []
    for line in output:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
        elif section == "Script":
            script_lines.append(stripped)

    removed_lines = set()
    for path_marker, rstore_expected, fmz_expected in SMZDM_FMZ_ADS_DUPLICATE_PAIRS:
        fmz_candidates = [
            line for line in script_lines
            if "smzdm_ads.js" in line and path_marker in re.sub(r"\\+", "", line)
        ]
        if not fmz_candidates:
            continue
        if len(fmz_candidates) != 1 or normalize(fmz_candidates[0]) != normalize(fmz_expected):
            raise ValueError(
                "SMZDM FMZ ad trigger inventory changed; refusing duplicate cleanup: "
                + repr(fmz_candidates)
            )
        rstore_candidates = [
            line for line in script_lines
            if "/smzdm.js" in line and path_marker in re.sub(r"\\+", "", line)
        ]
        if not rstore_candidates:
            # Do not remove a script unless its same-endpoint R-Store cover exists.
            continue
        if len(rstore_candidates) != 1 or normalize(rstore_candidates[0]) != normalize(rstore_expected):
            raise ValueError(
                "SMZDM R-Store cover trigger inventory changed; refusing duplicate cleanup: "
                + repr(rstore_candidates)
            )
        removed_lines.add(normalize(fmz_expected))

    if not removed_lines:
        return output, 0
    result = []
    section = ""
    removed = 0
    for line in output:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            result.append(line)
            continue
        if section == "Script" and normalize(stripped) in removed_lines:
            removed += 1
            continue
        result.append(line)
    if removed != len(removed_lines):
        raise ValueError("SMZDM FMZ duplicate trigger removal count mismatch")
    return result, removed


WECHAT_APPLET_NATIVE_MIGRATIONS = (
    (
        "wechat-api-dj.mstand.cn",
        "scrm/mini/app/index/info",
        r"http-response ^https?:\/\/wechat-api-dj\.mstand\.cn\/scrm\/mini\/app\/index\/info script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/wechatApplet.js,tag=MSTAND,requires-body=true",
        r'response if ${url} ~= /^https?:\/\/wechat-api-dj\.mstand\.cn\/scrm\/mini\/app\/index\/info/ then response.json.delete(["data.homeNewsAdv.jumpValue", "data.homeDineInAdv", "data.homePickupAdv", "data.nearbyShopInfo", "data.homeEventThemesAdv", "data.eventThemes", "data.homeRootAdv", "data.homeTopAdv", "data.homeDialogAdv", "data.homeBannerAdv", "data.homeCouponAdv", "data.homeCompanyAdv", "data.homeDeliveryAdv"])',
    ),
    (
        "coco-com.e.verystar.net",
        "home/info",
        r"http-response ^https?:\/\/coco-com\.e\.verystar\.net\/v\d\/home\/info script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/wechatApplet.js,tag=COCO,requires-body=true",
        r'response if ${url} ~= /^https?:\/\/coco-com\.e\.verystar\.net\/v\d\/home\/info/ then response.json.delete(["data.top_background_url", "data.bottom_banner_list"])',
    ),
    (
        "htwkop.xiaojukeji.com",
        "api=hm.fa.homeConfig",
        r"http-response ^https?:\/\/htwkop\.xiaojukeji\.com\/gateway\?api=hm\.fa\.homeConfig script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/wechatApplet.js,tag=DIDIQJ,requires-body=true",
        r'response if ${url} ~= /^https?:\/\/htwkop\.xiaojukeji\.com\/gateway\?api=hm\.fa\.homeConfig/ then response.json.delete("data.bannerInfoConfig")',
    ),
    (
        "minifm.maxxipoint.com",
        "banner/list",
        r"http-response ^https?:\/\/minifm\.maxxipoint\.com\/banner\/list script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/wechatApplet.js,tag=FM,requires-body=true",
        r'response if ${url} ~= /^https?:\/\/minifm\.maxxipoint\.com\/banner\/list/ then response.json.delete("data.topBanner")',
    ),
    (
        "mapi.xiaotucc.com",
        "main_page/index/getActivity",
        r"http-response ^https?:\/\/mapi\.xiaotucc\.com\/(mall\/main|\w+\/main_page\/index\/getActivity) script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/wechatApplet.js,tag=XIAOTUCC,requires-body=true",
        (
            r'response if ${url} ~= /^https?:\/\/mapi\.xiaotucc\.com\/mall\/main/ then response.json.delete("data")',
            r'response if ${url} ~= /^https?:\/\/mapi\.xiaotucc\.com\/\w+\/main_page\/index\/getActivity/ then response.json.delete("data.p3")',
        ),
    ),
)


def migrate_wechat_applet_simple_endpoints(lines):
    """Replace five simple WeChat-applet JSON scripts with equivalent native response.json.delete rules."""
    output = list(lines)
    section = ""
    script_lines = []
    rewrite_lines = []
    for line in output:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            continue
        if section == "Script":
            script_lines.append(stripped)
        elif section == "Rewrite":
            rewrite_lines.append(stripped)

    removed = set()
    native_rules = []
    for host_marker, path_marker, trigger, replacement in WECHAT_APPLET_NATIVE_MIGRATIONS:
        candidates = [
            line for line in script_lines
            if "wechatApplet.js" in line
            and host_marker in re.sub(r"\\+", "", line)
            and path_marker in re.sub(r"\\+", "", line)
        ]
        if not candidates:
            continue
        if len(candidates) != 1 or candidates[0] != trigger:
            raise ValueError(
                "WeChat applet trigger inventory changed; refusing native migration: "
                + repr(candidates)
            )
        existing_native = [
            line for line in rewrite_lines
            if line.startswith("response if")
            and host_marker in re.sub(r"\\+", "", line)
            and path_marker in re.sub(r"\\+", "", line)
        ]
        if existing_native:
            raise ValueError(
                "WeChat applet native response rule already exists; refusing duplicate migration: "
                + repr(existing_native)
            )
        removed.add(trigger)
        if isinstance(replacement, tuple):
            native_rules.extend(replacement)
        else:
            native_rules.append(replacement)

    if not removed:
        return output, 0

    result = []
    section = ""
    inserted = False
    removed_count = 0
    for line in output:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            result.append(line)
            if section == "Rewrite" and not inserted:
                result.extend(native_rules)
                inserted = True
            continue
        if section == "Script" and stripped in removed:
            removed_count += 1
            continue
        result.append(line)
    if not inserted or removed_count != len(removed):
        raise ValueError("WeChat applet native migration count or Rewrite section mismatch")
    return result, removed_count


WEIBO_NATIVE_MIGRATIONS = (
    (
        "api.weibo.cn",
        "2/messageflow/notice",
        r"http-response ^https?:\/\/api\.weibo\.cn\/2\/messageflow\/notice\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js,tag=WEIBO-13,requires-body=true",
        r'response if ${url} ~= /^https?:\/\/api\.weibo\.cn\/2\/messageflow\/notice\?/ then response.json.jq("if (.messages | type) == \"array\" then .messages |= map(select((.msg_card.ad_tag // false) != true)) else . end")',
    ),
    (
        "api.weibo.cn",
        "push/active",
        r"http-response ^https?:\/\/api\.weibo\.cn\/2\/(push\/active)\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js,tag=WEIBO,requires-body=true",
        r'response if ${url} ~= /^https?:\/\/api\.weibo\.cn\/2\/push\/active\?/ then response.json.jq("if .feed_redpacket then .feed_redpacket.starttime = \"2208960000\" | .feed_redpacket.interval = \"31536000\" | .feed_redpacket.endtime = \"2209046399\" else . end")',
    ),
    (
        "bootpreload.uve.weibo.com",
        "ad/preload",
        r"http-response ^https?:\/\/bootpreload\.uve\.weibo\.com\/v[12]\/ad\/preload script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js,tag=WEIBO-16,requires-body=true",
        r'response if ${url} ~= /^https?:\/\/bootpreload\.uve\.weibo\.com\/v[12]\/ad\/preload/ then response.json.jq("if (.ads | type) == \"array\" and (.ads | length) > 0 then .ads |= map(.start_time = 3818332800 | .end_time = 3818419199 | .daily_display_cnt = 50 | .display_duration = 0) else . end")',
    ),
    (
        "wbapp.uve.weibo.com",
        "wbapplua/wbpullad.lua",
        r"http-response ^https?:\/\/wbapp\.uve\.weibo\.com\/(preload\/get_ad|wbapplua\/wbpullad\.lua)\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js,tag=WEIBO-18,requires-body=true",
        r'response if ${url} ~= /^https?:\/\/wbapp\.uve\.weibo\.com\/(?:preload\/get_ad|wbapplua\/wbpullad\.lua)\?/ then response.json.jq("if (.cached_ad.ads | type) == \"array\" and (.cached_ad.ads | length) > 0 then .cached_ad.ads |= map(.show_count = 50 | .duration = 0 | .start_date = 3818332800 | .end_date = 3818419199) else . end")',
    ),
    (
        "new.vip.weibo.cn",
        "aj/appicon/list",
        r"http-response ^https?:\/\/new\.vip\.weibo\.cn\/aj\/appicon\/list\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js,tag=WEIBO-19,requires-body=true",
        r'response if ${url} ~= /^https?:\/\/new\.vip\.weibo\.cn\/aj\/appicon\/list\?/ then response.json.jq("if (.data.list | type) == \"array\" and (.data.list | length) > 0 then .data.list |= map(if (.cardType != null and .cardType != false and .cardType != 0 and .cardType != "") then .cardType = 2 else . end) else . end")',
    ),
)


def migrate_weibo_simple_endpoints(lines):
    """Replace five fixed-shape Weibo JSON script branches with native jq response rewrites."""
    output = list(lines)
    section = ""
    script_lines = []
    rewrite_lines = []
    for line in output:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            continue
        if section == "Script":
            script_lines.append(stripped)
        elif section == "Rewrite":
            rewrite_lines.append(stripped)

    removed = set()
    native_rules = []
    for host_marker, path_marker, trigger, replacement in WEIBO_NATIVE_MIGRATIONS:
        candidates = [
            line for line in script_lines
            if "weibo.js" in line
            and host_marker in re.sub(r"\\+", "", line)
            and path_marker in re.sub(r"\\+", "", line)
        ]
        if not candidates:
            continue
        if len(candidates) != 1 or candidates[0] != trigger:
            raise ValueError(
                "Weibo trigger inventory changed; refusing native migration: "
                + repr(candidates)
            )
        existing_native = [
            line for line in rewrite_lines
            if line.startswith("response if")
            and host_marker in re.sub(r"\\+", "", line)
            and path_marker.split("(")[0] in re.sub(r"\\+", "", line)
        ]
        if existing_native:
            raise ValueError(
                "Weibo native response rule already exists; refusing duplicate migration: "
                + repr(existing_native)
            )
        removed.add(trigger)
        native_rules.append(replacement)

    if not removed:
        return output, 0

    result = []
    section = ""
    inserted = False
    removed_count = 0
    for line in output:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            result.append(line)
            if section == "Rewrite" and not inserted:
                result.extend(native_rules)
                inserted = True
            continue
        if section == "Script" and stripped in removed:
            removed_count += 1
            continue
        result.append(line)
    if not inserted or removed_count != len(removed):
        raise ValueError("Weibo native migration count or Rewrite section mismatch")
    return result, removed_count


BILIBILI_FMZ_PROTOBUF_REQUIRED_MARKERS = (
    "dynamic.v2.Dynamic/DynAll",
    "view(unite)?",
    "community.service.dm.v1.DM/DmView",
    "polymer.app.search.v1.Search/SearchAll",
)
BILIBILI_FMZ_MAINLIST_DUPLICATE_BRANCH = r"|main\.community\.reply\.v1\.Reply\/MainList"
BILIBILI_PROTOBUF_DUPLICATE_PAIRS = (
    (
        "DynAll",
        r"http-response ^https?:\/\/(?:app\.bilibili\.com|grpc\.biliapi\.net)\/bilibili\.app\.dynamic\.v\d\.Dynamic\/DynAll script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliProtoA.js,tag=BAICIZHAN,requires-body=true,binary-body-mode=true",
        r"http-response ^https?:\/\/(?:app\.bilibili\.com|grpc\.biliapi\.net)\/bilibili\.app\.dynamic\.v[13-9]\.Dynamic\/DynAll script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliProtoA.js,tag=BAICIZHAN,requires-body=true,binary-body-mode=true",
    ),
    (
        "viewunite",
        r"http-response ^https?:\/\/(?:app\.bilibili\.com|grpc\.biliapi\.net)\/bilibili\.app\.(?:view|viewunite)\.v\d\.View\/View script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliProtoA.js,tag=BAICIZHAN-3,requires-body=true,binary-body-mode=true",
        r"http-response ^https?:\/\/(?:app\.bilibili\.com|grpc\.biliapi\.net)\/bilibili\.app\.(?:view|viewunite)\.v[2-9]\.View\/View script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliProtoA.js,tag=BAICIZHAN-3,requires-body=true,binary-body-mode=true",
    ),
    (
        "DmView",
        r"http-response ^https?:\/\/(?:app\.bilibili\.com|grpc\.biliapi\.net)\/bilibili\.community\.service\.dm\.v\d\.DM\/DmView script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliProtoA.js,tag=BAICIZHAN-4,requires-body=true,binary-body-mode=true",
        r"http-response ^https?:\/\/(?:app\.bilibili\.com|grpc\.biliapi\.net)\/bilibili\.community\.service\.dm\.v[2-9]\.DM\/DmView script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliProtoA.js,tag=BAICIZHAN-4,requires-body=true,binary-body-mode=true",
    ),
    (
        "SearchAll",
        r"http-response ^https?:\/\/(?:app\.bilibili\.com|grpc\.biliapi\.net)\/bilibili\.polymer\.app\.search\.v\d\.Search\/SearchAll script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliProtoA.js,tag=BAICIZHAN-6,requires-body=true,binary-body-mode=true",
        r"http-response ^https?:\/\/(?:app\.bilibili\.com|grpc\.biliapi\.net)\/bilibili\.polymer\.app\.search\.v[2-9]\.Search\/SearchAll script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliProtoA.js,tag=BAICIZHAN-6,requires-body=true,binary-body-mode=true",
    ),
)

# Sparkle does not process MainList. Keep BAICIZHAN-5 full v1-v9 coverage.
BILIBILI_PROTOBUF_NON_DUPLICATE_TRIGGER = (
    r"http-response ^https?:\/\/(?:app\.bilibili\.com|grpc\.biliapi\.net)\/bilibili\.main\.community\.reply\.v\d\.Reply\/MainList "
    r"script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliProtoA.js,tag=BAICIZHAN-5,requires-body=true,binary-body-mode=true"
)
BILIBILI_PROTOBUF_MAINLIST_PREVIOUS_NARROWED_TRIGGER = (
    r"http-response ^https?:\/\/(?:app\.bilibili\.com|grpc\.biliapi\.net)\/bilibili\.main\.community\.reply\.v[2-9]\.Reply\/MainList "
    r"script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliProtoA.js,tag=BAICIZHAN-5,requires-body=true,binary-body-mode=true"
)


def narrow_duplicate_bilibili_protobuf_triggers(lines):
    """Avoid duplicate binary protobuf processing where Sparkle's v1/v2 handler already covers R-Store."""
    output = list(lines)
    section = ""
    script_lines = []
    for line in output:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
        elif section == "Script":
            script_lines.append(stripped)

    fmz_candidates = [
        line for line in script_lines
        if "bilibili.protobuf.response.js" in line and line.startswith("response if")
    ]
    fmz_present = bool(fmz_candidates)
    if fmz_present:
        if len(fmz_candidates) != 1:
            raise ValueError("Bilibili Sparkle protobuf trigger inventory changed; refusing duplicate cleanup")
        normalized_fmz = re.sub(r"\\+", "", fmz_candidates[0])
        if not all(marker in normalized_fmz for marker in BILIBILI_FMZ_PROTOBUF_REQUIRED_MARKERS):
            raise ValueError("Bilibili Sparkle protobuf endpoint coverage changed; refusing duplicate cleanup")
        if (
            "main.community.reply" in normalized_fmz
            and "main.community.reply.v1.Reply/MainList" not in normalized_fmz
        ):
            raise ValueError("Bilibili Sparkle MainList matcher changed; refusing duplicate cleanup")
        if (
            "main.community.reply.v1.Reply/MainList" in normalized_fmz
            and fmz_candidates[0].count(BILIBILI_FMZ_MAINLIST_DUPLICATE_BRANCH) != 1
        ):
            raise ValueError("Bilibili Sparkle MainList escaping changed; refusing duplicate cleanup")

    # Only count the R-Store MainList handler here; Sparkle's MainList branch
    # is checked separately below and may be removed only when R-Store covers it.
    mainlist_candidates = [
        line for line in script_lines
        if "tag=BAICIZHAN-5" in line
        or ("bilibili.main.community.reply" in re.sub(r"\\\\+", "", line)
            and "bilibiliProtoA.js" in line)
    ]
    normalize_mainlist = lambda value: re.sub(r"\\+", "", value)
    if mainlist_candidates and (
        len(mainlist_candidates) != 1
        or normalize_mainlist(mainlist_candidates[0]) not in (
            normalize_mainlist(BILIBILI_PROTOBUF_NON_DUPLICATE_TRIGGER),
            normalize_mainlist(BILIBILI_PROTOBUF_MAINLIST_PREVIOUS_NARROWED_TRIGGER),
        )
    ):
        raise ValueError("Bilibili MainList trigger variant changed; refusing version restoration")

    replacements = {}
    if mainlist_candidates and normalize_mainlist(mainlist_candidates[0]) == normalize_mainlist(BILIBILI_PROTOBUF_MAINLIST_PREVIOUS_NARROWED_TRIGGER):
        replacements[mainlist_candidates[0]] = BILIBILI_PROTOBUF_NON_DUPLICATE_TRIGGER

    # Sparkle's protobuf handler also implements v1.Reply/MainList. The R-Store
    # BAICIZHAN-5 matcher covers v1-v9 on both hosts and appears earlier, so
    # this one Sparkle branch can never be selected. Remove only that exact
    # branch, preserving every other Sparkle endpoint and failing closed on drift.
    if fmz_present and mainlist_candidates:
        fmz_line = fmz_candidates[0]
        branch_count = fmz_line.count(BILIBILI_FMZ_MAINLIST_DUPLICATE_BRANCH)
        if branch_count > 1:
            raise ValueError("Bilibili Sparkle MainList branch duplicated; refusing duplicate cleanup")
        if branch_count == 1:
            replacements[fmz_line] = fmz_line.replace(BILIBILI_FMZ_MAINLIST_DUPLICATE_BRANCH, "", 1)

    for marker, original, narrowed in BILIBILI_PROTOBUF_DUPLICATE_PAIRS:
        candidates = [
            line for line in script_lines
            if "bilibiliProtoA.js" in line and marker in re.sub(r"\\+", "", line)
        ]
        if not candidates:
            continue
        if len(candidates) != 1:
            raise ValueError(
                "Bilibili R-Store protobuf trigger inventory changed; refusing duplicate cleanup: "
                + repr(candidates)
            )
        current = candidates[0]
        if current == original:
            replacements[current] = narrowed if fmz_present else original
        elif current == narrowed:
            replacements[current] = narrowed if fmz_present else original
        else:
            raise ValueError(
                "Bilibili R-Store protobuf trigger variant changed; refusing duplicate cleanup: "
                + current
            )

    if not replacements or all(old == new for old, new in replacements.items()):
        return output, 0

    result = []
    section = ""
    changed = 0
    for line in output:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            result.append(line)
            continue
        if section == "Script" and stripped in replacements:
            result.append(replacements[stripped])
            if replacements[stripped] != stripped:
                changed += 1
        else:
            result.append(line)
    return result, changed


XIMALAYA_SCRIPT_TRIGGER_OLD_HOST_PREFIX = r"^https?:\/\/.*\.xima.*\.com\/"
XIMALAYA_SCRIPT_TRIGGER_NEW_HOST_PREFIX = r"^https?:\/\/(?:[A-Za-z0-9-]+\.)+ximalaya\.com\/"
XIMALAYA_SCRIPT_TRIGGER_TAG_PATHS = {
    "tag=XMLY,": "customCategories",
    "tag=XMLY-2,": "focusPic",
    "tag=XMLY-3,": "/mix ",
    "tag=XMLY-4,": "/category ",
    "tag=XMLY-5,": "homePage",
}


def narrow_ximalaya_script_triggers(lines):
    """Restrict five Ximalaya response scripts to the observed ximalaya.com domain suffix."""
    output = list(lines)
    section = ""
    candidates = []
    for line in output:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
        elif (
            section == "Script"
            and stripped.startswith("http-response ")
            and "Res/Scripts/AntiAd/xmly.js" in stripped
        ):
            candidates.append(stripped)

    if not candidates:
        return output, 0
    if len(candidates) != len(XIMALAYA_SCRIPT_TRIGGER_TAG_PATHS):
        raise ValueError("Ximalaya response trigger inventory changed; refusing host narrowing")

    replacements = {}
    seen_tags = set()
    for line in candidates:
        matching_tags = [tag for tag in XIMALAYA_SCRIPT_TRIGGER_TAG_PATHS if tag in line]
        if len(matching_tags) != 1:
            raise ValueError("Ximalaya response trigger tag changed; refusing host narrowing")
        tag = matching_tags[0]
        if tag in seen_tags or XIMALAYA_SCRIPT_TRIGGER_TAG_PATHS[tag] not in line:
            raise ValueError("Ximalaya response trigger path changed; refusing host narrowing")
        seen_tags.add(tag)

        old_count = line.count(XIMALAYA_SCRIPT_TRIGGER_OLD_HOST_PREFIX)
        new_count = line.count(XIMALAYA_SCRIPT_TRIGGER_NEW_HOST_PREFIX)
        if old_count == 1 and new_count == 0:
            replacements[line] = line.replace(
                XIMALAYA_SCRIPT_TRIGGER_OLD_HOST_PREFIX,
                XIMALAYA_SCRIPT_TRIGGER_NEW_HOST_PREFIX,
                1,
            )
        elif old_count == 0 and new_count == 1:
            continue
        else:
            raise ValueError("Ximalaya response host matcher changed; refusing host narrowing")

    if seen_tags != set(XIMALAYA_SCRIPT_TRIGGER_TAG_PATHS):
        raise ValueError("Ximalaya response trigger coverage changed; refusing host narrowing")
    if not replacements:
        return output, 0

    result = []
    section = ""
    changed = 0
    for line in output:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            result.append(line)
            continue
        if section == "Script" and stripped in replacements:
            result.append(replacements[stripped])
            changed += 1
        else:
            result.append(line)
    return result, changed


BILIBILI_JSON_TRIGGER_PAIRS = (
    (
        "BAICIZHAN-8",
        r"http-response ^https?:\/\/api\.live\.bilibili\.com\/xlive\/app-room\/v\d\/index\/getInfoByRoom\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliJson.js,tag=BAICIZHAN-8,requires-body=true",
        r"http-response ^https?:\/\/api\.live\.bilibili\.com\/xlive\/app-room\/v[2-9]\/index\/getInfoByRoom\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliJson.js,tag=BAICIZHAN-8,requires-body=true",
    ),
    (
        "BAICIZHAN-9",
        r"http-response ^https?:\/\/app\.bilibili\.com\/x\/v\d\/(?:feed\/index(\/story)?|search\/square)\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliJson.js,tag=BAICIZHAN-9,requires-body=true",
        r"http-response ^https?:\/\/app\.bilibili\.com\/x\/v[13-9]\/(?:feed\/index(\/story)?|search\/square)\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliJson.js,tag=BAICIZHAN-9,requires-body=true",
    ),
    (
        "BAICIZHAN-10",
        r"http-response ^https?:\/\/app\.bilibili\.com\/x\/resource\/(?:top\/activity|show\/tab\/v\d)\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliJson.js,tag=BAICIZHAN-10,requires-body=true",
        r"http-response ^https?:\/\/app\.bilibili\.com\/x\/resource\/show\/tab\/v\d\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliJson.js,tag=BAICIZHAN-10,requires-body=true",
    ),
    (
        "BAICIZHAN-11",
        r"http-response ^https?:\/\/app\.bilibili\.com\/x\/v\d\/splash\/(?:brand\/list|event\/list2|list|show)\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliJson.js,tag=BAICIZHAN-11,requires-body=true",
        r"http-response ^https?:\/\/app\.bilibili\.com\/x\/v(?:[13-9]\/splash\/(?:brand\/list|event\/list2|list|show)|2\/splash\/brand\/list)\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliJson.js,tag=BAICIZHAN-11,requires-body=true",
    ),
    (
        "BAICIZHAN-12",
        r"http-response ^https?:\/\/app\.bilibili\.com\/x\/v\d\/account\/(?:mine(\/ipad)?|myinfo)\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliJson.js,tag=BAICIZHAN-12,requires-body=true",
        r"http-response ^https?:\/\/app\.bilibili\.com\/x\/(?:v(?:[13-9]|[1-9][0-9]+)\/account\/mine(\/ipad)?|v2\/account\/mine\/ipad|v\d\/account\/myinfo)\? script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliJson.js,tag=BAICIZHAN-12,requires-body=true",
    ),
)
BILIBILI_LOCAL_JSON_SCRIPT_URL = "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/bilibili/bilibili-json.js"
BILIBILI_RSTORE_JSON_SCRIPT_URL = "https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/bilibiliJson.js"
BILIBILI_LOCAL_JSON_TAGS = tuple(f"BAICIZHAN-{number}" for number in range(7, 14))
BILIBILI_LIVE_FMZ_MARKER = "app-room/v1/index/getInfoBy(Room|User)"
BILIBILI_NATIVE_RULE_REPLACEMENTS = (
    (
        r'response if ${url} ~= /^https:\/\/app\.bilibili\.com\/x\/v2\/feed\/index\?/ then response.json.jq(`if .data.items then .data.items |= map(select((.banner_item == null) and (.ad_info == null) and (.card_goto == "av") and (.card_type | IN("small_cover_v2", "large_cover_single_v9", "large_cover_v1")))) end`)',
        r'response if ${url} ~= /^https:\/\/app\.bilibili\.com\/x\/v2\/feed\/index\?/ then response.json.jq(`if .data.items then .data.items |= map(select((.banner_item == null) and (.ad_info == null) and (.card_goto == "av") and (.card_type | IN("small_cover_v2", "large_cover_single_v9", "large_cover_v1")))) else . end | if (.data.config.toast.has_toast? // false) then .data.config.toast.has_toast = false else . end`)',
    ),
    (
        r'response if ${url} ~= /^https:\/\/app\.bilibili\.com\/x\/v2\/feed\/index\/story\?/ then response.json.jq(`if .data.items then .data.items |= map(select((.ad_info == null) and (.card_goto | IN("vertical_ad_av", "vertical_ad_live", "vertical_ad_picture") | not)) | del(.story_cart_icon, .free_flow_toast, .image_infos, .course_info, .game_info)) end`)',
        r'response if ${url} ~= /^https:\/\/app\.bilibili\.com\/x\/v2\/feed\/index\/story\?/ then response.json.jq(`if .data.items then .data.items |= map(select((has("ad_info") | not) and (.card_goto | IN("vertical_ad_av", "vertical_live", "vertical_pgc", "vertical_ad_live", "vertical_ad_picture") | not)) | del(.creative_entrance, .story_cart_icon, .free_flow_toast, .image_infos, .course_info, .game_info)) else . end`)',
    ),
    (
        r'response if ${url} ~= /^https:\/\/app\.bilibili\.com\/x\/v2\/splash\/(show|event\/list2)\?/ then response.json.jq(`.data |= with_entries(if .key | IN("show", "event_list") then .value = [] else . end)`)',
        r'response if ${url} ~= /^https:\/\/app\.bilibili\.com\/x\/v2\/splash\/(show|event\/list2)\?/ then response.json.jq(`if (.data | type) == "object" then .data |= (del(.account, .event_list, .preload, .show) | if (.max_time != null and .max_time != false and .max_time != 0 and .max_time != "") then .max_time = 0 else . end | if (.min_interval != null and .min_interval != false and .min_interval != 0 and .min_interval != "") then .min_interval = 31536000 else . end | if (.pull_interval != null and .pull_interval != false and .pull_interval != 0 and .pull_interval != "") then .pull_interval = 31536000 else . end | if (.list | type) == "array" and (.list | length) > 0 then .list |= map(.duration = 0 | .enable_pre_download = false | .begin_time = 3818332800 | .end_time = 3818419199) else . end) else . end`)',
    ),
)
BILIBILI_NATIVE_PREREQUISITE_MARKERS = (
    r"response if ${url} ~= /^https:\/\/ap[ip]\.bilibili\.com\/x\/(resource\/(top\/activity|patch\/tab(\/v2)?)|v2\/search\/square|vip\/ads\/materials)\?/ then response.body.mock",
)


def optimize_bilibili_json_native_coverage(lines):
    """Narrow R-Store JSON triggers where existing native/Sparkle handlers cover the same current endpoints.

    Sparkle's native JQ owns v2/account/mine (including ipad); keep R-Store's
    BAICIZHAN-12 only for other account/mine API versions and account/myinfo.
    This removes the duplicate v2 parse without dropping R-Store's version
    fallback or the distinct myinfo VIP handler.
    """
    output = list(lines)
    section = ""
    script_lines = []
    rewrite_lines = []
    for line in output:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            continue
        if section == "Script":
            script_lines.append(stripped)
        elif section == "Rewrite":
            rewrite_lines.append(stripped)

    rstore_json_lines = [
        line for line in script_lines if "bilibiliJson.js" in line
    ]
    if not rstore_json_lines:
        return output, 0

    expected_json_tags = {f"BAICIZHAN-{number}" for number in range(7, 14)}
    actual_json_tags = [
        match.group(1) if (match := re.search(r"tag=(BAICIZHAN-\d+)", line)) else None
        for line in rstore_json_lines
    ]
    if (
        len(rstore_json_lines) != len(expected_json_tags)
        or set(actual_json_tags) != expected_json_tags
        or len(set(actual_json_tags)) != len(expected_json_tags)
    ):
        raise ValueError(
            "Bilibili R-Store JSON trigger inventory changed; refusing partial narrowing: "
            + repr(actual_json_tags)
        )

    fmz_live = [
        line for line in script_lines
        if "bilibili.json.js" in line and line.startswith("response if")
        and "api.live.bilibili.com" in re.sub(r"\\+", "", line)
    ]
    if len(fmz_live) != 1 or BILIBILI_LIVE_FMZ_MARKER not in re.sub(r"\\+", "", fmz_live[0]):
        raise ValueError("Bilibili live JSON native coverage changed; refusing duplicate trigger narrowing")

    for marker in BILIBILI_NATIVE_PREREQUISITE_MARKERS:
        if not any(marker in line for line in rewrite_lines):
            raise ValueError("Bilibili native response prerequisite missing; refusing trigger narrowing: " + marker)

    trigger_replacements = {}
    for tag, original, narrowed in BILIBILI_JSON_TRIGGER_PAIRS:
        candidates = [
            line for line in script_lines
            if "bilibiliJson.js" in line and "tag=" + tag in line
        ]
        if len(candidates) != 1:
            raise ValueError(
                "Bilibili R-Store JSON trigger inventory changed; refusing narrowing: "
                + repr(candidates)
            )
        current = candidates[0]
        if current == original or current == narrowed:
            trigger_replacements[current] = narrowed
        else:
            raise ValueError("Bilibili R-Store JSON trigger variant changed: " + current)

    native_replacements = {}
    for original, updated in BILIBILI_NATIVE_RULE_REPLACEMENTS:
        if original in rewrite_lines:
            if rewrite_lines.count(original) != 1:
                raise ValueError("duplicate Bilibili native response rule: " + original)
            native_replacements[original] = updated
        elif updated in rewrite_lines:
            if rewrite_lines.count(updated) != 1:
                raise ValueError("duplicate optimized Bilibili native response rule: " + updated)
        else:
            raise ValueError("Bilibili native response rule changed; refusing trigger narrowing: " + original)

    result = []
    section = ""
    for line in output:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            result.append(line)
            continue
        if section == "Script" and stripped in trigger_replacements:
            result.append(trigger_replacements[stripped])
        elif section == "Rewrite" and stripped in native_replacements:
            result.append(native_replacements[stripped])
        else:
            result.append(line)
    changed = sum(1 for old, new in trigger_replacements.items() if old != new)
    changed += sum(1 for old, new in native_replacements.items() if old != new)
    return result, changed



def migrate_bilibili_json_script_to_local(lines):
    """Serve the reviewed Bilibili JSON cleaner locally and keep all seven endpoint tags."""
    output = list(lines)
    section = ""
    candidates = {}
    for line in output:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            continue
        if section != "Script" or "bilibiliJson.js" not in stripped and BILIBILI_LOCAL_JSON_SCRIPT_URL not in stripped:
            continue
        tags = [tag for tag in BILIBILI_LOCAL_JSON_TAGS if "tag=" + tag in stripped]
        if len(tags) != 1:
            raise ValueError("Bilibili local JSON trigger tag changed; refusing migration: " + stripped)
        tag = tags[0]
        if tag in candidates:
            raise ValueError("duplicate Bilibili JSON trigger tag; refusing migration: " + tag)
        if "http-response " not in stripped or "requires-body=true" not in stripped:
            raise ValueError("Bilibili JSON trigger mode changed; refusing migration: " + stripped)
        if BILIBILI_LOCAL_JSON_SCRIPT_URL in stripped:
            candidates[tag] = stripped
        elif BILIBILI_RSTORE_JSON_SCRIPT_URL in stripped:
            candidates[tag] = stripped
        else:
            raise ValueError("Bilibili JSON script source changed; refusing migration: " + stripped)

    if not candidates:
        return output, 0
    if set(candidates) != set(BILIBILI_LOCAL_JSON_TAGS):
        raise ValueError("Bilibili JSON trigger inventory changed; refusing partial local migration: " + repr(sorted(candidates)))

    replacements = {
        line: line.replace(BILIBILI_RSTORE_JSON_SCRIPT_URL, BILIBILI_LOCAL_JSON_SCRIPT_URL)
        for line in candidates.values()
    }
    result = []
    section = ""
    changed = 0
    for line in output:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            result.append(line)
        elif section == "Script" and stripped in replacements:
            updated = replacements[stripped]
            result.append(updated)
            changed += updated != stripped
        else:
            result.append(line)
    return result, changed



GOOFISH_HOME_SECTIONS_OLD_RULE = r'''response if ${url} ~= /^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idlehome\.home\.nextfresh\//i then response.json.jq(".data.homeTopList |= map(select(.sectionType == \"kingkongDo\")) | .data.sections |= map(select(.data.clickParam.args.cardType as $ct | $ct != \"homeMultiBanner\" and $ct != \"mamaAD\")) | .data.sections |= map(select((.template.name|type==\"string\")and(.template.name==\"idlefish_home_new_commodity_card\"or(.template.name|contains(\"fish_home_tags_item_card\")))))")'''
GOOFISH_HOME_SECTIONS_NATIVE_RULE = r'''response if ${url} ~= /^https:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idlehome\.home\.nextfresh\//i then response.json.jq(".data.homeTopList |= map(select(.sectionType == \"kingkongDo\")) | .data.sections |= map(select((.data.clickParam.args.cardType as $ct | $ct != \"homeMultiBanner\" and $ct != \"mamaAD\") and ((.template.name|type)==\"string\") and (.template.name==\"idlefish_home_new_commodity_card\" or (.template.name|contains(\"fish_home_tags_item_card\")))))")'''


def optimize_goofish_home_sections_filter(lines):
    """Combine the two reviewed Goofish home sections filters into one map pass."""
    output, section, found, changed = [], "", 0, 0
    old_normalized = re.sub(r"\\+", "", GOOFISH_HOME_SECTIONS_OLD_RULE.strip())
    new_normalized = re.sub(r"\\+", "", GOOFISH_HOME_SECTIONS_NATIVE_RULE.strip())
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            output.append(line)
            continue
        normalized = re.sub(r"\\+", "", stripped)
        if "idlehome.home.nextfresh" not in normalized or ".data.sections" not in normalized:
            output.append(line)
            continue
        if section != "Rewrite" or "response.json.jq" not in normalized:
            raise ValueError("Goofish home sections response rule moved or changed; refusing an unreviewed override")
        found += 1
        if found > 1:
            raise ValueError("duplicate Goofish home sections response rules")
        if normalized == old_normalized:
            output.append(GOOFISH_HOME_SECTIONS_NATIVE_RULE)
            changed += 1
        elif normalized == new_normalized:
            output.append(line)
        else:
            raise ValueError("Goofish home sections jq rule changed; refusing an unreviewed optimization")
    return output, changed



def apply(text: str) -> str:
    if "[Script]" not in text or "[MITM]" not in text or "[Rewrite]" not in text:
        raise ValueError("plugin missing [Rewrite], [Script] or [MITM] section")

    lines = []
    section = ""
    for line in text.splitlines():
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            lines.append(line)
            continue

        if LEGACY_HELLOBIKE_MARKER in line:
            continue
        normalized_line = re.sub(r"\\+", "", line)
        if section == "Rewrite" and any(marker in normalized_line for marker in HELLOBIKE_REWRITE_MARKERS):
            continue
        if section == "Script" and any(marker in line for marker in HELLOBIKE_SCRIPT_MARKERS):
            continue
        if line.startswith("#!sources="):
            sources = [item for item in line[len("#!sources="):].split("+")
                       if item != HELLOBIKE_SOURCE]
            line = "#!sources=" + "+".join(sources)
        if section == "Rule" and PDD_HTTPDNS_MARKER in line and "URL-REGEX" in line:
            if PDD_HTTPDNS_IPV6_MARKER in line:
                # IPv6 HTTPDNS already had its own query boundary. Repair the
                # accidental suffix introduced by the prior broad IPv4 match.
                if PDD_HTTPDNS_IPV6_PREVIOUS_BAD_SUFFIX in line:
                    line = line.replace(PDD_HTTPDNS_IPV6_PREVIOUS_BAD_SUFFIX, PDD_HTTPDNS_IPV6_SUFFIX)
                elif PDD_HTTPDNS_IPV6_SUFFIX not in line:
                    raise ValueError("拼多多 IPv6 HTTPDNS matcher changed; refusing an unreviewed rewrite")
            elif PDD_HTTPDNS_IPV4_MARKER in line:
                if PDD_HTTPDNS_NEW_SUFFIX in line:
                    pass
                elif PDD_HTTPDNS_OLD_SUFFIX in line:
                    line = line.replace(PDD_HTTPDNS_OLD_SUFFIX, PDD_HTTPDNS_NEW_SUFFIX)
                else:
                    raise ValueError("拼多多 IPv4 HTTPDNS matcher changed; refusing an unreviewed rewrite")
            else:
                raise ValueError("拼多多 HTTPDNS address-family matcher changed; refusing an unreviewed rewrite")
        if section == "MITM" and line.strip().lower().startswith("hostname") and "=" in line:
            key, value = line.split("=", 1)
            hosts = [host.strip() for host in value.split(",") if host.strip()]
            # This local script is retained independently of the removed MyBlockAds feed.
            # Restore only its four exact HTTPS hosts instead of relying on an upstream feed.
            hosts.extend(sorted(REQUIRED_BANKCOMM_MITM_HOSTS - set(hosts)))
            # Defer legacy HelloBike host removal until all surviving Rewrite/Script
            # references are known. Some hosts are also used by unrelated base rules.
            line = key + "= " + ", ".join(hosts)
        lines.append(line)

    lines, _ = scope_taobao_ossgw_ad_assets(lines)
    lines, _ = remove_redundant_jd_keyword_rules(lines)
    lines, _ = remove_jd_core_service_domain_blocks(lines)
    lines, _ = scope_pdd_image_cdn_ad_rules(lines)
    lines, _ = remove_douyin_tnc_conflicting_rejects(lines)
    lines, _ = remove_douyin_content_cdn_overblocks(lines)
    lines, _ = remove_douyin_non_ad_service_host_blocks(lines)
    lines, _ = remove_bilibili_core_service_overblocks(lines)
    lines, _ = normalize_bilibili_non_ad_feature_overrides(lines)
    lines, _ = remove_douyin_hongguo_unsafe_rules(lines)
    lines, _ = remove_kugou_jin10_redundant_rewrites(lines)
    lines, _ = remove_pdd_order_endpoint_blocks(lines)

    # Preserve a legacy-listed MITM host whenever a non-HelloBike Rewrite or
    # Script trigger still references it. Normalize regex escaping before lookup.
    surviving_sections = []
    active_section = ""
    for candidate in lines:
        if candidate.startswith("[") and candidate.endswith("]"):
            active_section = candidate[1:-1]
        elif active_section in ("Rewrite", "Script"):
            surviving_sections.append(candidate)
    surviving_text = re.sub(r"\\+", "", "\n".join(surviving_sections))
    active_shared_hosts = {
        host for host in HELLOBIKE_ADDED_MITM_HOSTS if host in surviving_text
    }
    normalized_lines = []
    active_section = ""
    for candidate in lines:
        if candidate.startswith("[") and candidate.endswith("]"):
            active_section = candidate[1:-1]
        if active_section == "MITM" and candidate.strip().lower().startswith("hostname") and "=" in candidate:
            key, value = candidate.split("=", 1)
            hosts = [host.strip() for host in value.split(",") if host.strip()]
            hosts = [host for host in hosts
                     if host not in HELLOBIKE_ADDED_MITM_HOSTS or host in active_shared_hosts]
            candidate = key + "= " + ", ".join(hosts)
        normalized_lines.append(candidate)
    lines = normalized_lines
    lines, _ = replace_rrtv_json_script_with_native_rewrites(lines)
    lines, _ = consolidate_wechat_unblock_url_scripts(lines)
    lines, _ = consolidate_pdd_homepage_script(lines)
    lines, _ = remove_redundant_pdd_oak_script_trigger(lines)
    lines, guiderank_homepage_script_count = remove_guiderank_homepage_script(lines)
    lines, gaoding_converted_triggers = remove_gaoding_resource_scripts(lines)
    lines, _ = remove_redundant_taobao_scripts(lines)
    lines, _ = migrate_taobao_script_to_local(lines)
    lines, _ = remove_redundant_didi_usercenter_script(lines)
    lines, _ = consolidate_goofish_script_triggers(lines)
    lines, _ = optimize_goofish_home_sections_filter(lines)
    lines, _ = consolidate_jingdong_scripts(lines)
    lines, _ = consolidate_meituan_scripts(lines)
    lines, _ = remove_duplicate_tuhu_scripts(lines)
    lines, _ = remove_duplicate_cnftp_scripts(lines)
    lines, _ = consolidate_cnftp_iqiyi_home_triggers(lines)
    lines, _ = remove_cnftp_non_ad_triggers(lines)
    lines, _ = remove_dushu365_non_ad_triggers(lines)
    lines, _ = remove_same_source_duplicate_response_scripts(lines)
    lines, _ = remove_identical_script_response_duplicates(lines)
    lines, _ = consolidate_soul_scripts(lines)
    lines, _ = remove_more_duplicate_response_scripts(lines)
    lines, _ = remove_redundant_pupu_response_scripts(lines)
    lines, _ = migrate_pupu_response_script_to_local(lines)
    lines, _ = remove_redundant_alipan_onboard_response_script(lines)
    lines, _ = remove_unneeded_mgw_ecny_response_body_read(lines)
    lines, _ = remove_unneeded_usmile_response_body_read(lines)
    lines, _ = remove_unneeded_header_only_response_body_reads(lines)
    lines, _ = remove_shadowed_amdc_response_trigger(lines)
    lines, _ = remove_shadowed_cross_syntax_response_triggers(lines)
    lines, _ = optimize_maasea_youtube_shadowed_triggers(lines)
    lines, _ = remove_weibo_non_ad_response_triggers(lines)
    lines, _ = remove_redundant_dianping_scripts(lines)
    lines, _ = remove_redundant_baidumap_script(lines)
    lines, _ = migrate_baidumap_script_to_local(lines)
    lines, _ = remove_redundant_amap_legacy_scripts(lines)
    lines, _ = optimize_amap_response_script_overlaps(lines)
    lines, _ = remove_shadowed_ishowshu_amap_response_triggers(lines)
    lines, _ = consolidate_zhihu_response_scripts(lines)
    lines, _ = narrow_xiaohongshu_native_response_duplicates(lines)
    lines, _ = narrow_xiaohongshu_v3_video_native_duplicates(lines)
    lines, _ = migrate_xiaohongshu_v4_and_comment_processing(lines)
    lines, _ = remove_redundant_smzdm_homepage_script_trigger(lines)
    lines, _ = remove_redundant_smzdm_ads_script_triggers(lines)
    lines, _ = migrate_wechat_applet_simple_endpoints(lines)
    lines, _ = migrate_weibo_simple_endpoints(lines)
    lines, _ = narrow_ximalaya_script_triggers(lines)
    lines, _ = narrow_duplicate_bilibili_protobuf_triggers(lines)
    lines, _ = optimize_bilibili_json_native_coverage(lines)
    lines, _ = migrate_bilibili_json_script_to_local(lines)

    result_lines, rewrite_lines = [], []
    section = ""
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            if section == "Rewrite":
                rewrite_lines, _ = remove_duplicate_pdd_homepage_delete_path(rewrite_lines)
                rewrite_lines, _ = consolidate_pdd_splash_rules(rewrite_lines)
                rewrite_lines, _ = remove_redundant_pdd_feed_asset_rules(rewrite_lines)
                rewrite_lines, _ = remove_redundant_dache_core_icon_filter(rewrite_lines)
                rewrite_lines, _ = merge_didi_fast_homepage_json_deletes(rewrite_lines)
                rewrite_lines, _ = remove_didi_homepage_rejects_shadowing_field_cleaners(rewrite_lines)
                rewrite_lines, _ = consolidate_ximalaya_homepage_json_rewrites(rewrite_lines)
                rewrite_lines, _ = batch_same_response_json_deletes(rewrite_lines)
                rewrite_lines, _ = merge_adjacent_response_json_rewrites(rewrite_lines)
                rewrite_lines, _ = consolidate_starplucker_config_jq(rewrite_lines)
                rewrite_lines, _ = remove_redundant_zhihu_request_rules(rewrite_lines)
                rewrite_lines, _ = consolidate_zhihu_multi_action_rewrites(rewrite_lines)
                rewrite_lines, _ = remove_subsumed_soul_teenager_rule(rewrite_lines)
                rewrite_lines, _ = remove_duplicate_peopleapp_home_ad_rules(rewrite_lines)
                rewrite_lines, _ = remove_shadowed_peopleapp_rules(rewrite_lines)
                rewrite_lines, _ = remove_shadowed_terminal_block_rules(rewrite_lines)
                rewrite_lines, _ = remove_redundant_taobao_rewrite_rules(rewrite_lines)
                rewrite_lines, _ = remove_redundant_xianyu_rewrite_rules(rewrite_lines)
                rewrite_lines, _ = remove_lkcoffee_member_exchange_success_overrides(rewrite_lines)
                rewrite_lines, _ = replace_guiderank_special_sale_random_body(rewrite_lines)
                rewrite_lines, _ = replace_ddqx_newdetails_body_rewrites(rewrite_lines)
                if guiderank_homepage_script_count and GUIDERANK_HOMEPAGE_NATIVE_RULE not in [item.strip() for item in rewrite_lines]:
                    rewrite_lines.append(GUIDERANK_HOMEPAGE_NATIVE_RULE)
                existing_rewrites = {item.strip() for item in rewrite_lines}
                rewrite_lines.extend(rule for rule in GAODING_NATIVE_RULES if rule not in existing_rewrites and ((rule == GAODING_NATIVE_RULES[0] and GAODING_TEMPLATE_SCRIPT_TRIGGER in gaoding_converted_triggers) or (rule == GAODING_NATIVE_RULES[1] and GAODING_MINE_SCRIPT_TRIGGER in gaoding_converted_triggers)))
                result_lines.extend(rewrite_lines); rewrite_lines = []
            section = line[1:-1]; result_lines.append(line)
        elif section == "Rewrite": rewrite_lines.append(line)
        else: result_lines.append(line)
    if section == "Rewrite":
        rewrite_lines, _ = remove_duplicate_pdd_homepage_delete_path(rewrite_lines)
        rewrite_lines, _ = consolidate_pdd_splash_rules(rewrite_lines)
        rewrite_lines, _ = remove_redundant_pdd_feed_asset_rules(rewrite_lines)
        rewrite_lines, _ = remove_redundant_dache_core_icon_filter(rewrite_lines)
        rewrite_lines, _ = merge_didi_fast_homepage_json_deletes(rewrite_lines)
        rewrite_lines, _ = remove_didi_homepage_rejects_shadowing_field_cleaners(rewrite_lines)
        rewrite_lines, _ = consolidate_ximalaya_homepage_json_rewrites(rewrite_lines)
        rewrite_lines, _ = batch_same_response_json_deletes(rewrite_lines)
        rewrite_lines, _ = merge_adjacent_response_json_rewrites(rewrite_lines)
        rewrite_lines, _ = consolidate_starplucker_config_jq(rewrite_lines)
        rewrite_lines, _ = remove_redundant_zhihu_request_rules(rewrite_lines)
        rewrite_lines, _ = consolidate_zhihu_multi_action_rewrites(rewrite_lines)
        rewrite_lines, _ = remove_subsumed_soul_teenager_rule(rewrite_lines)
        rewrite_lines, _ = remove_duplicate_peopleapp_home_ad_rules(rewrite_lines)
        rewrite_lines, _ = remove_shadowed_peopleapp_rules(rewrite_lines)
        rewrite_lines, _ = remove_shadowed_terminal_block_rules(rewrite_lines)
        rewrite_lines, _ = remove_redundant_taobao_rewrite_rules(rewrite_lines)
        rewrite_lines, _ = remove_redundant_xianyu_rewrite_rules(rewrite_lines)
        rewrite_lines, _ = remove_lkcoffee_member_exchange_success_overrides(rewrite_lines)
        rewrite_lines, _ = replace_guiderank_special_sale_random_body(rewrite_lines)
        rewrite_lines, _ = replace_ddqx_newdetails_body_rewrites(rewrite_lines)
        if guiderank_homepage_script_count and GUIDERANK_HOMEPAGE_NATIVE_RULE not in [item.strip() for item in rewrite_lines]:
            rewrite_lines.append(GUIDERANK_HOMEPAGE_NATIVE_RULE)
        existing_rewrites = {item.strip() for item in rewrite_lines}
        rewrite_lines.extend(rule for rule in GAODING_NATIVE_RULES if rule not in existing_rewrites and ((rule == GAODING_NATIVE_RULES[0] and GAODING_TEMPLATE_SCRIPT_TRIGGER in gaoding_converted_triggers) or (rule == GAODING_NATIVE_RULES[1] and GAODING_MINE_SCRIPT_TRIGGER in gaoding_converted_triggers)))
        result_lines.extend(rewrite_lines)
    result_lines, _ = consolidate_pdd_homepage_native_response(result_lines)
    result_lines, _ = narrow_pdd_philo_hub_response_rules(result_lines)
    result_lines, _ = apply_didi_script_and_homepage_cleanup(result_lines)
    result_lines, _ = migrate_didiads_common_v5_to_local(result_lines)
    result = "\n".join(result_lines)
    # Scope YYting to the two confirmed hosts. Upstream and generated plugin
    # text may encode URL slashes with one or multiple backslashes; normalize
    # only slash escapes before comparing so the override matches real artifacts.
    def normalize_url_slash_escapes(value):
        return re.sub(r"\\+/", lambda _match: r"\/", value.strip())

    broad_yyting = r"request if ${url} ~= /^https?:\/\/.*\/yyting\/advertclient\/ClientAdvertList.action/ then reject(404)"
    scoped_yyting = [
        r"request if ${url} ~= /^https?:\/\/118\.178\.214\.118\/yyting\/advertclient\/ClientAdvertList\.action/ then reject(404)",
        r"request if ${url} ~= /^https?:\/\/dapis\.mting\.info\/yyting\/advertclient\/ClientAdvertList\.action/ then reject(404)",
    ]
    normalized_broad_yyting = normalize_url_slash_escapes(broad_yyting)
    result_lines = []
    section = ""
    for candidate in result.splitlines():
        if candidate.startswith("[") and candidate.endswith("]"):
            section = candidate[1:-1]
            result_lines.append(candidate)
        elif (section == "Rewrite"
              and normalize_url_slash_escapes(candidate) == normalized_broad_yyting):
            result_lines.extend(scoped_yyting)
        else:
            result_lines.append(candidate)
    result = "\n".join(result_lines)
    # Keep the unrelated Bankcomm override in [Script], idempotently.
    if RULE not in result:
        pos = result.index("[MITM]")
        result = result[:pos].rstrip() + "\n" + RULE + "\n\n" + result[pos:]
    return result + ("\n" if text.endswith("\n") and not result.endswith("\n") else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plugin", required=True)
    args = ap.parse_args()
    path = Path(args.plugin)
    path.write_text(apply(path.read_text(encoding="utf-8")), encoding="utf-8")
    print("已应用买单吧覆盖规则；已移除 PR #129 引入的哈啰整合规则")


if __name__ == "__main__":
    main()
