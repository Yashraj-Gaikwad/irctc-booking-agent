# Import Libraries
import os
import sqlite3
from google import genai
from google.genai import types

# Set your API key in Windows terminal first: set GEMINI_API_KEY=your_new_key
api_key = os.getenv("GEMINI_API_KEY", "GEMINI_API_KEY")
gemini_client = genai.Client(api_key=api_key)

# ==============================================================================
# STEP 1: CREATE AND POPULATE LOCAL SQLITE DATABASE
# ==============================================================================
database_filename = "irctc_bookings.db"

# Always start with a fresh database for the demo
if os.path.exists(database_filename):
    os.remove(database_filename)

# Create a new SQLite database and define the schema for passenger bookings and train schedules
db_connection = sqlite3.connect(database_filename)
db_cursor = db_connection.cursor()

# Create tables for passenger bookings and train schedules
db_cursor.execute("""
CREATE TABLE passenger_bookings (
    pnr_number TEXT PRIMARY KEY,
    passenger_name TEXT,
    train_number TEXT,
    train_name TEXT,
    source_station TEXT,
    destination_station TEXT,
    seat_class TEXT,
    booking_status TEXT
)
""")

# Create table for train schedules
db_cursor.execute("""
CREATE TABLE train_schedules (
    train_number TEXT PRIMARY KEY,
    train_name TEXT,
    source_station TEXT,
    destination_station TEXT,
    departure_time TEXT,
    seat_class TEXT,
    vacant_seats INTEGER,
    ticket_fare_inr INTEGER
)
""")

# Populate the tables with sample data for passenger bookings and train schedules
db_cursor.execute("""
INSERT INTO passenger_bookings VALUES 
('8421905612', 'Rohan Kulkarni', '12127', 'Mumbai - Pune Intercity Express', 'CSMT', 'PUNE', 'CC', 'WL 14'),
('8421909999', 'Ajay Deshmukh', '11007', 'Deccan Express', 'CSMT', 'PUNE', '2S', 'CNF / D4 / 32')
""")

# Populate the train schedules table with sample data
db_cursor.execute("""
INSERT INTO train_schedules VALUES 
('22105', 'Indrayani Express', 'CSMT', 'PUNE', '05:40', 'CC', 0, 510),
('12125', 'Pragati Express', 'CSMT', 'PUNE', '16:25', 'CC', 3, 525),
('12123', 'Deccan Queen', 'CSMT', 'PUNE', '17:10', 'CC', 6, 540)
""")

# Commit the changes and close the database connection
db_connection.commit()
db_connection.close()
print("Database ready.\n")

# ==============================================================================
# STEP 2: DEFINE THE 3 TOOLS FOR THE AGENT
# ==============================================================================

# Tool 1: Check PNR Status
def check_pnr_status(pnr_number: str) -> dict:
    """Checks the current IRCTC booking status and journey route for a PNR number."""
    print(f"[Tool 1] Checking PNR status in database for: {pnr_number}")

    # Connect to the SQLite database and fetch the booking record for the given PNR number
    conn = sqlite3.connect(database_filename)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM passenger_bookings WHERE pnr_number = ?", (pnr_number,))
    record = cursor.fetchone()
    conn.close()

    # If the record is not found, return an error message; otherwise, return the booking details
    if record is None:
        return {"error": f"PNR {pnr_number} does not exist."}

    # Return the booking details as a dictionary
    return {
        "pnr_number": record[0],
        "passenger_name": record[1],
        "train_number": record[2],
        "train_name": record[3],
        "source_station": record[4],
        "destination_station": record[5],
        "seat_class": record[6],
        "booking_status": record[7]
    }

# Tool 2: Find Alternative Trains
def find_alternative_trains(source_station: str, destination_station: str) -> list:
    """Finds trains between two station codes that currently have vacant seats."""
    print(f"[Tool 2] Searching vacant seats from {source_station} to {destination_station}")

    # Connect to the SQLite database and fetch trains with vacant seats for the given source and destination stations
    conn = sqlite3.connect(database_filename)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT train_number, train_name, departure_time, seat_class, vacant_seats, ticket_fare_inr
        FROM train_schedules
        WHERE source_station = ? AND destination_station = ? AND vacant_seats > 0
    """, (source_station, destination_station))
    rows = cursor.fetchall()
    conn.close()

    # If no trains are found, return an empty list; otherwise, return the matching trains as a list of dictionaries
    matching_trains = []
    for row in rows:
        matching_trains.append({
            "train_number": row[0],
            "train_name": row[1],
            "departure_time": row[2],
            "seat_class": row[3],
            "vacant_seats": row[4],
            "ticket_fare_inr": row[5]
        })
    return matching_trains


# Tool 3: Book Confirmed Seat
def book_confirmed_seat(train_number: str, passenger_name: str, seat_class: str) -> dict:
    """Books a confirmed seat on an alternative train and updates the SQLite database."""
    print(f"[Tool 3] Booking confirmed seat on Train {train_number} for {passenger_name}")

    # Connect to the SQLite database and fetch the train schedule for the given train number
    conn = sqlite3.connect(database_filename)
    cursor = conn.cursor()

    # Check if the train has vacant seats; if not, return an error message
    cursor.execute("""
        SELECT train_name, source_station, destination_station, vacant_seats 
        FROM train_schedules 
        WHERE train_number = ?
    """, (train_number,))
    train_info = cursor.fetchone()

    # If the train does not exist or has no vacant seats, return an error message
    if train_info is None or train_info[3] <= 0:
        conn.close()
        return {"error": "No vacant seats left on this train."}

    # Update the train schedule to reduce the vacant seat count by 1 and insert a new booking record for the passenger
    new_seat_count = train_info[3] - 1
    cursor.execute("UPDATE train_schedules SET vacant_seats = ? WHERE train_number = ?", (new_seat_count, train_number))

    # Generate a new PNR number for the booking (in a real application, this should be unique and generated properly)
    new_pnr = "8910443210"
    cursor.execute("""
        INSERT INTO passenger_bookings VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (new_pnr, passenger_name, train_number, train_info[0], train_info[1], train_info[2], seat_class, "CNF / C2 / 18"))

    # Commit the changes and close the database connection
    conn.commit()
    conn.close()

    # Return the booking confirmation details as a dictionary
    return {
        "status": "CONFIRMED",
        "new_pnr_number": new_pnr,
        "train_number": train_number,
        "train_name": train_info[0],
        "passenger_name": passenger_name,
        "allocated_seat": "Coach C2, Seat 18",
        "seats_left_on_train": new_seat_count
    }

# ==============================================================================
# STEP 3: EXPLICIT AGENTIC TOOL LOOP (Transparent & Never Hangs)
# ==============================================================================

# Define a mapping of available tools for the agent to use
available_tools = {
    "check_pnr_status": check_pnr_status,
    "find_alternative_trains": find_alternative_trains,
    "book_confirmed_seat": book_confirmed_seat
}

# Define the agent's instructions for handling user requests
agent_instructions = """
You are an Indian Railways Booking Assistant.
Follow these steps when helping a user:
1. Check the passenger's current PNR status first using check_pnr_status.
2. If the status starts with 'CNF' (Confirmed), do NOT book another ticket. Just tell the user their seat details.
3. If the status starts with 'WL' (Waitlisted), search for alternative trains on the same route using find_alternative_trains.
4. Pick the earliest departing train that has vacant seats and book it using book_confirmed_seat.
5. Give a clear summary of what you did.
"""

# Configure the agent's content generation settings, including system instructions, available tools, and HTTP options
run_config = types.GenerateContentConfig(
    system_instruction=agent_instructions,
    tools=[check_pnr_status, find_alternative_trains, book_confirmed_seat],
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    temperature=0.0,
    http_options=types.HttpOptions(timeout=20000)
)

# Define the user's message requesting PNR status check and alternative booking if waitlisted
user_message = (
    "Hi, can you check my PNR 8421905612? I am travelling from Mumbai to Pune today. "
    "If it is still waitlisted, please book me on an alternative train."
)

# Print the user's message for clarity
print("USER MESSAGE:")
print(user_message)
print("-" * 65)

# Initialize the chat history with the user's message
chat_history = [
    types.Content(role="user", parts=[types.Part.from_text(text=user_message)])
]

# Fallback models so a 503 traffic spike never crashes your live demo
backup_models = ["gemini-3.5-flash", "gemini-3.8-flash"]

# Start the agentic loop to handle the user's request, allowing multiple rounds of interaction if needed
round_number = 1
while True:
    print(f"\n--- Agent Round {round_number} ---")
    response = None

    # Try each backup model in order until one succeeds or all fail
    for model_name in backup_models:
        try:
            response = gemini_client.models.generate_content(
                model=model_name,
                contents=chat_history,
                config=run_config
            )
            break  # Success, exit fallback loop
        except Exception as err:
            print(f"[Notice] {model_name} busy ({err}). Switching to backup model...")

    # If all models are busy, inform the user and break the loop
    if response is None:
        print("All Gemini endpoints are temporarily busy. Try again in 10 seconds.")
        break

    # Append the assistant's reply to the chat history and print it for clarity
    assistant_reply = response.candidates[0].content
    chat_history.append(assistant_reply)

    # Print the assistant's reply to the console
    if not response.function_calls:
        print("-" * 65)
        print("AGENT FINAL ANSWER:")
        print(response.text)
        break

    # If the assistant made function calls, process each call and execute the corresponding tool
    tool_outputs = []
    for call in response.function_calls:
        function_name = call.name
        function_args = dict(call.args)

        selected_tool = available_tools[function_name]
        result_data = selected_tool(**function_args)

        tool_outputs.append(
            types.Part.from_function_response(
                name=function_name,
                response={"result": result_data}
            )
        )

    chat_history.append(types.Content(role="user", parts=tool_outputs))
    round_number += 1

# ==============================================================================
# STEP 4: PRINT DATABASE TO PROVE THE BOOKING WAS SAVED
# ==============================================================================

# Print the updated passenger bookings in the SQLite database to verify that the booking was successfully saved
print("\n" + "=" * 65)
print("UPDATED PASSENGER BOOKINGS IN SQLITE DATABASE:")
conn = sqlite3.connect(database_filename)
for row in conn.execute("SELECT * FROM passenger_bookings"):
    print(row)
conn.close()