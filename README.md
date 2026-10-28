# R-Store 去广告规则 · Loon 版

把 [zirawell/R-Store](https://github.com/zirawell/R-Store) 的 Quantumult X 去广告规则
按 **Loon 原生语法**转换，并通过 GitHub Actions 跟随上游自动更新。

上游有两套规则，本仓库产出两套各自独立的 Loon 产物：

| 上游（QuanX） | 本仓库产物 | 作用 |
|---|---|---|
| `rewrite/allAdRewrite.conf` | `allAdRewrite.plugin` | 重写 + 脚本（拦内容层广告） |
| `filter/allAdBlock.list` | `allAdBlock-Loon.list` / `.plugin` | 分流规则（拦域名/IP 层广告） |

## 一、直接使用（不用自己搭仓库）

### 重写规则插件

```
https://raw.githubusercontent.com/<用户名>/<仓库名>/main/allAdRewrite.plugin
```

Loon 里：**插件 → 右上角「+」→ 通过 URL 添加** → 粘贴上面的地址。

> 必须开启 MitM 并信任 CA 证书，否则所有重写/脚本规则都不生效。

### 分流规则

分流规则**不需要 MitM**，两种方式任选：

**方式 A：规则订阅（推荐，位置可控）**

在 Loon 主配置的 `[Rule]` 段里加一行，**放在 FINAL 之前**：

```ini
[Rule]
https://raw.githubusercontent.com/<用户名>/<仓库名>/main/allAdBlock-Loon.list,REJECT
...
FINAL,DIRECT
```

**方式 B：插件**

把 `allAdBlock-Loon.plugin` 也按上面的方式添加为插件，规则会自动合并。
（方式 A 能自己决定规则先后顺序，更稳妥。）

## 二、自己搭一个自动更新的仓库

1. **新建 GitHub 仓库**（Public），把本目录下所有内容上传：

   ```
   allAdRewrite.plugin
   allAdBlock-Loon.list
   allAdBlock-Loon.plugin
   convert_qx2loon.py                # 重写规则转换
   convert_filter_qx2loon.py         # 分流规则转换
   validate_plugin.py                # 产物自检（工作流会调用）
   .github/workflows/sync.yml
   README.md
   ```

2. **开启 Actions**：仓库 → Settings → Actions → General →
   勾选 *Read and write permissions*，保存。

3. （可选）立即跑一次：Actions → *Sync R-Store Adblock* → **Run workflow**。

之后每天北京时间 **09:07 / 21:23** 自动检查上游（已错开整点，降低被延迟概率）；
**有变化才提交**，没变化则跳过，不会产生空提交。

> 注意：GitHub 的定时任务是“尽力而为”，整点高负载时可能延迟、偶尔漏跑；
> 手动触发（Run workflow）与定时互不影响。一天两次 + 手动兜底，不会长期不更新。

### 订阅地址

```
https://raw.githubusercontent.com/<你的用户名>/<你的仓库名>/main/allAdRewrite.plugin
```

## 三、手动更新

```bash
# 拉取上游最新规则并转换
python3 convert_qx2loon.py -o allAdRewrite.plugin

# 或转换本地已有的 QuanX 规则文件
python3 convert_qx2loon.py -i allAdRewrite.conf -o allAdRewrite.plugin
```

转换脚本只依赖 Python 标准库。上游 `raw.githubusercontent.com` 不可达时，
会自动回退到 jsDelivr 镜像。

## 四、转换做了什么

不是简单的字段顺序调换，而是按 Loon 语法做语义级映射：

| Quantumult X | Loon |
|---|---|
| `^re url reject` | `^re reject` |
| `^re url script-response-body <js>` | `[Script] http-response ^re script-path=<js>,requires-body=true` |
| `^re url response-body A response-body B` | `^re response-body-replace-regex A B` |
| `^re url jsonjq-response-body 'jq'` | `response if ${url} ~= /re/ then response.json.jq(\`jq\`)` |
| `^re url echo-response json echo-response URL` | `... then response.body.mock_file("json", "URL", 200)` |
| `^re url 302 URL`（含 `$1`） | `... as m then redirect(302, "...${m.1}...")` |
| `^re url request-header A request-header B` | `^re header-replace-regex <头名> ^.*$ <值>` |

几个关键点：

- **原子组降级**：`(?>...)` 在 Loon（ICU 正则）中不被支持，全部转为 `(?:...)`。
- **脚本移出 rewrite**：Loon 的脚本是 `[Script]` 段的 `http-response` / `http-request`，
  不是 QuanX 那种写在 rewrite 行内的 `url script-response-body`。
- **二进制脚本加 `binary-body-mode`**：Loon 给脚本的 `$response.body` 默认是字符串，
  只有声明 `binary-body-mode=true` 才是 `Uint8Array`。protobuf 类脚本（`youtube`、
  `bilibiliProtoA`、`tiebaProto`、`spotify`、`baiduMap`）按字节读取，若拿到字符串会
  解析失败、放空响应，表现为 App 一直转圈（如 YouTube 首页刷不出新视频）。转换器会
  自动为这 5 个脚本加 `binary-body-mode=true`，并对内容做启发式扫描以覆盖未来新增。
- **jq / mock / 302 走新语法**：legacy 语法按空格切分参数，而 jq 表达式必然含空格，
  用 `\x20` 不可靠；Loon 官方文档明确允许新旧语法在同一 `[Rewrite]` 段混用。
- **MITM 域名收敛**：Loon 只支持 `*.` 前缀通配，中间通配符统一收敛为 `*.主域`。
- **缺 TLD 主机名自动修复**：上游个别 hostname 漏写顶级域（如 `img.yun.01zhuanche`，
  应为 `img.yun.01zhuanche.com`）。真实 TLD 只含字母，故末段含数字即判定为缺 TLD，
  转换器会从规则里找到对应的完整域名补全；无法补全的丢弃，避免写入无效 hostname。
- **生成后自检**：`validate_plugin.py` 会独立校验产物（非法 hostname / 裸公共后缀 /
  未知动作 / 二进制脚本是否带 `binary-body-mode`），工作流中一旦发现硬错误即失败，
  阻止错误产物被提交。

### 分流规则的转换

QuanX 用**小写**类型名和策略，Loon 用 Surge 风格的**大写**：

| Quantumult X | Loon |
|---|---|
| `host, x.com, reject` | `DOMAIN, x.com, REJECT` |
| `host-suffix, x.com, reject` | `DOMAIN-SUFFIX, x.com, REJECT` |
| `host-keyword, kw, reject` | `DOMAIN-KEYWORD, kw, REJECT` |
| `ip-cidr, 1.2.3.4/32, reject` | `IP-CIDR, 1.2.3.4/32, REJECT, no-resolve` |
| `ip6-cidr, ::/128, reject` | `IP-CIDR6, ::/128, REJECT, no-resolve` |

**为什么直接导入 QuanX 版识别不全**：Loon 不认识 `host` / `host-suffix` /
`ip-cidr` 这类小写类型名，整条规则会被忽略。

**为什么不直接照抄作者自己的 Surge 版**：Surge 版每条规则都带
`extended-matching, pre-matching`，这两个是 **Surge 专有参数，Loon 并不支持**，
照抄同样会导致规则解析失败。这里只保留 Loon 官方文档明确支持的 `no-resolve`
（用于 IP 类规则，避免多余的 DNS 查询）。

## 五、已知差异

- QuanX 的 `reject` 返回 404，Loon 的 `reject` 是直接断开连接。
  若某 App 弹出网络错误，把对应条目改成 `reject-200`。
- 脚本文件本身仍是上游的 QuanX 版 JS，但绝大多数内嵌了跨平台适配层（MagicJS 或
  等价框架），在 Loon 下会自动走 `$persistentStore` / `$httpClient` /
  `$notification` / `$done`；`$prefs`、`$task`、`$notify` 等 QuanX 专属调用
  只存在于 `isQuanX` 分支或 `typeof $task` 守卫内，Loon 下不会执行。
  个别 protobuf 脚本（如网易云）用到 `$utils.ungzip`，需 Loon Build ≥ 988，
  旧版报错时升级 Loon 即可。
- Spotify artistview 302 规则上游把原子组当子域名捕获（`$1` 实际是端口组），
  转换器已定向修正为显式捕获子域名、端口组非捕获。
- 有 1 条 `url-and-header` 复合匹配规则 Loon 无对应动作，已注释保留在文件末尾。

## 六、常见问题

**1. 添加插件时报 `Code=261 未能使用文本编码 UTF-8 打开文件 …lpx`**

插件文件本身没问题，是 Loon 本地缓存的那份下载坏了（大文件下载被截断，或一次
偶发的网络/代理干扰）。Loon 按 URL 哈希缓存，会复用坏文件。解决办法任选：

- 删掉该插件，**彻底关闭 Loon 后重开**，再添加；
- 或换一种 raw URL 形式（哈希不同，强制重新下载），把
  `.../refs/heads/main/allAdRewrite.plugin` 改成 `.../main/allAdRewrite.plugin`，
  二者内容完全相同、都不影响更新；
- 最稳：把插件存到 iCloud 云盘的 `Loon/Plugins/` 目录，添加时直接填文件名。

**2. 到点没看到自动运行**

GitHub 定时是“尽力而为”，可能延迟或漏跑，手动触发也不影响定时。已把时间错开
整点（09:07 / 21:23）；若仍不放心，可在 Actions 页面手动 **Run workflow**。

**3. 多个去广告插件是否冲突**

本合集已覆盖高德、百度地图、拼多多、滴滴等，若你另外单独装了这些 App 的插件，
属于重复（一般无害，只是重复处理、增加开销），可按需禁用，避免互相覆盖。

**4. 个别脚本（如网易云）报 `$utils.ungzip` 相关错误**

该 API 需 Loon Build ≥ 988，升级 Loon 即可，不影响其他脚本。

**5. 某 App 一直转圈、刷不出新内容（如 YouTube 首页只有缓存图）**

多为 protobuf 脚本没拿到二进制 body。已通过给 `youtube` / `bilibiliProtoA` /
`tiebaProto` / `spotify` / `baiduMap` 加 `binary-body-mode=true` 解决。若你是旧版
插件，更新到最新即可；更新后仍异常，先在 Loon 里关掉该插件确认是否由它引起。
