// loon-change: Didi response compaction and lazy serialization optimization v2; upstream zirawell/R-Store@a4f3b10d6038d77ae3e1ff68bd19a49071ebabd3
/********************************
Didi Remove Ads - Version 1.0
Please note that you may need to reinstall app for script to work.

QuantumultX rewrite link:
https://raw.githubusercontent.com/zirawell/R-Store/main/Rule/QuanX/Adblock/App/D/滴滴出行/rewrite/diditaxi.conf

Surge module link:
https://raw.githubusercontent.com/zirawell/R-Store/main/Rule/Surge/Adblock/App/D/滴滴出行/diditaxi.sgmodule
********************************/

const url = $request.url;
let modified = false;

function compactDidiByField(items, field, mode) {
  const length = items.length;
  let write = 0;
  for (let read = 0; read < length; read++) {
    const item = items[read];
    const value = item[field];
    let keep = true;

    if (mode === "scene") {
      keep = value !== "优惠商城";
    } else if (mode === "sceneId") {
      keep = value !== "scene_coupon_mall";
    } else if (mode === "nav") {
      keep = value === "dache_anycar" || value === "driverservice" || value === "bike";
    } else if (mode === "bottomNav") {
      keep = value === "v6x_home" || value === "user_center";
    } else if (mode === "walletItem") {
      keep = value === "优惠券";
    } else if (mode === "walletBottom") {
      keep = value === "省钱套餐" || value === "天天神券";
    } else if (mode === "card") {
      if (value === "天天领福利" || value === "金融服务" || value === "更多服务" ||
          value === "企业服务" || value === "安全中心") {
        keep = false;
      } else if (item.tag === "wallet") {
        if (item.items) compactDidiByField(item.items, "title", "walletItem");
        if (item.card_type === 4 && item.bottom_items) {
          compactDidiByField(item.bottom_items, "title", "walletBottom");
        }
      }
    }

    if (keep) {
      if (write !== read) items[write] = item;
      write++;
    }
  }
  items.length = write;
  if (write !== length) modified = true;
  return items;
}

if (!$response.body) {
  $done({});
} else {

let obj = JSON.parse($response.body);

if (url.includes("/other/pGetSceneList")) {
  if (obj && obj.data && obj.data.scene_list instanceof Array) {
    compactDidiByField(obj.data.scene_list, "text", "scene");
  }
  if (obj && obj.data && obj.data.show_data instanceof Array) {
    const showData = obj.data.show_data;
    for (let read = 0; read < showData.length; read++) {
      const block = showData[read];
      if (block.scene_ids instanceof Array) {
        compactDidiByField(block.scene_ids, "scene_ids", "sceneId");
      }
    }
  }
}

if (url.includes("/homepage/v") && url.includes("/core")) {
  // 保留打车、代驾、青桔骑行
  if (obj.data && obj.data.order_cards && obj.data.order_cards.nav_list_card && obj.data.order_cards.nav_list_card.data) {
    compactDidiByField(obj.data.order_cards.nav_list_card.data, "nav_id", "nav");
  }
  // 保留底部tap首页、我的
  if (obj.data && obj.data.disorder_cards && obj.data.disorder_cards.bottom_nav_list && obj.data.disorder_cards.bottom_nav_list.data) {
    compactDidiByField(obj.data.disorder_cards.bottom_nav_list.data, "id", "bottomNav");
  }
}

if (url.includes("/ota/na/yuantu/infoList")) {
  if (obj.data && obj.data.disorder_cards && obj.data.disorder_cards.top_banner_card && obj.data.disorder_cards.top_banner_card.data && obj.data.disorder_cards.top_banner_card.data[0] && obj.data.disorder_cards.top_banner_card.data[0].T === "yuentu_top_banner") {
    // 移除顶部卡片
    obj.data.disorder_cards.top_banner_card.data.splice(0, 1);
    modified = true;
  }
}

if (url.includes("/usercenter/me")) {
  if (obj.data && obj.data.cards) {
    compactDidiByField(obj.data.cards, "title", "card");
  }
}

$done(modified ? {body: JSON.stringify(obj)} : {});
}
