// loon-change: Didi response compaction and lazy serialization optimization v2; upstream zirawell/R-Store@237da8f819708af7a7c1933ae6e9f9597d3aad3f
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

// loon-change: Didi hot-loop specialized property loops v2;
function compactDidiByField(items, mode) {
  const length = items.length;
  let write = 0;

  if (mode === "scene") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      if (item.text !== "优惠商城") {
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
      const value = item.nav_id;
      if (value === "dache_anycar" || value === "driverservice" || value === "bike") {
        if (write !== read) items[write] = item;
        write++;
      }
    }
  } else if (mode === "bottomNav") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      const value = item.id;
      if (value === "v6x_home" || value === "user_center") {
        if (write !== read) items[write] = item;
        write++;
      }
    }
  } else if (mode === "walletItem") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      if (item.title === "优惠券") {
        if (write !== read) items[write] = item;
        write++;
      }
    }
  } else if (mode === "walletBottom") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      const value = item.title;
      if (value === "省钱套餐" || value === "天天神券") {
        if (write !== read) items[write] = item;
        write++;
      }
    }
  } else if (mode === "card") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      const title = item.title;
      if (title === "天天领福利" || title === "金融服务" || title === "更多服务" ||
          title === "企业服务" || title === "安全中心") {
        continue;
      }
      if (item.tag === "wallet") {
        // loon-change: Didi wallet nested property cache v2
        const walletItems = item.items;
        if (Array.isArray(walletItems)) {
          compactDidiByField(walletItems, "walletItem");
        }
        if (item.card_type === 4) {
          const walletBottomItems = item.bottom_items;
          if (Array.isArray(walletBottomItems)) {
            compactDidiByField(walletBottomItems, "walletBottom");
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
  // loon-change: Didi scene-list and show-data array reference cache v1
  const sceneList = responseData?.scene_list;
  if (sceneList instanceof Array) {
    compactDidiByField(sceneList, "scene");
  }
  const showData = responseData?.show_data;
  if (showData instanceof Array) {
    // loon-change: Didi show_data nested traversal cache v1
    const showDataLength = showData.length;
    for (let read = 0; read < showDataLength; read++) {
      const block = showData[read];
      const sceneIds = block.scene_ids;
      if (sceneIds instanceof Array) {
        compactDidiByField(sceneIds, "sceneId");
      }
    }
  }
}

if (isHomepageCore) {
  // loon-change: Didi homepage-core cached nested references v1
  const orderCards = responseData?.order_cards;
  const navListCard = orderCards?.nav_list_card;
  const navListData = navListCard?.data;
  if (navListData) {
    compactDidiByField(navListData, "nav");
  }

  const disorderCards = responseData?.disorder_cards;
  const bottomNavList = disorderCards?.bottom_nav_list;
  const bottomNavData = bottomNavList?.data;
  if (bottomNavData) {
    compactDidiByField(bottomNavData, "bottomNav");
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
  // loon-change: Didi user-center cards array reference cache v1
  const userCenterCards = responseData?.cards;
  if (userCenterCards) {
    compactDidiByField(userCenterCards, "card");
  }
}

$done(modified ? {body: JSON.stringify(obj)} : {});
}
}
