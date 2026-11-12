#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path
from integrate_spotify import integrate


SOURCE = r"""#!name=Spotify
[Argument]
hide_ai_dj = switch,true
[Rule]
AND,((DOMAIN-SUFFIX, spotify.com), (PROTOCOL, QUIC)),REJECT
DOMAIN,aet.spotify.com,REJECT
[Rewrite]
^https:\/\/(?:spclient\.wg|[\w-]+-spclient)\.spotify\.com(?::443)?\/(?:ads\/|ad-logic\/|[^?#]*\/ad-on-app-open) reject
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
    def test_extracts_only_ad_features_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "Spotify.lpx"
            source.write_text(SOURCE, encoding="utf-8")
            source_scripts = root / "upstream"
            source_scripts.mkdir()
            for name in ("spot-gabo.js", "spot-NoSearchAd.js", "spot-NoHomeAd.js", "spot-NoScrollAd.js"):
                (source_scripts / name).write_text("// upstream script\n" + "x" * 200, encoding="utf-8")
            plugin = root / "allAdRewrite.plugin"
            plugin.write_text("[Rule]\n[Rewrite]\n[Script]\n[MITM]\nhostname = example.com\n", encoding="utf-8")
            meta = root / "upstream.json"
            integrate(plugin, source, source_scripts, root / "scripts", "abc123", meta)
            first = plugin.read_text(encoding="utf-8")
            integrate(plugin, source, source_scripts, root / "scripts", "abc123", meta)
            second = plugin.read_text(encoding="utf-8")
            self.assertEqual(first, second)
            self.assertIn("DOMAIN,aet.spotify.com,REJECT", second)
            self.assertIn(r"ads\\/|ad-logic\\/", second)
            self.assertNotIn("premium-marketing", second)
            self.assertNotIn("spot-proto-ev3", second)
            self.assertIn("scripts/spotify/spot-NoHomeAd.js", second)
            self.assertIn("*spclient.spotify.com", second)
            self.assertEqual(len(list((root / "scripts").glob("*.js"))), 4)


if __name__ == "__main__":
    unittest.main()
