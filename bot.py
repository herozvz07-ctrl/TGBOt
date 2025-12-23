import os
import asyncio
import uuid
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from yt_dlp import YoutubeDL
from flask import Flask, request

# --- НАСТРОЙКИ ---
TOKEN = "7284903125:AAHrn9g2xWH4ydcGfGgfV6l8dyn0zhg22qM"
REQUIRED_CHANNEL = "@ttimperia"
RENDER_URL = "https://tgbot-1-ow0e.onrender.com"

# ИСПРАВЛЕННАЯ ИНИЦИАЛИЗАЦИЯ (для Aiogram 3.7+)
bot = Bot(
    token=TOKEN, 
    default=DefaultBotProperties(parse_mode='HTML')
)
dp = Dispatcher()
app = Flask(__name__)

user_data = {}
user_lang = {}
EMOJI_NUMS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]

# --- КЛАВИАТУРЫ ---
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

# --- ЛОГИКА СКАЧИВАНИЯ (SOUNDCLOUD) ---
async def download_music(url):
    file_id = str(uuid.uuid4())[:8]
    if not os.path.exists('downloads'): os.makedirs('downloads')
    
    ydl_opts = {
        'outtmpl': f'downloads/{file_id}.%(ext)s',
        'quiet': True,
        'format': 'bestaudio/best',
        'allowed_extractors': ['soundcloud.*', 'generic'], 
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    loop = asyncio.get_event_loop()
    # Запускаем тяжелое скачивание в отдельном потоке, чтобы бот не тормозил
    info = await loop.run_in_executor(None, lambda: YoutubeDL(ydl_opts).extract_info(url, download=True))
    fname = YoutubeDL(ydl_opts).prepare_filename(info)
    return os.path.splitext(fname)[0] + ".mp3", info.get('title', 'Music')

# --- ОБРАБОТЧИКИ (HANDLERS) ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    uid = message.from_user.id
    text = "<b>💎 Aiogram Music Bot</b>\n\nПришли название песни!" if user_lang.get(uid, 'RU') == 'RU' else "<b>💎 Aiogram Music Bot</b>\n\nSend me song title!"
    await message.answer(text, reply_markup=get_main_menu(uid))

@dp.callback_query(F.data == "btn_lang")
async def set_lang_menu(call: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="RU 🇷🇺", callback_data="set_RU"),
                types.InlineKeyboardButton(text="EN 🇺🇸", callback_data="set_EN"))
    await call.message.edit_text("Выберите язык / Choose language:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("set_"))
async def set_lang(call: types.CallbackQuery):
    lang = call.data.split('_')[1]
    user_lang[call.from_user.id] = lang
    await call.answer("OK!")
    await call.message.edit_text("<b>💎 Музыкальный Бот</b>", reply_markup=get_main_menu(call.from_user.id))

@dp.message()
async def handle_text(message: types.Message):
    query = message.text.strip()
    clean_query = query.split('?')[0].replace("https://", "").replace("www.youtube.com", "").replace("youtu.be", "")
    
    status_msg = await message.answer(f"🔎 Ищу: <b>{clean_query}</b>...")
    
    try:
        search_opts = {'quiet': True, 'extract_flat': True, 'allowed_extractors': ['soundcloud.*']}
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, lambda: YoutubeDL(search_opts).extract_info(f"scsearch9:{clean_query}", download=False).get('entries', []))
        
        if not res:
            await status_msg.edit_text("❌ Ничего не найдено.")
            return

        builder = InlineKeyboardBuilder()
        text = "<b>Результаты поиска:</b>\n\n"
        
        for i, entry in enumerate(res[:9]):
            rid = str(uuid.uuid4())[:8]
            user_data[rid] = entry['url']
            builder.add(types.InlineKeyboardButton(text=EMOJI_NUMS[i], callback_data=f"dl_{rid}"))
            text += f"{EMOJI_NUMS[i]} {entry.get('title', 'Track')[:50]}\n"
        
        builder.adjust(3)
        await status_msg.edit_text(text, reply_markup=builder.as_markup())
    except Exception as e:
        await status_msg.edit_text(f"Ошибка поиска: {e}")

@dp.callback_query(F.data.startswith("dl_"))
async def process_dl(call: types.CallbackQuery):
    rid = call.data.split('_')[1]
    url = user_data.get(rid)
    if not url: return

    # Используем edit_text чтобы пользователь видел статус
    await call.message.edit_text("🚀 Загрузка файла...")
    try:
        fpath, title = await download_music(url)
        await call.message.answer_audio(
            audio=types.FSInputFile(fpath), 
            caption=f"✅ {title}"
        )
        os.remove(fpath)
        await call.message.delete()
    except Exception as e:
        await call.message.answer(f"Ошибка загрузки: {e}")

# --- ВЕБХУК (FLASK + AIOGRAM) ---
@app.route('/' + TOKEN, methods=['POST'])
def webhook_receiver():
    # Асинхронная обработка внутри Flask
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    update = types.Update.model_validate_json(request.data.decode('utf-8'))
    loop.run_until_complete(dp.feed_update(bot, update))
    return "OK", 200

@app.route('/')
def index():
    # Установка вебхука при заходе на главную
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(bot.set_webhook(url=f"{RENDER_URL}/{TOKEN}", drop_pending_updates=True))
    return "Aiogram Bot Live!", 200

if __name__ == "__main__":
    if not os.path.exists('downloads'): os.makedirs('downloads')
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
    
