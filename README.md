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
| [Rewrite] | 3318 |
| [Script] | 618 |
| [MITM] hostname 条目 | 1482 |
| 唯一远程脚本 URL | 199 |
<!-- AUTO_PLUGIN_STATS:END -->

## 自动更新

GitHub Actions 每天北京时间 09:07 / 21:23 执行：转换 R-Store → 拉取独立 App 来源 → 合并去重 → 静态校验 → 更新本节统计 → 有变化才提交。

同步前会检查 R-Store、blockAdsV2、MyBlockAds 的有效内容量与区块结构，并核对 Thelongdarkorg、aoomee、zmjde、瓜子影视和高德插件来源文件；高德依赖脚本/JQ 同步镜像至 `sources/amap/`，防止远程依赖失效。HTML 错误页、空/截断响应、缺失必需插件或规则量相对上次报告下降超过 60% 时会触发 fail-closed。构建先写入临时目录，完整合并并通过插件校验后才替换正式产物；失败不会覆盖上一版有效插件。`source-report.json` 记录克隆仓库的 commit SHA 与来源文件数量，便于追溯。第六阶段第一批新增 `rule-provenance.json`：逐条记录 Rewrite/Script 规则的来源组、优先级、最终输出位置及同语义重复来源；Rule 记录新增、精确重复、语义覆盖和 Frontier 安全保护排除原因，并附上游版本报告。第六阶段第二批为 Thelongdarkorg、aoomee、zmjde App 多文件来源补充了精确插件文件名、原始 1-based 行号和原始行文本；其他来源暂保留提取序号，后续再逐类补齐。第六阶段第三批新增 `compare_rule_provenance.py`，每次同步前将新生成的追溯报告与上次已提交的报告比较，分别识别 Rewrite、Script、Rule 的新增、删除和可确定的动作变化，并记录上游 commit 变化。只有同一 matcher 在前后版本都唯一且动作不同，才归类为动作变化；多动作歧义会保守列为新增/删除，不猜测。差异报告以 `rule-diff.json` 保留并上传 Actions artifact，比较过程不修改规则或 MITM。该报告只描述合并过程，不证明规则在设备上的实际效果，也不改变正式 MITM/规则行为。第六阶段第四批增加来源可靠性评分与异常更新门禁：检查关键来源是否齐全、内容量与历史基线是否连续、高德依赖 SHA-256 是否完整、逐条来源追溯覆盖率，以及规则删除/动作变化/输出骤减幅度。高风险破坏性变化会暂停本轮发布并保留上一版正式插件；新增量异常只提示复核。`source-health.json` 随生产运行上传并提交，评分仅表示来源证据质量，不代表规则运行效果。该门禁不自动修改规则、MITM 或优先级。第六阶段第五批新增 `rule_risk_history.py`：新增规则默认中风险，删除和动作变化默认高风险；来源可靠性偏低时可将新增项提升为高风险。每次成功同步保留最近 30 次变化快照，按来源累计新增、删除和动作变化数量，生成 `rule-risk.json` 与 `rule-history.json`。风险标签用于安排人工复核，不证明规则有错，也不自动修改规则、MITM 或优先级。第七阶段第一批增加只读规则质量报告，定位宽泛 Rewrite、重复 matcher、交叉命中与 MITM/Script 覆盖候选；第七阶段第二批开始按已确认的 App 主机范围收敛规则。555影视本批将两条泛主机 Rewrite/Script 触发器限制到上游明确声明的 `vip7.fzwdyy.cn`、`*.qyfxgd.cn`、`*.weilai555.com`、`*.ecoliving168.com`，保留原有动作、脚本、开关和 MITM，不影响其他来源。对应变更记录在 `rule-provenance.json` 的 `scope_adjustments` 中，并有跨域名正反向回归测试。 第七阶段第二批后续优化将懒人听书 `ClientAdvertList.action` 的全主机匹配限制到上游该接口明确声明的 `118.178.214.118` 与 `dapis.mting.info`；`display.wting.info` 仅用于独立 JPEG 规则，不纳入该接口 matcher。原有动作及两条精确规则保持不变，并加入上游声明漂移失败保护和正反向回归测试。

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


## 第七阶段第二批：QQ音乐备用 CDN 匹配范围收敛

- 将 QQ音乐 `music/common/upload/t_splash_info` 的备用 CDN 全主机 Rewrite 限制到专用 QQ音乐插件明确声明的 `y.gtimg.cn` 与 `music.y.qq.com`。
- 同时处理 blockAdsV2 与 Thelongdarkorg 两个重复来源，避免高优先级来源仍保留宽泛 matcher。
- 保留原有 `reject` 动作、精确 `y.gtimg.cn` 规则，以及 blockAdsV2 独立 IPv4 直连拦截规则。
- 不新增 MITM hostname，不改 Script、Rule、优先级或其他 App 规则。
- 增加正向/负向 host 测试，并在上游 hostname/MITM 声明漂移时 fail-closed。
- 静态测试不替代 QQ音乐真机启动页验证。

## 第七阶段第七批：修复孤立 MITM 主机清理的误保留

- 生产审计发现第六批目标的三个涨乐财富通专属主机仍留在 MITM：原因是合并器将 Generic、Cron 等非 HTTP 脚本的远程脚本下载 URL 误判为业务请求主机引用。
- Loon 官方 Script 语义中，Generic 为手动执行，Cron 按计划执行，Network Changed 在网络变化时执行；它们的 script-path 是脚本资源地址，不是 HTTP URL 触发器。
- 清理判断跳过 generic、cron、network-changed 非 HTTP 触发类型；继续检查 HTTP Rewrite / Request / Response Script 的 URL matcher。
- 保留无法静态判断且可能匹配目标主机的 HTTP matcher，继续 fail-closed；不改变任何 Rewrite、Script、Rule、优先级或其他 MITM 主机。
- 增加生产型回归测试：在存在 ICU 正则导致通用裁剪器保守保留的情况下，Generic/Cron/Network Changed 的远程脚本 URL 不再阻止三个已确认孤立主机的清理；其他主机仍保留。



## 第七阶段第八批：修复纯 HTTP 捕获组导致的 MITM 误保留

- 生产同步日志显示 MITM 自动裁剪数为 0；进一步定位到一条仅匹配 `http://www.vgtime.com` 的捕获组重定向规则。
- 旧逻辑只要在无法提取主机的 matcher 中发现 `http://`，就将其视为可能需要 MITM，错误保留了与该规则无关的三个涨乐财富通主机。
- 增加 HTTPS 能力判断：区分纯 `http://` 与 `https://`、`https?://` 等可匹配 HTTPS 的写法；同时仅检查触发器部分，排除 `then` 后和 `script-path` 中的脚本下载 URL。
- 继续对无法解析且可能匹配 HTTPS 的 matcher fail-closed；不改变 Rewrite/Script 规则及动作。
- 增加回归测试：纯 HTTP 捕获组不再阻止无关 MITM 清理；HTTPS 捕获组仍保留保守保护。


## 第七阶段第九批：避免纯 HTTP 宽泛捕获组误保留 MITM

- 生产验收发现：纯 HTTP 捕获组若位于 URL authority（例如 `^http://(.*)/...`），host 提取器会得到可匹配任意主机的 `(.*)`；特殊主机保留逻辑此前未先判断协议，导致无关 MITM 主机仍被保留。
- 特殊主机引用判断现在先确认 matcher 可能匹配 HTTPS，再检查 host；纯 HTTP matcher 不需要 TLS 解密，不能作为保留 MITM 的理由。
- 对 HTTPS 宽泛捕获组继续保守保留，避免误删可能实际使用的 MITM hostname。
- 增加 HTTP/HTTPS authority 捕获组正反向回归测试；不改变任何 Rewrite/Script 规则及动作。

- 本批验收要求：必须以 main 分支正式同步生成的 `allAdRewrite.plugin` 为准，确认目标主机确实移除且 HTTPS 真实引用仍保留。


## 第七阶段第十批：追踪残留 MITM 主机的保留来源

- 第九批合并后的正式同步已成功，但正式产物未变化，三个涨乐财富通主机仍保留。
- 本批增加只读诊断日志：逐个输出这三个主机被保留的具体 Rewrite/Script matcher、host 正则和保守回退原因。
- 不改变 MITM 保留/裁剪判断，不改变任何广告规则；待根据生产日志确认真实引用后再决定是否需要修复，避免误删真实依赖。


## 第七阶段第十一批：修复转义斜杠导致的 MITM 主机误判

- 首轮 CI 暴露路径可选分组的左括号会残留在 host zone 末尾；本次补充括号平衡处理及集成回归测试，只移除未闭合的尾部左括号，不触碰主机中合法的平衡分组。

- 第十批生产诊断确认，三个涨乐财富通主机被一条完全无关的 gateway.tuhu.cn HTTPS 规则误保留。
- 根因是 host 提取器只把未转义的 / 识别为 URL 路径起点；Loon 常见的 \/ 被当作主机正则继续读取，连同路径中的可选分组一起纳入 host 正则，最终触发过宽的保守回退。
- 本批让 host 提取器同时识别 / 和 \/ 为 authority/path 分界；新增集成回归测试，验证 gateway.tuhu.cn 仍保留、三个无关主机被移除。
- 不改变任何 Rewrite/Script 规则及动作；正式验收仍以同步生成的 allAdRewrite.plugin 为准。


## 第七阶段第十二批：排除不可能匹配 DNS 主机的 ICU 控制字符规则

- 第十一批正式同步后，三个目标主机仍被一条 KFC 广告路径 matcher 错误保留；生产诊断显示其 host zone 为 `res\\.kfc\\.com.\\cn`，Python 因不支持 ICU 的 `\\cX` 控制字符转义而进入保守回退。
- Loon 使用的 ICU 正则中，`\\cX` 表示控制字符；控制字符不可能出现在合法 DNS hostname 中，因此该 host matcher 不可能引用任何 MITM 主机。
- 仅在三个历史遗留主机的只读保留诊断中识别这一种 DNS 不可能匹配的控制字符形式；其他 Python/ICU 不兼容表达式（例如 `\\p{L}`）继续保守保留。
- 不修改 KFC 或其他任何广告 Rewrite/Script 规则及动作；增加集成回归测试，验证控制字符模式不再误保留三个目标主机，同时既有 ICU Unicode 属性模式仍保留真实可能命中的主机。
- 正式验收以同步日志及 main 分支生成的 `allAdRewrite.plugin` 为准。


## 第七阶段第十三批：兼容 http[s]? 协议前缀

- 第十二批正式同步后，三个目标 MITM 主机仍被七猫小说的一条无关 matcher 误保留。
- 生产日志确认 matcher 为 \`^http[s]?://magev6\\.if\\.qidian\\.com/...\`；现有主机提取器只识别 \`https?://\` 文本形式，未识别等价的 \`http[s]?://\` 写法，导致返回无法提取主机的保守分支。
- 扩展协议前缀识别，同时兼容 \`https?://\` 与 \`http[s]?://\`；不改变 URL matcher 本身或广告动作。
- 新增集成回归测试：七猫主机仍被正确保留，三个无关涨乐财富通主机不再因该 matcher 被保留。
- 其他无法安全解析的 HTTPS matcher 仍维持 fail-closed。
- 正式验收以同步日志和生产 \`allAdRewrite.plugin\` 为准。


## 第七阶段第十四批：识别主机字符类中的斜杠

- 第十三批合并后的正式同步已成功，但三个涨乐财富通专属 MITM 主机仍被一条穿山甲规则误保留。
- 生产诊断显示该规则的 host matcher 使用 \`[^\s/]*\.pangle\.cn\`；host 解析器此前把字符类内部的 \`/\` 错当成 URL path 起点，截断为不完整的 \`[^\s\`，触发 Python 正则失败和保守保留。
- 本批让 host 解析器跟踪正则字符类状态：只有字符类外的未转义或转义斜杠才作为 authority/path 边界。
- 增加集成回归测试：保留真实的 \`foo.pangle.cn\` MITM 引用，同时移除三个无关的涨乐财富通主机。
- 不修改穿山甲规则、广告动作或其他 MITM 声明；其他无法安全解析的 HTTPS matcher 仍 fail-closed。
- 正式验收以同步日志和生产 \`allAdRewrite.plugin\` 为准。


## 第七阶段第十五批：识别字符类开头的字面右方括号

- 第十四批已处理普通字符类中的斜杠，但正则字符类允许在开头（或否定符 `^` 后）把 `]` 作为普通成员，例如 `[]/]`、`[^]/]`。
- 旧扫描状态会把这个首位 `]` 误判为字符类结束符，随后把同一字符类中的 `/` 当作 URL path 边界，造成 host zone 再次被截断。
- 本批为字符类扫描增加首位成员状态：允许可选的 `^`，并将首位 `]` 按字面成员处理；转义括号继续按普通转义字符消费。
- 同时识别 ICU/POSIX 风格 `[:...:]`、`[....]`、`[=...=]` 子表达式的内部结束符，避免误关闭外层字符类。
- 新增正向集成回归测试，覆盖普通与否定字符类中首位 `]` 的情况，确保 `foo.pangle.cn` 保留、三个无关涨乐财富通主机被清理。
- 不修改任何广告 Rewrite/Script 规则、动作或 MITM 声明；无法安全解析的 HTTPS matcher 仍维持 fail-closed。
- 正式验收以 PR CI 和合并后的生产同步日志/产物为准。


## 第七阶段第十六批：修复上游 Rewrite 来源追溯错位

- 深度审计复核发现，Thelongdarkorg 来源在合并前会按条件过滤不可达 Rewrite（例如被更早请求阶段 reject 终止的 JD Lite 响应改写）；但来源追溯报告仍按未过滤的原始文件行序号映射，导致后续规则可能被标记为错误的插件文件/行号。
- 改为在逐个读取插件时同步记录每条 Rewrite 的原始文件名、行号和原文，并在 JD Lite 规则过滤时同步过滤来源记录；QQ 音乐范围收敛仍保留原始行来源。
- 新增多插件集成回归测试：前一个插件的 Rewrite 被过滤后，后续插件规则的来源文件、行号和原文仍准确对应。
- 仅修复 `rule-provenance.json` 的来源定位；不改变 Rewrite、Script、Rule、MITM、动作或优先级。

## 第七阶段第十七批：加固腾讯云 HTTPDNS 宽泛拦截安全门禁

- 复核腾讯云官方 HTTPDNS 文档：当前 HTTP API 使用 `119.29.29.98/d`，HTTPS API 使用 `119.29.29.99/d`；旧 `119.29.29.29` 已停止服务。`/d` 是域名解析接口，不是广告资源路径。
- 原安全排除同时要求 matcher 和 `reject(200)` 动作完全一致；若上游只把动作改成等价的 `reject`，宽泛规则就可能绕过排除并重新进入正式插件。
- 现在对该精确宽泛 matcher 不依赖动作别名，任何动作形式均记录为安全排除；仍保留其他 IP、其他路径和其他 matcher。
- 新增回归测试：`reject(200)` 与 `reject` 两种动作均被排除，`119.29.29.98/health` 等非目标路径仍按原逻辑保留。
- 本批不改动其他广告规则、MITM hostname、Script、Rule 或优先级；目的在于防止上游动作格式变化意外恢复对 HTTPDNS 的拦截。
## 第七阶段第十八批：排除芒果 TV 的宽泛非广告探测请求

- 复核 blockAdsV2 的芒果 TV 规则上下文：/?cmd=indexes 被上游明确标注为“无用请求”，而不是广告接口；其 matcher 却覆盖任意数字 IP、任意五位端口，可能误拒绝其他 App 使用相同路径的请求。
- 该 matcher 同时存在于 R-Store 转换基础规则和 blockAdsV2。现在仅按精确 matcher 排除两路来源，不依赖动作别名，避免上游调整为 reject、reject(404) 等形式后重新进入产物。
- 保留芒果 TV odin 的 channel/ads 与 skin/config 广告/配置接口，以及其他 cmd 路径；不扩大到其他 IP、端口或路径。
- 新增集成测试覆盖 base 与 block 两种来源、多种动作别名，并验证 cmd=health 和 odin 规则仍保留。
- 本批不修改 MITM hostname、Script、Rule 或其他广告规则；正式验收以 PR CI 和合并后的 main 分支产物为准。
## 第七阶段第十九批：清理已被同动作规则完整覆盖的语义重复项

- 深度审计发现 3 条跨来源 Rewrite：Thelong 的 `vv.video.qq.com/(diff|get)vmind` 与 base 的 `(?:diff|get)` 等价；aoomee 的 Soul `https` 子集与 Huazhu 可选 query 子集，均已被 base 同动作规则完整覆盖。
- 仅在来源规则 matcher 与 `reject-dict` 动作均精确符合审计白名单时排除；若动作发生变化则构建失败并要求复核，不做通用正则包含关系推断。
- 保留 base 的覆盖规则，不改变拒绝动作、HTTP/HTTPS 覆盖范围或 MITM；把源文件、来源段索引、原始行、覆盖 matcher 和原因写入来源追溯报告。
- 新增集成测试验证三条重复项被排除、三条 base 规则仍保留，并验证上游动作改变时触发失败保护。
- 本批不调整其他 Rewrite、Script、Rule、MITM 或优先级。


## 第七阶段第二十批：区分已证明覆盖的语义重复项与真实规则删除风险

- 第十九批正式同步后，规则差异报告正确记录 3 条来源 Rewrite 被移除，但风险报告将它们全部标记为高风险，未识别它们在来源追溯中已有 `excluded_semantic_duplicate` 状态和明确的保留覆盖 matcher。
- 风险分类现在只对 Rewrite 删除项执行精确来源行匹配；必须同时满足排除状态为 `excluded_semantic_duplicate`、来源原始行完全一致、且存在非空 `covered_by` matcher，才将该事件标为低风险并记录覆盖证据。
- 不使用模糊文本匹配或通用正则包含推断；没有精确来源证据、覆盖 matcher 缺失、动作变化或其他类型的删除仍维持高风险。
- 保留原始新增/删除数量和按来源历史计数，避免把“低风险”误写成“没有发生变化”。
- 新增正反向测试，并让正式同步流程运行风险分类单元测试。
- 本批只改进审计风险标签，不修改任何 Rewrite、Script、Rule、MITM hostname、动作或优先级。
