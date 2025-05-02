import asyncio
import functools
import os
import logging
import importlib.util
from typing import Dict, Any

from .helpers.google import create_google_maps_link, create_google_calendar_link, get_event_location

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


# List of authorized user IDs
AUTHORIZED_USERS = [ADMIN_ID]

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Import main function from planner.py
spec = importlib.util.spec_from_file_location("planner", "./planner.py")
planner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(planner)

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
    await update.message.reply_text("Fetching events... This might take a moment.")
    
    try:
        # Run planner in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        
        # Define a synchronous function that we can run in the executor
        def sync_fetch_events(user_id):
            try:
                # Call planner.main with the logger to update the main database
                planner.main(logger)
                
                # Get all events from main database
                main_db = TinyDB(DATABASE_PATH)
                all_events = main_db.all()
                logger.info(f"Fetched {len(all_events)} events from the main database.")
                
                # Get user's seen events database
                user_db_path = get_user_db_path(user_id)
                user_db = TinyDB(user_db_path)
                
                # We need a way to uniquely identify events
                # Since events may not have an 'id' field, we'll use a combination of fields
                # that should uniquely identify an event
                seen_event_fingerprints = set()
                for record in user_db.all():
                    if 'fingerprint' in record:
                        seen_event_fingerprints.add(record['fingerprint'])
                
                logger.info(f"User {user_id} has seen a total of {len(seen_event_fingerprints)} events.")

                # Create a unique fingerprint for each event based on title + date
                new_events = []
                for event in all_events:
                    # Create a unique fingerprint for each event
                    # Using title + date as a simple unique identifier
                    fingerprint = f"{event.get('title', '')}-{event.get('date', '')}"
                    
                    if fingerprint not in seen_event_fingerprints:
                        new_events.append(event)
                        # Store the fingerprint in the user's database
                        user_db.insert({'fingerprint': fingerprint})
                        logger.info(f"User {user_id} has a new event: {event['title']} on {event['date']}")
                
                return new_events
            except Exception as e:
                logger.error(f"Error fetching events: {str(e)}")
                return []
        
        # Run the synchronous function in a thread pool
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

    # Add handlers
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
    
    try:
        # Keep the bot running until interrupted
        await asyncio.Event().wait()
    finally:
        # Properly shut down
        await app.stop()
        await app.shutdown()

if __name__ == "__main__":
    asyncio.run(main())