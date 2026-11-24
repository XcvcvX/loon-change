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
    // loon-change: Taobao clearArray null-target fast path v1
    if (target == null) return;
    // loon-change: Taobao clearArray caches property value once v1
    const current = target[key];
    if (Array.isArray(current) && current.length > 0) {
      target[key] = [];
      modified = true;
    }
  }
  // loon-change: Taobao splash item specialized updates v1
  function normalizeSplashItem(item) {
    if (item.waitTime !== "0") { item.waitTime = "0"; modified = true; }
    if (item.times !== "0") { item.times = "0"; modified = true; }
    if (item.hotStart !== "false") { item.hotStart = "false"; modified = true; }
    if (item.haveVoice !== "false") { item.haveVoice = "false"; modified = true; }
    if (item.hideTBLogo !== "false") { item.hideTBLogo = "false"; modified = true; }
    if (item.enable4G !== "false") { item.enable4G = "false"; modified = true; }
    if (item.coldStart !== "false") { item.coldStart = "false"; modified = true; }
    if (item.startTime !== "3818332800000") { item.startTime = "3818332800000"; modified = true; }
    if (item.endTime !== "3818419199000") { item.endTime = "3818419199000"; modified = true; }
    if (item.gmtStart !== "2090-12-31 00:00:00") { item.gmtStart = "2090-12-31 00:00:00"; modified = true; }
    if (item.gmtEnd !== "2090-12-31 23:59:59") { item.gmtEnd = "2090-12-31 23:59:59"; modified = true; }
    if (item.gmtStartMs !== "3818332800000") { item.gmtStartMs = "3818332800000"; modified = true; }
    if (item.gmtEndMs !== "3818419199000") { item.gmtEndMs = "3818419199000"; modified = true; }
    if (item?.imgUrl) { item.imgUrl = ""; modified = true; }
    if (item?.videoUrl) { item.videoUrl = ""; modified = true; }
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
  clearArray(videoData, "resources");
  clearArray(videoData, "caches");
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
          normalizeSplashItem(item);
        }
      }
    }
  }
} else if (isPoplayer) {
  // loon-change: Taobao cached Poplayer response objects v1
  const poplayerRes = obj?.res;
  const mainRes = obj?.mainRes;
  const poplayerEnabled = obj?.enable;
  clearArray(poplayerRes, "images");
  clearArray(poplayerRes, "videos");
  if (poplayerEnabled) {
    setIfDifferent(obj, "enable", false);
  }
  clearArray(mainRes, "images");
}
$done(modified ? {body: JSON.stringify(obj)} : {});
  }
}
