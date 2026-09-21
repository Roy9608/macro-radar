#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tz_convert.py —— 把事件日历换算到读者的本地时区，并检查作息契合度。

为什么需要它：美国宏观数据锚定在**美东时间**（08:30 / 10:30 / 14:00 ET），
所以"北京时间 21:30"对中国读者恰好合适，对伦敦读者是凌晨 02:30、对纽约读者是上午 09:30。
本工具回答三个问题：

  1. 接下来的事件，在我的时区是几点？（--events）
  2. 四条产品线现有的北京时间，换到我这里几点？我该改成几点？（--plan）
  3. 日历数据本身自洽吗？（--verify：用 ET 时刻反算北京时间，逐条对账）

零依赖：不依赖 IANA tz 数据库（每个事件自带 EST/EDT 标记，UTC = ET + 5h/4h）。
如需按 IANA 时区名（含自动夏令时），用 --iana（需要系统 tz 数据库或 tzdata 包）。

用法：
  python tools/tz_convert.py --utc-offset 8 --events          # 北京读者
  python tools/tz_convert.py --utc-offset -4 --events         # 纽约读者
  python tools/tz_convert.py --utc-offset -4 --plan           # 我的作息该怎么排
  python tools/tz_convert.py --verify                         # 日历自洽性检查
  python tools/tz_convert.py --iana Asia/Tokyo --events       # 有 tz 数据库时可用
"""
import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
CALENDAR = HERE.parent / "data" / "calendar.json"

ET_TO_UTC_HOURS = {"EST": 5, "EDT": 4}          # UTC = ET + 5h(冬令时) / +4h(夏令时)
BEIJING_OFFSET = 8.0                             # 日历里的 date_bj/time_bj 基准
PRODUCTS = [                                     # 生产系统的四条产品线（北京时间）
    ("daily", "每日宏观日报", 7, 0),
    ("t1", "T-1 事件提醒", 9, 0),
    ("weekly", "每周摘要", 9, 0),
]


def load_events():
    if not CALENDAR.exists():
        sys.exit(f"找不到日历文件: {CALENDAR}")
    return json.loads(CALENDAR.read_text(encoding="utf-8")).get("events", [])


def event_utc(ev):
    """事件 → UTC datetime（用 ET 时刻 + 该事件自带的 EST/EDT 标记）。"""
    et_tz = (ev.get("et_tz") or "").upper()
    if et_tz not in ET_TO_UTC_HOURS:
        return None
    naive = datetime.strptime(f"{ev['date_et']} {ev['time_et']}", "%Y-%m-%d %H:%M")
    return naive + timedelta(hours=ET_TO_UTC_HOURS[et_tz])


def fmt_local(utc_dt, offset, weekday=True):
    loc = utc_dt + timedelta(hours=offset)
    wd = "一二三四五六日"[loc.weekday()] if weekday else ""
    return f"{loc:%Y-%m-%d} {loc:%H:%M}", wd


def describe(offset):
    if offset == int(offset):
        sign = "+" if offset >= 0 else "-"
        return f"UTC{sign}{abs(int(offset))}"
    return f"UTC{'+' if offset >= 0 else '-'}{abs(offset):.1f}"


def cmd_events(events, offset, limit, from_date):
    """未来事件在本地时间的样子。"""
    rows = []
    for ev in events:
        u = event_utc(ev)
        if u is None:
            continue
        local_str, wd = fmt_local(u, offset)
        if datetime.strptime(local_str, "%Y-%m-%d %H:%M").date() < from_date:
            continue
        rows.append((local_str, wd, ev, u))
    rows.sort(key=lambda r: r[0])
    print(f"未来事件（本地时间 {describe(offset)}）" + (f" · 共 {len(rows)} 条" if rows else ""))
    print("-" * 78)
    print(f"{'本地时间':<17}{'周':<3}{'事件':<26}{'北京时间':<17}{'状态'}")
    for local_str, wd, ev, u in rows[:limit]:
        bj, _ = fmt_local(u, BEIJING_OFFSET)
        print(f"{local_str:<17}{wd:<3}{ev['name'][:24]:<26}{bj:<17}{ev.get('status','')}")
    if not rows:
        print("（无）")


def cmd_plan(offset):
    """四条产品线：北京时间 → 本地时间，并判断是否契合当地作息。"""
    print(f"作息契合度检查（本地时间 {describe(offset)}）")
    print("-" * 78)
    print(f"{'产品':<16}{'北京时间':<12}{'你的本地时间':<14}{'判断':<10}建议")
    for _key, name, hh, mm in PRODUCTS:
        total_utc = hh - BEIJING_OFFSET                      # 换算到 UTC
        local_hour = (total_utc + offset) % 24
        local_str = f"{int(local_hour):02d}:{mm:02d}"
        ok = 7 <= local_hour <= 21.9
        verdict = "契合" if ok else "偏离作息"
        if ok:
            suggestion = "保持不变"
        else:
            # 建议改成"本地 09:00"：反推对应的北京时间
            bj_hour = (9 - offset + BEIJING_OFFSET) % 24
            suggestion = f"改为本地 09:00（≈北京 {int(bj_hour):02d}:{mm:02d}）"
        print(f"{name:<16}{int(hh):02d}:{mm:02d}      {local_str:<14}{verdict:<10}{suggestion}")
    print()
    print("说明：")
    print("  · 数据快报不在此表——它锚定在美东发布时刻（08:30/10:30 ET）后 +30min，随事件自动落位；")
    print(f"  · 上表时刻可用宿主调度器按本地时间直接设置，无需改动任何代码。")
    print(f"  · 美东夏令时切换时（3月/11月），事件会自动前/后移 1 小时，本工具的 --verify 可核对。")


def cmd_verify(events):
    """自洽性对账：用 ET 时刻反算北京时间，与日历里写死的 date_bj/time_bj 比对。"""
    ok = bad = skip = 0
    print("日历自洽性检查（ET 时刻 + EST/EDT → 北京时间，逐条对账）")
    print("-" * 78)
    for ev in events:
        u = event_utc(ev)
        if u is None:
            skip += 1
            print(f"  跳过（缺 et_tz）: {ev.get('id')}")
            continue
        bj, _ = fmt_local(u, BEIJING_OFFSET)
        expect = f"{ev['date_bj']} {ev['time_bj']}"
        if bj == expect:
            ok += 1
        else:
            bad += 1
            print(f"  ✗ 不一致 {ev.get('id')}: 日历写 {expect}，按 ET 反算 {bj}")
    print(f"  一致 {ok} 条 · 不一致 {bad} 条 · 跳过 {skip} 条" + ("  → 日历自洽 ✓" if bad == 0 else "  → 需修正"))
    return bad


def resolve_offset(args):
    if args.iana:
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(args.iana)
            ref = datetime(2026, 1, 15, 12, tzinfo=tz).utcoffset()
            summer = datetime(2026, 7, 15, 12, tzinfo=tz).utcoffset()
            print(f"* 使用 IANA 时区 {args.iana}（冬令时 {ref}，夏令时 {summer}）")
            print("* 注意：本工具按固定偏移计算，夏令时切换期间请以 --verify 核对或用系统调度器本地时间")
            return ref.total_seconds() / 3600
        except Exception as e:  # 常见于 Windows 未安装 tzdata
            sys.exit(
                f"IANA 时区不可用（{type(e).__name__}: {e}）。\n"
                f"  选项：① 改用 --utc-offset（如 --utc-offset 9）\n"
                f"        ② 安装 tz 数据库：pip install tzdata\n"
                f"        ③ 直接用宿主调度器的本地时间"
            )
    return args.utc_offset


def main():
    ap = argparse.ArgumentParser(description="事件日历 → 本地时区换算 / 作息检查 / 日历自洽性校验")
    ap.add_argument("--utc-offset", type=float, default=None, help="目标时区相对 UTC 的偏移小时数，如 8、-4、5.5")
    ap.add_argument("--iana", help="IANA 时区名（如 Asia/Tokyo）；需要 tz 数据库，不可用时请用 --utc-offset")
    ap.add_argument("--events", action="store_true", help="列出未来事件在本地时间的样子")
    ap.add_argument("--plan", action="store_true", help="检查四条产品线与本地作息的契合度")
    ap.add_argument("--verify", action="store_true", help="校验日历自洽性（ET → 北京，逐条对账）")
    ap.add_argument("--next", type=int, default=8, help="--events 最多显示条数（默认 8）")
    ap.add_argument("--from", dest="from_date", help="起始日期 YYYY-MM-DD（默认今天）")
    args = ap.parse_args()

    events = load_events()

    if args.verify:
        sys.exit(1 if cmd_verify(events) else 0)

    if args.utc_offset is None and not args.iana:
        ap.print_help()
        sys.exit(2)

    offset = resolve_offset(args)
    from_date = (datetime.strptime(args.from_date, "%Y-%m-%d").date()
                 if args.from_date else datetime.now().date())

    if args.plan:
        cmd_plan(offset)
    elif args.events:
        cmd_events(events, offset, args.next, from_date)
    else:
        ap.print_help()
        sys.exit(2)


if __name__ == "__main__":
    main()
