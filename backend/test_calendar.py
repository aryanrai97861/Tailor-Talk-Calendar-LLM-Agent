from calendar_utils import authenticate_google_calendar, list_upcoming_events

if __name__ == "__main__":
    service = authenticate_google_calendar()
    calendar_id = input("Enter your calendar ID (usually your email): ")
    events = list_upcoming_events(service, calendar_id)
    if not events:
        print('No upcoming events found.')
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        print(start, event.get('summary', '(No Title)'))