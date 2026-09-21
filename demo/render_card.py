#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_card.py —— MacroRadar 卡片渲染器（零依赖，纯标准库）。

把一份 fixture JSON 渲染成设计系统规范的 HTML 卡片。
这既是"clone 即跑"的演示入口，也是本仓库模板层的参考实现。

设计系统（与 templates/ 一致）：
  · 页面底 #f2f4f8，白卡圆角 12px，max-width 520px
  · 顶部深蓝渐变头：linear-gradient(135deg,#0f1e4b,#1e3a8a 55%,#1d4ed8)
  · 分区左侧色条：alert 红 #dc2626 / warn 琥珀 #b45309 / good 绿 #047857 / info 蓝 #1d4ed8
  · 市场涨跌按中国习惯：**红涨绿跌**（由 pct 正负自动判定）
  · 概率条：hike 红渐变 / hold 琥珀渐变 / cut 绿渐变

用法：
  python render_card.py fixtures/daily-zh.json
  python render_card.py --all                    # 渲染 fixtures/ 下全部
  python render_card.py fixtures/daily-en.json -o /tmp/out.html
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

TONES = {
    "alert": ("#dc2626", "#fef2f2", "#7f1d1d"),
    "warn": ("#b45309", "#fffbeb", "#92400e"),
    "good": ("#047857", "#f0fdf4", "#065f46"),
    "info": ("#1d4ed8", "#eff6ff", "#1e40af"),
}
GRADS = {
    "hike": ("#f87171", "#dc2626"),
    "hold": ("#fbbf24", "#d97706"),
    "cut": ("#34d399", "#059669"),
}
# 涨跌配色约定：不同地区恰好相反，因此必须可选
#   cn   = 红涨绿跌（中国内地及港澳台地区、日本、韩国）
#   west = 绿涨红跌（美国、欧洲等）
CONVENTIONS = {
    "cn": ("#dc2626", "#047857"),      # (涨, 跌)
    "west": ("#047857", "#dc2626"),
}
LABELS = {
    "zh": {"data_sources": "数据来源", "disclaimer": "仅供参考，不构成投资建议"},
    "en": {"data_sources": "Data sources", "disclaimer": "For information only — not investment advice"},
}


def resolve_convention(fx):
    """auto：中文读者默认红涨绿跌；英文读者默认绿涨红跌。可用 color_convention 强制覆盖。"""
    conv = fx.get("color_convention", "auto")
    if conv in CONVENTIONS:
        return conv
    return "cn" if fx.get("locale", "zh") == "zh" else "west"


def pct_html(pct, up="#dc2626", down="#047857"):
    """涨跌着色。默认红涨绿跌（中国内地及港澳台地区、日本、韩国）。"""
    if pct is None:
        return ""
    color = up if pct > 0 else (down if pct < 0 else "#64748b")
    return f'<b style="color:{color};">{pct:+.2f}%</b>'


def section_html(sec, conv="cn"):
    up, down = CONVENTIONS[conv]
    bar, bg, head = TONES.get(sec.get("tone", "info"), TONES["info"])
    parts = [
        f'<div style="border-left:4px solid {bar};background:{bg};padding:10px 12px;'
        f'border-radius:0 8px 8px 0;margin-bottom:12px;">',
        f'<div style="font-size:13px;font-weight:800;color:{head};margin-bottom:6px;">{sec["title"]}</div>',
    ]
    if sec.get("table"):
        parts.append('<table style="width:100%;font-size:12.5px;color:#334155;border-collapse:collapse;">')
        for row in sec["table"]:
            note = f'<td style="text-align:right;color:#64748b;font-size:11px;">{row["note"]}</td>' if row.get("note") else "<td></td>"
            parts.append(
                f'<tr><td style="padding:2px 0;">{row["name"]}</td>'
                f'<td style="text-align:right;">{row["value"]} {pct_html(row.get("pct"), up, down)}</td>{note}</tr>'
            )
        parts.append("</table>")
    if sec.get("text"):
        parts.append(f'<div style="font-size:12.5px;color:#334155;line-height:1.7;">{sec["text"]}</div>')
    for item in sec.get("bullets", []):
        parts.append(f'<div style="font-size:12.5px;color:#334155;line-height:1.7;">• {item}</div>')
    for pr in sec.get("probabilities", []):
        g1, g2 = GRADS.get(pr.get("kind", "hold"), GRADS["hold"])
        parts.append(
            f'<div style="font-size:11px;color:#64748b;margin:6px 0 2px;">{pr["label"]}'
            f'&nbsp;<b style="color:{g2};">{pr["pct"]}%</b></div>'
            f'<div style="background:#edf0f5;height:7px;border-radius:4px;overflow:hidden;margin-bottom:3px;">'
            f'<div style="width:{pr["pct"]}%;height:100%;background:linear-gradient(90deg,{g1},{g2});"></div></div>'
        )
    parts.append("</div>")
    return "".join(parts)


def meta_line(fx):
    """日期行文案（按 locale 组装，展示 i18n 位）。"""
    loc = fx.get("locale", "zh")
    date = fx.get("date", "")
    weekday = fx.get("weekday", "")
    kind = fx.get("kind", "daily")
    kinds = {
        "zh": {"daily": "每日宏观日报", "t1": "T-1 事件提醒", "flash": "数据快报", "weekly": "每周摘要"},
        "en": {"daily": "Daily Brief", "t1": "T-1 Event Brief", "flash": "Data Flash", "weekly": "Weekly Summary"},
    }
    sep = " · " if loc == "zh" else " · "
    line = f'{date} {weekday}{sep}{kinds.get(loc, kinds["zh"]).get(kind, kind)}'.strip()
    tz = fx.get("timezone_label")
    return f"{line} · {tz}" if tz else line


def render(fx):
    loc = fx.get("locale", "zh")
    labels = LABELS.get(loc, LABELS["zh"])
    conv = resolve_convention(fx)
    bar, bg, _head = TONES.get(fx.get("tag_tone", "info"), TONES["info"])
    out = [
        '<div style="background:#f2f4f8;padding:16px 8px;font-family:-apple-system,'
        "'PingFang SC','Microsoft YaHei',sans-serif;\">",
        '<div style="max-width:520px;margin:0 auto;background:#ffffff;border-radius:12px;'
        'overflow:hidden;box-shadow:0 2px 12px rgba(15,30,75,.08);">',
        # 头部
        '<div style="background:linear-gradient(135deg,#0f1e4b 0%,#1e3a8a 55%,#1d4ed8 100%);'
        'padding:18px 20px;color:#ffffff;">',
        f'<div style="font-size:15px;font-weight:800;letter-spacing:1px;">{fx.get("brand", "MACRO RADAR")}</div>',
        f'<div style="font-size:12px;opacity:.85;margin-top:3px;">{meta_line(fx)}</div>',
        '<div style="margin-top:10px;">'
        f'<span style="display:inline-block;background:{bar};color:#fff;font-size:11px;font-weight:700;'
        f'padding:3px 10px;border-radius:999px;">{fx.get("event", "")}</span></div>',
        "</div>",
        '<div style="padding:14px 16px 4px;">',
    ]
    for sec in fx.get("sections", []):
        out.append(section_html(sec, conv))
    out.append("</div>")
    # 底部
    footer = fx.get("footer")
    if not footer:
        footer = [f'MacroRadar · {labels["data_sources"]}: Federal Reserve / BLS / BEA / CME FedWatch',
                  labels["disclaimer"]]
    out.append('<div style="padding:4px 16px 14px;color:#94a3b8;font-size:10.5px;line-height:1.6;">')
    out.extend(f"{line}<br>" for line in footer)
    out.append("</div></div></div>")
    return "".join(out)


def main():
    ap = argparse.ArgumentParser(description="MacroRadar 卡片渲染器（fixture JSON -> HTML）")
    ap.add_argument("fixture", nargs="?", help="fixture JSON 路径")
    ap.add_argument("--all", action="store_true", help="渲染 fixtures/ 下全部")
    ap.add_argument("-o", "--out", help="输出 HTML 路径（默认 output/<fixture名>.html）")
    args = ap.parse_args()

    if args.all:
        files = sorted((HERE / "fixtures").glob("*.json"))
    elif args.fixture:
        files = [Path(args.fixture)]
    else:
        ap.print_help()
        sys.exit(2)
    if not files:
        sys.exit("没有可渲染的 fixture")

    for f in files:
        fx = json.loads(Path(f).read_text(encoding="utf-8"))
        html = render(fx)
        out = Path(args.out) if (args.out and not args.all) else HERE / "output" / f"{Path(f).stem}.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        print(f"{f.name}  ->  {out}  ({len(html.encode('utf-8'))} bytes, locale={fx.get('locale')})")


if __name__ == "__main__":
    main()
