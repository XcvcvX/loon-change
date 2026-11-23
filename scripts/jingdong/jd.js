/********************************
Jingdong Remove Ads - Version 1.0
Please note that you may need to reinstall app for script to work.

QuantumultX rewrite link:
https://raw.githubusercontent.com/zirawell/R-Store/main/Rule/QuanX/Adblock/App/J/京东/rewrite/jd.conf

Surge module link:
https://raw.githubusercontent.com/zirawell/R-Store/main/Rule/Surge/Adblock/App/J/京东/jd.sgmodule
********************************/

// loon-change: Jingdong in-place response compaction and lazy serialization v1; upstream zirawell/R-Store@1e08bab55bcffc396be39f914f48151443344493
(function () {
  const url = ($request && $request.url) || "";
  const body = $response && $response.body;
  const argument = typeof $argument !== "undefined" ? $argument : null;
  const welcomeExtraEnabled = Boolean(
    argument && typeof argument === "object" && argument.jkds_enable === true
  );

  const shouldProcess =
    url.includes("functionId=start") ||
    url.includes("functionId=welcomeHome") ||
    url.includes("functionId=readCustomSurfaceList") ||
    url.includes("functionId=deliverLayer") ||
    url.includes("functionId=orderTrackBusiness") ||
    url.includes("functionId=getTabHomeInfo") ||
    url.includes("functionId=myOrderInfo") ||
    url.includes("functionId=personinfoBusiness");
  if (!shouldProcess || typeof body !== "string" || !body) {
    $done({});
    return;
  }

  let obj;
  try {
    obj = JSON.parse(body);
  } catch (_) {
    $done({});
    return;
  }
  if (!obj || typeof obj !== "object" || Array.isArray(obj)) {
    $done({});
    return;
  }

  let modified = false;

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
    if (write !== length) {
      items.length = write;
      modified = true;
    }
    return items;
  }

  function deleteIfPresent(target, key) {
    if (target && Object.prototype.hasOwnProperty.call(target, key)) {
      delete target[key];
      modified = true;
    }
  }

  function clearArrayIfNeeded(target, key) {
    if (target && Array.isArray(target[key]) && target[key].length > 0) {
      target[key] = [];
      modified = true;
    }
  }

  function isPersonInfoBusinessExcluded(id) {
    return id === "bigSaleFloor" || id === "buyOften" ||
      id === "newAttentionCard" || id === "newBigSaleFloor" ||
      id === "newStyleAttentionCard" || id === "newsFloor" ||
      id === "noticeFloor" || id === "recommendfloor";
  }

  function isWelcomeHomeType(type) {
    return type === "topTab" || type === "searchC" ||
      type === "dynamicIcon" || type === "locPermission" ||
      type === "login" || type === "hybrid" || type === "recommend";
  }

  function isWelcomeExtraExcluded(type) {
    return type === "bottomXview" || type === "float" ||
      type === "photoCeiling" || type === "ruleFloat" ||
      type === "searchIcon" || type === "topRotate" ||
      type === "tabBarAtmosphere";
  }

  function isCustomSurfaceName(name) {
    return name === "index" || name === "messagenew" ||
      name === "cart" || name === "home";
  }




function isPersonInfoBusinessExcluded(id) {
  return id === "bigSaleFloor" || id === "buyOften" ||
    id === "newAttentionCard" || id === "newBigSaleFloor" ||
    id === "newStyleAttentionCard" || id === "newsFloor" ||
    id === "noticeFloor" || id === "recommendfloor";
}

function isWelcomeHomeType(type) {
  return type === "topTab" || type === "searchC" ||
    type === "dynamicIcon" || type === "locPermission" ||
    type === "login" || type === "hybrid" || type === "recommend";
}

function isCustomSurfaceName(name) {
  return name === "index" || name === "messagenew" ||
    name === "cart" || name === "home";
}


// 开屏广告
if (url.includes("functionId=start")) {
  if (obj?.images?.length > 0) {
    obj.images = [];
    modified = true;
  }
  if (obj?.showTimesDaily) {
    obj.showTimesDaily = 0;
    modified = true;
  }
} else if (url.includes("functionId=welcomeHome")) {
  // 首页配置
  if (obj?.floorList?.length > 0) {
    // 首页 图层列表
    compactInPlace(obj.floorList, item =>
      isWelcomeHomeType(item && item.type) &&
      (!welcomeExtraEnabled || !isWelcomeExtraExcluded(item && item.type))
    );
  }
  // 首页 下拉二楼
  if (obj?.webViewFloorList?.length > 0) {
    clearArrayIfNeeded(obj, "webViewFloorList");
  }
  // 首页 顶部右部推荐
  if (obj?.promotionTabs) {
    deleteIfPresent(obj, "promotionTabs");
  }
} else if (url.includes("functionId=readCustomSurfaceList")) {
  const modeMap = obj.result && obj.result.modeMap;
  const darkNavigation = modeMap && modeMap.dark && modeMap.dark.navigationAll;
  if (Array.isArray(darkNavigation) && darkNavigation.length > 0) {
    compactInPlace(darkNavigation, item =>
      isCustomSurfaceName(item && item.functionId)
    );
  }
  const normalNavigation = modeMap && modeMap.normal && modeMap.normal.navigationAll;
  if (Array.isArray(normalNavigation) && normalNavigation.length > 0) {
    compactInPlace(normalNavigation, item =>
      isCustomSurfaceName(item && item.functionId)
    );
  }
} else if (url.includes("functionId=deliverLayer") || url.includes("functionId=orderTrackBusiness")) {
  // 物流页面
  if (obj?.bannerInfo) {
    // 收货时寄快递享八折 享受条件苛刻 故移除
    deleteIfPresent(obj, "bannerInfo");
  }
  if (obj?.floors?.length > 0) {
    // 运费八折
    compactInPlace(obj.floors, item => {
      const id = item && item.mId;
      return id !== "banner" && id !== "jdDeliveryBanner";
    });
  }
} else if (url.includes("functionId=getTabHomeInfo")) {
  // 新品页面
  if (obj?.result?.iconInfo) {
    // 新品页 悬浮动图
    deleteIfPresent(obj.result, "iconInfo");
  }
  if (obj?.result?.roofTop) {
    // 新品页 下拉二楼
    deleteIfPresent(obj.result, "roofTop");
  }
} else if (url.includes("functionId=myOrderInfo")) {
  if (Array.isArray(obj.floors) && obj.floors.length > 0) {
    compactInPlace(obj.floors, floor => {
      const id = floor && floor.mId;
      if (id === "bannerFloor" || id === "bpDynamicFloor" || id === "plusFloor") {
        return false;
      }
      if (id === "virtualServiceCenter") {
        const centers = floor.data && floor.data.virtualServiceCenters;
        if (Array.isArray(centers) && centers.length > 0) {
          for (let index = 0; index < centers.length; index++) {
            const item = centers[index];
            const serviceList = item && item.serviceList;
            if (Array.isArray(serviceList) && serviceList.length > 0) {
              compactInPlace(serviceList, card =>
                !(card && card.serviceTitle === "精选特惠")
              );
            }
          }
        }
      }
      if (id === "customerServiceFloor" && floor.data && floor.data.moreText) {
        deleteIfPresent(floor.data, "moreIcon");
        deleteIfPresent(floor.data, "moreIcon_dark");
        if (floor.data.moreText !== " ") {
          floor.data.moreText = " ";
          modified = true;
        }
      }
      return true;
    });
  }
} else if (url.includes("functionId=personinfoBusiness")) {
  if (obj?.floors?.length > 0) {
    obj.floors = processFloors(obj.floors);
  }
  
  if (obj?.others?.floors?.length > 0) {
    obj.others.floors = processFloors(obj.others.floors);
  }
}

$done(modified ? { body: JSON.stringify(obj) } : {});




function cleanFloorData(floor) {
  if (!floor || !floor.mId) return;
  const data = floor.data;

  if (floor.mId === "basefloorinfo") {
    deleteIfPresent(data, "commonPopup");
    deleteIfPresent(data, "commonPopup_dynamic");
    clearArrayIfNeeded(data, "commonTips");
    clearArrayIfNeeded(data, "commonWindows");
    deleteIfPresent(data, "floatLayer");
  } else if (floor.mId === "orderIdFloor") {
    const infos = data && data.commentRemindInfo && data.commentRemindInfo.infos;
    if (Array.isArray(infos) && infos.length > 0) {
      data.commentRemindInfo.infos = [];
      modified = true;
    }
  } else if (floor.mId === "userinfo") {
    deleteIfPresent(data, "newPlusBlackCard");
  }
}

function processFloors(floors) {
  if (!Array.isArray(floors) || floors.length === 0) return floors;
  return compactInPlace(floors, floor => {
    if (isPersonInfoBusinessExcluded(floor && floor.mId)) return false;
    cleanFloorData(floor);
    return true;
  });
}
})();
