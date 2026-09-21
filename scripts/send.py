#!/usr/bin/env python3
"""
宏观雷达 MacroRadar · 统一分发脚本
====================================
用法：
  # 微信 PushPlus 推送（可多个 token）
  python send.py --title "宏观雷达 · 每日宏观日报" --html <file.html> --push token1 token2

  # 邮件发送（可多个收件人）
  python send.py --title "宏观雷达 · 每日宏观日报" --html <file.html> --mail a@x.com b@y.com

  # 两者混合
  python send.py --title "..." --html <file.html> --push tk1 tk2 --mail a@x.com

说明：
  · --html 必填，指向已生成的 HTML 卡片文件（UTF-8）
  · --title 推送标题，默认「宏观雷达 MacroRadar」
  · --push 后的参数为 PushPlus token（任意数量）
  · --mail 后的参数为收件人邮箱（任意数量）
  · --subscribers 订阅名单 CSV：按 status=enabled 且 channels 含 --channel 过滤后自动补全收件人
  · SMTP 配置从 ../config/smtp.json 读取（host/port/use_ssl/sender/auth_code/sender_name/subject_prefix）
  · --dry-run 只检查不发送（无 token 也能跑），用于验证 HTML 与参数
  · 退出码 0 = 全部成功；1 = 部分失败（结果打印到 stdout）
"""
import argparse, json, sys, urllib.request
from pathlib import Path
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr

def load_smtp():
    p = Path(__file__).resolve().parent.parent / "config" / "smtp.json"
    if not p.exists():
        sys.exit(
            f"缺少 SMTP 配置: {p}\n"
            f"  先复制模板：cp config/smtp.example.json config/smtp.json（Windows 用 copy）\n"
            f"  再填入 sender 与 auth_code（邮箱授权码，不是登录密码）"
        )
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def load_subscribers(path, channel):
    """读订阅名单 CSV，返回 (tokens, emails, stats)。

    过滤规则：跳过空行 → status=enabled → channels 含本条频道 →
    有 pushplus_token 收进微信组、有 email 收进邮件组（两者都有则两边都收）。
    名单文件是私人的，不进仓库（见 .gitignore）。
    """
    import csv
    tokens, emails = [], []
    total = enabled = matched = blank = 0
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if not any((v or "").strip() for v in row.values()):
                blank += 1              # 表格编辑残留的空行
                continue
            total += 1
            if (row.get("status") or "").strip().lower() != "enabled":
                continue
            enabled += 1
            chans = [c.strip() for c in (row.get("channels") or "").split(",") if c.strip()]
            if channel and channel not in chans:
                continue
            matched += 1
            tk = (row.get("pushplus_token") or "").strip()
            em = (row.get("email") or "").strip()
            if tk:
                tokens.append(tk)
            if em:
                emails.append(em)
    return tokens, emails, {"total": total, "enabled": enabled, "matched": matched, "blank_rows_skipped": blank}

def pushplus(token, title, html):
    payload = json.dumps({"token": token, "title": title, "content": html, "template": "html"}).encode("utf-8")
    req = urllib.request.Request("https://www.pushplus.plus/send", data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def send_mail(cfg, to_addr, title, html):
    msg = MIMEText(html, "html", "utf-8")
    msg["From"] = formataddr((str(Header(cfg["sender_name"], "utf-8")), cfg["sender"]))
    msg["To"] = to_addr
    msg["Subject"] = Header(f'{cfg.get("subject_prefix", "")}{title}', "utf-8")
    if cfg.get("use_ssl", True):
        import smtplib
        with smtplib.SMTP_SSL(cfg["smtp_host"], cfg.get("smtp_port", 465), timeout=30) as s:
            s.login(cfg["sender"], cfg["auth_code"])
            s.sendmail(cfg["sender"], [to_addr], msg.as_string())
    else:
        import smtplib
        with smtplib.SMTP(cfg["smtp_host"], cfg.get("smtp_port", 587), timeout=30) as s:
            s.starttls()
            s.login(cfg["sender"], cfg["auth_code"])
            s.sendmail(cfg["sender"], [to_addr], msg.as_string())

def main():
    ap = argparse.ArgumentParser(description="宏观雷达统一分发")
    ap.add_argument("--title", default="宏观雷达 MacroRadar")
    ap.add_argument("--html", required=True, help="HTML 卡片文件路径")
    ap.add_argument("--push", nargs="*", default=[], help="PushPlus tokens")
    ap.add_argument("--mail", nargs="*", default=[], help="收件人邮箱")
    ap.add_argument("--subscribers", help="订阅名单 CSV 路径（按 status/channels 过滤后自动补全收件人）")
    ap.add_argument("--channel", default="daily", choices=["daily", "t1", "flash", "weekly"],
                    help="本条消息属于哪个频道，用于与名单的 channels 列匹配（默认 daily）")
    ap.add_argument("--dry-run", action="store_true",
                    help="只做检查与统计，不实际发送（无需任何 token/配置）")
    args = ap.parse_args()

    html = Path(args.html).read_text(encoding="utf-8")

    push_targets, mail_targets, sub_stats = list(args.push), list(args.mail), None
    if args.subscribers:
        if not Path(args.subscribers).exists():
            sys.exit(f"找不到订阅名单: {args.subscribers}")
        tks, ems, sub_stats = load_subscribers(args.subscribers, args.channel)
        push_targets += [t for t in tks if t not in push_targets]
        mail_targets += [e for e in ems if e not in mail_targets]

    if args.dry_run:
        report = {
            "ok": True, "dry_run": True,
            "html_bytes": len(html.encode("utf-8")),
            "push_targets": len(push_targets),
            "mail_targets": len(mail_targets),
            "note": "dry-run：未发送任何消息",
        }
        if sub_stats is not None:
            report["subscribers"] = sub_stats
        print(json.dumps(report, ensure_ascii=False, indent=2))
        sys.exit(0)

    results, ok = [], True

    for tk in push_targets:
        try:
            r = pushplus(tk, args.title, html)
            status = f"PushPlus code={r.get('code')} msg={r.get('msg')}"
            ok = ok and (r.get("code") == 200)
        except Exception as e:
            status, ok = f"PushPlus ERROR: {e}", False
        results.append(status)

    if mail_targets:
        cfg = load_smtp()
        for addr in mail_targets:
            try:
                send_mail(cfg, addr, args.title, html)
                status = f"邮件 OK -> {addr}"
            except Exception as e:
                status, ok = f"邮件 ERROR ({addr}): {e}", False
            results.append(status)

    print(json.dumps({"ok": ok, "results": results}, ensure_ascii=False, indent=2))
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
