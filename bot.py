import os
import random
import string
import re
import requests
from datetime import datetime
from pymongo import MongoClient
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    CallbackQueryHandler, MessageHandler,
    ContextTypes, filters
)

# ================= CONFIG =================
TOKEN = os.getenv("8559780995:AAF0TRWYgW-ZTgZP2Ky9ljSZahl4BjNy_MY")
MONGO_URI = os.getenv("mongodb+srv://l359d:eWvp2vPVrypCBycz@cluster0.0echb1b.mongodb.net/?appName=Cluster0")

FREE_LIMIT = 3
DOMAINS = ["1secmail.com", "1secmail.org", "1secmail.net"]

# ================= DB =================
client = MongoClient(MONGO_URI)
db = client["tempmail"]
users_col = db["users"]
mails_col = db["mails"]

# ================= HELPERS =================
def gen_login(k=10):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=k))

def gen_unique_email():
    while True:
        login = gen_login()
        domain = random.choice(DOMAINS)
        email = f"{login}@{domain}"
        if not mails_col.find_one({"email": email}):
            return login, domain, email

def extract_otp(text):
    m = re.search(r"\b\d{4,8}\b", text)
    return m.group(0) if m else None

def keyboard(active_id=None):
    btns = [
        [InlineKeyboardButton("📬 Inbox", callback_data="inbox")],
        [InlineKeyboardButton("🔄 New Email", callback_data="new")],
        [InlineKeyboardButton("🧾 My IDs", callback_data="ids")],
    ]
    if active_id:
        btns.append(
            [InlineKeyboardButton("🗑 Delete Active", callback_data=f"del_{active_id}")]
        )
    return InlineKeyboardMarkup(btns)

# ================= 1SECMail API =================
def api_msgs(login, domain):
    return requests.get(
        f"https://www.1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}",
        timeout=10
    ).json()

def api_read(login, domain, mid):
    return requests.get(
        f"https://www.1secmail.com/api/v1/?action=readMessage&login={login}&domain={domain}&id={mid}",
        timeout=10
    ).json()

# ================= COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    users_col.update_one(
        {"uid": uid},
        {"$setOnInsert": {"uid": uid, "count": 0}},
        upsert=True
    )

    await update.message.reply_text(
        "📧 *L359D Fake Mail*\n\n"
        "/generate – New fake mail\n"
        "/id – Your mail list\n\n"
        "Custom mail ke liye direct email bhejo 👇",
        parse_mode="Markdown"
    )

async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = users_col.find_one({"uid": uid})

    if user["count"] >= FREE_LIMIT:
        await update.message.reply_text("❌ Free limit reached.")
        return

    login, domain, email = gen_unique_email()
    mail_id = random.randint(10000000, 99999999)

    mails_col.insert_one({
        "uid": uid,
        "mail_id": mail_id,
        "login": login,
        "domain": domain,
        "email": email,
        "created": datetime.utcnow()
    })

    users_col.update_one(
        {"uid": uid},
        {"$set": {"active_mail": mail_id}, "$inc": {"count": 1}}
    )

    await update.message.reply_text(
        f"📧 *Your Temporary Email*\n\n"
        f"`{email}`\n\n"
        "Use this email for verification.\n"
        "Inbox yahin milega 👇",
        parse_mode="Markdown",
        reply_markup=keyboard(mail_id)
    )

async def my_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    mails = list(mails_col.find({"uid": uid}))

    if not mails:
        await update.message.reply_text(
            "You don't have any fake mail id,\ntry /generate"
        )
        return

    text = "📂 *Here are the list of fake mail ids you have*\n\n"
    for i, m in enumerate(mails, 1):
        text += f"{i}. `{m['email']}` | /delete_{m['mail_id']}\n"

    await update.message.reply_text(text, parse_mode="Markdown")

async def delete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    mail_id = int(update.message.text.split("_")[1])

    mail = mails_col.find_one({"uid": uid, "mail_id": mail_id})
    if not mail:
        await update.message.reply_text("❌ Mail not found.")
        return

    mails_col.delete_one({"uid": uid, "mail_id": mail_id})
    users_col.update_one(
        {"uid": uid, "active_mail": mail_id},
        {"$unset": {"active_mail": ""}}
    )

    await update.message.reply_text(
        f"🗑️ Your fakemail address `{mail['email']}` has been deleted.",
        parse_mode="Markdown"
    )

async def custom_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip().lower()

    if "@" not in text:
        return

    if mails_col.find_one({"email": text}):
        await update.message.reply_text("❌ This email already exists.")
        return

    user = users_col.find_one({"uid": uid})
    if user["count"] >= FREE_LIMIT:
        await update.message.reply_text("❌ Free limit reached.")
        return

    login, domain = text.split("@")
    mail_id = random.randint(10000000, 99999999)

    mails_col.insert_one({
        "uid": uid,
        "mail_id": mail_id,
        "login": login,
        "domain": domain,
        "email": text,
        "created": datetime.utcnow()
    })

    users_col.update_one(
        {"uid": uid},
        {"$set": {"active_mail": mail_id}, "$inc": {"count": 1}}
    )

    await update.message.reply_text(
        f"📧 *Your new fake mail id is*\n\n`{text}`",
        parse_mode="Markdown",
        reply_markup=keyboard(mail_id)
    )

# ================= CALLBACK BUTTONS =================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    user = users_col.find_one({"uid": uid})

    if q.data == "new":
        await generate(q, context)

    elif q.data == "ids":
        await my_ids(q, context)

    elif q.data.startswith("del_"):
        mail_id = int(q.data.split("_")[1])
        mails_col.delete_one({"uid": uid, "mail_id": mail_id})
        await q.edit_message_text("🗑️ Deleted.")

    elif q.data == "inbox":
        mail = mails_col.find_one({"mail_id": user.get("active_mail")})
        if not mail:
            await q.edit_message_text("No active email.")
            return

        msgs = api_msgs(mail["login"], mail["domain"])
        if not msgs:
            await q.edit_message_text("📭 Inbox empty.")
            return

        text = "📬 *Inbox*\n\n"
        for m in msgs:
            full = api_read(mail["login"], mail["domain"], m["id"])
            otp = extract_otp(full.get("textBody", "") + full.get("htmlBody", ""))
            text += f"From: {m['from']}\n"
            if otp:
                text += f"🔑 OTP: `{otp}`\n"
            text += "\n"

        await q.edit_message_text(text, parse_mode="Markdown")

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("generate", generate))
    app.add_handler(CommandHandler("id", my_ids))
    app.add_handler(MessageHandler(filters.Regex("^/delete_"), delete_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, custom_email))
    app.add_handler(CallbackQueryHandler(buttons))

    print("🤖 L359D Fake Mail Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
        {"$set": {"active_mail": mail_id}, "$inc": {"count": 1}}
    )

    await update.message.reply_text(
        f"✅ *Your new fake mail id is*\n`{email}`",
        parse_mode="Markdown",
        reply_markup=keyboard(mail_id)
    )

async def my_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    mails = list(mails_col.find({"uid": uid}))

    if not mails:
        await update.message.reply_text(
            "You don't have any fake mail id,\ntry /generate"
        )
        return

    text = "📂 *Here are the list of fake mail ids you have*\n\n"
    for i, m in enumerate(mails, 1):
        text += f"{i}. `{m['email']}` | /delete_{m['mail_id']}\n"

    await update.message.reply_text(text, parse_mode="Markdown")

async def delete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    mail_id = int(update.message.text.split("_")[1])

    mail = mails_col.find_one({"uid": uid, "mail_id": mail_id})
    if not mail:
        await update.message.reply_text("❌ Mail not found.")
        return

    mails_col.delete_one({"uid": uid, "mail_id": mail_id})
    users_col.update_one(
        {"uid": uid, "active_mail": mail_id},
        {"$unset": {"active_mail": ""}}
    )

    await update.message.reply_text(
        f"🗑️ `{mail['email']}` has been deleted.",
        parse_mode="Markdown"
    )

async def custom_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip().lower()

    if "@" not in text:
        return

    if mails_col.find_one({"email": text}):
        await update.message.reply_text("❌ This email already exists.")
        return

    user = users_col.find_one({"uid": uid})
    if user["count"] >= FREE_LIMIT:
        await update.message.reply_text("❌ Free limit reached.")
        return

    login, domain = text.split("@")
    mail_id = random.randint(10000000, 99999999)

    mails_col.insert_one({
        "uid": uid,
        "mail_id": mail_id,
        "login": login,
        "domain": domain,
        "email": text,
        "created": datetime.utcnow()
    })

    users_col.update_one(
        {"uid": uid},
        {"$set": {"active_mail": mail_id}, "$inc": {"count": 1}}
    )

    await update.message.reply_text(
        f"✅ *Your new fake mail id is*\n`{text}`",
        parse_mode="Markdown",
        reply_markup=keyboard(mail_id)
    )

# ================= CALLBACKS =================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    user = users_col.find_one({"uid": uid})

    if q.data == "new":
        await generate(q, context)

    elif q.data == "ids":
        await my_ids(q, context)

    elif q.data.startswith("del_"):
        mail_id = int(q.data.split("_")[1])
        mails_col.delete_one({"uid": uid, "mail_id": mail_id})
        await q.edit_message_text("🗑️ Deleted.")

    elif q.data == "inbox":
        mail = mails_col.find_one({"mail_id": user.get("active_mail")})
        if not mail:
            await q.edit_message_text("No active email.")
            return

        msgs = api_msgs(mail["login"], mail["domain"])
        if not msgs:
            await q.edit_message_text("📭 Inbox empty.")
            return

        text = "📬 *Inbox*\n\n"
        for m in msgs:
            full = api_read(mail["login"], mail["domain"], m["id"])
            otp = extract_otp(full.get("textBody", "") + full.get("htmlBody", ""))
            text += f"From: {m['from']}\n"
            if otp:
                text += f"🔑 OTP: `{otp}`\n"
            text += "\n"

        await q.edit_message_text(text, parse_mode="Markdown")

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("generate", generate))
    app.add_handler(CommandHandler("id", my_ids))
    app.add_handler(MessageHandler(filters.Regex("^/delete_"), delete_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, custom_email))
    app.add_handler(CallbackQueryHandler(buttons))

    print("🤖 Fake Mail Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()

