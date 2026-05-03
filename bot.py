#!/usr/bin/env python3
"""
Telegram Story Viewer Bot - التحكم عبر البوت + مشاهدة الستوري بحساب مستخدم
يتطلب: pip install telethon python-telegram-bot cryptography
"""

import os
import json
import asyncio
import logging
from datetime import datetime
from telethon import TelegramClient
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ─── الإعدادات ──────────────────────────────────────────────────────────
CONFIG_FILE = "config.json"
TARGETS_FILE = "targets.json"
DOWNLOADS_DIR = "downloads"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "bot_token": "8724429514:AAHlbtCRiiOxcifpVMeRbaG-EkEel-l5QQI",        # من @BotFather
    "api_id": 0,                                # من my.telegram.org
    "api_hash": "",                             # من my.telegram.org
    "user_session": "user_session",
    "allowed_users": [],                        # معرفات المستخدمين المسموح لهم
    "check_interval": 60,
    "remove_forward_header": True,
    "save_locally": True
}

# ─── كلاس البوت ─────────────────────────────────────────────────────────
class StoryViewerBot:
    def __init__(self):
        self.config = self._load_config()
        self.targets = self._load_targets()
        self.user_client = None
        self.bot_app = None
        self.known_stories = set()
        self.running = False

    def _load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        else:
            with open(CONFIG_FILE, "w") as f:
                json.dump(DEFAULT_CONFIG, f, indent=4)
            logger.info(f"تم إنشاء {CONFIG_FILE}. عدله ثم شغل البرنامج مجدداً.")
            exit(0)

    def _load_targets(self):
        if os.path.exists(TARGETS_FILE):
            with open(TARGETS_FILE, "r") as f:
                return json.load(f)
        else:
            default = {"targets": []}
            with open(TARGETS_FILE, "w") as f:
                json.dump(default, f, indent=4)
            return default

    def _save_targets(self):
        with open(TARGETS_FILE, "w") as f:
            json.dump(self.targets, f, indent=4)

    async def _handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE, func):
        """التحقق من صلاحية المستخدم قبل تنفيذ الأمر."""
        user_id = update.effective_user.id
        if user_id not in self.config["allowed_users"]:
            await update.message.reply_text("⛔ غير مصرح لك باستخدام هذا البوت.")
            return False
        await func(update, context)
        return True

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🤖 **بوت مشاهدة الستوريات**\n\n"
            "الأوامر المتاحة:\n"
            "/targets - عرض قائمة الأهداف\n"
            "/add @username - إضافة هدف\n"
            "/remove @username - حذف هدف\n"
            "/monitor - عرض حالة المراقبة\n"
            "/start_monitor - بدء المراقبة\n"
            "/stop_monitor - إيقاف المراقبة\n"
            "/status - حالة البوت"
        )

    async def list_targets(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        targets = self.targets.get("targets", [])
        if not targets:
            await update.message.reply_text("📭 لا توجد أهداف حالياً.")
            return
        msg = "**🎯 قائمة الأهداف:**\n"
        for i, t in enumerate(targets, 1):
            msg += f"{i}. {t}\n"
        await update.message.reply_text(msg)

    async def add_target(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("❗ استخدم: /add @username")
            return
        username = context.args[0].strip()
        if not username.startswith("@"):
            username = f"@{username}"
        
        if username not in self.targets["targets"]:
            self.targets["targets"].append(username)
            self._save_targets()
            await update.message.reply_text(f"✅ تم إضافة {username}")
        else:
            await update.message.reply_text(f"⚠️ {username} موجود بالفعل.")

    async def remove_target(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("❗ استخدم: /remove @username")
            return
        username = context.args[0].strip()
        if not username.startswith("@"):
            username = f"@{username}"
        
        if username in self.targets["targets"]:
            self.targets["targets"].remove(username)
            self._save_targets()
            await update.message.reply_text(f"✅ تم حذف {username}")
        else:
            await update.message.reply_text(f"⚠️ {username} غير موجود.")

    async def monitor_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        status = "🟢 **نشط**" if self.running else "🔴 **متوقف**"
        await update.message.reply_text(
            f"**حالة المراقبة:** {status}\n"
            f"**عدد الأهداف:** {len(self.targets.get('targets', []))}\n"
            f"**فترة الفحص:** {self.config['check_interval']} ثانية"
        )

    async def start_monitor(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.running:
            await update.message.reply_text("⚠️ المراقبة تعمل بالفعل.")
            return
        
        if not self.targets.get("targets"):
            await update.message.reply_text("❗ لا توجد أهداف للمراقبة. أضف أهدافاً أولاً.")
            return

        self.running = True
        await update.message.reply_text("✅ **بدأت المراقبة!**")
        
        # بدء حلقة المراقبة في الخلفية
        asyncio.create_task(self._monitor_loop(update.effective_user.id))

    async def stop_monitor(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.running = False
        await update.message.reply_text("⏹️ **تم إيقاف المراقبة.**")

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_client_status = "🟢 متصل" if self.user_client and self.user_client.is_connected() else "🔴 غير متصل"
        await update.message.reply_text(
            f"**حالة البوت:**\n"
            f"• حساب المستخدم: {user_client_status}\n"
            f"• المراقبة: {'نشطة' if self.running else 'متوقفة'}\n"
            f"• الأهداف: {len(self.targets.get('targets', []))}"
        )

    async def _monitor_loop(self, owner_id: int):
        """حلقة المراقبة - تعمل في الخلفية."""
        while self.running:
            for target in self.targets.get("targets", []):
                try:
                    entity = await self.user_client.get_entity(target)
                    stories = await self.user_client.get_stories(entity)
                    
                    if stories and stories.stories:
                        for story in stories.stories:
                            story_id = f"{entity.id}_{story.id}"
                            if story_id in self.known_stories:
                                continue
                            
                            self.known_stories.add(story_id)
                            logger.info(f"ستوري جديد من {target}: {story.id}")
                            
                            # تحميل وإرسال الستوري
                            os.makedirs(DOWNLOADS_DIR, exist_ok=True)
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            file_path = f"{DOWNLOADS_DIR}/{entity.id}_{timestamp}_story_{story.id}"
                            
                            path = await self.user_client.download_media(story.media, file=file_path)
                            
                            # إرسال عبر البوت للمالك
                            from telegram import InputFile
                            caption = f"📸 ستوري من {target}"
                            if self.config["remove_forward_header"]:
                                with open(path, "rb") as f:
                                    await self.bot_app.bot.send_document(
                                        chat_id=owner_id,
                                        document=InputFile(f, filename=f"story_{story.id}"),
                                        caption=caption
                                    )
                            else:
                                # إرسال كصورة/فيديو حسب النوع
                                if hasattr(story.media, 'photo') and story.media.photo:
                                    with open(path, "rb") as f:
                                        await self.bot_app.bot.send_photo(
                                            chat_id=owner_id, photo=f, caption=caption
                                        )
                                else:
                                    with open(path, "rb") as f:
                                        await self.bot_app.bot.send_video(
                                            chat_id=owner_id, video=f, caption=caption
                                        )
                except Exception as e:
                    logger.error(f"خطأ في فحص {target}: {e}")
            
            await asyncio.sleep(self.config["check_interval"])

    async def setup_handlers(self):
        """إعداد أوامر البوت."""
        self.bot_app = Application.builder().token(self.config["bot_token"]).build()
        
        # ربط الأوامر
        self.bot_app.add_handler(CommandHandler("start", self.start))
        self.bot_app.add_handler(CommandHandler("targets", lambda u, c: self._handle_command(u, c, self.list_targets)))
        self.bot_app.add_handler(CommandHandler("add", lambda u, c: self._handle_command(u, c, self.add_target)))
        self.bot_app.add_handler(CommandHandler("remove", lambda u, c: self._handle_command(u, c, self.remove_target)))
        self.bot_app.add_handler(CommandHandler("monitor", lambda u, c: self._handle_command(u, c, self.monitor_status)))
        self.bot_app.add_handler(CommandHandler("start_monitor", lambda u, c: self._handle_command(u, c, self.start_monitor)))
        self.bot_app.add_handler(CommandHandler("stop_monitor", lambda u, c: self._handle_command(u, c, self.stop_monitor)))
        self.bot_app.add_handler(CommandHandler("status", lambda u, c: self._handle_command(u, c, self.status)))

    async def run(self):
        # تشغيل حساب المستخدم (Telethon) - هذا هو المهم للستوريات
        self.user_client = TelegramClient(
            self.config["user_session"],
            self.config["api_id"],
            self.config["api_hash"]
        )
        await self.user_client.start()
        logger.info(f"✅ تم تسجيل دخول حساب المستخدم: {await self.user_client.get_me()}")

        # تشغيل البوت (للواجهة فقط)
        await self.setup_handlers()
        logger.info("✅ تم تشغيل البوت بالتوكن.")
        
        # إرسال رسالة بدء التشغيل
        for uid in self.config["allowed_users"]:
            try:
                await self.bot_app.bot.send_message(
                    uid, "🚀 تم تشغيل بوت مشاهدة الستوريات بنجاح."
                )
            except:
                pass

        # بدء البوت (Polling)
        await self.bot_app.run_polling(allowed_updates=Update.ALL_TYPES)

# ─── نقطة البداية ─────────────────────────────────────────────────────────
async def main():
    bot = StoryViewerBot()
    await bot.run()

if __name__ == "__main__":
    try:
        import asyncio
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("تم إيقاف البوت.")
