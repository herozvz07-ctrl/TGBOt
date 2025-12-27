import os, uuid, asyncio, logging
from dotenv import load_dotenv
from cachetools import TTLCache

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from yt_dlp import YoutubeDL

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = os.getenv("CHANNEL")
RENDER_URL = os.getenv("RENDER_URL")

WEB_PATH = f"/{TOKEN}"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

downloads_cache = TTLCache(maxsize=500, ttl=60 * 60)
download_queue = asyncio.Semaphore(2)
user_last_action = {}

# ───────────────────────────
def kb(*buttons):
    b = InlineKeyboardBuilder()
    for t, d in buttons:
        b.add(types.InlineKeyboardButton(text=t, callback_data=d))
    return b.as_markup()

# ───────────────────────────
async def is_subscribed(uid):
    try:
        m = await bot.get_chat_member(CHANNEL, uid)
        return m.status in ["member", "administrator", "creator"]
    except:
        return False

# ───────────────────────────
def anti_flood(uid):
    import time
    now = time.time()
    if uid in user_last_action and now - user_last_action[uid] < 4:
        return False
    user_last_action[uid] = now
    return True

# ───────────────────────────
async def ytdlp(url, audio=False):
    async with download_queue:
        if url in downloads_cache:
            return downloads_cache[url]

        file_id = str(uuid.uuid4())
        path = f"downloads/{file_id}"

        opts = {
            "outtmpl": path + ".%(ext)s",
            "quiet": True,
            "merge_output_format": "mp4"
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

        downloads_cache[url] = (filename, data["title"])
        return filename, data["title"]

# ───────────────────────────
@dp.message(Command("start"))
async def start(m: types.Message):
    await m.answer("🔥 Отправь ссылку или название песни")

# ───────────────────────────
@dp.message(F.text)
async def handle(m: types.Message):
    if not anti_flood(m.from_user.id):
        return await m.answer("⏳ Не так быстро")

    if not await is_subscribed(m.from_user.id):
        return await m.answer(
            "🔒 Подпишись чтобы использовать бота",
            reply_markup=kb(("📢 Канал", f"https://t.me/{CHANNEL[1:]}"))
        )

    text = m.text

    if "http" in text:
        await m.answer("Выбери формат:", reply_markup=kb(
            ("🎬 Видео", f"v|{text}"),
            ("🎵 MP3", f"a|{text}")
        ))
    else:
        await m.answer("🔎 Ищу...")
        opts = {"quiet": True, "extract_flat": True}
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, lambda: YoutubeDL(opts).extract_info(f"ytsearch5:{text}", False)["entries"])

        if not res:
            return await m.answer("❌ Ничего не найдено")

        out = ""
        kb2 = InlineKeyboardBuilder()
        for i, e in enumerate(res):
            out += f"{i+1}. {e['title']}\n"
            kb2.add(types.InlineKeyboardButton(text=str(i+1), callback_data=f"a|{e['url']}"))

        await m.answer(out, reply_markup=kb2.as_markup())

# ───────────────────────────
@dp.callback_query(F.data.contains("|"))
async def download(c: types.CallbackQuery):
    mode, url = c.data.split("|")
    await c.message.answer("⏬ Скачиваю...")

    try:
        path, title = await ytdlp(url, audio=(mode=="a"))
        file = types.FSInputFile(path)

        if mode == "a":
            await c.message.answer_audio(file, title=title)
        else:
            await c.message.answer_video(file, caption=title)

        os.remove(path)

    except Exception as e:
        await c.message.answer("❌ Ошибка загрузки")

# ───────────────────────────
async def on_startup(bot):
    await bot.set_webhook(RENDER_URL + WEB_PATH)

def main():
    app = web.Application()
    SimpleRequestHandler(dp, bot).register(app, path=WEB_PATH)
    setup_application(app, dp, bot)
    dp.startup.register(on_startup)
    web.run_app(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    main()
