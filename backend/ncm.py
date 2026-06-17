import json, time, random, base64, requests, logging

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://music.163.com/",
}

def api(base, path, cookie="", params=None):
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
    except requests.exceptions.Timeout:
        logging.getLogger("ncm").warning(f"超时 {path}")
        return {}
    except requests.exceptions.ConnectionError as e:
        logging.getLogger("ncm").warning(f"连接失败 {path}: {e}")
        return {}
    except ValueError:
        logging.getLogger("ncm").warning(f"非JSON {path} [{r.status_code}]: {r.text[:80]}")
        return {}
    except Exception as e:
        logging.getLogger("ncm").warning(f"请求失败 {path}: {e}")
        return {}

def normalize_cookie(raw):
    if not raw:
        return ""
    skip = {"path","expires","max-age","domain","secure","httponly","samesite"}
    kv = {}
    for line in raw.replace("\r","\n").split("\n"):
        for item in line.split(";"):
            item = item.strip()
            if "=" in item:
                k, v = item.split("=", 1)
                if k.strip().lower() not in skip:
                    kv[k.strip()] = v.strip()
    return "; ".join(f"{k}={v}" for k, v in kv.items())

def is_logged_in(base, cookie):
    return api(base, "/user/account", cookie).get("code") == 200

def get_uid(base, cookie):
    r = api(base, "/user/account", cookie)
    return str(r.get("account", {}).get("id", ""))

def get_user_profile(base, cookie):
    r = api(base, "/user/account", cookie)
    profile = r.get("profile", {})
    return {
        "nickname": profile.get("nickname", ""),
        "avatar":   profile.get("avatarUrl", ""),
    }

def fetch_my_events(base, cookie, uid, limit=30):
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

def do_share(base, cookie, share_cfg, count, today):
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

def delete_event(base, cookie, ev_id):
    if not ev_id:
        return False
    r = api(base, "/event/delete", cookie, {"eventId": ev_id})
    return r.get("code") == 200

def scrobble(base, cookie, song_id, source_id=None, time_sec=240):
    """模拟听歌打卡，source_id 为歌单/专辑 id，time_sec 为听歌时长（秒）"""
    params = {
        "id":       str(song_id),
        "sourceid": str(source_id or song_id),
        "time":     str(time_sec),
    }
    r = api(base, "/scrobble", cookie, params)
    return r.get("code") == 200

def qr_create(base):
    resp = api(base, "/login/qr/key")
    key = resp.get("data", {}).get("unikey", "")
    if not key:
        return {}
    data = api(base, "/login/qr/create", params={"key": key, "qrimg": True}).get("data", {})
    return {
        "key":   key,
        "qrimg": data.get("qrimg", ""),
        "qrurl": data.get("qrurl", ""),
    }

def qr_check(base, key):
    import logging
    _log = logging.getLogger("ncm.qr")
    r = api(base, "/login/qr/check", params={"key": key})
    _log.info(f"qr_check raw: {r}")
    if not r:
        return {}
    code = r.get("code", 0)
    if not code:
        return {}
    cookie = ""
    if code == 803:
        cookie = normalize_cookie(r.get("cookie", ""))
    return {"code": code, "cookie": cookie, "raw_cookie": r.get("cookie", "")}
