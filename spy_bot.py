from dotenv import load_dotenv
import os

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
import logging
import random
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# Enable logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Game State ---
games = {}  # {chat_id: {players: {}, state: 'waiting'/'started', location: '...', spy: user_id}}

# --- Sample Locations List ---
locations = [
    "Beach", "Hospital", "Airport", "School", "Library", "Cinema", "Restaurant", "Museum", "Zoo"
]

# --- Commands ---
def start(update: Update, context: CallbackContext):
    update.message.reply_text("Welcome to 🕵️ Spy Game Bot! Use /help to see how to play.")

def help_command(update: Update, context: CallbackContext):
    update.message.reply_text("🕹 How to Play:\n1 spy among civilians.\nAll civilians get same location.\nSpy doesn't.\nDiscuss and vote who’s the spy!\nUse /newgame to start.")

def rules(update: Update, context: CallbackContext):
    update.message.reply_text("📜 Rules:\n- One person is a spy, others are civilians.\n- Civilians know a secret location.\n- Spy doesn't know and must pretend.\n- After discussion, everyone votes to catch the spy!")

def newgame(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    games[chat_id] = {'players': {}, 'state': 'waiting', 'location': None, 'spy': None}
    update.message.reply_text("🆕 New game started! Players, join using /join")

def join(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    user = update.effective_user
    game = games.get(chat_id)

    if not game:
        update.message.reply_text("❌ No active game. Use /newgame to start one.")
        return

    if game['state'] != 'waiting':
        update.message.reply_text("🚫 Game already started.")
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
    update.message.reply_text("🧑‍🤝‍🧑 Players:\n" + "\n".join(names))

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

    for user_id in players:
        if user_id == spy:
            context.bot.send_message(chat_id=user_id, text="🕵️ You are the SPY! Try to guess the location.")
        else:
            context.bot.send_message(chat_id=user_id, text=f"🧭 You are a civilian.\nLocation: *{location}*", parse_mode='Markdown')

    update.message.reply_text("🎮 Game started! Discuss in group and then use /vote")

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
    update.message.reply_text("🗳 Voting not implemented yet. (Coming soon...)")

def endgame(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    if chat_id in games:
        del games[chat_id]
        update.message.reply_text("🛑 Game ended.")
    else:
        update.message.reply_text("❌ No game to end.")

# --- Main Function ---
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    # Register handlers
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

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
