import os
import re
import random
import string
import asyncio
import requests
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ================= CONFIG =================

TOKEN = os.getenv("BOT_TOKEN")  # Railway env variable
ADMIN_ID = 1969067694           # tumhara Telegram ID

DOMAINS = ["1secmail.com", "1secmail.net", "1secmail.org"]

FREE_EMAIL_LIMIT = 3
CHECK_INTERVAL_FREE = 25
CHECK_INTERVAL_PREMIUM = 10

# ================= STORAGE (RAM) =================

users = {}            # uid -> {login, domain, count}
seen_msgs = {}        # uid -> set(msg_ids)
premium_users = set()
banned_users = set()

# ================= HELPERS =================

def gen_email():
    login = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    domain = random.choice(DOMAINS)
    return login, domain, f"{login}@{domain}"

def extract_otp(text):
    m = re.search(r"\b\d{4,8}\b", text)
    return m.group() if m else None

def get_messages(login, domain):
    url = "https://www.1secmail.com/api/v1/"
    return requests.get(
        url,
        params={
            "action": "getMessages",
            "login": login,
            "domain": domain
        },
        timeout=10
    ).json()

def read_message(login, domain, msg_id):
    url = "https://www.1secmail.com/api/v1/"
    return requests.get(
        url,
        params={
            "action": "readMessage",
            "login": login,
            "domain": domain,
            "id": msg_id
        },
        timeout=10
    ).json()

def keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 Inbox", callback_data="inbox")],
        [InlineKeyboardButton("🔁 New Email", callback_data="new")],
        [InlineKeyboardButton("🗑 Clear Inbox", callback_data="clear")],
    ])

# ================= USER COMMANDS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if uid in banned_users:
        return

    data = users.get(uid, {"count": 0})

    if uid not in premium_users and data["count"] >= FREE_EMAIL_LIMIT:
        await update.message.reply_text(
            "⚠️ Free limit reached.\nUpgrade to PREMIUM 👑"
        )
        return

    login, domain, email = gen_email()
    users[uid] = {
        "login": login,
        "domain": domain,
        "count": data["count"] + 1
    }
    seen_msgs[uid] = set()

    await update.message.reply_text(
        f"📧 *Your Temporary Email*\n\n`{email}`\n\n"
        "Use this email for verification.\n"
        "Inbox yahin milega 👇",
        reply_markup=keyboard(),
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    if uid not in users:
        await query.message.reply_text("❗ First use /start")
        return

    login = users[uid]["login"]
    domain = users[uid]["domain"]

    if query.data == "new":
        login, domain, email = gen_email()
        users[uid]["login"] = login
        users[uid]["domain"] = domain
        users[uid]["count"] += 1
        seen_msgs[uid] = set()

        await query.message.reply_text(
            f"🔄 *New Email Generated*\n\n`{email}`",
            parse_mode="Markdown",
            reply_markup=keyboard()
        )

    elif query.data == "clear":
        seen_msgs[uid] = set()
        await query.message.reply_text("🗑 Inbox cleared.")

    elif query.data == "inbox":
        msgs = get_messages(login, domain)
        if not msgs:
            await query.message.reply_text("📭 Inbox empty.")
            return

        for msg in msgs:
            mid = msg["id"]
            if mid in seen_msgs[uid]:
                continue

            full = read_message(login, domain, mid)
            text = f"📩 *New Mail*\n\nFrom: {full['from']}\n\n{full['textBody']}"
            otp = extract_otp(full.get("textBody", ""))

            if otp:
                text += f"\n\n🔐 *OTP Detected:* `{otp}`"

            await query.message.reply_text(text, parse_mode="Markdown")
            seen_msgs[uid].add(mid)

# ================= ADMIN COMMANDS =================

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized")
        return

    await update.message.reply_text(
        "👑 *ADMIN PANEL*\n\n"
        "/stats – Bot stats\n"
        "/premium <id> – Add premium\n"
        "/remove <id> – Remove premium\n"
        "/ban <id> – Ban user\n"
        "/broadcast <msg> – Broadcast",
        parse_mode="Markdown"
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
        f"📊 *Stats*\n\n"
        f"Users: {len(users)}\n"
        f"Premium: {len(premium_users)}\n"
        f"Banned: {len(banned_users)}",
        parse_mode="Markdown"
    )

async def premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    uid = int(context.args[0])
    premium_users.add(uid)
    await update.message.reply_text(f"✅ {uid} is now PREMIUM")

async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    uid = int(context.args[0])
    premium_users.discard(uid)
    await update.message.reply_text(f"❌ Premium removed from {uid}")

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    uid = int(context.args[0])
    banned_users.add(uid)
    await update.message.reply_text(f"🚫 User {uid} banned")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    msg = " ".join(context.args)
    for uid in users:
        try:
            await context.bot.send_message(uid, msg)
        except:
            pass
    await update.message.reply_text("📢 Broadcast sent")

# ================= MAIN =================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("premium", premium))
    app.add_handler(CommandHandler("remove", remove))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("broadcast", broadcast))

    app.add_handler(CallbackQueryHandler(button_handler))

    print("🤖 Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()

