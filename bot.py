import os
import uuid
import asyncio
import logging
import time

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
RENDER_URL = os.getenv("RENDER_URL")

# Проверка только самых необходимых данных
if not TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения!")
if not RENDER_URL:
    raise ValueError("RENDER_URL не найден! Добавьте адрес вашего сервиса в настройки Render.")

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
    now = time.time()
    if uid in user_last_action and now - user_last_action[uid] < 3:
        return False
    user_last_action[uid] = now
    return True

def keyboard(*btns):
    kb = InlineKeyboardBuilder()
    for t, d in btns:
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
        # Извлекаем информацию
        data = await loop.run_in_executor(None, lambda: YoutubeDL(opts).extract_info(url, True))
        
        # Получаем имя файла
        filename = YoutubeDL(opts).prepare_filename(data)
        if audio:
            filename = filename.rsplit(".", 1)[0] + ".mp3"

        download_cache[url] = (filename, data.get("title", "Без названия"))
        return filename, data.get("title", "Без названия")

# ───────────── BOT HANDLERS ─────────────
@dp.message(Command("start"))
async def start(m: types.Message):
    await m.answer("👋 Привет! Я помогу скачать видео или музыку.\n\n"
                   "Отправь мне **ссылку** на YouTube/TikTok или просто **название** трека.")

@dp.message(F.text)
async def main_handler(m: types.Message):
    if not anti_flood(m.from_user.id):
        return await m.answer("⏳ Не так быстро! Подождите пару секунд.")

    text = m.text.strip()

    if "http" in text:
        # Если прислали ссылку
        await m.answer("Что скачать?", reply_markup=keyboard(
            ("🎬 Видео", f"v|{text}"),
            ("🎵 Музыка (MP3)", f"a|{text}")
        ))
    else:
        # Если просто текст — ищем на YouTube
        msg = await m.answer("🔎 Ищу...")
        opts = {"quiet": True, "extract_flat": True}
        loop = asyncio.get_event_loop()
        
        try:
            search_data = await loop.run_in_executor(None, lambda: YoutubeDL(opts).extract_info(f"ytsearch5:{text}", False))
            results = search_data.get("entries", [])
        except Exception:
            results = []

        if not results:
            return await msg.edit_text("❌ Ничего не найдено.")

        out = "<b>Выберите результат для скачивания (MP3):</b>\n\n"
        kb = InlineKeyboardBuilder()
        for i, e in enumerate(results):
            out += f"{i+1}. {e['title']}\n"
            kb.add(types.InlineKeyboardButton(text=str(i+1), callback_data=f"a|{e['url']}"))
        
        kb.adjust(5) # Кнопки в ряд
        await msg.edit_text(out, reply_markup=kb.as_markup())

@dp.callback_query(F.data.contains("|"))
async def downloader(c: types.CallbackQuery):
    mode, url = c.data.split("|")
    status_msg = await c.message.answer("⏬ Начинаю загрузку, подождите...")

    try:
        path, title = await download_media(url, audio=(mode == "a"))
        
        if not os.path.exists(path):
            raise FileNotFoundError("Файл не был создан")

        file = types.FSInputFile(path)

        if mode == "a":
            await c.message.answer_audio(file, title=title)
        else:
            await c.message.answer_video(file, caption=title)
        
        await status_msg.delete()
        
        # Удаляем файл после отправки
        if os.path.exists(path):
            os.remove(path)

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await c.message.answer(f"❌ Произошла ошибка при обработке.")

# ───────────── WEBHOOK & SERVER ─────────────
async def on_startup():
    logging.info(f"Установка вебхука на: {WEB_URL}")
    await bot.set_webhook(WEB_URL, drop_pending_updates=True)

def main():
    app = web.Application()

    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=WEB_PATH)

    setup_application(app, dp)
    dp.startup.register(on_startup)

    port = int(os.environ.get("PORT", 10000))
    web.run_app(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
    
