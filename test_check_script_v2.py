#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import unittest
from check_script_v2 import inspect_text

class ScriptV2GuardTests(unittest.TestCase):
    def test_dynamic_argument_interpolation_is_valid(self):
        text = """[Argument]
quda_enable = switch,true,false
[Script]
response if ${url} ~= /^https:\/\/example\.com/ then script("https://example.com/a.js") with enable=${quda_enable}
"""
        self.assertEqual(inspect_text(text), [])

    def test_boolean_literals_are_valid(self):
        text = """[Script]
response then script("https://example.com/a.js") with enable=true
response then script("https://example.com/b.js") with enable=false
"""
        self.assertEqual(inspect_text(text), [])

    def test_bare_dynamic_identifier_is_rejected(self):
        text = """[Script]
response then script("https://example.com/a.js") with enable=quda_enable
"""
        errors = inspect_text(text, "fixture.plugin")
        self.assertEqual(len(errors), 1)
        self.assertIn("fixture.plugin:2", errors[0])
        self.assertIn("enable=${quda_enable}", errors[0])

    def test_atomic_group_is_rejected_only_in_config_sections(self):
        text = """[Argument]
note = (?>this is ordinary text)
[Script]
response if ${url} ~= /(?>ads)/ then script("https://example.com/a.js")
[Rewrite]
^https://example.com/(?>ads) - reject
"""
        errors = inspect_text(text)
        self.assertEqual(len(errors), 2)
        self.assertTrue(all("atomic regex group" in item for item in errors))

    def test_non_script_sections_are_not_scanned(self):
        text = """[Rule]
DOMAIN,example.com,REJECT
[Argument]
enable = quda_enable
"""
        self.assertEqual(inspect_text(text), [])

if __name__ == "__main__":
    unittest.main()
