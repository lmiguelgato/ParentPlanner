import asyncio
import functools
from telegram import Update, BotCommand
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes, ApplicationBuilder
import os
import logging
from tinydb import TinyDB
import importlib.util
from urllib.parse import quote
import datetime

ADMIN_ID = os.getenv("ADMIN_ID")

# List of authorized user IDs (replace with your actual IDs)
AUTHORIZED_USERS = [
    ADMIN_ID,
]

# Import main function from planner.py
spec = importlib.util.spec_from_file_location("planner", "./planner.py")
planner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(planner)

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

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

# Define the function for handling the /restart command
async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Welcome! I am Parent Planner, an assistant that can help you find family events for the weekend. Use /help to see available commands.")

# Define the function for handling the /help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "I can do the following:\n"
        "/restart - Restart the bot\n"
        "/help - Show this help text\n"
        "/events - Get event information\n"
        "/echo - Echo your next message"
    )
    await update.message.reply_text(help_text)

# Define the function for handling the /events command
@restricted
async def events(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Fetching events... This might take a moment.")
     
    # Define a function to run planner.main in a separate thread
    def run_planner():
        try:
            # Call planner.main with the logger
            planner.main(logger)
            return True
        except Exception as e:
            logger.error(f"Error running planner: {str(e)}")
            return False
     
    # Run planner in a thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    success = await loop.run_in_executor(None, run_planner)
    
    if success:
        # After planner.main completes, fetch events from the database
        db = TinyDB('data/events.json')
        all_events = db.all()
        
        if all_events:
            # Send a header message
            await update.message.reply_text(f"Found {len(all_events)} upcoming events:")
            
            # List events
            for event in all_events:
                # Format each event as a separate message
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
                if 'is_estimated_address' in event and not bool(event['is_estimated_address']) and 'full_address' in event and event['full_address']:
                    # Create Google Maps link with properly encoded location
                    maps_url = f"https://maps.google.com/?daddr={quote(event['full_address'], safe='')}"
                    event_text += f"📍 *Location:* [{event['full_address']}]({maps_url})\n"
                
                # Location (estimated)
                elif 'is_estimated_address' in event and bool(event['is_estimated_address']) and 'location' in event and event['location']:
                    # Create Google Maps link with properly encoded location
                    maps_url = f"https://maps.google.com/?daddr={quote(event['location'], safe='')}"
                    event_text += f"📍 *Location:* [{event['location']}]({maps_url})\n"
                
                # Weather
                if 'weather' in event and event['weather']:
                    event_text += f"🌤️ *Weather:* {event['weather']['summary']}, with a max temperature of {event['weather']['temp_max']}°C, winds of up to {event['weather']['max_wind_speed']} km/h, and {event['weather']['precipitation_probability_text']}\n"
                
                # Add Google Calendar link
                if 'date' in event:
                    title = quote(event['title'])
                    location = quote(event.get('full_address', ''))
                    description = quote(event.get('description', ''))
                    
                    # Parse date for Google Calendar format (assumes date format like "Saturday, May 4")
                    try:
                        # Extract date info - this is basic and may need adjustment based on your date format
                        date_parts = event['date'].replace(',', '').split()
                        if len(date_parts) >= 2:
                            month_name = date_parts[1]
                            day = date_parts[2] if len(date_parts) > 2 else '1'
                            # Convert month name to number
                            month_num = {
                                'January': 1, 'February': 2, 'March': 3, 'April': 4,
                                'May': 5, 'June': 6, 'July': 7, 'August': 8,
                                'September': 9, 'October': 10, 'November': 11, 'December': 12
                            }.get(month_name, 1)
                            
                            # Use current year
                            current_year = datetime.datetime.now().year
                            
                            # Format date for Google Calendar
                            start_date = f"{current_year}{month_num:02d}{int(day):02d}"
                            end_date = start_date
                            
                            # Add time if available
                            time_info = ""
                            if 'time' in event and event['time']:
                                # This assumes time format is like "2:00 PM - 4:00 PM"
                                time_parts = event['time'].split(' - ')[0].split(':')
                                if len(time_parts) >= 2:
                                    hour = int(time_parts[0])
                                    minute = int(time_parts[1].split()[0])
                                    is_pm = 'PM' in event['time'].split(' - ')[0].upper()
                                    
                                    # Convert to 24-hour format
                                    if is_pm and hour < 12:
                                        hour += 12
                                    elif not is_pm and hour == 12:
                                        hour = 0
                                        
                                    time_info = f"T{hour:02d}{minute:02d}00"
                                    start_date += time_info
                                    
                                    # Try to get end time
                                    if ' - ' in event['time']:
                                        end_time = event['time'].split(' - ')[1]
                                        end_time_parts = end_time.split(':')
                                        if len(end_time_parts) >= 2:
                                            end_hour = int(end_time_parts[0])
                                            end_minute = int(end_time_parts[1].split()[0])
                                            end_is_pm = 'PM' in end_time.upper()
                                            
                                            if end_is_pm and end_hour < 12:
                                                end_hour += 12
                                            elif not end_is_pm and end_hour == 12:
                                                end_hour = 0
                                                
                                            end_time_info = f"T{end_hour:02d}{end_minute:02d}00"
                                            end_date += end_time_info
                                        else:
                                            end_date += time_info
                                    else:
                                        # Default to 1 hour event
                                        end_date += time_info
                            
                            # Create Google Calendar URL
                            calendar_url = f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={title}&dates={start_date}/{end_date}&details={description}&location={location}"
                            
                            event_text += f"\n📆 [Add to Google Calendar]({calendar_url})\n"
                    except Exception as e:
                        logger.error(f"Error creating calendar link: {str(e)}")
                
                # Description with italic formatting
                if 'description' in event and event['description']:
                    # Truncate description if too long (Telegram messages have length limits)
                    desc = event['description']
                    if len(desc) > 200:
                        desc = desc[:197] + "..."
                    event_text += f"\n_{desc}_"
                
                # Send each event as a separate message with Markdown parsing
                await update.message.reply_text(event_text, parse_mode="Markdown", disable_web_page_preview=False)
                
                # Add a small delay between messages to avoid rate limiting
                await asyncio.sleep(0.5)
        else:
            await update.message.reply_text("No events found in the database.")
    else:
        await update.message.reply_text("Sorry, there was an error fetching events. Please try again later.")

# Define the function for handling the /echo command
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Start listening for the next message the user sends
    context.user_data['echo_mode'] = True
    await update.message.reply_text("I will now echo whatever you send.")

# Define a function to handle messages when echo mode is active
async def handle_echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Only reply if the echo mode is active
    if context.user_data.get('echo_mode', False):
        await update.message.reply_text(update.message.text)
        context.user_data['echo_mode'] = False


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