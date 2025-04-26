import asyncio
import functools
from telegram import Update, BotCommand
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes, ApplicationBuilder
import os
import logging
from tinydb import TinyDB
import importlib.util

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
                
                # Location
                if 'full_address' in event and event['full_address']:
                    event_text += f"📍 *Location:* {event['full_address']}\n"
                
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
        BotCommand("restart", "Restart the bot from scratch"),
        BotCommand("events", "Get event information"),
        BotCommand("echo", "Repeat the next message you send"),
        BotCommand("help", "Show help information"),
    ]
    
    # Set the commands to show in the command menu
    await app.bot.set_my_commands(commands)

    # Add handlers
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