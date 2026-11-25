// loon-change: Didi response compaction and lazy serialization optimization v2; upstream zirawell/R-Store@52fcb40b118a15610686b9167a7ee8e59bc04709
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
        // loon-change: Didi wallet nested property cache v1
        const walletItems = item.items;
        if (Array.isArray(walletItems) && walletItems.length > 0) {
          compactDidiByField(walletItems, "title", "walletItem");
        }
        if (item.card_type === 4) {
          const walletBottomItems = item.bottom_items;
          if (Array.isArray(walletBottomItems) && walletBottomItems.length > 0) {
            compactDidiByField(walletBottomItems, "title", "walletBottom");
          }
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
// loon-change: Didi route dispatch cache v1
const isSceneList = url.includes("/other/pGetSceneList");
const isHomepageCore = url.includes("/homepage/v") && url.includes("/core");
const isInfoList = url.includes("/ota/na/yuantu/infoList");
const isUserCenter = url.includes("/usercenter/me");
const shouldProcess = isSceneList || isHomepageCore || isInfoList || isUserCenter;
if (!shouldProcess) {
  $done({});
} else {
  let obj = JSON.parse($response.body);
  // loon-change: Didi response data reference cache v1
  const responseData = obj.data;

if (isSceneList) {
  if (obj && responseData && responseData.scene_list instanceof Array) {
    compactDidiByField(responseData.scene_list, "text", "scene");
  }
  if (obj && responseData && responseData.show_data instanceof Array) {
    // loon-change: Didi show_data nested traversal cache v1
    const showData = responseData.show_data;
    const showDataLength = showData.length;
    for (let read = 0; read < showDataLength; read++) {
      const block = showData[read];
      const sceneIds = block.scene_ids;
      if (sceneIds instanceof Array) {
        compactDidiByField(sceneIds, "scene_ids", "sceneId");
      }
    }
  }
}

if (isHomepageCore) {
  // 保留打车、代驾、青桔骑行
  if (responseData && responseData.order_cards && responseData.order_cards.nav_list_card && responseData.order_cards.nav_list_card.data) {
    compactDidiByField(responseData.order_cards.nav_list_card.data, "nav_id", "nav");
  }
  // 保留底部tap首页、我的
  if (responseData && responseData.disorder_cards && responseData.disorder_cards.bottom_nav_list && responseData.disorder_cards.bottom_nav_list.data) {
    compactDidiByField(responseData.disorder_cards.bottom_nav_list.data, "id", "bottomNav");
  }
}

if (isInfoList) {
  // loon-change: Didi info-list cached nested references v1
  const topBannerData = responseData?.disorder_cards?.top_banner_card?.data;
  const firstTopBanner = topBannerData?.[0];
  if (firstTopBanner?.T === "yuentu_top_banner") {
    // 移除顶部卡片
    topBannerData.splice(0, 1);
    modified = true;
  }
}

if (isUserCenter) {
  if (responseData && responseData.cards) {
    compactDidiByField(responseData.cards, "title", "card");
  }
}

$done(modified ? {body: JSON.stringify(obj)} : {});
}
}
