import shutil
import subprocess
import unittest
from pathlib import Path

from optimize_cnftp import FILTER_MARKER, LOCAL_URL, REMOTE_URL, SOURCE_MARKER, optimize_source, rewrite_plugin

ROOT = Path(__file__).parent
SOURCE_PATH = ROOT / "scripts" / "cnftp" / "cnftp.js"


class CnftpPerformanceTests(unittest.TestCase):
    def test_optimized_source_is_idempotent_and_uses_stable_compaction(self):
        source = SOURCE_PATH.read_text(encoding="utf-8")
        self.assertIn(SOURCE_MARKER, source)
        self.assertEqual(optimize_source(source), source)
        start = source.index('  } else if (url.includes("columbus.home.query/")) {')
        end = source.index('  } else if (url.includes("columbus.uc.query/")) {', start)
        branch = source[start:end]
        self.assertIn("compactInPlace(objData.nodes", branch)
        self.assertNotIn("newNodes1", branch)
        self.assertNotIn("newNode2", branch)
        self.assertNotIn("newNode3", branch)
        self.assertNotIn("newNode4", branch)
        self.assertNotIn('console.log("移除首页的轮播广告")', branch)

    def test_terminal_empty_body_guard_is_added_idempotently(self):
        source = SOURCE_PATH.read_text(encoding="utf-8")
        self.assertIn("CNFTP terminal empty-body guard v1", source)
        self.assertIn("if (!$response.body) {\n  $done({});\n} else {", source)
        self.assertEqual(optimize_source(source), source)

    def test_node_runtime_empty_body_skips_json_parse(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for CNFTP runtime tests")
        harness = r'''
const fs = require("fs"), vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
let parseCalls = 0, doneCalls = 0, doneResult;
const trackedJSON = {
  parse(value) { parseCalls++; return JSON.parse(value); },
  stringify(value) { return JSON.stringify(value); }
};
const context = {
  JSON: trackedJSON,
  $request: { url: "https://acs.youku.com/gw/mtop.youku.columbus.home.feed/" },
  $response: { body: "" },
  $done(value) { doneCalls++; doneResult = value; },
  console: { log() {}, warn() {}, error() {} }
};
vm.createContext(context);
vm.runInContext(source, context, { timeout: 5000 });
if (parseCalls !== 0) throw new Error("empty response unexpectedly parsed JSON: " + parseCalls);
if (doneCalls !== 1 || !doneResult || Object.keys(doneResult).length !== 0) {
  throw new Error("empty response must complete once with pass-through");
}
'''
        result = subprocess.run(
            [node, "-e", harness, str(SOURCE_PATH)],
            capture_output=True, text=True, check=False, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_all_response_filter_assignments_use_in_place_compaction(self):
        source = SOURCE_PATH.read_text(encoding="utf-8")
        self.assertIn(FILTER_MARKER, source)
        self.assertNotRegex(source, r"\.filter\s*\(")
        self.assertEqual(optimize_source(source), source)

    def test_node_runtime_comment_filter_preserves_order_without_array_filter(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for CNFTP runtime tests")
        harness = r'''
const fs = require("fs"), vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const body = { cards: [
  { alias_name: "comment_resource_card", id: "ad-1" },
  { alias_name: "normal_comment", id: "keep-1" },
  { id: "missing-alias" },
  { alias_name: "comment_resource_convention_card", id: "ad-2" },
  { alias_name: "normal_comment", id: "keep-2" }
]};
let parseCalls = 0, stringifyCalls = 0, doneResult;
const nativeJSON = JSON;
const trackedJSON = {
  parse(value) { parseCalls++; return nativeJSON.parse(value); },
  stringify(value) { stringifyCalls++; return nativeJSON.stringify(value); }
};
const context = {
  JSON: trackedJSON,
  $request: { url: "https://iface2.iqiyi.com/views_comment/" },
  $response: { body: nativeJSON.stringify(body) },
  $done(value) { doneResult = value; },
  console: { log() {}, warn() {}, error() {} }
};
vm.createContext(context);
vm.runInContext(source, context, { timeout: 5000 });
if (parseCalls !== 1 || stringifyCalls !== 1) throw new Error("unexpected JSON round trips");
if (!doneResult || typeof doneResult.body !== "string") throw new Error("missing rewritten body");
const output = nativeJSON.parse(doneResult.body);
if (output.cards.length !== 2 || output.cards[0].id !== "keep-1" || output.cards[1].id !== "keep-2") {
  throw new Error("comment card compaction changed filtering or order");
}
'''
        result = subprocess.run(
            [node, "-e", harness, str(SOURCE_PATH)],
            capture_output=True, text=True, check=False, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_upstream_home_feed_branch_is_migrated_fail_closed(self):
        fixture = """const url = $request.url;
if (isYK) {
  } else if (url.includes("columbus.home.feed/")) {
  let newNodes1 = [];
  for (let node1 of objData.nodes) {
    if (node1?.typeName === "PHONE_FEED_CARD_GROUP") {
      let newNode2 = [];
      for (let node2 of node1.nodes) {
        if (node2?.typeName === "PHONE_FEED_CARD_S_AD") continue;
        else if (node2?.typeName === "PHONE_H_UC_AD") continue;
        else newNode2.push(node2);
      }
      node1.nodes = newNode2;
      newNodes1.push(node1);
    } else newNodes1.push(node1);
  }
  objData.nodes = newNodes1;
  } else if (url.includes("columbus.home.query/")) {
  let newNodes1 = []; let newNode2 = []; let newNode3 = []; let newNode4 = [];
  if (node3.id === 272768) {}
  } else if (url.includes("columbus.uc.query/")) {}
"""
        optimized = optimize_source(fixture, "a" * 40)
        self.assertIn("Youku home.feed in-place compaction v1", optimized)
        self.assertIn("compactInPlace(objData.nodes", optimized)
        self.assertIn("compactInPlace(node1.nodes", optimized)
        self.assertNotIn("let newNodes1 = [];", optimized)
        self.assertEqual(optimize_source(optimized), optimized)

    def test_node_runtime_compacts_youku_home_feed_without_filter_allocations(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for CNFTP runtime tests")
        harness = r'''
const fs = require("fs"), vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const body = { data: { "2019061000": { data: { nodes: [
  { typeName: "PHONE_FEED_CARD_GROUP", nodes: [
    { typeName: "PHONE_FEED_CARD_S_AD", id: "small-ad" },
    { typeName: "NORMAL", id: "keep-1" },
    { typeName: "PHONE_H_UC_AD", id: "wide-ad" },
    { typeName: "NORMAL", id: "keep-2" }
  ]},
  { typeName: "NORMAL", id: "outside-group" }
]}}}};
let parseCalls = 0, stringifyCalls = 0, doneResult;
const nativeJSON = JSON;
const trackedJSON = {
  parse(value) { parseCalls++; return nativeJSON.parse(value); },
  stringify(value) { stringifyCalls++; return nativeJSON.stringify(value); }
};
const context = {
  JSON: trackedJSON,
  $request: { url: "https://acs.youku.com/gw/mtop.youku.columbus.home.feed/" },
  $response: { body: nativeJSON.stringify(body) },
  $done(value) { doneResult = value; },
  console: { log() {}, warn() {}, error() {} }
};
vm.createContext(context);
const nativeFilter = Array.prototype.filter; Array.prototype.filter = function() { throw new Error("Array.filter allocation remains"); };
vm.runInContext(source, context, { timeout: 5000 });
Array.prototype.filter = nativeFilter;
if (parseCalls !== 1 || stringifyCalls !== 1) throw new Error("unexpected JSON round trips");
if (!doneResult || typeof doneResult.body !== "string") throw new Error("missing rewritten body");
const output = nativeJSON.parse(doneResult.body);
const nodes = output.data["2019061000"].data.nodes;
if (nodes.length !== 2 || nodes[1].id !== "outside-group") throw new Error("outer node order changed");
const children = nodes[0].nodes;
if (children.length !== 2 || children[0].id !== "keep-1" || children[1].id !== "keep-2") throw new Error("home feed ad compaction mismatch");
'''
        result = subprocess.run(
            [node, "-e", harness, str(SOURCE_PATH)],
            capture_output=True, text=True, check=False, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_rewrites_exact_cnftp_trigger_inventory_and_is_idempotent(self):
        fixture = "[Script]\n" + "\n".join(
            'response if ${url} ~= /^https:\\/\\/example\\.com\\/%d/ then script("%s") with requires_body=true' % (i, REMOTE_URL)
            for i in range(10)
        ) + "\n[MITM]\nhostname = example.com\n"
        result = rewrite_plugin(fixture)
        self.assertEqual(result.count(LOCAL_URL), 10)
        self.assertNotIn(REMOTE_URL, result)
        self.assertEqual(rewrite_plugin(result), result)

    def test_preserves_base_only_plugin_when_cnftp_handler_is_absent(self):
        fixture = "[Script]\nhttp-response ^https?:\\\\/\\\\/example\\\\.com script-path=https://example.invalid/keep.js\n[MITM]\nhostname = example.com\n"
        self.assertEqual(rewrite_plugin(fixture), fixture)

    def test_fails_closed_when_cnftp_trigger_count_drifts(self):
        fixture = "[Script]\n" + 'response if ${url} ~= /^https:\\/\\/example/ then script("%s")' % REMOTE_URL + "\n[MITM]\n"
        with self.assertRaisesRegex(ValueError, "trigger inventory changed"):
            rewrite_plugin(fixture)

    def test_node_runtime_preserves_nested_youku_home_query_results(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for CNFTP runtime tests")
        harness = r'''
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const data = {
  data: {
    "2019061000": {
      data: {
        data: { indexPositionResult: [{id: 1}] },
        nodes: [
          { data: { nodeKey: "CHILD" }, nodes: [{id: 999}] },
          {
            data: { nodeKey: "KEEP", indexPositionResult: [{id: 2}], refreshImg: "bg" },
            nodes: [
              { typeName: "UC广告抽屉", data: { crmSale: true } },
              {
                id: 31476,
                typeName: "NORMAL",
                data: { crmSale: true, keywords: ["hot"] },
                nodes: [
                  { typeName: "PHONE_FEED_CARD_B_AD", id: 1, nodes: [] },
                  {
                    typeName: "KEEP",
                    id: 2,
                    nodes: [
                      { typeName: "PHONE_FEED_CARD_S_AD", data: {} },
                      { typeName: "KEEP", data: {} },
                      { typeName: "KEEP", data: { ad: true } }
                    ]
                  },
                  { typeName: "KEEP", id: 272768, nodes: [] }
                ]
              },
              { id: 35505, data: {} },
              { id: 37335, data: {} },
              { id: 50000, nodes: [{id: 272768}, {id: 3, data: {}}] }
            ]
          }
        ]
      }
    }
  }
};
let parseCalls = 0, stringifyCalls = 0, doneResult;
const trackedJSON = {
  parse(...args) { parseCalls++; return JSON.parse(...args); },
  stringify(...args) { stringifyCalls++; return JSON.stringify(...args); }
};
vm.runInNewContext(source, {
  JSON: trackedJSON,
  $request: { url: "https://acs.youku.com/gw/mtop.youku.columbus.home.query/" },
  $response: { body: JSON.stringify(data) },
  $done(value) { doneResult = value; },
  console: { log() { throw new Error("home.query should not emit logs"); } }
});
if (parseCalls !== 1 || stringifyCalls !== 1) throw new Error("JSON parse/stringify count changed: " + parseCalls + "/" + stringifyCalls);
if (!doneResult || typeof doneResult.body !== "string") throw new Error("response body missing");
const output = JSON.parse(doneResult.body);
const root = output.data["2019061000"].data;
if (root.nodes.length !== 1 || root.nodes[0].data.nodeKey !== "KEEP") throw new Error("root nodes not filtered in stable order");
if (root.data.indexPositionResult.length !== 0) throw new Error("home indexPositionResult not cleared");
const node1 = root.nodes[0];
if (node1.data.indexPositionResult.length !== 0 || "refreshImg" in node1.data) throw new Error("node1 fields not cleaned");
if (node1.nodes.length !== 2 || node1.nodes[0].id !== 31476 || node1.nodes[1].id !== 50000) throw new Error("node2 compaction/order mismatch");
const node2 = node1.nodes[0];
if ("crmSale" in node2.data || "keywords" in node2.data) throw new Error("node2 promo fields not removed");
if (node2.nodes.length !== 1 || node2.nodes[0].id !== 2) throw new Error("node3 compaction/order mismatch");
if (node2.nodes[0].nodes.length !== 1 || node2.nodes[0].nodes[0].data.ad) throw new Error("node4 compaction mismatch");
if (node1.nodes[1].nodes.length !== 1 || node1.nodes[1].nodes[0].id !== 3) throw new Error("node3 id filter mismatch");
'''
        result = subprocess.run(
            [node, "-e", harness, str(SOURCE_PATH)],
            capture_output=True, text=True, check=False
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


    def test_iqiyi_waterfall_and_mango_lists_use_in_place_compaction(self):
        source = SOURCE_PATH.read_text(encoding="utf-8")
        self.assertIn("iQIYI waterfall nested stable in-place compaction v1", source)
        self.assertIn("Mango vrsList stable in-place compaction v1", source)
        self.assertIn("Mango odin channel stable in-place compaction v1", source)
        vrs = source[source.index('url.includes("/dynamic/v1/channel/vrsList/")'):source.index('url.includes("/mobile/config?")')]
        self.assertNotIn("obj.data = newItems;", vrs)
        self.assertEqual(optimize_source(source), source)

    def test_node_runtime_compaction_preserves_iqiyi_and_mango_order(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for CNFTP runtime tests")
        harness = r'''
const fs = require("fs"), vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
function run(url, body) {
  let doneResult, parseCalls = 0, stringifyCalls = 0;
  const nativeJSON = JSON;
  const trackedJSON = {
    parse(value) { parseCalls++; return nativeJSON.parse(value); },
    stringify(value) { stringifyCalls++; return nativeJSON.stringify(value); }
  };
  const context = {
    JSON: trackedJSON, $request: {url}, $response: {body: nativeJSON.stringify(body)},
    $done(value) { doneResult = value; }, console: {log(){},warn(){},error(){}}
  };
  vm.runInNewContext(source, context, {timeout:5000});
  if (parseCalls !== 1 || stringifyCalls !== 1) throw new Error("unexpected JSON roundtrip");
  return nativeJSON.parse(doneResult.body);
}
const iq = run("https://iface2.iqiyi.com/waterfall/", {cards:[
  {id:"ad",block_class:"ad",blocks:[]},
  {id:"keep1",blocks:[{id:"a",block_class:"ad"},{id:"b"},{id:"c"}]},
  {id:"keep2",blocks:[{id:"d"}]}
]});
if (iq.cards.length!==2 || iq.cards[0].id!=="keep1" || iq.cards[1].id!=="keep2") throw new Error("iQIYI outer order/filter changed");
if (iq.cards[0].blocks.length!==2 || iq.cards[0].blocks[0].id!=="b") throw new Error("iQIYI nested filter changed");
const mg1 = run("https://api.mgtv.com/dynamic/v1/channel/vrsList/", {data:[
  {vclassId:100043,id:"remove"},{vclassId:100160,id:"keep1"},{vclassId:100033,id:"keep2"}
]});
if (mg1.data.length!==2 || mg1.data[0].id!=="keep1" || mg1.data[1].id!=="keep2") throw new Error("Mango vrsList semantics changed");
const mg2 = run("https://api.mgtv.com/odin/c1/channel/index?", {data:[
  {moduleType:"childslideicon"},{moduleType:"normal",id:1},{moduleType:"normal",id:2}
]});
if (mg2.data.length!==2 || mg2.data[0].id!==1 || mg2.data[1].id!==2) throw new Error("Mango odin semantics changed");
'''
        result = subprocess.run([node, "-e", harness, str(SOURCE_PATH)], capture_output=True, text=True, check=False, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


    def test_iqiyi_mango_hot_array_markers_and_optimizer_idempotence(self):
        source = SOURCE_PATH.read_text(encoding="utf-8")
        for marker in (
            "iQIYI category nested stable in-place compaction v1",
            "iQIYI search nested stable in-place compaction v1",
            "Mango dynamic channel nested stable in-place compaction v1",
        ):
            self.assertIn(marker, source)
        self.assertEqual(optimize_source(source), source)

    def test_youku_mango_personal_compaction_markers_and_idempotence(self):
        source = SOURCE_PATH.read_text(encoding="utf-8")
        for marker in (
            "Youku personal center nested stable in-place compaction v1",
            "Youku comment nested stable in-place compaction v1",
            "Mango personal center nested stable in-place compaction v1",
        ):
            self.assertIn(marker, source)
        self.assertEqual(optimize_source(source), source)

    def test_node_runtime_youku_personal_comment_and_mango_personal(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for CNFTP runtime tests")
        harness = r'''
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync(process.argv[1],"utf8");
function run(url,body){let result,pc=0,sc=0;const J=JSON;const c={JSON:{parse(v){pc++;return J.parse(v)},stringify(v){sc++;return J.stringify(v)}},$request:{url},$response:{body:J.stringify(body)},$done(v){result=v},console:{log(){},warn(){},error(){}}};vm.runInNewContext(source,c,{timeout:5000});if(pc!==1||sc!==1)throw Error("JSON roundtrip "+pc+"/"+sc);return J.parse(result.body);}
const personal={data:{}};personal.data["2019061000"]={data:{nodes:[{nodes:[
{id:32133},{id:28912,nodes:[{id:110429},{id:5}]},{id:36015,nodes:[{nodes:[{id:683367},{id:683364},{id:683372}]}]},{id:50000}
]}]}};
const youku=run("https://acs.youku.com/gw/mtop.youku.columbus.uc.query/",personal);
const yn=youku.data["2019061000"].data.nodes[0].nodes;
if(yn.length!==3||yn[0].nodes[0].id!==5||yn[1].nodes[0].nodes[0].id!==683367||yn[1].nodes[0].nodes.length!==2)throw Error("Youku personal filtering/order");
const commentBody={data:{}};commentBody.data["2019061000"]={data:{nodes:[{nodes:[
{id:23242,nodes:[{typeName:"COMPONENT_YCP_NOTICE"},{id:1},{id:113941}]},{id:23243,nodes:[{id:-1000},{id:2}]},{id:3}
]}]}};
const comment=run("https://acs.youku.com/gw/mtop.youku.columbus.ycp.query/",commentBody);
const cn=comment.data["2019061000"].data.nodes[0].nodes;
if(cn.length!==3||cn[0].nodes.length!==1||cn[0].nodes[0].id!==1||cn[1].nodes.length!==1||cn[1].nodes[0].id!==2)throw Error("Youku comment filtering");
const mango=run("https://api.mgtv.com/v3/module/list?",{data:{list:[
{moduleType:3},{moduleType:2,title:"用户信息模块",data:[{title:"领取芒果卡权益"},{title:"保留"}]},
{moduleType:7,title:"我的服务",data:[{title:"我的音乐"},{title:"客服"}]},{moduleType:1}
]}});
const ml=mango.data.list;
if(ml.length!==3||ml[0].data.length!==1||ml[1].data.length!==1||ml[1].data[0].title!=="客服")throw Error("Mango personal filtering/order");
'''
        result = subprocess.run([node, "-e", harness, str(SOURCE_PATH)], capture_output=True, text=True, check=False, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


    def test_iqiyi_personal_home_and_mango_player_compaction_markers(self):
        source = SOURCE_PATH.read_text(encoding="utf-8")
        for marker in (
            "iQIYI personal menus nested stable in-place compaction v1",
            "iQIYI home cards allocation-free traversal v1",
            "Mango player modules stable in-place compaction v1",
        ):
            self.assertIn(marker, source)
        self.assertNotIn("let newMenus = []", source)
        self.assertNotIn("let newLists = []", source)
        self.assertNotIn("let newCards = []", source)
        self.assertNotIn("let newMods = []", source)
        self.assertEqual(optimize_source(source), source)

    def test_node_runtime_iqiyi_personal_home_and_mango_player(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for CNFTP runtime tests")
        harness = r'''
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync(process.argv[1],"utf8"),J=JSON;
function run(url,body){let result,pc=0,sc=0;const c={JSON:{parse(v){pc++;return J.parse(v)},stringify(v){sc++;return J.stringify(v)}},$request:{url},$response:{body:J.stringify(body)},$done(v){result=v},console:{log(){},warn(){},error(){}}};vm.runInNewContext(source,c,{timeout:5000});if(pc!==1||sc!==1)throw Error("JSON roundtrip "+pc+"/"+sc);return J.parse(result.body);}
const my=run("https://iface2.iqiyi.com/getMyMenus?",{data:[
 {statistic:{block:"wd_liebiao_2"},menuList:[{menuType:1}]},
 {statistic:{block:"keep"},menuList:[{menuType:121},{menuType:1,id:"menu-keep"}]},
 {statistic:{block:"keep-2"},menuList:[]}
]});
if(my.data.length!==2||my.data[0].menuList.length!==1||my.data[0].menuList[0].id!=="menu-keep"||my.data[1].statistic.block!=="keep-2")throw Error("iQIYI personal menu semantics/order");
const home=run("https://iface2.iqiyi.com/views_home/",{cards:[
 {alias_name:"ad_mobile_flow"},
 {alias_name:"normal",top_banner:{l_blocks:[{buttons:[1]},{buttons:[]},{text:"keep"}]}},
 {alias_name:"normal-2"}
]});
if(home.cards.length!==2||home.cards[0].alias_name!=="normal"||home.cards[1].alias_name!=="normal-2")throw Error("iQIYI home card filtering/order");
if("buttons" in home.cards[0].top_banner.l_blocks[0]||home.cards[0].top_banner.l_blocks[2].text!=="keep")throw Error("iQIYI home banner cleanup");
const mango=run("https://api.mgtv.com/v1/vod/info?",{data:{template:{modules:[
 {dataType:202,id:"remove"},{dataType:101,id:"keep-1",clipInfo:{rcInfo:"remove"}},
 {dataType:201,id:"keep-2",clipInfo:{other:"keep"}},{dataType:702,id:"remove-2"}
]}}});
const mods=mango.data.template.modules;
if(mods.length!==2||mods[0].id!=="keep-1"||mods[1].id!=="keep-2")throw Error("Mango module filtering/order");
if("rcInfo" in mods[0].clipInfo||mods[1].clipInfo.other!=="keep")throw Error("Mango recommendation cleanup");
'''
        result = subprocess.run(
            [node, "-e", harness, str(SOURCE_PATH)],
            capture_output=True, text=True, check=False, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_optimizer_fails_closed_for_changed_iqiyi_personal_menu_block(self):
        source = SOURCE_PATH.read_text(encoding="utf-8")
        changed = source.replace(
            "iQIYI personal menus nested stable in-place compaction v1",
            "iQIYI personal menus nested stable in-place compaction v2",
        )
        changed = changed.replace(
            'url.includes("/getMyMenus?")',
            'url.includes("/getMyMenus?")',
            1,
        )
        with self.assertRaisesRegex(ValueError, "iQIYI personal menus upstream structure changed"):
            optimize_source(changed)


    def test_supported_route_guard_is_present_and_optimizer_is_idempotent(self):
        source = SOURCE_PATH.read_text(encoding="utf-8")
        self.assertIn("CNFTP pre-parse supported-route guard v1", source)
        self.assertEqual(optimize_source(source), source)
        self.assertEqual(source.count("let obj = JSON.parse($response.body);"), 1)
        self.assertLess(source.index("const shouldProcess ="), source.index("let obj = JSON.parse($response.body);"))

    def test_node_runtime_unsupported_routes_skip_json_parse_and_stringify(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for CNFTP runtime tests")
        harness = r'''
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync(process.argv[1],"utf8"),nativeJSON=JSON;
let parseCalls=0,stringifyCalls=0,doneCalls=0,result;
const trackedJSON={parse(v){parseCalls++;return nativeJSON.parse(v)},stringify(v){stringifyCalls++;return nativeJSON.stringify(v)}};
const context={JSON:trackedJSON,$request:{url:"https://iface2.iqiyi.com/unhandled/large/response"},$response:{body:'{"large":[1,2,3]}'},$done(v){doneCalls++;result=v},console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,context,{timeout:5000});
if(parseCalls!==0||stringifyCalls!==0)throw Error("unsupported route parsed or serialized response");
if(doneCalls!==1||!result||Object.keys(result).length!==0)throw Error("unsupported route must pass through once");
'''
        result = subprocess.run([node, "-e", harness, str(SOURCE_PATH)], capture_output=True, text=True, check=False, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_node_runtime_supported_route_still_applies_filter(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for CNFTP runtime tests")
        harness = r'''
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync(process.argv[1],"utf8"),J=JSON;
let parseCalls=0,stringifyCalls=0,result;
const trackedJSON={parse(v){parseCalls++;return J.parse(v)},stringify(v){stringifyCalls++;return J.stringify(v)}};
const context={JSON:trackedJSON,$request:{url:"https://iface2.iqiyi.com/views_comment/"},$response:{body:J.stringify({cards:[{id:"ad"},{id:"keep",alias_name:"normal"}]})},$done(v){result=v},console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,context,{timeout:5000});
if(parseCalls!==1||stringifyCalls!==1)throw Error("supported route must parse and serialize once");
const out=J.parse(result.body);
if(out.cards.length!==1||out.cards[0].id!=="keep")throw Error("supported route filtering changed");
'''
        result = subprocess.run([node, "-e", harness, str(SOURCE_PATH)], capture_output=True, text=True, check=False, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_optimizer_fails_closed_when_supported_route_guard_is_damaged(self):
        source = SOURCE_PATH.read_text(encoding="utf-8")
        damaged = source.replace("CNFTP pre-parse supported-route guard v1", "CNFTP pre-parse supported-route guard v2", 1)
        with self.assertRaisesRegex(ValueError, "CNFTP supported-route guard marker/structure drift"):
            optimize_source(damaged)


    def test_cnftp_lazy_serialization_marker_and_optimizer_idempotence(self):
        source = SOURCE_PATH.read_text(encoding="utf-8")
        self.assertIn("CNFTP lazy response serialization v1", source)
        self.assertIn("$done(modified ? {body: JSON.stringify(obj)} : {});", source)
        self.assertIn("function setIfDifferent(", source)
        self.assertIn("function deleteIfPresent(", source)
        self.assertEqual(optimize_source(source), source)

    def test_node_runtime_supported_noop_skips_stringify(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for CNFTP runtime tests")
        harness = r'''
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync(process.argv[1],"utf8"),J=JSON;
let parseCalls=0,stringifyCalls=0,doneCalls=0,result;
const trackedJSON={parse(v){parseCalls++;return J.parse(v)},stringify(v){stringifyCalls++;return J.stringify(v)}};
const body={cards:[{alias_name:"normal",id:"keep-1"},{alias_name:"normal",id:"keep-2"}]};
const context={JSON:trackedJSON,$request:{url:"https://iface2.iqiyi.com/views_comment/"},$response:{body:J.stringify(body)},$done(v){doneCalls++;result=v},console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,context,{timeout:5000});
if(parseCalls!==1||stringifyCalls!==0)throw Error("no-op supported response must parse once and skip stringify: "+parseCalls+"/"+stringifyCalls);
if(doneCalls!==1||!result||Object.keys(result).length!==0)throw Error("no-op supported response must pass through once");
'''
        result = subprocess.run([node, "-e", harness, str(SOURCE_PATH)], capture_output=True, text=True, check=False, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_node_runtime_actual_mutation_serializes_once_and_preserves_output(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for CNFTP runtime tests")
        harness = r'''
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync(process.argv[1],"utf8"),J=JSON;
let parseCalls=0,stringifyCalls=0,doneCalls=0,result;
const trackedJSON={parse(v){parseCalls++;return J.parse(v)},stringify(v){stringifyCalls++;return J.stringify(v)}};
const body={cards:[{id:"ad"},{id:"keep",alias_name:"normal"}]};
const context={JSON:trackedJSON,$request:{url:"https://iface2.iqiyi.com/views_comment/"},$response:{body:J.stringify(body)},$done(v){doneCalls++;result=v},console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,context,{timeout:5000});
if(parseCalls!==1||stringifyCalls!==1)throw Error("mutated response must stringify once");
if(doneCalls!==1||!result||typeof result.body!=="string")throw Error("mutated response body missing");
const out=J.parse(result.body);
if(out.cards.length!==1||out.cards[0].id!=="keep")throw Error("comment filtering changed");
'''
        result = subprocess.run([node, "-e", harness, str(SOURCE_PATH)], capture_output=True, text=True, check=False, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_optimizer_fails_closed_when_lazy_serialization_marker_is_removed(self):
        source = SOURCE_PATH.read_text(encoding="utf-8")
        damaged = source.replace("CNFTP lazy response serialization v1", "CNFTP lazy response serialization v2", 1)
        with self.assertRaisesRegex(ValueError, "CNFTP lazy serialization marker/structure drift"):
            optimize_source(damaged)


if __name__ == "__main__":
    unittest.main()
