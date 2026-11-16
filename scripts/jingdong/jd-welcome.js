// FMZ's optional Jingdong welcomeHome cleanup.
// Kept as a separate switch-gated trigger because the R-Store cleaner is
// unconditional and its allowlist is not semantically identical to this filter.
(function () {
  const url = ($request && $request.url) || "";
  const body = $response && $response.body;
  if (!url.includes("functionId=welcomeHome") || typeof body !== "string" || !body) {
    $done({});
    return;
  }
  let obj;
  try {
    obj = JSON.parse(body);
  } catch (_) {
    $done({});
    return;
  }
  if (!obj || typeof obj !== "object" || Array.isArray(obj)) {
    $done({});
    return;
  }
  const excluded = [
    "bottomXview",
    "float",
    "photoCeiling",
    "ruleFloat",
    "searchIcon",
    "topRotate",
    "tabBarAtmosphere",
  ];
  if (Array.isArray(obj.floorList) && obj.floorList.length > 0) {
    obj.floorList = obj.floorList.filter((item) =>
      !excluded.includes(item && item.type)
    );
  }
  $done({ body: JSON.stringify(obj) });
})();
