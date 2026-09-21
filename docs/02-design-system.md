# 02 · 设计系统：一张卡片，一套规则

卡片是这个系统的门面。它必须做到三件事：**扫一眼能看到重点**、
**不用猜颜色什么意思**、**换内容不换骨架**。

## 一、设计令牌（Design Tokens）

| 令牌 | 值 | 用途 |
|---|---|---|
| 页面底色 | `#f2f4f8` 浅灰 | 卡片外底 |
| 卡片 | `#ffffff` + 圆角 `12px` + 阴影 `0 2px 12px rgba(15,30,75,.08)` | 主体 |
| 卡片宽度 | `max-width: 520px` | 手机端一屏可读；桌面端不至于拉成横幅 |
| 头部渐变 | `linear-gradient(135deg,#0f1e4b 0%,#1e3a8a 55%,#1d4ed8 100%)` | 品牌区（深蓝=权威感，不用亮色，避免与语义色抢注意力） |
| 字体栈 | `-apple-system,'PingFang SC','Microsoft YaHei',sans-serif` | 中英混排都能落到本地字体 |

## 二、语义色：「左侧色条 + 浅底」四态

所有分区都用同一个结构：`border-left:4px solid <深色>` + `background:<浅底>` + `<深色>` 标题。

| 语义 | 色条/文字 | 浅底 | 用在哪 |
|---|---|---|---|
| 鹰派 / 风险 | `#dc2626` | `#fef2f2` | 加息风险升温、通胀超预期、数据偏强 |
| 中性 / 关注 | `#b45309` | `#fffbeb` | 待观察、双刃剑、事件预告 |
| 鸽派 / 利好 | `#047857` | `#f0fdf4` | 降息预期、风险偏好回升 |
| 信息 / 背景 | `#1d4ed8` | `#eff6ff` | 机制解释、背景交代 |

**颜色的含义是固定的**，不随内容重要性变化——否则读者每次都要重新解码。

## 三、涨跌配色：**必须按受众切换**（不是一个常数）

涨跌配色不是审美选择，而是**地区约定**——而且各地区恰好相反：

| 地区 | 涨 | 跌 | 说明 |
|---|---|---|---|
| 中国内地及港澳台地区、日本、韩国 | **红** `#dc2626` | **绿** `#047857` | 东亚习惯 |
| 美国、欧洲等 | **绿** `#047857` | **红** `#dc2626` | 欧美习惯 |

**同一组数字、两种约定，含义完全相反**——把中国习惯的卡片发给纽约读者，
他会把上涨读成下跌。这是本项目里最容易造成实质误读的一个细节。

实现（`demo/render_card.py`，已实测两种约定）：

```python
CONVENTIONS = {"cn": ("#dc2626", "#047857"), "west": ("#047857", "#dc2626")}

def resolve_convention(fx):
    conv = fx.get("color_convention", "auto")     # auto | cn | west
    if conv in CONVENTIONS:
        return conv
    return "cn" if fx.get("locale", "zh") == "zh" else "west"
```

- fixture 里 `"color_convention": "auto"` → 中文卡红涨绿跌、英文卡绿涨红跌（当前默认）；
- 需要强制某一种时写 `"cn"` 或 `"west"`；
- **实测结果**：同一份 2026-09-21 数据，`daily-zh.html` 中 `+1.14%` 为红、`daily-en.html` 中为绿。

美股 / 美债收益率 / 美元 / 黄金 / BTC / VIX **在同一张卡内统一适用同一条约定**——
混合约定（有的涨红、有的涨绿）是最容易被忽略的可用性缺陷。

卡片头部还会渲染 `"timezone_label"`（如 `UTC-4 · New York`），
让读者任何时候都知道自己看的是哪个时钟——见 `docs/04`。

## 四、概率条（FedWatch 专用组件）

| 方向 | 渐变 | 语义 |
|---|---|---|
| 加息 | `#f87171 → #dc2626` | 紧缩 |
| 维持 | `#fbbf24 → #d97706` | 中性 |
| 降息 | `#34d399 → #059669` | 宽松 |

槽底统一 `#edf0f5`、高 `7px`、圆角 `4px`。
三态并列展示时（10月/12月各三条），**读者不需要读数字就能看出重心在哪一边**。

## 五、内容骨架与填充协议

5 个区块，顺序固化（AI 只填数据，不改结构）：

```
头部（品牌 + 日期/产品 + 事件标签）
 ├ 隔夜市场     表格式：名称 | 数值 涨跌 | 备注
 ├ 利率路径     当前利率 + 概率条
 ├ 今日焦点     机制解释 / 市场快评 / 投行视角
 ├ 事件预告     未来 7 天 + 本月日程
 └ 底部         数据来源 + 免责声明
```

填充协议见 `templates/*.html` 里的 `{占位符}` 注释——**复制模板、填空、删注释**。

## 六、程序员入口：fixture → 卡片

不喜欢手改 HTML 的话，用渲染器：

```bash
python demo/render_card.py demo/fixtures/daily-en.json
# -> demo/output/daily-en.html
```

fixture schema（完整示例见 `demo/fixtures/`）：

```json
{
  "locale": "en",
  "date": "2026-09-21", "weekday": "Mon", "kind": "daily",
  "event": "No major macro events — market recap",
  "tag_tone": "good",
  "sections": [
    {"tone": "good", "title": "Overnight markets",
     "table": [{"name": "S&P 500", "value": "7,637.76", "pct": 1.14, "note": "week -0.25%"}]},
    {"tone": "warn", "title": "Rate path", "text": "...",
     "probabilities": [{"label": "FOMC Oct — hike 25bp", "pct": 56.5, "kind": "hike"}]},
    {"tone": "info", "title": "Today's focus", "text": "..."}
  ],
  "footer": ["...", "..."]
}
```

`sections[].tone` 决定色条，`table[].pct` 决定涨跌色，`probabilities[].kind`
决定渐变——**设计规则由渲染器执行，而不是靠人记住色号**。

## 七、改样式只改一处

要换配色 / 宽度 / 字体：改 `templates/` 与 `demo/render_card.py` 顶部的令牌表。
**不要**在自动化 prompt 或具体报告里改样式——那样下次生成就被覆盖了。
