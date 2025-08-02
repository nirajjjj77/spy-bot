import asyncio
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext

from game.game_logic import GameLogic
from database.db_manager import DatabaseManager
from utils.message_formatter import MessageFormatter
from utils.keyboards import KeyboardBuilder

logger = logging.getLogger(__name__)

class GameHandlers:
    def __init__(self):
        self.game_logic = GameLogic()
        self.db = DatabaseManager()
        self.formatter = MessageFormatter()
        self.keyboard_builder = KeyboardBuilder()
        
        # Track active timers
        self.discussion_timers = {}
        self.voting_timers = {}
    
    async def start(self, update: Update, context: CallbackContext):
        """Start command - welcome message."""
        message = self.formatter.get_welcome_message()
        await update.message.reply_text(message, parse_mode='HTML')
    
    async def help_command(self, update: Update, context: CallbackContext):
        """Help command - show available commands."""
        message = self.formatter.get_help_message()
        await update.message.reply_text(message, parse_mode='HTML')
    
    async def new_game(self, update: Update, context: CallbackContext):
        """Create a new game."""
        chat_id = update.effective_chat.id
        user = update.effective_user
        
        # Check if it's a group chat
        if update.effective_chat.type == 'private':
            await update.message.reply_text(
                "❌ This game can only be played in groups!\n"
                "Add me to a group and try again."
            )
            return
        
        # Try to create new game
        game_id = self.game_logic.create_game(chat_id)
        
        if not game_id:
            await update.message.reply_text(
                "❌ There's already an active game in this chat!\n"
                "Use /cancel to cancel the current game first."
            )
            return
        
        # Auto-join the creator
        success = self.game_logic.join_game(
            game_id, 
            user.id, 
            user.username, 
            user.first_name, 
            user.last_name
        )
        
        if success:
            message = self.formatter.get_new_game_message(user.first_name)
            keyboard = self.keyboard_builder.get_join_game_keyboard()
            
            await update.message.reply_text(
                message, 
                reply_markup=keyboard, 
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text("❌ Failed to create game. Try again.")
    
    async def join_game(self, update: Update, context: CallbackContext):
        """Join an existing game."""
        chat_id = update.effective_chat.id
        user = update.effective_user
        
        # Get active game
        game = self.game_logic.get_active_game_by_chat(chat_id)
        
        if not game:
            await update.message.reply_text(
                "❌ No active game found!\n"
                "Use /newgame to start a new game."
            )
            return
        
        if game['status'] != 'waiting':
            await update.message.reply_text(
                "❌ Game has already started!\n"
                "Wait for the current game to finish."
            )
            return
        
        # Try to join
        success = self.game_logic.join_game(
            game['game_id'],
            user.id,
            user.username,
            user.first_name,
            user.last_name
        )
        
        if success:
            # Get updated game info
            updated_game = self.game_logic.get_game_info(game['game_id'])
            message = self.formatter.get_player_joined_message(
                user.first_name, 
                len(updated_game['players'])
            )
            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text(
                "❌ Couldn't join the game!\n"
                "You might already be in the game or it's full (max 8 players)."
            )
    
    async def start_game(self, update: Update, context: CallbackContext):
        """Start the game."""
        chat_id = update.effective_chat.id
        user = update.effective_user
        
        # Get active game
        game = self.game_logic.get_active_game_by_chat(chat_id)
        
        if not game:
            await update.message.reply_text("❌ No active game found!")
            return
        
        if game['status'] != 'waiting':
            await update.message.reply_text("❌ Game has already started!")
            return
        
        # Check if user is in the game
        if not any(p['user_id'] == user.id for p in game['players']):
            await update.message.reply_text("❌ You must join the game first!")
            return
        
        # Check if game can start
        can_start, message = self.game_logic.can_start_game(game['game_id'])
        if not can_start:
            await update.message.reply_text(f"❌ {message}")
            return
        
        # Start the game
        game_data = self.game_logic.start_game(game['game_id'])
        
        if not game_data:
            await update.message.reply_text("❌ Failed to start game!")
            return
        
        # Send role messages to players
        await self.send_role_messages(context, game_data)
        
        # Send game started message to group
        message = self.formatter.get_game_started_message(len(game_data['players']))
        await update.message.reply_text(message, parse_mode='HTML')
        
        # Start discussion timer
        await self.start_discussion_timer(context, game_data['game_id'], chat_id)
    
    async def send_role_messages(self, context: CallbackContext, game_data):
        """Send private messages to players about their roles."""
        spy_id = game_data['spy_id']
        location = game_data['location']
        
        for player in game_data['players']:
            user_id = player['user_id']
            is_spy = user_id == spy_id
            
            try:
                if is_spy:
                    message = self.formatter.get_spy_role_message(location)
                else:
                    message = self.formatter.get_civilian_role_message(location)
                
                await context.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Failed to send role message to user {user_id}: {e}")
    
    async def start_discussion_timer(self, context: CallbackContext, game_id: str, chat_id: int):
        """Start discussion phase timer."""
        # Cancel existing timer if any
        if game_id in self.discussion_timers:
            self.discussion_timers[game_id].cancel()
        
        async def discussion_timer():
            try:
                # Wait for 5 minutes
                await asyncio.sleep(300)  # 5 minutes
                
                # Check if game is still in discussion phase
                game = self.game_logic.get_game_info(game_id)
                if game and game['status'] == 'discussion':
                    # Start voting phase
                    await self.start_voting_phase(context, game_id, chat_id)
                
            except asyncio.CancelledError:
                pass
            finally:
                if game_id in self.discussion_timers:
                    del self.discussion_timers[game_id]
        
        # Create and start timer task
        self.discussion_timers[game_id] = asyncio.create_task(discussion_timer())
    
    async def start_voting_phase(self, context: CallbackContext, game_id: str, chat_id: int):
        """Start voting phase."""
        success = self.game_logic.start_voting_phase(game_id)
        
        if not success:
            return
        
        # Get voting keyboard
        players_data = self.game_logic.get_voting_keyboard_data(game_id)
        keyboard = self.keyboard_builder.get_voting_keyboard(players_data, game_id)
        
        message = self.formatter.get_voting_started_message()
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=message,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        # Start voting timer
        await self.start_voting_timer(context, game_id, chat_id)
    
    async def start_voting_timer(self, context: CallbackContext, game_id: str, chat_id: int):
        """Start voting phase timer."""
        # Cancel existing timer if any
        if game_id in self.voting_timers:
            self.voting_timers[game_id].cancel()
        
        async def voting_timer():
            try:
                # Wait for 30 seconds
                await asyncio.sleep(30)
                
                # Check if game is still in voting phase
                game = self.game_logic.get_game_info(game_id)
                if game and game['status'] == 'voting':
                    # End voting and show results
                    await self.end_voting_phase(context, game_id, chat_id)
                
            except asyncio.CancelledError:
                pass
            finally:
                if game_id in self.voting_timers:
                    del self.voting_timers[game_id]
        
        # Create and start timer task
        self.voting_timers[game_id] = asyncio.create_task(voting_timer())
    
    async def end_voting_phase(self, context: CallbackContext, game_id: str, chat_id: int):
        """End voting phase and show results."""
        results = self.game_logic.calculate_results(game_id)
        
        if not results:
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Error calculating results!"
            )
            return
        
        # Send results message
        message = self.formatter.get_results_message(results)
        await context.bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode='HTML'
        )
        
        # Clean up
        self.game_logic.cleanup_game(game_id)
        if game_id in self.voting_timers:
            del self.voting_timers[game_id]
    
    async def button_callback(self, update: Update, context: CallbackContext):
        """Handle inline keyboard button presses."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user = update.effective_user
        
        if data.startswith('join_game'):
            await self.handle_join_button(query, user)
        elif data.startswith('vote_'):
            await self.handle_vote_button(query, user, context)
    
    async def handle_join_button(self, query, user):
        """Handle join game button press."""
        chat_id = query.message.chat_id
        
        # Get active game
        game = self.game_logic.get_active_game_by_chat(chat_id)
        
        if not game:
            await query.edit_message_text("❌ No active game found!")
            return
        
        if game['status'] != 'waiting':
            await query.edit_message_text("❌ Game has already started!")
            return
        
        # Try to join
        success = self.game_logic.join_game(
            game['game_id'],
            user.id,
            user.username,
            user.first_name,
            user.last_name
        )
        
        if success:
            # Get updated game info
            updated_game = self.game_logic.get_game_info(game['game_id'])
            message = self.formatter.get_waiting_room_message(updated_game['players'])
            keyboard = self.keyboard_builder.get_join_game_keyboard()
            
            await query.edit_message_text(
                message,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        else:
            await query.message.reply_text(
                f"❌ {user.first_name}, you couldn't join the game!\n"
                "You might already be in the game or it's full."
            )
    
    async def handle_vote_button(self, query, user, context: CallbackContext):
        """Handle vote button press."""
        data_parts = query.data.split('_')
        if len(data_parts) != 3:
            await query.answer("❌ Invalid vote data!")
            return
        
        voted_for_id = int(data_parts[1])
        game_id = data_parts[2]
    
        # Check if game exists and is in voting phase
        game = self.game_logic.get_game_info(game_id)
        if not game or game['status'] != 'voting':
            await query.answer("❌ Voting is not active!")
            return
        
        # Check if user is in the game
        if not any(p['user_id'] == user.id for p in game['players']):
            await query.answer("❌ You're not in this game!")
            return
    
        # Check if user already voted - FIX: Use correct key name
        votes = game.get('votes', {})
        if str(user.id) in votes:
            await query.answer("❌ You have already voted!")
            return
        
        # Cast vote
        success = self.game_logic.cast_vote(game_id, user.id, voted_for_id)
        
        if not success:
            await query.answer("❌ Couldn't cast your vote!")
            return
        
        # Get voted player name - Get fresh game data after vote
        updated_game = self.game_logic.get_game_info(game_id)
        voted_player = next(
            (p for p in updated_game['players'] if p['user_id'] == voted_for_id), 
            None
        )
        
        voted_name = voted_player['first_name'] if voted_player else "Unknown"
        
        await query.answer(f"✅ You voted for {voted_name}!")
        
        # Send confirmation message to the chat
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"✅ {user.first_name} voted for {voted_name}!"
        )

        # Check if all players have voted - use fresh game data
        if self.game_logic.check_all_voted(game_id):
            # Cancel voting timer
            if game_id in self.voting_timers:
                self.voting_timers[game_id].cancel()
            
            # End voting immediately
            await self.end_voting_phase(context, game_id, query.message.chat_id)
    
    async def show_players(self, update: Update, context: CallbackContext):
        """Show current players in the game."""
        chat_id = update.effective_chat.id
        
        game = self.game_logic.get_active_game_by_chat(chat_id)
        
        if not game:
            await update.message.reply_text("❌ No active game found!")
            return
        
        message = self.formatter.get_current_players_message(game)
        await update.message.reply_text(message, parse_mode='HTML')
    
    async def show_leaderboard(self, update: Update, context: CallbackContext):
        """Show leaderboard."""
        leaderboard = self.db.get_leaderboard(10)
        
        if not leaderboard:
            await update.message.reply_text(
                "📊 No games played yet!\n"
                "Start playing to see the leaderboard."
            )
            return
        
        message = self.formatter.get_leaderboard_message(leaderboard)
        await update.message.reply_text(message, parse_mode='HTML')
    
    async def show_stats(self, update: Update, context: CallbackContext):
        """Show individual player stats."""
        user_id = update.effective_user.id
        stats = self.db.get_player_stats(user_id)
        
        if not stats:
            await update.message.reply_text(
                "📊 You haven't played any games yet!\n"
                "Use /newgame to start your first game."
            )
            return
        
        message = self.formatter.get_player_stats_message(stats)
        await update.message.reply_text(message, parse_mode='HTML')
    
    async def cancel_game(self, update: Update, context: CallbackContext):
        """Cancel current game."""
        chat_id = update.effective_chat.id
        user = update.effective_user
        
        game = self.game_logic.get_active_game_by_chat(chat_id)
        
        if not game:
            await update.message.reply_text("❌ No active game found!")
            return
        
        # Check if user is in the game or is admin
        is_admin = False
        try:
            chat_member = await context.bot.get_chat_member(chat_id, user.id)
            is_admin = chat_member.status in ['administrator', 'creator']
        except:
            pass
        
        user_in_game = any(p['user_id'] == user.id for p in game['players'])
        
        if not (is_admin or user_in_game):
            await update.message.reply_text(
                "❌ Only players in the game or group admins can cancel the game!"
            )
            return
        
        # Cancel the game
        success = self.game_logic.cancel_game(game['game_id'])
        
        if success:
            # Cancel any running timers
            if game['game_id'] in self.discussion_timers:
                self.discussion_timers[game['game_id']].cancel()
                del self.discussion_timers[game['game_id']]
            
            if game['game_id'] in self.voting_timers:
                self.voting_timers[game['game_id']].cancel()
                del self.voting_timers[game['game_id']]
            
            await update.message.reply_text(
                "🚫 Game cancelled successfully!\n"
                "Use /newgame to start a new game."
            )
        else:
            await update.message.reply_text("❌ Failed to cancel game!")
    
    async def error_handler(self, update: Update, context: CallbackContext):
        """Handle errors."""
        logger.error(f"Update {update} caused error {context.error}")
        
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ An error occurred! Please try again."
            )