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

MESSAGES = {
    'RU': {
        'start': "<b>💎 Меню обновлено!</b>\nВыберите действие или пришлите название.",
        'sub': "❌ Подпишитесь на канал:",
        'search': "🔎 Ищу: <i>{}</i>...",
        'found': "<b>Результаты поиска:</b>",
        'downloading': "🚀 Загрузка началась...",
        'top': "🔥 ТОП Хитов",
        'lang': "⚙️ Язык / Language",
        'choose_lang': "Выберите язык:",
    },
    'EN': {
        'start': "<b>💎 Menu updated!</b>\nChoose an action or send a title.",
        'sub': "❌ Subscribe to the channel:",
        'search': "🔎 Searching: <i>{}</i>...",
        'found': "<b>Search results:</b>",
        'downloading': "🚀 Download started...",
        'top': "🔥 Top Hits",
        'lang': "⚙️ Language",
        'choose_lang': "Choose language:",
    }
}

def get_lang(uid): return user_lang.get(uid, 'RU')

def main_menu(uid):
    lang = get_lang(uid)
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(MESSAGES[lang]['top'], callback_data="btn_top"),
        types.InlineKeyboardButton(MESSAGES[lang]['lang'], callback_data="btn_lang")
    )
    return markup

# --- СКАЧИВАНИЕ (МАКСИМАЛЬНЫЙ ОБХОД) ---
def download_media(query, mode='video'):
    file_id = str(uuid.uuid4())[:8]
    if not os.path.exists('downloads'): os.makedirs('downloads')
    
    ydl_opts = {
        'outtmpl': f'downloads/{file_id}.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        # Пробуем использовать cookies.txt если ты его загрузишь на GitHub
        'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
        'format': 'bestaudio/best' if mode == 'audio' else 'best[ext=mp4]/best',
        # Использование мобильных клиентов iOS/Android для обхода капчи
        'extractor_args': {
            'youtube': {
                'player_client': ['ios', 'android'],
            }
        },
    }

    if mode == 'audio':
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=True)
        if 'entries' in info: info = info['entries'][0]
        fname = ydl.prepare_filename(info)
        if mode == 'audio': fname = os.path.splitext(fname)[0] + ".mp3"
        return fname, info.get('title', 'Media')

@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    lang = get_lang(uid)
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
        handle_search(call.message, "Top Hits 2025")

@bot.callback_query_handler(func=lambda call: call.data.startswith('set_'))
def change_lang(call):
    new_lang = call.data.split('_')[1]
    user_lang[call.from_user.id] = new_lang
    bot.edit_message_text(MESSAGES[new_lang]['start'], call.message.chat.id, call.message.message_id, reply_markup=main_menu(call.from_user.id))

def handle_search(message, query):
    lang = get_lang(message.chat.id)
    msg = bot.send_message(message.chat.id, MESSAGES[lang]['search'].format(query))
    try:
        # Поиск через iOS клиент (самый стабильный)
        with YoutubeDL({'quiet': True, 'extract_flat': True, 'extractor_args': {'youtube': {'player_client': ['ios']}}}) as ydl:
            res = ydl.extract_info(f"ytsearch8:{query}", download=False).get('entries', [])
        
        if not res:
            bot.edit_message_text("❌ Ошибка поиска.", message.chat.id, msg.message_id)
            return

        markup = types.InlineKeyboardMarkup()
        btns = []
        for i, entry in enumerate(res):
            rid = str(uuid.uuid4())[:8]
            user_data[rid] = entry['url']
            # Используем Эмодзи-цифры
            btns.append(types.InlineKeyboardButton(EMOJI_NUMS[i] if i < 8 else str(i+1), callback_data=f"dl_{rid}"))
        
        # Добавляем в ряд по 3 КНОПКИ
        for i in range(0, len(btns), 3):
            markup.add(*btns[i:i+3])
        
        output = f"<b>{MESSAGES[lang]['found']}</b>\n\n"
        for i, e in enumerate(res, 1):
            output += f"{EMOJI_NUMS[i-1] if i <= 8 else i}. {e['title'][:50]}\n"
            
        bot.edit_message_text(output, message.chat.id, msg.message_id, reply_markup=markup)
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('dl_'))
def on_download(call):
    url = user_data.get(call.data.split('_')[1])
    lang = get_lang(call.from_user.id)
    bot.edit_message_text(MESSAGES[lang]['downloading'], call.message.chat.id, call.message.message_id)
    try:
        fpath, title = download_media(url, mode='audio')
        with open(fpath, 'rb') as f:
            bot.send_audio(call.message.chat.id, f, caption=f"✅ {title}")
        os.remove(fpath)
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception as e:
        bot.send_message(call.message.chat.id, f"Ошибка скачивания: {e}")

@bot.message_handler(func=lambda m: not m.text.startswith('/'))
def txt(m): handle_search(m, m.text)

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
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
        
