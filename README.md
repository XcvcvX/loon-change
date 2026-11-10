# R-Store × blockAdsV2 × 独立 App 去广告净化合集 · Loon 版

把多套去广告规则融合成**一个** Loon 原生插件，并通过 GitHub Actions 跟随上游自动更新：

- [zirawell/R-Store](https://github.com/zirawell/R-Store) 的 **Quantumult X** 规则（重写 + 独立分流），先按 Loon 原生语法转换，作为合并 **base**；
- [fmz200/wool_scripts](https://github.com/fmz200/wool_scripts) 的 **blockAdsV2.plugin**（本身已是 Loon 格式），合并去重；
- [Thelongdarkorg/loon-plugins](https://github.com/Thelongdarkorg/loon-plugins) 的 **29 个细分 App 去广告插件**（标准 Loon v1、零远程脚本），并入去重；
- [aoomee/Loon-Adblock-Plugins](https://github.com/aoomee/Loon-Adblock-Plugins) 的 **27 个独立 App 插件**（`.plugin`/`.lpx`，含远程脚本与 `[Argument]`），并入去重；
- [zmjde/loon-plugins](https://github.com/zmjde/loon-plugins) 的 **8 个 `.lpx`**：滴滴、拼多多、闲鱼、淘宝、什么值得买 5 个 App 插件（完整并入、替换重复），HTTPDNS 拦截器、广告平台拦截器、可莉广告过滤器（以 base 优先、只补不覆盖）；
- [ddgksf2013 墨鱼手记](https://ddgksf2013.top/rewrite/GuaZiVideoAds.conf) 的 **瓜子影视 `.conf`**（QuanX 单文件，脚本内转 Loon，专属 App 完整并入、24 host 纳入 MITM）；
- yfamilys 的 **adultraplus**（清洗后只取 reject 家族，剔除破解/重定向私货）。

> **只装一个 `allAdRewrite.plugin` 就够了。** 各来源的 Rewrite/Script/Rule/Argument/MITM
> 已全部并入，R-Store 独立分流也已补进 `[Rule]`，无需再装任何独立 App 插件或单独分流。

## 优先级（核心规则）

以 R-Store 转换产物为 base，但**独立 App 插件优先级最高**；同正则重复时，App 插件替换
base / blockAdsV2 / adultraplus 的对应行。数字小 = 优先级高：

| 优先级 | 来源 | 说明 |
|---|---|---|
| 0 | **zmjde App（滴滴/拼多多/闲鱼/淘宝/什么值得买）** | 完整并入，同正则覆盖 aoomee |
| 1 | **qx 单文件 App（瓜子影视）** | 脚本内转 Loon，完整并入 |
| 2 | **aoomee** | 同正则覆盖 Thelongdarkorg |
| 3 | **Thelongdarkorg** | 独立 App 插件 |
| 4 | R-Store（base） | QuanX → Loon 转换产物 |
| 5 | blockAdsV2 | 综合源 |
| 6 | **zmjde 通用（HTTPDNS/广告平台/可莉过滤器）** | base 优先，只补不覆盖 |
| 7 | adultraplus | 清洗后只取 reject 家族 |

- **同正则同动作**：按优先级保留高优先级那条，其余替换。
- **同正则互补动作**：不同动作（如 jq 改 body + header-del 删响应头）**并存**，不互相覆盖。
- 拒绝家族（reject / reject-200 / reject-dict / reject-img 等）视为同一语义签名折叠。
- zmjde 通用插件即使字符串不同，若已被更宽的 `DOMAIN-SUFFIX`/`IP-CIDR` 规则语义覆盖也去重（实测 67 条全部已覆盖、0 真缺失）。

## 产物一览

| 文件 | 作用 |
|---|---|
| `allAdRewrite.plugin` | 单插件自包含：开关 + 分流 + 重写 + 脚本 + MITM |

当前 `allAdRewrite.plugin` 含五个段：`[Argument]`（91 个开关）、`[Rule]`（3450 条）、
`[Rewrite]`（3836 条）、`[Script]`（959 条）、`[MITM]`（1615 个主机，具体 1516 + 标准通配 99）。

## 一、直接使用（不用自己搭仓库）

```
https://raw.githubusercontent.com/<用户名>/<仓库名>/main/allAdRewrite.plugin
```

Loon 里：**插件 → 右上角「+」→ 通过 URL 添加** → 粘贴地址。

> 必须开启 MitM 并信任 CA 证书，否则 HTTPS 重写/脚本规则不生效。
> `[Rule]` 里的域名/IP 拦截属于连接层规则，不依赖 MitM 也会生效。

## 二、自己搭一个自动更新的仓库

1. **新建 GitHub 仓库**（Public），上传本目录内容：

   ```
   allAdRewrite.plugin
   convert_qx2loon.py            # R-Store QuanX 重写 -> Loon（base 转换）
   merge_plugins.py              # 多来源合并、优先级去重、分流补全、MITM 自愈
   validate_plugin.py            # 产物自检（工作流调用）
   .github/workflows/sync.yml
   README.md
   ```

2. **开启 Actions**：Settings → Actions → General → 勾选 *Read and write permissions*。

3. （可选）立即跑一次：Actions → *Sync multi-source ad-block plugins* → **Run workflow**。

工作流每天北京时间 **09:07 / 21:23** 执行，步骤为：**转换 R-Store 重写 → clone
Thelongdarkorg、clone aoomee、clone zmjde、下载瓜子 .conf、在线抓取 blockAdsV2/adultraplus/R-Store 分流，
按优先级合并去重并补全 `[Rule]` → 自检 → 有变化才提交**。没变化则跳过，不产生空提交。

> 每次运行都重新 `git clone --depth 1` 拉取 aoomee、Thelongdarkorg、zmjde，并重新下载瓜子 .conf，
> 因此独立 App 插件的更新会自动并入。若 clone/下载失败，整个合并失败并阻止提交，
> 不会静默产出缺来源的版本。
>
> **提交触发看最终合并产物**：`git diff` 判定对象是 `allAdRewrite.plugin` 整体，
> 任一来源（含 zmjde、瓜子）导致它变化都会提交，**不要求 base 单独变化**。

## 三、手动更新

```bash
# 0) 拉取独立 App 插件
git clone --depth 1 https://github.com/Thelongdarkorg/loon-plugins.git /tmp/loon-plugins
git clone --depth 1 https://github.com/aoomee/Loon-Adblock-Plugins.git /tmp/aoomee
git clone --depth 1 https://github.com/zmjde/loon-plugins.git /tmp/zmjde
curl -fsSL -A "surge" https://ddgksf2013.top/rewrite/GuaZiVideoAds.conf -o /tmp/GuaZiVideoAds.conf

# 1) R-Store QuanX 重写 -> Loon（base）
python3 convert_qx2loon.py -o allAdRewrite.plugin

# 2) 按优先级合并全部来源并补全 R-Store 分流（在线抓取，含镜像回退），覆盖回写
python3 merge_plugins.py --base allAdRewrite.plugin --extra fetch --filter fetch \
  --apps /tmp/loon-plugins --aoomee /tmp/aoomee --zmjde /tmp/zmjde \
  --qxapp /tmp/GuaZiVideoAds.conf --mix fetch --out allAdRewrite.plugin

# 3) 自检
python3 validate_plugin.py allAdRewrite.plugin
```

`merge_plugins.py` 常用参数：`--extra`（blockAdsV2：`fetch` 或本地路径）、
`--filter`（R-Store 分流：`fetch` 默认 / 本地路径 / `none`）、`--apps`（Thelongdarkorg 目录）、
`--aoomee`（aoomee 目录）、`--zmjde`（zmjde 目录）、`--qxapp`（QuanX 单文件 .conf，可重复）、
`--mix`（adultraplus：`fetch` 或本地路径）。
所有脚本只依赖 Python 标准库；`raw.githubusercontent.com` 不可达时自动回退 jsDelivr 镜像。

## 四、合并、去重与 MITM 自愈

### 4.1 Rewrite / Script 优先级合并

- **统一优先级合并器**：八来源按位置顺序（base→block→zmjde通用→mix→Thelongdarkorg→aoomee→qx单文件→zmjdeApp）
  喂入，按规范化 URL 正则 + 动作签名判定覆盖；App 插件（zmjde App>qx 单文件>aoomee>Thelongdarkorg）同正则替换综合源。
- **QuanX 单文件 App（.conf）**：解析 `hostname=` 与 `^PAT url ...` 行，把 `jsonjq-response-body 'jq'`
  转成 Loon `response if ... then response.json.jq(`jq`)`，正则 relit 成 `/.../`、反引号转义；未识别动作不乱转。
- **互补动作并存**：拒绝家族折叠为一个签名；其余动作按 `(动作名, 完整动作)` 独立存储，
  同正则的 jq 改 body、header-del 等不同动作全部保留。
- **正确识别 v1/v2 语法**：v1（`^正则 动作`）与 v2（`... then ...`）的正则统一归一化，
  跨语法去重准确；`http-response ^PAT ...` 的正则取第二个 token，不被首词折叠。
- **Shadowrocket 风格转换**：`^regex url reject` / `url reject-dict` 去掉 Loon 不支持的
  `url` 关键字；大写旧动作（REJECT/REJECT-DICT 等）归一为官方小写。
- **无守卫行保留**：`generic` / `cron` 全局脚本（无 URL 守卫）按脚本 URL 独立保留，
  不参与正则去重。

### 4.2 MITM 收敛与自愈（只收明确 host，不凭空整域通配）

- **只接受两类明确 host**：① 具体域名（无通配）；② 上游明确声明的标准 `*.后缀`
  （开头 `*.`、其余无通配）。均通过 `HOST_OK` 格式校验与真实 TLD 白名单。
- **不做中间/前缀通配的整域退化**：形如 `m*.amap.com`、`*.xima.*` 的守卫，不再退化成
  `*.域` 整域通配。整域通配会把"窄路径规则"扩大成对整域所有子域强制 MITM，一旦该域
  SSL Pinning 就会握手失败、搞挂核心功能（amemv 故障即源于此，见本节末尾）。
- **无法安全收敛的条目**：用守卫真实 host 反查（`host_wildcard_resolve`，标签级匹配、
  不臆造 TLD），**只接受具体 host、过滤通配结果**，反查到几个就保留几个；查不到则丢弃。
  裸 IP、通配 IP、源损坏截断条目同样丢弃。
- **TLD 白名单**：静态白名单覆盖常见 TLD，并补入实际出现的 `so` / `group` / `ltd`，
  避免合法域名被误丢。
- **自愈只补具体 host**：扫描最终 Rewrite + Script 守卫，对未覆盖的**具体 host** 补全
  （脚本段 `http(s)-request/response` 同样扫描，不漏段）；守卫退化出的整域通配**不补**。
- **覆盖口径**：当前 3933 条 HTTPS 路径规则被 MITM 覆盖；194 条仅整域通配守卫的规则
  主动放弃（对应 50 个 `*.域`，全为广告/埋点路径）。这些域若 Pinning，旧机制本就 MITM
  失败、规则无法生效，放弃零损失；若不 Pinning，则仅这部分路径广告不拦截，App 功能不受影响。
- **证书绑定域主动 pass**：`amemv.com` 做了 SSL Pinning，强制 MITM 会握手失败（请求记录
  "MITM Failed"、0 字节），导致抖音核心 API 与长连接全断、私信无法收发。脚本用
  `_MITM_SKIP_DOMAINS` + `mitm_skip_host` 在收集与自愈环节统一过滤，amemv 整体不进 MITM
  （从源头 pass，不用负向 `-` 语法），相关域名直连、私信恢复。
- **ChatGPT 故障同样源头 pass**：R-Store 源在 `ios.chat.openai.com` 规则上已自带警告
  "可能导致新版本无法使用"。该 host 进 MITM 后，ChatGPT App 证书校验失败、弹"网络配置问题"
  且无法对话（系统 CA 已信任，属 App 层校验）。已把 `ios.chat.openai.com` 加入
  `_MITM_SKIP_DOMAINS`，从收集与自愈环节 pass、直连恢复；原 `app_support_status` 规则保留
  但 HTTPS 下不生效、无害。
- **7 个上游警告域批量源头 pass**：R-Store 源对多个证书绑定域自带「⚠️ 已无法 MITM / 可能导致
  App 功能不可用」警告。已将 7 个具体 host 加入 `_MITM_SKIP_DOMAINS`：`mobilepaas.abchina.com.cn`
  （农行，0 规则动作、纯解密）、`images.cib.com.cn`（兴业）、`elife.icbc.com.cn`（工行）、
  `openapi.boc.cn`（中行）、`res.cc.cmbimg.com`（招行）、`wcmp.189.cn`（电信）、`m.ctrip.com`
  （携程）。这些域 pinning，开屏/广告规则在握手失败下本就不生效，pass 零广告损失并避免手机银行、
  携程、电信 App 故障；对应规则保留但 HTTPS 下不生效、无害。
- **无动作 host 自动裁剪**：新增 `prune_unused_mitm`，在自愈后按最终 Rewrite/Script 守卫集合
  反向裁剪——移除不服务任何规则、仅解密的冗余 hostname（上游规则被去重后的残留声明）。已验证裁剪
  不新增任何覆盖缺口（守卫具体 host 仍被覆盖），非 MITM 四段 md5 不变。综合上述 pass，MITM
  1708→1475（具体 1392 + 标准通配 83）。
- **闲鱼/淘宝/什么值得买/可莉并入**：3 个 App 插件的 16 个具体 host 全部纳入 MITM；可莉过滤器的
  中间通配（`pangolin-sdk-toutiao*`、`api-mifit*`）经守卫反查命中具体 host 保留，`lfd?`/`sfd?`
  等无对应规则的残留通配反查为空、安全丢弃（自动裁剪亦兜底）。
- **守卫提取顺序无关化**：修复 `guard_hosts_from_lines` 的一个顺序敏感缺陷——同一 host 同时存在
  `https?` 规则与纯 `http` 规则时，旧逻辑可能因后处理的纯 http 规则把该 host 误判为"仅明文"而从
  TLS 守卫集合排除，导致其 HTTPS 广告规则漏生效。改为纯 http 规则不参与 https 集合，只要被任一
  https/https? 规则守卫就纳入。
- **瓜子影视 host 防误裁**：修复 `prune_unused_mitm` 的一个假阴性——瓜子规则守卫是
  `(?:api|sdapi|newapi|hyperf|oldapi)\.[a-z0-9]+\.com`（OR + 随机域名），守卫提取无法静态解析出
  具体 host，导致 24 个 host 被误判为"无动作"裁剪、规则在却无法解密而失效。已验证 24 个 host 都被
  规则守卫匹配，在构造需要集合时把 qxapp 权威 hostname 补入，裁剪不再误删。本轮 MITM 1475→1512
  （具体 1429 + 标准通配 83），0 非标准通配、既有 pinning 域零回归。
- **裸斜杠截断修复（系统性，影响 359 条规则）**：adultraplus 原始 URL Rewrite 含裸 `/`（如
  `^https?://app\.api\.ke\.com/.../bootpage reject`），旧 `convert_legacy_line` 把它包进 v2
  `/.../` 时未转义内部裸 `/`，而 `_read_v2_regex` 遇到第一个裸 `/` 即认为模式结束，导致这 359 条
  规则全部坍缩成同一 key `^https?:`、被优先级合并去重成一条而静默丢失。新增 `escape_slash_for_v2`
  转义裸 `/`→`\/`（保留已有转义），三处构造 `/.../` 全部应用；Rewrite 3646→3836（+190）。
- **prune 重构为正则匹配 + materialize（消除守卫退化假阴性）**：旧裁剪依赖 `guard_hosts_from_lines`
  退化集合，对端口分组 `(:\d+)?`、OR 分组、字符类随机域名（瓜子同款）假阴性，误裁具体 host 与标准
  通配。重构后用每条规则的完整 host 正则直接 fullmatch 候选 host；区分窄模式（含长度≥3 字面标签，
  先剔除字符类防否定字符类伪窄）与宽泛模式（`.*`/`.+?`/纯结构，不参与判定）。新增 `materialize_host`
  把正则通配替换成合法占位、并用原模式验证生成可信样本（OR 分组经 `expand_or_patterns` 全分支展开，
  可靠率 99.9%，损坏/IP 跳过）；标准通配 `*.X` 覆盖被保留具体 host、或其来源窄模式样本落在 X 子域
  即保留。重构后具体 host 零误裁，6 个被误裁通配（ahhhhfs/xbwpys/fuliapps/pipiapps/xiangjiaoapps/
  xiangxiangapps）恢复，qyfxgd/hitv 仅被否定字符类伪窄匹配、正确裁剪。
- **全量内容级零丢失复核**：以生产相同口径对全部源文件逐条做语义对比（非字符串级）。Rewrite/Script：
  源 6954 条 → 最终 4795 条，按 `(entry_regex, action_key)` 对比 **0 缺失**，2159 条差异全部是等价
  去重；Rule：源 3947 条 → 3450 条，精确保留 3386、语义覆盖 556、frontier 有意放行 5（保护抖音私信）、
  **真丢失 0**。除上述两个已修复的系统性 bug 外，无其他影响去广告的规则被静默精简。本轮 MITM 1512→1615
  （具体 1516 + 标准通配 99），validate 0 错误 0 警告，合法负向项 `-i.vip.iqiyi.com` 保留。

### 4.3 分流补全到 `[Rule]`

1. 抓取 R-Store `allAdBlock.list`，转换为 Loon 规则（小写类型 → 大写、IP 类加 `no-resolve`）；
2. 对每条规则按**语义覆盖**判定是否已被当前 `[Rule]` 包含：
   - `DOMAIN`：精确相等，或被 `DOMAIN-SUFFIX`（含父后缀）/ `DOMAIN-KEYWORD` 覆盖；
   - `DOMAIN-SUFFIX`：存在相等或更宽的父后缀；
   - `DOMAIN-KEYWORD`：关键字相等；
   - `IP-CIDR` / `IP-CIDR6`：网段被相等或更宽的网段包含（`subnet_of`）；
3. 组合逻辑（`AND` / `OR` / `URL-REGEX`）保守处理，精确去重后全部保留。
- aoomee 的小写规则类型/策略（`domain`/`ip-cidr`/`reject`/`direct` 等）统一归一化；
  IP-CIDR（/32）缺 `no-resolve` 自动补全。

## 五、R-Store 重写转换做了什么（QuanX → Loon）

语义级映射，不是简单调换字段顺序：

| Quantumult X | Loon |
|---|---|
| `^re url reject` | `^re reject` |
| `^re url script-response-body <js>` | `[Script] http-response ^re script-path=<js>,requires-body=true` |
| `^re url response-body A response-body B` | `^re response-body-replace-regex A B` |
| `^re url jsonjq-response-body 'jq'` | `response if ${url} ~= /re/ then response.json.jq(\`jq\`)` |
| `^re url 302 URL`（含 `$1`） | `... as m then redirect(302, "...${m.1}...")` |
| `^re url request-header A request-header B` | `^re header-replace-regex <头名> ^.*$ <值>` |

关键点：

- **原子组降级**：`(?>...)` ICU 不支持，全部转 `(?:...)`。
- **脚本移出 rewrite**：Loon 脚本在 `[Script]` 段，用 `http-response` / `http-request`。
- **二进制脚本加 `binary-body-mode`**：protobuf 类脚本按字节读取，声明
  `binary-body-mode=true` 才是 `Uint8Array`，否则解析失败、放空响应、App 一直转圈。
- **新旧语法同段混用**：Loon 官方允许 Rewrite/Script 新旧语法共存。
- **生成后自检**：`validate_plugin.py` 独立校验非法 hostname、裸公共后缀、未知动作、
  二进制脚本标记、主机覆盖；发现硬错误即失败，阻止错误产物提交。

## 六、已知差异与边界

- QuanX `reject` 返回 404，Loon `reject` 是直接断开；App 弹网络错误可改 `reject-200`。
- **裸 IP / IP 段**：官方 MITM hostname 只认域名（靠 SNI 判断解密），不接受 IP。
  官方 `[IP Rewrite]`（Build 1007+）是 TUN 层整 IPv4 精确匹配（不接受 CIDR/IPv6），
  动作仅 reflect/reject/drop，不能跑脚本、不能按路径/端口，无法等价替代
  「IP + 路径 + reject-dict/脚本」。故保留 21 条 IP 守卫（明文 HTTP 可命中，
  HTTPS 直连难解密但无害），不往 MITM 塞非法 IP。
- 脚本文件多为上游 QuanX 版 JS，内嵌跨平台适配层（MagicJS 等），Loon 下自动走
  `$persistentStore` / `$httpClient` / `$notification` / `$done`。
- 无守卫的 MITM hostname（上游规则被去重后的残留声明，仅多解密、无规则动作）已由
  `prune_unused_mitm` 在合并时自动裁剪，不进入最终产物；详见 4.2 节。
- **整域通配不凭空补**：脚本不再把通配守卫（`.+\.x.com`、`m*.x.com`）退化成整域
  `*.x.com` 强制 MITM，也不通过自愈补这类整域通配。仅保留上游明确写的标准 `*.后缀`，
  其余用守卫反查具体 host、查不到即丢弃。这样从根本上避免 Pinning 域被强制解密而握手失败
  （amemv 故障的架构成因）；代价是 192 条整域通配广告路径不拦截，App 核心功能不受影响。
- **抖音私信故障的两层修复**（现象：能收到 APNs 推送、但收发不了实时消息——推送走苹果
  系统通道、不经过 App 长连接）：
  1. **Rule 层 frontier 放行**：Frontier 是字节系 WebSocket 长连接网关（如
     `wss://frontier-im.douyin.com/ws/v2`），不是广告域名。上游 blockAdsV2 与 R-Store
     filter 原本 REJECT 共 6 条 frontier 规则，merge 在 `add_rule` 用 `is_frontier_guard`
     （含 frontier 即保护）跳过。
  2. **MITM 层 amemv 源头 pass（真正根因）**：`amemv.com`（含 `api.amemv.com` 核心 API 与
     `frontier-aweme-*.amemv.com` 长连接）做了 SSL Pinning，上游 hostname 与守卫退化出的
     `amemv.com`、`*.amemv.com` 强制 MITM 会握手失败（请求记录 "MITM Failed"、0 字节），
     核心功能全断。merge 用 `mitm_skip_host` 在收集与自愈环节统一过滤，amemv 整体不进
     MITM、直连恢复。两层均脚本层生效、自动更新不回退。

## 七、常见问题

**1. 添加插件报 `Code=261 未能使用 UTF-8 打开 …lpx`**

文件本身没问题，是 Loon 本地缓存下载坏了（大文件被截断）。删除插件并彻底重启 Loon
再添加；或换 raw URL 形式强制重下；最稳是放进 iCloud 的 `Loon/Plugins/` 目录直接填文件名。

**2. 到点没看到自动运行**

定时“尽力而为”，可能延迟漏跑，手动触发不影响定时；可在 Actions 手动 Run workflow。

**3. 我需要同时装独立 App 插件和这个合集吗？**

不需要。zmjde（滴滴/拼多多/闲鱼/淘宝/什么值得买）、瓜子影视、aoomee、Thelongdarkorg 等独立 App 插件都已按优先级完整并入，
再装属于重复（一般无害，仅增加 MITM/脚本开销），保留 `allAdRewrite.plugin` 一个即可。

**4. 某 App 一直转圈、刷不出内容**

多为 protobuf 脚本没拿到二进制 body，已通过 `binary-body-mode=true` 解决；更新到最新
插件即可，仍异常就先关掉该插件确认是否由它引起。

**5. 自动更新会拉取 aoomee、zmjde、瓜子吗？**

会。工作流每次运行都重新 clone aoomee、Thelongdarkorg、zmjde、重新下载瓜子 .conf，并通过
`--aoomee` / `--apps` / `--zmjde` / `--qxapp` 传入合并，独立 App 插件的更新自动生效。

**6. base 没更新、但其他来源更新了，会提交吗？**

会。提交判定看最终合并产物 `allAdRewrite.plugin` 的整体变化，任一来源（含 zmjde、瓜子等）
让它变化都会提交，不要求 base 单独变化；全部来源都无变化才跳过。

**7. 抖音私信收发不了、但有推送通知**

根因是 `amemv.com` 证书绑定（SSL Pinning）被强制 MITM 导致握手失败，另有 frontier 长连接
REJECT 规则的误杀（两层修复见"六、已知差异与边界"）。更新到含 `mitm_skip_host` 与
`is_frontier_guard` 保护的最新插件后，**移除本地 `-*.amemv.com` 临时绕过**，在 Loon 重新
加载插件并彻底重启抖音即可验证；APNs 推送正常正是系统通道与 App 长连接相互独立的典型表现。

**8. ChatGPT 弹"网络配置问题"、无法对话**

根因是 `ios.chat.openai.com` 被强制 MITM，App 层证书校验失败（R-Store 源对该域名本就有
"可能导致新版本无法使用"的警告）。更新到把该域加入 `_MITM_SKIP_DOMAINS` 的最新插件后，
**移除本地 `-*.openai.com` 临时绕过**，重新加载并彻底重启 ChatGPT 即可；可先关闭整个 MITM
验证，能对话即确认是该域名问题。

**9. 手机银行/银联/携程/电信 App 异常，或担心多余解密**

R-Store 上游对 7 个证书绑定域（农行、兴业、工行、中行、招行、电信、携程）自带「⚠️ 已无法
MITM / 可能导致功能不可用」警告，最新插件已把它们源头 pass，并自动裁剪所有不服务规则、仅解密的
冗余 host（MITM 1708→1475）。这些域的开屏/广告规则在 pinning 下本就不生效，pass 零广告损失。
若某 App 仍异常，可在 Loon 请求记录里看是否有对应域名 "MITM Failed"，把具体域名反馈以便补充
`_MITM_SKIP_DOMAINS`；不建议自行整域 `-` 以免误伤其他不 pinning 的子域。

**10. 闲鱼 / 淘宝 / 什么值得买去广告怎么生效？**

三者的 App 插件已作为最高优先级完整并入（含远程脚本、jq 文件），更新到最新插件后重新加载即可，
无需再装独立插件。可莉广告过滤器则按"去重补充"并入——只补合集里没有的规则，已覆盖的不重复添加。

> （注：部分内容由豆包 AI 生成）