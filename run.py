#!/usr/bin/env python3
"""
Run script for Spy Game Telegram Bot
This script provides a simple way to run the bot with error handling.
"""

import os
import sys
import signal
import logging
from pathlib import Path

def signal_handler(sig, frame):
    """Handle shutdown signals gracefully."""
    print('\n🛑 Bot shutdown requested...')
    print('👋 Goodbye!')
    sys.exit(0)

def check_setup():
    """Check if bot is properly set up."""
    issues = []
    
    # Check .env file
    if not os.path.exists('.env'):
        issues.append("❌ .env file not found. Run: python setup.py")
    
    # Check directories
    for directory in ['data', 'logs']:
        if not Path(directory).exists():
            issues.append(f"❌ Directory '{directory}' not found. Run: python setup.py")
    
    # Check BOT_TOKEN
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            content = f.read()
            if 'BOT_TOKEN=your_bot_token_here' in content:
                issues.append("❌ BOT_TOKEN not set in .env file")
    
    return issues

def main():
    """Main run function."""
    print("🤖 Starting Spy Game Telegram Bot...")
    print("=" * 40)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Check setup
    issues = check_setup()
    if issues:
        print("⚠️  Setup issues detected:")
        for issue in issues:
            print(f"   {issue}")
        print("\n💡 Please run: python setup.py")
        return 1
    
    try:
        # Import and run the main bot
        from main import main as bot_main
        bot_main()
        
    except KeyboardInterrupt:
        print('\n🛑 Bot stopped by user')
        return 0
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Please run: python setup.py")
        return 1
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        logging.exception("Unexpected error occurred")
        return 1

if __name__ == '__main__':
    sys.exit(main())