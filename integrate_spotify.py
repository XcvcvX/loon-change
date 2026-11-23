#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract only Spotify ad-blocking rules/scripts from the pinned upstream Loon plugin."""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

UPSTREAM = "devchristian1337/loon-plugins"
SCRIPT_FILES = {
    "spot-gabo.js": "Spotify gabo",
    "spot-NoSearchAd.js": "Spotify search ads",
    "spot-NoHomeAd.js": "Spotify home ads",
    "spot-NoScrollAd.js": "Spotify scroll ads",
}
AD_REWRITE = re.compile(r"(?:ads|ad-logic)\\?/|ad-on-app-open")
MITM_HOSTS = ("spclient.wg.spotify.com", "*spclient.spotify.com")


def sections(text):
    result = {}
    current = None
    for line in text.splitlines():
        match = re.match(r"^\[([^\]]+)\]\s*$", line.strip())
        if match:
            current = match.group(1).lower()
            result.setdefault(current, [])
        elif current:
            result[current].append(line)
    return result


def selected_source(source):
    parsed = sections(source)
    rules = [x.strip() for x in parsed.get("rule", [])
             if x.strip() == "DOMAIN,aet.spotify.com,REJECT"]
    rewrites = [re.sub(r"\|premium-marketing\\?/upsellOffer", "", x.strip())
                for x in parsed.get("rewrite", [])
                if x.strip() and not x.lstrip().startswith("#")
                and AD_REWRITE.search(x) and re.search(r"\breject\b", x)]
    scripts = {}
    for filename, tag in SCRIPT_FILES.items():
        matches = [x.strip() for x in parsed.get("script", [])
                   if x.strip() and tag.lower() in x.lower()]
        if len(matches) != 1:
            raise ValueError(f"上游脚本规则 {tag!r} 应恰好 1 条，实际 {len(matches)}")
        scripts[filename] = matches[0]
    if not rules:
        raise ValueError("上游未找到预期的 Spotify 广告跟踪域名规则")
    if not rewrites:
        raise ValueError("上游未找到预期的 Spotify 广告投放接口规则")
    return rules, rewrites, scripts


def insert_section(plugin, section, additions):
    lines = plugin.splitlines()
    header = f"[{section}]"
    starts = [i for i, line in enumerate(lines) if line.strip().lower() == header.lower()]
    if len(starts) != 1:
        raise ValueError(f"目标插件必须且只能有一个 {header} 区段，实际 {len(starts)}")
    start = starts[0] + 1
    end = next((i for i in range(start, len(lines)) if re.match(r"^\s*\[[^\]]+\]\s*$", lines[i])), len(lines))
    current = lines[start:end]
    missing = [x for x in additions if x not in current]
    if missing:
        while current and not current[-1].strip():
            current.pop()
        current.extend(["", "# Spotify ad-block rules; generated from upstream by integrate_spotify.py"])
        current.extend(missing)
        lines[start:end] = current
    return "\n".join(lines).rstrip() + "\n"


def replace_rstore_spotify_rules(plugin, independent_entries=()):
    """Replace R-Store Spotify entries with the independent Spotify plugin's entries."""
    output = []
    section = None
    removed = 0
    independent_entries = set(independent_entries)
    has_independent_entries = any(line in independent_entries for line in plugin.splitlines())
    for line in plugin.splitlines():
        header = re.match(r"^\s*\[([^\]]+)\]\s*$", line)
        if header:
            section = header.group(1).strip().lower()
            output.append(line)
            continue
        if section in {"rule", "rewrite", "script"}:
            if (line.strip() == "# Spotify ad-block rules; generated from upstream by integrate_spotify.py"
                    and not has_independent_entries):
                continue
            if not line.lstrip().startswith("#") and line not in independent_entries:
                lower = line.lower()
                if "spotify.com" in lower or r"spotify\.com" in lower or "spotify.js" in lower:
                    removed += 1
                    continue
        if section == "mitm" and line.strip().lower().startswith("hostname"):
            prefix, values = line.split("=", 1)
            hosts = [host.strip() for host in values.split(",") if host.strip()]
            kept_hosts = [host for host in hosts if "spotify.com" not in host.lower()]
            removed += len(hosts) - len(kept_hosts)
            line = prefix + "= " + ", ".join(kept_hosts)
        output.append(line)
    return "\n".join(output).rstrip() + "\n", removed


HOME_FAST_PATH_MARKER = "// loon-change: Spotify Home protobuf no-ad allocation fast path v1"

HOME_FAST_PATH = """// loon-change: Spotify Home protobuf no-ad allocation fast path v1
// Inspect section ranges directly. The common no-ad path creates no kept-array,
// per-section subarray views, or section metadata objects.
function isAdSection(body, start, end) {
  let r = readVarint(body, start);
  if (r.value !== 0x0a) return false;
  r = readVarint(body, r.pos);
  const headerEnd = r.pos + r.value;
  let name = "";
  const limit = Math.min(headerEnd, end);
  for (let i = r.pos; i < limit; i++) name += String.fromCharCode(body[i]);
  let contentField = -1;
  if (headerEnd < end) {
    const key = readVarint(body, headerEnd);
    contentField = Math.floor(key.value / 8);
  }
  if (AD_NAME.test(name) || AD_FIELDS.has(contentField)) return name;
  return false;
}

function stripAds(body) {
  // Top level: field 1 (key 0x0a) wrapping the section list.
  let r = readVarint(body, 0);
  if (r.value !== 0x0a) return null;
  r = readVarint(body, r.pos);
  const listStart = r.pos;
  const listEnd = listStart + r.value;
  if (listEnd > body.length) return null;

  // First pass validates the complete section list and detects whether any
  // section needs removal. Clean responses return without allocating views/arrays.
  let removed = 0;
  let keptLength = 0;
  let pos = listStart;
  while (pos < listEnd) {
    const itemStart = pos;
    const key = readVarint(body, pos);
    if ((key.value & 7) !== 2) return null;
    const len = readVarint(body, key.pos);
    const dataStart = len.pos;
    const itemEnd = dataStart + len.value;
    if (itemEnd > listEnd) return null;
    if (key.value === 0x0a) {
      const adName = isAdSection(body, dataStart, itemEnd);
      if (adName !== false) {
        removed++;
        console.log(`Spotify Home: removed section ${adName.slice(adName.indexOf("|") + 1)}`);
      } else {
        keptLength += itemEnd - itemStart;
      }
    } else {
      keptLength += itemEnd - itemStart;
    }
    pos = itemEnd;
  }
  if (removed === 0) return null;

  const prefix = [0x0a].concat(writeVarint(keptLength));
  const tailLength = body.length - listEnd;
  const out = new Uint8Array(prefix.length + keptLength + tailLength);
  out.set(prefix, 0);
  let off = prefix.length;

  // Second pass copies retained wire ranges directly into the final buffer.
  pos = listStart;
  while (pos < listEnd) {
    const itemStart = pos;
    const key = readVarint(body, pos);
    const len = readVarint(body, key.pos);
    const dataStart = len.pos;
    const itemEnd = dataStart + len.value;
    const adName = key.value === 0x0a ? isAdSection(body, dataStart, itemEnd) : false;
    if (adName === false) {
      out.set(body.subarray(itemStart, itemEnd), off);
      off += itemEnd - itemStart;
    }
    pos = itemEnd;
  }
  out.set(body.subarray(listEnd), off);
  return out;
}
"""


def optimize_spotify_home_script(source):
    if HOME_FAST_PATH_MARKER in source:
        if source.count(HOME_FAST_PATH_MARKER) != 1 or "const kept = []" in source:
            raise ValueError("Spotify Home optimized marker/structure drift")
        if "function isAdSection(body, start, end)" not in source:
            raise ValueError("Spotify Home optimized helper missing")
        return source
    start = source.find("// Reads the header name and the content field number of a section message.")
    end = source.find("\ntry {", start)
    if start < 0 or end < 0 or source.count("function stripAds(body)") != 1:
        raise ValueError("Spotify Home protobuf parser anchors changed; refusing optimization")
    return source[:start] + HOME_FAST_PATH + source[end:]


def integrate(plugin_path, source_path, scripts_source, scripts_dest, upstream_commit, metadata_path):
    source = Path(source_path).read_text(encoding="utf-8")
    rules, rewrites, script_rules = selected_source(source)
    src_dir, dst_dir = Path(scripts_source), Path(scripts_dest)
    dst_dir.mkdir(parents=True, exist_ok=True)
    rewritten_script_rules = []
    script_hashes = {}
    for filename, line in script_rules.items():
        src = src_dir / filename
        if not src.is_file() or src.stat().st_size < 100:
            raise ValueError(f"上游脚本缺失或异常: {src}")
        data = src.read_bytes()
        script_hashes[filename] = hashlib.sha256(data).hexdigest()
        if filename == "spot-NoHomeAd.js":
            optimized = optimize_spotify_home_script(data.decode("utf-8"))
            (dst_dir / filename).write_text(optimized, encoding="utf-8")
        else:
            shutil.copyfile(src, dst_dir / filename)
        line = re.sub(
            r"script-path=https://raw\.githubusercontent\.com/devchristian1337/loon-plugins/refs/heads/main/Scripts/Spotify/[^,\s]+",
            f"script-path=https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/spotify/{filename}",
            line,
        )
        if "script-path=https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/spotify/" not in line:
            raise ValueError(f"无法安全转换上游脚本地址: {line}")
        rewritten_script_rules.append(line)

    plugin = Path(plugin_path).read_text(encoding="utf-8")
    plugin, removed_rstore_script = replace_rstore_spotify_rules(
        plugin, [*rules, *rewrites, *rewritten_script_rules]
    )
    if removed_rstore_script:
        print("Replaced %d R-Store Spotify rule/script/MITM entries with the independent Spotify source" % removed_rstore_script)
    plugin = insert_section(plugin, "Rule", rules)
    plugin = insert_section(plugin, "Rewrite", rewrites)
    plugin = insert_section(plugin, "Script", rewritten_script_rules)

    lines = plugin.splitlines()
    mitm_index = next((i for i, x in enumerate(lines) if x.strip().lower() == "[mitm]"), None)
    if mitm_index is None:
        raise ValueError("目标插件缺少 [MITM] 区段")
    hostname_index = next((i for i in range(mitm_index + 1, len(lines))
                           if lines[i].strip().lower().startswith("hostname =")), None)
    if hostname_index is None:
        raise ValueError("[MITM] 区段缺少 hostname")
    hosts_line = lines[hostname_index]
    prefix, values = hosts_line.split("=", 1)
    hosts = [x.strip() for x in values.split(",") if x.strip()]
    for host in MITM_HOSTS:
        if host not in hosts:
            hosts.append(host)
    lines[hostname_index] = prefix + "= " + ", ".join(hosts)
    Path(plugin_path).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    metadata = {
        "schema_version": 1,
        "upstream_repository": UPSTREAM,
        "upstream_commit": upstream_commit,
        "upstream_plugin_sha256": hashlib.sha256(Path(source_path).read_bytes()).hexdigest(),
        "scripts_sha256": script_hashes,
        "extracted": {
            "rules": rules,
            "rewrite_rules": rewrites,
            "script_tags": list(SCRIPT_FILES.values()),
            "mitm_hosts": list(MITM_HOSTS),
        },
    }
    Path(metadata_path).parent.mkdir(parents=True, exist_ok=True)
    Path(metadata_path).write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin", required=True)
    parser.add_argument("--source-plugin", required=True)
    parser.add_argument("--scripts-source", required=True)
    parser.add_argument("--scripts-dest", required=True)
    parser.add_argument("--upstream-commit", required=True)
    parser.add_argument("--metadata", required=True)
    args = parser.parse_args()
    metadata = integrate(args.plugin, args.source_plugin, args.scripts_source,
                         args.scripts_dest, args.upstream_commit, args.metadata)
    print(f"Spotify ad rules integrated from {metadata['upstream_repository']}@{metadata['upstream_commit']}")
    print(f"rules={len(metadata['extracted']['rules'])}, rewrite={len(metadata['extracted']['rewrite_rules'])}, scripts={len(metadata['scripts_sha256'])}")


if __name__ == "__main__":
    main()
