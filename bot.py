import os, re, random, string, requests, asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ================= CONFIG =================

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 1969067694   # ✅ YOUR ID

DOMAINS = ["1secmail.com", "1secmail.org", "1secmail.net"]
FREE_EMAIL_LIMIT = 3

# ================= STORAGE =================

users = {}
seen_msgs = {}
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

def get_msgs(login, domain):
    return requests.get(
        f"https://www.1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}",
        timeout=10
    ).json()

def read_msg(login, domain, mid):
    return requests.get(
        f"https://www.1secmail.com/api/v1/?action=readMessage&login={login}&domain={domain}&id={mid}",
        timeout=10
    ).json()

def keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 Inbox", callback_data="inbox")],
        [InlineKeyboardButton("🔁 New Email", callback_data="new")],
        [InlineKeyboardButton("🗑 Clear Inbox", callback_data="clear")]
    ])

# ================= USER =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if uid in banned_users:
        return

    data = users.get(uid, {"count": 0})
    if uid not in premium_users and data["count"] >= FREE_EMAIL_LIMIT:
        await update.message.reply_text("⚠️ Free limit reached.")
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
        f"📧 Your Temporary Email\n\n{email}\n\nInbox yahin milega 👇",
        reply_markup=keyboard()
    )

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    if uid not in users:
        return

    user = users[uid]

    if q.data == "new":
        await start(update, context)

    elif q.data == "clear":
        seen_msgs[uid] = set()
        await q.edit_message_text("🗑 Inbox cleared", reply_markup=keyboard())

    elif q.data == "inbox":
        msgs = get_msgs(user["login"], user["domain"])
        if not msgs:
            await q.edit_message_text("📭 Inbox empty", reply_markup=keyboard())
            return

        txt = "📥 Inbox\n\n"
        for m in msgs:
            mail = read_msg(user["login"], user["domain"], m["id"])
            body = (mail.get("textBody") or "") + (mail.get("htmlBody") or "")
            otp = extract_otp(body)
            txt += f"From: {m['from']}\nSub: {m['subject']}\n"
            if otp:
                txt += f"OTP: {otp}\n"
            txt += "--------\n"

        await q.edit_message_text(txt, reply_markup=keyboard())

# ================= ADMIN (FIXED) =================

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != ADMIN_ID:
        await update.message.reply_text("❌ You are not admin")
        return

    # ✅ PLAIN TEXT (NO MARKDOWN) — GUARANTEED
    await update.message.reply_text(
        "👑 ADMIN PANEL\n\n"
        "/stats\n"
        "/premium <user_id>\n"
        "/remove <user_id>\n"
        "/ban <user_id>\n"
        "/broadcast <message>"
    )

async def stats(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(
        f"Users: {len(users)}\n"
        f"Premium: {len(premium_users)}\n"
        f"Banned: {len(banned_users)}"
    )

async def premium(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        return
    uid = int(context.args[0])
    premium_users.add(uid)
    await update.message.reply_text(f"{uid} → PREMIUM")

async def remove(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        return
    uid = int(context.args[0])
    premium_users.discard(uid)
    await update.message.reply_text(f"{uid} → REMOVED")

async def ban(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        return
    uid = int(context.args[0])
    banned_users.add(uid)
    await update.message.reply_text(f"{uid} → BANNED")

async def broadcast(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        return
    msg = " ".join(context.args)
    for uid in users:
        try:
            await context.bot.send_message(uid, msg)
        except:
            pass

# ================= MAIN =================

def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN missing")

    app = ApplicationBuilder().token(TOKEN).build()

    # 🔴 ADMIN FIRST (CRITICAL)
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("premium", premium))
    app.add_handler(CommandHandler("remove", remove))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("broadcast", broadcast))

    # 🔵 USER
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))

    print("✅ L359D Mail BOT LIVE (ADMIN FIXED)")
    app.run_polling()

if __name__ == "__main__":
    main()

    if q.data == "new":
        await start(update, context)

    elif q.data == "clear":
        seen_msgs[uid] = set()
        await q.edit_message_text("🗑 Inbox cleared", reply_markup=keyboard())

    elif q.data == "inbox":
        msgs = get_msgs(user["login"], user["domain"])
        if not msgs:
            await q.edit_message_text("📭 Inbox empty", reply_markup=keyboard())
            return

        txt = "📥 *Inbox*\n\n"
        for m in msgs:
            mail = read_msg(user["login"], user["domain"], m["id"])
            body = (mail.get("textBody") or "") + (mail.get("htmlBody") or "")
            otp = extract_otp(body)

            txt += f"📩 *From:* {m['from']}\n"
            txt += f"*Subject:* {m['subject']}\n"
            if otp:
                txt += f"🔐 *OTP:* `{otp}`\n"
            txt += "──────────\n"

        await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=keyboard())

# ================= AUTO NOTIFY =================

async def auto_notify(app):
    while True:
        for uid, user in users.items():
            if uid in banned_users:
                continue

            try:
                msgs = get_msgs(user["login"], user["domain"])
                for m in msgs:
                    if m["id"] in seen_msgs.get(uid, set()):
                        continue

                    mail = read_msg(user["login"], user["domain"], m["id"])
                    body = (mail.get("textBody") or "") + (mail.get("htmlBody") or "")
                    otp = extract_otp(body)

                    msg = (
                        f"📨 *New Mail*\n\n"
                        f"*From:* {m['from']}\n"
                        f"*Subject:* {m['subject']}\n"
                    )
                    if otp:
                        msg += f"\n🔐 *OTP:* `{otp}`"

                    await app.bot.send_message(uid, msg, parse_mode="Markdown")
                    seen_msgs.setdefault(uid, set()).add(m["id"])
            except:
                pass

        await asyncio.sleep(10)

# ================= ADMIN COMMANDS =================

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(
        "👑 *ADMIN PANEL*\n\n"
        "/stats\n"
        "/premium <user_id>\n"
        "/remove <user_id>\n"
        "/ban <user_id>\n"
        "/broadcast <message>",
        parse_mode="Markdown"
    )

async def stats(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(
        f"👥 Users: {len(users)}\n"
        f"👑 Premium: {len(premium_users)}\n"
        f"🚫 Banned: {len(banned_users)}"
    )

async def premium(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        return
    uid = int(context.args[0])
    premium_users.add(uid)
    await update.message.reply_text(f"✅ {uid} is now PREMIUM")

async def remove(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        return
    uid = int(context.args[0])
    premium_users.discard(uid)
    await update.message.reply_text(f"❌ {uid} premium removed")

async def ban(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        return
    uid = int(context.args[0])
    banned_users.add(uid)
    await update.message.reply_text(f"🚫 {uid} banned")

async def broadcast(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        return
    msg = " ".join(context.args)
    for uid in users:
        try:
            await context.bot.send_message(uid, msg)
        except:
            pass

# ================= MAIN (ADMIN FIXED) =================

def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN not set")

    app = ApplicationBuilder().token(TOKEN).build()

    # 🔴 ADMIN COMMANDS FIRST (IMPORTANT)
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("premium", premium))
    app.add_handler(CommandHandler("remove", remove))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("broadcast", broadcast))

    # 🔵 USER COMMANDS
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))

    # 🔔 AUTO NOTIFY LOOP
    app.job_queue.run_once(lambda _: asyncio.create_task(auto_notify(app)), 1)

    print("🔥 L359D Mail — FULL PREMIUM + ADMIN LIVE")
    app.run_polling()

if __name__ == "__main__":
    main()

