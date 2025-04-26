import asyncio
from telegram import Update, BotCommand
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes, ApplicationBuilder
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

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
    # Respond with "Hello world!" when the /events command is issued
    await update.message.reply_text("Hello world!")

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