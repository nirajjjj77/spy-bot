import sqlite3
import json
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str = 'data/spy_game.db'):
        self.db_path = db_path
        # Create data directory if it doesn't exist
        import os
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    def get_connection(self):
        """Get database connection."""
        return sqlite3.connect(self.db_path)
    
    def init_db(self):
        """Initialize database tables."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Games table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS games (
                    game_id TEXT PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'waiting',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    ended_at TIMESTAMP,
                    players TEXT,
                    spy_id INTEGER,
                    location TEXT,
                    votes TEXT,
                    winner TEXT,
                    discussion_end TIMESTAMP,
                    voting_end TIMESTAMP
                )
            ''')
            
            # Players table for leaderboard
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS players (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    games_played INTEGER DEFAULT 0,
                    games_won INTEGER DEFAULT 0,
                    spy_games INTEGER DEFAULT 0,
                    spy_wins INTEGER DEFAULT 0,
                    civilian_games INTEGER DEFAULT 0,
                    civilian_wins INTEGER DEFAULT 0,
                    total_votes_cast INTEGER DEFAULT 0,
                    correct_votes INTEGER DEFAULT 0,
                    last_played TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Game participants table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS game_participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id TEXT,
                    user_id INTEGER,
                    role TEXT,
                    vote_cast INTEGER,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (game_id) REFERENCES games (game_id),
                    FOREIGN KEY (user_id) REFERENCES players (user_id)
                )
            ''')
            
            conn.commit()
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def create_game(self, game_id: str, chat_id: int) -> bool:
        """Create a new game."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO games (game_id, chat_id, status, players, votes)
                VALUES (?, ?, 'waiting', '[]', '{}')
            ''', (game_id, chat_id))
            
            conn.commit()
            logger.info(f"Game {game_id} created successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error creating game: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def add_player_to_game(self, game_id: str, user_id: int, username: str, first_name: str, last_name: str = None) -> bool:
        """Add player to game and update player stats."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # First, ensure player exists in players table
            cursor.execute('''
                INSERT OR IGNORE INTO players 
                (user_id, username, first_name, last_name, 
                 games_played, games_won, spy_games, spy_wins, 
                 civilian_games, civilian_wins, total_votes_cast, correct_votes, last_played)
                VALUES (?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, CURRENT_TIMESTAMP)
            ''', (user_id, username, first_name, last_name))
            
            # Update player info if they already exist
            cursor.execute('''
                UPDATE players 
                SET username = ?, first_name = ?, last_name = ?, last_played = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (username, first_name, last_name, user_id))
            
            # Get current players in game
            cursor.execute('SELECT players FROM games WHERE game_id = ?', (game_id,))
            result = cursor.fetchone()
            
            if not result:
                logger.error(f"Game {game_id} not found when adding player")
                return False
            
            players = json.loads(result[0])
            
            # Check if player already in game
            if any(p['user_id'] == user_id for p in players):
                logger.warning(f"Player {user_id} already in game {game_id}")
                return False
            
            # Check max players
            if len(players) >= 8:
                logger.warning(f"Game {game_id} is full (8 players)")
                return False
            
            # Add player to list
            players.append({
                'user_id': user_id,
                'username': username,
                'first_name': first_name,
                'last_name': last_name
            })
            
            # Update game with new players list
            cursor.execute('''
                UPDATE games SET players = ? WHERE game_id = ?
            ''', (json.dumps(players), game_id))
            
            if cursor.rowcount == 0:
                logger.error(f"Failed to update game {game_id} with new player")
                return False
            
            conn.commit()
            logger.info(f"Player {user_id} ({first_name}) added to game {game_id}. Total players: {len(players)}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding player to game: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def start_game(self, game_id: str, spy_id: int, location: str) -> bool:
        """Start the game with assigned spy and location."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE games 
                SET status = 'discussion', spy_id = ?, location = ?, 
                    started_at = CURRENT_TIMESTAMP,
                    discussion_end = datetime(CURRENT_TIMESTAMP, '+5 minutes')
                WHERE game_id = ?
            ''', (spy_id, location, game_id))
            
            # Add participants to game_participants table
            cursor.execute('SELECT players FROM games WHERE game_id = ?', (game_id,))
            result = cursor.fetchone()
            
            if result:
                players = json.loads(result[0])
                for player in players:
                    role = 'spy' if player['user_id'] == spy_id else 'civilian'
                    cursor.execute('''
                        INSERT INTO game_participants (game_id, user_id, role)
                        VALUES (?, ?, ?)
                    ''', (game_id, player['user_id'], role))
            
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error starting game: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def get_game(self, game_id: str) -> Optional[Dict]:
        """Get game details."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT game_id, chat_id, status, players, spy_id, location, 
                       votes, discussion_end, voting_end, winner
                FROM games WHERE game_id = ?
            ''', (game_id,))
            
            result = cursor.fetchone()
            if result:
                game_data = {
                    'game_id': result[0],
                    'chat_id': result[1],
                    'status': result[2],
                    'players': json.loads(result[3]) if result[3] else [],
                    'spy_id': result[4],
                    'location': result[5],
                    'votes': json.loads(result[6]) if result[6] else {},
                    'discussion_end': result[7],
                    'voting_end': result[8],
                    'winner': result[9]
                }
                logger.debug(f"Retrieved game {game_id}: {len(game_data['players'])} players")
                return game_data
            
            logger.warning(f"Game {game_id} not found")
            return None
            
        except Exception as e:
            logger.error(f"Error getting game: {e}")
            return None
        finally:
            conn.close()
    
    def get_active_game_by_chat(self, chat_id: int) -> Optional[Dict]:
        """Get active game in a chat."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT game_id, chat_id, status, players, spy_id, location, 
                       votes, discussion_end, voting_end, winner
                FROM games 
                WHERE chat_id = ? AND status IN ('waiting', 'discussion', 'voting')
                ORDER BY created_at DESC LIMIT 1
            ''', (chat_id,))
            
            result = cursor.fetchone()
            if result:
                game_data = {
                    'game_id': result[0],
                    'chat_id': result[1],
                    'status': result[2],
                    'players': json.loads(result[3]) if result[3] else [],
                    'spy_id': result[4],
                    'location': result[5],
                    'votes': json.loads(result[6]) if result[6] else {},
                    'discussion_end': result[7],
                    'voting_end': result[8],
                    'winner': result[9]
                }
                logger.debug(f"Retrieved active game for chat {chat_id}: {game_data['game_id']} with {len(game_data['players'])} players")
                return game_data
            
            logger.debug(f"No active game found for chat {chat_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting active game: {e}")
            return None
        finally:
            conn.close()
    
    def cast_vote(self, game_id: str, voter_id: int, voted_for_id: int) -> bool:
        """Cast a vote in the game."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Get current votes
            cursor.execute('SELECT votes FROM games WHERE game_id = ?', (game_id,))
            result = cursor.fetchone()
            
            if result:
                votes = json.loads(result[0])
                votes[str(voter_id)] = voted_for_id
                
                cursor.execute('''
                    UPDATE games SET votes = ? WHERE game_id = ?
                ''', (json.dumps(votes), game_id))
                
                # Update game_participants
                cursor.execute('''
                    UPDATE game_participants 
                    SET vote_cast = ? 
                    WHERE game_id = ? AND user_id = ?
                ''', (voted_for_id, game_id, voter_id))
                
                conn.commit()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error casting vote: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def start_voting(self, game_id: str) -> bool:
        """Start voting phase."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE games 
                SET status = 'voting',
                    voting_end = datetime(CURRENT_TIMESTAMP, '+30 seconds')
                WHERE game_id = ?
            ''', (game_id,))
            
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error starting voting: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def end_game(self, game_id: str, winner: str) -> bool:
        """End the game and update stats."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Update game status
            cursor.execute('''
                UPDATE games 
                SET status = 'ended', winner = ?, ended_at = CURRENT_TIMESTAMP
                WHERE game_id = ?
            ''', (winner, game_id))
            
            # Get game details for stats update
            cursor.execute('''
                SELECT players, spy_id, votes FROM games WHERE game_id = ?
            ''', (game_id,))
            
            result = cursor.fetchone()
            if result:
                players = json.loads(result[0])
                spy_id = result[1]
                votes = json.loads(result[2])
                
                # Update player stats
                for player in players:
                    user_id = player['user_id']
                    is_spy = user_id == spy_id
                    won = (winner == 'spy' and is_spy) or (winner == 'civilians' and not is_spy)
                    
                    # Update stats
                    if is_spy:
                        cursor.execute('''
                            UPDATE players 
                            SET games_played = games_played + 1,
                                spy_games = spy_games + 1,
                                spy_wins = spy_wins + ?,
                                games_won = games_won + ?,
                                total_votes_cast = total_votes_cast + ?,
                                last_played = CURRENT_TIMESTAMP
                            WHERE user_id = ?
                        ''', (1 if won else 0, 1 if won else 0, 1 if str(user_id) in votes else 0, user_id))
                    else:
                        cursor.execute('''
                            UPDATE players 
                            SET games_played = games_played + 1,
                                civilian_games = civilian_games + 1,
                                civilian_wins = civilian_wins + ?,
                                games_won = games_won + ?,
                                total_votes_cast = total_votes_cast + ?,
                                correct_votes = correct_votes + ?,
                                last_played = CURRENT_TIMESTAMP
                            WHERE user_id = ?
                        ''', (
                            1 if won else 0, 
                            1 if won else 0, 
                            1 if str(user_id) in votes else 0,
                            1 if str(user_id) in votes and votes[str(user_id)] == spy_id else 0,
                            user_id
                        ))
            
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error ending game: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        """Get leaderboard."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT user_id, username, first_name, games_played, games_won,
                       spy_games, spy_wins, civilian_games, civilian_wins,
                       total_votes_cast, correct_votes
                FROM players 
                WHERE games_played > 0
                ORDER BY games_won DESC, games_played DESC
                LIMIT ?
            ''', (limit,))
            
            results = cursor.fetchall()
            leaderboard = []
            
            for row in results:
                win_rate = (row[4] / row[3] * 100) if row[3] > 0 else 0
                accuracy = (row[10] / row[9] * 100) if row[9] > 0 else 0
                
                leaderboard.append({
                    'user_id': row[0],
                    'username': row[1],
                    'first_name': row[2],
                    'games_played': row[3],
                    'games_won': row[4],
                    'spy_games': row[5],
                    'spy_wins': row[6],
                    'civilian_games': row[7],
                    'civilian_wins': row[8],
                    'total_votes': row[9],
                    'correct_votes': row[10],
                    'win_rate': win_rate,
                    'accuracy': accuracy
                })
            
            return leaderboard
            
        except Exception as e:
            logger.error(f"Error getting leaderboard: {e}")
            return []
        finally:
            conn.close()
    
    def get_player_stats(self, user_id: int) -> Optional[Dict]:
        """Get individual player stats."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT username, first_name, games_played, games_won,
                       spy_games, spy_wins, civilian_games, civilian_wins,
                       total_votes_cast, correct_votes, last_played
                FROM players WHERE user_id = ?
            ''', (user_id,))
            
            result = cursor.fetchone()
            if result:
                win_rate = (result[3] / result[2] * 100) if result[2] > 0 else 0
                spy_win_rate = (result[5] / result[4] * 100) if result[4] > 0 else 0
                civilian_win_rate = (result[7] / result[6] * 100) if result[6] > 0 else 0
                accuracy = (result[9] / result[8] * 100) if result[8] > 0 else 0
                
                return {
                    'username': result[0],
                    'first_name': result[1],
                    'games_played': result[2],
                    'games_won': result[3],
                    'spy_games': result[4],
                    'spy_wins': result[5],
                    'civilian_games': result[6],
                    'civilian_wins': result[7],
                    'total_votes': result[8],
                    'correct_votes': result[9],
                    'last_played': result[10],
                    'win_rate': win_rate,
                    'spy_win_rate': spy_win_rate,
                    'civilian_win_rate': civilian_win_rate,
                    'accuracy': accuracy
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting player stats: {e}")
            return None
        finally:
            conn.close()
    
    def cancel_game(self, game_id: str) -> bool:
        """Cancel an active game."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE games 
                SET status = 'cancelled', ended_at = CURRENT_TIMESTAMP
                WHERE game_id = ?
            ''', (game_id,))
            
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling game: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()