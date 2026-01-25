from datetime import datetime, timedelta
from typing import Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from jarvis.config import get_settings
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)


class GoogleCalendarClient:
    def __init__(self):
        settings = get_settings()
        self.credentials = Credentials(
            token=None,
            refresh_token=settings.google_refresh_token,
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            token_uri="https://oauth2.googleapis.com/token"
        )
        self.service = build("calendar", "v3", credentials=self.credentials)

    def get_events(
        self,
        start: datetime = None,
        end: datetime = None,
        max_results: int = 50,
        calendar_id: str = "primary"
    ) -> list[dict]:
        """Fetch calendar events."""
        if not start:
            start = datetime.utcnow()
        if not end:
            end = start + timedelta(days=7)

        events_result = self.service.events().list(
            calendarId=calendar_id,
            timeMin=start.isoformat() + "Z",
            timeMax=end.isoformat() + "Z",
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        events = events_result.get("items", [])

        return [self._format_event(e) for e in events]

    def create_event(
        self,
        title: str,
        start: datetime,
        end: datetime,
        description: str = None,
        location: str = None,
        attendees: list[str] = None,
        calendar_id: str = "primary"
    ) -> dict:
        """Create a new calendar event."""
        event = {
            "summary": title,
            "start": {"dateTime": start.isoformat(), "timeZone": "Europe/Rome"},
            "end": {"dateTime": end.isoformat(), "timeZone": "Europe/Rome"},
        }

        if description:
            event["description"] = description
        if location:
            event["location"] = location
        if attendees:
            event["attendees"] = [{"email": a} for a in attendees]

        result = self.service.events().insert(
            calendarId=calendar_id,
            body=event,
            sendUpdates="all" if attendees else "none"
        ).execute()

        return self._format_event(result)

    def update_event(
        self,
        event_id: str,
        updates: dict,
        calendar_id: str = "primary"
    ) -> dict:
        """Update an existing event."""
        # Get current event
        event = self.service.events().get(
            calendarId=calendar_id,
            eventId=event_id
        ).execute()

        # Apply updates
        if "title" in updates:
            event["summary"] = updates["title"]
        if "start" in updates:
            event["start"]["dateTime"] = updates["start"].isoformat()
        if "end" in updates:
            event["end"]["dateTime"] = updates["end"].isoformat()
        if "description" in updates:
            event["description"] = updates["description"]
        if "location" in updates:
            event["location"] = updates["location"]

        result = self.service.events().update(
            calendarId=calendar_id,
            eventId=event_id,
            body=event
        ).execute()

        return self._format_event(result)

    def delete_event(
        self,
        event_id: str,
        calendar_id: str = "primary"
    ) -> bool:
        """Delete an event."""
        self.service.events().delete(
            calendarId=calendar_id,
            eventId=event_id
        ).execute()
        return True

    def find_free_slots(
        self,
        duration_minutes: int,
        start: datetime = None,
        end: datetime = None,
        calendar_id: str = "primary"
    ) -> list[dict]:
        """Find available time slots."""
        if not start:
            start = datetime.utcnow()
        if not end:
            end = start + timedelta(days=7)

        # Get busy times
        body = {
            "timeMin": start.isoformat() + "Z",
            "timeMax": end.isoformat() + "Z",
            "items": [{"id": calendar_id}]
        }

        result = self.service.freebusy().query(body=body).execute()
        busy_times = result["calendars"][calendar_id]["busy"]

        # Find free slots (simplified - between 9 AM and 6 PM)
        free_slots = []
        current = start.replace(hour=9, minute=0, second=0, microsecond=0)

        while current < end:
            slot_end = current + timedelta(minutes=duration_minutes)

            # Check if slot is within working hours
            if current.hour >= 9 and slot_end.hour <= 18:
                is_free = True
                for busy in busy_times:
                    busy_start = datetime.fromisoformat(busy["start"].replace("Z", "+00:00"))
                    busy_end = datetime.fromisoformat(busy["end"].replace("Z", "+00:00"))

                    if not (slot_end <= busy_start or current >= busy_end):
                        is_free = False
                        break

                if is_free:
                    free_slots.append({
                        "start": current.isoformat(),
                        "end": slot_end.isoformat()
                    })

            current += timedelta(minutes=30)  # Check every 30 min

            # Skip to next day if past working hours
            if current.hour >= 18:
                current = (current + timedelta(days=1)).replace(hour=9, minute=0)

        return free_slots[:10]  # Return max 10 slots

    def _format_event(self, event: dict) -> dict:
        """Format event for consistent output."""
        start = event.get("start", {})
        end = event.get("end", {})

        return {
            "id": event.get("id"),
            "title": event.get("summary", "No title"),
            "start": start.get("dateTime") or start.get("date"),
            "end": end.get("dateTime") or end.get("date"),
            "description": event.get("description"),
            "location": event.get("location"),
            "attendees": [a.get("email") for a in event.get("attendees", [])],
            "link": event.get("htmlLink")
        }


# Singleton
calendar_client = GoogleCalendarClient()
