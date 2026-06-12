"""FastAPI 后端入口"""
import os
import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

from scheduler import scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(title="CloudMusic Dashboard")


@app.on_event("startup")
async def startup():
    scheduler.init()   # 确保 data 目录和默认 config 存在
    scheduler.load_config()
    scheduler.load_state()
    scheduler.start()


# ── 状态 ─────────────────────────────────────

@app.get("/api/status")
def get_status():
    return {"accounts": scheduler.get_status()}


@app.get("/api/logs")
def get_logs(n: int = 100):
    return {"logs": list(scheduler.logs)[-n:]}


@app.get("/api/config")
def get_config():
    cfg = dict(scheduler.cfg)
    tg = dict(cfg.get("telegram", {}))
    if tg.get("token"):
        tg["token_masked"] = tg["token"][:6] + "****"
    cfg["telegram"] = tg
    return cfg


# ── 配置保存 ──────────────────────────────────

class TelegramConfig(BaseModel):
    token: Optional[str] = ""
    chat_id: Optional[str] = ""

class ShareConfig(BaseModel):
    type: str = "song"
    id: str = ""
    msg: str = "本月第{{count}}次分享 ✅ {{date}}"

class AccountConfig(BaseModel):
    name: str

class ConfigBody(BaseModel):
    apiBase: str
    runAt: str = "12:00"
    quotaPerMonth: int = 5
    share: ShareConfig
    telegram: Optional[TelegramConfig] = None
    accounts: list[AccountConfig]

@app.post("/api/config")
def save_config(body: ConfigBody):
    data = body.dict()
    # token 如果是脱敏值就保留原来的
    old_token = scheduler.cfg.get("telegram", {}).get("token", "")
    new_token  = (data.get("telegram") or {}).get("token", "")
    if new_token and new_token.endswith("****"):
        data["telegram"]["token"] = old_token
    scheduler.cfg = data
    scheduler.save_config()
    return {"ok": True}


# ── 手动触发 ──────────────────────────────────

@app.post("/api/run")
def manual_run(name: str = None):
    import threading
    t = threading.Thread(target=scheduler.run_once, args=(name,), daemon=True)
    t.start()
    return {"ok": True}


# ── 二维码登录 ────────────────────────────────

@app.post("/api/login/start")
def login_start(name: str):
    return scheduler.qr_start(name)

@app.get("/api/login/status")
def login_status(name: str):
    return scheduler.qr_status(name)


# ── 静态前端 ──────────────────────────────────

STATIC_DIR = "/app/frontend/dist"
if os.path.exists(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=f"{STATIC_DIR}/assets"), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        return FileResponse(f"{STATIC_DIR}/index.html")