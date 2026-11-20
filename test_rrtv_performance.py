import json
import shutil
import subprocess
import unittest
from pathlib import Path

from optimize_rrtv import EXPECTED_TRIGGERS, LOCAL, MARKER, REMOTE, optimize_source, rewrite_plugin

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "scripts" / "rrtv" / "rrtv.js"
NODE = shutil.which("node")


class RRTVOptimizerTests(unittest.TestCase):
    def test_snapshot_is_idempotent_and_drops_unused_framework(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn(MARKER, source)
        self.assertEqual(optimize_source(source), source)
        self.assertNotIn("function MagicJS(", source)
        self.assertNotIn("new MagicJS(", source)
        self.assertNotIn("$persistentStore", source)
        self.assertNotIn("$httpClient", source)
        self.assertIn("function createLoonRuntime(name)", source)
        self.assertIn("function compactInPlace(items, keep)", source)
        self.assertIn("function rewritePlaybackFlags(body)", source)
        self.assertEqual(source.count("rewritePlaybackFlags(magicJS.response.body)"), 2)
        self.assertLess(len(source), 18000)

    def test_all_nine_triggers_migrate_and_remain_idempotent(self):
        fixture = "[Script]\n" + "\n".join(
            "http-response ^https://api.rr.tv/%d script-path=%s,tag=RRTV-%d,requires-body=true"
            % (index, REMOTE, index)
            for index in range(EXPECTED_TRIGGERS)
        ) + "\n[MITM]\nhostname = api.rr.tv\n"
        migrated = rewrite_plugin(fixture)
        self.assertEqual(migrated.count(LOCAL), EXPECTED_TRIGGERS)
        self.assertNotIn(REMOTE, migrated)
        self.assertEqual(rewrite_plugin(migrated), migrated)

    def test_partial_and_mixed_inventories_fail_closed(self):
        partial = "[Script]\n" + "\n".join(
            "http-response ^https://api.rr.tv/%d script-path=%s" % (index, REMOTE)
            for index in range(EXPECTED_TRIGGERS - 1)
        )
        with self.assertRaisesRegex(ValueError, "expected 9"):
            rewrite_plugin(partial)
        mixed = partial + "\nhttp-response ^https://api.rr.tv/local script-path=" + LOCAL
        with self.assertRaisesRegex(ValueError, "mixed local and remote"):
            rewrite_plugin(mixed)


@unittest.skipUnless(NODE, "Node.js is required for RRTV response runtime tests")
class RRTVRuntimeTests(unittest.TestCase):
    def run_script(self, url, body):
        runner = r"""
const fs = require("fs"), vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
const nativeParse = JSON.parse.bind(JSON);
const nativeStringify = JSON.stringify.bind(JSON);
const nativeReplace = String.prototype.replace;
let doneResult, doneCount = 0;
const context = {
  $request: { url: payload.url },
  $response: { body: payload.body === null ? "" : payload.body },
  $done(value) { doneResult = value === undefined ? null : value; doneCount++; },
  parseCount: 0, stringifyCount: 0, replaceCount: 0,
  nativeParse, nativeStringify, nativeReplace,
  console: { log() {}, warn() {}, error() {} }
};
vm.createContext(context);
vm.runInContext(