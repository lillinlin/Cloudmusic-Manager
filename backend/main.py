"""FastAPI 后端"""
import os, hashlib, secrets, logging
from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional

from scheduler import scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
app = FastAPI(title="CloudMusic Dashboard")
bearer = HTTPBearer(auto_error=False)

# ── Token 认证 ────────────────────────────────
_tokens: set[str] = set()

def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def check_auth(cred: HTTPAuthorizationCredentials = Depends(bearer)):
    if not cred or cred.credentials not in _tokens:
        raise HTTPException(status_code=401, detail="未登录")

# ── 启动 ──────────────────────────────────────
@app.on_event("startup")
async def startup():
    scheduler.init()
    scheduler.load_config()
    scheduler.load_state()
    scheduler.start()

# ── 认证相关（无需 token）────────────────────

class AuthBody(BaseModel):
    username: str
    password: str

@app.get("/api/auth/status")
def auth_status():
    """前端用来判断是否已设置过密码、是否需要初始化"""
    cfg = scheduler.cfg
    has_cred = bool(cfg.get("auth", {}).get("password_hash"))
    return {"initialized": has_cred}

@app.post("/api/auth/setup")
def auth_setup(body: AuthBody):
    """首次设置用户名密码"""
    cfg = scheduler.cfg
    if cfg.get("auth", {}).get("password_hash"):
        raise HTTPException(status_code=400, detail="已设置过密码，请使用登录接口")
    cfg.setdefault("auth", {})
    cfg["auth"]["username"]      = body.username
    cfg["auth"]["password_hash"] = _hash(body.password)
    scheduler.save_config()
    token = secrets.token_hex(32)
    _tokens.add(token)
    return {"ok": True, "token": token}

@app.post("/api/auth/login")
def auth_login(body: AuthBody):
    cfg = scheduler.cfg
    auth = cfg.get("auth", {})
    if not auth.get("password_hash"):
        raise HTTPException(status_code=400, detail="尚未设置密码")
    if body.username != auth.get("username") or _hash(body.password) != auth["password_hash"]:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = secrets.token_hex(32)
    _tokens.add(token)
    return {"ok": True, "token": token}

@app.post("/api/auth/logout")
def auth_logout(cred: HTTPAuthorizationCredentials = Depends(bearer)):
    if cred and cred.credentials in _tokens:
        _tokens.discard(cred.credentials)
    return {"ok": True}

@app.post("/api/auth/change_password")
def change_password(body: AuthBody, _=Depends(check_auth)):
    cfg = scheduler.cfg
    cfg.setdefault("auth", {})
    cfg["auth"]["username"]      = body.username
    cfg["auth"]["password_hash"] = _hash(body.password)
    scheduler.save_config()
    _tokens.clear()   # 踢掉所有会话，强制重新登录
    return {"ok": True}

# ── 以下接口全部需要认证 ──────────────────────

@app.get("/api/status")
def get_status(_=Depends(check_auth)):
    return {"accounts": scheduler.get_status()}

@app.get("/api/logs")
def get_logs(n: int = 100, _=Depends(check_auth)):
    return {"logs": list(scheduler.logs)[-n:]}

@app.get("/api/config")
def get_config(_=Depends(check_auth)):
    cfg = dict(scheduler.cfg)
    cfg.pop("auth", None)   # 不返回密码 hash
    tg = dict(cfg.get("telegram", {}))
    if tg.get("token"):
        tg["token"] = tg["token"][:6] + "****"
    cfg["telegram"] = tg
    return cfg

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
def save_config(body: ConfigBody, _=Depends(check_auth)):
    data = body.dict()
    old_token = scheduler.cfg.get("telegram", {}).get("token", "")
    new_token  = (data.get("telegram") or {}).get("token", "")
    if new_token and new_token.endswith("****"):
        data["telegram"]["token"] = old_token
    # 保留 auth 字段
    data["auth"] = scheduler.cfg.get("auth", {})
    scheduler.cfg = data
    scheduler.save_config()
    # 重启调度器使新配置生效
    scheduler.reload()
    return {"ok": True}

@app.post("/api/run")
def manual_run(name: str = None, _=Depends(check_auth)):
    import threading
    threading.Thread(target=scheduler.run_once, args=(name,), daemon=True).start()
    return {"ok": True}

@app.post("/api/login/start")
def login_start(name: str, _=Depends(check_auth)):
    return scheduler.qr_start(name)

@app.get("/api/login/status")
def login_status(name: str, _=Depends(check_auth)):
    return scheduler.qr_status(name)

# ── 账号管理 ──────────────────────────────────

@app.post("/api/accounts/add")
def add_account(name: str, _=Depends(check_auth)):
    accounts = scheduler.cfg.get("accounts", [])
    if any(a["name"] == name for a in accounts):
        raise HTTPException(status_code=400, detail="账号名已存在")
    accounts.append({"name": name})
    scheduler.cfg["accounts"] = accounts
    scheduler.save_config()
    return {"ok": True}

@app.delete("/api/accounts/{name}")
def del_account(name: str, _=Depends(check_auth)):
    accounts = scheduler.cfg.get("accounts", [])
    scheduler.cfg["accounts"] = [a for a in accounts if a["name"] != name]
    scheduler.save_config()
    # 删除 cookie 文件
    p = scheduler.cookie_path(name)
    if os.path.exists(p):
        os.remove(p)
    return {"ok": True}

# ── 静态前端 ──────────────────────────────────
STATIC_DIR = "/app/frontend/dist"
if os.path.exists(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=f"{STATIC_DIR}/assets"), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        return FileResponse(f"{STATIC_DIR}/index.html")
