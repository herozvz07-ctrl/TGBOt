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

# АВТО-УСТАНОВКА FFMPEG
try:
    subprocess.run(["ffmpeg", "-version"], check=True, capture_output=True)
except:
    os.system("apt-get update && apt-get install -y ffmpeg")

DOWNLOAD_DIR = "downloads"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

user_data = {}

# --- ПРОВЕРКА ПОДПИСКИ ---
def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(REQUIRED_CHANNEL, user_id).status
        return status in ['member', 'administrator', 'creator']
    except:
        return True 

def sub_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ Подписаться на канал", url=f"https://t.me/{REQUIRED_CHANNEL[1:]}"))
    return markup

# --- СКАЧИВАНИЕ ---
def download_media(query, mode='video', is_search=False):
    file_id = str(uuid.uuid4())[:8]
    ydl_opts = {
        'outtmpl': f'{DOWNLOAD_DIR}/{file_id}.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
    }

    if mode == 'audio':
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
        if is_search: query = f"ytsearch5:{query}"
    else:
        ydl_opts.update({'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'})

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=True)
        if 'entries' in info: info = info['entries'][0]
        fname = ydl.prepare_filename(info)
        if mode == 'audio': fname = os.path.splitext(fname)[0] + ".mp3"
        return fname, info.get('title', 'Media')

# --- ОБРАБОТЧИКИ ---
@bot.message_handler(commands=['start'])
def start(message):
    if not is_subscribed(message.from_user.id):
        bot.send_message(message.chat.id, "<b>Привет!</b> Для использования бота подпишись на канал:", reply_markup=sub_markup())
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔥 ТОП Хитов")
    bot.send_message(message.chat.id, "<b>💎 Бот готов!</b>\nОтправь ссылку (TikTok, Reels, YT) или название песни.", reply_markup=markup)

@bot.message_handler(func=lambda m: any(d in m.text for d in ["tiktok.com", "instagram.com", "youtube.com", "youtu.be"]))
def handle_link(message):
    if not is_subscribed(message.from_user.id):
        bot.send_message(message.chat.id, "Сначала подпишись на канал!", reply_markup=sub_markup())
        return

    link_id = str(uuid.uuid4())[:8]
    user_data[link_id] = message.text.strip()
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🎬 Видео", callback_data=f"vid_{link_id}"),
               types.InlineKeyboardButton("🎵 Аудио", callback_data=f"aud_{link_id}"))
    bot.reply_to(message, "Что скачать?", reply_markup=markup)

@bot.message_handler(func=lambda m: not m.text.startswith('/'))
def search_music(message):
    if not is_subscribed(message.from_user.id):
        bot.send_message(message.chat.id, "Сначала подпишись на канал!", reply_markup=sub_markup())
        return

    query = message.text.strip()
    if query == "🔥 ТОП Хитов": query = "Top Hits 2025"
    
    status = bot.send_message(message.chat.id, f"🔎 Ищу: <i>{query}</i>...")
    try:
        with YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
            res = ydl.extract_info(f"ytsearch5:{query}", download=False).get('entries', [])
        
        if not res:
            bot.edit_message_text("❌ Ничего не найдено.", message.chat.id, status.message_id)
            return

        markup = types.InlineKeyboardMarkup()
        text = "<b>Найдено несколько вариантов:</b>\n\n"
        for i, entry in enumerate(res, 1):
            rid = str(uuid.uuid4())[:8]
            user_data[rid] = entry['url']
            text += f"{i}. {entry['title'][:50]}\n"
            markup.add(types.InlineKeyboardButton(f"{i}", callback_data=f"dl_{rid}"))
        
        bot.edit_message_text(text, message.chat.id, status.message_id, reply_markup=markup)
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка поиска: {e}")

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    prefix, data_id = call.data.split('_')
    url = user_data.get(data_id)
    if not url:
        bot.answer_callback_query(call.id, "Данные устарели, отправь ссылку снова.")
        return

    bot.edit_message_text("🚀 Загрузка... Пожалуйста, подождите", call.message.chat.id, call.message.message_id)
    try:
        mode = 'audio' if prefix in ['aud', 'dl'] else 'video'
        fpath, title = download_media(url, mode=mode)
        with open(fpath, 'rb') as f:
            if mode == 'audio': bot.send_audio(call.message.chat.id, f, caption=f"✅ {title}")
            else: bot.send_video(call.message.chat.id, f, caption=f"✅ {title}")
        os.remove(fpath)
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception as e:
        bot.send_message(call.message.chat.id, f"Ошибка скачивания: {e}")

# --- ВЕБХУК ---
@app.route('/' + TOKEN, methods=['POST'])
def getMessage():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "!", 200

@app.route("/")
def webhook():
    bot.remove_webhook()
    # Очищаем старые сообщения (drop_pending_updates=True)
    bot.set_webhook(url=f"{RENDER_URL}/{TOKEN}", drop_pending_updates=True)
    return "Статус: Ок", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
    
