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
   .github/workflows/sync.yml
   README.md
   ```

2. **开启 Actions**：仓库 → Settings → Actions → General →
   勾选 *Read and write permissions*，保存。

3. （可选）立即跑一次：Actions → *Sync R-Store Adblock* → **Run workflow**。

之后每天北京时间 09:00 / 21:00 自动检查上游；**有变化才提交**，
没变化则跳过，不会产生空提交。

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
- **jq / mock / 302 走新语法**：legacy 语法按空格切分参数，而 jq 表达式必然含空格，
  用 `\x20` 不可靠；Loon 官方文档明确允许新旧语法在同一 `[Rewrite]` 段混用。
- **MITM 域名收敛**：Loon 只支持 `*.` 前缀通配，中间通配符统一收敛为 `*.主域`。

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
- 脚本文件本身仍是上游的 QuanX 版 JS，少数用到 `$prefs`、`$notification` 等
  QuanX 特有 API 的可能报错，可在 Loon 日志中查看。
- 有 1 条 `url-and-header` 复合匹配规则 Loon 无对应动作，已注释保留在文件末尾。
