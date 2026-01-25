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
    "JARVIS sta pensando...",
]

from jarvis.config import get_settings
from jarvis.core.orchestrator import process_message
from jarvis.core.router import router
from jarvis.core.freshness import freshness
from jarvis.core.memory import memory
from jarvis.db.repositories import ChatRepository, TaskRepository, LLMLogsRepository
from jarvis.integrations.deepgram_stt import deepgram
from jarvis.utils.logging import get_logger
from langchain_core.messages import HumanMessage, AIMessage
from dateparser import parse as parse_date

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
        "/remind <quando> <messaggio> - Imposta promemoria\n"
        "/tasks - Mostra i tuoi task pendenti\n"
        "/costs - Mostra costi LLM\n"
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


async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /remind command."""
    user_id = update.effective_user.id
    user_id_str = str(user_id)

    if not is_authorized(user_id):
        return

    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_text(
            "Uso: /remind <quando> <messaggio>\n"
            "Esempi:\n"
            "  /remind domani alle 9 Chiamare il dottore\n"
            "  /remind tra 30 minuti Controllare la mail\n"
            "  /remind lunedi prossimo Meeting settimanale"
        )
        return

    # Parse the entire text after /remind
    full_text = " ".join(args)

    # Try to parse the date/time from the beginning
    parsed_date = None
    message = full_text

    # Try to find a time expression at the beginning
    try:
        parsed_date = parse_date(
            full_text,
            languages=["it", "en"],
            settings={
                "PREFER_DATES_FROM": "future",
                "RELATIVE_BASE": None
            }
        )
        if parsed_date:
            # Find where the date expression ends
            # Simple heuristic: the message starts after common time words
            time_words = [
                "alle", "dopo", "fra", "tra", "domani", "oggi",
                "lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato", "domenica",
                "prossimo", "prossima", "minuti", "ore", "giorni"
            ]
            words = full_text.split()
            msg_start = 0
            for i, word in enumerate(words):
                if any(tw in word.lower() for tw in time_words) or word[0].isdigit():
                    msg_start = i + 1
                else:
                    break
            message = " ".join(words[msg_start:]) if msg_start < len(words) else full_text
    except Exception:
        pass

    if not parsed_date:
        await update.message.reply_text(
            "Non ho capito quando vuoi il promemoria.\n"
            "Prova con: 'domani alle 9', 'tra 30 minuti', 'lunedi prossimo'"
        )
        return

    if not message or message == full_text:
        message = "Promemoria"

    # Create the reminder task
    try:
        task = await TaskRepository.enqueue(
            user_id=user_id_str,
            task_type="reminder",
            payload={"message": message},
            scheduled_at=parsed_date,
            priority=3  # Higher priority for reminders
        )

        if task:
            formatted_date = parsed_date.strftime("%d/%m/%Y alle %H:%M")
            await update.message.reply_text(
                f"Promemoria impostato per {formatted_date}\n"
                f"Messaggio: {message}"
            )
        else:
            await update.message.reply_text("Errore nell'impostare il promemoria. Riprova.")

    except Exception as e:
        logger.error(f"Error creating reminder: {e}")
        await update.message.reply_text("Errore nell'impostare il promemoria. Riprova.")


async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /tasks command - show pending tasks."""
    user_id = update.effective_user.id
    user_id_str = str(user_id)

    if not is_authorized(user_id):
        return

    try:
        tasks = await TaskRepository.get_user_tasks(user_id_str, limit=10)

        if not tasks:
            await update.message.reply_text("Non hai task in corso.")
            return

        text = "I tuoi task:\n\n"
        for task in tasks:
            status_emoji = {
                "pending": "....",
                "claimed": "...",
                "running": "..",
                "completed": ".",
                "failed": "!",
                "cancelled": "x"
            }.get(task["status"], "?")

            task_type = task["task_type"]
            payload = task.get("payload", {})
            description = payload.get("message", payload.get("query", ""))[:30]

            if task.get("scheduled_at"):
                from datetime import datetime
                scheduled = datetime.fromisoformat(task["scheduled_at"].replace("Z", "+00:00"))
                time_str = scheduled.strftime("%d/%m %H:%M")
                text += f"{status_emoji} [{task_type}] {time_str} - {description}\n"
            else:
                text += f"{status_emoji} [{task_type}] {description}\n"

        await update.message.reply_text(text)

    except Exception as e:
        logger.error(f"Error fetching tasks: {e}")
        await update.message.reply_text("Errore nel recuperare i task.")


async def costs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /costs command - show LLM usage costs."""
    user_id = update.effective_user.id
    user_id_str = str(user_id)

    if not is_authorized(user_id):
        return

    try:
        # Get today's cost
        today_cost = await LLMLogsRepository.get_total_cost_today(user_id_str)

        # Get costs by model for last 30 days
        costs = await LLMLogsRepository.get_costs_by_period(user_id=user_id_str)

        text = f"Costi LLM:\n\nOggi: ${today_cost:.4f}\n"

        if costs:
            text += "\nUltimi 30 giorni per modello:\n"
            total = 0
            for c in costs:
                model_cost = float(c.get("total_cost", 0) or 0)
                total += model_cost
                text += f"  {c['provider']}/{c['model']}: ${model_cost:.4f} ({c['requests']} req)\n"
            text += f"\nTotale: ${total:.4f}"
        else:
            text += "\nNessun dato disponibile per gli ultimi 30 giorni."

        await update.message.reply_text(text)

    except Exception as e:
        logger.error(f"Error fetching costs: {e}")
        await update.message.reply_text("Errore nel recuperare i costi.")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming voice messages."""
    user_id = update.effective_user.id
    user_id_str = str(user_id)

    if not is_authorized(user_id):
        return

    # Send acknowledgment
    ack_message = await update.message.reply_text("Sto trascrivendo il tuo messaggio vocale...")

    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING
    )

    try:
        # Get the voice message file
        voice = update.message.voice or update.message.audio
        if not voice:
            await ack_message.edit_text("Non riesco a trovare il file audio.")
            return

        # Download the file
        file = await context.bot.get_file(voice.file_id)
        audio_data = await file.download_as_bytearray()

        # Determine file extension
        if voice.mime_type:
            ext_map = {
                "audio/ogg": ".ogg",
                "audio/mpeg": ".mp3",
                "audio/mp4": ".m4a",
                "audio/wav": ".wav",
                "audio/webm": ".webm",
            }
            ext = ext_map.get(voice.mime_type, ".ogg")
        else:
            ext = ".ogg"

        # Transcribe with Deepgram Nova-3
        deepgram.set_user_context(user_id_str)
        transcribed_text = await deepgram.transcribe_bytes(
            bytes(audio_data),
            filename=f"voice{ext}",
            language="it",
            user_id=user_id_str
        )

        if not transcribed_text or not transcribed_text.strip():
            await ack_message.edit_text("Non sono riuscito a trascrivere il messaggio vocale.")
            return

        # Update ack message with transcription
        await ack_message.edit_text(f"JARVIS sta pensando...\n\n(Hai detto: \"{transcribed_text[:100]}{'...' if len(transcribed_text) > 100 else ''}\")")

        # Process the transcribed text as a normal message
        history = conversation_cache.get(user_id)
        response = await process_message(user_id_str, transcribed_text, history.copy())

        # Update cache
        conversation_cache.update(user_id, transcribed_text, response)

        # Delete ack and send response
        try:
            await ack_message.delete()
        except Exception:
            pass

        await update.message.reply_text(response, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error processing voice message: {e}", exc_info=True)
        try:
            await ack_message.delete()
        except Exception:
            pass
        await update.message.reply_text(
            "Mi dispiace, c'è stato un errore nel processare il messaggio vocale. Riprova."
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages."""
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

        # Send response with HTML parsing
        await update.message.reply_text(response, parse_mode="HTML")

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
    app.add_handler(CommandHandler("remind", remind_command))
    app.add_handler(CommandHandler("tasks", tasks_command))
    app.add_handler(CommandHandler("costs", costs_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

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
