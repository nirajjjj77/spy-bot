import random
import asyncio
import time
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import Counter

from database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)

class GameLogic:
    def __init__(self):
        self.db = DatabaseManager()
        self.locations = [
            "🏢 Airport", "🏦 Bank", "🏖️ Beach", "🎰 Casino", "⛪ Church", 
            "🎬 Cinema", "🎪 Circus", "🏛️ Embassy", "🏥 Hospital", "🏨 Hotel",
            "📚 Library", "🛍️ Mall", "🏛️ Museum", "🏢 Office", "🌳 Park",
            "🍽️ Restaurant", "🏫 School", "🏟️ Stadium", "🚇 Subway", "🎭 Theater",
            "🎓 University", "🦁 Zoo", "🏰 Castle", "⛲ Fountain", "🌉 Bridge",
            "🚂 Train Station", "🚢 Port", "🏭 Factory", "🏪 Store", "🎨 Art Gallery"
        ]
        
        # Active games tracking
        self.active_games: Dict[str, dict] = {}
        self.discussion_tasks: Dict[str, asyncio.Task] = {}
        self.voting_tasks: Dict[str, asyncio.Task] = {}
    
    def create_game(self, chat_id: int) -> Optional[str]:
        """Create a new game."""
        # Check if there's already an active game
        existing_game = self.db.get_active_game_by_chat(chat_id)
        if existing_game:
            return None
        
        game_id = f"spy_{chat_id}_{int(time.time())}"
        
        if self.db.create_game(game_id, chat_id):
            self.active_games[game_id] = {
                'chat_id': chat_id,
                'status': 'waiting',
                'players': [],
                'spy_id': None,
                'location': None,
                'votes': {},
                'discussion_end_time': None,
                'voting_end_time': None
            }
            return game_id
        
        return None
    
    def join_game(self, game_id: str, user_id: int, username: str, first_name: str, last_name: str = None) -> bool:
        """Add player to game."""
        game = self.db.get_game(game_id)
        if not game or game['status'] != 'waiting':
            return False
        
        # Check if player already joined
        if any(p['user_id'] == user_id for p in game['players']):
            return False
        
        # Maximum 8 players
        if len(game['players']) >= 8:
            return False
        
        return self.db.add_player_to_game(game_id, user_id, username, first_name, last_name)
    
    def can_start_game(self, game_id: str) -> Tuple[bool, str]:
        """Check if game can be started."""
        game = self.db.get_game(game_id)
        if not game:
            return False, "Game not found"
        
        if game['status'] != 'waiting':
            return False, "Game already started or ended"
        
        if len(game['players']) < 3:
            return False, "Need at least 3 players to start"
        
        return True, "Game can be started"
    
    def start_game(self, game_id: str) -> Optional[Dict]:
        """Start the game - assign spy and location."""
        game = self.db.get_game(game_id)
        if not game:
            return None
        
        can_start, message = self.can_start_game(game_id)
        if not can_start:
            return None
        
        # Select random spy and location
        spy = random.choice(game['players'])
        location = random.choice(self.locations)
        
        # Start game in database
        if self.db.start_game(game_id, spy['user_id'], location):
            # Update local tracking
            self.active_games[game_id] = {
                'chat_id': game['chat_id'],
                'status': 'discussion',
                'players': game['players'],
                'spy_id': spy['user_id'],
                'location': location,
                'votes': {},
                'discussion_end_time': datetime.now() + timedelta(minutes=5),
                'voting_end_time': None
            }
            
            return {
                'game_id': game_id,
                'spy_id': spy['user_id'],
                'location': location,
                'players': game['players']
            }
        
        return None
    
    def get_game_info(self, game_id: str) -> Optional[Dict]:
        """Get current game information."""
        if game_id in self.active_games:
            return self.active_games[game_id].copy()
        
        # Fallback to database
        return self.db.get_game(game_id)
    
    def get_active_game_by_chat(self, chat_id: int) -> Optional[Dict]:
        """Get active game in chat."""
        # Check local tracking first
        for game_id, game_data in self.active_games.items():
            if game_data['chat_id'] == chat_id and game_data['status'] in ['waiting', 'discussion', 'voting']:
                return {**game_data, 'game_id': game_id}
        
        # Fallback to database
        return self.db.get_active_game_by_chat(chat_id)
    
    def start_voting_phase(self, game_id: str) -> bool:
        """Start voting phase."""
        if game_id not in self.active_games:
            return False
        
        if self.db.start_voting(game_id):
            self.active_games[game_id]['status'] = 'voting'
            self.active_games[game_id]['voting_end_time'] = datetime.now() + timedelta(seconds=30)
            return True
        
        return False
    
    def cast_vote(self, game_id: str, voter_id: int, voted_for_id: int) -> bool:
        """Cast a vote."""
        game = self.get_game_info(game_id)
        if not game or game['status'] != 'voting':
            return False
        
        # Check if voter is in game
        if not any(p['user_id'] == voter_id for p in game['players']):
            return False
        
        # Check if voted player is in game
        if not any(p['user_id'] == voted_for_id for p in game['players']):
            return False
        
        if self.db.cast_vote(game_id, voter_id, voted_for_id):
            # Update local tracking
            if game_id in self.active_games:
                self.active_games[game_id]['votes'][str(voter_id)] = voted_for_id
            return True
        
        return False
    
    def check_all_voted(self, game_id: str) -> bool:
        """Check if all players have voted."""
        game = self.get_game_info(game_id)
        if not game:
            return False
        
        total_players = len(game['players'])
        votes_cast = len(game['votes'])
        
        return votes_cast >= total_players
    
    def calculate_results(self, game_id: str) -> Optional[Dict]:
        """Calculate voting results and determine winner."""
        game = self.get_game_info(game_id)
        if not game:
            return None
        
        votes = game['votes']
        spy_id = game['spy_id']
        
        if not votes:
            # No votes cast - spy wins
            winner = 'spy'
            eliminated_player_id = None
            vote_counts = {}
        else:
            # Count votes
            vote_counts = Counter(votes.values())
            
            # Find player with most votes
            eliminated_player_id = vote_counts.most_common(1)[0][0]
            
            # Determine winner
            if eliminated_player_id == spy_id:
                winner = 'civilians'
            else:
                winner = 'spy'
        
        # End game in database
        self.db.end_game(game_id, winner)
        
        # Update local tracking
        if game_id in self.active_games:
            self.active_games[game_id]['status'] = 'ended'
        
        # Get eliminated player info
        eliminated_player = None
        if eliminated_player_id:
            eliminated_player = next(
                (p for p in game['players'] if p['user_id'] == eliminated_player_id), 
                None
            )
        
        # Get spy info
        spy_player = next(
            (p for p in game['players'] if p['user_id'] == spy_id), 
            None
        )
        
        return {
            'winner': winner,
            'eliminated_player': eliminated_player,
            'spy_player': spy_player,
            'vote_counts': dict(vote_counts),
            'total_votes': len(votes),
            'location': game['location']
        }
    
    def cancel_game(self, game_id: str) -> bool:
        """Cancel an active game."""
        if self.db.cancel_game(game_id):
            # Clean up local tracking
            if game_id in self.active_games:
                del self.active_games[game_id]
            
            # Cancel any running tasks
            if game_id in self.discussion_tasks:
                self.discussion_tasks[game_id].cancel()
                del self.discussion_tasks[game_id]
            
            if game_id in self.voting_tasks:
                self.voting_tasks[game_id].cancel()
                del self.voting_tasks[game_id]
            
            return True
        
        return False
    
    def cleanup_game(self, game_id: str):
        """Clean up game from memory after completion."""
        if game_id in self.active_games:
            del self.active_games[game_id]
        
        if game_id in self.discussion_tasks:
            del self.discussion_tasks[game_id]
        
        if game_id in self.voting_tasks:
            del self.voting_tasks[game_id]
    
    def get_player_role_info(self, game_id: str, user_id: int) -> Optional[Dict]:
        """Get role-specific information for a player."""
        game = self.get_game_info(game_id)
        if not game:
            return None
        
        is_spy = user_id == game['spy_id']
        
        return {
            'role': 'spy' if is_spy else 'civilian',
            'location': None if is_spy else game['location'],
            'is_spy': is_spy
        }
    
    def get_voting_keyboard_data(self, game_id: str) -> List[Dict]:
        """Get data for voting keyboard."""
        game = self.get_game_info(game_id)
        if not game:
            return []
        
        return [
            {
                'user_id': player['user_id'],
                'display_name': player['first_name'] + (f" (@{player['username']})" if player['username'] else ""),
                'username': player['username']
            }
            for player in game['players']
        ]
    
    def is_discussion_time_over(self, game_id: str) -> bool:
        """Check if discussion time is over."""
        if game_id not in self.active_games:
            return True
        
        game = self.active_games[game_id]
        if game['status'] != 'discussion':
            return True
        
        if game['discussion_end_time'] and datetime.now() >= game['discussion_end_time']:
            return True
        
        return False
    
    def is_voting_time_over(self, game_id: str) -> bool:
        """Check if voting time is over."""
        if game_id not in self.active_games:
            return True
        
        game = self.active_games[game_id]
        if game['status'] != 'voting':
            return True
        
        if game['voting_end_time'] and datetime.now() >= game['voting_end_time']:
            return True
        
        return False
    
    def get_remaining_discussion_time(self, game_id: str) -> int:
        """Get remaining discussion time in seconds."""
        if game_id not in self.active_games:
            return 0
        
        game = self.active_games[game_id]
        if game['status'] != 'discussion' or not game['discussion_end_time']:
            return 0
        
        remaining = (game['discussion_end_time'] - datetime.now()).total_seconds()
        return max(0, int(remaining))
    
    def get_remaining_voting_time(self, game_id: str) -> int:
        """Get remaining voting time in seconds."""
        if game_id not in self.active_games:
            return 0
        
        game = self.active_games[game_id]
        if game['status'] != 'voting' or not game['voting_end_time']:
            return 0
        
        remaining = (game['voting_end_time'] - datetime.now()).total_seconds()
        return max(0, int(remaining))
    
    def get_game_stats_summary(self, game_id: str) -> Optional[str]:
        """Get a summary of the game for stats display."""
        game = self.db.get_game(game_id)
        if not game:
            return None
        
        total_players = len(game['players'])
        votes_cast = len(game['votes'])
        
        summary = f"🎮 Game Summary:\n"
        summary += f"👥 Players: {total_players}\n"
        summary += f"🗳️ Votes Cast: {votes_cast}/{total_players}\n"
        summary += f"📍 Location: {game['location']}\n"
        
        if game['winner']:
            summary += f"🏆 Winner: {game['winner'].title()}\n"
        
        return summary