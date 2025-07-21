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
# Structure: {chat_id: {players: {user_id: name}, state: 'waiting'/'mode_select'/'started', mode: 'normal', location: str, spy: user_id, double_agent:user_id, votes: {user_id: voted_id}, timers: []}}
games = {}
player_stats = {}
# Structure: {user_id: {'games_played': int, 'spy_wins': int, 'civilian_wins': int, 'spy_games': int, 'civilian_games': int, 'spies_caught': int, 'achievements': []}}

# Game modes configuration
GAME_MODES = {
    'normal': {
        'name': '🎯 Normal Mode',
        'description': '5 min discussion, standard rules',
        'discussion_time': 300,
        'voting_time': 60,
        'guess_time': 30,
        'special': None
    },
    'speed': {
        'name': '⚡ Speed Round',
        'description': '2 min discussion, 30s voting',
        'discussion_time': 120,
        'voting_time': 30,
        'guess_time': 20,
        'special': None
    },
    'marathon': {
        'name': '🏃 Marathon Mode',
        'description': '10 min discussion for deep strategy',
        'discussion_time': 600,
        'voting_time': 90,
        'guess_time': 45,
        'special': None
    },
    'team_spy': {
        'name': '👥 Team Spy',
        'description': '2 spies vs civilians (6+ players)',
        'discussion_time': 300,
        'voting_time': 60,
        'guess_time': 30,
        'special': 'two_spies'
    },
    'double_agent': {
        'name': '🎭 Double Agent',
        'description': 'Spy + double agent with wrong location',
        'discussion_time': 300,
        'voting_time': 60,
        'guess_time': 30,
        'special': 'double_agent'
    }
}

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

*Game Modes:*
🎯 Normal - 5 min discussion, standard rules
⚡ Speed - 2 min discussion, quick decisions  
🏃 Marathon - 10 min discussion, deep strategy
👥 Team Spy - 2 spies vs civilians (6+ players)
🎭 Double Agent - Spy + agent with wrong location

*Commands:*
/newgame – Select mode and start new game session.
/join – Join the ongoing game.
/leave – Leave the current game.
/players – Show current participants.
/begin – Begin the mission (minimum 3 players).
/location – Civilians can check their secret location.
/vote – Vote who you think is the spy.
/endgame – End the current game.
/guide - Quick gameplay instructions.
/intel - Read the detailed game rules.
/modes - See all available game modes.
/stats - View your personal game statistics and win rates.
/leaderboard - See top players rankings
/achievements - Check your unlocked achievements

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

🎮 *Game Modes Available:*

🎯 **Normal Mode:** Classic gameplay with 5-minute discussion and standard rules.

⚡ **Speed Round:** Fast-paced 2-minute discussion, 30-second voting. Perfect for quick games and testing your instant instincts!

🏃 **Marathon Mode:** Extended 10-minute discussion phase for deep psychological analysis and complex strategies. More time to deceive and deduce.

👥 **Team Spy Mode:** Two spies work together! Requires 6+ players. Both spies know each other and must coordinate to survive. Civilians must catch BOTH spies to win.

🎭 **Double Agent Mode:** Most chaotic mode! One real spy (no location) + one double agent (gets WRONG location but thinks they're civilian). Double agent will confidently give wrong clues, creating beautiful confusion. Civilians must identify both threats!

---

⏱️ *Game Phases:*
1. **Join Phase:** Players use /join to enter the game.
2. **Start Game:** Host uses /begin to assign roles and start the timer.
3. **Discussion (5 minutes):** Talk in group, ask questions, act casual.
4. **Voting (1 minute):** Use /vote to choose who you think is the spy.
5. **Spy Guess (30 sec):** If spy survives, they try guessing the location.

---

👥 *Commands:*
/newgame – Create a new game
/join – Join the current game
/leave – Leave the current game
/players – List of joined players
/begin – Officially start the game
/location – Get your secret location (privately)
/vote – Vote who you suspect
/endgame – End the current game manually
/guide – Quick gameplay instructions
/intel – You're here 😉
/modes – List all game modes
/stats – View your personal game statistics
/leaderboard – See top players rankings
/achievements – Check your unlocked achievements

---

💡 *Pro Tips:*
- Civilians: Don’t be too obvious about the location.
- Spy: Ask vague but smart questions.
- Everyone: Keep the conversation going. Silence is suspicious!

Good luck, Agent. Your mission starts soon. 🎩""",
        parse_mode='Markdown'
    )

def modes(update: Update, context: CallbackContext):
    modes_text = "🎮 *Available Game Modes:*\n\n"
    
    for mode_key, mode_data in GAME_MODES.items():
        modes_text += f"{mode_data['name']}\n"
        modes_text += f"⏱️ Discussion: {mode_data['discussion_time']//60} min\n"
        modes_text += f"📝 {mode_data['description']}\n\n"
    
    modes_text += "Use /newgame to select a mode and start playing!"
    
    update.message.reply_text(modes_text, parse_mode='Markdown')

def newgame(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    if chat_id in games:
        update.message.reply_text("⚠️ A game is already in progress. Use /endgame to end it before starting a new one.")
        return
    
    games[chat_id] = {
        'players': {}, 
        'state': 'mode_select', 
        'mode': None,
        'location': None, 
        'spy': None, 
        'double_agent': None,
        'votes': {}, 
        'timers': [],
        'awaiting_guess': False
    }
    
    # Create mode selection keyboard
    keyboard = [
        [InlineKeyboardButton(mode_data['name'], callback_data=f"mode:{mode_key}")]
        for mode_key, mode_data in GAME_MODES.items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        "🎮 *Select Game Mode:*\n\n" + 
        "\n".join([f"{data['name']}: {data['description']}" for data in GAME_MODES.values()]),
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

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

    location = random.choice(locations)
    game['state'] = 'started'
    game['location'] = location
    game['votes'] = {}
    game['awaiting_guess'] = False

    # Clear any existing timers
    for timer in game['timers']:
        timer.cancel()
    game['timers'] = []
    
    # Get mode configuration
    mode_config = GAME_MODES[game['mode']]
    discussion_time = mode_config['discussion_time']

    # Handle special modes
    if mode_config['special'] == 'two_spies':
        if len(players) < 6:
            update.message.reply_text("🚨 Team Spy mode needs at least 6 players.")
            return
        spies = random.sample(players, 2)
        game['spy'] = spies
        
        # Send messages for two spies
        for uid in players:
            if uid in spies:
                other_spy = [s for s in spies if s != uid][0]
                other_name = game['players'][other_spy]
                context.bot.send_message(uid, f"🕵️ You are a SPY! Your partner is {other_name}. Work together!")
            else:
                context.bot.send_message(uid, f"🧭 You are a civilian.\nLocation: *{location}*", parse_mode='Markdown')
    
    elif mode_config['special'] == 'double_agent':
        spy = random.choice(players)
        remaining = [p for p in players if p != spy]
        double_agent = random.choice(remaining)
        fake_location = random.choice([loc for loc in locations if loc != location])
        
        game['spy'] = spy
        game['double_agent'] = double_agent
        
        # Send messages for double agent mode
        for uid in players:
            if uid == spy:
                context.bot.send_message(uid, "🕵️ You are the SPY! Try to blend in and guess the location.")
            elif uid == double_agent:
                context.bot.send_message(uid, f"🧭 You are a civilian.\nLocation: *{fake_location}* ❌", parse_mode='Markdown')
            else:
                context.bot.send_message(uid, f"🧭 You are a civilian.\nLocation: *{location}*", parse_mode='Markdown')

    else:
        # Normal mode (existing code)
        spy = random.choice(players)
        game['spy'] = spy
        
        for uid in players:
            if uid == spy:
                context.bot.send_message(uid, "🕵️ You are the SPY! Try to blend in and guess the location.")
            else:
                context.bot.send_message(uid, f"🧭 You are a civilian.\nLocation: *{location}*", parse_mode='Markdown')

    update.message.reply_text(f"🎮 *{mode_config['name']} started!* Discuss for {discussion_time//60} minutes.", parse_mode='Markdown')

    def trigger_vote():
        if chat_id in games:
            context.bot.send_message(chat_id, "🗳️ Time's up! Voting begins now.")
            start_voting(chat_id, context)

    timer = Timer(discussion_time, trigger_vote)
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
    start_voting(chat_id, context)
    
def start_voting(chat_id, context):
    game = games.get(chat_id)
    if not game or game['state'] != 'started':
        context.bot.send_message(chat_id, "❌ No game in progress or game has not started yet.")
        return
    
    game['votes'] = {}  # Reset votes
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"vote:{uid}")]
        for uid, name in game['players'].items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_message(
        chat_id,
        "🗳 *Who do you think is the spy?*\nVote by tapping on a name below.", 
        reply_markup=reply_markup, 
        parse_mode='Markdown'
    )

    #Get voting time from mode config
    mode_config = GAME_MODES[game['mode']]
    voting_time = mode_config['voting_time']

    def timeout_vote():
        if chat_id not in games:  # Check if game still exists
            context.bot.send_message(chat_id, "⏰ Voting time is up!")
            finish_vote(chat_id, context)

    def vote_progress():
        if chat_id in games:
            current = len(games[chat_id]['votes'])
            total = len(games[chat_id]['players'])
            if current < total:
                context.bot.send_message(chat_id, f"📥 {current}/{total} votes submitted...")

    vote_timer = Timer(voting_time, timeout_vote)
    progress_timer = Timer(30, vote_progress)
    
    vote_timer.start()
    progress_timer.start()
    
    game['timers'].extend([vote_timer, progress_timer])  # Check progress every 10 seconds

def vote_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    game = games.get(chat_id)

    if not game or user_id not in game['players']:
        query.answer("You’re not in the game.")
        return

    voted_id = int(query.data.split(":")[1])
    game['votes'][user_id] = voted_id
    voted_name = game['players'].get(voted_id, 'Unknown')
    query.answer(f"Voted for {voted_name}")

    if len(game['votes']) == len(game['players']):
        finish_vote(chat_id, context)

def mode_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    chat_id = query.message.chat_id
    game = games.get(chat_id)
    
    if not game or game['state'] != 'mode_select':
        query.answer("Invalid game state.")
        return
    
    mode = query.data.split(":")[1]
    game['mode'] = mode
    game['state'] = 'waiting'
    
    mode_info = GAME_MODES[mode]
    query.answer(f"Selected: {mode_info['name']}")
    
    context.bot.edit_message_text(
        text=f"✅ *{mode_info['name']} Selected!*\n{mode_info['description']}\n\nPlayers, use /join to participate.",
        chat_id=chat_id,
        message_id=query.message.message_id,
        parse_mode='Markdown'
    )

def finish_vote(chat_id, context):
    game = games.get(chat_id)
    if not game:
        return
   
    # Cancel any remaining timers
    for timer in game['timers']:
        timer.cancel()
    game['timers'] = []

    votes = game['votes']
    if not votes:
        context.bot.send_message(chat_id, "❌ No votes received. Game ended.")
        del games[chat_id]
        return
    
    counts = {}
    for voter, voted in votes.items():
        counts[voted] = counts.get(voted, 0) + 1

    # Prepare vote breakdown
    breakdown = "🗳️ *Voting Result:*\n"
    for voter_id, voted_id in votes.items():
        voter_name = game['players'].get(voter_id, 'Unknown')
        voted_name = game['players'].get(voted_id, 'Unknown')
        breakdown += f"- {voter_name} voted for {voted_name}\n"

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

    # Update statistics for voting
    for voter_id in game['votes']:
        if voter_id not in player_stats:
            player_stats[voter_id] = {
                'games_played': 0, 'spy_wins': 0, 'civilian_wins': 0,
                'spy_games': 0, 'civilian_games': 0, 'spies_caught': 0,
                'achievements': [], 'name': game['players'].get(voter_id, 'Unknown')
            }
    
        # Check if they caught the spy
        if isinstance(game['spy'], list):  #Team Spy mode
            if game['votes'][voter_id] in game['spy']:
                player_stats[voter_id]['spies_caught'] += 1
        else:
            if game['votes'][voter_id] == game['spy']:
                player_stats[voter_id]['spies_caught'] += 1

    # Handle special mode win conditions
    mode_config = GAME_MODES[game['mode']]
    
    if mode_config['special'] == 'team_spy':
        if chosen in game['spy']:  # One spy caught
            msg = f"✅ {name} was a spy! But their partner is still hidden..."
            context.bot.send_message(chat_id=chat_id, text=msg)
            # Remove caught spy and continue
            game['spy'] = [s for s in game['spy'] if s != chosen]
            del game['players'][chosen]
            if len(game['spy']) == 0:
                context.bot.send_message(chat_id, "🎉 All spies caught! Civilians win!")
                end_game(chat_id, 'civilian_win')
            else:
                # Start another voting round
                start_voting(chat_id, context)
            return
        else:
            msg = f"❌ {name} was innocent. The spies were {[game['players'].get(s, 'unknown') for s in game['spy']]}. Spy wins!"
            context.bot.send_message(chat_id=chat_id, text=msg)
            end_game(chat_id, 'spy_win')
            return
        
    elif mode_config['special'] == 'double_agent':
        if chosen == game['spy']:
            msg = f"✅ {name} was the real spy! But the double agent is still among you..."
            context.bot.send_message(chat_id=chat_id, text=msg)
            context.bot.send_message(chat_id,  "🎉 Civilians win!")
            end_game(chat_id, 'civilian_win')
            return
        elif chosen == game['double_agent']:
            msg = f"❌ {name} was the double agent, but the real spy escaped! Spy wins!"
            spy_name = game['players'].get(game['spy'], 'Unknown')
            context.bot.send_message(chat_id=chat_id, text=msg + f" The real spy was {spy_name}.")
            end_game(chat_id, 'spy_win')
            return
        else:                
            msg = f"❌ {name} was innocent. Spy wins!"
            spy_name = game['players'].get(game['spy'], 'Unknown')
            da_name = game['players'].get(game['double_agent'], 'Unknown')
            context.bot.send_message(chat_id=chat_id, text=msg + f" The spy was {spy_name} and double agent was {da_name}.")
            end_game(chat_id, 'spy_win')
            return
        
    # Normal mode handling
    if chosen == game['spy']:
        msg = f"✅ {name} was the spy and was caught! Civilians win! 🎉"
        context.bot.send_message(chat_id=chat_id, text=msg)
        end_game(chat_id, 'civilian_win')
    else:
        spy_name = game['players'].get(game['spy'], 'Unknown')
        msg = f"❌ {name} was innocent. The spy was {spy_name}."
        context.bot.send_message(chat_id=chat_id, text=msg)
        
        # Spy gets to guess
        spy = game['spy']
        context.bot.send_message(spy, "🕵️ You've survived! Now guess the location! You have 30 seconds. Reply with your guess.")
        game['awaiting_guess'] = True

        def timeout_guess():
            if chat_id in games and games[chat_id].get('awaiting_guess'):
                context.bot.send_message(chat_id, "⏰ Spy failed to guess in time. Civilians win!")
                end_game(chat_id, 'civilian_win')

        guess_time = GAME_MODES[game['mode']]['guess_time']
        guess_timer = Timer(guess_time, timeout_guess)
        guess_timer.start()
        game['timers'].append(guess_timer)

# Spy guess handler

def handle_guess(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    user_id = update.effective_user.id
    game = games.get(chat_id)

    if not game or not game.get('awaiting_guess') or user_id != game['spy']:
        return

    guess = update.message.text.strip().lower()
    correct = game['location'].lower()

    # Cancel guess timer
    for timer in game['timers']:
        timer.cancel()
    game['timers'] = []
    
    if guess == correct:
        context.bot.send_message(chat_id, f"🎉 The spy guessed correctly ({guess}) and wins!")
        end_game(chat_id, 'spy_win')
    else:
        context.bot.send_message(chat_id, f"❌ The spy guessed {guess}, but the real location was '{game['location']}'. Civilians win!")
        end_game(chat_id, 'civilian_win')

def end_game(chat_id, result):
    game = games.get(chat_id)
    if not game:
        return
    
    # Update player statistics
    for player_id in game['players']:
        was_spy = (player_id == game['spy'] or 
                  (isinstance(game['spy'], list) and player_id in game['spy']))
        update_player_stats(player_id, game['players'][player_id], result, was_spy)
    
    # Cancel all timers
    for timer in game['timers']:
        timer.cancel()
    
    del games[chat_id]

def endgame(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    if chat_id in games:
        #cancel any active timers
        game = games[chat_id]
        for timer in game.get('timers', []):
            timer.cancel()
        del games[chat_id]
        update.message.reply_text("🛑 Game ended.")
    else:
        update.message.reply_text("❌ No game to end.")

def test_command(update: Update, context: CallbackContext):
    print("TEST COMMAND TRIGGERED")
    update.message.reply_text("✅ Test working!")

def show_stats(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    stats = player_stats.get(user_id, {})
    if not stats:
        update.message.reply_text("📊 No games played yet! Join a game to start building your stats.")
        return
    
    games_played = stats.get('games_played', 0)
    spy_wins = stats.get('spy_wins', 0)
    civilian_wins = stats.get('civilian_wins', 0)
    spy_games = stats.get('spy_games', 0)
    civilian_games = stats.get('civilian_games', 0)
    spies_caught = stats.get('spies_caught', 0)
    
    spy_win_rate = (spy_wins / spy_games * 100) if spy_games > 0 else 0
    civilian_win_rate = (civilian_wins / civilian_games * 100) if civilian_games > 0 else 0
    
    stats_text = f"""📊 *Your Statistics:*
    
🎮 Games Played: {games_played}
🕵️ Times as Spy: {spy_games}
👥 Times as Civilian: {civilian_games}

🏆 *Win Rates:*
🕵️ Spy Success: {spy_win_rate:.1f}% ({spy_wins}/{spy_games})
👥 Civilian Success: {civilian_win_rate:.1f}% ({civilian_wins}/{civilian_games})
🎯 Spies Caught: {spies_caught}

🏅 Achievements: {len(stats.get('achievements', []))}"""
    
    update.message.reply_text(stats_text, parse_mode='Markdown')

def show_leaderboard(update: Update, context: CallbackContext):
    if not player_stats:
        update.message.reply_text("📊 No stats available yet!")
        return
    
    # Sort players by various metrics
    spy_masters = sorted(player_stats.items(), key=lambda x: x[1].get('spy_wins', 0), reverse=True)[:5]
    detectives = sorted(player_stats.items(), key=lambda x: x[1].get('spies_caught', 0), reverse=True)[:5]
    
    leaderboard = "🏆 *LEADERBOARD*\n\n🕵️ *Top Spy Masters:*\n"
    for i, (user_id, stats) in enumerate(spy_masters, 1):
        name = stats.get('name', f'Agent {user_id}')
        wins = stats.get('spy_wins', 0)
        leaderboard += f"{i}. {name}: {wins} spy wins\n"
    
    leaderboard += "\n🎯 *Top Detectives:*\n"
    for i, (user_id, stats) in enumerate(detectives, 1):
        name = stats.get('name', f'Agent {user_id}')
        caught = stats.get('spies_caught', 0)
        leaderboard += f"{i}. {name}: {caught} spies caught\n"
    
    update.message.reply_text(leaderboard, parse_mode='Markdown')

def show_achievements(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    stats = player_stats.get(user_id, {})
    achievements = stats.get('achievements', [])
    
    if not achievements:
        update.message.reply_text("🏅 No achievements yet! Keep playing to unlock them.")
        return
    
    achievement_text = "🏅 *Your Achievements:*\n\n" + "\n".join([f"🎖️ {ach}" for ach in achievements])
    update.message.reply_text(achievement_text, parse_mode='Markdown')

def update_player_stats(user_id, name, result_type, was_spy):
    if user_id not in player_stats:
        player_stats[user_id] = {
            'games_played': 0, 'spy_wins': 0, 'civilian_wins': 0, 
            'spy_games': 0, 'civilian_games': 0, 'spies_caught': 0, 
            'achievements': [], 'name': name
        }
    
    stats = player_stats[user_id]
    stats['games_played'] += 1
    stats['name'] = name  # Update name in case it changed
    
    if was_spy:
        stats['spy_games'] += 1
        if result_type == 'spy_win':
            stats['spy_wins'] += 1
    else:
        stats['civilian_games'] += 1
        if result_type == 'civilian_win':
            stats['civilian_wins'] += 1
    
    # Check for achievements
    check_achievements(user_id, stats)

def check_achievements(user_id, stats):
    unlocked = set(stats['achievements'])
    new_achievements = []
    
    # Achievement checks
    if stats['spy_wins'] >= 5 and 'Master Spy' not in unlocked:
        new_achievements.append('Master Spy')
    if stats['spies_caught'] >= 10 and 'Super Detective' not in unlocked:
        new_achievements.append('Super Detective')
    if stats['games_played'] >= 50 and 'Veteran Agent' not in unlocked:
        new_achievements.append('Veteran Agent')
    if stats['spy_games'] >= 20 and 'Professional Deceiver' not in unlocked:
        new_achievements.append('Professional Deceiver')
    
        stats['achievements'].extend(new_achievements)
        # You can send notification here if desired

# --- Main ---
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("guide", guide))
    dp.add_handler(CommandHandler("intel", intel))
    dp.add_handler(CommandHandler("modes", modes))
    dp.add_handler(CommandHandler("newgame", newgame))
    dp.add_handler(CommandHandler("join", join))
    dp.add_handler(CommandHandler("leave", leave))
    dp.add_handler(CommandHandler("players", players))
    dp.add_handler(CommandHandler("begin", begin))
    dp.add_handler(CommandHandler("location", location_command))
    dp.add_handler(CommandHandler("vote", vote))
    dp.add_handler(CommandHandler("endgame", endgame))
    dp.add_handler(CommandHandler("stats", show_stats))
    dp.add_handler(CommandHandler("leaderboard", show_leaderboard))
    dp.add_handler(CommandHandler("achievements", show_achievements))
    dp.add_handler(CommandHandler("test", test_command))

    dp.add_handler(CallbackQueryHandler(vote_callback, pattern=r"^vote:"))
    dp.add_handler(CallbackQueryHandler(mode_callback, pattern=r"^mode:"))

    # Message filter should be limited to spy guess scenario
    dp.add_handler(MessageHandler(Filters.text & Filters.private, handle_guess))
    
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
    