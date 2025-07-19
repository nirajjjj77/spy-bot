# Upgraded AgentAmongUs Bot (Python-Telegram-Bot v13.15 compatible)
# Improvements: Voting, UX, error checks, multiple games, persistent game logic

from dotenv import load_dotenv
import os
import logging
import random
from threading import Timer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, CallbackQueryHandler, MessageHandler, Filters

# Load environment
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN is missing. Please set it in environment.")

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Game state
# Structure: {chat_id: {players: {user_id: name}, state: 'waiting'/'started', location: str, spy: user_id, votes: {user_id: voted_id}, timers: [], update, context}}
games = {}
locations = ["Beach", "Hospital", "Airport", "School", "Library", "Cinema", "Restaurant", "Museum", "Zoo"]

# --- Command Handlers ---
def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        """🕵️‍♂️ *Welcome, Agent!*  
    You've entered the world of *deception, deduction, and danger!* 🔍💣

    🎯 *Goal:* Blend in, lie smart, and expose the SPY (or hide if you are one 😏).

    🎮 Use /guide to learn the rules or /newgame to create a new mission!""",
        parse_mode='Markdown'
    )

def guide(update: Update, context: CallbackContext):
    update.message.reply_text(
        """🎮 *How to Play:*

    🕵️ There is *1 spy* and multiple civilians.
    📍 Civilians are told the same location.
    ❌ The spy does *not* know the location.

    💬 Discuss among yourselves.
    🗳️ Use /vote to identify the spy.
    🎯 Catch the spy before time runs out!

    *Commands:*
    /newgame – Start a new game session.
    /join – Join the ongoing game.
    /leave – Leave the current game.
    /players – Show current participants.
    /begin – Begin the mission (minimum 3 players).
    /location – Civilians can check their secret location.
    /vote – Vote who you think is the spy.
    /endgame – End the current game.
    /intel - Read the detailed game rules.

    _Use /start if you're new or want the intro again._""",
        parse_mode='Markdown'
    )

def intel(update: Update, context: CallbackContext):
    update.message.reply_text("\U0001F4DC *Rules:*\n- One spy, others are civilians\n- Civilians know a location\n- Spy pretends and guesses\n- Vote to catch the spy!", parse_mode='Markdown')

def newgame(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    if chat_id in games:
        update.message.reply_text("⚠️ A game is already in progress. Use /endgame to end it before starting a new one.")
        return
    games[chat_id] = {'players': {}, 'state': 'waiting', 'location': None, 'spy': None, 'votes': {}, 'timers': []}
    update.message.reply_text("🆕 *New game created!*\nPlayers, use /join to participate.", parse_mode='Markdown')

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
    if not game['players']:
        update.message.reply_text("👥 No players have joined yet.")
        return
    names = list(game['players'].values())
    update.message.reply_text("👥 *Players:*\n" + "\n".join(names), parse_mode='Markdown')

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
    game['update'] = update
    game['context'] = context

    for uid in players:
        if uid == spy:
            context.bot.send_message(uid, "🕵️ You are the SPY! Try to blend in and guess the location.")
        else:
            context.bot.send_message(uid, f"🧭 You are a civilian.\nLocation: *{location}*", parse_mode='Markdown')

    update.message.reply_text("🎮 *Game started!* Discuss in group for 5 minutes. Then voting begins.", parse_mode='Markdown')

    def trigger_vote():
        context.bot.send_message(chat_id, "🗳️ Time's up! Voting begins now.")
        vote(update, context)

    timer = Timer(300, trigger_vote)
    timer.start()
    game['timers'].append(timer)

def location_command(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    user_id = update.effective_user.id
    game = games.get(chat_id)

    if not game or game['state'] != 'started':
        update.message.reply_text("❌ Game hasn’t started yet.")
        return
    
     # Always send public confirmation message
    update.message.reply_text("📬 Location information has been sent to you privately.")

    if user_id == game['spy']:
        context.bot.send_message(chat_id=user_id, text="🤫 You are the SPY. No location for you.")
    elif user_id in game['players']:
        context.bot.send_message(chat_id=user_id, text=f"📍 Location: *{game['location']}*", parse_mode='Markdown')
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

    def timeout_vote():
        context.bot.send_message(chat_id, "⏰ Voting time is up!")
        finish_vote(chat_id, context)

    Timer(60, timeout_vote).start()

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

    if len(game['votes']) == len(game['players']):
        finish_vote(chat_id, context)
    
def finish_vote(chat_id, context):
    game = games.get(chat_id)
    if not game:
        return

    votes = game['votes']
    counts = {}
    for v in votes.values():
        counts[v] = counts.get(v, 0) + 1
    max_voted = max(counts, key=counts.get)
    name = game['players'].get(max_voted, "Unknown")

    if max_voted == game['spy']:
        msg = f"✅ {name} was the spy and was caught! Civilians win!"
        context.bot.send_message(chat_id=chat_id, text=msg)
        del games[chat_id]
    else:
        msg = f"❌ {name} was innocent. The spy was {game['players'].get(game['spy'], 'Unknown')}. Spy wins!"
        context.bot.send_message(chat_id=chat_id, text=msg)
        spy = game['spy']
        context.bot.send_message(spy, "🕵️ You've survived… now guess the location! You have 30 seconds. Reply with your guess.")

        def timeout_guess():
            context.bot.send_message(chat_id, "⏰ Spy failed to guess in time. Civilians win!")
            del games[chat_id]

        Timer(30, timeout_guess).start()
        game['awaiting_guess'] = True

# Spy guess handler

def handle_guess(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    user_id = update.effective_user.id
    game = games.get(chat_id)

    if not game or not game.get('awaiting_guess') or user_id != game['spy']:
        return

    guess = update.message.text.strip().lower()
    correct = game['location'].lower()
    if guess == correct:
        context.bot.send_message(chat_id, f"🎉 The spy guessed correctly ({guess}) and wins!")
    else:
        context.bot.send_message(chat_id, f"❌ The spy guessed {guess}, but the real location was {game['location']}. Civilians win!")
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
    dp.add_handler(CommandHandler("guide", guide))
    dp.add_handler(CommandHandler("intel", intel))
    dp.add_handler(CommandHandler("newgame", newgame))
    dp.add_handler(CommandHandler("join", join))
    dp.add_handler(CommandHandler("leave", leave))
    dp.add_handler(CommandHandler("players", players))
    dp.add_handler(CommandHandler("begin", begin))
    dp.add_handler(CommandHandler("location", location_command))
    dp.add_handler(CommandHandler("vote", vote))
    dp.add_handler(CommandHandler("endgame", endgame))
    dp.add_handler(CallbackQueryHandler(vote_callback, pattern=r"^vote:"))
    dp.add_handler(MessageHandler(Filters.text, handle_guess))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
