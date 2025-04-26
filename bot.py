import asyncio
from telegram import Update, BotCommand
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes, ApplicationBuilder
import os
import logging
from tinydb import TinyDB
import importlib.util

# Import main function from planner.py
spec = importlib.util.spec_from_file_location("planner", "./planner.py")
planner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(planner)

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the function for handling the /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Welcome! I am your Telegram bot. Use /menu to see available commands.")

# Define the function for handling the /menu command
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    menu_text = (
        "Here are the available commands:\n"
        "/start - Start the bot from scratch\n"
        "/menu - Show this menu\n"
        "/help - Show help information\n"
        "/events - Get events (currently just says 'Hello world!')\n"
        "/echo - Repeat the next message you send"
    )
    await update.message.reply_text(menu_text)

# Define the function for handling the /help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "I am a simple bot that can do the following:\n"
        "/start - Start the bot\n"
        "/menu - Show available commands\n"
        "/help - Show this help text\n"
        "/events - Get event information\n"
        "/echo - Echo your next message"
    )
    await update.message.reply_text(help_text)

# Define the function for handling the /events command
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
            # Format the event information for the user
            event_text = "Here are some upcoming events:\n\n"
            # Limit to 5 events to avoid message size limits
            for event in all_events[:5]:
                event_text += f"📌 *{event['title']}*\n"
                event_text += f"📅 {event['date']} at {event['time']}\n"
                event_text += f"📍 {event['location']}\n"
                if 'suggestion' in event and event['suggestion'] != "TBD":
                    event_text += f"💡 {event['suggestion']}\n"
                event_text += "\n"
            
            event_text += f"\nFound {len(all_events)} events in total."
            await update.message.reply_text(event_text, parse_mode="Markdown")
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
        BotCommand("start", "Start the bot from scratch"),
        BotCommand("menu", "Show available commands"),
        BotCommand("help", "Show help information"),
        BotCommand("events", "Get event information"),
        BotCommand("echo", "Repeat the next message you send")
    ]
    
    # Set the commands to show in the command menu
    await app.bot.set_my_commands(commands)

    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("events", events))
    app.add_handler(CommandHandler("echo", echo))
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