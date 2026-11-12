/*
 * 买单吧开屏广告图片识别（iPhone 15 Pro Max）
 * 仅拦截实际图片像素尺寸 1290×2796；其它尺寸一律放行。
 * 注意：1290×2796 是 iPhone 15 Pro Max 屏幕像素规格，不代表服务端必然下发同尺寸素材；
 * 首次启用请查看 [MDB-AD] 日志确认实际素材尺寸，若不同应按抓包值调整。
 */
const TARGET_WIDTH = 1290;
const TARGET_HEIGHT = 2796;

function bytesOf(v) {
  if (v instanceof Uint8Array) return v;
  if (v instanceof ArrayBuffer) return new Uint8Array(v);
  if (ArrayBuffer.isView(v)) return new Uint8Array(v.buffer, v.byteOffset, v.byteLength);
  if (Array.isArray(v)) return new Uint8Array(v);
  return null;
}
function imageSize(b) {
  if (!b || b.length < 10) return null;
  // PNG
  if (b.length >= 24 && b[0]===137 && b[1]===80 && b[2]===78 && b[3]===71) {
    const u32 = i => (b[i]*0x1000000+b[i+1]*0x10000+b[i+2]*0x100+b[i+3])>>>0;
    return {format:"PNG", width:u32(16), height:u32(20)};
  }
  // GIF
  if (b[0]===71 && b[1]===73 && b[2]===70 && b[3]===56) {
    return {format:"GIF", width:b[6]|(b[7]<<8), height:b[8]|(b[9]<<8)};
  }
  // JPEG
  if (b[0]===255 && b[1]===216) {
    let i=2;
    while (i+9<b.length) {
      if (b[i]!==255) { i++; continue; }
      const marker=b[i+1]; i+=2;
      if (marker===216 || marker===217 || marker===1 || (marker>=208 && marker<=215)) continue;
      if (i+1>=b.length) break;
      const len=(b[i]<<8)|b[i+1];
      if (len<2 || i+len>b.length) break;
      if ([192,193,194,195,197,198,199,201,202,203,205,206,207].includes(marker)) {
        return {format:"JPEG", height:(b[i+3]<<8)|b[i+4], width:(b[i+5]<<8)|b[i+6]};
      }
      i+=len;
    }
  }
  // WebP VP8X
  if (b.length>=30 && b[0]===82 && b[1]===73 && b[2]===70 && b[3]===70 &&
      b[8]===87 && b[9]===69 && b[10]===66 && b[11]===80 &&
      String.fromCharCode(b[12],b[13],b[14],b[15])==="VP8X") {
    const u24=i=>b[i]+(b[i+1]<<8)+(b[i+2]<<16)+1;
    return {format:"WebP", width:u24(24), height:u24(27)};
  }
  return null;
}
const body = typeof $response.bodyBytes !== "undefined" && $response.bodyBytes
  ? $response.bodyBytes : $response.body;
const b = bytesOf(body);
const img = imageSize(b);
if (!img) {
  console.log("[MDB-AD] 图片格式/响应体无法识别，放行");
  $done({});
} else {
  console.log("[MDB-AD] " + img.format + " " + img.width + "x" + img.height);
  if (img.width===TARGET_WIDTH && img.height===TARGET_HEIGHT) {
    console.log("[MDB-AD] 命中 iPhone 15 Pro Max 开屏素材 -> 204");
    $done({status:204, headers:{}, body:""});
  } else {
    console.log("[MDB-AD] 非目标尺寸，放行");
    $done({});
  }
}
