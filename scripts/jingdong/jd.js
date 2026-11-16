// Consolidated Jingdong response cleaner.
// Preserves the combined R-Store + FMZ behavior while parsing each response once.
(function () {
  const url = ($request && $request.url) || "";
  const body = $response && $response.body;
  if (typeof body !== "string" || !body) {
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

  const PERSON_INFO_BUSINESS_MID_EXCLUDE = [
    "bigSaleFloor",
    "buyOften",
    "newAttentionCard",
    "newBigSaleFloor",
    "newStyleAttentionCard",
    "newsFloor",
    "noticeFloor",
    "recommendfloor",
  ];
  const WELCOME_HOME_TYPE_INCLUDE = [
    "topTab",
    "searchC",
    "dynamicIcon",
    "locPermission",
    "login",
    "hybrid",
    "recommend",
  ];
  const WELCOME_HOME_TYPE_EXCLUDE = [
    "bottomXview",
    "float",
    "photoCeiling",
    "ruleFloat",
    "searchIcon",
    "topRotate",
    "tabBarAtmosphere",
  ];
  const CUSTOM_SURFACE_NAME_INCLUDE = ["index", "messagenew", "cart", "home"];

  function cleanFloorData(floor) {
    if (!floor || typeof floor !== "object" || !floor.mId) return;
    if (floor.mId === "basefloorinfo") {
      if (floor.data && typeof floor.data === "object") {
        delete floor.data.commonPopup;
        delete floor.data.commonPopup_dynamic;
        if (Array.isArray(floor.data.commonTips) && floor.data.commonTips.length) {
          floor.data.commonTips = [];
        }
        if (Array.isArray(floor.data.commonWindows) && floor.data.commonWindows.length) {
          floor.data.commonWindows = [];
        }
        delete floor.data.floatLayer;
      }
    } else if (floor.mId === "orderIdFloor") {
      const infos = floor.data && floor.data.commentRemindInfo && floor.data.commentRemindInfo.infos;
      if (Array.isArray(infos) && infos.length) {
        floor.data.commentRemindInfo.infos = [];
      }
    } else if (floor.mId === "userinfo") {
      if (floor.data && typeof floor.data === "object") {
        delete floor.data.newPlusBlackCard;
      }
    }
  }

  function processFloors(floors) {
    if (!Array.isArray(floors) || floors.length === 0) return floors;
    return floors.filter((floor) => !PERSON_INFO_BUSINESS_MID_EXCLUDE.includes(floor && floor.mId))
      .map((floor) => {
        cleanFloorData(floor);
        return floor;
      });
  }

  if (url.includes("functionId=start")) {
    // Keep the original splash behavior from both sources.
    if (Array.isArray(obj.images) && obj.images.length > 0) obj.images = [];
    if (obj.showTimesDaily) obj.showTimesDaily = 0;
  } else if (url.includes("functionId=welcomeHome")) {
    // Apply R-Store's allowlist first, then FMZ's additional exclusions.
    if (Array.isArray(obj.floorList) && obj.floorList.length > 0) {
      obj.floorList = obj.floorList.filter((item) =>
        WELCOME_HOME_TYPE_INCLUDE.includes(item && item.type)
      );
      obj.floorList = obj.floorList.filter((item) =>
        !WELCOME_HOME_TYPE_EXCLUDE.includes(item && item.type)
      );
    }
    if (Array.isArray(obj.webViewFloorList) && obj.webViewFloorList.length > 0) {
      obj.webViewFloorList = [];
    }
    delete obj.promotionTabs;
  } else if (url.includes("functionId=readCustomSurfaceList")) {
    const modeMap = obj.result && obj.result.modeMap;
    ["dark", "normal"].forEach((mode) => {
      const navigation = modeMap && modeMap[mode] && modeMap[mode].navigationAll;
      if (Array.isArray(navigation) && navigation.length > 0) {
        modeMap[mode].navigationAll = navigation.filter((item) =>
          CUSTOM_SURFACE_NAME_INCLUDE.includes(item && item.functionId)
        );
      }
    });
  } else if (url.includes("functionId=deliverLayer") || url.includes("functionId=orderTrackBusiness")) {
    delete obj.bannerInfo;
    if (Array.isArray(obj.floors) && obj.floors.length > 0) {
      obj.floors = obj.floors.filter((item) =>
        !["banner", "jdDeliveryBanner"].includes(item && item.mId)
      );
    }
  } else if (url.includes("functionId=getTabHomeInfo")) {
    if (obj.result && typeof obj.result === "object") {
      delete obj.result.iconInfo;
      delete obj.result.roofTop;
    }
  } else if (url.includes("functionId=myOrderInfo")) {
    if (Array.isArray(obj.floors) && obj.floors.length > 0) {
      const newFloors = [];
      for (const floor of obj.floors) {
        if (["bannerFloor", "bpDynamicFloor", "plusFloor"].includes(floor && floor.mId)) {
          continue;
        }
        if (floor && floor.mId === "virtualServiceCenter") {
          const centers = floor.data && floor.data.virtualServiceCenters;
          if (Array.isArray(centers) && centers.length > 0) {
            floor.data.virtualServiceCenters = centers.map((item) => {
              if (item && Array.isArray(item.serviceList) && item.serviceList.length > 0) {
                item.serviceList = item.serviceList.filter((card) =>
                  !(card && card.serviceTitle === "精选特惠")
                );
              }
              return item;
            });
          }
        }
        if (floor && floor.mId === "customerServiceFloor" &&
            floor.data && floor.data.moreText) {
          delete floor.data.moreIcon;
          delete floor.data.moreIcon_dark;
          floor.data.moreText = " ";
        }
        newFloors.push(floor);
      }
      obj.floors = newFloors;
    }
  } else if (url.includes("functionId=personinfoBusiness")) {
    if (Array.isArray(obj.floors) && obj.floors.length > 0) {
      obj.floors = processFloors(obj.floors);
    }
    if (obj.others && Array.isArray(obj.others.floors) && obj.others.floors.length > 0) {
      obj.others.floors = processFloors(obj.others.floors);
    }
  }

  $done({ body: JSON.stringify(obj) });
})();
