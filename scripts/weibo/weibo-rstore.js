// loon-change: R-Store Weibo in-place response compaction v1; upstream zirawell/R-Store@52fcb40b118a15610686b9167a7ee8e59bc04709
// loon-change: Weibo flowlist/asyn nested reference cache v1
// loon-change: Weibo feed and comment lazy serialization v1
// loon-change: Weibo hot-loop scalar membership v1
// loon-change: Weibo /2/page cached itemid reads v1
/********************************
Weibo Remove Ads - Version 1.0
Checkout Source - https://raw.githubusercontent.com/RuCu6/QuanX/main/Scripts/weibo.js
Please note that you may need to reinstall app for script to work.

QuantumultX rewrite link:
https://raw.githubusercontent.com/zirawell/R-Store/main/Rule/QuanX/Adblock/App/W/微博/rewrite/weibo.conf

Surge module link:
https://raw.githubusercontent.com/zirawell/R-Store/main/Rule/Surge/Adblock/App/W/微博/weibo.sgmodule
********************************/

const url = $request.url;
let modified = !url.includes("/2/cardlist") && !url.includes("/2/comments/build_comments");

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
if (!$response) $done({});
if (!$response.body) $done({});
let body = $response.body;

// 微博详情页菜单配置
const itemMenusConfig = {
  creatortypeask: false, // 转发任务
  mblog_menus_apeal: true, // 申诉
  mblog_menus_avatar_widget: false, // 用此头像挂件
  mblog_menus_bullet_shield: true, // 屏蔽弹幕
  mblog_menus_card_bg: false, // 用此卡片背景
  mblog_menus_comment_manager: true, // 评论管理
  mblog_menus_copy_url: true, // 复制链接
  mblog_menus_custom: false, // 寄微博
  mblog_menus_delete: true, // 删除
  mblog_menus_edit: true, // 编辑
  mblog_menus_edit_history: true, // 编辑记录
  mblog_menus_edit_video: true, // 编辑视频
  mblog_menus_favorite: true, // 收藏
  mblog_menus_follow: true, // 关注
  mblog_menus_home: false, // 返回首页
  mblog_menus_long_picture: true, // 生成长图
  mblog_menus_modify_visible: true, // 设置分享范围
  mblog_menus_novelty: false, // 新鲜事投稿
  mblog_menus_open_reward: false, // 赞赏
  mblog_menus_popularize: false,
  mblog_menus_promote: false, // 推广
  mblog_menus_report: true, // 投诉
  mblog_menus_shield: true, // 屏蔽
  mblog_menus_sticking: true, // 置顶
  mblog_menus_video_feedback: false, // 播放反馈
  mblog_menus_video_later: false // 可能是稍后再看
};

if (url.includes("/interface/sdk/sdkad.php")) {
  // 开屏广告
  let obj = JSON.parse(body.substring(0, body.length - 2));
  if (obj?.needlocation) {
    obj.needlocation = false;
  }
  if (obj?.show_push_splash_ad) {
    obj.show_push_splash_ad = false;
  }
  if (obj?.background_delay_display_time) {
    obj.background_delay_display_time = 31536000; // 60 * 60 * 24 * 365 = 31536000
  }
  if (obj?.lastAdShow_delay_display_time) {
    obj.lastAdShow_delay_display_time = 31536000;
  }
  if (obj?.realtime_ad_video_stall_time) {
    obj.realtime_ad_video_stall_time = 0;
  }
  if (obj?.realtime_ad_timeout_duration) {
    obj.realtime_ad_timeout_duration = 0;
  }
  if (obj?.ads?.length > 0) {
    for (let item of obj.ads) {
      item.displaytime = 0;
      item.displayintervel = 31536000;
      item.allowdaydisplaynum = 0;
      item.begintime = "2040-01-01 00:00:00";
      item.endtime = "2040-01-01 23:59:59";
    }
  }
  $done({body: JSON.stringify(obj) + "OK"});
} else {
  let obj = JSON.parse(body);
  if (url.includes("/2/cardlist")) {
    if (obj?.cards?.length > 0) {
      const __loonSource32 = obj.cards;
      let __loonWrite32 = 0;
      const __loonLength32 = __loonSource32.length;
      for (let __loonRead32 = 0; __loonRead32 < __loonLength32; __loonRead32++) {
        let card = __loonSource32[__loonRead32];
        if (card?.card_group?.length > 0) {
          const __loonSource31 = card.card_group;
          let __loonWrite31 = 0;
          const __loonLength31 = __loonSource31.length;
          for (let __loonRead31 = 0; __loonRead31 < __loonLength31; __loonRead31++) {
            let group = __loonSource31[__loonRead31];
            let cardType = group.card_type;
            // 120,145 视频版块轮播图 192横版热门视频 电影 颜值 电视剧等
            if ((cardType === 120 || cardType === 145 || cardType === 192)) {
              continue;
            }
            // 我的热搜 查看更多热搜
            if ((cardType === 6 || cardType === 101)) {
              continue;
            }
            if (group?.mblog) {
              // 卡片挂件,关注按钮
              removeAvatar(group?.mblog);
            }
            __loonSource31[__loonWrite31++] = group;
          }
          __loonSource31.length = __loonWrite31;
          if (__loonWrite31 !== __loonLength31) modified = true;
          __loonSource32[__loonWrite32++] = card;
        } else {
          let cardType = card.card_type;
          // 17猜你想搜 58搜索偏好设置
          if ((cardType === 17 || cardType === 58)) {
            continue;
          }
          if (card?.mblog) {
            // 卡片挂件,关注按钮
            removeAvatar(card?.mblog);
          }
          __loonSource32[__loonWrite32++] = card;
        }
      }
      __loonSource32.length = __loonWrite32;
      if (__loonWrite32 !== __loonLength32) modified = true;
    }
  } else if (url.includes("/2/checkin/show")) {
    // 首页签到
    if (obj?.show) {
      obj.show = 0;
    }
    if (obj?.show_time) {
      obj.show_time = 0;
    }
  } else if (url.includes("/2/client/publisher_list")) {
    // 首页右上角按钮
    if (obj?.elements?.length > 0) {
      compactInPlace(obj.elements, i => i.app_name === "写微博" || i.app_name === "图片" || i.app_name === "视频");
    }
  } else if (url.includes("/2/comments/build_comments")) {
    // 评论区
    // loon-change: Weibo comment top-level array reference cache v1
    const commentDatas = obj?.datas;
    let rootComments;
    let replyComments;
    if (commentDatas?.length > 0) {
      const __loonSource30 = commentDatas;
      let __loonWrite30 = 0;
      const __loonLength30 = __loonSource30.length;
      for (let __loonRead30 = 0; __loonRead30 < __loonLength30; __loonRead30++) {
        let item = __loonSource30[__loonRead30];
        // loon-change: Weibo comment data reference cache v1
        const commentData = item?.data;
        if (commentData) {
          if (!isAd(commentData)) {
            // 微博伪装评论
            // loon-change: Weibo comment user/name reference cache v1
            const commentUser = commentData?.user;
            if (commentUser) {
              // 头像挂件,关注按钮
              removeAvatar(commentData, commentUser);
              const commentUserName = commentUser.name;
              if (commentUserName === "超话社区" || commentUserName === "微博开新年" || commentUserName === "微博热搜" || commentUserName === "微博视频") {
                continue;
              }
            }
            // loon-change: Weibo comment data decoration single-read cache v1
            // 评论气泡
            const commentBubble = commentData?.comment_bubble;
            if (commentBubble) {
              modified = true;
              delete commentData.comment_bubble;
            }
            // 评论弹幕
            const commentBulletMessage = commentData?.comment_bullet_screens_message;
            if (commentBulletMessage) {
              modified = true;
              delete commentData.comment_bullet_screens_message;
            }
            // 热评小图标 弹幕 首评
            const commentHotIcon = commentData?.hot_icon;
            if (commentHotIcon) {
              modified = true;
              delete commentData.hot_icon;
            }
            // 会员气泡按钮
            const commentVipButton = commentData?.vip_button;
            if (commentVipButton) {
              modified = true;
              delete commentData.vip_button;
            }
            // 6为你推荐更多精彩内容 15过滤提示
            if (item?.type === 6 || item?.type === 15) {
              continue;
            }
            if (item?.adType === "相关内容" || item?.adType === "相关评论" || item?.adType === "推荐") {
              continue;
            }
            __loonSource30[__loonWrite30++] = item;
          }
        }
      }
      __loonSource30.length = __loonWrite30;
      if (__loonWrite30 !== __loonLength30) modified = true;
    } else if ((rootComments = obj?.root_comments)?.length > 0) {
      const __loonSource29 = rootComments;
      let __loonWrite29 = 0;
      const __loonLength29 = __loonSource29.length;
      for (let __loonRead29 = 0; __loonRead29 < __loonLength29; __loonRead29++) {
        let item = __loonSource29[__loonRead29];
        if (!isAd(item)) {
          // 微博伪装评论
          // loon-change: Weibo root-comment user reference cache v1
          const commentUser = item.user;
          if (commentUser) {
            // 头像挂件,关注按钮
            removeAvatar(item, commentUser);
            const commentUserName = commentUser.name;
            if (commentUserName === "超话社区" || commentUserName === "微博视频") {
              continue;
            }
          }
          // loon-change: Weibo root-comment decoration single-read cache v1
          // 评论气泡
          const rootCommentBubble = item?.comment_bubble;
          if (rootCommentBubble) {
            modified = true;
            delete item.comment_bubble;
          }
          // 评论弹幕
          const rootCommentBulletMessage = item?.comment_bullet_screens_message;
          if (rootCommentBulletMessage) {
            modified = true;
            delete item.comment_bullet_screens_message;
          }
          // 热评小图标 弹幕 首评
          const rootCommentHotIcon = item?.hot_icon;
          if (rootCommentHotIcon) {
            modified = true;
            delete item.hot_icon;
          }
          // 会员气泡按钮
          const rootCommentVipButton = item?.vip_button;
          if (rootCommentVipButton) {
            modified = true;
            delete item.vip_button;
          }
          __loonSource29[__loonWrite29++] = item;
        }
      }
      __loonSource29.length = __loonWrite29;
      if (__loonWrite29 !== __loonLength29) modified = true;
    } else if ((replyComments = obj?.comments)?.length > 0) {
      const __loonSource28 = replyComments;
      let __loonWrite28 = 0;
      const __loonLength28 = __loonSource28.length;
      for (let __loonRead28 = 0; __loonRead28 < __loonLength28; __loonRead28++) {
        let item = __loonSource28[__loonRead28];
        // loon-change: Weibo reply-comment decoration single-read cache v1
        const replyUser = item?.user;
        const replyUserIcons = replyUser?.icons;
        if (replyUserIcons) {
          modified = true;
          delete replyUser.icons;
        }
        const replyComment = item?.reply_comment;
        const replyCommentBadge = replyComment?.comment_badge;
        if (replyCommentBadge) {
          modified = true;
          delete replyComment.comment_badge;
        }
        __loonSource28[__loonWrite28++] = item;
      }
      __loonSource28.length = __loonWrite28;
      if (__loonWrite28 !== __loonLength28) modified = true;
    }
    // loon-change: Weibo rootComment bubble single-read cache v1
    const rootComment = obj?.rootComment;
    const rootCommentBubble = rootComment?.comment_bubble;
    if (rootCommentBubble) {
      modified = true;
      delete rootComment.comment_bubble;
    }
    // 投票窗口
    if (obj?.status?.page_info) {
      removeVoteInfo(obj?.status);
    }
  } else if (url.includes("/2/container/asyn")) {
    // loon-change: Weibo container/asyn nested reference cache v1
    const asynItems = obj?.items;
    const asynItemsLength = asynItems?.length || 0;
    if (asynItemsLength > 0) {
      const __loonSource27 = asynItems;
      let __loonWrite27 = 0;
      const __loonLength27 = asynItemsLength;
      for (let __loonRead27 = 0; __loonRead27 < __loonLength27; __loonRead27++) {
        let item = __loonSource27[__loonRead27];
        const itemData = item?.data;
        const itemId = item?.itemId;
        // 关注按钮
        removeAvatar(itemData);
        if (/infeed_may_interest_in/.test(itemId)) {
          // 你可能感兴趣的超话
          continue;
        }
        if (itemId === null) {
          // 横版博主卡片
          continue;
        }
        const nestedItems = item?.items;
        const nestedItemsLength = nestedItems?.length || 0;
        if (nestedItemsLength > 0) {
          for (let nestedIndex = 0; nestedIndex < nestedItemsLength; nestedIndex++) {
            const nestedItem = nestedItems[nestedIndex];
            const nestedData = nestedItem?.data;
            // 背景卡片
            removeAvatar(nestedData);
            // 投票窗口
            removeVoteInfo(nestedData);
          }
        }
        __loonSource27[__loonWrite27++] = item;
      }
      __loonSource27.length = __loonWrite27;
      if (__loonWrite27 !== __loonLength27) modified = true;
    }
  } else if (url.includes("/2/direct_messages/user_list")) {
    if (obj?.user_list?.length > 0) {
      compactInPlace(obj.user_list, i => !(i?.user?.name === "活动通知" || i?.user?.name === "闪聊"));
    }
  } else if (url.includes("/2/flowlist")) {
    // loon-change: Weibo flowlist nested reference cache v1
    // 关注列表
    const flowItems = obj?.items;
    const flowItemsLength = flowItems?.length || 0;
    if (flowItemsLength > 0) {
      for (let itemIndex = 0; itemIndex < flowItemsLength; itemIndex++) {
        const item = flowItems[itemIndex];
        const nestedItems = item?.items;
        const nestedItemsLength = nestedItems?.length || 0;
        if (nestedItemsLength > 0) {
          for (let nestedIndex = 0; nestedIndex < nestedItemsLength; nestedIndex++) {
            const nestedItem = nestedItems[nestedIndex];
            const nestedData = nestedItem?.data;
            // 背景卡片
            removeAvatar(nestedData);
            // 投票窗口
            removeVoteInfo(nestedData);
          }
        }
      }
    }
    const channelInfo = obj?.channelInfo;
    const flowChannels = channelInfo?.channels;
    const flowChannelCount = flowChannels?.length || 0;
    if (flowChannelCount > 0) {
      const __loonSource26 = flowChannels;
      let __loonWrite26 = 0;
      const __loonLength26 = flowChannelCount;
      for (let __loonRead26 = 0; __loonRead26 < __loonLength26; __loonRead26++) {
        let tab = __loonSource26[__loonRead26];
        const flowId = tab?.flowId;
        if (/_selfrecomm/.test(flowId)) {
          // 关注页推荐tab
          continue;
        } else if (/_chaohua/.test(flowId)) {
          // 关注页超话tab
          continue;
        } else {
          __loonSource26[__loonWrite26++] = tab;
        }
      }
      __loonSource26.length = __loonWrite26;
      if (__loonWrite26 !== __loonLength26) modified = true;
    }
  } else if (url.includes("/2/flowpage")) {
    // 热搜列表
    if (obj?.items?.length > 0) {
      const __loonSource25 = obj.items;
      let __loonWrite25 = 0;
      const __loonLength25 = __loonSource25.length;
      for (let __loonRead25 = 0; __loonRead25 < __loonLength25; __loonRead25++) {
        let item = __loonSource25[__loonRead25];
        if (item?.data?.itemid === "hot-search-push-notice") {
          // 开启推送通知的提示
          continue;
        }
        if (item?.items?.length > 0) {
          const __loonSource24 = item.items;
          let __loonWrite24 = 0;
          const __loonLength24 = __loonSource24.length;
          for (let __loonRead24 = 0; __loonRead24 < __loonLength24; __loonRead24++) {
            let i = __loonSource24[__loonRead24];
            if (i?.data?.hasOwnProperty("promotion")) {
              // 热搜列表中的推广项目
              continue;
            } else if (/_img_search_stick/.test(i?.data?.pic)) {
              // 手动置顶的微博热搜
              continue;
            } else {
              __loonSource24[__loonWrite24++] = i;
            }
          }
          __loonSource24.length = __loonWrite24;
          if (__loonWrite24 !== __loonLength24) modified = true;
        }
        __loonSource25[__loonWrite25++] = item;
      }
      __loonSource25.length = __loonWrite25;
      if (__loonWrite25 !== __loonLength25) modified = true;
    }
  } else if (url.includes("/2/groups/allgroups/v2")) {
    // 顶部tab
    if (obj?.pageDatas?.length > 0) {
      // homeFeed关注 homeHot推荐
      const __loonSource23 = obj.pageDatas;
      let __loonWrite23 = 0;
      const __loonLength23 = __loonSource23.length;
      for (let __loonRead23 = 0; __loonRead23 < __loonLength23; __loonRead23++) {
        let item = __loonSource23[__loonRead23];
        if (item?.pageDataType === "homeExtend") {
          // 多余的推广tab 比如华为Mate60
          continue;
        } else {
          if (item?.categories?.length > 0) {
            const __loonSource22 = item.categories;
            let __loonWrite22 = 0;
            const __loonLength22 = __loonSource22.length;
            for (let __loonRead22 = 0; __loonRead22 < __loonLength22; __loonRead22++) {
              let i = __loonSource22[__loonRead22];
              if (i?.title === "默认分组") {
                if (i?.pageDatas?.length > 0) {
                  const __loonSource21 = i.pageDatas;
                  let __loonWrite21 = 0;
                  const __loonLength21 = __loonSource21.length;
                  for (let __loonRead21 = 0; __loonRead21 < __loonLength21; __loonRead21++) {
                    let ii = __loonSource21[__loonRead21];
                    if ((ii?.title === "最新微博" || ii?.title === "特别关注" || ii?.title === "好友圈" || ii?.title === "视频")) {
                      // 白名单列表
                      __loonSource21[__loonWrite21++] = ii;
                    } else {
                      continue;
                    }
                    if (ii?.title === "最新微博") {
                      ii.title = "微博";
                    }
                  }
                  __loonSource21.length = __loonWrite21;
                  if (__loonWrite21 !== __loonLength21) modified = true;
                }
              }
              __loonSource22[__loonWrite22++] = i;
            }
            __loonSource22.length = __loonWrite22;
            if (__loonWrite22 !== __loonLength22) modified = true;
          }
          __loonSource23[__loonWrite23++] = item;
        }
      }
      __loonSource23.length = __loonWrite23;
      if (__loonWrite23 !== __loonLength23) modified = true;
    }
  } else if (url.includes("/2/messageflow/notice")) {
    // 消息动态页
    if (obj?.messages?.length > 0) {
      const __loonSource20 = obj.messages;
      let __loonWrite20 = 0;
      const __loonLength20 = __loonSource20.length;
      for (let __loonRead20 = 0; __loonRead20 < __loonLength20; __loonRead20++) {
        let msg = __loonSource20[__loonRead20];
        if (msg?.msg_card?.ad_tag) {
          continue;
        } else {
          __loonSource20[__loonWrite20++] = msg;
        }
      }
      __loonSource20.length = __loonWrite20;
      if (__loonWrite20 !== __loonLength20) modified = true;
    }
  } else if (url.includes("/2/page")) {
    // 搜索页列表,超话
    if (obj?.cards?.length > 0) {
      if (obj?.cards?.[0]?.card_group?.length > 0) {
        compactInPlace(obj.cards[0].card_group, c => {
          if (c?.actionlog?.ext?.includes("ads_word")) return false;
          const itemId = c?.itemid;
          return !(itemId?.includes("t:51") || itemId?.includes("ads_word"));
        });
      }
      compactInPlace(obj.cards, i => {
        const itemId = i.itemid;
        return !(
          itemId?.includes("feed_-_invite") ||
          itemId?.includes("infeed_friends_recommend") ||
          itemId?.includes("infeed_may_interest_in") ||
          itemId?.includes("infeed_pagemanual3") ||
          itemId?.includes("infeed_weibo_mall") ||
          i?.mblog?.mblogtypename?.includes("广告")
        );
      });
    } else if (obj?.card_group?.length > 0) {
      compactInPlace(obj.card_group, i => i?.desc?.includes("你可能感兴趣的超话"));
    }
  } else if (url.includes("/2/profile/container_timeline")) {
    // loon-change: Weibo profile timeline hot-property cache v1
    // loon-change: Weibo profile timeline cached nested data v1
    // 个人主页关注弹窗
    if (obj?.loadedInfo?.follow_guide_info) {
      delete obj.loadedInfo.follow_guide_info;
    }
    // 个人主页信息流
    const profileItems = obj?.items;
    const profileItemsLength = profileItems?.length || 0;
    if (profileItemsLength > 0) {
      const __loonSource19 = profileItems;
      let __loonWrite19 = 0;
      const __loonLength19 = profileItemsLength;
      for (let __loonRead19 = 0; __loonRead19 < __loonLength19; __loonRead19++) {
        let item = __loonSource19[__loonRead19];
        const itemData = item?.data;
        const itemCategory = item?.category;
        const itemCardType = itemData?.card_type;
        const itemName = itemData?.name;
        const itemLeftHint = itemData?.left_hint;
        const itemData = item?.data;
        if (itemData?.left_hint?.[0]?.content === "全部微博(0)" && itemData?.card_type === 216) {
          // 全部微博为0的博主
          break;
        } else if (/内容/?.test(itemData?.name) && itemData?.card_type === 58) {
          // 个人微博页刷完后的推荐微博
          break;
        } else {
          if (item?.category === "card") {
            // 58微博展示时间段提示 216筛选按钮
            if ((itemData?.card_type === 58 || itemData?.card_type === 216)) {
              if (/没有公开博文，为你推荐以下精彩内容/.test(itemData?.name)) {
                // 个人微博页刷完后的推荐信息流
                continue;
              }
            }
            __loonSource19[__loonWrite19++] = item;
          } else if (item?.category === "group") {
            // 遍历group,保留置顶微博
            const itemHeader = item?.header;
            const itemHeaderData = itemHeader?.data;
            if (itemHeaderData?.icon) {
              // 置顶微博背景图
              delete itemHeaderData.icon;
            }
            const itemId = item?.itemId;
            if (itemId?.includes("INTEREST_PEOPLE")) {
              // 可能感兴趣的人
              continue;
            }
            const profileTypeId = item?.profile_type_id;
            if (profileTypeId === "weibo_cardpics") {
              // 近期热门 精选微博 那年今日等横版内容
              continue;
            }
            const groupItems = item?.items;
            const groupItemsLength = groupItems?.length || 0;
            if (groupItemsLength > 0) {
              const __loonSource18 = groupItems;
              let __loonWrite18 = 0;
              const __loonLength18 = groupItemsLength;
              for (let __loonRead18 = 0; __loonRead18 < __loonLength18; __loonRead18++) {
                let ii = __loonSource18[__loonRead18];
                const iiData = ii?.data;
                const iiCategory = ii?.category;
                const iiData = ii?.data;
                if (iiCategory === "feed") {
                  // 头像挂件,关注按钮
                  removeAvatar(iiData);
                  // 信息流推广
                  removeFeedAd(iiData);
                  // 投票窗口
                  removeVoteInfo(iiData);
                  // 评论指引
                  const enableCommentGuide = iiData?.enable_comment_guide;
                  if (enableCommentGuide) {
                    iiData.enable_comment_guide = false;
                  }
                  __loonSource18[__loonWrite18++] = ii;
                } else if (iiCategory === "card") {
                    const iiCardType = iiData?.card_type;
                  if ((iiCardType === 10 || iiCardType === 48 || iiCardType === 176)) {
                    // 最近关注与互动过的博主
                    continue;
                  }
                  const iiRightImage = iiData?.rightImage;
                  if (iiRightImage) {
                    // 新版置顶微博皇冠
                    delete iiData.rightImage;
                  }
                  const iiBackgroundImage = iiData?.backgroundImage;
                  if (iiBackgroundImage) {
                    // 新版置顶微博背景图
                    delete iiData.backgroundImage;
                  }
                  __loonSource18[__loonWrite18++] = ii;
                }
              }
              __loonSource18.length = __loonWrite18;
              if (__loonWrite18 !== __loonLength18) modified = true;
            }
            __loonSource19[__loonWrite19++] = item;
          } else if (item?.category === "feed") {
            if (!isAd(itemData)) {
              // 信息流推广
              removeFeedAd(itemData);
              // 投票窗口
              removeVoteInfo(itemData);
              const itemSource = itemData?.source;
              if (itemSource?.includes("生日动态")) {
                // 移除生日祝福微博
                continue;
              }
              const itemTitle = itemData?.title;
              if (itemTitle?.text !== "热门" && itemTitle?.structs?.length > 0) {
                // 移除赞过的微博 保留热门内容
                continue;
              }
              __loonSource19[__loonWrite19++] = item;
            }
          }
        }
      }
      __loonSource19.length = __loonWrite19;
      if (__loonWrite19 !== __loonLength19) modified = true;
    }
  } else if (url.includes("/2/profile/dealatt") || url.includes("/2/friendships/")) {
    // 个人主页点击关注后展示菜单
    if (obj?.cards?.length > 0) {
      // 相关推荐卡片
      obj.cards = [];
    }
    if (obj?.toolbar_menus_new?.items?.length > 0) {
      let toolbar = obj.toolbar_menus_new;
      // 底部菜单
      const __loonSource17 = toolbar.items;
      let __loonWrite17 = 0;
      const __loonLength17 = __loonSource17.length;
      for (let __loonRead17 = 0; __loonRead17 < __loonLength17; __loonRead17++) {
        let item = __loonSource17[__loonRead17];
        if (item?.identifier === "recommend") {
          // 相关推荐
          continue;
        } else if (/reward_/.test(item?.identifier)) {
          // 赞赏
          continue;
        } else {
          __loonSource17[__loonWrite17++] = item;
        }
      }
      __loonSource17.length = __loonWrite17;
      if (__loonWrite17 !== __loonLength17) modified = true;
    }
  } else if (url.includes("/2/profile/me")) {
    // 我的页面
    if (obj?.vipHeaderBgImage) {
      delete obj.vipHeaderBgImage;
    }
    if (obj?.items?.length > 0) {
      const __loonSource16 = obj.items;
      let __loonWrite16 = 0;
      const __loonLength16 = __loonSource16.length;
      for (let __loonRead16 = 0; __loonRead16 < __loonLength16; __loonRead16++) {
        let item = __loonSource16[__loonRead16];
        let itemId = item.itemId;
        if (itemId === "profileme_mine") {
          if (item?.header) {
            delete item.header.vipView;
            delete item.header.vipCenter;
            delete item.header.vipIcon;
          }
          if (item?.items?.length > 0) {
            for (let d of item.items) {
              if (d.itemId === "mainnums_friends") {
                let s = d.click.modules[0].scheme;
                d.click.modules[0].scheme = s.replace("231093_-_selfrecomm", "231093_-_selffollowed");
              }
            }
          }
          __loonSource16[__loonWrite16++] = item;
        } else if (itemId === "100505_-_top8") {
          if (item?.items?.length > 0) {
            compactInPlace(item.items, i =>
            i.itemId === "100505_-_album" ||
            i.itemId === "100505_-_like" ||
            i.itemId === "100505_-_watchhistory" ||
            i.itemId === "100505_-_draft"
          );
          }
          __loonSource16[__loonWrite16++] = item;
        } else if (itemId === "100505_-_manage") {
          if (item?.style) {
            delete item.style;
          }
          // 移除分隔符的点点点
          if (item?.images) {
            delete item.images;
          }
          __loonSource16[__loonWrite16++] = item;
        } else if (itemId === "100505_-_manage2") {
          // 移除面板样式
          if (item?.footer) {
            delete item.footer;
          }
          // 移除框内推广
          if (item?.body) {
            delete item.body;
          }
          __loonSource16[__loonWrite16++] = item;
        } else if (itemId === "100505_-_chaohua" || itemId === "100505_-_recentlyuser") {
          __loonSource16[__loonWrite16++] = item;
        } else {
          // 移除其他推广
          continue;
        }
      }
      __loonSource16.length = __loonWrite16;
      if (__loonWrite16 !== __loonLength16) modified = true;
    }
  } else if (url.includes("/2/profile/statuses/tab")) {
    if (obj?.cards?.length > 0) {
      const __loonSource15 = obj.cards;
      let __loonWrite15 = 0;
      const __loonLength15 = __loonSource15.length;
      for (let __loonRead15 = 0; __loonRead15 < __loonLength15; __loonRead15++) {
        let card = __loonSource15[__loonRead15];
        if (card?.card_group?.length > 0) {
          const __loonSource14 = card.card_group;
          let __loonWrite14 = 0;
          const __loonLength14 = __loonSource14.length;
          for (let __loonRead14 = 0; __loonRead14 < __loonLength14; __loonRead14++) {
            let group = __loonSource14[__loonRead14];
            let cardType = group.card_type;
            // 22那年今天
            if (cardType === 22) {
              continue;
            }
            if (group?.mblog) {
              // 卡片挂件,关注按钮
              removeAvatar(group?.mblog);
              // 投票窗口
              removeVoteInfo(group?.mblog);
            }
            __loonSource14[__loonWrite14++] = group;
          }
          __loonSource14.length = __loonWrite14;
          if (__loonWrite14 !== __loonLength14) modified = true;
          __loonSource15[__loonWrite15++] = card;
        } else {
          if (card?.mblog) {
            // 卡片挂件,关注按钮
            removeAvatar(card?.mblog);
            // 投票窗口
            removeVoteInfo(card?.mblog);
          }
          __loonSource15[__loonWrite15++] = card;
        }
      }
      __loonSource15.length = __loonWrite15;
      if (__loonWrite15 !== __loonLength15) modified = true;
    }
    // 我的热搜
    if (obj?.cardlistInfo?.page_type === "08") {
      delete obj.cardlistInfo;
    }
  } else if (url.includes("/2/profile/userinfo")) {
    // 个人详情页
    if (obj?.footer?.data) {
      let toolbar = obj.footer.data.toolbar_menus_new;
      // 底部菜单项目
      if (toolbar?.items?.length > 0) {
        const __loonSource13 = toolbar.items;
        let __loonWrite13 = 0;
        const __loonLength13 = __loonSource13.length;
        for (let __loonRead13 = 0; __loonRead13 < __loonLength13; __loonRead13++) {
          let item = __loonSource13[__loonRead13];
          if (item?.identifier === "recommend") {
            // 相关推荐
            continue;
          } else if (item?.identifier === "urge") {
            // 催更
            continue;
          } else if (/reward_/.test(item?.identifier)) {
            // 赞赏
            continue;
          } else {
            __loonSource13[__loonWrite13++] = item;
          }
        }
        __loonSource13.length = __loonWrite13;
        if (__loonWrite13 !== __loonLength13) modified = true;
      }
      if (toolbar?.lottie_guide) {
        // 弹窗
        delete toolbar.lottie_guide;
      }
      if (toolbar?.servicePopup?.subData) {
        // 服务悬浮窗口
        delete toolbar.servicePopup.subData;
      }
    }
    // 头部信息
    if (obj?.header?.data) {
      let head = obj.header.data.userInfo;
      // 头像挂件
      if (head?.avatar_extend_info) {
        delete head.avatar_extend_info;
      }
    }
    // 全套个性皮肤
    if (obj?.profileSkin?.data) {
      delete obj.profileSkin.data;
    }
  } else if (url.includes("/2/push/active")) {
    // 首页右上角红包图标
    if (obj?.feed_redpacket) {
      obj.feed_redpacket.starttime = "2208960000";
      obj.feed_redpacket.interval = "31536000";
      obj.feed_redpacket.endtime = "2209046399";
    }
  } else if (url.includes("/2/search/")) {
    // 搜索页信息流
    if (url.includes("container_timeline")) {
      // loon-change: Weibo search timeline nested reference cache v1
      const searchItems = obj?.items;
      const searchItemsLength = searchItems?.length || 0;
      if (searchItemsLength > 0) {
        const __loonSource12 = searchItems;
        let __loonWrite12 = 0;
        const __loonLength12 = searchItemsLength;
        for (let __loonRead12 = 0; __loonRead12 < __loonLength12; __loonRead12++) {
          let item = __loonSource12[__loonRead12];
          if (item?.category === "feed") {
            const itemData = item?.data;
            if (!isAd(itemData)) {
              // 信息流推广
              removeFeedAd(itemData);
              __loonSource12[__loonWrite12++] = item;
            }
          } else if (item?.category === "card") {
            // 19热议等tab 118横版广告图片 206,249横版视频广告 208实况热聊 217错过了热词 236微博趋势 261奥运滚动横幅
            const cardData = item?.data;
            const cardType = cardData?.card_type;
            if ((cardType === 19 || cardType === 118 || cardType === 206 || cardType === 208 || cardType === 217 || cardType === 236 || cardType === 249 || cardType === 261)) {
              continue;
            } else if (cardType === 101 && cardData?.cate_id === "1114") {
              // 微博趋势标题
              continue;
            } else if (cardType === 196 && cardData?.hasOwnProperty("rank")) {
              // 奥运等排行榜
              continue;
            } else {
              __loonSource12[__loonWrite12++] = item;
            }
          } else if (item?.category === "cell") {
            // 保留信息流分割线
            __loonSource12[__loonWrite12++] = item;
          } else if (item?.category === "group") {
            const groupItems = item?.items;
            const groupItemsLength = groupItems?.length || 0;
            if (groupItemsLength > 0) {
              const __loonSource11 = groupItems;
              let __loonWrite11 = 0;
              const __loonLength11 = groupItemsLength;
              for (let __loonRead11 = 0; __loonRead11 < __loonLength11; __loonRead11++) {
                let ii = __loonSource11[__loonRead11];
                const innerData = ii?.data;
                const innerCardType = innerData?.card_type;
                // 118横版广告图片 182热议话题 217错过了热词 247横版视频广告
                if ((innerCardType === 118 || innerCardType === 182 || innerCardType === 217 || innerCardType === 247)) {
                  continue;
                } else {
                  __loonSource11[__loonWrite11++] = ii;
                }
              }
              __loonSource11.length = __loonWrite11;
              if (__loonWrite11 !== __loonLength11) modified = true;
            }
            __loonSource12[__loonWrite12++] = item;
          }
        }
        __loonSource12.length = __loonWrite12;
        if (__loonWrite12 !== __loonLength12) modified = true;
      }
      if (obj?.loadedInfo) {
        delete obj?.loadedInfo;
      }
    } else if (url.includes("finder")) {
      let channels = obj.channelInfo.channels;
      if (channels?.length > 0) {
        for (let channel of channels) {
          let payload = channel.payload;
          if (payload) {
            if (payload?.loadedInfo) {
              // 去除搜索框填充词
              if (payload?.loadedInfo?.searchBarContent?.length > 0) {
                payload.loadedInfo.searchBarContent = [];
              }
              // 去除搜索背景图片
              if (payload?.loadedInfo?.headerBack?.channelStyleMap) {
                delete payload.loadedInfo.headerBack.channelStyleMap;
              }
              // 搜索框样式
              if (payload?.loadedInfo?.searchBarStyleInfo) {
                delete payload.loadedInfo.searchBarStyleInfo;
              }
            }
            if (payload?.items?.length > 0) {
              const __loonSource10 = payload.items;
              let __loonWrite10 = 0;
              const __loonLength10 = __loonSource10.length;
              for (let __loonRead10 = 0; __loonRead10 < __loonLength10; __loonRead10++) {
                let item = __loonSource10[__loonRead10];
                if (item?.category === "feed") {
                  if (!isAd(item?.data)) {
                    // 信息流推广
                    removeFeedAd(item.data);
                    __loonSource10[__loonWrite10++] = item;
                  }
                } else if (item?.category === "card") {
                  // 19热议等tab 118横版广告图片 206,249横版视频广告 208实况热聊 217错过了热词 236微博趋势 261奥运滚动横幅
                  if ((item?.data?.card_type === 19 || item?.data?.card_type === 118 || item?.data?.card_type === 206 || item?.data?.card_type === 208 || item?.data?.card_type === 217 || item?.data?.card_type === 236 || item?.data?.card_type === 249 || item?.data?.card_type === 261)) {
                    continue;
                  } else if (item?.data?.card_type === 101 && item?.data?.cate_id === "1114") {
                    // 微博趋势标题
                    continue;
                  } else if (item?.data?.card_type === 196 && item?.data?.hasOwnProperty("rank")) {
                    // 奥运等排行榜
                    continue;
                  } else {
                    __loonSource10[__loonWrite10++] = item;
                  }
                } else if (item?.category === "cell") {
                  // 保留信息流分割线
                  __loonSource10[__loonWrite10++] = item;
                } else if (item?.category === "group") {
                  if (item?.items?.length > 0) {
                    const __loonSource9 = item.items;
                    let __loonWrite9 = 0;
                    const __loonLength9 = __loonSource9.length;
                    for (let __loonRead9 = 0; __loonRead9 < __loonLength9; __loonRead9++) {
                      let ii = __loonSource9[__loonRead9];
                      // 118横版广告图片 182热议话题 192横版好看视频 217错过了热词 247横版视频广告
                      if ((ii?.data?.card_type === 118 || ii?.data?.card_type === 182 || ii?.data?.card_type === 192 || ii?.data?.card_type === 217 || ii?.data?.card_type === 247)) {
                        continue;
                      } else {
                        __loonSource9[__loonWrite9++] = ii;
                      }
                    }
                    __loonSource9.length = __loonWrite9;
                    if (__loonWrite9 !== __loonLength9) modified = true;
                  }
                  __loonSource10[__loonWrite10++] = item;
                }
              }
              __loonSource10.length = __loonWrite10;
              if (__loonWrite10 !== __loonLength10) modified = true;
            }
          }
        }
      }
    }
  } else if (url.includes("/2/searchall")) {
    if (obj?.header?.data) {
      // 商品推广头部淘宝跳转
      const items = ["bg_img", "background_scheme", "background_url"];
      for (let i of items) {
        delete obj.header.data[i];
      }
    }
    if (obj?.loadedInfo?.serviceMap?.layer?.pic) {
      // 搜索结果 悬浮窗
      delete obj.loadedInfo.serviceMap.layer;
    }
    if (obj?.footer) {
      if (obj?.footer?.data?.bg_lottie) {
        // 讨论区动画
        delete obj.footer.data.bg_lottie;
        delete obj.footer.data.bg_lottie_dark;
      }
      if (obj?.footer?.data?.discuss_avatars?.length > 0) {
        // 进入讨论区气泡动画头像
        delete obj.footer.data.discuss_avatars;
      }
      if (obj?.footer?.data?.menus?.length > 0) {
        // 底部菜单
        compactInPlace(obj.footer.data.menus, i => !/\d+_ai\./.test(i?.pic));
      }
    }
    if (obj?.cards?.length > 0) {
      const __loonSource8 = obj.cards;
      let __loonWrite8 = 0;
      const __loonLength8 = __loonSource8.length;
      for (let __loonRead8 = 0; __loonRead8 < __loonLength8; __loonRead8++) {
        let card = __loonSource8[__loonRead8];
        if (card?.card_group?.length > 0) {
          const __loonSource7 = card.card_group;
          let __loonWrite7 = 0;
          const __loonLength7 = __loonSource7.length;
          for (let __loonRead7 = 0; __loonRead7 < __loonLength7; __loonRead7++) {
            let group = __loonSource7[__loonRead7];
            if (group?.card_type === 22) {
              // 先筛选card_group里面的card_type
              // 横版广告图
              continue;
            } else if (group?.card_type === 42 && group?.title_extra_text === "广告") {
              // 推荐品牌广告
              continue;
            } else if (group?.card_type === 3 && group?.pics?.length > 0) {
              // 推荐品牌广告图
              continue;
            } else {
              if (group?.mblog) {
                // 有mblog字段的过滤广告
                if (!isAd(group?.mblog)) {
                  // 头像挂件,关注按钮
                  removeAvatar(group?.mblog);
                  if (group?.mblog?.title_source) {
                    delete group.mblog.title_source;
                  }
                  if (group?.mblog?.source_tag_struct) {
                    delete group.mblog.source_tag_struct;
                  }
                  if (group?.mblog?.extend_info) {
                    delete group.mblog.extend_info;
                  }
                  // 商品橱窗
                  if (group?.mblog?.common_struct) {
                    delete group.mblog.common_struct;
                  }
                  // 投票窗口
                  removeVoteInfo(group?.mblog);
                  // 新版热推
                  if (group?.mblog?.is_ad === 1) {
                    continue;
                  }
                  __loonSource7[__loonWrite7++] = group;
                }
              } else {
                // 没有mblog字段的全部推送
                __loonSource7[__loonWrite7++] = group;
              }
            }
          }
          __loonSource7.length = __loonWrite7;
          if (__loonWrite7 !== __loonLength7) modified = true;
          __loonSource8[__loonWrite8++] = card;
        } else {
          if (card?.mblog) {
            if (!isAd(card?.mblog)) {
              // 头像挂件,关注按钮
              removeAvatar(card?.mblog);
              if (card?.mblog?.title_source) {
                delete card.mblog.title_source;
              }
              if (card?.mblog?.source_tag_struct) {
                delete card.mblog.source_tag_struct;
              }
              if (card?.mblog?.extend_info) {
                delete card.mblog.extend_info;
              }
              // 商品橱窗
              if (card?.mblog?.common_struct) {
                delete card.mblog.common_struct;
              }
              // 投票窗口
              removeVoteInfo(card?.mblog);
              // 隐藏在 cards 里面的投票窗口
              if (card?.mblog?.page_info?.cards?.length > 0) {
                let page = card.mblog.page_info;
                for (let i of page.cards) {
                  if (i?.media_info?.vote_info) {
                    delete i.media_info.vote_info;
                  }
                }
              }
              __loonSource8[__loonWrite8++] = card;
            }
          }
        }
      }
      __loonSource8.length = __loonWrite8;
      if (__loonWrite8 !== __loonLength8) modified = true;
    }
    // 13.11.1版本obj下的cards变为了items 2023-11-26
    if (obj?.items?.length > 0) {
      const __loonSource6 = obj.items;
      let __loonWrite6 = 0;
      const __loonLength6 = __loonSource6.length;
      for (let __loonRead6 = 0; __loonRead6 < __loonLength6; __loonRead6++) {
        let item = __loonSource6[__loonRead6];
        if (!isAd(item?.data)) {
          if (item?.category === "feed") {
            // 信息流推广
            removeFeedAd(item?.data);
            // 投票窗口
            removeVoteInfo(item?.data);
            __loonSource6[__loonWrite6++] = item;
          } else if (item?.category === "group") {
            if (item?.items?.length > 0) {
              const __loonSource5 = item.items;
              let __loonWrite5 = 0;
              const __loonLength5 = __loonSource5.length;
              for (let __loonRead5 = 0; __loonRead5 < __loonLength5; __loonRead5++) {
                let ii = __loonSource5[__loonRead5];
                if (!isAd(ii?.data)) {
                  if (ii?.data) {
                    removeAvatar(ii?.data);
                    // 3推广卡片 17相关搜索 22广告图 30推荐博主 42,236智搜问答 89商品推广视频 206推广视频
                    if ((ii?.data?.card_type === 3 || ii?.data?.card_type === 17 || ii?.data?.card_type === 22 || ii?.data?.card_type === 30 || ii?.data?.card_type === 42 || ii?.data?.card_type === 89 || ii?.data?.card_type === 206 || ii?.data?.card_type === 236)) {
                      continue;
                    }
                    // 商品推广desc
                    if (ii?.data?.card_type === 42 && ii?.data?.is_ads === true) {
                      continue;
                    }
                    // 商品橱窗
                    removeFeedAd(ii?.data);
                  }
                  __loonSource5[__loonWrite5++] = ii;
                }
              }
              __loonSource5.length = __loonWrite5;
              if (__loonWrite5 !== __loonLength5) modified = true;
            }
            __loonSource6[__loonWrite6++] = item;
          } else {
            __loonSource6[__loonWrite6++] = item;
          }
        }
      }
      __loonSource6.length = __loonWrite6;
      if (__loonWrite6 !== __loonLength6) modified = true;
    }
  } else if (url.includes("/2/statuses/container_timeline_hot") || url.includes("/2/statuses/unread_hot_timeline")) {
    // loon-change: Weibo hot timeline nested reference cache v1
    // 首页推荐tab信息流
    for (let s of ["ad", "advertises", "trends", "headers"]) {
      if (obj?.[s]) {
        delete obj[s];
      }
    }
    const hotItems = obj?.items;
    const hotItemsLength = hotItems?.length || 0;
    if (hotItemsLength > 0) {
      const __loonSource4 = hotItems;
      let __loonWrite4 = 0;
      const __loonLength4 = hotItemsLength;
      for (let __loonRead4 = 0; __loonRead4 < __loonLength4; __loonRead4++) {
        let item = __loonSource4[__loonRead4];
        const itemData = item?.data;
        if (!isAd(itemData)) {
          if (item?.category === "feed") {
            // 信息流推广
            removeFeedAd(itemData);
            // 投票窗口
            removeVoteInfo(itemData);
            __loonSource4[__loonWrite4++] = item;
          } else {
            // 移除其他推广
            continue;
          }
        }
      }
      __loonSource4.length = __loonWrite4;
      if (__loonWrite4 !== __loonLength4) modified = true;
    }
    const hotStatuses = obj?.statuses;
    const hotStatusesLength = hotStatuses?.length || 0;
    if (hotStatusesLength > 0) {
      const __loonSource3 = hotStatuses;
      let __loonWrite3 = 0;
      const __loonLength3 = hotStatusesLength;
      for (let __loonRead3 = 0; __loonRead3 < __loonLength3; __loonRead3++) {
        let item = __loonSource3[__loonRead3];
        if (!isAd(item)) {
          // 信息流推广
          removeFeedAd(item);
          __loonSource3[__loonWrite3++] = item;
        }
      }
      __loonSource3.length = __loonWrite3;
      if (__loonWrite3 !== __loonLength3) modified = true;
    }
  } else if (url.includes("/2/statuses/container_timeline?") || url.includes("/2/statuses/container_timeline_unread")) {
    // loon-change: Weibo following timeline nested reference cache v1
    // 首页关注tab信息流
    if (obj?.loadedInfo?.headers) {
      delete obj.loadedInfo.headers;
    }
    // 商品橱窗
    if (obj?.common_struct) {
      delete obj?.common_struct;
    }
    const timelineItems = obj?.items;
    const timelineItemsLength = timelineItems?.length || 0;
    if (timelineItemsLength > 0) {
      const __loonSource2 = timelineItems;
      let __loonWrite2 = 0;
      const __loonLength2 = timelineItemsLength;
      for (let __loonRead2 = 0; __loonRead2 < __loonLength2; __loonRead2++) {
        let item = __loonSource2[__loonRead2];
        const itemData = item?.data;
        if (!isAd(itemData)) {
          if (item?.category === "feed") {
            // 信息流推广
            removeFeedAd(itemData);
            const itemTitle = itemData?.title;
            if (itemTitle?.structs) {
              // 移除 未关注人消息 (你关注的博主，他自己关注的别的博主的微博消息)
              continue;
            }
            if (itemData?.action_button_icon_dic) {
              delete itemData.action_button_icon_dic;
            }
            // 投票窗口
            removeVoteInfo(itemData);
            // 快转内容
            const screenNameSuffixNew = itemData?.screen_name_suffix_new;
            if (screenNameSuffixNew?.length > 0) {
              if (screenNameSuffixNew[3]?.content === "快转了") {
                continue;
              }
            }
            // 美妆精选季
            if (itemTitle?.text?.includes("精选")) {
              continue;
            }
            // 未关注博主
            const itemUser = itemData?.user;
            if (itemUser?.following === false) {
              continue;
            }
            // 关闭关注推荐
            if (itemUser?.unfollowing_recom_switch === 1) {
              itemUser.unfollowing_recom_switch = 0;
            }
            // 博主top100
            const tagStruct = itemData?.tag_struct;
            if (tagStruct?.length > 0) {
              itemData.tag_struct = [];
            }
            __loonSource2[__loonWrite2++] = item;
          } else if (item?.category === "feedBiz") {
            // 管理特别关注按钮
            __loonSource2[__loonWrite2++] = item;
          } else {
            // 移除其他推广
            continue;
          }
        }
      }
      __loonSource2.length = __loonWrite2;
      if (__loonWrite2 !== __loonLength2) modified = true;
    }
  } else if (url.includes("/2/statuses/container_timeline_topic")) {
    // 超话信息流
    if (obj?.header?.data?.follow_guide_info) {
      // 底部弹出的关注按钮
      delete obj.header.data.follow_guide_info;
    }
    if (obj?.items?.length > 0) {
      const __loonSource1 = obj.items;
      let __loonWrite1 = 0;
      const __loonLength1 = __loonSource1.length;
      for (let __loonRead1 = 0; __loonRead1 < __loonLength1; __loonRead1++) {
        let item = __loonSource1[__loonRead1];
        if (item?.category === "feed") {
          if (item.data) {
            // 头像挂件,关注按钮
            removeAvatar(item?.data);
            if (!isAd(item?.data)) {
              if (item?.data?.title?.text?.includes("新人导师")) {
                // 萌新帖 互动赢新人导师
                delete item.data.title;
              }
              __loonSource1[__loonWrite1++] = item;
            }
          }
        } else if (item?.category === "card") {
          if (!(item?.data?.card_type === 4 || item?.data?.card_type === 197 || item?.data?.card_type === 1012)) {
            // 4 你可能感兴趣的超话
            // 197 你可能感兴趣的超话
            // 1012 热门超话
            __loonSource1[__loonWrite1++] = item;
          }
        } else if (item?.category === "group") {
          // loon-change: Weibo topic-group nested array reference cache v1
          const nestedItems = item?.items;
          if (nestedItems?.length > 0) {
            if (item?.itemId === null) {
              // 超话页顶部乱七八糟
              // loon-change: Weibo topic-group in-place item compaction v1;
              const groupItems = nestedItems;
              const groupLength = groupItems.length;
              let groupWrite = 0;
              for (let groupRead = 0; groupRead < groupLength; groupRead++) {
                const ii = groupItems[groupRead];
                const itemData = ii?.data;
                const itemId = itemData?.itemid;
                let keep = false;
                if (itemData?.hasOwnProperty("itemid")) {
                  if (itemId?.includes("mine_topics")) {
                    // 保留我的超话
                    keep = true;
                  } else if (itemId?.includes("tab_search_input")) {
                    // 保留搜索框
                    if (itemData?.hotwords) {
                      // 删除热搜词
                      itemData.hotwords = [{word: "搜索超话"}];
                    }
                    keep = true;
                  } else if (itemId?.includes("poiRankList")) {
                    // 保留地点超话 地标人气榜
                    keep = true;
                  }
                } else {
                  // 放行无itemid字段的内容
                  keep = true;
                }
                if (keep) groupItems[groupWrite++] = ii;
                // 头像挂件,关注按钮
                removeAvatar(itemData);
              }
              groupItems.length = groupWrite;
            } else {
              // loon-change: Weibo topic-group nested data reference cache v1
              const nestedLength = nestedItems.length;
              for (let nestedIndex = 0; nestedIndex < nestedLength; nestedIndex++) {
                const ii = nestedItems[nestedIndex];
                const iiData = ii?.data;
                if (iiData) {
                  removeAvatar(iiData);
                  const commonStruct = iiData.common_struct;
                  if (commonStruct) {
                    delete iiData.common_struct;
                  }
                }
              }
            }
          }
          if (item?.style?.topHover) {
            // 空降发帖背景图
            delete item.style.topHover;
          }
          if (item?.header?.arrayText?.contents?.length > 0) {
            // 你的好友也关注了
            continue;
          }
          __loonSource1[__loonWrite1++] = item;
        } else {
          // 移除其他推广
          continue;
        }
      }
      __loonSource1.length = __loonWrite1;
      if (__loonWrite1 !== __loonLength1) modified = true;
    }
  } else if (url.includes("/2/statuses/extend")) {
    // 微博详情页
    if (obj?.trend?.extra_struct?.extBtnInfo?.btn_picurl?.includes("ad")) {
      delete obj.trend;
    }
    if (obj.trend?.titles) {
      let title = obj.trend.titles.title;
      if (/(博主好物种草|相关推荐|专区)/?.test(title)) {
        delete obj.trend;
      }
    }
    const item = [
      "bubble_guide_data", // 评论区弹窗
      "button_extra_info", // 推荐评论
      "display_info", // 二楼
      "extend_info", // 拓展卡片
      "floating_button", // 悬浮购物车按钮
      "follow_data", // 关注提醒
      "head_cards", // 超话投票
      "highlight", // 二楼
      "interaction_extra_info", // ai评论
      "page_alerts", // 超话新帖 新用户通知
      "reward_info", // 公益赞赏
      "source_tag_struct" // 二楼
    ];
    if (obj) {
      item.forEach((i) => {
        delete obj[i];
      });
    }
    if (obj?.custom_action_list?.length > 0) {
      let newActions = [];
      for (let item of obj.custom_action_list) {
        let type = item.type;
        let add = itemMenusConfig[type];
        if (type === "mblog_menus_copy_url") {
          newActions.unshift(item);
        } else if (add) {
          newActions.push(item);
        }
      }
      obj.custom_action_list = newActions;
    }
    // 商品橱窗
    if (obj?.has_common_struct) {
      obj.has_common_struct = false;
    }
    // 评论指引
    if (obj?.enable_comment_guide) {
      obj.enable_comment_guide = false;
    }
  } else if (url.includes("/2/statuses/show")) {
    // 信息流推广
    removeFeedAd(obj);
    // 循环引用中的商品橱窗
    if (obj?.text) {
      // 信息流推广
      removeFeedAd(obj.text);
    }
    // 赞赏信息
    if (obj?.reward_info) {
      delete obj.reward_info;
    }
    // 投票窗口
    removeVoteInfo(obj);
  } else if (url.includes("/2/video/tiny_stream_video_list")) {
    if (obj?.statuses?.length > 0) {
      // 移除视频自动连播
      obj.statuses = [];
      // obj.statuses = obj.statuses.filter((m) => !(m.mblogtypename === "广告"));
    }
    if (obj?.tab_list?.length > 0) {
      obj.tab_list = [];
    }
  } else if (url.includes("/2/!/huati/discovery_home_bottom_channels")) {
    // 超话左上角,右上角图标
    if (obj?.button_configs) {
      delete obj.button_configs;
    }
    // 广场页
    if (obj?.channelInfo?.channel_list?.length > 0) {
      compactInPlace(obj.channelInfo.channel_list, t => t.title !== "广场");
    }
  } else if (url.includes("/aj/appicon/list")) {
    if (obj?.data?.list?.length > 0) {
      for (let item of obj.data.list) {
        if (item?.cardType) {
          item.cardType = 2;
        }
      }
    }
  } else if (url.includes("/v1/ad/preload") || url.includes("/v2/ad/preload")) {
    // 开屏广告
    if (obj?.ads?.length > 0) {
      for (let item of obj.ads) {
        item.start_time = 3818332800; // Unix 时间戳 2090-12-31 00:00:00
        item.end_time = 3818419199; // Unix 时间戳 2090-12-31 23:59:59
        item.daily_display_cnt = 50; // total_display_cnt: 50
        item.display_duration = 0;
      }
      if (obj?.ads?.creatives?.length > 0) {
        for (let item of obj.ads.creatives) {
          item.start_time = 3818332800; // Unix 时间戳 2090-12-31 00:00:00
          item.end_time = 3818419199; // Unix 时间戳 2090-12-31 23:59:59
          item.daily_display_cnt = 50; // total_display_cnt: 50
          item.display_duration = 0;
        }
      }
    }
  } else if (url.includes("/wbapplua/wbpullad.lua") || url.includes("/preload/get_ad")) {
    // 开屏广告
    if (obj?.cached_ad?.ads?.length > 0) {
      for (let item of obj.cached_ad.ads) {
        item.show_count = 50;
        item.duration = 0; // 60 * 60 * 24 * 365 = 31536000
        item.start_date = 3818332800; // Unix 时间戳 2090-12-31 00:00:00
        item.end_date = 3818419199; // Unix 时间戳 2090-12-31 23:59:59
      }
    }
  }
  $done(modified ? {body: JSON.stringify(obj)} : {});
}

// 判断信息流
function isAd(data) {
  // loon-change: Weibo shared ad predicate single-read cache v1
  const mblogTypeName = data?.mblogtypename;
  if (mblogTypeName?.includes("广告")) {
    return true;
  }
  if (mblogTypeName?.includes("热推")) {
    return true;
  }
  const promotion = data?.promotion;
  const promotionType = promotion?.type;
  if (promotionType?.includes("ad")) {
    return true;
  }
  const contentAuthInfo = data?.content_auth_info;
  const contentAuthTitle = contentAuthInfo?.content_auth_title;
  if (contentAuthTitle?.includes("广告")) {
    return true;
  }
  const adsMaterialInfo = data?.ads_material_info;
  const isAds = adsMaterialInfo?.is_ads;
  if (isAds === true) {
    return true;
  }
  return false;
}

// 移除头像挂件,关注按钮
function removeAvatar(data, user = data?.user) {
  // loon-change: Weibo removeAvatar cached user reference v1
  // loon-change: Weibo removeAvatar single-read property cache v1
  const blockCardBg = data?.block_card_bg;
  if (blockCardBg) {
    modified = true;
    delete data.block_card_bg;
  }
  const buttons = data?.buttons;
  if (buttons) {
    modified = true;
    delete data.buttons;
  }
  const cardId = data?.cardid;
  if (cardId) {
    modified = true;
    delete data.cardid;
  }
  const icons = data?.icons;
  if (icons) {
    modified = true;
    delete data.icons;
  }
  const mblogButtons = data?.mblog_buttons;
  if (mblogButtons) {
    // 转发按钮图标
    modified = true;
    delete data.mblog_buttons;
  }
  const picBgNew = data?.pic_bg_new;
  if (picBgNew) {
    modified = true;
    delete data.pic_bg_new;
  }
  const avatarGjId = user?.avatargj_id;
  if (avatarGjId) {
    modified = true;
    delete user.avatargj_id;
  }
  const avatarExtendInfo = user?.avatar_extend_info;
  if (avatarExtendInfo) {
    modified = true;
    delete user.avatar_extend_info;
  }
  const userCardId = user?.cardid;
  if (userCardId) {
    modified = true;
    delete user.cardid;
  }
  const userIcons = user?.icons;
  if (userIcons) {
    modified = true;
    delete user.icons;
  }
  const memberType = user?.mbtype;
  if (memberType) {
    // 会员等级图标
    modified = true;
    delete user.mbtype;
  }
}

// 移除信息流关注按钮,推广,热评
function removeFeedAd(item) {
  // 头像挂件,关注按钮
  removeAvatar(item);
  if (item?.retweeted_status) {
    removeAvatar(item?.retweeted_status);
  }
  // 商品橱窗
  if (item?.common_struct) {
    delete item.common_struct;
  }
  // 移除信息流中的热评
  if (item?.comment_summary) {
    delete item.comment_summary;
  }
  // 商品橱窗
  if (item?.semantic_brand_params) {
    delete item.semantic_brand_params;
  }
}

// 移除投票窗口
function removeVoteInfo(item) {
  if (item?.page_info?.media_info?.vote_info) {
    modified = true;
    delete item.page_info.media_info.vote_info;
  }
}
