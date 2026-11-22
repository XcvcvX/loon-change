// loon-change: RRTV lightweight runtime and response fast paths v1; upstream zirawell/R-Store@a4f3b10d6038d77ae3e1ff68bd19a49071ebabd3
/********************************
RRTV Remove Ads - Version 1.0
Checkout Source - https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/rrtv_json.js
Please note that you may need to reinstall app for script to work.

QuantumultX rewrite link:
https://raw.githubusercontent.com/zirawell/R-Store/main/Rule/QuanX/Adblock/App/R/人人视频/rewrite/rrtv.conf

Surge module link:
https://raw.githubusercontent.com/zirawell/R-Store/main/Rule/Surge/Adblock/App/R/人人视频/rrtv.sgmodule
********************************/

function createLoonRuntime(name) {
  return {
    isResponse: typeof $response !== "undefined" && $response !== null,
    request: typeof $request !== "undefined" ? $request : {},
    response: typeof $response !== "undefined" ? $response : {},
    logError(error) {
      console.log("[" + name + "] " + error);
    },
    logWarning(message) {
      console.log("[" + name + "] " + message);
    },
    done(value) {
      if (arguments.length === 0) $done();
      else $done(value);
    }
  };
}

function compactInPlace(items, keep) {
  let write = 0;
  const length = items.length;
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

const playbackFlags = /currentQuality":"\w+|canPlay":false|canShowVip":true|externalAds":true/g;
function rewritePlaybackFlags(body) {
  const rewritten = body.replace(playbackFlags, match => {
    if (match.startsWith('currentQuality":"')) return 'currentQuality":"AI_OD';
    if (match === 'canPlay":false') return 'canPlay":true';
    if (match === 'canShowVip":true') return 'canShowVip":false';
    return 'externalAds":false';
  });
  return rewritten === body ? null : rewritten;
}
const scriptName = "RRTV";
if (!$response || !$response.body) {
  $done({});
} else {
const magicJS = createLoonRuntime(scriptName);
const rrtv_tab_home = /.*\/v3plus\/index\/channel\?pageNum=1&position=CHANNEL_INDEX/;
const rrtv_tab_my = /.*\/v3plus\/index\/channel\?pageNum=1&position=CHANNEL_MY/;
const rrtv_tab_cfg = /.*\/app\/config\/h5NativeBar/;
const rrtv_drama_detail = /.*\/drama\/detail\?/;
const rrtv_user_info = /.*\/user\/personal/;
const rrtv_level = /.*\/level\/info/;
const rrtv_ad_getall = /.*\/ad\/getAll/;
const rrtv_watch_v4 = /.*\/watch\/v4/;

(() => {
  let body = null;
  if (magicJS.isResponse) {
    switch (true) {
        //首页去广告
      case rrtv_tab_home.test(magicJS.request.url):
        try {
          let obj = JSON.parse(magicJS.response.body);
          //delete obj.data.bannerTop;
          const sectionsChanged = compactInPlace(obj.data.sections, section =>
            section.sectionType !== "AD" &&
            section.sectionType !== "SINGLE_IMAGE" &&
            section.sectionType !== "SHORT_VIDEO"
          );
          if (sectionsChanged) body = JSON.stringify(obj);
        } catch (err) {
          magicJS.logError(`首页去广告出现异常：${err}`);
        }
        break;
        //去除广场
      case rrtv_tab_cfg.test(magicJS.request.url):
        try {
          let obj = JSON.parse(magicJS.response.body);
          obj['data']['homeBarPage'] = [{
            "darkSelPag": "http://img.rr.tv/barSelpag/20210310/o_1615343956536.pag",
            "selPag": "http://img.rr.tv/barSelpag/20210310/o_1615343961034.pag",
            "pageType": 0,
            "darkUnselImg": "http://img.rr.tv/cover/20210310/o_1615343982560.png",
            "webUrl": "",
            "selImg": "http://img.rr.tv/cover/20210310/o_1615343977931.png",
            "unselImg": "http://img.rr.tv/cover/20210310/o_1615343979417.png",
            "name": "首页",
            "index": 1,
            "nativeAlias": "home",
            "darkSelImg": "http://img.rr.tv/cover/20210310/o_1615343985261.png"
          }, {
            "darkSelPag": "http://img.rr.tv/barSelpag/20210310/o_1615344101664.pag",
            "selPag": "http://img.rr.tv/barSelpag/20210310/o_1615344101761.pag",
            "pageType": 0,
            "darkUnselImg": "http://img.rr.tv/cover/20210310/o_1615344088886.png",
            "webUrl": "",
            "selImg": "http://img.rr.tv/cover/20210310/o_1615344085709.png",
            "unselImg": "http://img.rr.tv/cover/20210310/o_1615344087390.png",
            "name": "快看",
            "index": 2,
            "nativeAlias": "amwayVideo",
            "darkSelImg": "http://img.rr.tv/cover/20210310/o_1615344091229.png"
          }, {
            "darkSelPag": "http://img.rr.tv/barSelpag/20210310/o_1615344145409.pag",
            "selPag": "http://img.rr.tv/barSelpag/20210310/o_1615344143099.pag",
            "pageType": 0,
            "darkUnselImg": "http://img.rr.tv/img/img/20211013/o_ca5e3b6ce6b747e992789e55222445f2.png",
            "webUrl": "",
            "selImg": "http://img.rr.tv/img/img/20211013/o_14667f24618841a1906fbb2233b8869a.png",
            "unselImg": "http://img.rr.tv/img/img/20211013/o_963933dfc49b4c8bab6e3b36a8a2b42b.png",
            "name": "VIP",
            "index": 3,
            "nativeAlias": "vip",
            "darkSelImg": "http://img.rr.tv/img/img/20211013/o_ad54fb0336764d38910304488804f2a1.png"
          }, {
            "darkSelPag": "http://img.rr.tv/barSelpag/20210310/o_1615344154522.pag",
            "selPag": "http://img.rr.tv/barSelpag/20210310/o_1615344153652.pag",
            "pageType": 0,
            "darkUnselImg": "http://img.rr.tv/img/img/20211013/o_e35b6941e4a0429486cd5b535337544f.png",
            "webUrl": "",
            "selImg": "http://img.rr.tv/img/img/20211013/o_2e5efef7fd654e3ea8a60e3e719e6e8c.png",
            "unselImg": "http://img.rr.tv/img/img/20211013/o_7492019b1603486383733b7154e967b3.png",
            "name": "我的",
            "index": 4,
            "nativeAlias": "my",
            "darkSelImg": "http://img.rr.tv/img/img/20211013/o_f98a74489e3d4dc9bf8651eea65b949e.png"
          }];
          body = JSON.stringify(obj);
        } catch (err) {
          magicJS.logError(`广场去广告出现异常：${err}`);
        }
        break;
        //去除商城广告
      case rrtv_tab_my.test(magicJS.request.url):
        try {
          let obj = JSON.parse(magicJS.response.body);
          obj['data']['sections'] = [{
            "id": 2541,
            "sectionType": "MAGIC_CUBE",
            "displayTitle": "1",
            "startTime": null,
            "position": 23,
            "display": "SCROLL",
            "moreText": "",
            "sectionContents": [{
              "feeMode": null,
              "pictureHeight": null,
              "targetId": "rrspjump://webview?url=http%3A%2F%2Fmobile.rr.tv%2FappWeb%2F%23%2FbugList",
              "id": 34,
              "pictureWidth": null,
              "title": "帮助反馈",
              "targetType": "H5",
              "sectionId": 2541,
              "orderNum": 1,
              "subTitle": null,
              "icon": "http://img.rr.tv/cover/20210201/o_1612169512400.png"
            }, {
              "feeMode": null,
              "pictureHeight": null,
              "targetId": "rrspjump://webview?url=http%3A%2F%2Fmobile.rr.tv%2Fmission%2F%23%2Fachievement%2Fcenter",
              "id": 35,
              "pictureWidth": null,
              "title": "成就中心",
              "targetType": "H5",
              "sectionId": 2541,
              "orderNum": 2,
              "subTitle": null,
              "icon": "http://img.rr.tv/cover/20210201/o_1612169790308.png"
            },],
            "endTime": null,
            "targetType": null,
            "sequence": 3,
            "name": "其他",
            "targetId": "rrspjump://empty"
          }];
          body = JSON.stringify(obj);
        } catch (err) {
          magicJS.logError(`商城去广告出现异常：${err}`);
        }
        break;
        //rrtv_ad_getall
      case rrtv_ad_getall.test(magicJS.request.url):
        try {
          let obj = JSON.parse(magicJS.response.body);
          if (obj.data.adList.length !== 0) {
            obj.data.adList = [];
            body = JSON.stringify(obj);
          }
        } catch (err) {
          magicJS.logError(`ad_getall去广告出现异常：${err}`);
        }
        break;
        //rrtv_drama
      case rrtv_drama_detail.test(magicJS.request.url):
        try {
          body = rewritePlaybackFlags(magicJS.response.body);
        } catch (err) {
          magicJS.logError(`drama去广告出现异常：${err}`);
        }
        break;
        //rrtv_watch_4
      case rrtv_watch_v4.test(magicJS.request.url):
        try {
          body = rewritePlaybackFlags(magicJS.response.body);
        } catch (err) {
          magicJS.logError(`watch_4去广告出现异常：${err}`);
        }
        break;
        //rrtv_pro
      case rrtv_user_info.test(magicJS.request.url):
        try {
          let obj = JSON.parse(magicJS.response.body);
          obj.data.user.medalList = [{
            "name": "大魔王",
            "endTime": "2099-02-22 02:44:53",
            "imgUrl": "http://img.rr.tv/cover/20200424/o_1587720799676.png",
            "id": 1
          }];
          obj.data.user.privilegeList = [{
            "id": null,
            "createTimeStr": "",
            "createTime": null,
            "updateTime": null,
            "effectObject": "video",
            "action": "play",
            "function": "originalPainting",
            "func": "originalPainting",
            "description": "解锁原画",
            "icon": "jiesuoyuanhua",
            "endTime": 9999987654321
          }, {
            "id": null,
            "createTimeStr": "",
            "createTime": null,
            "updateTime": null,
            "effectObject": "mall",
            "action": "sale",
            "function": "mallDiscount",
            "func": "mallDiscount",
            "description": "龙醇商城九折",
            "icon": "longchunshangcheng",
            "endTime": 9999987654321
          }, {
            "id": null,
            "createTimeStr": "",
            "createTime": null,
            "updateTime": null,
            "effectObject": "article",
            "action": "write",
            "function": "highLight",
            "func": "highLight",
            "description": "高亮发帖",
            "icon": "gaoliangfatie",
            "endTime": 9999987654321
          }, {
            "id": null,
            "createTimeStr": "",
            "createTime": null,
            "updateTime": null,
            "effectObject": "nickName",
            "action": "show",
            "function": "nameHighLight",
            "func": "nameHighLight",
            "description": "高亮昵称",
            "icon": "gaoliangnicheng",
            "endTime": 9999987654321
          }, {
            "id": null,
            "createTimeStr": "",
            "createTime": null,
            "updateTime": null,
            "effectObject": "comment",
            "action": "write",
            "function": "highLight",
            "func": "highLight",
            "description": "高亮评论回复",
            "icon": "huifu",
            "endTime": 9999987654321
          }, {
            "id": null,
            "createTimeStr": "",
            "createTime": null,
            "updateTime": null,
            "effectObject": "danmu",
            "action": "send",
            "function": "superBarrageBlue",
            "func": "superBarrageBlue",
            "description": "超级弹幕",
            "icon": "chaojidanmu",
            "endTime": 9999987654321
          }, {
            "id": null,
            "createTimeStr": "",
            "createTime": null,
            "updateTime": null,
            "effectObject": "video",
            "action": "play",
            "function": "vipVideo",
            "func": "vipVideo",
            "description": "勋章专享剧集",
            "icon": "zhuanxiangjuji",
            "endTime": 9999987654321
          }, {
            "id": null,
            "createTimeStr": "",
            "createTime": null,
            "updateTime": null,
            "effectObject": "growth",
            "action": "play",
            "function": "0.4",
            "func": "0.4",
            "description": "看剧经验+40%",
            "icon": "jingyanzhijiacheng",
            "endTime": 9999987654321
          }, {
            "id": null,
            "createTimeStr": "",
            "createTime": null,
            "updateTime": null,
            "effectObject": "video",
            "action": "play",
            "function": "noLimit",
            "func": "noLimit",
            "description": "看剧无限制",
            "icon": "kanjuwuxianzhi",
            "endTime": 9999987654321
          }, {
            "id": null,
            "createTimeStr": "",
            "createTime": null,
            "updateTime": null,
            "effectObject": "video",
            "action": "play",
            "function": "noAd",
            "func": "noAd",
            "description": "看剧无广告",
            "icon": "kanjuwuguanggao",
            "endTime": 9999987654321
          }];
          obj.data.user.vipMedal = {
            "name": "大魔王",
            "endTime": "2099-02-22 02:44:53",
            "imgUrl": "http://img.rr.tv/cover/20200424/o_1587720799676.png",
            "id": 1,
            "isExpired": false
          };
          obj.data.user.vipInfo = {"level": "1", "expiredTime": 4000000000000, "valid": true};
          body = JSON.stringify(obj);
        } catch (err) {
          magicJS.logError(`pro去广告出现异常：${err}`);
        }
        break;
      case rrtv_level.test(magicJS.request.url):
        try {
          let obj = JSON.parse(magicJS.response.body);
          obj.data = {
            "level": "1",
            "expiredTime": 4000000000000,
            "valid": true
          };
          body = JSON.stringify(obj);
        } catch (err) {
          magicJS.logError(`rrtv_level出现异常：${err}`);
        }
        break;
      default:
        magicJS.logWarning("触发意外的请求处理，请确认脚本或复写配置正常。");
        break;
    }
  } else {
    magicJS.logWarning("触发意外的请求处理，请确认脚本或复写配置正常。");
  }
  if (body) {
    magicJS.done({body});
  } else {
    magicJS.done();
  }
})();
}
