# R-Store × blockAdsV2 × 独立 App 去广告净化合集 · Loon 版

把多套去广告规则融合成**一个** Loon 原生插件，并通过 GitHub Actions 跟随上游自动更新：

- [zirawell/R-Store](https://github.com/zirawell/R-Store) 的 Quantumult X 规则（重写 + 独立分流），先转换为 Loon 语法；
- [fmz200/wool_scripts](https://github.com/fmz200/wool_scripts) 的 blockAdsV2.plugin；
- [Thelongdarkorg/loon-plugins](https://github.com/Thelongdarkorg/loon-plugins) 的细分 App 去广告插件；
- [aoomee/Loon-Adblock-Plugins](https://github.com/aoomee/Loon-Adblock-Plugins) 的独立 App 插件（含远程脚本与 Argument）；
- [zmjde/loon-plugins](https://github.com/zmjde/loon-plugins) 的 App 插件与通用过滤规则；
- [ddgksf2013 墨鱼手记](https://ddgksf2013.top/rewrite/GuaZiVideoAds.conf) 的瓜子影视规则；
- [RuCu6 MyBlockAds](https://rucu6.pages.dev/Plugins/myblockads.lpx)（在线失败回退仓库缓存）。

> **只装一个 allAdRewrite.plugin 就够了。** 各来源规则经过优先级合并，R-Store 独立分流也会补进 Rule。

## 优先级（核心规则）

以 R-Store 转换产物为 base，独立 App 插件优先级更高；同正则重复时按合并器的来源优先级处理。不同动作可能互补并存，不应仅凭相同 URL 正则就直接删除。

## 产物一览

| 文件 | 作用 |
|---|---|
| allAdRewrite.plugin | 单插件自包含：开关 + 分流 + 重写 + 脚本 + MITM |
| validate_plugin.py | 静态质量门禁：结构、MITM、动作、Argument、重复触发器与风险提示 |
| test_validate_plugin.py | 校验器单元测试 |\n| test_merge_plugins.py | 合并器集成测试：重复区块、reject 动作、TLD hostname |

当前产物统计由工作流自动维护：

<!-- AUTO_PLUGIN_STATS:START -->
统计将在下一次 GitHub Actions 构建时生成。
<!-- AUTO_PLUGIN_STATS:END -->

## 自动更新

GitHub Actions 每天北京时间 09:07 / 21:23 执行：转换 R-Store → 拉取独立 App 来源 → 合并去重 → 静态校验 → 更新本节统计 → 有变化才提交。

如果校验发现硬错误，工作流会失败并阻止提交。警告（例如重复触发器、全局 UDP/443、远程脚本风险）不会擅自删除规则，也不会阻止更新，需结合 Loon 实际运行情况判断。

## 本地检查

    python3 -m unittest -v test_validate_plugin.py test_merge_plugins.py\n    python3 -m py_compile merge_plugins.py validate_plugin.py convert_qx2loon.py convert_filter_qx2loon.py
    python3 validate_plugin.py allAdRewrite.plugin
    python3 validate_plugin.py allAdRewrite.plugin --update-readme README.md
    python3 validate_plugin.py allAdRewrite.plugin --check-remote

--check-remote 会对最多 80 个唯一远程脚本 URL 发起 HEAD 检查，仅输出警告，不代表脚本逻辑已通过测试；部分 CDN 不支持 HEAD 或会限流。

## 安全边界

- 校验器只报告问题，不自动删改广告规则、QUIC 规则或 MITM hostname，避免静态工具造成漏拦截或 App 故障。
- 全局 UDP/443 拦截可能影响 HTTP/3/QUIC。是否移除应结合实际网络和 App 测试决定；本次不会擅自改变用户已有规则。
- MITM hostname 检查覆盖格式、重复、已知必需主机；复杂 URL 正则的 MITM 覆盖关系仍需 Loon 日志和真实设备验证。
- 正则使用 Loon/ICU 语法，Python re 编译只作辅助提示，不能代替 Loon 解析器。
