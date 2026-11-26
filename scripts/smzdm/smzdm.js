// loon-change: SMZDM in-place compaction and lazy serialization v1; upstream zirawell/R-Store@237da8f819708af7a7c1933ae6e9f9597d3aad3f
/********************************
SMZDM Remove Ads - Version 1.0
Checkout Source -
1.https://raw.githubusercontent.com/ZenmoFeiShi/Qx/main/Smzdm.js
2.https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/smzdm/smzdm_ads.js
Please note that you may need to reinstall app for script to work.

QuantumultX rewrite link:
https://raw.githubusercontent.com/zirawell/R-Store/main/Rule/QuanX/Adblock/App/S/什么值得买/rewrite/smzdm.conf

Surge module link:
https://raw.githubusercontent.com/zirawell/R-Store/main/Rule/Surge/Adblock/App/S/什么值得买/smzdm.sgmodule
********************************/

const url = $request.url;
if (!$response.body) {
    $done({});
} else {
let body = $response.body;
let obj = JSON.parse(body);

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


const fixPos = (arr) => {
    for (let i = 0; i < arr.length; i++) {
        if (arr[i].pos !== i + 1) {
            arr[i].pos = i + 1;
            modified = true;
        }
    }
};

if (url.includes("/home") && url.includes("homepage-api")) {
    const recursivelyFilterByCellType = (data) => {
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
    };

    obj.data = recursivelyFilterByCellType(obj.data);
}

if (url.includes("/vip")) {
    if (obj?.data?.big_banner) {
        deleteIfPresent(obj.data, "big_banner");
    }
    if (obj?.data?.top_banner) {
        deleteIfPresent(obj.data, "top_banner");
    }
    if (obj?.data?.yaoqingshaiwu) {
        deleteIfPresent(obj.data, "yaoqingshaiwu");
    }
    // 个人中心广告
    if (url.includes("/creator_user_center")) {
        if (!obj.data || typeof obj.data !== "object" || Array.isArray(obj.data) || Object.keys(obj.data).length > 0) {
            obj.data = {};
            modified = true;
        }
    } else if (url.includes("/bottom_card_list")) {
        if (obj?.data?.rows) {
            deleteIfPresent(obj.data, "rows");
        }
    }
} else if (url.includes("/util/update")) {
    if (obj?.data?.ad_black_list) {
        deleteIfPresent(obj.data, "ad_black_list");
    }
    // 弹窗图片广告
    if (obj?.data?.operation_float) {
        deleteIfPresent(obj.data, "operation_float");
    }
    if (obj?.data?.haojia_widget) {
        deleteIfPresent(obj.data, "haojia_widget");
    }
} else if (url.includes("/util/loading")) {
    if (obj?.data) {
        deleteIfPresent(obj, "data");
    }
} else if (url.includes("/home/list")) {
    if (obj?.data?.banner_v2) {
        deleteIfPresent(obj.data, "banner_v2");
    }
} else if (url.includes("/home") && url.includes("homepage-api")) {
    compactInPlace(obj.data.component, item =>
        item.zz_type === "circular_banner" || item.zz_type === "fixed_banner" || item.zz_type === "filter" || item.zz_type === "list"
    );
    fixPos(obj.data.component);
    if (obj?.data?.functions) {
        compactInPlace(obj.data.functions, item => item.type === "message");
        fixPos(obj.data.functions);
    }
} else if (url.includes("/publish/get_bubble")) {
    if (obj?.data) {
        deleteIfPresent(obj, "data");
    }
} else if (url.includes("/app/home")) {
    if (obj?.data) {
        compactInPlace(obj.data, item => item.id === "40" || item.id === "20");
        fixPos(obj.data);
    }
} else if (url.includes("/detail_modul/user_related_modul")) {
    // 详情页广告
    if (obj?.data?.super_coupon) {
        deleteIfPresent(obj.data, "super_coupon");
    }
} else if (url.includes("/ranking_list/articles") || url.includes("/sou/list_v")) {
    // 排行榜广告&搜索结果广告
    compactInPlace(obj.data.rows, item => item.model_type !== "ads");
} else if (url.includes("/sou/filter/tags/hot_tags")) {
    // 搜索热榜广告
    compactInPlace(obj.data.search_hot.home, item => item.pos);
    if (obj?.data?.tonglan) {
        deleteIfPresent(obj.data, "tonglan");
    }
    if (obj?.data?.hongbao) {
        deleteIfPresent(obj.data, "hongbao");
    }
} else if (url.includes("/ajax_app/ajax_get_footer_list")) {
    if (obj?.data?.activity_banner?.hot_widget) {
        obj.data.activity_banner.hot_widget.forEach(widget => {
            if (widget.pic_url) {
                deleteIfPresent(widget, "pic_url");
            }
        });
    }
}
if (obj?.data?.services) {
    compactInPlace(obj.data.services, item => item.type === "articel_manage" || item.type === "199794" || item.type === "199796");
    fixPos(obj.data.services);
}
if (obj?.data?.widget) {
    deleteIfPresent(obj.data, "widget");
}
if (obj?.data?.operation_float_screen) {
    deleteIfPresent(obj.data, "operation_float_screen");
}
if (obj?.data?.rows?.length > 0) {
    compactInPlace(obj.data.rows,
        i => !(i?.hasOwnProperty("ad_banner_id") || ["ad_campaign_id_", "ad_campaign_name", "abs_position"]?.includes(i?.ad))
    );
}

if (modified) {
    body = JSON.stringify(obj);
    $done({body});
} else {
    $done({});
}
}
