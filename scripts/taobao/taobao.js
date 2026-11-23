/********************************
Taobao Remove Ads - Version 1.0
Please note that you may need to reinstall app for script to work.

QuantumultX rewrite link:
https://raw.githubusercontent.com/zirawell/R-Store/main/Rule/QuanX/Adblock/App/T/淘宝/rewrite/taobao.conf

Surge module link:
https://raw.githubusercontent.com/zirawell/R-Store/main/Rule/Surge/Adblock/App/T/淘宝/taobao.sgmodule
********************************/

if (!$response.body) {
  $done({});
} else {
  const url = $request.url;
  let modified = false;

  function setIfDifferent(target, key, value) {
    if (target[key] !== value) {
      target[key] = value;
      modified = true;
    }
  }

  function clearArray(target, key) {
    if (Array.isArray(target[key]) && target[key].length > 0) {
      target[key] = [];
      modified = true;
    }
  }
  // loon-change: Taobao pre-parse supported-route guard v1
  const shouldProcess =
    url.includes("guide-acs.m.taobao.com/gw/mtop/mtop.taobao.cloudvideo.video.query") ||
    url.includes("guide-acs.m.taobao.com/gw/mtop/mtop.taobao.wireless.home.splash.awesome.get") ||
    url.includes("poplayer.template.alibaba.com/");
  if (!shouldProcess) {
    $done({});
  } else {
  const obj = JSON.parse($response.body);
if (url.includes("mtop.taobao.cloudvideo.video.query")) {
  if (obj?.data?.duration) {
    setIfDifferent(obj.data, "duration", "0");
  }
  clearArray(obj?.data || {}, "resources");
  clearArray(obj?.data || {}, "caches");
  if (obj?.data?.respTimeInMs) {
    setIfDifferent(obj.data, "respTimeInMs", "3818332800000");
  }
} else if (url.includes("mtop.taobao.wireless.home.splash.awesome.get")) {
  if (obj?.data?.containers?.splash_home_base) {
    let splash = obj.data.containers.splash_home_base;
    if (splash?.base?.sections?.length > 0) {
      for (let items of splash.base.sections) {
        if ("taobao-splash" in items.bizData) {
          if (items?.bizData?.["taobao-splash"]?.data?.length > 0) {
            for (let item of items.bizData["taobao-splash"].data) {
              setIfDifferent(item, "waitTime", "0");
              setIfDifferent(item, "times", "0");
              setIfDifferent(item, "hotStart", "false");
              setIfDifferent(item, "haveVoice", "false");
              setIfDifferent(item, "hideTBLogo", "false");
              setIfDifferent(item, "enable4G", "false");
              setIfDifferent(item, "coldStart", "false");
              setIfDifferent(item, "startTime", "3818332800000");
              setIfDifferent(item, "endTime", "3818419199000");
              setIfDifferent(item, "gmtStart", "2090-12-31 00:00:00");
              setIfDifferent(item, "gmtEnd", "2090-12-31 23:59:59");
              setIfDifferent(item, "gmtStartMs", "3818332800000");
              setIfDifferent(item, "gmtEndMs", "3818419199000");
              if (item?.imgUrl) setIfDifferent(item, "imgUrl", "");
              if (item?.videoUrl) setIfDifferent(item, "videoUrl", "");
            }
          }
        }
      }
    }
  }
} else if (url.includes("poplayer.template.alibaba.com")) {
  clearArray(obj?.res || {}, "images");
  clearArray(obj?.res || {}, "videos");
  if (obj?.enable) {
    setIfDifferent(obj, "enable", false);
  }
  clearArray(obj?.mainRes || {}, "images");
}
$done(modified ? {body: JSON.stringify(obj)} : {});
  }
}
