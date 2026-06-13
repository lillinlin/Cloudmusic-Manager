"""后台调度器"""
import json
import os
import time
import threading
import logging
from datetime import datetime, timedelta
from collections import deque

import ncm
import notifier

logger = logging.getLogger("scheduler")

DATA_DIR    = os.environ.get("DATA_DIR", "/app/data")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
STATE_PATH  = os.path.join(DATA_DIR, "state.json")
LOG_MAX     = 200

DEFAULT_CONFIG = {
    "apiBase": "",
    "runAt": "12:00",
    "quotaPerMonth": 5,
    "share": {
        "type": "song",
        "id": "1297494209",
        "msg": "本月第{{count}}次分享 ✅ {{date}}"
    },
    "telegram": {
        "token": "",
        "chat_id": ""
    },
    "accounts": []
}


def _ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Scheduler:
    def __init__(self):
        self.cfg: dict = {}
        self.state: dict = {"accounts": {}}
        self.logs: deque = deque(maxlen=LOG_MAX)
        self.runtime: dict = {}
        self.qr_sessions: dict = {}
        self._lock = threading.Lock()
        self._thread = None

    def init(self):
        """首次启动初始化：确保目录和默认配置文件存在"""
        os.makedirs(DATA_DIR, exist_ok=True)
        if not os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
            logger.info("已创建默认配置文件，请在面板中完成设置")

    # ── 日志 ─────────────────────────────────

    def log(self, msg: str, level: str = "INFO"):
        entry = {"ts": _ts(), "level": level, "msg": msg}
        self.logs.append(entry)
        getattr(logger, level.lower(), logger.info)(msg)

    # ── 配置 / 状态 ──────────────────────────

    def load_config(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                self.cfg = json.load(f)
        except Exception as e:
            self.log(f"配置加载失败：{e}，使用默认配置", "WARNING")
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

    # ── Cookie ───────────────────────────────

    def cookie_path(self, name: str) -> str:
        return os.path.join(DATA_DIR, f"cookie_{name}.txt")

    def load_cookie(self, name: str) -> str:
        p = self.cookie_path(name)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return f.read().strip()
        return ""

    def save_cookie(self, name: str, cookie: str):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(self.cookie_path(name), "w", encoding="utf-8") as f:
            f.write(cookie)

    # ── 二维码登录 ────────────────────────────

    def qr_start(self, name: str) -> dict:
        base = self.cfg.get("apiBase", "")
        if not base:
            return {"ok": False, "msg": "请先在设置中填写 API 地址"}
        data = ncm.qr_create(base)
        if not data:
            return {"ok": False, "msg": "获取二维码失败，请检查 API 地址"}
        self.qr_sessions[name] = {
            "key": data["key"], "qrimg": data["qrimg"],
            "qrurl": data["qrurl"], "status": 801, "cookie": "",
        }
        threading.Thread(target=self._qr_poll, args=(name,), daemon=True).start()
        return {"ok": True, "qrimg": data["qrimg"], "qrurl": data["qrurl"]}

    def _qr_poll(self, name: str):
        base = self.cfg.get("apiBase", "")
        key  = self.qr_sessions.get(name, {}).get("key", "")
        self.log(f"[{name}] 等待扫码…")
        for _ in range(120):   # 最多等4分钟，每2秒查一次
            time.sleep(2)
            result = ncm.qr_check(base, key)
            if not result:     # 空响应跳过，不改状态
                continue
            code = result.get("code", 0)
            if code == 0:      # 接口异常，跳过
                continue
            self.qr_sessions[name]["status"] = code
            if code == 803:
                cookie = result["cookie"]
                self.qr_sessions[name]["cookie"] = cookie
                self.save_cookie(name, cookie)
                self.log(f"[{name}] 扫码登录成功")
                self._update_runtime(name, logged_in=True)
                profile = ncm.get_user_profile(base, cookie)
                self._update_runtime(name, **profile)
                return
            if code == 800:
                self.log(f"[{name}] 二维码过期", "WARNING")
                return
            # 802 = 已扫码等确认，继续轮询
        self.log(f"[{name}] 扫码超时", "WARNING")

    def qr_status(self, name: str) -> dict:
        sess = self.qr_sessions.get(name)
        if not sess:
            return {"status": 0}
        return {"status": sess["status"]}

    # ── 运行时状态 ────────────────────────────

    def _update_runtime(self, name: str, **kwargs):
        if name not in self.runtime:
            self.runtime[name] = {
                "logged_in": False, "nickname": "", "avatar": "",
                "last_run": "", "next_run": "",
            }
        self.runtime[name].update(kwargs)

    def get_status(self) -> list:
        self.load_state()
        now   = datetime.now()
        ym    = now.strftime("%Y-%m")
        quota = self.cfg.get("quotaPerMonth", 5)
        result = []
        for acc in self.cfg.get("accounts", []):
            name = acc["name"]
            st   = self.state["accounts"].get(name, {})
            rt   = self.runtime.get(name, {})
            cookie    = self.load_cookie(name)
            logged_in = bool(cookie) and ncm.is_logged_in(self.cfg.get("apiBase", ""), cookie)
            self._update_runtime(name, logged_in=logged_in)
            result.append({
                "name":      name,
                "logged_in": logged_in,
                "nickname":  rt.get("nickname", ""),
                "avatar":    rt.get("avatar", ""),
                "ym":        st.get("ym", ym),
                "count":     st.get("count", 0),
                "quota":     quota,
                "days":      st.get("days", {}),
                "last_run":  rt.get("last_run", ""),
                "next_run":  rt.get("next_run", ""),
                "qr_status": self.qr_sessions.get(name, {}).get("status", 0),
            })
        return result

    # ── 核心执行逻辑 ──────────────────────────

    def run_once(self, force_name: str = None):
        self.load_config()
        self.load_state()
        now   = datetime.now()
        ym    = now.strftime("%Y-%m")
        today = now.strftime("%Y-%m-%d")
        day   = now.day
        quota = self.cfg.get("quotaPerMonth", 5)
        base  = self.cfg.get("apiBase", "")
        tg    = self.cfg.get("telegram", {})

        if not base:
            self.log("API 地址未配置，跳过本轮", "WARNING")
            return
        if not self.cfg.get("accounts"):
            self.log("没有账号，跳过本轮", "WARNING")
            return

        for acc in self.cfg.get("accounts", []):
            name = acc["name"]
            if force_name and name != force_name:
                continue

            self.log(f"── 账号：{name} ──")
            self._update_runtime(name, last_run=_ts())

            st = self.state["accounts"].setdefault(name, {
                "ym": ym, "count": 0, "days": {}, "event_ids": [],
                "prev_ym": "", "prev_event_ids": [],
            })

            # 检查登录
            cookie = self.load_cookie(name)
            if not cookie or not ncm.is_logged_in(base, cookie):
                self.log(f"[{name}] Cookie 失效，需要重新登录", "WARNING")
                self._update_runtime(name, logged_in=False)
                notifier.notify_login_expired(tg.get("token",""), tg.get("chat_id",""), name)
                continue
            self._update_runtime(name, logged_in=True)

            # 更新昵称（无则获取）
            if not self.runtime.get(name, {}).get("nickname"):
                profile = ncm.get_user_profile(base, cookie)
                self._update_runtime(name, **profile)

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
                    self.log(f"[{name}] 从列表匹配上月动态…")
                    uid = ncm.get_uid(base, cookie)
                    if uid:
                        events = ncm.fetch_my_events(base, cookie, uid, limit=50)
                        keyword = st["prev_ym"]
                        ids_to_delete = [e["id"] for e in events if keyword in e["msg"]]
                        if ids_to_delete:
                            self.log(f"[{name}] 匹配到 {len(ids_to_delete)} 条")
                if ids_to_delete:
                    failed, deleted = [], 0
                    for ev_id in ids_to_delete:
                        ok = ncm.delete_event(base, cookie, ev_id)
                        self.log(f"[{name}]   {'✅' if ok else '✗'} {ev_id}")
                        if not ok:
                            failed.append(ev_id)
                        else:
                            deleted += 1
                        time.sleep(0.5)
                    st["prev_event_ids"] = failed
                    if deleted:
                        notifier.notify_delete_done(tg.get("token",""), tg.get("chat_id",""), name, deleted, st.get("prev_ym",""))

            # 判断是否发布
            if st["count"] >= quota:
                self.log(f"[{name}] 本月已完成 {st['count']}/{quota}")
                self.save_state()
                continue

            if st["days"].get(today):
                self.log(f"[{name}] 今天已发过 ({st['count']}/{quota})")
                self.save_state()
                continue

            if not ((1 <= day <= 5) or (day > 5 and st["count"] < quota)):
                self.log(f"[{name}] {day}号，不在发布窗口")
                self.save_state()
                continue

            # 发布
            n = st["count"] + 1
            self.log(f"[{name}] 发布第 {n}/{quota} 次…")
            ok, ev_id, msg_sent = ncm.do_share(base, cookie, self.cfg["share"], n, today)
            if ok:
                st["count"] += 1
                st["days"][today] = True
                if ev_id:
                    st["event_ids"].append(ev_id)
                self.log(f"[{name}] ✅ 发布成功，本月 {st['count']}/{quota}")
                notifier.notify_share_success(tg.get("token",""), tg.get("chat_id",""), name, st["count"], quota, msg_sent)
                if st["count"] >= quota:
                    notifier.notify_quota_done(tg.get("token",""), tg.get("chat_id",""), name, quota)
            else:
                self.log(f"[{name}] ✗ 发布失败", "ERROR")
                notifier.notify_share_fail(tg.get("token",""), tg.get("chat_id",""), name)

            self.save_state()

        self.log("── 本轮完毕 ──")

    # ── 主循环 ────────────────────────────────

    def _next_run_time(self) -> datetime:
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
            t     = self._next_run_time()
            delta = (t - datetime.now()).total_seconds()
            next_str = t.strftime("%Y-%m-%d %H:%M")
            self.log(f"⏳ 下次执行：{next_str}")
            for acc in self.cfg.get("accounts", []):
                self._update_runtime(acc["name"], next_run=next_str)
            time.sleep(delta)
            self.run_once()

    def reload(self):
        """配置变更后重新加载（调度时间等）"""
        self.load_config()
        self.log("配置已重新加载")

    def start(self):
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()


scheduler = Scheduler()
