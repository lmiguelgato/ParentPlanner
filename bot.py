import asyncio
import functools
import os
import logging
import datetime
from urllib.parse import quote
import importlib.util
from typing import Dict, Any, List, Optional

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
DATABASE_PATH = 'data/events.json'
DEFAULT_LOCATION = 'Washington state, United States'

# List of authorized user IDs
AUTHORIZED_USERS = [ADMIN_ID]

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Import main function from planner.py
spec = importlib.util.spec_from_file_location("planner", "./planner.py")
planner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(planner)

# Decorator function to check authorization
def restricted(func):
    @functools.wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if str(user_id) not in AUTHORIZED_USERS:
            log_message = f"Unauthorized access attempt by user with ID: {user_id} and with username: {update.effective_user.username}"
            print(log_message)
            logger.warning(log_message)
            await update.message.reply_text("Sorry, you are not authorized to use this bot.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

# Command handlers
async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

# Helper functions for event processing
def get_event_location(event: Dict[str, Any]) -> str:
    """Extract the location from the event data."""
    if 'is_estimated_address' in event and not bool(event['is_estimated_address']) and 'full_address' in event and event['full_address']:
        return event['full_address']
    elif 'is_estimated_address' in event and bool(event['is_estimated_address']) and 'location' in event and event['location']:
        return event['location']
    return DEFAULT_LOCATION

def create_google_maps_link(location: str) -> str:
    """Create a Google Maps link for the given location."""
    return f"https://maps.google.com/?daddr={quote(location)}"

def parse_event_date(event_date: str, event_time: Optional[str] = None) -> dict:
    """Parse event date and time for calendar formatting."""
    try:
        date_parts = event_date.replace(',', '').split()
        if len(date_parts) < 2:
            return {}
            
        month_name = date_parts[1]
        day = date_parts[2] if len(date_parts) > 2 else '1'
        
        # Convert month name to number
        month_map = {
            'January': 1, 'February': 2, 'March': 3, 'April': 4,
            'May': 5, 'June': 6, 'July': 7, 'August': 8,
            'September': 9, 'October': 10, 'November': 11, 'December': 12
        }
        month_num = month_map.get(month_name, 1)
        
        # Use current year
        current_year = datetime.datetime.now().year
        
        # Format date
        date_str = f"{current_year}{month_num:02d}{int(day):02d}"
        
        result = {
            'start_date': date_str,
            'end_date': date_str
        }
        
        # Add time if available
        if event_time:
            time_parts = event_time.split(' - ')
            start_time = parse_time(time_parts[0])
            
            if start_time:
                result['start_date'] += start_time
                
                # Try to get end time
                if len(time_parts) > 1:
                    end_time = parse_time(time_parts[1])
                    if end_time:
                        result['end_date'] += end_time
                    else:
                        result['end_date'] += start_time  # Default to same as start time
                else:
                    result['end_date'] += start_time  # Default to same as start time
        
        return result
    except Exception as e:
        logger.error(f"Error parsing event date: {str(e)}")
        return {}

def parse_time(time_str: str) -> Optional[str]:
    """Parse time string into Google Calendar format."""
    try:
        time_parts = time_str.split(':')
        if len(time_parts) < 2:
            return None
            
        hour = int(time_parts[0])
        minute = int(time_parts[1].split()[0])
        is_pm = 'PM' in time_str.upper()
        
        # Convert to 24-hour format
        if is_pm and hour < 12:
            hour += 12
        elif not is_pm and hour == 12:
            hour = 0
            
        return f"T{hour:02d}{minute:02d}00"
    except Exception:
        return None

def create_calendar_link(event: Dict[str, Any]) -> str:
    """Create a Google Calendar link for the event."""
    title = quote(event['title'])
    location = quote(get_event_location(event))
    description = quote(event.get('description', ''))
    
    date_info = parse_event_date(event['date'], event.get('time', ''))
    if not date_info:
        return ""
    
    return (f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={title}"
            f"&dates={date_info['start_date']}/{date_info['end_date']}"
            f"&details={description}&location={location}")

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
        calendar_url = create_calendar_link(event)
        if calendar_url:
            event_text += f"\n📆 [Add to Google Calendar]({calendar_url})\n"
    
    # Description with italic formatting
    if 'description' in event and event['description']:
        desc = event['description']
        if len(desc) > 200:
            desc = desc[:197] + "..."
        event_text += f"\n_{desc}_"
    
    return event_text

async def fetch_events() -> List[Dict[str, Any]]:
    """Fetch events from the database using the planner module."""
    try:
        # Call planner.main with the logger
        planner.main(logger)
        
        # After planner.main completes, fetch events from the database
        db = TinyDB(DATABASE_PATH)
        return db.all()
    except Exception as e:
        logger.error(f"Error fetching events: {str(e)}")
        return []

# Main events command handler
@restricted
async def events(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Fetching events... This might take a moment.")
    
    # Run planner in a thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    all_events = await loop.run_in_executor(None, lambda: fetch_events())
    
    if all_events:
        # Send a header message
        await update.message.reply_text(f"Found {len(all_events)} upcoming events:")
        
        # Send each event as a separate message
        for event in all_events:
            event_text = format_event_message(event)
            await update.message.reply_text(event_text, parse_mode="Markdown", disable_web_page_preview=False)
            
            # Add a small delay between messages to avoid rate limiting
            await asyncio.sleep(0.5)
    else:
        await update.message.reply_text("No events found. Please try again later.")

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