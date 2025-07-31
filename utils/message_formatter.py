from typing import List, Dict, Optional

class MessageFormatter:
    def __init__(self):
        self.emojis = {
            'spy': '🕵️',
            'civilian': '👤',
            'location': '📍',
            'vote': '🗳️',
            'winner': '🏆',
            'time': '⏰',
            'discussion': '💬',
            'voting': '🗳️',
            'game': '🎮',
            'players': '👥',
            'stats': '📊',
            'leaderboard': '🏆'
        }
    
    def get_welcome_message(self) -> str:
        """Get welcome message."""
        return (
            f"{self.emojis['game']} <b>Welcome to Spy Game!</b>\n\n"
            f"🎯 <b>How to play:</b>\n"
            f"• One player is secretly chosen as the SPY\n"
            f"• All civilians get the same location\n"
            f"• The spy doesn't know the location\n"
            f"• Discuss for 5 minutes to figure out who's the spy\n"
            f"• Vote to eliminate someone!\n\n"
            f"🏆 <b>Win conditions:</b>\n"
            f"• Civilians win if they vote out the spy\n"
            f"• Spy wins if they survive the vote\n\n"
            f"Use /help to see all commands!"
        )
    
    def get_help_message(self) -> str:
        """Get help message with all commands."""
        return (
            f"🤖 <b>Spy Game Bot Commands:</b>\n\n"
            f"<b>Game Commands:</b>\n"
            f"/newgame - Create a new game\n"
            f"/join - Join current game\n"
            f"/startgame - Start the game (3-8 players)\n"
            f"/players - Show current players\n"
            f"/cancel - Cancel current game\n\n"
            f"<b>Stats Commands:</b>\n"
            f"/stats - Show your statistics\n"
            f"/leaderboard - Show top players\n\n"
            f"<b>Info Commands:</b>\n"
            f"/help - Show this help message\n\n"
            f"<b>Admin Commands:</b>\n"
            f"/admin - Show admin panel\n"
            f"/endgame - Force end current game\n\n"
            f"💡 <b>Tips:</b>\n"
            f"• Game needs 3-8 players\n"
            f"• Works only in group chats\n"
            f"• You'll get a private message with your role\n"
            f"• Discussion time: 5 minutes\n"
            f"• Voting time: 30 seconds"
        )
    
    def get_new_game_message(self, creator_name: str) -> str:
        """Get new game created message."""
        return (
            f"{self.emojis['game']} <b>New Spy Game Created!</b>\n\n"
            f"🎮 Created by: {creator_name}\n"
            f"{self.emojis['players']} Players: 1/8\n\n"
            f"Click the button below to join!\n"
            f"Need 3-8 players to start the game."
        )
    
    def get_player_joined_message(self, player_name: str, total_players: int) -> str:
        """Get player joined message."""
        ready_msg = "🎯 Ready to start! Use /startgame" if total_players >= 3 else f"Need {3 - total_players} more players to start."
        return (
            f"✅ <b>{player_name}</b> joined the game!\n"
            f"{self.emojis['players']} Players: {total_players}/8\n\n"
            f"{ready_msg}"
        )
    
    def get_waiting_room_message(self, players: List[Dict]) -> str:
        """Get waiting room message with player list."""
        message = f"{self.emojis['game']} <b>Spy Game Lobby</b>\n\n"
        message += f"{self.emojis['players']} <b>Players ({len(players)}/8):</b>\n"
        
        for i, player in enumerate(players, 1):
            name = player['first_name']
            username = f"@{player['username']}" if player['username'] else ""
            message += f"{i}. {name} {username}\n"
        
        message += f"\n"
        if len(players) >= 3:
            message += f"🎯 Ready to start! Use /startgame\n"
        else:
            message += f"Need {3 - len(players)} more players to start.\n"
        
        message += f"Click below to join!"
        
        return message
    
    def get_game_started_message(self, total_players: int) -> str:
        """Get game started message."""
        return (
            f"{self.emojis['game']} <b>Game Started!</b>\n\n"
            f"{self.emojis['players']} Players: {total_players}\n"
            f"{self.emojis['spy']} One of you is the SPY!\n\n"
            f"{self.emojis['discussion']} <b>Discussion Phase</b>\n"
            f"{self.emojis['time']} Time: 5 minutes\n\n"
            f"💌 Check your private messages for your role!\n"
            f"🔍 Try to figure out who the spy is!\n\n"
            f"💡 <b>Tip:</b> Ask questions about the location!"
        )
    
    def get_spy_role_message(self, location: str) -> str:
        """Get spy role private message."""
        return (
            f"{self.emojis['spy']} <b>You are the SPY!</b>\n\n"
            f"🎯 <b>Your mission:</b>\n"
            f"• You DON'T know the location\n"
            f"• Try to figure out the location without being obvious\n"
            f"• Survive the voting phase to win!\n\n"
            f"🤫 <b>Strategy tips:</b>\n"
            f"• Ask general questions\n"
            f"• Agree with others when possible\n"
            f"• Don't be too quiet or too talkative\n"
            f"• Try to redirect suspicion to others\n\n"
            f"🏆 <b>You win if:</b> You survive the vote!\n\n"
        )
    
    def get_civilian_role_message(self, location: str) -> str:
        """Get civilian role private message."""
        return (
            f"{self.emojis['civilian']} <b>You are a CIVILIAN!</b>\n\n"
            f"{self.emojis['location']} <b>Location:</b> {location}\n\n"
            f"🎯 <b>Your mission:</b>\n"
            f"• Find and vote out the SPY\n"
            f"• The spy doesn't know the location\n"
            f"• Work with other civilians to identify the spy\n\n"
            f"🤔 <b>Strategy tips:</b>\n"
            f"• Ask specific questions about the location\n"
            f"• Watch for vague or confused answers\n"
            f"• Share your knowledge to prove you're civilian\n"
            f"• But don't make it too obvious for the spy!\n\n"
            f"🏆 <b>You win if:</b> The spy gets voted out!"
        )
    
    def get_voting_started_message(self) -> str:
        """Get voting phase started message."""
        return (
            f"{self.emojis['voting']} <b>Voting Phase Started!</b>\n\n"
            f"{self.emojis['time']} Time limit: 30 seconds\n"
            f"🗳️ Vote for who you think is the SPY!\n\n"
            f"⚠️ <b>Important:</b>\n"
            f"• You must vote within 30 seconds\n"
            f"• Player with most votes gets eliminated\n"
            f"• If all players vote early, voting ends immediately\n\n"
            f"Choose wisely! 👇"
        )
    
    def get_results_message(self, results: Dict) -> str:
        """Get game results message."""
        winner = results['winner']
        eliminated_player = results['eliminated_player']
        spy_player = results['spy_player']
        vote_counts = results['vote_counts']
        total_votes = results['total_votes']
        location = results['location']
        
        message = f"{self.emojis['game']} <b>Game Results!</b>\n\n"
        
        # Winner announcement
        if winner == 'spy':
            message += f"🕵️ <b>SPY WINS!</b> 🎉\n"
            message += f"The spy successfully deceived everyone!\n\n"
        else:
            message += f"👥 <b>CIVILIANS WIN!</b> 🎉\n"
            message += f"Great detective work!\n\n"
        
        # Reveal spy
        if spy_player:
            spy_name = spy_player['first_name']
            message += f"{self.emojis['spy']} <b>The Spy was:</b> {spy_name}\n"
        
        # Reveal location
        message += f"{self.emojis['location']} <b>Location was:</b> {location}\n\n"
        
        # Voting results
        if total_votes > 0 and eliminated_player:
            eliminated_name = eliminated_player['first_name']
            message += f"🗳️ <b>Voting Results:</b>\n"
            message += f"❌ <b>Eliminated:</b> {eliminated_name}\n"
            message += f"📊 <b>Vote breakdown:</b>\n"
            
            # Sort vote counts by votes received
            sorted_votes = sorted(vote_counts.items(), key=lambda x: x[1], reverse=True)
            
            for player_id, votes in sorted_votes:
                # Find player name
                player = None
                if spy_player and spy_player['user_id'] == player_id:
                    player = spy_player
                elif eliminated_player and eliminated_player['user_id'] == player_id:
                    player = eliminated_player
                
                if player:
                    player_name = player['first_name']
                    message += f"  • {player_name}: {votes} votes\n"
            
            message += f"\n📈 Total votes cast: {total_votes}\n"
        else:
            message += f"🗳️ No votes were cast - Spy wins by default!\n"
        
        message += f"\n🆕 Use /newgame to start another round!"
        
        return message
    
    def get_current_players_message(self, game: Dict) -> str:
        """Get current players in game message."""
        players = game['players']
        status = game['status']
        
        message = f"{self.emojis['players']} <b>Current Game Players</b>\n\n"
        message += f"📊 Status: {status.title()}\n"
        message += f"👥 Players ({len(players)}/8):\n\n"
        
        for i, player in enumerate(players, 1):
            name = player['first_name']
            username = f"@{player['username']}" if player['username'] else ""
            message += f"{i}. {name} {username}\n"
        
        if status == 'waiting':
            if len(players) >= 3:
                message += f"\n🎯 Ready to start! Use /startgame"
            else:
                message += f"\nNeed {3 - len(players)} more players to start."
        elif status == 'discussion':
            message += f"\n💬 Discussion phase in progress..."
        elif status == 'voting':
            message += f"\n🗳️ Voting phase in progress..."
        
        return message
    
    def get_leaderboard_message(self, leaderboard: List[Dict]) -> str:
        """Get leaderboard message."""
        message = f"{self.emojis['leaderboard']} <b>Leaderboard - Top Players</b>\n\n"
        
        for i, player in enumerate(leaderboard, 1):
            name = player['first_name']
            username = f"@{player['username']}" if player['username'] else ""
            games_played = player['games_played']
            games_won = player['games_won']
            win_rate = player['win_rate']
            
            medal = ""
            if i == 1:
                medal = "🥇"
            elif i == 2:
                medal = "🥈"
            elif i == 3:
                medal = "🥉"
            else:
                medal = f"{i}."
            
            message += f"{medal} <b>{name}</b> {username}\n"
            message += f"   🎮 Games: {games_played} | 🏆 Won: {games_won} | 📊 Rate: {win_rate:.1f}%\n\n"
        
        message += f"💡 Use /stats to see your detailed statistics!"
        
        return message
    
    def get_player_stats_message(self, stats: Dict) -> str:
        """Get individual player stats message."""
        name = stats['first_name']
        username = f"@{stats['username']}" if stats['username'] else ""
        
        message = f"{self.emojis['stats']} <b>Statistics for {name}</b> {username}\n\n"
        
        # Overall stats
        message += f"🎮 <b>Overall Performance:</b>\n"
        message += f"   Games Played: {stats['games_played']}\n"
        message += f"   Games Won: {stats['games_won']}\n"
        message += f"   Win Rate: {stats['win_rate']:.1f}%\n\n"
        
        # Role-specific stats
        message += f"🕵️ <b>As Spy:</b>\n"
        message += f"   Games: {stats['spy_games']}\n"
        message += f"   Wins: {stats['spy_wins']}\n"
        if stats['spy_games'] > 0:
            message += f"   Win Rate: {stats['spy_win_rate']:.1f}%\n"
        else:
            message += f"   Win Rate: N/A\n"
        message += f"\n"
        
        message += f"👤 <b>As Civilian:</b>\n"
        message += f"   Games: {stats['civilian_games']}\n"
        message += f"   Wins: {stats['civilian_wins']}\n"
        if stats['civilian_games'] > 0:
            message += f"   Win Rate: {stats['civilian_win_rate']:.1f}%\n"
        else:
            message += f"   Win Rate: N/A\n"
        message += f"\n"
        
        # Voting accuracy
        message += f"🗳️ <b>Voting Accuracy:</b>\n"
        message += f"   Votes Cast: {stats['total_votes']}\n"
        message += f"   Correct Votes: {stats['correct_votes']}\n"
        message += f"   Accuracy: {stats['accuracy']:.1f}%\n\n"
        
        if stats['last_played']:
            message += f"🕐 Last Played: {stats['last_played']}\n\n"
        
        message += f"🏆 Use /leaderboard to see how you rank!"
        
        return message
    
    def get_admin_panel_message(self, stats: Dict) -> str:
        """Get admin panel message."""
        message = f"🔧 <b>Admin Panel</b>\n\n"
        
        message += f"📊 <b>Bot Statistics:</b>\n"
        message += f"   Total Games: {stats.get('total_games', 0)}\n"
        message += f"   Active Games: {stats.get('active_games', 0)}\n"
        message += f"   Completed Games: {stats.get('completed_games', 0)}\n"
        message += f"   Games Today: {stats.get('games_today', 0)}\n\n"
        
        message += f"👥 <b>Player Statistics:</b>\n"
        message += f"   Total Players: {stats.get('total_players', 0)}\n"
        message += f"   Average Win Rate: {stats.get('avg_win_rate', 0):.1f}%\n\n"
        
        most_active = stats.get('most_active')
        if most_active:
            name = most_active[0]
            username = f"@{most_active[1]}" if most_active[1] else ""
            games = most_active[2]
            message += f"🎮 <b>Most Active Player:</b>\n"
            message += f"   {name} {username} ({games} games)\n\n"
        
        message += f"🛠️ <b>Admin Commands:</b>\n"
        message += f"/endgame - Force end current game\n"
        message += f"/resetstats <user_id> - Reset player stats\n"
        message += f"/broadcast <message> - Send message to all players\n"
        message += f"/cleanup - Clean up old games\n"
        message += f"/logs - View recent game logs"
        
        return message
