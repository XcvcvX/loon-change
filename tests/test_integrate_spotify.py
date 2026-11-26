#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import tempfile
import shutil
import unittest
import sys
from unittest.mock import patch
from pathlib import Path
from integrate_spotify import integrate, main, optimize_spotify_home_script, optimize_spotify_nested_script


SOURCE = r"""#!name=Spotify
[Argument]
hide_ai_dj = switch,true
[Rule]
AND,((DOMAIN-SUFFIX, spotify.com), (PROTOCOL, QUIC)),REJECT
DOMAIN,aet.spotify.com,REJECT
[Rewrite]
^https:\/\/(?:spclient\.wg|[\w-]+-spclient)\.spotify\.com(?::443)?\/(?:ads\/|ad-logic\/|[^?#]*\/ad-on-app-open|premium-marketing\/upsellOffer) reject
^https:\/\/spclient\.wg\.spotify\.com\/premium-marketing\/upsellOffer reject
[Mitm]
hostname = spclient.wg.spotify.com, *spclient.spotify.com
[Script]
http-request ^https:\/\/(.*-spclient\.spotify\.com(:443)?|spclient\.wg\.spotify\.com)\/gabo-receiver-service script-path=https://raw.githubusercontent.com/devchristian1337/loon-plugins/refs/heads/main/Scripts/Spotify/spot-gabo.js, timeout=10, tag=Spotify gabo
http-response ^https:\/\/(spclient\.wg\.spotify\.com|.*-spclient\.spotify\.com(:443)?)\/browsita\/v.\/browse script-path=https://raw.githubusercontent.com/devchristian1337/loon-plugins/refs/heads/main/Scripts/Spotify/spot-NoSearchAd.js, requires-body=true, binary-body-mode=true, timeout=10, tag=Spotify search ads
http-response ^https:\/\/(spclient\.wg\.spotify\.com|.*-spclient\.spotify\.com(:443)?)\/casita\/v.\/home\/ script-path=https://raw.githubusercontent.com/devchristian1337/loon-plugins/refs/heads/main/Scripts/Spotify/spot-NoHomeAd.js, requires-body=true, binary-body-mode=true, timeout=10, tag=Spotify home ads
http-response ^https:\/\/(spclient\.wg\.spotify\.com|.*-spclient\.spotify\.com(:443)?)\/scrollsita\/v.\/scroll\/spotify script-path=https://raw.githubusercontent.com/devchristian1337/loon-plugins/refs/heads/main/Scripts/Spotify/spot-NoScrollAd.js, requires-body=true, binary-body-mode=true, timeout=10, tag=Spotify scroll ads
http-response ^https:\/\/spclient\.wg\.spotify\.com\/bootstrap script-path=https://raw.githubusercontent.com/devchristian1337/loon-plugins/refs/heads/main/Scripts/Spotify/spot-proto-ev3.js, tag=Spotify protobuf
"""


class SpotifyIntegrationTests(unittest.TestCase):
    def test_cli_entrypoint_runs_without_module_scope_name_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'Spotify.lpx'
            source.write_text(SOURCE, encoding='utf-8')
            source_scripts = root / 'upstream'
            source_scripts.mkdir()
            for name in ('spot-gabo.js', 'spot-NoSearchAd.js', 'spot-NoHomeAd.js', 'spot-NoScrollAd.js'):
                if name in ('spot-NoHomeAd.js', 'spot-NoSearchAd.js', 'spot-NoScrollAd.js'):
                    content = (Path(__file__).parent / 'scripts' / 'spotify' / name).read_text(encoding='utf-8')
                else:
                    content = '// upstream script\n' + 'x' * 200
                (source_scripts / name).write_text(content, encoding='utf-8')
            plugin = root / 'allAdRewrite.plugin'
            plugin.write_text('[Rule]\n[Rewrite]\n[Script]\n[MITM]\nhostname = example.com\n', encoding='utf-8')
            meta = root / 'upstream.json'
            argv = ['integrate_spotify.py', '--plugin', str(plugin), '--source-plugin', str(source),
                    '--scripts-source', str(source_scripts), '--scripts-dest', str(root / 'scripts'),
                    '--upstream-commit', 'abc123', '--metadata', str(meta)]
            with patch.object(sys, 'argv', argv):
                main()
            self.assertTrue(meta.exists())
            self.assertIn('DOMAIN,aet.spotify.com,REJECT', plugin.read_text(encoding='utf-8'))
    def test_independent_spotify_source_replaces_all_rstore_spotify_entries(self):
        from integrate_spotify import replace_rstore_spotify_rules
        plugin = """[Rule]
DOMAIN,aet.spotify.com,REJECT
DOMAIN,keep.example.com,REJECT
[Rewrite]
^https?:\/\/spclient.wg.spotify.com\/ads\/ reject
^https?:\/\/keep.example.com\/ads\/ reject
[Script]
http-response ^https?:\/\/spclient.wg.spotify.com\/bootstrap script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/spotify.js,tag=SPOTIFY
http-response ^https:\/\/keep.example.com\/unrelated script-path=https://example.com/other.js,tag=OTHER
[MITM]
hostname = api.example.com, *spotify.com, spclient.wg.spotify.com
"""
        cleaned, removed = replace_rstore_spotify_rules(plugin)
        self.assertEqual(removed, 5)
        self.assertNotIn("spotify.com", cleaned)
        self.assertNotIn("spotify.js", cleaned)
        self.assertIn("keep.example.com", cleaned)
        self.assertIn("tag=OTHER", cleaned)

    def test_rstore_spotify_filter_is_safe_when_script_absent(self):
        from integrate_spotify import replace_rstore_spotify_rules
        cleaned, removed = replace_rstore_spotify_rules("[Script]\n# no R-Store Spotify handler\n[MITM]\nhostname = api.example.com\n")
        self.assertEqual(removed, 0)
        self.assertIn("# no R-Store Spotify handler", cleaned)

    def test_extracts_only_ad_features_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "Spotify.lpx"
            source.write_text(SOURCE, encoding="utf-8")
            source_scripts = root / "upstream"
            source_scripts.mkdir()
            for name in ("spot-gabo.js", "spot-NoSearchAd.js", "spot-NoHomeAd.js", "spot-NoScrollAd.js"):
                if name in ("spot-NoHomeAd.js", "spot-NoSearchAd.js", "spot-NoScrollAd.js"):
                    content = (Path(__file__).parent / "scripts" / "spotify" / name).read_text(encoding="utf-8")
                else:
                    content = "// upstream script\n" + "x" * 200
                (source_scripts / name).write_text(content, encoding="utf-8")
            plugin = root / "allAdRewrite.plugin"
            plugin.write_text("[Rule]\n[Rewrite]\n[Script]\n[MITM]\nhostname = example.com\n", encoding="utf-8")
            meta = root / "upstream.json"
            integrate(plugin, source, source_scripts, root / "scripts", "abc123", meta)
            first = plugin.read_text(encoding="utf-8")
            integrate(plugin, source, source_scripts, root / "scripts", "abc123", meta)
            second = plugin.read_text(encoding="utf-8")
            self.assertEqual(first, second)
            self.assertIn("DOMAIN,aet.spotify.com,REJECT", second)
            self.assertIn("ad-logic", second)
            self.assertIn("ad-on-app-open", second)
            self.assertNotIn("premium-marketing", second)
            self.assertNotIn("spot-proto-ev3", second)
            self.assertIn("scripts/spotify/spot-NoHomeAd.js", second)
            self.assertIn("*spclient.spotify.com", second)
            self.assertEqual(len(list((root / "scripts").glob("*.js"))), 4)


    def test_spotify_home_optimizer_is_idempotent_and_preserves_upstream_refresh(self):
        from integrate_spotify import HOME_FAST_PATH_MARKER
        upstream = Path(__file__).parent / "scripts" / "spotify" / "spot-NoHomeAd.js"
        optimized = optimize_spotify_home_script(upstream.read_text(encoding="utf-8"))
        self.assertIn(HOME_FAST_PATH_MARKER, optimized)
        self.assertNotIn("const kept = []", optimized)
        self.assertEqual(optimize_spotify_home_script(optimized), optimized)

    @unittest.skipUnless(shutil.which("node"), "Node.js is required for Spotify binary runtime tests")
    def test_spotify_home_clean_response_avoids_subarray_and_kept_array_allocations(self):
        import json
        import subprocess
        import tempfile
        from integrate_spotify import HOME_FAST_PATH_MARKER
        source = (Path(__file__).parent / "scripts" / "spotify" / "spot-NoHomeAd.js").read_text(encoding="utf-8")
        self.assertIn(HOME_FAST_PATH_MARKER, source)
        def varint(value):
            result = bytearray()
            while value >= 0x80:
                result.append((value & 0x7f) | 0x80)
                value >>= 7
            result.append(value)
            return bytes(result)
        def section(name, content_field=1):
            header = name.encode()
            key = varint(content_field * 8 + 2)
            return b"\x0a" + varint(len(header)) + header + key + b"\x01x"
        def wrap(items, tail=b""):
            payload = b"".join(b"\x0a" + varint(len(item)) + item for item in items)
            return b"\x0a" + varint(len(payload)) + payload + tail
        normal = section("spotify:section:home|recommendations")
        ad = section("spotify:section:home|brand-ad")
        tail = b"\x10\x01"
        runner = r"""
const fs = require("fs");
const vm = require("vm");
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
const source = fs.readFileSync(process.argv[1], "utf8");
let doneResult;
let subarrayCount = 0;
const nativeSubarray = Uint8Array.prototype.subarray;
Uint8Array.prototype.subarray = function(...args) {
  subarrayCount++;
  return nativeSubarray.apply(this, args);
};
const context = {
  Uint8Array,
  $response: { body: Uint8Array.from(payload.body) },
  $done(value) { doneResult = value; },
  console: { log() {} }
};
vm.createContext(context);
vm.runInContext(source, context, { timeout: 3000 });
process.stdout.write(JSON.stringify({
  emptyRewrite: !!doneResult && Object.keys(doneResult).length === 0,
  subarrayCount,
  output: doneResult && doneResult.body ? Array.from(doneResult.body) : null
}));
"""
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "home.js"
            script.write_text(source, encoding="utf-8")
            clean = wrap([normal], tail)
            completed = subprocess.run(
                [shutil.which("node"), "-e", runner, str(script)],
                input=json.dumps({"body": list(clean)}), text=True,
                capture_output=True, check=True, timeout=10,
            )
            clean_result = json.loads(completed.stdout)
            self.assertTrue(clean_result["emptyRewrite"])
            self.assertEqual(clean_result["subarrayCount"], 0)
            changed = wrap([normal, ad], tail)
            completed = subprocess.run(
                [shutil.which("node"), "-e", runner, str(script)],
                input=json.dumps({"body": list(changed)}), text=True,
                capture_output=True, check=True, timeout=10,
            )
            changed_result = json.loads(completed.stdout)
            self.assertEqual(bytes(changed_result["output"]), wrap([normal], tail))
            self.assertGreater(changed_result["subarrayCount"], 0)


    def test_spotify_search_and_scroll_optimizers_are_idempotent(self):
        from integrate_spotify import SEARCH_FAST_PATH_MARKER, SCROLL_FAST_PATH_MARKER
        root = Path(__file__).parent / "scripts" / "spotify"
        for filename, kind, marker in (
            ("spot-NoSearchAd.js", "search", SEARCH_FAST_PATH_MARKER),
            ("spot-NoScrollAd.js", "scroll", SCROLL_FAST_PATH_MARKER),
        ):
            upstream = (root / filename).read_text(encoding="utf-8")
            optimized = optimize_spotify_nested_script(upstream, kind)
            self.assertIn(marker, optimized)
            self.assertIn("function hasTargetField(buf, depth, start, end)", optimized)
            self.assertIn("const out = hasTargetField(bytes, 0) ? renameField(bytes, 0,", optimized)
            self.assertEqual(optimize_spotify_nested_script(optimized, kind), optimized)

    @unittest.skipUnless(shutil.which("node"), "Node.js is required for Spotify binary runtime tests")
    def test_spotify_search_and_scroll_noop_preflight_avoids_subarray_views(self):
        import json
        import subprocess
        import tempfile
        root = Path(__file__).parent / "scripts" / "spotify"
        def varint(value):
            out = bytearray()
            while value >= 128:
                out.append((value & 127) | 128)
                value >>= 7
            out.append(value)
            return bytes(out)
        def field(number, payload):
            return varint(number * 8 + 2) + varint(len(payload)) + payload
        clean = field(1, field(2, b"clean"))
        cases = (
            ("spot-NoSearchAd.js", "search", field(6, b"x" * 12001)),
            ("spot-NoScrollAd.js", "scroll", field(30, b"x")),
        )
        runner = r"""
const fs = require("fs"), vm = require("vm"), payload = JSON.parse(fs.readFileSync(0, "utf8"));
const source = fs.readFileSync(process.argv[1], "utf8");
let result, subarrayCount = 0;
const native = Uint8Array.prototype.subarray;
Uint8Array.prototype.subarray = function(...args) { subarrayCount++; return native.apply(this,args); };
const context = { Uint8Array, $response:{body:Uint8Array.from(payload.body)}, $done(v){result=v;}, console:{log(){}} };
vm.createContext(context); vm.runInContext(source,context,{timeout:3000});
process.stdout.write(JSON.stringify({result: result && result.body ? Array.from(result.body) : null, subarrayCount, empty: !!result && Object.keys(result).length===0}));
"""
        with tempfile.TemporaryDirectory() as tmp:
            for filename, kind, ad_field in cases:
                source = (root / filename).read_text(encoding="utf-8")
                script = Path(tmp) / filename
                script.write_text(source, encoding="utf-8")
                completed = subprocess.run([shutil.which("node"), "-e", runner, str(script)],
                    input=json.dumps({"body": list(clean)}), text=True, capture_output=True, check=True, timeout=10)
                no_op = json.loads(completed.stdout)
                self.assertTrue(no_op["empty"])
                self.assertEqual(no_op["subarrayCount"], 0)
                changed = field(1, ad_field)
                completed = subprocess.run([shutil.which("node"), "-e", runner, str(script)],
                    input=json.dumps({"body": list(changed)}), text=True, capture_output=True, check=True, timeout=10)
                changed_result = json.loads(completed.stdout)
                self.assertIsNotNone(changed_result["result"])
                self.assertGreater(changed_result["subarrayCount"], 0)


if __name__ == "__main__":
    unittest.main()
