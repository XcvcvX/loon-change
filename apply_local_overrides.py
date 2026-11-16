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
DIDI_HOME_SLOW_LEGACY_REJECT = r"^https:\/\/conf\.diditaxi\.com\.cn\/homepage\/v1\/other\/slow reject-dict"
DIDI_HOME_FAST_LEGACY_REJECT = r"^https:\/\/conf\.diditaxi\.com\.cn\/homepage\/v1\/other\/fast reject-dict"
DIDI_HOME_SLOW_RESPONSE_PREFIX = r"response if ${url} ~= /^https:\/\/conf\.diditaxi\.com\.cn\/homepage\/v\d\/other\/slow\?/i then response.json.delete("
DIDI_HOME_FAST_RESPONSE_PREFIX = r"response if ${url} ~= /^https:\/\/conf\.diditaxi\.com\.cn\/homepage\/v\d\/other\/fast\?/i then response.json.delete("


DIDI_HOME_CORE_LEGACY_REJECT = r"^https:\\/\\/conf\\.diditaxi\\.com\\.cn\\/homepage\\/v\\d\\/core reject-dict"
DIDI_HOME_CORE_RESPONSE_PREFIX = r"response if ${url} ~= /^https:\\/\\/conf\\.diditaxi\\.com\\.cn\\/homepage\\/v\\d\\/core\\?/i then response.json.jq("


def remove_didi_homepage_rejects_shadowing_field_cleaners(lines):
    """Remove exact whole-endpoint rejects only when precise field cleaners supersede them."""
    output = list(lines)
    removed = 0
    targets = (
        (DIDI_HOME_SLOW_LEGACY_REJECT, DIDI_HOME_SLOW_RESPONSE_PREFIX, "slow"),
        (DIDI_HOME_FAST_LEGACY_REJECT, DIDI_HOME_FAST_RESPONSE_PREFIX, "fast", "homepage/v1/other/fast"),
        (DIDI_HOME_CORE_LEGACY_REJECT, DIDI_HOME_CORE_RESPONSE_PREFIX, "core", "homepage/v\\d/core"),
    )
    for legacy_rule, response_prefix, label, drift_marker in targets:
        exact_positions = [i for i, line in enumerate(output) if line.strip() == legacy_rule]
        drifted = [
            line.strip() for line in output
            if "conf.diditaxi.com.cn/homepage/v1/other/" + label
            in re.sub(r"\\+", "", line)
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
    lines, guiderank_homepage_script_count = remove_guiderank_homepage_script(lines)
    lines, gaoding_converted_triggers = remove_gaoding_resource_scripts(lines)
    lines, _ = remove_redundant_taobao_scripts(lines)
    lines, _ = remove_redundant_didi_usercenter_script(lines)

    result_lines, rewrite_lines = [], []
    section = ""
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            if section == "Rewrite":
                rewrite_lines, _ = remove_duplicate_pdd_homepage_delete_path(rewrite_lines)
                rewrite_lines, _ = remove_redundant_dache_core_icon_filter(rewrite_lines)
                rewrite_lines, _ = merge_didi_fast_homepage_json_deletes(rewrite_lines)
                rewrite_lines, _ = remove_didi_homepage_rejects_shadowing_field_cleaners(rewrite_lines)
                rewrite_lines, _ = merge_adjacent_response_json_rewrites(rewrite_lines)
                rewrite_lines, _ = remove_subsumed_soul_teenager_rule(rewrite_lines)
                rewrite_lines, _ = remove_shadowed_peopleapp_rules(rewrite_lines)
                rewrite_lines, _ = remove_shadowed_terminal_block_rules(rewrite_lines)
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
        rewrite_lines, _ = remove_redundant_dache_core_icon_filter(rewrite_lines)
        rewrite_lines, _ = merge_didi_fast_homepage_json_deletes(rewrite_lines)
        rewrite_lines, _ = remove_didi_homepage_rejects_shadowing_field_cleaners(rewrite_lines)
        rewrite_lines, _ = merge_adjacent_response_json_rewrites(rewrite_lines)
        rewrite_lines, _ = remove_subsumed_soul_teenager_rule(rewrite_lines)
        rewrite_lines, _ = remove_shadowed_peopleapp_rules(rewrite_lines)
        rewrite_lines, _ = remove_shadowed_terminal_block_rules(rewrite_lines)
        rewrite_lines, _ = remove_lkcoffee_member_exchange_success_overrides(rewrite_lines)
        rewrite_lines, _ = replace_guiderank_special_sale_random_body(rewrite_lines)
        rewrite_lines, _ = replace_ddqx_newdetails_body_rewrites(rewrite_lines)
        if guiderank_homepage_script_count and GUIDERANK_HOMEPAGE_NATIVE_RULE not in [item.strip() for item in rewrite_lines]:
            rewrite_lines.append(GUIDERANK_HOMEPAGE_NATIVE_RULE)
        existing_rewrites = {item.strip() for item in rewrite_lines}
        rewrite_lines.extend(rule for rule in GAODING_NATIVE_RULES if rule not in existing_rewrites and ((rule == GAODING_NATIVE_RULES[0] and GAODING_TEMPLATE_SCRIPT_TRIGGER in gaoding_converted_triggers) or (rule == GAODING_NATIVE_RULES[1] and GAODING_MINE_SCRIPT_TRIGGER in gaoding_converted_triggers)))
        result_lines.extend(rewrite_lines)
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
