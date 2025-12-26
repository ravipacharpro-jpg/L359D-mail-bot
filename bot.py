import os
import re
import random
import string
import requests
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

# 🔐 BOT TOKEN (Railway ENV variable)
TOKEN = os.getenv("BOT_TOKEN")

# User data (in-memory; server pe DB later add ho sakta hai)
users = {}

# Temp mail domains
DOMAINS = ["1secmail.com", "1secmail.org", "1secmail.net"]

# ---------- Helpers ----------

def generate_email():
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

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 Inbox", callback_data="inbox")],
        [InlineKeyboardButton("🔁 New Email", callback_data="new")],
        [InlineKeyboardButton("🗑 Clear Inbox", callback_data="clear")]
    ])

# ---------- Handlers ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    login, domain, email = generate_email()
    users[update.effective_user.id] = {
        "login": login,
        "domain": domain,
        "email": email
    }

    await update.message.reply_text(
        f"📧 *Your Temporary Email*\n\n"
        f"`{email}`\n\n"
        "Use this email for verification.\n"
        "Inbox yahin milega 👇",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    if uid not in users:
        await q.edit_message_text("❌ Please use /start first")
        return

    user = users[uid]

    if q.data == "new":
        login, domain, email = generate_email()
        users[uid] = {"login": login, "domain": domain, "email": email}
        await q.edit_message_text(
            f"🔁 *New Email Generated*\n\n`{email}`",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )

    elif q.data == "clear":
        await q.edit_message_text(
            "🗑 *Inbox cleared*\n\n"
            "(Temporary inbox provider auto-expires mails)",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )

    elif q.data == "inbox":
        msgs = get_messages(user["login"], user["domain"])
        if not msgs:
            await q.edit_message_text(
                "📭 *Inbox empty*",
                parse_mode="Markdown",
                reply_markup=main_keyboard()
            )
            return

        text = "📥 *Inbox Messages*\n\n"
        for m in msgs:
            mail = read_message(user["login"], user["domain"], m["id"])
            body = (mail.get("textBody") or "") + "\n" + (mail.get("htmlBody") or "")
            otp = extract_otp(body)

            text += f"📩 *From:* {m['from']}\n"
            text += f"*Subject:* {m['subject']}\n"
            if otp:
                text += f"🔐 *OTP:* `{otp}`\n"
            text += "──────────────\n"

        await q.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )

# ---------- App ----------

def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN env variable not set")

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_buttons))

    print("🔥 L359D Mail Bot Running...")
    app.run_polling()

if __name__ == "__main__":
    main()

