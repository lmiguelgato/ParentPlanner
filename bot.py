import asyncio
import functools
import os
import logging
import importlib.util
import time
import glob
from typing import Dict, Any, List, Set
from datetime import datetime

from helpers.google import create_google_maps_link, create_google_calendar_link, get_event_location

from telegram import Update, BotCommand
from telegram.ext import (
    CommandHandler, 
    MessageHandler, 
    filters, 
    ContextTypes, 
    ApplicationBuilder
)
from tinydb import TinyDB

# Constants
ADMIN_ID = os.getenv("ADMIN_ID")
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_PATH = 'data/events.json'  # Main event storage
AUTHORIZED_USERS_DB = 'data/authorized_users.json'


# List of authorized user IDs
AUTHORIZED_USERS = [ADMIN_ID]

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Import main function from planner.py
spec = importlib.util.spec_from_file_location("planner", "./planner.py")
planner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(planner)

# Global variable to track last update time
last_update_time = 0
UPDATE_INTERVAL = 60 * 60 * 24  # 24 hours in seconds

def load_authorized_users():
    """Load authorized users from the database and append to AUTHORIZED_USERS."""
    os.makedirs('data', exist_ok=True)
    db = TinyDB(AUTHORIZED_USERS_DB)
    user_ids = [str(u['user_id']) for u in db.all() if 'user_id' in u]
    # Avoid duplicates
    for uid in user_ids:
        if uid not in AUTHORIZED_USERS:
            AUTHORIZED_USERS.append(uid)

def add_authorized_user(user_id: str):
    db = TinyDB(AUTHORIZED_USERS_DB)
    if not db.contains({'user_id': user_id}):
        db.insert({'user_id': user_id})

def remove_authorized_user(user_id: str):
    db = TinyDB(AUTHORIZED_USERS_DB)
    db.remove(lambda u: u.get('user_id') == user_id)

async def scheduled_update(app):
    """Background task that updates the event database every hour and notifies users of new events."""
    global last_update_time
    
    while True:
        current_time = time.time()
        
        # Check if an hour has passed since the last update
        if current_time - last_update_time >= UPDATE_INTERVAL:
            logger.info(f"Running scheduled update at {datetime.now()}")
            try:
                # Get count of events before update
                event_count_before = 0
                try:
                    if os.path.exists(DATABASE_PATH):
                        main_db = TinyDB(DATABASE_PATH)
                        event_count_before = len(main_db.all())
                except Exception as e:
                    logger.error(f"Error counting events before update: {str(e)}")
                
                # Run planner in a thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, lambda: planner.main(logger))
                
                # Update the last update time
                last_update_time = current_time
                logger.info(f"Scheduled update completed at {datetime.now()}")
                
                # Get count of events after update
                event_count_after = 0
                try:
                    if os.path.exists(DATABASE_PATH):
                        main_db = TinyDB(DATABASE_PATH)
                        event_count_after = len(main_db.all())
                except Exception as e:
                    logger.error(f"Error counting events after update: {str(e)}")
                
                # If new events were added, notify users
                new_event_count = event_count_after - event_count_before
                if new_event_count > 0:
                    logger.info(f"Found {new_event_count} new events, sending notifications to users")
                    await notify_users_of_new_events(app, new_event_count)
                
            except Exception as e:
                logger.error(f"Error in scheduled update: {str(e)}")
        
        # Sleep for a minute before checking again
        await asyncio.sleep(60)

async def notify_users_of_new_events(app, new_event_count: int):
    """Send notification to all users that new events are available."""
    user_ids = get_all_user_ids()
    logger.info(f"Sending notifications to {len(user_ids)} users")
    
    # Prepare notification message
    if new_event_count == 1:
        message = "🔔 There is 1 new event available! Use /events to check it out."
    else:
        message = f"🔔 There are {new_event_count} new events available! Use /events to check them out."
    
    # Send notification to each user
    for user_id in user_ids:
        try:
            # Convert string user ID to integer for Telegram API
            int_user_id = int(user_id)
            if str(int_user_id) in AUTHORIZED_USERS:
                await app.bot.send_message(chat_id=int_user_id, text=message)
                logger.info(f"Sent notification to user {user_id}")
                # Add small delay to avoid hitting rate limits
                await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Failed to send notification to user {user_id}: {str(e)}")

# Function to get list of all user IDs from data directory
def get_all_user_ids() -> List[str]:
    """Get all user IDs by listing the JSON files in the data directory except events.json."""
    user_ids = []
    os.makedirs('data', exist_ok=True)  # Ensure directory exists
    
    # List all .json files in the data directory
    json_files = glob.glob('data/*.json')
    
    for file_path in json_files:
        # Extract just the filename without path or extension
        filename = os.path.basename(file_path)
        name_without_ext = os.path.splitext(filename)[0]
        
        # Skip the main events database
        if name_without_ext != 'events':
            # Only add IDs that are numeric (valid user IDs)
            if name_without_ext.isdigit():
                user_ids.append(name_without_ext)
    
    return user_ids

# Helper functions for event processing
def format_event_message(event: Dict[str, Any]) -> str:
    """Format event data into a formatted message string."""
    event_text = ""
    
    # Title as clickable link
    title_text = f"{event['title']}"
    if 'link' in event and event['link']:
        title_text = f"[{title_text}]({event['link']})"
    event_text += f"📌 {title_text}\n\n"
    
    # Date and time
    if 'date' in event:
        event_text += f"📅 *Date:* {event['date']}\n"
    if 'time' in event and event['time']:
        event_text += f"🕒 *Time:* {event['time']}\n"
    
    # Status
    if 'status' in event and event['status'] and event['status'] != "Confirmed":
        event_text += f"📊 *Status:* {event['status']}\n"
    
    # Cost
    if 'cost' in event and event['cost']:
        event_text += f"💰 *Cost:* {event['cost']}\n"
    
    # Location with Google Maps link
    location = get_event_location(event)
    maps_url = create_google_maps_link(location)
    event_text += f"📍 *Location:* [{location}]({maps_url})\n"
    
    # Weather
    if 'weather' in event and event['weather']:
        weather = event['weather']
        event_text += (f"🌤️ *Weather:* {weather['summary']}, with a max temperature of {weather['temp_max']}°C, "
                       f"winds of up to {weather['max_wind_speed']} km/h, and {weather['precipitation_probability_text']}\n")
    
    # Add Google Calendar link
    if 'date' in event:
        calendar_url = create_google_calendar_link(event)
        if calendar_url:
            event_text += f"\n📆 [Add to Google Calendar]({calendar_url})\n"
    
    # Description with italic formatting
    if 'description' in event and event['description']:
        desc = event['description']
        if len(desc) > 200:
            desc = desc[:197] + "..."
        event_text += f"\n_{desc}_"
    
    return event_text

def get_user_db_path(user_id: int) -> str:
    """Return the database path for a specific user's seen events."""
    os.makedirs('data', exist_ok=True)  # Ensure directory exists
    return f'data/{user_id}.json'

# Decorator function to check authorization
def restricted(func):
    @functools.wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if str(user_id) not in AUTHORIZED_USERS:
            log_message = f"Unauthorized access attempt by user with ID: {user_id} and with username: {update.effective_user.username}"
            logger.warning(log_message)
            await update.message.reply_text("Sorry, you are not authorized to use this bot.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

# Command handlers
@restricted
async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if str(user_id) != ADMIN_ID:
        await update.message.reply_text("Only the admin can add users.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /add_user <user_id>")
        return
    new_user_id = context.args[0]
    add_authorized_user(new_user_id)
    if new_user_id not in AUTHORIZED_USERS:
        AUTHORIZED_USERS.append(new_user_id)
    await update.message.reply_text(f"User {new_user_id} added to authorized users.")

@restricted
async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if str(user_id) != ADMIN_ID:
        await update.message.reply_text("Only the admin can remove users.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /remove_user <user_id>")
        return
    remove_id = context.args[0]
    db = TinyDB(AUTHORIZED_USERS_DB)
    user_exists = db.contains({'user_id': remove_id})
    if user_exists:
        remove_authorized_user(remove_id)
        if remove_id in AUTHORIZED_USERS:
            AUTHORIZED_USERS.remove(remove_id)
        await update.message.reply_text(f"User {remove_id} removed from authorized users.")
    else:
        await update.message.reply_text(f"User {remove_id} was not an authorized user.")

@restricted
async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if str(user_id) != ADMIN_ID:
        await update.message.reply_text("Only the admin can list authorized users.")
        return
    db = TinyDB(AUTHORIZED_USERS_DB)
    users = [str(u['user_id']) for u in db.all() if 'user_id' in u]
    if not users:
        await update.message.reply_text("No authorized users found.")
    else:
        users_text = "\n".join(users)
        await update.message.reply_text(f"Authorized users:\n{users_text}")

@restricted
async def force_fetch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Force fetch command received.")

    user_id = update.effective_user.id

    if str(user_id) == ADMIN_ID:
        try:
            # Get count of events before update
            event_count_before = 0
            try:
                if os.path.exists(DATABASE_PATH):
                    main_db = TinyDB(DATABASE_PATH)
                    event_count_before = len(main_db.all())
            except Exception as e:
                logger.error(f"Error counting events before update: {str(e)}")
            
            # Run planner in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: planner.main(logger))
            
            # Get count of events after update
            event_count_after = 0
            try:
                if os.path.exists(DATABASE_PATH):
                    main_db = TinyDB(DATABASE_PATH)
                    event_count_after = len(main_db.all())
            except Exception as e:
                logger.error(f"Error counting events after update: {str(e)}")
            
            # If new events were added, notify users
            new_event_count = event_count_after - event_count_before
            if new_event_count > 0:
                logger.info(f"Found {new_event_count} new events, sending notifications to users")
                # Use the application from context instead of app
                await notify_users_of_new_events(context.application, new_event_count)
                await update.message.reply_text(f"Force fetch completed. Found {new_event_count} new events.")
            else:
                await update.message.reply_text("Force fetch completed. No new events found.")
            
        except Exception as e:
            logger.error(f"Error in force fetch: {str(e)}")
            await update.message.reply_text("An error occurred during force fetch.")

@restricted
async def main_db_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Main database reset command received.")

    user_id = update.effective_user.id

    if str(user_id) == ADMIN_ID:
        # Remove the main database file if it exists
        if os.path.exists(DATABASE_PATH):
            try:
                os.remove(DATABASE_PATH)
                await update.message.reply_text("Main database reset successfully.")
                logger.info(f"Main database reset by admin {user_id}.")
            except Exception as e:
                await update.message.reply_text("Error resetting main database.")
                logger.error(f"Error resetting main database: {str(e)}")
        else:
            await update.message.reply_text("Main database does not exist.")

@restricted
async def user_db_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("User database reset command received.")
    
    user_id = update.effective_user.id

    if str(user_id) == ADMIN_ID:
        # Remove all user databases
        user_files = glob.glob('data/*.json')
        for file_path in user_files:
            filename = os.path.basename(file_path)
            name_without_ext = os.path.splitext(filename)[0]
            
            # Skip the main events database
            if name_without_ext != 'events':
                try:
                    os.remove(file_path)
                    await update.message.reply_text(f"Removed user database for user {name_without_ext}.")
                    logger.info(f"Removed user database for user {name_without_ext}.")
                except Exception as e:
                    await update.message.reply_text(f"Error removing user database for {name_without_ext}.")
                    logger.error(f"Error removing user database for {name_without_ext}: {str(e)}")
        await update.message.reply_text("All user databases reset successfully.")

@restricted
async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_db_path = get_user_db_path(user_id)
    
    # Remove user's database if it exists
    if os.path.exists(user_db_path):
        try:
            os.remove(user_db_path)
            logger.info(f"Removed seen events database for user {user_id}")
        except Exception as e:
            logger.error(f"Error removing database for user {user_id}: {str(e)}")
    
    await update.message.reply_text("Welcome! I am Parent Planner, an assistant that can help you find family events for the weekend. Use /help to see available commands.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "I can do the following:\n"
        "/restart - Restart the bot\n"
        "/help - Show this help text\n"
        "/events - Get event information\n"
        "/echo - Echo your next message"
    )
    await update.message.reply_text(help_text)

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data['echo_mode'] = True
    await update.message.reply_text("I will now echo whatever you send.")

async def handle_echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get('echo_mode', False):
        await update.message.reply_text(update.message.text)
        context.user_data['echo_mode'] = False

# Main events command handler
@restricted
async def events(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    await update.message.reply_text("Fetching events...")
    
    try:
        # Define a synchronous function that we can run in the executor
        def sync_fetch_events(user_id):
            try:
                # Get all events from main database
                main_db = TinyDB(DATABASE_PATH)
                all_events = main_db.all()
                logger.info(f"Fetched {len(all_events)} events from the main database.")
                
                # Get user's seen events database
                user_db_path = get_user_db_path(user_id)
                user_db = TinyDB(user_db_path)
                
                # Get previously seen events
                seen_event_fingerprints = set()
                for record in user_db.all():
                    if 'fingerprint' in record:
                        seen_event_fingerprints.add(record['fingerprint'])
                
                logger.info(f"User {user_id} has seen a total of {len(seen_event_fingerprints)} events.")

                # Filter out events the user has already seen
                new_events = []
                for event in all_events:
                    fingerprint = f"{event.get('title', '')}-{event.get('date', '')}"
                    
                    if fingerprint not in seen_event_fingerprints:
                        new_events.append(event)
                        user_db.insert({'fingerprint': fingerprint})
                
                return new_events
            except Exception as e:
                logger.error(f"Error fetching events: {str(e)}")
                return []
        
        # Run the synchronous function in a thread pool
        loop = asyncio.get_event_loop()
        new_events = await loop.run_in_executor(None, lambda: sync_fetch_events(user_id))
        
        if new_events:
            # Send a header message
            await update.message.reply_text(f"Found {len(new_events)} new events:")
            
            # Send each event as a separate message
            for event in new_events:
                event_text = format_event_message(event)
                await update.message.reply_text(event_text, parse_mode="Markdown", disable_web_page_preview=False)
                
                # Add a small delay between messages to avoid rate limiting
                await asyncio.sleep(0.5)
        else:
            await update.message.reply_text("No new events found. Use /restart to reset your event history.")
    except Exception as e:
        logger.error(f"Error processing events command: {str(e)}")
        await update.message.reply_text("An error occurred while fetching events. Please try again later.")

# Main function to set up the bot
async def main():
    # Load authorized users from DB before starting the bot
    load_authorized_users()

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Define commands for the command menu
    commands = [
        BotCommand("restart", "Restart the bot"),
        BotCommand("events", "Get event information"),
        BotCommand("echo", "Repeat the next message you send"),
        BotCommand("help", "Show help information"),
    ]
    
    # Set the commands to show in the command menu
    await app.bot.set_my_commands(commands)

    # Admin commands
    app.add_handler(CommandHandler("main_db_reset", main_db_reset))
    app.add_handler(CommandHandler("user_db_reset", user_db_reset))
    app.add_handler(CommandHandler("force_fetch", force_fetch))
    app.add_handler(CommandHandler("add_user", add_user))
    app.add_handler(CommandHandler("remove_user", remove_user))
    app.add_handler(CommandHandler("list_users", list_users))

    # User commands
    app.add_handler(CommandHandler("start", restart))
    app.add_handler(CommandHandler("restart", restart))
    app.add_handler(CommandHandler("events", events))
    app.add_handler(CommandHandler("echo", echo))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_echo))

    # Start the bot
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    # Start the background task for scheduled updates
    global last_update_time
    # Force an immediate first update
    logger.info("Starting initial data fetch...")
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, lambda: planner.main(logger))
        last_update_time = time.time()
        logger.info("Initial data fetch completed")
    except Exception as e:
        logger.error(f"Error in initial update: {str(e)}")
        last_update_time = 0  # Force retry on next check
    
    # Start the scheduled update task
    asyncio.create_task(scheduled_update(app))
    
    try:
        # Keep the bot running until interrupted
        await asyncio.Event().wait()
    finally:
        # Properly shut down
        await app.stop()
        await app.shutdown()

if __name__ == "__main__":
    asyncio.run(main())