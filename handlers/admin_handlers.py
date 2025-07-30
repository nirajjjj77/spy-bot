import logging
from telegram import Update
from telegram.ext import CallbackContext

from game.game_logic import GameLogic
from database.db_manager import DatabaseManager
from utils.message_formatter import MessageFormatter

logger = logging.getLogger(__name__)

class AdminHandlers:
    def __init__(self):
        self.game_logic = GameLogic()
        self.db = DatabaseManager()
        self.formatter = MessageFormatter()
        
        # List of admin user IDs (you can modify this or store in database)
        self.admin_ids = []  # Add your admin user IDs here
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin."""
        return user_id in self.admin_ids
    
    async def is_chat_admin(self, context: CallbackContext, chat_id: int, user_id: int) -> bool:
        """Check if user is admin in the chat."""
        try:
            chat_member = await context.bot.get_chat_member(chat_id, user_id)
            return chat_member.status in ['administrator', 'creator']
        except:
            return False
    
    async def admin_panel(self, update: Update, context: CallbackContext):
        """Show admin panel with statistics."""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Check if user is admin (either bot admin or chat admin)
        is_bot_admin = self.is_admin(user_id)
        is_chat_admin = await self.is_chat_admin(context, chat_id, user_id)
        
        if not (is_bot_admin or is_chat_admin):
            await update.message.reply_text("❌ You don't have admin permissions!")
            return
        
        # Get admin statistics
        stats = self.get_admin_stats()
        message = self.formatter.get_admin_panel_message(stats)
        
        await update.message.reply_text(message, parse_mode='HTML')
    
    def get_admin_stats(self) -> dict:
        """Get admin statistics."""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        try:
            # Total games
            cursor.execute("SELECT COUNT(*) FROM games")
            total_games = cursor.fetchone()[0]
            
            # Active games
            cursor.execute("SELECT COUNT(*) FROM games WHERE status IN ('waiting', 'discussion', 'voting')")
            active_games = cursor.fetchone()[0]
            
            # Completed games
            cursor.execute("SELECT COUNT(*) FROM games WHERE status = 'ended'")
            completed_games = cursor.fetchone()[0]
            
            # Total players
            cursor.execute("SELECT COUNT(*) FROM players")
            total_players = cursor.fetchone()[0]
            
            # Games today
            cursor.execute("SELECT COUNT(*) FROM games WHERE DATE(created_at) = DATE('now')")
            games_today = cursor.fetchone()[0]
            
            # Most active player
            cursor.execute("""
                SELECT first_name, username, games_played 
                FROM players 
                WHERE games_played > 0 
                ORDER BY games_played DESC 
                LIMIT 1
            """)
            most_active = cursor.fetchone()
            
            # Win rates
            cursor.execute("SELECT AVG(CAST(games_won AS FLOAT) / games_played * 100) FROM players WHERE games_played > 0")
            avg_win_rate = cursor.fetchone()[0] or 0
            
            return {
                'total_games': total_games,
                'active_games': active_games,
                'completed_games': completed_games,
                'total_players': total_players,
                'games_today': games_today,
                'most_active': most_active,
                'avg_win_rate': avg_win_rate
            }
            
        except Exception as e:
            logger.error(f"Error getting admin stats: {e}")
            return {}
        finally:
            conn.close()
    
    async def end_game(self, update: Update, context: CallbackContext):
        """Force end current game (admin only)."""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Check if user is admin
        is_bot_admin = self.is_admin(user_id)
        is_chat_admin = await self.is_chat_admin(context, chat_id, user_id)
        
        if not (is_bot_admin or is_chat_admin):
            await update.message.reply_text("❌ You don't have admin permissions!")
            return
        
        # Get active game
        game = self.game_logic.get_active_game_by_chat(chat_id)
        
        if not game:
            await update.message.reply_text("❌ No active game found!")
            return
        
        # Force end the game
        success = self.game_logic.cancel_game(game['game_id'])
        
        if success:
            await update.message.reply_text(
                "🔨 Game forcefully ended by admin!\n"
                "Use /newgame to start a new game."
            )
        else:
            await update.message.reply_text("❌ Failed to end game!")
    
    async def reset_player_stats(self, update: Update, context: CallbackContext):
        """Reset a player's statistics (bot admin only)."""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            await update.message.reply_text("❌ This command is only available to bot administrators!")
            return
        
        # Get target user ID from command arguments
        if not context.args:
            await update.message.reply_text(
                "Usage: /resetstats <user_id>\n"
                "Example: /resetstats 123456789"
            )
            return
        
        try:
            target_user_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID!")
            return
        
        # Reset stats
        success = self.reset_user_stats(target_user_id)
        
        if success:
            await update.message.reply_text(f"✅ Stats reset for user ID: {target_user_id}")
        else:
            await update.message.reply_text("❌ Failed to reset stats or user not found!")
    
    def reset_user_stats(self, user_id: int) -> bool:
        """Reset user statistics."""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE players 
                SET games_played = 0, games_won = 0, spy_games = 0, spy_wins = 0,
                    civilian_games = 0, civilian_wins = 0, total_votes_cast = 0,
                    correct_votes = 0
                WHERE user_id = ?
            """, (user_id,))
            
            if cursor.rowcount > 0:
                conn.commit()
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Error resetting user stats: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    async def broadcast_message(self, update: Update, context: CallbackContext):
        """Broadcast message to all players (bot admin only)."""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            await update.message.reply_text("❌ This command is only available to bot administrators!")
            return
        
        if not context.args:
            await update.message.reply_text(
                "Usage: /broadcast <message>\n"
                "Example: /broadcast Server maintenance in 10 minutes!"
            )
            return
        
        message = " ".join(context.args)
        success_count = 0
        fail_count = 0
        
        # Get all players
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT user_id FROM players")
            players = cursor.fetchall()
            
            for player in players:
                try:
                    await context.bot.send_message(
                        chat_id=player[0],
                        text=f"📢 <b>Broadcast from Bot Admin:</b>\n\n{message}",
                        parse_mode='HTML'
                    )
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to send broadcast to {player[0]}: {e}")
                    fail_count += 1
            
            await update.message.reply_text(
                f"📢 Broadcast sent!\n"
                f"✅ Success: {success_count}\n"
                f"❌ Failed: {fail_count}"
            )
            
        except Exception as e:
            logger.error(f"Error broadcasting message: {e}")
            await update.message.reply_text("❌ Failed to broadcast message!")
        finally:
            conn.close()
    
    async def cleanup_old_games(self, update: Update, context: CallbackContext):
        """Clean up old completed games (bot admin only)."""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            await update.message.reply_text("❌ This command is only available to bot administrators!")
            return
        
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        try:
            # Delete games older than 30 days
            cursor.execute("""
                DELETE FROM games 
                WHERE status IN ('ended', 'cancelled') 
                AND created_at < datetime('now', '-30 days')
            """)
            
            deleted_games = cursor.rowcount
            
            # Clean up orphaned game participants
            cursor.execute("""
                DELETE FROM game_participants 
                WHERE game_id NOT IN (SELECT game_id FROM games)
            """)
            
            deleted_participants = cursor.rowcount
            
            conn.commit()
            
            await update.message.reply_text(
                f"🧹 Cleanup completed!\n"
                f"🗑️ Deleted {deleted_games} old games\n"
                f"🗑️ Cleaned {deleted_participants} orphaned records"
            )
            
        except Exception as e:
            logger.error(f"Error cleaning up games: {e}")
            await update.message.reply_text("❌ Failed to cleanup games!")
        finally:
            conn.close()
    
    async def view_logs(self, update: Update, context: CallbackContext):
        """View recent game logs (bot admin only)."""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            await update.message.reply_text("❌ This command is only available to bot administrators!")
            return
        
        try:
            # Read last 50 lines from log file
            log_file = 'logs/bot.log'
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                recent_logs = ''.join(lines[-50:])
            
            if recent_logs:
                # Split into chunks if too long
                max_length = 4000
                if len(recent_logs) > max_length:
                    chunks = [recent_logs[i:i+max_length] for i in range(0, len(recent_logs), max_length)]
                    for i, chunk in enumerate(chunks[:3]):  # Max 3 chunks
                        await update.message.reply_text(
                            f"📋 <b>Recent Logs ({i+1}/{len(chunks)}):</b>\n\n"
                            f"<code>{chunk}</code>",
                            parse_mode='HTML'
                        )
                else:
                    await update.message.reply_text(
                        f"📋 <b>Recent Logs:</b>\n\n<code>{recent_logs}</code>",
                        parse_mode='HTML'
                    )
            else:
                await update.message.reply_text("📋 No logs found!")
                
        except FileNotFoundError:
            await update.message.reply_text("📋 Log file not found!")
        except Exception as e:
            logger.error(f"Error reading logs: {e}")
            await update.message.reply_text("❌ Failed to read logs!")