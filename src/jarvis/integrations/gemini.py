from google import genai
from google.genai import types
from typing import Optional
from jarvis.config import get_settings
from jarvis.utils.logging import get_logger
from jarvis.utils.llm_logger import LLMLogEntry, llm_logger

logger = get_logger(__name__)


class GeminiClient:
    def __init__(self):
        settings = get_settings()
        self.client = genai.Client(api_key=settings.google_api_key)
        self.default_model = settings.default_model
        self.powerful_model = settings.powerful_model
        self.embedding_model = settings.embedding_model
        self._current_user_id: Optional[str] = None

    def set_user_context(self, user_id: str):
        """Set current user for logging context."""
        self._current_user_id = user_id

    async def generate(
        self,
        prompt: str,
        system_instruction: str = None,
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        user_id: str = None
    ) -> str:
        """Generate text response."""
        model_to_use = model or self.default_model
        effective_user_id = user_id or self._current_user_id

        # Prepare log entry
        log_entry = LLMLogEntry(
            provider="gemini",
            model=model_to_use,
            user_prompt=prompt,
            system_prompt=system_instruction,
            temperature=temperature,
            max_tokens=max_tokens,
            user_id=effective_user_id,
        )
        log_entry.start_timer()

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        if system_instruction:
            config.system_instruction = system_instruction

        try:
            response = await self.client.aio.models.generate_content(
                model=model_to_use,
                contents=prompt,
                config=config
            )

            log_entry.stop_timer()
            log_entry.response = response.text
            log_entry.finish_reason = "stop"

            # Extract token counts if available
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                log_entry.input_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0)
                log_entry.output_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0)
                log_entry.cached_tokens = getattr(response.usage_metadata, 'cached_content_token_count', 0)

            await llm_logger.log(log_entry)
            return response.text

        except Exception as e:
            log_entry.stop_timer()
            log_entry.is_error = True
            log_entry.error_message = str(e)
            await llm_logger.log(log_entry)
            raise

    async def generate_with_history(
        self,
        messages: list[dict],
        system_instruction: str = None,
        model: str = None,
        temperature: float = 0.7,
        user_id: str = None
    ) -> str:
        """Generate with conversation history."""
        model_to_use = model or self.default_model
        effective_user_id = user_id or self._current_user_id

        # Get last user message for logging
        last_user_msg = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"),
            ""
        )

        # Prepare log entry
        log_entry = LLMLogEntry(
            provider="gemini",
            model=model_to_use,
            user_prompt=last_user_msg,
            system_prompt=system_instruction,
            full_messages=messages,
            temperature=temperature,
            user_id=effective_user_id,
        )
        log_entry.start_timer()

        # Convert messages to Gemini format
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(types.Content(
                role=role,
                parts=[types.Part(text=msg["content"])]
            ))

        config = types.GenerateContentConfig(
            temperature=temperature,
        )

        if system_instruction:
            config.system_instruction = system_instruction

        try:
            response = await self.client.aio.models.generate_content(
                model=model_to_use,
                contents=contents,
                config=config
            )

            log_entry.stop_timer()
            log_entry.response = response.text
            log_entry.finish_reason = "stop"

            # Extract token counts if available
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                log_entry.input_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0)
                log_entry.output_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0)
                log_entry.cached_tokens = getattr(response.usage_metadata, 'cached_content_token_count', 0)

            await llm_logger.log(log_entry)
            return response.text

        except Exception as e:
            log_entry.stop_timer()
            log_entry.is_error = True
            log_entry.error_message = str(e)
            await llm_logger.log(log_entry)
            raise

    async def generate_stream(
        self,
        prompt: str,
        system_instruction: str = None,
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        user_id: str = None
    ):
        """Generate text response as an async stream of chunks."""
        model_to_use = model or self.default_model
        effective_user_id = user_id or self._current_user_id

        log_entry = LLMLogEntry(
            provider="gemini",
            model=model_to_use,
            user_prompt=prompt,
            system_prompt=system_instruction,
            temperature=temperature,
            max_tokens=max_tokens,
            user_id=effective_user_id,
        )
        log_entry.start_timer()

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        if system_instruction:
            config.system_instruction = system_instruction

        full_response = []
        try:
            async for chunk in self.client.aio.models.generate_content_stream(
                model=model_to_use,
                contents=prompt,
                config=config
            ):
                if chunk.text:
                    full_response.append(chunk.text)
                    yield chunk.text

            log_entry.stop_timer()
            log_entry.response = "".join(full_response)
            log_entry.finish_reason = "stop"
            await llm_logger.log(log_entry)

        except Exception as e:
            log_entry.stop_timer()
            log_entry.is_error = True
            log_entry.error_message = str(e)
            await llm_logger.log(log_entry)
            raise

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for text."""
        try:
            response = await self.client.aio.models.embed_content(
                model=self.embedding_model,
                contents=text
            )
            return response.embeddings[0].values
        except Exception as e:
            logger.error(f"Embedding failed for model {self.embedding_model}: {e}")
            raise

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        try:
            response = await self.client.aio.models.embed_content(
                model=self.embedding_model,
                contents=texts
            )
            return [emb.values for emb in response.embeddings]
        except Exception as e:
            logger.error(f"Batch embedding failed for model {self.embedding_model}: {e}")
            raise


# Singleton
gemini = GeminiClient()
