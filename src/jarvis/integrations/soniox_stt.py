import httpx
import wave
import io
import asyncio
import json
from pathlib import Path
from jarvis.config import get_settings
from jarvis.utils.logging import get_logger
from jarvis.integrations.gemini import gemini

logger = get_logger(__name__)

SYSTEM_PROMPT = """
## Auto-correzioni:
Quando l’utente si corregge, SCARTI tutto ciò che precede il trigger di correzione:
- Trigger: "no", "aspetta", "in realtà", "annulla", "cancella", "no no", "annulla tutto", "non importa", "scusa", "ops"
- Esempio: "compra latte no aspetta compra acqua" → "Compra acqua." (NON "Compra latte. Compra acqua.")
- Esempio: "di’ a John no in realtà di’ a Sarah" → "Di’ a Sarah."
- Se la correzione annulla completamente: "invia email no aspetta annulla tutto" → "" (vuoto)

## Catene di comandi multipli:
Quando più comandi sono concatenati, ESEGUA TUTTI in sequenza:
- "rendi X in grassetto no aspetta rendi Y in grassetto" → **Y** (correzione + formattazione)
- "intestazione spesa elenco latte no uova" →
  # Spesa
  - Uova (intestazione + correzione + punto elenco)
- "il prezzo è cinquanta no sessanta euro" → Il prezzo è 60 €. (correzione + numero)

## Pulizia del testo:
- Elimini TUTTI i duplicati.
- Elimini TUTTE le filler words e intercalari vocali come: “uh”, “uhm”, “um”, “mh”, “…”.
- Ritorni ESCLUSIVAMENTE il testo finale pulito, ordinato e normalizzato.
- Nessun commento, nessuna spiegazione, nessun contenuto extra.

## Normalizzazione del vocabolario:
Quando rileva incongruenze tra il testo e il vocabolario sottostante, SOSTITUISCA automaticamente con il termine corretto.

Custom vocabulary (canonico):
- GoHighlevel
- API
- Squadd
- CRM
- ngrok
- vs code
- kill
- killato
- killa
- VPS
- Server
- Form
- Custom
- Clickup
- claude code
- gpt
- AI
- core
- postgres
- supabase
- NON aggiunga emoji a meno che l’utente non le richieda esplicitamente (es.: "battuta sui gatti" → NO 😺)ore" → ❤️, "emoji fuoco" → 🔥
"""

class SonioxClient:
    """Soniox STT Client with Gemini post-processing."""

    def __init__(self):
        self._settings = get_settings()
        self._api_key = self._settings.soniox_api_key
        self._model = self._settings.soniox_model or "srt-tt-v4"
        self._user_id = None
        self._base_url = "https://api.soniox.com/v1"

    def set_user_context(self, user_id: str):
        """Set user context for logging."""
        self._user_id = user_id

    async def _clean_transcript(self, text: str) -> str:
        """Clean transcript using Gemini with custom prompt."""
        if not text:
            return ""
        
        try:
            logger.info(f"Cleaning transcript: {text[:50]}...")
            cleaned = await gemini.generate(
                prompt=f"Clean this transcript:\n\n{text}",
                system_instruction=SYSTEM_PROMPT,
                model="gemini-2.5-flash",  # Use fast model
                user_id=self._user_id
            )
            logger.info(f"Cleaned transcript: {cleaned[:50]}...")
            return cleaned.strip()
        except Exception as e:
            logger.error(f"Error cleaning transcript: {e}")
            return text  # Fallback to original text

    async def _transcribe_file(self, file_content: bytes, filename: str, language: str = "it") -> str:
        """Upload file and transcribe using Soniox REST API."""
        if not self._api_key:
            raise ValueError("SONIOX_API_KEY not configured")

        headers = {"Authorization": f"Bearer {self._api_key}"}
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            # 1. Upload File
            logger.debug(f"Uploading file: {filename} ({len(file_content)} bytes)")
            files = {"file": (filename, file_content)}
            resp = await client.post(f"{self._base_url}/files", headers=headers, files=files)
            resp.raise_for_status()
            file_id = resp.json()["id"]

            try:
                # 2. Create Transcription
                logger.debug(f"Creating transcription for file_id: {file_id}")
                
                # Context with custom vocabulary (though LLM cleaning handles it too, this helps STT accuracy)
                custom_terms = [
                    "GoHighlevel", "API", "Squadd", "CRM", "ngrok", "vs code", 
                    "kill", "killato", "killa", "VPS", "Server", "Form", "Custom", 
                    "Clickup", "claude code", "gpt", "AI", "core", "postgres", "supabase"
                ]
                
                payload = {
                    "file_id": file_id,
                    "model": self._model,
                    "language_hints": ["it", "en"] if language == "it" else [language],
                    "context": {
                        "terms": custom_terms
                    }
                }
                
                resp = await client.post(f"{self._base_url}/transcriptions", headers=headers, json=payload)
                resp.raise_for_status()
                transcription_id = resp.json()["id"]

                # 3. Poll for completion
                logger.debug(f"Polling transcription: {transcription_id}")
                while True:
                    await asyncio.sleep(0.5)  # Poll every 500ms
                    resp = await client.get(f"{self._base_url}/transcriptions/{transcription_id}", headers=headers)
                    resp.raise_for_status()
                    status = resp.json()["status"]
                    
                    if status == "completed":
                        break
                    elif status == "error":
                        error_msg = resp.json().get("error_message", "Unknown error")
                        raise RuntimeError(f"Transcription failed: {error_msg}")
                
                # 4. Get Transcript
                logger.debug("Getting transcript text")
                resp = await client.get(f"{self._base_url}/transcriptions/{transcription_id}/transcript", headers=headers)
                resp.raise_for_status()
                result = resp.json()
                
                full_text = ""
                if "text" in result:
                    full_text = result["text"]
                elif "words" in result:
                    full_text = "".join([w.get("text", "") for w in result["words"]])
                else:
                    full_text = str(result)

                logger.info(f"Raw Soniox Transcript: {full_text[:50]}...")
                
                # 5. Clean with Gemini
                return await self._clean_transcript(full_text)

            finally:
                # Cleanup file
                try:
                    await client.delete(f"{self._base_url}/files/{file_id}", headers=headers)
                except Exception as e:
                    logger.warning(f"Failed to delete file {file_id}: {e}")

    async def transcribe(self, audio_path: str | Path, language: str = "it", user_id: str = None) -> str:
        """Transcribe audio file from path."""
        if user_id:
            self.set_user_context(user_id)
            
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {path}")
            
        with open(path, "rb") as f:
            content = f.read()
            
        return await self._transcribe_file(content, path.name, language)

    async def transcribe_bytes(self, audio_data: bytes, filename: str = "audio.ogg", language: str = "it", user_id: str = None) -> str:
        """Transcribe audio bytes."""
        if user_id:
            self.set_user_context(user_id)
        return await self._transcribe_file(audio_data, filename, language)

    async def transcribe_pcm(self, audio_data: bytes, sample_rate: int = 16000, language: str = "it", user_id: str = None) -> str:
        """Transcribe raw PCM audio (wrapped in WAV)."""
        if user_id:
            self.set_user_context(user_id)
            
        # Wrap PCM in WAV
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data)
            
        wav_content = buffer.getvalue()
        return await self._transcribe_file(wav_content, "audio.wav", language)

# Singleton
soniox = SonioxClient()
