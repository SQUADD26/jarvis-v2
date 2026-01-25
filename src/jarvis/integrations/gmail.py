import base64
from email.mime.text import MIMEText
from typing import Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from jarvis.config import get_settings
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)


class GmailClient:
    def __init__(self):
        settings = get_settings()
        self.credentials = Credentials(
            token=None,
            refresh_token=settings.google_refresh_token,
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            token_uri="https://oauth2.googleapis.com/token"
        )
        self.service = build("gmail", "v1", credentials=self.credentials)

    def get_inbox(
        self,
        max_results: int = 20,
        unread_only: bool = False,
        query: str = None,
        fetch_full_details: bool = False
    ) -> list[dict]:
        """Fetch inbox emails.

        Args:
            max_results: Maximum number of emails to fetch
            unread_only: Filter to only unread emails
            query: Gmail search query
            fetch_full_details: If True, fetches full email details (slower).
                              If False, returns summary with snippets only.
        """
        q = query or ""
        if unread_only:
            q = f"is:unread {q}".strip()

        results = self.service.users().messages().list(
            userId="me",
            maxResults=max_results,
            q=q or None
        ).execute()

        messages = results.get("messages", [])

        if not messages:
            return []

        if fetch_full_details:
            # Fetch full details for each message (N+1 pattern, use sparingly)
            return [self.get_email(msg["id"]) for msg in messages]

        # Fetch minimal details using METADATA format to avoid N+1 issue
        email_summaries = []
        for msg in messages:
            summary = self._get_email_summary(msg["id"])
            if summary:
                email_summaries.append(summary)

        return email_summaries

    def _get_email_summary(self, message_id: str) -> dict:
        """Get email summary with minimal API calls using METADATA format."""
        message = self.service.users().messages().get(
            userId="me",
            id=message_id,
            format="metadata",
            metadataHeaders=["From", "To", "Subject", "Date"]
        ).execute()

        headers = message.get("payload", {}).get("headers", [])

        def get_header(name: str) -> str:
            for h in headers:
                if h["name"].lower() == name.lower():
                    return h["value"]
            return ""

        return {
            "id": message_id,
            "thread_id": message.get("threadId"),
            "from": get_header("From"),
            "to": get_header("To"),
            "subject": get_header("Subject"),
            "date": get_header("Date"),
            "snippet": message.get("snippet"),
            "labels": message.get("labelIds", []),
            "is_unread": "UNREAD" in message.get("labelIds", [])
        }

    def get_email(self, message_id: str) -> dict:
        """Get full email details."""
        message = self.service.users().messages().get(
            userId="me",
            id=message_id,
            format="full"
        ).execute()

        headers = message.get("payload", {}).get("headers", [])

        def get_header(name: str) -> str:
            for h in headers:
                if h["name"].lower() == name.lower():
                    return h["value"]
            return ""

        # Get body
        body = self._get_body(message.get("payload", {}))

        return {
            "id": message_id,
            "thread_id": message.get("threadId"),
            "from": get_header("From"),
            "to": get_header("To"),
            "subject": get_header("Subject"),
            "date": get_header("Date"),
            "snippet": message.get("snippet"),
            "body": body,
            "labels": message.get("labelIds", []),
            "is_unread": "UNREAD" in message.get("labelIds", [])
        }

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        cc: str = None,
        bcc: str = None
    ) -> dict:
        """Send an email."""
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject

        if cc:
            message["cc"] = cc
        if bcc:
            message["bcc"] = bcc

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        result = self.service.users().messages().send(
            userId="me",
            body={"raw": raw}
        ).execute()

        return {"id": result["id"], "status": "sent"}

    def reply_email(
        self,
        message_id: str,
        body: str
    ) -> dict:
        """Reply to an email."""
        original = self.get_email(message_id)

        # Build reply
        message = MIMEText(body)
        message["to"] = original["from"]
        message["subject"] = f"Re: {original['subject']}"
        message["In-Reply-To"] = message_id
        message["References"] = message_id

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        result = self.service.users().messages().send(
            userId="me",
            body={
                "raw": raw,
                "threadId": original["thread_id"]
            }
        ).execute()

        return {"id": result["id"], "status": "sent"}

    def search_emails(self, query: str, max_results: int = 20) -> list[dict]:
        """Search emails with Gmail query syntax."""
        return self.get_inbox(max_results=max_results, query=query)

    def mark_as_read(self, message_id: str) -> bool:
        """Mark email as read."""
        self.service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": ["UNREAD"]}
        ).execute()
        return True

    def _get_body(self, payload: dict) -> str:
        """Extract email body from payload."""
        if "body" in payload and payload["body"].get("data"):
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode()

        if "parts" in payload:
            for part in payload["parts"]:
                if part.get("mimeType") == "text/plain":
                    if part.get("body", {}).get("data"):
                        return base64.urlsafe_b64decode(part["body"]["data"]).decode()
                elif "parts" in part:
                    return self._get_body(part)

        return ""


# Singleton
gmail_client = GmailClient()
