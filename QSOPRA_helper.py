# -*- coding: utf-8 -*-
"""
QSOPRA Helper · Remaster 2.0
Фиолетовый стиль · Жалобы · Биржа · Модерация · Роли
Главный владелец: @QSOPRA_baby
"""

import os
import re
import time
import random
import sqlite3
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, ChatPermissions
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)
from telegram.constants import ChatMemberStatus

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN", "8874641769:AAEZoWbXbY4TW7mII2uqaDUJlZlxkWlgtic").strip()
MAIN_ADMIN = os.getenv("MAIN_ADMIN", "QSOPRA_baby").strip().lstrip("@")
MAIN_ADMIN_ID = int(os.getenv("MAIN_ADMIN_ID", "0") or 0)

if not TOKEN:
    raise RuntimeError("Укажите BOT_TOKEN")

DB_PATH = Path("qsopra_helper.db")
ONLINE_TIMEOUT = 300
ONLINE_USERS = {}
MIN_BET = 25
VERSION = "2.2"
PRICE_TICK_SEC = 3600  # автообновление курса раз в час

# ── Антифлуд и спам-фильтры ──
SPAM_WINDOW = 6          # окно антифлуда (сек)
SPAM_MAX_MSG = 4         # сообщений в окне → мут
SPAM_SAME_LIMIT = 3      # одинаковый текст ×N → мут
SPAM_WARN_AT = 3         # предупреждение с N-го сообщения
SPAM_MUTE_SEC = 3600     # мут 1 час
SPAM_MAX_LINKS = 3       # ссылок в одном сообщении
SPAM_MAX_MENTIONS = 5    # @упоминаний в одном сообщении
SPAM_CAPS_RATIO = 0.7    # доля ЗАГЛАВНЫХ (мин. 12 символов)
SPAM_CAPS_MIN_LEN = 12
# key: (chat_id, user_id) -> list of (timestamp, text)
_SPAM_LOG = {}

# Автобан по варнам
WARN_LIMIT = 3       # столько варнов → автобан
WARN_BAN_SEC = 0     # 0 = навсегда; иначе секунды (86400 = 1 день)

# Биржа 40+ · крипта и акции · названия «живые», цены выше
EXCHANGE = {
    # ── Крипта ──
    "HLN":  {"name": "Гелионит",      "emoji": "💜", "base": 8500,  "cat": "crypto"},
    "NXA":  {"name": "Нокса",         "emoji": "🌑", "base": 12400, "cat": "crypto"},
    "AML":  {"name": "Аметилин",      "emoji": "💎", "base": 19800, "cat": "crypto"},
    "VLC":  {"name": "Виолеткоин",    "emoji": "🔮", "base": 27600, "cat": "crypto"},
    "QZR":  {"name": "Квазар-Q",      "emoji": "✨", "base": 45200, "cat": "crypto"},
    "DRK":  {"name": "Даркпульс",     "emoji": "🖤", "base": 15600, "cat": "crypto"},
    "LUM":  {"name": "Лумин",         "emoji": "🌙", "base": 9200,  "cat": "crypto"},
    "ORB":  {"name": "Орбиток",       "emoji": "🪐", "base": 33400, "cat": "crypto"},
    "PHX":  {"name": "Феникс-Q",      "emoji": "🔥", "base": 22100, "cat": "crypto"},
    "SHD":  {"name": "Шедоулин",      "emoji": "👤", "base": 11300, "cat": "crypto"},
    "CRY":  {"name": "Кристаллин",    "emoji": "💠", "base": 18700, "cat": "crypto"},
    "NEB":  {"name": "Небулкоин",     "emoji": "🌌", "base": 25900, "cat": "crypto"},
    "VOR":  {"name": "Вортекс",       "emoji": "🌀", "base": 30100, "cat": "crypto"},
    "AUR":  {"name": "Аурора-X",      "emoji": "🌅", "base": 14200, "cat": "crypto"},
    "GLX":  {"name": "Галаксион",     "emoji": "⭐", "base": 40800, "cat": "crypto"},
    "MTR":  {"name": "Метеорит",      "emoji": "☄️", "base": 16700, "cat": "crypto"},
    "PLM":  {"name": "Плазмин",       "emoji": "⚡", "base": 9900,  "cat": "crypto"},
    "ECH":  {"name": "Эхочейн",       "emoji": "📡", "base": 21400, "cat": "crypto"},
    "SIL":  {"name": "Сильверин",     "emoji": "🪙", "base": 7800,  "cat": "crypto"},
    "NOC":  {"name": "Ноктюрн",       "emoji": "🦇", "base": 13500, "cat": "crypto"},
    "RFT":  {"name": "Рифткоин",      "emoji": "🌊", "base": 24600, "cat": "crypto"},
    "ZNT":  {"name": "Зенит-Q",       "emoji": "🔆", "base": 38200, "cat": "crypto"},
    # ── Акции ──
    "QSP":  {"name": "QSOPRA Soft",   "emoji": "🖥️", "base": 52000, "cat": "stock"},
    "NVX":  {"name": "NovaX Labs",    "emoji": "🔬", "base": 67800, "cat": "stock"},
    "PRP":  {"name": "Purple Media",  "emoji": "📺", "base": 41500, "cat": "stock"},
    "STN":  {"name": "StoneGate",     "emoji": "🏗️", "base": 28900, "cat": "stock"},
    "FLW":  {"name": "FlowEnergy",    "emoji": "🔋", "base": 35600, "cat": "stock"},
    "CLD":  {"name": "CloudNest",     "emoji": "☁️", "base": 49300, "cat": "stock"},
    "BIO":  {"name": "BioViolet",     "emoji": "🧬", "base": 72100, "cat": "stock"},
    "ARC":  {"name": "ArcMotors",     "emoji": "🚗", "base": 55800, "cat": "stock"},
    "LUN":  {"name": "LunaRetail",    "emoji": "🛒", "base": 31200, "cat": "stock"},
    "HRZ":  {"name": "Horizon Bank",  "emoji": "🏦", "base": 88400, "cat": "stock"},
    "SKR":  {"name": "SkyRail",       "emoji": "🚄", "base": 44700, "cat": "stock"},
    "OCN":  {"name": "OceanFoods",    "emoji": "🐟", "base": 19800, "cat": "stock"},
    "PLT":  {"name": "Platinum AG",   "emoji": "⚙️", "base": 63500, "cat": "stock"},
    "DRG":  {"name": "DragonGames",   "emoji": "🎮", "base": 27400, "cat": "stock"},
    "MED":  {"name": "MediCore",      "emoji": "🏥", "base": 59100, "cat": "stock"},
    "AGR":  {"name": "AgroPrime",     "emoji": "🌾", "base": 22600, "cat": "stock"},
    "NET":  {"name": "NetPulse",      "emoji": "📶", "base": 46800, "cat": "stock"},
    "SPK":  {"name": "SparkTech",     "emoji": "💡", "base": 33900, "cat": "stock"},
    "FRS":  {"name": "ForestWood",    "emoji": "🌲", "base": 15700, "cat": "stock"},
    "GLD":  {"name": "GoldRiver",     "emoji": "🥇", "base": 95200, "cat": "stock"},
    "ICE":  {"name": "IceLogistics",  "emoji": "❄️", "base": 38300, "cat": "stock"},
    "SUN":  {"name": "SunPower Co",   "emoji": "☀️", "base": 51200, "cat": "stock"},
}

# Полные права для размута (совместимо с PTB 20+)
UNMUTE_PERMS = ChatPermissions(
    can_send_messages=True,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
    can_change_info=False,
    can_invite_users=True,
    can_pin_messages=False,
)

MUTE_PERMS = ChatPermissions(
    can_send_messages=False,
    can_send_audios=False,
    can_send_documents=False,
    can_send_photos=False,
    can_send_videos=False,
    can_send_video_notes=False,
    can_send_voice_notes=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
)

# ═══════════════════════════════════════════════════════════
# БАЗА
# ═══════════════════════════════════════════════════════════
def db():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=20000")
    return con

def q(sql, args=(), fetch=True):
    with db() as con:
        cur = con.execute(sql, args)
        con.commit()
        return cur.fetchall() if fetch else None

def init_db():
    q("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        balance INTEGER DEFAULT 1000,
        warns INTEGER DEFAULT 0,
        wins INTEGER DEFAULT 0,
        losses INTEGER DEFAULT 0,
        rating INTEGER DEFAULT 0,
        last_daily TEXT,
        registered TEXT
    )""", fetch=False)
    q("""CREATE TABLE IF NOT EXISTS marriages (
        user1 INTEGER PRIMARY KEY, user2 INTEGER, date TEXT
    )""", fetch=False)
    q("""CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY, username TEXT
    )""", fetch=False)
    q("""CREATE TABLE IF NOT EXISTS moderators (
        user_id INTEGER PRIMARY KEY, username TEXT
    )""", fetch=False)
    q("""CREATE TABLE IF NOT EXISTS owners (
        user_id INTEGER PRIMARY KEY, username TEXT, granted_at TEXT
    )""", fetch=False)
    q("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY, value TEXT
    )""", fetch=False)
    q("""CREATE TABLE IF NOT EXISTS complaints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_id INTEGER,
        from_name TEXT,
        text TEXT,
        status TEXT DEFAULT 'open',
        created TEXT,
        handled_by INTEGER,
        target_id INTEGER,
        target_name TEXT
    )""", fetch=False)
    try:
        cols_c = [r[1] for r in q("PRAGMA table_info(complaints)")]
        if "target_id" not in cols_c:
            q("ALTER TABLE complaints ADD COLUMN target_id INTEGER", fetch=False)
        if "target_name" not in cols_c:
            q("ALTER TABLE complaints ADD COLUMN target_name TEXT", fetch=False)
    except Exception:
        pass
    q("""CREATE TABLE IF NOT EXISTS portfolio (
        user_id INTEGER,
        symbol TEXT,
        amount INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, symbol)
    )""", fetch=False)
    q("""CREATE TABLE IF NOT EXISTS traders (
        user_id INTEGER PRIMARY KEY,
        last_active TEXT
    )""", fetch=False)
    q("""CREATE TABLE IF NOT EXISTS user_settings (
        user_id INTEGER,
        key TEXT,
        value TEXT,
        PRIMARY KEY (user_id, key)
    )""", fetch=False)
    q("""CREATE TABLE IF NOT EXISTS chat_members (
        chat_id INTEGER,
        user_id INTEGER,
        username TEXT,
        full_name TEXT,
        last_seen TEXT,
        PRIMARY KEY (chat_id, user_id)
    )""", fetch=False)
    q("""CREATE TABLE IF NOT EXISTS market_prices (
        symbol TEXT PRIMARY KEY,
        price INTEGER,
        prev_price INTEGER,
        updated TEXT
    )""", fetch=False)
    q("INSERT OR IGNORE INTO settings(key, value) VALUES('maintenance', '0')", fetch=False)

    cols = [r[1] for r in q("PRAGMA table_info(users)")]
    for col, ddl in [
        ("wins", "ALTER TABLE users ADD COLUMN wins INTEGER DEFAULT 0"),
        ("losses", "ALTER TABLE users ADD COLUMN losses INTEGER DEFAULT 0"),
        ("rating", "ALTER TABLE users ADD COLUMN rating INTEGER DEFAULT 0"),
        ("last_daily", "ALTER TABLE users ADD COLUMN last_daily TEXT"),
    ]:
        if col not in cols:
            try:
                q(ddl, fetch=False)
            except Exception:
                pass

    for sym, meta in EXCHANGE.items():
        q("INSERT OR IGNORE INTO market_prices(symbol, price, prev_price, updated) VALUES (?,?,?,?)",
          (sym, meta["base"], meta["base"], datetime.now().isoformat()), fetch=False)
    # миграция prev_price
    try:
        cols_m = [r[1] for r in q("PRAGMA table_info(market_prices)")]
        if "prev_price" not in cols_m:
            q("ALTER TABLE market_prices ADD COLUMN prev_price INTEGER", fetch=False)
            q("UPDATE market_prices SET prev_price = price", fetch=False)
    except Exception:
        pass

    if MAIN_ADMIN_ID:
        q("INSERT OR IGNORE INTO owners(user_id, username, granted_at) VALUES (?,?,?)",
          (MAIN_ADMIN_ID, MAIN_ADMIN or f"id{MAIN_ADMIN_ID}", datetime.now().isoformat()), fetch=False)
        q("INSERT OR IGNORE INTO admins(user_id, username) VALUES (?,?)",
          (MAIN_ADMIN_ID, MAIN_ADMIN or f"id{MAIN_ADMIN_ID}"), fetch=False)

def ensure_user(user):
    row = q("SELECT user_id FROM users WHERE user_id=?", (user.id,))
    if not row:
        q("INSERT INTO users (user_id, username, full_name, registered) VALUES (?,?,?,?)",
          (user.id, user.username, user.full_name, datetime.now().isoformat()), fetch=False)
    else:
        q("UPDATE users SET username=?, full_name=? WHERE user_id=?",
          (user.username, user.full_name, user.id), fetch=False)
    if user.username and user.username.lower() == MAIN_ADMIN.lower():
        q("INSERT OR IGNORE INTO owners(user_id, username, granted_at) VALUES (?,?,?)",
          (user.id, user.username, datetime.now().isoformat()), fetch=False)
        q("INSERT OR IGNORE INTO admins(user_id, username) VALUES (?,?)",
          (user.id, user.username), fetch=False)

def get_user(uid):
    r = q("SELECT user_id, username, full_name, balance, warns, wins, losses, rating, last_daily FROM users WHERE user_id=?", (uid,))
    return r[0] if r else None

def add_balance(uid, amount):
    q("UPDATE users SET balance = MAX(0, balance + ?) WHERE user_id=?", (amount, uid), fetch=False)

def add_warn(uid):
    q("UPDATE users SET warns = warns + 1 WHERE user_id=?", (uid,), fetch=False)
    r = q("SELECT warns FROM users WHERE user_id=?", (uid,))
    return r[0][0] if r else 0

def get_warns(uid):
    r = q("SELECT warns FROM users WHERE user_id=?", (uid,))
    return r[0][0] if r else 0

def clear_warns(uid):
    q("UPDATE users SET warns = 0 WHERE user_id=?", (uid,), fetch=False)

def warns_should_ban(count):
    return count >= WARN_LIMIT

def register_win(uid, rating_gain=5):
    q("UPDATE users SET wins = wins + 1, rating = rating + ? WHERE user_id=?", (rating_gain, uid), fetch=False)

def register_loss(uid, rating_loss=2):
    q("UPDATE users SET losses = losses + 1, rating = MAX(0, rating - ?) WHERE user_id=?", (rating_loss, uid), fetch=False)

def get_marriage(uid):
    r = q("SELECT user1, user2, date FROM marriages WHERE user1=? OR user2=?", (uid, uid))
    return r[0] if r else None

def create_marriage(u1, u2):
    q("INSERT OR REPLACE INTO marriages (user1, user2, date) VALUES (?,?,?)",
      (u1, u2, datetime.now().strftime("%d.%m.%Y")), fetch=False)

def delete_marriage(uid):
    q("DELETE FROM marriages WHERE user1=? OR user2=?", (uid, uid), fetch=False)

def get_top(category="balance", limit=10):
    order = {
        "balance": "balance DESC",
        "rating": "rating DESC",
        "wins": "wins DESC",
    }.get(category, "balance DESC")
    return q(f"SELECT user_id, full_name, balance, rating, wins FROM users ORDER BY {order} LIMIT ?", (limit,))

def maintenance_on():
    r = q("SELECT value FROM settings WHERE key='maintenance'")
    return bool(r and r[0][0] == "1")

def set_maintenance(on: bool):
    q("INSERT OR REPLACE INTO settings(key, value) VALUES('maintenance', ?)", ("1" if on else "0",), fetch=False)

def mark_online(uid):
    ONLINE_USERS[int(uid)] = time.time()

def online_count():
    now = time.time()
    return sum(1 for ts in ONLINE_USERS.values() if now - ts <= ONLINE_TIMEOUT)

def clear_staff_state(context):
    context.user_data.pop("staff_action", None)
    context.user_data.pop("pending_rp", None)
    context.user_data.pop("game", None)
    context.user_data.pop("complaint", None)
    context.user_data.pop("exchange_action", None)

# ── Жалобы на пользователей ──
def add_complaint(uid, name, text, target_id=None, target_name=None):
    q(
        """INSERT INTO complaints(from_id, from_name, text, status, created, target_id, target_name)
           VALUES (?,?,?,?,?,?,?)""",
        (
            uid,
            name,
            text,
            "open",
            datetime.now().strftime("%d.%m.%Y %H:%M"),
            target_id,
            target_name,
        ),
        fetch=False,
    )
    return q("SELECT last_insert_rowid()")[0][0]

def open_complaints(limit=15):
    return q(
        """SELECT id, from_id, from_name, text, created, target_id, target_name
           FROM complaints WHERE status='open' ORDER BY id DESC LIMIT ?""",
        (limit,),
    )

def close_complaint(cid, handler_id):
    q(
        "UPDATE complaints SET status='closed', handled_by=? WHERE id=?",
        (handler_id, cid),
        fetch=False,
    )

def get_complaint(cid):
    r = q(
        """SELECT id, from_id, from_name, text, status, created, target_id, target_name
           FROM complaints WHERE id=?""",
        (cid,),
    )
    return r[0] if r else None

def complaint_card_staff(cid, from_name, from_id, from_un, text, target_id=None, target_name=None):
    body = (
        f"От · <b>{from_name}</b> (@{from_un or '—'})\n"
        f"ID · <code>{from_id}</code>\n"
    )
    if target_id or target_name:
        body += (
            f"\n🎯 На кого · <b>{target_name or '—'}</b>\n"
            f"ID цели · <code>{target_id or '—'}</code>\n"
        )
    body += f"\n📝 {text}\n\nЗакрыть: панель → жалобы"
    return card("📩", f"ЖАЛОБА #{cid}", body)

def staff_user_ids():
    ids = set()
    for table in ("owners", "admins", "moderators"):
        for (uid,) in (q(f"SELECT user_id FROM {table}") or []):
            ids.add(uid)
    if MAIN_ADMIN_ID:
        ids.add(MAIN_ADMIN_ID)
    return ids

# ── Биржа ──
def _last_tick_ts():
    r = q("SELECT value FROM settings WHERE key='last_price_tick'")
    if not r:
        return 0
    try:
        return float(r[0][0])
    except Exception:
        return 0

def tick_prices(force=False):
    """Движение цен. Автоматически не чаще 1 раза в час (если не force)."""
    now = time.time()
    if not force and now - _last_tick_ts() < PRICE_TICK_SEC:
        return False
    for sym, meta in EXCHANGE.items():
        row = q("SELECT price FROM market_prices WHERE symbol=?", (sym,))
        price = row[0][0] if row else meta["base"]
        # крипта волатильнее акций
        if meta.get("cat") == "crypto":
            change = random.uniform(-0.09, 0.10)
        else:
            change = random.uniform(-0.04, 0.05)
        new_price = max(int(meta["base"] * 0.35), int(price * (1 + change)))
        q("INSERT OR REPLACE INTO market_prices(symbol, price, prev_price, updated) VALUES (?,?,?,?)",
          (sym, new_price, price, datetime.now().isoformat()), fetch=False)
    q("INSERT OR REPLACE INTO settings(key, value) VALUES('last_price_tick', ?)", (str(now),), fetch=False)
    return True

def maybe_auto_tick():
    """Вызывать при открытии биржи — обновит, если прошёл час."""
    return tick_prices(force=False)

def get_price(symbol):
    r = q("SELECT price FROM market_prices WHERE symbol=?", (symbol,))
    return r[0][0] if r else EXCHANGE[symbol]["base"]

def get_price_info(symbol):
    r = q("SELECT price, prev_price FROM market_prices WHERE symbol=?", (symbol,))
    if not r:
        base = EXCHANGE[symbol]["base"]
        return base, base, 0.0
    price, prev = r[0][0], (r[0][1] or r[0][0])
    pct = ((price - prev) / prev * 100) if prev else 0.0
    return price, prev, pct

def assets_by_cat(cat):
    return {s: m for s, m in EXCHANGE.items() if m.get("cat") == cat}

def next_tick_in():
    left = PRICE_TICK_SEC - (time.time() - _last_tick_ts())
    if left <= 0:
        return "сейчас"
    m = int(left // 60)
    return f"{m} мин"

def get_holding(uid, symbol):
    r = q("SELECT amount FROM portfolio WHERE user_id=? AND symbol=?", (uid, symbol))
    return r[0][0] if r else 0

def set_holding(uid, symbol, amount):
    if amount <= 0:
        q("DELETE FROM portfolio WHERE user_id=? AND symbol=?", (uid, symbol), fetch=False)
    else:
        q("INSERT OR REPLACE INTO portfolio(user_id, symbol, amount) VALUES (?,?,?)",
          (uid, symbol, amount), fetch=False)

def mark_trader(uid):
    q("INSERT OR REPLACE INTO traders(user_id, last_active) VALUES (?,?)",
      (uid, datetime.now().isoformat()), fetch=False)

def trader_ids():
    return [r[0] for r in (q("SELECT user_id FROM traders") or [])]

def portfolio_value(uid):
    total = 0
    rows = q("SELECT symbol, amount FROM portfolio WHERE user_id=?", (uid,)) or []
    for sym, amt in rows:
        total += amt * get_price(sym)
    return total

def market_summary_text():
    """Краткий обзор после обновления курса."""
    ups, downs = [], []
    for sym, meta in EXCHANGE.items():
        price, prev, pct = get_price_info(sym)
        line = f"{meta['emoji']} {meta['name']} · {money(price)} ({pct:+.1f}%)"
        if pct >= 1:
            ups.append(line)
        elif pct <= -1:
            downs.append(line)
    ups = ups[:5] or ["—"]
    downs = downs[:5] or ["—"]
    return card("📈", "КУРС ОБНОВЛЁН",
        f"Следующее обновление через ~1 час\n\n"
        f"<b>Рост</b>\n" + "\n".join(ups) + "\n\n"
        f"<b>Падение</b>\n" + "\n".join(downs) + "\n\n"
        f"Открой биржу: <code>биржа</code>"
    )

# ═══════════════════════════════════════════════════════════
# РОЛИ
# ═══════════════════════════════════════════════════════════
def is_main_owner(user):
    if not user:
        return False
    if MAIN_ADMIN_ID and user.id == MAIN_ADMIN_ID:
        return True
    if user.username and MAIN_ADMIN and user.username.lower() == MAIN_ADMIN.lower():
        return True
    return False

def is_owner(user):
    if is_main_owner(user):
        return True
    if q("SELECT 1 FROM owners WHERE user_id=?", (user.id,)):
        return True
    if user.username and q("SELECT 1 FROM owners WHERE username=? COLLATE NOCASE", (user.username,)):
        return True
    return False

def is_admin(user):
    if is_owner(user):
        return True
    if q("SELECT 1 FROM admins WHERE user_id=?", (user.id,)):
        return True
    if user.username and q("SELECT 1 FROM admins WHERE username=? COLLATE NOCASE", (user.username,)):
        return True
    return False

def is_mod(user):
    if is_admin(user):
        return True
    if q("SELECT 1 FROM moderators WHERE user_id=?", (user.id,)):
        return True
    if user.username and q("SELECT 1 FROM moderators WHERE username=? COLLATE NOCASE", (user.username,)):
        return True
    return False

def is_staff(user):
    return is_mod(user)

def grant_admin(uid, username=None):
    un = (username or "").lstrip("@") or f"id{uid}"
    q("INSERT OR REPLACE INTO admins(user_id, username) VALUES (?,?)", (uid, un), fetch=False)

def revoke_admin(uid):
    q("DELETE FROM admins WHERE user_id=?", (uid,), fetch=False)

def grant_mod(uid, username=None):
    un = (username or "").lstrip("@") or f"id{uid}"
    q("INSERT OR REPLACE INTO moderators(user_id, username) VALUES (?,?)", (uid, un), fetch=False)

def revoke_mod(uid):
    q("DELETE FROM moderators WHERE user_id=?", (uid,), fetch=False)

def grant_owner(uid, username=None):
    un = (username or "").lstrip("@") or f"id{uid}"
    q("INSERT OR REPLACE INTO owners(user_id, username, granted_at) VALUES (?,?,?)",
      (uid, un, datetime.now().isoformat()), fetch=False)
    grant_admin(uid, un)

def revoke_owner(uid):
    u = get_user(uid)
    if u and u[1] and u[1].lower() == MAIN_ADMIN.lower():
        return False
    if MAIN_ADMIN_ID and uid == MAIN_ADMIN_ID:
        return False
    q("DELETE FROM owners WHERE user_id=?", (uid,), fetch=False)
    return True

def get_role_name(uid):
    if MAIN_ADMIN_ID and uid == MAIN_ADMIN_ID:
        return "👑 Владелец"
    if q("SELECT 1 FROM owners WHERE user_id=?", (uid,)):
        return "👑 Владелец"
    if q("SELECT 1 FROM admins WHERE user_id=?", (uid,)):
        return "💜 Администратор"
    if q("SELECT 1 FROM moderators WHERE user_id=?", (uid,)):
        return "🔮 Модератор"
    return "👤 Участник"

# ═══════════════════════════════════════════════════════════
# ВИЗУАЛ
# ═══════════════════════════════════════════════════════════
def header(emoji, title):
    return f"╔══════════════╗\n  {emoji} <b>{title}</b>\n╚══════════════╝"

def card(emoji, title, body):
    return f"{header(emoji, title)}\n\n{body}"

def money(n):
    return f"{int(n):,}".replace(",", " ") + " Q"

def soft_error(kind="default"):
    """Вежливые сообщения об ошибках без технических деталей."""
    texts = {
        "default": "😔 Извините, произошла ошибка.\nПопробуйте ещё раз чуть позже.",
        "rights": "😔 Извините, не удалось выполнить действие.\nПроверьте права бота в чате.",
        "not_found": "😔 Извините, не удалось найти этого пользователя.",
        "forbidden": "😔 Извините, это действие сейчас недоступно.",
        "network": "😔 Извините, временный сбой связи.\nПопробуйте снова через минуту.",
        "mod": "😔 Извините, не удалось применить наказание.\nВозможно, у цели выше права, чем у бота.",
    }
    return texts.get(kind, texts["default"])

def parse_time(text):
    """Парсит срок: 30м · 2ч · 3д · 2мес · 15г / 15лет."""
    if not text:
        return None
    t = text.lower().replace(" ", "")
    # сначала длинные формы, чтобы «15лет» не съелось как «15л»
    patterns = [
        (r"(\d+)\s*(?:лет|года|год|г|y|years?)", 365 * 86400),
        (r"(\d+)\s*(?:мес|месяц(?:ев|а|е)?|mo|months?)", 30 * 86400),
        (r"(\d+)\s*(?:дн(?:ей|я|и)?|день|д|d|days?)", 86400),
        (r"(\d+)\s*(?:час(?:ов|а|ы)?|ч|h|hours?)", 3600),
        (r"(\d+)\s*(?:мин(?:ут[аы]?)?|м|m|min)", 60),
    ]
    for pat, mult in patterns:
        m = re.search(pat, text.lower())
        if m:
            return int(m.group(1)) * mult
    return None

def format_duration(sec):
    if not sec or sec <= 0:
        return "навсегда"
    if sec >= 365 * 86400:
        n = sec // (365 * 86400)
        return f"{n} г."
    if sec >= 30 * 86400:
        n = sec // (30 * 86400)
        return f"{n} мес."
    if sec >= 86400:
        n = sec // 86400
        return f"{n} д."
    if sec >= 3600:
        n = sec // 3600
        return f"{n} ч."
    return f"{max(1, sec // 60)} мин."

def parse_mod_reason(text):
    """
    Достаёт причину из команды.
    Примеры:
      бан @user 1д спам
      мут 2ч оскорбления
      бан 15г | флуд
    """
    if not text:
        return ""
    t = text.strip()
    # после | или —
    for sep in ("|", "—", "–"):
        if sep in t:
            part = t.split(sep, 1)[1].strip()
            if part:
                return part[:200]
    # убрать команду, @user, id, срок
    cleaned = re.sub(
        r"^(размут|разбан|бан|мут|варн|кик)\s*",
        "",
        t,
        flags=re.I,
    )
    cleaned = re.sub(r"@[A-Za-z0-9_]{3,}", " ", cleaned)
    cleaned = re.sub(r"\b\d{6,15}\b", " ", cleaned)  # user id
    cleaned = re.sub(
        r"\d+\s*(?:лет|года|год|г|y|years?|мес|месяц(?:ев|а|е)?|mo|months?|"
        r"дн(?:ей|я|и)?|день|д|d|days?|час(?:ов|а|ы)?|ч|h|hours?|"
        r"мин(?:ут[аы]?)?|м|m|min)",
        " ",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,;:-")
    return cleaned[:200] if cleaned else ""

def mod_action_footer(moderator, reason=""):
    """Строка внизу: кто выдал + ранг + причина."""
    name = moderator.full_name or moderator.username or str(moderator.id)
    un = f" @{moderator.username}" if moderator.username else ""
    role = get_role_name(moderator.id)
    lines = [
        "────────────",
        f"👤 Выдал: <b>{name}</b>{un}",
        f"🏅 Ранг: {role}",
    ]
    if reason:
        lines.append(f"📝 Причина: <i>{reason}</i>")
    return "\n".join(lines)

def get_target(update):
    if update.message and update.message.reply_to_message:
        return update.message.reply_to_message.from_user
    return None

def track_chat_member(chat_id, user):
    """Запоминает участника группы/канала — чтобы потом мутить по @юзу."""
    if not user or getattr(user, "is_bot", False):
        return
    q(
        """INSERT INTO chat_members(chat_id, user_id, username, full_name, last_seen)
           VALUES (?,?,?,?,?)
           ON CONFLICT(chat_id, user_id) DO UPDATE SET
             username=excluded.username,
             full_name=excluded.full_name,
             last_seen=excluded.last_seen""",
        (chat_id, user.id, user.username, user.full_name, datetime.now().isoformat()),
        fetch=False,
    )
    ensure_user(user)

def _count_links(text):
    if not text:
        return 0
    patterns = [
        r"https?://\S+",
        r"t\.me/\S+",
        r"telegram\.me/\S+",
        r"www\.\S+",
        r"\b\w+\.(com|ru|net|org|xyz|info|me|io|pro|cc|tk)\b",
    ]
    n = 0
    for p in patterns:
        n += len(re.findall(p, text, flags=re.I))
    return n

def _count_mentions(text):
    if not text:
        return 0
    return len(re.findall(r"@[A-Za-z0-9_]{3,}", text))

def _caps_ratio(text):
    letters = [c for c in (text or "") if c.isalpha()]
    if len(letters) < SPAM_CAPS_MIN_LEN:
        return 0.0
    upper = sum(1 for c in letters if c.isupper())
    return upper / len(letters)

def check_spam(chat_id, user_id, text):
    """
    Антифлуд + спам-фильтры.
    Возвращает (уровень, причина):
      0 — ок
      1 — предупреждение
      2 — мут
    """
    raw = text or ""
    th = raw.strip().lower()[:200]
    now = time.time()
    key = (int(chat_id), int(user_id))

    # ── Мгновенные фильтры (одно сообщение) ──
    links = _count_links(raw)
    if links >= SPAM_MAX_LINKS:
        return 2, f"много ссылок ({links})"

    mentions = _count_mentions(raw)
    if mentions >= SPAM_MAX_MENTIONS:
        return 2, f"много упоминаний ({mentions})"

    if _caps_ratio(raw) >= SPAM_CAPS_RATIO:
        return 1, "слишком много ЗАГЛАВНЫХ букв"

    # ── Антифлуд по частоте ──
    log = _SPAM_LOG.get(key, [])
    log = [(t, h) for t, h in log if now - t <= SPAM_WINDOW]
    log.append((now, th))
    _SPAM_LOG[key] = log

    same = sum(1 for _, h in log if th and h == th) if th else 0
    count = len(log)

    if same >= SPAM_SAME_LIMIT:
        return 2, "повторяющийся текст (флуд)"
    if count >= SPAM_MAX_MSG:
        return 2, "слишком много сообщений подряд (флуд)"
    if count >= SPAM_WARN_AT:
        return 1, "часто пишет"

    return 0, ""

async def anti_spam_action(bot, message, user, level, reason):
    """
    level 1 — предупреждение
    level 2 — мут 1ч + сообщение
    Работает и на админах группы (если бот выше них в списке админов).
    """
    chat_id = message.chat_id
    name = user.full_name or user.username or str(user.id)

    # удалить спам-сообщение
    try:
        await message.delete()
    except Exception:
        pass

    if level == 1:
        try:
            await bot.send_message(
                chat_id,
                f"⚠️ <b>{name}</b>, хватит спамить!\n"
                f"📝 {reason}\n"
                f"Ещё немного — и будет мут на 1 час.",
                parse_mode="HTML",
            )
        except Exception:
            pass
        return True

    # level 2 — мут (в том числе админам группы)
    muted = False
    err_hint = ""
    try:
        # проверка: владелец чата — мут невозможен
        try:
            tm = await bot.get_chat_member(chat_id, user.id)
            st = tm.status
            if st in (ChatMemberStatus.OWNER, "creator"):
                err_hint = "это владелец группы — Telegram не даёт его мутить"
            else:
                until = datetime.now() + timedelta(seconds=SPAM_MUTE_SEC)
                await bot.restrict_chat_member(
                    chat_id, user.id, permissions=MUTE_PERMS, until_date=until
                )
                muted = True
        except Exception as e:
            err_hint = str(e)
            # повторная попытка мута
            try:
                until = datetime.now() + timedelta(seconds=SPAM_MUTE_SEC)
                await bot.restrict_chat_member(
                    chat_id, user.id, permissions=MUTE_PERMS, until_date=until
                )
                muted = True
                err_hint = ""
            except Exception:
                muted = False
    except Exception:
        muted = False

    _SPAM_LOG.pop((int(chat_id), int(user.id)), None)

    try:
        if muted:
            await bot.send_message(
                chat_id,
                f"🔇 <b>{name}</b>, хватит спамить!\n"
                f"Мут на <b>1 час</b>.\n"
                f"📝 Причина: {reason}",
                parse_mode="HTML",
            )
        else:
            extra = ""
            if err_hint and ("owner" in err_hint.lower() or "владелец" in err_hint):
                extra = "\n(Владельца группы замутить нельзя — ограничение Telegram.)"
            else:
                extra = (
                    "\nЧтобы мутить админов: бот должен быть админом "
                    "с правом «блокировать участников» и стоять "
                    "в списке админов выше них."
                )
            await bot.send_message(
                chat_id,
                f"⚠️ <b>{name}</b>, хватит спамить!{extra}",
                parse_mode="HTML",
            )
    except Exception:
        pass
    return muted

def find_in_chat(chat_id, username=None, user_id=None):
    if user_id:
        r = q(
            "SELECT user_id, full_name, username FROM chat_members WHERE chat_id=? AND user_id=?",
            (chat_id, user_id),
        )
        if r:
            return r[0][0], r[0][1] or r[0][2] or str(r[0][0])
    if username:
        un = username.lstrip("@")
        r = q(
            "SELECT user_id, full_name, username FROM chat_members WHERE chat_id=? AND username=? COLLATE NOCASE",
            (chat_id, un),
        )
        if r:
            return r[0][0], r[0][1] or f"@{un}"
        r = q(
            "SELECT user_id, full_name, username FROM users WHERE username=? COLLATE NOCASE",
            (un,),
        )
        if r:
            return r[0][0], r[0][1] or f"@{un}"
    return None, None

async def resolve_mod_target(bot, chat_id, update, text):
    """
    Цель модерации (по приоритету):
    1) text_mention / mention из entities
    2) ответ на сообщение
    3) @username → база чата / users / get_chat
    4) числовой ID
    """
    msg = update.message

    # 1) entities: text_mention даёт user id напрямую
    if msg and msg.entities:
        for ent in msg.entities:
            et = ent.type if isinstance(ent.type, str) else getattr(ent.type, "value", str(ent.type))
            if et in ("text_mention", "text_mention".upper()) or str(et) == "text_mention":
                if ent.user and not ent.user.is_bot:
                    track_chat_member(chat_id, ent.user)
                    return ent.user.id, ent.user.full_name or str(ent.user.id)
            if et in ("mention",) or str(et) == "mention":
                try:
                    raw = (msg.text or "")[ent.offset: ent.offset + ent.length]
                    un = raw.lstrip("@")
                    uid, name = find_in_chat(chat_id, username=un)
                    if uid:
                        return uid, name
                except Exception:
                    pass

    # 2) reply
    if msg and msg.reply_to_message and msg.reply_to_message.from_user:
        u = msg.reply_to_message.from_user
        if not u.is_bot:
            track_chat_member(chat_id, u)
            return u.id, u.full_name or u.username or str(u.id)

    # 3) @username в тексте (любой регистр, с/без @)
    m = re.search(r"@([A-Za-z0-9_]{3,})", text or "")
    if not m:
        # «мут username 1ч» без собаки — слово после команды
        m2 = re.match(
            r"(?:размут|разбан|бан|мут|варн|кик)\s+([A-Za-z0-9_]{3,})",
            (text or "").strip(),
            re.I,
        )
        if m2 and not m2.group(1).isdigit():
            class _M:
                def group(self, n):
                    return m2.group(1)
            m = _M()
    if m:
        un = m.group(1)
        uid, name = find_in_chat(chat_id, username=un)
        if uid:
            return uid, name
        row = q("SELECT user_id, full_name FROM users WHERE username=? COLLATE NOCASE", (un,))
        if row:
            return row[0][0], row[0][1] or f"@{un}"
        try:
            chat = await bot.get_chat(f"@{un}")
            name = getattr(chat, "full_name", None) or getattr(chat, "username", None) or f"@{un}"
            return chat.id, name
        except Exception:
            pass
        return None, None

    # 4) numeric id
    for m in re.finditer(r"\b(\d{6,15})\b", text or ""):
        uid = int(m.group(1))
        try:
            member = await bot.get_chat_member(chat_id, uid)
            track_chat_member(chat_id, member.user)
            return member.user.id, member.user.full_name or str(uid)
        except Exception:
            uid2, name2 = find_in_chat(chat_id, user_id=uid)
            if uid2:
                return uid2, name2
            u = get_user(uid)
            if u:
                return uid, u[2] or u[1] or str(uid)
            return uid, str(uid)

    return None, None

# ═══════════════════════════════════════════════════════════
# КЛАВИАТУРЫ
# ═══════════════════════════════════════════════════════════
def main_reply_kb(user):
    rows = [
        [KeyboardButton("👤 Профиль"), KeyboardButton("💜 Экономика")],
        [KeyboardButton("📈 Биржа"), KeyboardButton("🎮 Игры")],
        [KeyboardButton("🏆 Топы"), KeyboardButton("📩 Жалоба")],
        [KeyboardButton("💜 Отношения"), KeyboardButton("🎭 RP")],
        [KeyboardButton("🛡 Модерация"), KeyboardButton("ℹ️ Помощь")],
        [KeyboardButton("🔔 Уведомления"), KeyboardButton("📈 Открыть биржу")],
    ]
    if is_mod(user):
        rows.append([KeyboardButton("🔮 Панель мод")])
    if is_admin(user):
        rows.append([KeyboardButton("💜 Панель админ")])
    if is_owner(user):
        rows.append([KeyboardButton("👑 Панель овнер")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def main_inline_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👤 Профиль", callback_data="m_profile"),
            InlineKeyboardButton("💜 Баланс", callback_data="m_balance"),
        ],
        [
            InlineKeyboardButton("📈 Биржа", callback_data="m_exchange"),
            InlineKeyboardButton("🎮 Игры", callback_data="m_games"),
        ],
        [
            InlineKeyboardButton("🏆 Топы", callback_data="m_tops"),
            InlineKeyboardButton("📩 Жалоба", callback_data="m_complaint"),
        ],
        [
            InlineKeyboardButton("💍 Брак", callback_data="m_marriage"),
            InlineKeyboardButton("🎭 RP", callback_data="m_rp"),
        ],
        [
            InlineKeyboardButton("🟢 Онлайн", callback_data="m_online"),
            InlineKeyboardButton("🎁 Daily", callback_data="m_daily"),
        ],
        [
            InlineKeyboardButton("🔔 Уведомления", callback_data="m_notify"),
            InlineKeyboardButton("ℹ️ Помощь", callback_data="m_help"),
        ],
    ])

def back_kb(target="m_main"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("‹ Назад", callback_data=target)]])

def cancel_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel_action")]])

def games_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🪙 Монетка", callback_data="game_coin"),
            InlineKeyboardButton("🎲 Кости", callback_data="game_dice"),
        ],
        [
            InlineKeyboardButton("🎯 Угадай", callback_data="game_guess"),
            InlineKeyboardButton("🎰 Слоты", callback_data="game_slots"),
        ],
        [InlineKeyboardButton("‹ Назад", callback_data="m_main")],
    ])

def tops_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💜 Q-коины", callback_data="top_balance"),
            InlineKeyboardButton("⭐ Рейтинг", callback_data="top_rating"),
        ],
        [InlineKeyboardButton("🏆 Победы", callback_data="top_wins")],
        [InlineKeyboardButton("‹ Назад", callback_data="m_main")],
    ])

def exchange_main_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💎 Крипта", callback_data="excat_crypto"),
            InlineKeyboardButton("📊 Акции", callback_data="excat_stock"),
        ],
        [
            InlineKeyboardButton("💼 Портфель", callback_data="ex_portfolio"),
            InlineKeyboardButton("📋 Все курсы", callback_data="ex_all"),
        ],
        [
            InlineKeyboardButton("🔄 Обновить курс", callback_data="ex_refresh"),
        ],
        [InlineKeyboardButton("‹ В меню", callback_data="m_main")],
    ])

def exchange_list_kb(cat, page=0, per_page=8):
    items = list(assets_by_cat(cat).items())
    total_pages = max(1, (len(items) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    chunk = items[page * per_page:(page + 1) * per_page]
    rows = []
    for sym, meta in chunk:
        price, _, pct = get_price_info(sym)
        arrow = "▲" if pct >= 0 else "▼"
        short = f"{price // 1000}k" if price >= 10000 else str(price)
        rows.append([InlineKeyboardButton(
            f"{meta['emoji']} {meta['name']} · {short} {arrow}",
            callback_data=f"ex_{sym}"
        )])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("‹", callback_data=f"expage_{cat}_{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("›", callback_data=f"expage_{cat}_{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("‹ К бирже", callback_data="m_exchange")])
    return InlineKeyboardMarkup(rows)

def exchange_asset_kb(sym):
    cat = EXCHANGE.get(sym, {}).get("cat", "crypto")
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🟢 Купить ×1", callback_data=f"exbuy1_{sym}"),
            InlineKeyboardButton("🟢 ×5", callback_data=f"exbuy5_{sym}"),
            InlineKeyboardButton("🟢 ×10", callback_data=f"exbuy10_{sym}"),
        ],
        [
            InlineKeyboardButton("🔴 Продать ×1", callback_data=f"exsell1_{sym}"),
            InlineKeyboardButton("🔴 ×5", callback_data=f"exsell5_{sym}"),
            InlineKeyboardButton("🔴 Всё", callback_data=f"exsellall_{sym}"),
        ],
        [
            InlineKeyboardButton("✏️ Купить N", callback_data=f"exbuy_{sym}"),
            InlineKeyboardButton("✏️ Продать N", callback_data=f"exselln_{sym}"),
        ],
        [InlineKeyboardButton("‹ Назад", callback_data=f"excat_{cat}")],
    ])

def portfolio_kb(uid):
    rows = q("SELECT symbol, amount FROM portfolio WHERE user_id=?", (uid,)) or []
    buttons = []
    for sym, amt in rows[:12]:
        meta = EXCHANGE.get(sym, {"name": sym, "emoji": "•"})
        buttons.append([InlineKeyboardButton(
            f"🔴 Продать {meta['emoji']} {meta['name']} (×{amt})",
            callback_data=f"exsellall_{sym}"
        )])
    buttons.append([InlineKeyboardButton("‹ К бирже", callback_data="m_exchange")])
    return InlineKeyboardMarkup(buttons)

# совместимость со старым именем
def exchange_kb():
    return exchange_main_kb()

def rp_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🤗 Обнять", callback_data="rp_обнять"),
            InlineKeyboardButton("💋 Поцеловать", callback_data="rp_поцеловать"),
        ],
        [
            InlineKeyboardButton("👊 Ударить", callback_data="rp_ударить"),
            InlineKeyboardButton("🤚 Погладить", callback_data="rp_погладить"),
        ],
        [
            InlineKeyboardButton("🦷 Укусить", callback_data="rp_укусить"),
            InlineKeyboardButton("🦵 Пнуть", callback_data="rp_пнуть"),
        ],
        [
            InlineKeyboardButton("👅 Лизнуть", callback_data="rp_лизнуть"),
            InlineKeyboardButton("👋 Дать пять", callback_data="rp_дать пять"),
        ],
        [InlineKeyboardButton("👋 Шлепнуть", callback_data="rp_шлепнуть")],
        [InlineKeyboardButton("‹ Назад", callback_data="m_main")],
    ])

def economy_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💜 Баланс", callback_data="m_balance"),
            InlineKeyboardButton("📈 Биржа", callback_data="m_exchange"),
        ],
        [
            InlineKeyboardButton("🎁 Daily", callback_data="m_daily"),
            InlineKeyboardButton("🏆 Топы", callback_data="m_tops"),
        ],
        [InlineKeyboardButton("‹ Назад", callback_data="m_main")],
    ])

def marriage_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💍 Мой брак", callback_data="m_marriage")],
        [InlineKeyboardButton("📖 Как вступить", callback_data="mar_help")],
        [InlineKeyboardButton("‹ Назад", callback_data="m_main")],
    ])

def mod_panel_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📩 Открытые жалобы", callback_data="cmp_list")],
        [InlineKeyboardButton("📋 Модераторы", callback_data="mod_list")],
        [InlineKeyboardButton("📖 Команды", callback_data="m_modhelp")],
        [InlineKeyboardButton("‹ Назад", callback_data="m_main")],
    ])

def admin_panel_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Модер", callback_data="adm_add_mod"),
            InlineKeyboardButton("➖ Модер", callback_data="adm_del_mod"),
        ],
        [
            InlineKeyboardButton("📋 Модеры", callback_data="mod_list"),
            InlineKeyboardButton("📋 Админы", callback_data="adm_list"),
        ],
        [
            InlineKeyboardButton("💜 Выдать Q", callback_data="adm_give"),
            InlineKeyboardButton("⚠️ Сброс варнов", callback_data="adm_clear_warns"),
        ],
        [InlineKeyboardButton("📩 Жалобы", callback_data="cmp_list")],
        [InlineKeyboardButton("‹ Назад", callback_data="m_main")],
    ])

def owner_panel_kb():
    maint = "🟢 Снять техработы" if maintenance_on() else "🔴 Техработы"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Админ", callback_data="own_add_admin"),
            InlineKeyboardButton("➖ Админ", callback_data="own_del_admin"),
        ],
        [
            InlineKeyboardButton("➕ Овнер", callback_data="own_add_owner"),
            InlineKeyboardButton("➖ Овнер", callback_data="own_del_owner"),
        ],
        [
            InlineKeyboardButton("➕ Модер", callback_data="adm_add_mod"),
            InlineKeyboardButton("➖ Модер", callback_data="adm_del_mod"),
        ],
        [
            InlineKeyboardButton("💜 Выдать Q", callback_data="adm_give"),
            InlineKeyboardButton("📋 Роли", callback_data="own_all_roles"),
        ],
        [
            InlineKeyboardButton("📢 Объявление", callback_data="own_broadcast"),
            InlineKeyboardButton(maint, callback_data="own_maint"),
        ],
        [InlineKeyboardButton("📩 Жалобы", callback_data="cmp_list")],
        [InlineKeyboardButton("‹ Назад", callback_data="m_main")],
    ])

# ═══════════════════════════════════════════════════════════
# ТЕКСТЫ
# ═══════════════════════════════════════════════════════════
def profile_text(uid):
    u = get_user(uid)
    if not u:
        return "Не найден."
    role = get_role_name(uid)
    total = (u[5] or 0) + (u[6] or 0)
    wr = round((u[5] or 0) / total * 100, 1) if total else 0
    pv = portfolio_value(uid)
    m = get_marriage(uid)
    if m:
        pid = m[1] if m[0] == uid else m[0]
        p = get_user(pid)
        marriage = f"💍 Брак с <b>{p[2] if p else pid}</b> · с {m[2]}"
    else:
        marriage = "💜 Не в браке"
    return card("👤", "ПРОФИЛЬ",
        f"🎭 <b>{u[2] or u[1] or uid}</b>\n"
        f"🏅 {role}\n\n"
        f"💜 На руках\n   <b>{money(u[3])}</b>\n"
        f"📈 В активах\n   <b>{money(pv)}</b>\n\n"
        f"⭐ Рейтинг · <b>{u[7] or 0}</b>\n"
        f"🏆 {u[5] or 0} / 💀 {u[6] or 0} · WR {wr}%\n"
        f"⚠️ Варны · <b>{u[4]}</b>\n\n"
        f"{marriage}"
    )

def top_text(category="balance"):
    titles = {
        "balance": ("💜", "ТОП · Q-КОИНЫ"),
        "rating": ("⭐", "ТОП · РЕЙТИНГ"),
        "wins": ("🏆", "ТОП · ПОБЕДЫ"),
    }
    emoji, title = titles.get(category, titles["balance"])
    rows = get_top(category, 10)
    text = header(emoji, title) + "\n\n"
    if not rows:
        return text + "<i>Пусто</i>"
    medals = ["🥇", "🥈", "🥉"] + [f"{i}." for i in range(4, 11)]
    for i, (uid, name, bal, rating, wins) in enumerate(rows):
        mark = medals[i] if i < len(medals) else f"{i+1}."
        if category == "rating":
            stat = f"⭐ <b>{rating or 0}</b>"
        elif category == "wins":
            stat = f"🏆 <b>{wins or 0}</b>"
        else:
            stat = f"<b>{money(bal)}</b>"
        text += f"{mark} {name or uid}\n      {stat}\n"
    return text

def online_text():
    n = online_count()
    total = (q("SELECT COUNT(*) FROM users") or [[0]])[0][0]
    return card("🟢", "ОНЛАЙН",
        f"Сейчас · <b>{n}</b>\nВсего · <b>{total}</b>\n\n"
        f"<i>Активность за {ONLINE_TIMEOUT // 60} мин</i>"
    )

def exchange_text(uid=None):
    maybe_auto_tick()
    crypto_n = len(assets_by_cat("crypto"))
    stock_n = len(assets_by_cat("stock"))
    bal = ""
    if uid:
        u = get_user(uid)
        if u:
            bal = (
                f"💜 Баланс · <b>{money(u[3])}</b>\n"
                f"💼 Активы · <b>{money(portfolio_value(uid))}</b>\n\n"
            )
    return card("📈", "БИРЖА QSOPRA",
        bal +
        f"💎 Крипта · <b>{crypto_n}</b> активов\n"
        f"📊 Акции · <b>{stock_n}</b> активов\n\n"
        f"⏱ Курс обновляется <b>раз в час</b>\n"
        f"Следующее · через <b>{next_tick_in()}</b>\n\n"
        "Торговля за <b>Q-коины</b>\n"
        "Выбери раздел ниже\n\n"
        "────────────\n"
        "<code>купить HLN 2</code>\n"
        "<code>продать NXA 1</code>"
    )

def exchange_cat_text(cat, uid=None):
    maybe_auto_tick()
    title = "💎 КРИПТА" if cat == "crypto" else "📊 АКЦИИ"
    items = list(assets_by_cat(cat).items())
    # топ по движению + несколько строк
    scored = []
    for sym, meta in items:
        price, prev, pct = get_price_info(sym)
        scored.append((abs(pct), sym, meta, price, pct))
    scored.sort(reverse=True)
    lines = []
    for _, sym, meta, price, pct in scored[:10]:
        arrow = "📈" if pct >= 0 else "📉"
        hold = get_holding(uid, sym) if uid else 0
        hold_s = f" · ×{hold}" if hold else ""
        lines.append(
            f"{meta['emoji']} <b>{meta['name']}</b> <code>{sym}</code>\n"
            f"   {money(price)}  {arrow} {pct:+.1f}%{hold_s}"
        )
    return card("📈", title,
        f"Показаны топ‑движения · всего {len(items)}\n"
        f"Обновление через <b>{next_tick_in()}</b>\n\n"
        + "\n\n".join(lines) +
        "\n\nЖми актив на кнопке 👇"
    )

def portfolio_text(uid):
    rows = q("SELECT symbol, amount FROM portfolio WHERE user_id=?", (uid,)) or []
    if not rows:
        return card("💼", "ПОРТФЕЛЬ", "Пусто.\nКупи крипту или акции на бирже.")
    lines = []
    total = 0
    for sym, amt in rows:
        meta = EXCHANGE.get(sym, {"name": sym, "emoji": "•", "cat": "?"})
        price = get_price(sym)
        val = amt * price
        total += val
        kind = "крипта" if meta.get("cat") == "crypto" else "акция"
        lines.append(
            f"{meta['emoji']} <b>{meta['name']}</b> × <b>{amt}</b> · {kind}\n"
            f"   {money(price)} · ≈ <b>{money(val)}</b>"
        )
    return card("💼", "ПОРТФЕЛЬ",
        "\n\n".join(lines) +
        f"\n\n════════════\nИтого · <b>{money(total)}</b>\n\n"
        "Кнопка «Продать» ниже — продажа всего по активу"
    )

def help_text():
    return card("ℹ️", f"ПОМОЩЬ · v{VERSION}",
        "<b>Разделы</b>\n"
        "Профиль · Экономика · Биржа · Игры\n"
        "Топы · Жалобы · RP · Модерация\n\n"
        "<b>Валюта</b> — только Q-коины\n\n"
        "<b>Биржа</b>\n"
        "Гелионит · Нокса · Аметилин\n"
        "Виолеткоин · Квазар-Q\n\n"
        "<b>Команды</b>\n"
        "<code>баланс</code> · <code>биржа</code> · <code>daily</code>\n"
        "<code>жалоба</code> · <code>онлайн</code> · <code>топ</code>\n"
        "<code>брак</code> · <code>развод</code> · <code>передать 100</code>\n"
        "<code>бан</code> · <code>мут 1ч</code> · <code>размут</code> · <code>разбан</code>\n"
        "<code>админ</code> · <code>мод</code> · <code>овнер</code>\n"
        "<code>отмена</code> — сброс любого ввода\n\n"
        f"<i>@QSOPRA_baby · remaster {VERSION}</i>"
    )

def mod_help_text():
    return card("🛡", "МОДЕРАЦИЯ",
        "Работает <b>ответом</b> или по <b>@юзеру / ID</b>:\n\n"
        "• <code>бан</code> — навсегда\n"
        "• <code>бан @user 15г</code> — на 15 лет\n"
        "• <code>бан @user 1д спам</code> — с причиной\n"
        "• <code>мут 2ч | оскорбления</code>\n"
        "• <code>мут @user 2ч</code>\n"
        "• <code>размут @user</code>\n"
        "• <code>разбан @user</code>\n"
        "• <code>варн @user</code> · <code>кик @user</code>\n\n"
        f"<b>Автобан</b>: {WARN_LIMIT} варна → бан "
        f"{'навсегда' if WARN_BAN_SEC == 0 else format_duration(WARN_BAN_SEC)}\n\n"
        "Сроки: <code>30м</code> <code>2ч</code> <code>3д</code>\n"
        "<code>2мес</code> <code>1г</code> <code>15лет</code>\n\n"
        "<b>Антифлуд и спам-фильтры</b>\n"
        f"• {SPAM_MAX_MSG}+ сообщ. за {SPAM_WINDOW}с → мут 1ч\n"
        f"• один текст ×{SPAM_SAME_LIMIT} → мут\n"
        f"• {SPAM_MAX_LINKS}+ ссылок в сообщении → мут\n"
        f"• {SPAM_MAX_MENTIONS}+ @упоминаний → мут\n"
        f"• капс (много ЗАГЛАВНЫХ) → предупреждение\n"
        f"Действует на всех, включая админов группы.\n"
        f"Исключение: @{MAIN_ADMIN}\n\n"
        "Бот = админ чата, право блокировки,\n"
        "в списке админов выше тех, кого мутит."
    )

def welcome_text(name):
    return (
        f"👋 <b>{name}</b>, добро пожаловать\n\n"
        + header("💜", "QSOPRA HELPER") + "\n\n"
        f"Версия <b>v{VERSION}</b>\n"
        "Q-коины · Биржа · Жалобы · Игры\n"
        "Роли · Мод / Админ / Владелец\n\n"
        "Главный · @QSOPRA_baby"
    )

# ═══════════════════════════════════════════════════════════
# ИГРЫ
# ═══════════════════════════════════════════════════════════
async def play_coin(message, uid, amount, choice):
    u = get_user(uid)
    if not u or u[3] < amount:
        await message.reply_text(f"❌ Нужно <b>{money(amount)}</b>", parse_mode="HTML")
        return
    add_balance(uid, -amount)
    result = random.choice(["о", "р"])
    label = "🦅 Орёл" if result == "о" else "🪙 Решка"
    if choice == result:
        win = amount * 2
        add_balance(uid, win)
        register_win(uid, 5)
        await message.reply_text(card("🪙", "МОНЕТКА", f"{label}\n\n💜 +<b>{money(win)}</b>\n⭐ +5"), parse_mode="HTML")
    else:
        register_loss(uid, 2)
        await message.reply_text(card("🪙", "МОНЕТКА", f"{label}\n\n💀 −<b>{money(amount)}</b>\n⭐ −2"), parse_mode="HTML")

async def play_dice(message, uid, amount):
    u = get_user(uid)
    if not u or u[3] < amount:
        await message.reply_text(f"❌ Нужно <b>{money(amount)}</b>", parse_mode="HTML")
        return
    add_balance(uid, -amount)
    val = random.randint(1, 6)
    if val >= 5:
        win = amount * 2
        add_balance(uid, win)
        register_win(uid, 5)
        await message.reply_text(card("🎲", "КОСТИ", f"Выпало · <b>{val}</b>\n\n💜 +<b>{money(win)}</b>\n⭐ +5"), parse_mode="HTML")
    else:
        register_loss(uid, 2)
        await message.reply_text(card("🎲", "КОСТИ", f"Выпало · <b>{val}</b>\n\n💀 −<b>{money(amount)}</b>\n⭐ −2"), parse_mode="HTML")

async def play_guess(message, uid, amount, number):
    u = get_user(uid)
    if not u or u[3] < amount:
        await message.reply_text(f"❌ Нужно <b>{money(amount)}</b>", parse_mode="HTML")
        return
    add_balance(uid, -amount)
    secret = random.randint(1, 10)
    if number == secret:
        win = amount * 5
        add_balance(uid, win)
        register_win(uid, 10)
        await message.reply_text(card("🎯", "УГАДАЙ", f"Число · <b>{secret}</b>\n\n💜 +<b>{money(win)}</b>\n⭐ +10"), parse_mode="HTML")
    else:
        register_loss(uid, 3)
        await message.reply_text(card("🎯", "УГАДАЙ", f"Было · <b>{secret}</b> · вы · {number}\n\n💀 −<b>{money(amount)}</b>\n⭐ −3"), parse_mode="HTML")

async def play_slots(message, uid, amount):
    u = get_user(uid)
    if not u or u[3] < amount:
        await message.reply_text(f"❌ Нужно <b>{money(amount)}</b>", parse_mode="HTML")
        return
    add_balance(uid, -amount)
    symbols = ["🍒", "🍋", "🍇", "7️⃣", "⭐"]
    s = [random.choice(symbols) for _ in range(3)]
    line = f"  {s[0]}   {s[1]}   {s[2]}  "
    if s[0] == s[1] == s[2]:
        mult = 10 if s[0] == "7️⃣" else 5
        win = amount * mult
        add_balance(uid, win)
        register_win(uid, 8)
        await message.reply_text(card("🎰", "СЛОТЫ", f"<code>{line}</code>\n\n💜 x{mult} · +<b>{money(win)}</b>\n⭐ +8"), parse_mode="HTML")
    elif s[0] == s[1] or s[1] == s[2] or s[0] == s[2]:
        win = int(amount * 1.5)
        add_balance(uid, win)
        register_win(uid, 3)
        await message.reply_text(card("🎰", "СЛОТЫ", f"<code>{line}</code>\n\n💜 +<b>{money(win)}</b>\n⭐ +3"), parse_mode="HTML")
    else:
        register_loss(uid, 2)
        await message.reply_text(card("🎰", "СЛОТЫ", f"<code>{line}</code>\n\n💀 −<b>{money(amount)}</b>\n⭐ −2"), parse_mode="HTML")

# ═══════════════════════════════════════════════════════════
# ОБРАБОТЧИКИ
# ═══════════════════════════════════════════════════════════
async def safe_edit(query, text, reply_markup=None):
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
    except Exception:
        try:
            await query.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")
        except Exception:
            pass

async def _do_buy(query, uid, sym, qty):
    if sym not in EXCHANGE or qty <= 0:
        return
    mark_trader(uid)
    price = get_price(sym)
    cost = price * qty
    u = get_user(uid)
    if not u or u[3] < cost:
        await query.answer(f"Нужно {money(cost)}", show_alert=True)
        return
    add_balance(uid, -cost)
    set_holding(uid, sym, get_holding(uid, sym) + qty)
    meta = EXCHANGE[sym]
    kind = "крипта" if meta.get("cat") == "crypto" else "акция"
    await safe_edit(query, card("🟢", "КУПЛЕНО",
        f"{meta['emoji']} <b>{meta['name']}</b> × {qty}\n"
        f"Тип · {kind}\n"
        f"Списано · <b>{money(cost)}</b>\n"
        f"Теперь · <b>{get_holding(uid, sym)}</b> шт."
    ), exchange_asset_kb(sym))

async def _do_sell(query, uid, sym, qty):
    if sym not in EXCHANGE or qty <= 0:
        return
    mark_trader(uid)
    hold = get_holding(uid, sym)
    if hold < qty:
        await query.answer(f"У вас только {hold} шт.", show_alert=True)
        return
    price = get_price(sym)
    gain = price * qty
    set_holding(uid, sym, hold - qty)
    add_balance(uid, gain)
    meta = EXCHANGE[sym]
    kind = "крипта" if meta.get("cat") == "crypto" else "акция"
    await safe_edit(query, card("🔴", "ПРОДАНО",
        f"{meta['emoji']} <b>{meta['name']}</b> × {qty}\n"
        f"Тип · {kind}\n"
        f"Получено · <b>{money(gain)}</b>\n"
        f"Осталось · <b>{get_holding(uid, sym)}</b> шт."
    ), exchange_asset_kb(sym) if get_holding(uid, sym) else exchange_kb())

# ── Фильтры уведомлений ──
# key -> (название, default_on, для кого: all|staff|trader)
NOTIFY_KEYS = {
    "complaints": ("📩 Жалобы", True, "staff"),
    "modlog": ("🛡 Мод-лог (бан/мут)", True, "staff"),
    "exchange": ("📈 Биржа · все курсы", True, "all"),
    "exchange_big": ("📊 Биржа · только сильные движения", False, "all"),
    "broadcast": ("📢 Объявления", True, "all"),
}
EXCHANGE_BIG_PCT = 3.0  # порог по умолчанию (%)
TRIGGER_PCT_CHOICES = (2, 3, 5, 7, 10)

def get_notify(uid, key, default=None):
    if default is None:
        default = NOTIFY_KEYS.get(key, ("", True, "all"))[1]
    r = q("SELECT value FROM user_settings WHERE user_id=? AND key=?", (uid, f"notify_{key}"))
    if not r:
        return default
    return r[0][0] == "1"

def set_notify(uid, key, on: bool):
    q(
        "INSERT OR REPLACE INTO user_settings(user_id, key, value) VALUES (?,?,?)",
        (uid, f"notify_{key}", "1" if on else "0"),
        fetch=False,
    )

def get_trigger_pct(uid):
    """Порог «сильного» движения курса для пользователя."""
    r = q("SELECT value FROM user_settings WHERE user_id=? AND key=?", (uid, "trigger_exchange_pct"))
    if not r:
        return EXCHANGE_BIG_PCT
    try:
        v = float(r[0][0])
        return max(1.0, min(50.0, v))
    except Exception:
        return EXCHANGE_BIG_PCT

def set_trigger_pct(uid, pct):
    pct = max(1.0, min(50.0, float(pct)))
    q(
        "INSERT OR REPLACE INTO user_settings(user_id, key, value) VALUES (?,?,?)",
        (uid, "trigger_exchange_pct", str(pct)),
        fetch=False,
    )
    return pct

def market_has_big_moves(threshold=None):
    if threshold is None:
        threshold = EXCHANGE_BIG_PCT
    for sym in EXCHANGE:
        _, _, pct = get_price_info(sym)
        if abs(pct) >= threshold:
            return True
    return False

def market_max_move():
    best = 0.0
    for sym in EXCHANGE:
        _, _, pct = get_price_info(sym)
        if abs(pct) > abs(best):
            best = pct
    return best

def notify_settings_text(user):
    pct = get_trigger_pct(user.id)
    lines = [
        "Фильтры и триггеры уведомлений.\n"
        "Нажмите кнопку, чтобы переключить.\n"
    ]
    if is_staff(user):
        lines.append("<b>Для стаффа</b>")
        for key in ("complaints", "modlog"):
            title, default, _ = NOTIFY_KEYS[key]
            on = get_notify(user.id, key, default)
            lines.append(f"{title} · {'✅ вкл' if on else '❌ выкл'}")
        lines.append("")
    lines.append("<b>Общие фильтры</b>")
    for key in ("exchange", "exchange_big", "broadcast"):
        title, default, _ = NOTIFY_KEYS[key]
        on = get_notify(user.id, key, default)
        lines.append(f"{title} · {'✅ вкл' if on else '❌ выкл'}")
    lines.append("")
    lines.append("<b>Триггер биржи</b>")
    lines.append(f"Сильное движение · от <b>{pct:g}%</b>")
    lines.append(
        f"\n<i>При фильтре «только сильные» уведомление "
        f"придёт, если курс изменился ≥ {pct:g}%</i>"
    )
    return card("🔔", "ФИЛЬТРЫ И ТРИГГЕРЫ", "\n".join(lines))

def notify_settings_kb(user):
    rows = []
    if is_staff(user):
        for key in ("complaints", "modlog"):
            title, default, _ = NOTIFY_KEYS[key]
            on = get_notify(user.id, key, default)
            short = title.split("·")[0].strip() if "·" in title else title
            rows.append([InlineKeyboardButton(
                f"{short} · {'✅' if on else '❌'}",
                callback_data=f"ntf_{key}",
            )])
    for key in ("exchange", "exchange_big", "broadcast"):
        on = get_notify(user.id, key)
        short = {
            "exchange": "📈 Все курсы",
            "exchange_big": "📊 Только сильные",
            "broadcast": "📢 Объявления",
        }.get(key, key)
        rows.append([InlineKeyboardButton(
            f"{short} · {'✅' if on else '❌'}",
            callback_data=f"ntf_{key}",
        )])
    rows.append([InlineKeyboardButton("⚙️ Триггеры", callback_data="ntf_triggers")])
    rows.append([InlineKeyboardButton("‹ В меню", callback_data="m_main")])
    return InlineKeyboardMarkup(rows)

def trigger_settings_text(user):
    pct = get_trigger_pct(user.id)
    mx = market_max_move()
    return card(
        "⚙️",
        "ТРИГГЕРЫ ФИЛЬТРОВ",
        f"<b>Биржа · сильное движение</b>\n"
        f"Сейчас порог · <b>{pct:g}%</b>\n"
        f"Макс. движение сейчас · <b>{mx:+.1f}%</b>\n\n"
        f"Уведомление «только сильные» сработает,\n"
        f"если изменение курса ≥ вашего порога.\n\n"
        f"Выберите порог кнопкой ниже.",
    )

def trigger_settings_kb(user):
    cur = get_trigger_pct(user.id)
    row = []
    for p in TRIGGER_PCT_CHOICES:
        mark = "·" if abs(cur - p) < 0.01 else ""
        row.append(InlineKeyboardButton(
            f"{'✓ ' if mark else ''}{p}%",
            callback_data=f"ntg_{p}",
        ))
    return InlineKeyboardMarkup([
        row[:3],
        row[3:],
        [InlineKeyboardButton("‹ К фильтрам", callback_data="m_notify")],
    ])

async def notify_traders(bot, text, big_only_check=True):
    """
    Учитывает фильтры и персональный триггер % у каждого.
    """
    for tid in trader_ids():
        want_all = get_notify(tid, "exchange")
        want_big = get_notify(tid, "exchange_big")
        if want_all:
            send = True
        elif want_big and big_only_check:
            thr = get_trigger_pct(tid)
            send = market_has_big_moves(thr)
        elif want_big and not big_only_check:
            send = True
        else:
            send = False
        if not send:
            continue
        try:
            await bot.send_message(tid, text, parse_mode="HTML")
            await asyncio.sleep(0.04)
        except Exception:
            pass

async def notify_staff(bot, text, kind="complaints"):
    """
    kind: complaints | modlog
    """
    for sid in staff_user_ids():
        if not get_notify(sid, kind):
            continue
        try:
            await bot.send_message(sid, text, parse_mode="HTML")
            await asyncio.sleep(0.03)
        except Exception:
            pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user)
    mark_online(user.id)
    clear_staff_state(context)
    if maintenance_on() and not is_staff(user):
        await update.message.reply_text(
            card("🔧", "ТЕХРАБОТЫ", "Бот временно недоступен.\nЗайдите позже."),
            parse_mode="HTML"
        )
        return
    name = user.first_name or "друг"
    await update.message.reply_text(
        welcome_text(name),
        reply_markup=main_reply_kb(user),
        parse_mode="HTML"
    )
    await update.message.reply_text(
        card("📋", "МЕНЮ", "Выберите раздел:"),
        reply_markup=main_inline_kb(),
        parse_mode="HTML"
    )

async def claim_daily(uid):
    u = get_user(uid)
    if not u:
        return None, "Сначала /start"
    today = datetime.now().strftime("%Y-%m-%d")
    if u[8] == today:
        return None, "Уже забрали сегодня. Завтра снова."
    reward = random.randint(400, 900)
    add_balance(uid, reward)
    q("UPDATE users SET last_daily=? WHERE user_id=?", (today, uid), fetch=False)
    return reward, None

async def menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    try:
        await query.answer()
    except Exception:
        pass

    user = query.from_user
    uid = user.id
    ensure_user(user)
    mark_online(uid)
    d = query.data or ""

    if d == "cancel_action":
        clear_staff_state(context)
        await safe_edit(query, card("❌", "ОТМЕНА", "Действие отменено."), main_inline_kb())
        return

    if maintenance_on() and not is_staff(user) and not d.startswith("own_"):
        await safe_edit(query, card("🔧", "ТЕХРАБОТЫ", "Бот временно недоступен."), back_kb())
        return

    if d == "m_main":
        await safe_edit(query, card("📋", "МЕНЮ", "Выберите раздел:"), main_inline_kb())
    elif d == "m_profile":
        await safe_edit(query, profile_text(uid), back_kb())
    elif d == "m_balance":
        u = get_user(uid)
        await safe_edit(query, card("💜", "БАЛАНС",
            f"На руках\n   <b>{money(u[3])}</b>\n\n"
            f"В активах\n   <b>{money(portfolio_value(uid))}</b>\n\n"
            f"⭐ Рейтинг · <b>{u[7] or 0}</b>\n\n"
            "Перевод: ответом <code>передать 100</code>"
        ), economy_kb())
    elif d == "m_daily":
        reward, err = await claim_daily(uid)
        if err:
            await safe_edit(query, card("🎁", "DAILY", err), back_kb())
        else:
            await safe_edit(query, card("🎁", "DAILY", f"Получено\n   <b>+{money(reward)}</b>"), back_kb())
    elif d == "m_exchange":
        mark_trader(uid)
        await safe_edit(query, exchange_text(uid), exchange_main_kb())
    elif d == "excat_crypto":
        mark_trader(uid)
        await safe_edit(query, exchange_cat_text("crypto", uid), exchange_list_kb("crypto", 0))
    elif d == "excat_stock":
        mark_trader(uid)
        await safe_edit(query, exchange_cat_text("stock", uid), exchange_list_kb("stock", 0))
    elif d.startswith("expage_"):
        parts = d.split("_")
        if len(parts) >= 3:
            cat, page = parts[1], int(parts[2])
            await safe_edit(query, exchange_cat_text(cat, uid), exchange_list_kb(cat, page))
    elif d == "ex_all":
        mark_trader(uid)
        await safe_edit(query, exchange_cat_text("crypto", uid) + "\n\n<i>Сначала крипта · акции во вкладке</i>", exchange_list_kb("crypto", 0))
    elif d == "noop":
        await query.answer()
    elif d == "ex_refresh":
        mark_trader(uid)
        changed = tick_prices(force=True)
        await safe_edit(query, exchange_text(uid) + "\n\n<i>✅ Курс обновлён вручную</i>", exchange_main_kb())
        if changed:
            await notify_traders(context.bot, market_summary_text())
    elif d == "ex_portfolio":
        mark_trader(uid)
        await safe_edit(query, portfolio_text(uid), portfolio_kb(uid))
    elif d.startswith("ex_") and d[3:] in EXCHANGE:
        mark_trader(uid)
        sym = d[3:]
        meta = EXCHANGE[sym]
        price, prev, pct = get_price_info(sym)
        hold = get_holding(uid, sym)
        kind = "💎 Крипта" if meta.get("cat") == "crypto" else "📊 Акция"
        trend = f"📈 +{pct:.1f}%" if pct >= 0 else f"📉 {pct:.1f}%"
        await safe_edit(query, card(meta["emoji"], meta["name"],
            f"{kind}\n"
            f"Тикер · <code>{sym}</code>\n"
            f"Курс · <b>{money(price)}</b>\n"
            f"Динамика · {trend}\n"
            f"У вас · <b>{hold}</b> шт.\n"
            f"Стоимость · <b>{money(hold * price)}</b>\n\n"
            "🟢 Купить · 🔴 Продать — кнопки\n"
            f"<code>купить {sym} 2</code>\n"
            f"<code>продать {sym} 1</code>"
        ), exchange_asset_kb(sym))
    elif d.startswith("exbuy1_"):
        await _do_buy(query, uid, d[7:], 1)
    elif d.startswith("exbuy5_"):
        await _do_buy(query, uid, d[7:], 5)
    elif d.startswith("exbuy10_"):
        await _do_buy(query, uid, d[8:], 10)
    elif d.startswith("exsell1_"):
        await _do_sell(query, uid, d[8:], 1)
    elif d.startswith("exsell5_"):
        await _do_sell(query, uid, d[8:], 5)
    elif d.startswith("exsellall_"):
        sym = d[10:]
        hold = get_holding(uid, sym)
        if hold <= 0:
            await query.answer("Нечего продавать", show_alert=True)
            return
        await _do_sell(query, uid, sym, hold)
    elif d.startswith("exselln_"):
        sym = d[8:]
        if sym not in EXCHANGE:
            return
        context.user_data["exchange_action"] = f"sell:{sym}"
        await safe_edit(query, card("🔴", "ПРОДАЖА",
            f"{EXCHANGE[sym]['emoji']} {EXCHANGE[sym]['name']}\n"
            f"У вас · <b>{get_holding(uid, sym)}</b> шт.\n\n"
            "Сколько продать?\nНапишите число\n\n<code>отмена</code>"
        ), cancel_kb())
    elif d.startswith("exbuy_"):
        sym = d[6:]
        if sym not in EXCHANGE:
            return
        context.user_data["exchange_action"] = f"buy:{sym}"
        await safe_edit(query, card("🟢", "ПОКУПКА",
            f"{EXCHANGE[sym]['emoji']} {EXCHANGE[sym]['name']}\n"
            f"Курс · {money(get_price(sym))}\n\n"
            "Сколько купить?\nНапишите число\n\n<code>отмена</code>"
        ), cancel_kb())
    elif d.startswith("exsell_"):
        sym = d[7:]
        if sym not in EXCHANGE:
            return
        context.user_data["exchange_action"] = f"sell:{sym}"
        await safe_edit(query, card("🔴", "ПРОДАЖА",
            f"{EXCHANGE[sym]['emoji']} {EXCHANGE[sym]['name']}\n"
            f"У вас · {get_holding(uid, sym)}\n\n"
            "Сколько продать?\nНапишите число\n\n<code>отмена</code>"
        ), cancel_kb())
    elif d == "m_games":
        await safe_edit(query, card("🎮", "ИГРЫ",
            f"Ставки в Q-коинах\nМин. · <b>{money(MIN_BET)}</b>"
        ), games_kb())
    elif d == "m_tops":
        await safe_edit(query, card("🏆", "ТОПЫ", "Категория:"), tops_kb())
    elif d == "top_balance":
        await safe_edit(query, top_text("balance"), tops_kb())
    elif d == "top_rating":
        await safe_edit(query, top_text("rating"), tops_kb())
    elif d == "top_wins":
        await safe_edit(query, top_text("wins"), tops_kb())
    elif d == "m_online":
        await safe_edit(query, online_text(), back_kb())
    elif d == "m_complaint":
        context.user_data["complaint"] = True
        context.user_data.pop("complaint_target", None)
        await safe_edit(query, card("📩", "ЖАЛОБА НА ПОЛЬЗОВАТЕЛЯ",
            "1) Ответьте на сообщение нарушителя и напишите <code>жалоба</code>\n"
            "   или укажите: <code>жалоба @ник</code>\n"
            "2) Затем одним сообщением опишите ситуацию.\n\n"
            "Жалоба уйдёт модерам, админам и владельцам.\n"
            "<code>отмена</code> — выход"
        ), cancel_kb())
    elif d == "m_marriage":
        m = get_marriage(uid)
        if m:
            pid = m[1] if m[0] == uid else m[0]
            p = get_user(pid)
            text = card("💍", "БРАК", f"С <b>{p[2] if p else pid}</b>\nс {m[2]}\n\n<code>развод</code> — расторгнуть")
        else:
            text = card("💜", "ОТНОШЕНИЯ", "Не в браке.\nОтветьте на сообщение и напишите <code>брак</code>")
        await safe_edit(query, text, marriage_kb())
    elif d == "mar_help":
        await safe_edit(query, card("📖", "БРАК", "1. Ответ на сообщение\n2. <code>брак</code>\n\nРазвод: <code>развод</code>"), back_kb("m_marriage"))
    elif d == "m_rp":
        await safe_edit(query, card("🎭", "RP", "Выберите действие, затем ответьте на сообщение."), rp_kb())
    elif d == "m_modhelp":
        await safe_edit(query, mod_help_text(), back_kb())
    elif d == "m_help":
        await safe_edit(query, help_text(), back_kb())
    elif d == "m_notify":
        await safe_edit(query, notify_settings_text(user), notify_settings_kb(user))
    elif d == "ntf_triggers":
        await safe_edit(query, trigger_settings_text(user), trigger_settings_kb(user))
    elif d.startswith("ntg_"):
        try:
            pct = float(d[4:])
        except ValueError:
            return
        set_trigger_pct(user.id, pct)
        # авто-включить «только сильные», если выбрали триггер
        if not get_notify(user.id, "exchange_big"):
            set_notify(user.id, "exchange_big", True)
        await query.answer(f"Порог: {pct:g}%", show_alert=False)
        await safe_edit(query, trigger_settings_text(user), trigger_settings_kb(user))
    elif d.startswith("ntf_"):
        key = d[4:]
        if key == "triggers":
            return
        if key not in NOTIFY_KEYS:
            return
        scope = NOTIFY_KEYS[key][2]
        if scope == "staff" and not is_staff(user):
            await query.answer("Только для стаффа", show_alert=True)
            return
        cur = get_notify(user.id, key)
        set_notify(user.id, key, not cur)
        await safe_edit(query, notify_settings_text(user), notify_settings_kb(user))
    elif d.startswith("rp_"):
        action = d[3:]
        context.user_data["pending_rp"] = action
        await safe_edit(query, card("🎭", "RP", f"Выбрано: <b>{action}</b>\n\nОтветьте на сообщение человека."), back_kb("m_rp"))
    elif d == "game_coin":
        await safe_edit(query, card("🪙", "МОНЕТКА", "Формат:\n<code>монетка 50 о</code>\n<code>монетка 50 р</code>"), back_kb("m_games"))
    elif d == "game_dice":
        await safe_edit(query, card("🎲", "КОСТИ", f"Формат: <code>кости 50</code>\nПобеда при 5–6 · x2"), back_kb("m_games"))
    elif d == "game_guess":
        await safe_edit(query, card("🎯", "УГАДАЙ", "Формат: <code>угадай 50 7</code>\n1–10 · x5"), back_kb("m_games"))
    elif d == "game_slots":
        await safe_edit(query, card("🎰", "СЛОТЫ", "Формат: <code>слоты 50</code>"), back_kb("m_games"))

    # Жалобы — список для стаффа
    elif d == "cmp_list":
        if not is_staff(user):
            await query.answer("⛔", show_alert=True)
            return
        rows = open_complaints()
        if not rows:
            await safe_edit(query, card("📩", "ЖАЛОБЫ", "Открытых нет."), back_kb("m_main"))
            return
        lines = []
        buttons = []
        for row in rows:
            cid, fid, fname, text, created = row[0], row[1], row[2], row[3], row[4]
            tid = row[5] if len(row) > 5 else None
            tname = row[6] if len(row) > 6 else None
            preview = (text[:40] + "…") if len(text) > 40 else text
            target_line = f"\n🎯 {tname or tid}" if (tid or tname) else ""
            lines.append(f"<b>#{cid}</b> · от {fname}{target_line}\n{preview}\n<i>{created}</i>")
            buttons.append([
                InlineKeyboardButton(f"#{cid} открыть", callback_data=f"cmp_view_{cid}"),
                InlineKeyboardButton(f"✓ закрыть", callback_data=f"cmp_close_{cid}"),
            ])
        buttons.append([InlineKeyboardButton("‹ Назад", callback_data="m_main")])
        await safe_edit(query, card("📩", "ОТКРЫТЫЕ ЖАЛОБЫ", "\n\n".join(lines)), InlineKeyboardMarkup(buttons))
    elif d.startswith("cmp_view_"):
        if not is_staff(user):
            await query.answer("⛔", show_alert=True)
            return
        try:
            cid = int(d.split("_")[-1])
        except ValueError:
            return
        c = get_complaint(cid)
        if not c:
            await query.answer("Не найдена", show_alert=True)
            return
        # id, from_id, from_name, text, status, created, target_id, target_name
        body = complaint_card_staff(
            c[0], c[2], c[1], None, c[3],
            target_id=c[6] if len(c) > 6 else None,
            target_name=c[7] if len(c) > 7 else None,
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✓ Закрыть", callback_data=f"cmp_close_{cid}")],
            [InlineKeyboardButton("‹ К списку", callback_data="cmp_list")],
        ])
        await safe_edit(query, body, kb)
    elif d.startswith("cmp_close_"):
        if not is_staff(user):
            await query.answer("⛔", show_alert=True)
            return
        try:
            cid = int(d.split("_")[-1])
        except ValueError:
            return
        c = get_complaint(cid)
        if not c:
            await query.answer("Не найдена", show_alert=True)
            return
        close_complaint(cid, uid)
        try:
            await context.bot.send_message(
                c[1],
                card("✅", "ЖАЛОБА", f"Ваша жалоба #{cid} рассмотрена.\nСпасибо за обращение."),
                parse_mode="HTML",
            )
        except Exception:
            pass
        await safe_edit(query, card("✅", "ЗАКРЫТО", f"Жалоба #{cid} закрыта."), back_kb("m_main"))

    elif d == "mod_list":
        rows = q("SELECT user_id, username FROM moderators") or []
        text = card("🔮", "МОДЕРАТОРЫ", "\n".join(f"• @{un or mid}" for mid, un in rows) or "<i>пусто</i>")
        await safe_edit(query, text, back_kb("m_main"))
    elif d == "adm_list":
        rows = q("SELECT user_id, username FROM admins") or []
        text = card("💜", "АДМИНЫ", "\n".join(f"• @{un or mid}" for mid, un in rows) or "<i>пусто</i>")
        await safe_edit(query, text, back_kb("m_main"))
    elif d == "own_all_roles":
        owners = q("SELECT user_id, username FROM owners") or []
        admins = q("SELECT user_id, username FROM admins") or []
        mods = q("SELECT user_id, username FROM moderators") or []
        text = card("👑", "РОЛИ",
            "<b>👑 Владельцы</b>\n" + ("\n".join(f"• @{u or i}" for i, u in owners) or "<i>нет</i>") +
            "\n\n<b>💜 Админы</b>\n" + ("\n".join(f"• @{u or i}" for i, u in admins) or "<i>нет</i>") +
            "\n\n<b>🔮 Модеры</b>\n" + ("\n".join(f"• @{u or i}" for i, u in mods) or "<i>нет</i>")
        )
        await safe_edit(query, text, back_kb("m_main"))
    elif d == "own_maint":
        if not is_owner(user):
            await query.answer("⛔", show_alert=True)
            return
        new = not maintenance_on()
        set_maintenance(new)
        status = "🔴 ВКЛЮЧЕНЫ" if new else "🟢 ВЫКЛЮЧЕНЫ"
        await safe_edit(query, card("🔧", "ТЕХРАБОТЫ", f"Статус · <b>{status}</b>"), owner_panel_kb())
    elif d == "own_broadcast":
        if not is_owner(user):
            await query.answer("⛔", show_alert=True)
            return
        context.user_data["staff_action"] = "broadcast"
        await safe_edit(query, card("📢", "ОБЪЯВЛЕНИЕ", "Напишите текст.\nУйдёт всем.\n\n<code>отмена</code>"), cancel_kb())
    elif d in ("adm_add_mod", "adm_del_mod", "own_add_admin", "own_del_admin",
               "own_add_owner", "own_del_owner", "adm_give", "adm_clear_warns"):
        if d.startswith("own_") and not is_owner(user):
            await query.answer("⛔ Только владелец", show_alert=True)
            return
        if d.startswith("adm_") and not is_admin(user):
            await query.answer("⛔ Только админ", show_alert=True)
            return
        context.user_data["staff_action"] = d
        prompts = {
            "adm_add_mod": "Username или ID для выдачи модератора",
            "adm_del_mod": "Username или ID для снятия модератора",
            "own_add_admin": "Username или ID для выдачи админа",
            "own_del_admin": "Username или ID для снятия админа",
            "own_add_owner": "Username или ID для выдачи владельца",
            "own_del_owner": "Username или ID для снятия владельца",
            "adm_give": "Формат: @user 1000",
            "adm_clear_warns": "Username или ID для сброса варнов",
        }
        await safe_edit(query, card("✏️", "ВВОД", f"{prompts[d]}\n\n<code>отмена</code> — выход"), cancel_kb())

async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return

    user = update.effective_user
    ensure_user(user)
    mark_online(user.id)
    chat = update.effective_chat
    text = (update.message.text or "").strip()
    low = text.lower().strip()

    # запоминаем всех из групп/каналов — для мута по @юзу
    if chat and chat.type in ("group", "supergroup", "channel"):
        track_chat_member(chat.id, user)
        if update.message.reply_to_message and update.message.reply_to_message.from_user:
            track_chat_member(chat.id, update.message.reply_to_message.from_user)

        # ── Антиспам на всех, включая админов группы.
        # Не действует только на @QSOPRA_baby.
        if not is_main_owner(user):
            level, reason = check_spam(chat.id, user.id, text or "")
            if level >= 1:
                await anti_spam_action(context.bot, update.message, user, level, reason)
                return

    # Глобальная отмена — всегда первой
    if low in ("отмена", "cancel", "❌ отмена"):
        clear_staff_state(context)
        await update.message.reply_text("❌ Отменено", reply_markup=main_reply_kb(user))
        return

    if maintenance_on() and not is_staff(user):
        await update.message.reply_text(card("🔧", "ТЕХРАБОТЫ", "Бот временно недоступен."), parse_mode="HTML")
        return

    # ── Жалоба на пользователя ──
    if context.user_data.get("complaint"):
        if len(text) < 5:
            await update.message.reply_text(
                "Слишком коротко. Опишите подробнее или <code>отмена</code>",
                parse_mode="HTML",
            )
            return
        tgt = context.user_data.pop("complaint_target", None) or {}
        # если в тексте есть @ник — тоже считаем целью
        m_at = re.search(r"@([A-Za-z0-9_]{3,})", text)
        target_id = tgt.get("id")
        target_name = tgt.get("name")
        if m_at and not target_id:
            un = m_at.group(1)
            row = q("SELECT user_id, full_name FROM users WHERE username=? COLLATE NOCASE", (un,))
            if row:
                target_id, target_name = row[0][0], row[0][1] or f"@{un}"
            else:
                target_name = f"@{un}"
        cid = add_complaint(
            user.id,
            user.full_name or user.username or str(user.id),
            text,
            target_id=target_id,
            target_name=target_name,
        )
        context.user_data.pop("complaint", None)
        who = f"\n🎯 На · <b>{target_name}</b>" if target_name else ""
        await update.message.reply_text(
            card("📩", "ЖАЛОБА", f"Принята · <b>#{cid}</b>{who}\nСтафф уже уведомлён."),
            parse_mode="HTML",
        )
        await notify_staff(
            context.bot,
            complaint_card_staff(
                cid,
                user.full_name,
                user.id,
                user.username,
                text,
                target_id=target_id,
                target_name=target_name,
            ),
        )
        return

    # ── Биржа: ввод количества ──
    ex = context.user_data.get("exchange_action")
    if ex:
        if not text.isdigit() or int(text) <= 0:
            await update.message.reply_text("Нужно целое число > 0\nили <code>отмена</code>", parse_mode="HTML")
            return
        qty = int(text)
        side, sym = ex.split(":")
        if sym not in EXCHANGE:
            clear_staff_state(context)
            return
        price = get_price(sym)
        meta = EXCHANGE[sym]
        if side == "buy":
            cost = price * qty
            u = get_user(user.id)
            if u[3] < cost:
                await update.message.reply_text(f"❌ Нужно <b>{money(cost)}</b>", parse_mode="HTML")
                return
            add_balance(user.id, -cost)
            set_holding(user.id, sym, get_holding(user.id, sym) + qty)
            context.user_data.pop("exchange_action", None)
            await update.message.reply_text(card("🟢", "КУПЛЕНО",
                f"{meta['emoji']} {meta['name']} × {qty}\n"
                f"Списано · <b>{money(cost)}</b>"
            ), parse_mode="HTML")
        else:
            hold = get_holding(user.id, sym)
            if hold < qty:
                await update.message.reply_text(f"❌ У вас только {hold} шт.")
                return
            gain = price * qty
            set_holding(user.id, sym, hold - qty)
            add_balance(user.id, gain)
            context.user_data.pop("exchange_action", None)
            await update.message.reply_text(card("🔴", "ПРОДАНО",
                f"{meta['emoji']} {meta['name']} × {qty}\n"
                f"Получено · <b>{money(gain)}</b>"
            ), parse_mode="HTML")
        return

    # ── Staff actions ──
    action = context.user_data.get("staff_action")
    if action:
        if action == "broadcast":
            if not is_owner(user):
                clear_staff_state(context)
                return
            users = q("SELECT user_id FROM users") or []
            ok = 0
            skip = 0
            for (tid,) in users:
                if not get_notify(tid, "broadcast"):
                    skip += 1
                    continue
                try:
                    await context.bot.send_message(tid, card("📢", "ОБЪЯВЛЕНИЕ", text), parse_mode="HTML")
                    ok += 1
                    await asyncio.sleep(0.04)
                except Exception:
                    pass
            clear_staff_state(context)
            await update.message.reply_text(
                f"✅ Доставлено: {ok}/{len(users)}\n"
                f"🔕 Отключено у: {skip}"
            )
            return

        target_uid = None
        target_un = None
        amount = None
        parts = text.replace("@", "").split()

        if action == "adm_give":
            if len(parts) < 2:
                await update.message.reply_text("Формат: @user 1000\nили <code>отмена</code>", parse_mode="HTML")
                return
            who, amount_s = parts[0], parts[1]
            if not amount_s.isdigit():
                await update.message.reply_text("Сумма — число")
                return
            amount = int(amount_s)
            if who.isdigit():
                target_uid = int(who)
            else:
                r = q("SELECT user_id, username FROM users WHERE username=? COLLATE NOCASE", (who,))
                if r:
                    target_uid, target_un = r[0]
        else:
            who = parts[0] if parts else ""
            if who.isdigit():
                target_uid = int(who)
            else:
                r = q("SELECT user_id, username FROM users WHERE username=? COLLATE NOCASE", (who,))
                if r:
                    target_uid, target_un = r[0]

        if not target_uid:
            await update.message.reply_text(
                "Не найден. Пусть напишет боту /start\n"
                "Или <code>отмена</code>",
                parse_mode="HTML"
            )
            return  # staff_action НЕ сбрасываем — можно повторить или отменить

        tu = get_user(target_uid)
        target_un = target_un or (tu[1] if tu else f"id{target_uid}")

        if action == "adm_add_mod":
            if not is_admin(user):
                clear_staff_state(context)
                return
            grant_mod(target_uid, target_un)
            await update.message.reply_text(f"✅ Модератор · @{target_un}")
            try:
                await context.bot.send_message(target_uid, "🔮 Вам выданы права модератора")
            except Exception:
                pass
        elif action == "adm_del_mod":
            if not is_admin(user):
                clear_staff_state(context)
                return
            revoke_mod(target_uid)
            await update.message.reply_text(f"✅ Снят модер · @{target_un}")
        elif action == "own_add_admin":
            if not is_owner(user):
                clear_staff_state(context)
                return
            grant_admin(target_uid, target_un)
            await update.message.reply_text(f"✅ Админ · @{target_un}")
            try:
                await context.bot.send_message(target_uid, "💜 Вам выданы права администратора")
            except Exception:
                pass
        elif action == "own_del_admin":
            if not is_owner(user):
                clear_staff_state(context)
                return
            revoke_admin(target_uid)
            await update.message.reply_text(f"✅ Снят админ · @{target_un}")
        elif action == "own_add_owner":
            if not is_main_owner(user):
                await update.message.reply_text("⛔ Только @QSOPRA_baby")
                clear_staff_state(context)
                return
            grant_owner(target_uid, target_un)
            await update.message.reply_text(f"👑 Владелец · @{target_un}")
            try:
                await context.bot.send_message(target_uid, "👑 Вам выданы права владельца")
            except Exception:
                pass
        elif action == "own_del_owner":
            if not is_main_owner(user):
                clear_staff_state(context)
                return
            if not revoke_owner(target_uid):
                await update.message.reply_text("Нельзя снять @QSOPRA_baby")
            else:
                await update.message.reply_text(f"✅ Снят овнер · @{target_un}")
        elif action == "adm_give":
            if not is_admin(user):
                clear_staff_state(context)
                return
            add_balance(target_uid, amount)
            await update.message.reply_text(f"✅ +{money(amount)} → @{target_un}", parse_mode="HTML")
            try:
                await context.bot.send_message(target_uid, f"💜 Вам выдано <b>{money(amount)}</b>", parse_mode="HTML")
            except Exception:
                pass
        elif action == "adm_clear_warns":
            if not is_admin(user):
                clear_staff_state(context)
                return
            clear_warns(target_uid)
            await update.message.reply_text(f"✅ Варны сброшены · @{target_un}")

        clear_staff_state(context)
        return

    # ── Кнопки клавиатуры ──
    kb_map = {
        "👤 Профиль": "profile",
        "💜 Экономика": "economy",
        "📈 Биржа": "exchange",
        "📈 Открыть биржу": "exchange",
        "🎮 Игры": "games",
        "🏆 Топы": "tops",
        "📩 Жалоба": "complaint",
        "💜 Отношения": "relations",
        "🎭 RP": "rp",
        "🛡 Модерация": "modhelp",
        "ℹ️ Помощь": "help",
        "🔔 Уведомления": "notify",
        "🔮 Панель мод": "modpanel",
        "💜 Панель админ": "adminpanel",
        "👑 Панель овнер": "ownerpanel",
    }
    if text in kb_map:
        clear_staff_state(context)
        key = kb_map[text]
        if key == "profile":
            await update.message.reply_text(profile_text(user.id), parse_mode="HTML")
        elif key == "economy":
            u = get_user(user.id)
            await update.message.reply_text(
                card("💜", "ЭКОНОМИКА", f"Баланс · <b>{money(u[3])}</b>\nАктивы · <b>{money(portfolio_value(user.id))}</b>"),
                reply_markup=economy_kb(), parse_mode="HTML"
            )
        elif key == "exchange":
            mark_trader(user.id)
            await update.message.reply_text(exchange_text(user.id), reply_markup=exchange_main_kb(), parse_mode="HTML")
        elif key == "games":
            await update.message.reply_text(card("🎮", "ИГРЫ", f"Мин. ставка · {money(MIN_BET)}"), reply_markup=games_kb(), parse_mode="HTML")
        elif key == "tops":
            await update.message.reply_text(card("🏆", "ТОПЫ", "Категория:"), reply_markup=tops_kb(), parse_mode="HTML")
        elif key == "complaint":
            context.user_data["complaint"] = True
            context.user_data.pop("complaint_target", None)
            await update.message.reply_text(
                card(
                    "📩",
                    "ЖАЛОБА НА ПОЛЬЗОВАТЕЛЯ",
                    "Ответьте на сообщение нарушителя и напишите <code>жалоба</code>\n"
                    "или: <code>жалоба @ник</code>\n"
                    "затем опишите ситуацию.\n\n"
                    "<code>отмена</code> — выход",
                ),
                parse_mode="HTML",
            )
        elif key == "relations":
            await update.message.reply_text(card("💜", "ОТНОШЕНИЯ", "Выберите:"), reply_markup=marriage_kb(), parse_mode="HTML")
        elif key == "rp":
            await update.message.reply_text(card("🎭", "RP", "Выберите действие:"), reply_markup=rp_kb(), parse_mode="HTML")
        elif key == "modhelp":
            await update.message.reply_text(mod_help_text(), parse_mode="HTML")
        elif key == "help":
            await update.message.reply_text(help_text(), parse_mode="HTML")
        elif key == "notify":
            await update.message.reply_text(
                notify_settings_text(user),
                reply_markup=notify_settings_kb(user),
                parse_mode="HTML",
            )
        elif key == "modpanel":
            if not is_mod(user):
                await update.message.reply_text("⛔")
                return
            await update.message.reply_text(card("🔮", "ПАНЕЛЬ МОД", "Доступ:"), reply_markup=mod_panel_kb(), parse_mode="HTML")
        elif key == "adminpanel":
            if not is_admin(user):
                await update.message.reply_text("⛔")
                return
            await update.message.reply_text(card("💜", "ПАНЕЛЬ АДМИН", "Доступ:"), reply_markup=admin_panel_kb(), parse_mode="HTML")
        elif key == "ownerpanel":
            if not is_owner(user):
                await update.message.reply_text("⛔")
                return
            await update.message.reply_text(card("👑", "ПАНЕЛЬ ОВНЕР", "Доступ:"), reply_markup=owner_panel_kb(), parse_mode="HTML")
        return

    # ── Текстовые команды ──
    if low in ("меню", "menu", "старт"):
        await start(update, context)
        return
    if low in ("профиль", "я"):
        await update.message.reply_text(profile_text(user.id), parse_mode="HTML")
        return
    if low in ("помощь", "хелп", "help", "команды"):
        await update.message.reply_text(help_text(), parse_mode="HTML")
        return
    if low in ("уведомления", "уведы", "notify", "нотиф", "фильтры", "триггеры"):
        await update.message.reply_text(
            notify_settings_text(user),
            reply_markup=notify_settings_kb(user),
            parse_mode="HTML",
        )
        return
    # триггер порога текстом: триггер 5
    m_tr = re.match(r"триггер\s+(\d+(?:[.,]\d+)?)\s*%?", low)
    if m_tr:
        pct = float(m_tr.group(1).replace(",", "."))
        pct = set_trigger_pct(user.id, pct)
        set_notify(user.id, "exchange_big", True)
        await update.message.reply_text(
            card(
                "⚙️",
                "ТРИГГЕР",
                f"Порог сильного движения · <b>{pct:g}%</b>\n"
                f"Фильтр «только сильные» · ✅ вкл",
            ),
            reply_markup=trigger_settings_kb(user),
            parse_mode="HTML",
        )
        return
    if low in ("онлайн", "online"):
        await update.message.reply_text(online_text(), parse_mode="HTML")
        return
    if low in ("баланс", "б"):
        u = get_user(user.id)
        await update.message.reply_text(
            f"💜 <b>{money(u[3])}</b>\n📈 активы · {money(portfolio_value(user.id))}",
            parse_mode="HTML"
        )
        return
    if low in ("топ", "top", "топы"):
        await update.message.reply_text(top_text("balance"), reply_markup=tops_kb(), parse_mode="HTML")
        return
    if low in ("биржа", "биржа qsopra", "exchange", "курс", "рынок"):
        mark_trader(user.id)
        await update.message.reply_text(exchange_text(user.id), reply_markup=exchange_main_kb(), parse_mode="HTML")
        return
    if low in ("портфель", "активы"):
        mark_trader(user.id)
        await update.message.reply_text(portfolio_text(user.id), reply_markup=portfolio_kb(user.id), parse_mode="HTML")
        return
    if low in ("daily", "ежедневка", "бонус"):
        reward, err = await claim_daily(user.id)
        if err:
            await update.message.reply_text(err)
        else:
            await update.message.reply_text(card("🎁", "DAILY", f"+<b>{money(reward)}</b>"), parse_mode="HTML")
        return
    if low.startswith("жалоба") or low.startswith("репорт") or low.startswith("report"):
        context.user_data["complaint"] = True
        context.user_data.pop("complaint_target", None)
        # ответ на сообщение = жалоба на этого человека
        if update.message.reply_to_message and update.message.reply_to_message.from_user:
            t = update.message.reply_to_message.from_user
            if not t.is_bot and t.id != user.id:
                context.user_data["complaint_target"] = {
                    "id": t.id,
                    "name": t.full_name or t.username or str(t.id),
                }
                track_chat_member(chat.id, t) if chat and chat.type in ("group", "supergroup", "channel") else None
        # жалоба @nick
        m_at = re.search(r"@([A-Za-z0-9_]{3,})", text)
        if m_at and not context.user_data.get("complaint_target"):
            un = m_at.group(1)
            row = q("SELECT user_id, full_name FROM users WHERE username=? COLLATE NOCASE", (un,))
            if row:
                context.user_data["complaint_target"] = {
                    "id": row[0][0],
                    "name": row[0][1] or f"@{un}",
                }
            else:
                context.user_data["complaint_target"] = {"id": None, "name": f"@{un}"}
        tgt = context.user_data.get("complaint_target")
        extra = ""
        if tgt:
            extra = f"\n🎯 Цель: <b>{tgt.get('name')}</b>\n"
        await update.message.reply_text(
            card(
                "📩",
                "ЖАЛОБА НА ПОЛЬЗОВАТЕЛЯ",
                f"{extra}"
                "Опишите одним сообщением, что произошло.\n"
                "Текст уйдёт модерам, админам и владельцам.\n\n"
                "<code>отмена</code> — выход",
            ),
            parse_mode="HTML",
        )
        return
    if low in ("мод", "модер", "модератор", "mod"):
        if not is_mod(user):
            await update.message.reply_text("⛔")
            return
        await update.message.reply_text(card("🔮", "ПАНЕЛЬ МОД", "Доступ:"), reply_markup=mod_panel_kb(), parse_mode="HTML")
        return
    if low in ("админ", "admin", "админка"):
        if not is_admin(user):
            await update.message.reply_text("⛔")
            return
        await update.message.reply_text(card("💜", "ПАНЕЛЬ АДМИН", "Доступ:"), reply_markup=admin_panel_kb(), parse_mode="HTML")
        return
    if low in ("овнер", "owner", "владелец"):
        if not is_owner(user):
            await update.message.reply_text("⛔")
            return
        await update.message.reply_text(card("👑", "ПАНЕЛЬ ОВНЕР", "Доступ:"), reply_markup=owner_panel_kb(), parse_mode="HTML")
        return
    if low in ("рп", "rp"):
        await update.message.reply_text(card("🎭", "RP", "Выберите:"), reply_markup=rp_kb(), parse_mode="HTML")
        return
    if low in ("игры", "игра"):
        await update.message.reply_text(card("🎮", "ИГРЫ", f"Мин. · {money(MIN_BET)}"), reply_markup=games_kb(), parse_mode="HTML")
        return

    # Купить / продать текстом (крипта и акции)
    m_buy = re.match(r"купить\s+(\w+)\s+(\d+)", low)
    if m_buy:
        sym, qty = m_buy.group(1).upper(), int(m_buy.group(2))
        if sym not in EXCHANGE:
            await update.message.reply_text("Неизвестный тикер. Напиши <code>биржа</code>", parse_mode="HTML")
            return
        mark_trader(user.id)
        price = get_price(sym)
        cost = price * qty
        u = get_user(user.id)
        if u[3] < cost:
            await update.message.reply_text(f"❌ Нужно {money(cost)}", parse_mode="HTML")
            return
        add_balance(user.id, -cost)
        set_holding(user.id, sym, get_holding(user.id, sym) + qty)
        meta = EXCHANGE[sym]
        kind = "крипта" if meta.get("cat") == "crypto" else "акция"
        await update.message.reply_text(
            card("🟢", "КУПЛЕНО",
                 f"{meta['emoji']} <b>{meta['name']}</b> × {qty}\n"
                 f"Тип · {kind}\n−{money(cost)}"),
            parse_mode="HTML"
        )
        return

    m_sell = re.match(r"продать\s+(\w+)\s+(\d+)", low)
    if m_sell:
        sym, qty = m_sell.group(1).upper(), int(m_sell.group(2))
        if sym not in EXCHANGE:
            await update.message.reply_text("Неизвестный тикер.")
            return
        mark_trader(user.id)
        hold = get_holding(user.id, sym)
        if hold < qty:
            await update.message.reply_text(f"❌ У вас {hold} шт.")
            return
        gain = get_price(sym) * qty
        set_holding(user.id, sym, hold - qty)
        add_balance(user.id, gain)
        meta = EXCHANGE[sym]
        kind = "крипта" if meta.get("cat") == "crypto" else "акция"
        await update.message.reply_text(
            card("🔴", "ПРОДАНО",
                 f"{meta['emoji']} <b>{meta['name']}</b> × {qty}\n"
                 f"Тип · {kind}\n+{money(gain)}"),
            parse_mode="HTML"
        )
        return

    # продать всё по тикеру
    m_sell_all = re.match(r"продать\s+(\w+)\s+вс[её]", low)
    if m_sell_all:
        sym = m_sell_all.group(1).upper()
        if sym not in EXCHANGE:
            await update.message.reply_text("Неизвестный тикер.")
            return
        mark_trader(user.id)
        hold = get_holding(user.id, sym)
        if hold <= 0:
            await update.message.reply_text("Нечего продавать")
            return
        gain = get_price(sym) * hold
        set_holding(user.id, sym, 0)
        add_balance(user.id, gain)
        meta = EXCHANGE[sym]
        await update.message.reply_text(
            card("🔴", "ПРОДАНО ВСЁ",
                 f"{meta['emoji']} <b>{meta['name']}</b> × {hold}\n+{money(gain)}"),
            parse_mode="HTML"
        )
        return

    # Игры
    if low.startswith("монетка"):
        parts = text.split()
        amount = next((int(p) for p in parts if p.isdigit()), None)
        side = None
        for p in parts:
            pl = p.lower()
            if pl in ("о", "орёл", "орел", "o"):
                side = "о"
            elif pl in ("р", "решка", "p"):
                side = "р"
        if not amount or amount < MIN_BET or not side:
            await update.message.reply_text(f"<code>монетка 50 о</code> · мин {money(MIN_BET)}", parse_mode="HTML")
            return
        await play_coin(update.message, user.id, amount, side)
        return

    if low.startswith("кости"):
        amount = next((int(p) for p in text.split() if p.isdigit()), None)
        if not amount or amount < MIN_BET:
            await update.message.reply_text(f"<code>кости 50</code> · мин {money(MIN_BET)}", parse_mode="HTML")
            return
        await play_dice(update.message, user.id, amount)
        return

    if low.startswith("угадай"):
        nums = [int(p) for p in text.split() if p.isdigit()]
        if len(nums) < 2 or nums[0] < MIN_BET or not 1 <= nums[1] <= 10:
            await update.message.reply_text("<code>угадай 50 7</code>", parse_mode="HTML")
            return
        await play_guess(update.message, user.id, nums[0], nums[1])
        return

    if low.startswith("слоты"):
        amount = next((int(p) for p in text.split() if p.isdigit()), None)
        if not amount or amount < MIN_BET:
            await update.message.reply_text(f"<code>слоты 50</code> · мин {money(MIN_BET)}", parse_mode="HTML")
            return
        await play_slots(update.message, user.id, amount)
        return

    if low.startswith("передать"):
        target = get_target(update)
        if not target:
            await update.message.reply_text("Ответьте на сообщение: передать 100")
            return
        ensure_user(target)
        amount = next((int(p) for p in text.split() if p.isdigit()), None)
        if not amount or amount <= 0:
            await update.message.reply_text("Укажите сумму")
            return
        sender = get_user(user.id)
        if sender[3] < amount:
            await update.message.reply_text("Недостаточно Q")
            return
        add_balance(user.id, -amount)
        add_balance(target.id, amount)
        await update.message.reply_text(f"✅ {money(amount)} → {target.full_name}", parse_mode="HTML")
        return

    if low == "брак":
        if not update.message.reply_to_message:
            await update.message.reply_text("Ответьте на сообщение")
            return
        target = update.message.reply_to_message.from_user
        if target.id == user.id or target.is_bot:
            await update.message.reply_text("Нельзя")
            return
        ensure_user(target)
        if get_marriage(user.id) or get_marriage(target.id):
            await update.message.reply_text("Кто-то уже в браке")
            return
        create_marriage(user.id, target.id)
        await update.message.reply_text(f"💍 {user.full_name} и {target.full_name} — в браке!")
        return

    if low == "развод":
        if not get_marriage(user.id):
            await update.message.reply_text("Вы не в браке")
            return
        delete_marriage(user.id)
        await update.message.reply_text("Брак расторгнут")
        return

    if low in ("мой брак", "брак мой"):
        m = get_marriage(user.id)
        if not m:
            await update.message.reply_text("Не в браке")
            return
        pid = m[1] if m[0] == user.id else m[0]
        p = get_user(pid)
        await update.message.reply_text(f"💍 С <b>{p[2] if p else pid}</b> · с {m[2]}", parse_mode="HTML")
        return

    RP = {
        "обнять": "обнял(а)", "поцеловать": "поцеловал(а)", "ударить": "ударил(а)",
        "погладить": "погладил(а)", "укусить": "укусил(а)", "пнуть": "пнул(а)",
        "лизнуть": "лизнул(а)", "шлепнуть": "шлепнул(а)", "дать пять": "дал(а) пять",
    }
    if low in RP:
        if not update.message.reply_to_message:
            await update.message.reply_text("Ответьте на сообщение")
            return
        target = update.message.reply_to_message.from_user
        await update.message.reply_text(f"{user.full_name} {RP[low]} {target.full_name}")
        return

    # ── Модерация: reply ИЛИ @user ИЛИ id · сроки до лет ──
    if any(low.startswith(cmd) for cmd in ("размут", "разбан", "бан", "мут", "варн", "кик")):
        if update.effective_chat.type == "private":
            await update.message.reply_text("Модерация только в группах/супергруппах")
            return
        if not is_mod(user):
            try:
                member = await update.effective_chat.get_member(user.id)
                if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER, "administrator", "creator"):
                    await update.message.reply_text("⛔ У вас недостаточно прав для модерации.")
                    return
            except Exception:
                await update.message.reply_text("⛔ У вас недостаточно прав для модерации.")
                return

        bot = context.bot
        chat_id = update.effective_chat.id
        target_id, target_name = await resolve_mod_target(bot, chat_id, update, text)
        if not target_id:
            await update.message.reply_text(
                "😔 Не удалось найти пользователя.\n\n"
                "Как выдать мут или бан:\n"
                "1) Ответьте на его сообщение → <code>мут 1ч</code>\n"
                "2) Пусть он напишет в чат, затем: <code>мут @ник 1ч</code>\n"
                "3) Или по ID: <code>мут 123456789 1ч</code>",
                parse_mode="HTML"
            )
            return
        if target_id == user.id:
            await update.message.reply_text("⛔ Нельзя применить наказание к себе.")
            return
        if target_id == bot.id:
            await update.message.reply_text("⛔ Нельзя применить наказание к боту.")
            return

        # Защита @QSOPRA_baby
        protected = False
        if MAIN_ADMIN_ID and target_id == MAIN_ADMIN_ID:
            protected = True
        tu = get_user(target_id)
        if tu and tu[1] and str(tu[1]).lower() == MAIN_ADMIN.lower():
            protected = True
        if re.search(rf"@{re.escape(MAIN_ADMIN)}\b", text or "", re.I):
            protected = True
        if protected and any(low.startswith(c) for c in ("бан", "мут", "кик", "варн")):
            await update.message.reply_text(
                f"⛔ @{MAIN_ADMIN} защищён.\nНа него нельзя выдать бан, мут, кик или варн."
            )
            return

        # Владелец чата
        try:
            tm = await bot.get_chat_member(chat_id, target_id)
            if tm.status in (ChatMemberStatus.OWNER, "creator"):
                await update.message.reply_text(
                    f"⛔ <b>{target_name}</b> — владелец группы.\n"
                    "На владельца чата нельзя выдать мут или бан.",
                    parse_mode="HTML"
                )
                return
        except Exception:
            pass

        reason = parse_mod_reason(text)
        foot = mod_action_footer(user, reason)
        chat_title = getattr(update.effective_chat, "title", None) or str(chat_id)

        async def _modlog(action_text):
            await notify_staff(
                bot,
                card(
                    "🛡",
                    "МОД-ЛОГ",
                    f"{action_text}\n"
                    f"Чат · <b>{chat_title}</b>\n\n{foot}",
                ),
                kind="modlog",
            )

        try:
            if low.startswith("размут"):
                await bot.restrict_chat_member(chat_id, target_id, permissions=UNMUTE_PERMS)
                await update.message.reply_text(
                    f"🔊 <b>{target_name}</b> размучен\n\n{foot}",
                    parse_mode="HTML",
                )
                await _modlog(f"🔊 Размут · <b>{target_name}</b>")
            elif low.startswith("разбан"):
                await bot.unban_chat_member(chat_id, target_id, only_if_banned=False)
                await update.message.reply_text(
                    f"✅ <b>{target_name}</b> разбанен (может вернуться)\n\n{foot}",
                    parse_mode="HTML",
                )
                await _modlog(f"✅ Разбан · <b>{target_name}</b>")
            elif low.startswith("бан"):
                sec = parse_time(text) or 0
                until = datetime.now() + timedelta(seconds=sec) if sec else None
                await bot.ban_chat_member(chat_id, target_id, until_date=until)
                await update.message.reply_text(
                    f"🚫 <b>{target_name}</b> забанен\n"
                    f"⏱ Срок: <b>{format_duration(sec)}</b>\n\n{foot}",
                    parse_mode="HTML",
                )
                await _modlog(
                    f"🚫 Бан · <b>{target_name}</b>\n⏱ {format_duration(sec)}"
                )
            elif low.startswith("мут"):
                sec = parse_time(text) or 3600
                until = datetime.now() + timedelta(seconds=sec)
                await bot.restrict_chat_member(chat_id, target_id, permissions=MUTE_PERMS, until_date=until)
                await update.message.reply_text(
                    f"🔇 <b>{target_name}</b> в муте\n"
                    f"⏱ Срок: <b>{format_duration(sec)}</b>\n\n{foot}",
                    parse_mode="HTML",
                )
                await _modlog(
                    f"🔇 Мут · <b>{target_name}</b>\n⏱ {format_duration(sec)}"
                )
            elif low.startswith("варн"):
                class _T:
                    id = target_id
                    username = None
                    full_name = target_name
                ensure_user(_T())
                w = add_warn(target_id)
                left = max(0, WARN_LIMIT - w)
                msg = (
                    f"⚠️ <b>{target_name}</b>\n"
                    f"Варны: <b>{w}/{WARN_LIMIT}</b>\n"
                )
                if left > 0:
                    msg += f"До автобана: <b>{left}</b>\n\n{foot}"
                    await update.message.reply_text(msg, parse_mode="HTML")
                    await _modlog(f"⚠️ Варн · <b>{target_name}</b> · {w}/{WARN_LIMIT}")
                else:
                    ban_ok = False
                    try:
                        until = (
                            datetime.now() + timedelta(seconds=WARN_BAN_SEC)
                            if WARN_BAN_SEC > 0
                            else None
                        )
                        await bot.ban_chat_member(chat_id, target_id, until_date=until)
                        ban_ok = True
                        clear_warns(target_id)
                    except Exception:
                        ban_ok = False
                    if ban_ok:
                        msg += (
                            f"\n🚫 <b>Автобан</b> — достигнут лимит варнов ({WARN_LIMIT})\n"
                            f"⏱ Срок: <b>{format_duration(WARN_BAN_SEC)}</b>\n\n{foot}"
                        )
                        await _modlog(
                            f"🚫 Автобан по варнам · <b>{target_name}</b>\n"
                            f"⏱ {format_duration(WARN_BAN_SEC)}"
                        )
                    else:
                        msg += (
                            f"\n🚫 Лимит варнов ({WARN_LIMIT}) достигнут, "
                            f"но забанить не удалось.\n\n{foot}"
                        )
                    await update.message.reply_text(msg, parse_mode="HTML")
            elif low.startswith("кик"):
                await bot.ban_chat_member(chat_id, target_id)
                await bot.unban_chat_member(chat_id, target_id)
                await update.message.reply_text(
                    f"👢 <b>{target_name}</b> исключён\n\n{foot}",
                    parse_mode="HTML",
                )
                await _modlog(f"👢 Кик · <b>{target_name}</b>")
        except Exception:
            await update.message.reply_text(soft_error("mod"))

async def hourly_market_job(context: ContextTypes.DEFAULT_TYPE):
    """Автообновление курса раз в час + совет трейдерам."""
    if tick_prices(force=True):
        await notify_traders(context.bot, market_summary_text())

async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Глобальный обработчик — в чат только вежливое сообщение, без трейса."""
    err = context.error
    # в консоль — для отладки
    try:
        print(f"[ошибка] {type(err).__name__}: {err}")
    except Exception:
        pass
    # пользователю — только мягкий текст
    try:
        if update and getattr(update, "effective_message", None):
            await update.effective_message.reply_text(soft_error())
        elif update and getattr(update, "callback_query", None):
            try:
                await update.callback_query.answer("Извините, произошла ошибка", show_alert=False)
            except Exception:
                pass
            if update.callback_query.message:
                await update.callback_query.message.reply_text(soft_error())
    except Exception:
        pass

def main():
    init_db()
    tick_prices(force=True)
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", start))
    app.add_handler(CommandHandler("help", lambda u, c: u.message.reply_text(help_text(), parse_mode="HTML")))
    app.add_handler(CallbackQueryHandler(menu_cb))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))
    app.add_error_handler(on_error)

    try:
        if app.job_queue:
            app.job_queue.run_repeating(hourly_market_job, interval=PRICE_TICK_SEC, first=PRICE_TICK_SEC)
            print("Автокурс: каждый час")
        else:
            print("job_queue недоступен — курс обновится при открытии биржи")
    except Exception as e:
        print("job_queue:", e)

    print(f"QSOPRA Helper Remaster {VERSION} | биржа · жалобы · антиспам")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
