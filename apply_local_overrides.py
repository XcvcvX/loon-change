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
PDD_ISHOWSHU_HOMEPAGE_TRIGGER = r"http-response ^https:\/\/api\.pinduoduo\.com\/api\/alexa\/homepage\/hub script-path = https://github.com/ishowshu/qx/raw/refs/heads/main/script/pdd.js, requires-body = true, tag = 拼多多首页简化(底部菜单、顶部分类)"


def consolidate_pdd_homepage_script(lines):
    """Replace two overlapping PDD homepage scripts with one behavior-preserving local handler."""
    output, section = [], ""
    counts = {"rstore": 0, "local": 0, "ishowshu": 0}
    normalized_triggers = {
        re.sub(r"\\+", "", PDD_RSTORE_HOMEPAGE_TRIGGER.strip()): "rstore",
        re.sub(r"\\+", "", PDD_LOCAL_HOMEPAGE_TRIGGER.strip()): "local",
        re.sub(r"\\+", "", PDD_ISHOWSHU_HOMEPAGE_TRIGGER.strip()): "ishowshu",
    }
    target_seen = False
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue
        normalized = re.sub(r"\\+", "", line.strip())
        is_target = section == "Script" and "api.pinduoduo.com/api/alexa/" in normalized
        if not is_target:
            output.append(line)
            continue
        target_seen = True
        kind = normalized_triggers.get(normalized)
        if kind is None:
            raise ValueError("Pinduoduo homepage script trigger changed; refusing unreviewed consolidation")
        counts[kind] += 1
        if counts[kind] > 1:
            raise ValueError("duplicate Pinduoduo homepage script trigger; refusing ambiguous consolidation")
        if kind == "ishowshu":
            continue
        if kind == "rstore":
            output.append(PDD_LOCAL_HOMEPAGE_TRIGGER)
        else:
            output.append(line)

    if not target_seen:
        return output, 0
    if counts["rstore"] + counts["local"] != 1:
        raise ValueError("Pinduoduo canonical homepage script inventory changed; expected exactly one R-Store/local trigger")
    return output, counts["ishowshu"] + counts["rstore"]


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
    if old_count + canonical_count != 1 or duplicate_count > 1 or any(count > 1 for count in distinct_counts):
        raise ValueError("Pinduoduo splash rule inventory changed or duplicated; refusing consolidation")
    if len(target) != known:
        raise ValueError("unknown Pinduoduo splash matcher found; refusing unreviewed consolidation")
    if canonical_count == 1 and duplicate_count == 0 and known == 3:
        return list(lines), 0
    if not all(distinct_counts):
        raise ValueError("Pinduoduo splash distinct action inventory missing; refusing consolidation")
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


def remove_redundant_taobao_scripts(lines):
    """Keep the two canonical R-Store Taobao triggers and remove eight equivalent duplicates."""
    canonical = {re.sub(r"\\+", "", item.strip()): item for item in TAOBAO_CANONICAL_SCRIPT_TRIGGERS}
    redundant = {re.sub(r"\\+", "", item.strip()): item for item in TAOBAO_REDUNDANT_SCRIPT_TRIGGERS}
    counts = {item: 0 for item in (*TAOBAO_CANONICAL_SCRIPT_TRIGGERS, *TAOBAO_REDUNDANT_SCRIPT_TRIGGERS)}
    output, section, target_seen = [], "", False
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue
        normalized = re.sub(r"\\+", "", line.strip())
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
            output.append(line)
            continue
        if normalized in redundant:
            trigger = redundant[normalized]
            counts[trigger] += 1
            if counts[trigger] > 1:
                raise ValueError("duplicate redundant Taobao script trigger; refusing ambiguous deduplication")
            continue
        raise ValueError("Taobao splash script trigger changed; refusing an unreviewed deduplication")
    if not target_seen:
        return output, 0
    canonical_complete = all(counts[trigger] == 1 for trigger in TAOBAO_CANONICAL_SCRIPT_TRIGGERS)
    redundant_absent = all(counts[trigger] == 0 for trigger in TAOBAO_REDUNDANT_SCRIPT_TRIGGERS)
    if canonical_complete and redundant_absent:
        return output, 0
    missing = [trigger for trigger, count in counts.items() if count != 1]
    if missing:
        raise ValueError("Taobao splash script trigger inventory changed; expected each reviewed trigger exactly once")
    return output, len(TAOBAO_REDUNDANT_SCRIPT_TRIGGERS)





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
)


def consolidate_goofish_script_triggers(lines):
    """Replace all audited Xianyu script triggers with one local trigger per endpoint."""
    normalize = lambda value: re.sub(r"\\+", "", value.strip())
    canonical = {normalize(item): item for item in GOOFISH_CANONICAL_SCRIPT_TRIGGERS}
    redundant = {normalize(item): item for item in GOOFISH_REDUNDANT_SCRIPT_TRIGGERS}
    counts = {item: 0 for item in (*GOOFISH_CANONICAL_SCRIPT_TRIGGERS, *GOOFISH_REDUNDANT_SCRIPT_TRIGGERS)}
    output, section, target_seen = [], "", False
    insert_canonical = False
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            if section == "Script" and insert_canonical:
                output.extend(GOOFISH_CANONICAL_SCRIPT_TRIGGERS)
                insert_canonical = False
            section = line[1:-1]
            output.append(line)
            continue
        normalized = normalize(line)
        is_target = section == "Script" and "goofish.com" in normalized and (
            "goofish.js" in normalized or "script(" in normalized
        )
        if not is_target:
            output.append(line)
            continue
        target_seen = True
        if normalized in canonical:
            trigger = canonical[normalized]
            counts[trigger] += 1
            if counts[trigger] > 1:
                raise ValueError("duplicate canonical Goofish script trigger")
            output.append(line)
            continue
        if normalized in redundant:
            trigger = redundant[normalized]
            counts[trigger] += 1
            if counts[trigger] > 1:
                raise ValueError("duplicate redundant Goofish script trigger")
            insert_canonical = True
            continue
        raise ValueError("Goofish script trigger inventory changed; refusing unreviewed consolidation")

    if section == "Script" and insert_canonical:
        output.extend(GOOFISH_CANONICAL_SCRIPT_TRIGGERS)
    if not target_seen:
        return output, 0
    canonical_complete = all(counts[item] == 1 for item in GOOFISH_CANONICAL_SCRIPT_TRIGGERS)
    redundant_absent = all(counts[item] == 0 for item in GOOFISH_REDUNDANT_SCRIPT_TRIGGERS)
    if canonical_complete and redundant_absent:
        return output, 0
    redundant_complete = all(counts[item] == 1 for item in GOOFISH_REDUNDANT_SCRIPT_TRIGGERS)
    canonical_absent = all(counts[item] == 0 for item in GOOFISH_CANONICAL_SCRIPT_TRIGGERS)
    if redundant_complete and canonical_absent:
        return output, len(GOOFISH_REDUNDANT_SCRIPT_TRIGGERS)
    raise ValueError("Goofish script trigger inventory incomplete; refusing partial consolidation")


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


def remove_redundant_didi_usercenter_script(lines):
    """Remove only the FMZ duplicate for the exact Didi user-center response endpoint."""
    canonical = re.sub(r"\\+", "", DIDI_USERCENTER_CANONICAL_TRIGGER.strip())
    redundant = re.sub(r"\\+", "", DIDI_USERCENTER_REDUNDANT_TRIGGER.strip())
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
        if normalized == redundant:
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
    normalized_matcher = re.sub(r"\\+", "", DDQX_NEWDETAILS_MATCHER)
    normalized_native = re.sub(r"\\+", "", DDQX_NEWDETAILS_NATIVE_RULE)
    normalized_legacy = normalized_matcher + " " + DDQX_NEWDETAILS_LEGACY_ACTION
    normalized_modern = re.sub(r"\\+", "", DDQX_NEWDETAILS_MODERN_ACTION)
    for line in lines:
        normalized = re.sub(r"\\+", "", line.strip())
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
        raise ValueError("Duoduo Grocery newDetails suspension rule changed; refusing an unreviewed conversion")
    if legacy_count > 1 or modern_count > 1 or native_count > 1:
        raise ValueError("duplicate Duoduo Grocery newDetails suspension rules; refusing ambiguous conversion")
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
    norm = lambda value: re.sub(r"\\+", "", value.strip()).lower()

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

    common_v5 = [line for line in output if line.strip() == DIDIADS_COMMON_V5_SCRIPT]
    if len(common_v5) != 1:
        raise ValueError("Didi common/v5 canonical script trigger missing or duplicated")
    for legacy, marker, label in (
        (DIDI_CORE_LEGACY_SCRIPT, "homepage/vd/core", "core"),
        (DIDI_USERCENTER_LEGACY_SCRIPT, "common/vd/usercenter/me", "usercenter"),
    ):
        exact = [line for line in output if line.strip() == legacy]
        drifted = [line for line in output if "AntiAd/didi.js" in line and marker in norm(line) and line.strip() != legacy]
        if drifted:
            raise ValueError("Didi " + label + " legacy script trigger drifted")
        if len(exact) > 1:
            raise ValueError("duplicate Didi " + label + " legacy script trigger")
        if exact:
            output = [line for line in output if line.strip() != legacy]

    removed_noop = 0
    for legacy in DIDIADS_NOOP_SCRIPT_RULES:
        marker = norm(legacy.split(" then script(", 1)[0])
        exact = [line for line in output if line.strip() == legacy]
        drifted = [line for line in output if "didiAds.js" in line and marker in norm(line) and line.strip() != legacy]
        if drifted:
            raise ValueError("DidiAds no-op script trigger drifted; refusing unreviewed cleanup")
        if len(exact) > 1:
            raise ValueError("duplicate DidiAds no-op script trigger")
        if exact:
            output = [line for line in output if line.strip() != legacy]
            removed_noop += 1

    remaining_didiads = [line.strip() for line in output if "didiAds.js" in line]
    if remaining_didiads != [DIDIADS_COMMON_V5_SCRIPT]:
        raise ValueError("DidiAds script trigger inventory changed; expected common/v5 only")
    for keeper in (DIDI_OTA_KEEP_SCRIPT, DIDI_PRESALE_KEEP_SCRIPT):
        if sum(line.strip() == keeper for line in output) != 1:
            raise ValueError("Didi R-Store retained script inventory changed")
    remaining_rstore = [line.strip() for line in output if "AntiAd/didi.js" in line]
    if sorted(remaining_rstore) != sorted((DIDI_OTA_KEEP_SCRIPT, DIDI_PRESALE_KEEP_SCRIPT)):
        raise ValueError("Didi R-Store script inventory changed")
    return output, removed_noop

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
            raise ValueError("Dianping gated script trigger missing or changed: " + label)
        output = [line for line in output if line.strip() != legacy]
        removed += 1
    return output, removed



BAIDUMAP_LEGACY_SCRIPT_RULE = ("http-response ^https?:\\/\\/newclient\\.map\\.baidu\\.com\\/client\\/phpui2\\/\\?qt=ads script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/baiduMap.js,tag=BAIDUMAP,requires-body=true,binary-body-mode=true", "response if ${url} ~= /^https?:\\/\\/newclient\\.map\\.baidu\\.com\\/client\\/phpui2\\/\\?qt=ads/i then script(\"https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/baidumap.js\") with enable=bdduditu_enable, tag=\"百度地图广告\", timeout=60, requires_body=true", "newclient.map.baidu.com/qt=ads")


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
        raise ValueError("Baidu Maps gated script trigger missing or changed: " + label)
    output = [line for line in output if line.strip() != legacy]
    return output, 1



AMAP_LEGACY_SCRIPT_EXPECTED_COUNT = 33
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
        targets.append((line, required))
    if not targets:
        return output, 0
    if expected_count is not None and len(targets) != expected_count:
        raise ValueError(
            "Amap legacy response script inventory changed; expected %d, found %d"
            % (expected_count, len(targets))
        )
    for _line, required_markers in targets:
        for marker in required_markers:
            count = sum(marker in handler for handler in response_handlers)
            if count != 1:
                raise ValueError(
                    "Amap canonical response handler missing or duplicated: " + marker
                )
    remaining = [line for line in lines]
    for target_line, _required in targets:
        remaining.remove(target_line)
    return remaining, len(targets)



# Jingdong: retain the unconditional R-Store cleaner and preserve the optional
# FMZ welcomeHome-only extension behind its existing user switch.
JD_RSTORE_LEGACY_TRIGGER = r"http-response ^https?:\/\/api\.m\.jd\.com\/client\.action\?functionId=(?:deliverLayer|getTabHomeInfo|myOrderInfo|orderTrackBusiness|personinfoBusiness|start|welcomeHome|readCustomSurfaceList) script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/jd.js,tag=JD,requires-body=true"
JD_FMZ_LEGACY_TRIGGER = r'response if ${url} ~= /^https:\/\/api\.m\.jd\.com\/client\.action\?functionId=(deliverLayer|getTabHomeInfo|myOrderInfo|orderTrackBusiness|personinfoBusiness|start|welcomeHome)/i then script("https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/jingdong/jingdong.js") with enable=jkds_enable, tag="京东", timeout=60, requires_body=true'
JD_CANONICAL_TRIGGER = r"http-response ^https?:\/\/api\.m\.jd\.com\/client\.action\?functionId=(?:deliverLayer|getTabHomeInfo|myOrderInfo|orderTrackBusiness|personinfoBusiness|start|welcomeHome|readCustomSurfaceList) script-path=https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/jingdong/jd.js,tag=JD-CONSOLIDATED,requires-body=true"
JD_OPTIONAL_WELCOME_TRIGGER = r'response if ${url} ~= /^https:\/\/api\.m\.jd\.com\/client\.action\?functionId=welcomeHome/i then script("https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/jingdong/jd-welcome.js") with enable=jkds_enable, tag="京东首页额外清理", timeout=60, requires_body=true'


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
    fmz_count = scoped.count(JD_FMZ_LEGACY_TRIGGER)
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
    if rstore_count != 1 or fmz_count != 1:
        raise ValueError(
            "Jingdong legacy trigger inventory changed; expected one R-Store and one FMZ trigger"
        )

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
        if section == "Script" and line.strip() == JD_FMZ_LEGACY_TRIGGER:
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
    if canonical_count or unknown_legacy or any(count != 1 for count in counts):
        raise ValueError(
            "Meituan script trigger inventory changed; refusing partial or mixed consolidation"
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
    return output, len(MEITUAN_LEGACY_TRIGGERS)



# Douyin / Hongguo boundary safety:
# - dig.bdurl.net is ByteDance HTTPDNS, not an ad host.
# - webcast-open.douyin.com supplies recommended live-room feeds, not ads.
# - the broad "minigame" keyword can disable ByteDance mini-game runtime.
DOUYIN_HONGGUO_UNSAFE_RULES = {
    "DOMAIN,webcast-open.douyin.com,REJECT",
    "DOMAIN-KEYWORD,minigame,REJECT",
    "DOMAIN-SUFFIX,dig.bdurl.net,REJECT",
}
DOUYIN_LIVE_FEED_REWRITE_RULES = {
    r"^https?:\/\/webcast-open\.douyin\.com\/webcast\/openapi\/feed\/ reject-dict",
    r"request if ${url} ~= /^https:\/\/webcast-open\.douyin\.com\/webcast\/openapi\/feed\/\?/ then reject_dict(200)",
}
DOUYIN_LIVE_FEED_HOST = "webcast-open.douyin.com"


def remove_douyin_hongguo_unsafe_rules(lines):
    """Remove only the reviewed HTTPDNS/runtime/live-feed blocks and MITM host."""
    section = ""
    rule_counts = {rule: 0 for rule in DOUYIN_HONGGUO_UNSAFE_RULES}
    rewrite_counts = {rule: 0 for rule in DOUYIN_LIVE_FEED_REWRITE_RULES}
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
    if not any(counts) and live_feed_host_count == 0 and not unknown:
        return list(lines), 0
    if unknown or any(count != 1 for count in counts) or live_feed_host_count != 1:
        raise ValueError(
            "Douyin/Hongguo safety inventory changed; refusing partial, drifted or duplicated cleanup"
        )

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
        if section == "Rewrite" and value in DOUYIN_LIVE_FEED_REWRITE_RULES:
            continue
        if section == "MITM" and value.lower().startswith("hostname") and "=" in value:
            key, host_text = line.split("=", 1)
            hosts = [host.strip() for host in host_text.split(",") if host.strip()]
            hosts = [host for host in hosts if host.lower() != DOUYIN_LIVE_FEED_HOST]
            line = key + "= " + ", ".join(hosts)
        output.append(line)
    return output, len(counts) + 1



# Kugou/Jin10 rewrite deduplication is deliberately limited to audited exact matchers.
KUGOU_DUPLICATE_REWRITES = {
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
KUGOU_OBSOLETE_ROOM_LIST_REWRITE = "^https:\\/\\/gzacshow\\.kugou\\.com\\/mfanxing-home\\/cdn\\/room\\/index\\/list_v reject-dict"
JIN10_REDUNDANT_AD_RESPONSE_REWRITE = "^https:\\/\\/jad-api\\.jin10\\.com\\/ad reject-dict"


def remove_kugou_jin10_redundant_rewrites(lines):
    section = ""
    counts = {rule: 0 for rule in KUGOU_DUPLICATE_REWRITES}
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
    values = list(counts.values())
    if all(count == 1 for count in values) and obsolete_count == 0 and jin10_response_count == 0:
        return list(lines), 0
    if any(count != 2 for count in values) or obsolete_count != 1 or jin10_response_count != 1:
        raise ValueError("Kugou/Jin10 rewrite inventory changed; refusing partial or drifted deduplication")
    output, section, seen = [], "", set()
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            output.append(line)
            continue
        value = line.strip()
        if section == "Rewrite":
            if value in counts:
                if value in seen:
                    continue
                seen.add(value)
            elif value in (KUGOU_OBSOLETE_ROOM_LIST_REWRITE, JIN10_REDUNDANT_AD_RESPONSE_REWRITE):
                continue
        output.append(line)
    if seen != set(KUGOU_DUPLICATE_REWRITES):
        raise ValueError("Kugou/Jin10 canonical rewrite insertion failed")
    return output, len(KUGOU_DUPLICATE_REWRITES) + 2


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
            if not REQUIRED_BANKCOMM_MITM_HOSTS.issubset(set(hosts)):
                raise ValueError("required Bankcomm image hosts missing from MITM")
            # Defer legacy HelloBike host removal until all surviving Rewrite/Script
            # references are known. Some hosts are also used by unrelated base rules.
            line = key + "= " + ", ".join(hosts)
        lines.append(line)

    lines, _ = remove_douyin_hongguo_unsafe_rules(lines)
    lines, _ = remove_kugou_jin10_redundant_rewrites(lines)

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
    lines, _ = consolidate_pdd_homepage_script(lines)
    lines, _ = remove_redundant_pdd_oak_script_trigger(lines)
    lines, guiderank_homepage_script_count = remove_guiderank_homepage_script(lines)
    lines, gaoding_converted_triggers = remove_gaoding_resource_scripts(lines)
    lines, _ = remove_redundant_taobao_scripts(lines)
    lines, _ = remove_redundant_didi_usercenter_script(lines)
    lines, _ = consolidate_goofish_script_triggers(lines)
    lines, _ = consolidate_jingdong_scripts(lines)
    lines, _ = consolidate_meituan_scripts(lines)
    lines, _ = remove_redundant_dianping_scripts(lines)
    lines, _ = remove_redundant_baidumap_script(lines)
    lines, _ = remove_redundant_amap_legacy_scripts(lines)

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
                rewrite_lines, _ = merge_adjacent_response_json_rewrites(rewrite_lines)
                rewrite_lines, _ = remove_subsumed_soul_teenager_rule(rewrite_lines)
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
        rewrite_lines, _ = merge_adjacent_response_json_rewrites(rewrite_lines)
        rewrite_lines, _ = remove_subsumed_soul_teenager_rule(rewrite_lines)
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
    result_lines, _ = apply_didi_script_and_homepage_cleanup(result_lines)
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
