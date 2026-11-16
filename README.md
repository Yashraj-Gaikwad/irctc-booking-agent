# IRCTC Waitlist & Alternative Train Booking Agent

An Agentic AI system built with the Google GenAI SDK (`gemini-3.5-flash`) and SQLite that autonomously resolves waitlisted Indian Railways (IRCTC) tickets.

## How It Works
1. **`check_pnr_status`**: Queries `irctc_bookings.db` to check if a PNR is Confirmed (`CNF`) or Waitlisted (`WL`).
2. **`find_alternative_trains`**: Searches available trains between source and destination stations (`vacant_seats > 0`).
3. **`book_confirmed_seat`**: Books the earliest departing train with vacant seats and commits the new PNR record to SQLite.

## How to Run Locally
```bash
pip install -r requirements.txt
set GEMINI_API_KEY=your_api_key_here
python agent_demo.py