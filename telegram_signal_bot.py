from __future__ import annotations
"""
CodexBot Telegram Signal-Only Bot.

IMPORTANT:
- READ-ONLY market data. No exchange API keys are used.
- NO order placement, NO positions, NO withdrawals.
- Telegram access is private and admin-approved.
- Supports Toobit Spot and USDT-M Futures public market data.
- Existing CodexBot strategies remain available for Futures; the added
  ensemble strategy is independent and can be enabled/disabled.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import math
import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
from dotenv import load_dotenv

try:
    from config.settings import AppSettings
    from execution.toobit_client import ToobitClient
    from models.domain import SignalType
    from strategies.registry import STRATEGIES, create_strategy, strategy_spec
except Exception:
    AppSettings = None
    ToobitClient = None
    SignalType = None
    STRATEGIES = {}
    create_strategy = strategy_spec = None

load_dotenv()

LOG = logging.getLogger("codexbot_signal_only")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ADMIN_IDS = {int(x) for x in os.getenv("TELEGRAM_ADMIN_IDS", "").replace(" ", "").split(",") if x}
REFERRAL_URL = os.getenv("REFERRAL_URL", "").strip()
REFERRAL_CODE = os.getenv("REFERRAL_CODE", "").strip()
POLL_SECONDS = max(15, int(os.getenv("POLL_SECONDS", "45")))
MIN_SCORE = max(1, min(100, int(os.getenv("MIN_SCORE", "70"))))
MIN_RR = max(1.0, float(os.getenv("MIN_RR", "2.0")))
DB_PATH = Path(os.getenv("SIGNAL_DB", "telegram_signal_bot.sqlite3"))
API = "https://api.toobit.com"
TG = "https://api.telegram.org"

INTERVAL_MS = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
    "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000,
    "4h": 14_400_000, "6h": 21_600_000, "8h": 28_800_000,
    "12h": 43_200_000, "1d": 86_400_000, "1w": 604_800_000, "1M": 2_592_000_000,
}
FUTURES_INTERVAL = {"1m":"1m","3m":"3m","5m":"5m","15m":"15m","30m":"30m",
                    "1h":"1H","2h":"2H","4h":"4H","6h":"6H","8h":"8H","12h":"12H",
                    "1d":"1D","1w":"1W","1M":"1M"}

DEFAULT_SETTINGS = {
    "market": "futures",
    "symbols": "BTCUSDT",
    "timeframe": "15m",
    "strategies": "ensemble",
    "min_score": str(MIN_SCORE),
    "min_rr": str(MIN_RR),
    "enabled": "1",
    "template": (
        "🚨 {market} SIGNAL\n\n"
        "{direction} {symbol}\n"
        "⏱ {timeframe}\n"
        "💰 Entry: {entry}\n"
        "🛑 SL: {sl}\n"
        "🎯 TP1: {tp1}\n"
        "🎯 TP2: {tp2}\n"
        "⚖️ R:R: {rr}\n"
        "📊 Score: {score}%\n"
        "📈 Historical Win Rate: {winrate}\n"
        "🧠 Strategy: {strategy}\n\n"
        "⚠️ SIGNAL ONLY — NO AUTOMATIC TRADING"
    ),
}

def db():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
          chat_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
          referral TEXT, status TEXT NOT NULL DEFAULT 'pending',
          created_at TEXT NOT NULL, approved_at TEXT
        );
        CREATE TABLE IF NOT EXISTS settings(
          chat_id INTEGER PRIMARY KEY, market TEXT, symbols TEXT, timeframe TEXT,
          strategies TEXT, min_score INTEGER, min_rr REAL, enabled INTEGER, template TEXT
        );
        CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS signals(
          id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER NOT NULL,
          market TEXT, symbol TEXT, timeframe TEXT, strategy TEXT, direction TEXT,
          entry REAL, sl REAL, tp1 REAL, tp2 REAL, score REAL,
          candle_time INTEGER, created_at TEXT, outcome TEXT DEFAULT 'OPEN',
          resolved_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_signals_open ON signals(outcome, symbol, timeframe);
        """)

def get_setting(chat_id: int) -> dict:
    with db() as c:
        row = c.execute("SELECT * FROM settings WHERE chat_id=?", (chat_id,)).fetchone()
    if not row:
        return DEFAULT_SETTINGS.copy()
    return dict(row)

def set_settings(chat_id: int, **kw):
    s = get_setting(chat_id); s.update(kw)
    with db() as c:
        c.execute("""INSERT INTO settings(chat_id,market,symbols,timeframe,strategies,min_score,min_rr,enabled,template)
        VALUES(?,?,?,?,?,?,?,?,?)
        ON CONFLICT(chat_id) DO UPDATE SET market=excluded.market,symbols=excluded.symbols,
        timeframe=excluded.timeframe,strategies=excluded.strategies,min_score=excluded.min_score,
        min_rr=excluded.min_rr,enabled=excluded.enabled,template=excluded.template""",
        (chat_id,s["market"],s["symbols"],s["timeframe"],s["strategies"],int(s["min_score"]),
         float(s["min_rr"]),int(s["enabled"]),s["template"]))

def now():
    return datetime.now(timezone.utc).isoformat()

class ToobitPublic:
    def __init__(self):
        self.client = httpx.AsyncClient(base_url=API, timeout=20)

    async def close(self): await self.client.aclose()

    async def get(self, path, params=None):
        r = await self.client.get(path, params=params)
        r.raise_for_status()
        return r.json()

    async def spot_symbols(self):
        d = await self.get("/api/v1/exchangeInfo")
        return [x["symbol"] for x in d.get("symbols", []) if x.get("status","TRADING") in ("TRADING","1")]

    async def futures_symbols(self):
        d = await self.get("/api/v1/exchangeInfo")
        rows = d.get("contracts", d.get("symbols", []))
        return [x.get("symbol") for x in rows if x.get("symbol","").endswith("-SWAP-USDT") and x.get("status","TRADING") in ("TRADING","1")]

    async def tickers(self, market):
        path = "/quote/v1/ticker/24hr" if market == "spot" else "/quote/v1/contract/ticker/24hr"
        d = await self.get(path)
        return d if isinstance(d,list) else []

    async def klines(self, market, symbol, interval, limit=300):
        if market == "spot":
            p = {"symbol": symbol, "interval": interval, "limit": min(limit,1000)}
            d = await self.get("/quote/v1/klines", p)
        else:
            p = {"symbol": symbol if "-SWAP-" in symbol else symbol.replace("USDT","-SWAP-USDT"),
                 "interval": FUTURES_INTERVAL.get(interval, interval), "limit": min(limit,1000)}
            d = await self.get("/quote/v1/klines", p)
        rows=[]
        for r in d:
            if len(r)<6: continue
            rows.append([int(r[0]),float(r[1]),float(r[2]),float(r[3]),float(r[4]),float(r[5])])
        return pd.DataFrame(rows, columns=["time","open","high","low","close","volume"]).sort_values("time").drop_duplicates("time")

def indicators(df: pd.DataFrame) -> pd.DataFrame:
    x=df.copy()
    x["ema20"]=x.close.ewm(span=20,adjust=False).mean()
    x["ema50"]=x.close.ewm(span=50,adjust=False).mean()
    x["ema200"]=x.close.ewm(span=200,adjust=False).mean()
    d=x.close.diff()
    gain=d.clip(lower=0).ewm(alpha=1/14,adjust=False).mean()
    loss=(-d.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean()
    rs=gain/loss.replace(0,float("nan"))
    x["rsi"]=100-(100/(1+rs))
    ema12=x.close.ewm(span=12,adjust=False).mean()
    ema26=x.close.ewm(span=26,adjust=False).mean()
    x["macd"]=ema12-ema26
    x["macds"]=x.macd.ewm(span=9,adjust=False).mean()
    tr=pd.concat([(x.high-x.low),(x.high-x.close.shift()).abs(),(x.low-x.close.shift()).abs()],axis=1).max(axis=1)
    x["atr"]=tr.ewm(alpha=1/14,adjust=False).mean()
    x["vol_ma"]=x.volume.rolling(20).mean()
    x["hh20"]=x.high.shift(1).rolling(20).max()
    x["ll20"]=x.low.shift(1).rolling(20).min()
    return x

@dataclass
class Signal:
    direction:str; entry:float; sl:float; tp1:float; tp2:float; score:float; strategy:str; reason:str

def ensemble(df: pd.DataFrame, market: str) -> Signal|None:
    if len(df)<220: return None
    x=indicators(df); r=x.iloc[-1]; p=x.iloc[-2]
    score_long=score_short=0; reasons=[]
    # Independent ensemble components; this does not disable existing strategies.
    if r.ema20>r.ema50>r.ema200: score_long+=20; reasons.append("EMA trend")
    if r.ema20<r.ema50<r.ema200: score_short+=20; reasons.append("EMA trend")
    if r.macd>r.macds and r.macd>p.macd: score_long+=15
    if r.macd<r.macds and r.macd<p.macd: score_short+=15
    if 52<=r.rsi<=70: score_long+=15
    if 30<=r.rsi<=48: score_short+=15
    if r.close>r.hh20: score_long+=20; reasons.append("20-bar breakout")
    if r.close<r.ll20: score_short+=20; reasons.append("20-bar breakdown")
    if r.volume>1.2*r.vol_ma: score_long+=10; score_short+=10; reasons.append("volume")
    if r.close>r.ema20 and r.close>p.close: score_long+=10
    if r.close<r.ema20 and r.close<p.close: score_short+=10
    direction="LONG" if score_long>score_short else "SHORT"
    score=max(score_long,score_short)
    if score<70: return None
    entry=float(r.close); atr=float(r.atr)
    if not math.isfinite(atr) or atr<=0: return None
    if direction=="LONG":
        sl=entry-1.2*atr; risk=entry-sl; tp1=entry+2*risk; tp2=entry+3*risk
    else:
        sl=entry+1.2*atr; risk=sl-entry; tp1=entry-2*risk; tp2=entry-3*risk
    if market=="spot" and direction=="SHORT": return None
    return Signal(direction,entry,sl,tp1,tp2,float(score),"Ensemble","; ".join(reasons))

def fmt(v):
    if v is None: return "-"
    return f"{float(v):,.8g}"

async def existing_strategy(client: ToobitPublic, market: str, symbol: str, timeframe: str, key: str):
    # Existing CodexBot strategies are retained for Futures only.
    if market!="futures" or create_strategy is None: return None
    try:
        spec=strategy_spec(key)
        settings=AppSettings(symbol=symbol, strategy=key, entry_timeframe=spec.entry_timeframe, higher_timeframe=spec.higher_timeframe)
        strat=create_strategy(settings)
        entry=await client.klines("futures",symbol,settings.entry_timeframe,500)
        higher=await client.klines("futures",symbol,settings.higher_timeframe,500)
        if len(entry)<strat.warmup_bars or len(higher)<strat.warmup_bars: return None
        e=entry.rename(columns={"time":"timestamp"}); h=higher.rename(columns={"time":"timestamp"})
        for q in (e,h): q["timestamp"]=pd.to_datetime(q["timestamp"],unit="ms",utc=True)
        prepared=strat.prepare(e,h)
        if prepared.empty: return None
        row=prepared.iloc[-1]
        sig=str(row.get("signal",""))
        longv=getattr(SignalType,"LONG",None)
        shortv=getattr(SignalType,"SHORT",None)
        if sig not in {str(getattr(longv,"value","LONG")),str(getattr(shortv,"value","SHORT")),"LONG","SHORT"}: return None
        direction="LONG" if "LONG" in sig else "SHORT"
        entry=float(row["close"]); atr=float(row.get("atr", entry*0.01))
        sl=entry-1.2*atr if direction=="LONG" else entry+1.2*atr
        risk=abs(entry-sl); tp1=entry+(2*risk if direction=="LONG" else -2*risk); tp2=entry+(3*risk if direction=="LONG" else -3*risk)
        return Signal(direction,entry,sl,tp1,tp2,70.0,spec.name,str(row.get("signal_reason","existing strategy")))
    except Exception as e:
        LOG.warning("existing strategy %s/%s failed: %s",symbol,key,e)
        return None

def users_for_broadcast():
    with db() as c:
        return [r["chat_id"] for r in c.execute("SELECT chat_id FROM users WHERE status='approved'")]

def winrate(chat_id, market=None, symbol=None, strategy=None):
    q="SELECT outcome FROM signals WHERE chat_id=? AND outcome IN ('WIN','LOSS')"
    args=[chat_id]
    if market: q+=" AND market=?"; args.append(market)
    if symbol: q+=" AND symbol=?"; args.append(symbol)
    if strategy: q+=" AND strategy=?"; args.append(strategy)
    with db() as c: rows=c.execute(q,args).fetchall()
    if len(rows)<10: return "N/A (<10 resolved)"
    w=sum(r["outcome"]=="WIN" for r in rows)
    return f"{100*w/len(rows):.1f}% ({w}/{len(rows)})"

def record_signal(chat_id, market, symbol, tf, sig:Signal, candle_time):
    with db() as c:
        c.execute("""INSERT INTO signals(chat_id,market,symbol,timeframe,strategy,direction,entry,sl,tp1,tp2,score,candle_time,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",(chat_id,market,symbol,tf,sig.strategy,sig.direction,sig.entry,sig.sl,sig.tp1,sig.tp2,sig.score,candle_time,now()))

async def resolve_open(api: ToobitPublic):
    with db() as c: rows=c.execute("SELECT * FROM signals WHERE outcome='OPEN' ORDER BY id LIMIT 500").fetchall()
    for r in rows:
        try:
            df=await api.klines(r["market"],r["symbol"],r["timeframe"],300)
            future=df[df.time>r["candle_time"]]
            outcome=None
            for _,k in future.iterrows():
                if r["direction"]=="LONG":
                    hit_sl=k.low<=r["sl"]; hit_tp=k.high>=r["tp1"]
                else:
                    hit_sl=k.high>=r["sl"]; hit_tp=k.low<=r["tp1"]
                if hit_sl and hit_tp: outcome="AMBIGUOUS"; break
                if hit_tp: outcome="WIN"; break
                if hit_sl: outcome="LOSS"; break
            if outcome:
                with db() as c: c.execute("UPDATE signals SET outcome=?,resolved_at=? WHERE id=?",(outcome,now(),r["id"]))
        except Exception: continue

class Bot:
    def __init__(self, token):
        self.http=httpx.AsyncClient(base_url=f"{TG}/bot{token}",timeout=20)
        self.offset=0
    async def close(self): await self.http.aclose()
    async def send(self,chat,text,reply_markup=None):
        p={"chat_id":chat,"text":text}
        if reply_markup: p["reply_markup"]=reply_markup
        r=await self.http.post("/sendMessage",json=p); return r.json()
    async def updates(self):
        r=await self.http.get("/getUpdates",params={"offset":self.offset,"timeout":20})
        d=r.json()
        return d.get("result",[]) if d.get("ok") else []
    async def handle(self,u):
        self.offset=u["update_id"]+1
        m=u.get("message") or {}; chat=int((m.get("chat") or {}).get("id",0))
        text=(m.get("text") or "").strip()
        if not chat: return
        parts=text.split(maxsplit=1); cmd=parts[0].split("@")[0].lower() if parts else ""
        arg=parts[1].strip() if len(parts)>1 else ""
        user=m.get("from") or {}
        with db() as c:
            c.execute("""INSERT INTO users(chat_id,username,first_name,referral,status,created_at)
            VALUES(?,?,?,?, 'pending',?) ON CONFLICT(chat_id) DO UPDATE SET username=excluded.username,first_name=excluded.first_name""",
            (chat,user.get("username",""),user.get("first_name",""),arg,now()))
        if chat in ADMIN_IDS:
            if cmd=="/admin": return await self.admin(chat)
            if cmd=="/approve" and arg:
                try: uid=int(arg); 
                except: return await self.send(chat,"شناسه کاربر نامعتبر است.")
                with db() as c: c.execute("UPDATE users SET status='approved',approved_at=? WHERE chat_id=?",(now(),uid))
                return await self.send(chat,f"کاربر {uid} تأیید شد.")
            if cmd=="/reject" and arg:
                with db() as c: c.execute("UPDATE users SET status='rejected' WHERE chat_id=?",(int(arg),))
                return await self.send(chat,"کاربر رد شد.")
            if cmd=="/broadcast" and arg:
                for uid in users_for_broadcast(): await self.send(uid,arg)
                return await self.send(chat,"ارسال شد.")
            if cmd=="/template" and arg:
                set_settings(chat,template=arg); return await self.send(chat,"قالب ذخیره شد.")
        with db() as c: row=c.execute("SELECT status FROM users WHERE chat_id=?",(chat,)).fetchone()
        status=row["status"] if row else "pending"
        if cmd=="/start":
            referral=arg or REFERRAL_CODE or "ندارد"
            with db() as c: c.execute("UPDATE users SET referral=? WHERE chat_id=?",(referral,chat))
            if REFERRAL_URL:
                return await self.send(chat,f"برای درخواست دسترسی ابتدا با Referral ثبت‌نام کن:\n{REFERRAL_URL}\n\nبعد /start را دوباره بزن. درخواستت برای تأیید مدیر ثبت می‌شود.")
            return await self.send(chat,"درخواستت ثبت شد. Referral Code را در پیام /start بعد از دستور وارد کن؛ سپس مدیر تأیید می‌کند.")
        if status!="approved":
            return await self.send(chat,"🔒 دسترسی شما هنوز تأیید نشده است.\nپس از بررسی Referral توسط مدیر، دسترسی فعال می‌شود.")
        if cmd=="/stop":
            with db() as c: c.execute("UPDATE users SET status='stopped' WHERE chat_id=?",(chat,))
            return await self.send(chat,"دریافت سیگنال متوقف شد.")
        if cmd=="/settings": return await self.send(chat, self.settings_text(chat))
        if cmd=="/status": return await self.send(chat,f"✅ فعال\nWin Rate: {winrate(chat)}\n\n{self.settings_text(chat)}")
        if cmd=="/setmarket" and arg.lower() in ("spot","futures","both"):
            set_settings(chat,market=arg.lower()); return await self.send(chat,"Market ذخیره شد.")
        if cmd=="/setsymbols" and arg:
            set_settings(chat,symbols=arg.upper()); return await self.send(chat,"Symbols ذخیره شد.")
        if cmd=="/settf" and arg in INTERVAL_MS:
            set_settings(chat,timeframe=arg); return await self.send(chat,"Timeframe ذخیره شد.")
        if cmd=="/setscore":
            try: v=max(50,min(100,int(arg))); set_settings(chat,min_score=v); return await self.send(chat,f"حداقل Score={v}%")
            except: pass
        if cmd=="/help": return await self.send(chat,self.help())
        await self.send(chat,self.help())
    def settings_text(self,chat):
        s=get_setting(chat); return f"⚙️ Market: {s['market']}\nSymbols: {s['symbols']}\nTF: {s['timeframe']}\nMin Score: {s['min_score']}%\nMin R:R: {s['min_rr']}"
    def help(self):
        return ("/start [referral]\n/settings\n/setmarket spot|futures|both\n/setsymbols BTCUSDT,ETHUSDT\n/settf 5m|15m|1h|4h\n/setscore 70\n/status\n/stop\n\nفقط سیگنال؛ هیچ معامله‌ای انجام نمی‌شود.")
    async def admin(self,chat):
        with db() as c:
            pending=c.execute("SELECT chat_id,username,referral FROM users WHERE status='pending'").fetchall()
        txt="👑 ADMIN\n\nPending:\n"+("\n".join(f"{r['chat_id']} @{r['username']} ref={r['referral']}" for r in pending) if pending else "ندارد")
        txt+="\n\nبرای تأیید: /approve CHAT_ID\nبرای رد: /reject CHAT_ID"
        return await self.send(chat,txt)

async def scan(api:ToobitPublic, bot:Bot):
    approved=users_for_broadcast()
    for chat in approved:
        s=get_setting(chat)
        if not int(s.get("enabled",1)): continue
        markets=["spot","futures"] if s["market"]=="both" else [s["market"]]
        symbols=[x.strip().upper() for x in s["symbols"].split(",") if x.strip()]
        for market in markets:
            for symbol in symbols:
                actual=symbol if market=="spot" else (symbol if "-SWAP-" in symbol else symbol.replace("USDT","-SWAP-USDT"))
                try:
                    df=await api.klines(market,actual,s["timeframe"],300)
                    if len(df)<220: continue
                    # Only completed candle: drop latest in case it is still forming.
                    step=INTERVAL_MS[s["timeframe"]]
                    nowms=int(time.time()*1000)
                    df=df[df.time+step<=nowms].copy()
                    if len(df)<220: continue
                    sigs=[]
                    if "ensemble" in s["strategies"].lower() or s["strategies"].lower()=="all":
                        q=ensemble(df,market)
                        if q: sigs.append(q)
                    for key in STRATEGIES if s["strategies"].lower()=="all" else [x.strip() for x in s["strategies"].split(",") if x.strip() and x.strip()!="ensemble"]:
                        q=await existing_strategy(api,market,actual,s["timeframe"],key)
                        if q: sigs.append(q)
                    for sig in sigs:
                        if sig.score<float(s["min_score"]): continue
                        rr=abs(sig.tp1-sig.entry)/max(abs(sig.entry-sig.sl),1e-12)
                        if rr<float(s["min_rr"]): continue
                        candle=int(df.iloc[-1].time)
                        with db() as c:
                            exists=c.execute("SELECT 1 FROM signals WHERE chat_id=? AND symbol=? AND timeframe=? AND strategy=? AND candle_time=?",
                                             (chat,actual,s["timeframe"],sig.strategy,candle)).fetchone()
                        if exists: continue
                        text=s["template"].format(market=market.upper(),direction=("🟢 LONG" if sig.direction=="LONG" else "🔴 SHORT"),
                            symbol=actual,timeframe=s["timeframe"],entry=fmt(sig.entry),sl=fmt(sig.sl),
                            tp1=fmt(sig.tp1),tp2=fmt(sig.tp2),rr=f"1:{rr:.2f}",score=f"{sig.score:.0f}",
                            winrate=winrate(chat,market,actual,sig.strategy),strategy=sig.strategy)
                        await bot.send(chat,text); record_signal(chat,market,actual,s["timeframe"],sig,candle)
                except Exception as e:
                    LOG.warning("scan %s/%s: %s",market,actual,e)

async def main():
    if not TOKEN: raise SystemExit("TELEGRAM_BOT_TOKEN is missing")
    if not ADMIN_IDS: raise SystemExit("TELEGRAM_ADMIN_IDS is missing")
    init_db()
    api=ToobitPublic(); bot=Bot(TOKEN)
    try:
        while True:
            try:
                for u in await bot.updates(): await bot.handle(u)
                await resolve_open(api)
                await scan(api,bot)
            except Exception as e: LOG.exception("main cycle: %s",e)
            await asyncio.sleep(POLL_SECONDS)
    finally:
        await api.close(); await bot.close()

if __name__=="__main__":
    asyncio.run(main())
