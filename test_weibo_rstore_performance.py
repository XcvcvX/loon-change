import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from optimize_weibo_rstore import LOCAL, REMOTE, MARKER, LAZY_MARKER, GUARD_DECLARATION, HELPER, LEGACY_HELPER, optimize_source, rewrite_plugin, optimize_page_filter_cached_itemid, TOPIC_GROUP_MARKER, optimize_topic_group_in_place, COMMENT_DATA_CACHE_MARKER, COMMENT_DATA_CACHE_OLD, COMMENT_DATA_CACHE_NEW, optimize_comment_data_reference_cache, REMOVE_AVATAR_USER_CACHE_MARKER, COMMENT_USER_CACHE_MARKER, COMMENT_USER_CACHE_OLD, COMMENT_USER_CACHE_NEW, optimize_comment_user_reference_cache, TOPIC_GROUP_NESTED_DATA_MARKER, optimize_topic_group_nested_data_cache, ROOT_COMMENT_USER_CACHE_MARKER, optimize_root_comment_user_cache, REMOVE_AVATAR_PROPERTY_CACHE_MARKER, REMOVE_AVATAR_HELPER_NEW, optimize_remove_avatar_property_cache, COMMENT_DECORATION_SINGLE_READ_MARKER, ROOT_COMMENT_DECORATION_SINGLE_READ_MARKER, REPLY_DECORATION_SINGLE_READ_MARKER, ROOT_COMMENT_BUBBLE_SINGLE_READ_MARKER, optimize_comment_decoration_single_read, COMMENT_ARRAY_REFERENCE_CACHE_MARKER, optimize_comment_array_reference_cache, FOLLOWING_TIMELINE_DATA_CACHE_MARKER, optimize_following_timeline_data_cache, HOT_TIMELINE_DATA_CACHE_MARKER, optimize_hot_timeline_data_cache, FLOWLIST_ASYN_REFERENCE_CACHE_MARKER, optimize_flowlist_asyn_nested_reference_cache, SEARCH_TIMELINE_REFERENCE_CACHE_MARKER, optimize_search_timeline_nested_reference_cache, PROFILE_TIMELINE_PROPERTY_CACHE_MARKER, optimize_profile_timeline_property_cache, IS_AD_PROPERTY_CACHE_MARKER, optimize_is_ad_property_cache, REMOVE_FEED_AD_CACHE_MARKER, optimize_shared_feed_cleanup_cache, VOTE_INFO_NESTED_REFERENCE_CACHE_MARKER, optimize_vote_info_nested_reference_cache

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "scripts/weibo/weibo-rstore.js"
NODE = shutil.which("node")


class RStoreWeiboOptimizerTests(unittest.TestCase):
    def test_vote_info_nested_reference_cache_is_idempotent_and_fails_closed(self):
        source = """function removeVoteInfo(item) {
  if (item?.page_info?.media_info?.vote_info) {
    modified = true;
    delete item.page_info.media_info.vote_info;
  }
}"""
        optimized = optimize_vote_info_nested_reference_cache(source)
        self.assertIn(VOTE_INFO_NESTED_REFERENCE_CACHE_MARKER, optimized)
        self.assertIn("const pageInfo = hasCachedPageInfo ? cachedPageInfo : item?.page_info;", optimized)
        self.assertIn("const mediaInfo = pageInfo?.media_info;", optimized)
        self.assertIn("const voteInfo = mediaInfo?.vote_info;", optimized)
        self.assertIn("delete mediaInfo.vote_info;", optimized)
        self.assertEqual(optimize_vote_info_nested_reference_cache(optimized), optimized)
        with self.assertRaises(ValueError):
            optimize_vote_info_nested_reference_cache("function removeVoteInfo(item) {}")

    def test_fresh_source_transform_order_caches_user_before_avatar_fields(self):
        optimizer = Path(__file__).with_name("optimize_weibo_rstore.py").read_text(encoding="utf-8")
        lines = [line.strip() for line in optimizer.splitlines()
                 if "return optimize_comment_status_page_info_cache(" in line]
        self.assertEqual(len(lines), 2)
        for line in lines:
            comment_data = line.index("optimize_comment_data_reference_cache(")
            comment_user = line.index("optimize_comment_user_reference_cache(")
            avatar_fields = line.index("optimize_remove_avatar_property_cache(")
            # The wrappers are written outer-to-inner; runtime evaluation applies
            # the nested transforms in reverse (comment data -> user -> avatar fields).
            self.assertLess(avatar_fields, comment_user)
            self.assertLess(comment_user, comment_data)

    def test_generated_script_is_marked_and_idempotent(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(MARKER, source)
        self.assertIn(LAZY_MARKER, source)
        self.assertIn('let modified = !url.includes("/2/cardlist") && !url.includes("/2/comments/build_comments");', source)
        self.assertIn('$done(modified ? {body: JSON.stringify(obj)} : {});', source)
        self.assertEqual(optimize_source(source), source)
        self.assertEqual(len(re.findall(r"const __loonSource\d+ =", source)), 32)
        self.assertEqual(len(re.findall(r"(?m)^\s*const __loonLength\d+ = __loonSource\d+\.length;$", source)), 23)
        for cached_length in ("timelineItemsLength", "hotItemsLength", "hotStatusesLength", "asynItemsLength", "flowItemsLength", "searchItemsLength", "groupItemsLength"):
            self.assertIn(cached_length, source)
        self.assertNotRegex(source, r"for \(let __loonRead\d+ = 0, __loonLength\d+")
        self.assertNotRegex(source, r"\[[^\]\n]+\]\??\.includes\(")
        remaining = re.findall(r"\b(new[A-Za-z0-9_]*)\s*=\s*\[\s*\]", source)
        self.assertEqual(sorted(remaining), ["newActions"])
        self.assertIn(VOTE_INFO_NESTED_REFERENCE_CACHE_MARKER, source)
        self.assertIn("const pageInfo = hasCachedPageInfo ? cachedPageInfo : item?.page_info;", source)
        self.assertIn("const mediaInfo = pageInfo?.media_info;", source)
        self.assertIn("const voteInfo = mediaInfo?.vote_info;", source)
        self.assertNotIn("item?.page_info?.media_info?.vote_info", source)
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
        self.assertIn("const groupItems = nestedItems;", source)
        self.assertIn("const groupLength = groupItems.length;", source)
        self.assertIn("groupItems.length = groupWrite;", source)
        self.assertNotIn("let newII = [];", source)
        self.assertNotIn("item.items = newII;", source)
        damaged = source.replace("const groupItems = nestedItems;", "const groupItems = undefined;", 1)
        with self.assertRaisesRegex(ValueError, "marker/structure drift"):
            optimize_topic_group_in_place(damaged)


    def test_nested_topic_group_data_references_are_cached(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(optimize_topic_group_nested_data_cache(source), source)
        self.assertEqual(source.count(TOPIC_GROUP_NESTED_DATA_MARKER), 1)
        start = '} else if (url.includes("/2/statuses/container_timeline_topic")) {'
        end = '} else if (url.includes("/2/statuses/extend")) {'
        block = source[source.index(start):source.index(end, source.index(start) + len(start))]
        self.assertIn("const nestedItems = item?.items;", block)
        self.assertIn("const nestedLength = nestedItems.length;", block)
        self.assertIn("const iiData = ii?.data;", block)
        self.assertIn("const commonStruct = iiData.common_struct;", block)
        self.assertNotIn("for (let ii of item.items)", block)
        self.assertNotIn("removeAvatar(ii?.data)", block)
        damaged_block = block.replace("const iiData = ii?.data;", "const iiData = undefined;", 1)
        damaged = source[:source.index(start)] + damaged_block + source[source.index(end, source.index(start) + len(start)):]
        with self.assertRaisesRegex(ValueError, "data-cache structure drift"):
            optimize_topic_group_nested_data_cache(damaged)

        # Other Weibo response routes may legitimately retain the same source pattern.
        unrelated = source + "\nfor (let ii of item.items) { removeAvatar(ii?.data); }\n"
        self.assertEqual(optimize_topic_group_nested_data_cache(unrelated), unrelated)


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


    def test_search_timeline_nested_reference_cache_is_idempotent_and_fails_closed(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(SEARCH_TIMELINE_REFERENCE_CACHE_MARKER, source)
        self.assertEqual(optimize_search_timeline_nested_reference_cache(source), source)
        for token in (
            "const searchItems = obj?.items;",
            "const searchItemsLength = searchItems?.length || 0;",
            "const itemData = item?.data;",
            "const cardData = item?.data;",
            "const cardType = cardData?.card_type;",
            "const groupItems = item?.items;",
            "const groupItemsLength = groupItems?.length || 0;",
            "const innerData = ii?.data;",
            "const innerCardType = innerData?.card_type;",
        ):
            self.assertIn(token, source)
        damaged = source.replace("const cardType = cardData?.card_type;", "const cardType = null;", 1)
        with self.assertRaisesRegex(ValueError, "structure drift"):
            optimize_search_timeline_nested_reference_cache(damaged)

    def test_flowlist_asyn_nested_reference_cache_is_idempotent_and_fails_closed(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(FLOWLIST_ASYN_REFERENCE_CACHE_MARKER, source)
        self.assertEqual(optimize_flowlist_asyn_nested_reference_cache(source), source)
        for token in (
            "const asynItems = obj?.items;",
            "const asynItemsLength = asynItems?.length || 0;",
            "const itemData = item?.data;",
            "const itemId = item?.itemId;",
            "const nestedData = nestedItem?.data;",
            "const flowItems = obj?.items;",
            "const channelInfo = obj?.channelInfo;",
            "const flowChannels = channelInfo?.channels;",
            "const flowId = tab?.flowId;",
        ):
            self.assertIn(token, source)
        damaged = source.replace("const flowId = tab?.flowId;", "const flowId = null;", 1)
        with self.assertRaisesRegex(ValueError, "structure drift"):
            optimize_flowlist_asyn_nested_reference_cache(damaged)

    def test_hot_feed_cache_markers_are_inserted_before_postconditions(self):
        optimizer = Path(__file__).with_name("optimize_weibo_rstore.py").read_text(encoding="utf-8")
        specs = (
            ("optimize_following_timeline_data_cache",
             'block = block.replace(start, start + "\\n    " + FOLLOWING_TIMELINE_DATA_CACHE_MARKER, 1)',
             "if any(token not in block for token in required):"),
            ("optimize_hot_timeline_data_cache",
             'block = block.replace(start, start + "\\n    " + HOT_TIMELINE_DATA_CACHE_MARKER, 1)',
             "if any(token not in block for token in required):"),
            ("optimize_flowlist_asyn_nested_reference_cache",
             'asyn = asyn.replace(asyn_start, asyn_start + "\\n    // loon-change: Weibo container/asyn nested reference cache v1", 1)',
             "if any(x not in asyn for x in required_asyn)"),
            ("optimize_flowlist_asyn_nested_reference_cache",
             'flow = flow.replace(flow_start, flow_start + "\\n    // loon-change: Weibo flowlist nested reference cache v1", 1)',
             "or any(x not in flow for x in required_flow)"),
            ("optimize_search_timeline_nested_reference_cache",
             'block = block.replace(start, start + "\\n      " + SEARCH_TIMELINE_REFERENCE_CACHE_MARKER, 1)',
             "if any(token not in block for token in required):"),
        )
        for function_name, marker_insertion, postcondition in specs:
            start = optimizer.index("def " + function_name + "(")
            next_def = optimizer.find("\n" + "def ", start + 1)
            block = optimizer[start: next_def if next_def >= 0 else len(optimizer)]
            insertion_index = block.index(marker_insertion)
            self.assertLess(insertion_index, block.index(postcondition, insertion_index), function_name)


    def test_hot_timeline_caches_arrays_and_item_data(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(HOT_TIMELINE_DATA_CACHE_MARKER, source)
        self.assertEqual(optimize_hot_timeline_data_cache(source), source)
        for token in (
            "const hotItemsLength = hotItems?.length || 0;",
            "const __loonLength4 = hotItemsLength;",
            "const itemData = item?.data;",
            "const hotStatusesLength = hotStatuses?.length || 0;",
            "const __loonLength3 = hotStatusesLength;",
        ):
            self.assertIn(token, source)
        damaged = source.replace("const __loonSource4 = hotItems;", "const __loonSource4 = obj.items;", 1)
        with self.assertRaisesRegex(ValueError, "structure drift"):
            optimize_hot_timeline_data_cache(damaged)

    def test_following_timeline_caches_nested_data_references(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(FOLLOWING_TIMELINE_DATA_CACHE_MARKER, source)
        self.assertEqual(optimize_following_timeline_data_cache(source), source)
        for token in (
            "const timelineItemsLength = timelineItems?.length || 0;",
            "const __loonLength2 = timelineItemsLength;",
            "const itemData = item?.data;",
            "const itemTitle = itemData?.title;",
            "const screenNameSuffixNew = itemData?.screen_name_suffix_new;",
            "const itemUser = itemData?.user;",
            "const tagStruct = itemData?.tag_struct;",
        ):
            self.assertIn(token, source)
        start = source.index('} else if (url.includes("/2/statuses/container_timeline?") || url.includes("/2/statuses/container_timeline_unread")) {')
        end = source.index('} else if (url.includes("/2/statuses/container_timeline_topic")) {', start)
        block = source[start:end].replace("const itemData = item?.data;", "const cachedData = item?.data;", 1)
        damaged = source[:start] + block + source[end:]
        with self.assertRaisesRegex(ValueError, "structure drift"):
            optimize_following_timeline_data_cache(damaged)

    def test_comment_array_reference_cache_is_branch_lazy_and_fails_closed(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(COMMENT_ARRAY_REFERENCE_CACHE_MARKER, source)
        self.assertEqual(optimize_comment_array_reference_cache(source), source)
        self.assertIn("const commentDatas = obj?.datas;", source)
        self.assertIn("(rootComments = obj?.root_comments)?.length > 0", source)
        self.assertIn("(replyComments = obj?.comments)?.length > 0", source)
        self.assertNotIn("if (obj?.datas?.length > 0)", source)
        self.assertNotIn("else if (obj?.root_comments?.length > 0)", source)
        self.assertNotIn("else if (obj?.comments?.length > 0)", source)
        damaged = source.replace("const __loonSource30 = commentDatas;", "const __loonSource30 = obj.datas;", 1)
        with self.assertRaisesRegex(ValueError, "structure drift"):
            optimize_comment_array_reference_cache(damaged)

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

    def test_remove_avatar_optimizer_ignores_following_comment_punctuation(self):
        source = REMOVE_AVATAR_HELPER_NEW + "\n\n// 移除信息流关注按钮,推广,热评\nfunction removeFeedAd(item) {}"
        optimized = optimize_remove_avatar_property_cache(source)
        self.assertIn(REMOVE_AVATAR_PROPERTY_CACHE_MARKER, optimized)
        self.assertIn("const blockCardBg = data?.block_card_bg;", optimized)
        self.assertIn("const avatarGjId = user?.avatargj_id;", optimized)
        self.assertIn("// 移除信息流关注按钮,推广,热评", optimized)
        self.assertEqual(optimize_remove_avatar_property_cache(optimized), optimized)

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
        damaged_block = block.replace("const itemData = item?.data;", "const cachedItemData = item?.data;", 1)
        damaged = source[:start] + damaged_block + source[end:]
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

        damaged_helper = source.replace("const avatarGjId = user?.avatargj_id;", "const avatarGjId = data?.user?.avatargj_id;", 1)
        with self.assertRaisesRegex(ValueError, "removeAvatar user-cache avatar field cache drift"):
            optimize_comment_user_reference_cache(damaged_helper)

        user_marker_index = source.index(COMMENT_USER_CACHE_MARKER)
        damaged_comment = (
            source[:user_marker_index]
            + source[user_marker_index:].replace(
                "const commentUserName = commentUser.name;",
                "const commentUserName = commentUser.username;",
                1
            )
        )
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

    def test_search_timeline_caches_data_and_group_references_once(self):
        runner = r"""
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync(process.argv[1],"utf8");
const payload=JSON.parse(fs.readFileSync(0,"utf8"));
let doneResult,tracking=false;
const counts=Object.create(null);
const nativeParse=JSON.parse.bind(JSON),nativeStringify=JSON.stringify.bind(JSON);
const wrap=(target,key,label)=>{
  let current=target[key];counts[label]=0;
  Object.defineProperty(target,key,{enumerable:true,configurable:true,
    get(){if(tracking)counts[label]++;return current;},set(value){current=value;}});
};
const trackedJSON={
  parse(value){
    const parsed=nativeParse(value);
    const items=parsed.items;
    const itemsProxy=new Proxy(items,{get(target,key,receiver){
      if(tracking&&key==="length")counts["items.length"]++;
      return Reflect.get(target,key,receiver);
    }});
    parsed.items=itemsProxy;counts["items.length"]=0;
    const feed=itemsProxy[0],card=itemsProxy[1],group=itemsProxy[2];
    wrap(parsed,"items","response.items");
    wrap(feed,"data","feed.data");
    wrap(card,"data","card.data");
    wrap(group,"items","group.items");
    const groupItems=group.items;
    const groupProxy=new Proxy(groupItems,{get(target,key,receiver){
      if(tracking&&key==="length")counts["group.length"]++;
      return Reflect.get(target,key,receiver);
    }});
    group.items=groupProxy;counts["group.length"]=0;
    wrap(groupItems[0],"data","inner0.data");
    wrap(groupItems[1],"data","inner1.data");
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
        body = {"items": [
            {"category": "feed", "data": {"id": "feed-kept", "mblogtypename": "普通微博"}},
            {"category": "card", "data": {"id": "card-kept", "card_type": 55, "cate_id": "misc"}},
            {"category": "group", "items": [
                {"data": {"card_type": 118, "id": "drop-inner"}},
                {"data": {"card_type": 1, "id": "keep-inner"}}
            ]}
        ]}
        completed = subprocess.run(
            [NODE, "-e", runner, str(SCRIPT)],
            input=json.dumps({"url": "https://api.weibo.cn/2/search/container_timeline?fixture=ref-cache", "body": body}),
            capture_output=True, text=True, check=False, timeout=10
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["counts"], {
            "items.length": 1, "response.items": 1, "feed.data": 1, "card.data": 1,
            "group.items": 1, "group.length": 1, "inner0.data": 1, "inner1.data": 1
        })
        output = json.loads(result["doneResult"]["body"])
        self.assertEqual(
            [x["data"]["id"] for x in output["items"] if x["category"] in ("feed", "card")],
            ["feed-kept", "card-kept"]
        )
        self.assertEqual([x["data"]["id"] for x in output["items"][2]["items"]], ["keep-inner"])

    def test_flowlist_and_container_asyn_cache_nested_array_and_data_references(self):
        runner = r"""
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync(process.argv[1],"utf8");
const payload=JSON.parse(fs.readFileSync(0,"utf8"));
let doneResult,tracking=false;
const counts=Object.create(null);
const nativeParse=JSON.parse.bind(JSON),nativeStringify=JSON.stringify.bind(JSON);
const wrap=(target,key,label)=>{
  let current=target[key];counts[label]=0;
  Object.defineProperty(target,key,{enumerable:true,configurable:true,
    get(){if(tracking)counts[label]++;return current;},set(value){current=value;}});
};
const trackedJSON={
  parse(value){
    const parsed=nativeParse(value);
    if(payload.case==="asyn"){
      const items=parsed.items;
      const itemsProxy=new Proxy(items,{get(target,key,receiver){
        if(tracking&&key==="length")counts["items.length"]++;
        return Reflect.get(target,key,receiver);
      }});
      parsed.items=itemsProxy;counts["items.length"]=0;
      const card=itemsProxy[0],nested=card.items;
      counts["nested.length"]=0;
      const nestedProxy=new Proxy(nested,{get(target,key,receiver){
        if(tracking&&key==="length")counts["nested.length"]++;
        return Reflect.get(target,key,receiver);
      }});
      wrap(parsed,"items","response.items");
      wrap(card,"itemId","item.itemId");
      wrap(card,"items","item.items");
      card.items=nestedProxy;
      wrap(nested[0],"data","nested.data");
    } else {
      const items=parsed.items;
      const itemsProxy=new Proxy(items,{get(target,key,receiver){
        if(tracking&&key==="length")counts["items.length"]++;
        return Reflect.get(target,key,receiver);
      }});
      parsed.items=itemsProxy;counts["items.length"]=0;
      const card=itemsProxy[0],nested=card.items;
      counts["nested.length"]=0;
      const nestedProxy=new Proxy(nested,{get(target,key,receiver){
        if(tracking&&key==="length")counts["nested.length"]++;
        return Reflect.get(target,key,receiver);
      }});
      wrap(parsed,"items","response.items");
      wrap(card,"items","item.items");
      card.items=nestedProxy;
      wrap(nested[0],"data","nested.data");
      const channelInfo=parsed.channelInfo,channels=channelInfo.channels;
      const channelsProxy=new Proxy(channels,{get(target,key,receiver){
        if(tracking&&key==="length")counts["channels.length"]++;
        return Reflect.get(target,key,receiver);
      }});
      wrap(parsed,"channelInfo","response.channelInfo");
      wrap(channelInfo,"channels","channelInfo.channels");
      channelInfo.channels=channelsProxy;
      for(let index=0;index<channels.length;index++)wrap(channels[index],"flowId","tab"+index+".flowId");
      counts["channels.length"]=0;
    }
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
            ("asyn", "https://api.weibo.cn/2/container/asyn?fixture=cache",
             {"items": [{"itemId": "normal-card", "data": {}, "items": [{"data": {
                 "buttons": [{"type": "follow"}], "page_info": {"media_info": {"vote_info": {"id": 1}}}
             }}]}, {"itemId": "infeed_may_interest_in_1", "items": []}]},
             {"response.items": 1, "items.length": 1, "item.itemId": 1, "item.items": 1, "nested.length": 1, "nested.data": 1}),
            ("flow", "https://api.weibo.cn/2/flowlist?fixture=cache",
             {"items": [{"items": [{"data": {
                 "buttons": [{"type": "follow"}], "page_info": {"media_info": {"vote_info": {"id": 1}}}
             }}]}],
              "channelInfo": {"channels": [
                  {"flowId": "normal"}, {"flowId": "x_selfrecomm"}, {"flowId": "x_chaohua"}
              ]}},
             {"response.items": 1, "items.length": 1, "item.items": 1, "nested.length": 1, "nested.data": 1,
              "response.channelInfo": 1, "channelInfo.channels": 1, "channels.length": 1,
              "tab0.flowId": 1, "tab1.flowId": 1, "tab2.flowId": 1}),
        ]
        for case_name, url, body, expected in cases:
            completed = subprocess.run(
                [NODE, "-e", runner, str(SCRIPT)],
                input=json.dumps({"case": case_name, "url": url, "body": body}),
                capture_output=True, text=True, check=False, timeout=10
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(completed.stdout)
            self.assertEqual(result["counts"], expected)
            output = json.loads(result["doneResult"]["body"])
            self.assertNotIn("buttons", output["items"][0]["items"][0]["data"])
            self.assertNotIn("vote_info", output["items"][0]["items"][0]["data"]["page_info"]["media_info"])
            if case_name == "flow":
                self.assertEqual([x["flowId"] for x in output["channelInfo"]["channels"]], ["normal"])

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
      let current=target[key];
      Object.defineProperty(target,key,{enumerable:true,configurable:true,
        get(){if(tracking)counts[label]=(counts[label]||0)+1;return current;},set(value){current=value;}});
    };
    for(const key of ["datas","root_comments","comments"])wrap(parsed,key,"top."+key);
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
            ]}, {"top.datas", "datas.comment_bubble", "datas.comment_bullet_screens_message", "datas.hot_icon", "datas.vip_button"}),
            ("https://api.weibo.cn/2/comments/build_comments?fixture=root-read-count", {"root_comments": [
                {"user": {"name": "ordinary"}, "comment_bubble": {"x": 1},
                 "comment_bullet_screens_message": {"x": 1}, "hot_icon": {"x": 1}, "vip_button": {"x": 1}}
            ]}, {"top.datas", "top.root_comments", "root.comment_bubble", "root.comment_bullet_screens_message", "root.hot_icon", "root.vip_button"}),
            ("https://api.weibo.cn/2/comments/build_comments?fixture=reply-read-count", {"comments": [
                {"user": {"icons": [{"x": 1}]}, "reply_comment": {"comment_badge": {"x": 1}}}
            ]}, {"top.datas", "top.root_comments", "top.comments", "reply.user.icons", "reply.comment_badge"}),
            ("https://api.weibo.cn/2/comments/build_comments?fixture=root-comment-read-count", {"rootComment": {"comment_bubble": {"x": 1}}}, {"top.datas", "top.root_comments", "top.comments", "rootComment.comment_bubble"}),
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

    def test_hot_timeline_reads_top_level_arrays_and_item_data_once(self):
        runner = r"""
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync(process.argv[1],"utf8");
const payload=JSON.parse(fs.readFileSync(0,"utf8"));
let doneResult,tracking=false;
const counts=Object.create(null);
const nativeParse=JSON.parse.bind(JSON),nativeStringify=JSON.stringify.bind(JSON);
const trackedJSON={
  parse(value){
    const parsed=nativeParse(value);
    const wrap=(target,key,label)=>{
      let current=target[key];counts[label]=0;
      Object.defineProperty(target,key,{enumerable:true,configurable:true,
        get(){if(tracking)counts[label]++;return current;},set(value){current=value;}});
    };
    parsed.items=new Proxy(parsed.items,{get(target,key,receiver){
      if(tracking&&key==="length")counts["items.length"]++;
      return Reflect.get(target,key,receiver);
    }});
    parsed.statuses=new Proxy(parsed.statuses,{get(target,key,receiver){
      if(tracking&&key==="length")counts["statuses.length"]++;
      return Reflect.get(target,key,receiver);
    }});
    counts["items.length"]=0;counts["statuses.length"]=0;
    const card=parsed.items[0];
    wrap(parsed,"items","top.items");
    wrap(parsed,"statuses","top.statuses");
    wrap(card,"data","item.data");
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
        body = {
            "items": [{"category": "feed", "data": {
                "mblogtypename": "普通微博",
                "common_struct": {"type": "shop"},
                "comment_summary": {"text": "summary"},
                "semantic_brand_params": {"brand": "brand"},
                "page_info": {"media_info": {"vote_info": {"id": 1}}}
            }}],
            "statuses": [{"id": "status-1", "mblogtypename": "普通微博"}]
        }
        completed = subprocess.run(
            [NODE, "-e", runner, str(SCRIPT)],
            input=json.dumps({"url": "https://api.weibo.cn/2/statuses/container_timeline_hot?fixture=ref-cache", "body": body}),
            capture_output=True, text=True, check=False, timeout=10
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(
            set(result["counts"]),
            {"top.items", "items.length", "item.data", "top.statuses", "statuses.length"}
        )
        self.assertEqual(set(result["counts"].values()), {1})
        output = json.loads(result["doneResult"]["body"])
        self.assertEqual([item["id"] for item in output["statuses"]], ["status-1"])
        data = output["items"][0]["data"]
        self.assertNotIn("common_struct", data)
        self.assertNotIn("comment_summary", data)
        self.assertNotIn("semantic_brand_params", data)
        self.assertNotIn("vote_info", data["page_info"]["media_info"])

    def test_following_timeline_reads_each_nested_hot_reference_once(self):
        runner = r"""
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync(process.argv[1],"utf8");
const payload=JSON.parse(fs.readFileSync(0,"utf8"));
let doneResult,tracking=false;
const counts=Object.create(null);
const nativeParse=JSON.parse.bind(JSON),nativeStringify=JSON.stringify.bind(JSON);
const trackedJSON={
  parse(value){
    const parsed=nativeParse(value);
    const wrap=(target,key,label)=>{
      let current=target[key];counts[label]=0;
      Object.defineProperty(target,key,{enumerable:true,configurable:true,
        get(){if(tracking)counts[label]++;return current;},set(value){current=value;}});
    };
    parsed.items=new Proxy(parsed.items,{get(target,key,receiver){
      if(tracking&&key==="length")counts["items.length"]++;
      return Reflect.get(target,key,receiver);
    }});
    counts["items.length"]=0;
    const card=parsed.items[0],data=card.data;
    wrap(parsed,"items","top.items");
    wrap(card,"data","item.data");
    wrap(data,"title","data.title");
    wrap(data,"screen_name_suffix_new","data.screen_name_suffix_new");
    wrap(data,"user","data.user");
    wrap(data,"tag_struct","data.tag_struct");
    counts["suffix.length"]=0;
    counts["suffix[3]"]=0;
    data.screen_name_suffix_new=new Proxy(data.screen_name_suffix_new,{get(target,key,receiver){
      if(tracking&&key==="length")counts["suffix.length"]++;
      if(tracking&&key==="3")counts["suffix[3]"]++;
      return Reflect.get(target,key,receiver);
    }});
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
        body = {"items": [{
            "category": "feed",
            "data": {
                "mblogtypename": "普通微博",
                "title": {"text": "普通内容", "structs": None},
                "action_button_icon_dic": {"follow": 1},
                "screen_name_suffix_new": [{}, {}, {}, {"content": "普通文案"}],
                "user": {"following": True, "unfollowing_recom_switch": 1},
                "tag_struct": [{"type": "creator"}],
                "common_struct": {"type": "shop"},
                "comment_summary": {"text": "summary"},
                "semantic_brand_params": {"brand": "brand"},
                "page_info": {"media_info": {"vote_info": {"id": 1}}}
            }
        }]}
        completed = subprocess.run(
            [NODE, "-e", runner, str(SCRIPT)],
            input=json.dumps({"url": "https://api.weibo.cn/2/statuses/container_timeline?fixture=ref-cache", "body": body}),
            capture_output=True, text=True, check=False, timeout=10
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        expected = {
            "top.items", "items.length", "item.data", "data.title",
            "data.screen_name_suffix_new", "data.user", "data.tag_struct",
            "suffix.length", "suffix[3]"
        }
        self.assertEqual(set(result["counts"]), expected)
        self.assertEqual(result["counts"]["data.user"], 2)
        self.assertEqual(
            {count for label, count in result["counts"].items() if label != "data.user"},
            {1}
        )
        output = json.loads(result["doneResult"]["body"])
        data = output["items"][0]["data"]
        self.assertNotIn("action_button_icon_dic", data)
        self.assertEqual(data["user"]["unfollowing_recom_switch"], 0)
        self.assertEqual(data["tag_struct"], [])
        self.assertNotIn("common_struct", data)
        self.assertNotIn("comment_summary", data)
        self.assertNotIn("semantic_brand_params", data)
        self.assertNotIn("vote_info", data["page_info"]["media_info"])

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

    def test_profile_hot_property_cache_is_idempotent_and_fails_closed(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(PROFILE_TIMELINE_PROPERTY_CACHE_MARKER, source)
        self.assertEqual(optimize_profile_timeline_property_cache(source), source)
        for token in (
            "const profileItems = obj?.items;",
            "const profileItemsLength = profileItems?.length || 0;",
            "const itemCategory = item?.category;",
            "const groupItems = item?.items;",
            "const groupItemsLength = groupItems?.length || 0;",
            "const iiCategory = ii?.category;",
            "const iiCardType = iiData?.card_type;",
            "const itemHeaderData = itemHeader?.data;",
            "const itemTitle = itemData?.title;",
        ):
            self.assertIn(token, source)
        damaged = source.replace("const groupItemsLength = groupItems?.length || 0;",
                                "const groupItemsLength = 0;", 1)
        with self.assertRaisesRegex(ValueError, "marker/structure drift"):
            optimize_profile_timeline_property_cache(damaged)

    def test_profile_hot_property_getters_and_array_lengths_are_read_once(self):
        runner = r"""
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync(process.argv[1],"utf8");
const payload=JSON.parse(fs.readFileSync(0,"utf8"));
let doneResult,tracking=false;
const counts=Object.create(null);
const nativeParse=JSON.parse.bind(JSON),nativeStringify=JSON.stringify.bind(JSON);
const trackedJSON={
  parse(value){
    const parsed=nativeParse(value);
    const wrap=(target,key,label)=>{
      let current=target[key];counts[label]=0;
      Object.defineProperty(target,key,{enumerable:true,configurable:true,
        get(){if(tracking)counts[label]++;return current;},set(value){current=value;}});
    };
    const proxyArray=(array,label)=>{
      return new Proxy(array,{get(target,key,receiver){
        if(tracking&&key==="length")counts[label+".length"]=(counts[label+".length"]||0)+1;
        return Reflect.get(target,key,receiver);
      }});
    };
    const group=parsed.items[0],header=group.header,headerData=header.data;
    const feed=group.items[0],card=group.items[1],feedData=feed.data,cardData=card.data;
    wrap(parsed,"items","profile.items");
    const profileItems=proxyArray(parsed.items,"profile.items");counts["profile.items.ref"]=0;
    Object.defineProperty(parsed,"items",{enumerable:true,configurable:true,get(){if(tracking)counts["profile.items.ref"]++;return profileItems;}});
    wrap(group,"data","group.data");wrap(group,"category","group.category");
    wrap(group,"header","group.header");wrap(header,"data","group.header.data");wrap(headerData,"icon","group.header.icon");
    wrap(group,"itemId","group.itemId");wrap(group,"profile_type_id","group.profile_type_id");
    wrap(group,"items","group.items");
    const groupItems=proxyArray(group.items,"group.items");counts["group.items.ref"]=0;
    Object.defineProperty(group,"items",{enumerable:true,configurable:true,get(){if(tracking)counts["group.items.ref"]++;return groupItems;}});
    for(const [item,label,data] of [[feed,"feed",feedData],[card,"card",cardData]]){
      wrap(item,"category",label+".category");wrap(item,"data",label+".data");
    }
    wrap(feedData,"enable_comment_guide","feed.enable_comment_guide");
    wrap(feedData,"block_card_bg","feed.block_card_bg");
    wrap(feedData,"retweeted_status","feed.retweeted_status");
    wrap(cardData,"card_type","card.card_type");wrap(cardData,"rightImage","card.rightImage");
    wrap(cardData,"backgroundImage","card.backgroundImage");
    tracking=true;
    return parsed;
  },
  stringify(value){tracking=false;return nativeStringify(value);}
};
const context={JSON:trackedJSON,$request:{url:payload.url},$response:{body:nativeStringify(payload.body)},
  $done(value){doneResult=value;},console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,context,{timeout:5000});
process.stdout.write(nativeStringify({doneResult,counts}));
"""
        body = {"items": [{
            "category": "group", "data": {}, "header": {"data": {"icon": "remove"}},
            "itemId": "ordinary", "profile_type_id": "regular",
            "items": [
                {"category": "feed", "data": {"enable_comment_guide": True, "block_card_bg": "x", "retweeted_status": {"user": {}}, "source": "normal",
                                                 "title": {"text": "热门", "structs": []}}},
                {"category": "card", "data": {"card_type": 1, "rightImage": "x", "backgroundImage": "y"}}
            ]
        }]}
        completed = subprocess.run(
            [NODE, "-e", runner, str(SCRIPT)],
            input=json.dumps({"url": "https://api.weibo.cn/2/profile/container_timeline?fixture=cache",
                              "body": body}),
            capture_output=True, text=True, check=False, timeout=10
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        output = json.loads(result["doneResult"]["body"])
        counts = result["counts"]
        for key in ("profile.items.ref", "profile.items.length", "group.category", "group.data",
                    "group.header", "group.header.data", "group.header.icon", "group.itemId",
                    "group.profile_type_id", "group.items.ref", "group.items.length",
                    "feed.category", "feed.data", "card.category", "card.data",
                    "feed.enable_comment_guide", "feed.block_card_bg", "feed.retweeted_status",
                    "card.card_type", "card.rightImage", "card.backgroundImage"):
            self.assertEqual(counts.get(key), 1, key)
        self.assertEqual(len(output["items"][0]["items"]), 2)
        self.assertNotIn("icon", output["items"][0]["header"]["data"])
        self.assertNotIn("rightImage", output["items"][0]["items"][1]["data"])
        self.assertNotIn("backgroundImage", output["items"][0]["items"][1]["data"])
        self.assertFalse(output["items"][0]["items"][0]["data"]["enable_comment_guide"])

    def test_shared_is_ad_cache_is_idempotent_and_preserves_all_predicates(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(IS_AD_PROPERTY_CACHE_MARKER, source)
        self.assertEqual(optimize_is_ad_property_cache(source), source)
        for data in (
            {"mblogtypename": "广告"},
            {"mblogtypename": "热推"},
            {"promotion": {"type": "native_ad"}},
            {"content_auth_info": {"content_auth_title": "广告"}},
            {"ads_material_info": {"is_ads": True}},
        ):
            result = self.run_script("https://api.weibo.cn/2/comments/build_comments?fixture=is-ad",
                                     {"datas": [{"data": data}]})
            output = json.loads(result["doneResult"]["body"])
            self.assertEqual(output["datas"], [])

    def test_shared_is_ad_nested_properties_are_read_once_on_deep_comments(self):
        runner = r"""
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync(process.argv[1],"utf8");
const payload=JSON.parse(fs.readFileSync(0,"utf8"));
let doneResult,tracking=false;
const counts=Object.create(null);
const nativeParse=JSON.parse.bind(JSON),nativeStringify=JSON.stringify.bind(JSON);
const trackedJSON={
  parse(value){
    const parsed=nativeParse(value),data=parsed.datas[0].data;
    for(const key of ["mblogtypename","promotion","content_auth_info","ads_material_info"]){
      let current=data[key];counts[key]=0;
      Object.defineProperty(data,key,{enumerable:true,configurable:true,
        get(){if(tracking)counts[key]++;return current;},set(value){current=value;}});
    }
    tracking=true;return parsed;
  },
  stringify(value){tracking=false;return nativeStringify(value);}
};
const context={JSON:trackedJSON,$request:{url:payload.url},$response:{body:nativeStringify(payload.body)},
  $done(value){doneResult=value;},console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,context,{timeout:5000});
process.stdout.write(nativeStringify({doneResult,counts}));
"""
        body = {"datas": [{"type": 1, "data": {
            "mblogtypename": "普通内容", "promotion": {"type": "normal"},
            "content_auth_info": {"content_auth_title": ""},
            "ads_material_info": {"is_ads": False}, "user": {"name": "普通用户"}
        }}]}
        completed = subprocess.run(
            [NODE, "-e", runner, str(SCRIPT)],
            input=json.dumps({"url": "https://api.weibo.cn/2/comments/build_comments?fixture=is-ad-reads",
                              "body": body}),
            capture_output=True, text=True, check=False, timeout=10
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["doneResult"], {})
        for key in ("mblogtypename", "promotion", "content_auth_info", "ads_material_info"):
            self.assertEqual(result["counts"].get(key), 1, key)



    def test_profile_group_feed_does_not_call_avatar_cleanup_twice(self):
        source = SCRIPT.read_text(encoding="utf-8")
        start = source.index('} else if (url.includes("/2/profile/container_timeline")) {')
        end = source.index('} else if (url.includes("/2/profile/dealatt")', start)
        block = source[start:end]
        self.assertNotIn("removeAvatar(iiData);", block)
        self.assertEqual(block.count("removeFeedAd(iiData);"), 1)

    def test_shared_feed_cleanup_cache_is_idempotent_and_fails_closed(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(REMOVE_FEED_AD_CACHE_MARKER, source)
        self.assertEqual(optimize_shared_feed_cleanup_cache(source), source)
        self.assertIn("const retweetedStatus = item?.retweeted_status;", source)
        self.assertNotIn("removeAvatar(item?.retweeted_status);", source)
        damaged = source.replace("const retweetedStatus = item?.retweeted_status;",
                                 "const retweetedStatus = null;", 1)
        with self.assertRaisesRegex(ValueError, "marker/structure drift"):
            optimize_shared_feed_cleanup_cache(damaged)

    def test_comment_status_page_info_cache_is_idempotent_and_fails_closed(self):
        from optimize_weibo_rstore import (
            COMMENT_STATUS_PAGE_INFO_CACHE_MARKER,
            optimize_comment_status_page_info_cache,
        )
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(COMMENT_STATUS_PAGE_INFO_CACHE_MARKER, source)
        self.assertEqual(optimize_comment_status_page_info_cache(source), source)
        self.assertIn("const commentStatus = obj?.status;", source)
        self.assertIn("const commentStatusPageInfo = commentStatus?.page_info;", source)
        self.assertIn("removeVoteInfo(commentStatus, commentStatusPageInfo, true);", source)
        damaged = source.replace("const commentStatusPageInfo = commentStatus?.page_info;",
                                 "const commentStatusPageInfo = null;", 1)
        with self.assertRaisesRegex(ValueError, "marker/structure drift"):
            optimize_comment_status_page_info_cache(damaged)

    def test_comment_status_and_page_info_are_read_once_on_comment_response(self):
        runner = r"""
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync(process.argv[1],"utf8");
const payload=JSON.parse(fs.readFileSync(0,"utf8"));
let doneResult,tracking=false;
const counts={status:0,page_info:0};
const nativeParse=JSON.parse.bind(JSON),nativeStringify=JSON.stringify.bind(JSON);
const trackedJSON={
  parse(value){
    const parsed=nativeParse(value),status=parsed.status;
    let currentStatus=status;
    Object.defineProperty(parsed,"status",{enumerable:true,configurable:true,
      get(){if(tracking)counts.status++;return currentStatus;},set(value){currentStatus=value;}});
    let currentPageInfo=status.page_info;
    Object.defineProperty(status,"page_info",{enumerable:true,configurable:true,
      get(){if(tracking)counts.page_info++;return currentPageInfo;},set(value){currentPageInfo=value;}});
    tracking=true;return parsed;
  },
  stringify(value){tracking=false;return nativeStringify(value);}
};
const context={JSON:trackedJSON,$request:{url:payload.url},$response:{body:nativeStringify(payload.body)},
  $done(value){doneResult=value;},console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,context,{timeout:5000});
process.stdout.write(nativeStringify({doneResult,counts}));
"""
        body = {"status": {"page_info": {"media_info": {"vote_info": {"id": 1}}}}}
        completed = subprocess.run(
            [NODE, "-e", runner, str(SCRIPT)],
            input=json.dumps({"url": "https://api.weibo.cn/2/comments/build_comments?fixture=status-cache",
                              "body": body}),
            capture_output=True, text=True, check=False, timeout=10
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["counts"], {"status": 1, "page_info": 1})
        output = json.loads(result["doneResult"]["body"])
        self.assertNotIn("vote_info", output["status"]["page_info"]["media_info"])


    def test_comment_adtype_single_read_optimizer_is_idempotent_and_fails_closed(self):
        from optimize_weibo_rstore import (
            COMMENT_ADTYPE_SINGLE_READ_MARKER,
            optimize_comment_adtype_single_read,
        )
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(COMMENT_ADTYPE_SINGLE_READ_MARKER, source)
        self.assertEqual(optimize_comment_adtype_single_read(source), source)
        self.assertIn("const commentAdType = item?.adType;", source)
        self.assertIn('commentAdType === "相关内容" || commentAdType === "相关评论" || commentAdType === "推荐"', source)
        damaged = source.replace("const commentAdType = item?.adType;", "const commentAdType = null;", 1)
        with self.assertRaisesRegex(ValueError, "marker/structure drift"):
            optimize_comment_adtype_single_read(damaged)

    def test_deep_comment_adtype_is_read_once_and_filtering_is_unchanged(self):
        runner = r"""
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync(process.argv[1],"utf8");
const payload=JSON.parse(fs.readFileSync(0,"utf8"));
let doneResult,tracking=false;
const counts=[];
const nativeParse=JSON.parse.bind(JSON),nativeStringify=JSON.stringify.bind(JSON);
const trackedJSON={
  parse(value){
    const parsed=nativeParse(value);
    parsed.datas.forEach((entry,index)=>{
      let current=entry.adType;counts[index]=0;
      Object.defineProperty(entry,"adType",{enumerable:true,configurable:true,
        get(){if(tracking)counts[index]++;return current;},set(value){current=value;}});
    });
    tracking=true;return parsed;
  },
  stringify(value){tracking=false;return nativeStringify(value);}
};
const context={JSON:trackedJSON,$request:{url:payload.url},$response:{body:nativeStringify(payload.body)},
  $done(value){doneResult=value;},console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,context,{timeout:5000});
process.stdout.write(nativeStringify({doneResult,counts}));
"""
        body = {"datas": [
            {"adType": "相关内容", "data": {"user": {"name": "普通用户"}}},
            {"adType": "相关评论", "data": {"user": {"name": "普通用户"}}},
            {"adType": "推荐", "data": {"user": {"name": "普通用户"}}},
            {"adType": "普通评论", "data": {"user": {"name": "普通用户"}, "text": "保留"}}
        ]}
        completed = subprocess.run(
            [NODE, "-e", runner, str(SCRIPT)],
            input=json.dumps({"url": "https://api.weibo.cn/2/comments/build_comments?fixture=adtype-cache",
                              "body": body}),
            capture_output=True, text=True, check=False, timeout=10
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["counts"], [1, 1, 1, 1])
        output = json.loads(result["doneResult"]["body"])
        self.assertEqual(len(output["datas"]), 1)
        self.assertEqual(output["datas"][0]["data"]["text"], "保留")


if __name__ == "__main__":
    unittest.main()
