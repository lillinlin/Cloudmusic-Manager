import json
import time
import random
import base64
import requests
from datetime import datetime

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://music.163.com/",
}


def api(base: str, path: str, cookie: str = "", params: dict = None) -> dict:
    p = dict(params or {})
    p.setdefault("timestamp", int(time.time() * 1000))
    h = dict(HEADERS)
    if cookie:
        h["Cookie"] = cookie
        p["cookie"] = cookie
    try:
        r = requests.get(base + path, params=p, headers=h, timeout=20)
        if not r.text.strip():
            return {}
        return r.json()
    except Exception:
        return {}


def normalize_cookie(raw: str) -> str:
    if not raw:
        return ""
    skip = {"path", "expires", "max-age", "domain", "secure", "httponly", "samesite"}
    kv: dict = {}
    for line in raw.replace("\r", "\n").split("\n"):
        for item in line.split(";"):
            item = item.strip()
            if "=" in item:
                k, v = item.split("=", 1)
                if k.strip().lower() not in skip:
                    kv[k.strip()] = v.strip()
    return "; ".join(f"{k}={v}" for k, v in kv.items())


def is_logged_in(base: str, cookie: str) -> bool:
    return api(base, "/user/account", cookie).get("code") == 200


def get_uid(base: str, cookie: str) -> str:
    r = api(base, "/user/account", cookie)
    return str(r.get("account", {}).get("id", ""))


def get_user_profile(base: str, cookie: str) -> dict:
    """返回昵称和头像"""
    r = api(base, "/user/account", cookie)
    profile = r.get("profile", {})
    return {
        "nickname": profile.get("nickname", ""),
        "avatar": profile.get("avatarUrl", ""),
    }


def fetch_my_events(base: str, cookie: str, uid: str, limit: int = 30) -> list:
    r = api(base, "/user/event", cookie, {"uid": uid, "limit": limit})
    result = []
    for e in r.get("events", []):
        eid = str(e.get("id", ""))
        try:
            msg = json.loads(e.get("json", "{}")).get("msg", "")
        except Exception:
            msg = ""
        if eid:
            result.append({"id": eid, "msg": msg})
    return result


def do_share(base: str, cookie: str, share_cfg: dict, count: int, today: str) -> tuple:
    msg = (share_cfg["msg"]
           .replace("{{count}}", str(count))
           .replace("{{date}}", today))
    r = api(base, "/share/resource", cookie, {
        "type": share_cfg["type"],
        "id":   str(share_cfg["id"]),
        "msg":  msg,
    })
    if r.get("code") == 200:
        ev_id = str(r.get("data", {}).get("eventId") or r.get("eventId") or "")
        if not ev_id:
            time.sleep(1)
            uid = get_uid(base, cookie)
            if uid:
                events = fetch_my_events(base, cookie, uid, limit=5)
                if events:
                    ev_id = events[0]["id"]
        return True, ev_id, msg
    return False, "", msg


def delete_event(base: str, cookie: str, ev_id: str) -> bool:
    if not ev_id:
        return False
    r = api(base, "/event/delete", cookie, {"eventId": ev_id})
    return r.get("code") == 200


# ── 二维码登录 ──────────────────────────────

def qr_create(base: str) -> dict:
    """创建二维码，返回 {key, qrimg_b64, qrurl}"""
    resp = api(base, "/login/qr/key")
    key = resp.get("data", {}).get("unikey", "")
    if not key:
        return {}
    data = api(base, "/login/qr/create", params={"key": key, "qrimg": True}).get("data", {})
    return {
        "key": key,
        "qrimg": data.get("qrimg", ""),   # data:image/png;base64,...
        "qrurl": data.get("qrurl", ""),
    }


def qr_check(base: str, key: str) -> dict:
    """
    检查扫码状态
    返回 {code, cookie}，空响应返回 {}
    code: 801=等待扫码 802=待确认 803=成功 800=过期
    """
    import logging
    _log = logging.getLogger("ncm.qr")
    r = api(base, "/login/qr/check", params={"key": key})
    _log.info(f"qr_check raw: {r}")   # debug
    if not r:
        return {}
    code = r.get("code", 0)
    if not code:
        return {}
    cookie = ""
    if code == 803:
        cookie = normalize_cookie(r.get("cookie", ""))
    return {"code": code, "cookie": cookie}
