# main.py
# -*- coding: utf-8 -*-

import os
import re
import asyncio
from secrets import token_urlsafe
from urllib.parse import quote as urlquote
from datetime import datetime, timezone

# Telegram Bot API imports
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputTextMessageContent,
    InlineQueryResultArticle,
)
from telegram.constants import ParseMode, ChatType
from telegram.error import Forbidden, BadRequest
from telegram.ext import (
    Application,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    InlineQueryHandler,
    ChosenInlineResultHandler,
    ChatMemberHandler,
    filters,
)

# Database library
import asyncpg

# --------- تنظیمات اصلی ربات ---------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# شناسه‌های عددی ادمین‌های ربات (برای گزارش‌گیری و دستورات ویژه)
# لطفا شناسه‌ها را داخل {} و با کاما از هم جدا کنید
ADMIN_IDS = {7662192190, 6041119040}

# کانال عضویت اجباری (یوزرنیم بدون @)
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "RHINOSOUL_TM")

# تنظیمات جانبی
MAX_GROUPS = int(os.environ.get("MAX_GROUPS", "100"))
SUPPORT_CONTACT = os.environ.get("SUPPORT_CONTACT", "OLDKASEB")

# ---------- ثوابت برنامه ----------
TRIGGERS = {"نجوا", "درگوشی", "سکرت", "غیبت"}
GUIDE_DELETE_AFTER_SEC = 180
ALERT_SNIPPET = 190
FAR_FUTURE = datetime(2099, 1, 1, tzinfo=timezone.utc)

MANDATORY_CHANNELS = [ch.replace("@", "").strip() for ch in CHANNEL_USERNAME.split(',') if ch]

# ---------- متغیرهای سراسری ----------
BOT_USERNAME: str = "RHINOSOUL_AI_BOT"
app: Application = None
pool: asyncpg.Pool = None

# ---------- دیتابیس (PostgreSQL) ----------

CREATE_SQL = """
-- جدول کاربران ربات
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_seen TIMESTAMPTZ DEFAULT NOW()
);

-- جدول چت‌ها (خصوصی و گروه)
CREATE TABLE IF NOT EXISTS chats (
    chat_id BIGINT PRIMARY KEY,
    title TEXT,
    type TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_seen TIMESTAMPTZ DEFAULT NOW()
);

-- جدول نجواهای فردی (ریپلای و اینلاین)
CREATE TABLE IF NOT EXISTS whispers (
    id BIGSERIAL PRIMARY KEY,
    group_id BIGINT,
    sender_id BIGINT NOT NULL,
    receiver_id BIGINT NOT NULL,
    text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'sent', -- 'sent' یا 'read'
    is_anonymous BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    message_id BIGINT,
    inline_message_id TEXT
);

-- جدول درخواست‌های در حال انتظار برای ارسال متن نجوا
CREATE TABLE IF NOT EXISTS pending (
    sender_id BIGINT PRIMARY KEY,
    group_id BIGINT NOT NULL,
    receiver_id BIGINT NOT NULL,
    is_anonymous BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    guide_message_id BIGINT,
    reply_to_msg_id BIGINT
);

-- جدول نجواهای گروهی (برای حالت اینلاین گروهی)
CREATE TABLE IF NOT EXISTS group_whispers (
    id BIGSERIAL PRIMARY KEY,
    sender_id BIGINT NOT NULL,
    text TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    inline_message_id TEXT,
    is_finished BOOLEAN DEFAULT FALSE
);

-- جدول گیرندگان نجواهای گروهی
CREATE TABLE IF NOT EXISTS group_whisper_recipients (
    id BIGSERIAL PRIMARY KEY,
    whisper_id BIGINT REFERENCES group_whispers(id) ON DELETE CASCADE,
    receiver_id BIGINT NOT NULL,
    status TEXT NOT NULL DEFAULT 'sent' -- 'sent' یا 'read'
);

-- جدول مخاطبین اخیر کاربر برای حالت اینلاین
CREATE TABLE IF NOT EXISTS whisper_contacts (
    owner_id BIGINT NOT NULL,
    peer_id BIGINT NOT NULL,
    last_used TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (owner_id, peer_id)
);
"""

ALTER_SQL = """
-- این دستورات برای اطمینان از وجود ستون‌های جدید در نسخه‌های قدیمی‌تر است
ALTER TABLE whispers ADD COLUMN IF NOT EXISTS is_anonymous BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE pending ADD COLUMN IF NOT EXISTS is_anonymous BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE whispers ADD COLUMN IF NOT EXISTS inline_message_id TEXT;
ALTER TABLE group_whispers ADD COLUMN IF NOT EXISTS is_finished BOOLEAN DEFAULT FALSE;
"""

async def init_db():
    """اتصال به دیتابیس و ایجاد جداول در صورت نیاز."""
    global pool
    try:
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
        async with pool.acquire() as con:
            await con.execute(CREATE_SQL)
            await con.execute(ALTER_SQL)
        print("Database connection successful.")
    except Exception as e:
        print(f"FATAL: Could not connect to the database. Error: {e}")
        # در صورت عدم اتصال به دیتابیس، ربات نباید اجرا شود
        # os._exit(1) # Uncomment for production

# ---------- توابع کمکی (Helpers) ----------

def sanitize(name: str) -> str:
    """جلوگیری از تزریق HTML در نام کاربران."""
    return (name or "کاربر").replace("<", "&lt;").replace(">", "&gt;")

def mention_html(user_id: int, name: str) -> str:
    """ایجاد یک منشن قابل کلیک برای کاربر."""
    return f'<a href="tg://user?id={user_id}">{sanitize(name)}</a>'

async def safe_delete(bot, chat_id: int, message_id: int):
    """حذف امن یک پیام با چند بار تلاش."""
    for _ in range(3):
        try:
            await bot.delete_message(chat_id, message_id)
            return True
        except Exception:
            await asyncio.sleep(0.5)
    return False

def schedule_delete(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, delay_sec: int):
    """زمان‌بندی حذف یک پیام برای چند ثانیه بعد."""
    async def _delete_task():
        await asyncio.sleep(delay_sec)
        await safe_delete(context.bot, chat_id, message_id)
    context.application.create_task(_delete_task())

async def report_to_admins(context: ContextTypes.DEFAULT_TYPE, text: str):
    """ارسال یک پیام متنی به تمام ادمین‌های تعریف شده."""
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        except (Forbidden, BadRequest) as e:
            print(f"Could not send report to admin {admin_id}: {e}")

async def get_name_for(user_id: int, fallback: str = "کاربر") -> str:
    """دریافت نام کاربر از دیتابیس یا از طریق API تلگرام."""
    if not pool: return sanitize(fallback)
    async with pool.acquire() as con:
        # ابتدا از دیتابیس محلی تلاش می‌کنیم
        name = await con.fetchval("SELECT first_name FROM users WHERE user_id=$1;", user_id)
    if name:
        return sanitize(name)
    try: # اگر در دیتابیس نبود، از تلگرام می‌پرسیم
        user_chat = await app.bot.get_chat(user_id)
        return sanitize(user_chat.first_name)
    except Exception:
        return sanitize(fallback)

# ---------- توابع مدیریت دیتابیس (CRUD) ----------

async def upsert_user(u: "User"):
    """افزودن یا به‌روزرسانی اطلاعات یک کاربر در دیتابیس."""
    if not pool or not u: return
    async with pool.acquire() as con:
        await con.execute(
            "INSERT INTO users (user_id, username, first_name, last_seen) VALUES ($1, $2, $3, NOW()) "
            "ON CONFLICT (user_id) DO UPDATE SET username=EXCLUDED.username, first_name=EXCLUDED.first_name, last_seen=NOW();",
            u.id, u.username, u.first_name
        )

async def upsert_chat(c: "Chat", active: bool = True):
    """افزودن یا به‌روزرسانی اطلاعات یک چت (گروه) در دیتابیس."""
    if not pool or not c: return
    async with pool.acquire() as con:
        await con.execute(
            "INSERT INTO chats (chat_id, title, type, is_active, last_seen) VALUES ($1, $2, $3, $4, NOW()) "
            "ON CONFLICT (chat_id) DO UPDATE SET title=EXCLUDED.title, type=EXCLUDED.type, is_active=$4, last_seen=NOW();",
            c.id, getattr(c, "title", "گروه خصوصی"), c.type, active
        )

# ---------- منطق عضویت اجباری (Force Join) ----------

async def is_member_of_channels(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    """بررسی می‌کند که آیا کاربر در تمام کانال‌های اجباری عضو است یا خیر."""
    if not MANDATORY_CHANNELS:
        return True
    try:
        for ch_username in MANDATORY_CHANNELS:
            member = await context.bot.get_chat_member(f"@{ch_username}", user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        return True
    except Exception as e:
        print(f"Error checking channel membership for {user_id}: {e}")
        # در صورت بروز خطا، موقتا به کاربر اجازه عبور می‌دهیم تا ربات متوقف نشود
        return True

def get_join_channels_markup() -> InlineKeyboardMarkup:
    """ایجاد دکمه‌ها برای عضویت در کانال‌ها."""
    buttons = [[InlineKeyboardButton("✅ عضویت خود را تایید کنید", callback_data="check_join")]]
    for ch_username in MANDATORY_CHANNELS:
        buttons.append([InlineKeyboardButton(f"عضویت در کانال {ch_username}", url=f"https://t.me/{ch_username}")])
    return InlineKeyboardMarkup(buttons)

# ---------- متن‌های ربات (با لحن رسمی) ----------
def get_start_text() -> str:
    channels_str = " و ".join([f"@{ch}" for ch in MANDATORY_CHANNELS])
    return (
        "کاربر گرامی، سلام!\n"
        "به ربات نجوا رسان تیم **RHINOSOUL** خوش آمدید.\n\n"
        f"جهت استفاده از خدمات ربات، لطفا ابتدا در کانال رسمی ما ({channels_str}) عضو شوید و سپس دکمه تایید را لمس نمایید."
    )

INTRO_TEXT = (
    "✅ عضویت شما تایید شد.\n\n"
    "**راهنمای استفاده از ربات نجوا رسان RHINOSOUL:**\n\n"
    "🔹 **روش اول (ریپلای):**\n"
    "در گروه، کلمه‌ی «نجوا» یا «سکرت» را بر روی پیام کاربر مورد نظر خود ریپلای کنید. سپس ربات از شما می‌خواهد که متن پیام را در چت خصوصی برای آن ارسال نمایید.\n\n"
    "🔹 **روش دوم (اینلاین):**\n"
    "در هر چتی، یوزرنیم ربات (`@{BOT_USERNAME}`) را تایپ کرده، یک فاصله بگذارید، متن نجوای خود را بنویسید و در انتها یوزرنیم کاربر یا کاربران مقصد را با @ وارد کنید."
)

# ---------- Command Handlers ----------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر دستور /start."""
    user = update.effective_user
    if update.effective_chat.type != ChatType.PRIVATE:
        return

    is_new_user = not await pool.fetchval("SELECT 1 FROM users WHERE user_id=$1;", user.id)
    await upsert_user(user)

    if is_new_user:
        report = (
            f"👤 **کاربر جدیدی ربات را آغاز کرد**\n\n"
            f"**نام:** {mention_html(user.id, user.first_name)}\n"
            f"**یوزرنیم:** @{user.username or 'تعیین نشده'}\n"
            f"**شناسه:** `{user.id}`"
        )
        await report_to_admins(context, report)

    if await is_member_of_channels(context, user.id):
        await update.message.reply_text(
            INTRO_TEXT.format(BOT_USERNAME=BOT_USERNAME),
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(get_start_text(), reply_markup=get_join_channels_markup())

async def anonymous_whisper_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """آغاز فرآیند ارسال نجوای ناشناس با دستور /nashenas."""
    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not msg.reply_to_message:
        warn = await msg.reply_text("خطا: برای ارسال نجوای ناشناس، باید این دستور را روی پیام کاربر هدف ریپلای نمایید.")
        schedule_delete(context, chat.id, warn.message_id, 20)
        return

    target = msg.reply_to_message.from_user
    if target.is_bot or target.id == user.id:
        warn = await msg.reply_text("خطا: ارسال نجوا به ربات یا به خودتان امکان‌پذیر نیست.")
        schedule_delete(context, chat.id, warn.message_id, 20)
        return

    # حذف پیام دستور برای حفظ ناشناسی
    await safe_delete(context.bot, chat.id, msg.message_id)

    if not await is_member_of_channels(context, user.id):
        await msg.reply_text("برای استفاده از این قابلیت، ابتدا باید در کانال‌های معرفی شده عضو شوید.", reply_markup=get_join_channels_markup())
        return

    async with pool.acquire() as con:
        await con.execute(
            "INSERT INTO pending (sender_id, group_id, receiver_id, is_anonymous, created_at, expires_at, reply_to_msg_id) "
            "VALUES ($1, $2, $3, TRUE, NOW(), $4, $5) ON CONFLICT (sender_id) DO UPDATE SET "
            "group_id=EXCLUDED.group_id, receiver_id=EXCLUDED.receiver_id, is_anonymous=TRUE, created_at=NOW(), "
            "expires_at=$4, reply_to_msg_id=$5;",
            user.id, chat.id, target.id, FAR_FUTURE, msg.reply_to_message.message_id
        )

    try:
        target_name = sanitize(target.first_name)
        await context.bot.send_message(
            user.id,
            f"🔹 شما در حال ارسال یک نجوای **ناشناس** به کاربر **{target_name}** هستید.\n\n"
            f"لطفا متن پیام خود را ارسال فرمایید. هویت شما برای گیرنده فاش نخواهد شد.",
            parse_mode=ParseMode.HTML
        )
    except Forbidden:
        warn_text = f"{mention_html(user.id, user.first_name)}، برای ارسال متن نجوا، لطفا ابتدا ربات را در چت خصوصی خود استارت نمایید."
        warn_msg = await msg.reply_text(warn_text, parse_mode=ParseMode.HTML)
        schedule_delete(context, chat.id, warn_msg.message_id, 45)

async def admin_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر دستورات ویژه ادمین."""
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        return

    command = update.message.text.split()[0]

    if command == "/stats":
        async with pool.acquire() as con:
            users_count = await con.fetchval("SELECT COUNT(*) FROM users;")
            active_groups = await con.fetchval("SELECT COUNT(*) FROM chats WHERE type IN ('group','supergroup') AND is_active=TRUE;")
            whispers_count = await con.fetchval("SELECT COUNT(*) FROM whispers;")
            gwhispers_count = await con.fetchval("SELECT COUNT(*) FROM group_whispers;")
        stats_text = (
            f"📊 **آمار عملکرد ربات RHINOSOUL**\n\n"
            f"👤 **تعداد کاربران:** {users_count}\n"
            f"- **تعداد گروه‌های فعال:** {active_groups} / {MAX_GROUPS}\n"
            f"- **مجموع نجواهای فردی:** {whispers_count}\n"
            f"- **مجموع نجواهای گروهی:** {gwhispers_count}"
        )
        await update.message.reply_text(stats_text, parse_mode=ParseMode.HTML)

    elif command == "/list_groups":
        await update.message.reply_text("درحال تهیه لیست گروه‌های فعال...")
        async with pool.acquire() as con:
            rows = await con.fetch("SELECT chat_id, title FROM chats WHERE type IN ('group','supergroup') AND is_active=TRUE ORDER BY title;")
        
        lines = []
        for i, row in enumerate(rows, 1):
            gid = int(row["chat_id"])
            title = sanitize(row["title"])
            link_str = ""
            try:
                invite_link = await context.bot.export_chat_invite_link(gid)
                link_str = f" - <a href='{invite_link}'>ورود</a>"
            except Exception:
                pass
            lines.append(f"{i}. <b>{title}</b> (<code>{gid}</code>){link_str}")

        if not lines:
            await update.message.reply_text("هیچ گروه فعالی یافت نشد.")
            return

        # ارسال لیست در بسته‌های 20 تایی
        for j in range(0, len(lines), 20):
            chunk = lines[j:j + 20]
            await update.message.reply_text("\n".join(chunk), parse_mode=ParseMode.HTML, disable_web_page_preview=True)

    # افزودن دستورات ارسال همگانی
    elif command in ["/send_to_users", "/send_to_groups"]:
        try:
            body = update.message.text.split(' ', 1)[1]
            context.user_data['broadcast_body'] = body
            context.user_data['broadcast_mode'] = 'users' if command == '/send_to_users' else 'groups'
            await update.message.reply_text(
                f"⚠️ **تایید ارسال همگانی** ⚠️\n\n"
                f"شما در حال ارسال پیام زیر به **{'تمام کاربران' if context.user_data['broadcast_mode'] == 'users' else 'تمام گروه‌ها'}** هستید:\n\n"
                f"{body}\n\n"
                f"آیا تایید می‌کنید؟",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("✅ بله، ارسال کن", callback_data="confirm_broadcast"),
                    InlineKeyboardButton("❌ خیر، لغو", callback_data="cancel_broadcast")
                ]])
            )
        except IndexError:
            await update.message.reply_text(f"خطا: لطفا متن پیام را بعد از دستور وارد کنید.\nمثال: `{command} سلام به همه`")

# ---------- حالت اینلاین (Inline Mode) ----------

def _preview(s: str, n: int = 50) -> str:
    """خلاصه‌سازی متن برای پیش‌نمایش."""
    return s if len(s) <= n else (s[:n-1] + "…")

async def on_inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر اصلی برای درخواست‌های اینلاین."""
    iq = update.inline_query
    query = (iq.query or "").strip()
    user = iq.from_user
    results = []

    # استخراج یوزرنیم‌ها از متن کوئری
    usernames = sorted(list(set(re.findall(r"@([a-zA-Z0-9_]{5,})", query))))
    text = re.sub(r"\s*@([a-zA-Z0-9_]{5,})", "", query).strip()

    if not text:
        results.append(InlineQueryResultArticle(
            id="help",
            title="راهنمای استفاده از حالت اینلاین",
            description="ابتدا متن نجوا و سپس یوزرنیم مقصد را وارد کنید.",
            input_message_content=InputTextMessageContent(
                "🔹 **راهنمای اینلاین ربات RHINOSOUL** 🔹\n\n"
                "برای ارسال نجوا، ابتدا متن پیام خود را تایپ کرده و سپس یوزرنیم کاربر یا کاربران مورد نظر را با @ وارد نمایید.\n\n"
                "مثال نجوا فردی: `سلام خوبی؟ @user1`\n"
                "مثال نجوای گروهی: `جلسه فردا ساعت ۱۰ @user1 @user2 @user3`"
            , parse_mode=ParseMode.MARKDOWN)
        ))
        await iq.answer(results, cache_time=5)
        return

    # --- حالت نجوای فردی ---
    if len(usernames) == 1:
        uname = usernames[0]
        token = token_urlsafe(12)
        
        async with pool.acquire() as con:
            await con.execute(
                "INSERT INTO whispers (sender_id, receiver_user_name, text, inline_token) VALUES ($1, $2, $3, $4);",
                user.id, uname.lower(), text, token
            )

        # گزینه ۱: نجوای عادی
        results.append(InlineQueryResultArticle(
            id=f"single_normal:{token}",
            title=f"ارسال نجوا به @{uname}",
            description=_preview(text),
            input_message_content=InputTextMessageContent(f"🔒 یک پیام خصوصی برای @{uname} ارسال شد."),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👁️‍🗨️ نمایش پیام", callback_data=f"iws_s:{token}")]]),
        ))
        # گزینه ۲: نجوای مخفی (بدون نمایش نام گیرنده)
        results.append(InlineQueryResultArticle(
            id=f"single_hidden:{token}",
            title="ارسال به صورت مخفی (بدون نام)",
            description="در این حالت، نام گیرنده در پیام نمایش داده نمی‌شود.",
            input_message_content=InputTextMessageContent("🔒 یک پیام خصوصی برای شما ارسال شده است."),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👁️‍🗨️ نمایش پیام", callback_data=f"iws_s:{token}")]]),
        ))
    
    # --- حالت نجوای گروهی ---
    elif len(usernames) > 1:
        token = token_urlsafe(16)
        
        async with pool.acquire() as con:
            whisper_id = await con.fetchval(
                "INSERT INTO group_whispers (sender_id, text, inline_token) VALUES ($1, $2, $3) RETURNING id;",
                user.id, text, token
            )
            # افزودن گیرندگان به جدول دیگر
            recipient_data = [(whisper_id, uname.lower()) for uname in usernames]
            await con.copy_records_to_table('group_whisper_recipients', records=recipient_data, columns=['whisper_id', 'receiver_username'])

        recipient_list_str = ", ".join([f"@{u}" for u in usernames])
        results.append(InlineQueryResultArticle(
            id=f"group:{token}",
            title=f"ارسال نجوای گروهی به {len(usernames)} نفر",
            description=f"گیرندگان: {recipient_list_str}",
            input_message_content=InputTextMessageContent(
                f"🔒 یک نجوای گروهی برای کاربران زیر ارسال شد:\n{recipient_list_str}"
            ),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👁️‍🗨️ نمایش پیام گروهی", callback_data=f"iws_g:{token}")]]),
        ))

    await iq.answer(results, cache_time=0, is_personal=True)


async def on_chosen_inline_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ذخیره inline_message_id پس از انتخاب نتیجه اینلاین توسط کاربر."""
    result = update.chosen_inline_result
    inline_message_id = result.inline_message_id
    
    try:
        mode, token = result.result_id.split(':', 1)
    except ValueError:
        return

    if not inline_message_id:
        return

    async with pool.acquire() as con:
        if mode in ["single_normal", "single_hidden"]:
            await con.execute(
                "UPDATE whispers SET inline_message_id=$1 WHERE inline_token=$2",
                inline_message_id, token
            )
        elif mode == "group":
            await con.execute(
                "UPDATE group_whispers SET inline_message_id=$1 WHERE inline_token=$2",
                inline_message_id, token
            )

# ---------- منطق اصلی نجوا (ریپلای و خصوصی) ----------

async def group_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر تشخیص کلمات کلیدی (نجوا، سکرت) در گروه."""
    msg = update.effective_message
    if not msg or not msg.text: return

    text = msg.text.strip().lower()
    if text not in TRIGGERS: return

    if not msg.reply_to_message:
        warn = await msg.reply_text("راهنما: برای ارسال نجوا، باید کلمه «نجوا» را روی پیام کاربر مورد نظر ریپلای کنید.")
        schedule_delete(context, msg.chat.id, warn.message_id, 20)
        return

    user = update.effective_user
    target = msg.reply_to_message.from_user
    chat = update.effective_chat

    if target.is_bot or target.id == user.id:
        warn = await msg.reply_text("خطا: امکان ارسال نجوا به ربات یا به خودتان وجود ندارد.")
        schedule_delete(context, chat.id, warn.message_id, 20)
        return

    if not await is_member_of_channels(context, user.id):
        await msg.reply_text("برای استفاده از ربات، ابتدا باید در کانال‌های معرفی شده عضو شوید.", reply_markup=get_join_channels_markup())
        return

    # ایجاد یک درخواست pending برای کاربر
    async with pool.acquire() as con:
        await con.execute(
            "INSERT INTO pending (sender_id, group_id, receiver_id, is_anonymous, created_at, expires_at, reply_to_msg_id) "
            "VALUES ($1, $2, $3, FALSE, NOW(), $4, $5) ON CONFLICT (sender_id) DO UPDATE SET "
            "group_id=EXCLUDED.group_id, receiver_id=EXCLUDED.receiver_id, is_anonymous=FALSE, created_at=NOW(), "
            "expires_at=$4, reply_to_msg_id=$5;",
            user.id, chat.id, target.id, FAR_FUTURE, msg.reply_to_message.message_id
        )

    try:
        await context.bot.send_message(
            user.id,
            f"🔹 شما در حال ارسال نجوا به کاربر **{sanitize(target.first_name)}** در گروه **{sanitize(chat.title)}** هستید.\n"
            "لطفا متن پیام خود را ارسال فرمایید.",
            parse_mode=ParseMode.HTML
        )
        guide = await msg.reply_text(
            f"{mention_html(user.id, user.first_name)}، لطفا جهت ارسال متن نجوا به چت خصوصی ربات مراجعه فرمایید.",
            parse_mode=ParseMode.HTML
        )
        schedule_delete(context, chat.id, guide.message_id, GUIDE_DELETE_AFTER_SEC)

    except Forbidden:
        warn_text = f"{mention_html(user.id, user.first_name)}، برای ارسال متن نجوا، لطفا ابتدا ربات را در چت خصوصی خود استارت نمایید."
        warn_msg = await msg.reply_text(warn_text, parse_mode=ParseMode.HTML)
        schedule_delete(context, chat.id, warn_msg.message_id, 45)

async def private_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر دریافت متن نجوا در چت خصوصی."""
    user = update.effective_user
    text = update.message.text
    if not text:
        await update.message.reply_text("خطا: لطفا فقط پیام متنی ارسال فرمایید.")
        return

    async with pool.acquire() as con:
        pending_row = await con.fetchrow("SELECT * FROM pending WHERE sender_id=$1 AND expires_at > NOW();", user.id)

    if not pending_row:
        await update.message.reply_text("در حال حاضر درخواست نجوای فعالی برای شما ثبت نشده است.")
        return

    # حذف درخواست از جدول pending
    await pool.execute("DELETE FROM pending WHERE sender_id=$1;", user.id)

    # اطلاعات نجوا
    group_id = pending_row['group_id']
    receiver_id = pending_row['receiver_id']
    is_anonymous = pending_row['is_anonymous']
    
    # ذخیره نجوا در دیتابیس و دریافت ID
    whisper_id = await pool.fetchval(
        "INSERT INTO whispers (group_id, sender_id, receiver_id, text, is_anonymous) VALUES ($1, $2, $3, $4, $5) RETURNING id;",
        group_id, user.id, receiver_id, text, is_anonymous
    )

    sender_name = await get_name_for(user.id)
    receiver_name = await get_name_for(receiver_id)

    if is_anonymous:
        notify_text = f"{mention_html(receiver_id, receiver_name)}، شما یک پیام **ناشناس** دریافت کرده‌اید!"
    else:
        notify_text = f"{mention_html(receiver_id, receiver_name)}، شما یک پیام خصوصی از طرف {mention_html(user.id, sender_name)} دریافت کرده‌اید."
    
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("👁️‍🗨️ نمایش پیام", callback_data=f"show:{whisper_id}")]])
    
    # ارسال پیام به گروه (بدون ریپلای)
    sent_message = await context.bot.send_message(
        chat_id=group_id,
        text=notify_text,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard
    )
    
    # ذخیره message_id برای قابلیت ادیت
    await pool.execute("UPDATE whispers SET message_id=$1 WHERE id=$2;", sent_message.message_id, whisper_id)
    
    await update.message.reply_text("پیام شما با موفقیت ارسال گردید. (تیم RHINOSOUL)")

    # ارسال گزارش به ادمین‌ها
    group_title = (await context.bot.get_chat(group_id)).title
    report = (
        f"📥 **گزارش نجوای جدید**\n\n"
        f"**نوع:** {'ناشناس' if is_anonymous else 'ریپلای'}\n"
        f"**گروه:** {sanitize(group_title)} (`{group_id}`)\n"
        f"**فرستنده:** {mention_html(user.id, sender_name)}\n"
        f"**گیرنده:** {mention_html(receiver_id, receiver_name)}\n\n"
        f"**متن پیام:**\n`{text}`"
    )
    await report_to_admins(context, report)

# ---------- Callback Query Handlers (منطق دکمه‌ها) ----------

async def show_whisper_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر اصلی نمایش نجوا (فردی و اینلاین) و مدیریت دکمه‌ها."""
    cq = update.callback_query
    user = update.effective_user
    
    try:
        # پشتیبانی از فرمت‌های مختلف callback_data
        prefix, data = cq.data.split(':', 1)
        if prefix in ['show', 'reshow', 'reply', 'rewhip']:
            whisper_id = int(data)
            w = await pool.fetchrow("SELECT * FROM whispers WHERE id = $1;", whisper_id)
        # elif prefix in ['iws_s']: # Inline Single Whisper
        #     token = data
        #     w = await pool.fetchrow("SELECT * FROM whispers WHERE inline_token = $1;", token)
        else:
            await cq.answer("خطای داخلی: فرمت دکمه نامعتبر است.", show_alert=True)
            return
    except (ValueError, IndexError):
        await cq.answer("خطا در پردازش درخواست.", show_alert=True)
        return

    if not w:
        await cq.answer("این نجوا منقضی شده یا نامعتبر است.", show_alert=True)
        try:
            # اگر پیام هنوز دکمه دارد، آن را پاک می‌کنیم
            await cq.edit_message_text("این نجوا دیگر در دسترس نیست.")
        except:
            pass
        return

    sender_id = int(w["sender_id"])
    receiver_id = int(w["receiver_id"])
    is_admin = user.id in ADMIN_IDS

    # --- بررسی دسترسی (امنیت دکمه‌ها) ---
    if not (user.id == sender_id or user.id == receiver_id or is_admin):
        await cq.answer("⛔️ این پیام برای شما ارسال نشده است.", show_alert=True)
        return

    # --- مدیریت اکشن‌های مختلف بر اساس دکمه فشرده شده ---

    # 1. نمایش پیام
    if prefix in ['show', 'reshow', 'iws_s']:
        await cq.answer(w['text'], show_alert=True)
        
        # اگر گیرنده برای اولین بار پیام را می‌خواند، پیام را ادیت کن
        if prefix == 'show' and user.id == receiver_id and w['status'] == 'sent':
            await pool.execute("UPDATE whispers SET status='read' WHERE id=$1;", w['id'])
            
            buttons = [
                InlineKeyboardButton("💬 پاسخ", callback_data=f"reply:{w['id']}"),
                InlineKeyboardButton("🔁 ارسال مجدد", callback_data=f"rewhip:{w['id']}"),
                InlineKeyboardButton("👁️‍🗨️ نمایش مجدد", callback_data=f"reshow:{w['id']}")
            ]
            keyboard = InlineKeyboardMarkup([buttons])

            read_text = "✅ این پیام خصوصی توسط گیرنده مطالعه شد."
            if w['is_anonymous']:
                read_text = "✅ پیام ناشناس توسط گیرنده مطالعه شد."

            try:
                if w['message_id']: # نجوا از نوع ریپلای
                    await cq.edit_message_text(read_text, reply_markup=keyboard)
                # elif w['inline_message_id']: # نجوا از نوع اینلاین
                #     await context.bot.edit_message_text(read_text, inline_message_id=w['inline_message_id'], reply_markup=keyboard)
            except Exception as e:
                print(f"Failed to edit message after read: {e}")

    # 2. پاسخ به نجوا
    elif prefix == 'reply':
        if user.id != receiver_id:
            await cq.answer("فقط گیرنده اصلی پیام می‌تواند به آن پاسخ دهد.", show_alert=True)
            return
        
        # ایجاد درخواست pending برای پاسخ
        await pool.execute(
            "INSERT INTO pending (sender_id, group_id, receiver_id, is_anonymous, created_at, expires_at) "
            "VALUES ($1, $2, $3, FALSE, NOW(), $4) ON CONFLICT (sender_id) DO UPDATE SET "
            "group_id=EXCLUDED.group_id, receiver_id=EXCLUDED.receiver_id, is_anonymous=FALSE, created_at=NOW(), expires_at=$4;",
            user.id, w['group_id'], sender_id, FAR_FUTURE
        )
        sender_name = await get_name_for(sender_id)
        await context.bot.send_message(user.id, f"🔹 در حال پاسخ به نجوای کاربر **{sender_name}**...\nلطفا متن پاسخ خود را ارسال فرمایید.", parse_mode=ParseMode.HTML)
        await cq.answer("به چت خصوصی ربات مراجعه کنید.", show_alert=False)

    # 3. ارسال مجدد نجوا
    elif prefix == 'rewhip':
        if user.id != sender_id:
            await cq.answer("فقط فرستنده اصلی پیام می‌تواند آن را مجددا ارسال کند.", show_alert=True)
            return

        await pool.execute(
            "INSERT INTO pending (sender_id, group_id, receiver_id, is_anonymous, created_at, expires_at) "
            "VALUES ($1, $2, $3, $4, NOW(), $5) ON CONFLICT (sender_id) DO UPDATE SET "
            "group_id=EXCLUDED.group_id, receiver_id=EXCLUDED.receiver_id, is_anonymous=$4, created_at=NOW(), expires_at=$5;",
            user.id, w['group_id'], receiver_id, w['is_anonymous'], FAR_FUTURE
        )
        receiver_name = await get_name_for(receiver_id)
        await context.bot.send_message(user.id, f"🔹 در حال ارسال مجدد نجوا به کاربر **{receiver_name}**...\nلطفا متن جدید را ارسال فرمایید.", parse_mode=ParseMode.HTML)
        await cq.answer("به چت خصوصی ربات مراجعه کنید.", show_alert=False)

async def show_group_whisper_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر نمایش و مدیریت نجوای گروهی."""
    # ... (این تابع به دلیل پیچیدگی بالا در مرحله بعد اضافه خواهد شد)
    # در حال حاضر یک پیام موقت نمایش می‌دهد
    await update.callback_query.answer("قابلیت نجوای گروهی در به‌روزرسانی بعدی فعال خواهد شد.", show_alert=True)

# ... (سایر هندلرهای callback مانند تایید عضویت و ارسال همگانی)

# ---------- هندلرهای سیستمی و متفرقه ----------

async def on_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """گزارش‌گیری هنگام افزودن یا حذف ربات از یک گروه."""
    my_member = update.my_chat_member
    chat = my_member.chat
    user = my_member.from_user

    if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    old_status = my_member.old_chat_member.status
    new_status = my_member.new_chat_member.status
    
    # ربات از گروه حذف شده است
    if new_status in ['left', 'kicked']:
        await upsert_chat(chat, active=False)
        report = (
            f"❌ **ربات از یک گروه حذف شد**\n\n"
            f"**گروه:** {sanitize(chat.title)} (`{chat.id}`)\n"
            f"**توسط:** {mention_html(user.id, user.first_name)}"
        )
        await report_to_admins(context, report)
    
    # ربات به گروه اضافه شده است
    elif old_status in ['left', 'kicked'] and new_status in ['member', 'administrator']:
        active_count = await pool.fetchval("SELECT COUNT(*) FROM chats WHERE is_active=TRUE AND type IN ('group','supergroup');")
        if active_count >= MAX_GROUPS:
            await context.bot.send_message(chat.id, f"ظرفیت پذیرش گروه‌ها برای این ربات تکمیل شده است. لطفا با پشتیبانی (@{SUPPORT_CONTACT}) تماس بگیرید.")
            await context.bot.leave_chat(chat.id)
            return

        await upsert_chat(chat, active=True)
        member_count = await context.bot.get_chat_member_count(chat.id)
        report = (
            f"✅ **ربات به گروه جدیدی افزوده شد**\n\n"
            f"**گروه:** {sanitize(chat.title)} (`{chat.id}`)\n"
            f"**تعداد اعضا:** {member_count}\n"
            f"**توسط:** {mention_html(user.id, user.first_name)}"
        )
        await report_to_admins(context, report)

async def on_check_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر دکمه تایید عضویت."""
    cq = update.callback_query
    user = cq.from_user

    if await is_member_of_channels(context, user.id):
        await cq.answer("عضویت شما با موفقیت تایید شد.", show_alert=False)
        await cq.edit_message_text(
            INTRO_TEXT.format(BOT_USERNAME=BOT_USERNAME),
            parse_mode=ParseMode.HTML
        )
    else:
        await cq.answer("شما هنوز در تمام کانال‌ها عضو نشده‌اید. لطفا مجددا بررسی کنید.", show_alert=True)

# ---------- تابع اصلی اجرای ربات (main) ----------
async def post_init(application: Application):
    """کارهایی که باید پس از راه‌اندازی اولیه ربات انجام شود."""
    await init_db()
    me = await application.bot.get_me()
    global BOT_USERNAME
    BOT_USERNAME = me.username
    print(f"Bot @{BOT_USERNAME} started successfully.")

def main():
    """راه‌اندازی و اجرای ربات."""
    if not all([BOT_TOKEN, DATABASE_URL, ADMIN_IDS]):
        raise SystemExit("خطای حیاتی: متغیرهای BOT_TOKEN, DATABASE_URL, ADMIN_IDS به درستی تنظیم نشده‌اند.")

    builder = Application.builder().token(BOT_TOKEN)
    application = builder.build()
    application.post_init = post_init

    # ثبت Command Handlers
    application.add_handler(CommandHandler("start", start_command, filters=filters.ChatType.PRIVATE))
    application.add_handler(CommandHandler("nashenas", anonymous_whisper_start, filters=filters.ChatType.GROUPS & filters.REPLY))
    admin_handler = CommandHandler(["stats", "list_groups", "send_to_users", "send_to_groups"], admin_commands, filters=filters.ChatType.PRIVATE)
    application.add_handler(admin_handler)

    # ثبت Callback Query Handlers (دکمه‌ها)
    application.add_handler(CallbackQueryHandler(on_check_join, pattern="^check_join$"))
    # application.add_handler(CallbackQueryHandler(confirm_broadcast_handler, pattern="^confirm_broadcast$"))
    # application.add_handler(CallbackQueryHandler(cancel_broadcast_handler, pattern="^cancel_broadcast$"))
    application.add_handler(CallbackQueryHandler(show_whisper_handler, pattern=r"^(show|reshow|reply|rewhip|iws_s):"))
    application.add_handler(CallbackQueryHandler(show_group_whisper_handler, pattern=r"^(iws_g|gwh_reshow|gwh_rewhip):"))

    # ثبت Message Handlers
    application.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.TEXT & (~filters.COMMAND), group_trigger))
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & (~filters.COMMAND), private_text_handler))

    # ثبت Inline Handlers
    application.add_handler(InlineQueryHandler(on_inline_query))
    application.add_handler(ChosenInlineResultHandler(on_chosen_inline_result))

    # ثبت System Handlers
    application.add_handler(ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))

    print("Bot is running...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
