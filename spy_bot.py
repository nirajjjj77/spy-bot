# Upgraded AgentAmongUs Bot (Python-Telegram-Bot v13.15 compatible)
# Improvements: Voting, UX, error checks, multiple games, persistent game logic

from dotenv import load_dotenv
import os
import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, CallbackQueryHandler

# Load environment
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN is missing. Please set it in environment.")

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Game state
# Structure: {chat_id: {players: {user_id: name}, state: 'waiting'/'started', location: str, spy: user_id, votes: {user_id: voted_id}}}
games = {}
locations = ["Beach", "Hospital", "Airport", "School", "Library", "Cinema", "Restaurant", "Museum", "Zoo"]

# --- Command Handlers ---
def start(update: Update, context: CallbackContext):
    update.message.reply_text("\U0001F575\uFE0F *Welcome to AgentAmongUs!*\nUse /help to know how to play.", parse_mode='Markdown')

def help_command(update: Update, context: CallbackContext):
    update.message.reply_text("\U0001F3AE *How to Play:*\n1 spy among civilians.\nCivilians get same location.\nSpy doesn’t.\nDiscuss and /vote to find the spy!\n/start to begin, /join to enter, /begin to start the game.", parse_mode='Markdown')

def rules(update: Update, context: CallbackContext):
    update.message.reply_text("\U0001F4DC *Rules:*\n- One spy, others are civilians\n- Civilians know a location\n- Spy pretends and guesses\n- Vote to catch the spy!", parse_mode='Markdown')

def newgame(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    games[chat_id] = {'players': {}, 'state': 'waiting', 'location': None, 'spy': None, 'votes': {}}
    update.message.reply_text("\U0001F195 *New game created!*\nPlayers, use /join to participate.", parse_mode='Markdown')

def join(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    user = update.effective_user
    game = games.get(chat_id)

    if not game:
        update.message.reply_text("❌ No active game. Use /newgame to start one.")
        return
    if game['state'] != 'waiting':
        update.message.reply_text("⛔ Game already started.")
        return
    if user.id in game['players']:
        update.message.reply_text("⚠️ You already joined.")
        return

    game['players'][user.id] = user.first_name
    update.message.reply_text(f"✅ {user.first_name} joined the game!")

def leave(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    user = update.effective_user
    game = games.get(chat_id)

    if game and user.id in game['players']:
        del game['players'][user.id]
        update.message.reply_text(f"👋 {user.first_name} left the game.")
    else:
        update.message.reply_text("⚠️ You’re not in the game.")

def players(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    game = games.get(chat_id)
    if not game:
        update.message.reply_text("❌ No game in progress.")
        return
    names = list(game['players'].values())
    update.message.reply_text("\U0001F465 *Players:*\n" + "\n".join(names), parse_mode='Markdown')

def begin(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    game = games.get(chat_id)

    if not game or game['state'] != 'waiting':
        update.message.reply_text("⚠️ No game to begin.")
        return

    players = list(game['players'].keys())
    if len(players) < 3:
        update.message.reply_text("🚨 At least 3 players needed.")
        return

    spy = random.choice(players)
    location = random.choice(locations)
    game['state'] = 'started'
    game['location'] = location
    game['spy'] = spy
    game['votes'] = {}

    for uid in players:
        if uid == spy:
            context.bot.send_message(uid, "🕵️ You are the SPY! Try to blend in and guess the location.")
        else:
            context.bot.send_message(uid, f"🧭 You are a civilian.\nLocation: *{location}*", parse_mode='Markdown')

    update.message.reply_text("🎮 *Game started!* Discuss in group and use /vote to catch the spy.", parse_mode='Markdown')

def location_command(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    user_id = update.effective_user.id
    game = games.get(chat_id)

    if not game or game['state'] != 'started':
        update.message.reply_text("❌ Game hasn’t started yet.")
        return

    if user_id == game['spy']:
        update.message.reply_text("🤫 You're the spy. No location for you.")
    elif user_id in game['players']:
        update.message.reply_text(f"📍 Location: {game['location']}")
    else:
        update.message.reply_text("⚠️ You’re not in the game.")

def vote(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    game = games.get(chat_id)
    if not game or game['state'] != 'started':
        update.message.reply_text("❌ No active game.")
        return

    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"vote:{uid}")]
        for uid, name in game['players'].items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("🗳 *Who do you think is the spy?*", reply_markup=reply_markup, parse_mode='Markdown')

def vote_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    game = games.get(chat_id)

    if not game or user_id not in game['players']:
        query.answer("You’re not in the game.")
        return

    voted_id = int(query.data.split(":" )[1])
    game['votes'][user_id] = voted_id
    query.answer("Vote registered.")

    total = len(game['players'])
    if len(game['votes']) == total:
        counts = {}
        for v in game['votes'].values():
            counts[v] = counts.get(v, 0) + 1
        max_voted = max(counts, key=counts.get)
        name = game['players'].get(max_voted, "Unknown")
        if max_voted == game['spy']:
            msg = f"✅ {name} was the spy and was caught! Civilians win!"
        else:
            spy_name = game['players'].get(game['spy'], "Unknown")
            msg = f"❌ {name} was innocent. The spy was {spy_name}. Spy wins!"
        context.bot.send_message(chat_id=chat_id, text=msg)
        del games[chat_id]

def endgame(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    if chat_id in games:
        del games[chat_id]
        update.message.reply_text("🛑 Game ended.")
    else:
        update.message.reply_text("❌ No game to end.")

# --- Main ---
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("rules", rules))
    dp.add_handler(CommandHandler("newgame", newgame))
    dp.add_handler(CommandHandler("join", join))
    dp.add_handler(CommandHandler("leave", leave))
    dp.add_handler(CommandHandler("players", players))
    dp.add_handler(CommandHandler("begin", begin))
    dp.add_handler(CommandHandler("location", location_command))
    dp.add_handler(CommandHandler("vote", vote))
    dp.add_handler(CommandHandler("endgame", endgame))
    dp.add_handler(CallbackQueryHandler(vote_callback, pattern=r"^vote:"))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
