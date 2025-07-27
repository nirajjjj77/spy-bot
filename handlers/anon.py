from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext

import hashlib
import time

from utils.game_state import game_state
from utils.helpers import validate_input
from utils.logger import logger

def anon(update: Update, context: CallbackContext):
    """Handle anonymous messages from players"""
    if update.effective_chat.type != 'private':
        update.message.reply_text(
            "❌ Anonymous messages can only be sent in private chat with the bot.\n"
            "Message me directly to send anonymous messages to your game."
        )
        return
    
    user_id = update.effective_user.id
    current_time = time.time()
    
    COOLDOWN = 60

    # Cooldown check
    with game_state.lock:
       if user_id in game_state.anon_cooldowns:
            time_elapsed = current_time - game_state.anon_cooldowns[user_id]
            if time_elapsed < COOLDOWN:
                # Last message yaad rakha gaya hai ya nahi
                last_message = (
                    game_state.anon_last_message.get(user_id, "No previous message.")
                    if hasattr(game_state, "anon_last_message")
                    else "No previous message."
                )
                update.message.reply_text(
                    f"⏳ Please wait {COOLDOWN - int(time_elapsed)} seconds before sending another message.\n\n"
                    f"📝 *Your last message was:*\n_{last_message}_",
                    parse_mode='Markdown'
                )
                return
    
    # Validate message
    message = ' '.join(context.args) if context.args else ""
    is_valid, result = validate_input(message)
    
    if not is_valid:
        update.message.reply_text(f"❌ {result}")
        return

    message = result
    
    # Find active games
    active_games = []
    with game_state.lock:
        for chat_id, game in game_state.games.items():
            if (user_id in game['players'] and game['state'] == 'started'):
                active_games.append((chat_id, game))
    
    if not active_games:
        update.message.reply_text(
            "❌ You're not in any active games or the game hasn't started yet."
        )
        return
    
    # Multiple games - use message ID system
    if len(active_games) > 1:
        import hashlib
        message_id = hashlib.md5(f"{user_id}_{current_time}_{message}".encode()).hexdigest()[:8]
        
        # Store message temporarily
        with game_state.lock:
            game_state.temp_anon_messages[message_id] = {
                'message': message,
                'user_id': user_id,
                'timestamp': current_time
            }
        
        keyboard = []
        for chat_id, game in active_games:
            try:
                chat = context.bot.get_chat(chat_id)
                group_name = chat.title or f"Game with {game['players'][game['host']]}"
            except:
                group_name = f"Game with {game['players'][game['host']]}"
            
            keyboard.append([
                InlineKeyboardButton(
                    group_name,
                    callback_data=f"anon_game:{chat_id}:{message_id}"
                )
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(
            "📌 Select which game to send your anonymous message to:",
            reply_markup=reply_markup
        )
        return
    
    # Single game
    chat_id = active_games[0][0]

    with game_state.lock:
        if not hasattr(game_state, 'anon_last_message'):
            game_state.anon_last_message = {}
        game_state.anon_cooldowns[user_id] = time.time()
        game_state.anon_last_message[user_id] = message

    _send_anon_message(context, user_id, chat_id, message)

def anon_callback(update: Update, context: CallbackContext):
    """Handle game selection for anonymous messages"""
    query = update.callback_query
    query.answer()
    
    try:
        data = query.data.split(':')
        if len(data) != 3:
            query.edit_message_text("❌ Invalid request.")
            return
            
        chat_id = int(data[1])
        message_id = data[2]
        user_id = query.from_user.id
        
        # Get stored message
        with game_state.lock:
            message_data = game_state.temp_anon_messages.get(message_id)
        
        if not message_data:
            query.edit_message_text("❌ Message expired. Please try again.")
            return
        
        if message_data['user_id'] != user_id:
            query.edit_message_text("❌ Invalid request.")
            return
        
        message = message_data['message']
        
        # Verify game still exists
        game = game_state.get_game(chat_id)
        if not game or user_id not in game['players'] or game['state'] != 'started':
            query.edit_message_text("❌ Game no longer active.")
            with game_state.lock:
                game_state.temp_anon_messages.pop(message_id, None)
            return
        
        _send_anon_message(context, user_id, chat_id, message)
        query.edit_message_text("✅ Message sent anonymously!")
        
        # Clean up
        with game_state.lock:
            game_state.temp_anon_messages.pop(message_id, None)
        
    except Exception as e:
        logger.error(f"Error in anon_callback: {e}")
        query.edit_message_text("❌ Failed to send message.")

def _send_anon_message(context: CallbackContext, user_id: int, chat_id: int, message: str):
    """Actually send the anonymous message with proper error handling"""
    # Apply cooldown with thread safety
    with game_state.lock:
        if not hasattr(game_state, 'anon_cooldowns'):
            game_state.anon_cooldowns = {}
        game_state.anon_cooldowns[user_id] = time.time()
    
    try:
        # Verify game still exists
        game = game_state.get_game(chat_id)
        if not game or game['state'] != 'started':
            context.bot.send_message(
                user_id,
                "❌ Game no longer active. Message not sent."
            )
            return
        
        # Format and send message
        formatted_msg = f"{message.strip()}"
        
        # Send to group
        context.bot.send_message(
            chat_id,
            formatted_msg,
            parse_mode='Markdown'
        )
        
        # Notify sender
        context.bot.send_message(
            user_id,
            "✅ Message sent!",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Failed to send anonymous message from {user_id}: {e}")
        try:
            context.bot.send_message(
                user_id,
                "❌ Failed to send your anonymous message. Please try again later.",
                parse_mode='Markdown'
            )
        except Exception as fallback_error:
            logger.error(f"Couldn't notify sender of failure: {fallback_error}")