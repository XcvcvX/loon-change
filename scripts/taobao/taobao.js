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
  // loon-change: Taobao cached route classification v1
  const isCloudVideo = url.includes("guide-acs.m.taobao.com/gw/mtop.taobao.cloudvideo.video.query");
  const isSplash = url.includes("guide-acs.m.taobao.com/gw/mtop.taobao.wireless.home.splash.awesome.get");
  const isPoplayer = url.includes("poplayer.template.alibaba.com/");
  const shouldProcess = isCloudVideo || isSplash || isPoplayer;
  if (!shouldProcess) {
    $done({});
  } else {
  const obj = JSON.parse($response.body);
if (isCloudVideo) {
  // loon-change: Taobao cached video response object v1
  const videoData = obj?.data;
  if (videoData?.duration) {
    setIfDifferent(videoData, "duration", "0");
  }
  clearArray(videoData || {}, "resources");
  clearArray(videoData || {}, "caches");
  if (videoData?.respTimeInMs) {
    setIfDifferent(videoData, "respTimeInMs", "3818332800000");
  }
} else if (isSplash) {
  if (obj?.data?.containers?.splash_home_base) {
    const sections = obj.data.containers.splash_home_base.base?.sections;
    if (Array.isArray(sections) && sections.length > 0) {
      // loon-change: Taobao indexed splash traversal v1
      const sectionCount = sections.length;
      for (let sectionIndex = 0; sectionIndex < sectionCount; sectionIndex++) {
        const bizData = sections[sectionIndex]?.bizData;
        const splashItems = bizData?.["taobao-splash"]?.data;
        if (!Array.isArray(splashItems) || splashItems.length === 0) continue;

        const itemCount = splashItems.length;
        for (let itemIndex = 0; itemIndex < itemCount; itemIndex++) {
          const item = splashItems[itemIndex];
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
} else if (isPoplayer) {
  // loon-change: Taobao cached Poplayer response objects v1
  const poplayerRes = obj?.res;
  const mainRes = obj?.mainRes;
  const poplayerEnabled = obj?.enable;
  clearArray(poplayerRes || {}, "images");
  clearArray(poplayerRes || {}, "videos");
  if (poplayerEnabled) {
    setIfDifferent(obj, "enable", false);
  }
  clearArray(mainRes || {}, "images");
}
$done(modified ? {body: JSON.stringify(obj)} : {});
  }
}
