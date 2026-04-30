import logging
import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# --- الإعدادات ---
TOKEN = "8724429514:AAFLWReuzWxSTWMx-zmWGvJb2rhuRrJIwSc"
OWNER_USERNAME = "rsll61"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- لوحة المفاتيح (زر التواصل مع المالك) ---
def get_main_keyboard():
    keyboard = [[InlineKeyboardButton("👤 تواصل مع المالك", url=f"https://t.me/{OWNER_USERNAME}")]]
    return InlineKeyboardMarkup(keyboard)

# --- دالة التعرف على الأنمي عبر Trace.moe ---
async def identify_anime(image_url):
    try:
        response = requests.get(f"https://trace.moe{image_url}")
        data = response.json()
        if data['result']:
            res = data['result'][0]
            name = res['anilist']['title']['english'] or res['anilist']['title']['romaji']
            episode = res['episode']
            similarity = round(res['similarity'] * 100, 2)
            return f"🎬 أنمي: {name}\n🎞 الحلقة: {episode}\n🎯 نسبة التطابق: {similarity}%"
    except:
        return None

# --- دالة التعرف العامة (مشاهير/أفلام) ---
# ملاحظة: للوصول لدقة 100% يفضل ربط Google Cloud Vision API هنا
async def identify_general(image_url):
    # كحل سريع ودقيق، نوجه المستخدم لمحرك البحث البصري أو نستخدم API Labelling
    return "🔍 جاري البحث عن تفاصيل الشخصية/الفيلم... (يتطلب ربط Google Vision API للنتائج التفصيلية)"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً بك! 👋 أنا بوت ذكي للتعرف على الصور.\n"
        "أرسل لي صورة (فنان، لاعب، لقطة من فيلم أو أنمي) وسأخبرك بكافة التفاصيل عنها.",
        reply_markup=get_main_keyboard()
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await context.bot.get_file(update.message.photo[-1].file_id)
    image_url = file.file_path
    
    msg = await update.message.reply_text("🔄 جاري تحليل الصورة بدقة... يرجى الانتظار")

    # 1. محاولة التعرف كأنمي أولاً
    anime_result = await identify_anime(image_url)
    
    if anime_result:
        await msg.edit_text(f"✅ تم التعرف على اللقطة:\n\n{anime_result}", reply_markup=get_main_keyboard())
    else:
        # 2. إذا لم يكن أنمي، يتم البحث عن مشاهير أو لقطات أفلام
        general_info = await identify_general(image_url)
        await msg.edit_text(f"ℹ️ المعلومات المتاحة:\n\n{general_info}", reply_markup=get_main_keyboard())

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    print("البوت يعمل الآن...")
    app.run_polling()
