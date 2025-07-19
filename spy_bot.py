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
locations = [
    # 🌆 City Locations
    "Bank", "Train Station", "Police Station", "Fire Station", "Shopping Mall", "Parking Garage", "Post Office", "Apartment Complex",
    "Metro Station", "Taxi Stand", "Highway Toll Booth", "Train Compartment", "Dockyard",

    # 🏫 Educational & Institutional
    "University", "Kindergarten", "Science Lab", "Art Studio", "Debate Hall",

    # 🏥 Medical / Health
    "Hospital", "Dentist Office", "Pharmacy", "Veterinary Clinic", "Psychiatric Hospital",

    # 🛫 Travel & Transit
    "Airport", "Space Station", "Cruise Ship", "Border Checkpoint", "Ferry Terminal", "Airplane",

    # 🏠 Indoor Settings
    "Elevator", "Basement", "Attic", "Rooftop Garden", "Garage Workshop",

    # 🍕 Food & Entertainment
    "Cinema", "Ice Cream Shop", "Nightclub", "Game Arcade", "Buffet Restaurant", "Food Truck", "Karaoke Bar", "Bowling Alley", "Escape Room", "Laser Tag Arena", "VR Arcade", "Theme Park",

    # 🌳 Outdoor & Nature
    "Beach", "Forest Camp", "Waterfall", "Hiking Trail", "Farm", "Desert Camp", "Jungle Safari",

    # 🏰 Fictional / Fun
    "Wizard School", "Supervillain Lair", "Zombie Apocalypse Shelter", "Pirate Ship", "Alien Planet",

    # ⚔️ Historical
    "Roman Colosseum", "Medieval Castle", "Ancient Pyramid", "World War Bunker", "Samurai Dojo",

    # ⛪ Religious / Cultural
    "Church", "Mosque", "Temple", "Cemetery", "Wedding Hall",

    # 🏢 Office & Workplaces
    "Startup Office", "Call Center", "Recording Studio", "Newsroom", "Conference Room",

    # 🧪 Scientific / Military
    "Nuclear Reactor", "Control Room", "Space Research Center", "Submarine", "Secret Lab",

    # 🏫 Others
    "Library", "Restaurant", "School", "Museum", "Zoo"
]

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
    update.message.reply_text(
        """📖 *INTEL — Deep Briefing for Agents*

🕵️‍♂️ *Game Overview:*
- 1 player is randomly chosen as the *Spy*.
- All others are *Civilians* and get the *same secret location*.
- The spy gets *no location* and must figure it out based on discussion.

---

🎯 *Objectives:*
- *Civilians:* Work together and vote out the spy without revealing the location.
- *Spy:* Pretend to know the location. If you survive the vote, guess the location to win!

---

⏱️ *Game Phases:*
1. **Join Phase:** Players use `/join` to enter the game.
2. **Start Game:** Host uses `/begin` to assign roles and start the timer.
3. **Discussion (5 minutes):** Talk in group, ask questions, act casual.
4. **Voting (1 minute):** Use `/vote` to choose who you think is the spy.
5. **Spy Guess (30 sec):** If spy survives, they try guessing the location.

---

👥 *Commands:*
- `/newgame` – Create a new game
- `/join` – Join the current game
- `/begin` – Officially start the game
- `/location` – Get your secret location (privately)
- `/vote` – Vote who you suspect
- `/endgame` – End the current game manually
- `/players` – List of joined players
- `/guide` – Quick gameplay instructions
- `/intel` – You're here 😉

---

💡 *Pro Tips:*
- Civilians: Don’t be too obvious about the location.
- Spy: Ask vague but smart questions.
- Everyone: Keep the conversation going. Silence is suspicious!

Good luck, Agent. Your mission starts soon. 🎩""",
        parse_mode='Markdown'
    )

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
    
    game['votes'] = {}  # Reset votes
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"vote:{uid}")]
        for uid, name in game['players'].items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("🗳 *Who do you think is the spy?*" \
_Vote by tapping on a name below._", reply_markup=reply_markup, parse_mode='Markdown')

    def timeout_vote():
        context.bot.send_message(chat_id, "⏰ Voting time is up!")
        finish_vote(chat_id, context)

    Timer(60, timeout_vote).start()

    def vote_progress():
        if chat_id in games:
            current = len(games[chat_id]['votes'])
            total = len(games[chat_id]['players'])
            if current < total:
                context.bot.send_message(chat_id, f"📥 {current}/{total} votes submitted...")
    Timer(30, vote_progress).start()

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
    for voter, voted in votes.items():
        counts[voted] = counts.get(voted, 0) + 1

    # Prepare vote breakdown
    breakdown = "🗳️ *Voting Result:*
"
    for voter_id, voted_id in votes.items():
        voter_name = game['players'].get(voter_id, 'Unknown')
        voted_name = game['players'].get(voted_id, 'Unknown')
        breakdown += f"- {voter_name} voted for {voted_name}
"

    # Detect highest voted
    max_votes = max(counts.values())
    top_voted = [uid for uid, c in counts.items() if c == max_votes]

    # Tie case
    if len(top_voted) > 1:
        chosen = random.choice(top_voted)
        tie_msg = "⚠️ There was a tie! Randomly selecting one among them..."
        context.bot.send_message(chat_id, tie_msg)
    else:
        chosen = top_voted[0]

    name = game['players'].get(chosen, 'Unknown')
    context.bot.send_message(chat_id, breakdown, parse_mode='Markdown')

    if chosen == game['spy']:
        msg = f"✅ {name} was the spy and was caught! Civilians win! 🎉"
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
    