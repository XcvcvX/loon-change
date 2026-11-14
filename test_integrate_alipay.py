#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path

from integrate_alipay import integrate

SOURCE = """#!name=支付宝小程序-广告拦截合集
[Rule]
DOMAIN,abapi.hellobike.com,REJECT
DOMAIN,apmgw.hellobike.com,REJECT
DOMAIN,cdn.hellobike.com,REJECT
DOMAIN,ip.hellobike.com,REJECT
[Rewrite]
request if ${url} ~= /^https?:\\/\\/api\\.hellobike\\.com\\/api\\?msg\\.toast\\.user/i then reject(200)
request if ${url} ~= /^https?:\\/\\/api\\.hellobike\\.com\\/api\\?homepage\\.shortcut\\.scene\\.perception/i then reject(200)
request if ${url} ~= /^https?:\\/\\/api\\.hellobike\\.com\\/api\\?homepage\\.module\\.newAlipay/i then reject(200)
request if ${url} ~= /^https?:\\/\\/waimai-guide\\.ele\\.me\\/h5\\/mtop\\.alsc\\.interact\\.content\\.homepage\\.float/i then reject(200)
request if ${url} ~= /^https?:\\/\\/api\\.hellobike\\.com\\/api\\?bottom\\.aggregation\\.tab\\.info/i then reject(200)
request if ${url} ~= /^https?:\\/\\/waimai-guide\\.ele\\.me\\/(gw|h5)\\/mtop\\.alsc\\.eleme\\.trigger\\.respond/i then reject(200)
request if ${url} ~= /^https?:\\/\\/api\\.hellobike\\.com\\/api\\?homepage\\.recommend\\.popUp/i then reject(200)
response if ${url} ~= /^https?:\\/\\/alsc-buy2\\.ele\\.me\\/h5\\/mtop\\.alsc\\.eleme\\.order\\.detail\\.miniapp\\.build/i then response.body.replace(/orderDetailCdpTriggerInfo/, "random_body")
^https?:\\/\\/mdn\\.alicdn\\.com\\/imgextra\\/i1\\/.*-tps-180-180\\.gif$ mock-response-body data-type=tiny-gif status-code=200
response if ${url} ~= /^https?:\\/\\/waimai-guide\\.ele\\.me\\/h5\\/mtop\\.ele\\.growth\\.fission\\.client\\.etmd\\.et\\.getmainpageicon/i then response.body.mock("json", "{}", 200)
response if ${url} ~= /^https?:\\/\\/shopping\\.ele\\.me\\/(gw|h5)\\/mtop\\.o2o\\.ad\\.exposure\\.get/i then response.body.mock("json", "{}", 200)
response if ${url} ~= /^https?:\\/\\/m5-zb\\.amap\\.com\\/ws\\/promotion-web\\/resource/i then response.body.mock("json", "{}", 200)
response if ${url} ~= /^https?:\\/\\/guide-acs\\.m\\.taobao\\.com\\/gw\\/mtop\\.film\\.life\\.(popup|aristotle)\\.get/i then response.body.mock("json", "{}", 200)
response if ${url} ~= /^https?:\\/\\/creditcardapp\\.bankcomm\\.com\\/cnsvPmpaAliCardWeb\\/page\\/getGuidePageAds/i then response.body.mock("json", "{}", 200)
response if ${url} ~= /^https?:\\/\\/guide-acs\\.m\\.taobao\\.com\\/gw\\/mtop\\.cainiao\\.guoguo\\.nbnetflow\\.ads/i then response.body.mock("json", "{}", 200)
response if ${url} ~= /^https?:\\/\\/m5-zb\\.amap\\.com\\/ws\\/boss\\/end\\/recommend/i then response.body.mock("json", "{}", 200)
response if ${url} ~= /^https?:\\/\\/api\\.hellobike\\.com\\/api\\?homepage\\.hitch\\.awareness/i then response.body.mock("json", "{}", 200)
response if ${url} ~= /^https?:\\/\\/waimai-guide\\.ele\\.me\\/(gw|h5)\\/mtop\\.alsc\\.upp\\.tbet\\.send/i then response.body.mock("json", "{}", 200)
response if ${url} ~= /^https?:\\/\\/api\\.hellobike\\.com\\/api\\?homepage\\.newWelfare\\.alipay/i then response.body.mock("json", "{}", 200)
response if ${url} ~= /^https?:\\/\\/api\\.hellobike\\.com\\/api\\?applet\\.homepage\\.medal\\.activity/i then response.body.mock("json", "{}", 200)
[Script]
response if ${url} ~= /^https?:\\/\\/waimai-guide\\.ele\\.me\\/(gw|h5)\\/mtop\\.alsc\\.eleme\\.miniapp\\.homepage/i then script("https://github.com/ifflagged/Romeo/raw/main/Modules/JavaScript/zirawell/alipayAdBlock/zirawell_eleme.js") with tag="eleme", requires_body=true
[MITM]
hostname = api.hellobike.com, shopping.ele.me, waimai-guide.ele.me, guide-acs.m.taobao.com, mdn.alicdn.com, aimai-guide.m.taobao.com, alsc-buy2.ele.me, m5-zb.amap.com
"""
PLUGIN = """#!name=combined
[Argument]
[Rule]
DOMAIN,example.com,REJECT
[Rewrite]
[Script]
[MITM]
hostname = example.com
"""


class IntegrateAlipayTests(unittest.TestCase):
    def test_integration_is_idempotent_and_vendors_script_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin, source, js = root / "out.plugin", root / "source.lpx", root / "eleme.js"
            plugin.write_text(PLUGIN, encoding="utf-8")
            source.write_text(SOURCE, encoding="utf-8")
            js.write_text("const body = {}; " * 20, encoding="utf-8")
            url = "https://raw.githubusercontent.com/XcvcvX/loon-change/main/sources/alipay/zirawell_eleme.js"
            first = integrate(plugin, source, js, url)
            result1 = plugin.read_text()
            second = integrate(plugin, source, js, url)
            result2 = plugin.read_text()
            self.assertEqual(result1, result2)
            self.assertGreater(first["added"]["Rewrite"], 0)
            self.assertEqual(second["added"]["Rewrite"], 0)
            self.assertIn(url, result2)
            self.assertNotIn("github.com/ifflagged/Romeo/raw/main/Modules/JavaScript/zirawell", result2)
            self.assertNotIn("aimai-guide.m.taobao.com", result2)
            self.assertIn("waimai-guide.ele.me", result2)
            self.assertIn("creditcardapp.bankcomm.com", result2)

    def test_rejects_missing_javascript_dependency(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin, source, js = root / "out.plugin", root / "source.lpx", root / "eleme.js"
            plugin.write_text(PLUGIN, encoding="utf-8")
            source.write_text(SOURCE, encoding="utf-8")
            js.write_text("<html>not found</html>", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "JavaScript"):
                integrate(plugin, source, js, "https://example.com/script.js")

    def test_rejects_truncated_upstream(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin, source, js = root / "out.plugin", root / "source.lpx", root / "eleme.js"
            plugin.write_text(PLUGIN, encoding="utf-8")
            source.write_text("[Rule]\nDOMAIN,a.example,REJECT", encoding="utf-8")
            js.write_text("const x = 1;" * 20, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "规则数量异常"):
                integrate(plugin, source, js, "https://example.com/script.js")


if __name__ == "__main__":
    unittest.main()
