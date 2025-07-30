import os
import logging
import sys
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from handlers.game_handlers import GameHandlers
from handlers.admin_handlers import AdminHandlers
from database.db_manager import DatabaseManager

# Load environment variables
load_dotenv()

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    handlers=[
        logging.FileHandler('logs/bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    """Start the bot."""
    # Get bot token from environment
    TOKEN = os.getenv('BOT_TOKEN')
    if not TOKEN:
        logger.error("BOT_TOKEN not found in environment variables!")
        logger.error("Please create a .env file with your bot token.")
        logger.error("Example: BOT_TOKEN=your_bot_token_here")
        return
    
    try:
        # Initialize database
        db_manager = DatabaseManager()
        db_manager.init_db()
        logger.info("Database initialized successfully")

        # Create the Application
        application = Application.builder().token(TOKEN).build()
        
        # Initialize handlers
        game_handlers = GameHandlers()
        admin_handlers = AdminHandlers()
        
        # Set admin IDs from environment
        admin_ids_str = os.getenv('ADMIN_IDS', '')
        if admin_ids_str:
            try:
                admin_handlers.admin_ids = [int(x.strip()) for x in admin_ids_str.split(',') if x.strip()]
                logger.info(f"Loaded {len(admin_handlers.admin_ids)} admin IDs")
            except ValueError:
                logger.warning("Invalid ADMIN_IDS format in .env file")
        
        # Register command handlers
        application.add_handler(CommandHandler("start", game_handlers.start))
        application.add_handler(CommandHandler("help", game_handlers.help_command))
        application.add_handler(CommandHandler("newgame", game_handlers.new_game))
        application.add_handler(CommandHandler("join", game_handlers.join_game))
        application.add_handler(CommandHandler("startgame", game_handlers.start_game))
        application.add_handler(CommandHandler("players", game_handlers.show_players))
        application.add_handler(CommandHandler("leaderboard", game_handlers.show_leaderboard))
        application.add_handler(CommandHandler("stats", game_handlers.show_stats))
        application.add_handler(CommandHandler("cancel", game_handlers.cancel_game))
        
        # Admin commands
        application.add_handler(CommandHandler("admin", admin_handlers.admin_panel))
        application.add_handler(CommandHandler("endgame", admin_handlers.end_game))
        application.add_handler(CommandHandler("resetstats", admin_handlers.reset_player_stats))
        application.add_handler(CommandHandler("broadcast", admin_handlers.broadcast_message))
        application.add_handler(CommandHandler("cleanup", admin_handlers.cleanup_old_games))
        application.add_handler(CommandHandler("logs", admin_handlers.view_logs))
        
        # Callback query handler for inline keyboards
        application.add_handler(CallbackQueryHandler(game_handlers.button_callback))
        
        # Error handler
        application.add_error_handler(game_handlers.error_handler)
        
        # Start the Bot
        logger.info("Starting bot...")
        application.run_polling(allowed_updates=["message", "callback_query"])
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

if __name__ == '__main__':
    main()