import os
import re
import logging
import yt_dlp
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    filters,
    ContextTypes,
)

URL_RE = re.compile(r"https?://\S+")

TOKEN = os.environ["8724429514:AAFLWReuzWxSTWMx-zmWGvJb2rhuRrJIwSc"]
OWNER_ID = int(os.environ.get("TELEGRAM_OWNER_ID", "0"))
OWNER_USERNAME = os.environ.get("TELEGRAM_OWNER_USERNAME", "").strip().lstrip("@")
INSTAGRAM_COOKIES_FILE = os.environ.get("INSTAGRAM_COOKIES_FILE", "").strip()

if OWNER_USERNAME:
    OWNER_CONTACT_URL = f"https://t.me/{OWNER_USERNAME}"
elif OWNER_ID:
    OWNER_CONTACT_URL = f"tg://user?id={OWNER_ID}"
else:
    OWNER_CONTACT_URL = "https://t.me/"

FREE_LIMIT = 25
PREMIUM_PRICE_STARS = 50
ALLOWED_HEIGHTS = (240, 360, 480, 720, 1080)
MIN_HEIGHT = 240
MAX_HEIGHT = 1080

TELEGRAM_VERIFY_CHANNELS = [
    {"username": "@Naru62x", "title": "قناة Naru62x", "url": "https://t.me/Naru62x"},
]

TRUST_LINKS = [
    {"title": "بوت Hack696", "url": "https://t.me/Hack696bot"},
    {"title": "تيك توك sou.r31", "url": "https://www.tiktok.com/@sou.r31"},
    {"title": "إنستغرام n.61x1", "url": "https://www.instagram.com/n.61x1"},
]

WELCOME_TEXT = (
    "مرحباً 👋\n"
    "أنا بوت مخصص لمساعدتك في تنزيل فيديوهات بجودة تصل إلى Full HD 🎬\n\n"
    "فقط أرسل الرابط، أو اختر منصة من الأزرار في الأسفل."
)

users = {}
verified_users = set()
premium_users = set()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def is_premium(user_id):
    return user_id == OWNER_ID or user_id in premium_users


def get_user_limit(user_id):
    if is_premium(user_id):
        return 999999
    return users.get(user_id, FREE_LIMIT)


def decrease_limit(user_id):
    if is_premium(user_id):
        return
    current = users.get(user_id, FREE_LIMIT)
    users[user_id] = current - 1


def main_menu_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("▶️ يوتيوب", callback_data="youtube"),
                InlineKeyboardButton("🎵 تيك توك", callback_data="tiktok"),
            ],
            [
                InlineKeyboardButton("📸 إنستغرام", callback_data="instagram"),
                InlineKeyboardButton("📘 فيسبوك", callback_data="facebook"),
            ],
            [InlineKeyboardButton("⭐ ترقية دائمة بالنجوم", callback_data="upgrade")],
            [InlineKeyboardButton("👤 تواصل مع المالك", url=OWNER_CONTACT_URL)],
        ]
    )


def subscription_keyboard():
    rows = []
    icons = {
        "telegram": "✈️",
        "tiktok": "🎵",
        "instagram": "📸",
        "bot": "🤖",
    }
    for ch in TELEGRAM_VERIFY_CHANNELS:
        rows.append(
            [InlineKeyboardButton(f"{icons['telegram']} {ch['title']}", url=ch["url"])]
        )
    for link in TRUST_LINKS:
        url = link["url"]
        if "tiktok.com" in url:
            ic = icons["tiktok"]
        elif "instagram.com" in url:
            ic = icons["instagram"]
        elif "t.me" in url:
            ic = icons["bot"]
        else:
            ic = "🔗"
        rows.append([InlineKeyboardButton(f"{ic} {link['title']}", url=url)])
    rows.append([InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="verify")])
    return InlineKeyboardMarkup(rows)


async def is_subscribed_telegram(context, user_id):
    for ch in TELEGRAM_VERIFY_CHANNELS:
        try:
            member = await context.bot.get_chat_member(ch["username"], user_id)
            if member.status not in ("member", "administrator", "creator"):
                return False, ch
        except Exception as e:
            logger.warning("get_chat_member failed for %s: %s", ch["username"], e)
            return False, ch
    return True, None


async def send_subscription_prompt(message_or_query, user_id, context, edit=False):
    text = (
        "🚫 للوصول إلى البوت، يجب الاشتراك أولاً في القنوات والحسابات التالية:\n\n"
        "اشترك ثم اضغط زر «تحقق من الاشتراك» 👇"
    )
    kb = subscription_keyboard()
    if edit:
        await message_or_query.edit_message_text(text, reply_markup=kb)
    else:
        await message_or_query.reply_text(text, reply_markup=kb)


async def ensure_subscribed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id if update.effective_user else None
    if user_id is None:
        return False
    if user_id == OWNER_ID or user_id in verified_users:
        return True
    ok, _ = await is_subscribed_telegram(context, user_id)
    if not ok:
        target = update.message or (
            update.callback_query.message if update.callback_query else None
        )
        if target:
            await send_subscription_prompt(target, user_id, context)
        return False
    verified_users.add(user_id)
    return True


def balance_line(user_id):
    if is_premium(user_id):
        if user_id == OWNER_ID:
            return "👑 رصيدك: غير محدود (المالك)"
        return "⭐ رصيدك: غير محدود (مشترك دائم)"
    return f"💳 رصيدك الحالي: {get_user_limit(user_id)} / {FREE_LIMIT} فيديو"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id == OWNER_ID:
        text = f"👑 أهلاً بالمالك\n\n{WELCOME_TEXT}\n\n{balance_line(user_id)}"
        await update.message.reply_text(text, reply_markup=main_menu_keyboard())
        return

    if user_id not in verified_users:
        ok, _ = await is_subscribed_telegram(context, user_id)
        if not ok:
            await send_subscription_prompt(update.message, user_id, context)
            return
        verified_users.add(user_id)

    text = f"{WELCOME_TEXT}\n\n{balance_line(user_id)}"
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())


async def verify_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    ok, _ = await is_subscribed_telegram(context, user_id)
    if not ok:
        await query.answer("لم تشترك بعد في كل القنوات المطلوبة 🚫", show_alert=True)
        return

    verified_users.add(user_id)
    await query.answer("تم التحقق بنجاح ✅")
    text = f"{WELCOME_TEXT}\n\n{balance_line(user_id)}"
    await query.edit_message_text(text, reply_markup=main_menu_keyboard())


async def platform_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if user_id != OWNER_ID and user_id not in verified_users:
        ok, _ = await is_subscribed_telegram(context, user_id)
        if not ok:
            await query.answer("اشترك أولاً في القنوات 🚫", show_alert=True)
            await send_subscription_prompt(query, user_id, context, edit=True)
            return
        verified_users.add(user_id)

    await query.answer()
    platform = query.data
    names = {
        "youtube": "يوتيوب",
        "instagram": "إنستغرام",
        "facebook": "فيسبوك",
        "tiktok": "تيك توك",
    }
    extra = ""
    if platform == "instagram":
        extra = "\n\nℹ️ بعض فيديوهات إنستغرام الخاصة قد لا تعمل لأنها تتطلب تسجيل دخول."
    await query.edit_message_text(
        f"اخترت {names.get(platform, platform)}.\nأرسل رابط الفيديو الآن 🔗{extra}"
    )


async def upgrade_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if is_premium(user_id):
        await query.answer("أنت مشترك دائم بالفعل ⭐", show_alert=True)
        return

    await query.answer()
    await context.bot.send_invoice(
        chat_id=query.message.chat_id,
        title="⭐ ترقية دائمة (تنزيل غير محدود)",
        description=(
            "ادفع مرة واحدة بالنجوم واحصل على تنزيل غير محدود مدى الحياة.\n"
            "بدون أي حد على عدد الفيديوهات."
        ),
        payload="premium_unlimited",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice("اشتراك دائم", PREMIUM_PRICE_STARS)],
        start_parameter="premium",
    )


async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if is_premium(user_id):
        await update.message.reply_text("أنت مشترك دائم بالفعل ⭐")
        return
    await context.bot.send_invoice(
        chat_id=update.message.chat_id,
        title="⭐ ترقية دائمة (تنزيل غير محدود)",
        description=(
            "ادفع مرة واحدة بالنجوم واحصل على تنزيل غير محدود مدى الحياة.\n"
            "بدون أي حد على عدد الفيديوهات."
        ),
        payload="premium_unlimited",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice("اشتراك دائم", PREMIUM_PRICE_STARS)],
        start_parameter="premium",
    )


async def grant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        await update.message.reply_text("هذا الأمر للمالك فقط 🚫")
        return
    if not context.args:
        await update.message.reply_text(
            "الاستخدام: /grant <user_id>\n"
            "مثال: /grant 123456789\n\n"
            "يمكنك أيضاً الرد على رسالة شخص بـ /grant لتفعيله."
        )
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("المعرّف يجب أن يكون رقماً ❌")
        return

    premium_users.add(target_id)
    verified_users.add(target_id)
    await update.message.reply_text(
        f"✅ تم إعفاء المستخدم {target_id} ومنحه اشتراك دائم غير محدود ⭐"
    )


async def revoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        await update.message.reply_text("هذا الأمر للمالك فقط 🚫")
        return
    if not context.args:
        await update.message.reply_text("الاستخدام: /revoke <user_id>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("المعرّف يجب أن يكون رقماً ❌")
        return

    premium_users.discard(target_id)
    await update.message.reply_text(
        f"❌ تم سحب الاشتراك الدائم من المستخدم {target_id}"
    )


async def list_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        await update.message.reply_text("هذا الأمر للمالك فقط 🚫")
        return
    if not premium_users:
        await update.message.reply_text("لا يوجد مشتركون دائمون حالياً.")
        return
    lines = "\n".join(f"• {uid}" for uid in premium_users)
    await update.message.reply_text(
        f"⭐ المشتركون الدائمون ({len(premium_users)}):\n{lines}"
    )


async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    if query.invoice_payload == "premium_unlimited":
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="منتج غير معروف ❌")


async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    premium_users.add(user_id)
    await update.message.reply_text(
        "🎉 شكراً لك! تم تفعيل الاشتراك الدائم ⭐\n"
        "أصبح بإمكانك الآن تنزيل فيديوهات بدون أي حد.",
        reply_markup=main_menu_keyboard(),
    )


def filter_qualities(formats):
    combined = [
        f
        for f in formats
        if f.get("height")
        and MIN_HEIGHT <= f.get("height") <= MAX_HEIGHT
        and f.get("acodec") != "none"
        and f.get("vcodec") != "none"
    ]
    seen = set()
    unique = []
    for f in sorted(combined, key=lambda x: x.get("height") or 0):
        h = f.get("height")
        if h in seen:
            continue
        seen.add(h)
        unique.append(f)
    return unique


def make_ydl_opts(extra=None):
    opts = {"quiet": True, "no_warnings": True}
    if INSTAGRAM_COOKIES_FILE and os.path.exists(INSTAGRAM_COOKIES_FILE):
        opts["cookiefile"] = INSTAGRAM_COOKIES_FILE
    if extra:
        opts.update(extra)
    return opts


async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text or ""

    if not await ensure_subscribed(update, context):
        return

    match = URL_RE.search(text)
    if not match:
        await update.message.reply_text(
            "لم أجد رابطاً في رسالتك ❌\nأرسل رابط الفيديو فقط 🔗"
        )
        return
    link = match.group(0).rstrip(".,!?")

    if get_user_limit(user_id) <= 0:
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "⭐ ترقية دائمة بالنجوم", callback_data="upgrade"
                    )
                ]
            ]
        )
        await update.message.reply_text(
            f"انتهت محاولاتك المجانية ({FREE_LIMIT}) ❌\n\n"
            "اشترك بالنجوم مرة واحدة واستمتع بتنزيل غير محدود ⭐",
            reply_markup=kb,
        )
        return

    status_msg = await update.message.reply_text("جاري فحص الرابط وجلب الجودات... 🔍")

    try:
        with yt_dlp.YoutubeDL(make_ydl_opts()) as ydl:
            info = ydl.extract_info(link, download=False)
            formats = info.get("formats", [])
            unique = filter_qualities(formats)

            context.bot_data.setdefault("links", {})
            link_id = str(abs(hash(link)))[:10]
            context.bot_data["links"][link_id] = link

            quality_labels = {
                240: "240p",
                360: "360p",
                480: "480p SD",
                720: "720p HD",
                1080: "1080p Full HD",
            }

            buttons = []
            for f in unique:
                h = f.get("height")
                fid = f.get("format_id")
                label = quality_labels.get(h, f"{h}p")
                buttons.append(
                    [
                        InlineKeyboardButton(
                            f"🎬 {label}", callback_data=f"dl|{fid}|{link_id}"
                        )
                    ]
                )

            buttons.append(
                [
                    InlineKeyboardButton(
                        "🚀 أفضل جودة (حتى 1080p)", callback_data=f"dl|best|{link_id}"
                    )
                ]
            )

            await status_msg.edit_text(
                "اختر الجودة المطلوبة (240p حتى Full HD 1080p):",
                reply_markup=InlineKeyboardMarkup(buttons),
            )

    except Exception as e:
        logger.exception("link error")
        msg = "حدث خطأ: الرابط غير مدعوم أو غير صحيح ❌"
        if "instagram" in link.lower() and (
            "login" in str(e).lower() or "rate-limit" in str(e).lower()
        ):
            msg = (
                "إنستغرام يطلب تسجيل دخول لهذا الفيديو 🔒\n"
                "جرّب رابطاً عاماً (Reels/Posts بدون قيود)، "
                "أو فيديو من حساب عام."
            )
        await status_msg.edit_text(msg)


async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if user_id != OWNER_ID and user_id not in verified_users:
        ok, _ = await is_subscribed_telegram(context, user_id)
        if not ok:
            await query.answer("اشترك أولاً في القنوات 🚫", show_alert=True)
            await send_subscription_prompt(query, user_id, context, edit=True)
            return
        verified_users.add(user_id)

    await query.answer()

    _, format_id, link_id = query.data.split("|")
    link = context.bot_data.get("links", {}).get(link_id)
    if not link:
        await query.edit_message_text("انتهت صلاحية الرابط، أرسله مرة أخرى 🔁")
        return

    await query.edit_message_text("جاري التحميل والمعالجة... ⏳")

    file_path = f"/tmp/video_{user_id}.mp4"
    if format_id == "best":
        fmt_string = (
            f"bestvideo[height<={MAX_HEIGHT}]+bestaudio/"
            f"best[height<={MAX_HEIGHT}]/best"
        )
    else:
        fmt_string = format_id

    ydl_opts = make_ydl_opts(
        {
            "format": fmt_string,
            "outtmpl": file_path,
            "merge_output_format": "mp4",
        }
    )

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([link])

        with open(file_path, "rb") as vf:
            await query.message.reply_video(
                video=vf, caption="تم التحميل بواسطة بوتك ✅"
            )

        if os.path.exists(file_path):
            os.remove(file_path)
        decrease_limit(user_id)
        try:
            await query.message.delete()
        except Exception:
            pass

    except Exception as e:
        logger.exception("download error")
        msg = "فشل التحميل ❌"
        if "instagram" in link.lower() and (
            "login" in str(e).lower() or "rate-limit" in str(e).lower()
        ):
            msg = (
                "فشل التحميل من إنستغرام 🔒\n"
                "هذا الفيديو يتطلب تسجيل دخول. جرّب رابطاً عاماً."
            )
        await query.message.reply_text(msg)
        if os.path.exists(file_path):
            os.remove(file_path)


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("grant", grant))
    app.add_handler(CommandHandler("revoke", revoke))
    app.add_handler(CommandHandler("premium", list_premium))
    app.add_handler(CallbackQueryHandler(verify_subscription, pattern="^verify$"))
    app.add_handler(CallbackQueryHandler(upgrade_button, pattern="^upgrade$"))
    app.add_handler(
        CallbackQueryHandler(
            platform_button, pattern="^(youtube|instagram|facebook|tiktok)$"
        )
    )
    app.add_handler(CallbackQueryHandler(download_video, pattern=r"^dl\|"))
    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(
        MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment)
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))

    logger.info("البوت يعمل الآن...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
