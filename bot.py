import os, random, string, re, asyncio, requests
from datetime import datetime
from pymongo import MongoClient
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes
)

# ================= CONFIG =================
TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
ADMIN_ID = 1969067694  # <-- tumhari admin ID

DOMAINS = ["1secmail.com", "1secmail.org", "1secmail.net"]
CHECK_INTERVAL_FREE = 25
CHECK_INTERVAL_PREMIUM = 10
FREE_LIMIT = 3

# ================= DB =================
client = MongoClient(MONGO_URI)
db = client["tempmail"]
users_col = db["users"]     # user data
mails_col = db["mails"]     # all generated mails

# ================= HELPERS =================
def gen_login(k=10):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=k))

def gen_email():
    login = gen_login()
    domain = random.choice(DOMAINS)
    return login, domain, f"{login}@{domain}"

def otp_from_text(text):
    m = re.search(r"\b\d{4,8}\b", text)
    return m.group(0) if m else None

def keyboard(active_id=None):
    btns = [
        [InlineKeyboardButton("📬 Inbox", callback_data="inbox")],
        [InlineKeyboardButton("🔄 New Email", callback_data="new")],
        [InlineKeyboardButton("🧾 My IDs", callback_data="ids")],
    ]
    if active_id:
        btns.append([InlineKeyboardButton("🗑️ Delete Active", callback_data=f"del_{active_id}")])
    return InlineKeyboardMarkup(btns)

# ================= API =================
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
    user = users_col.find_one({"uid": uid}) or {
        "uid": uid, "premium": False, "active_mail": None, "count": 0, "banned": False
    }
    if user.get("banned"):
        return

    if not user.get("active_mail"):
        if not user.get("premium") and user.get("count", 0) >= FREE_LIMIT:
            await update.message.reply_text("⚠️ Free limit reached. Upgrade to Premium.")
            return
        login, domain, email = gen_email()
        mail_id = random.randint(10000000, 99999999)
        mails_col.insert_one({
            "uid": uid, "mail_id": mail_id,
            "login": login, "domain": domain,
            "email": email, "created": datetime.utcnow()
        })
        user["active_mail"] = mail_id
        user["count"] = user.get("count", 0) + 1
        users_col.update_one({"uid": uid}, {"$set": user}, upsert=True)

    mail = mails_col.find_one({"mail_id": user["active_mail"]})
    await update.message.reply_text(
        f"📧 *Your Temporary Email*\n`{mail['email']}`\n\nInbox yahin milega 👇",
        parse_mode="Markdown",
        reply_markup=keyboard(user["active_mail"])
    )

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(
        "👑 *ADMIN PANEL*\n\n"
        "/stats – Bot stats\n"
        "/allmails – All generated mails\n"
        "/premium <uid>\n"
        "/remove <uid>\n"
        "/ban <uid>\n"
        "/broadcast <msg>",
        parse_mode="Markdown"
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(
        f"👥 Users: {users_col.count_documents({})}\n"
        f"📧 Mails: {mails_col.count_documents({})}"
    )

async def allmails(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    text = "📧 *ALL MAILS*\n"
    for m in mails_col.find().limit(30):
        text += f"- `{m['email']}` (uid {m['uid']})\n"
    await update.message.reply_text(text, parse_mode="Markdown")

# ================= CALLBACKS =================
async def on_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    user = users_col.find_one({"uid": uid})
    if not user: return

    if q.data == "new":
        if not user.get("premium") and user.get("count", 0) >= FREE_LIMIT:
            await q.edit_message_text("⚠️ Free limit reached.")
            return
        login, domain, email = gen_email()
        mail_id = random.randint(10000000, 99999999)
        mails_col.insert_one({
            "uid": uid, "mail_id": mail_id,
            "login": login, "domain": domain,
            "email": email, "created": datetime.utcnow()
        })
        users_col.update_one(
            {"uid": uid},
            {"$set": {"active_mail": mail_id}, "$inc": {"count": 1}}
        )
        await q.edit_message_text(
            f"📧 *New Email*\n`{email}`",
            parse_mode="Markdown",
            reply_markup=keyboard(mail_id)
        )

    elif q.data == "ids":
        mails = list(mails_col.find({"uid": uid}))
        if not mails:
            await q.edit_message_text("No emails yet.")
            return
        text = "*Your Mail IDs*\n"
        kb = []
        for i, m in enumerate(mails, 1):
            text += f"{i}. `{m['email']}`\n"
            kb.append([
                InlineKeyboardButton("Use", callback_data=f"use_{m['mail_id']}"),
                InlineKeyboardButton("Delete", callback_data=f"del_{m['mail_id']}")
            ])
        await q.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

    elif q.data.startswith("use_"):
        mid = int(q.data.split("_")[1])
        users_col.update_one({"uid": uid}, {"$set": {"active_mail": mid}})
        mail = mails_col.find_one({"mail_id": mid})
        await q.edit_message_text(
            f"✅ Active set to `{mail['email']}`",
            parse_mode="Markdown",
            reply_markup=keyboard(mid)
        )

    elif q.data.startswith("del_"):
        mid = int(q.data.split("_")[1])
        mails_col.delete_one({"uid": uid, "mail_id": mid})
        if user.get("active_mail") == mid:
            users_col.update_one({"uid": uid}, {"$set": {"active_mail": None}})
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
        text = "📬 *Inbox*\n"
        for m in msgs:
            full = api_read(mail["login"], mail["domain"], m["id"])
            otp = otp_from_text(full.get("textBody", "") + full.get("htmlBody", ""))
            text += f"- From: {m['from']}\n"
            if otp: text += f"🔑 OTP: `{otp}`\n"
            text += "\n"
        await q.edit_message_text(text, parse_mode="Markdown")

# ================= MAIN =================
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("admin", admin))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(CommandHandler("allmails", allmails))
app.add_handler(CallbackQueryHandler(on_btn))

app.run_polling()
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

