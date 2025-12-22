import os
import telebot
import uuid
import subprocess
from telebot import types
from yt_dlp import YoutubeDL
from flask import Flask, request

# --- НАСТРОЙКИ ---
TOKEN = "7284903125:AAHrn9g2xWH4ydcGfGgfV6l8dyn0zhg22qM"
REQUIRED_CHANNEL = "@ttimperia"
RENDER_URL = "https://tgbot-1-ow0e.onrender.com"

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
app = Flask(__name__)

user_data = {}
user_lang = {}
EMOJI_NUMS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"]

# --- КОРРЕКТИРОВКА СКАЧИВАНИЯ (SOUNDCLOUD + YT MUSIC) ---
def download_media(query, mode='audio'):
    file_id = str(uuid.uuid4())[:8]
    if not os.path.exists('downloads'): os.makedirs('downloads')
    
    # Мы меняем приоритет на SoundCloud и YouTube Music API
    ydl_opts = {
        'outtmpl': f'downloads/{file_id}.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        # Важно: пробуем скачать из SoundCloud если это просто музыка, там нет блокировок
        'default_search': 'ytsearch', 
        'format': 'bestaudio/best',
        'noplaylist': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        # Подменяем заголовки на более агрессивные
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    }

    # Если ссылка на YouTube, пробуем использовать альтернативный веб-клиент
    if "youtube.com" in query or "youtu.be" in query:
        ydl_opts['extractor_args'] = {'youtube': {'player_client': ['web_embedded']}}

    with YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(query, download=True)
            if 'entries' in info: info = info['entries'][0]
            fname = ydl.prepare_filename(info)
            if mode == 'audio': fname = os.path.splitext(fname)[0] + ".mp3"
            return fname, info.get('title', 'Music')
        except Exception as e:
            # Если YT заблочен совсем, пробуем найти это же название в SoundCloud автоматически
            if not ("youtube.com" in query or "youtu.be" in query):
                 raise e
            print("YT заблокирован, пробую SoundCloud...")
            ydl_opts['default_search'] = 'scsearch'
            with YoutubeDL(ydl_opts) as ydl_sc:
                info = ydl_sc.extract_info(query, download=True)
                if 'entries' in info: info = info['entries'][0]
                fname = ydl_sc.prepare_filename(info)
                return fname, info.get('title', 'Music')

# --- HANDLERS (С ЭМОДЗИ И 3 В РЯД) ---
def handle_search(message, query):
    lang = user_lang.get(message.chat.id, 'RU')
    msg = bot.send_message(message.chat.id, f"🔎 Ищу <b>{query}</b> везде...")
    
    try:
        # Ищем сразу в SoundCloud и YouTube (Flat extract не триггерит капчу)
        with YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
            # Ищем 6 результатов для красоты (2 ряда по 3 кнопки)
            res = ydl.extract_info(f"ytsearch6:{query}", download=False).get('entries', [])
        
        if not res:
            bot.edit_message_text("❌ Ничего не найдено.", message.chat.id, msg.message_id)
            return

        markup = types.InlineKeyboardMarkup()
        btns = []
        text = "<b>🎵 Выберите трек для скачивания:</b>\n\n"
        
        for i, entry in enumerate(res):
            rid = str(uuid.uuid4())[:8]
            user_data[rid] = entry['url']
            btns.append(types.InlineKeyboardButton(EMOJI_NUMS[i], callback_data=f"dl_{rid}"))
            text += f"{EMOJI_NUMS[i]} {entry.get('title')[:50]}\n"

        # Сетка по 3 кнопки в ряд
        for i in range(0, len(btns), 3):
            markup.add(*btns[i:i+3])

        bot.edit_message_text(text, message.chat.id, msg.message_id, reply_markup=markup, parse_mode='HTML')
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка поиска: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('dl_'))
def on_download(call):
    url = user_data.get(call.data.split('_')[1])
    bot.edit_message_text("🚀 Готовлю файл... Это может занять до 30 сек.", call.message.chat.id, call.message.message_id)
    try:
        fpath, title = download_media(url)
        with open(fpath, 'rb') as f:
            bot.send_audio(call.message.chat.id, f, caption=f"✅ <b>{title}</b>\nСкачано через @YourBot")
        os.remove(fpath)
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Ошибка скачивания.\nВероятно, YouTube заблокировал сервер. Попробуйте другую песню.\n\nDebug: {str(e)[:100]}")

# Добавьте остальные функции (start, lang и т.д.) из предыдущего кода
