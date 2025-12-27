import os
import uuid
import asyncio
import logging

from dotenv import load_dotenv
from cachetools import TTLCache

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from yt_dlp import YoutubeDL

# ───────────── LOAD ENV ─────────────
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = os.getenv("CHANNEL")
# Render дает URL в формате https://project.onrender.com
RENDER_URL = os.getenv("RENDER_URL")

# Проверка критических переменных перед запуском
if not TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения!")
if not RENDER_URL:
    raise ValueError("RENDER_URL не найден! Добавьте его в настройках Render.")
if not CHANNEL:
    raise ValueError("CHANNEL не найден! Укажите ID или @username канала.")

WEB_PATH = f"/webhook/{TOKEN}"
WEB_URL = f"{RENDER_URL.rstrip('/')}{WEB_PATH}"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# ───────────── SYSTEM ─────────────
download_cache = TTLCache(maxsize=500, ttl=3600)
download_queue = asyncio.Semaphore(2)
user_last_action = {}

os.makedirs("downloads", exist_ok=True)

# ───────────── HELPERS ─────────────
def anti_flood(uid):
    import time
    now = time.time()
    if uid in user_last_action and now - user_last_action[uid] < 4:
        return False
    user_last_action[uid] = now
    return True

async def is_subscribed(uid):
    try:
        # Убираем @ если пользователь ввел его в CHANNEL, для метода get_chat_member
        chat_id = CHANNEL if CHANNEL.startswith("-") else (f"@{CHANNEL.lstrip('@')}")
        m = await bot.get_chat_member(chat_id, uid)
        return m.status in ["member", "administrator", "creator"]
    except Exception as e:
        logging.error(f"Ошибка проверки подписки: {e}")
        return False

def keyboard(*btns):
    kb = InlineKeyboardBuilder()
    for t, d in btns:
        # Если d начинается с http, это URL кнопка, иначе callback
        if d.startswith("http"):
            kb.add(types.InlineKeyboardButton(text=t, url=d))
        else:
            kb.add(types.InlineKeyboardButton(text=t, callback_data=d))
    return kb.as_markup()

# ───────────── YT-DLP ─────────────
async def download_media(url, audio=False):
    async with download_queue:
        if url in download_cache:
            return download_cache[url]

        uid = str(uuid.uuid4())
        path = f"downloads/{uid}"

        opts = {
            "outtmpl": path + ".%(ext)s",
            "quiet": True,
            "merge_output_format": "mp4",
            "noplaylist": True,
            "ffmpeg_location": "/usr/bin/ffmpeg" # Стандартный путь в Linux
        }

        if audio:
            opts["format"] = "bestaudio/best"
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
        else:
            opts["format"] = "bestvideo+bestaudio/best"

        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: YoutubeDL(opts).extract_info(url, True))

        filename = YoutubeDL(opts).prepare_filename(data)
        if audio:
            filename = filename.rsplit(".", 1)[0] + ".mp3"

        download_cache[url] = (filename, data["title"])
        return filename, data["title"]

# ───────────── BOT ─────────────
@dp.message(Command("start"))
async def start(m: types.Message):
    await m.answer("🔥 Отправь ссылку YouTube или название трека")

@dp.message(F.text)
async def main_handler(m: types.Message):
    if not anti_flood(m.from_user.id):
        return await m.answer("⏳ Не так быстро")

    if not await is_subscribed(m.from_user.id):
        link = f"https://t.me/{CHANNEL.lstrip('@')}"
        return await m.answer(
            "🔒 Подпишись на канал, чтобы использовать бота",
            reply_markup=keyboard(("📢 Канал", link))
        )

    text = m.text.strip()

    if "http" in text:
        await m.answer("Выбери формат:", reply_markup=keyboard(
            ("🎬 Видео", f"v|{text}"),
            ("🎵 MP3", f"a|{text}")
        ))
    else:
        await m.answer("🔎 Ищу...")
        opts = {"quiet": True, "extract_flat": True}
        loop = asyncio.get_event_loop()
        try:
            search_data = await loop.run_in_executor(None, lambda: YoutubeDL(opts).extract_info(f"ytsearch5:{text}", False))
            results = search_data.get("entries", [])
        except:
            results = []

        if not results:
            return await m.answer("❌ Ничего не найдено")

        out = "Выберите результат:\n"
        kb = InlineKeyboardBuilder()
        for i, e in enumerate(results):
            out += f"{i+1}. {e['title']}\n"
            kb.add(types.InlineKeyboardButton(text=str(i+1), callback_data=f"a|{e['url']}"))

        await m.answer(out, reply_markup=kb.as_markup())

@dp.callback_query(F.data.contains("|"))
async def downloader(c: types.CallbackQuery):
    mode, url = c.data.split("|")
    msg = await c.message.answer("⏬ Скачиваю...")

    try:
        path, title = await download_media(url, audio=(mode == "a"))
        file = types.FSInputFile(path)

        if mode == "a":
            await c.message.answer_audio(file, title=title)
        else:
            await c.message.answer_video(file, caption=title)
        
        await msg.delete()
        if os.path.exists(path):
            os.remove(path)

    except Exception as e:
        logging.error(f"Ошибка загрузки: {e}")
        await c.message.answer(f"❌ Ошибка загрузки: {str(e)[:50]}")

# ───────────── WEBHOOK ─────────────
async def on_startup():
    logging.info(f"Установка вебхука на: {WEB_URL}")
    await bot.set_webhook(WEB_URL)

def main():
    app = web.Application()

    # Настройка обработчика вебхуков
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=WEB_PATH)

    setup_application(app, dp)
    dp.startup.register(on_startup)

    port = int(os.environ.get("PORT", 10000))
    web.run_app(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
