#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the active R-Store Weibo response script with allocation-free array compaction."""
import argparse
import re
from pathlib import Path

REMOTE = "https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/weibo.js"
LOCAL = "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/weibo/weibo-rstore.js"
MARKER = "// loon-change: R-Store Weibo in-place response compaction v1; upstream zirawell/R-Store@"
EXPECTED = 32

HELPER = """function compactInPlace(items, keep) {
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

def _regex_start(source, index):
    previous = source[:index].rstrip()
    if not previous:
        return True
    if previous[-1] in "=(:,[!&|?{};":
        return True
    return re.search(r"\\b(return|case|throw|yield|await|else|do)\\s*$", previous) is not None

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
            if char == "\\n":
                state = "code"
        elif state == "block":
            if char == "*" and nxt == "/":
                state = "code"
                index += 2
                continue
        elif state == "string":
            if escaped:
                escaped = False
            elif char == "\\\\":
                escaped = True
            elif char == quote:
                state = "code"
        elif state == "regex":
            if escaped:
                escaped = False
            elif char == "\\\\":
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
    declarations = list(re.finditer(r"let\\s+(new[A-Za-z0-9_]*)\\s*=\\s*\\[\\s*\\]\\s*;", source))
    for declaration in reversed(declarations):
        name = declaration.group(1)
        header = re.search(
            r"for\\s*\\(\\s*let\\s+([A-Za-z_$][\\w$]*)\\s+of\\s+([^)]+)\\)\\s*\\{",
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
        if re.search(r"\\b" + re.escape(name) + r"\\.unshift\\s*\\(", body):
            continue
        push = re.compile(r"\\b" + re.escape(name) + r"\\.push\\(\\s*" + re.escape(iterator) + r"\\s*\\)\\s*;")
        body, pushes = push.subn("__SOURCE__[__WRITE__++] = " + iterator + ";", body)
        if not pushes:
            continue
        assignment = re.search(
            r"(?m)^(?P<indent>[ \\t]*)(?P<dest>[A-Za-z_$][\\w$]*(?:\\.[A-Za-z_$][\\w$]*)*)\\s*=\\s*" +
            re.escape(name) + r"\\s*;",
            source[closing + 1:closing + 1 + 900]
        )
        if not assignment or assignment.group("dest") != source_expr:
            continue

        source_name = "__loonSource%d" % sequence
        write_name = "__loonWrite%d" % sequence
        read_name = "__loonRead%d" % sequence
        length_name = "__loonLength%d" % sequence
        body = body.replace("__SOURCE__", source_name).replace("__WRITE__", write_name)
        line_start = source.rfind("\\n", 0, declaration.start()) + 1
        decl_indent = source[line_start:declaration.start()]
        loop_line = source.rfind("\\n", 0, header_start) + 1
        loop_indent = source[loop_line:header_start]
        assign_start = closing + 1 + assignment.start()
        assign_end = closing + 1 + assignment.end()
        decl_replacement = (
            "const " + source_name + " = " + source_expr + ";\\n" +
            decl_indent + "let " + write_name + " = 0;"
        )
        between = source[declaration.end():header_start]
        header_replacement = (
            "for (let " + read_name + " = 0, " + length_name + " = " +
            source_name + ".length; " + read_name + " < " + length_name +
            "; " + read_name + "++) {\\n" + loop_indent + "  let " +
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

def optimize_source(source, commit="unknown"):
    if MARKER in source:
        if "__loonSource32" not in source or "compactInPlace(items, keep)" not in source:
            raise ValueError("marked Weibo script is incomplete")
        return source
    source = source.replace("const url = $request.url;", "const url = $request.url;\\n\\n" + HELPER, 1)
    if source.count(HELPER) != 1:
        raise ValueError("Weibo helper insertion failed")
    source = compact_collecting_loops(source)
    remaining = re.findall(r"\\b(new[A-Za-z0-9_]*)\\s*=\\s*\\[\\s*\\]", source)
    if sorted(remaining) != ["newActions", "newII"]:
        raise ValueError("unexpected remaining Weibo temporary arrays: " + repr(remaining))
    return MARKER + commit + "\\n" + source

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
    result = "\\n".join(output)
    if REMOTE in result:
        raise ValueError("remote Weibo references remain")
    return result + ("\\n" if plugin.endswith("\\n") else "")

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

if __name__ == "__main__":
    main()
