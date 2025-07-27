import time
from threading import Lock, Timer
from typing import Dict, List, Optional, Tuple

from utils.logger import logger

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
        """ENHANCED: Always cleanup timers when removing game"""
        with self.lock:
            # First cancel all timers
            if chat_id in self.active_timers:
                for timer in self.active_timers[chat_id]:
                    try:
                        timer.cancel()  # Cancel the timer
                    except Exception as e:
                        print(f"Error canceling timer: {e}")
                del self.active_timers[chat_id]
            
            # Then remove game
            if chat_id in self.games:
                del self.games[chat_id]

    def add_timer(self, chat_id: int, timer: Timer):
        """ENHANCED: Better timer tracking"""
        with self.lock:
            if chat_id not in self.active_timers:
                self.active_timers[chat_id] = []
            self.active_timers[chat_id].append(timer)

    def clear_timers(self, chat_id: int):
        """ENHANCED: More thorough timer cleanup"""
        with self.lock:
            if chat_id in self.active_timers:
                for timer in self.active_timers[chat_id]:
                    try:
                        if timer.is_alive():  # Check if timer is still running
                            timer.cancel()
                    except Exception as e:
                        print(f"Error clearing timer: {e}")
                self.active_timers[chat_id] = []  # Clear the list

    def safe_timer_operation(self, chat_id: int, operation_name: str, timer_func, delay: float):
        """NEW: Safe way to create timers with automatic cleanup"""
        def wrapped_timer_func():
            try:
                # Check if game still exists before executing
                if self.get_game(chat_id):
                    timer_func()
            except Exception as e:
                logger.error(f"Timer {operation_name} error: {e}", exc_info=True)
        timer = Timer(delay, wrapped_timer_func)
        timer.start()
        self.add_timer(chat_id, timer)
        return timer

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

game_state = GameState()

def validate_game_state(chat_id: int, required_state: str = None, user_id: int = None) -> Tuple[bool, str, dict]:
    """Comprehensive game state validation - FIXED VERSION"""
    game = game_state.get_game(chat_id)  # ✅ Now this is correct!
    
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