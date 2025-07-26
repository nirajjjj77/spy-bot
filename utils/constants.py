import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(i) for i in os.getenv("ADMIN_IDS", "").split(",") if i]

if not TOKEN:
    raise ValueError("BOT_TOKEN missing from .env file")

# Enhanced game modes configuration
GAME_MODES = {
    'normal': {
        'name': '🎯 Normal Mode',
        'description': '5 min discussion, standard rules',
        'discussion_time': 300,
        'voting_time': 60,
        'guess_time': 30,
        'min_players': 3,
        'special': None
    },
    'speed': {
        'name': '⚡ Speed Round',
        'description': '2 min discussion, 30s voting',
        'discussion_time': 120,
        'voting_time': 30,
        'guess_time': 20,
        'min_players': 3,
        'special': None
    },
    'marathon': {
        'name': '🏃 Marathon Mode',
        'description': '10 min discussion for deep strategy',
        'discussion_time': 600,
        'voting_time': 90,
        'guess_time': 45,
        'min_players': 4,
        'special': None
    },
    'team_spy': {
        'name': '👥 Team Spy',
        'description': '2 spies vs civilians (6+ players)',
        'discussion_time': 300,
        'voting_time': 60,
        'guess_time': 30,
        'min_players': 6,
        'special': 'two_spies'
    },
    'double_agent': {
        'name': '🎭 Double Agent',
        'description': 'Spy + agent with wrong location',
        'discussion_time': 300,
        'voting_time': 60,
        'guess_time': 30,
        'min_players': 4,
        'special': 'double_agent'
    },
    'chaos': {
        'name': '🌀 Chaos Mode',
        'description': 'Multiple spies and double agents',
        'discussion_time': 360,
        'voting_time': 75,
        'guess_time': 40,
        'min_players': 8,
        'special': 'chaos'
    }
}

# Add these constants after imports
ERROR_MESSAGES = {
    'no_game': "❌ No active game found. Use /newgame to start one.",
    'game_started': "⚠️ Game already started. Cannot join now.",
    'not_in_game': "⚠️ You're not in the current game.",
    'not_authorized': "⛔ You don't have permission to do this.",
    'invalid_state': "❌ This action is not available in the current game state.",
    'rate_limited': "⏳ Please wait {} seconds before trying again.",
    'network_error': "❌ Network error occurred. Please try again.",
}
    
# Expanded locations database with categories
LOCATIONS = {
    "🌆 City": [
        "Bank", "Train Station", "Police Station", "Fire Station", 
        "Shopping Mall", "Parking Garage", "Post Office", "Apartment Complex",
        "Metro Station", "Taxi Stand", "Highway Toll Booth", "Train Compartment"
    ],
    "🏫 Education": [
        "University", "Kindergarten", "Science Lab", "Art Studio", 
        "Debate Hall", "Library", "School"
    ],
    "🏥 Medical": [
        "Hospital", "Dentist Office", "Pharmacy", 
        "Veterinary Clinic", "Psychiatric Hospital"
    ],
    "✈️ Travel": [
        "Airport", "Space Station", "Cruise Ship", 
        "Border Checkpoint", "Ferry Terminal", "Airplane"
    ],
    "🍕 Entertainment": [
        "Cinema", "Ice Cream Shop", "Nightclub", "Game Arcade", 
        "Buffet Restaurant", "Karaoke Bar", "Bowling Alley", "Theme Park"
    ],
    "🏰 Fictional": [
        "Wizard School", "Supervillain Lair", "Zombie Apocalypse Shelter", 
        "Pirate Ship", "Alien Planet", "Time Machine"
    ],
    "⚔️ Historical": [
        "Roman Colosseum", "Medieval Castle", "Ancient Pyramid", 
        "World War Bunker", "Samurai Dojo", "Wild West Saloon"
    ],
    "🧪 Scientific": [
        "Nuclear Reactor", "Control Room", "Space Research Center", 
        "Submarine", "Secret Lab", "Particle Accelerator"
    ],
    "🌳 Outdoor": [
        "Beach", "Forest Camp", "Waterfall", "Hiking Trail", 
        "Farm", "Desert Camp", "Jungle Safari"
    ]
}

# Achievements system
ACHIEVEMENTS = {
    "rookie": {"name": "Rookie Agent", "condition": lambda s: s['games_played'] >= 1},
    "spy_novice": {"name": "Spy Novice", "condition": lambda s: s['spy_wins'] >= 3},
    "detective": {"name": "Junior Detective", "condition": lambda s: s['spies_caught'] >= 5},
    "master_spy": {"name": "Master Spy", "condition": lambda s: s['spy_wins'] >= 10 and s['spy_games'] >= 20},
    "super_sleuth": {"name": "Super Sleuth", "condition": lambda s: s['spies_caught'] >= 20},
    "veteran": {"name": "Veteran Agent", "condition": lambda s: s['games_played'] >= 50},
    "deceiver": {"name": "Master Deceiver", "condition": lambda s: s['spy_wins'] >= 15 and s['spy_win_rate'] >= 70},
    "team_player": {"name": "Team Player", "condition": lambda s: s['civilian_wins'] >= 20},
    "perfectionist": {"name": "Perfectionist", "condition": lambda s: s['civilian_win_rate'] >= 80 and s['civilian_games'] >= 15},
    "legend": {"name": "Legendary Agent", "condition": lambda s: s['games_played'] >= 100 and s['spy_win_rate'] >= 60 and s['civilian_win_rate'] >= 60}
}