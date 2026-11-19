// Consolidated Xianyu response cleanup.
const AD_TEMPLATE_NAMES = new Set([
  "fish_home_advertise_card_d3",
  "fish_home_advertise_card_d4",
  "fish_local_advertise_card_d4",
  "idlefish_local_feed2_marketing",
  "fish_home_feeds_pager_banner",
  "detail_recommend_ad_card"
]);
const AD_TEMPLATE_RE = /^(fish_home_advertise_card_d[34]|fish_local_advertise_card_d4|idlefish_local_feed2_marketing|fish_home_feeds_pager_banner|detail_recommend_ad_card)$/;
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
    const stack = [splash];
    while (stack.length) {
      const node = stack.pop();
      if (!node || typeof node !== "object") continue;
      if (Array.isArray(node)) {
        for (let i = 0; i < node.length; i++) stack.push(node[i]);
        continue;
      }
      for (const key of Object.keys(node)) {
        if (key === "realTimeAd" && node[key] && typeof node[key] === "object") {
          delete node[key];
          removed++;
        } else {
          stack.push(node[key]);
        }
      }
    }
    return removed ? $done({ body: JSON.stringify(splash) }) : $done({});
  }

  const supportedPaths = [
      "/mtop.taobao.idlehome.home.nextfresh",
      "/mtop.taobao.idle.local.home",
      "/mtop.taobao.idle.home.whale.modulet",
      "/mtop.idle.user.page.my.adapter",
      "/mtop.taobao.idlehome.home.circle.list",
      "/mtop.taobao.idle.local.nearby.itemdetail.enter",
      "/mtop.taobao.idlemtopsearch.search",
      "/mtop.taobao.idle.local.flow.plat.section"
    ];
    if (!supportedPaths.some(path => url.includes(path))) return $done({});

    let obj;
  try {
    obj = JSON.parse(body);
  } catch (error) {
    console.log("Goofish: invalid JSON, leave response unchanged");
    return $done({});
  }

  const data = obj && obj.data;
  let modified = false;

  function compactTracked(items, keep) {
    const originalLength = items.length;
    compactInPlace(items, keep);
    if (items.length !== originalLength) modified = true;
    return items;
  }

  function deleteTracked(target, key) {
    if (Object.prototype.hasOwnProperty.call(target, key)) {
      delete target[key];
      modified = true;
    }
  }

  function normalizeRecycleCard(recycle) {
    if (!recycle.showInfo || typeof recycle.showInfo !== "object") {
      recycle.showInfo = {};
      modified = true;
    }
    const holder = recycle.showInfo;
    const current = holder.rightTagImage;
    if (!current || typeof current !== "object" ||
        Array.isArray(current) || Object.keys(current).length > 0) {
      holder.rightTagImage = {};
      // JSON.stringify ignores custom properties attached to arrays.
      if (!Array.isArray(holder)) modified = true;
    }
  }

  if (url.includes("/mtop.taobao.idlehome.home.nextfresh")) {
    if (data && typeof data === "object") {
      // R-Store: remove homepage widgets and banner payloads.
      deleteTracked(data, "widgetReturnDO");
      deleteTracked(data, "bannerReturnDO");

      // R-Store + ishowshu: retain the same intersection of feed filters.
      if (Array.isArray(data.sections)) {
        const excludedTemplates = new Set([
          "fish_home_yunying_card_d3",
          "idlefish_seafood_market",
          "fish_home_chat_room"
        ]);
        compactTracked(data.sections, section => {
          if (!section || typeof section !== "object") return false;
          const sectionData = section.data;
          if (sectionData && (sectionData.bizType === "AD" || sectionData.bizType === "homepage")) {
            return false;
          }
          const templateName = section.template && section.template.name;
          const dataTemplateName = sectionData && sectionData.template && sectionData.template.name;
          const cardType = sectionData && (sectionData.cardType || sectionData.cardTypeValue);
          if (excludedTemplates.has(templateName) || AD_TEMPLATE_NAMES.has(templateName) ||
              AD_TEMPLATE_NAMES.has(dataTemplateName) || cardType === "mamaAD" ||
              cardType === "homeMultiBanner") return false;
          const exContent = sectionData && sectionData.item && sectionData.item.main &&
            sectionData.item.main.exContent;
          if (exContent && (exContent.isAliMaMaAD === true || exContent.isAliMaMaAD === "true")) return false;
          return !!(sectionData && sectionData.cardTypeValue === "Item");
        });
      }

      // ishowshu's existing handling of the newer top icon menu.
      if (!Array.isArray(data.homeTopList) || data.homeTopList.length > 0) {
        data.homeTopList = [];
        modified = true;
      }
    }
  }

  if (url.includes("/mtop.taobao.idle.local.home")) {
    if (data && Array.isArray(data.sections)) {
      compactTracked(data.sections, section => {
        const sectionData = section && section.data;
        if (!sectionData) return true;
        const templateName = section.template && section.template.name;
        const dataTemplateName = sectionData.template && sectionData.template.name;
        const cardType = sectionData.cardType || sectionData.cardTypeValue;
        const adTemplate = /^(fish_home_advertise_card_d[34]|fish_local_advertise_card_d4|idlefish_local_feed2_marketing|fish_home_feeds_pager_banner|detail_recommend_ad_card)$/;
        return sectionData.bizType !== "AD" &&
          !AD_TEMPLATE_RE.test(templateName || "") &&
          !AD_TEMPLATE_RE.test(dataTemplateName || "") &&
          cardType !== "mamaAD" && cardType !== "homeMultiBanner";
      });
    }
  }

  if (url.includes("/mtop.taobao.idle.home.whale.modulet")) {
    if (data && data.container && typeof data.container === "object") {
      deleteTracked(data.container, "sections");
    }
  }

  if (url.includes("/mtop.idle.user.page.my.adapter")) {
    if (data && data.container && Array.isArray(data.container.sections)) {
      const keepIndexes = new Set(["0", "1", "3"]);
      compactTracked(data.container.sections, item =>
        item && keepIndexes.has(String(item.index))
      );
    }
    if (data && typeof data === "object" &&
        (!Array.isArray(data.ability) || data.ability.length > 0)) {
      data.ability = [];
      modified = true;
    }
  }

  if (url.includes("/mtop.taobao.idlehome.home.circle.list")) {
    if (data && Array.isArray(data.circleList)) {
      compactTracked(data.circleList, circle =>
        circle && (circle.circleId === "1" || circle.circleId === "2")
      );
    }

    const filterHeadList = list => Array.isArray(list)
      ? compactTracked(list, item => item && (item.bizCode === "main" || item.bizCode === "recycle"))
      : list;

    if (data && data.next && Array.isArray(data.next.headList)) {
      data.next.headList = filterHeadList(data.next.headList);
      const recycle = data.next.headList.find(item => item.bizCode === "recycle");
      if (recycle) {
        normalizeRecycleCard(recycle);
      }
    }

    if (data && Array.isArray(data.headList)) {
      data.headList = filterHeadList(data.headList);
      const recycle = data.headList.find(item => item.bizCode === "recycle");
      if (recycle) {
        normalizeRecycleCard(recycle);
      }
    }
  }

  if (url.includes("/mtop.taobao.idle.local.nearby.itemdetail.enter")) {
    if (data && typeof data === "object") {
      if (data.targetUrl !== "") { data.targetUrl = ""; modified = true; }
      if (data.trackParams && typeof data.trackParams === "object" &&
          data.trackParams.itemIds !== "") {
        data.trackParams.itemIds = "";
        modified = true;
      }
      if (!Array.isArray(data.nearbyItemInfoList) || data.nearbyItemInfoList.length > 0) {
        data.nearbyItemInfoList = [];
        modified = true;
      }
      if (data.name !== "") { data.name = ""; modified = true; }
      if (data.desc !== "") { data.desc = ""; modified = true; }
      if (data.poiName !== "") { data.poiName = ""; modified = true; }
    }
  }

  if (url.includes("/mtop.taobao.idlemtopsearch.search")) {
    if (data && Array.isArray(data.resultList)) {
      const excludedTemplates = new Set([
        "idlefish_search_card_category_select",
        "idlefish_search_spu_market_publish"
      ]);
      compactTracked(data.resultList, element => {
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
      deleteTracked(data, "resultPrefixBar");
      if (Array.isArray(data.topList) && data.topList.length > 0) {
        data.topList = [];
        modified = true;
      }
    }
  }

  if (url.includes("/mtop.taobao.idle.local.flow.plat.section")) {
    const components = data && data.data && data.data.components;
    if (Array.isArray(components)) {
      compactTracked(components, item =>
        item && item.key !== "fish_home_activity_enter_cardV1"
      );
    }
  }

  return $done(modified ? { body: JSON.stringify(obj) } : {});
}
main();
