from typing import List, Dict
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

class KeyboardBuilder:
    def __init__(self):
        pass
    
    def get_join_game_keyboard(self) -> InlineKeyboardMarkup:
        """Get join game keyboard."""
        keyboard = [
            [InlineKeyboardButton("🎮 Join Game", callback_data="join_game")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def get_admin_keyboard(self) -> InlineKeyboardMarkup:
        """Get admin panel keyboard."""
        keyboard = [
            [
                InlineKeyboardButton("📊 Stats", callback_data="admin_stats"),
                InlineKeyboardButton("🎮 Games", callback_data="admin_games")
            ],
            [
                InlineKeyboardButton("👥 Players", callback_data="admin_players"),
                InlineKeyboardButton("🔧 Tools", callback_data="admin_tools")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def get_game_control_keyboard(self, game_id: str) -> InlineKeyboardMarkup:
        """Get game control keyboard for admins."""
        keyboard = [
            [
                InlineKeyboardButton("⏹️ End Game", callback_data=f"admin_end_{game_id}"),
                InlineKeyboardButton("📊 Game Stats", callback_data=f"admin_game_stats_{game_id}")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def get_confirmation_keyboard(self, action: str, target_id: str) -> InlineKeyboardMarkup:
        """Get confirmation keyboard for admin actions."""
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_{action}_{target_id}"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_action")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)