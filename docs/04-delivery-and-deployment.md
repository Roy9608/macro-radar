# 04 · 分发与部署：邮件为主，微信可选（含 PushPlus 配置教程）

分发是系统的**确定性半场**：同样的 HTML 和名单，必须得到同样的结果。
本文讲怎么部署、怎么填配置、以及一路踩过的坑。

## 一、通道选择：邮件为主

| 通道 | 适用 | 依赖 | 建议 |
|---|---|---|---|
| **邮件（SMTP）** | 全球通用，默认主线 | 任一支持 SMTP 的邮箱 | ✅ 默认用这个 |
| PushPlus（微信） | 中国境内读者，手机直达 | pushplus.plus 账号 + 实名 | 可选，见第四节教程 |
| Webhook（Slack/Discord/飞书/Telegram） | 团队/群组 | 各自 webhook URL | 自行扩展（`send.py` 结构易于加一个分支） |

**为什么要邮件优先**：HTML 卡片在邮件客户端能保持较完整的样式，
且不依赖任何第三方账号体系；PushPlus 在中国体验极好（微信内直接渲染 HTML），
但对中国大陆以外的用户没有意义。

## 二、配置

### 1. SMTP 配置 `config/smtp.json`

```json
{
  "smtp_host": "smtp.example.com",
  "smtp_port": 465,
  "use_ssl": true,
  "sender": "you@example.com",
  "auth_code": "your_smtp_auth_code",
  "sender_name": "MACRO RADAR",
  "subject_prefix": "[MacroRadar] "
}
```

- `auth_code` 是邮箱服务商的**授权码**（不是登录密码）；
  QQ 邮箱在「设置 → 账户 → POP3/SMTP 服务」里生成；
- 该文件**永远不要提交到仓库**——仓库里只有 `smtp.example.json`；
- 想更安全：把 `auth_code` 改为从环境变量读取（`os.environ`），改 `send.py` 一行即可。

### 2. 订阅名单 `data/subscribers.csv`

```csv
nickname,status,pushplus_token,email,channels
alice,enabled,YOUR_PUSHPLUS_TOKEN,,daily,t1,flash,weekly
bob,enabled,,bob@example.com,daily,weekly
carol,disabled,,,
```

过滤规则（`send.py --subscribers` 已实现，不是"调度层自己做"）：

```
① 跳过空行（表格编辑残留）
② 只保留 status=enabled
③ 只保留 channels 列包含本频道的行（--channel daily|t1|flash|weekly）
④ 有 pushplus_token → 微信组；有 email → 邮件组；两者都有 → 两边都发
⑤ channels 为空的单元格 = 未订阅任何频道（安全默认：空白不当作"全部"）
```

自查方式：`--dry-run` 会返回 `subscribers` 统计（`total / enabled / matched /
blank_rows_skipped`），`matched` 比你预期少时，先看 ② ③ ⑤ 三条规则。

## 三、发送与自检

```bash
# 1) 只检查不发送（推荐每次改完配置先跑这个）
python scripts/send.py --title "MacroRadar · daily" \
  --html demo/output/daily-en.html --dry-run

# 2) 邮件发送
python scripts/send.py --title "MacroRadar · daily" \
  --html demo/output/daily-en.html --mail bob@example.com

# 3) 微信（PushPlus）发送
python scripts/send.py --title "MacroRadar · daily" \
  --html demo/output/daily-en.html --push YOUR_PUSHPLUS_TOKEN
```

`send.py` 输出 JSON：`{"ok": true/false, "results": [...]}`，
**退出码 0 = 全部成功，1 = 有失败**。把退出码当完成判据，
不要用"屏幕上看起来发出去了"当判据。

## 四、PushPlus 配置教程（中国用户可选）

1. 打开 [pushplus.plus](https://www.pushplus.plus/)，用微信扫码注册；
2. **完成实名认证**——未实名的账号调用接口会返回 `code=905` 并被拒；
3. 在「一对一推送 / 我的」页面复制 **token**（32 位）；
4. 填入订阅表的 `pushplus_token` 列（或命令行 `--push`）；
5. 关键参数：`content` 必须是**整段 HTML**、`template="html"`
   （`send.py` 已处理），标题单独走 `title` 字段。

**注意**：PushPlus 是第三方服务，token 泄露 = 别人可以给你推送任意内容。
按凭据对待：放配置/环境变量，不要写进代码或文档。

## 五、已踩过的坑（部署必读）

| 坑 | 症状 | 对策 |
|---|---|---|
| **部署 ≠ 流程结束** | 网页部署成功，但摘要卡片没发出去 | 把"分发成功（退出码 0）"作为流程的最后一步，不可省略 |
| **夏令时 / 冬令时** | 数据发布时刻随美东 DST 移动 1 小时 | 调度固定 RRULE，但**发布后+30min 的快报要自检**：触发时校验当前时刻是否匹配应有推送时刻，不匹配则自我修正 |
| **未收盘数据** | 最新一根数值持续变化 | 只用已收盘 / 已发布的数据 |
| **空记录行** | 名单最后一行空字段导致报错 | 过滤时跳过无字段值的行 |
| **相对路径** | 调度器 cwd 不同，脚本找不到文件 | 脚本内一律用 `Path(__file__).resolve()` 推导绝对路径 |
| **中文主题乱码** | 邮件主题显示乱码 | 用 `email.header.Header(subject, "utf-8")` 编码（`send.py` 已处理） |
| **HTML 被当纯文本** | 微信里看到一堆标签 | PushPlus 必须 `template="html"` |
| **重复推送** | 同一内容发两遍 | 四条产品线职责边界写死（见 docs/01），避免同一事件被两条线各推一次 |

## 六、最小部署路径（从零到能跑）

```bash
git clone <this-repo> && cd macro-radar
python demo/render_card.py --all                      # ① 无网无密钥，先看渲染结果
python scripts/send.py --html demo/output/daily-en.html --dry-run   # ② 校验发送链路
cp config/smtp.example.json config/smtp.json          # ③ 填自己的 SMTP
cp data/subscribers.example.csv data/subscribers.csv  # ④ 填自己的名单
python scripts/send.py --title "MacroRadar · test" \
  --html demo/output/daily-en.html --mail you@example.com           # ⑤ 真实发一封给自己
```

能收到第 ⑤ 步的邮件，系统就算落地；剩下的只是把调度接上。

### 调度示例（按**你的本地时间**填）

```bash
# Linux / macOS —— crontab -e
0 7  * * 1-5  cd ~/macro-radar && python scripts/send.py --title "MacroRadar · daily"  --html reports/daily.html  --subscribers data/subscribers.csv --channel daily
0 9  * * 1-5  cd ~/macro-radar && python scripts/send.py --title "MacroRadar · T-1"    --html reports/t1.html     --subscribers data/subscribers.csv --channel t1
0 9  * * 6    cd ~/macro-radar && python scripts/send.py --title "MacroRadar · weekly" --html reports/weekly.html --subscribers data/subscribers.csv --channel weekly
```

```powershell
# Windows 任务计划程序（schtasks）
schtasks /create /tn "MacroRadar-Daily" /sc weekly /d MON,TUE,WED,THU,FRI /st 07:00 ^
  /tr "python C:\macro-radar\scripts\send.py --html C:\macro-radar\reports\daily.html --subscribers C:\macro-radar\data\subscribers.csv --channel daily"
```

**数据快报不写死在调度里**：它锚定"发布时刻 +30min"，由研究腿在数据日动态触发；
硬编码时刻在夏令时切换后必然错位（这正是上面第七节要处理的问题）。

上表时刻是**本地时间**——先跑 `tools/tz_convert.py --utc-offset <你的偏移> --plan`
看现成的北京时间在你这里是否落在作息内。

## 七、时区与作息：把系统搬到**你的**时钟上

**一个必须先认清的事实**：美国宏观数据锚定在**美东时间**（08:30 / 10:30 / 14:00 ET）。
系统里写死的调度是**北京时间**（生产环境在中国）。这两件事对非中国读者会同时错位。

### 1. 同一场发布，在不同读者的时钟上

以 2026-09-30 的 PCE 为例（数据来自 `tools/tz_convert.py` 实跑）：

| 读者所在时区 | 看到 PCE 发布的时刻 |
|---|---|
| 北京 UTC+8 | 2026-09-30 **20:30** |
| 纽约 UTC-4 | 2026-09-30 **08:30**（等于源锚点） |
| 伦敦 UTC+1 | 2026-09-30 **13:30** |

FOMC 利率决议更极端：美东 14:00 = **北京时间次日 02:00**
（`2026-10-28 14:00 ET` → 北京 `2026-10-29 02:00`）。
"T-1 事件提醒"这个产品的存在理由，正是这场决议落在了亚洲读者的深夜。

### 2. 三条现成命令

```bash
python tools/tz_convert.py --verify                    # 日历自洽性：ET ↔ 北京逐条对账（实测 105/105 一致）
python tools/tz_convert.py --utc-offset -4 --events    # 未来事件在我这里的时刻
python tools/tz_convert.py --utc-offset 1  --plan      # 我的作息该怎么排
```

`--plan` 的判断标准很朴素：**本地 07:00–22:00 = 契合，其余报警**。实测两个例子：

| 读者 | 每日日报（北京 07:00） | 判断 | 工具建议 |
|---|---|---|---|
| 纽约 UTC-4 | 本地 **19:00** | 契合（收盘后 3 小时，合理） | 保持不变 |
| 伦敦 UTC+1 | 本地 **00:00** | 偏离作息 | 改为本地 09:00（≈北京 16:00） |

### 3. 落地原则（三句话）

1. **调度设在本地时间**：cron / 任务计划 / 宿主平台里直接填你的本地时刻，
   **不要改代码**——系统的四条产品线不关心自己几点被触发；
2. **数据锚在美东时间**：事件时刻永远以 ET 为准（日历里同时存 `date_et` 与 `date_bj`，
   `--verify` 就是拿这两者互相对账）；
3. **夏令时不用手工维护**：每个事件自带 `EST`/`EDT` 标记，换季时 `--verify` 一跑就知道有没有错位；
   若用 `--iana`（需要系统 tz 数据库或 `pip install tzdata`）可自动处理，否则用 `--utc-offset` 固定偏移。

> Windows 用户注意：`zoneinfo` 需要 tz 数据库，缺失时本工具会给出明确提示并建议改用 `--utc-offset`
> （实测报错信息与三条替代路径均已验证）。
