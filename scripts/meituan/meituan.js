// Consolidated Meituan response cleaner.
// Combines R-Store's Meituan image/mini-program handlers and the vendored
// aoomee Meituan app handlers without widening the reviewed URL inventory.
(function () {
  const url = ($request && $request.url) || "";
  const imageUrlRegex = /^https?:\/\/p\d\.meituan\.net\/linglong\//;

  function extractAfterAt(value) {
    const atIndex = value.lastIndexOf("@");
    return atIndex === -1 ? "-1" : value.substring(atIndex + 1);
  }

  function compareDimensions(value) {
    const widthMatch = value.match(/(\d+)w/);
    const width = widthMatch ? parseInt(widthMatch[1], 10) : null;
    const heightMatch = value.match(/(\d+)h/);
    const height = heightMatch ? parseInt(heightMatch[1], 10) : null;
    if (width == null || height == null) return false;
    return width === height || Math.abs(width - height) === 1;
  }

  function cleanLinglongImage() {
    const iconRegex1 = /\.(gif|jpg|webp|png)@(132w_96h|186w_135h|1284w|250w_0h|400w_0h|700w_0h|1200w_0h)/;
    const iconRegex2 = /%(4088h_88w|40115h_115w|4047h_189w|40157h_189w)_1e_1l\.(gif|jpg|webp|png)/;
    const urlRegex = /^https?:\/\/p\d\.meituan\.net\/linglong\/\w+\.(gif|jpg|webp|png)$/;
    let removeFlag = true;
    if (urlRegex.test(url)) {
      const headers = ($request && $request.headers) || {};
      const traceKey = Object.keys(headers).find((key) => /^(ai|dt|al|u)$/i.test(key));
      removeFlag = !!traceKey;
      if (url.endsWith("@1sc")) removeFlag = false;
    } else {
      const dimStr = extractAfterAt(url);
      if (dimStr !== "-1" && compareDimensions(dimStr)) removeFlag = false;
      if (iconRegex1.test(url) || iconRegex2.test(url)) removeFlag = false;
    }
    if (removeFlag) {
      $done({ body: "", headers: "", status: "HTTP/1.1 204 No Content" });
    } else {
      $done({});
    }
  }

  function isObj(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value);
  }

  function cleanTabArea(obj) {
    const resource = obj && obj.data && obj.data.resource;
    if (!isObj(resource) || !Array.isArray(resource.tabArea)) return false;
    const keepTabs = ["homepage", "mine"];
    const hideTabs = ["video", "xiaotuan"];
    const names = resource.tabArea.map((tab) => (isObj(tab) ? tab.tabName : ""));
    if (!keepTabs.every((name) => names.indexOf(name) >= 0)) return false;
    const kept = resource.tabArea.filter((tab) =>
      !(isObj(tab) && hideTabs.indexOf(tab.tabName) >= 0)
    );
    if (kept.length === resource.tabArea.length) return false;
    resource.tabArea = kept;
    return true;
  }

  function cleanFeed(obj) {
    const match = url.match(/\/lycoris\/scene\/([A-Za-z0-9_]+)/);
    if (!match || !["gwc_feed1_2265", "personalcenter_2154"].includes(match[1])) return false;
    if (!isObj(obj) || !Array.isArray(obj.data)) return false;
    obj.data = [];
    obj.bottom = true;
    if (!isObj(obj.ext)) obj.ext = {};
    obj.ext.forbidByExp = true;
    return true;
  }

  function cleanMine(obj) {
    if (!isObj(obj) || !Array.isArray(obj.children)) return false;
    const kept = obj.children.filter((child) =>
      !(isObj(child) && child.name === "mine_cross_recommend")
    );
    if (kept.length === obj.children.length) return false;
    obj.children = kept;
    return true;
  }

  function cleanDefaultWord(obj) {
    const response = obj && obj.searchIntroduceResponse;
    if (!isObj(response)) return false;
    let changed = false;
    const defaultWord = response.defaultWordRes;
    if (isObj(defaultWord) && Array.isArray(defaultWord.defaultWordItems) &&
        defaultWord.defaultWordItems.length) {
      defaultWord.defaultWordItems = [];
      changed = true;
    }
    if (Array.isArray(response.HotWordInfos) && response.HotWordInfos.length) {
      response.HotWordInfos = [];
      changed = true;
    }
    return changed;
  }

  function cleanHotRecommend(obj) {
    const data = obj && obj.data;
    if (!isObj(data) || !Array.isArray(data.segmentsV2)) return false;
    let changed = false;
    const keptSegments = [];
    data.segmentsV2.forEach((segment) => {
      if (!isObj(segment) || !Array.isArray(segment.hotwordSegments)) {
        keptSegments.push(segment);
        return;
      }
      const keptHotwords = segment.hotwordSegments.filter((hotword) =>
        !(isObj(hotword) &&
          ["EntranceHotwordsV2Hotwords", "EntranceHotwordsV2ContentCard"].includes(hotword.pageName))
      );
      if (keptHotwords.length === segment.hotwordSegments.length) {
        keptSegments.push(segment);
        return;
      }
      changed = true;
      if (keptHotwords.length) {
        segment.hotwordSegments = keptHotwords;
        keptSegments.push(segment);
      }
    });
    if (changed) data.segmentsV2 = keptSegments;
    const bubble = data.aiSearchBubble;
    if (isObj(bubble) && Array.isArray(bubble.bubbleTexts) && bubble.bubbleTexts.length) {
      bubble.bubbleTexts = [];
      changed = true;
    }
    return changed;
  }

  function cleanAiSkill(obj) {
    if (!isObj(obj) || typeof obj.data !== "string") return false;
    const data = JSON.parse(obj.data);
    if (!isObj(data) || !isObj(data.skills) || !Object.keys(data.skills).length) return false;
    data.skills = {};
    obj.data = JSON.stringify(data);
    return true;
  }

  function clearArea(root, key) {
    const holders = [root, root && root.data];
    let changed = false;
    holders.forEach((holder) => {
      if (!isObj(holder)) return;
      [holder.resourcesMap, holder.resource].forEach((resource) => {
        if (isObj(resource) && Array.isArray(resource[key]) && resource[key].length) {
          resource[key] = [];
          changed = true;
        }
      });
    });
    return changed;
  }

  function cleanMiniProgram(obj) {
    if (!obj || !obj.data) return false;
    if (Array.isArray(obj.data)) {
      const kept = obj.data.filter((item) =>
        item && item.name && ["首页", "神券", "我的"].includes(item.name)
      );
      const changed = kept.length !== obj.data.length;
      if (changed) obj.data = kept;
      return changed;
    }
    if (obj.data.oneCentBuy) {
      delete obj.data.oneCentBuy;
      return true;
    }
    return false;
  }

  if (imageUrlRegex.test(url)) {
    cleanLinglongImage();
    return;
  }

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

  let changed = false;
  try {
    if (/\/api\/miniprogram\//.test(url)) changed = cleanMiniProgram(obj);
    else if (/\/aggroup\/indexTab/.test(url)) changed = cleanTabArea(obj);
    else if (/\/lycoris\/scene\//.test(url)) changed = cleanFeed(obj);
    else if (/\/usercenter\/display/.test(url)) changed = cleanMine(obj);
    else if (/\/searchpage\/defaultword/.test(url)) changed = cleanDefaultWord(obj);
    else if (/\/searchpage\/hotword\/city\/divide\/hotrecommend\//.test(url)) changed = cleanHotRecommend(obj);
    else if (/\/assistant\/getAppClientHornConfig/.test(url)) changed = cleanAiSkill(obj);
    else if (/\/mop\/entry\/shoppingCartEntry/.test(url)) changed = clearArea(obj, "topBannerArea");
    else if (/\/entryModule\/startupPicture/.test(url)) changed = clearArea(obj, "startupPicArea");
  } catch (_) {
    changed = false;
  }

  if (changed) $done({ body: JSON.stringify(obj) });
  else $done({});
})();
