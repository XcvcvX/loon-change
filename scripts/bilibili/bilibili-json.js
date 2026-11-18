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
      if (predicate(item, read)) {\n        if (write !== read) items[write] = item;\n        write++;\n      }
    }
    items.length = write;
    return items;
  }

if (url.includes("/x/resource/show/tab/")) {
  // 底部选项卡
  if (obj?.data?.bottom?.length > 0) {
    const sortLists = ["首页", "动态", "关注", "我的"];
    filterInPlace(obj.data.bottom, (i) => sortLists.includes(i?.name)).sort((a, b) => sortLists.indexOf(a?.name) - sortLists.indexOf(b?.name));
  }
  // 首页导航栏
  if (obj?.data?.tab?.length > 0) {
    const sortLists = ["推荐", "热门", "影视", "动画"];
    filterInPlace(obj.data.tab, (i) => sortLists.includes(i?.name)).sort((a, b) => sortLists.indexOf(a?.name) - sortLists.indexOf(b?.name));
  }
  // 右上角按钮
  if (obj?.data?.top?.length > 0) {
    filterInPlace(obj.data.top, (i) => i?.name === "消息");
    if (obj?.data?.top?.[0]?.pos) {
      obj.data.top[0].pos = 1;
    }
  }
} else if (url.includes("/account/mine?")) {
  // 我的页面
  const del = ["rework_v1", "vip_section", "vip_section_v2"];
  for (let i of del) {
    // 不必要项目
    delete obj.data[i];
  }
  if (obj?.data?.sections_v2?.length > 0) {
    const sections = obj.data.sections_v2;
    let sectionWrite = 0;
    for (let sectionRead = 0, sectionLength = sections.length; sectionRead < sectionLength; sectionRead++) {
      let item = sections[sectionRead];
      delete item.button;
      if (item?.style) {
        if (item?.style === 1 || item?.style === 2) {
          if (item?.title) {
            if (item?.title === "创作中心" || item?.title === "推荐服务") {
              // 创作中心 推荐服务
              continue;
            } else if (item?.title === "更多服务") {
              delete item.title;
              if (item?.items?.length > 0) {
                const items = item.items;
                let itemWrite = 0;
                for (let itemRead = 0, itemLength = items.length; itemRead < itemLength; itemRead++) {
                  const i = items[itemRead];
                  if (/user_center\/feedback/g.test(i?.uri)) {
                    // 联系客服
                    if (itemWrite !== itemRead) items[itemWrite] = i;\n                    itemWrite++;
                  } else if (/user_center\/setting/g.test(i?.uri)) {
                    // 设置
                    if (itemWrite !== itemRead) items[itemWrite] = i;\n                    itemWrite++;
                  } else {
                    continue;
                  }
                }
                items.length = itemWrite;
              }
            }
          }
        } else {
          // 其他style
          continue;
        }
      }
      if (sectionWrite !== sectionRead) sections[sectionWrite] = item;\n      sectionWrite++;
    }
    sections.length = sectionWrite;
  }
  // 非会员开启本地会员标识
  if (obj?.data?.vip) {
    if (obj?.data?.vip?.status === 0) {
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
  delete obj.data.ipad_upper_sections; // 投稿 创作首页 稿件管理 有奖活动
  if (obj?.data?.ipad_recommend_sections?.length > 0) {
    // 789我的关注 790我的消息 791我的钱包 792直播中心 793大会员 794我的课程 2542我的游戏
    const itemList = [789, 790];
    filterInPlace(obj.data.ipad_recommend_sections, (i) => itemList.includes(i.id));
  }
  if (obj?.data?.ipad_more_sections?.length > 0) {
    // 797我的客服 798设置 1070青少年守护
    const itemList = [797, 798];
    filterInPlace(obj.data.ipad_more_sections, (i) => itemList.includes(i.id));
  }
} else if (url.includes("/account/myinfo")) {
  // 非会员开启会员专属清晰度
  if (obj?.data?.vip) {
    if (obj?.data?.vip?.status === 0) {
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
    filterInPlace(obj.data.items, (i) => i?.card_goto === "av");
  }
  if (obj?.data?.config?.toast?.has_toast) {
    obj.data.config.toast.has_toast = false;
  }
} else if (url.includes("/feed/index/story")) {
  // 竖屏模式信息流
  if (obj?.data?.items?.length > 0) {
    // vertical_live 直播内容
    // vertical_pgc 大会员专享
    const items = obj.data.items;
    let itemWrite = 0;
    for (let itemRead = 0, itemLength = items.length; itemRead < itemLength; itemRead++) {
      let item = items[itemRead];
      if (item?.hasOwnProperty("ad_info")) {
        continue;
      } else if (["vertical_ad_av", "vertical_live", "vertical_pgc"]?.includes(item?.card_goto)) {
        continue;
      } else {
        delete item.creative_entrance; // 推荐话题搜索框
        delete item.story_cart_icon; // 相关话题图标
        if (itemWrite !== itemRead) items[itemWrite] = item;\n        itemWrite++;
      }
    }
    items.length = itemWrite;
  }
} else if (url.includes("/search/square")) {
  // 搜索框
  if (obj?.data) {
    obj.data = {type: "history", title: "搜索历史", search_hotword_revision: 2};
  }
} else if (url.includes("/splash")) {
  // 开屏广告
  if (obj?.data) {
    const item = ["account", "event_list", "preload", "show"];
    item.forEach((i) => {
      delete obj.data[i];
    });
    if (obj?.data?.max_time) {
      obj.data.max_time = 0;
    }
    if (obj?.data?.min_interval) {
      obj.data.min_interval = 31536000;
    }
    if (obj?.data?.pull_interval) {
      obj.data.pull_interval = 31536000;
    }
    if (obj?.data?.list?.length > 0) {
      for (let i of obj.data.list) {
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
          filterInPlace(i.items, (ii) => ii?.link?.includes("play"));
        }
      } else if (i?.style?.startsWith("function")) {
        if (i?.items?.length > 0) {
          filterInPlace(i.items, (ii) => ii?.blink?.startsWith("bilibili"));
        }
      } else if ([241, 1283, 1284, 1441]?.includes(i?.module_id)) {
        if (i?.items?.length > 0) {
          i.items = [];
        }
      } else if (i?.style?.startsWith("tip")) {
        if (i?.items?.length > 0) {
          i.items = [];
        }
      }
    });
  }
} else if (url.includes("/index/getInfoByRoom")) {
  // 直播
  delete obj.data.activity_banner_info;
  if (obj?.data?.shopping_info) {
    obj.data.shopping_info = {is_show: 0};
  }
  if (obj?.data?.new_tab_info?.outer_list?.length > 0) {
    filterInPlace(obj.data.new_tab_info.outer_list, (i) => i?.biz_id !== 33);
  }
}

$done({body: JSON.stringify(obj)});
}
