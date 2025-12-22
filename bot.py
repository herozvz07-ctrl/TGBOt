import os
import telebot
import uuid
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
EMOJI_NUMS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]

MESSAGES = {
    'RU': {
        'start': "<b>💎 Музыкальный Бот</b>\n\nПришли название песни или исполнителя. Я найду музыку в SoundCloud и пришлю её тебе в MP3.",
        'sub': "❌ <b>Доступ закрыт!</b>\nСначала подпишись на наш канал:",
        'search': "🔎 Ищу: <i>{}</i> в SoundCloud...",
        'found': "<b>Найдено! Выберите трек:</b>",
        'downloading': "🚀 Загрузка...",
        'top': "🔥 ТОП Хитов",
        'lang': "⚙️ Язык",
        'choose_lang': "Выберите язык:",
    },
    'EN': {
        'start': "<b>💎 Music Downloader</b>\n\nSend me a song title or artist.",
        'sub': "❌ <b>Access Denied!</b>",
        'search': "🔎 Searching: <i>{}</i> on SoundCloud...",
        'found': "<b>Found! Choose a track:</b>",
        'downloading': "🚀 Downloading...",
        'top': "🔥 Top Hits",
        'lang': "⚙️ Language",
        'choose_lang': "Choose language:",
    }
}

def is_subscribed(user_id):
    try:
        return bot.get_chat_member(REQUIRED_CHANNEL, user_id).status in ['member','administrator','creator']
    except:
        return True

def get_lang(uid):
    return user_lang.get(uid, 'RU')

def main_menu(uid):
    lang = get_lang(uid)
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton(MESSAGES[lang]['top'], callback_data="btn_top"),
        types.InlineKeyboardButton(MESSAGES[lang]['lang'], callback_data="btn_lang")
    )
    return kb

# --- DOWNLOAD ---
def download_music(url):
    file_id = str(uuid.uuid4())[:8]
    os.makedirs('downloads', exist_ok=True)

    ydl_opts = {
        'outtmpl': f'downloads/{file_id}.%(ext)s',
        'quiet': True,
        'format': 'bestaudio',
        'allowed_extractors': ['soundcloud'],
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        name = ydl.prepare_filename(info)
        return os.path.splitext(name)[0] + ".mp3", info.get('title', 'Music')

@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    lang = get_lang(uid)

    if not is_subscribed(uid):
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("➕ Подписаться", url=f"https://t.me/{REQUIRED_CHANNEL[1:]}"))
        bot.send_message(message.chat.id, MESSAGES[lang]['sub'], reply_markup=kb)
        return

    bot.send_message(message.chat.id, MESSAGES[lang]['start'], reply_markup=main_menu(uid))

def handle_search(message, query):
    lang = get_lang(message.chat.id)
    msg = bot.send_message(message.chat.id, MESSAGES[lang]['search'].format(query))

    with YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
        res = ydl.extract_info(f"scsearch10:{query}", download=False).get('entries', [])

    markup = types.InlineKeyboardMarkup()
    text = f"<b>{MESSAGES[lang]['found']}</b>\n\n"
    btns = []
    idx = 0

    for e in res:
        url = e.get('url', '')
        if not url.startswith("https://soundcloud.com/"):
            continue

        rid = str(uuid.uuid4())[:8]
        user_data[rid] = url

        btns.append(types.InlineKeyboardButton(EMOJI_NUMS[idx], callback_data=f"dl_{rid}"))
        text += f"{EMOJI_NUMS[idx]} {e.get('title','')[:50]}\n"
        idx += 1
        if idx >= 9:
            break

    if not btns:
        bot.edit_message_text("❌ SoundCloud треки не найдены.", message.chat.id, msg.message_id)
        return

    for i in range(0, len(btns), 3):
        markup.add(*btns[i:i+3])

    bot.edit_message_text(text, message.chat.id, msg.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("dl_"))
def dl(c):
    url = user_data.get(c.data.split("_")[1])
    bot.edit_message_text("⏬ Загрузка...", c.message.chat.id, c.message.message_id)

    try:
        f, title = download_music(url)
        with open(f, 'rb') as a:
            bot.send_audio(c.message.chat.id, a, caption=title)
        os.remove(f)
    except Exception as e:
        bot.send_message(c.message.chat.id, f"❌ {e}")

@bot.message_handler(func=lambda m: not m.text.startswith('/'))
def msg(m):
    handle_search(m, m.text)

# --- WEB ---
@app.route('/' + TOKEN, methods=['POST'])
def hook():
    bot.process_new_updates([telebot.types.Update.de_json(request.data.decode())])
    return "OK"

@app.route('/')
def home():
    bot.remove_webhook()
    bot.set_webhook(f"{RENDER_URL}/{TOKEN}")
    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
