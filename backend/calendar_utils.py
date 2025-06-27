from typing import List, Optional
from datetime import datetime, timezone
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Path to your service account key file
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), 'credentials.json')
SCOPES = ['https://www.googleapis.com/auth/calendar']


def authenticate_google_calendar():
    """Authenticate and return a Google Calendar service client using a service account."""
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    service = build('calendar', 'v3', credentials=credentials)
    return service


def check_availability(service, calendar_id: str, start: datetime, end: datetime) -> bool:
    """Check if the calendar is free between start and end times."""
    body = {
        "timeMin": start.isoformat(),
        "timeMax": end.isoformat(),
        "items": [{"id": calendar_id}]
    }
    events_result = service.freebusy().query(body=body).execute()
    busy_times = events_result['calendars'][calendar_id]['busy']
    return len(busy_times) == 0


def book_event(service, calendar_id: str, start: datetime, end: datetime, summary: str, description: Optional[str] = None, attendees: Optional[List[str]] = None):
    """Book an event in the calendar."""
    event = {
        'summary': summary,
        'start': {
            'dateTime': start.isoformat(),
            'timeZone': start.tzinfo.tzname(start) if start.tzinfo else 'UTC',
        },
        'end': {
            'dateTime': end.isoformat(),
            'timeZone': end.tzinfo.tzname(end) if end.tzinfo else 'UTC',
        },
    }
    if description:
        event['description'] = description
    if attendees:
        event['attendees'] = [{'email': email} for email in attendees]
    created_event = service.events().insert(calendarId=calendar_id, body=event).execute()
    return created_event


def list_upcoming_events(service, calendar_id: str, max_results: int = 5):
    """List the next max_results events on the calendar."""
    now = datetime.now(timezone.utc).isoformat()
    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=now,
        maxResults=max_results,
        singleEvents=True,
        orderBy='startTime',
    ).execute()
    events = events_result.get('items', [])
    return events


def suggest_free_slots(service, calendar_id: str, date: datetime, slot_duration_minutes: int = 60, window_start_hour: int = 9, window_end_hour: int = 18, max_suggestions: int = 3):
    """Suggest up to max_suggestions free slots of given duration on the same day as 'date'."""
    from datetime import timedelta
    suggestions = []
    # Set the search window for the day
    day_start = date.replace(hour=window_start_hour, minute=0, second=0, microsecond=0)
    day_end = date.replace(hour=window_end_hour, minute=0, second=0, microsecond=0)
    # Query busy times for the day
    body = {
        "timeMin": day_start.isoformat(),
        "timeMax": day_end.isoformat(),
        "items": [{"id": calendar_id}]
    }
    events_result = service.freebusy().query(body=body).execute()
    busy_times = events_result['calendars'][calendar_id]['busy']
    # Build a list of busy intervals
    intervals = [(datetime.fromisoformat(b['start']), datetime.fromisoformat(b['end'])) for b in busy_times]
    # Sort intervals by start time
    intervals.sort()
    # Find free slots
    current = day_start
    while current + timedelta(minutes=slot_duration_minutes) <= day_end and len(suggestions) < max_suggestions:
        next_slot_end = current + timedelta(minutes=slot_duration_minutes)
        # Check for overlap with any busy interval
        overlap = False
        for b_start, b_end in intervals:
            if current < b_end and next_slot_end > b_start:
                overlap = True
                current = b_end  # Skip to end of busy interval
                break
        if not overlap:
            suggestions.append(current)
            current = next_slot_end
        # If overlapped, current is already updated
    return suggestions


if __name__ == "__main__":
    service = authenticate_google_calendar()
    calendar_id = input("Enter your calendar ID (usually your email): ")
    mode = input("Type 'list' to list events, 'check' to check availability, or 'book' to book an event: ").strip().lower()
    if mode == 'list':
        events = list_upcoming_events(service, calendar_id)
        if not events:
            print('No upcoming events found.')
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            print(start, event.get('summary', '(No Title)'))
    elif mode == 'check':
        from dateutil import parser
        start_str = input("Enter start datetime (YYYY-MM-DDTHH:MM:SS, e.g. 2024-07-01T14:00:00): ")
        end_str = input("Enter end datetime (YYYY-MM-DDTHH:MM:SS, e.g. 2024-07-01T15:00:00): ")
        start = parser.isoparse(start_str)
        end = parser.isoparse(end_str)
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        is_free = check_availability(service, calendar_id, start, end)
        if is_free:
            print(f"The calendar is FREE between {start} and {end}.")
        else:
            print(f"The calendar is BUSY between {start} and {end}.")
    elif mode == 'book':
        from dateutil import parser
        from datetime import timezone
        start_str = input("Enter start datetime (YYYY-MM-DDTHH:MM:SS, e.g. 2024-07-01T14:00:00): ")
        end_str = input("Enter end datetime (YYYY-MM-DDTHH:MM:SS, e.g. 2024-07-01T15:00:00): ")
        summary = input("Enter event summary: ")
        description = input("Enter event description (optional): ") or None
        attendees_str = input("Enter attendee emails, comma-separated (optional): ")
        attendees = [email.strip() for email in attendees_str.split(",") if email.strip()] if attendees_str else None
        start = parser.isoparse(start_str)
        end = parser.isoparse(end_str)
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        event = book_event(service, calendar_id, start, end, summary, description, attendees)
        print(f"Event created: {event.get('htmlLink')}")
    else:
        print("Unknown mode. Please type 'list', 'check', or 'book'.") 