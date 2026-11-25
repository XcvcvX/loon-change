#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the active R-Store Weibo response script with allocation-free array compaction."""
import argparse
import re
from pathlib import Path

REMOTE = "https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js"
LOCAL = "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/weibo/weibo-rstore.js"
MARKER = "// loon-change: R-Store Weibo in-place response compaction v1; upstream zirawell/R-Store@"
LAZY_MARKER = "// loon-change: Weibo feed and comment lazy serialization v1"
GUARD_DECLARATION = "let modified = !url.includes(\"/2/cardlist\") && !url.includes(\"/2/comments/build_comments\");"
EXPECTED = 32

LEGACY_HELPER = """function compactInPlace(items, keep) {
  let write = 0;
  for (let read = 0, length = items.length; read < length; read++) {
    const item = items[read];
    if (keep(item, read)) {
      if (write !== read) items[write] = item;
      write++;
    }
  }
  items.length = write;
  return items;
}"""

HELPER = """function compactInPlace(items, keep) {
  const length = items.length;
  let write = 0;
  for (let read = 0; read < length; read++) {
    const item = items[read];
    if (keep(item, read)) {
      if (write !== read) items[write] = item;
      write++;
    }
  }
  items.length = write;
  if (write !== length) modified = true;
  return items;
}"""


FILTER_REWRITES = [
    (
        r'''obj.elements = obj.elements.filter((i) => i.app_name === "写微博" || i.app_name === "图片" || i.app_name === "视频");''',
        r'''compactInPlace(obj.elements, i => i.app_name === "写微博" || i.app_name === "图片" || i.app_name === "视频");''',
        "publisher list"
    ),
    (
        r'''obj.user_list = obj.user_list.filter((i) => !["活动通知", "闪聊"]?.includes(i?.user?.name));''',
        r'''compactInPlace(obj.user_list, i => !["活动通知", "闪聊"].includes(i?.user?.name));''',
        "direct message list"
    ),
    (
        r'''obj.cards[0].card_group = obj.cards[0].card_group.filter(
            (c) => !(c?.actionlog?.ext?.includes("ads_word") || c?.itemid?.includes("t:51") || c?.itemid?.includes("ads_word"))
        );''',
        r'''compactInPlace(obj.cards[0].card_group, c => !(c?.actionlog?.ext?.includes("ads_word") || c?.itemid?.includes("t:51") || c?.itemid?.includes("ads_word")));''',
        "search card group"
    ),
    (
        r'''obj.cards = obj.cards.filter(
          (i) =>
              !(
                  i.itemid?.includes("feed_-_invite") || // 超话里的好友
                  i.itemid?.includes("infeed_friends_recommend") || // 好友关注
                  i.itemid?.includes("infeed_may_interest_in") || // 你可能感兴趣的超话
                  i.itemid?.includes("infeed_pagemanual3") || // 手动区域3
                  i.itemid?.includes("infeed_weibo_mall") || // 微博小店
                  i?.mblog?.mblogtypename?.includes("广告")
              )
      );''',
        r'''compactInPlace(obj.cards, i => !(
          i.itemid?.includes("feed_-_invite") ||
          i.itemid?.includes("infeed_friends_recommend") ||
          i.itemid?.includes("infeed_may_interest_in") ||
          i.itemid?.includes("infeed_pagemanual3") ||
          i.itemid?.includes("infeed_weibo_mall") ||
          i?.mblog?.mblogtypename?.includes("广告")
        ));''',
        "search cards"
    ),
    (
        r'''obj.card_group = obj.card_group.filter((i) => i?.desc?.includes("你可能感兴趣的超话"));''',
        r'''compactInPlace(obj.card_group, i => i?.desc?.includes("你可能感兴趣的超话"));''',
        "topic card group"
    ),
    (
        r'''item.items = item.items.filter(
                (i) =>
                    i.itemId === "100505_-_album" || // 我的相册
                    i.itemId === "100505_-_like" || // 赞/收藏
                    i.itemId === "100505_-_watchhistory" || // 浏览记录
                    i.itemId === "100505_-_draft" // 草稿箱
                // i.itemId === "100505_-_pay" || // 我的钱包
                // i.itemId === "100505_-_ordercenter" || // 我的订单
                // i.itemId === "100505_-_productcenter" || // 创作中心
                // i.itemId === "100505_-_promote" || // 广告中心
            );''',
        r'''compactInPlace(item.items, i =>
            i.itemId === "100505_-_album" ||
            i.itemId === "100505_-_like" ||
            i.itemId === "100505_-_watchhistory" ||
            i.itemId === "100505_-_draft"
          );''',
        "profile menu"
    ),
    (
        r'''obj.footer.data.menus = obj.footer.data.menus.filter((i) => !/\d+_ai\./?.test(i?.pic));''',
        r'''compactInPlace(obj.footer.data.menus, i => !/\d+_ai\./.test(i?.pic));''',
        "search footer menu"
    ),
    (
        r'''obj.channelInfo.channel_list = obj.channelInfo.channel_list.filter((t) => t.title !== "广场");''',
        r'''compactInPlace(obj.channelInfo.channel_list, t => t.title !== "广场");''',
        "topic channels"
    ),
]

def _regex_start(source, index):
    previous = source[:index].rstrip()
    if not previous:
        return True
    if previous[-1] in "=(:,[!&|?{};":
        return True
    return re.search(r"\b(return|case|throw|yield|await|else|do)\s*$", previous) is not None

def _matching_brace(source, opening):
    depth = 0
    state = "code"
    quote = ""
    escaped = False
    in_class = False
    index = opening
    while index < len(source):
        char = source[index]
        nxt = source[index + 1] if index + 1 < len(source) else ""
        if state == "code":
            if char == "/" and nxt == "/":
                state = "line"
                index += 2
                continue
            if char == "/" and nxt == "*":
                state = "block"
                index += 2
                continue
            if char == "/" and _regex_start(source, index):
                state = "regex"
                escaped = False
                in_class = False
                index += 1
                continue
            if char in ("'", '"', chr(96)):
                state = "string"
                quote = char
                escaped = False
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return index
        elif state == "line":
            if char == "\n":
                state = "code"
        elif state == "block":
            if char == "*" and nxt == "/":
                state = "code"
                index += 2
                continue
        elif state == "string":
            if escaped:
                escaped = False
            elif ord(char) == 92:
                escaped = True
            elif char == quote:
                state = "code"
        elif state == "regex":
            if escaped:
                escaped = False
            elif ord(char) == 92:
                escaped = True
            elif char == "[":
                in_class = True
            elif char == "]":
                in_class = False
            elif char == "/" and not in_class:
                state = "code"
        index += 1
    raise ValueError("unterminated JavaScript loop")

def _transform_one(source, sequence):
    declarations = list(re.finditer(r"let\s+(new[A-Za-z0-9_]*)\s*=\s*\[\s*\]\s*;", source))
    for declaration in reversed(declarations):
        name = declaration.group(1)
        header = re.search(
            r"for\s*\(\s*let\s+([A-Za-z_$][\w$]*)\s+of\s+([^)]+)\)\s*\{",
            source[declaration.end():declaration.end() + 500]
        )
        if not header:
            continue
        iterator = header.group(1)
        source_expr = header.group(2).strip()
        header_start = declaration.end() + header.start()
        opening = declaration.end() + header.end() - 1
        closing = _matching_brace(source, opening)
        body = source[opening + 1:closing]
        if re.search(r"\b" + re.escape(name) + r"\.unshift\s*\(", body):
            continue
        push = re.compile(r"\b" + re.escape(name) + r"\.push\(\s*" + re.escape(iterator) + r"\s*\)\s*;")
        body, pushes = push.subn("__SOURCE__[__WRITE__++] = " + iterator + ";", body)
        if not pushes:
            continue
        assignment = re.search(
            r"(?m)^(?P<indent>[ \t]*)(?P<dest>[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s*=\s*" +
            re.escape(name) + r"\s*;",
            source[closing + 1:closing + 1 + 900]
        )
        if not assignment or assignment.group("dest") != source_expr:
            continue

        source_name = "__loonSource%d" % sequence
        write_name = "__loonWrite%d" % sequence
        read_name = "__loonRead%d" % sequence
        length_name = "__loonLength%d" % sequence
        body = body.replace("__SOURCE__", source_name).replace("__WRITE__", write_name)
        line_start = source.rfind("\n", 0, declaration.start()) + 1
        decl_indent = source[line_start:declaration.start()]
        loop_line = source.rfind("\n", 0, header_start) + 1
        loop_indent = source[loop_line:header_start]
        assign_start = closing + 1 + assignment.start()
        assign_end = closing + 1 + assignment.end()
        decl_replacement = (
            "const " + source_name + " = " + source_expr + ";\n" +
            decl_indent + "let " + write_name + " = 0;"
        )
        between = source[declaration.end():header_start]
        header_replacement = (
            "const " + length_name + " = " + source_name + ".length;\n" +
            loop_indent + "for (let " + read_name + " = 0; " + read_name + " < " +
            length_name + "; " + read_name + "++) {\n" + loop_indent + "  let " +
            iterator + " = " + source_name + "[" + read_name + "];"
        )
        assignment_replacement = assignment.group("indent") + source_name + ".length = " + write_name + ";"
        return (
            source[:declaration.start()] + decl_replacement + between +
            header_replacement + body + source[closing:assign_start] +
            assignment_replacement + source[assign_end:]
        ), True
    return source, False

def compact_collecting_loops(source):
    count = 0
    while True:
        source, changed = _transform_one(source, count + 1)
        if not changed:
            break
        count += 1
        if count > 80:
            raise ValueError("unexpectedly large Weibo array-loop inventory")
    if count != EXPECTED:
        raise ValueError("Weibo loop inventory drift: expected %d, transformed %d" % (EXPECTED, count))
    return source

def add_lazy_serialization_guard(source):
    delete_targets = [
        "data.block_card_bg", "data.buttons", "data.cardid", "data.icons",
        "data.mblog_buttons", "data.pic_bg_new", "data.user.avatargj_id",
        "data.user.avatar_extend_info", "data.user.cardid", "data.user.icons",
        "data.user.mbtype", "item.data.comment_bubble",
        "item.data.comment_bullet_screens_message", "item.data.hot_icon",
        "item.data.vip_button", "item.comment_bubble",
        "item.comment_bullet_screens_message", "item.hot_icon", "item.vip_button",
        "item.user.icons", "item.reply_comment.comment_badge",
        "item.page_info.media_info.vote_info", "obj.rootComment.comment_bubble",
    ]
    if COMMENT_DATA_CACHE_MARKER in source:
        delete_targets = [
            target.replace("item.data.", "commentData.") if target.startswith("item.data.") else target
            for target in delete_targets
        ]
    elif "item.data.hot_icon" not in source:
        delete_targets.remove("item.data.hot_icon")

    if REMOVE_AVATAR_USER_CACHE_MARKER in source:
        delete_targets = [
            target.replace("data.user.", "user.") if target.startswith("data.user.") else target
            for target in delete_targets
        ]

    if LAZY_MARKER in source:
        if GUARD_DECLARATION not in source or '$done(modified ? {body: JSON.stringify(obj)} : {});' not in source:
            raise ValueError('marked Weibo lazy-serialization guard is incomplete')
        loop_markers = re.findall(r'if \(__loonWrite\d+ !== __loonLength\d+\) modified = true;', source)
        allowed_loop_counts = {EXPECTED}
        if TOPIC_GROUP_MARKER in source:
            allowed_loop_counts.add(EXPECTED - 1)
        if len(loop_markers) not in allowed_loop_counts:
            raise ValueError('Weibo lazy-serialization loop inventory drift')
        for target in delete_targets:
            pattern = re.compile(r'(?m)^([ \t]*)modified = true;\n[ \t]*delete ' + re.escape(target) + r';$')
            if not pattern.search(source):
                raise ValueError('Weibo tracked-delete marker missing for ' + target)
        return source

    if GUARD_DECLARATION not in source:
        anchor = 'const url = $request.url;'
        if source.count(anchor) != 1:
            raise ValueError('Weibo URL declaration anchor drift')
        source = source.replace(anchor, anchor + '\n' + GUARD_DECLARATION, 1)
    if LEGACY_HELPER in source:
        source = source.replace(LEGACY_HELPER, HELPER, 1)
    elif HELPER not in source:
        raise ValueError('Weibo compaction helper anchor drift')

    loop_pattern = re.compile(r'(?m)^([ \t]*)__loonSource(\d+)\.length = __loonWrite\2;$')
    def mark_loop(match):
        index = match.group(2)
        return match.group(0) + '\n' + match.group(1) + 'if (__loonWrite' + index + ' !== __loonLength' + index + ') modified = true;'
    source, loop_count = loop_pattern.subn(mark_loop, source)
    if loop_count != EXPECTED:
        raise ValueError('Weibo compact-loop inventory drift: expected %d, got %d' % (EXPECTED, loop_count))

    for target in delete_targets:
        pattern = re.compile(r'(?m)^([ \t]*)delete ' + re.escape(target) + r';$')
        source, count = pattern.subn(lambda match: match.group(1) + 'modified = true;\n' + match.group(0), source)
        if count != 1:
            raise ValueError('Weibo tracked-delete inventory drift for ' + target)

    final_call = '$done({body: JSON.stringify(obj)});'
    if source.count(final_call) != 1:
        raise ValueError('Weibo common final response anchor drift')
    source = source.replace(final_call, '$done(modified ? {body: JSON.stringify(obj)} : {});', 1)
    first_line_end = source.find('\n')
    if first_line_end < 0:
        raise ValueError('Weibo header marker is missing')
    return source[:first_line_end + 1] + LAZY_MARKER + '\n' + source[first_line_end + 1:]


COMMENT_DATA_CACHE_MARKER = "// loon-change: Weibo comment data reference cache v1"
COMMENT_DATA_CACHE_OLD = "        let item = __loonSource30[__loonRead30];\n        if (item?.data) {\n          if (!isAd(item?.data)) {\n            // 微博伪装评论\n            if (item?.data?.user) {\n              // 头像挂件,关注按钮\n              removeAvatar(item?.data);\n              if ((item.data?.user?.name === \"超话社区\" || item.data?.user?.name === \"微博开新年\" || item.data?.user?.name === \"微博热搜\" || item.data?.user?.name === \"微博视频\")) {\n                continue;\n              }\n            }\n            // 评论气泡\n            if (item?.data?.comment_bubble) {\n              modified = true;\n              delete item.data.comment_bubble;\n            }\n            // 评论弹幕\n            if (item?.data?.comment_bullet_screens_message) {\n              modified = true;\n              delete item.data.comment_bullet_screens_message;\n            }\n            // 热评小图标 弹幕 首评\n            if (item?.data?.hot_icon) {\n              modified = true;\n              delete item.data.hot_icon;\n            }\n            // 会员气泡按钮\n            if (item?.data?.vip_button) {\n              modified = true;\n              delete item.data.vip_button;\n            }\n            // 6为你推荐更多精彩内容 15过滤提示\n            if (item?.type === 6 || item?.type === 15) {\n              continue;\n            }\n            if (item?.adType === \"相关内容\" || item?.adType === \"相关评论\" || item?.adType === \"推荐\") {\n              continue;\n            }\n            __loonSource30[__loonWrite30++] = item;\n          }\n        }"
COMMENT_DATA_CACHE_OLD_UNTRACKED_HOT_ICON = COMMENT_DATA_CACHE_OLD.replace("              modified = true;" + chr(10) + "              delete item.data.hot_icon;", "              delete item.data.hot_icon;")
COMMENT_DATA_CACHE_NEW = "        let item = __loonSource30[__loonRead30];\n        // loon-change: Weibo comment data reference cache v1\n        const commentData = item?.data;\n        if (commentData) {\n          if (!isAd(commentData)) {\n            // 微博伪装评论\n            if (commentData?.user) {\n              // 头像挂件,关注按钮\n              removeAvatar(commentData);\n              if ((commentData.user?.name === \"超话社区\" || commentData.user?.name === \"微博开新年\" || commentData.user?.name === \"微博热搜\" || commentData.user?.name === \"微博视频\")) {\n                continue;\n              }\n            }\n            // 评论气泡\n            if (commentData?.comment_bubble) {\n              modified = true;\n              delete commentData.comment_bubble;\n            }\n            // 评论弹幕\n            if (commentData?.comment_bullet_screens_message) {\n              modified = true;\n              delete commentData.comment_bullet_screens_message;\n            }\n            // 热评小图标 弹幕 首评\n            if (commentData?.hot_icon) {\n              modified = true;\n              delete commentData.hot_icon;\n            }\n            // 会员气泡按钮\n            if (commentData?.vip_button) {\n              modified = true;\n              delete commentData.vip_button;\n            }\n            // 6为你推荐更多精彩内容 15过滤提示\n            if (item?.type === 6 || item?.type === 15) {\n              continue;\n            }\n            if (item?.adType === \"相关内容\" || item?.adType === \"相关评论\" || item?.adType === \"推荐\") {\n              continue;\n            }\n            __loonSource30[__loonWrite30++] = item;\n          }\n        }"

def optimize_comment_data_reference_cache(source):
    if COMMENT_DATA_CACHE_MARKER in source:
        expected_new = COMMENT_DATA_CACHE_NEW
        if "COMMENT_USER_CACHE_NEW" in globals() and "COMMENT_USER_CACHE_OLD" in globals():
            expected_new = expected_new.replace(COMMENT_USER_CACHE_OLD, COMMENT_USER_CACHE_NEW, 1)
        if source.count(COMMENT_DATA_CACHE_MARKER) != 1 or COMMENT_DATA_CACHE_OLD in source or expected_new not in source:
            raise ValueError("Weibo comment data-cache marker/structure drift")
        return source
    old_block = COMMENT_DATA_CACHE_OLD
    if source.count(old_block) != 1:
        old_block = COMMENT_DATA_CACHE_OLD_UNTRACKED_HOT_ICON
    if source.count(old_block) != 1:
        raise ValueError("Weibo comment data-cache anchor drift")
    source = source.replace(old_block, COMMENT_DATA_CACHE_NEW, 1)
    if source.count(COMMENT_DATA_CACHE_MARKER) != 1:
        raise ValueError("Weibo comment data-cache postcondition failed")
    return source


REMOVE_AVATAR_USER_CACHE_MARKER = "// loon-change: Weibo removeAvatar cached user reference v1"
REMOVE_AVATAR_HELPER_OLD = "function removeAvatar(data) {\n  if (data?.block_card_bg) {\n    modified = true;\n    delete data.block_card_bg;\n  }\n  if (data?.buttons) {\n    modified = true;\n    delete data.buttons;\n  }\n  if (data?.cardid) {\n    modified = true;\n    delete data.cardid;\n  }\n  if (data?.icons) {\n    modified = true;\n    delete data.icons;\n  }\n  if (data?.mblog_buttons) {\n    // 转发按钮图标\n    modified = true;\n    delete data.mblog_buttons;\n  }\n  if (data?.pic_bg_new) {\n    modified = true;\n    delete data.pic_bg_new;\n  }\n  if (data?.user?.avatargj_id) {\n    modified = true;\n    delete data.user.avatargj_id;\n  }\n  if (data?.user?.avatar_extend_info) {\n    modified = true;\n    delete data.user.avatar_extend_info;\n  }\n  if (data?.user?.cardid) {\n    modified = true;\n    delete data.user.cardid;\n  }\n  if (data?.user?.icons) {\n    modified = true;\n    delete data.user.icons;\n  }\n  if (data?.user?.mbtype) {\n    // 会员等级图标\n    modified = true;\n    delete data.user.mbtype;\n  }\n}"
REMOVE_AVATAR_HELPER_NEW = "function removeAvatar(data, user = data?.user) {\n  // loon-change: Weibo removeAvatar cached user reference v1\n  if (data?.block_card_bg) {\n    modified = true;\n    delete data.block_card_bg;\n  }\n  if (data?.buttons) {\n    modified = true;\n    delete data.buttons;\n  }\n  if (data?.cardid) {\n    modified = true;\n    delete data.cardid;\n  }\n  if (data?.icons) {\n    modified = true;\n    delete data.icons;\n  }\n  if (data?.mblog_buttons) {\n    // 转发按钮图标\n    modified = true;\n    delete data.mblog_buttons;\n  }\n  if (data?.pic_bg_new) {\n    modified = true;\n    delete data.pic_bg_new;\n  }\n  if (user?.avatargj_id) {\n    modified = true;\n    delete user.avatargj_id;\n  }\n  if (user?.avatar_extend_info) {\n    modified = true;\n    delete user.avatar_extend_info;\n  }\n  if (user?.cardid) {\n    modified = true;\n    delete user.cardid;\n  }\n  if (user?.icons) {\n    modified = true;\n    delete user.icons;\n  }\n  if (user?.mbtype) {\n    // 会员等级图标\n    modified = true;\n    delete user.mbtype;\n  }\n}"

COMMENT_USER_CACHE_MARKER = "// loon-change: Weibo comment user/name reference cache v1"
COMMENT_USER_CACHE_OLD = "            if (commentData?.user) {\n              // 头像挂件,关注按钮\n              removeAvatar(commentData);\n              if ((commentData.user?.name === \"超话社区\" || commentData.user?.name === \"微博开新年\" || commentData.user?.name === \"微博热搜\" || commentData.user?.name === \"微博视频\")) {\n                continue;\n              }\n            }"
COMMENT_USER_CACHE_NEW = "            // loon-change: Weibo comment user/name reference cache v1\n            const commentUser = commentData?.user;\n            if (commentUser) {\n              // 头像挂件,关注按钮\n              removeAvatar(commentData, commentUser);\n              const commentUserName = commentUser.name;\n              if (commentUserName === \"超话社区\" || commentUserName === \"微博开新年\" || commentUserName === \"微博热搜\" || commentUserName === \"微博视频\") {\n                continue;\n              }\n            }"

def optimize_comment_user_reference_cache(source):
    """Cache each comment's user/name and reuse the user reference in removeAvatar."""
    if REMOVE_AVATAR_USER_CACHE_MARKER in source:
        if source.count(REMOVE_AVATAR_USER_CACHE_MARKER) != 1 or REMOVE_AVATAR_HELPER_OLD in source or REMOVE_AVATAR_HELPER_NEW not in source:
            raise ValueError("Weibo removeAvatar user-cache marker/structure drift")
    else:
        if source.count(REMOVE_AVATAR_HELPER_OLD) != 1:
            raise ValueError("Weibo removeAvatar helper anchor drift")
        source = source.replace(REMOVE_AVATAR_HELPER_OLD, REMOVE_AVATAR_HELPER_NEW, 1)

    if COMMENT_USER_CACHE_MARKER in source:
        if source.count(COMMENT_USER_CACHE_MARKER) != 1 or COMMENT_USER_CACHE_OLD in source or COMMENT_USER_CACHE_NEW not in source:
            raise ValueError("Weibo comment user-cache marker/structure drift")
    else:
        if source.count(COMMENT_USER_CACHE_OLD) != 1:
            raise ValueError("Weibo comment user-cache anchor drift")
        source = source.replace(COMMENT_USER_CACHE_OLD, COMMENT_USER_CACHE_NEW, 1)

    if source.count(REMOVE_AVATAR_USER_CACHE_MARKER) != 1 or source.count(COMMENT_USER_CACHE_MARKER) != 1:
        raise ValueError("Weibo comment user-cache postcondition failed")
    return source




PROFILE_TIMELINE_DATA_CACHE_MARKER = "// loon-change: Weibo profile timeline cached nested data v1"

def optimize_profile_timeline_data_cache(source):
    """Cache top-level and nested feed data references in the profile timeline hot loop."""
    start = '} else if (url.includes("/2/profile/container_timeline")) {'
    end = '} else if (url.includes("/2/profile/dealatt") || url.includes("/2/friendships/")) {'
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError("Weibo profile timeline block boundary drift")
    left = source.index(start)
    right = source.index(end, left + len(start))
    block = source[left:right]
    if PROFILE_TIMELINE_DATA_CACHE_MARKER in block:
        required = ("const itemData = item?.data;", "const iiData = ii?.data;")
        stripped = block.replace(required[0], "").replace(required[1], "")
        if block.count(PROFILE_TIMELINE_DATA_CACHE_MARKER) != 1 or any(token not in block for token in required):
            raise ValueError("Weibo profile timeline data-cache marker/structure drift")
        if any(token in stripped for token in ("item?.data", "ii?.data", "ii.data")):
            raise ValueError("Weibo repeated profile timeline data reads remain")
        return source
    item_anchor = "        let item = __loonSource19[__loonRead19];"
    ii_anchor = "                let ii = __loonSource18[__loonRead18];"
    if block.count(item_anchor) != 1 or block.count(ii_anchor) != 1:
        raise ValueError("Weibo profile timeline loop anchors drifted")
    block = block.replace(item_anchor, item_anchor + "\n        const itemData = item?.data;", 1)
    block = block.replace(ii_anchor, ii_anchor + "\n                const iiData = ii?.data;", 1)
    block = block.replace("item?.data", "itemData").replace("ii?.data", "iiData").replace("ii.data", "iiData")
    block = block.replace("const itemData = itemData;", "const itemData = item?.data;")
    block = block.replace("const iiData = iiData;", "const iiData = ii?.data;")
    block = block.replace(start, start + "\n    " + PROFILE_TIMELINE_DATA_CACHE_MARKER, 1)
    stripped = block.replace("const itemData = item?.data;", "").replace("const iiData = ii?.data;", "")
    if any(token in stripped for token in ("item?.data", "ii?.data", "ii.data")):
        raise ValueError("Weibo profile timeline cache postcondition failed")
    return source[:left] + block + source[right:]


def optimize_source(source, commit="unknown"):
    if MARKER in source:
        if "__loonSource32" not in source or "compactInPlace(items, keep)" not in source:
            raise ValueError("marked Weibo script is incomplete")
        return optimize_flowlist_asyn_nested_reference_cache(optimize_hot_timeline_data_cache(optimize_following_timeline_data_cache(optimize_comment_array_reference_cache(optimize_profile_timeline_data_cache(optimize_comment_user_reference_cache(optimize_comment_data_reference_cache(optimize_comment_decoration_single_read(optimize_remove_avatar_property_cache(optimize_root_comment_user_cache(optimize_topic_group_nested_data_cache(optimize_topic_group_in_place(optimize_page_filter_cached_itemid(optimize_scalar_membership(add_lazy_serialization_guard(source)))))))))))))))
    source = source.replace("const url = $request.url;", "const url = $request.url;\n" + GUARD_DECLARATION + "\n\n" + HELPER, 1)
    if source.count(HELPER) != 1:
        raise ValueError("Weibo helper insertion failed")
    source = compact_collecting_loops(source)
    for old, new, label in FILTER_REWRITES:
        if source.count(old) != 1:
            raise ValueError(label + " filter anchor drift")
        source = source.replace(old, new, 1)
    remaining = re.findall(r"\b(new[A-Za-z0-9_]*)\s*=\s*\[\s*\]", source)
    if sorted(remaining) != ["newActions", "newII"]:
        raise ValueError("unexpected remaining Weibo temporary arrays: " + repr(remaining))
    return optimize_flowlist_asyn_nested_reference_cache(optimize_hot_timeline_data_cache(optimize_following_timeline_data_cache(optimize_comment_array_reference_cache(optimize_profile_timeline_data_cache(optimize_comment_user_reference_cache(optimize_comment_data_reference_cache(optimize_comment_decoration_single_read(optimize_remove_avatar_property_cache(optimize_root_comment_user_cache(optimize_topic_group_nested_data_cache(optimize_topic_group_in_place(optimize_page_filter_cached_itemid(optimize_scalar_membership(add_lazy_serialization_guard(MARKER + commit + "\n" + source)))))))))))))))

SCALAR_MEMBERSHIP_MARKER = "// loon-change: Weibo hot-loop scalar membership v1"
SCALAR_MEMBERSHIP_REWRITES = [
    ("[120, 145, 192]?.includes(cardType)", "(cardType === 120 || cardType === 145 || cardType === 192)", 1),
    ("[6, 101]?.includes(cardType)", "(cardType === 6 || cardType === 101)", 1),
    ("[17, 58]?.includes(cardType)", "(cardType === 17 || cardType === 58)", 1),
    ("[\"超话社区\", \"微博开新年\", \"微博热搜\", \"微博视频\"]?.includes(item.data?.user?.name)", "(item.data?.user?.name === \"超话社区\" || item.data?.user?.name === \"微博开新年\" || item.data?.user?.name === \"微博热搜\" || item.data?.user?.name === \"微博视频\")", 1),
    ("![\"活动通知\", \"闪聊\"].includes(i?.user?.name)", "!(i?.user?.name === \"活动通知\" || i?.user?.name === \"闪聊\")", 1),
    ("[\"最新微博\", \"特别关注\", \"好友圈\", \"视频\"]?.includes(ii?.title)", "(ii?.title === \"最新微博\" || ii?.title === \"特别关注\" || ii?.title === \"好友圈\" || ii?.title === \"视频\")", 1),
    ("[58, 216]?.includes(item?.data?.card_type)", "(item?.data?.card_type === 58 || item?.data?.card_type === 216)", 1),
    ("[10, 48, 176]?.includes(ii?.data?.card_type)", "(ii?.data?.card_type === 10 || ii?.data?.card_type === 48 || ii?.data?.card_type === 176)", 1),
    ("[22]?.includes(cardType)", "cardType === 22", 1),
    ("[19, 118, 206, 208, 217, 236, 249, 261]?.includes(item?.data?.card_type)", "(item?.data?.card_type === 19 || item?.data?.card_type === 118 || item?.data?.card_type === 206 || item?.data?.card_type === 208 || item?.data?.card_type === 217 || item?.data?.card_type === 236 || item?.data?.card_type === 249 || item?.data?.card_type === 261)", 2),
    ("[118, 182, 217, 247]?.includes(ii?.data?.card_type)", "(ii?.data?.card_type === 118 || ii?.data?.card_type === 182 || ii?.data?.card_type === 217 || ii?.data?.card_type === 247)", 1),
    ("[118, 182, 192, 217, 247]?.includes(ii?.data?.card_type)", "(ii?.data?.card_type === 118 || ii?.data?.card_type === 182 || ii?.data?.card_type === 192 || ii?.data?.card_type === 217 || ii?.data?.card_type === 247)", 1),
    ("[3, 17, 22, 30, 42, 89, 206, 236]?.includes(ii?.data?.card_type)", "(ii?.data?.card_type === 3 || ii?.data?.card_type === 17 || ii?.data?.card_type === 22 || ii?.data?.card_type === 30 || ii?.data?.card_type === 42 || ii?.data?.card_type === 89 || ii?.data?.card_type === 206 || ii?.data?.card_type === 236)", 1),
    ("![4, 197, 1012]?.includes(item?.data?.card_type)", "!(item?.data?.card_type === 4 || item?.data?.card_type === 197 || item?.data?.card_type === 1012)", 1),
]

def optimize_scalar_membership(source):
    if SCALAR_MEMBERSHIP_MARKER in source:
        if source.count(SCALAR_MEMBERSHIP_MARKER) != 1:
            raise ValueError("Weibo scalar-membership marker duplicated")
        for old, _, _ in SCALAR_MEMBERSHIP_REWRITES:
            if old in source:
                raise ValueError("Weibo scalar-membership marker/structure drift")
        return source
    for old, new, expected in SCALAR_MEMBERSHIP_REWRITES:
        count = source.count(old)
        if count != expected:
            raise ValueError("Weibo scalar-membership inventory drift: expected %d for %s, got %d" % (expected, old, count))
        source = source.replace(old, new)
    if source.count(LAZY_MARKER) != 1:
        raise ValueError("Weibo lazy marker anchor drift")
    source = source.replace(LAZY_MARKER, LAZY_MARKER + "\n" + SCALAR_MEMBERSHIP_MARKER, 1)
    for old, _, _ in SCALAR_MEMBERSHIP_REWRITES:
        if old in source:
            raise ValueError("Weibo scalar-membership postcondition failed")
    return source



PAGE_ITEMID_MARKER = "// loon-change: Weibo /2/page cached itemid reads v1"
PAGE_ITEMID_OLD = "      if (obj?.cards?.[0]?.card_group?.length > 0) {\n        compactInPlace(obj.cards[0].card_group, c => !(c?.actionlog?.ext?.includes(\"ads_word\") || c?.itemid?.includes(\"t:51\") || c?.itemid?.includes(\"ads_word\")));\n      }\n      compactInPlace(obj.cards, i => !(\n          i.itemid?.includes(\"feed_-_invite\") ||\n          i.itemid?.includes(\"infeed_friends_recommend\") ||\n          i.itemid?.includes(\"infeed_may_interest_in\") ||\n          i.itemid?.includes(\"infeed_pagemanual3\") ||\n          i.itemid?.includes(\"infeed_weibo_mall\") ||\n          i?.mblog?.mblogtypename?.includes(\"广告\")\n        ));"
PAGE_ITEMID_NEW = "      if (obj?.cards?.[0]?.card_group?.length > 0) {\n        compactInPlace(obj.cards[0].card_group, c => {\n          if (c?.actionlog?.ext?.includes(\"ads_word\")) return false;\n          const itemId = c?.itemid;\n          return !(itemId?.includes(\"t:51\") || itemId?.includes(\"ads_word\"));\n        });\n      }\n      compactInPlace(obj.cards, i => {\n        const itemId = i.itemid;\n        return !(\n          itemId?.includes(\"feed_-_invite\") ||\n          itemId?.includes(\"infeed_friends_recommend\") ||\n          itemId?.includes(\"infeed_may_interest_in\") ||\n          itemId?.includes(\"infeed_pagemanual3\") ||\n          itemId?.includes(\"infeed_weibo_mall\") ||\n          i?.mblog?.mblogtypename?.includes(\"广告\")\n        );\n      });"

def optimize_page_filter_cached_itemid(source):
    if PAGE_ITEMID_MARKER in source:
        if source.count(PAGE_ITEMID_MARKER) != 1 or PAGE_ITEMID_OLD in source:
            raise ValueError("Weibo /2/page cached-itemid marker/structure drift")
        if PAGE_ITEMID_NEW not in source:
            raise ValueError("Weibo /2/page cached-itemid transformed block missing")
        return source
    if source.count(PAGE_ITEMID_OLD) != 1:
        raise ValueError("Weibo /2/page filter anchor drift")
    source = source.replace(PAGE_ITEMID_OLD, PAGE_ITEMID_NEW, 1)
    if source.count(SCALAR_MEMBERSHIP_MARKER) != 1:
        raise ValueError("Weibo scalar membership marker anchor drift")
    source = source.replace(SCALAR_MEMBERSHIP_MARKER, SCALAR_MEMBERSHIP_MARKER + "\n" + PAGE_ITEMID_MARKER, 1)
    return source


TOPIC_GROUP_MARKER = "// loon-change: Weibo topic-group in-place item compaction v1"
TOPIC_GROUP_OLD = """              // 超话页顶部乱七八糟
              let newII = [];
              for (let ii of item.items) {
                if (ii?.data?.hasOwnProperty(\"itemid\")) {
                  if (ii?.data?.itemid?.includes(\"mine_topics\")) {
                    // 保留我的超话
                    newII.push(ii);
                  } else if (ii?.data?.itemid?.includes(\"tab_search_input\")) {
                    // 保留搜索框
                    if (ii?.data?.hotwords) {
                      // 删除热搜词
                      ii.data.hotwords = [{word: \"搜索超话\"}];
                    }
                    newII.push(ii);
                  } else if (ii?.data?.itemid?.includes(\"poiRankList\")) {
                    // 保留地点超话 地标人气榜
                    newII.push(ii);
                  }
                } else {
                  // 放行无itemid字段的内容
                  newII.push(ii);
                }
                // 头像挂件,关注按钮
                removeAvatar(ii?.data);
                item.items = newII;
              }"""
TOPIC_GROUP_NEW = """              // 超话页顶部乱七八糟
              // loon-change: Weibo topic-group in-place item compaction v1;
              const groupItems = item.items;
              const groupLength = groupItems.length;
              let groupWrite = 0;
              for (let groupRead = 0; groupRead < groupLength; groupRead++) {
                const ii = groupItems[groupRead];
                const itemData = ii?.data;
                const itemId = itemData?.itemid;
                let keep = false;
                if (itemData?.hasOwnProperty(\"itemid\")) {
                  if (itemId?.includes(\"mine_topics\")) {
                    // 保留我的超话
                    keep = true;
                  } else if (itemId?.includes(\"tab_search_input\")) {
                    // 保留搜索框
                    if (itemData?.hotwords) {
                      // 删除热搜词
                      itemData.hotwords = [{word: \"搜索超话\"}];
                    }
                    keep = true;
                  } else if (itemId?.includes(\"poiRankList\")) {
                    // 保留地点超话 地标人气榜
                    keep = true;
                  }
                } else {
                  // 放行无itemid字段的内容
                  keep = true;
                }
                if (keep) groupItems[groupWrite++] = ii;
                // 头像挂件,关注按钮
                removeAvatar(itemData);
              }
              groupItems.length = groupWrite;"""

def optimize_topic_group_in_place(source):
    if TOPIC_GROUP_MARKER in source:
        if source.count(TOPIC_GROUP_MARKER) != 1 or TOPIC_GROUP_OLD in source or TOPIC_GROUP_NEW not in source:
            raise ValueError("Weibo topic-group compaction marker/structure drift")
        if "let newII = [];" in source or "item.items = newII;" in source:
            raise ValueError("Weibo topic-group compaction legacy allocation remains")
        return source
    if source.count(TOPIC_GROUP_OLD) != 1:
        raise ValueError("Weibo topic-group compaction anchor drift")
    source = source.replace(TOPIC_GROUP_OLD, TOPIC_GROUP_NEW, 1)
    if source.count(TOPIC_GROUP_MARKER) != 1 or "let newII = [];" in source:
        raise ValueError("Weibo topic-group compaction postcondition failed")
    return source


def rewrite_plugin(plugin):
    if LOCAL in plugin:
        if REMOTE in plugin:
            raise ValueError("mixed local and remote Weibo references")
        return plugin
    section = None
    count = 0
    output = []
    for line in plugin.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].strip().lower()
        if section == "script" and REMOTE in line:
            count += line.count(REMOTE)
            line = line.replace(REMOTE, LOCAL)
        output.append(line)
    if count != 10:
        raise ValueError("expected 10 R-Store Weibo triggers, found %d" % count)
    result = "\n".join(output)
    if REMOTE in result:
        raise ValueError("remote Weibo references remain")
    return result + ("\n" if plugin.endswith("\n") else "")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source")
    parser.add_argument("--output")
    parser.add_argument("--upstream-commit", default="unknown")
    parser.add_argument("--plugin")
    args = parser.parse_args()
    if args.source or args.output:
        if not args.source or not args.output:
            parser.error("--source and --output must be supplied together")
        result = optimize_source(Path(args.source).read_text(encoding="utf-8-sig"), args.upstream_commit)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(result, encoding="utf-8")
        print("Optimized R-Store Weibo script", len(result))
    if args.plugin:
        path = Path(args.plugin)
        path.write_text(rewrite_plugin(path.read_text(encoding="utf-8-sig")), encoding="utf-8")
        print("Routed 10 Weibo triggers to the local optimized handler")
    if not (args.source or args.output or args.plugin):
        parser.error("provide --source/--output and/or --plugin")

TOPIC_GROUP_NESTED_DATA_MARKER = "// loon-change: Weibo topic-group nested data reference cache v1"
TOPIC_GROUP_NESTED_DATA_OLD = """          if (item?.items?.length > 0) {
            if (item?.itemId === null) {
              // 超话页顶部乱七八糟
              // loon-change: Weibo topic-group in-place item compaction v1;
              const groupItems = item.items;
              const groupLength = groupItems.length;
              let groupWrite = 0;
              for (let groupRead = 0; groupRead < groupLength; groupRead++) {
                const ii = groupItems[groupRead];
                const itemData = ii?.data;
                const itemId = itemData?.itemid;
                let keep = false;
                if (itemData?.hasOwnProperty("itemid")) {
                  if (itemId?.includes("mine_topics")) {
                    // 保留我的超话
                    keep = true;
                  } else if (itemId?.includes("tab_search_input")) {
                    // 保留搜索框
                    if (itemData?.hotwords) {
                      // 删除热搜词
                      itemData.hotwords = [{word: "搜索超话"}];
                    }
                    keep = true;
                  } else if (itemId?.includes("poiRankList")) {
                    // 保留地点超话 地标人气榜
                    keep = true;
                  }
                } else {
                  // 放行无itemid字段的内容
                  keep = true;
                }
                if (keep) groupItems[groupWrite++] = ii;
                // 头像挂件,关注按钮
                removeAvatar(itemData);
              }
              groupItems.length = groupWrite;
            } else {
              for (let ii of item.items) {
                if (ii?.data) {
                  removeAvatar(ii?.data);
                  if (ii?.data?.common_struct) {
                    delete ii.data.common_struct;
                  }
                }
              }
            }
          }"""
TOPIC_GROUP_NESTED_DATA_NEW = """          // loon-change: Weibo topic-group nested array reference cache v1
          const nestedItems = item?.items;
          if (nestedItems?.length > 0) {
            if (item?.itemId === null) {
              // 超话页顶部乱七八糟
              // loon-change: Weibo topic-group in-place item compaction v1;
              const groupItems = nestedItems;
              const groupLength = groupItems.length;
              let groupWrite = 0;
              for (let groupRead = 0; groupRead < groupLength; groupRead++) {
                const ii = groupItems[groupRead];
                const itemData = ii?.data;
                const itemId = itemData?.itemid;
                let keep = false;
                if (itemData?.hasOwnProperty("itemid")) {
                  if (itemId?.includes("mine_topics")) {
                    // 保留我的超话
                    keep = true;
                  } else if (itemId?.includes("tab_search_input")) {
                    // 保留搜索框
                    if (itemData?.hotwords) {
                      // 删除热搜词
                      itemData.hotwords = [{word: "搜索超话"}];
                    }
                    keep = true;
                  } else if (itemId?.includes("poiRankList")) {
                    // 保留地点超话 地标人气榜
                    keep = true;
                  }
                } else {
                  // 放行无itemid字段的内容
                  keep = true;
                }
                if (keep) groupItems[groupWrite++] = ii;
                // 头像挂件,关注按钮
                removeAvatar(itemData);
              }
              groupItems.length = groupWrite;
            } else {
              // loon-change: Weibo topic-group nested data reference cache v1
              const nestedLength = nestedItems.length;
              for (let nestedIndex = 0; nestedIndex < nestedLength; nestedIndex++) {
                const ii = nestedItems[nestedIndex];
                const iiData = ii?.data;
                if (iiData) {
                  removeAvatar(iiData);
                  const commonStruct = iiData.common_struct;
                  if (commonStruct) {
                    delete iiData.common_struct;
                  }
                }
              }
            }
          }"""

TOPIC_GROUP_NESTED_DATA_REQUIRED = (
    "const nestedItems = item?.items;",
    "const nestedLength = nestedItems.length;",
    "const iiData = ii?.data;",
    "const commonStruct = iiData.common_struct;",
    "removeAvatar(iiData);",
)

def optimize_topic_group_nested_data_cache(source):
    """Cache nested topic-group arrays and per-item data references on hot-topic paths."""
    marker = TOPIC_GROUP_NESTED_DATA_MARKER
    if marker in source:
        if source.count(marker) != 1 or any(token not in source for token in TOPIC_GROUP_NESTED_DATA_REQUIRED):
            raise ValueError("Weibo nested topic-group data-cache structure drift")
        if TOPIC_GROUP_NESTED_DATA_OLD in source or "for (let ii of item.items)" in source or "removeAvatar(ii?.data)" in source:
            raise ValueError("Weibo repeated nested topic-group property reads remain")
        return source
    if source.count(TOPIC_GROUP_NESTED_DATA_OLD) != 1:
        raise ValueError("Weibo nested topic-group cache anchor drift")
    source = source.replace(TOPIC_GROUP_NESTED_DATA_OLD, TOPIC_GROUP_NESTED_DATA_NEW, 1)
    if source.count(marker) != 1 or any(token not in source for token in TOPIC_GROUP_NESTED_DATA_REQUIRED):
        raise ValueError("Weibo nested topic-group data-cache postcondition failed")
    if "for (let ii of item.items)" in source or "removeAvatar(ii?.data)" in source:
        raise ValueError("Weibo repeated nested topic-group property reads remain")
    return source



ROOT_COMMENT_USER_CACHE_MARKER = "// loon-change: Weibo root-comment user reference cache v1"
ROOT_COMMENT_USER_CACHE_OLD = """          if (item.user) {
            // 头像挂件,关注按钮
            removeAvatar(item);
            if (item?.user?.name === "超话社区" || item?.user?.name === "微博视频") {
              continue;
            }
          }"""
ROOT_COMMENT_USER_CACHE_NEW = """          // loon-change: Weibo root-comment user reference cache v1
          const commentUser = item.user;
          if (commentUser) {
            // 头像挂件,关注按钮
            removeAvatar(item, commentUser);
            const commentUserName = commentUser.name;
            if (commentUserName === "超话社区" || commentUserName === "微博视频") {
              continue;
            }
          }"""

def optimize_root_comment_user_cache(source):
    """Reuse root-comment user/name references during the high-frequency comment loop."""
    marker = ROOT_COMMENT_USER_CACHE_MARKER
    required = (
        marker,
        "const commentUser = item.user;",
        "removeAvatar(item, commentUser);",
        "const commentUserName = commentUser.name;",
        'commentUserName === "超话社区" || commentUserName === "微博视频"',
    )
    if marker in source:
        if source.count(marker) != 1 or any(token not in source for token in required):
            raise ValueError("Weibo root-comment user-cache structure drift")
        if "item?.user?.name ===" in source or "removeAvatar(item);" in source[source.index(marker):source.index(marker)+600]:
            raise ValueError("Weibo repeated root-comment user property reads remain")
        return source
    if source.count(ROOT_COMMENT_USER_CACHE_OLD) != 1:
        raise ValueError("Weibo root-comment user-cache anchor drift")
    source = source.replace(ROOT_COMMENT_USER_CACHE_OLD, ROOT_COMMENT_USER_CACHE_NEW, 1)
    if source.count(marker) != 1 or any(token not in source for token in required):
        raise ValueError("Weibo root-comment user-cache postcondition failed")
    return source



REMOVE_AVATAR_PROPERTY_CACHE_MARKER = "// loon-change: Weibo removeAvatar single-read property cache v1"
REMOVE_AVATAR_HELPER_PROPERTY_CACHE_NEW = "function removeAvatar(data, user = data?.user) {\n  // loon-change: Weibo removeAvatar cached user reference v1\n  // loon-change: Weibo removeAvatar single-read property cache v1\n  const blockCardBg = data?.block_card_bg;\n  if (blockCardBg) {\n    modified = true;\n    delete data.block_card_bg;\n  }\n  const buttons = data?.buttons;\n  if (buttons) {\n    modified = true;\n    delete data.buttons;\n  }\n  const cardId = data?.cardid;\n  if (cardId) {\n    modified = true;\n    delete data.cardid;\n  }\n  const icons = data?.icons;\n  if (icons) {\n    modified = true;\n    delete data.icons;\n  }\n  const mblogButtons = data?.mblog_buttons;\n  if (mblogButtons) {\n    // 转发按钮图标\n    modified = true;\n    delete data.mblog_buttons;\n  }\n  const picBgNew = data?.pic_bg_new;\n  if (picBgNew) {\n    modified = true;\n    delete data.pic_bg_new;\n  }\n  const avatarGjId = user?.avatargj_id;\n  if (avatarGjId) {\n    modified = true;\n    delete user.avatargj_id;\n  }\n  const avatarExtendInfo = user?.avatar_extend_info;\n  if (avatarExtendInfo) {\n    modified = true;\n    delete user.avatar_extend_info;\n  }\n  const userCardId = user?.cardid;\n  if (userCardId) {\n    modified = true;\n    delete user.cardid;\n  }\n  const userIcons = user?.icons;\n  if (userIcons) {\n    modified = true;\n    delete user.icons;\n  }\n  const memberType = user?.mbtype;\n  if (memberType) {\n    // 会员等级图标\n    modified = true;\n    delete user.mbtype;\n  }\n}"

def optimize_remove_avatar_property_cache(source):
    """Read each removable Weibo avatar decoration field once before deleting it."""
    marker = REMOVE_AVATAR_PROPERTY_CACHE_MARKER
    start_token = "function removeAvatar(data, user = data?.user) {"
    end_token = "\n}\n\n// 移除信息流关注按钮"
    if start_token not in source or end_token not in source:
        raise ValueError("Weibo removeAvatar property-cache helper boundary drift")
    start = source.index(start_token)
    end = source.index(end_token, start) + 2
    block = source[start:end]
    required = (
        marker,
        "const blockCardBg = data?.block_card_bg;",
        "const mblogButtons = data?.mblog_buttons;",
        "const avatarGjId = user?.avatargj_id;",
        "const avatarExtendInfo = user?.avatar_extend_info;",
        "const userCardId = user?.cardid;",
        "const userIcons = user?.icons;",
        "const memberType = user?.mbtype;",
    )
    if marker in block:
        if block.count(marker) != 1 or any(token not in block for token in required):
            raise ValueError("Weibo removeAvatar single-read cache structure drift")
        if "if (data?.block_card_bg)" in block or "if (user?.avatargj_id)" in block:
            raise ValueError("Weibo repeated removeAvatar property reads remain")
        return source
    if block != REMOVE_AVATAR_HELPER_NEW:
        raise ValueError("Weibo removeAvatar property-cache source anchor changed")
    source = source[:start] + REMOVE_AVATAR_HELPER_PROPERTY_CACHE_NEW + source[end:]
    return source



COMMENT_DECORATION_SINGLE_READ_MARKER = "// loon-change: Weibo comment data decoration single-read cache v1"
ROOT_COMMENT_DECORATION_SINGLE_READ_MARKER = "// loon-change: Weibo root-comment decoration single-read cache v1"
REPLY_DECORATION_SINGLE_READ_MARKER = "// loon-change: Weibo reply-comment decoration single-read cache v1"
ROOT_COMMENT_BUBBLE_SINGLE_READ_MARKER = "// loon-change: Weibo rootComment bubble single-read cache v1"

COMMENT_DECORATION_OLD_TOP = """            // 评论气泡
            if (commentData?.comment_bubble) {
              modified = true;
              delete commentData.comment_bubble;
            }
            // 评论弹幕
            if (commentData?.comment_bullet_screens_message) {
              modified = true;
              delete commentData.comment_bullet_screens_message;
            }
            // 热评小图标 弹幕 首评
            if (commentData?.hot_icon) {
              modified = true;
              delete commentData.hot_icon;
            }
            // 会员气泡按钮
            if (commentData?.vip_button) {
              modified = true;
              delete commentData.vip_button;
            }"""
COMMENT_DECORATION_NEW_TOP = """            // loon-change: Weibo comment data decoration single-read cache v1
            // 评论气泡
            const commentBubble = commentData?.comment_bubble;
            if (commentBubble) {
              modified = true;
              delete commentData.comment_bubble;
            }
            // 评论弹幕
            const commentBulletMessage = commentData?.comment_bullet_screens_message;
            if (commentBulletMessage) {
              modified = true;
              delete commentData.comment_bullet_screens_message;
            }
            // 热评小图标 弹幕 首评
            const commentHotIcon = commentData?.hot_icon;
            if (commentHotIcon) {
              modified = true;
              delete commentData.hot_icon;
            }
            // 会员气泡按钮
            const commentVipButton = commentData?.vip_button;
            if (commentVipButton) {
              modified = true;
              delete commentData.vip_button;
            }"""
COMMENT_DECORATION_OLD_ROOT = """          // 评论气泡
          if (item?.comment_bubble) {
            modified = true;
            delete item.comment_bubble;
          }
          // 评论弹幕
          if (item?.comment_bullet_screens_message) {
            modified = true;
            delete item.comment_bullet_screens_message;
          }
          // 热评小图标 弹幕 首评
          if (item?.hot_icon) {
            modified = true;
            delete item.hot_icon;
          }
          // 会员气泡按钮
          if (item?.vip_button) {
            modified = true;
            delete item.vip_button;
          }"""
COMMENT_DECORATION_NEW_ROOT = """          // loon-change: Weibo root-comment decoration single-read cache v1
          // 评论气泡
          const rootCommentBubble = item?.comment_bubble;
          if (rootCommentBubble) {
            modified = true;
            delete item.comment_bubble;
          }
          // 评论弹幕
          const rootCommentBulletMessage = item?.comment_bullet_screens_message;
          if (rootCommentBulletMessage) {
            modified = true;
            delete item.comment_bullet_screens_message;
          }
          // 热评小图标 弹幕 首评
          const rootCommentHotIcon = item?.hot_icon;
          if (rootCommentHotIcon) {
            modified = true;
            delete item.hot_icon;
          }
          // 会员气泡按钮
          const rootCommentVipButton = item?.vip_button;
          if (rootCommentVipButton) {
            modified = true;
            delete item.vip_button;
          }"""
COMMENT_DECORATION_OLD_REPLIES = """        if (item?.user?.icons) {
          modified = true;
          delete item.user.icons;
        }
        if (item?.reply_comment?.comment_badge) {
          modified = true;
          delete item.reply_comment.comment_badge;
        }"""
COMMENT_DECORATION_NEW_REPLIES = """        // loon-change: Weibo reply-comment decoration single-read cache v1
        const replyUser = item?.user;
        const replyUserIcons = replyUser?.icons;
        if (replyUserIcons) {
          modified = true;
          delete replyUser.icons;
        }
        const replyComment = item?.reply_comment;
        const replyCommentBadge = replyComment?.comment_badge;
        if (replyCommentBadge) {
          modified = true;
          delete replyComment.comment_badge;
        }"""
COMMENT_DECORATION_OLD_ROOT_COMMENT = """    if (obj?.rootComment) {
      if (obj?.rootComment?.comment_bubble) {
        modified = true;
        delete obj.rootComment.comment_bubble;
      }
    }"""
COMMENT_DECORATION_NEW_ROOT_COMMENT = """    // loon-change: Weibo rootComment bubble single-read cache v1
    const rootComment = obj?.rootComment;
    const rootCommentBubble = rootComment?.comment_bubble;
    if (rootCommentBubble) {
      modified = true;
      delete rootComment.comment_bubble;
    }"""

def optimize_comment_decoration_single_read(source):
    """Cache frequently removed Weibo comment decoration values once before deletion."""
    markers = (
        COMMENT_DECORATION_SINGLE_READ_MARKER,
        ROOT_COMMENT_DECORATION_SINGLE_READ_MARKER,
        REPLY_DECORATION_SINGLE_READ_MARKER,
        ROOT_COMMENT_BUBBLE_SINGLE_READ_MARKER,
    )
    required = (
        "const commentBubble = commentData?.comment_bubble;",
        "const commentBulletMessage = commentData?.comment_bullet_screens_message;",
        "const commentHotIcon = commentData?.hot_icon;",
        "const commentVipButton = commentData?.vip_button;",
        "const rootCommentBubble = item?.comment_bubble;",
        "const rootCommentBulletMessage = item?.comment_bullet_screens_message;",
        "const rootCommentHotIcon = item?.hot_icon;",
        "const rootCommentVipButton = item?.vip_button;",
        "const replyUser = item?.user;",
        "const replyUserIcons = replyUser?.icons;",
        "const replyComment = item?.reply_comment;",
        "const replyCommentBadge = replyComment?.comment_badge;",
        "const rootComment = obj?.rootComment;",
        "const rootCommentBubble = rootComment?.comment_bubble;",
    )
    if any(marker in source for marker in markers):
        if any(source.count(marker) != 1 for marker in markers) or any(token not in source for token in required):
            raise ValueError("Weibo comment decoration single-read cache structure drift")
        old_patterns = (
            "if (commentData?.comment_bubble)",
            "if (commentData?.comment_bullet_screens_message)",
            "if (commentData?.hot_icon)",
            "if (commentData?.vip_button)",
            "if (item?.comment_bubble)",
            "if (item?.comment_bullet_screens_message)",
            "if (item?.hot_icon)",
            "if (item?.vip_button)",
            "if (item?.user?.icons)",
            "if (item?.reply_comment?.comment_badge)",
            "if (obj?.rootComment?.comment_bubble)",
        )
        if any(token in source for token in old_patterns):
            raise ValueError("Weibo repeated comment decoration property reads remain")
        return source

    replacements = (
        (COMMENT_DECORATION_OLD_TOP, COMMENT_DECORATION_NEW_TOP, "datas comment decorations"),
        (COMMENT_DECORATION_OLD_ROOT, COMMENT_DECORATION_NEW_ROOT, "root comment decorations"),
        (COMMENT_DECORATION_OLD_REPLIES, COMMENT_DECORATION_NEW_REPLIES, "reply comment decorations"),
        (COMMENT_DECORATION_OLD_ROOT_COMMENT, COMMENT_DECORATION_NEW_ROOT_COMMENT, "rootComment bubble"),
    )
    for old, new, label in replacements:
        if source.count(old) != 1:
            raise ValueError("Weibo " + label + " cache anchor drift")
        source = source.replace(old, new, 1)
    if any(source.count(marker) != 1 for marker in markers) or any(token not in source for token in required):
        raise ValueError("Weibo comment decoration single-read cache postcondition failed")
    return source


COMMENT_ARRAY_REFERENCE_CACHE_MARKER = "// loon-change: Weibo comment top-level array reference cache v1"

def optimize_comment_array_reference_cache(source):
    """Read the mutually exclusive Weibo comment response arrays once per tested branch."""
    start = '} else if (url.includes("/2/comments/build_comments")) {'
    end = '} else if (url.includes("/2/container/asyn")) {'
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError("Weibo comment-array cache route boundary drift")
    left = source.index(start)
    right = source.index(end, left + len(start))
    block = source[left:right]
    required = (
        COMMENT_ARRAY_REFERENCE_CACHE_MARKER,
        "const commentDatas = obj?.datas;",
        "let rootComments;",
        "let replyComments;",
        "if (commentDatas?.length > 0)",
        "(rootComments = obj?.root_comments)?.length > 0",
        "(replyComments = obj?.comments)?.length > 0",
        "const __loonSource30 = commentDatas;",
        "const __loonSource29 = rootComments;",
        "const __loonSource28 = replyComments;",
    )
    if COMMENT_ARRAY_REFERENCE_CACHE_MARKER in block:
        if block.count(COMMENT_ARRAY_REFERENCE_CACHE_MARKER) != 1 or any(token not in block for token in required):
            raise ValueError("Weibo comment-array reference cache structure drift")
        old = (
            "if (obj?.datas?.length > 0)",
            "obj?.root_comments?.length > 0",
            "obj?.comments?.length > 0",
            "const __loonSource30 = obj.datas;",
            "const __loonSource29 = obj.root_comments;",
            "const __loonSource28 = obj.comments;",
        )
        if any(token in block for token in old):
            raise ValueError("Weibo repeated top-level comment array reads remain")
        return source
    replacements = (
        ("    if (obj?.datas?.length > 0) {",
         "    // loon-change: Weibo comment top-level array reference cache v1\n"
         "    const commentDatas = obj?.datas;\n"
         "    let rootComments;\n"
         "    let replyComments;\n"
         "    if (commentDatas?.length > 0) {"),
        ("    } else if (obj?.root_comments?.length > 0) {",
         "    } else if ((rootComments = obj?.root_comments)?.length > 0) {"),
        ("    } else if (obj?.comments?.length > 0) {",
         "    } else if ((replyComments = obj?.comments)?.length > 0) {"),
        ("      const __loonSource30 = obj.datas;", "      const __loonSource30 = commentDatas;"),
        ("      const __loonSource29 = obj.root_comments;", "      const __loonSource29 = rootComments;"),
        ("      const __loonSource28 = obj.comments;", "      const __loonSource28 = replyComments;"),
    )
    for old, new in replacements:
        if block.count(old) != 1:
            raise ValueError("Weibo comment-array cache anchor drift: " + old[:70])
        block = block.replace(old, new, 1)
    if any(token not in block for token in required):
        raise ValueError("Weibo comment-array reference cache postcondition failed")
    return source[:left] + block + source[right:]


FOLLOWING_TIMELINE_DATA_CACHE_MARKER = "// loon-change: Weibo following timeline nested reference cache v1"

def optimize_following_timeline_data_cache(source):
    """Cache the high-frequency following-feed item and nested response references."""
    start = '} else if (url.includes("/2/statuses/container_timeline?") || url.includes("/2/statuses/container_timeline_unread")) {'
    end = '} else if (url.includes("/2/statuses/container_timeline_topic")) {'
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError("Weibo following timeline cache route boundary drift")
    left = source.index(start)
    right = source.index(end, left + len(start))
    block = source[left:right]
    required = (
        FOLLOWING_TIMELINE_DATA_CACHE_MARKER,
        "const timelineItems = obj?.items;",
        "const timelineItemsLength = timelineItems?.length || 0;",
        "const __loonSource2 = timelineItems;",
        "const __loonLength2 = timelineItemsLength;",
        "const itemData = item?.data;",
        "const itemTitle = itemData?.title;",
        "const screenNameSuffixNew = itemData?.screen_name_suffix_new;",
        "const itemUser = itemData?.user;",
        "const tagStruct = itemData?.tag_struct;",
        "removeFeedAd(itemData);",
        "removeVoteInfo(itemData);",
    )
    if FOLLOWING_TIMELINE_DATA_CACHE_MARKER in block:
        if block.count(FOLLOWING_TIMELINE_DATA_CACHE_MARKER) != 1 or any(token not in block for token in required):
            raise ValueError("Weibo following timeline cache structure drift")
        stripped = block.replace("const itemData = item?.data;", "")
        if any(token in stripped for token in ("item?.data", "item.data", "obj?.items?.length", "const __loonLength2 = __loonSource2.length;")):
            raise ValueError("Weibo following timeline repeated data/array reads remain")
        return source
    replacements = (
        ("    if (obj?.items?.length > 0) {",
         "    const timelineItems = obj?.items;\n"
         "    const timelineItemsLength = timelineItems?.length || 0;\n"
         "    if (timelineItemsLength > 0) {"),
        ("      const __loonSource2 = obj.items;", "      const __loonSource2 = timelineItems;"),
        ("      const __loonLength2 = __loonSource2.length;", "      const __loonLength2 = timelineItemsLength;"),
        ("        let item = __loonSource2[__loonRead2];",
         "        let item = __loonSource2[__loonRead2];\n        const itemData = item?.data;"),
        ("        if (!isAd(item?.data)) {", "        if (!isAd(itemData)) {"),
        ("            removeFeedAd(item?.data);", "            removeFeedAd(itemData);"),
        ("            if (item.data?.title?.structs) {",
         "            const itemTitle = itemData?.title;\n            if (itemTitle?.structs) {"),
        ("            if (item?.data?.action_button_icon_dic) {", "            if (itemData?.action_button_icon_dic) {"),
        ("              delete item.data.action_button_icon_dic;", "              delete itemData.action_button_icon_dic;"),
        ("            removeVoteInfo(item?.data);", "            removeVoteInfo(itemData);"),
        ("            if (item?.data?.screen_name_suffix_new?.length > 0) {\n"
         "              if (item?.data?.screen_name_suffix_new?.[3]?.content === \"快转了\") {",
         "            const screenNameSuffixNew = itemData?.screen_name_suffix_new;\n"
         "            if (screenNameSuffixNew?.length > 0) {\n"
         "              if (screenNameSuffixNew[3]?.content === \"快转了\") {"),
        ("            if (item?.data?.title?.text?.includes(\"精选\")) {", "            if (itemTitle?.text?.includes(\"精选\")) {"),
        ("            if (item?.data?.user?.following === false) {",
         "            const itemUser = itemData?.user;\n            if (itemUser?.following === false) {"),
        ("            if (item?.data?.user?.unfollowing_recom_switch === 1) {\n"
         "              item.data.user.unfollowing_recom_switch = 0;",
         "            if (itemUser?.unfollowing_recom_switch === 1) {\n"
         "              itemUser.unfollowing_recom_switch = 0;"),
        ("            if (item?.data?.tag_struct?.length > 0) {\n"
         "              item.data.tag_struct = [];",
         "            const tagStruct = itemData?.tag_struct;\n"
         "            if (tagStruct?.length > 0) {\n"
         "              itemData.tag_struct = [];"),
    )
    for old, new in replacements:
        if block.count(old) != 1:
            raise ValueError("Weibo following timeline cache anchor drift: " + old[:75])
        block = block.replace(old, new, 1)
    if any(token not in block for token in required):
        raise ValueError("Weibo following timeline cache postcondition failed")
    block = block.replace(start, start + "\n    " + FOLLOWING_TIMELINE_DATA_CACHE_MARKER, 1)
    stripped = block.replace("const itemData = item?.data;", "")
    if any(token in stripped for token in ("item?.data", "item.data", "obj?.items?.length", "const __loonLength2 = __loonSource2.length;")):
        raise ValueError("Weibo following timeline repeated data/array reads remain")
    return source[:left] + block + source[right:]


HOT_TIMELINE_DATA_CACHE_MARKER = "// loon-change: Weibo hot timeline nested reference cache v1"

def optimize_hot_timeline_data_cache(source):
    """Cache item/status arrays, their lengths, and each hot-feed card data reference."""
    start = '} else if (url.includes("/2/statuses/container_timeline_hot") || url.includes("/2/statuses/unread_hot_timeline")) {'
    end = '} else if (url.includes("/2/statuses/container_timeline?") || url.includes("/2/statuses/container_timeline_unread")) {'
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError("Weibo hot timeline cache route boundary drift")
    left = source.index(start)
    right = source.index(end, left + len(start))
    block = source[left:right]
    required = (
        HOT_TIMELINE_DATA_CACHE_MARKER,
        "const hotItems = obj?.items;",
        "const hotItemsLength = hotItems?.length || 0;",
        "const __loonSource4 = hotItems;",
        "const __loonLength4 = hotItemsLength;",
        "const itemData = item?.data;",
        "if (!isAd(itemData))",
        "removeFeedAd(itemData);",
        "removeVoteInfo(itemData);",
        "const hotStatuses = obj?.statuses;",
        "const hotStatusesLength = hotStatuses?.length || 0;",
        "const __loonSource3 = hotStatuses;",
        "const __loonLength3 = hotStatusesLength;",
    )
    if HOT_TIMELINE_DATA_CACHE_MARKER in block:
        if block.count(HOT_TIMELINE_DATA_CACHE_MARKER) != 1 or any(token not in block for token in required):
            raise ValueError("Weibo hot timeline cache structure drift")
        stripped = block.replace("const itemData = item?.data;", "")
        old = ("item?.data", "obj?.items?.length", "obj?.statuses?.length",
               "const __loonLength4 = __loonSource4.length;", "const __loonLength3 = __loonSource3.length;")
        if any(token in stripped for token in old):
            raise ValueError("Weibo hot timeline repeated response reads remain")
        return source
    replacements = (
        ("    if (obj?.items?.length > 0) {",
         "    const hotItems = obj?.items;\n"
         "    const hotItemsLength = hotItems?.length || 0;\n"
         "    if (hotItemsLength > 0) {"),
        ("      const __loonSource4 = obj.items;", "      const __loonSource4 = hotItems;"),
        ("      const __loonLength4 = __loonSource4.length;", "      const __loonLength4 = hotItemsLength;"),
        ("        let item = __loonSource4[__loonRead4];",
         "        let item = __loonSource4[__loonRead4];\n        const itemData = item?.data;"),
        ("        if (!isAd(item?.data)) {", "        if (!isAd(itemData)) {"),
        ("            removeFeedAd(item?.data);", "            removeFeedAd(itemData);"),
        ("            removeVoteInfo(item?.data);", "            removeVoteInfo(itemData);"),
        ("    if (obj?.statuses?.length > 0) {",
         "    const hotStatuses = obj?.statuses;\n"
         "    const hotStatusesLength = hotStatuses?.length || 0;\n"
         "    if (hotStatusesLength > 0) {"),
        ("      const __loonSource3 = obj.statuses;", "      const __loonSource3 = hotStatuses;"),
        ("      const __loonLength3 = __loonSource3.length;", "      const __loonLength3 = hotStatusesLength;"),
    )
    for old, new in replacements:
        if block.count(old) != 1:
            raise ValueError("Weibo hot timeline cache anchor drift: " + old[:75])
        block = block.replace(old, new, 1)
    if any(token not in block for token in required):
        raise ValueError("Weibo hot timeline cache postcondition failed")
    block = block.replace(start, start + "\n    " + HOT_TIMELINE_DATA_CACHE_MARKER, 1)
    stripped = block.replace("const itemData = item?.data;", "")
    if any(token in stripped for token in ("item?.data", "obj?.items?.length", "obj?.statuses?.length",
                                            "const __loonLength4 = __loonSource4.length;",
                                            "const __loonLength3 = __loonSource3.length;")):
        raise ValueError("Weibo hot timeline repeated response reads remain")
    return source[:left] + block + source[right:]


FLOWLIST_ASYN_REFERENCE_CACHE_MARKER = "// loon-change: Weibo flowlist/asyn nested reference cache v1"

def optimize_flowlist_asyn_nested_reference_cache(source):
    """Cache top-level/nested array and card references on Weibo flowlist/asyn paths."""
    asyn_start = '} else if (url.includes("/2/container/asyn")) {'
    asyn_end = '} else if (url.includes("/2/direct_messages/user_list")) {'
    flow_start = '} else if (url.includes("/2/flowlist")) {'
    flow_end = '} else if (url.includes("/2/flowpage")) {'
    if any(source.count(token) != 1 for token in (asyn_start, asyn_end, flow_start, flow_end)):
        raise ValueError("Weibo flowlist/asyn route boundary drift")
    def extract(start, end):
        left = source.index(start)
        right = source.index(end, left + len(start))
        return source[left:right]
    asyn = extract(asyn_start, asyn_end)
    flow = extract(flow_start, flow_end)
    required_asyn = (
        "// loon-change: Weibo container/asyn nested reference cache v1",
        "const asynItems = obj?.items;",
        "const asynItemsLength = asynItems?.length || 0;",
        "const itemData = item?.data;",
        "const itemId = item?.itemId;",
        "const nestedItems = item?.items;",
        "const nestedItemsLength = nestedItems?.length || 0;",
        "const nestedData = nestedItem?.data;",
    )
    required_flow = (
        "// loon-change: Weibo flowlist nested reference cache v1",
        "const flowItems = obj?.items;",
        "const flowItemsLength = flowItems?.length || 0;",
        "const channelInfo = obj?.channelInfo;",
        "const flowChannels = channelInfo?.channels;",
        "const flowChannelCount = flowChannels?.length || 0;",
        "const nestedItems = item?.items;",
        "const nestedItemsLength = nestedItems?.length || 0;",
        "const nestedData = nestedItem?.data;",
        "const flowId = tab?.flowId;",
        "const __loonLength26 = flowChannelCount;",
    )
    if FLOWLIST_ASYN_REFERENCE_CACHE_MARKER in source:
        if source.count(FLOWLIST_ASYN_REFERENCE_CACHE_MARKER) != 1 or any(x not in asyn for x in required_asyn) or any(x not in flow for x in required_flow):
            raise ValueError("Weibo flowlist/asyn reference cache structure drift")
        forbidden_asyn = ("obj?.items?.length", "const __loonSource27 = obj.items;", "item?.items?.length", "for (let i of item.items)", "removeAvatar(i?.data)", "removeVoteInfo(i?.data)", "item?.itemId")
        forbidden_flow = ("obj?.items?.length", "obj?.channelInfo?.channels?.length", "const __loonSource26 = obj.channelInfo.channels;", "item?.items?.length", "for (let i of item.items)", "removeAvatar(i?.data)", "removeVoteInfo(i?.data)", "tab?.flowId")
        if any(x in asyn for x in forbidden_asyn) or any(x in flow for x in forbidden_flow):
            raise ValueError("Weibo flowlist/asyn repeated property reads remain")
        return source
    changes_asyn = (
        ("    if (obj?.items?.length > 0) {",
         "    const asynItems = obj?.items;\n"
         "    const asynItemsLength = asynItems?.length || 0;\n"
         "    if (asynItemsLength > 0) {"),
        ("      const __loonSource27 = obj.items;", "      const __loonSource27 = asynItems;"),
        ("      const __loonLength27 = __loonSource27.length;", "      const __loonLength27 = asynItemsLength;"),
        ("        let item = __loonSource27[__loonRead27];\n"
         "        // 关注按钮\n"
         "        removeAvatar(item?.data);\n"
         "        if (/infeed_may_interest_in/.test(item?.itemId)) {",
         "        let item = __loonSource27[__loonRead27];\n"
         "        const itemData = item?.data;\n"
         "        const itemId = item?.itemId;\n"
         "        // 关注按钮\n"
         "        removeAvatar(itemData);\n"
         "        if (/infeed_may_interest_in/.test(itemId)) {"),
        ("        if (item?.itemId === null) {", "        if (itemId === null) {"),
        ("        if (item?.items?.length > 0) {\n"
         "          for (let i of item.items) {\n"
         "            // 背景卡片\n"
         "            removeAvatar(i?.data);\n"
         "            // 投票窗口\n"
         "            removeVoteInfo(i?.data);\n"
         "          }\n"
         "        }",
         "        const nestedItems = item?.items;\n"
         "        const nestedItemsLength = nestedItems?.length || 0;\n"
         "        if (nestedItemsLength > 0) {\n"
         "          for (let nestedIndex = 0; nestedIndex < nestedItemsLength; nestedIndex++) {\n"
         "            const nestedItem = nestedItems[nestedIndex];\n"
         "            const nestedData = nestedItem?.data;\n"
         "            // 背景卡片\n"
         "            removeAvatar(nestedData);\n"
         "            // 投票窗口\n"
         "            removeVoteInfo(nestedData);\n"
         "          }\n"
         "        }"),
    )
    changes_flow = (
        ("    if (obj?.items?.length > 0) {\n"
         "      for (let item of obj.items) {\n"
         "        if (item?.items?.length > 0) {\n"
         "          for (let i of item.items) {\n"
         "            // 背景卡片\n"
         "            removeAvatar(i?.data);\n"
         "            // 投票窗口\n"
         "            removeVoteInfo(i?.data);\n"
         "          }\n"
         "        }\n"
         "      }\n"
         "    }\n"
         "    if (obj?.channelInfo?.channels?.length > 0) {\n"
         "      const __loonSource26 = obj.channelInfo.channels;",
         "    const flowItems = obj?.items;\n"
         "    const flowItemsLength = flowItems?.length || 0;\n"
         "    if (flowItemsLength > 0) {\n"
         "      for (let itemIndex = 0; itemIndex < flowItemsLength; itemIndex++) {\n"
         "        const item = flowItems[itemIndex];\n"
         "        const nestedItems = item?.items;\n"
         "        const nestedItemsLength = nestedItems?.length || 0;\n"
         "        if (nestedItemsLength > 0) {\n"
         "          for (let nestedIndex = 0; nestedIndex < nestedItemsLength; nestedIndex++) {\n"
         "            const nestedItem = nestedItems[nestedIndex];\n"
         "            const nestedData = nestedItem?.data;\n"
         "            // 背景卡片\n"
         "            removeAvatar(nestedData);\n"
         "            // 投票窗口\n"
         "            removeVoteInfo(nestedData);\n"
         "          }\n"
         "        }\n"
         "      }\n"
         "    }\n"
         "    const channelInfo = obj?.channelInfo;\n"
         "    const flowChannels = channelInfo?.channels;\n"
         "    const flowChannelCount = flowChannels?.length || 0;\n"
         "    if (flowChannelCount > 0) {\n"
         "      const __loonSource26 = flowChannels;"),
        ("      const __loonLength26 = __loonSource26.length;", "      const __loonLength26 = flowChannelCount;"),
        ("        let tab = __loonSource26[__loonRead26];\n"
         "        if (/_selfrecomm/.test(tab?.flowId)) {",
         "        let tab = __loonSource26[__loonRead26];\n"
         "        const flowId = tab?.flowId;\n"
         "        if (/_selfrecomm/.test(flowId)) {"),
        ("        } else if (/_chaohua/.test(tab?.flowId)) {",
         "        } else if (/_chaohua/.test(flowId)) {"),
    )
    def patch_block(source_block, changes, label):
        for old, new in changes:
            if source_block.count(old) != 1:
                raise ValueError("Weibo " + label + " cache anchor drift: " + old[:72])
            source_block = source_block.replace(old, new, 1)
        return source_block
    asyn = patch_block(asyn, changes_asyn, "container/asyn")
    flow = patch_block(flow, changes_flow, "flowlist")
    if any(x not in asyn for x in required_asyn) or any(x not in flow for x in required_flow):
        raise ValueError("Weibo flowlist/asyn reference-cache postcondition failed")
    asyn = asyn.replace(asyn_start, asyn_start + "\n    // loon-change: Weibo container/asyn nested reference cache v1", 1)
    flow = flow.replace(flow_start, flow_start + "\n    // loon-change: Weibo flowlist nested reference cache v1", 1)
    return source[:source.index(asyn_start)] + asyn + source[source.index(asyn_end):source.index(flow_start)] + flow + source[source.index(flow_end):]



if __name__ == "__main__":
    main()
