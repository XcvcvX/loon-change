// Removes advertising sections from the Spotify Home feed (casita/v1/home/*).
// The response is a protobuf: field 1 wraps the list of sections, each section is a
// field-1 message whose first field is a header ("spotify:section:<id>|<name>") followed
// by one content field whose number identifies the section type. Ad sections are
// identified by name (e.g. "brand-ad", the video HPTO shown under the shortcuts) or by
// their content field (20: brand ad, 21: legacy home ad). The whole section is dropped
// and the wrapper is re-encoded; anything unexpected passes through unchanged.

const AD_NAME = /\|(?:brand-ad|hpto|[a-z0-9-]*-ad)$/;
const AD_FIELDS = new Set([20, 21]);

function readVarint(buf, pos) {
  let value = 0;
  let shift = 0;
  for (;;) {
    if (pos >= buf.length) throw new Error("truncated varint");
    const byte = buf[pos++];
    value += (byte & 0x7f) * Math.pow(2, shift);
    if ((byte & 0x80) === 0) return { value, pos };
    shift += 7;
  }
}

function writeVarint(value) {
  const out = [];
  while (value >= 0x80) {
    out.push((value % 0x80) | 0x80);
    value = Math.floor(value / 0x80);
  }
  out.push(value);
  return out;
}

// loon-change: Spotify Home protobuf no-ad allocation fast path v1
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

try {
  const body = $response.body;
  const bytes = body instanceof Uint8Array ? body : new Uint8Array(body);
  const out = stripAds(bytes);
  if (out) {
    $done({ body: out });
  } else {
    console.log("Spotify Home: no ad section found");
    $done({});
  }
} catch (e) {
  console.log(`Spotify Home: response left unchanged (${e})`);
  $done({});
}
