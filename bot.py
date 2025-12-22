import os
import telebot
import uuid
from telebot import types
from yt_dlp import YoutubeDL
from flask import Flask, request

# --- НАСТРОЙКИ ---
TOKEN = "7284903125:AAHrn9g2xWH4ydcGfGgfV6l8dyn0zhg22qM"
REQUIRED_CHANNEL = "@your_channel_username" # Замените на ваш канал (с @)
# ВАЖНО: Бот должен быть администратором в этом канале!

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
app = Flask(__name__)

DOWNLOAD_DIR = "downloads"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# Временное хранилище
user_data = {}

# --- ПРОВЕРКА ПОДПИСКИ ---
def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(REQUIRED_CHANNEL, user_id).status
        return status in ['member', 'administrator', 'creator']
    except Exception:
        return True # Если не удается проверить, пропускаем (чтобы не ломать бота)

def sub_keyboard():
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton("➕ Подписаться на канал", url=f"https://t.me/{REQUIRED_CHANNEL[1:]}")
    check = types.InlineKeyboardButton("✅ Я подписался", callback_data="check_sub")
    markup.add(btn)
    markup.add(check)
    return markup

# --- ФУНКЦИИ СКАЧИВАНИЯ ---
def download_media(query, mode='video', is_search=False):
    file_id = str(uuid.uuid4())[:8]
    
    # Современные опции для удаления водяных знаков и макс. качества
    ydl_opts = {
        'outtmpl': f'{DOWNLOAD_DIR}/{file_id}.%(ext)s',
        'quiet': True,
        'noplaylist': True,
    }

    if mode == 'audio':
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
        })
        if is_search:
            query = f"ytsearch5:{query}"
    else:
        # Автоматический подбор лучшего видео без водяных знаков (для TikTok/Reels)
        ydl_opts.update({'format': 'bestvideo+bestaudio/best'})

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=True)
        if 'entries' in info:
            info = info['entries'][0]
        
        filename = ydl.prepare_filename(info)
        if mode == 'audio':
            filename = os.path.splitext(filename)[0] + ".mp3"
        return filename, info.get('title', 'Unknown')

# --- КОМАНДЫ ---
@bot.message_handler(commands=['start'])
def start(message):
    if not is_subscribed(message.from_user.id):
        bot.send_message(message.chat.id, f"<b>Привет!</b> Чтобы пользоваться ботом, подпишись на наш канал:", reply_markup=sub_keyboard())
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔥 ТОП Хитов", "⚙️ Настройки")
    
    welcome_text = (
        "<b>💎 Профессиональный Загрузчик</b>\n\n"
        "📥 <b>Как скачивать:</b>\n"
        "Просто отправь ссылку из TikTok, Reels или YouTube.\n\n"
        "🔎 <b>Как найти музыку:</b>\n"
        "Напиши название песни или слова из неё.\n\n"
        "⚡️ <i>Работает быстро и без водяных знаков!</i>"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🔥 ТОП Хитов")
def top_hits(message):
    bot.send_message(message.chat.id, "📊 Собираю актуальные хиты этой недели...")
    # Поиск популярных треков через YouTube Music Chart
    handle_text_search(message, "Top Hits 2025")

# --- ОБРАБОТКА ССЫЛОК И ТЕКСТА ---
@bot.message_handler(func=lambda m: not m.text.startswith('/'))
def handle_all(message):
    if not is_subscribed(message.from_user.id):
        bot.send_message(message.chat.id, "❌ Сначала подпишитесь!", reply_markup=sub_keyboard())
        return

    text = message.text.strip()
    
    # Проверка на ссылку
    if any(d in text for d in ["tiktok.com", "instagram.com", "youtube.com", "youtu.be"]):
        link_id = str(uuid.uuid4())[:8]
        user_data[link_id] = text
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🎬 Видео (HD)", callback_data=f"vid_{link_id}"),
            types.InlineKeyboardButton("🎵 Аудио (MP3)", callback_data=f"aud_{link_id}"),
            types.InlineKeyboardButton("🔍 Найти оригинал", callback_data=f"src_{link_id}")
        )
        bot.reply_to(message, "<b>Медиа файл обнаружен!</b>\nВыберите формат загрузки:", reply_markup=markup)
    else:
        handle_text_search(message, text)

def handle_text_search(message, query):
    status = bot.send_message(message.chat.id, "🔎 <i>Ищу лучшие варианты...</i>")
    try:
        with YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
            results = ydl.extract_info(f"ytsearch8:{query}", download=False).get('entries', [])
        
        if not results:
            bot.edit_message_text("❌ Ничего не найдено.", message.chat.id, status.message_id)
            return

        markup = types.InlineKeyboardMarkup()
        response = f"<b>🎶 Результаты поиска:</b>\n\n"
        
        for i, entry in enumerate(results, 1):
            res_id = str(uuid.uuid4())[:8]
            user_data[res_id] = entry.get('url')
            dur = entry.get('duration')
            time = f"{int(dur//60)}:{int(dur%60):02d}" if dur else "0:00"
            
            response += f"{i}. <b>{entry.get('title')[:40]}</b> — <code>[{time}]</code>\n"
            markup.add(types.InlineKeyboardButton(f"{i}", callback_data=f"dl_{res_id}"))
            
        bot.edit_message_text(response, message.chat.id, status.message_id, reply_markup=markup)
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка поиска: {e}")

# --- CALLBACK HANDLER ---
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data == "check_sub":
        if is_subscribed(call.from_user.id):
            bot.answer_callback_query(call.id, "✅ Спасибо за подписку!")
            start(call.message)
        else:
            bot.answer_callback_query(call.id, "❌ Вы еще не подписались!", show_alert=True)
        return

    # Логика скачивания
    prefix = call.data.split('_')[0]
    data_id = call.data.split('_')[1]
    url = user_data.get(data_id)

    if not url:
        bot.answer_callback_query(call.id, "Ошибка: данные устарели.")
        return

    bot.edit_message_text("🚀 <b>Начинаю загрузку...</b>", call.message.chat.id, call.message.message_id)
    
    try:
        mode = 'audio' if prefix in ['aud', 'dl', 'src'] else 'video'
        file_path, title = download_media(url, mode=mode)
        
        with open(file_path, 'rb') as f:
            if mode == 'audio':
                bot.send_audio(call.message.chat.id, f, caption=f"✅ <b>{title}</b>\n@YourBot")
            else:
                bot.send_video(call.message.chat.id, f, caption=f"✅ <b>{title}</b>\n@YourBot")
        
        os.remove(file_path)
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Ошибка: {e}")

# --- RENDER WEBHOOK SERVER ---
@app.route('/' + TOKEN, methods=['POST'])
def getMessage():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "!", 200

@app.route("/")
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url='ВАШ_URL_НА_RENDER/' + TOKEN)
    return "Бот активен!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
          
