import os
import asyncio
import uuid
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from yt_dlp import YoutubeDL

# --- НАСТРОЙКИ ---
TOKEN = "7284903125:AAHrn9g2xWH4ydcGfGgfV6l8dyn0zhg22qM"
REQUIRED_CHANNEL = "@ttimperia"
RENDER_URL = "https://tgbot-1-ow0e.onrender.com"
WEB_PATH = f"/{TOKEN}"

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

user_data = {}
user_lang = {}
EMOJI_NUMS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]

# --- ЛОГИКА ---
def get_main_menu(uid):
    lang = user_lang.get(uid, 'RU')
    builder = InlineKeyboardBuilder()
    if lang == 'RU':
        builder.row(types.InlineKeyboardButton(text="🔥 ТОП Хитов", callback_data="btn_top"),
                    types.InlineKeyboardButton(text="⚙️ Язык", callback_data="btn_lang"))
    else:
        builder.row(types.InlineKeyboardButton(text="🔥 Top Hits", callback_data="btn_top"),
                    types.InlineKeyboardButton(text="⚙️ Language", callback_data="btn_lang"))
    return builder.as_markup()

async def download_music(url):
    file_id = str(uuid.uuid4())[:8]
    if not os.path.exists('downloads'): os.makedirs('downloads')
    ydl_opts = {
        'outtmpl': f'downloads/{file_id}.%(ext)s',
        'quiet': True,
        'format': 'bestaudio/best',
        'allowed_extractors': ['soundcloud.*', 'generic'],
        'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}]
    }
    loop = asyncio.get_event_loop()
    info = await loop.run_in_executor(None, lambda: YoutubeDL(ydl_opts).extract_info(url, download=True))
    fname = YoutubeDL(ydl_opts).prepare_filename(info)
    return os.path.splitext(fname)[0] + ".mp3", info.get('title', 'Music')

# --- ОБРАБОТЧИКИ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    uid = message.from_user.id
    text = "<b>💎 Music Bot</b>\n\nПришли название песни!"
    await message.answer(text, reply_markup=get_main_menu(uid))

@dp.message()
async def handle_text(message: types.Message):
    query = message.text.strip()
    status_msg = await message.answer(f"🔎 Ищу: <b>{query}</b>...")
    try:
        search_opts = {'quiet': True, 'extract_flat': True, 'allowed_extractors': ['soundcloud.*']}
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, lambda: YoutubeDL(search_opts).extract_info(f"scsearch9:{query}", download=False).get('entries', []))
        if not res:
            await status_msg.edit_text("❌ Ничего не найдено.")
            return
        builder = InlineKeyboardBuilder()
        text = "<b>Выберите трек:</b>\n\n"
        for i, entry in enumerate(res[:9]):
            rid = str(uuid.uuid4())[:8]
            user_data[rid] = entry['url']
            builder.add(types.InlineKeyboardButton(text=EMOJI_NUMS[i], callback_data=f"dl_{rid}"))
            text += f"{EMOJI_NUMS[i]} {entry.get('title')[:50]}\n"
        builder.adjust(3)
        await status_msg.edit_text(text, reply_markup=builder.as_markup())
    except Exception as e:
        await status_msg.edit_text(f"Ошибка: {e}")

@dp.callback_query(F.data.startswith("dl_"))
async def process_dl(call: types.CallbackQuery):
    url = user_data.get(call.data.split('_')[1])
    if not url: return
    await call.message.edit_text("🚀 Скачивание...")
    try:
        fpath, title = await download_music(url)
        await call.message.answer_audio(audio=types.FSInputFile(fpath), caption=f"✅ {title}")
        os.remove(fpath)
        await call.message.delete()
    except Exception as e:
        await call.message.answer(f"Ошибка: {e}")

# --- ЗАПУСК ВЕБ-СЕРВЕРА ---
async def on_startup(bot: Bot):
    await bot.set_webhook(url=f"{RENDER_URL}{WEB_PATH}", drop_pending_updates=True)

def main():
    if not os.path.exists('downloads'): os.makedirs('downloads')
    
    # Создаем aiohttp приложение
    app = web.Application()
    
    # Настраиваем обработчик запросов от Telegram
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=WEB_PATH)
    
    # Настраиваем запуск и остановку
    setup_application(app, dp, bot=bot)
    dp.startup.register(on_startup)
    
    # Render передает PORT в переменные окружения
    port = int(os.environ.get("PORT", 10000))
    web.run_app(app, host='0.0.0.0', port=port)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
    
