import os
import telebot
import uuid
import subprocess
from telebot import types
from yt_dlp import YoutubeDL
from flask import Flask, request

# АВТО-УСТАНОВКА FFMPEG (для Render)
try:
    subprocess.run(["ffmpeg", "-version"], check=True, capture_output=True)
except:
    print("Установка ffmpeg...")
    os.system("apt-get update && apt-get install -y ffmpeg")

# --- НАСТРОЙКИ ---
# Пробуем взять из переменных Render, если нет — используйте строку
TOKEN = os.environ.get("BOT_TOKEN") 
if not TOKEN or TOKEN == "ВАШ_ТОКЕН":
    TOKEN = "7284903125:AAHrn9g2xWH4ydcGfGgfV6l8dyn0zhg22qM"

REQUIRED_CHANNEL = "@ttimperia" # ЗАМЕНИТЕ НА СВОЙ

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
app = Flask(__name__)

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

# --- СКАЧИВАНИЕ ---
def download_media(query, mode='video', is_search=False):
    file_id = str(uuid.uuid4())[:8]
    ydl_opts = {
        'outtmpl': f'{DOWNLOAD_DIR}/{file_id}.%(ext)s',
        'quiet': True,
        'no_warnings': True,
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

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔥 ТОП Хитов")
    bot.send_message(message.chat.id, "<b>Привет!</b> Пришли ссылку или название песни.", reply_markup=markup)

@bot.message_handler(func=lambda m: any(d in m.text for d in ["tiktok.com", "instagram.com", "youtube.com", "youtu.be"]))
def handle_link(message):
    link_id = str(uuid.uuid4())[:8]
    user_data[link_id] = message.text.strip()
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🎬 Видео", callback_data=f"vid_{link_id}"),
               types.InlineKeyboardButton("🎵 Аудио", callback_data=f"aud_{link_id}"))
    bot.reply_to(message, "Выберите формат:", reply_markup=markup)

@bot.message_handler(func=lambda m: not m.text.startswith('/'))
def search_music(message):
    query = message.text.strip()
    if query == "🔥 ТОП Хитов": query = "Top Music 2025"
    
    status = bot.send_message(message.chat.id, "🔎 Поиск...")
    try:
        with YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
            res = ydl.extract_info(f"ytsearch5:{query}", download=False).get('entries', [])
        
        markup = types.InlineKeyboardMarkup()
        for i, entry in enumerate(res, 1):
            rid = str(uuid.uuid4())[:8]
            user_data[rid] = entry['url']
            markup.add(types.InlineKeyboardButton(f"{i}. {entry['title'][:30]}", callback_data=f"dl_{rid}"))
        bot.edit_message_text(f"Результаты для: {query}", message.chat.id, status.message_id, reply_markup=markup)
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка: {e}")

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    prefix, data_id = call.data.split('_')
    url = user_data.get(data_id)
    if not url: return

    bot.edit_message_text("🚀 Загрузка...", call.message.chat.id, call.message.message_id)
    try:
        mode = 'audio' if prefix in ['aud', 'dl'] else 'video'
        fpath, title = download_media(url, mode=mode)
        with open(fpath, 'rb') as f:
            if mode == 'audio': bot.send_audio(call.message.chat.id, f, caption=title)
            else: bot.send_video(call.message.chat.id, f, caption=title)
        os.remove(fpath)
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception as e:
        bot.send_message(call.message.chat.id, f"Ошибка: {e}")

# --- FLASK SERVER ДЛЯ RENDER ---
@app.route('/' + TOKEN, methods=['POST'])
def getMessage():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "!", 200

@app.route("/")
def webhook():
    bot.remove_webhook()
    # Замените на вашу ссылку от Render
    bot.set_webhook(url='https://ВАШ-АДРЕС.onrender.com/' + TOKEN)
    return "Статус: Ок", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
    
