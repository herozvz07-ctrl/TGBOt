import os
import uuid
import asyncio
from fastapi import FastAPI
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from yt_dlp import YoutubeDL
import uvicorn

TOKEN = os.getenv("BOT_TOKEN") or "ТУТ_ТВОЙ_ТОКЕН"

bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher()
app = FastAPI()

user_tracks = {}
EMOJI = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣"]

# ---------------- DOWNLOAD ----------------
def download_sc(url):
    uid = str(uuid.uuid4())[:8]
    os.makedirs("downloads", exist_ok=True)

    ydl_opts = {
        "outtmpl": f"downloads/{uid}.%(ext)s",
        "format": "bestaudio",
        "quiet": True,
        "allowed_extractors": ["soundcloud"],
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = ydl.prepare_filename(info)
        return os.path.splitext(path)[0] + ".mp3", info.get("title", "Music")

# ---------------- SEARCH ----------------
def search_sc(query):
    with YoutubeDL({"quiet": True}) as ydl:
        data = ydl.extract_info(
            f"https://soundcloud.com/search/sounds?q={query}",
            download=False
        )

    results = []
    for e in data.get("entries", []):
        url = e.get("webpage_url", "")
        if url.startswith("https://soundcloud.com/"):
            results.append({"title": e.get("title", ""), "url": url})
        if len(results) >= 9:
            break
    return results

# ---------------- BOT ----------------
@dp.message(CommandStart())
async def start(msg: types.Message):
    await msg.answer(
        "💎 <b>Music Bot</b>\n\n"
        "🔍 Название песни\n"
        "🔗 Или ссылка SoundCloud\n\n"
        "⚡ Быстро • Бесплатно"
    )

@dp.message()
async def handle(msg: types.Message):
    text = msg.text.strip()

    # LINK
    if text.startswith("https://soundcloud.com/"):
        await msg.answer("⏬ Загружаю...")
        try:
            file, title = await asyncio.to_thread(download_sc, text)
            await msg.answer_audio(types.FSInputFile(file), caption=title)
            os.remove(file)
        except Exception as e:
            await msg.answer(f"❌ {e}")
        return

    # SEARCH
    await msg.answer("🔎 Ищу...")
    tracks = await asyncio.to_thread(search_sc, text)

    if not tracks:
        await msg.answer("❌ Ничего не найдено.")
        return

    kb = InlineKeyboardMarkup()
    text_out = "<b>Найдено:</b>\n\n"

    for i, t in enumerate(tracks):
        tid = str(uuid.uuid4())[:8]
        user_tracks[tid] = t["url"]
        kb.add(InlineKeyboardButton(text=EMOJI[i], callback_data=f"dl_{tid}"))
        text_out += f"{EMOJI[i]} {t['title'][:45]}\n"

    await msg.answer(text_out, reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("dl_"))
async def dl(c: types.CallbackQuery):
    url = user_tracks.get(c.data.split("_")[1])
    await c.message.edit_text("⏬ Загружаю...")

    try:
        file, title = await asyncio.to_thread(download_sc, url)
        await c.message.answer_audio(types.FSInputFile(file), caption=title)
        os.remove(file)
    except Exception as e:
        await c.message.answer(f"❌ {e}")

# ---------------- WEB (PORT FOR RENDER) ----------------
@app.get("/")
async def root():
    return {"status": "ok"}

async def start_bot():
    await dp.start_polling(bot)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(start_bot())
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
