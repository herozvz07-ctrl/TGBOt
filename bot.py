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

# Хранилища
user_data = {}
user_lang = {}

MESSAGES = {
    'RU': {
        'start': "<b>💎 Добро пожаловать!</b>\n\nПришли мне ссылку или название песни. Я скачаю всё быстро и без рекламы.",
        'sub': "❌ <b>Доступ ограничен!</b>\nПодпишитесь на канал, чтобы продолжить:",
        'search': "🔎 Ищу: <i>{}</i>...",
        'found': "<b>Выберите вариант:</b>",
        'downloading': "🚀 Загрузка... Пожалуйста, подождите",
        'top': "🔥 ТОП Хитов",
        'lang': "⚙️ Язык / Language",
        'choose_lang': "Выберите язык:",
        'back': "⬅️ Назад"
    },
    'EN': {
        'start': "<b>💎 Welcome!</b>\n\nSend me a link or song title. I will download it fast and clean.",
        'sub': "❌ <b>Access denied!</b>\nPlease subscribe to the channel:",
        'search': "🔎 Searching: <i>{}</i>...",
        'found': "<b>Choose an option:</b>",
        'downloading': "🚀 Downloading... Please wait",
        'top': "🔥 Top Hits",
        'lang': "⚙️ Language",
        'choose_lang': "Choose language:",
        'back': "⬅️ Back"
    }
}

# --- ФУНКЦИИ ---
def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(REQUIRED_CHANNEL, user_id).status
        return status in ['member', 'administrator', 'creator']
    except: return True

def get_lang(uid):
    return user_lang.get(uid, 'RU')

def main_menu(uid):
    lang = get_lang(uid)
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(MESSAGES[lang]['top'], callback_data="btn_top"),
        types.InlineKeyboardButton(MESSAGES[lang]['lang'], callback_data="btn_lang")
    )
    return markup

# --- СКАЧИВАНИЕ (С ОБХОДОМ БЛОКИРОВКИ) ---
def download_media(query, mode='video'):
    file_id = str(uuid.uuid4())[:8]
    if not os.path.exists('downloads'): os.makedirs('downloads')
    
    # Продвинутые настройки для обхода "Sign in to confirm"
    ydl_opts = {
        'outtmpl': f'downloads/{file_id}.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'source_address': '0.0.0.0', # Помогает с IP
        # Имитируем реальные клиенты
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
                'player_skip': ['webpage', 'configs']
            }
        },
        'user_agent': 'Mozilla/5.0 (Android 14; Mobile; rv:128.0) Gecko/128.0 Firefox/128.0',
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
        ydl_opts.update({'format': 'best[ext=mp4]/best'})

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=True)
        if 'entries' in info: info = info['entries'][0]
        fname = ydl.prepare_filename(info)
        if mode == 'audio': fname = os.path.splitext(fname)[0] + ".mp3"
        return fname, info.get('title', 'Media')

# --- HANDLERS ---
@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    lang = get_lang(uid)
    if not is_subscribed(uid):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("➕ Subscribe", url=f"https://t.me/{REQUIRED_CHANNEL[1:]}"))
        bot.send_message(message.chat.id, MESSAGES[lang]['sub'], reply_markup=markup)
        return
    bot.send_message(message.chat.id, MESSAGES[lang]['start'], reply_markup=main_menu(uid))

@bot.callback_query_handler(func=lambda call: call.data.startswith('btn_'))
def handle_menu(call):
    uid = call.from_user.id
    lang = get_lang(uid)
    if call.data == "btn_lang":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Русский 🇷🇺", callback_data="set_RU"),
                   types.InlineKeyboardButton("English 🇺🇸", callback_data="set_EN"))
        bot.edit_message_text(MESSAGES[lang]['choose_lang'], call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif call.data == "btn_top":
        handle_search(call.message, "Top Music Hits 2025")

@bot.callback_query_handler(func=lambda call: call.data.startswith('set_'))
def change_lang(call):
    new_lang = call.data.split('_')[1]
    user_lang[call.from_user.id] = new_lang
    # Полное обновление меню после смены языка
    bot.edit_message_text(MESSAGES[new_lang]['start'], call.message.chat.id, call.message.message_id, reply_markup=main_menu(call.from_user.id))

@bot.message_handler(func=lambda m: not m.text.startswith('/'))
def on_text(message):
    uid = message.from_user.id
    lang = get_lang(uid)
    if not is_subscribed(uid): return
    
    text = message.text.strip()
    if "tiktok.com" in text or "instagram.com" in text or "youtu" in text:
        link_id = str(uuid.uuid4())[:8]
        user_data[link_id] = text
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎬 Video", callback_data=f"vid_{link_id}"),
                   types.InlineKeyboardButton("🎵 MP3", callback_data=f"aud_{link_id}"))
        bot.reply_to(message, "Format:", reply_markup=markup)
    else:
        handle_search(message, text)

def handle_search(message, query):
    lang = get_lang(message.chat.id if message.chat else message.from_user.id)
    msg = bot.send_message(message.chat.id, MESSAGES[lang]['search'].format(query))
    try:
        # Поиск через мобильный клиент
        search_opts = {'quiet': True, 'extract_flat': True, 'extractor_args': {'youtube': {'player_client': ['android']}}}
        with YoutubeDL(search_opts) as ydl:
            res = ydl.extract_info(f"ytsearch8:{query}", download=False).get('entries', [])
        
        if not res:
            bot.edit_message_text("❌ Not found.", message.chat.id, msg.message_id)
            return

        markup = types.InlineKeyboardMarkup()
        btns = [types.InlineKeyboardButton(f"[{i+1}]", callback_data=f"dl_{str(uuid.uuid4())[:8]}") for i in range(len(res))]
        for i, b in enumerate(btns): user_data[b.callback_data.split('_')[1]] = res[i]['url']
        
        for i in range(0, len(btns), 2): markup.add(*btns[i:i+2])
        
        output = f"<b>{MESSAGES[lang]['found']}</b>\n\n"
        for i, e in enumerate(res, 1): output += f"{i}. {e['title'][:55]}\n"
        bot.edit_message_text(output, message.chat.id, msg.message_id, reply_markup=markup)
    except Exception as e:
        bot.send_message(message.chat.id, f"Search Error: {e}")

@bot.callback_query_handler(func=lambda call: call.data.split('_')[0] in ['vid', 'aud', 'dl'])
def on_download(call):
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
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
    
