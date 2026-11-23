// loon-change: Ximalaya in-place filters and lazy response serialization v1; upstream zirawell/R-Store@1e08bab55bcffc396be39f914f48151443344493
const KEEP_CATEGORY_TYPES = new Set(["recommend", "template_category", "single_category"]);
const KEEP_HOME_ENTRANCE_IDS = new Set([210, 213, 215]);

const url = typeof $request !== "undefined" && $request ? ($request.url || "") : "";
const body = typeof $response !== "undefined" && $response ? $response.body : "";

if (typeof body !== "string" || body.length === 0) {
  $done({});
} else {
  let route = 0;
  if (url.includes("/discovery-category/customCategories")) route = 1;
  else if (/\/discovery-category\/v\d\/category/.test(url)) route = 2;
  else if (url.includes("/focus-mobile/focusPic")) route = 3;
  else if (/\/discovery-feed\/v\d\/mix/.test(url)) route = 4;
  else if (/\/mobile-user\/v\d\/homePage/.test(url)) route = 5;

  if (route === 0) {
    $done({});
  } else {
    let modified = false;
    try {
      const obj = JSON.parse(body);

      switch (route) {
        case 1:
          if (obj.customCategoryList) {
            modified = compactInPlace(obj.customCategoryList, item =>
              KEEP_CATEGORY_TYPES.has(item.itemType) && item.categoryId !== 1005
            ) || modified;
          }
          if (obj.defaultTabList) {
            modified = compactInPlace(obj.defaultTabList, item =>
              KEEP_CATEGORY_TYPES.has(item.itemType) && item.categoryId !== 1005
            ) || modified;
          }
          break;

        case 2:
          if (obj.focusImages && obj.focusImages.data) {
            modified = compactInPlace(obj.focusImages.data, item =>
              item.realLink.indexOf("open") !== -1 && !item.isAd
            ) || modified;
          }
          break;

        case 3:
          if (obj.header && obj.header.length <= 1) {
            modified = compactInPlace(obj.header[0].item.list[0].data, item =>
              item.realLink.indexOf("open") !== -1 && !item.isAd
            ) || modified;
          }
          break;

        case 4:
          if (Array.isArray(obj.header) && obj.header.length === 2) {
            delete obj.header[0];
            modified = true;
          }
          modified = compactInPlace(obj.body, item =>
            !(item.item?.adInfo || item.item?.moduleType == "mix_ad" || "bigCard" == item.displayClass)
          ) || modified;
          break;

        case 5:
          if (obj.data.serviceModule.entrances) {
            modified = compactInPlace(obj.data.serviceModule.entrances, item =>
              KEEP_HOME_ENTRANCE_IDS.has(item.id)
            ) || modified;
          }
          break;
      }

      if (modified) {
        $done({body: JSON.stringify(obj)});
      } else {
        $done({});
      }
    } catch (error) {
      console.log("[Ximalaya] response cleanup failed; keeping original response: " + error.message);
      $done({});
    }
  }
}

function compactInPlace(items, keep) {
  if (!Array.isArray(items)) {
    throw new TypeError("Expected an array for Ximalaya response cleanup");
  }
  const length = items.length;
  let write = 0;
  for (let read = 0; read < length; read++) {
    const item = items[read];
    if (keep(item, read)) {
      if (write !== read) items[write] = item;
      write++;
    }
  }
  if (write === length) return false;
  items.length = write;
  return true;
}

