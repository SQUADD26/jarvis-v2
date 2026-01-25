from google import genai
from google.genai import types
from typing import Optional
from jarvis.config import get_settings
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)


class GeminiClient:
    def __init__(self):
        settings = get_settings()
        self.client = genai.Client(api_key=settings.google_api_key)
        self.default_model = settings.default_model
        self.powerful_model = settings.powerful_model

    async def generate(
        self,
        prompt: str,
        system_instruction: str = None,
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> str:
        """Generate text response."""
        model_to_use = model or self.default_model

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        if system_instruction:
            config.system_instruction = system_instruction

        response = await self.client.aio.models.generate_content(
            model=model_to_use,
            contents=prompt,
            config=config
        )

        return response.text

    async def generate_with_history(
        self,
        messages: list[dict],
        system_instruction: str = None,
        model: str = None,
        temperature: float = 0.7
    ) -> str:
        """Generate with conversation history."""
        model_to_use = model or self.default_model

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

        response = await self.client.aio.models.generate_content(
            model=model_to_use,
            contents=contents,
            config=config
        )

        return response.text

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for text."""
        response = await self.client.aio.models.embed_content(
            model="text-embedding-004",
            contents=text
        )
        return response.embeddings[0].values

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        response = await self.client.aio.models.embed_content(
            model="text-embedding-004",
            contents=texts
        )
        return [emb.values for emb in response.embeddings]


# Singleton
gemini = GeminiClient()
