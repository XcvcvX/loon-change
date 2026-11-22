// loon-change: Soul lightweight response runtime and in-place cleanup v1; upstream zirawell/R-Store@a4f3b10d6038d77ae3e1ff68bd19a49071ebabd3
const GAME_TITLES_TO_REMOVE = [
  "异世界回响", "狼人魅影", "梦想海岛王", "幻想星球",
  "爆弹喵", "星球实验室", "兴趣群组", "群聊派对"
];

(function () {
  const request = typeof $request !== "undefined" && $request ? $request : {};
  const response = typeof $response !== "undefined" && $response ? $response : {};
  const req_url = request.url || "";
  const rsp_body = response.body;

  if (typeof rsp_body !== "string" || rsp_body.length === 0) {
    $done({});
    return;
  }

  let mod_rsp;
  try {
    mod_rsp = JSON.parse(rsp_body);
  } catch (error) {
    console.log("[Soul] invalid JSON; keeping original response: " + error.message);
    $done({});
    return;
  }

  let modified = false;
  try {
    const shouldDeleteData =
      req_url.includes("/post/homepage/guide/card") ||
      req_url.includes("/furion/position/content") ||
      req_url.includes("/hot/soul/rank") ||
      req_url.includes("/post/gift/list") ||
      req_url.includes("/mobile/app/version/queryIos") ||
      req_url.includes("/teenager/config") ||
      req_url.includes("/winterfell/v2/getIpByDomain") ||
      req_url.includes("/official/scene/module");

    const shouldModifyLimitInfo =
      req_url.includes("/chat/limitInfo") &&
      mod_rsp && mod_rsp.data &&
      mod_rsp.data.limit !== undefined;

    if (mod_rsp && mod_rsp.data && shouldDeleteData) {
      delete mod_rsp.data;
      modified = true;
    }

    if (shouldModifyLimitInfo && mod_rsp.data.limit !== false) {
      mod_rsp.data.limit = false;
      modified = true;
    }

    if (req_url.includes("/v6/planet/config") && mod_rsp && mod_rsp.data) {
      const data = mod_rsp.data;
      if (data.gameInfo && Array.isArray(data.gameInfo.gameCards)) {
        modified = compactInPlace(data.gameInfo.gameCards, card =>
          GAME_TITLES_TO_REMOVE.indexOf(card.title) === -1
        ) || modified;
      }

      if (Array.isArray(data.coreCards)) {
        modified = compactInPlace(data.coreCards, card =>
          GAME_TITLES_TO_REMOVE.indexOf(card.title) === -1
        ) || modified;

        for (let i = 0; i < data.coreCards.length; i++) {
          const card = data.coreCards[i];
          if (card && Array.isArray(card.secondCards)) {
            modified = compactInPlace(card.secondCards, item =>
              GAME_TITLES_TO_REMOVE.indexOf(item.title) === -1
            ) || modified;
          }
        }
      }
    }

    if (mod_rsp && mod_rsp.data && Array.isArray(mod_rsp.data.coreCards)) {
      const cards = mod_rsp.data.coreCards;
      for (let i = 0; i < cards.length; i++) {
        if (cards[i].style === 2) {
          cards[i].style = 1;
          modified = true;
        }
      }
    }
  } catch (error) {
    console.log("[Soul] response cleanup failed; keeping original response: " + error.message);
    $done({});
    return;
  }

  if (modified) {
    $done({body: JSON.stringify(mod_rsp)});
  } else {
    $done({});
  }
})();

function compactInPlace(items, keep) {
  const length = items.length;
  let write = 0;
  for (let read = 0; read < length; read++) {
    const item = items[read];
    if (keep(item)) {
      if (write !== read) items[write] = item;
      write++;
    }
  }
  if (write === length) return false;
  items.length = write;
  return true;
}


