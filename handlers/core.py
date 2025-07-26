from telegram import Update
from telegram.ext import CallbackContext

from utils.constants import GAME_MODES
from utils.helpers import format_time

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