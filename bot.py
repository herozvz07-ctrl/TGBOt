import os, asyncio, uuid, logging
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

# --- КЛАВИАТУРЫ ---
def get_main_menu(uid):
    lang = user_lang.get(uid, 'RU')
    builder = InlineKeyboardBuilder()
    btns = [("🔥 ТОП Хитов", "btn_top"), ("⚙️ Язык", "btn_lang")] if lang == 'RU' else [("🔥 Top Hits", "btn_top"), ("⚙️ Language", "btn_lang")]
    for text, data in btns:
        builder.add(types.InlineKeyboardButton(text=text, callback_data=data))
    return builder.as_markup()

# --- СКАЧИВАНИЕ ---
async def download_media(url, mode='video'):
    file_id = str(uuid.uuid4())[:8]
    if not os.path.exists('downloads'): os.makedirs('downloads')
    
    ydl_opts = {
        'outtmpl': f'downloads/{file_id}.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }

    if mode == 'audio':
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}]
        })
    else:
        # Для TikTok/Insta без водяных знаков
        ydl_opts.update({'format': 'bestvideo+bestaudio/best'})

    loop = asyncio.get_event_loop()
    info = await loop.run_in_executor(None, lambda: YoutubeDL(ydl_opts).extract_info(url, download=True))
    path = YoutubeDL(ydl_opts).prepare_filename(info)
    if mode == 'audio': path = os.path.splitext(path)[0] + ".mp3"
    return path, info.get('title', 'Media')

# --- ОБРАБОТЧИКИ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("<b>💎 Главное меню</b>", reply_markup=get_main_menu(message.from_user.id))

@dp.callback_query(F.data == "btn_lang")
async def lang_menu(call: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="RU 🇷🇺", callback_data="set_RU"),
                types.InlineKeyboardButton(text="EN 🇺🇸", callback_data="set_EN"))
    await call.message.edit_text("Выберите язык:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("set_"))
async def set_lang(call: types.CallbackQuery):
    user_lang[call.from_user.id] = call.data.split('_')[1]
    await call.answer("Готово!")
    await call.message.edit_text("<b>💎 Меню обновлено</b>", reply_markup=get_main_menu(call.from_user.id))

@dp.message(F.text)
async def handle_message(message: types.Message):
    text = message.text.strip()
    
    # ПРОВЕРКА: ССЫЛКА ИЛИ ТЕКСТ
    if "http" in text:
        rid = str(uuid.uuid4())[:8]
        user_data[rid] = text
        builder = InlineKeyboardBuilder()
        builder.add(types.InlineKeyboardButton(text="🎬 Видео", callback_data=f"media_v_{rid}"),
                    types.InlineKeyboardButton(text="🎵 MP3", callback_data=f"media_a_{rid}"))
        await message.reply("⚙️ Выберите формат:", reply_markup=builder.as_markup())
    else:
        # ПОИСК МУЗЫКИ
        status = await message.answer("🔎 Ищу музыку...")
        try:
            opts = {'quiet': True, 'extract_flat': True, 'allowed_extractors': ['soundcloud.*']}
            loop = asyncio.get_event_loop()
            res = await loop.run_in_executor(None, lambda: YoutubeDL(opts).extract_info(f"scsearch6:{text}", download=False).get('entries', []))
            
            if not res:
                return await status.edit_text("❌ Ничего не найдено.")

            builder = InlineKeyboardBuilder()
            out = "<b>Результаты:</b>\n\n"
            for i, e in enumerate(res):
                uid = str(uuid.uuid4())[:8]
                user_data[uid] = e['url']
                builder.add(types.InlineKeyboardButton(text=EMOJI_NUMS[i], callback_data=f"media_a_{uid}"))
                out += f"{EMOJI_NUMS[i]} {e.get('title')[:50]}\n"
            
            builder.adjust(3)
            await status.edit_text(out, reply_markup=builder.as_markup())
        except:
            await status.edit_text("❌ Ошибка поиска.")

@dp.callback_query(F.data.startswith("media_"))
async def process_download(call: types.CallbackQuery):
    _, mode_code, rid = call.data.split('_')
    url = user_data.get(rid)
    if not url: return await call.answer("Ошибка данных.")

    mode = 'video' if mode_code == 'v' else 'audio'
    wait_msg = await call.message.answer("🚀 Загрузка...")
    
    try:
        path, title = await download_media(url, mode)
        file = types.FSInputFile(path)
        if mode == 'video':
            await call.message.answer_video(video=file, caption=f"✅ {title}")
        else:
            await call.message.answer_audio(audio=file, caption=f"✅ {title}")
        os.remove(path)
        await wait_msg.delete()
    except Exception as e:
        await call.message.answer(f"❌ Ошибка: {str(e)[:50]}")

# --- SERVER ---
async def on_startup(bot: Bot):
    await bot.set_webhook(url=f"{RENDER_URL}{WEB_PATH}", drop_pending_updates=True)

def main():
    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEB_PATH)
    setup_application(app, dp, bot=bot)
    dp.startup.register(on_startup)
    web.run_app(app, host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    main()
    
