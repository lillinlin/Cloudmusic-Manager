import json, os, time, threading, logging
from datetime import datetime, timedelta
from collections import deque

import ncm
import notifier

logger      = logging.getLogger("scheduler")
DATA_DIR    = os.environ.get("DATA_DIR", "/app/data")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
STATE_PATH  = os.path.join(DATA_DIR, "state.json")
LOG_MAX     = 300

DEFAULT_CONFIG = {
    "apiBase": "",
    "runAt": "12:00",
    "quotaPerMonth": 5,
    "share": {
        "type": "song",
        "id":   "1297494209",
        "msg":  "本月第{{count}}次分享 ✅ {{date}}"
    },
    "telegram": {"token": "", "chat_id": ""},
    "accounts": []
}

def _ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Scheduler:
    def __init__(self):
        self.cfg          = {}
        self.state        = {"accounts": {}}
        self.logs         = deque(maxlen=LOG_MAX)
        self.runtime      = {}
        self.qr_sessions  = {}
        self._lock        = threading.Lock()
        self._thread      = None

    def init(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        if not os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
            logger.info("已创建默认配置文件")

    # ── 日志 ─────────────────────────────────
    def log(self, msg, level="INFO"):
        entry = {"ts": _ts(), "level": level, "msg": msg}
        self.logs.append(entry)
        getattr(logger, level.lower(), logger.info)(msg)

    # ── 配置 / 状态 ──────────────────────────
    def load_config(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                self.cfg = json.load(f)
        except Exception as e:
            self.log(f"配置加载失败：{e}", "WARNING")
            self.cfg = dict(DEFAULT_CONFIG)

    def save_config(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self.cfg, f, ensure_ascii=False, indent=2)
        self.log("配置已保存")

    def load_state(self):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                self.state = json.load(f)
        except Exception:
            self.state = {"accounts": {}}

    def save_state(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def reload(self):
        self.load_config()
        self.log("配置已重新加载")

    # ── Cookie ───────────────────────────────
    def cookie_path(self, name):
        return os.path.join(DATA_DIR, f"cookie_{name}.txt")

    def load_cookie(self, name):
        p = self.cookie_path(name)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return f.read().strip()
        return ""

    def save_cookie(self, name, cookie):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(self.cookie_path(name), "w", encoding="utf-8") as f:
            f.write(cookie)

    # ── 二维码登录 ────────────────────────────
    def qr_start(self, name):
        base = self.cfg.get("apiBase", "")
        if not base:
            return {"ok": False, "msg": "请先在设置中填写 API 地址"}
        data = ncm.qr_create(base)
        if not data:
            return {"ok": False, "msg": "获取二维码失败，请检查 API 地址"}
        self.qr_sessions[name] = {
            "key":    data["key"],
            "qrimg":  data["qrimg"],
            "qrurl":  data["qrurl"],
            "status": 801,
            "cookie": "",
        }
        threading.Thread(target=self._qr_poll, args=(name,), daemon=True).start()
        return {"ok": True, "qrimg": data["qrimg"], "qrurl": data["qrurl"]}

    def _qr_poll(self, name):
        base = self.cfg.get("apiBase", "")
        key  = self.qr_sessions.get(name, {}).get("key", "")
        self.log(f"[{name}] 等待扫码…")

        confirmed       = False
        empty_after_802 = 0
        last_802_cookie = ""

        for _ in range(240):
            time.sleep(0.8 if confirmed else 2)
            result = ncm.qr_check(base, key)

            if not result:
                if confirmed:
                    empty_after_802 += 1
                    if empty_after_802 <= 5:
                        time.sleep(0.3)
                        continue
                continue

            code = result.get("code", 0)
            if not code:
                continue

            self.qr_sessions[name]["status"] = code

            if code == 802:
                confirmed       = True
                empty_after_802 = 0
                last_802_cookie = ncm.normalize_cookie(result.get("raw_cookie", ""))
                self.log(f"[{name}] 已扫码，等待确认…")
                continue

            if code == 803:
                self._login_success(name, result["cookie"])
                return

            if code == 800:
                if confirmed and last_802_cookie:
                    self.log(f"[{name}] 802→800 流程，使用 802 cookie 登录")
                    self._login_success(name, last_802_cookie)
                    return
                self.log(f"[{name}] 二维码过期", "WARNING")
                return

        self.log(f"[{name}] 扫码超时", "WARNING")

    def _login_success(self, name, cookie):
        self.qr_sessions[name]["cookie"] = cookie
        self.qr_sessions[name]["status"] = 803
        self.save_cookie(name, cookie)
        self.log(f"[{name}] 登录成功")
        self._update_runtime(name, logged_in=True)
        base    = self.cfg.get("apiBase", "")
        profile = ncm.get_user_profile(base, cookie)
        self._update_runtime(name, **profile)

    def qr_status(self, name):
        sess = self.qr_sessions.get(name)
        if not sess:
            return {"status": 0}
        return {"status": sess["status"]}

    # ── 运行时状态 ────────────────────────────
    def _update_runtime(self, name, **kwargs):
        if name not in self.runtime:
            self.runtime[name] = {
                "logged_in": False,
                "nickname":  "",
                "avatar":    "",
                "last_run":  "",
                "next_run":  "",
            }
        self.runtime[name].update(kwargs)

    def get_status(self):
        self.load_state()
        now   = datetime.now()
        ym    = now.strftime("%Y-%m")
        quota = self.cfg.get("quotaPerMonth", 5)
        result = []

        for acc in self.cfg.get("accounts", []):
            name      = acc["name"]
            role      = acc.get("role", "sharer")
            st        = self.state["accounts"].get(name, {})
            rt        = self.runtime.get(name, {})
            cookie    = self.load_cookie(name)
            logged_in = bool(cookie) and ncm.is_logged_in(self.cfg.get("apiBase", ""), cookie)
            self._update_runtime(name, logged_in=logged_in)

            item = {
                "name":      name,
                "role":      role,
                "logged_in": logged_in,
                "nickname":  rt.get("nickname", ""),
                "avatar":    rt.get("avatar", ""),
                "last_run":  rt.get("last_run", ""),
                "next_run":  rt.get("next_run", ""),
                "qr_status": self.qr_sessions.get(name, {}).get("status", 0),
                # sharer
                "ym":    st.get("ym", ym),
                "count": st.get("count", 0),
                "quota": quota,
                "days":  st.get("days", {}),
                # listener
                "songs":         acc.get("songs", []),
                "song_index":    st.get("song_index", 0),
                "song_listened": st.get("song_listened", 0),
                "listen_daily":  acc.get("listen_daily", 10),
                # 通用
                "song_id": acc.get("song_id", self.cfg.get("share", {}).get("id", "")),
            }
            result.append(item)

        return result

    # ── 分享逻辑 ──────────────────────────────
    def _run_sharer(self, acc, cookie, base, tg, now):
        name  = acc["name"]
        ym    = now.strftime("%Y-%m")
        today = now.strftime("%Y-%m-%d")
        day   = now.day
        quota = self.cfg.get("quotaPerMonth", 5)

        st = self.state["accounts"].setdefault(name, {
            "ym": ym, "count": 0, "days": {}, "event_ids": [],
            "prev_ym": "", "prev_event_ids": [],
        })

        # 月份切换
        if st.get("ym") != ym:
            self.log(f"[{name}] 新月份 {ym}，归档上月")
            st["prev_ym"]        = st.get("ym", "")
            st["prev_event_ids"] = st.get("event_ids", [])
            st.update({"ym": ym, "count": 0, "days": {}, "event_ids": []})

        # 月初删除上月动态
        if day == 1:
            ids_to_delete = list(st.get("prev_event_ids", []))
            if not ids_to_delete and st.get("prev_ym"):
                uid = ncm.get_uid(base, cookie)
                if uid:
                    events  = ncm.fetch_my_events(base, cookie, uid, limit=50)
                    keyword = st["prev_ym"]
                    ids_to_delete = [e["id"] for e in events if keyword in e["msg"]]
                    if ids_to_delete:
                        self.log(f"[{name}] 匹配到上月 {len(ids_to_delete)} 条动态")
            if ids_to_delete:
                failed, deleted = [], 0
                for ev_id in ids_to_delete:
                    ok = ncm.delete_event(base, cookie, ev_id)
                    self.log(f"[{name}]   {'✅' if ok else '✗'} 删除 {ev_id}")
                    if ok:
                        deleted += 1
                    else:
                        failed.append(ev_id)
                    time.sleep(0.5)
                st["prev_event_ids"] = failed
                if deleted:
                    notifier.notify_delete_done(
                        tg.get("token", ""), tg.get("chat_id", ""),
                        name, deleted, st.get("prev_ym", "")
                    )

        if st["count"] >= quota:
            self.log(f"[{name}] 本月已完成 {st['count']}/{quota}")
            return
        if st["days"].get(today):
            self.log(f"[{name}] 今天已发过 ({st['count']}/{quota})")
            return
        if not ((1 <= day <= 5) or (day > 5 and st["count"] < quota)):
            self.log(f"[{name}] {day} 号，不在发布窗口")
            return

        share_cfg = dict(self.cfg.get("share", {}))
        if acc.get("song_id"):
            share_cfg["id"] = acc["song_id"]

        n = st["count"] + 1
        self.log(f"[{name}] 发布第 {n}/{quota} 次…")
        ok, ev_id, msg_sent = ncm.do_share(base, cookie, share_cfg, n, today)
        if ok:
            st["count"] += 1
            st["days"][today] = True
            if ev_id:
                st["event_ids"].append(ev_id)
            self.log(f"[{name}] ✅ 发布成功，本月 {st['count']}/{quota}")
            notifier.notify_share_success(
                tg.get("token", ""), tg.get("chat_id", ""),
                name, st["count"], quota, msg_sent
            )
            if st["count"] >= quota:
                notifier.notify_quota_done(
                    tg.get("token", ""), tg.get("chat_id", ""), name, quota
                )
        else:
            self.log(f"[{name}] ✗ 发布失败", "ERROR")
            notifier.notify_share_fail(tg.get("token", ""), tg.get("chat_id", ""), name)

    # ── 听歌保活逻辑 ──────────────────────────
    def _run_listener(self, acc, cookie, base, now):
        name  = acc["name"]
        month = now.strftime("%Y-%m")
        songs = acc.get("songs", [])

        if not songs:
            self.log(f"[{name}] 歌单为空，跳过听歌", "WARNING")
            return

        st = self.state["accounts"].setdefault(name, {
            "listen_month":  "",
            "song_index":    0,
            "song_listened": 0,
        })

        # 新月份重置
        if st.get("listen_month") != month:
            st["listen_month"]  = month
            st["song_index"]    = 0
            st["song_listened"] = 0
            self.log(f"[{name}] 新月份，歌单进度重置")

        idx = st.get("song_index", 0)
        if idx >= len(songs):
            self.log(f"[{name}] 本月歌单已全部听完")
            return

        current = songs[idx]
        song_id = current.get("song_id", "")
        target  = current.get("times", 3)
        done    = st.get("song_listened", 0)

        if not song_id:
            self.log(f"[{name}] 第 {idx+1} 首歌曲ID为空，跳过", "WARNING")
            st["song_index"]    += 1
            st["song_listened"]  = 0
            return

        # 当前歌曲已听完，切下一首
        if done >= target:
            st["song_index"]    += 1
            st["song_listened"]  = 0
            idx = st["song_index"]
            if idx >= len(songs):
                self.log(f"[{name}] 🎉 本月歌单全部听完")
                return
            current = songs[idx]
            song_id = current.get("song_id", "")
            target  = current.get("times", 3)
            done    = 0
            self.log(f"[{name}] 切换到第 {idx+1} 首：{song_id}")

        remaining = target - done
        self.log(f"[{name}] 🎵 第 {idx+1}/{len(songs)} 首（{song_id}），还需听 {remaining} 次")

        for _ in range(remaining):
            ok = ncm.scrobble(base, cookie, song_id)
            if ok:
                st["song_listened"] += 1
                self.log(f"[{name}]   ✅ {st['song_listened']}/{target} 次")
            else:
                self.log(f"[{name}]   ✗ 听歌请求失败", "WARNING")
                break
            time.sleep(2)

        # 听完后推进到下一首
        if st["song_listened"] >= target:
            st["song_index"]    += 1
            st["song_listened"]  = 0
            if st["song_index"] >= len(songs):
                self.log(f"[{name}] 🎉 本月歌单全部听完")
            else:
                self.log(f"[{name}] 当前歌曲听完，下次从第 {st['song_index']+1} 首继续")

    # ── 主执行入口 ────────────────────────────
    def run_once(self, force_name=None):
        self.load_config()
        self.load_state()
        now  = datetime.now()
        base = self.cfg.get("apiBase", "")
        tg   = self.cfg.get("telegram", {})

        if not base:
            self.log("API 地址未配置，跳过", "WARNING")
            return
        if not self.cfg.get("accounts"):
            self.log("没有账号，跳过", "WARNING")
            return

        for acc in self.cfg.get("accounts", []):
            name = acc["name"]
            if force_name and name != force_name:
                continue

            role = acc.get("role", "sharer")
            self.log(f"── 账号：{name} ({role}) ──")
            self._update_runtime(name, last_run=_ts())

            cookie = self.load_cookie(name)
            if not cookie or not ncm.is_logged_in(base, cookie):
                self.log(f"[{name}] Cookie 失效", "WARNING")
                self._update_runtime(name, logged_in=False)
                notifier.notify_login_expired(
                    tg.get("token", ""), tg.get("chat_id", ""), name
                )
                continue

            self._update_runtime(name, logged_in=True)

            if not self.runtime.get(name, {}).get("nickname"):
                profile = ncm.get_user_profile(base, cookie)
                self._update_runtime(name, **profile)

            if role == "listener":
                self._run_listener(acc, cookie, base, now)
            else:
                self._run_sharer(acc, cookie, base, tg, now)

            self.save_state()

        self.log("── 本轮完毕 ──")

    # ── 主循环 ────────────────────────────────
    def _next_run_time(self):
        h, m = map(int, self.cfg.get("runAt", "12:00").split(":"))
        t = datetime.now().replace(hour=h, minute=m, second=0, microsecond=0)
        if t <= datetime.now():
            t += timedelta(days=1)
        return t

    def _loop(self):
        self.log("🚀 调度器启动")
        self.load_config()
        self.run_once()
        while True:
            t        = self._next_run_time()
            delta    = (t - datetime.now()).total_seconds()
            next_str = t.strftime("%Y-%m-%d %H:%M")
            self.log(f"⏳ 下次执行：{next_str}")
            for acc in self.cfg.get("accounts", []):
                self._update_runtime(acc["name"], next_run=next_str)
            time.sleep(delta)
            self.run_once()

    def start(self):
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()


scheduler = Scheduler()
