#!/usr/bin/env python3
# Enhanced Spy Bot - The Ultimate Social Deduction Game Bot
# Features: Robust error handling, advanced game mechanics, comprehensive stats, achievement system

import os
import logging
import random
import time
import hashlib
from threading import Timer, Lock
from datetime import datetime
from typing import Dict, List, Optional, Union, Tuple
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram import ChatMemberAdministrator, ChatMemberOwner
from telegram.ext import (
    Updater, CommandHandler, CallbackContext, CallbackQueryHandler,
    MessageHandler, Filters, Dispatcher
)

# ---Configuration---
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "").split(",") if id]

if not TOKEN:
    raise ValueError("BOT_TOKEN is missing. Please set it in environment.")

# Enhanced logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Thread-safe data structures
class GameState:
    def __init__(self):
        self.lock = Lock()
        self.games: Dict[int, dict] = {}  # {chat_id: game_data}
        self.player_stats: Dict[int, dict] = {}  # {user_id: stats}
        self.active_timers: Dict[int, List[Timer]] = {}  # {chat_id: timers}
        self.anon_cooldowns: Dict[int, float] = {}  # {user_id: last_used_time}
        self.temp_anon_messages: Dict[str, dict] = {}

    def get_game(self, chat_id: int) -> Optional[dict]:
        with self.lock:
            return self.games.get(chat_id)

    def add_game(self, chat_id: int, game_data: dict):
        with self.lock:
            self.games[chat_id] = game_data

    def remove_game(self, chat_id: int):
        with self.lock:
            if chat_id in self.games:
                del self.games[chat_id]
            if chat_id in self.active_timers:
                for timer in self.active_timers[chat_id]:
                    timer.cancel()
                del self.active_timers[chat_id]
            if hasattr(self, 'temp_anon_messages'):
                # Clean up any temp messages for this chat
                self.temp_anon_messages = {
                    k: v for k, v in self.temp_anon_messages.items() 
                    if k.split('_')[0] != str(chat_id)
                }

    def add_timer(self, chat_id: int, timer: Timer):
        with self.lock:
            if chat_id not in self.active_timers:
                self.active_timers[chat_id] = []
            self.active_timers[chat_id].append(timer)

    def clear_timers(self, chat_id: int):
        with self.lock:
            if chat_id in self.active_timers:
                for timer in self.active_timers[chat_id]:
                    timer.cancel()
                self.active_timers[chat_id] = []

    def cleanup_old_data(self):
        """Clean up old temporary data"""
        with self.lock:
            current_time = time.time()
        
            # Clean old cooldowns (older than 1 hour)
            self.anon_cooldowns = {
                uid: timestamp for uid, timestamp in self.anon_cooldowns.items()
                if current_time - timestamp < 3600
            }
        
            # Clean old temp messages (older than 10 minutes)
            if hasattr(self, 'temp_anon_messages'):
                self.temp_anon_messages = {
                    msg_id: data for msg_id, data in self.temp_anon_messages.items()
                    if current_time - data.get('timestamp', 0) < 600
                }

    def validate_game_state(chat_id: int, required_state: str = None, user_id: int = None) -> tuple[bool, str, dict]:
        """Comprehensive game state validation"""
        game = game_state.get_game(chat_id)
    
        if not game:
            return False, "No active game found", {}
    
        if required_state and game.get('state') != required_state:
            return False, f"Game not in {required_state} state", game
        
        if user_id and user_id not in game.get('players', {}):
            return False, "You're not in this game", game
        
        # Check for corrupted game data
        required_keys = ['players', 'state', 'mode']
        missing_keys = [key for key in required_keys if key not in game]
        if missing_keys:
            return False, f"Game data corrupted (missing: {missing_keys})", game
        
        return True, "Valid", game

game_state = GameState()

# Enhanced game modes configuration
GAME_MODES = {
    'normal': {
        'name': '🎯 Normal Mode',
        'description': '5 min discussion, standard rules',
        'discussion_time': 300,
        'voting_time': 60,
        'guess_time': 30,
        'min_players': 3,
        'special': None
    },
    'speed': {
        'name': '⚡ Speed Round',
        'description': '2 min discussion, 30s voting',
        'discussion_time': 120,
        'voting_time': 30,
        'guess_time': 20,
        'min_players': 3,
        'special': None
    },
    'marathon': {
        'name': '🏃 Marathon Mode',
        'description': '10 min discussion for deep strategy',
        'discussion_time': 600,
        'voting_time': 90,
        'guess_time': 45,
        'min_players': 4,
        'special': None
    },
    'team_spy': {
        'name': '👥 Team Spy',
        'description': '2 spies vs civilians (6+ players)',
        'discussion_time': 300,
        'voting_time': 60,
        'guess_time': 30,
        'min_players': 6,
        'special': 'two_spies'
    },
    'double_agent': {
        'name': '🎭 Double Agent',
        'description': 'Spy + agent with wrong location',
        'discussion_time': 300,
        'voting_time': 60,
        'guess_time': 30,
        'min_players': 4,
        'special': 'double_agent'
    },
    'chaos': {
        'name': '🌀 Chaos Mode',
        'description': 'Multiple spies and double agents',
        'discussion_time': 360,
        'voting_time': 75,
        'guess_time': 40,
        'min_players': 8,
        'special': 'chaos'
    }
}

# Add these constants after imports
ERROR_MESSAGES = {
    'no_game': "❌ No active game found. Use /newgame to start one.",
    'game_started': "⚠️ Game already started. Cannot join now.",
    'not_in_game': "⚠️ You're not in the current game.",
    'not_authorized': "⛔ You don't have permission to do this.",
    'invalid_state': "❌ This action is not available in the current game state.",
    'rate_limited': "⏳ Please wait {} seconds before trying again.",
    'network_error': "❌ Network error occurred. Please try again.",
}

def get_error_message(key: str, *args) -> str:
    """Get formatted error message"""
    return ERROR_MESSAGES.get(key, "❌ An error occurred.").format(*args)
    
# Expanded locations database with categories
LOCATIONS = {
    "🌆 City": [
        "Bank", "Train Station", "Police Station", "Fire Station", 
        "Shopping Mall", "Parking Garage", "Post Office", "Apartment Complex",
        "Metro Station", "Taxi Stand", "Highway Toll Booth", "Train Compartment"
    ],
    "🏫 Education": [
        "University", "Kindergarten", "Science Lab", "Art Studio", 
        "Debate Hall", "Library", "School"
    ],
    "🏥 Medical": [
        "Hospital", "Dentist Office", "Pharmacy", 
        "Veterinary Clinic", "Psychiatric Hospital"
    ],
    "✈️ Travel": [
        "Airport", "Space Station", "Cruise Ship", 
        "Border Checkpoint", "Ferry Terminal", "Airplane"
    ],
    "🍕 Entertainment": [
        "Cinema", "Ice Cream Shop", "Nightclub", "Game Arcade", 
        "Buffet Restaurant", "Karaoke Bar", "Bowling Alley", "Theme Park"
    ],
    "🏰 Fictional": [
        "Wizard School", "Supervillain Lair", "Zombie Apocalypse Shelter", 
        "Pirate Ship", "Alien Planet", "Time Machine"
    ],
    "⚔️ Historical": [
        "Roman Colosseum", "Medieval Castle", "Ancient Pyramid", 
        "World War Bunker", "Samurai Dojo", "Wild West Saloon"
    ],
    "🧪 Scientific": [
        "Nuclear Reactor", "Control Room", "Space Research Center", 
        "Submarine", "Secret Lab", "Particle Accelerator"
    ],
    "🌳 Outdoor": [
        "Beach", "Forest Camp", "Waterfall", "Hiking Trail", 
        "Farm", "Desert Camp", "Jungle Safari"
    ]
}

# Achievements system
ACHIEVEMENTS = {
    "rookie": {"name": "Rookie Agent", "condition": lambda s: s['games_played'] >= 1},
    "spy_novice": {"name": "Spy Novice", "condition": lambda s: s['spy_wins'] >= 3},
    "detective": {"name": "Junior Detective", "condition": lambda s: s['spies_caught'] >= 5},
    "master_spy": {"name": "Master Spy", "condition": lambda s: s['spy_wins'] >= 10 and s['spy_games'] >= 20},
    "super_sleuth": {"name": "Super Sleuth", "condition": lambda s: s['spies_caught'] >= 20},
    "veteran": {"name": "Veteran Agent", "condition": lambda s: s['games_played'] >= 50},
    "deceiver": {"name": "Master Deceiver", "condition": lambda s: s['spy_wins'] >= 15 and s['spy_win_rate'] >= 70},
    "team_player": {"name": "Team Player", "condition": lambda s: s['civilian_wins'] >= 20},
    "perfectionist": {"name": "Perfectionist", "condition": lambda s: s['civilian_win_rate'] >= 80 and s['civilian_games'] >= 15},
    "legend": {"name": "Legendary Agent", "condition": lambda s: s['games_played'] >= 100 and s['spy_win_rate'] >= 60 and s['civilian_win_rate'] >= 60}
}

# --- Helper Functions ---
def get_random_location(category: str = None) -> str:
    """Get a random location, optionally filtered by category"""
    if category and category in LOCATIONS:
        return random.choice(LOCATIONS[category])
    all_locations = [loc for sublist in LOCATIONS.values() for loc in sublist]
    return random.choice(all_locations)

def format_time(seconds: int) -> str:
    """Convert seconds to human-readable time format"""
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes}m {seconds}s" if minutes else f"{seconds}s"

def is_admin(user_id: int) -> bool:
    """Secure admin verification"""
    if not ADMIN_IDS:
        logger.warning("No admin IDs configured")
        return False
    
    return user_id in ADMIN_IDS

def verify_admin_action(user_id: int, action: str) -> bool:
    """Log and verify admin actions"""
    if is_admin(user_id):
        logger.info(f"Admin {user_id} performed action: {action}")
        return True
    else:
        logger.warning(f"Unauthorized admin attempt by {user_id} for action: {action}")
        return False

def validate_game_data(game: dict) -> bool:
    """Validate game data integrity"""
    required_fields = ['players', 'state', 'mode', 'host']
    
    # Check required fields exist
    for field in required_fields:
        if field not in game:
            logger.error(f"Game missing required field: {field}")
            return False
    
    # Validate data types
    if not isinstance(game['players'], dict):
        logger.error("Game players field is not a dictionary")
        return False
    
    if game['state'] not in ['mode_select', 'waiting', 'started']:
        logger.error(f"Invalid game state: {game['state']}")
        return False
    
    if game['mode'] and game['mode'] not in GAME_MODES:
        logger.error(f"Invalid game mode: {game['mode']}")
        return False
    
    return True

def validate_game(chat_id: int, user_id: int = None, state: str = None) -> bool:
    """Validate game state and user permissions"""
    game = game_state.get_game(chat_id)
    if not game:
        return False
    if user_id and user_id not in game['players']:
        return False
    if state and game['state'] != state:
        return False
    return True

def cancel_timers(chat_id: int):
    """Cancel all active timers for a game"""
    game_state.clear_timers(chat_id)

def send_to_all_players(context: CallbackContext, chat_id: int, message: str, exclude: List[int] = None):
    """Send message to all players in a game"""
    game = game_state.get_game(chat_id)
    if not game:
        return
    
    exclude = exclude or []
    for player_id in game['players']:
        if player_id not in exclude:
            try:
                context.bot.send_message(player_id, message, parse_mode='Markdown')
            except Exception as e:
                logger.error(f"Failed to send message to {player_id}: {e}")

def validate_input(text: str, max_length: int = 500, min_length: int = 1, allow_markdown: bool = False) -> tuple[bool, str]:
    """Enhanced input validation with security checks"""
    if not text or not text.strip():
        return False, "Message cannot be empty"
    
    text = text.strip()
    
    if len(text) < min_length:
        return False, f"Message too short (min {min_length} characters)"
    
    if len(text) > max_length:
        return False, f"Message too long (max {max_length} characters)"
    
    # Security: Check for potential injection attempts
    dangerous_patterns = [
        '<script', '</script>', 'javascript:', 'data:', 'vbscript:',
        'onload=', 'onerror=', 'onclick=', 'eval(', 'setTimeout(',
        'setInterval(', 'Function(', 'alert(', 'confirm(', 'prompt('
    ]
    
    text_lower = text.lower()
    for pattern in dangerous_patterns:
        if pattern in text_lower:
            return False, "Message contains potentially dangerous content"
    
    # Basic HTML sanitization (if not allowing markdown)
    if not allow_markdown:
        forbidden_chars = ['<', '>', '&', '"', "'", '`']
        if any(char in text for char in forbidden_chars):
            return False, "Message contains forbidden characters"
    
    # Length check for individual words (prevent spam)
    words = text.split()
    if any(len(word) > 50 for word in words):
        return False, "Individual words too long (max 50 characters each)"
    
    return True, text

def check_rate_limit(user_id: int, action: str, limit_seconds: int = 60) -> tuple[bool, int]:
    """Check if user is rate limited for specific action"""
    with game_state.lock:
        key = f"{action}_{user_id}"
        if not hasattr(game_state, 'action_cooldowns'):
            game_state.action_cooldowns = {}
        
        current_time = time.time()
        last_action = game_state.action_cooldowns.get(key, 0)
        time_left = limit_seconds - (current_time - last_action)
        
        if time_left > 0:
            return False, int(time_left)
        
        game_state.action_cooldowns[key] = current_time
        return True, 0

def send_safe_message(context: CallbackContext, chat_id: int, message: str, parse_mode: str = 'Markdown') -> bool:
    """Safely send message with error handling"""
    try:
        context.bot.send_message(chat_id, message, parse_mode=parse_mode)
        return True
    except Exception as e:
        logger.error(f"Failed to send message to {chat_id}: {e}")
        return False

def get_user_name_safe(user) -> str:
    """Safely get user name with fallback"""
    return getattr(user, 'first_name', None) or getattr(user, 'username', 'Unknown')

def is_authorized_to_control_game(user_id: int, game: dict, context: CallbackContext, chat_id: int) -> bool:
    """Check if user can control the game (host, bot admin, or group admin)"""
    # Bot admin check
    if is_admin(user_id):
        return True
    
    # Host check
    if user_id == game.get('host'):
        return True
    
    # Group admin check
    try:
        member = context.bot.get_chat_member(chat_id, user_id)
        return member.status in ['administrator', 'creator']
    except:
        return False

# --- Command handlers ---
def start(update: Update, context: CallbackContext):
    """Send welcome message"""
    update.message.reply_text(
        """🕵️‍♂️ *Welcome to Spy Bot - Ultimate Social Deduction Game!*

🎯 *Your Mission:* Blend in, lie smart, and expose the SPY (or hide if you are one 😏).

🎮 *Quick Start:*
• Use /guide for rules
• Use /newgame to create a mission
• Use /stats to see your progress

🆕 *What's New:*
• Enhanced game modes including Chaos Mode 💀
• Improved statistics and achievements 🏅
• Better admin controls and error handling
• Persistent data storage

Ready to begin your mission, Agent?""",
        parse_mode='Markdown'
    )

def guide(update: Update, context: CallbackContext):
    """Send quick guide"""
    update.message.reply_text(
        """🎮 *Quick Guide:*

1. Host creates game with /newgame
2. Players join with /join
3. Host starts with /begin
4. Discuss and ask questions
5. Vote with /vote when ready
6. Spy gets to guess if not caught

*Key Commands:*
/newgame - Create game
/join - Join current game
/begin - Start game
/vote - Start voting
/location - Check your role
/stats - View your statistics

For full details, use /intel""",
        parse_mode='Markdown'
    )

def intel(update: Update, context: CallbackContext):
    """Send detailed instructions"""
    modes_text = "\n".join([
        f"• {mode['name']}: {mode['description']} (Min players: {mode['min_players']})"
        for mode in GAME_MODES.values()
    ])
    
    update.message.reply_text(
        f"""📚 *Spy Bot Comprehensive Guide*

🎯 *Objective:*
Civilians must identify the Spy through discussion and voting.
The Spy must blend in and guess the location if not caught.

⏱️ *Game Phases:*
1. Joining (/join)
2. Discussion (ask questions)
3. Voting (/vote)
4. Spy's guess (if applicable)

🎮 *Game Modes:*
{modes_text}

🏆 *Scoring:*
- Civilians win if they catch the Spy
- Spy wins if they survive or guess correctly

📊 *Statistics Tracked:*
- Games played as Spy/Civilian
- Win rates
- Spies caught
- Achievements unlocked

Use /newgame to start your first mission!""",
        parse_mode='Markdown'
    )

def modes(update: Update, context: CallbackContext):
    """List available game modes"""
    modes_list = []
    for mode_id, mode in GAME_MODES.items():
        modes_list.append(
            f"• {mode['name']}\n"
            f"  {mode['description']}\n"
            f"  ⏱ Discussion: {format_time(mode['discussion_time'])}\n"
            f"  👥 Min players: {mode['min_players']}"
        )
    
    update.message.reply_text(
        "🎮 *Available Game Modes:*\n\n" + "\n\n".join(modes_list) +
        "\n\nUse /newgame to select a mode and start playing!",
        parse_mode='Markdown'
    )

def newgame(update: Update, context: CallbackContext):
    """Start a new game"""
    chat_id = update.message.chat_id
    user = update.effective_user
    
    if game_state.get_game(chat_id):
        update.message.reply_text("⚠️ Game already in progress. Use /endgame first.")
        return
    
    game_data = {
        'players': {},
        'state': 'mode_select',
        'mode': None,
        'location': None,
        'spy': None,
        'double_agent': None,
        'votes': {},
        'host': user.id,
        'created_at': datetime.now().isoformat(),
        'awaiting_guess': False
    }
    
    game_state.add_game(chat_id, game_data)
    
    keyboard = [
        [InlineKeyboardButton(mode['name'], callback_data=f"mode:{mode_id}")]
        for mode_id, mode in GAME_MODES.items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        "🎮 *Select Game Mode:*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

def join(update: Update, context: CallbackContext):
    """Join current game"""
    chat_id = update.message.chat_id
    user = update.effective_user
    game = game_state.get_game(chat_id)
    
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
    
    # Update player count
    player_count = len(game['players'])
    min_players = GAME_MODES.get(game.get('mode', 'normal'), {}).get('min_players', 3)
    if player_count >= min_players:
        update.message.reply_text(
            f"👥 Enough players joined! Host can /begin the game now.",
            reply_to_message_id=update.message.message_id
        )

def leave(update: Update, context: CallbackContext):
    """Leave current game"""
    chat_id = update.message.chat_id
    user = update.effective_user
    game = game_state.get_game(chat_id)
    
    if not game:
        update.message.reply_text("⚠️ No game to leave.")
        return
    
    if user.id not in game['players']:
        update.message.reply_text("⚠️ You're not in the game.")
        return
    
    if game['state'] != 'waiting':
        update.message.reply_text("⚠️ Cannot leave after game started.")
        return
    
    del game['players'][user.id]
    update.message.reply_text(f"👋 {user.first_name} left the game.")
    
    # Check if host left
    if user.id == game['host'] and game['players']:
        new_host = next(iter(game['players']))
        game['host'] = new_host
        update.message.reply_text(
            f"👑 {game['players'][new_host]} is now the host.",
            reply_to_message_id=update.message.message_id
        )
    elif not game['players']:
        game_state.remove_game(chat_id)
        update.message.reply_text("🛑 Game closed due to no players.")

def players(update: Update, context: CallbackContext):
    """List current players"""
    chat_id = update.message.chat_id
    game = game_state.get_game(chat_id)
    
    if not game:
        update.message.reply_text("❌ No game in progress.")
        return
    
    if not game['players']:
        update.message.reply_text("👥 No players yet.")
        return
    
    player_list = [f"• {name}" for name in game['players'].values()]
    host_marker = lambda uid: " 👑" if uid == game['host'] else ""
    player_list = [
        f"• {name}{host_marker(uid)}"
        for uid, name in game['players'].items()
    ]
    
    mode_info = GAME_MODES.get(game.get('mode', 'normal'), {})
    min_players = mode_info.get('min_players', 3)
    player_count = len(game['players'])
    
    update.message.reply_text(
        f"👥 *Players ({player_count}/{min_players}):*\n" + "\n".join(player_list) +
        (f"\n\n✅ Ready to /begin!" if player_count >= min_players else ""),
        parse_mode='Markdown'
    )    

def begin(update: Update, context: CallbackContext):
    """Start the game"""
    chat_id = update.message.chat_id
    user = update.effective_user
    game = game_state.get_game(chat_id)
    
    if not game or game['state'] != 'waiting':
        update.message.reply_text("⚠️ No game to begin.")
        return
    
    # Permission checks
    is_bot_admin = is_admin(user.id)
    is_host = user.id == game['host']
    is_group_admin = False
    
    try:
        if update.effective_chat.type in ['group', 'supergroup']:
            member = context.bot.get_chat_member(chat_id, user.id)
            is_group_admin = member.status in ['administrator', 'creator']
    except Exception as e:
        logger.warning(f"Failed to check admin status: {e}")
    
    if not (is_host or is_bot_admin or is_group_admin):
        update.message.reply_text(
            "⛔ Only game host (@{host}), bot admins, or group admins can start the game.".format(
                host=game['players'].get(game['host'], "unknown")
            )
        )
        return
    
    mode_config = GAME_MODES.get(game['mode'], GAME_MODES['normal'])
    min_players = mode_config['min_players']
    
    if len(game['players']) < min_players:
        update.message.reply_text(f"🚨 Need at least {min_players} players.")
        return
    
    # Select location and assign roles
    game['location'] = get_random_location()
    game['state'] = 'started'
    game['votes'] = {}
    game['awaiting_guess'] = False
    
    players = list(game['players'].keys())
    
    # Handle special game modes
    if mode_config['special'] == 'two_spies':
        game['spy'] = random.sample(players, 2)
        for uid in players:
            if uid in game['spy']:
                partner = next(s for s in game['spy'] if s != uid)
                context.bot.send_message(
                    uid,
                    f"🕵️ You are a SPY!\nYour partner is {game['players'][partner]}.",
                    parse_mode='Markdown'
                )
            else:
                context.bot.send_message(
                    uid,
                    f"🧭 You are a civilian.\nLocation: *{game['location']}*",
                    parse_mode='Markdown'
                )
    
    elif mode_config['special'] == 'double_agent':
        game['spy'] = random.choice(players)
        remaining = [p for p in players if p != game['spy']]
        game['double_agent'] = [random.choice(remaining)]
        fake_location = get_random_location()
        
        for uid in players:
            if uid == game['spy']:
                context.bot.send_message(uid, "🕵️ You are the SPY!")
            elif uid in game.get('double_agent', []):
                context.bot.send_message(
                    uid,
                    f"🧭 You are a civilian.\nLocation: *{fake_location}* ❌",
                    parse_mode='Markdown'
                )
            else:
                context.bot.send_message(
                    uid,
                    f"🧭 You are a civilian.\nLocation: *{game['location']}*",
                    parse_mode='Markdown'
                )
    
    elif mode_config['special'] == 'chaos':
        spy_count = max(2, len(players) // 3)
        game['spy'] = random.sample(players, spy_count)
        remaining = [p for p in players if p not in game['spy']]
        da_count = max(1, len(remaining) // 3)
        game['double_agent'] = random.sample(remaining, da_count)
        
        for uid in players:
            if uid in game['spy']:
                partners = [s for s in game['spy'] if s != uid]
                partners_names = ", ".join(game['players'][p] for p in partners)
                context.bot.send_message(
                    uid,
                    f"🕵️ You are a SPY!\nPartners: {partners_names}",
                    parse_mode='Markdown'
                )
            elif uid in game.get('double_agent', []):
                fake_location = get_random_location()
                context.bot.send_message(
                    uid,
                    f"🧭 You are a civilian.\nLocation: *{fake_location}* ❌",
                    parse_mode='Markdown'
                )
            else:
                context.bot.send_message(
                    uid,
                    f"🧭 You are a civilian.\nLocation: *{game['location']}*",
                    parse_mode='Markdown'
                )
    
    else:  # Normal mode
        game['spy'] = random.choice(players)
        for uid in players:
            if uid == game['spy']:
                context.bot.send_message(uid, "🕵️ You are the SPY!")
            else:
                context.bot.send_message(
                    uid,
                    f"🧭 You are a civilian.\nLocation: *{game['location']}*",
                    parse_mode='Markdown'
                )
    
    # Start discussion timer
    discussion_time = mode_config['discussion_time']
    update.message.reply_text(
        f"🎮 *{mode_config['name']} started!*\n"
        f"Discuss for {format_time(discussion_time)}.\n"
        f"Use /vote when ready or wait for timer.",
        parse_mode='Markdown'
    )
    
    def start_voting_wrapper():
        game = game_state.get_game(chat_id)
        if game and game['state'] == 'started':
            try:
                context.bot.send_message(
                    chat_id,
                    "⏰ Discussion time over! Starting voting...",
                    parse_mode='Markdown'
                )
                start_voting(chat_id, context)
            except Exception as e:
                logger.error(f"Failed to start voting automatically: {e}")
    
    timer = Timer(discussion_time, start_voting_wrapper)
    timer.start()
    game_state.add_timer(chat_id, timer)

def anon(update: Update, context: CallbackContext):
    """Handle anonymous messages from players"""
    if update.effective_chat.type != 'private':
        update.message.reply_text(
            "❌ Anonymous messages can only be sent in private chat with the bot.\n"
            "Message me directly to send anonymous messages to your game."
        )
        return
    
    user_id = update.effective_user.id
    current_time = time.time()
    
    # Rate limiting with thread safety
    with game_state.lock:
        if user_id in game_state.anon_cooldowns:
            time_elapsed = current_time - game_state.anon_cooldowns[user_id]
            if time_elapsed < 60:
                update.message.reply_text(
                    f"⏳ Please wait {60 - int(time_elapsed)} seconds before sending another anonymous message."
                )
                return
    
    # Validate message
    message = ' '.join(context.args) if context.args else ""
    is_valid, result = validate_input(message)
    
    if not is_valid:
        update.message.reply_text(f"❌ {result}")
        return

    message = result
    
    # Find active games
    active_games = []
    with game_state.lock:
        for chat_id, game in game_state.games.items():
            if (user_id in game['players'] and game['state'] == 'started'):
                active_games.append((chat_id, game))
    
    if not active_games:
        update.message.reply_text(
            "❌ You're not in any active games or the game hasn't started yet."
        )
        return
    
    # Multiple games - use message ID system
    if len(active_games) > 1:
        import hashlib
        message_id = hashlib.md5(f"{user_id}_{current_time}_{message}".encode()).hexdigest()[:8]
        
        # Store message temporarily
        with game_state.lock:
            game_state.temp_anon_messages[message_id] = {
                'message': message,
                'user_id': user_id,
                'timestamp': current_time
            }
        
        keyboard = []
        for chat_id, game in active_games:
            try:
                chat = context.bot.get_chat(chat_id)
                group_name = chat.title or f"Game with {game['players'][game['host']]}"
            except:
                group_name = f"Game with {game['players'][game['host']]}"
            
            keyboard.append([
                InlineKeyboardButton(
                    group_name,
                    callback_data=f"anon_game:{chat_id}:{message_id}"
                )
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(
            "📌 Select which game to send your anonymous message to:",
            reply_markup=reply_markup
        )
        return
    
    # Single game
    chat_id = active_games[0][0]
    _send_anon_message(context, user_id, chat_id, message)

def anon_callback(update: Update, context: CallbackContext):
    """Handle game selection for anonymous messages"""
    query = update.callback_query
    query.answer()
    
    try:
        data = query.data.split(':')
        if len(data) != 3:
            query.edit_message_text("❌ Invalid request.")
            return
            
        chat_id = int(data[1])
        message_id = data[2]
        user_id = query.from_user.id
        
        # Get stored message
        with game_state.lock:
            message_data = game_state.temp_anon_messages.get(message_id)
        
        if not message_data:
            query.edit_message_text("❌ Message expired. Please try again.")
            return
        
        if message_data['user_id'] != user_id:
            query.edit_message_text("❌ Invalid request.")
            return
        
        message = message_data['message']
        
        # Verify game still exists
        game = game_state.get_game(chat_id)
        if not game or user_id not in game['players'] or game['state'] != 'started':
            query.edit_message_text("❌ Game no longer active.")
            with game_state.lock:
                game_state.temp_anon_messages.pop(message_id, None)
            return
        
        _send_anon_message(context, user_id, chat_id, message)
        query.edit_message_text("✅ Message sent anonymously!")
        
        # Clean up
        with game_state.lock:
            game_state.temp_anon_messages.pop(message_id, None)
        
    except Exception as e:
        logger.error(f"Error in anon_callback: {e}")
        query.edit_message_text("❌ Failed to send message.")

def _send_anon_message(context: CallbackContext, user_id: int, chat_id: int, message: str):
    """Actually send the anonymous message with proper error handling"""
    # Apply cooldown with thread safety
    with game_state.lock:
        if not hasattr(game_state, 'anon_cooldowns'):
            game_state.anon_cooldowns = {}
        game_state.anon_cooldowns[user_id] = time.time()
    
    try:
        # Verify game still exists
        game = game_state.get_game(chat_id)
        if not game or game['state'] != 'started':
            context.bot.send_message(
                user_id,
                "❌ Game no longer active. Message not sent."
            )
            return
        
        # Format and send message
        formatted_msg = (
            f"🕵️‍♂️ *Anonymous Message from a Player:*\n\n"
            f"{message.strip()}\n\n"
            f"_Use /anon in private chat with me to send anonymous messages_"
        )
        
        # Send to group
        context.bot.send_message(
            chat_id,
            formatted_msg,
            parse_mode='Markdown'
        )
        
        # Notify sender
        context.bot.send_message(
            user_id,
            "✅ Your anonymous message was sent to the game group!",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Failed to send anonymous message from {user_id}: {e}")
        try:
            context.bot.send_message(
                user_id,
                "❌ Failed to send your anonymous message. Please try again later.",
                parse_mode='Markdown'
            )
        except Exception as fallback_error:
            logger.error(f"Couldn't notify sender of failure: {fallback_error}")

def location_command(update: Update, context: CallbackContext):
    """Send location info to player"""
    chat_id = update.message.chat_id
    user_id = update.effective_user.id
    game = game_state.get_game(chat_id)
    
    if not game or game['state'] != 'started':
        update.message.reply_text("❌ Game hasn't started yet.")
        return
    
    if user_id not in game['players']:
        update.message.reply_text("⚠️ You're not in the game.")
        return
    
    # Public response
    update.message.reply_text("📬 Check your private messages for your role info.")
    
    # Private message with role info
    if isinstance(game['spy'], list) and user_id in game['spy']:
        partners = [s for s in game['spy'] if s != user_id]
        partners_names = ", ".join(game['players'][p] for p in partners)
        context.bot.send_message(
            user_id,
            f"🕵️ You are a SPY!\nPartners: {partners_names}",
            parse_mode='Markdown'
        )
    elif user_id == game.get('spy'):
        context.bot.send_message(user_id, "🕵️ You are the SPY!")
    elif user_id in game.get('double_agent', []):
        fake_location = get_random_location()
        context.bot.send_message(
            user_id,
            f"🧭 You are a civilian.\nLocation: *{fake_location}*",
            parse_mode='Markdown'
        )
    else:
        context.bot.send_message(
            user_id,
            f"🧭 You are a civilian.\nLocation: *{game['location']}*",
            parse_mode='Markdown'
        )

def vote(update: Update, context: CallbackContext):
    """Start voting process"""
    chat_id = update.message.chat_id
    game = game_state.get_game(chat_id)
    
    if not game or game['state'] != 'started':
        update.message.reply_text("❌ Voting not available now.")
        return
    
    # Cancel discussion timer if voting started manually
    cancel_timers(chat_id)
    start_voting(chat_id, context)

def start_voting(chat_id: int, context: CallbackContext):
    """Initiate voting phase"""
    game = game_state.get_game(chat_id)
    if not game or game['state'] != 'started':
        return
    
    game['votes'] = {}
    
    # Create voting buttons
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"vote:{uid}")]
        for uid, name in game['players'].items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    context.bot.send_message(
        chat_id,
        "🗳 *Who is the spy?*\nVote by selecting a player below:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    # Set voting timer
    mode_config = GAME_MODES.get(game['mode'], GAME_MODES['normal'])
    voting_time = mode_config['voting_time']
    
    def voting_timeout():
        game = game_state.get_game(chat_id)
        if game and game['state'] == 'started':
            context.bot.send_message(chat_id, "⏰ Voting time over!")
            finish_vote(chat_id, context)
    
    def voting_progress():
        game = game_state.get_game(chat_id)
        if game and game['state'] == 'started' and 'votes' in game:
            votes_received = len(game['votes'])
            total_players = len(game['players'])
            if votes_received < total_players:
                try:
                    context.bot.send_message(
                        chat_id,
                        f"📥 Votes received: {votes_received}/{total_players}",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to send voting progress: {e}")
    
    vote_timer = Timer(voting_time, voting_timeout)
    progress_timer = Timer(voting_time/2, voting_progress)
    
    vote_timer.start()
    progress_timer.start()
    
    game_state.add_timer(chat_id, vote_timer)
    game_state.add_timer(chat_id, progress_timer)

def vote_callback(update: Update, context: CallbackContext):
    """Handle vote button presses"""
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    game = game_state.get_game(chat_id)
    
    if not game or game['state'] != 'started':
        query.answer("Voting not active.")
        return
    
    if user_id not in game['players']:
        query.answer("You're not in this game.")
        return
    
    if user_id in game['votes']:
        query.answer("You already voted!")
        return
    
    voted_id = int(query.data.split(":")[1])
    game['votes'][user_id] = voted_id
    voted_name = game['players'].get(voted_id, "Unknown")
    
    query.answer(f"Voted for {voted_name}")
    
    # Check if all votes are in
    if len(game['votes']) == len(game['players']):
        finish_vote(chat_id, context)

def mode_callback(update: Update, context: CallbackContext):
    """Handle game mode selection"""
    query = update.callback_query
    chat_id = query.message.chat_id
    game = game_state.get_game(chat_id)
    
    if not game or game['state'] != 'mode_select':
        query.answer("Invalid selection.")
        return
    
    mode_id = query.data.split(":")[1]
    if mode_id not in GAME_MODES:
        query.answer("Invalid mode.")
        return
    
    game['mode'] = mode_id
    game['state'] = 'waiting'
    
    mode_info = GAME_MODES[mode_id]
    min_players = mode_info['min_players']
    
    query.answer(f"Selected: {mode_info['name']}")
    
    context.bot.edit_message_text(
        text=f"✅ *{mode_info['name']} selected!*\n"
             f"{mode_info['description']}\n"
             f"👥 Minimum players: {min_players}\n\n"
             f"Players, use /join to participate.",
        chat_id=chat_id,
        message_id=query.message.message_id,
        parse_mode='Markdown'
    )

def finish_vote(chat_id: int, context: CallbackContext):
    """Process voting results"""
    game = game_state.get_game(chat_id)
    if not game:
        return
    
    # Cancel any remaining timers
    cancel_timers(chat_id)
    
    votes = game['votes']
    if not votes:
        context.bot.send_message(chat_id, "❌ No votes received. Game aborted.")
        game_state.remove_game(chat_id)
        return
    
    # Count votes
    vote_counts = {}
    for voted_id in votes.values():
        vote_counts[voted_id] = vote_counts.get(voted_id, 0) + 1
    
    # Prepare vote breakdown
    breakdown = "🗳️ *Voting Results:*\n"
    for voter_id, voted_id in votes.items():
        voter_name = game['players'].get(voter_id, "Unknown")
        voted_name = game['players'].get(voted_id, "Unknown")
        breakdown += f"- {voter_name} → {voted_name}\n"
    
    # Determine who was voted out
    max_votes = max(vote_counts.values())
    top_voted = [uid for uid, count in vote_counts.items() if count == max_votes]
    
    if len(top_voted) > 1:
        # Tie - randomly select one
        chosen = random.choice(top_voted)
        context.bot.send_message(chat_id, "⚠️ Voting tie! Randomly selecting one...")
    else:
        chosen = top_voted[0]
    
    chosen_name = game['players'].get(chosen, "Unknown")
    context.bot.send_message(chat_id, breakdown, parse_mode='Markdown')
    
    # Update statistics for voters
    for voter_id in votes:
        if voter_id not in game_state.player_stats:
            game_state.player_stats[voter_id] = create_player_stats(game['players'][voter_id])
        
        # Check if they caught a spy
        if isinstance(game['spy'], list):
            if votes[voter_id] in game['spy']:
                game_state.player_stats[voter_id]['spies_caught'] += 1
        else:
            if votes[voter_id] == game['spy']:
                game_state.player_stats[voter_id]['spies_caught'] += 1
    
    # Handle special modes
    mode_config = GAME_MODES.get(game['mode'], GAME_MODES['normal'])
    
    if mode_config['special'] == 'team_spy':
        if chosen in game['spy']:
            # Store name before deletion
            chosen_name = game['players'][chosen]
            # Remove caught spy
            game['spy'] = [s for s in game['spy'] if s != chosen]
            del game['players'][chosen]
            
            if not game['spy']:
                # All spies caught
                context.bot.send_message(chat_id, "🎉 All spies caught! Civilians win!")
                end_game(chat_id, 'civilian_win', context)
            else:
                # Continue with remaining spies
                remaining_spies = ", ".join(game['players'][s] for s in game['spy'])
                context.bot.send_message(
                    chat_id,
                    f"✅ {chosen_name} was a spy! Remaining spies: {remaining_spies}",
                    parse_mode='Markdown'
                )
                start_voting(chat_id, context)
        else:
            # Innocent voted out
            spies = ", ".join(game['players'][s] for s in game['spy'])
            context.bot.send_message(
                chat_id,
                f"❌ {chosen_name} was innocent. Spies were: {spies}",
                parse_mode='Markdown'
            )
            end_game(chat_id, 'spy_win', context)
    
    elif mode_config['special'] in ['double_agent', 'chaos']:
        if chosen == game.get('spy'):
            # Real spy caught
            context.bot.send_message(
                chat_id,
                f"✅ {chosen_name} was the real spy! Civilians win!",
                parse_mode='Markdown'
            )
            end_game(chat_id, 'civilian_win', context)
        elif chosen in game.get('double_agent', []):
            # Double agent caught
            spy_name = game['players'].get(game['spy'], "Unknown")
            context.bot.send_message(
                chat_id,
                f"❌ {chosen_name} was a double agent! Real spy {spy_name} wins!",
                parse_mode='Markdown'
            )
            end_game(chat_id, 'spy_win', context)
        else:
            # Innocent voted out
            spy_name = game['players'].get(game['spy'], "Unknown")
            da_names = ", ".join(game['players'][da] for da in game.get('double_agent', []))
            context.bot.send_message(
                chat_id,
                f"❌ {chosen_name} was innocent.\n"
                f"Spy: {spy_name}\n"
                f"Double agents: {da_names or 'None'}",
                parse_mode='Markdown'
            )
            end_game(chat_id, 'spy_win', context)
    
    else:  # Normal mode
        if chosen == game['spy']:
            # Spy caught
            context.bot.send_message(
                chat_id,
                f"✅ {chosen_name} was the spy! Civilians win! 🎉",
                parse_mode='Markdown'
            )
            end_game(chat_id, 'civilian_win', context)
        else:
            # Innocent voted out
            spy_name = game['players'].get(game['spy'], "Unknown")
            context.bot.send_message(
                chat_id,
                f"❌ {chosen_name} was innocent. The spy was {spy_name}!",
                parse_mode='Markdown'
            )
            
            # Spy gets to guess
            game['awaiting_guess'] = True
            context.bot.send_message(
                game['spy'],
                "🕵️ You survived! Guess the location (reply here):",
                parse_mode='Markdown'
            )
            
            # Set guess timer
            guess_time = mode_config['guess_time']
            
            def guess_timeout():
               game = game_state.get_game(chat_id)
               if game and game.get('awaiting_guess', False):
                    try:
                        context.bot.send_message(
                            chat_id,
                            "⏰ Spy failed to guess in time. Civilians win!",
                            parse_mode='Markdown'
                        )
                        end_game(chat_id, 'civilian_win', context)
                    except Exception as e:
                        logger.error(f"Failed to send timeout message: {e}")
            
            timer = Timer(guess_time, guess_timeout)
            timer.start()
            game_state.add_timer(chat_id, timer)

def handle_guess(update: Update, context: CallbackContext):
    """Process spy's location guess"""
    chat_id = update.message.chat_id
    user_id = update.effective_user.id
    game = game_state.get_game(chat_id)
    
    if not game or not game['awaiting_guess'] or user_id != game.get('spy'):
        return
    
    guess = update.message.text.strip().lower()
    correct = game['location'].lower()
    
    # Cancel guess timer
    cancel_timers(chat_id)
    game['awaiting_guess'] = False
    
    # Check guess
    if guess == correct:
        context.bot.send_message(
            chat_id,
            f"🎉 The spy guessed correctly! Location was *{game['location']}*. Spy wins!",
            parse_mode='Markdown'
        )
        end_game(chat_id, 'spy_win', context)
    else:
        context.bot.send_message(
            chat_id,
            f"❌ Spy guessed '{guess}'. Correct was *{game['location']}*. Civilians win!",
            parse_mode='Markdown'
        )
        end_game(chat_id, 'civilian_win', context)

def end_game(chat_id: int, result: str, context: CallbackContext = None):
    """Finalize game and update statistics"""
    game = game_state.get_game(chat_id)
    if not game:
        return
    
    # Update stats for all players
    for player_id in game['players']:
        was_spy = (
            player_id == game.get('spy') or 
            (isinstance(game.get('spy'), list) and player_id in game['spy'])
        )
        update_player_stats(player_id, game['players'][player_id], result, was_spy, context)
    
    # Clean up
    game_state.remove_game(chat_id)

def endgame(update: Update, context: CallbackContext):
    """Manually end current game"""
    chat_id = update.message.chat_id
    user = update.effective_user
    game = game_state.get_game(chat_id)
    
    if not game:
        update.message.reply_text("❌ No game to end.")
        return

    # Permission checks
    is_bot_admin = is_admin(user.id)
    is_host = user.id == game['host']
    is_group_admin = False

     # Check Telegram group admin status (if in group)
    try:
        if update.effective_chat.type in ['group', 'supergroup']:
            member = context.bot.get_chat_member(chat_id, user.id)
            is_group_admin = member.status in ['administrator', 'creator']
    except Exception as e:
        logger.warning(f"Failed to check admin status: {e}")

    # Reject unauthorized users
    if not (is_host or is_bot_admin or is_group_admin):
        update.message.reply_text(
            "⛔ Only game host (@{host}), bot admins, or group admins can end the game.".format(
                host=game['players'].get(game['host'], "unknown")
            )
        )
        return
    
    # Clean up game
    game_state.remove_game(chat_id)

     # Success message
    if is_host:
        update.message.reply_text("🛑 Game ended by host.")
    elif is_bot_admin:
        update.message.reply_text("🛑 Game ended by bot admin.")
    else:
        update.message.reply_text("🛑 Game ended by group admin.")

def show_stats(update: Update, context: CallbackContext):
    """Display player statistics"""
    user_id = update.effective_user.id
    stats = game_state.player_stats.get(user_id, {})
    
    if not stats:
        update.message.reply_text("📊 No games played yet!")
        return
    
    # Calculate win rates
    spy_win_rate = (stats['spy_wins'] / stats['spy_games'] * 100) if stats['spy_games'] > 0 else 0
    civilian_win_rate = (stats['civilian_wins'] / stats['civilian_games'] * 100) if stats['civilian_games'] > 0 else 0
    
    stats_text = f"""📊 *{stats['name']}'s Stats:*

🎮 Games Played: {stats['games_played']}
🕵️ Spy Games: {stats['spy_games']} ({spy_win_rate:.1f}% win rate)
👥 Civilian Games: {stats['civilian_games']} ({civilian_win_rate:.1f}% win rate)
🎯 Spies Caught: {stats['spies_caught']}

🏅 Achievements: {len(stats['achievements'])}/{len(ACHIEVEMENTS)}"""
    
    update.message.reply_text(stats_text, parse_mode='Markdown')
    
    # Show unlocked achievements if any
    if stats['achievements']:
        achievements_text = "🏅 *Your Achievements:*\n" + "\n".join(
            f"• {ach}" for ach in stats['achievements']
        )
        update.message.reply_text(achievements_text, parse_mode='Markdown')

def show_leaderboard(update: Update, context: CallbackContext):
    """Display leaderboard"""
    if not game_state.player_stats:
        update.message.reply_text("📊 No stats available yet!")
        return
    
    # Prepare stats with calculated win rates
    enhanced_stats = []
    for user_id, stats in game_state.player_stats.items():
        spy_rate = (stats['spy_wins'] / stats['spy_games'] * 100) if stats['spy_games'] > 0 else 0
        civ_rate = (stats['civilian_wins'] / stats['civilian_games'] * 100) if stats['civilian_games'] > 0 else 0
        enhanced_stats.append({
            **stats,
            'spy_win_rate': spy_rate,
            'civilian_win_rate': civ_rate,
            'user_id': user_id
        })
    
    # Top spies by wins
    top_spies = sorted(
        enhanced_stats,
        key=lambda x: (x['spy_wins'], x['spy_win_rate']),
        reverse=True
    )[:5]
    
    # Top civilians by win rate (min 10 games)
    top_civilians = sorted(
        [s for s in enhanced_stats if s['civilian_games'] >= 10],
        key=lambda x: (x['civilian_win_rate'], x['civilian_wins']),
        reverse=True
    )[:5]
    
    # Most games played
    most_active = sorted(
        enhanced_stats,
        key=lambda x: x['games_played'],
        reverse=True
    )[:5]
    
    # Build leaderboard message
    leaderboard = "🏆 *Leaderboard*\n\n"
    
    leaderboard += "🕵️ *Top Spies (Wins):*\n"
    for i, stat in enumerate(top_spies, 1):
        leaderboard += f"{i}. {stat['name']}: {stat['spy_wins']} wins ({stat['spy_win_rate']:.1f}%)\n"
    
    leaderboard += "\n👥 *Top Civilians (Win Rate):*\n"
    for i, stat in enumerate(top_civilians, 1):
        leaderboard += f"{i}. {stat['name']}: {stat['civilian_win_rate']:.1f}% ({stat['civilian_wins']}/{stat['civilian_games']})\n"
    
    leaderboard += "\n🎮 *Most Active Players:*\n"
    for i, stat in enumerate(most_active, 1):
        leaderboard += f"{i}. {stat['name']}: {stat['games_played']} games\n"
    
    update.message.reply_text(leaderboard, parse_mode='Markdown')

def show_achievements(update: Update, context: CallbackContext):
    """Display all achievements and player progress"""
    user_id = update.effective_user.id
    stats = game_state.player_stats.get(user_id, create_player_stats(update.effective_user.first_name))
    
    achievements_text = "🏅 *Achievements List:*\n\n"
    
    for ach_id, ach_data in ACHIEVEMENTS.items():
        unlocked = ach_data['name'] in stats['achievements']
        prefix = "🔓" if unlocked else "🔒"
        achievements_text += f"{prefix} *{ach_data['name']}*"
        
        if not unlocked:
            achievements_text += " (Locked)"
        
        achievements_text += "\n"
    
    update.message.reply_text(achievements_text, parse_mode='Markdown')

def create_player_stats(name: str) -> dict:
    """Create a new player stats dictionary"""
    return {
        'games_played': 0,
        'spy_wins': 0,
        'civilian_wins': 0,
        'spy_games': 0,
        'civilian_games': 0,
        'spies_caught': 0,
        'achievements': [],
        'name': name,
        'first_game': datetime.now().isoformat(),
        'last_game': None
    }

def update_player_stats(user_id: int, name: str, result: str, was_spy: bool, context: CallbackContext = None):
    """Update player statistics after game"""
    if user_id not in game_state.player_stats:
        game_state.player_stats[user_id] = create_player_stats(name)
    
    stats = game_state.player_stats[user_id]
    stats['games_played'] += 1
    stats['last_game'] = datetime.now().isoformat()
    stats['name'] = name  # Update name in case it changed
    
    if was_spy:
        stats['spy_games'] += 1
        if result == 'spy_win':
            stats['spy_wins'] += 1
    else:
        stats['civilian_games'] += 1
        if result == 'civilian_win':
            stats['civilian_wins'] += 1
    
    # Check for new achievements
    check_achievements(user_id, stats, context)


def check_achievements(user_id: int, stats: dict, context: CallbackContext = None):
    """Check and unlock new achievements"""
    unlocked = set(stats['achievements'])
    new_achievements = []
    
    # Calculate win rates for achievement conditions
    spy_win_rate = (stats['spy_wins'] / stats['spy_games'] * 100) if stats['spy_games'] > 0 else 0
    civ_win_rate = (stats['civilian_wins'] / stats['civilian_games'] * 100) if stats['civilian_games'] > 0 else 0
    
    enhanced_stats = {
        **stats,
        'spy_win_rate': spy_win_rate,
        'civilian_win_rate': civ_win_rate
    }
    
    # Check each achievement
    for ach_id, ach_data in ACHIEVEMENTS.items():
        ach_name = ach_data['name']
        if ach_name not in unlocked and ach_data['condition'](enhanced_stats):
            new_achievements.append(ach_name)
    
    # Add new achievements
    if new_achievements:
        stats['achievements'].extend(new_achievements)
        # Notify player if possible
        try:
            message = "🏆 *New Achievement(s) Unlocked!*\n" + "\n".join(f"🎖️ {ach}" for ach in new_achievements)
            if context:
                context.bot.send_message(user_id, message, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Failed to notify player {user_id} of achievements: {e}")   

def admin_stats(update: Update, context: CallbackContext):
    """Admin command to view bot statistics"""
    if not is_admin(update.effective_user.id):
        update.message.reply_text("⛔ Admin only.")
        return
      
    active_games = len(game_state.games)
    total_players = sum(len(g['players']) for g in game_state.games.values())
    registered_players = len(game_state.player_stats)
    
    update.message.reply_text(
        f"📊 *Admin Stats*\n\n"
        f"Active Games: {active_games}\n"
        f"Active Players: {total_players}\n"
        f"Registered Players: {registered_players}",
        parse_mode='Markdown'
    )

def error_handler(update: Update, context: CallbackContext):
    """Log errors and notify admins"""
    logger.error(f"Update {update} caused error {context.error}")
    
    # Notify admins
    for admin_id in ADMIN_IDS:
        try:
            context.bot.send_message(
                admin_id,
                f"⚠️ Error occurred:\n{context.error}\n\nIn update:\n{update}",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")

# --- Main ---
def main():
    """Start the bot"""
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    # Command handlers
    commands = [
        ('start', start),
        ('guide', guide),
        ('intel', intel),
        ('modes', modes),
        ('newgame', newgame),
        ('join', join),
        ('leave', leave),
        ('players', players),
        ('begin', begin),
        ('location', location_command),
        ('vote', vote),
        ('endgame', endgame),
        ('stats', show_stats),
        ('leaderboard', show_leaderboard),
        ('achievements', show_achievements),
        ('adminstats', admin_stats),
        ('anon', anon),
    ]
    
    for cmd, handler in commands:
        dp.add_handler(CommandHandler(cmd, handler))
    
    # Callback handlers
    dp.add_handler(CallbackQueryHandler(vote_callback, pattern=r"^vote:"))
    dp.add_handler(CallbackQueryHandler(mode_callback, pattern=r"^mode:"))
    dp.add_handler(CallbackQueryHandler(anon_callback, pattern=r"^anon_game:"))
    
    # Message handler for spy guesses
    dp.add_handler(MessageHandler(Filters.text & Filters.private, handle_guess))
    
    # Error handler
    dp.add_error_handler(error_handler)
    
    # Start bot
    updater.start_polling()
    logger.info("Spy Bot is now running...")
    updater.idle()

if __name__ == "__main__":
    main()
    