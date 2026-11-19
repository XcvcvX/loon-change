// Consolidated Xianyu response cleanup.
// Combines the overlapping R-Store and ishowshu goofish handlers so each
// response is parsed once while preserving the previously configured filters.
function main() {
  const url = ($request && $request.url) || "";

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
    return items;
  }
  const body = $response && $response.body;
  if (!body) return $done({});

  // 开屏：只在专用 splash API 上解析；删除实测下发节点 realTimeAd，
  // 让 App 收到与服务端“当日无广告”一致的响应形状。
  if (url.includes("/mtop.taobao.idlecommerce.splash.")) {
    if (typeof body !== "string" || !body.includes('"realTimeAd"')) return $done({});
    let splash;
    try {
      splash = JSON.parse(body);
    } catch (_) {
      return $done({});
    }
    let removed = 0;
    function removeRealTimeAd(node) {
      if (!node || typeof node !== "object") return;
      if (Array.isArray(node)) {
        for (let i = 0; i < node.length; i++) removeRealTimeAd(node[i]);
        return;
      }
      for (const key of Object.keys(node)) {
        if (key === "realTimeAd" && node[key] && typeof node[key] === "object") {
          delete node[key];
          removed++;
        } else {
          removeRealTimeAd(node[key]);
        }
      }
    }
    removeRealTimeAd(splash);
    return removed ? $done({ body: JSON.stringify(splash) }) : $done({});
  }

  let obj;
  try {
    obj = JSON.parse(body);
  } catch (error) {
    console.log("Goofish: invalid JSON, leave response unchanged");
    return $done({});
  }

  const data = obj && obj.data;

  if (url.includes("/mtop.taobao.idlehome.home.nextfresh")) {
    if (data && typeof data === "object") {
      // R-Store: remove homepage widgets and banner payloads.
      delete data.widgetReturnDO;
      delete data.bannerReturnDO;

      // R-Store + ishowshu: retain the same intersection of feed filters.
      if (Array.isArray(data.sections)) {
        const excludedTemplates = new Set([
          "fish_home_yunying_card_d3",
          "idlefish_seafood_market",
          "fish_home_chat_room"
        ]);
        compactInPlace(data.sections, section => {
          if (!section || typeof section !== "object") return false;
          const sectionData = section.data;
          if (sectionData && (sectionData.bizType === "AD" || sectionData.bizType === "homepage")) {
            return false;
          }
          const templateName = section.template && section.template.name;
          const dataTemplateName = sectionData && sectionData.template && sectionData.template.name;
          const cardType = sectionData && (sectionData.cardType || sectionData.cardTypeValue);
          const adTemplates = new Set([
            "fish_home_advertise_card_d3",
            "fish_home_advertise_card_d4",
            "fish_local_advertise_card_d4",
            "idlefish_local_feed2_marketing",
            "fish_home_feeds_pager_banner",
            "detail_recommend_ad_card"
          ]);
          if (excludedTemplates.has(templateName) || adTemplates.has(templateName) ||
              adTemplates.has(dataTemplateName) || cardType === "mamaAD" ||
              cardType === "homeMultiBanner") return false;
          const exContent = sectionData && sectionData.item && sectionData.item.main &&
            sectionData.item.main.exContent;
          if (exContent && (exContent.isAliMaMaAD === true || exContent.isAliMaMaAD === "true")) return false;
          return !!(sectionData && sectionData.cardTypeValue === "Item");
        });
      }

      // ishowshu's existing handling of the newer top icon menu.
      data.homeTopList = [];
    }
  }

  if (url.includes("/mtop.taobao.idle.local.home")) {
    if (data && Array.isArray(data.sections)) {
      compactInPlace(data.sections, section => {
        const sectionData = section && section.data;
        if (!sectionData) return true;
        const templateName = section.template && section.template.name;
        const dataTemplateName = sectionData.template && sectionData.template.name;
        const cardType = sectionData.cardType || sectionData.cardTypeValue;
        const adTemplate = /^(fish_home_advertise_card_d[34]|fish_local_advertise_card_d4|idlefish_local_feed2_marketing|fish_home_feeds_pager_banner|detail_recommend_ad_card)$/;
        return sectionData.bizType !== "AD" &&
          !adTemplate.test(templateName || "") &&
          !adTemplate.test(dataTemplateName || "") &&
          cardType !== "mamaAD" && cardType !== "homeMultiBanner";
      });
    }
  }

  if (url.includes("/mtop.taobao.idle.home.whale.modulet")) {
    if (data && data.container && typeof data.container === "object") {
      delete data.container.sections;
    }
  }

  if (url.includes("/mtop.idle.user.page.my.adapter")) {
    if (data && data.container && Array.isArray(data.container.sections)) {
      const keepIndexes = new Set(["0", "1", "3"]);
      compactInPlace(data.container.sections, item =>
        item && keepIndexes.has(String(item.index))
      );
    }
    if (data && typeof data === "object") data.ability = [];
  }

  if (url.includes("/mtop.taobao.idlehome.home.circle.list")) {
    if (data && Array.isArray(data.circleList)) {
      compactInPlace(data.circleList, circle =>
        circle && (circle.circleId === "1" || circle.circleId === "2")
      );
    }

    const filterHeadList = list => Array.isArray(list)
      ? compactInPlace(list, item => item && (item.bizCode === "main" || item.bizCode === "recycle"))
      : list;

    if (data && data.next && Array.isArray(data.next.headList)) {
      data.next.headList = filterHeadList(data.next.headList);
      const recycle = data.next.headList.find(item => item.bizCode === "recycle");
      if (recycle) {
        if (!recycle.showInfo || typeof recycle.showInfo !== "object") recycle.showInfo = {};
        recycle.showInfo.rightTagImage = {};
      }
    }

    if (data && Array.isArray(data.headList)) {
      data.headList = filterHeadList(data.headList);
      const recycle = data.headList.find(item => item.bizCode === "recycle");
      if (recycle) {
        if (!recycle.showInfo || typeof recycle.showInfo !== "object") recycle.showInfo = {};
        recycle.showInfo.rightTagImage = {};
      }
    }
  }

  if (url.includes("/mtop.taobao.idle.local.nearby.itemdetail.enter")) {
    if (data && typeof data === "object") {
      data.targetUrl = "";
      if (data.trackParams && typeof data.trackParams === "object") data.trackParams.itemIds = "";
      data.nearbyItemInfoList = [];
      data.name = "";
      data.desc = "";
      data.poiName = "";
    }
  }

  if (url.includes("/mtop.taobao.idlemtopsearch.search")) {
    if (data && Array.isArray(data.resultList)) {
      const excludedTemplates = new Set([
        "idlefish_search_card_category_select",
        "idlefish_search_spu_market_publish"
      ]);
      compactInPlace(data.resultList, element => {
        if (!element || typeof element !== "object") return false;
        const exContent = element.data && element.data.item &&
          element.data.item.main && element.data.item.main.exContent;
        if (exContent && (exContent.isAliMaMaAD === true || exContent.isAliMaMaAD === "true")) {
          return false;
        }
        const cardType = element.data && element.data.cardType;
        if (cardType === "mamaAD" || cardType === "homeMultiBanner") return false;
        const templateName = element.data && element.data.template && element.data.template.name;
        return !excludedTemplates.has(templateName);
      });
    }
    if (data && typeof data === "object") {
      delete data.resultPrefixBar;
      if (Array.isArray(data.topList)) data.topList = [];
    }
  }

  if (url.includes("/mtop.taobao.idle.local.flow.plat.section")) {
    const components = data && data.data && data.data.components;
    if (Array.isArray(components)) {
      compactInPlace(components, item =>
        item && item.key !== "fish_home_activity_enter_cardV1"
      );
    }
  }

  return $done({ body: JSON.stringify(obj) });
}
main();
