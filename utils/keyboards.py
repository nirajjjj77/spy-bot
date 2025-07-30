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
    
    def get_voting_keyboard(self, players_data: List[Dict], game_id: str) -> InlineKeyboardMarkup:
        """Get voting keyboard with all players."""
        keyboard = []
        
        # Create buttons for each player (2 per row)
        for i in range(0, len(players_data), 2):
            row = []
            
            # First player in row
            player1 = players_data[i]
            button1 = InlineKeyboardButton(
                f"🗳️ {player1['display_name']}", 
                callback_data=f"vote_{player1['user_id']}_{game_id}"
            )
            row.append(button1)
            
            # Second player in row (if exists)
            if i + 1 < len(players_data):
                player2 = players_data[i + 1]
                button2 = InlineKeyboardButton(
                    f"🗳️ {player2['display_name']}", 
                    callback_data=f"vote_{player2['user_id']}_{game_id}"
                )
                row.append(button2)
            
            keyboard.append(row)
        
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