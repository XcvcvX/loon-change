import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NODE = shutil.which("node")
SOURCE = ROOT / "scripts" / "bilibili" / "bilibili-json.js"


@unittest.skipUnless(NODE, "Node.js is required for Bilibili response runtime tests")
class BilibiliResponseCompactionTests(unittest.TestCase):
    def run_script(self, url, items):
        runner = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
const NativeJSON = JSON;
let numericWrites = 0;
const instrumentedJSON = {
  parse(text) {
    const value = NativeJSON.parse(text);
    const list = value && value.data && value.data.items;
    if (Array.isArray(list)) {
      value.data.items = new Proxy(list, {
        set(target, key, next) {
          if (/^(0|[1-9][0-9]*)$/.test(String(key))) numericWrites++;
          return Reflect.set(target, key, next);
        }
      });
    }
    return value;
  },
  stringify(value) { return NativeJSON.stringify(value); }
};
let doneResult;
const context = {
  JSON: instrumentedJSON,
  $request: { url: payload.url },
  $response: { body: JSON.stringify(payload.body) },
  $done(value) { doneResult = value; },
  console: { log() {}, warn() {}, error() {} }
};
vm.runInNewContext(source, context, { timeout: 5000 });
if (!doneResult || typeof doneResult.body !== "string") throw new Error("missing rewritten response");
const output = JSON.parse(doneResult.body);
process.stdout.write(JSON.stringify({ output, numericWrites }));
"""
        body = {"data": {"items": items}}
        completed = subprocess.run(
            [NODE, "-e", runner, str(SOURCE)],
            input=json.dumps({"url": url, "body": body}),
            capture_output=True, text=True, check=True, timeout=10,
        )
        return json.loads(completed.stdout)

    def test_feed_kept_items_are_not_written_back_to_the_same_indices(self):
        items = [{"id": "a", "card_goto": "av"}, {"id": "b", "card_goto": "av"}]
        result = self.run_script("https://app.bilibili.com/x/v2/feed/index?pull=1", items)
        self.assertEqual([item["id"] for item in result["output"]["data"]["items"]], ["a", "b"])
        self.assertEqual(result["numericWrites"], 0)

    def test_feed_compaction_writes_only_when_items_shift(self):
        items = [
            {"id": "ad", "card_goto": "banner"},
            {"id": "a", "card_goto": "av"},
            {"id": "b", "card_goto": "av"},
        ]
        result = self.run_script("https://app.bilibili.com/x/v2/feed/index?pull=1", items)
        self.assertEqual([item["id"] for item in result["output"]["data"]["items"]], ["a", "b"])
        self.assertEqual(result["numericWrites"], 2)

    def test_story_feed_preserves_kept_items_without_redundant_array_writes(self):
        items = [{"id": "a", "card_goto": "vertical_av"}, {"id": "b", "card_goto": "vertical_av"}]
        result = self.run_script("https://app.bilibili.com/x/v2/feed/index/story?pull=1", items)
        self.assertEqual([item["id"] for item in result["output"]["data"]["items"]], ["a", "b"])
        self.assertEqual(result["numericWrites"], 0)

    def test_compaction_loops_cache_array_lengths_and_guard_same_index_writes(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("if (write !== read) items[write] = item;", source)
        self.assertIn("let read = 0, length = items.length", source)
        self.assertNotIn("items[write++]", source)
        self.assertNotIn("sections[sectionWrite++]", source)
        self.assertNotIn("items[itemWrite++]", source)


if __name__ == "__main__":
    unittest.main()
