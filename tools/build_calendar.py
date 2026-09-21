# -*- coding: utf-8 -*-
"""宏观雷达 MacroRadar · 年度日历生成器
从官方日程生成 data/calendar.json（自动换算北京时间，含夏令时）
用法: python build_calendar.py
更新日历：改下方官方日程表后重新运行即可
"""
import json
from datetime import date, timedelta

# ============ 官方日程数据源（federalreserve.gov / bls.gov / bea.gov） ============

# FOMC 会议：(月, 首日, 决议日)
FOMC_2026 = [(1,27,28),(3,17,18),(4,28,29),(6,16,17),(7,28,29),(9,15,16),(10,27,28),(12,8,9)]
FOMC_2027 = [(1,26,27),(3,16,17),(4,27,28),(6,8,9),(7,27,28),(9,14,15),(10,26,27),(12,7,8)]

# CPI：(月, 日) 2026 官方；2027 按每月 12 日前后预计
CPI_2026 = [(1,13),(2,13),(3,11),(4,10),(5,12),(6,10),(7,14),(8,12),(9,11),(10,14),(11,10),(12,10)]
CPI_2027 = [(1,12),(2,12),(3,12),(4,12),(5,12),(6,12),(7,12),(8,12),(9,12),(10,12),(11,12),(12,12)]

# 非农：(月, 日) 2026 官方；2027 按每月首个周五预计
NFP_2026 = [(1,9),(2,11),(3,6),(4,3),(5,8),(6,5),(7,2),(8,7),(9,4),(10,2),(11,6),(12,4)]
NFP_2027 = [(1,8),(2,5),(3,5),(4,2),(5,7),(6,4),(7,2),(8,6),(9,3),(10,1),(11,5),(12,3)]

# PCE：(月, 日, 发布小时ET) 2026 官方；2027 按月末预计
PCE_2026 = [(1,22,10),(2,20,8),(3,13,8),(4,9,8),(4,30,8),(5,28,8),(6,25,8),(7,30,8),(8,26,8),(9,30,8),(10,29,8),(11,25,8),(12,23,8)]
PCE_2027 = [(1,29,8),(2,26,8),(3,26,8),(4,30,8),(5,28,8),(6,25,8),(7,30,8),(8,27,8),(9,30,8),(10,29,8),(11,26,8),(12,23,8)]

# ============ 夏令时换算（美东 3月第二个周日 ~ 11月第一个周日） ============

def dst_start(y):
    d = date(y, 3, 8)
    return d + timedelta(days=(6 - d.weekday()) % 7)

def dst_end(y):
    d = date(y, 11, 1)
    return d + timedelta(days=(6 - d.weekday()) % 7)

def et_to_bj(y, m, d, hh, mm):
    """美东时间 -> 北京时间（EDT=UTC-4 即北京+12h；EST=UTC-5 即北京+13h）"""
    dt = date(y, m, d)
    is_dst = dst_start(y) <= dt <= dst_end(y)
    offset = 12 if is_dst else 13
    total_min = hh*60 + mm + offset*60
    days = total_min // 1440
    bj_dt = dt + timedelta(days=days)
    return bj_dt, (total_min % 1440)//60, total_min % 60, ("EDT" if is_dst else "EST")

# ============ 生成 ============

events = []

def add(eid, etype, name, y, m, d, hh, mm, prio, status, note=""):
    bj_dt, bj_hh, bj_mm, tz = et_to_bj(y, m, d, hh, mm)
    events.append({
        "id": eid, "type": etype, "name": name,
        "date_et": f"{y}-{m:02d}-{d:02d}", "time_et": f"{hh:02d}:{mm:02d}", "et_tz": tz,
        "date_bj": f"{bj_dt.year}-{bj_dt.month:02d}-{bj_dt.day:02d}",
        "time_bj": f"{bj_hh:02d}:{bj_mm:02d}",
        "priority": prio, "status": status, "notes": note
    })

for y, fomc, sep_yr in ((2026, FOMC_2026, "2026"), (2027, FOMC_2027, "2027")):
    for m, d1, d2 in fomc:
        has_sep = m in (3,6,9,12)
        add(f"fomc-{y}-{m:02d}", "fomc", f"FOMC 利率决议 {m}月" + ("（含点阵图/经济预测）" if has_sep else ""),
            y, m, d2, 14, 0, "P0", "confirmed" if y==2026 else "tentative",
            "含点阵图，会后约 02:30 主席新闻发布会" if has_sep else "会后约 02:30 主席新闻发布会")
        mdt = date(y, m, d2) + timedelta(days=21)
        add(f"fomc-min-{y}-{m:02d}", "fomc-minutes", f"FOMC 会议纪要 {m}月",
            mdt.year, mdt.month, mdt.day, 14, 0, "P0", "confirmed" if y==2026 else "tentative",
            "决议后约 3 周发布（官方日期以实际为准）")

for y, cpi in ((2026, CPI_2026), (2027, CPI_2027)):
    for m, d in cpi:
        dm = 12 if m == 1 else m - 1   # 数据月 = 发布月 - 1（1月发布上年12月数据）
        add(f"cpi-{y}-{m:02d}", "cpi", f"CPI 通胀数据（{dm}月数据）", y, m, d, 8, 30, "P0",
            "confirmed" if y==2026 else "estimated",
            "" if y==2026 else "预计日期（每月 12 日前后），以 BLS 正式日程为准")

nfp_notes = {(2026,2):"政府停摆延迟", (2026,7):"独立日提前"}
for y, nfp in ((2026, NFP_2026), (2027, NFP_2027)):
    for m, d in nfp:
        dm = 12 if m == 1 else m - 1
        add(f"nfp-{y}-{m:02d}", "nfp", f"非农就业报告（{dm}月数据）", y, m, d, 8, 30, "P0",
            "confirmed" if y==2026 else "estimated",
            nfp_notes.get((y,m), "" if y==2026 else "预计每月首个周五，以 BLS 正式日程为准"))

for y, pce in ((2026, PCE_2026), (2027, PCE_2027)):
    for m, d, hh in pce:
        dm = 12 if m == 1 else m - 1
        add(f"pce-{y}-{m:02d}", "pce", f"PCE 通胀数据（{dm}月数据）", y, m, d, hh, 30, "P0",
            "confirmed" if y==2026 else "estimated",
            "美联储首选通胀指标，含核心 PCE" if y==2026 else "预计日期（月末），以 BEA 正式日程为准")

events.sort(key=lambda e: (e["date_bj"], e["time_bj"]))

data = {
    "meta": {
        "project": "宏观雷达 MacroRadar",
        "version": "1.0",
        "updated": "2026-08-07",
        "sources": ["federalreserve.gov", "bls.gov", "bea.gov", "cmegroup FedWatch"],
        "note": "北京时间已换算（含美东夏令时/冬令时）；status=confirmed 官方确认，tentative=官方暂定，estimated=按规律预计",
        "current_context": {
            "fed_funds_rate": "3.50%-3.75%",
            "chair": "Kevin Warsh（2026年6月起任美联储主席，鲍威尔 5/15 届满）",
            "inflation_trend": "2026 年通胀回升：CPI 4月 +3.8%（2025年末约 2.4%），核心 PCE 约 3.3%",
            "market_regime": "通胀回升背景下，市场焦点从'何时降息'转向'高利率维持更久'"
        }
    },
    "events": events
}

import os
out = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "calendar.json")
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"生成 {len(events)} 个事件 -> {out}")
print("\n=== 未来 90 天事件预览（北京时间）===")
today = "2026-08-07"
limit = date(2026, 11, 5).isoformat()
for e in events:
    if today <= e["date_bj"] <= limit:
        print(f"{e['date_bj']} {e['time_bj']}  [{e['priority']}] {e['name']} ({e['status']})")
