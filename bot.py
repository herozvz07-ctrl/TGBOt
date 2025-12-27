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
RENDER_URL = os.getenv("RENDER_URL")

WEB_PATH = f"/{TOKEN}"

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
        m = await bot.get_chat_member(CHANNEL, uid)
        return m.status in ["member", "administrator", "creator"]
    except:
        return False

def keyboard(*btns):
    kb = InlineKeyboardBuilder()
    for t, d in btns:
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
            "noplaylist": True
        }

        if audio:
            opts["format"] = "bestaudio"
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3"
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
    await m.answer("🔥 Отправь ссылку или название трека")

@dp.message(F.text)
async def main_handler(m: types.Message):
    if not anti_flood(m.from_user.id):
        return await m.answer("⏳ Не так быстро")

    if not await is_subscribed(m.from_user.id):
        return await m.answer(
            "🔒 Подпишись на канал, чтобы использовать бота",
            reply_markup=keyboard(("📢 Канал", f"https://t.me/{CHANNEL[1:]}"))
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
        results = await loop.run_in_executor(None, lambda: YoutubeDL(opts).extract_info(f"ytsearch5:{text}", False)["entries"])

        if not results:
            return await m.answer("❌ Ничего не найдено")

        out = ""
        kb = InlineKeyboardBuilder()
        for i, e in enumerate(results):
            out += f"{i+1}. {e['title']}\n"
            kb.add(types.InlineKeyboardButton(text=str(i+1), callback_data=f"a|{e['url']}"))

        await m.answer(out, reply_markup=kb.as_markup())

@dp.callback_query(F.data.contains("|"))
async def downloader(c: types.CallbackQuery):
    mode, url = c.data.split("|")
    await c.message.answer("⏬ Скачиваю...")

    try:
        path, title = await download_media(url, audio=(mode == "a"))
        file = types.FSInputFile(path)

        if mode == "a":
            await c.message.answer_audio(file, title=title)
        else:
            await c.message.answer_video(file, caption=title)

        os.remove(path)

    except Exception:
        await c.message.answer("❌ Ошибка загрузки")

# ───────────── WEBHOOK ─────────────
async def on_startup():
    await bot.set_webhook(RENDER_URL + WEB_PATH)

def main():
    app = web.Application()

    SimpleRequestHandler(dp, bot).register(app, path=WEB_PATH)
    setup_application(app, dp)

    dp.startup.register(on_startup)

    web.run_app(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    main()
