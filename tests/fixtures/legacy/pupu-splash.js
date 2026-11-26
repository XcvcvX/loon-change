/**
 * Pupu Supermarket response cleanup.
 *
 * Local performance-optimized snapshot of fmz200/wool_scripts/Scripts/PupuSplashAds.js
 * Upstream source commit: eca3853dfed0f2db829408a81b98ff279bcfe8f9
 *
 * One response follows exactly one endpoint branch. The body is parsed once,
 * serialized once, and completed once.
 */
const url = $request.url || "";
const body = $response.body;

if (!body) {
  $done({});
} else {
  const obj = JSON.parse(body);

  if (url.includes("/search/hot_keywords")) {
    obj.data = [];
  } else if (url.includes("/resource_preload/list_h5_resource")) {
    obj.data = obj.data.filter(item => item.filename !== "RecommendProduct.29e31893.js");
  } else if (url.includes("/advertisement/v1")) {
    obj.data = obj.data.filter(item => ![30, 50, 90, 320, 100, 770].includes(item.region_code));
    obj.data = obj.data.map(item => {
      if (item.region_code === 2) {
        // Remove the homepage carousel and banner ad positions.
        item.positions = item.positions.filter(position => ![890, 60, 2, 240, 2503].includes(position.component_code));
      }
      return item;
    });
  } else if (url.includes("/search_box/products")) {
    obj.data.feed_banner_cards = [];
  } else if (url.includes("/order_settlement/detail")) {
    obj.data.member_card_v2 = {};
  } else if (url.includes("/orders/list")) {
    if (obj && obj.data) {
      obj.data.forEach(item => {
        if (item) {
          delete item.just_in_time_comment;
        }
      });
    }
  }

  $done({ body: JSON.stringify(obj) });
}
