# R-Store 去广告规则 · Loon 版

把 [zirawell/R-Store](https://github.com/zirawell/R-Store) 的 Quantumult X 广告重写规则
（`Rule/QuanX/Adblock/All/rewrite/allAdRewrite.conf`）按 **Loon 原生语法**转换，
产出可直接订阅的 `allAdRewrite.plugin`，并通过 GitHub Actions 跟随上游自动更新。

## 一、直接使用（不用自己搭仓库）

订阅地址（把 `<你的仓库>` 换成实际地址）：

```
https://raw.githubusercontent.com/<用户名>/<仓库名>/main/allAdRewrite.plugin
```

Loon 里：**插件 → 右上角「+」→ 通过 URL 添加** → 粘贴上面的地址。

> 必须开启 MitM 并信任 CA 证书，否则所有重写/脚本规则都不生效。

## 二、自己搭一个自动更新的仓库

1. **新建 GitHub 仓库**（Public），把本目录下所有内容上传：

   ```
   allAdRewrite.plugin
   convert_qx2loon.py
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

## 五、已知差异

- QuanX 的 `reject` 返回 404，Loon 的 `reject` 是直接断开连接。
  若某 App 弹出网络错误，把对应条目改成 `reject-200`。
- 脚本文件本身仍是上游的 QuanX 版 JS，少数用到 `$prefs`、`$notification` 等
  QuanX 特有 API 的可能报错，可在 Loon 日志中查看。
- 有 1 条 `url-and-header` 复合匹配规则 Loon 无对应动作，已注释保留在文件末尾。
