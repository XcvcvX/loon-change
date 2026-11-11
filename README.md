# R-Store × blockAdsV2 × 独立 App 去广告净化合集 · Loon 版

把多套去广告规则融合成**一个** Loon 原生插件，并通过 GitHub Actions 跟随上游自动更新：

- [zirawell/R-Store](https://github.com/zirawell/R-Store) 的 Quantumult X 规则（重写 + 独立分流），先转换为 Loon 语法；
- [fmz200/wool_scripts](https://github.com/fmz200/wool_scripts) 的 blockAdsV2.plugin；
- [Thelongdarkorg/loon-plugins](https://github.com/Thelongdarkorg/loon-plugins) 的细分 App 去广告插件；
- [aoomee/Loon-Adblock-Plugins](https://github.com/aoomee/Loon-Adblock-Plugins) 的独立 App 插件（含远程脚本与 Argument）；
- [zmjde/loon-plugins](https://github.com/zmjde/loon-plugins) 的 App 插件与通用过滤规则；
- [RuCu6 高德地图插件](https://rucu6.pages.dev/Plugins/amap.lpx)（通过 Romeo GitHub 镜像同步；JS/JQ 依赖缓存到 `sources/amap/`，合并后使用仓库内资源地址）；
- [ddgksf2013 墨鱼手记](https://ddgksf2013.top/rewrite/GuaZiVideoAds.conf) 的瓜子影视规则；
- [RuCu6 MyBlockAds](https://rucu6.pages.dev/Plugins/myblockads.lpx)（在线失败回退仓库缓存）。

> **只装一个 allAdRewrite.plugin 就够了。** 各来源规则经过优先级合并，R-Store 独立分流也会补进 Rule。

## 优先级（核心规则）

以 R-Store 转换产物为 base，独立 App 插件优先级更高。高德地图设为 `priority=-1`（最高），其次为 zmjde App `0`、QuanX 单文件 App `1`、aoomee `2`、Thelongdarkorg `3`；通用源按既有顺序。相同 URL 正则且动作等价时由高优先级来源胜出；不同动作（例如 JSON 字段删除与 reject）作为互补动作保留。高德的 `*.amap.com` 仅在确有规则守卫时保留，不加入裸 IP MITM。

## 产物一览

| 文件 | 作用 |
|---|---|
| allAdRewrite.plugin | 单插件自包含：开关 + 分流 + 重写 + 脚本 + MITM |
| validate_plugin.py | 静态质量门禁：结构、MITM、动作、Argument、重复触发器与风险提示 |
| test_source_guard.py | 上游来源防损坏测试：空响应、HTML、规则数量、必需插件 |
| test_validate_plugin.py | 校验器单元测试 |
| test_merge_plugins.py | 合并器集成测试：重复区块、reject 动作、TLD hostname、高德最高优先级与互补动作 |
| sources/amap/ | 高德上游插件、JS 与 3 份 JQ 依赖的可追溯缓存 |
| source_guard.py | 上游响应/仓库结构完整性门禁，阻止 HTML 错误页、空文件和缺失源 |
| rule-provenance.json | 逐条 Rewrite/Script/Rule 来源、合并胜出/重复/覆盖关系与上游版本追溯 |
| rule-diff.json | 与上次生产追溯基线比较，记录规则新增、删除、动作变化及上游版本变化 |
| source_health_guard.py | 上游来源可靠性评分、来源追溯完整度与异常更新发布门禁 |
| source-health.json | 每次生产同步的来源健康评分、规则变化幅度、警告与阻断原因报告 |
| rule_risk_history.py | 对新增、删除、动作变化进行风险分级，并维护最近 30 次同步的来源变化趋势 |
| rule-risk.json | 当前规则变更风险等级、逐条风险原因和来源评分关联 |
| rule-history.json | 最近 30 次成功生产同步的规则变化与来源趋势历史 |
| audit_plugin.py | 基础只读审计全局 UDP/443、MITM 通配覆盖候选、Script URL 与错放 Rewrite Action |
| deep_audit.py | 深度只读审计 Rewrite 宽泛匹配/动作冲突、MITM 字面守卫候选、Script URL 复用与触发类型，可输出 JSON/Markdown |

当前产物统计由工作流自动维护：

<!-- AUTO_PLUGIN_STATS:START -->
**由 GitHub Actions 自动更新的最新产物统计**

| 区块 | 条目数 |
|---|---:|
| [Argument] | 91 |
| [Rule] | 3498 |
| [Rewrite] | 3326 |
| [Script] | 616 |
| [MITM] hostname 条目 | 1484 |
| 唯一远程脚本 URL | 199 |
<!-- AUTO_PLUGIN_STATS:END -->

## 自动更新

GitHub Actions 每天北京时间 09:07 / 21:23 执行：转换 R-Store → 拉取独立 App 来源 → 合并去重 → 静态校验 → 更新本节统计 → 有变化才提交。

同步前会检查 R-Store、blockAdsV2、MyBlockAds 的有效内容量与区块结构，并核对 Thelongdarkorg、aoomee、zmjde、瓜子影视和高德插件来源文件；高德依赖脚本/JQ 同步镜像至 `sources/amap/`，防止远程依赖失效。HTML 错误页、空/截断响应、缺失必需插件或规则量相对上次报告下降超过 60% 时会触发 fail-closed。构建先写入临时目录，完整合并并通过插件校验后才替换正式产物；失败不会覆盖上一版有效插件。`source-report.json` 记录克隆仓库的 commit SHA 与来源文件数量，便于追溯。第六阶段第一批新增 `rule-provenance.json`：逐条记录 Rewrite/Script 规则的来源组、优先级、最终输出位置及同语义重复来源；Rule 记录新增、精确重复、语义覆盖和 Frontier 安全保护排除原因，并附上游版本报告。第六阶段第二批为 Thelongdarkorg、aoomee、zmjde App 多文件来源补充了精确插件文件名、原始 1-based 行号和原始行文本；其他来源暂保留提取序号，后续再逐类补齐。第六阶段第三批新增 `compare_rule_provenance.py`，每次同步前将新生成的追溯报告与上次已提交的报告比较，分别识别 Rewrite、Script、Rule 的新增、删除和可确定的动作变化，并记录上游 commit 变化。只有同一 matcher 在前后版本都唯一且动作不同，才归类为动作变化；多动作歧义会保守列为新增/删除，不猜测。差异报告以 `rule-diff.json` 保留并上传 Actions artifact，比较过程不修改规则或 MITM。该报告只描述合并过程，不证明规则在设备上的实际效果，也不改变正式 MITM/规则行为。第六阶段第四批增加来源可靠性评分与异常更新门禁：检查关键来源是否齐全、内容量与历史基线是否连续、高德依赖 SHA-256 是否完整、逐条来源追溯覆盖率，以及规则删除/动作变化/输出骤减幅度。高风险破坏性变化会暂停本轮发布并保留上一版正式插件；新增量异常只提示复核。`source-health.json` 随生产运行上传并提交，评分仅表示来源证据质量，不代表规则运行效果。该门禁不自动修改规则、MITM 或优先级。第六阶段第五批新增 `rule_risk_history.py`：新增规则默认中风险，删除和动作变化默认高风险；来源可靠性偏低时可将新增项提升为高风险。每次成功同步保留最近 30 次变化快照，按来源累计新增、删除和动作变化数量，生成 `rule-risk.json` 与 `rule-history.json`。风险标签用于安排人工复核，不证明规则有错，也不自动修改规则、MITM 或优先级。

如果校验发现硬错误，工作流会失败并阻止提交。警告（例如重复触发器、全局 UDP/443、远程脚本风险）不会擅自删除规则，也不会阻止更新，需结合 Loon 实际运行情况判断。

每次定时、手动或 main 推送触发的同步构建还会上传一份 `deep-audit-sync` 深度审计报告（JSON + Markdown，保留 14 天）；可在对应 Actions 运行页的 Artifacts 中查看完整候选明细，不必从控制台日志中手动筛选。该报告只用于风险追踪，不会自动删改生产规则。

## 本地检查

    python3 -m unittest -v test_validate_plugin.py test_merge_plugins.py test_source_guard.py test_audit_plugin.py test_deep_audit.py test_amap_dependency_guard.py test_compare_rule_provenance.py test_source_health_guard.py test_rule_risk_history.py
    python3 -m py_compile merge_plugins.py validate_plugin.py source_guard.py audit_plugin.py deep_audit.py amap_dependency_guard.py compare_rule_provenance.py source_health_guard.py rule_risk_history.py convert_qx2loon.py convert_filter_qx2loon.py
    python3 validate_plugin.py allAdRewrite.plugin
    python3 validate_plugin.py allAdRewrite.plugin --update-readme README.md
    python3 validate_plugin.py allAdRewrite.plugin --check-remote
    python3 audit_plugin.py allAdRewrite.plugin --summary-only
    python3 deep_audit.py allAdRewrite.plugin --summary-only
    python3 deep_audit.py allAdRewrite.plugin --json deep-audit.json --markdown deep-audit.md

--check-remote 会对最多 80 个唯一远程脚本 URL 发起 HEAD 检查，仅输出警告，不代表脚本逻辑已通过测试；部分 CDN 不支持 HEAD 或会限流。`audit_plugin.py` 输出基础运行风险统计。`deep_audit.py` 进一步输出 Rewrite 宽泛匹配、同匹配器多动作、MITM 未发现明显字面守卫的候选，以及 Script 触发器类型和远程 URL 复用报告；第五阶段第二批规范化正则中的转义 URL 分隔符，并区分域名限定、子域名通配、路径通配和无明确域名约束的 Rewrite，减少正常域名规则的误报。第五阶段第三批补充现代条件式 Rewrite 的正则边界识别，兼容未转义 URL 斜杠、正则 flags、`as m` 捕获别名、`&&`/`||` 条件以及数字型旧式动作（如 `302`），并继续保留无法识别的条目供人工复核。分类与解析结果仅用于审计，不自动删改规则。第五阶段第四批进一步按语义归类 Rewrite 动作，覆盖拒绝、重定向、响应模拟、响应正文改写、JSON 修改、请求正文改写和 Header 修改，并为可能改变业务响应/请求行为的动作生成复核优先级与原因。动作分类是人工检查线索，不代表规则有错；不自动删改规则。第五阶段第五批增加样本驱动的 Rewrite 交叉命中审计：为受限安全子集生成代表性 URL 样本，检查不同 matcher 是否可能命中同一 URL，并区分同阶段不同动作、同类动作、request/response 明确跨阶段命中，以及 legacy 语法无法确定阶段的歧义命中；复杂正则会跳过并列入人工复核。样本审计不是完整正则交集证明，也不推断 Loon 规则执行顺序，不自动修复或删改正式规则。第五阶段第六批进一步将 Rewrite 与 Script 的字面 URL 触发主机和 MITM hostname 做关联覆盖审计，识别未被正向 MITM 覆盖、被负向 hostname 排除、动态主机的稳定后缀能否被通配项覆盖，以及没有明显字面触发器引用的 MITM 正向项；纯 HTTP 和裸 IPv4 单独分类，不误报为应补入 MITM 的缺口。通配覆盖按子域语义核对，负向排除优先提示；Script 的远程脚本下载主机与脚本触发 URL 主机分开处理，不能把 CDN 下载域名误当作需要 MITM 的业务请求域名。结果仅为人工复核候选，不自动添加或删除 MITM。第五阶段第七批在此基础上增加 MITM 必要性证据分级：区分被字面触发器覆盖、仅在规则文本中出现的间接/嵌入主机、动态或通用触发证据不足，以及未发现字面引用的候选；对未覆盖项进一步区分 HTTPS 明确候选与协议/matcher 歧义。通用 Script、动态主机、通配域和脚本/CDN 地址均保留不确定性，不把静态未引用等同于冗余。该分级仅用于人工复核，不自动增删 hostname，也不生成删除建议。第五阶段第八批改进 MITM 主机提取：识别可选/动态端口、可选子域名和带稳定字面后缀的动态主机；仅把明确转义的点号视为域名标签边界，公共后缀及无法证明的复杂表达式继续保留歧义，不自动增删 MITM。

## 安全边界

- 校验器只报告问题，不自动删改广告规则、QUIC 规则或 MITM hostname，避免静态工具造成漏拦截或 App 故障。
- 全局 UDP/443 拦截可能影响 HTTP/3/QUIC。是否移除应结合实际网络和 App 测试决定；本次不会擅自改变用户已有规则。
- MITM hostname 检查覆盖格式、重复、已知必需主机；复杂 URL 正则的 MITM 覆盖关系仍需 Loon 日志和真实设备验证。
- 正则使用 Loon/ICU 语法，Python re 编译只作辅助提示，不能代替 Loon 解析器。
