from datetime import datetime
from telegram import Update
from telegram.ext import CallbackContext

from utils.game_state import game_state
from utils.constants import ACHIEVEMENTS
from utils.logger import logger
from utils.helpers import is_admin, escace_markdown

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
    
    stats_text = f"""📊 *{escace_markdown(stats['name'])}'s Stats:*

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
        leaderboard += f"{i}. {escace_markdown(stat['name'])}: {stat['spy_wins']} wins ({stat['spy_win_rate']:.1f}%)\n"
    
    leaderboard += "\n👥 *Top Civilians (Win Rate):*\n"
    for i, stat in enumerate(top_civilians, 1):
        leaderboard += f"{i}. {escace_markdown(stat['name'])}: {stat['civilian_win_rate']:.1f}% ({stat['civilian_wins']}/{stat['civilian_games']})\n"
    
    leaderboard += "\n🎮 *Most Active Players:*\n"
    for i, stat in enumerate(most_active, 1):
        leaderboard += f"{i}. {escace_markdown(stat['name'])}: {stat['games_played']} games\n"
    
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