// loon-change: Didi response compaction and lazy serialization optimization v2; upstream zirawell/R-Store@1e08bab55bcffc396be39f914f48151443344493
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

// loon-change: Didi hot-loop mode dispatch v1;
function compactDidiByField(items, field, mode) {
  const length = items.length;
  let write = 0;

  if (mode === "scene") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      if (item[field] !== "优惠商城") {
        if (write !== read) items[write] = item;
        write++;
      }
    }
  } else if (mode === "sceneId") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      if (item !== "scene_coupon_mall") {
        if (write !== read) items[write] = item;
        write++;
      }
    }
  } else if (mode === "nav") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      const value = item[field];
      if (value === "dache_anycar" || value === "driverservice" || value === "bike") {
        if (write !== read) items[write] = item;
        write++;
      }
    }
  } else if (mode === "bottomNav") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      const value = item[field];
      if (value === "v6x_home" || value === "user_center") {
        if (write !== read) items[write] = item;
        write++;
      }
    }
  } else if (mode === "walletItem") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      if (item[field] === "优惠券") {
        if (write !== read) items[write] = item;
        write++;
      }
    }
  } else if (mode === "walletBottom") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      const value = item[field];
      if (value === "省钱套餐" || value === "天天神券") {
        if (write !== read) items[write] = item;
        write++;
      }
    }
  } else if (mode === "card") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      const title = item[field];
      if (title === "天天领福利" || title === "金融服务" || title === "更多服务" ||
          title === "企业服务" || title === "安全中心") {
        continue;
      }
      if (item.tag === "wallet") {
        if (Array.isArray(item.items) && item.items.length > 0) {
          compactDidiByField(item.items, "title", "walletItem");
        }
        if (item.card_type === 4 && Array.isArray(item.bottom_items) && item.bottom_items.length > 0) {
          compactDidiByField(item.bottom_items, "title", "walletBottom");
        }
      }
      if (write !== read) items[write] = item;
      write++;
    }
  } else {
    return items;
  }

  if (write !== length) {
    items.length = write;
    modified = true;
  }
  return items;
}
if (!$response.body) {
  $done({});
} else {

// loon-change: Didi pre-parse supported-route guard v1
const shouldProcess =
  url.includes("/other/pGetSceneList") ||
  (url.includes("/homepage/v") && url.includes("/core")) ||
  url.includes("/ota/na/yuantu/infoList") ||
  url.includes("/usercenter/me");
if (!shouldProcess) {
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
}
