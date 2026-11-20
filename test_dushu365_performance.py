import unittest
from pathlib import Path

from optimize_dushu365 import EXPECTED_TRIGGERS, LOCAL, REMOTE, rewrite_plugin

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / "scripts" / "dushu365" / "dushu365.js"


class Dushu365OptimizerTests(unittest.TestCase):
    def test_local_runtime_has_five_routes_and_keeps_encryption_support(self):
        source = RUNTIME.read_text(encoding="utf-8")
        self.assertEqual(source.count("pathname.includes("), EXPECTED_TRIGGERS)
        self.assertIn("base64.decode", source)
        self.assertIn("utf8.decode", source)
        self.assertIn("base64.encode", source)
        self.assertIn("utf8.encode", source)
        self.assertNotIn(".filter(", source)
        self.assertNotIn(".map(", source)
        self.assertIn("if (changed)", source)
        self.assertIn("if (!route || ($response.status ?? $request.statusCode) !== 200)", source)

    def test_five_response_hooks_migrate_exactly_and_fail_closed(self):
        fixture = "[Script]\n" + "\n".join(
            "http-response ^https://g%d.dushu365.com/api script-path=%s,tag=DUSHU365-%d,requires-body=true"
            % (index, REMOTE, index)
            for index in range(EXPECTED_TRIGGERS)
        ) + "\n[MITM]\nhostname = g.dushu365.com\n"
        migrated = rewrite_plugin(fixture)
        self.assertEqual(migrated.count(LOCAL), EXPECTED_TRIGGERS)
        self.assertNotIn(REMOTE, migrated)
        self.assertEqual(rewrite_plugin(migrated), migrated)
        partial = "\n".join(line for line in fixture.splitlines() if "tag=DUSHU365-4," not in line)
        with self.assertRaisesRegex(ValueError, "expected 5"):
            rewrite_plugin(partial)
        mixed = fixture + "\nhttp-response ^https://g.dushu365.com/other script-path=" + LOCAL
        with self.assertRaisesRegex(ValueError, "mixed local and remote"):
            rewrite_plugin(mixed)


if __name__ == "__main__":
    unittest.main()
