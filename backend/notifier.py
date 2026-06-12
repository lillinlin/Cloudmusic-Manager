"""Telegram 通知"""
import requests


def send(token: str, chat_id: str, text: str) -> bool:
    if not token or not chat_id:
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        return r.json().get("ok", False)
    except Exception:
        return False


def notify_share_success(token: str, chat_id: str, name: str, count: int, quota: int, msg: str):
    send(token, chat_id,
         f"✅ <b>{name}</b> 发布成功\n"
         f"本月进度：{count}/{quota}\n"
         f"内容：{msg}")


def notify_share_fail(token: str, chat_id: str, name: str):
    send(token, chat_id,
         f"❌ <b>{name}</b> 发布失败，请检查日志")


def notify_login_expired(token: str, chat_id: str, name: str):
    send(token, chat_id,
         f"⚠️ <b>{name}</b> Cookie 已过期，请打开面板重新扫码登录\n"
         f"👉 登录后脚本会自动继续运行")


def notify_delete_done(token: str, chat_id: str, name: str, count: int, prev_ym: str):
    send(token, chat_id,
         f"🗑 <b>{name}</b> 已删除上月({prev_ym})动态 {count} 条")


def notify_quota_done(token: str, chat_id: str, name: str, quota: int):
    send(token, chat_id,
         f"🎉 <b>{name}</b> 本月 {quota} 次动态已全部完成！")
