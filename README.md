# R-Store base × 独立 App 去广告净化合集 · Loon 版

把多套去广告规则融合成**一个** Loon 原生插件，并通过 GitHub Actions 跟随上游自动更新：

- [zirawell/R-Store](https://github.com/zirawell/R-Store) 的 base 规则，转换为 Loon 语法；综合规则不再额外合并 blockAdsV2、Thelongdarkorg、MyBlockAds 或独立 filter 补充源；
- [ifflagged/Romeo](https://github.com/ifflagged/Romeo/tree/main/Modules/Loon) 的独立 App 插件（固定 commit 同步，替代原 AOOMEE 上游）；
- Romeo 没有完整等价版本的 7 个 AOOMEE 专项插件保留为本地快照（`sources/romeo_legacy/`），其两份远程脚本也已随仓库保存（`scripts/romeo_legacy/`），构建不再克隆或请求 AOOMEE 仓库；
- 原 zmjde 引用的 8 个 App/通用插件统一映射到 Romeo `Modules/Loon/Kelee/Official`，脚本与 JQ 依赖也从同一 Romeo commit 获取；不再单独克隆 zmjde 仓库。
- [RuCu6 高德地图插件](https://rucu6.pages.dev/Plugins/amap.lpx)（通过 Romeo GitHub 镜像同步；JS/JQ 依赖缓存到 `sources/amap/`，合并后使用仓库内资源地址）；
- [ddgksf2013 墨鱼手记瓜子影视规则](https://github.com/ifflagged/Romeo/blob/main/Modules/QuantumultX/ddgksf2013/Official/GuaZiVideoAds.conf)（与高德共用固定 Romeo commit；保留原有 QuanX → Loon 转换与规则优先级）；
- `fmz200/wool_scripts` 仅作为 CNFTP、小红书本地响应脚本的上游输入，不再导入其 blockAds 综合规则插件；
- [zirawell 支付宝小程序去广告合集](https://github.com/ifflagged/Romeo/tree/main/Modules/Loon/zirawell/Beta)（与其他 Romeo 来源共用固定 commit；只补充未覆盖的精确 Loon v2 Rewrite 规则）；
- [Kelee 微信公众号、微信小程序与微店去广告](https://github.com/ifflagged/Romeo/tree/main/Modules/Loon/Kelee)（三个插件纳入 Romeo 固定版本 App 槽；14 个响应脚本依赖逐一校验并固定到同一 commit，随综合插件合并）；
- [ddgksf2013 金十数据去广告](https://github.com/ifflagged/Romeo/blob/main/Modules/Loon/ddgksf2013/Beta/JinShiDataAds.lpx)（固定 Romeo commit 同步，无额外脚本依赖；与 base 已有的金十广告拦截规则按 base 优先去重）。
- [BruceWae KFC_AdBlock](https://github.com/BruceWae/my-loon-plugins/blob/main/Plugin/KFC_AdBlock.plugin)（KFC 广告路由及 AI 弹窗接口按实际响应结构返回空广告数据；保留其他 API 拦截与现有 KFC 路径规则，仅补充精准 splash 素材拦截，不添加整域 REJECT 或宽泛 `.*ad/` 规则）。

> **只装一个 allAdRewrite.plugin 就够了。** 综合规则以 R-Store base 为唯一规则源；保留的独立 App 插件按优先级补充各自专属功能。

## 优先级（核心规则）

以 R-Store 转换产物为 base，独立 App 插件优先级更高。高德地图设为 `priority=-1`（最高），其次为 Romeo 映射的原 zmjde App 槽 `0`、QuanX 单文件 App `1`、Romeo（原 AOOMEE 来源槽）`2`；两个历史合并槽共用同一个 Romeo commit 与映射清单，优先级只为兼容既有规则行为而保留；通用源按既有顺序。zirawell AlipayAdBlock 为 `8`（最低，仅补充高优先级来源未覆盖的精确 Loon v2 Rewrite）。AlipayAdBlock 中的 HelloBike 规则、旧式通配图片 mock 行、重复 Eleme 脚本、Rule 与 MITM 不重复导入；既有 base 规则和 MITM 范围保持优先。

## 产物一览

| 文件 | 作用 |
|---|---|
| allAdRewrite.plugin | 单插件自包含：开关 + 分流 + 重写 + 脚本 + MITM |
| tools/validate_plugin.py | 静态质量门禁：结构、MITM、动作、Argument、重复触发器与风险提示 |
| tests/test_source_guard.py | 上游来源防损坏测试：空响应、HTML、规则数量、必需插件 |
| tests/test_validate_plugin.py | 校验器单元测试 |
| tests/test_merge_plugins.py | 合并器集成测试：重复区块、reject 动作、TLD hostname、高德最高优先级与互补动作 |
| sources/amap/ | 高德上游插件、JS 与 3 份 JQ 依赖的可追溯缓存 |
| sources/alipayAdBlock/ | zirawell AlipayAdBlock 上游 Loon 插件缓存（固定 Romeo commit） |
| sources/romeo_legacy/ | Romeo 无完整等价版本的 7 个 AOOMEE 专项插件快照 |
| scripts/romeo_legacy/ | 随插件快照保存的两份远程脚本，避免继续依赖 AOOMEE Raw |
| 运行时外部依赖 | 拼多多脚本内部引用的 Kelee CDN 页面资源，单独登记并在同步时校验 |
| romeo_resource_map.json | AOOMEE 与原 zmjde 两批插件、Script/JQ 资源的唯一映射清单 |
| tools/stage_romeo_plugins.py | 按同一固定 Romeo commit 构建 AOOMEE 与原 zmjde 两个历史合并槽，并固定其运行时依赖 |
| tests/test_stage_romeo_plugins.py | Romeo 来源映射、快照完整性与旧脚本 URL 回归测试 |
| tools/source_guard.py | 上游响应/仓库结构完整性门禁，阻止 HTML 错误页、空文件和缺失源 |
| rule-provenance.json | 逐条 Rewrite/Script/Rule 来源、合并胜出/重复/覆盖关系与上游版本追溯 |
| Actions artifact：rule-diff.json | 每次同步生成的规则新增、删除、动作变化及上游版本差异报告（不在仓库长期留存） |
| tools/source_health_guard.py | 上游来源可靠性评分、来源追溯完整度与异常更新发布门禁 |
| Actions artifact：source-health.json | 每次生产同步的来源健康评分、规则变化幅度、警告与阻断原因报告（不在仓库长期留存） |
| tools/rule_risk_history.py | 对新增、删除、动作变化进行风险分级，并维护最近 30 次同步的来源变化趋势 |
| Actions artifact：rule-risk.json | 当前规则变更风险等级、逐条风险原因和来源评分关联（不在仓库长期留存） |
| rule-history.json | 最近 30 次成功生产同步的规则变化与来源趋势历史 |
| tools/audit_plugin.py | 基础只读审计全局 UDP/443、MITM 通配覆盖候选、Script URL 与错放 Rewrite Action |
| tools/deep_audit.py | 深度只读审计 Rewrite 宽泛匹配/动作冲突、MITM 字面守卫候选、Script URL 复用与触发类型，可输出 JSON/Markdown |
| optimization_invariants.json / optimization_output_invariants.json | 本地性能优化及最终产物结构的 fail-closed 不变量清单 |
| audits/ | 按阶段/批次保存优化审计记录；入口见 [审计索引](audits/README.md) |

当前产物统计由工作流自动维护：

<!-- AUTO_PLUGIN_STATS:START -->
**由 GitHub Actions 自动更新的最新产物统计**

| 区块 | 条目数 |
|---|---:|
| [Argument] | 18 |
| [Rule] | 719 |
| [Rewrite] | 2305 |
| [Script] | 323 |
| [MITM] hostname 条目 | 1204 |
| 唯一远程脚本 URL | 135 |
<!-- AUTO_PLUGIN_STATS:END -->

## 自动更新

GitHub Actions 每天北京时间 09:07 / 21:23 执行：转换 R-Store → 拉取独立 App 来源 → 合并去重 → 静态校验 → 更新本节统计 → 有变化才提交。

同步前会检查 base、AlipayAdBlock 的有效内容量与区块结构，并核对 Romeo（包含 AOOMEE 兼容槽、原 zmjde 8 个插件映射、3 个 Kelee 微信/微店插件、金十数据插件及其 14 个 Script 依赖）、AOOMEE 独有本地快照、瓜子影视和高德插件来源文件；原 AOOMEE 与 zmjde 两批插件、其运行时 Script/JQ 资源，以及瓜子影视、高德与 AlipayAdBlock 使用同一固定 Romeo commit，来源报告记录对应路径与 commit；高德依赖脚本/JQ 同步镜像至 `sources/amap/`，防止远程依赖失效。HTML 错误页、空/截断响应、缺失必需插件或规则量相对上次报告下降超过 60% 时会触发 fail-closed。构建先写入临时目录，完整合并并通过插件校验后才替换正式产物；失败不会覆盖上一版有效插件。`source-report.json` 记录克隆仓库的 commit SHA 与来源文件数量，便于追溯。第六阶段第一批新增 `rule-provenance.json`：逐条记录 Rewrite/Script 规则的来源组、优先级、最终输出位置及同语义重复来源；Rule 记录新增、精确重复、语义覆盖和 Frontier 安全保护排除原因，并附上游版本报告。第六阶段第二批为 Thelongdarkorg、Romeo（历史来源键 aoomee）、zmjde App 多文件来源补充了精确插件文件名、原始 1-based 行号和原始行文本；其他来源暂保留提取序号，后续再逐类补齐。第六阶段第三批新增 `tools/compare_rule_provenance.py`，每次同步前将新生成的追溯报告与上次已提交的报告比较，分别识别 Rewrite、Script、Rule 的新增、删除和可确定的动作变化，并记录上游 commit 变化。只有同一 matcher 在前后版本都唯一且动作不同，才归类为动作变化；多动作歧义会保守列为新增/删除，不猜测。差异报告仅上传为 Actions artifact，比较过程不修改规则或 MITM。该报告只描述合并过程，不证明规则在设备上的实际效果，也不改变正式 MITM/规则行为。第六阶段第四批增加来源可靠性评分与异常更新门禁：检查关键来源是否齐全、内容量与历史基线是否连续、高德依赖 SHA-256 是否完整、逐条来源追溯覆盖率，以及规则删除/动作变化/输出骤减幅度。高风险破坏性变化会暂停本轮发布并保留上一版正式插件；新增量异常仅生成自动诊断提示。来源健康报告仅上传为 Actions artifact，评分仅表示来源证据质量，不代表规则运行效果。该门禁不自动修改规则、MITM 或优先级。第六阶段第五批新增 `tools/rule_risk_history.py`：新增规则默认中风险，删除和动作变化默认高风险；来源可靠性偏低时可将新增项提升为高风险。每次成功同步保留最近 30 次变化快照，按来源累计新增、删除和动作变化数量，生成 `rule-risk.json`（仅作为 Actions artifact）与 `rule-history.json`（保留为下一轮同步的历史状态基线）。风险标签用于自动化分级与诊断，不证明规则有错，也不自动修改规则、MITM 或优先级。第七阶段第一批增加只读规则质量报告，定位宽泛 Rewrite、重复 matcher、交叉命中与 MITM/Script 覆盖候选；第七阶段第二十二批修正深度审计对旧式 Rewrite 的解析：此前只保留动作 token、丢弃动作参数，导致同一 matcher 下不同 JSON/JQ 操作被误判为同动作重复。现在保留完整动作表达式，并分别报告完全重复动作组、同 matcher 多操作组和跨动作类别冲突组；每组附逐条行号、动作类别与操作内容。该改进只提高审计精度，不改动任何生产规则或 MITM。第七阶段第二批开始按已确认的 App 主机范围收敛规则。555影视本批将两条泛主机 Rewrite/Script 触发器限制到上游明确声明的 `vip7.fzwdyy.cn`、`*.qyfxgd.cn`、`*.weilai555.com`、`*.ecoliving168.com`，保留原有动作、脚本、开关和 MITM，不影响其他来源。对应变更记录在 `rule-provenance.json` 的 `scope_adjustments` 中，并有跨域名正反向回归测试。 第七阶段第二批后续优化将懒人听书 `ClientAdvertList.action` 的全主机匹配限制到上游该接口明确声明的 `118.178.214.118` 与 `dapis.mting.info`；`display.wting.info` 仅用于独立 JPEG 规则，不纳入该接口 matcher。原有动作及两条精确规则保持不变，并加入上游声明漂移失败保护和正反向回归测试。

如果校验发现硬错误，工作流会失败并阻止提交。警告（例如重复触发器、全局 UDP/443、远程脚本风险）不会擅自删除规则，也不会阻止更新，需结合 Loon 实际运行情况判断。

每次定时、手动或 main 推送触发的同步构建还会上传一份 `deep-audit-sync` 深度审计报告（JSON + Markdown，保留 14 天）；可在对应 Actions 运行页的 Artifacts 中查看完整候选明细，不必从控制台日志中手动筛选。该报告只用于风险追踪，不会自动删改生产规则。

## 本地检查

    python3 -m unittest -v tests.test_validate_plugin tests.test_merge_plugins tests.test_source_guard tests.test_audit_plugin tests.test_deep_audit tests.test_amap_dependency_guard tests.test_compare_rule_provenance tests.test_source_health_guard tests.test_rule_risk_history tests.test_stage_romeo_plugins tests.test_amap_response_guard tests.test_xianyu_zhihu_route_guards
    python3 -m py_compile tools/merge_plugins.py tools/validate_plugin.py tools/source_guard.py tools/stage_romeo_plugins.py tools/audit_plugin.py tools/deep_audit.py tools/amap_dependency_guard.py tools/compare_rule_provenance.py tools/source_health_guard.py tools/rule_risk_history.py tools/rule_semantics.py tools/optimize_dushu365.py tools/convert_qx2loon.py tools/convert_filter_qx2loon.py
    python3 tools/validate_plugin.py allAdRewrite.plugin
    python3 tools/validate_plugin.py allAdRewrite.plugin --update-readme README.md
    python3 tools/validate_plugin.py allAdRewrite.plugin --check-remote
    python3 tools/audit_plugin.py allAdRewrite.plugin --summary-only
    python3 tools/deep_audit.py allAdRewrite.plugin --summary-only
    python3 tools/deep_audit.py allAdRewrite.plugin --json deep-audit.json --markdown deep-audit.md

--check-remote 会对最多 80 个唯一远程脚本 URL 发起 HEAD 检查，仅输出警告，不代表脚本逻辑已通过测试；部分 CDN 不支持 HEAD 或会限流。`tools/audit_plugin.py` 输出基础运行风险统计。`tools/deep_audit.py` 进一步输出 Rewrite 宽泛匹配、同匹配器多动作、MITM 未发现明显字面守卫的候选，以及 Script 触发器类型和远程 URL 复用报告；第五阶段第二批规范化正则中的转义 URL 分隔符，并区分域名限定、子域名通配、路径通配和无明确域名约束的 Rewrite，减少正常域名规则的误报。第五阶段第三批补充现代条件式 Rewrite 的正则边界识别，兼容未转义 URL 斜杠、正则 flags、`as m` 捕获别名、`&&`/`||` 条件以及数字型旧式动作（如 `302`），并继续保留无法识别的条目并生成兼容性警告。分类与解析结果仅用于审计，不自动删改规则。第五阶段第四批进一步按语义归类 Rewrite 动作，覆盖拒绝、重定向、响应模拟、响应正文改写、JSON 修改、请求正文改写和 Header 修改，并为可能改变业务响应/请求行为的动作生成自动诊断优先级与原因。动作分类是自动诊断线索，不代表规则有错；不自动删改规则。第五阶段第五批增加样本驱动的 Rewrite 交叉命中审计：为受限安全子集生成代表性 URL 样本，检查不同 matcher 是否可能命中同一 URL，并区分同阶段不同动作、同类动作、request/response 明确跨阶段命中，以及 legacy 语法无法确定阶段的歧义命中；复杂正则会跳过并记录为自动诊断警告。样本审计不是完整正则交集证明，也不推断 Loon 规则执行顺序，不自动修复或删改正式规则。第五阶段第六批进一步将 Rewrite 与 Script 的字面 URL 触发主机和 MITM hostname 做关联覆盖审计，识别未被正向 MITM 覆盖、被负向 hostname 排除、动态主机的稳定后缀能否被通配项覆盖，以及没有明显字面触发器引用的 MITM 正向项；纯 HTTP 和裸 IPv4 单独分类，不误报为应补入 MITM 的缺口。通配覆盖按子域语义核对，负向排除优先提示；Script 的远程脚本下载主机与脚本触发 URL 主机分开处理，不能把 CDN 下载域名误当作需要 MITM 的业务请求域名。结果仅为自动诊断候选，不自动添加或删除 MITM。第五阶段第七批在此基础上增加 MITM 必要性证据分级：区分被字面触发器覆盖、仅在规则文本中出现的间接/嵌入主机、动态或通用触发证据不足，以及未发现字面引用的候选；对未覆盖项进一步区分 HTTPS 明确候选与协议/matcher 歧义。通用 Script、动态主机、通配域和脚本/CDN 地址均保留不确定性，不把静态未引用等同于冗余。该分级仅用于自动诊断提示，不自动增删 hostname，也不生成删除建议。第五阶段第八批改进 MITM 主机提取：识别可选/动态端口、可选子域名和带稳定字面后缀的动态主机；仅把明确转义的点号视为域名标签边界，公共后缀及无法证明的复杂表达式继续保留歧义，不自动增删 MITM。

## 历史优化记录

阶段性优化说明已独立归档，避免 README 被长期变更日志淹没：详见 [历史记录索引](audits/README.md)，其中包含历史汇总与逐批专项审计报告。

## 安全边界

- 校验器只报告问题，不自动删改广告规则、QUIC 规则或 MITM hostname，避免静态工具造成漏拦截或 App 故障。
- 不允许无域名/应用范围限制的全局 UDP/443 REJECT：它会直接切断部分 DIRECT 网络路径；只保留有明确广告主机或 App 范围的 QUIC 拦截，并通过来源追溯记录安全排除。
- MITM hostname 检查覆盖格式、重复、已知必需主机；复杂 URL 正则的 MITM 覆盖关系仍需 Loon 日志和真实设备验证。
- 正则使用 Loon/ICU 语法，Python re 编译只作辅助提示，不能代替 Loon 解析器。
