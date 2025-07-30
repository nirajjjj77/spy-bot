#!/usr/bin/env python3
"""
Setup script for Spy Game Telegram Bot
This script helps set up the bot environment and check dependencies.
"""

import os
import sys
import subprocess
import sqlite3
from pathlib import Path

def create_directories():
    """Create necessary directories."""
    directories = ['data', 'logs']
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✅ Created directory: {directory}")

def check_env_file():
    """Check if .env file exists and guide user."""
    if not os.path.exists('.env'):
        print("❌ .env file not found!")
        print("📝 Creating .env file from template...")
        
        if os.path.exists('.env.example'):
            # Copy .env.example to .env
            with open('.env.example', 'r') as example_file:
                content = example_file.read()
            
            with open('.env', 'w') as env_file:
                env_file.write(content)
            
            print("✅ .env file created!")
            print("⚠️  IMPORTANT: Please edit .env file and add your BOT_TOKEN!")
            print("   Get your token from @BotFather on Telegram")
            return False
        else:
            print("❌ .env.example not found. Please create .env manually.")
            return False
    else:
        print("✅ .env file exists")
        
        # Check if BOT_TOKEN is set
        with open('.env', 'r') as env_file:
            content = env_file.read()
            if 'BOT_TOKEN=your_bot_token_here' in content or 'BOT_TOKEN=' in content.split('\n')[0]:
                print("⚠️  Please set your BOT_TOKEN in .env file!")
                return False
        
        print("✅ BOT_TOKEN appears to be set")
        return True

def check_python_version():
    """Check Python version."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 7):
        print(f"❌ Python {version.major}.{version.minor} detected")
        print("⚠️  Python 3.7+ is required!")
        return False
    else:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro} is compatible")
        return True

def install_dependencies():
    """Install Python dependencies."""
    try:
        print("📦 Installing dependencies...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
        print("✅ Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install dependencies!")
        print("💡 Try running: pip install -r requirements.txt")
        return False

def test_database():
    """Test database connection."""
    try:
        from database.db_manager import DatabaseManager
        db = DatabaseManager()
        db.init_db()
        print("✅ Database initialized successfully!")
        return True
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def test_imports():
    """Test if all modules can be imported."""
    modules = [
        'telegram',
        'telegram.ext',
        'dotenv',
        'database.db_manager',
        'handlers.game_handlers',
        'handlers.admin_handlers',
        'utils.message_formatter',
        'utils.keyboards',
        'game.game_logic'
    ]
    
    failed_imports = []
    
    for module in modules:
        try:
            __import__(module)
            print(f"✅ {module}")
        except ImportError as e:
            print(f"❌ {module}: {e}")
            failed_imports.append(module)
    
    if failed_imports:
        print(f"\n❌ Failed to import {len(failed_imports)} modules")
        return False
    else:
        print("\n✅ All modules imported successfully!")
        return True

def main():
    """Main setup function."""
    print("🚀 Spy Game Telegram Bot Setup")
    print("=" * 40)
    
    all_good = True
    
    # Check Python version
    if not check_python_version():
        all_good = False
    
    # Create directories
    create_directories()
    
    # Check .env file
    if not check_env_file():
        all_good = False
    
    # Install dependencies
    if not install_dependencies():
        all_good = False
    
    # Test imports
    if not test_imports():
        all_good = False
    
    # Test database
    if not test_database():
        all_good = False
    
    print("\n" + "=" * 40)
    
    if all_good:
        print("🎉 Setup completed successfully!")
        print("🚀 You can now run the bot with: python main.py")
    else:
        print("⚠️  Setup completed with issues!")
        print("📋 Please fix the issues above before running the bot.")
        print("💡 Check the README.md for more information.")
    
    print("\n📖 Bot Commands:")
    print("   /start - Welcome message")
    print("   /newgame - Create new game")
    print("   /help - Show help")
    print("   /admin - Admin panel")

if __name__ == '__main__':
    main()