# assets/ —— README 首屏卡片图

| 文件名 | 内容 | 对应的 HTML |
|---|---|---|
| `card-zh.png` | 中文卡（**红涨绿跌**，UTC+8） | `demo/output/daily-zh.html` |
| `card-en.png` | 英文卡（**绿涨红跌**，UTC-4） | `demo/output/daily-en.html` |

## 这两张图是怎么来的（诚实说明）

**不是浏览器截图。** 生成环境无法启动无头浏览器（系统把浏览器启动接管给了桌面会话），
因此这两张图由本地脚本从**同一份 fixture JSON**、**同一套设计令牌**绘制：

- 色值、四态 tone 映射、涨跌约定（`CONVENTIONS`/`TONES`/`GRADS`）直接从
  `demo/render_card.py` import，避免两套设计系统漂移；
- 布局规则（520px 卡片、左侧 4px 色条、概率条三色渐变、页脚）按 `docs/02` 复刻；
- 因此它们**忠实呈现**了 `demo/output/*.html` 的样子，但**不保证逐像素相同**
  （字体度量与阴影细节会有差异）。

绘制脚本使用 Pillow，属第三方依赖，**刻意不放进本仓库**——仓库要守住"零依赖"这条线。
有浏览器环境的读者，直接打开 `demo/output/*.html` 截图即可得到浏览器原件。

## 纪律

卡片样式（`templates/` 或 `render_card.py` 的令牌）一旦改动，**这两张图必须重新生成**，
不允许留着与代码不符的旧图。
