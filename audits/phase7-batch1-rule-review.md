# 第七阶段第一批：正式规则只读筛查报告

**审计基线：** `allAdRewrite.plugin`（main，2026-11-11 07:29 UTC 生成）

**范围：** 仅分析现有 Rewrite / Script / MITM 关系及静态匹配风险；本报告不修改任何规则、MITM hostname、优先级、脚本开关或插件行为。

## 总体结果

| 检查项 | 数量 |
|---|---:|
| Rewrite 条目 / 未解析 | 3,326 / 0 |
| 宽泛匹配候选 | 10 |
| 重复匹配器组 / 同匹配器多动作组 | 28 / 27 |
| 动作语义复核候选 | 386 |
| 交叉命中候选组 / 需人工复核组 | 110 / 71 |
| MITM 正向唯一主机 / 通配主机 | 1,483 / 58 |
| MITM 无明显字面守卫候选 | 80 |
| MITM 未覆盖 Rewrite/Script 字面主机引用 | 22 |
| Script 条目 / 唯一远程脚本 URL | 616 / 199 |
| 多触发器复用脚本 URL / 通用触发器候选 | 98 / 254 |

**重要限制：** 静态审计无法证明设备端实际请求是否命中，也无法证明某条规则一定误拦截。所有候选必须结合原始请求日志、App 正常功能和真实响应验证。MITM 未被静态引用、被通配覆盖或缺少明显字面守卫，均不构成自动删除/新增/修改依据。

## 优先复核建议

1. **P1：泛主机 URL 规则。** 优先核实 `api/vN/advert`、`yyting/advertclient`、`music/common/upload/t_splash_info` 等路径是否确实只属于广告请求。

2. **P1：DNS/网络基础设施路径。** `119.29.29.* /d` 需要确认其是否为 DNS 相关请求，以及是否可能影响解析；在验证前不改。

3. **P2：相同匹配器多动作。** 区分“有意的分步 JSON 清理”与“重复拦截动作冲突”，不能简单删掉其中一条。

4. **P2：图片/CDN 与银行业务。** 对银行主题图片、地图/电商图片等匹配，必须确认是否只针对广告资源，避免正常 UI 图片损坏。

5. **P3：MITM 与 Script 触发器。** 只记录待验证缺口，不因静态分析结果自动改 MITM。

## 宽泛 Rewrite 候选（逐项保留原始 matcher）（10 项）

### 1. 行 4232 · legacy · reject
- Matcher：`^https?:\/\/[\d\.]+:\d{5}\/\?cmd=indexes`
- 风险提示：协议级 URL 匹配未见明确域名；范围：`url_without_domain`
- 来源：base [selected]; block [duplicate_same_semantics]
- 判断：**待验证，不建议仅凭静态结果删除或收窄。**

### 2. 行 4233 · legacy · reject-dict
- Matcher：`^https?:\/\/[\d\.]+\/odin\/c\d\/(channel\/ads|skin\/config)\?`
- 风险提示：协议级 URL 匹配未见明确域名；范围：`url_without_domain`
- 来源：base [selected]
- 判断：**待验证，不建议仅凭静态结果删除或收窄。**

### 3. 行 4887 · legacy · reject
- Matcher：`^https?:\/\/.*\/yyting\/advertclient\/ClientAdvertList.action`
- 风险提示：含未限定域名的贪婪通配; 协议级 URL 匹配未见明确域名；范围：`url_without_domain`
- 来源：base [selected]; block [duplicate_same_semantics]
- 判断：**待验证，不建议仅凭静态结果删除或收窄。**

### 4. 行 5391 · request · reject(404)
- Matcher：`^https?:\/\/[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+){1,3}(:\d+)?\/api\/v\d\/advert`
- 风险提示：协议级 URL 匹配未见明确域名；范围：`url_without_domain`
- 来源：block [selected]
- 判断：**待验证，不建议仅凭静态结果删除或收窄。**

### 5. 行 5788 · request · reject_dict(200)
- Matcher：`^https?:\/\/[\d\.]+\/odin\/c1\/(channel\/ads|skin\/config)\?`
- 风险提示：协议级 URL 匹配未见明确域名；范围：`url_without_domain`
- 来源：block [selected]
- 判断：**待验证，不建议仅凭静态结果删除或收窄。**

### 6. 行 5833 · request · reject(404)
- Matcher：`^https?:\/\/103\.91\.210\.141\:2515\/xgapp\.php\/v2\/top_notice`
- 风险提示：协议级 URL 匹配未见明确域名；范围：`url_without_domain`
- 来源：block [selected]
- 判断：**待验证，不建议仅凭静态结果删除或收窄。**

### 7. 行 5898 · legacy · reject
- Matcher：`^https?:\/\/.+?\/music\/common\/upload\/t_splash_info\/`
- 风险提示：含未限定域名的贪婪通配; 协议级 URL 匹配未见明确域名；范围：`url_without_domain`
- 来源：block [duplicate_same_semantics]; thelong / qqmusic_splash_ad_block.plugin:82 [selected]
- 判断：**待验证，不建议仅凭静态结果删除或收窄。**

### 8. 行 5900 · request · reject(404)
- Matcher：`^https?:\/\/((25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\.){3}(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\/music\/common\/upload\/t_splash_info\/`
- 风险提示：协议级 URL 匹配未见明确域名；范围：`url_without_domain`
- 来源：block [selected]
- 判断：**待验证，不建议仅凭静态结果删除或收窄。**

### 9. 行 6214 · request · reject(200)
- Matcher：`^https?:\/\/119\.29\.29\.\d+\/d`
- 风险提示：协议级 URL 匹配未见明确域名；范围：`url_without_domain`
- 来源：block [selected]
- 判断：**待验证，不建议仅凭静态结果删除或收窄。**

### 10. 行 6492 · legacy · reject
- Matcher：`^http:\/\/[\d\.:]*\/?(defaultts\.tc|vmind\.qqvideo\.tc|finderpdd\.video)\.qq\.com\/\w+`
- 风险提示：协议级 URL 匹配未见明确域名；范围：`url_without_domain`
- 来源：thelong / tencentvideo_splash_ad_block.plugin:93 [selected]
- 判断：**待验证，不建议仅凭静态结果删除或收窄。**

## 同匹配器多动作组（全部列出）（27 项）

### 1. 行 6568, 6569 · legacy
- Matcher：`^https:\/\/(api|page-info)(?:\.zhihu)?\.com\/answers\/v\d\/\d+(?:\?.*)?$`
- 动作：`response-body-json-del`; `response-body-json-jq`
- 来源：thelong / zhihu_splash_ad_block.plugin:23 [selected]; thelong / zhihu_splash_ad_block.plugin:24 [selected]
- 判断：同一 matcher 下多条响应体处理可能是互补步骤；若是多个请求拦截动作，则需确认 Loon 的执行/优先级语义。

### 2. 行 6485, 6523 · legacy
- Matcher：`^https:\/\/acs\.m\.taobao\.com\/gw\/mtop\.taobao\.idlecommerce\.splash\.ads`
- 动作：`reject-200`; `reject-dict`
- 来源：thelong / taobao_splash_ad_block.plugin:33 [selected]; thelong / xianyu_splash_ad_block.plugin:40 [selected]
- 判断：同一 matcher 下多条响应体处理可能是互补步骤；若是多个请求拦截动作，则需确认 Loon 的执行/优先级语义。

### 3. 行 6486, 6522 · legacy
- Matcher：`^https:\/\/guide-acs\.m\.taobao\.com\/gw\/mtop\.taobao\.wireless\.home\.splash\.awesome\.get`
- 动作：`reject-200`; `reject-dict`
- 来源：thelong / taobao_splash_ad_block.plugin:41 [selected]; thelong / xianyu_splash_ad_block.plugin:38 [selected]
- 判断：同一 matcher 下多条响应体处理可能是互补步骤；若是多个请求拦截动作，则需确认 Loon 的执行/优先级语义。

### 4. 行 4287, 6424 · legacy
- Matcher：`^https?:\/\/(bdsp-x|dsp-x)\.jd\.com\/adx\/`
- 动作：`reject`; `reject-200`
- 来源：base [selected]; block [duplicate_same_semantics]; thelong / jd_splash_ad_block.plugin:22 [selected]
- 判断：同一 matcher 下多条响应体处理可能是互补步骤；若是多个请求拦截动作，则需确认 Loon 的执行/优先级语义。

### 5. 行 4343, 6426 · legacy
- Matcher：`^https?:\/\/api\.m\.jd\.com\/client\.action\?functionId=lite_advertising`
- 动作：`reject`; `response-body-replace-regex`
- 来源：base [selected]; block [selected]; thelong / jd_splash_ad_block.plugin:31 [selected]
- 判断：同一 matcher 下多条响应体处理可能是互补步骤；若是多个请求拦截动作，则需确认 Loon 的执行/优先级语义。

### 6. 行 3864, 6493 · legacy
- Matcher：`^https?:\/\/appactive\.1234567\.com\.cn\/AppoperationApi\/OperationService\/GetAppStartImg`
- 动作：`reject`; `response-body-json-jq`
- 来源：base [selected]; block [duplicate_same_semantics]; thelong / tiantianjijin_splash_ad_block.plugin:195 [selected]
- 判断：同一 matcher 下多条响应体处理可能是互补步骤；若是多个请求拦截动作，则需确认 Loon 的执行/优先级语义。

### 7. 行 6494, 6495 · legacy
- Matcher：`^https?:\/\/appconfig2\.1234567\.com\.cn\/config\/GetAppHome(?:\?.*)?$`
- 动作：`response-body-json-jq`; `response-header-del`
- 来源：thelong / tiantianjijin_splash_ad_block.plugin:203 [selected]; thelong / tiantianjijin_splash_ad_block.plugin:204 [selected]
- 判断：同一 matcher 下多条响应体处理可能是互补步骤；若是多个请求拦截动作，则需确认 Loon 的执行/优先级语义。

### 8. 行 4256, 6456 · legacy
- Matcher：`^https?:\/\/axxd\.xmseeyouyima\.com\/.*getad\?`
- 动作：`reject`; `reject-dict`
- 来源：base [selected]; thelong / meiyou_splash_ad_block.plugin:16 [selected]
- 判断：同一 matcher 下多条响应体处理可能是互补步骤；若是多个请求拦截动作，则需确认 Loon 的执行/优先级语义。

### 9. 行 4255, 6455 · legacy
- Matcher：`^https?:\/\/axxd\.xmseeyouyima\.com\/ad`
- 动作：`reject`; `reject-dict`
- 来源：base [selected]; thelong / meiyou_splash_ad_block.plugin:14 [selected]
- 判断：同一 matcher 下多条响应体处理可能是互补步骤；若是多个请求拦截动作，则需确认 Loon 的执行/优先级语义。

### 10. 行 4109, 5106 · legacy
- Matcher：`^https?:\/\/c\.m\.163\.com\/nc\/gl\/`
- 动作：`reject`; `reject-200`
- 来源：base [selected]; block [duplicate_same_semantics]
- 判断：同一 matcher 下多条响应体处理可能是互补步骤；若是多个请求拦截动作，则需确认 Loon 的执行/优先级语义。

### 11. 行 3712, 6616 · legacy
- Matcher：`^https?:\/\/cdn1\.mbs\.boc\.cn\/ubas-mgateway-static\/images\/theme\/`
- 动作：`reject-200`; `reject-dict`
- 来源：base [selected]; aoomee / plugins/boc.plugin:17 [selected]
- 判断：同一 matcher 下多条响应体处理可能是互补步骤；若是多个请求拦截动作，则需确认 Loon 的执行/优先级语义。

### 12. 行 3710, 6614 · legacy
- Matcher：`^https?:\/\/mbs\.boc\.cn\/ubas-mgateway-static\/images\/theme\/`
- 动作：`reject-200`; `reject-dict`
- 来源：base [selected]; aoomee / plugins/boc.plugin:15 [selected]
- 判断：同一 matcher 下多条响应体处理可能是互补步骤；若是多个请求拦截动作，则需确认 Loon 的执行/优先级语义。

### 13. 行 5145, 5149 · legacy
- Matcher：`^https?:\/\/support\.you\.163\.com\/xhr\/boot\/getBootMedia`
- 动作：`reject`; `reject-200`
- 来源：base [selected]; block [selected]
- 判断：同一 matcher 下多条响应体处理可能是互补步骤；若是多个请求拦截动作，则需确认 Loon 的执行/优先级语义。

### 14. 行 3726, 4504 · legacy
- Matcher：`^https?:\/\/us\.l\.qq\.com\/exapp`
- 动作：`reject`; `reject-200`
- 来源：base [selected]; block [duplicate_same_semantics]; zmjgen [duplicate_same_semantics]; block [selected]
- 判断：同一 matcher 下多条响应体处理可能是互补步骤；若是多个请求拦截动作，则需确认 Loon 的执行/优先级语义。

### 15. 行 4254, 6457 · legacy
- Matcher：`^https?:\/\/x\.seeyouyima\.com\/adx\/staticstics\?`
- 动作：`reject`; `reject-200`
- 来源：base [selected]; thelong / meiyou_splash_ad_block.plugin:18 [selected]
- 判断：同一 matcher 下多条响应体处理可能是互补步骤；若是多个请求拦截动作，则需确认 Loon 的执行/优先级语义。

### 16. 行 5399, 6331 · request
- Matcher：`^https:\/\/acs\.m\.taobao\.com\/gw\/mtop\.taobao\.idle\.home\.welcome`
- 动作：`reject(404)`; `reject_dict(200)`
- 来源：block [duplicate_same_semantics]; thelong / taobao_splash_ad_block.plugin:31 [duplicate_same_semantics]; zmjapp / Plugin/Taobao_remove_ads.lpx:29 [selected]; zmjgen [selected]
- 判断：同一 matcher 下多条响应体处理可能是互补步骤；若是多个请求拦截动作，则需确认 Loon 的执行/优先级语义。

### 17. 行 5554, 6283 · request
- Matcher：`^https?:\/\/adx-cn\.anythinktech\.com\/bid`
- 动作：`reject(200)`; `reject_dict(200)`
- 来源：block [selected]
- 判断：同一 matcher 下多条响应体处理可能是互补步骤；若是多个请求拦截动作，则需确认 Loon 的执行/优先级语义。

### 18. 行 5719, 5720 · response
- Matcher：`^https:\/\/(apissl|az2-api(-js|-idc)?)\.(gifshow|ksapisrv)\.com\/rest\/system\/startup\?`
- 动作：`response.json.delete("reskinConfig") | response.json.delete("sidebarExSquareStyle.moreList") | response.json.delete("sidebarExSquareStyle.topList")`; `response.json.jq(`.sidebarExSquareStyle.commonlyUsedList |= map(select(.title == "设置" or .title == "历史记录" or .title == "草稿箱" or .title == "我的钱包" or .title == "小程序" or .title == "未成年人模式" or .title == "官方客服" or .title == "内容偏好" or .title == "离线模式" or .title == "稍后再看" or .title == "举报中心" or .title == "挂件"))`)`
- 来源：block [selected]
- 判断：同一 matcher 下多条响应体处理可能是互补步骤；若是多个请求拦截动作，则需确认 Loon 的执行/优先级语义。

### 19. 行 6059, 6061 · response
- Matcher：`^https:\/\/(mobile|mobilehera|mobwsa)\.ximalaya\.com\/mobile-user\/v\d\/homePage\/`
- 动作：`response.json.delete("data.freeListenV2")`; `response.json.jq(`.data.serviceModule.entrances |= map(select(.name == "全部服务"))`)`
- 来源：block [selected]
- 判断：同一 matcher 下多条响应体处理可能是互补步骤；若是多个请求拦截动作，则需确认 Loon 的执行/优先级语义。

### 20. 行 6825, 6826 · response
- Matcher：`^https:\/\/api\.pinduoduo\.com\/api\/alexa\/homepage\/hub\?`
- 动作：`response.json.delete(["result.dy_module.irregular_banner_dy", "result.icon_set", "result.search_bar_hot_query", "result.dy_module.irregular_banner_dy"])`; `response.json.jq(".result.bottom_tabs? |= map(select(.link | IN(\"index.html\", \"chat_list.html\", \"personal.html\"))) | .result.buffer_bottom_tabs? |= map(select(.link | IN(\"index.html\", \"chat_list.html\", \"personal.html\"))) | .result.all_top_opts |= map(del(.selected_image, .image, .height, .width))")`
- 来源：zmjapp / Plugin/PinDuoDuo_remove_ads.lpx:55 [selected]; zmjapp / Plugin/PinDuoDuo_remove_ads.lpx:57 [selected]
- 判断：同一 matcher 下多条响应体处理可能是互补步骤；若是多个请求拦截动作，则需确认 Loon 的执行/优先级语义。

### 21. 行 6787, 6788 · response
- Matcher：`^https:\/\/api\.udache\.com\/gulfstream\/porsche\/v\d\/dache_homepage_layout\?`
- 动作：`response.json.delete("data.instances.dache_main_core_icon")`; `response.json.jq(".data |= (.instances |= (to_entries | map(select(.key | test(\"feed_back_|dache_main_member|order_container_|dache_main_core_icon|dache_main_card_\"))) | from_entries))")`
- 来源：zmjapp / Plugin/DiDi_remove_ads.lpx:35 [selected]; zmjapp / Plugin/DiDi_remove_ads.lpx:37 [selected]
- 判断：同一 matcher 下多条响应体处理可能是互补步骤；若是多个请求拦截动作，则需确认 Loon 的执行/优先级语义。

### 22. 行 6859, 6860, 6861 · response
- Matcher：`^https:\/\/app-api\.smzdm\.com\/util\/update$`
- 动作：`response.json.delete(["data.silence_local_push_msg", "data.video_cache_num_configs", "data.haojia_widget", "data.widget", "data.operation_float"])`; `response.json.jq("def r: if type==\"object\" then if has(\"ad_campaign_name\") and (.ad_campaign_name|type==\"string\") and (.ad_campaign_name|test(\"\\\\S\")) then empty else . end elif type==\"array\" then map(r) else . end; .data.operation_float |= map(map(r))")`; `response.json.replace(["data.silence_local_push", "data.baichuan_redirect_switch"], [0, 0])`
- 来源：zmjapp / Plugin/smzdm_remove_ads.lpx:19 [selected]; zmjapp / Plugin/smzdm_remove_ads.lpx:21 [selected]; zmjapp / Plugin/smzdm_remove_ads.lpx:23 [selected]
- 判断：同一 matcher 下多条响应体处理可能是互补步骤；若是多个请求拦截动作，则需确认 Loon 的执行/优先级语义。

### 23. 行 6782, 6786 · response
- Matcher：`^https:\/\/conf\.diditaxi\.com\.cn\/homepage\/v\d\/other\/fast\?`
- 动作：`response.json.delete(["data.disorder_cards.communicate_card", "data.disorder_cards.not_login_bottom_bar", "data.disorder_cards.riding_code_card", "data.order_cards", "data.disorder_cards.car_icon.data.icon_info_new_agreement"])`; `response.json.delete(["data.disorder_cards.guess_card", "data.disorder_cards.scene_list_card"])`
- 来源：zmjapp / Plugin/DiDi_remove_ads.lpx:26 [selected]; zmjapp / Plugin/DiDi_remove_ads.lpx:33 [selected]
- 判断：同一 matcher 下多条响应体处理可能是互补步骤；若是多个请求拦截动作，则需确认 Loon 的执行/优先级语义。

### 24. 行 6851, 6852 · response
- Matcher：`^https:\/\/g-acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idlemtopsearch\.search\/`
- 动作：`response.json.delete("data.resultPrefixBar")`; `response.json.jq(".data.resultList |= map(if .data.item.main.exContent.dislikeFeedback.clickParam.args.bizType == \"ad\" then empty else . end)")`
- 来源：zmjapp / Plugin/FleaMarket_remove_ads.lpx:50 [selected]; zmjapp / Plugin/FleaMarket_remove_ads.lpx:52 [selected]
- 判断：同一 matcher 下多条响应体处理可能是互补步骤；若是多个请求拦截动作，则需确认 Loon 的执行/优先级语义。

### 25. 行 6865, 6866 · response
- Matcher：`^https:\/\/haojia-api\.smzdm\.com\/home\/list\?`
- 动作：`response.json.delete("data.header_operation.theme")`; `response.json.jq(".data.rows |= map(select(.cell_type == \"39001\")) | .data.banner_v2 |= map(select(.cell_type == \"21028\"))")`
- 来源：zmjapp / Plugin/smzdm_remove_ads.lpx:31 [selected]; zmjapp / Plugin/smzdm_remove_ads.lpx:33 [selected]
- 判断：同一 matcher 下多条响应体处理可能是互补步骤；若是多个请求拦截动作，则需确认 Loon 的执行/优先级语义。

### 26. 行 6874, 6875 · response
- Matcher：`^https:\/\/s-api\.smzdm\.com\/sou\/filter\/tags\/hot_tags\?`
- 动作：`response.json.delete(["data.search_faxian", "data.tonglan", "data.hongbao"])`; `response.json.jq(".data.hot_tab |= (if type == \"array\" then map(select(.search_method != \"热点主题榜\")) else . end) | if .data.hot_tab then .data.hot_tab |= map(if .search_method == \"热搜榜搜索热榜\" and .rows then .rows |= map(select(.pos != null and ((.pos | tonumber) != null))) else . end) else . end")`
- 来源：zmjapp / Plugin/smzdm_remove_ads.lpx:49 [selected]; zmjapp / Plugin/smzdm_remove_ads.lpx:51 [selected]
- 判断：同一 matcher 下多条响应体处理可能是互补步骤；若是多个请求拦截动作，则需确认 Loon 的执行/优先级语义。

### 27. 行 4394, 4395 · response
- Matcher：`^https?:\/\/starplucker\.cyapi\.cn\/v\d\/config`
- 动作：`response.json.jq(`(.pic_page_card_orders[]?, .map_page_card_orders[]?) |= select(.name | test("^(A|C01)") | not)`)`; `response.json.jq(`del(.search_suggestions)?`)`
- 来源：base [selected]
- 判断：同一 matcher 下多条响应体处理可能是互补步骤；若是多个请求拦截动作，则需确认 Loon 的执行/优先级语义。

## 重复匹配器组（全部列出）（28 项）

### 1. 行 6568, 6569 · legacy
- Matcher：`^https:\/\/(api|page-info)(?:\.zhihu)?\.com\/answers\/v\d\/\d+(?:\?.*)?$`
- 动作：`response-body-json-del`; `response-body-json-jq`
- 来源：thelong / zhihu_splash_ad_block.plugin:23 [selected]; thelong / zhihu_splash_ad_block.plugin:24 [selected]
- 判断：需区分相同动作重复、同类动作不同响应码、以及不同响应处理；暂不合并。

### 2. 行 6485, 6523 · legacy
- Matcher：`^https:\/\/acs\.m\.taobao\.com\/gw\/mtop\.taobao\.idlecommerce\.splash\.ads`
- 动作：`reject-200`; `reject-dict`
- 来源：thelong / taobao_splash_ad_block.plugin:33 [selected]; thelong / xianyu_splash_ad_block.plugin:40 [selected]
- 判断：需区分相同动作重复、同类动作不同响应码、以及不同响应处理；暂不合并。

### 3. 行 6564, 6570 · legacy
- Matcher：`^https:\/\/api\.zhihu\.com\/topstory\/recommend\?`
- 动作：`response-body-json-jq`
- 来源：thelong / zhihu_splash_ad_block.plugin:19 [selected]; thelong / zhihu_splash_ad_block.plugin:25 [selected]
- 判断：需区分相同动作重复、同类动作不同响应码、以及不同响应处理；暂不合并。

### 4. 行 6486, 6522 · legacy
- Matcher：`^https:\/\/guide-acs\.m\.taobao\.com\/gw\/mtop\.taobao\.wireless\.home\.splash\.awesome\.get`
- 动作：`reject-200`; `reject-dict`
- 来源：thelong / taobao_splash_ad_block.plugin:41 [selected]; thelong / xianyu_splash_ad_block.plugin:38 [selected]
- 判断：需区分相同动作重复、同类动作不同响应码、以及不同响应处理；暂不合并。

### 5. 行 4287, 6424 · legacy
- Matcher：`^https?:\/\/(bdsp-x|dsp-x)\.jd\.com\/adx\/`
- 动作：`reject`; `reject-200`
- 来源：base [selected]; block [duplicate_same_semantics]; thelong / jd_splash_ad_block.plugin:22 [selected]
- 判断：需区分相同动作重复、同类动作不同响应码、以及不同响应处理；暂不合并。

### 6. 行 4343, 6426 · legacy
- Matcher：`^https?:\/\/api\.m\.jd\.com\/client\.action\?functionId=lite_advertising`
- 动作：`reject`; `response-body-replace-regex`
- 来源：base [selected]; block [selected]; thelong / jd_splash_ad_block.plugin:31 [selected]
- 判断：需区分相同动作重复、同类动作不同响应码、以及不同响应处理；暂不合并。

### 7. 行 3864, 6493 · legacy
- Matcher：`^https?:\/\/appactive\.1234567\.com\.cn\/AppoperationApi\/OperationService\/GetAppStartImg`
- 动作：`reject`; `response-body-json-jq`
- 来源：base [selected]; block [duplicate_same_semantics]; thelong / tiantianjijin_splash_ad_block.plugin:195 [selected]
- 判断：需区分相同动作重复、同类动作不同响应码、以及不同响应处理；暂不合并。

### 8. 行 6494, 6495 · legacy
- Matcher：`^https?:\/\/appconfig2\.1234567\.com\.cn\/config\/GetAppHome(?:\?.*)?$`
- 动作：`response-body-json-jq`; `response-header-del`
- 来源：thelong / tiantianjijin_splash_ad_block.plugin:203 [selected]; thelong / tiantianjijin_splash_ad_block.plugin:204 [selected]
- 判断：需区分相同动作重复、同类动作不同响应码、以及不同响应处理；暂不合并。

### 9. 行 4256, 6456 · legacy
- Matcher：`^https?:\/\/axxd\.xmseeyouyima\.com\/.*getad\?`
- 动作：`reject`; `reject-dict`
- 来源：base [selected]; thelong / meiyou_splash_ad_block.plugin:16 [selected]
- 判断：需区分相同动作重复、同类动作不同响应码、以及不同响应处理；暂不合并。

### 10. 行 4255, 6455 · legacy
- Matcher：`^https?:\/\/axxd\.xmseeyouyima\.com\/ad`
- 动作：`reject`; `reject-dict`
- 来源：base [selected]; thelong / meiyou_splash_ad_block.plugin:14 [selected]
- 判断：需区分相同动作重复、同类动作不同响应码、以及不同响应处理；暂不合并。

### 11. 行 4109, 5106 · legacy
- Matcher：`^https?:\/\/c\.m\.163\.com\/nc\/gl\/`
- 动作：`reject`; `reject-200`
- 来源：base [selected]; block [duplicate_same_semantics]
- 判断：需区分相同动作重复、同类动作不同响应码、以及不同响应处理；暂不合并。

### 12. 行 3712, 6616 · legacy
- Matcher：`^https?:\/\/cdn1\.mbs\.boc\.cn\/ubas-mgateway-static\/images\/theme\/`
- 动作：`reject-200`; `reject-dict`
- 来源：base [selected]; aoomee / plugins/boc.plugin:17 [selected]
- 判断：需区分相同动作重复、同类动作不同响应码、以及不同响应处理；暂不合并。

### 13. 行 3710, 6614 · legacy
- Matcher：`^https?:\/\/mbs\.boc\.cn\/ubas-mgateway-static\/images\/theme\/`
- 动作：`reject-200`; `reject-dict`
- 来源：base [selected]; aoomee / plugins/boc.plugin:15 [selected]
- 判断：需区分相同动作重复、同类动作不同响应码、以及不同响应处理；暂不合并。

### 14. 行 5145, 5149 · legacy
- Matcher：`^https?:\/\/support\.you\.163\.com\/xhr\/boot\/getBootMedia`
- 动作：`reject`; `reject-200`
- 来源：base [selected]; block [selected]
- 判断：需区分相同动作重复、同类动作不同响应码、以及不同响应处理；暂不合并。

### 15. 行 3726, 4504 · legacy
- Matcher：`^https?:\/\/us\.l\.qq\.com\/exapp`
- 动作：`reject`; `reject-200`
- 来源：base [selected]; block [duplicate_same_semantics]; zmjgen [duplicate_same_semantics]; block [selected]
- 判断：需区分相同动作重复、同类动作不同响应码、以及不同响应处理；暂不合并。

### 16. 行 4254, 6457 · legacy
- Matcher：`^https?:\/\/x\.seeyouyima\.com\/adx\/staticstics\?`
- 动作：`reject`; `reject-200`
- 来源：base [selected]; thelong / meiyou_splash_ad_block.plugin:18 [selected]
- 判断：需区分相同动作重复、同类动作不同响应码、以及不同响应处理；暂不合并。

### 17. 行 5399, 6331 · request
- Matcher：`^https:\/\/acs\.m\.taobao\.com\/gw\/mtop\.taobao\.idle\.home\.welcome`
- 动作：`reject(404)`; `reject_dict(200)`
- 来源：block [duplicate_same_semantics]; thelong / taobao_splash_ad_block.plugin:31 [duplicate_same_semantics]; zmjapp / Plugin/Taobao_remove_ads.lpx:29 [selected]; zmjgen [selected]
- 判断：需区分相同动作重复、同类动作不同响应码、以及不同响应处理；暂不合并。

### 18. 行 5554, 6283 · request
- Matcher：`^https?:\/\/adx-cn\.anythinktech\.com\/bid`
- 动作：`reject(200)`; `reject_dict(200)`
- 来源：block [selected]
- 判断：需区分相同动作重复、同类动作不同响应码、以及不同响应处理；暂不合并。

### 19. 行 5719, 5720 · response
- Matcher：`^https:\/\/(apissl|az2-api(-js|-idc)?)\.(gifshow|ksapisrv)\.com\/rest\/system\/startup\?`
- 动作：`response.json.delete("reskinConfig") | response.json.delete("sidebarExSquareStyle.moreList") | response.json.delete("sidebarExSquareStyle.topList")`; `response.json.jq(`.sidebarExSquareStyle.commonlyUsedList |= map(select(.title == "设置" or .title == "历史记录" or .title == "草稿箱" or .title == "我的钱包" or .title == "小程序" or .title == "未成年人模式" or .title == "官方客服" or .title == "内容偏好" or .title == "离线模式" or .title == "稍后再看" or .title == "举报中心" or .title == "挂件"))`)`
- 来源：block [selected]
- 判断：需区分相同动作重复、同类动作不同响应码、以及不同响应处理；暂不合并。

### 20. 行 6059, 6061 · response
- Matcher：`^https:\/\/(mobile|mobilehera|mobwsa)\.ximalaya\.com\/mobile-user\/v\d\/homePage\/`
- 动作：`response.json.delete("data.freeListenV2")`; `response.json.jq(`.data.serviceModule.entrances |= map(select(.name == "全部服务"))`)`
- 来源：block [selected]
- 判断：需区分相同动作重复、同类动作不同响应码、以及不同响应处理；暂不合并。

### 21. 行 6825, 6826 · response
- Matcher：`^https:\/\/api\.pinduoduo\.com\/api\/alexa\/homepage\/hub\?`
- 动作：`response.json.delete(["result.dy_module.irregular_banner_dy", "result.icon_set", "result.search_bar_hot_query", "result.dy_module.irregular_banner_dy"])`; `response.json.jq(".result.bottom_tabs? |= map(select(.link | IN(\"index.html\", \"chat_list.html\", \"personal.html\"))) | .result.buffer_bottom_tabs? |= map(select(.link | IN(\"index.html\", \"chat_list.html\", \"personal.html\"))) | .result.all_top_opts |= map(del(.selected_image, .image, .height, .width))")`
- 来源：zmjapp / Plugin/PinDuoDuo_remove_ads.lpx:55 [selected]; zmjapp / Plugin/PinDuoDuo_remove_ads.lpx:57 [selected]
- 判断：需区分相同动作重复、同类动作不同响应码、以及不同响应处理；暂不合并。

### 22. 行 6787, 6788 · response
- Matcher：`^https:\/\/api\.udache\.com\/gulfstream\/porsche\/v\d\/dache_homepage_layout\?`
- 动作：`response.json.delete("data.instances.dache_main_core_icon")`; `response.json.jq(".data |= (.instances |= (to_entries | map(select(.key | test(\"feed_back_|dache_main_member|order_container_|dache_main_core_icon|dache_main_card_\"))) | from_entries))")`
- 来源：zmjapp / Plugin/DiDi_remove_ads.lpx:35 [selected]; zmjapp / Plugin/DiDi_remove_ads.lpx:37 [selected]
- 判断：需区分相同动作重复、同类动作不同响应码、以及不同响应处理；暂不合并。

### 23. 行 6859, 6860, 6861 · response
- Matcher：`^https:\/\/app-api\.smzdm\.com\/util\/update$`
- 动作：`response.json.delete(["data.silence_local_push_msg", "data.video_cache_num_configs", "data.haojia_widget", "data.widget", "data.operation_float"])`; `response.json.jq("def r: if type==\"object\" then if has(\"ad_campaign_name\") and (.ad_campaign_name|type==\"string\") and (.ad_campaign_name|test(\"\\\\S\")) then empty else . end elif type==\"array\" then map(r) else . end; .data.operation_float |= map(map(r))")`; `response.json.replace(["data.silence_local_push", "data.baichuan_redirect_switch"], [0, 0])`
- 来源：zmjapp / Plugin/smzdm_remove_ads.lpx:19 [selected]; zmjapp / Plugin/smzdm_remove_ads.lpx:21 [selected]; zmjapp / Plugin/smzdm_remove_ads.lpx:23 [selected]
- 判断：需区分相同动作重复、同类动作不同响应码、以及不同响应处理；暂不合并。

### 24. 行 6782, 6786 · response
- Matcher：`^https:\/\/conf\.diditaxi\.com\.cn\/homepage\/v\d\/other\/fast\?`
- 动作：`response.json.delete(["data.disorder_cards.communicate_card", "data.disorder_cards.not_login_bottom_bar", "data.disorder_cards.riding_code_card", "data.order_cards", "data.disorder_cards.car_icon.data.icon_info_new_agreement"])`; `response.json.delete(["data.disorder_cards.guess_card", "data.disorder_cards.scene_list_card"])`
- 来源：zmjapp / Plugin/DiDi_remove_ads.lpx:26 [selected]; zmjapp / Plugin/DiDi_remove_ads.lpx:33 [selected]
- 判断：需区分相同动作重复、同类动作不同响应码、以及不同响应处理；暂不合并。

### 25. 行 6851, 6852 · response
- Matcher：`^https:\/\/g-acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idlemtopsearch\.search\/`
- 动作：`response.json.delete("data.resultPrefixBar")`; `response.json.jq(".data.resultList |= map(if .data.item.main.exContent.dislikeFeedback.clickParam.args.bizType == \"ad\" then empty else . end)")`
- 来源：zmjapp / Plugin/FleaMarket_remove_ads.lpx:50 [selected]; zmjapp / Plugin/FleaMarket_remove_ads.lpx:52 [selected]
- 判断：需区分相同动作重复、同类动作不同响应码、以及不同响应处理；暂不合并。

### 26. 行 6865, 6866 · response
- Matcher：`^https:\/\/haojia-api\.smzdm\.com\/home\/list\?`
- 动作：`response.json.delete("data.header_operation.theme")`; `response.json.jq(".data.rows |= map(select(.cell_type == \"39001\")) | .data.banner_v2 |= map(select(.cell_type == \"21028\"))")`
- 来源：zmjapp / Plugin/smzdm_remove_ads.lpx:31 [selected]; zmjapp / Plugin/smzdm_remove_ads.lpx:33 [selected]
- 判断：需区分相同动作重复、同类动作不同响应码、以及不同响应处理；暂不合并。

### 27. 行 6874, 6875 · response
- Matcher：`^https:\/\/s-api\.smzdm\.com\/sou\/filter\/tags\/hot_tags\?`
- 动作：`response.json.delete(["data.search_faxian", "data.tonglan", "data.hongbao"])`; `response.json.jq(".data.hot_tab |= (if type == \"array\" then map(select(.search_method != \"热点主题榜\")) else . end) | if .data.hot_tab then .data.hot_tab |= map(if .search_method == \"热搜榜搜索热榜\" and .rows then .rows |= map(select(.pos != null and ((.pos | tonumber) != null))) else . end) else . end")`
- 来源：zmjapp / Plugin/smzdm_remove_ads.lpx:49 [selected]; zmjapp / Plugin/smzdm_remove_ads.lpx:51 [selected]
- 判断：需区分相同动作重复、同类动作不同响应码、以及不同响应处理；暂不合并。

### 28. 行 4394, 4395 · response
- Matcher：`^https?:\/\/starplucker\.cyapi\.cn\/v\d\/config`
- 动作：`response.json.jq(`(.pic_page_card_orders[]?, .map_page_card_orders[]?) |= select(.name | test("^(A|C01)") | not)`)`; `response.json.jq(`del(.search_suggestions)?`)`
- 来源：base [selected]
- 判断：需区分相同动作重复、同类动作不同响应码、以及不同响应处理；暂不合并。

## 交叉命中人工复核样本（前 30 组）（30 项）

### 1. 行  · unknown
- 样本 URL：``
- 判断：先核实命中顺序与动作是否兼容；跨 request/response 阶段的组合不自动视为冲突。

### 2. 行  · unknown
- 样本 URL：``
- 判断：先核实命中顺序与动作是否兼容；跨 request/response 阶段的组合不自动视为冲突。

### 3. 行  · unknown
- 样本 URL：``
- 判断：先核实命中顺序与动作是否兼容；跨 request/response 阶段的组合不自动视为冲突。

### 4. 行  · unknown
- 样本 URL：``
- 判断：先核实命中顺序与动作是否兼容；跨 request/response 阶段的组合不自动视为冲突。

### 5. 行  · unknown
- 样本 URL：``
- 判断：先核实命中顺序与动作是否兼容；跨 request/response 阶段的组合不自动视为冲突。

### 6. 行  · unknown
- 样本 URL：``
- 判断：先核实命中顺序与动作是否兼容；跨 request/response 阶段的组合不自动视为冲突。

### 7. 行  · unknown
- 样本 URL：``
- 判断：先核实命中顺序与动作是否兼容；跨 request/response 阶段的组合不自动视为冲突。

### 8. 行  · unknown
- 样本 URL：``
- 判断：先核实命中顺序与动作是否兼容；跨 request/response 阶段的组合不自动视为冲突。

### 9. 行  · unknown
- 样本 URL：``
- 判断：先核实命中顺序与动作是否兼容；跨 request/response 阶段的组合不自动视为冲突。

### 10. 行  · unknown
- 样本 URL：``
- 判断：先核实命中顺序与动作是否兼容；跨 request/response 阶段的组合不自动视为冲突。

### 11. 行  · unknown
- 样本 URL：``
- 判断：先核实命中顺序与动作是否兼容；跨 request/response 阶段的组合不自动视为冲突。

### 12. 行  · unknown
- 样本 URL：``
- 判断：先核实命中顺序与动作是否兼容；跨 request/response 阶段的组合不自动视为冲突。

### 13. 行  · unknown
- 样本 URL：``
- 判断：先核实命中顺序与动作是否兼容；跨 request/response 阶段的组合不自动视为冲突。

### 14. 行  · unknown
- 样本 URL：``
- 判断：先核实命中顺序与动作是否兼容；跨 request/response 阶段的组合不自动视为冲突。

### 15. 行  · unknown
- 样本 URL：``
- 判断：先核实命中顺序与动作是否兼容；跨 request/response 阶段的组合不自动视为冲突。

### 16. 行  · unknown
- 样本 URL：``
- 判断：先核实命中顺序与动作是否兼容；跨 request/response 阶段的组合不自动视为冲突。

### 17. 行  · unknown
- 样本 URL：``
- 判断：先核实命中顺序与动作是否兼容；跨 request/response 阶段的组合不自动视为冲突。

### 18. 行  · unknown
- 样本 URL：``
- 判断：先核实命中顺序与动作是否兼容；跨 request/response 阶段的组合不自动视为冲突。

### 19. 行  · unknown
- 样本 URL：``
- 判断：先核实命中顺序与动作是否兼容；跨 request/response 阶段的组合不自动视为冲突。

### 20. 行  · unknown
- 样本 URL：``
- 判断：先核实命中顺序与动作是否兼容；跨 request/response 阶段的组合不自动视为冲突。

### 21. 行  · unknown
- 样本 URL：``
- 判断：先核实命中顺序与动作是否兼容；跨 request/response 阶段的组合不自动视为冲突。

### 22. 行  · unknown
- 样本 URL：``
- 判断：先核实命中顺序与动作是否兼容；跨 request/response 阶段的组合不自动视为冲突。

### 23. 行  · unknown
- 样本 URL：``
- 判断：先核实命中顺序与动作是否兼容；跨 request/response 阶段的组合不自动视为冲突。

### 24. 行  · unknown
- 样本 URL：``
- 判断：先核实命中顺序与动作是否兼容；跨 request/response 阶段的组合不自动视为冲突。

### 25. 行  · unknown
- 样本 URL：``
- 判断：先核实命中顺序与动作是否兼容；跨 request/response 阶段的组合不自动视为冲突。

### 26. 行  · unknown
- 样本 URL：``
- 判断：先核实命中顺序与动作是否兼容；跨 request/response 阶段的组合不自动视为冲突。

### 27. 行  · unknown
- 样本 URL：``
- 判断：先核实命中顺序与动作是否兼容；跨 request/response 阶段的组合不自动视为冲突。

### 28. 行  · unknown
- 样本 URL：``
- 判断：先核实命中顺序与动作是否兼容；跨 request/response 阶段的组合不自动视为冲突。

### 29. 行  · unknown
- 样本 URL：``
- 判断：先核实命中顺序与动作是否兼容；跨 request/response 阶段的组合不自动视为冲突。

### 30. 行  · unknown
- 样本 URL：``
- 判断：先核实命中顺序与动作是否兼容；跨 request/response 阶段的组合不自动视为冲突。

## MITM 未覆盖的字面 Rewrite/Script 引用（全部列出，仅作诊断）（22 项）

### 1. 行 3655 · rewrite · pv.elife.icbc.com.cn
- Host：`pv.elife.icbc.com.cn` · scheme：`http_or_https` · action：`reject-200`
- Matcher/触发器：`^https?:\/\/pv\.elife\.icbc\.com\.cn\/OFSTPV\/utm\.gif`
- 判断：先确认请求协议、Loon 执行阶段与 MITM 实际必要性；HTTP-only、裸 IP、动态 host 及非 MITM 请求不得机械添加。

### 2. 行 3656 · rewrite · elife.icbc.com.cn
- Host：`elife.icbc.com.cn` · scheme：`http_or_https` · action：`reject-dict`
- Matcher/触发器：`^https?:\/\/elife\.icbc\.com\.cn\/OFSTNEWBASE\/floorinfo\/getStartupPages`
- 判断：先确认请求协议、Loon 执行阶段与 MITM 实际必要性；HTTP-only、裸 IP、动态 host 及非 MITM 请求不得机械添加。

### 3. 行 3753 · rewrite · openapi.boc.cn
- Host：`openapi.boc.cn` · scheme：`http_or_https` · action：`reject-200`
- Matcher/触发器：`^https?:\/\/openapi\.boc\.cn\/unlogin\/app\/cbsp\/query_ad_list`
- 判断：先确认请求协议、Loon 执行阶段与 MITM 实际必要性；HTTP-only、裸 IP、动态 host 及非 MITM 请求不得机械添加。

### 4. 行 3786 · rewrite · res.cc.cmbimg.com
- Host：`res.cc.cmbimg.com` · scheme：`http_or_https` · action：`response-body-replace-regex`
- Matcher/触发器：`^https?:\/\/res\.cc\.cmbimg\.com\/fsp\/File\/ClientFacePublic\/\w+\.DAT$`
- 判断：先确认请求协议、Loon 执行阶段与 MITM 实际必要性；HTTP-only、裸 IP、动态 host 及非 MITM 请求不得机械添加。

### 5. 行 4381 · rewrite · ios.chat.openai.com
- Host：`ios.chat.openai.com` · scheme：`http_or_https` · action：`reject-dict`
- Matcher/触发器：`^https?:\/\/ios\.chat\.openai\.com\/public-api\/mobile\/app_support_status`
- 判断：先确认请求协议、Loon 执行阶段与 MITM 实际必要性；HTTP-only、裸 IP、动态 host 及非 MITM 请求不得机械添加。

### 6. 行 4631 · rewrite · m.ctrip.com
- Host：`m.ctrip.com` · scheme：`http_or_https` · action：`reject`
- Matcher/触发器：`^https?:\/\/m\.ctrip\.com\/restapi\/.*\/getTimeZoneServerIpList`
- 判断：先确认请求协议、Loon 执行阶段与 MITM 实际必要性；HTTP-only、裸 IP、动态 host 及非 MITM 请求不得机械添加。

### 7. 行 4632 · rewrite · m.ctrip.com
- Host：`m.ctrip.com` · scheme：`http_or_https` · action：`reject`
- Matcher/触发器：`^https?:\/\/m\.ctrip\.com\/restapi\/.*\/tripAds`
- 判断：先确认请求协议、Loon 执行阶段与 MITM 实际必要性；HTTP-only、裸 IP、动态 host 及非 MITM 请求不得机械添加。

### 8. 行 4633 · rewrite · m.ctrip.com
- Host：`m.ctrip.com` · scheme：`http_or_https` · action：`reject`
- Matcher/触发器：`^https?:\/\/m\.ctrip\.com\/restapi\/.*\/getAdsList`
- 判断：先确认请求协议、Loon 执行阶段与 MITM 实际必要性；HTTP-only、裸 IP、动态 host 及非 MITM 请求不得机械添加。

### 9. 行 4634 · rewrite · m.ctrip.com
- Host：`m.ctrip.com` · scheme：`http_or_https` · action：`reject`
- Matcher/触发器：`^https?:\/\/m\.ctrip\.com\/restapi\/.*\/getAppConfig`
- 判断：先确认请求协议、Loon 执行阶段与 MITM 实际必要性；HTTP-only、裸 IP、动态 host 及非 MITM 请求不得机械添加。

### 10. 行 4635 · rewrite · m.ctrip.com
- Host：`m.ctrip.com` · scheme：`http_or_https` · action：`reject`
- Matcher/触发器：`^https?:\/\/m\.ctrip\.com\/restapi\/.*\/incrQueryTrans`
- 判断：先确认请求协议、Loon 执行阶段与 MITM 实际必要性；HTTP-only、裸 IP、动态 host 及非 MITM 请求不得机械添加。

### 11. 行 4636 · rewrite · m.ctrip.com
- Host：`m.ctrip.com` · scheme：`http_or_https` · action：`reject`
- Matcher/触发器：`^https?:\/\/m\.ctrip\.com\/restapi\/.*\/getDiscardUbts`
- 判断：先确认请求协议、Loon 执行阶段与 MITM 实际必要性；HTTP-only、裸 IP、动态 host 及非 MITM 请求不得机械添加。

### 12. 行 4637 · rewrite · m.ctrip.com
- Host：`m.ctrip.com` · scheme：`http_or_https` · action：`reject`
- Matcher/触发器：`^https?:\/\/m\.ctrip\.com\/html5\/webresource\/js\/iscroll\.js$`
- 判断：先确认请求协议、Loon 执行阶段与 MITM 实际必要性；HTTP-only、裸 IP、动态 host 及非 MITM 请求不得机械添加。

### 13. 行 4646 · rewrite · images.cib.com.cn
- Host：`images.cib.com.cn` · scheme：`http_or_https` · action：`reject-200`
- Matcher/触发器：`^https?:\/\/images\.cib\.com\.cn\/commons\/uploads\/commons\/[a-zA-Z0-9]{32}\.jpg\?ver=20221[1-2]{1}`
- 判断：先确认请求协议、Loon 执行阶段与 MITM 实际必要性；HTTP-only、裸 IP、动态 host 及非 MITM 请求不得机械添加。

### 14. 行 4647 · rewrite · images.cib.com.cn
- Host：`images.cib.com.cn` · scheme：`http_or_https` · action：`reject-200`
- Matcher/触发器：`^https?:\/\/images\.cib\.com\.cn\/commons\/uploads\/commons\/[a-zA-Z0-9]{32}\.jpg\?ver=20230[1-9]{1}`
- 判断：先确认请求协议、Loon 执行阶段与 MITM 实际必要性；HTTP-only、裸 IP、动态 host 及非 MITM 请求不得机械添加。

### 15. 行 5191 · rewrite · elife.icbc.com.cn
- Host：`elife.icbc.com.cn` · scheme：`http_or_https` · action：`reject-200`
- Matcher/触发器：`^https?:\/\/elife\.icbc\.com\.cn\/OFSTNEWBASE\/floorinfo\/(getStartupMantleFlatingFloor|getMantlePages)`
- 判断：先确认请求协议、Loon 执行阶段与 MITM 实际必要性；HTTP-only、裸 IP、动态 host 及非 MITM 请求不得机械添加。

### 16. 行 5196 · rewrite · wcmp.189.cn
- Host：`wcmp.189.cn` · scheme：`http_or_https` · action：`response-body-replace-regex`
- Matcher/触发器：`^https?:\/\/wcmp\.189\.cn\/xcxApiService\/api\/gateway`
- 判断：先确认请求协议、Loon 执行阶段与 MITM 实际必要性；HTTP-only、裸 IP、动态 host 及非 MITM 请求不得机械添加。

### 17. 行 5320 · rewrite · m.ctrip.com
- Host：`m.ctrip.com` · scheme：`http_or_https` · action：`reject-dict`
- Matcher/触发器：`^https?:\/\/m\.ctrip\.com\/restapi\/soa\d\/\d+\/(?:tripAds|queryWeChatHotEvent)`
- 判断：先确认请求协议、Loon 执行阶段与 MITM 实际必要性；HTTP-only、裸 IP、动态 host 及非 MITM 请求不得机械添加。

### 18. 行 5632 · rewrite · elife.icbc.com.cn
- Host：`elife.icbc.com.cn` · scheme：`http_or_https` · action：`reject(200)`
- Matcher/触发器：`^https?:\/\/elife\.icbc\.com\.cn\/OFSTNEWBASE\/floorinfo\/getMantlePages\.do`
- 判断：先确认请求协议、Loon 执行阶段与 MITM 实际必要性；HTTP-only、裸 IP、动态 host 及非 MITM 请求不得机械添加。

### 19. 行 6133 · rewrite · m.ctrip.com
- Host：`m.ctrip.com` · scheme：`http_or_https` · action：`reject(200)`
- Matcher/触发器：`^https?:\/\/m\.ctrip\.com\/restapi\/soa2\/[0-9]{5}\/json\/getTimeZoneServerIpList\?__gw_os=IOS`
- 判断：先确认请求协议、Loon 执行阶段与 MITM 实际必要性；HTTP-only、裸 IP、动态 host 及非 MITM 请求不得机械添加。

### 20. 行 6134 · rewrite · m.ctrip.com
- Host：`m.ctrip.com` · scheme：`http_or_https` · action：`reject(200)`
- Matcher/触发器：`^https?:\/\/m\.ctrip\.com\/restapi\/soa2\/13916\/json\/tripAds`
- 判断：先确认请求协议、Loon 执行阶段与 MITM 实际必要性；HTTP-only、裸 IP、动态 host 及非 MITM 请求不得机械添加。

### 21. 行 6250 · rewrite · m.ctrip.com
- Host：`m.ctrip.com` · scheme：`http_or_https` · action：`reject_dict(200)`
- Matcher/触发器：`^https?:\/\/m\.ctrip\.com\/restapi\/soa2\/13916\/scjson\/tripAds`
- 判断：先确认请求协议、Loon 执行阶段与 MITM 实际必要性；HTTP-only、裸 IP、动态 host 及非 MITM 请求不得机械添加。

### 22. 行 7541 · script_trigger · mobilepaas.abchina.com.cn
- Host：`mobilepaas.abchina.com.cn` · scheme：`https_only` · action：`None`
- Matcher/触发器：`if ${url} ~= /^https:\/\/mobilepaas\.abchina\.com\.cn:441\/mgw\.htm$/i then script("https://rucu6.pages.dev/Scripts/header.js") with`
- 判断：先确认请求协议、Loon 执行阶段与 MITM 实际必要性；HTTP-only、裸 IP、动态 host 及非 MITM 请求不得机械添加。

## 本批结论

本批发现的是需要验证的风险面，而不是已经确认的错误规则。当前没有任何证据足以支持批量删除 MITM、合并重复规则或调整拦截动作。下一批应从 P1 候选中挑选少量规则，逐条建立正向/反向测试样本（广告样本、正常业务样本），验证匹配边界后再形成规则修改 PR。

## 可复核的机器审计原件

- `deep-audit-sync.json`：完整静态审计数据（本次 Actions artifact）。
- `deep-audit-sync.md`：完整审计报告（本次 Actions artifact）。
- `rule-provenance.json`：规则来源映射（本次 Actions artifact）。
- 本报告行号对应审计时的 `allAdRewrite.plugin` 物理行号；后续上游同步后行号可能变化，必须重新定位。