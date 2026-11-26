// 2024-08-20 09:49
/*需要分流禁用掉 
ip-cidr, 123.207.209.39/32, reject
ip-cidr, 123.207.209.60/32, reject
ip-cidr, 139.199.240.12/32, reject
ip-cidr, 162.14.157.2/32, reject
ip-cidr, 162.14.157.24/32, reject
群友EDDA分享
ip-cidr, 139.199.240.15/32, reject
*/

const url = $request.url;
if (!$response.body) {
  $done({});
} else {
  let obj = JSON.parse($response.body);

  function filterInPlace(items, predicate) {
    let write = 0;
    for (let read = 0; read < items.length; read++) {
      const item = items[read];
      if (predicate(item, read)) items[write++] = item;
    }
    items.length = write;
    return items;
  }

if (url.includes("/other/pGetSceneList")) {
  if (Array.isArray(obj.data?.scene_list)) {
    filterInPlace(obj.data.scene_list, item => item.text !== "优惠商城");
  }
  if (Array.isArray(obj.data?.show_data)) {
    for (let i = 0; i < obj.data.show_data.length; i++) {
      const block = obj.data.show_data[i];
      if (Array.isArray(block.scene_ids)) {
        filterInPlace(block.scene_ids, id => id !== "scene_coupon_mall");
      }
    }
  }
}

if (url.includes("/homepage/v1/core")) {
  const keepNavIds = ['dache_anycar', 'driverservice', 'bike'];
  if (obj.data?.order_cards?.nav_list_card?.data) {
    filterInPlace(obj.data.order_cards.nav_list_card.data, item => keepNavIds.includes(item.nav_id));
  }
  const keepBottomNavIds = ['v6x_home', 'home_page', 'user_center'];
  if (obj.data?.disorder_cards?.bottom_nav_list?.data) {
    filterInPlace(obj.data.disorder_cards.bottom_nav_list.data, item => keepBottomNavIds.includes(item.id));
  }
}

if (url.includes("/ota/na/yuantu/infoList")) {
  if (obj.data?.disorder_cards?.top_banner_card?.data[0]?.T === "yuentu_top_banner") {
    obj.data.disorder_cards.top_banner_card.data.splice(0, 1);
  }
}

if (url.includes("/gulfstream/passenger-center/v2/other/pInTripLayout")) {
  const namesToRemove = ["passenger_common_casper"];
  filterInPlace(obj.data.order_components, component => !(component.name && namesToRemove.includes(component.name)));
}

if (url.includes("/usercenter/me")) {
  const excludedTitles = ['天天领福利', '金融服务', '更多服务', '企业服务', '安全中心'];

  if (obj.data?.cards) {
    filterInPlace(obj.data.cards, card => !excludedTitles.includes(card.title));

    for (let i = 0; i < obj.data.cards.length; i++) {
      const card = obj.data.cards[i];
      if (card.tag === "wallet") {
        if (card.items) {
          filterInPlace(card.items, item => item.title === "优惠券");
        }
        if (card.card_type === 4 && card.bottom_items) {
          filterInPlace(card.bottom_items, item => item.title === "省钱套餐" || item.title === "天天神券");
        }
      }
    }
  }
}

// 微信小程序
if (url.includes("/common/v5")) {
  filterInPlace(obj.data.sections, item => item.sectionId === "center_v2" || item.sectionId === "head_v2" || item.sectionId === "core_function");
}

$done({body: JSON.stringify(obj)});
}
