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

const DIDI_KEEP_NAV_IDS = new Set(["dache_anycar", "driverservice", "bike"]);
const DIDI_KEEP_BOTTOM_NAV_IDS = new Set(["v6x_home", "user_center"]);
const DIDI_EXCLUDED_CARD_TITLES = new Set([
  "天天领福利", "金融服务", "更多服务", "企业服务", "安全中心"
]);


function compactInPlace(items, keep) {
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
}

function keepDidiSceneItem(item) {
  return item.text !== "优惠商城";
}

function keepDidiSceneId(id) {
  return id !== "scene_coupon_mall";
}

function keepDidiNavItem(item) {
  return DIDI_KEEP_NAV_IDS.has(item.nav_id);
}

function keepDidiBottomNavItem(item) {
  return DIDI_KEEP_BOTTOM_NAV_IDS.has(item.id);
}

function keepDidiWalletItem(item) {
  return item.title === "优惠券";
}

function keepDidiWalletBottomItem(item) {
  return item.title === "省钱套餐" || item.title === "天天神券";
}

function keepDidiUserCenterCard(card) {
  if (DIDI_EXCLUDED_CARD_TITLES.has(card.title)) return false;
  if (card.tag === "wallet") {
    if (card.items) {
      compactInPlace(card.items, keepDidiWalletItem);
    }
    if (card.card_type === 4 && card.bottom_items) {
      compactInPlace(card.bottom_items, keepDidiWalletBottomItem);
    }
  }
  return true;
}

if (!$response.body) {
  $done({});
} else {

let obj = JSON.parse($response.body);

if (url.includes("/other/pGetSceneList")) {
  if (obj && obj.data && obj.data.scene_list instanceof Array) {
    compactInPlace(obj.data.scene_list, keepDidiSceneItem);
  }
  if (obj && obj.data && obj.data.show_data instanceof Array) {
    const showData = obj.data.show_data;
    for (let read = 0; read < showData.length; read++) {
      const block = showData[read];
      if (block.scene_ids instanceof Array) {
        compactInPlace(block.scene_ids, keepDidiSceneId);
      }
    }
  }
}

if (url.includes("/homepage/v") && url.includes("/core")) {
  // 保留打车、代驾、青桔骑行
  if (obj.data && obj.data.order_cards && obj.data.order_cards.nav_list_card && obj.data.order_cards.nav_list_card.data) {
    compactInPlace(obj.data.order_cards.nav_list_card.data, keepDidiNavItem);
  }
  // 保留底部tap首页、我的
  if (obj.data && obj.data.disorder_cards && obj.data.disorder_cards.bottom_nav_list && obj.data.disorder_cards.bottom_nav_list.data) {
    compactInPlace(obj.data.disorder_cards.bottom_nav_list.data, keepDidiBottomNavItem);
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
    compactInPlace(obj.data.cards, keepDidiUserCenterCard);
  }
}

$done(modified ? {body: JSON.stringify(obj)} : {});
}
