import unittest
from fix_script_configs import repair_plugin_text

class ScriptConfigRepairTests(unittest.TestCase):
    def test_converts_legacy_argument_lists_to_plugin_objects(self):
        source = '[Argument]\nenabled = switch,true,false,tag=启用\nregion = select,"CN","US",tag=地区\n\n[Script]\nhttp-request ^https://example.com script-path=request.js,argument=[{enabled},{region}],tag=Test\ncron "0 * * * *" script-path=cron.js,argument=[{region}],tag=Cron\n'
        repaired, counts = repair_plugin_text(source)
        self.assertIn("argument={enabled,region}", repaired)
        self.assertIn("argument={region}", repaired)
        self.assertEqual(counts["legacy_argument_lists"], 2)

    def test_repairs_maasea_argument_keys(self):
        source = '[Argument]\n屏蔽上传按钮=switch,"true","false",tag=屏蔽上传按钮, desc=屏蔽上传按钮\n屏蔽选段按钮=switch,"true","false",tag=屏蔽选段按钮, desc=屏蔽选段按钮\n屏蔽Shorts按钮=switch,"false","true",tag=屏蔽Shorts按钮, desc=屏蔽Shorts按钮\n字幕翻译语言=input,off,tag=字幕翻译语言, desc=字幕翻译语言\n启用调试模式=switch,"false","true",tag=启用调试模式, desc=启用调试模式\n\n[Script]\nhttp-response ^https://youtubei.googleapis.com/ script-path=https://example/Maasea_youtube.response.js, requires-body=true, argument="{"captionLang":"{字幕翻译语言}"}"\nhttp-request ^https://googlevideo.com/ script-path=https://example/Maasea_youtube.request.js, requires-body=true, argument="{"captionLang":"{字幕翻译语言}"}"\n'
        repaired, counts = repair_plugin_text(source)
        self.assertIn("blockUpload=switch,true,false,tag=屏蔽上传按钮, desc=屏蔽上传按钮", repaired)
        self.assertIn("blockImmersive=switch,true,false,tag=屏蔽选段按钮, desc=屏蔽选段按钮", repaired)
        self.assertIn("blockShorts=switch,false,true,tag=屏蔽Shorts按钮, desc=屏蔽Shorts按钮", repaired)
        self.assertIn("captionLang=input,off,tag=字幕翻译语言, desc=字幕翻译语言", repaired)
        self.assertIn("debug=switch,false,true,tag=启用调试模式, desc=启用调试模式", repaired)
        self.assertIn("argument={captionLang,blockUpload,blockImmersive,blockShorts,debug}", repaired)
        self.assertIn("argument={captionLang}", repaired)
        self.assertEqual(counts["maasea_response"], 1)
        self.assertEqual(counts["maasea_request"], 1)

    def test_boolean_normalization_and_idempotence(self):
        source = "[Script]\nhttp-response ^https://example.com script-path=x.js,requires-body=1\n"
        repaired, counts = repair_plugin_text(source)
        self.assertIn("requires-body=true", repaired)
        self.assertEqual(counts["requires_body_boolean"], 1)
        self.assertEqual(repair_plugin_text(repaired)[0], repaired)

    def test_plain_string_arguments_are_unchanged(self):
        source = '[Script]\ngeneric script-path=x.js,argument="hello"\n'
        repaired, counts = repair_plugin_text(source)
        self.assertEqual(repaired, source)
        self.assertEqual(counts["legacy_argument_lists"], 0)

    def test_repairs_all_bare_script_enable_identifiers_and_is_idempotent(self):
        from check_script_v2 import inspect_text

        source = (
            "[Script]\n"
            "response if ${url} ~= /^https?:\\/\\/a.example/ then script(\"a.js\") with enable=quda_enable, tag=\"A\"\n"
            "response if ${url} ~= /^https?:\\/\\/b.example/ then script(\"b.js\") with enable=whyiyzdccidm_enable, tag=\"B\"\n"
            "response if ${url} ~= /^https?:\\/\\/c.example/ then script(\"c.js\") with enable=vhuhgsjn_enable, tag=\"C\"\n"
            "response if ${url} ~= /^https?:\\/\\/d.example/ then script(\"d.js\") with enable=aiqiyi_enable, tag=\"D\"\n"
            + "".join(
                f'response if ${{url}} ~= /^https?:\\/\\/mgtv{i}.example/ then script("mgtv.js") with enable=mhgotv_enable, tag="MGTV {i}"\n'
                for i in range(7)
            )
            + "response if ${url} ~= /^https?:\\/\\/bool.example/ then script(\"bool.js\") with enable=true\n"
            + "response if ${url} ~= /^https?:\\/\\/dynamic.example/ then script(\"dynamic.js\") with enable=${already_enable}\n"
            + "[Rewrite]\n^https://rewrite.example enable=leave_this_alone\n"
        )
        repaired, counts = repair_plugin_text(source)
        self.assertEqual(counts["bare_enable_variables"], 11)
        self.assertIn("enable=${quda_enable}", repaired)
        self.assertIn("enable=${mhgotv_enable}", repaired)
        self.assertIn("enable=true", repaired)
        self.assertIn("enable=${already_enable}", repaired)
        self.assertIn("enable=leave_this_alone", repaired)
        self.assertEqual(inspect_text(repaired), [])
        repaired_again, second_counts = repair_plugin_text(repaired)
        self.assertEqual(repaired_again, repaired)
        self.assertEqual(second_counts["bare_enable_variables"], 0)

if __name__ == "__main__":
    unittest.main()
