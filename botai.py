import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import Application, Command_Handler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
import yt_dlp

# --- الإعدادات ---
TOKEN = '8413954282:AAFLK9JkREO_F0bNwAZx1SrdXIIaiNvtYnA'
OWNER_ID = 5868896814  # أيدي حسابك
CHANNEL_ID = '@your_channel'  # معرف قناتك للاشتراك الإجباري
DB_USERS = {}  # لتخزين بيانات المستخدمين (يفضل استخدام قاعدة بيانات حقيقية لاحقاً)

# --- الوظائف المساعدة ---
async def check_sub(user_id, bot):
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

# --- الأوامر ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # 1. التحقق من الاشتراك الإجباري
    if not await check_sub(user_id, context.bot):
        keyboard = [[InlineKeyboardButton("اضغط هنا للاشتراك", url=f"https://t.me{CHANNEL_ID[1:]}")],
                    [InlineKeyboardButton("تحقق من الاشتراك ✅", callback_data="verify")]]
        await update.message.reply_text("عذراً! يجب عليك الاشتراك في القناة أولاً لاستخدام البوت.", 
                                       reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # 2. تهيئة بيانات المستخدم
    if user_id not in DB_USERS:
        DB_USERS[user_id] = {'count': 0, 'access': True}

    # 3. الرسالة الترحيبية
    welcome_text = "مرحبا بك أنا بوت مصمم خصيصاً للتنزيل فيديوهات من مواقع التواصل الاجتماعي، فقط أرسل رابط، أو اختر تحت منصة."
    keyboard = [
        [InlineKeyboardButton("YouTube", callback_data="yt"), InlineKeyboardButton("TikTok", callback_data="tt")],
        [InlineKeyboardButton("Facebook", callback_data="fb")],
        [InlineKeyboardButton("Contact Owner 👨‍💻", url="https://t.meyour_username")]
    ]
    await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    url = update.message.text

    if user_id not in DB_USERS: return

    # التحقق من عدد المحاولات (25 محاولة مجانية)
    if DB_USERS[user_id]['count'] >= 25 and DB_USERS[user_id]['access']:
        await ask_for_stars(update, context)
        return

    await update.message.reply_text("جاري جلب الجودات المتاحة (قد يستغرق ذلك لحظات)...")
    
    # استخراج الجودات باستخدام yt-dlp
    try:
        with yt_dlp.YoutubeDL() as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])
            
            keyboard = []
            # عرض خيارات الجودة العالية
            for f in formats:
                if f.get('height') in [720, 1080, 2160]: # 2160 هي 4K
                    label = f"{f['height']}p - {f['ext']}"
                    keyboard.append([InlineKeyboardButton(label, callback_data=f"dl|{f['format_id']}|{url}")])
            
            await update.message.reply_text("اختر الجودة المطلوبة:", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        await update.message.reply_text("خطأ: الرابط غير مدعوم أو غير صحيح.")

async def ask_for_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # نظام دفع النجوم (تبسيط للمنطق)
    title = "شراء محاولات تحميل"
    description = "50 نجمة مقابل تحميل 20 فيديو إضافي بجودة عالية"
    payload = "premium_pack"
    currency = "XTR" # كود النجوم
    price = [LabeledPrice("الاشتراك", 50)]
    
    await context.bot.send_invoice(
        update.effective_chat.id, title, description, payload, "", "provider_token_from_botfather", 
        currency, price
    )

# --- تشغيل البوت ---
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(Command_Handler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("البوت يعمل الآن...")
    app.run_polling()

if __name__ == '__main__':
    main()
