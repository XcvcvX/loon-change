import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from optimize_weibo_rstore import LOCAL, REMOTE, MARKER, LAZY_MARKER, GUARD_DECLARATION, HELPER, LEGACY_HELPER, optimize_source, rewrite_plugin, optimize_page_filter_cached_itemid, TOPIC_GROUP_MARKER, optimize_topic_group_in_place, COMMENT_DATA_CACHE_MARKER, COMMENT_DATA_CACHE_OLD, COMMENT_DATA_CACHE_NEW, optimize_comment_data_reference_cache, REMOVE_AVATAR_USER_CACHE_MARKER, COMMENT_USER_CACHE_MARKER, COMMENT_USER_CACHE_OLD, COMMENT_USER_CACHE_NEW, optimize_comment_user_reference_cache, TOPIC_GROUP_NESTED_DATA_MARKER, optimize_topic_group_nested_data_cache, ROOT_COMMENT_USER_CACHE_MARKER, optimize_root_comment_user_cache, REMOVE_AVATAR_PROPERTY_CACHE_MARKER, optimize_remove_avatar_property_cache, COMMENT_DECORATION_SINGLE_READ_MARKER, ROOT_COMMENT_DECORATION_SINGLE_READ_MARKER, REPLY_DECORATION_SINGLE_READ_MARKER, ROOT_COMMENT_BUBBLE_SINGLE_READ_MARKER, optimize_comment_decoration_single_read

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "scripts/weibo/weibo-rstore.js"
NODE = shutil.which("node")


class RStoreWeiboOptimizerTests(unittest.TestCase):
    def test_generated_script_is_marked_and_idempotent(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(MARKER, source)
        self.assertIn(LAZY_MARKER, source)
        self.assertIn('let modified = !url.includes("/2/cardlist") && !url.includes("/2/comments/build_comments");', source)
        self.assertIn('$done(modified ? {body: JSON.stringify(obj)} : {});', source)
        self.assertEqual(optimize_source(source), source)
        self.assertEqual(len(re.findall(r"const __loonSource\d+ =", source)), 32)
        self.assertEqual(len(re.findall(r"(?m)^\s*const __loonLength\d+ = __loonSource\d+\.length;$", source)), 32)
        self.assertNotRegex(source, r"for \(let __loonRead\d+ = 0, __loonLength\d+")
        self.assertNotRegex(source, r"\[[^\]\n]+\]\??\.includes\(")
        remaining = re.findall(r"\b(new[A-Za-z0-9_]*)\s*=\s*\[\s*\]", source)
        self.assertEqual(sorted(remaining), ["newActions"])
        self.assertIn("compactInPlace(obj.elements", source)
        self.assertIn("compactInPlace(obj.user_list", source)
        self.assertIn("compactInPlace(obj.cards", source)
        self.assertNotIn("obj.elements = obj.elements.filter(", source)
        self.assertNotIn("obj.user_list = obj.user_list.filter(", source)
        self.assertNotIn("obj.channelInfo.channel_list = obj.channelInfo.channel_list.filter(", source)

    def test_hot_loop_membership_uses_scalar_comparisons(self):
        source = SCRIPT.read_text(encoding="utf-8")
        marker = "// loon-change: Weibo hot-loop scalar membership v1"
        self.assertEqual(source.count(marker), 1)
        self.assertEqual(optimize_source(source), source)
        self.assertNotRegex(source, r"\[[^\]\n]+\]\??\.includes\(")
        self.assertIn("cardType === 120 || cardType === 145 || cardType === 192", source)
        self.assertIn("item?.data?.card_type === 19 || item?.data?.card_type === 118", source)
        self.assertIn("!(item?.data?.card_type === 4 || item?.data?.card_type === 197", source)


    def test_page_filter_caches_repeated_itemid_property_reads(self):
        source = SCRIPT.read_text(encoding="utf-8")
        marker = "// loon-change: Weibo /2/page cached itemid reads v1"
        self.assertEqual(source.count(marker), 1)
        self.assertEqual(optimize_page_filter_cached_itemid(source), source)
        self.assertIn("const itemId = c?.itemid;", source)
        self.assertIn("const itemId = i.itemid;", source)
        self.assertEqual(source.count("i.itemid?.includes("), 0)
        self.assertEqual(source.count("c?.itemid?.includes("), 0)
        damaged = source.replace("const itemId = i.itemid;", "const cachedItemId = i.itemid;", 1)
        with self.assertRaisesRegex(ValueError, "transformed block missing"):
            optimize_page_filter_cached_itemid(damaged)

    def test_topic_group_compaction_is_in_place_idempotent_and_fails_closed(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(optimize_topic_group_in_place(source), source)
        self.assertEqual(source.count(TOPIC_GROUP_MARKER), 1)
        self.assertIn("const groupItems = item.items;", source)
        self.assertIn("const groupLength = groupItems.length;", source)
        self.assertIn("groupItems.length = groupWrite;", source)
        self.assertNotIn("let newII = [];", source)
        self.assertNotIn("item.items = newII;", source)
        damaged = source.replace("const groupItems = item.items;", "const groupItems = undefined;", 1)
        with self.assertRaisesRegex(ValueError, "marker/structure drift"):
            optimize_topic_group_in_place(damaged)


    def test_nested_topic_group_data_references_are_cached(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(optimize_topic_group_nested_data_cache(source), source)
        self.assertEqual(source.count(TOPIC_GROUP_NESTED_DATA_MARKER), 1)
        self.assertIn("const nestedItems = item?.items;", source)
        self.assertIn("const nestedLength = nestedItems.length;", source)
        self.assertIn("const iiData = ii?.data;", source)
        self.assertIn("const commonStruct = iiData.common_struct;", source)
        self.assertNotIn("for (let ii of item.items)", source)
        self.assertNotIn("removeAvatar(ii?.data)", source)
        damaged = source.replace("const iiData = ii?.data;", "const iiData = undefined;", 1)
        with self.assertRaisesRegex(ValueError, "data-cache structure drift"):
            optimize_topic_group_nested_data_cache(damaged)


    def test_root_comment_user_reference_is_cached_once(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(optimize_root_comment_user_cache(source), source)
        self.assertEqual(source.count(ROOT_COMMENT_USER_CACHE_MARKER), 1)
        self.assertIn("const commentUser = item.user;", source)
        self.assertIn("removeAvatar(item, commentUser);", source)
        self.assertIn("const commentUserName = commentUser.name;", source)
        self.assertNotIn('item?.user?.name === "超话社区"', source)
        damaged = source.replace("const commentUser = item.user;", "const commentUser = null;", 1)
        with self.assertRaisesRegex(ValueError, "user-cache structure drift"):
            optimize_root_comment_user_cache(damaged)


    def test_comment_decoration_optimizer_is_idempotent_and_fails_closed(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(optimize_comment_decoration_single_read(source), source)
        for marker in (
            COMMENT_DECORATION_SINGLE_READ_MARKER,
            ROOT_COMMENT_DECORATION_SINGLE_READ_MARKER,
            REPLY_DECORATION_SINGLE_READ_MARKER,
            ROOT_COMMENT_BUBBLE_SINGLE_READ_MARKER,
        ):
            self.assertEqual(source.count(marker), 1)
        for token in (
            "const commentBubble = commentData?.comment_bubble;",
            "const commentBulletMessage = commentData?.comment_bullet_screens_message;",
            "const commentHotIcon = commentData?.hot_icon;",
            "const commentVipButton = commentData?.vip_button;",
            "const rootCommentBubble = item?.comment_bubble;",
            "const replyUser = item?.user;",
            "const replyComment = item?.reply_comment;",
            "const rootComment = obj?.rootComment;",
        ):
            self.assertIn(token, source)
        damaged = source.replace("const commentBubble = commentData?.comment_bubble;", "const commentBubble = null;", 1)
        with self.assertRaisesRegex(ValueError, "structure drift"):
            optimize_comment_decoration_single_read(damaged)

    def test_remove_avatar_properties_are_read_once_before_deletion(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(REMOVE_AVATAR_PROPERTY_CACHE_MARKER, source)
        self.assertEqual(optimize_remove_avatar_property_cache(source), source)
        for token in (
            "const blockCardBg = data?.block_card_bg;",
            "const buttons = data?.buttons;",
            "const cardId = data?.cardid;",
            "const icons = data?.icons;",
            "const mblogButtons = data?.mblog_buttons;",
            "const picBgNew = data?.pic_bg_new;",
            "const avatarGjId = user?.avatargj_id;",
            "const avatarExtendInfo = user?.avatar_extend_info;",
            "const userCardId = user?.cardid;",
            "const userIcons = user?.icons;",
            "const memberType = user?.mbtype;",
        ):
            self.assertIn(token, source)
        damaged = source.replace("const buttons = data?.buttons;", "const buttons = null;", 1)
        with self.assertRaisesRegex(ValueError, "single-read cache structure drift"):
            optimize_remove_avatar_property_cache(damaged)

    def test_profile_timeline_caches_nested_data_references_once(self):
        from optimize_weibo_rstore import PROFILE_TIMELINE_DATA_CACHE_MARKER, optimize_profile_timeline_data_cache
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(PROFILE_TIMELINE_DATA_CACHE_MARKER, source)
        self.assertEqual(optimize_profile_timeline_data_cache(source), source)
        start = source.index('} else if (url.includes("/2/profile/container_timeline")) {')
        end = source.index('} else if (url.includes("/2/profile/dealatt")', start)
        block = source[start:end]
        self.assertIn("const itemData = item?.data;", block)
        self.assertIn("const iiData = ii?.data;", block)
        self.assertNotIn("item?.data", block.replace("const itemData = item?.data;", ""))
        self.assertNotIn("ii?.data", block.replace("const iiData = ii?.data;", ""))
        self.assertNotIn("ii.data", block.replace("const iiData = ii?.data;", ""))
        damaged = source.replace("const itemData = item?.data;", "const cachedItemData = item?.data;", 1)
        with self.assertRaisesRegex(ValueError, "marker/structure drift"):
            optimize_profile_timeline_data_cache(damaged)

    def test_comment_loop_caches_data_reference_once_and_fails_closed(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(source.count(COMMENT_DATA_CACHE_MARKER), 1)
        self.assertEqual(optimize_comment_data_reference_cache(source), source)
        self.assertIn("const commentData = item?.data;", source)
        self.assertIn("if (!isAd(commentData))", source)
        self.assertIn("removeAvatar(commentData, commentUser);", source)
        self.assertNotIn(COMMENT_DATA_CACHE_OLD, source)
        damaged = source.replace("const commentData = item?.data;", "const cachedCommentData = item?.data;", 1)
        with self.assertRaisesRegex(ValueError, "marker/structure drift"):
            optimize_comment_data_reference_cache(damaged)

    def test_comment_user_reference_cache_is_idempotent_and_fails_closed(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(optimize_comment_user_reference_cache(source), source)
        self.assertIn(REMOVE_AVATAR_USER_CACHE_MARKER, source)
        self.assertIn(COMMENT_USER_CACHE_MARKER, source)
        self.assertIn("function removeAvatar(data, user = data?.user)", source)
        self.assertIn("removeAvatar(commentData, commentUser);", source)
        self.assertIn("const commentUserName = commentUser.name;", source)

        damaged_helper = source.replace("if (user?.avatargj_id)", "if (data?.user?.avatargj_id)", 1)
        with self.assertRaisesRegex(ValueError, "removeAvatar user-cache marker/structure drift"):
            optimize_comment_user_reference_cache(damaged_helper)

        damaged_comment = source.replace("const commentUserName = commentUser.name;", "const commentUserName = commentUser.username;", 1)
        with self.assertRaisesRegex(ValueError, "comment user-cache marker/structure drift"):
            optimize_comment_user_reference_cache(damaged_comment)

    def test_comment_cache_transform_applies_to_unoptimized_source(self):
        source = SCRIPT.read_text(encoding="utf-8")
        legacy = source.replace(COMMENT_USER_CACHE_NEW, COMMENT_USER_CACHE_OLD, 1)
        legacy = legacy.replace(COMMENT_DATA_CACHE_NEW, COMMENT_DATA_CACHE_OLD, 1)
        self.assertNotEqual(legacy, source)
        rebuilt = optimize_comment_user_reference_cache(optimize_comment_data_reference_cache(legacy))
        self.assertEqual(rebuilt, source)

    def test_old_optimized_snapshot_regains_lazy_serialization_guard(self):
        source = SCRIPT.read_text(encoding="utf-8")
        legacy = source.replace(LAZY_MARKER + "\n", "", 1)
        legacy = legacy.replace(GUARD_DECLARATION + "\n", "", 1)
        legacy = legacy.replace(HELPER, LEGACY_HELPER, 1)
        legacy = re.sub(r"(?m)^([ \t]*)if \(__loonWrite\d+ !== __loonLength\d+\) modified = true;\n", "", legacy)
        legacy = re.sub(r"(?m)^([ \t]*)modified = true;\n([ \t]*delete .+;)$", r"\2", legacy)
        legacy = legacy.replace("$done(modified ? {body: JSON.stringify(obj)} : {});", "$done({body: JSON.stringify(obj)});", 1)
        rebuilt = optimize_source(legacy)
        self.assertIn(LAZY_MARKER, rebuilt)
        self.assertIn(COMMENT_DATA_CACHE_MARKER, rebuilt)
        self.assertIn(GUARD_DECLARATION, rebuilt)
        self.assertIn("delete commentData.comment_bubble;", rebuilt)
        self.assertEqual(optimize_source(rebuilt), rebuilt)

    def test_exactly_ten_live_rstore_triggers_are_routed_to_local_script(self):
        plugin = (ROOT / "allAdRewrite.plugin").read_text(encoding="utf-8")
        self.assertEqual(plugin.count(REMOTE), 0)
        self.assertEqual(plugin.count(LOCAL), 10)
        routed = rewrite_plugin(plugin)
        self.assertEqual(routed.count(LOCAL), 10)
        self.assertNotIn(REMOTE, routed)
        self.assertEqual(rewrite_plugin(routed), routed)

    def test_trigger_count_drift_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "expected 10"):
            rewrite_plugin("[Script]\nhttp-response ^https://example.invalid script-path=" + REMOTE + "\n")


@unittest.skipUnless(NODE, "Node.js is required for Weibo runtime regression tests")
class RStoreWeiboRuntimeTests(unittest.TestCase):
    def run_script(self, url, body):
        runner = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
let doneResult;
let parseCount = 0, stringifyCount = 0;
const nativeParse = JSON.parse.bind(JSON);
const nativeStringify = JSON.stringify.bind(JSON);
const trackedJSON = {
  parse(value) { parseCount++; return nativeParse(value); },
  stringify(value) { stringifyCount++; return nativeStringify(value); }
};
const context = {
  JSON: trackedJSON,
  $request: {url: payload.url},
  $response: {body: JSON.stringify(payload.body)},
  $done(value) { doneResult = value; },
  console: {log() {}, warn() {}, error() {}}
};
vm.runInNewContext(source, context, {timeout: 5000});
process.stdout.write(JSON.stringify({doneResult, parseCount, stringifyCount}));
"""
        completed = subprocess.run(
            [NODE, "-e", runner, str(SCRIPT)],
            input=json.dumps({"url": url, "body": body}),
            capture_output=True, text=True, check=False, timeout=10
        )
        if completed.returncode:
            raise AssertionError(
                "Node VM failed (exit %s):\\n%s\\nstdout:\\n%s"
                % (completed.returncode, completed.stderr, completed.stdout)
            )
        return json.loads(completed.stdout)

    def test_cardlist_nested_arrays_compact_in_place_without_changing_order(self):
        body = {"cards": [
            {"card_group": [
                {"card_type": 120},
                {"card_type": 1, "mblog": {"buttons": [{"type": "follow"}]}}
            ]},
            {"card_type": 17},
            {"card_type": 2, "mblog": {"buttons": [{"type": "follow"}]}}
        ]}
        result = self.run_script("https://api.weibo.cn/2/cardlist?containerid=fixture", body)
        output = json.loads(result["doneResult"]["body"])
        self.assertEqual(len(output["cards"]), 2)
        self.assertEqual([g["card_type"] for g in output["cards"][0]["card_group"]], [1])
        self.assertNotIn("buttons", output["cards"][0]["card_group"][0]["mblog"])
        self.assertNotIn("buttons", output["cards"][1]["mblog"])
        self.assertEqual(result["parseCount"], 1)
        self.assertEqual(result["stringifyCount"], 1)


    def test_search_page_filters_preserve_order_and_ads_semantics(self):
        body = {"cards": [
            {"itemid": "keep-group", "card_group": [
                {"itemid": "normal"},
                {"itemid": "t:51:banner"},
                {"actionlog": {"ext": "ads_word"}, "itemid": "normal-2"},
                {"itemid": "ads_word"}
            ]},
            {"itemid": "feed_-_invite:1"},
            {"itemid": "infeed_friends_recommend:1"},
            {"itemid": "infeed_may_interest_in:1"},
            {"itemid": "infeed_pagemanual3:1"},
            {"itemid": "infeed_weibo_mall:1"},
            {"itemid": "normal-card", "mblog": {"mblogtypename": "广告"}},
            {"itemid": "keep-1"},
            {"itemid": "keep-2"}
        ]}
        result = self.run_script("https://api.weibo.cn/2/page?containerid=fixture", body)
        output = json.loads(result["doneResult"]["body"])
        self.assertEqual([item["itemid"] for item in output["cards"]], ["keep-group", "keep-1", "keep-2"])
        self.assertEqual([item["itemid"] for item in output["cards"][0]["card_group"]], ["normal"])

    def test_comment_decoration_properties_are_read_once(self):
        runner = r"""
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync(process.argv[1],"utf8");
const payload=JSON.parse(fs.readFileSync(0,"utf8"));
let doneResult,tracking=false;
const nativeParse=JSON.parse.bind(JSON),nativeStringify=JSON.stringify.bind(JSON);
const counts=Object.create(null);
const trackedJSON={
  parse(value){
    const parsed=nativeParse(value);
    const wrap=(target,key,label)=>{
      if(!target)return;
      let current=target[key]; counts[label]=0;
      Object.defineProperty(target,key,{enumerable:true,configurable:true,
        get(){if(tracking)counts[label]++;return current;},set(value){current=value;}});
    };
    if(parsed.datas)for(const entry of parsed.datas)if(entry?.data){
      for(const key of ["comment_bubble","comment_bullet_screens_message","hot_icon","vip_button"])wrap(entry.data,key,"datas."+key);
    }
    if(parsed.root_comments)for(const item of parsed.root_comments)if(item){
      for(const key of ["comment_bubble","comment_bullet_screens_message","hot_icon","vip_button"])wrap(item,key,"root."+key);
    }
    if(parsed.comments)for(const item of parsed.comments)if(item){
      if(item.user)wrap(item.user,"icons","reply.user.icons");
      if(item.reply_comment)wrap(item.reply_comment,"comment_badge","reply.comment_badge");
    }
    if(parsed.rootComment)wrap(parsed.rootComment,"comment_bubble","rootComment.comment_bubble");
    tracking=true;
    return parsed;
  },
  stringify(value){tracking=false;return nativeStringify(value);}
};
const context={JSON:trackedJSON,$request:{url:payload.url},$response:{body:nativeStringify(payload.body)},
  $done(value){doneResult=value;},console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,context,{timeout:5000});
process.stdout.write(nativeStringify({doneResult,counts}));
""";
        cases = [
            ("https://api.weibo.cn/2/comments/build_comments?fixture=read-count", {"datas": [
                {"type": 1, "data": {"user": {"name": "ordinary"},
                    "comment_bubble": {"x": 1}, "comment_bullet_screens_message": {"x": 1},
                    "hot_icon": {"x": 1}, "vip_button": {"x": 1}}}
            ]}, {"datas.comment_bubble", "datas.comment_bullet_screens_message", "datas.hot_icon", "datas.vip_button"}),
            ("https://api.weibo.cn/2/comments/build_comments?fixture=root-read-count", {"root_comments": [
                {"user": {"name": "ordinary"}, "comment_bubble": {"x": 1},
                 "comment_bullet_screens_message": {"x": 1}, "hot_icon": {"x": 1}, "vip_button": {"x": 1}}
            ]}, {"root.comment_bubble", "root.comment_bullet_screens_message", "root.hot_icon", "root.vip_button"}),
            ("https://api.weibo.cn/2/comments/build_comments?fixture=reply-read-count", {"comments": [
                {"user": {"icons": [{"x": 1}]}, "reply_comment": {"comment_badge": {"x": 1}}}
            ]}, {"reply.user.icons", "reply.comment_badge"}),
            ("https://api.weibo.cn/2/comments/build_comments?fixture=root-comment-read-count", {"rootComment": {"comment_bubble": {"x": 1}}}, {"rootComment.comment_bubble"}),
        ]
        for url, body, expected_keys in cases:
            completed = subprocess.run(
                [NODE, "-e", runner, str(SCRIPT)],
                input=json.dumps({"url": url, "body": body}),
                capture_output=True, text=True, check=False, timeout=10
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(completed.stdout)
            self.assertEqual(set(result["counts"]), expected_keys)
            self.assertEqual(set(result["counts"].values()), {1})
            self.assertIn("doneResult", result)

    def test_comments_cleanup_keeps_only_allowed_items(self):
        body = {"datas": [
            {"data": {"mblogtypename": "广告"}},
            {"type": 1, "data": {
                "user": {"name": "普通用户", "icons": [{"type": "vip"}]},
                "comment_bubble": {"text": "x"},
                "comment_bullet_screens_message": {"text": "x"},
                "hot_icon": {"type": "hot"},
                "vip_button": {"text": "x"}
            }},
            {"type": 1, "data": {"user": {"name": "超话社区"}}},
            {"type": 6, "data": {"user": {"name": "普通用户"}}}
        ]}
        result = self.run_script("https://api.weibo.cn/2/comments/build_comments?flow=fixture", body)
        output = json.loads(result["doneResult"]["body"])
        self.assertEqual(len(output["datas"]), 1)
        kept = output["datas"][0]["data"]
        self.assertNotIn("icons", kept["user"])
        for key in ("comment_bubble", "comment_bullet_screens_message", "hot_icon", "vip_button"):
            self.assertNotIn(key, kept)
        self.assertEqual(result["parseCount"], 1)
        self.assertEqual(result["stringifyCount"], 1)


    def test_remove_avatar_reads_each_decoration_property_once(self):
        runner = r"""
const fs=require("fs"),vm=require("vm");
const source=fs.readFileSync(process.argv[1],"utf8"),payload=JSON.parse(fs.readFileSync(0,"utf8"));
let doneResult,tracking=false;
const dataKeys=["block_card_bg","buttons","cardid","icons","mblog_buttons","pic_bg_new"];
const userKeys=["avatargj_id","avatar_extend_info","cardid","icons","mbtype"];
const dataReads=Object.create(null),userReads=Object.create(null);
const nativeParse=JSON.parse.bind(JSON),nativeStringify=JSON.stringify.bind(JSON);
const trackedJSON={
  parse(value){
    const parsed=nativeParse(value);
    for(const entry of parsed.datas||[]){
      const data=entry?.data;
      if(!data)continue;
      const user=data.user;
      for(const key of dataKeys){
        let current=data[key];
        dataReads[key]=0;
        Object.defineProperty(data,key,{enumerable:true,configurable:true,get(){if(tracking)dataReads[key]++;return current;},set(value){current=value;}});
      }
      if(user){
        for(const key of userKeys){
          let current=user[key];
          userReads[key]=0;
          Object.defineProperty(user,key,{enumerable:true,configurable:true,get(){if(tracking)userReads[key]++;return current;},set(value){current=value;}});
        }
      }
    }
    tracking=true;
    return parsed;
  },
  stringify(value){tracking=false;return nativeStringify(value);}
};
const context={JSON:trackedJSON,$request:{url:payload.url},$response:{body:nativeStringify(payload.body)},$done(value){doneResult=value;},console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,context,{timeout:5000});
process.stdout.write(nativeStringify({doneResult,dataReads,userReads}));
""";
        constBody = {"datas": [{"type": 1, "data": {
            "user": {"name": "ordinary", "avatargj_id": "x", "avatar_extend_info": "x",
                     "cardid": "u", "icons": [{"type": "vip"}], "mbtype": 2},
            "block_card_bg": "x", "buttons": [{"type": "follow"}], "cardid": "d",
            "icons": [{"type": "x"}], "mblog_buttons": [{"type": "forward"}], "pic_bg_new": "x",
            "comment_bubble": {"text": "remove"}
        }}]}
        completed = subprocess.run(
            [NODE, "-e", runner, str(SCRIPT)],
            input=json.dumps({"url": "https://api.weibo.cn/2/comments/build_comments?fixture=remove-avatar-reads", "body": constBody}),
            capture_output=True, text=True, check=False, timeout=10
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        output = json.loads(result["doneResult"]["body"])
        self.assertEqual(len(output["datas"]), 1)
        self.assertEqual(set(result["dataReads"].values()), {1})
        self.assertEqual(set(result["userReads"].values()), {1})
        for key in ("block_card_bg", "buttons", "cardid", "icons", "mblog_buttons", "pic_bg_new"):
            self.assertNotIn(key, output["datas"][0]["data"])
        for key in ("avatargj_id", "avatar_extend_info", "cardid", "icons", "mbtype"):
            self.assertNotIn(key, output["datas"][0]["data"]["user"])

    def test_comment_user_and_name_accessors_are_read_once_per_comment(self):
        runner = r"""
const fs=require("fs"),vm=require("vm");
const source=fs.readFileSync(process.argv[1],"utf8"),payload=JSON.parse(fs.readFileSync(0,"utf8"));
let doneResult,trackReads=false,userReads=0,nameReads=0;
const nativeParse=JSON.parse.bind(JSON),nativeStringify=JSON.stringify.bind(JSON);
const trackedJSON={
  parse(value){
    const parsed=nativeParse(value);
    for(const entry of parsed.datas||[]){
      const data=entry?.data;
      if(!data||!data.user)continue;
      let user=data.user;
      Object.defineProperty(data,"user",{enumerable:true,configurable:true,get(){if(trackReads)userReads++;return user;},set(value){user=value;}});
      let name=user.name;
      Object.defineProperty(user,"name",{enumerable:true,configurable:true,get(){if(trackReads)nameReads++;return name;},set(value){name=value;}});
    }
    userReads=0;nameReads=0;trackReads=true;
    return parsed;
  },
  stringify(value){trackReads=false;return nativeStringify(value);}
};
const context={JSON:trackedJSON,$request:{url:payload.url},$response:{body:nativeStringify(payload.body)},$done(value){doneResult=value;},console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,context,{timeout:5000});
process.stdout.write(nativeStringify({doneResult,userReads,nameReads}));
"""
        body = {"datas": [
            {"type": 1, "data": {"user": {
                "name": "普通用户", "avatargj_id": "x", "avatar_extend_info": "x",
                "cardid": "x", "icons": [{"type": "vip"}], "mbtype": 2
            }, "comment_bubble": {"text": "remove"}}},
            {"type": 1, "data": {"user": {
                "name": "超话社区", "avatargj_id": "y", "icons": [{"type": "vip"}]
            }, "text": "filtered"}}
        ]}
        completed = subprocess.run(
            [NODE, "-e", runner, str(SCRIPT)],
            input=json.dumps({"url": "https://api.weibo.cn/2/comments/build_comments?fixture=reads", "body": body}),
            capture_output=True, text=True, check=False, timeout=10
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        output = json.loads(result["doneResult"]["body"])
        self.assertEqual(len(output["datas"]), 1)
        user = output["datas"][0]["data"]["user"]
        for key in ("avatargj_id", "avatar_extend_info", "cardid", "icons", "mbtype"):
            self.assertNotIn(key, user)
        self.assertNotIn("comment_bubble", output["datas"][0]["data"])
        self.assertEqual(result["userReads"], 2)
        self.assertEqual(result["nameReads"], 2)

    def test_clean_cardlist_and_comments_skip_response_serialization(self):
        cardlist = {"cards": [
            {"card_group": [{"card_type": 1, "mblog": {"id": "keep-1"}}]},
            {"card_type": 2, "mblog": {"id": "keep-2"}}
        ]}
        result = self.run_script("https://api.weibo.cn/2/cardlist?containerid=clean", cardlist)
        self.assertEqual(result["doneResult"], {})
        self.assertEqual(result["parseCount"], 1)
        self.assertEqual(result["stringifyCount"], 0)

        comments = {"datas": [
            {"type": 1, "data": {"user": {"name": "普通用户"}, "text": "keep"}}
        ]}
        result = self.run_script("https://api.weibo.cn/2/comments/build_comments?flow=clean", comments)
        self.assertEqual(result["doneResult"], {})
        self.assertEqual(result["parseCount"], 1)
        self.assertEqual(result["stringifyCount"], 0)

    def test_other_response_routes_keep_legacy_serialization(self):
        result = self.run_script("https://api.weibo.cn/2/checkin/show", {})
        self.assertEqual(result["parseCount"], 1)
        self.assertEqual(result["stringifyCount"], 1)
        self.assertIn("body", result["doneResult"])

    def test_hot_timeline_compaction_preserves_feed_order(self):
        body = {
            "items": [
                {"category": "feed", "data": {"id": "keep-1"}},
                {"category": "feed", "data": {"mblogtypename": "广告"}},
                {"category": "card", "data": {"id": "drop-card"}},
                {"category": "feed", "data": {"id": "keep-2"}}
            ],
            "statuses": [
                {"id": "drop-ad", "mblogtypename": "广告"},
                {"id": "keep-status"}
            ],
            "ad": {"x": 1},
            "trends": [{"x": 1}]
        }
        result = self.run_script("https://api.weibo.cn/2/statuses/container_timeline_hot?refresh=1", body)
        output = json.loads(result["doneResult"]["body"])
        self.assertEqual([x["data"].get("id") for x in output["items"]], ["keep-1", "keep-2"])
        self.assertEqual([x["id"] for x in output["statuses"]], ["keep-status"])
        self.assertNotIn("ad", output)
        self.assertNotIn("trends", output)

    def test_topic_group_top_items_compact_in_place_preserving_order_and_hotwords(self):
        body = {"items": [{
            "category": "group",
            "itemId": None,
            "items": [
                {"data": {"itemid": "mine_topics_1", "buttons": [{"type": "follow"}]}},
                {"data": {"itemid": "tab_search_input", "hotwords": [{"word": "old"}], "icons": [{"type": "x"}]}},
                {"data": {"itemid": "poiRankList"}},
                {"data": {"itemid": "unwanted_recommend"}},
                {"data": {"title": "no itemid", "buttons": [{"type": "follow"}]}},
                {"title": "missing data"}
            ]
        }]}
        result = self.run_script("https://api.weibo.cn/2/statuses/container_timeline_topic?fixture=1", body)
        output = json.loads(result["doneResult"]["body"])
        kept = output["items"][0]["items"]
        self.assertEqual(len(kept), 5)
        self.assertEqual([x.get("data", {}).get("itemid") for x in kept[:3]],
                         ["mine_topics_1", "tab_search_input", "poiRankList"])
        self.assertEqual(kept[1]["data"]["hotwords"], [{"word": "搜索超话"}])
        self.assertNotIn("buttons", kept[0]["data"])
        self.assertNotIn("icons", kept[1]["data"])
        self.assertEqual(kept[3]["data"]["title"], "no itemid")
        self.assertEqual(kept[4]["title"], "missing data")

    def test_search_page_filters_ads_in_place(self):
        body = {"cards": [
            {"itemid": "normal", "card_group": [
                {"itemid": "normal-group"},
                {"itemid": "t:51-sponsored"},
                {"actionlog": {"ext": "ads_word"}}
            ]},
            {"itemid": "infeed_friends_recommend"},
            {"itemid": "feed_-_invite"},
            {"itemid": "keep-2"}
        ]}
        result = self.run_script("https://api.weibo.cn/2/page?containerid=fixture", body)
        output = json.loads(result["doneResult"]["body"])
        self.assertEqual([x["itemid"] for x in output["cards"]], ["normal", "keep-2"])
        self.assertEqual([x["itemid"] for x in output["cards"][0]["card_group"]], ["normal-group"])


if __name__ == "__main__":
    unittest.main()
