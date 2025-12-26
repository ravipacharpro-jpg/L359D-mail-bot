import os
import re
import time
import random
import string
import requests
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

# ================= CONFIG =================

TOKEN = os.getenv("BOT_TOKEN")

DOMAINS = ["1secmail.com", "1secmail.org", "1secmail.net"]
CHECK_INTERVAL = 15            # seconds (auto notify)
MAX_EMAILS_PER_USER = 5        # security limit

# ================= STORAGE =================

users = {}      # user_id -> data
seen_msgs = {}  # user_id -> set(msg_ids)

# ================= HELPERS =================

def gen_email():
    login = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    domain = random.choice(DOMAINS)
    return login, domain, f"{login}@{domain}"

def get_messages(login, domain):
    url = f"https://www.1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}"
    return requests.get(url, timeout=10).json()

def read_message(login, domain, mid):
    url = f"https://www.1secmail.com/api/v1/?action=readMessage&login={login}&domain={domain}&id={mid}"
    return requests.get(url, timeout=10).json()

def extract_otp(text):
    m = re.search(r"\b\d{4,8}\b", text)
    return m.group() if m else None

def keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 Inbox", callback_data="inbox")],
        [InlineKeyboardButton("🔁 New Email", callback_data="new")],
        [InlineKeyboardButton("🗑 Clear Inbox", callback_data="clear")],
    ])

# ================= HANDLERS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    data = users.get(uid, {"count": 0})
    if data["count"] >= MAX_EMAILS_PER_USER:
        await update.message.reply_text(
            "⚠️ Limit reached.\nPlease wait or use existing email."
        )
        return

    login, domain, email = gen_email()
    users[uid] = {
        "login": login,
        "domain": domain,
        "email": email,
        "count": data["count"] + 1
    }
    seen_msgs[uid] = set()

    await update.message.reply_text(
        f"✨ *Welcome to L359D Mail*\n\n"
        f"📧 *Your Temp Email*\n`{email}`\n\n"
        "🔔 Auto notify ON\n"
        "🔐 OTP auto-detect ON\n\n"
        "⚡ Powered by L359D",
        parse_mode="Markdown",
        reply_markup=keyboard()
    )

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    if uid not in users:
        await q.edit_message_text("❌ Use /start first")
        return

    user = users[uid]

    if q.data == "new":
        login, domain, email = gen_email()
        users[uid].update({
            "login": login,
            "domain": domain,
            "email": email
        })
        seen_msgs[uid] = set()

        await q.edit_message_text(
            f"🔁 *New Email*\n\n`{email}`",
            parse_mode="Markdown",
            reply_markup=keyboard()
        )

    elif q.data == "clear":
        seen_msgs[uid] = set()
        await q.edit_message_text(
            "🗑 Inbox cleared\n(Provider side mails auto-expire)",
            reply_markup=keyboard()
        )

    elif q.data == "inbox":
        msgs = get_messages(user["login"], user["domain"])
        if not msgs:
            await q.edit_message_text("📭 Inbox empty", reply_markup=keyboard())
            return

        text = "📥 *Inbox*\n\n"
        for m in msgs:
            mail = read_message(user["login"], user["domain"], m["id"])
            body = (mail.get("textBody") or "") + (mail.get("htmlBody") or "")
            otp = extract_otp(body)

            text += f"📩 *From:* {m['from']}\n"
            text += f"*Subject:* {m['subject']}\n"
            if otp:
                text += f"🔐 *OTP:* `{otp}`\n"
            text += "────────────\n"

        await q.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=keyboard()
        )

# ================= AUTO NOTIFY LOOP =================

async def auto_notify(app):
    while True:
        for uid, user in users.items():
            try:
                msgs = get_messages(user["login"], user["domain"])
                for m in msgs:
                    if m["id"] in seen_msgs.get(uid, set()):
                        continue

                    mail = read_message(user["login"], user["domain"], m["id"])
                    body = (mail.get("textBody") or "") + (mail.get("htmlBody") or "")
                    otp = extract_otp(body)

                    msg = (
                        f"📨 *New Mail Received*\n\n"
                        f"*From:* {m['from']}\n"
                        f"*Subject:* {m['subject']}\n"
                    )
                    if otp:
                        msg += f"\n🔐 *OTP:* `{otp}`"

                    await app.bot.send_message(
                        chat_id=uid,
                        text=msg,
                        parse_mode="Markdown"
                    )

                    seen_msgs.setdefault(uid, set()).add(m["id"])
            except:
                pass

        await asyncio.sleep(CHECK_INTERVAL)

# ================= MAIN =================

def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN not set")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))

    app.job_queue.run_once(lambda _: asyncio.create_task(auto_notify(app)), 1)

    print("🔥 L359D Mail Bot FULL PRO Running...")
    app.run_polling()

if __name__ == "__main__":
    main()

