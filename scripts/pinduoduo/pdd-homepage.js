// Pinduoduo homepage response cleanup.
// Consolidates the overlapping R-Store and ishowshu handlers while preserving
// their combined filtering behavior and the native JSON field cleanup.
// Keep immutable lookup tables and predicates outside the response hot path.
const ALLOWED_BOTTOM_LINKS = new Set(["index.html", "chat_list.html", "personal.html"]);
const ALLOWED_BOTTOM_TITLES = new Set(["首页", "聊天", "个人中心"]);
const DENIED_BOTTOM_TITLES = new Set(["多多视频", "大促会场", "搜索", "直播"]);
const REMOVED_HOMEPAGE_MODULES = new Set([
  "irregular_banner_dy", "irregular_banner", "ad_module",
  "icon_set", "recommend_fresh_info", "timeline"
]);

function keepBottomTab(tab) {
  return tab && ALLOWED_BOTTOM_TITLES.has(tab.title)
    && !DENIED_BOTTOM_TITLES.has(tab.title)
    && ALLOWED_BOTTOM_LINKS.has(String(tab.link || ""));
}

function keepBufferBottomTab(tab) {
  return tab && ALLOWED_BOTTOM_LINKS.has(String(tab.link || ""));
}

function keepHomepageModule(item) {
  return item && !REMOVED_HOMEPAGE_MODULES.has(item.module_name);
}

function main() {
  const url = $request.url || "";

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
    items.length = write;
    if (write !== length) modified = true;
    return items;
  }

  function deleteIfPresent(target, key) {
    if (target && Object.prototype.hasOwnProperty.call(target, key)) {
      delete target[key];
      modified = true;
    }
  }
  const body = $response && $response.body;
  if (!body) return $done({});

  let obj;
  try {
    obj = JSON.parse(body);
  } catch (error) {
    console.log("PDD homepage: invalid JSON, leave response unchanged");
    return $done({});
  }

  if (url.includes("/api/alexa/homepage/hub")) {
    const result = obj && obj.result;
    if (result && typeof result === "object") {
      if (result.dy_module && typeof result.dy_module === "object") {
        deleteIfPresent(result.dy_module, "irregular_banner_dy");
      }
      deleteIfPresent(result, "icon_set");
      deleteIfPresent(result, "search_bar_hot_query");

      // Preserve both upstream bottom-tab filters.
      if (Array.isArray(result.bottom_tabs)) {
        compactInPlace(result.bottom_tabs, keepBottomTab);
      }
      if (Array.isArray(result.buffer_bottom_tabs)) {
        compactInPlace(result.buffer_bottom_tabs, keepBufferBottomTab);
      }

      // ishowshu removes the homepage top category bar.
      if (Array.isArray(result.all_top_opts) && result.all_top_opts.length > 0) {
        result.all_top_opts = [];
        modified = true;
      }

      // ishowshu's homepage feed-module cleanup.
      if (Array.isArray(result.module_order)) {
        compactInPlace(result.module_order, keepHomepageModule);
      }
    }
  }

  return $done(modified ? { body: JSON.stringify(obj) } : {});
}
main();
