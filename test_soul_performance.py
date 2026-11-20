import json
import shutil
import subprocess
import unittest
from pathlib import Path

from optimize_soul import EXPECTED_TRIGGERS, LOCAL, MARKER, REMOTE, optimize_source, rewrite_plugin

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "scripts" / "soul" / "soul.js"
NODE = shutil.which("node")


class SoulOptimizerTests(unittest.TestCase):
    def test_snapshot_is_idempotent_and_unused_framework_is_removed(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn(MARKER, source)
        self.assertEqual(optimize_source(source), source)
        self.assertNotIn("function Env(", source)
        self.assertNotIn("new Env(", source)
        self.assertNotIn(".filter(", source)
        self.assertNotIn(".map(", source)
        self.assertIn("function compactInPlace(items, keep)", source)
        self.assertIn("if (modified)", source)

    def test_nine_triggers_migrate_and_fail_closed(self):
        fixture = "[Script]\n" + "\n".join(
            "http-response ^https://soul%d.example/api script-path=%s,tag=SOUL-%d,requires-body=true"
            % (index, REMOTE, index)
            for index in range(EXPECTED_TRIGGERS)
        )
        migrated = rewrite_plugin(fixture)
        self.assertEqual(migrated.count(LOCAL), EXPECTED_TRIGGERS)
        self.assertNotIn(REMOTE, migrated)
        self.assertEqual(rewrite_plugin(migrated), migrated)
        with self.assertRaisesRegex(ValueError, "expected 9"):
            rewrite_plugin(fixture.rsplit("\n", 1)[0])
        mixed = fixture + "\nhttp-response ^https://soul.local/api script-path=" + LOCAL
        with self.assertRaisesRegex(ValueError, "mixed local and remote"):
            rewrite_plugin(mixed)


@unittest.skipUnless(NODE, "Node.js is required for Soul runtime tests")
class SoulRuntimeTests(unittest.TestCase):
    def run_script(self, url, body):
        runner = r"""
const fs = require("fs"), vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const parse = JSON.parse.bind(JSON), stringify = JSON.stringify.bind(JSON);
let doneValue, doneCount = 0;
const c = {
  $request: {url: input.url},
  $response: {body: input.body},
  $done(value) { doneValue = value; doneCount++; },
  parseCount: 0, stringifyCount: 0, parse, stringify,
  console: {log() {}, warn() {}, error() {}}
};
vm.createContext(c);
vm.runInContext(
  "JSON.parse=function(v){parseCount++;return parse(v)};" +
  "JSON.stringify=function(v){stringifyCount++;return stringify(v)};" +
  "Array.prototype.filter=function(){throw new Error('Array.filter must not be used')};" +
  "Array.prototype.map=function(){throw new Error('Array.map must not be used')};",
  c
);
vm.runInContext(source, c, {timeout:5000});
if (doneCount !== 1) throw new Error("expected one $done call, got " + doneCount);
const output = doneValue && typeof doneValue.body === "string" ? parse(doneValue.body) : null;
process.stdout.write(stringify({
  done: doneValue, output, parseCount: c.parseCount,
  stringifyCount: c.stringifyCount, doneCount
}));
"""
        result = subprocess.run(
            [NODE, "-e", runner, str(SOURCE)],
            input=json.dumps({"url": url, "body": body}, ensure_ascii=False),
            capture_output=True, text=True, check=True, timeout=10,
        )
        return json.loads(result.stdout)

    def test_empty_and_invalid_bodies_pass_through_without_serialization(self):
        empty = self.run_script("https://api-a.soulapp.cn/v1/post/gift/list", "")
        self.assertEqual(empty["done"], {})
        self.assertEqual(empty["parseCount"], 0)
        self.assertEqual(empty["stringifyCount"], 0)

        invalid = self.run_script("https://api-a.soulapp.cn/v1/post/gift/list", "{bad json")
        self.assertEqual(invalid["done"], {})
        self.assertEqual(invalid["parseCount"], 1)
        self.assertEqual(invalid["stringifyCount"], 0)

    def test_delete_data_only_when_target_route_has_data(self):
        changed = self.run_script(
            "https://api-a.soulapp.cn/v1/post/gift/list",
            json.dumps({"data": {"items": [1, 2]}, "meta": {"ok": True}}),
        )
        self.assertEqual(changed["output"], {"meta": {"ok": True}})
        self.assertEqual(changed["stringifyCount"], 1)

        clean = self.run_script(
            "https://api-a.soulapp.cn/v1/post/gift/list",
            json.dumps({"meta": {"ok": True}}),
        )
        self.assertEqual(clean["done"], {})
        self.assertEqual(clean["stringifyCount"], 0)

    def test_chat_limit_is_changed_only_when_needed(self):
        changed = self.run_script(
            "https://api-chat.soulapp.cn/chat/limitInfo",
            json.dumps({"data": {"limit": True, "other": 1}}),
        )
        self.assertEqual(changed["output"]["data"], {"limit": False, "other": 1})
        self.assertEqual(changed["stringifyCount"], 1)

        clean = self.run_script(
            "https://api-chat.soulapp.cn/chat/limitInfo",
            json.dumps({"data": {"limit": False, "other": 1}}),
        )
        self.assertEqual(clean["done"], {})
        self.assertEqual(clean["stringifyCount"], 0)

    def test_planet_game_lists_are_compacted_in_place_and_card_style_is_preserved(self):
        body = {
            "data": {
                "gameInfo": {"gameCards": [
                    {"title": "异世界回响"}, {"title": "ordinary"}
                ]},
                "coreCards": [
                    {"title": "狼人魅影", "style": 2},
                    {"title": "ordinary", "style": 2, "secondCards": [
                        {"title": "群聊派对"}, {"title": "keep"}
                    ]},
                ],
            }
        }
        result = self.run_script("https://api-a.soulapp.cn/v6/planet/config", json.dumps(body, ensure_ascii=False))
        data = result["output"]["data"]
        self.assertEqual([x["title"] for x in data["gameInfo"]["gameCards"]], ["ordinary"])
        self.assertEqual([x["title"] for x in data["coreCards"]], ["ordinary"])
        self.assertEqual(data["coreCards"][0]["style"], 1)
        self.assertEqual([x["title"] for x in data["coreCards"][0]["secondCards"]], ["keep"])
        self.assertEqual(result["stringifyCount"], 1)

    def test_core_card_style_cleanup_remains_active_on_other_triggered_routes(self):
        result = self.run_script(
            "https://api-pay.soulapp.cn/privilege/supervip/status",
            json.dumps({"data": {"coreCards": [{"style": 2}, {"style": 1}]}}),
        )
        self.assertEqual([x["style"] for x in result["output"]["data"]["coreCards"]], [1, 1])
        self.assertEqual(result["stringifyCount"], 1)

    def test_unmodified_triggered_payload_is_returned_untouched(self):
        result = self.run_script(
            "https://api-pay.soulapp.cn/vip/meet/userInfo",
            json.dumps({"data": {"user": {"id": 1}}}),
        )
        self.assertEqual(result["done"], {})
        self.assertEqual(result["stringifyCount"], 0)


if __name__ == "__main__":
    unittest.main()
