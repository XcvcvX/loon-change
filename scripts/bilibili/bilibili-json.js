/********************************
Bilibili Remove Ads - Version 1.0
Checkout Source - https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/bilibili/json.js
Please note that you may need to reinstall app for script to work.

QuantumultX rewrite link:
https://raw.githubusercontent.com/zirawell/R-Store/main/Rule/QuanX/Adblock/App/B/哔哩哔哩/rewrite/bilibili.conf

Surge module link:
https://raw.githubusercontent.com/zirawell/R-Store/main/Rule/Surge/Adblock/App/B/哔哩哔哩/bilibili.sgmodule
********************************/

const url = $request.url;
if (!$response.body) {
  $done({});
} else {
  let obj = JSON.parse($response.body);

  function filterInPlace(items, predicate) {
    let write = 0;
    for (let read = 0, length = items.length; read < length; read++) {
      const item = items[read];
      if (predicate(item, read)) {
        if (write !== read) items[write] = item;
        write++;
      }
    }
    items.length = write;
    return items;
  }

  let modified = false;

  function filterTracked(items, predicate) {
    const originalLength = items.length;
    filterInPlace(items, predicate);
    if (items.length !== originalLength) modified = true;
    return items;
  }

  function deleteTracked(target, key) {
    if (Object.prototype.hasOwnProperty.call(target, key)) {
      delete target[key];
      modified = true;
    }
  }

  function filterAndSortAllowed(items, allowedNames) {
    const originalLength = items.length;
    filterInPlace(items, item => allowedNames.includes(item?.name));
    if (items.length !== originalLength) modified = true;
    let needsSort = false;
    for (let i = 1; i < items.length; i++) {
      if (allowedNames.indexOf(items[i - 1]?.name) > allowedNames.indexOf(items[i]?.name)) {
        modified = true;
        needsSort = true;
        break;
      }
    }
    if (needsSort) {
      items.sort((a, b) => allowedNames.indexOf(a?.name) - allowedNames.indexOf(b?.name));
    }
    return items;
  }

if (url.includes("/x/resource/show/tab/")) {
  // 底部选项卡
  if (obj?.data?.bottom?.length > 0) {
    const sortLists = ["首页", "动态", "关注", "我的"];
    filterAndSortAllowed(obj.data.bottom, sortLists);
  }
  // 首页导航栏
  if (obj?.data?.tab?.length > 0) {
    const sortLists = ["推荐", "热门", "影视", "动画"];
    filterAndSortAllowed(obj.data.tab, sortLists);
  }
  // 右上角按钮
  if (obj?.data?.top?.length > 0) {
    filterTracked(obj.data.top, (i) => i?.name === "消息");
    if (obj?.data?.top?.[0]?.pos) {
      if (obj.data.top[0].pos !== 1) { obj.data.top[0].pos = 1; modified = true; }
    }
  }
} else if (url.includes("/account/mine?")) {
  // 我的页面
  const del = ["rework_v1", "vip_section", "vip_section_v2"];
  for (let i of del) {
    // 不必要项目
    deleteTracked(obj.data, i);
  }
  if (obj?.data?.sections_v2?.length > 0) {
    const sections = obj.data.sections_v2;
    const originalSectionLength = sections.length;
    let sectionWrite = 0;
    for (let sectionRead = 0, sectionLength = sections.length; sectionRead < sectionLength; sectionRead++) {
      let item = sections[sectionRead];
      deleteTracked(item, "button");
      if (item?.style) {
        if (item?.style === 1 || item?.style === 2) {
          if (item?.title) {
            if (item?.title === "创作中心" || item?.title === "推荐服务") {
              // 创作中心 推荐服务
              continue;
            } else if (item?.title === "更多服务") {
              deleteTracked(item, "title");
              if (item?.items?.length > 0) {
                const items = item.items;
                const originalItemsLength = items.length;
                let itemWrite = 0;
                for (let itemRead = 0, itemLength = originalItemsLength; itemRead < itemLength; itemRead++) {
                  const i = items[itemRead];
                  if (/user_center\/feedback/g.test(i?.uri)) {
                    // 联系客服
                    if (itemWrite !== itemRead) items[itemWrite] = i;
                    itemWrite++;
                  } else if (/user_center\/setting/g.test(i?.uri)) {
                    // 设置
                    if (itemWrite !== itemRead) items[itemWrite] = i;
                    itemWrite++;
                  } else {
                    continue;
                  }
                }
                items.length = itemWrite;
                if (itemWrite !== originalItemsLength) modified = true;
              }
            }
          }
        } else {
          // 其他style
          continue;
        }
      }
      if (sectionWrite !== sectionRead) sections[sectionWrite] = item;
      sectionWrite++;
    }
    sections.length = sectionWrite;
    if (sectionWrite !== originalSectionLength) modified = true;
  }
  // 非会员开启本地会员标识
  if (obj?.data?.vip) {
    if (obj?.data?.vip?.status === 0) {
      modified = true;
      obj.data.vip_type = 2;
      obj.data.vip.type = 2;
      obj.data.vip.status = 1;
      obj.data.vip.due_date = 3818419199; // Unix 时间戳 2090-12-31 23:59:59
      obj.data.vip.label = {
        path: "",
        text: "年度大会员",
        label_theme: "annual_vip",
        text_color: "#FFFFFF",
        bg_style: 1,
        bg_color: "#FB7299",
        border_color: "",
        image: "https://i0.hdslb.com/bfs/vip/8d4f8bfc713826a5412a0a27eaaac4d6b9ede1d9.png"
      };
      obj.data.vip.nickname_color = "#FB7299";
      obj.data.vip.role = 3;
    }
  }
} else if (url.includes("/account/mine/ipad")) {
  // ipad我的页面
  deleteTracked(obj.data, "ipad_upper_sections"); // 投稿 创作首页 稿件管理 有奖活动
  if (obj?.data?.ipad_recommend_sections?.length > 0) {
    // 789我的关注 790我的消息 791我的钱包 792直播中心 793大会员 794我的课程 2542我的游戏
    const itemList = [789, 790];
    filterTracked(obj.data.ipad_recommend_sections, (i) => itemList.includes(i.id));
  }
  if (obj?.data?.ipad_more_sections?.length > 0) {
    // 797我的客服 798设置 1070青少年守护
    const itemList = [797, 798];
    filterTracked(obj.data.ipad_more_sections, (i) => itemList.includes(i.id));
  }
} else if (url.includes("/account/myinfo")) {
  // 非会员开启会员专属清晰度
  if (obj?.data?.vip) {
    if (obj?.data?.vip?.status === 0) {
      modified = true;
      obj.data.vip.type = 2;
      obj.data.vip.status = 1;
      obj.data.vip.due_date = 3818419199; // Unix 时间戳 2090-12-31 23:59:59
      obj.data.vip.role = 3;
    }
  }
} else if (url.includes("/feed/index?")) {
  // 首页推荐信息流
  if (obj?.data?.items?.length > 0) {
    // 白名单
    filterTracked(obj.data.items, (i) => i?.card_goto === "av");
  }
  if (obj?.data?.config?.toast?.has_toast) {
    obj.data.config.toast.has_toast = false;
    modified = true;
  }
} else if (url.includes("/feed/index/story")) {
  // 竖屏模式信息流
  if (obj?.data?.items?.length > 0) {
    // vertical_live 直播内容
    // vertical_pgc 大会员专享
    const items = obj.data.items;
    const originalItemLength = items.length;
    let itemWrite = 0;
    for (let itemRead = 0, itemLength = items.length; itemRead < itemLength; itemRead++) {
      let item = items[itemRead];
      if (item?.hasOwnProperty("ad_info")) {
        continue;
      } else if (["vertical_ad_av", "vertical_live", "vertical_pgc"]?.includes(item?.card_goto)) {
        continue;
      } else {
        deleteTracked(item, "creative_entrance"); // 推荐话题搜索框
        deleteTracked(item, "story_cart_icon"); // 相关话题图标
        if (itemWrite !== itemRead) items[itemWrite] = item;
        itemWrite++;
      }
    }
    items.length = itemWrite;
    if (itemWrite !== originalItemLength) modified = true;
  }
} else if (url.includes("/search/square")) {
  // 搜索框
  if (obj?.data) {
    const current = obj.data;
    const keys = current && typeof current === "object" && !Array.isArray(current) ? Object.keys(current) : [];
    const alreadyClean = keys.length === 3 && current.type === "history" &&
      current.title === "搜索历史" && current.search_hotword_revision === 2;
    if (!alreadyClean) {
      obj.data = {type: "history", title: "搜索历史", search_hotword_revision: 2};
      modified = true;
    }
  }
} else if (url.includes("/splash")) {
  // 开屏广告
  if (obj?.data) {
    const item = ["account", "event_list", "preload", "show"];
    item.forEach((i) => {
      deleteTracked(obj.data, i);
    });
    if (obj?.data?.max_time) {
      if (obj.data.max_time !== 0) { obj.data.max_time = 0; modified = true; }
    }
    if (obj?.data?.min_interval) {
      if (obj.data.min_interval !== 31536000) { obj.data.min_interval = 31536000; modified = true; }
    }
    if (obj?.data?.pull_interval) {
      if (obj.data.pull_interval !== 31536000) { obj.data.pull_interval = 31536000; modified = true; }
    }
    if (obj?.data?.list?.length > 0) {
      for (let i of obj.data.list) {
        if (i.duration !== 0 || i.enable_pre_download !== false ||
            i.begin_time !== 3818332800 || i.end_time !== 3818419199) modified = true;
        i.duration = 0;
        i.enable_pre_download = false;
        i.begin_time = 3818332800; // Unix 时间戳 2090-12-31 00:00:00
        i.end_time = 3818419199; // Unix 时间戳 2090-12-31 23:59:59
      }
    }
  }
} else if (url.includes("/pgc/page/")) {
  // 观影页
  if (obj.result?.modules?.length > 0) {
    obj.result.modules.forEach((i) => {
      if (i?.style?.startsWith("banner")) {
        if (i?.items?.length > 0) {
          filterTracked(i.items, (ii) => ii?.link?.includes("play"));
        }
      } else if (i?.style?.startsWith("function")) {
        if (i?.items?.length > 0) {
          filterTracked(i.items, (ii) => ii?.blink?.startsWith("bilibili"));
        }
      } else if ([241, 1283, 1284, 1441]?.includes(i?.module_id)) {
        if (i?.items?.length > 0) {
          i.items = [];
          modified = true;
        }
      } else if (i?.style?.startsWith("tip")) {
        if (i?.items?.length > 0) {
          i.items = [];
          modified = true;
        }
      }
    });
  }
} else if (url.includes("/index/getInfoByRoom")) {
  // 直播
  deleteTracked(obj.data, "activity_banner_info");
  if (obj?.data?.shopping_info) {
    const shopping = obj.data.shopping_info;
    if (typeof shopping !== "object" || Array.isArray(shopping) ||
        shopping.is_show !== 0 || Object.keys(shopping).length !== 1) {
      obj.data.shopping_info = {is_show: 0};
      modified = true;
    }
  }
  if (obj?.data?.new_tab_info?.outer_list?.length > 0) {
    filterTracked(obj.data.new_tab_info.outer_list, (i) => i?.biz_id !== 33);
  }
}

$done(modified ? {body: JSON.stringify(obj)} : {});
}
