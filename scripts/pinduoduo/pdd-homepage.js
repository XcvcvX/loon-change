// Pinduoduo homepage response cleanup.
// Consolidates the overlapping R-Store and ishowshu handlers while preserving
// their combined filtering behavior and the native JSON field cleanup.
function main() {
  const url = $request.url || "";

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
        delete result.dy_module.irregular_banner_dy;
      }
      delete result.icon_set;
      delete result.search_bar_hot_query;

      // Preserve both upstream bottom-tab filters.
      const allowedLinks = new Set(["index.html", "chat_list.html", "personal.html"]);
      const allowedTitles = new Set(["首页", "聊天", "个人中心"]);
      const deniedTitles = new Set(["多多视频", "大促会场", "搜索", "直播"]);
      if (Array.isArray(result.bottom_tabs)) {
        compactInPlace(result.bottom_tabs, tab =>
          tab && allowedTitles.has(tab.title) && !deniedTitles.has(tab.title)
          && allowedLinks.has(String(tab.link || ""))
        );
      }
      if (Array.isArray(result.buffer_bottom_tabs)) {
        compactInPlace(result.buffer_bottom_tabs, tab =>
          tab && allowedLinks.has(String(tab.link || ""))
        );
      }

      // ishowshu removes the homepage top category bar.
      if (Array.isArray(result.all_top_opts)) result.all_top_opts = [];

      // ishowshu's homepage feed-module cleanup.
      const removedModules = new Set([
        "irregular_banner_dy", "irregular_banner", "ad_module",
        "icon_set", "recommend_fresh_info", "timeline"
      ]);
      if (Array.isArray(result.module_order)) {
        compactInPlace(result.module_order, item =>
          item && !removedModules.has(item.module_name)
        );
      }
    }
  }

  return $done({ body: JSON.stringify(obj) });
}
main();
