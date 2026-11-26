#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a reproducibly optimized, local SMZDM R-Store response handler."""
from __future__ import annotations

import argparse
from pathlib import Path

REMOTE = "https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/smzdm.js"
LOCAL = "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/smzdm/smzdm.js"
EXPECTED_TRIGGERS = 9
MARKER = "// loon-change: SMZDM in-place compaction and lazy serialization v1; upstream zirawell/R-Store@"
HELPERS = '''
let modified = false;
function compactInPlace(items, keep) {
    let write = 0;
    const length = items.length;
    for (let read = 0; read < length; read++) {
        const item = items[read];
        if (keep(item, read)) {
            if (write !== read) items[write] = item;
            write++;
        }
    }
    if (write !== length) {
        items.length = write;
        modified = true;
    }
    return items;
}

function deleteIfPresent(target, key) {
    if (target != null && Object.prototype.hasOwnProperty.call(target, key)) {
        delete target[key];
        modified = true;
    }
}
'''


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise ValueError(f"SMZDM upstream {label} anchor changed: expected 1, got {count}")
    return source.replace(old, new, 1)


def optimize_source(source: str, commit: str = "unknown") -> str:
    if MARKER in source:
        if source.count(MARKER) != 1:
            raise ValueError("SMZDM optimization marker count drift")
        for forbidden in (".filter(", ".map("):
            if forbidden in source:
                raise ValueError("SMZDM optimized snapshot still allocates through %s" % forbidden)
        required = (
            "if (!$response.body) {", "function compactInPlace(items, keep)",
            "function deleteIfPresent(target, key)", "if (modified) {",
        )
        if any(token not in source for token in required) or not source.rstrip().endswith("}"):
            raise ValueError("SMZDM optimized snapshot structure drift")
        return source

    source = replace_once(
        source,
        "if (!$response.body) $done({});",
        "if (!$response.body) {\n    $done({});\n} else {",
        "empty-body guard",
    )
    source = replace_once(source, "let obj = JSON.parse(body);", "let obj = JSON.parse(body);\n" + HELPERS, "JSON parse")

    source = replace_once(
        source,
        '''const fixPos = (arr) => {
    for (let i = 0; i < arr.length; i++) {
        arr[i].pos = i + 1;
    }
};''',
        '''const fixPos = (arr) => {
    for (let i = 0; i < arr.length; i++) {
        if (arr[i].pos !== i + 1) {
            arr[i].pos = i + 1;
            modified = true;
        }
    }
};''',
        "position normalization",
    )

    source = replace_once(
        source,
        '''    const recursivelyFilterByCellType = (data) => {
        if (Array.isArray(data)) {
            return data.map(item => recursivelyFilterByCellType(item)).filter(Boolean);
        } else if (typeof data === 'object') {
            if (data['cell_type'] === '23008' || data['cell_type'] === '23005' || data['cell_type'] === '23024') {
                return null;
            } else {
                for (const key in data) {
                    data[key] = recursivelyFilterByCellType(data[key]);
                }
                return data;
            }
        }
        return data;
    };''',
        '''    const recursivelyFilterByCellType = (data) => {
        if (Array.isArray(data)) {
            compactInPlace(data, item => Boolean(recursivelyFilterByCellType(item)));
        } else if (data !== null && typeof data === "object") {
            const cellType = data.cell_type;
            if (cellType === "23008" || cellType === "23005" || cellType === "23024") {
                modified = true;
                return null;
            }
            for (const key in data) {
                data[key] = recursivelyFilterByCellType(data[key]);
            }
        }
        return data;
    };''',
        "recursive cell-type filter",
    )

    replacements = [
        (
            '''obj.data.component = obj.data.component.filter((item) =>
        item.zz_type === "circular_banner" || item.zz_type === "fixed_banner" || item.zz_type === "filter" || item.zz_type === "list"
    );''',
            '''compactInPlace(obj.data.component, item =>
        item.zz_type === "circular_banner" || item.zz_type === "fixed_banner" || item.zz_type === "filter" || item.zz_type === "list"
    );''', "homepage component filter"),
        (
            'obj.data.functions = obj.data.functions.filter((item) => item.type === "message");',
            'compactInPlace(obj.data.functions, item => item.type === "message");', "homepage functions filter"),
        (
            'obj.data = obj.data.filter((item) => item.id === "40" || item.id === "20");',
            'compactInPlace(obj.data, item => item.id === "40" || item.id === "20");', "app home filter"),
        (
            'obj.data.rows = obj.data.rows.filter(item => item.model_type !== "ads");',
            'compactInPlace(obj.data.rows, item => item.model_type !== "ads");', "ranking rows filter"),
        (
            'obj.data.search_hot.home = obj.data.search_hot.home.filter(item => item.pos);',
            'compactInPlace(obj.data.search_hot.home, item => item.pos);', "hot tags filter"),
        (
            'obj.data.services = obj.data.services.filter((item) => item.type === "articel_manage" || item.type === "199794" || item.type === "199796");',
            'compactInPlace(obj.data.services, item => item.type === "articel_manage" || item.type === "199794" || item.type === "199796");', "services filter"),
        (
            '''obj.data.rows = obj.data.rows.filter(
        (i) => !(i?.hasOwnProperty("ad_banner_id") || ["ad_campaign_id_", "ad_campaign_name", "abs_position"]?.includes(i?.ad))
    );''',
            '''compactInPlace(obj.data.rows,
        i => !(i?.hasOwnProperty("ad_banner_id") || ["ad_campaign_id_", "ad_campaign_name", "abs_position"]?.includes(i?.ad))
    );''', "ad rows filter"),
    ]
    for old, new, label in replacements:
        source = replace_once(source, old, new, label)

    deletion_replacements = [
        ("delete obj.data.big_banner;", 'deleteIfPresent(obj.data, "big_banner");', 1),
        ("delete obj.data.top_banner;", 'deleteIfPresent(obj.data, "top_banner");', 1),
        ("delete obj.data.yaoqingshaiwu;", 'deleteIfPresent(obj.data, "yaoqingshaiwu");', 1),
        ("delete obj.data.rows;", 'deleteIfPresent(obj.data, "rows");', 1),
        ("delete obj.data.ad_black_list;", 'deleteIfPresent(obj.data, "ad_black_list");', 1),
        ("delete obj.data.operation_float;", 'deleteIfPresent(obj.data, "operation_float");', 1),
        ("delete obj.data.haojia_widget;", 'deleteIfPresent(obj.data, "haojia_widget");', 1),
        ("delete obj.data;", 'deleteIfPresent(obj, "data");', 2),
        ("delete obj.data.banner_v2;", 'deleteIfPresent(obj.data, "banner_v2");', 1),
        ("delete obj.data.super_coupon;", 'deleteIfPresent(obj.data, "super_coupon");', 1),
        ("delete obj.data.tonglan;", 'deleteIfPresent(obj.data, "tonglan");', 1),
        ("delete obj.data.hongbao;", 'deleteIfPresent(obj.data, "hongbao");', 1),
        ("delete widget.pic_url;", 'deleteIfPresent(widget, "pic_url");', 1),
        ("delete obj.data.widget;", 'deleteIfPresent(obj.data, "widget");', 1),
        ("delete obj.data.operation_float_screen;", 'deleteIfPresent(obj.data, "operation_float_screen");', 1),
    ]
    for old, new, expected in deletion_replacements:
        count = source.count(old)
        if count != expected:
            raise ValueError("SMZDM upstream field deletion anchor changed: expected %d, got %d for %s" % (expected, count, old))
        source = source.replace(old, new)

    source = replace_once(
        source,
        """    if (url.includes("/creator_user_center")) {
        obj.data = {};
    } else if (url.includes("/bottom_card_list")) {""",
        """    if (url.includes("/creator_user_center")) {
        if (!obj.data || typeof obj.data !== "object" || Array.isArray(obj.data) || Object.keys(obj.data).length > 0) {
            obj.data = {};
            modified = true;
        }
    } else if (url.includes("/bottom_card_list")) {""",
        "creator center reset",
    )

    source = replace_once(
        source,
        '''body = JSON.stringify(obj);
$done({body});''',
        '''if (modified) {
    body = JSON.stringify(obj);
    $done({body});
} else {
    $done({});
}
}''',
        "lazy response serialization",
    )

    source = MARKER + commit + "\n" + source
    for forbidden in (".filter(", ".map("):
        if forbidden in source:
            raise ValueError("SMZDM allocation method remains after optimization: %s" % forbidden)
    if source.count("function compactInPlace(items, keep)") != 1:
        raise ValueError("SMZDM in-place helper count drift")
    return source


def rewrite_plugin(plugin: str) -> str:
    local_count = plugin.count(LOCAL)
    remote_count = plugin.count(REMOTE)
    if local_count and remote_count:
        raise ValueError("mixed local and remote SMZDM script URLs")
    if local_count:
        if local_count != EXPECTED_TRIGGERS:
            raise ValueError("SMZDM local trigger inventory changed: expected %d, got %d" % (EXPECTED_TRIGGERS, local_count))
        return plugin
    if remote_count != EXPECTED_TRIGGERS:
        raise ValueError("SMZDM trigger inventory changed: expected %d, got %d" % (EXPECTED_TRIGGERS, remote_count))
    result = plugin.replace(REMOTE, LOCAL)
    if REMOTE in result or result.count(LOCAL) != EXPECTED_TRIGGERS:
        raise ValueError("SMZDM local trigger migration incomplete")
    return result


def main() -> None:
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
        print("Optimized SMZDM response script: %s (%d bytes)" % (args.output, len(result)))
    if args.plugin:
        path = Path(args.plugin)
        rewritten = rewrite_plugin(path.read_text(encoding="utf-8-sig"))
        path.write_text(rewritten, encoding="utf-8")
        print("Routed all %d SMZDM response triggers to the local optimized handler" % EXPECTED_TRIGGERS)
    if not (args.source or args.output or args.plugin):
        parser.error("provide source/output and/or plugin")


if __name__ == "__main__":
    main()
