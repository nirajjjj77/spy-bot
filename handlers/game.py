import random

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext

from datetime import datetime
from threading import Timer

from utils.game_state import game_state
from utils.helpers import is_admin, format_time, get_random_location, cancel_timers, validate_input
from utils.constants import GAME_MODES
from utils.logger import logger

from handlers.stats import create_player_stats, update_player_stats

def newgame(update: Update, context: CallbackContext):
    """Start a new game"""
    chat_id = update.message.chat_id
    user = update.effective_user
    
    if game_state.get_game(chat_id):
        update.message.reply_text("⚠️ Game already in progress. Use /endgame first.")
        return
    
    game_data = {
        'players': {},
        'state': 'mode_select',
        'mode': None,
        'location': None,
        'spy': None,
        'double_agent': None,
        'votes': {},
        'host': user.id,
        'created_at': datetime.now().isoformat(),
        'awaiting_guess': False
    }
    
    game_state.add_game(chat_id, game_data)
    
    keyboard = [
        [InlineKeyboardButton(mode['name'], callback_data=f"mode:{mode_id}")]
        for mode_id, mode in GAME_MODES.items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        "🎮 *Select Game Mode:*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

def join(update: Update, context: CallbackContext):
    """Join current game"""
    chat_id = update.message.chat_id
    user = update.effective_user
    game = game_state.get_game(chat_id)
    
    if not game:
        update.message.reply_text("❌ No active game. Use /newgame to start one.")
        return
    
    if game['state'] != 'waiting':
        update.message.reply_text("⛔ Game already started.")
        return
    
    if user.id in game['players']:
        update.message.reply_text("⚠️ You already joined.")
        return
    
    game['players'][user.id] = user.first_name
    update.message.reply_text(f"✅ {user.first_name} joined the game!")
    
    # Update player count
    player_count = len(game['players'])
    min_players = GAME_MODES.get(game.get('mode', 'normal'), {}).get('min_players', 3)
    if player_count >= min_players:
        update.message.reply_text(
            f"👥 Enough players joined! Host can /begin the game now.",
            reply_to_message_id=update.message.message_id
        )

def leave(update: Update, context: CallbackContext):
    """Leave current game"""
    chat_id = update.message.chat_id
    user = update.effective_user
    game = game_state.get_game(chat_id)
    
    if not game:
        update.message.reply_text("⚠️ No game to leave.")
        return
    
    if user.id not in game['players']:
        update.message.reply_text("⚠️ You're not in the game.")
        return
    
    if game['state'] != 'waiting':
        update.message.reply_text("⚠️ Cannot leave after game started.")
        return
    
    del game['players'][user.id]
    update.message.reply_text(f"👋 {user.first_name} left the game.")
    
    # Check if host left
    if user.id == game['host'] and game['players']:
        new_host = next(iter(game['players']))
        game['host'] = new_host
        update.message.reply_text(
            f"👑 {game['players'][new_host]} is now the host.",
            reply_to_message_id=update.message.message_id
        )
    elif not game['players']:
        game_state.remove_game(chat_id)
        update.message.reply_text("🛑 Game closed due to no players.")

def players(update: Update, context: CallbackContext):
    """List current players"""
    chat_id = update.message.chat_id
    game = game_state.get_game(chat_id)
    
    if not game:
        update.message.reply_text("❌ No game in progress.")
        return
    
    if not game['players']:
        update.message.reply_text("👥 No players yet.")
        return
    
    player_list = [f"• {name}" for name in game['players'].values()]
    host_marker = lambda uid: " 👑" if uid == game['host'] else ""
    player_list = [
        f"• {name}{host_marker(uid)}"
        for uid, name in game['players'].items()
    ]
    
    mode_info = GAME_MODES.get(game.get('mode', 'normal'), {})
    min_players = mode_info.get('min_players', 3)
    player_count = len(game['players'])
    
    update.message.reply_text(
        f"👥 *Players ({player_count}/{min_players}):*\n" + "\n".join(player_list) +
        (f"\n\n✅ Ready to /begin!" if player_count >= min_players else ""),
        parse_mode='Markdown'
    )    

def begin(update: Update, context: CallbackContext):
    """FIXED: Better timer management in game start"""
    chat_id = update.message.chat_id
    user = update.effective_user
    game = game_state.get_game(chat_id)
    
    if not game or game['state'] != 'waiting':
        update.message.reply_text("⚠️ No game to begin.")
        return
    
    # Permission checks
    is_bot_admin = is_admin(user.id)
    is_host = user.id == game['host']
    is_group_admin = False
    
    try:
        if update.effective_chat.type in ['group', 'supergroup']:
            member = context.bot.get_chat_member(chat_id, user.id)
            is_group_admin = member.status in ['administrator', 'creator']
    except Exception as e:
        logger.warning(f"Failed to check admin status: {e}")
    
    if not (is_host or is_bot_admin or is_group_admin):
        update.message.reply_text(
            "⛔ Only game host (@{host}), bot admins, or group admins can start the game.".format(
                host=game['players'].get(game['host'], "unknown")
            )
        )
        return
    
    mode_config = GAME_MODES.get(game['mode'], GAME_MODES['normal'])
    min_players = mode_config['min_players']
    
    if len(game['players']) < min_players:
        update.message.reply_text(f"🚨 Need at least {min_players} players.")
        return
    
    # Select location and assign roles
    game['location'] = get_random_location()
    game['state'] = 'started'
    game['votes'] = {}
    game['awaiting_guess'] = False
    
    players = list(game['players'].keys())
    
    # Handle special game modes
    if mode_config['special'] == 'two_spies':
        game['spy'] = random.sample(players, 2)
        for uid in players:
            if uid in game['spy']:
                partner = next(s for s in game['spy'] if s != uid)
                context.bot.send_message(
                    uid,
                    f"🕵️ You are a SPY!\nYour partner is {game['players'][partner]}.",
                    parse_mode='Markdown'
                )
            else:
                context.bot.send_message(
                    uid,
                    f"🧭 You are a civilian.\nLocation: *{game['location']}*",
                    parse_mode='Markdown'
                )
    
    elif mode_config['special'] == 'double_agent':
        game['spy'] = random.choice(players)
        remaining = [p for p in players if p != game['spy']]
        game['double_agent'] = [random.choice(remaining)]
        fake_location = get_random_location()
        
        for uid in players:
            if uid == game['spy']:
                context.bot.send_message(uid, "🕵️ You are the SPY!")
            elif uid in game.get('double_agent', []):
                context.bot.send_message(
                    uid,
                    f"🧭 You are a civilian.\nLocation: *{fake_location}*",
                    parse_mode='Markdown'
                )
            else:
                context.bot.send_message(
                    uid,
                    f"🧭 You are a civilian.\nLocation: *{game['location']}*",
                    parse_mode='Markdown'
                )
    
    elif mode_config['special'] == 'chaos':
        spy_count = max(2, len(players) // 3)
        game['spy'] = random.sample(players, spy_count)
        remaining = [p for p in players if p not in game['spy']]
        da_count = max(1, len(remaining) // 3)
        game['double_agent'] = random.sample(remaining, da_count)
        
        for uid in players:
            if uid in game['spy']:
                partners = [s for s in game['spy'] if s != uid]
                partners_names = ", ".join(game['players'][p] for p in partners)
                context.bot.send_message(
                    uid,
                    f"🕵️ You are a SPY!\nPartners: {partners_names}",
                    parse_mode='Markdown'
                )
            elif uid in game.get('double_agent', []):
                fake_location = get_random_location()
                context.bot.send_message(
                    uid,
                    f"🧭 You are a civilian.\nLocation: *{fake_location}* ❌",
                    parse_mode='Markdown'
                )
            else:
                context.bot.send_message(
                    uid,
                    f"🧭 You are a civilian.\nLocation: *{game['location']}*",
                    parse_mode='Markdown'
                )
    
    else:  # Normal mode
        game['spy'] = random.choice(players)
        for uid in players:
            if uid == game['spy']:
                context.bot.send_message(uid, "🕵️ You are the SPY!")
            else:
                context.bot.send_message(
                    uid,
                    f"🧭 You are a civilian.\nLocation: *{game['location']}*",
                    parse_mode='Markdown'
                )

    game_state.clear_timers(chat_id)
    
    # Start discussion timer
    discussion_time = mode_config['discussion_time']
    update.message.reply_text(
        f"🎮 *{mode_config['name']} started!*\n"
        f"Discuss for {format_time(discussion_time)}.\n"
        f"Use /vote when ready or wait for timer.",
        parse_mode='Markdown'
    )
    
    def start_voting_wrapper():
        game = game_state.get_game(chat_id)
        if game and game['state'] == 'started' and not game.get('voting_active', False):  # ✅ Check if voting not already started
            try:
                context.bot.send_message(
                    chat_id,
                    "⏰ Discussion time over! Starting voting...",
                    parse_mode='Markdown'
                )
                start_voting(chat_id, context)
            except Exception as e:
                logger.error(f"Failed to start voting automatically: {e}")
    
    game_state.safe_timer_operation(
        chat_id, 
        "discussion_timer", 
        start_voting_wrapper, 
        discussion_time
    )

def location_command(update: Update, context: CallbackContext):
    """Send location info to player"""
    chat_id = update.message.chat_id
    user_id = update.effective_user.id
    game = game_state.get_game(chat_id)
    
    if not game or game['state'] != 'started':
        update.message.reply_text("❌ Game hasn't started yet.")
        return
    
    if user_id not in game['players']:
        update.message.reply_text("⚠️ You're not in the game.")
        return
    
    # Public response
    update.message.reply_text("📬 Check your private messages for your role info.")
    
    # Private message with role info
    if isinstance(game['spy'], list) and user_id in game['spy']:
        partners = [s for s in game['spy'] if s != user_id]
        partners_names = ", ".join(game['players'][p] for p in partners)
        context.bot.send_message(
            user_id,
            f"🕵️ You are a SPY!\nPartners: {partners_names}",
            parse_mode='Markdown'
        )
    elif user_id == game.get('spy'):
        context.bot.send_message(user_id, "🕵️ You are the SPY!")
    elif user_id in game.get('double_agent', []):
        fake_location = get_random_location()
        context.bot.send_message(
            user_id,
            f"🧭 You are a civilian.\nLocation: *{fake_location}*",
            parse_mode='Markdown'
        )
    else:
        context.bot.send_message(
            user_id,
            f"🧭 You are a civilian.\nLocation: *{game['location']}*",
            parse_mode='Markdown'
        )

def vote(update: Update, context: CallbackContext):
    """Start voting process - FIXED"""
    chat_id = update.message.chat_id
    game = game_state.get_game(chat_id)
    
    if not game or game['state'] != 'started':
        update.message.reply_text("❌ Voting not available now.")
        return
    
    # ✅ Check if voting already started
    if game.get('voting_active', False):
        update.message.reply_text("🗳 Voting already in progress!")
        return
    
    start_voting(chat_id, context)

def start_voting(chat_id: int, context: CallbackContext):
    """FINAL FIX: Prevent double voting start"""
    game = game_state.get_game(chat_id)
    if not game or game['state'] != 'started':
        return
    
    # ✅ CRITICAL FIX: Check if voting already active
    with game_state.lock:
        if game.get('voting_active', False):
            return  # Voting already started, don't start again
        
        # Clear any existing timers first
        game_state.clear_timers(chat_id)
        game['votes'] = {}
        game['voting_active'] = True
    
    # Create voting buttons
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"vote:{uid}")]
        for uid, name in game['players'].items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        msg = context.bot.send_message(
            chat_id,
            "🗳 *Who is the spy?*\nVote by selecting a player below:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        # Store message ID for editing
        with game_state.lock:
            game['voting_message_id'] = msg.message_id

    except Exception as e:
        print(f"Failed to send voting message: {e}")
        return
    
    # Get voting time from mode config
    mode_config = GAME_MODES.get(game['mode'], GAME_MODES['normal'])
    voting_time = mode_config['voting_time']
    
    # ✅ FIXED: Only create voting timeout timer
    def voting_timeout():
        try:
            with game_state.lock:
                game = game_state.get_game(chat_id)
                if game and game.get('voting_active', False):
                    game['voting_active'] = False
            
            context.bot.send_message(chat_id, "⏰ Voting time over!")
            finish_vote(chat_id, context)
        except Exception as e:
            print(f"Voting timeout error: {e}")
    
    # Create timer using safe operation
    game_state.safe_timer_operation(chat_id, "voting_timeout", voting_timeout, voting_time)

def vote_callback(update: Update, context: CallbackContext):
    """FIXED: Thread-safe voting with proper race condition handling"""
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    
    # ✅ FIX: Get game and validate under lock
    with game_state.lock:
        game = game_state.games.get(chat_id)
        
        if not game or game['state'] != 'started':
            query.answer("Voting not active.")
            return
        
        if not game.get('voting_active', False):
            query.answer("Voting has ended.")
            return
        
        if user_id not in game['players']:
            query.answer("You're not in this game.")
            return
        
        # ✅ FIX: Check if already voted INSIDE the lock
        if user_id in game.get('votes', {}):
            query.answer("You already voted!")
            return
        
        # Parse vote target
        try:
            voted_id = int(query.data.split(":")[1])
        except (ValueError, IndexError):
            query.answer("Invalid vote.")
            return
        
        if voted_id not in game['players']:
            query.answer("Invalid player.")
            return
        
        # ✅ FIX: Record vote INSIDE the lock - prevents race conditions
        if 'votes' not in game:
            game['votes'] = {}
        
        game['votes'][user_id] = voted_id
        voted_name = game['players'].get(voted_id, "Unknown")
        votes_received = len(game['votes'])
        total_players = len(game['players'])

        # Check if voting complete
        voting_complete = votes_received == total_players
        if voting_complete:
            game['voting_active'] = False  # Stop accepting votes
    
    # Now we can safely answer and update outside the lock
    query.answer(f"Voted for {voted_name}")
    
    # Update vote count display
    try:
        context.bot.edit_message_text(
            text=f"🗳 *Who is the spy?*\nVotes received: {votes_received}/{total_players}",
            chat_id=chat_id,
            message_id=query.message.message_id,
            reply_markup=query.message.reply_markup if not voting_complete else None,
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"Failed to update vote progress: {e}")
    
    # ✅ FIX: Check if all votes are in (with lock)
    if voting_complete:
        # Send completion message
        try:
            context.bot.send_message(
                chat_id, 
                "✅ All votes received! Calculating results...",
                parse_mode='Markdown'
            )
        except:
            pass
        
        # Small delay then finish vote
        game_state.safe_timer_operation(
            chat_id, 
            "complete_voting", 
            lambda: finish_vote(chat_id, context), 
            1.0  # 1 second delay to show completion message
        )

def mode_callback(update: Update, context: CallbackContext):
    """Handle game mode selection"""
    query = update.callback_query
    chat_id = query.message.chat_id
    game = game_state.get_game(chat_id)
    
    if not game or game['state'] != 'mode_select':
        query.answer("Invalid selection.")
        return
    
    mode_id = query.data.split(":")[1]
    if mode_id not in GAME_MODES:
        query.answer("Invalid mode.")
        return
    
    game['mode'] = mode_id
    game['state'] = 'waiting'
    
    mode_info = GAME_MODES[mode_id]
    min_players = mode_info['min_players']
    
    query.answer(f"Selected: {mode_info['name']}")
    
    context.bot.edit_message_text(
        text=f"✅ *{mode_info['name']} selected!*\n"
             f"{mode_info['description']}\n"
             f"👥 Minimum players: {min_players}\n\n"
             f"Players, use /join to participate.",
        chat_id=chat_id,
        message_id=query.message.message_id,
        parse_mode='Markdown'
    )

def finish_vote(chat_id: int, context: CallbackContext):
    """"FIXED: Always cleanup timers at start and show results properly"""
    game_state.clear_timers(chat_id)

    game = game_state.get_game(chat_id)
    if not game:
        return
    
    # Check if voting is still active (prevent double execution)
    if not game.get('voting_active', True):
        # If voting already finished, don't process again
        return
    
    # Mark voting as finished
    with game_state.lock:
        game['voting_active'] = False

    votes = game['votes']
    if not votes:
        context.bot.send_message(chat_id, "❌ No votes received. Game aborted.")
        game_state.remove_game(chat_id)
        return
    
    # Count votes
    vote_counts = {}
    for voted_id in votes.values():
        vote_counts[voted_id] = vote_counts.get(voted_id, 0) + 1

    # After counting votes
    logger.info(f"Votes received: {votes}")
    logger.info(f"Vote counts: {vote_counts}")

    # After deciding who is voted out
    logger.info(f"Top voted player: {chosen_name}")
    
    # Prepare vote breakdown
    breakdown = "🗳️ *Voting Results:*\n"
    for voter_id, voted_id in votes.items():
        voter_name = game['players'].get(voter_id, "Unknown")
        voted_name = game['players'].get(voted_id, "Unknown")
        breakdown += f"• {voter_name} → {voted_name}\n"

    # Add vote count summary
    breakdown += "\n📊 *Vote Count:*\n"
    for player_id, count in vote_counts.items():
        player_name = game['players'].get(player_id, "Unknown")
        breakdown += f"• {player_name}: {count} vote(s)\n"
    
    # Send breakdown first
    context.bot.send_message(chat_id, breakdown, parse_mode='Markdown')
    
    # Determine who was voted out
    max_votes = max(vote_counts.values())
    top_voted = [uid for uid, count in vote_counts.items() if count == max_votes]
    
    if len(top_voted) > 1:
        # Tie - randomly select one
        chosen = random.choice(top_voted)
        chosen_name = game['players'].get(chosen, "Unknown")
        context.bot.send_message(
            chat_id, 
            f"⚠️ Voting tie! Randomly selecting **{chosen_name}**",
            parse_mode='Markdown'
        )
    else:
        chosen = top_voted[0]
        chosen_name = game['players'].get(chosen, "Unknown")
    
    # MISSING PART - Announce elimination result
    context.bot.send_message(
        chat_id,
        f"🎯 **{chosen_name}** was eliminated with **{vote_counts[chosen]}** vote(s)!",
        parse_mode='Markdown'
    )
    
    # Update statistics for voters
    for voter_id in votes:
        if voter_id not in game_state.player_stats:
            game_state.player_stats[voter_id] = create_player_stats(game['players'][voter_id])
        
        # Check if they caught a spy
        if isinstance(game['spy'], list):
            if votes[voter_id] in game['spy']:
                game_state.player_stats[voter_id]['spies_caught'] += 1
        else:
            if votes[voter_id] == game['spy']:
                game_state.player_stats[voter_id]['spies_caught'] += 1
    
    # Handle special modes
    mode_config = GAME_MODES.get(game['mode'], GAME_MODES['normal'])
    
    if mode_config['special'] == 'team_spy':
        if chosen in game['spy']:
            # Remove caught spy
            game['spy'] = [s for s in game['spy'] if s != chosen]
            del game['players'][chosen]
            
            if not game['spy']:
                # All spies caught
                context.bot.send_message(chat_id, "🎉 All spies caught! Civilians win!")
                end_game(chat_id, 'civilian_win', context)
            else:
                # Continue with remaining spies
                remaining_spies = ", ".join(game['players'][s] for s in game['spy'])
                context.bot.send_message(
                    chat_id,
                    f"✅ {chosen_name} was a spy! Remaining spies: {remaining_spies}",
                    parse_mode='Markdown'
                )
                start_voting(chat_id, context)
        else:
            # Innocent voted out
            spies = ", ".join(game['players'][s] for s in game['spy'])
            context.bot.send_message(
                chat_id,
                f"❌ {chosen_name} was innocent. Spies were: {spies}",
                parse_mode='Markdown'
            )
            end_game(chat_id, 'spy_win', context)
    
    elif mode_config['special'] in ['double_agent', 'chaos']:
        if isinstance(game.get('spy'), list):
            # Handle multiple spies in chaos mode
            if chosen in game['spy']:
                context.bot.send_message(
                    chat_id,
                    f"✅ {chosen_name} was a spy! Civilians win!",
                    parse_mode='Markdown'
                )
                end_game(chat_id, 'civilian_win', context)
            elif chosen in game.get('double_agent', []):
                spy_names = ", ".join(game['players'][s] for s in game['spy'])
                context.bot.send_message(
                    chat_id,
                    f"❌ {chosen_name} was a double agent! Real spies {spy_names} win!",
                    parse_mode='Markdown'
                )
                end_game(chat_id, 'spy_win', context)
            else:
                spy_names = ", ".join(game['players'][s] for s in game['spy'])
                da_names = ", ".join(game['players'][da] for da in game.get('double_agent', []))
                context.bot.send_message(
                    chat_id,
                    f"❌ {chosen_name} was innocent.\n"
                    f"Spies: {spy_names}\n"
                    f"Double agents: {da_names or 'None'}",
                    parse_mode='Markdown'
                )
                end_game(chat_id, 'spy_win', context)
        else:
            # Single spy mode
            if chosen == game.get('spy'):
                context.bot.send_message(
                    chat_id,
                    f"✅ {chosen_name} was the real spy! Civilians win!",
                    parse_mode='Markdown'
                )
                end_game(chat_id, 'civilian_win', context)
            elif chosen in game.get('double_agent', []):
                spy_name = game['players'].get(game['spy'], "Unknown")
                context.bot.send_message(
                    chat_id,
                    f"❌ {chosen_name} was a double agent! Real spy {spy_name} wins!",
                    parse_mode='Markdown'
                )
                end_game(chat_id, 'spy_win', context)
            else:
                spy_name = game['players'].get(game['spy'], "Unknown")
                da_names = ", ".join(game['players'][da] for da in game.get('double_agent', []))
                context.bot.send_message(
                    chat_id,
                    f"❌ {chosen_name} was innocent.\n"
                    f"Spy: {spy_name}\n"
                    f"Double agents: {da_names or 'None'}",
                    parse_mode='Markdown'
                )
                end_game(chat_id, 'spy_win', context)
    
    else:  # Normal mode
        if chosen == game['spy']:
            # Spy caught
            context.bot.send_message(
                chat_id,
                f"🎉 {chosen_name} was the spy! Civilians win!",
                parse_mode='Markdown'
            )
            end_game(chat_id, 'civilian_win', context)
        else:
            # Innocent voted out - spy gets to guess
            spy_name = game['players'].get(game['spy'], "Unknown")
            context.bot.send_message(
                chat_id,
                f"❌ {chosen_name} was innocent. The spy was {spy_name}!",
                parse_mode='Markdown'
            )
            
            # Spy gets to guess
            game['awaiting_guess'] = True
            try:
                context.bot.send_message(
                    game['spy'],
                    f"🕵️ You survived! Guess the location within {mode_config['guess_time']} seconds:",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Failed to send guess message to spy: {e}")
                # If can't message spy, civilians win
                context.bot.send_message(
                    chat_id,
                    "❌ Spy unreachable. Civilians win!",
                    parse_mode='Markdown'
                )
                end_game(chat_id, 'civilian_win', context)
                return
            
            # Set guess timer
            guess_time = mode_config['guess_time']
            
            def guess_timeout():
                game = game_state.get_game(chat_id)
                if game and game.get('awaiting_guess', False):
                    try:
                        context.bot.send_message(
                            chat_id,
                            "⏰ Spy failed to guess in time. Civilians win!",
                            parse_mode='Markdown'
                        )
                        end_game(chat_id, 'civilian_win', context)
                    except Exception as e:
                        logger.error(f"Failed to send timeout message: {e}")
            
            timer = Timer(guess_time, guess_timeout)
            timer.start()
            game_state.add_timer(chat_id, timer)

def handle_guess(update: Update, context: CallbackContext):
    """Process spy's location guess"""
    if update.effective_chat.type != 'private':
        return  # Only process guesses in private chat
    
    user_id = update.effective_user.id
    guess_text = update.message.text.strip()
    
    # Find the game where this user is the spy and awaiting guess
    target_chat_id = None
    target_game = None
    
    with game_state.lock:
        for chat_id, game in game_state.games.items():
            if (game.get('awaiting_guess', False) and 
                ((isinstance(game.get('spy'), list) and user_id in game['spy']) or 
                 game.get('spy') == user_id)):
                target_chat_id = chat_id
                target_game = game
                break
    
    if not target_game or not target_chat_id:
        return  # Not a valid guess context
    
    # Validate guess input
    is_valid, validated_guess = validate_input(guess_text, max_length=100, min_length=1)
    if not is_valid:
        update.message.reply_text(f"❌ {validated_guess}")
        return
    
    guess = validated_guess.lower().strip()
    correct = target_game['location'].lower().strip()
    
    # Cancel guess timer and update game state
    cancel_timers(target_chat_id)
    target_game['awaiting_guess'] = False
    
    # Check if guess is correct (exact match or very close)
    is_correct = (guess == correct or 
                  guess in correct or 
                  correct in guess or
                  abs(len(guess) - len(correct)) <= 2 and 
                  sum(a != b for a, b in zip(guess, correct)) <= 2)
    
    try:
        if is_correct:
            context.bot.send_message(
                target_chat_id,
                f"🎉 The spy guessed correctly! Location was **{target_game['location']}**. Spy wins!",
                parse_mode='Markdown'
            )
            update.message.reply_text("🎉 Correct guess! You win!")
            end_game(target_chat_id, 'spy_win', context)
        else:
            context.bot.send_message(
                target_chat_id,
                f"❌ Spy guessed '{guess_text}'. Correct was **{target_game['location']}**. Civilians win!",
                parse_mode='Markdown'
            )
            update.message.reply_text(f"❌ Wrong! Correct answer was: {target_game['location']}")
            end_game(target_chat_id, 'civilian_win', context)
            
    except Exception as e:
        logger.error(f"Failed to send guess result: {e}")
        # Fallback - end game as civilian win
        end_game(target_chat_id, 'civilian_win', context)

def end_game(chat_id: int, result: str, context: CallbackContext = None):
    """Finalize game and update statistics"""
    game = game_state.get_game(chat_id)
    if not game:
        return
    
    # Update stats for all players
    for player_id in game['players']:
        was_spy = (
            player_id == game.get('spy') or 
            (isinstance(game.get('spy'), list) and player_id in game['spy'])
        )
        update_player_stats(player_id, game['players'][player_id], result, was_spy, context)
    
    # Clean up
    game_state.remove_game(chat_id)

def endgame(update: Update, context: CallbackContext):
    """FIXED: Enhanced cleanup"""
    chat_id = update.message.chat_id
    user = update.effective_user
    game = game_state.get_game(chat_id)
    
    if not game:
        update.message.reply_text("❌ No game to end.")
        return

    # Permission checks
    is_bot_admin = is_admin(user.id)
    is_host = user.id == game['host']
    is_group_admin = False

     # Check Telegram group admin status (if in group)
    try:
        if update.effective_chat.type in ['group', 'supergroup']:
            member = context.bot.get_chat_member(chat_id, user.id)
            is_group_admin = member.status in ['administrator', 'creator']
    except Exception as e:
        logger.warning(f"Failed to check admin status: {e}")

    # Reject unauthorized users
    if not (is_host or is_bot_admin or is_group_admin):
        update.message.reply_text(
            "⛔ Only game host (@{host}), bot admins, or group admins can end the game.".format(
                host=game['players'].get(game['host'], "unknown")
            )
        )
        return
    
    # Clean up game
    game_state.remove_game(chat_id)

     # Success message
    if is_host:
        update.message.reply_text("🛑 Game ended by host.")
    elif is_bot_admin:
        update.message.reply_text("🛑 Game ended by bot admin.")
    else:
        update.message.reply_text("🛑 Game ended by group admin.")