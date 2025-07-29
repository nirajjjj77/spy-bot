import random
import time
import re
from typing import Tuple, List

from utils.constants import ADMIN_IDS
from utils.logger import logger
from utils.game_state import game_state
from utils.constants import ERROR_MESSAGES, GAME_MODES, LOCATIONS

from telegram.ext import CallbackContext

def escape_markdown(text: str) -> str:
    """Escape special Markdown characters to avoid parse errors"""
    return re.sub(r'([_*[\]()~`>#+-=|{}.!])', r'\\\1', text)

def is_admin(user_id: int) -> bool:
    """Secure admin verification"""
    if not ADMIN_IDS:
        logger.warning("No admin IDs configured")
        return False
    return user_id in ADMIN_IDS

def validate_input(text: str, max_length: int = 500, min_length: int = 1, allow_markdown: bool = False) -> Tuple[bool, str]:
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

def cancel_timers(chat_id: int):
    """Cancel all active timers for a game"""
    game_state.clear_timers(chat_id)

def emergency_cleanup():
    """NEW: Emergency cleanup function for bot shutdown"""
    with game_state.lock:
        for chat_id in list(game_state.active_timers.keys()):
            game_state.clear_timers(chat_id)
        game_state.active_timers.clear()

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

def check_rate_limit(user_id: int, action: str, limit_seconds: int = 60) -> Tuple[bool, int]:
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
    
def get_error_message(key: str, *args) -> str:
    """Get formatted error message"""
    return ERROR_MESSAGES.get(key, "❌ An error occurred.").format(*args)