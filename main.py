from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters

from utils.constants import TOKEN
from utils.logger import logger
from utils.error_handler import error_handler

from handlers import core, game, anon, stats

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    # Command Handlers
    dp.add_handler(CommandHandler("start", core.start))
    dp.add_handler(CommandHandler("guide", core.guide))
    dp.add_handler(CommandHandler("intel", core.intel))
    dp.add_handler(CommandHandler("modes", core.modes))

    dp.add_handler(CommandHandler("newgame", game.newgame))
    dp.add_handler(CommandHandler("join", game.join))
    dp.add_handler(CommandHandler("leave", game.leave))
    dp.add_handler(CommandHandler("players", game.players))
    dp.add_handler(CommandHandler("begin", game.begin))
    dp.add_handler(CommandHandler("vote", game.vote))
    dp.add_handler(CommandHandler("endgame", game.endgame))
    dp.add_handler(CommandHandler("location", game.location_command))

    dp.add_handler(CommandHandler("anon", anon.anon))

    dp.add_handler(CommandHandler("stats", stats.show_stats))
    dp.add_handler(CommandHandler("leaderboard", stats.show_leaderboard))
    dp.add_handler(CommandHandler("achievements", stats.show_achievements))
    dp.add_handler(CommandHandler("adminstats", stats.admin_stats))

    # CallbackQuery Handlers
    dp.add_handler(CallbackQueryHandler(game.vote_callback, pattern=r"^vote:"))
    dp.add_handler(CallbackQueryHandler(game.mode_callback, pattern=r"^mode:"))
    dp.add_handler(CallbackQueryHandler(anon.anon_callback, pattern=r"^anon_game:"))

    # Message handler for spy guesses
    dp.add_handler(MessageHandler(Filters.text & Filters.private, game.handle_guess))

    # Error handler
    dp.add_error_handler(error_handler)

    updater.start_polling()
    logger.info("Spy Bot is running...")
    updater.idle()

if __name__ == "__main__":
    main()
