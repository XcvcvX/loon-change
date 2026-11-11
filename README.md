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
| audit_plugin.py | 只读审计全局 UDP/443、MITM 通配覆盖候选、Script URL 与错放 Rewrite Action，不自动删改规则 |
| audit_runtime.py | 深度只读审计 Rewrite 宽泛/冲突候选、MITM 无字面守卫候选、Script 重复触发器与远程脚本健康检查 |
| test_audit_runtime.py | 深度运行时审计器单元测试 |

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

同步前会检查 R-Store、blockAdsV2、MyBlockAds 的有效内容量与区块结构，并核对 Thelongdarkorg、aoomee、zmjde、瓜子影视和高德插件来源文件；高德依赖脚本/JQ 同步镜像至 `sources/amap/`，防止远程依赖失效。HTML 错误页、空/截断响应、缺失必需插件或规则量相对上次报告下降超过 60% 时会触发 fail-closed。构建先写入临时目录，完整合并并通过插件校验后才替换正式产物；失败不会覆盖上一版有效插件。`source-report.json` 记录克隆仓库的 commit SHA 与来源文件数量，便于追溯。

如果校验发现硬错误，工作流会失败并阻止提交。警告（例如重复触发器、全局 UDP/443、远程脚本风险）不会擅自删除规则，也不会阻止更新，需结合 Loon 实际运行情况判断。

## 本地检查

    python3 -m unittest -v test_validate_plugin.py test_merge_plugins.py test_source_guard.py test_audit_plugin.py test_audit_runtime.py
    python3 -m py_compile merge_plugins.py validate_plugin.py source_guard.py audit_plugin.py audit_runtime.py convert_qx2loon.py convert_filter_qx2loon.py
    python3 validate_plugin.py allAdRewrite.plugin
    python3 validate_plugin.py allAdRewrite.plugin --update-readme README.md
    python3 validate_plugin.py allAdRewrite.plugin --check-remote
    python3 audit_plugin.py allAdRewrite.plugin --summary-only
    python3 audit_runtime.py allAdRewrite.plugin --output runtime-audit.json
    python3 audit_runtime.py allAdRewrite.plugin --check-remote --limit 80 --output runtime-audit-remote.json

--check-remote 会对最多 80 个唯一远程脚本 URL 发起 HEAD 检查，仅输出警告，不代表脚本逻辑已通过测试；部分 CDN 不支持 HEAD 或会限流。`audit_plugin.py` 输出全局 UDP/443、MITM 通配重叠候选、Script URL 与错放 Action 统计，不自动修改规则。`audit_runtime.py` 补充宽泛/冲突 Rewrite、MITM 无字面守卫候选、重复 Script 触发器审计；可选 `--check-remote` 对最多 80 个唯一脚本 URL 发起 HEAD 检查。深度报告由 Actions 作为 `loon-runtime-audit-report` artifact 上传。所有结果均为待人工复核的候选，不自动改写生产规则。

## 安全边界

- 校验器只报告问题，不自动删改广告规则、QUIC 规则或 MITM hostname，避免静态工具造成漏拦截或 App 故障。
- 全局 UDP/443 拦截可能影响 HTTP/3/QUIC。是否移除应结合实际网络和 App 测试决定；本次不会擅自改变用户已有规则。
- MITM hostname 检查覆盖格式、重复、已知必需主机；复杂 URL 正则的 MITM 覆盖关系仍需 Loon 日志和真实设备验证。
- 正则使用 Loon/ICU 语法，Python re 编译只作辅助提示，不能代替 Loon 解析器。
