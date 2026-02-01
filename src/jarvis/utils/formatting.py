"""Telegram message formatting utilities.

Converts Markdown to Telegram-compatible HTML and escapes special characters.
"""

import re


def format_for_telegram(text: str) -> str:
    """Convert Markdown-style text to Telegram HTML format.

    Handles: **bold**, *italic*, __underline__, `code`, ```code blocks```,
    headers (##), bullet points (- or *), and HTML escaping.

    Returns the original text if input is empty/None.
    """
    if not text:
        return text or ""

    # Step 1: Strip unsupported HTML tags BEFORE anything else
    # Convert <li> items to "- " bullet points
    text = re.sub(r"<li[^>]*>\s*", "- ", text, flags=re.IGNORECASE)
    text = re.sub(r"</li>", "", text, flags=re.IGNORECASE)
    # Remove <ol>, </ol>, <ul>, </ul>, <p>, </p>, <div>, </div>, <span>, </span>, <br>, <h1-6>
    text = re.sub(r"</?(?:ol|ul|p|div|span|h[1-6]|br/?)[^>]*>", "", text, flags=re.IGNORECASE)

    # Step 2: Protect existing valid Telegram HTML tags with placeholders
    protected_segments: list[tuple[str, str]] = []
    placeholder_counter = 0

    def protect(match: re.Match) -> str:
        nonlocal placeholder_counter
        placeholder = f"\x00PROT{placeholder_counter}\x00"
        protected_segments.append((placeholder, match.group(0)))
        placeholder_counter += 1
        return placeholder

    # Protect existing HTML tags that Telegram supports
    telegram_tags = r"</?(?:b|i|u|s|code|pre|a|tg-spoiler|blockquote)(?:\s[^>]*)?>"
    text = re.sub(telegram_tags, protect, text, flags=re.IGNORECASE)

    # Step 3: Protect code blocks (``` ... ```)
    def protect_code_block(match: re.Match) -> str:
        nonlocal placeholder_counter
        lang = match.group(1) or ""
        code = match.group(2)
        # Escape HTML inside code
        code = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if lang:
            html = f'<pre><code class="language-{lang}">{code}</code></pre>'
        else:
            html = f"<pre>{code}</pre>"
        placeholder = f"\x00PROT{placeholder_counter}\x00"
        protected_segments.append((placeholder, html))
        placeholder_counter += 1
        return placeholder

    text = re.sub(r"```(\w+)?\n?(.*?)```", protect_code_block, text, flags=re.DOTALL)

    # Step 4: Protect inline code (` ... `)
    def protect_inline_code(match: re.Match) -> str:
        nonlocal placeholder_counter
        code = match.group(1)
        code = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html = f"<code>{code}</code>"
        placeholder = f"\x00PROT{placeholder_counter}\x00"
        protected_segments.append((placeholder, html))
        placeholder_counter += 1
        return placeholder

    text = re.sub(r"`([^`]+)`", protect_inline_code, text)

    # Step 5: Escape HTML entities in remaining text
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")

    # Step 6: Convert Markdown to HTML

    # Headers: ## Text -> <b>Text</b>
    text = re.sub(r"^#{1,6}\s+(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)

    # Bold: **text** -> <b>text</b>
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)

    # Underline: __text__ -> <u>text</u> (must be before italic)
    text = re.sub(r"__(.+?)__", r"<u>\1</u>", text)

    # Italic: *text* -> <i>text</i>  (single asterisks, not bullets at line start)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)

    # Bullet points: lines starting with - or * followed by space
    text = re.sub(r"^[\-\*]\s+", "- ", text, flags=re.MULTILINE)

    # Step 7: Restore protected segments (in reverse order to handle nesting)
    for placeholder, original in reversed(protected_segments):
        text = text.replace(placeholder, original)

    # Clean up excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()
