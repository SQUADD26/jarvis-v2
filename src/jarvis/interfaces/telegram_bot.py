import asyncio
import random
from collections import OrderedDict
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from telegram.constants import ChatAction

# Varied acknowledgment messages for natural interaction
ACKNOWLEDGMENT_MESSAGES = [
    "Certamente, solo un attimo... ⏳",
    "Un momento, ci penso subito... 🤔",
    "Dammi un secondo... ⏳",
    "Ci sono, fammi controllare... 👀",
    "Subito, un attimo di pazienza... ⏳",
    "Ok, verifico immediatamente... 🔍",
    "Sì, dammi un istante... ⏳",
    "Perfetto, controllo subito... ✨",
    "Un secondo che verifico... 🔎",
    "Certo, fammi dare un'occhiata... 👁️",
    "Arrivo, solo un momento... ⏳",
    "Ci sono sopra, un attimo... 💭",
    "Ok, mi metto subito al lavoro... ⚡",
    "Capito, dammi un secondo... ⏳",
    "Sì sì, controllo subito... 🎯",
    "Un momento che ci guardo... 👀",
    "Perfetto, fammi vedere... 🔍",
    "D'accordo, un istante... ⏳",
    "Ricevuto, ci penso io... 💡",
    "Aspetta un attimo che controllo... ⏳",
]

from jarvis.config import get_settings
from jarvis.core.orchestrator import process_message
from jarvis.core.router import router
from jarvis.core.freshness import freshness
from jarvis.core.memory import memory
from jarvis.db.repositories import ChatRepository
from jarvis.utils.logging import get_logger
from langchain_core.messages import HumanMessage, AIMessage

logger = get_logger(__name__)
settings = get_settings()

# LRU cache for conversation history with bounded size
MAX_CACHED_USERS = 100  # Maximum users to keep in memory
MAX_HISTORY_PER_USER = 20  # Maximum messages per user


class ConversationCache:
    """LRU cache for conversation history with bounded memory usage."""

    def __init__(self, max_users: int = MAX_CACHED_USERS, max_history: int = MAX_HISTORY_PER_USER):
        self._cache: OrderedDict[int, list] = OrderedDict()
        self._max_users = max_users
        self._max_history = max_history

    def get(self, user_id: int) -> list:
        """Get conversation history for user, moving to end (most recently used)."""
        if user_id in self._cache:
            self._cache.move_to_end(user_id)
            return self._cache[user_id]
        return []

    def update(self, user_id: int, user_message: str, assistant_response: str):
        """Update conversation history for user."""
        if user_id not in self._cache:
            self._cache[user_id] = []

        self._cache[user_id].append(HumanMessage(content=user_message))
        self._cache[user_id].append(AIMessage(content=assistant_response))

        # Trim history if too long
        if len(self._cache[user_id]) > self._max_history * 2:
            self._cache[user_id] = self._cache[user_id][-self._max_history * 2:]

        # Move to end (most recently used)
        self._cache.move_to_end(user_id)

        # Evict oldest users if cache is full
        while len(self._cache) > self._max_users:
            self._cache.popitem(last=False)

    def clear(self, user_id: int):
        """Clear conversation history for user."""
        if user_id in self._cache:
            del self._cache[user_id]


# Singleton conversation cache
conversation_cache = ConversationCache()


def is_authorized(user_id: int) -> bool:
    """Check if user is authorized."""
    allowed = settings.telegram_allowed_users_list
    return not allowed or user_id in allowed


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("Non sei autorizzato ad usare questo bot.")
        return

    await update.message.reply_text(
        "Ciao! Sono Jarvis, il tuo assistente personale.\n\n"
        "Posso aiutarti con:\n"
        "- Calendario e appuntamenti\n"
        "- Email\n"
        "- Ricerche web\n"
        "- E molto altro!\n\n"
        "Scrivi qualcosa per iniziare."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await update.message.reply_text(
        "Comandi disponibili:\n"
        "/start - Avvia il bot\n"
        "/help - Mostra questo messaggio\n"
        "/refresh [calendar|email|all] - Aggiorna cache\n"
        "/memory - Mostra fatti memorizzati\n"
        "/clear - Pulisci cronologia conversazione\n"
    )


async def refresh_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /refresh command."""
    user_id = str(update.effective_user.id)

    if not is_authorized(int(user_id)):
        return

    args = context.args
    resource = args[0] if args else "all"

    await update.message.reply_text(f"Aggiornamento cache {resource}...")

    if resource == "all":
        await freshness.invalidate("calendar", user_id)
        await freshness.invalidate("email", user_id)
    else:
        await freshness.invalidate(resource, user_id)

    await update.message.reply_text("Cache aggiornata!")


async def memory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /memory command."""
    user_id = str(update.effective_user.id)

    if not is_authorized(int(user_id)):
        return

    facts = await memory.get_all_facts(user_id)

    if not facts:
        await update.message.reply_text("Non ho ancora memorizzato nulla su di te.")
        return

    text = "Ecco cosa ricordo:\n\n"
    for fact in facts[:20]:  # Limit to 20
        category_emoji = {
            "preference": "⭐",
            "fact": "📌",
            "episode": "📅",
            "task": "✅"
        }.get(fact["category"], "•")
        text += f"{category_emoji} {fact['fact']}\n"

    await update.message.reply_text(text)


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clear command."""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        return

    conversation_cache.clear(user_id)
    await update.message.reply_text("Cronologia conversazione cancellata!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages."""
    user_id = update.effective_user.id
    user_id_str = str(user_id)

    if not is_authorized(user_id):
        return

    message = update.message.text

    # Send immediate acknowledgment (random variation)
    ack_text = random.choice(ACKNOWLEDGMENT_MESSAGES)
    ack_message = await update.message.reply_text(ack_text)

    # Show typing indicator while processing
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING
    )

    try:
        # Get conversation history from cache
        history = conversation_cache.get(user_id)

        # Process message with Jarvis
        response = await process_message(user_id_str, message, history.copy())

        # Update cache with new messages
        conversation_cache.update(user_id, message, response)

        # Delete the acknowledgment message and send the real response
        try:
            await ack_message.delete()
        except Exception:
            pass  # Ignore if we can't delete (e.g., message too old)

        # Send response
        await update.message.reply_text(response)

    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        # Try to delete ack message on error too
        try:
            await ack_message.delete()
        except Exception:
            pass
        await update.message.reply_text(
            "Mi dispiace, c'è stato un errore. Riprova tra poco."
        )


def create_bot() -> Application:
    """Create and configure the Telegram bot."""
    app = Application.builder().token(settings.telegram_bot_token).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("refresh", refresh_command))
    app.add_handler(CommandHandler("memory", memory_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app


async def run_bot():
    """Run the Telegram bot."""
    # Initialize router
    await router.initialize()

    # Create and run bot
    app = create_bot()

    logger.info("Starting Telegram bot...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
