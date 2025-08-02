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
            logger.warning(f"Active game already exists in chat {chat_id}")
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
            logger.info(f"Created new game {game_id} in chat {chat_id}")
            return game_id
        
        return None
    
    def join_game(self, game_id: str, user_id: int, username: str, first_name: str, last_name: str = None) -> bool:
        """Add player to game."""
        # Get fresh game data from database
        game = self.db.get_game(game_id)
        if not game:
            logger.error(f"Game {game_id} not found when player {user_id} tried to join")
            return False
        
        if game['status'] != 'waiting':
            logger.warning(f"Game {game_id} status is {game['status']}, cannot join")
            return False
        
        # Check if player already joined
        if any(p['user_id'] == user_id for p in game['players']):
            logger.warning(f"Player {user_id} already in game {game_id}")
            return False
        
        # Maximum 8 players
        if len(game['players']) >= 8:
            logger.warning(f"Game {game_id} is full (8 players)")
            return False
        
        # Add to database
        success = self.db.add_player_to_game(game_id, user_id, username, first_name, last_name)
        
        if success:
            # Update local tracking with fresh data from database
            updated_game = self.db.get_game(game_id)
            if updated_game and game_id in self.active_games:
                self.active_games[game_id]['players'] = updated_game['players']
                logger.info(f"Player {user_id} ({first_name}) joined game {game_id}. Total players: {len(updated_game['players'])}")
            else:
                logger.error(f"Failed to update local tracking for game {game_id}")
        else:
            logger.error(f"Failed to add player {user_id} to game {game_id}")
        
        return success
    
    def can_start_game(self, game_id: str) -> Tuple[bool, str]:
        """Check if game can be started."""
        # Always get fresh data from database for this check
        game = self.db.get_game(game_id)
        if not game:
            return False, "Game not found"
        
        if game['status'] != 'waiting':
            return False, "Game already started or ended"
        
        if len(game['players']) < 3:
            return False, f"Need at least 3 players to start (currently {len(game['players'])})"
        
        return True, "Game can be started"
    
    def start_game(self, game_id: str) -> Optional[Dict]:
        """Start the game - assign spy and location."""
        # Get fresh game data from database
        game = self.db.get_game(game_id)
        if not game:
            logger.error(f"Game {game_id} not found when trying to start")
            return None
        
        can_start, message = self.can_start_game(game_id)
        if not can_start:
            logger.warning(f"Cannot start game {game_id}: {message}")
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
            
            logger.info(f"Started game {game_id} with {len(game['players'])} players. Spy: {spy['user_id']}, Location: {location}")
            
            return {
                'game_id': game_id,
                'spy_id': spy['user_id'],
                'location': location,
                'players': game['players']
            }
        
        logger.error(f"Failed to start game {game_id} in database")
        return None
    
    def get_game_info(self, game_id: str) -> Optional[Dict]:
        """Get current game information."""
        # Always get fresh data from database for consistency
        game = self.db.get_game(game_id)
        if game:
            # Update local tracking if it exists
            if game_id in self.active_games:
                self.active_games[game_id].update({
                    'players': game['players'],
                    'status': game['status'],
                    'votes': game['votes']
                })
            return game
        
        # Fallback to local tracking if database fails
        if game_id in self.active_games:
            return self.active_games[game_id].copy()
        
        return None
    
    def get_active_game_by_chat(self, chat_id: int) -> Optional[Dict]:
        """Get active game in chat."""
        # Always check database first for most current data
        game = self.db.get_active_game_by_chat(chat_id)
        if game:
            # Update local tracking if game exists
            game_id = game['game_id']
            if game_id in self.active_games:
                self.active_games[game_id].update({
                    'players': game['players'],
                    'status': game['status'],
                    'votes': game['votes']
                })
            return game
        
        # Fallback to local tracking
        for game_id, game_data in self.active_games.items():
            if game_data['chat_id'] == chat_id and game_data['status'] in ['waiting', 'discussion', 'voting']:
                return {**game_data, 'game_id': game_id}
        
        return None
    
    def start_voting_phase(self, game_id: str) -> bool:
        """Start voting phase."""
        if self.db.start_voting(game_id):
            if game_id in self.active_games:
                self.active_games[game_id]['status'] = 'voting'
                self.active_games[game_id]['voting_end_time'] = datetime.now() + timedelta(seconds=30)
            logger.info(f"Started voting phase for game {game_id}")
            return True
        
        logger.error(f"Failed to start voting phase for game {game_id}")
        return False
    
    def cast_vote(self, game_id: str, voter_id: int, voted_for_id: int) -> bool:
        """Cast a vote."""
        # Get fresh game data from database
        game = self.db.get_game(game_id)
        if not game or game['status'] != 'voting':
            logger.warning(f"Cannot cast vote in game {game_id}: game not found or not in voting phase (status: {game.get('status') if game else 'None'})")
            return False

        # Check if voter is in game
        if not any(p['user_id'] == voter_id for p in game['players']):
            logger.warning(f"Voter {voter_id} not in game {game_id}")
            return False

        # Check if voted player is in game
        if not any(p['user_id'] == voted_for_id for p in game['players']):
            logger.warning(f"Voted player {voted_for_id} not in game {game_id}")
            return False

        # Check if user already voted
        current_votes = game.get('votes', {})
        if str(voter_id) in current_votes:
            logger.warning(f"Player {voter_id} already voted in game {game_id}")
            return False

        # Cast vote in database
        if self.db.cast_vote(game_id, voter_id, voted_for_id):
            # Update local tracking
            if game_id in self.active_games:
                if 'votes' not in self.active_games[game_id]:
                    self.active_games[game_id]['votes'] = {}
                self.active_games[game_id]['votes'][str(voter_id)] = voted_for_id
            
            logger.info(f"Player {voter_id} voted for {voted_for_id} in game {game_id}")
            return True

        logger.error(f"Failed to cast vote in database for game {game_id}")
        return False
    
    def check_all_voted(self, game_id: str) -> bool:
        """Check if all players have voted."""
        game = self.get_game_info(game_id)
        if not game:
            return False
        
        total_players = len(game['players'])
        votes_cast = len(game['votes'])
        
        logger.debug(f"Game {game_id}: {votes_cast}/{total_players} votes cast")
        return votes_cast >= total_players
    
    def calculate_results(self, game_id: str) -> Optional[Dict]:
        """Calculate voting results and determine winner."""
        game = self.get_game_info(game_id)
        if not game:
            logger.error(f"Game {game_id} not found when calculating results")
            return None
        
        votes = game['votes']
        spy_id = game['spy_id']
        
        if not votes:
            # No votes cast - spy wins
            winner = 'spy'
            eliminated_player_id = None
            vote_counts = {}
            logger.info(f"Game {game_id}: No votes cast, spy wins by default")
        else:
            # Count votes
            vote_counts = Counter(votes.values())
            
            # Find player with most votes
            eliminated_player_id = vote_counts.most_common(1)[0][0]
            
            # Determine winner
            if eliminated_player_id == spy_id:
                winner = 'civilians'
                logger.info(f"Game {game_id}: Spy eliminated, civilians win")
            else:
                winner = 'spy'
                logger.info(f"Game {game_id}: Civilian eliminated, spy wins")
        
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
            
            logger.info(f"Cancelled game {game_id}")
            return True
        
        logger.error(f"Failed to cancel game {game_id}")
        return False
    
    def cleanup_game(self, game_id: str):
        """Clean up game from memory after completion."""
        if game_id in self.active_games:
            del self.active_games[game_id]
        
        if game_id in self.discussion_tasks:
            del self.discussion_tasks[game_id]
        
        if game_id in self.voting_tasks:
            del self.voting_tasks[game_id]
        
        logger.info(f"Cleaned up game {game_id}")
    
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