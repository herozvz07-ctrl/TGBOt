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

# Хранилище данных (в памяти)
user_data = {}
user_lang = {} # Хранение языка пользователя

# Тексты на двух языках
MESSAGES = {
    'RU': {
        'start': "<b>💎 Добро пожаловать!</b>\n\nЯ помогу тебе скачать музыку и видео без водяных знаков.\nПришли мне ссылку или название песни.",
        'sub': "❌ <b>Доступ ограничен!</b>\nПожалуйста, подпишитесь на наш канал, чтобы использовать бота:",
        'search': "🔎 Ищу: <i>{}</i>...",
        'found': "<b>Найдено несколько вариантов:</b>",
        'downloading': "🚀 Загрузка... Пожалуйста, подождите",
        'top': "🔥 ТОП Хитов",
        'lang': "⚙️ Язык / Language",
        'choose_lang': "Выберите язык / Choose language:"
    },
    'EN': {
        'start': "<b>💎 Welcome!</b>\n\nI can help you download music and videos without watermarks.\nSend me a link or song name.",
        'sub': "❌ <b>Access denied!</b>\nPlease subscribe to our channel to use the bot:",
        'search': "🔎 Searching: <i>{}</i>...",
        'found': "<b>Search results:</b>",
        'downloading': "🚀 Downloading... Please wait",
        'top': "🔥 Top Hits",
        'lang': "⚙️ Language",
        'choose_lang': "Choose language:"
    }
}

# --- ПРОВЕРКА ПОДПИСКИ ---
def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(REQUIRED_CHANNEL, user_id).status
        return status in ['member', 'administrator', 'creator']
    except:
        return True

def get_lang(uid):
    return user_lang.get(uid, 'RU')

# --- КЛАВИАТУРЫ ---
def main_menu(uid):
    lang = get_lang(uid)
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_top = types.InlineKeyboardButton(MESSAGES[lang]['top'], callback_data="btn_top")
    btn_lang = types.InlineKeyboardButton(MESSAGES[lang]['lang'], callback_data="btn_lang")
    markup.add(btn_top, btn_lang)
    return markup

def sub_markup(lang):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ Subscribe", url=f"https://t.me/{REQUIRED_CHANNEL[1:]}"))
    return markup

# --- СКАЧИВАНИЕ ---
def download_media(query, mode='video'):
    file_id = str(uuid.uuid4())[:8]
    ydl_opts = {
        'outtmpl': f'downloads/{file_id}.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        # Обход блокировки YouTube (User-Agent)
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
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
    else:
        # Для видео используем формат, который чаще всего доступен без куки
        ydl_opts.update({'format': 'best[ext=mp4]/best'})

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=True)
        if 'entries' in info: info = info['entries'][0]
        fname = ydl.prepare_filename(info)
        if mode == 'audio': fname = os.path.splitext(fname)[0] + ".mp3"
        return fname, info.get('title', 'Media')

# --- ОБРАБОТЧИКИ ---
@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    lang = get_lang(uid)
    if not is_subscribed(uid):
        bot.send_message(message.chat.id, MESSAGES[lang]['sub'], reply_markup=sub_markup(lang))
        return
    bot.send_message(message.chat.id, MESSAGES[lang]['start'], reply_markup=main_menu(uid))

@bot.callback_query_handler(func=lambda call: call.data.startswith('btn_'))
def menu_callbacks(call):
    uid = call.from_user.id
    lang = get_lang(uid)
    
    if call.data == "btn_lang":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Русский 🇷🇺", callback_data="set_RU"),
                   types.InlineKeyboardButton("English 🇺🇸", callback_data="set_EN"))
        bot.edit_message_text(MESSAGES[lang]['choose_lang'], call.message.chat.id, call.message.message_id, reply_markup=markup)
    
    elif call.data == "btn_top":
        # Имитируем поиск топа
        handle_search(call.message, "Top Hits 2025 World", is_top=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('set_'))
def set_language(call):
    lang = call.data.split('_')[1]
    user_lang[call.from_user.id] = lang
    bot.edit_message_text("✅ Language updated!", call.message.chat.id, call.message.message_id)
    start(call.message)

@bot.message_handler(func=lambda m: not m.text.startswith('/'))
def handle_text(message):
    uid = message.from_user.id
    lang = get_lang(uid)
    if not is_subscribed(uid):
        bot.send_message(message.chat.id, MESSAGES[lang]['sub'], reply_markup=sub_markup(lang))
        return

    text = message.text.strip()
    if any(d in text for d in ["tiktok.com", "instagram.com", "youtube.com", "youtu.be"]):
        # Обработка ссылки
        link_id = str(uuid.uuid4())[:8]
        user_data[link_id] = text
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎬 Video", callback_data=f"vid_{link_id}"),
                   types.InlineKeyboardButton("🎵 MP3", callback_data=f"aud_{link_id}"))
        bot.reply_to(message, "Format:", reply_markup=markup)
    else:
        handle_search(message, text)

def handle_search(message, query, is_top=False):
    lang = get_lang(message.chat.id)
    status = bot.send_message(message.chat.id, MESSAGES[lang]['search'].format(query))
    try:
        with YoutubeDL({'quiet': True, 'extract_flat': True, 'user_agent': 'Mozilla/5.0...'}) as ydl:
            res = ydl.extract_info(f"ytsearch8:{query}", download=False).get('entries', [])
        
        if not res:
            bot.edit_message_text("❌ Nothing found.", message.chat.id, status.message_id)
            return

        markup = types.InlineKeyboardMarkup()
        # Сетка кнопок по 2 в ряд для красивого вида
        btns = []
        for i, entry in enumerate(res, 1):
            rid = str(uuid.uuid4())[:8]
            user_data[rid] = entry['url']
            btns.append(types.InlineKeyboardButton(f"[{i}]", callback_data=f"dl_{rid}"))
        
        # Группируем кнопки по 2
        for i in range(0, len(btns), 2):
            markup.add(*btns[i:i+2])

        text = MESSAGES[lang]['found'] + "\n\n"
        for i, entry in enumerate(res, 1):
            text += f"{i}. {entry['title'][:50]}\n"
        
        bot.edit_message_text(text, message.chat.id, status.message_id, reply_markup=markup)
    except Exception as e:
        bot.send_message(message.chat.id, f"Error: {e}")

@bot.callback_query_handler(func=lambda call: call.data.split('_')[0] in ['vid', 'aud', 'dl'])
def download_callback(call):
    prefix, data_id = call.data.split('_')
    url = user_data.get(data_id)
    lang = get_lang(call.from_user.id)
    if not url: return

    bot.edit_message_text(MESSAGES[lang]['downloading'], call.message.chat.id, call.message.message_id)
    try:
        mode = 'audio' if prefix in ['aud', 'dl'] else 'video'
        fpath, title = download_media(url, mode=mode)
        with open(fpath, 'rb') as f:
            if mode == 'audio': bot.send_audio(call.message.chat.id, f, caption=f"✅ {title}")
            else: bot.send_video(call.message.chat.id, f, caption=f"✅ {title}")
        os.remove(fpath)
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception as e:
        bot.send_message(call.message.chat.id, f"Download Error: {e}")

# --- ВЕБХУК ---
@app.route('/' + TOKEN, methods=['POST'])
def getMessage():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "!", 200

@app.route("/")
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_URL}/{TOKEN}", drop_pending_updates=True)
    return "Статус: Ок", 200

if __name__ == "__main__":
    if not os.path.exists('downloads'): os.makedirs('downloads')
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
