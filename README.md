# R-Store × blockAdsV2 去广告净化合集 · Loon 版

把两套去广告规则融合成**一个** Loon 原生插件，并通过 GitHub Actions 跟随上游自动更新：

- [zirawell/R-Store](https://github.com/zirawell/R-Store) 的 **Quantumult X** 规则（重写 + 独立分流），先按 Loon 原生语法转换（作为 base）；
- [fmz200/wool_scripts](https://github.com/zirawell/R-Store) 的 **blockAdsV2.plugin**（本身已是 Loon 格式），再合并去重。

> **只装一个 `allAdRewrite.plugin` 就够了。** blockAdsV2 的 Rewrite/Script/Rule/Argument/MITM
> 已全部并入，R-Store 独立分流的规则也已补进 `[Rule]`，无需再装 blockAdsV2 或任何独立分流。

## 产物一览

| 文件 | 来源 | 作用 |
|---|---|---|
| `allAdRewrite.plugin` | R-Store 转换 + blockAdsV2 合并 + 分流补全 | 单插件自包含：开关 + 分流 + 重写 + 脚本 + MITM |

`allAdRewrite.plugin` 内含五个段：`[Argument]`（74 个开关）、`[Rule]`（3446 条）、
`[Rewrite]`、`[Script]`、`[MITM]`（1336 个主机）。

## 一、直接使用（不用自己搭仓库）

```
https://raw.githubusercontent.com/<用户名>/<仓库名>/main/allAdRewrite.plugin
```

Loon 里：**插件 → 右上角「+」→ 通过 URL 添加** → 粘贴地址。

> 必须开启 MitM 并信任 CA 证书，否则重写/脚本规则不生效。
> `[Rule]` 里的域名/IP 拦截属于连接层规则，不依赖 MitM 也会生效。

**不需要再单独订阅任何分流**：`[Rule]` 已 100% 覆盖 R-Store 原独立分流的 1435 条规则
（见第四节覆盖验证），装这一个插件即可，没有第二个文件要配。

## 二、自己搭一个自动更新的仓库

1. **新建 GitHub 仓库**（Public），上传本目录内容：

   ```
   allAdRewrite.plugin
   convert_qx2loon.py            # R-Store QuanX 重写 -> Loon（base 转换）
   merge_plugins.py              # 合并 blockAdsV2、去重、补全 R-Store 分流到 [Rule]
   validate_plugin.py            # 产物自检（工作流调用）
   sources/blockAdsV2.plugin     # blockAdsV2 本地副本（运行时默认在线抓取）
   .github/workflows/sync.yml
   README.md
   ```

   > `convert_filter_qx2loon.py` 已废弃——独立分流的转换与补全已并入 `merge_plugins.py`，
   > 工作流不再引用它，可删除。

2. **开启 Actions**：Settings → Actions → General → 勾选 *Read and write permissions*。

3. （可选）立即跑一次：Actions → *Sync R-Store + blockAdsV2* → **Run workflow**。

工作流每天北京时间 **09:07 / 21:23** 执行，步骤为：**转换 R-Store 重写 → 在线抓取
blockAdsV2 与 R-Store 分流、合并去重并补全 `[Rule]` → 自检 → 有变化才提交**。
没变化则跳过，不产生空提交。

> GitHub 定时是“尽力而为”，整点高负载可能延迟、偶尔漏跑；手动触发与定时互不影响，
> 一天两次 + 手动兜底，不会长期不更新。

## 三、手动更新

```bash
# 1) R-Store QuanX 重写 -> Loon（base）
python3 convert_qx2loon.py -o allAdRewrite.plugin

# 2) 合并 blockAdsV2 并补全 R-Store 分流（均在线抓取，含镜像回退），覆盖回写
python3 merge_plugins.py --base allAdRewrite.plugin --extra fetch --filter fetch --out allAdRewrite.plugin

# 3) 自检
python3 validate_plugin.py allAdRewrite.plugin
```

`merge_plugins.py` 的 `--filter` 可选：`fetch`（默认，在线补全分流）、本地路径、
`none`（不补全 `[Rule]`）。所有脚本只依赖 Python 标准库；`raw.githubusercontent.com`
不可达时自动回退 jsDelivr 镜像。

## 四、合并、去重与分流补全

### 4.1 Rewrite / Script 合并（Loon ↔ Loon）

以 R-Store 转换产物为 base，blockAdsV2 只做补充：

- **同正则 base 优先**：建立 base 全部 URL 正则集合（Rewrite + Script 一起），
  blockAdsV2 命中的正则一律跳过，仅补充 base 没有的；段内、跨段冲突统一处理。
- **正确识别 v1 脚本正则**：`http-response ^PAT ...` 的正则取第二个 token，
  不会被首词 `http-response` 折叠，保证跨新旧语法去重准确。
- **完全相同的行折叠**：逐字重复行只保留第一条，最终 `[Rule]`/Rewrite/Script 均无重复行。
- **blockAdsV2 残留 7 行 QuanX 旧写法分类处理**：3 行转 v2（beehive `reject_dict(200)`、
  vgtime/zhihu 两条 `redirect(302, ...)`），4 行丢弃（base 已覆盖或源损坏）。
- **MITM 主机收敛**：中间/前缀通配退化为 `*.最长字面后缀`；`souhu→sohu` 拼写纠错；
  裸 IP、通配 TLD、源损坏等 23 个无法安全收敛的主机丢弃，最终 1336 个主机全部合法。

### 4.2 分流补全到 `[Rule]`（替代独立分流）

blockAdsV2 自带的 `[Rule]` 并不完整覆盖 R-Store 独立分流，因此合并时额外做了一步：

1. 抓取 R-Store `allAdBlock.list`，转换为 Loon 规则（小写类型 → 大写、IP 类加 `no-resolve`）；
2. 对每条规则按**语义覆盖**判定是否已被当前 `[Rule]` 包含：
   - `DOMAIN`：精确相等，或被某条 `DOMAIN-SUFFIX`（含父后缀）/ `DOMAIN-KEYWORD` 覆盖；
   - `DOMAIN-SUFFIX`：存在相等或更宽的父后缀；
   - `DOMAIN-KEYWORD`：关键字相等；
   - `IP-CIDR` / `IP-CIDR6`：网段被相等或更宽的网段包含（`subnet_of`）；
3. 只追加未覆盖的规则，并动态更新索引以处理规则间的包含关系。

**实测结果**：R-Store 分流 1435 条，其中 856 条本就被 blockAdsV2 覆盖，**补入 579 条**；
最终 `[Rule]` 共 3446 条。独立复核（按段重新解析、不依赖固定行号）确认 1435 条
**100% 被覆盖、0 缺口**，故独立分流产物已停止生成、可安全删除。

最近一次合并量：Rewrite 1789 + 新增 869（跳过 524）；Script 304 + 新增 140（跳过 78）；
Rule 3446（含分流补入 579）；Argument 74；MITM 1336。

## 五、R-Store 重写转换做了什么（QuanX → Loon）

语义级映射，不是简单调换字段顺序：

| Quantumult X | Loon |
|---|---|
| `^re url reject` | `^re reject` |
| `^re url script-response-body <js>` | `[Script] http-response ^re script-path=<js>,requires-body=true` |
| `^re url response-body A response-body B` | `^re response-body-replace-regex A B` |
| `^re url jsonjq-response-body 'jq'` | `response if ${url} ~= /re/ then response.json.jq(\`jq\`)` |
| `^re url echo-response json echo-response URL` | `... then response.body.mock_file("json", "URL", 200)` |
| `^re url 302 URL`（含 `$1`） | `... as m then redirect(302, "...${m.1}...")` |
| `^re url request-header A request-header B` | `^re header-replace-regex <头名> ^.*$ <值>` |

关键点：

- **原子组降级**：`(?>...)` ICU 不支持，全部转 `(?:...)`。
- **脚本移出 rewrite**：Loon 脚本在 `[Script]` 段，用 `http-response` / `http-request`。
- **二进制脚本加 `binary-body-mode`**：`$response.body` 默认是字符串，声明
  `binary-body-mode=true` 才是 `Uint8Array`。protobuf 类脚本（`youtube`、`bilibiliProtoA`、
  `tiebaProto`、`spotify`、`baiduMap`）按字节读取，拿到字符串会解析失败、放空响应，
  表现为 App 一直转圈（如 YouTube 首页刷不出新视频）。转换器自动为这 5 个脚本加标记，
  并做启发式扫描覆盖未来新增。
- **新旧语法同段混用**：Loon 官方允许 Rewrite/Script 新旧语法共存，已验证规则保留原写法。
- **缺 TLD / 拼写纠错 / 漏写补全**：末段含数字判定缺 TLD 并从规则补全；单字符编辑
  可匹配规则时自动纠错（如 `*.souhu.com→*.sohu.com`、`aimai-guide.ele.me→waimai-guide.ele.me`）；
  规则主机未被 hostname 覆盖时补全（顺丰、飞猪、到家、苏宁等）。
- **生成后自检**：`validate_plugin.py` 独立校验非法 hostname、裸公共后缀、未知动作、
  二进制脚本标记、typo 复现、主机覆盖；发现硬错误即失败，阻止错误产物提交。

## 六、已知差异

- QuanX `reject` 返回 404，Loon `reject` 是直接断开；App 弹网络错误可改 `reject-200`。
- 脚本文件多为上游 QuanX 版 JS，但内嵌跨平台适配层（MagicJS 等），Loon 下自动走
  `$persistentStore` / `$httpClient` / `$notification` / `$done`；QuanX 专属调用在
  `isQuanX` 分支或类型守卫内，不会执行。个别 protobuf 脚本用到 `$utils.ungzip`，
  需 Loon Build ≥ 988。
- Spotify artistview 302 上游把原子组当子域名捕获，转换器已定向修正为显式捕获子域名。
- 1 条 `url-and-header` 复合匹配 Loon 无对应动作，已跳过。

## 七、常见问题

**1. 添加插件报 `Code=261 未能使用 UTF-8 打开 …lpx`**

文件本身没问题，是 Loon 本地缓存的下载坏了（大文件被截断）。解决：删除插件并彻底重启
Loon 再添加；或换 raw URL 形式（哈希不同强制重下），`.../refs/heads/main/x.plugin` 与
`.../main/x.plugin` 内容相同、不影响更新；最稳是放进 iCloud 的 `Loon/Plugins/` 目录直接填文件名。

**2. 到点没看到自动运行**

定时“尽力而为”，可能延迟漏跑，手动触发不影响定时；可在 Actions 手动 Run workflow。

**3. 我需要同时装 blockAdsV2 和这个合集吗？**

不需要。blockAdsV2 已完整并入，再装属于重复（一般无害，仅增加 MITM/脚本开销），
保留 `allAdRewrite.plugin` 一个即可。

**4. 某 App 一直转圈、刷不出新内容（如 YouTube 首页只有缓存图）**

多为 protobuf 脚本没拿到二进制 body，已通过 `binary-body-mode=true` 解决；更新到最新
插件即可，仍异常就先关掉该插件确认是否由它引起。

**5. 个别脚本报 `$utils.ungzip` 错误**

需 Loon Build ≥ 988，升级即可，不影响其他脚本。
