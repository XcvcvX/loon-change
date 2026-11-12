/*
 * ============================================================
 * 买单吧开屏广告拦截
 * Loon Response Script
 * ============================================================
 *
 * 适用设备：按指定开屏广告素材尺寸识别，不按设备型号硬编码
 *
 * 目标图片尺寸：1242 × 2688（按 iPhone 15 Pro Max 原生屏幕像素）
 * 使用精确宽高匹配；服务端是否下发该尺寸，需由 Loon 日志验证。
 *
 * 支持图片格式：
 * JPEG / PNG / WebP / GIF
 *
 * ------------------------------------------------------------
 * 【其他手机 / 其他机型如果不生效】
 *
 * 如果 Loon 已经执行了这个脚本，但是日志显示：
 *
 * [MDB-AD] JPEG xxxx×xxxx ...
 * [MDB-AD] 普通图片 -> 放行
 *
 * 说明广告图片尺寸超出了当前判断范围。
 *
 * 这种情况不用修改下面的大段代码，
 * 只需要修改下面“开屏广告尺寸参数”中的 4 个数字。
 *
 * ============================================================
 */


/* ============================================================
 * 【买单吧开屏广告尺寸参数】
 *
 * 按你的要求，将目标图片尺寸设为：1242 × 2688。
 *
 * 采用精确宽高匹配，避免把其它尺寸的商品图/普通图片误拦截。
 * 注意：这代表按设备屏幕规格设定的目标值，服务端实际下发
 * 的广告素材是否也是该尺寸，仍需通过 Loon 日志验证。
 * ============================================================
 */

const TARGET_SPLASH_WIDTH  = 1242;
const TARGET_SPLASH_HEIGHT = 2688;


/* ============================================================
 * 以下为图片解析代码
 * 一般不需要修改
 * ============================================================
 */


function getBytes() {
    let body = null;

    if (
        typeof $response.bodyBytes !== "undefined" &&
        $response.bodyBytes
    ) {
        body = $response.bodyBytes;

    } else if (
        typeof $response.body !== "undefined"
    ) {
        body = $response.body;
    }

    if (!body) {
        return null;
    }

    if (body instanceof Uint8Array) {
        return body;
    }

    if (body instanceof ArrayBuffer) {
        return new Uint8Array(body);
    }

    if (ArrayBuffer.isView(body)) {
        return new Uint8Array(
            body.buffer,
            body.byteOffset,
            body.byteLength
        );
    }

    if (Array.isArray(body)) {
        return new Uint8Array(body);
    }

    return null;
}


/* ============================
 * JPEG 尺寸识别
 * ============================
 */

function getJpegSize(b) {

    if (
        !b ||
        b.length < 10 ||
        b[0] !== 0xFF ||
        b[1] !== 0xD8
    ) {
        return null;
    }

    let i = 2;

    while (i + 9 < b.length) {

        if (b[i] !== 0xFF) {
            i++;
            continue;
        }

        const marker = b[i + 1];

        i += 2;

        if (
            marker === 0xD8 ||
            marker === 0xD9 ||
            marker === 0x01 ||
            (
                marker >= 0xD0 &&
                marker <= 0xD7
            )
        ) {
            continue;
        }

        if (i + 1 >= b.length) {
            break;
        }

        const len =
            (b[i] << 8) |
            b[i + 1];

        if (
            len < 2 ||
            i + len > b.length
        ) {
            break;
        }

        if (
            marker === 0xC0 ||
            marker === 0xC1 ||
            marker === 0xC2 ||
            marker === 0xC3 ||
            marker === 0xC5 ||
            marker === 0xC6 ||
            marker === 0xC7 ||
            marker === 0xC9 ||
            marker === 0xCA ||
            marker === 0xCB ||
            marker === 0xCD ||
            marker === 0xCE ||
            marker === 0xCF
        ) {

            return {
                format: "JPEG",

                width:
                    (b[i + 5] << 8) |
                    b[i + 6],

                height:
                    (b[i + 3] << 8) |
                    b[i + 4]
            };
        }

        i += len;
    }

    return null;
}


/* ============================
 * PNG 尺寸识别
 * ============================
 */

function getPngSize(b) {

    if (
        !b ||
        b.length < 24
    ) {
        return null;
    }

    if (
        b[0] !== 0x89 ||
        b[1] !== 0x50 ||
        b[2] !== 0x4E ||
        b[3] !== 0x47 ||
        b[4] !== 0x0D ||
        b[5] !== 0x0A ||
        b[6] !== 0x1A ||
        b[7] !== 0x0A
    ) {
        return null;
    }

    const width =
        (
            b[16] * 0x1000000 +
            b[17] * 0x10000 +
            b[18] * 0x100 +
            b[19]
        ) >>> 0;

    const height =
        (
            b[20] * 0x1000000 +
            b[21] * 0x10000 +
            b[22] * 0x100 +
            b[23]
        ) >>> 0;

    return {
        format: "PNG",
        width: width,
        height: height
    };
}


/* ============================
 * GIF 尺寸识别
 * ============================
 */

function getGifSize(b) {

    if (
        !b ||
        b.length < 10
    ) {
        return null;
    }

    const isGif =
        b[0] === 0x47 &&
        b[1] === 0x49 &&
        b[2] === 0x46 &&
        b[3] === 0x38 &&
        (
            b[4] === 0x37 ||
            b[4] === 0x39
        ) &&
        b[5] === 0x61;

    if (!isGif) {
        return null;
    }

    return {
        format: "GIF",

        width:
            b[6] |
            (b[7] << 8),

        height:
            b[8] |
            (b[9] << 8)
    };
}


/* ============================
 * WebP 尺寸识别
 * ============================
 */

function getWebpSize(b) {

    if (
        !b ||
        b.length < 30
    ) {
        return null;
    }

    if (
        b[0] !== 0x52 ||
        b[1] !== 0x49 ||
        b[2] !== 0x46 ||
        b[3] !== 0x46 ||
        b[8] !== 0x57 ||
        b[9] !== 0x45 ||
        b[10] !== 0x42 ||
        b[11] !== 0x50
    ) {
        return null;
    }

    const type = String.fromCharCode(
        b[12],
        b[13],
        b[14],
        b[15]
    );


    // VP8X
    if (
        type === "VP8X" &&
        b.length >= 30
    ) {

        const width =
            1 +
            b[24] +
            (b[25] << 8) +
            (b[26] << 16);

        const height =
            1 +
            b[27] +
            (b[28] << 8) +
            (b[29] << 16);

        return {
            format: "WebP",
            width: width,
            height: height
        };
    }


    // VP8L
    if (
        type === "VP8L" &&
        b.length >= 25 &&
        b[20] === 0x2F
    ) {

        const bits =
            (
                b[21] |
                (b[22] << 8) |
                (b[23] << 16) |
                (b[24] << 24)
            ) >>> 0;

        const width =
            (bits & 0x3FFF) + 1;

        const height =
            ((bits >>> 14) & 0x3FFF) + 1;

        return {
            format: "WebP",
            width: width,
            height: height
        };
    }


    // VP8
    if (
        type === "VP8 " &&
        b.length >= 30 &&
        b[23] === 0x9D &&
        b[24] === 0x01 &&
        b[25] === 0x2A
    ) {

        const width =
            (
                b[26] |
                (b[27] << 8)
            ) & 0x3FFF;

        const height =
            (
                b[28] |
                (b[29] << 8)
            ) & 0x3FFF;

        return {
            format: "WebP",
            width: width,
            height: height
        };
    }

    return null;
}


/* ============================
 * 统一识别图片类型
 * ============================
 */

function getImageSize(b) {

    return (
        getJpegSize(b) ||
        getPngSize(b) ||
        getWebpSize(b) ||
        getGifSize(b)
    );
}


/* ============================================================
 * 开始处理响应体
 * ============================================================
 */

const bytes = getBytes();


if (!bytes) {

    console.log(
        "[MDB-AD] 未取得二进制响应体 -> 放行"
    );

    $done({});

} else {

    const img = getImageSize(bytes);


    if (!img) {

        console.log(
            "[MDB-AD] 未识别图片格式 -> 放行"
        );

        $done({});

    } else {

        const ratio =
            img.width > 0
                ? img.height / img.width
                : 0;


        console.log(
            "[MDB-AD] " +
            img.format +
            " " +
            img.width +
            "x" +
            img.height +
            " ratio=" +
            ratio.toFixed(3) +
            " / " +
            bytes.length +
            " bytes"
        );


        /* ====================================================
         * 精确匹配 iPhone 15 Pro Max 目标图片尺寸
         * ====================================================
         */

        const isSplash =
            img.width === TARGET_SPLASH_WIDTH &&
            img.height === TARGET_SPLASH_HEIGHT;


        if (isSplash) {

            console.log(
                "[MDB-AD] 命中买单吧开屏广告 -> 204"
            );

            $done({
                status: 204,
                headers: {},
                body: ""
            });

        } else {

            console.log(
                "[MDB-AD] 普通图片 -> 放行"
            );

            $done({});
        }
    }
}