// Removes the ad block from the Spotify scroll feed (scrollsita/v*/scroll/spotify).
// The response is a protobuf whose field 30 carries the ad block. The field is not
// deleted but renumbered to an unknown field (1000), so the client skips it and the rest
// of the message is kept intact. The message is parsed properly (top level and nested
// messages up to depth 3), the first matching field is renamed and every enclosing
// length is recomputed. Anything unexpected passes through unchanged.

const AD_FIELD = 30;
const UNKNOWN_FIELD = 1000;
const MAX_DEPTH = 3;

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


// loon-change: Spotify Scroll protobuf no-ad allocation preflight v1
// Scan wire ranges without materializing field arrays or subarray views.
// The existing allocating rewrite is entered only after a target field is found.
function hasTargetField(buf, depth, start, end) {
  start = start || 0;
  end = end === undefined ? buf.length : end;
  let pos = start;
  while (pos < end) {
    const key = readVarint(buf, pos);
    const no = Math.floor(key.value / 8);
    const wire = key.value % 8;
    pos = key.pos;
    let payloadStart = -1;
    let payloadEnd = -1;
    if (wire === 0) pos = readVarint(buf, pos).pos;
    else if (wire === 1) pos += 8;
    else if (wire === 5) pos += 4;
    else if (wire === 2) {
      const len = readVarint(buf, pos);
      payloadStart = len.pos;
      payloadEnd = len.pos + len.value;
      pos = payloadEnd;
    } else throw new Error("unsupported wire type " + wire);
    if (pos > end) throw new Error("truncated field");
    if (wire === 2) {
      if (no === AD_FIELD) return true;
      if (depth < MAX_DEPTH) {
        try {
          if (hasTargetField(buf, depth + 1, payloadStart, payloadEnd)) return true;
        } catch (e) {
          // Non-message strings/bytes are expected; match the original parser's behavior.
        }
      }
    }
  }
  return false;
}

// loon-change: Spotify nested protobuf allocation-light rewrite v2
// Only materialize byte views when a matching ad field is found. Rebuild each
// ancestor directly into one output buffer; no per-field objects or map/reduce arrays.
function wrap(no, payload) {
  const key = writeVarint(no * 8 + 2);
  const size = writeVarint(payload.length);
  const out = new Uint8Array(key.length + size.length + payload.length);
  let offset = 0;
  for (let i = 0; i < key.length; i++) out[offset++] = key[i];
  for (let i = 0; i < size.length; i++) out[offset++] = size[i];
  out.set(payload, offset);
  return out;
}

function replaceRange(buf, start, end, fieldStart, fieldEnd, replacement) {
  const prefixLength = fieldStart - start;
  const suffixLength = end - fieldEnd;
  const out = new Uint8Array(prefixLength + replacement.length + suffixLength);
  out.set(buf.subarray(start, fieldStart), 0);
  out.set(replacement, prefixLength);
  out.set(buf.subarray(fieldEnd, end), prefixLength + replacement.length);
  return out;
}

// Return the first depth-first matching field with all parent lengths rebuilt.
function renameField(buf, depth, start, end, kind) {
  let pos = start;
  while (pos < end) {
    const fieldStart = pos;
    const key = readVarint(buf, pos);
    const no = Math.floor(key.value / 8);
    const wire = key.value % 8;
    pos = key.pos;
    let payloadStart = -1;
    let payloadEnd = -1;

    if (wire === 0) pos = readVarint(buf, pos).pos;
    else if (wire === 1) pos += 8;
    else if (wire === 5) pos += 4;
    else if (wire === 2) {
      const len = readVarint(buf, pos);
      payloadStart = len.pos;
      payloadEnd = len.pos + len.value;
      pos = payloadEnd;
    } else throw new Error("unsupported wire type " + wire);

    if (pos > end) throw new Error("truncated field");
    if (wire !== 2) continue;

    const isTarget = no === AD_FIELD &&
      (kind === "scroll" || payloadEnd - payloadStart > MIN_AD_SIZE);
    if (isTarget) {
      const replacement = wrap(UNKNOWN_FIELD, buf.subarray(payloadStart, payloadEnd));
      return replaceRange(buf, start, end, fieldStart, pos, replacement);
    }

    if (depth < MAX_DEPTH) {
      let inner = null;
      try {
        inner = renameField(buf, depth + 1, payloadStart, payloadEnd, kind);
      } catch (e) {
        // Non-message strings/bytes are expected; preserve the original payload.
      }
      if (inner) {
        return replaceRange(buf, start, end, fieldStart, pos, wrap(no, inner));
      }
    }
  }
  return null;
}

try {
  const body = $response.body;
  const bytes = body instanceof Uint8Array ? body : new Uint8Array(body);
  const out = hasTargetField(bytes, 0) ? renameField(bytes, 0, 0, bytes.length, "scroll") : null;
  if (out) {
    console.log("Spotify scroll: ad block hidden");
    $done({ body: out });
  } else {
    console.log("Spotify scroll: no ad block found");
    $done({});
  }
} catch (e) {
  console.log(`Spotify scroll: response left unchanged (${e})`);
  $done({});
}
