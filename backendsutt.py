
import csv
import os
from typing import Dict, List, Optional, Set


# ----------------------------
# Custom Exceptions
# ----------------------------
class RoomNotFoundError(Exception):
    """Raised when the requested room_no does not exist in the system."""
    pass


class TimeslotAlreadyBookedError(Exception):
    """Raised when attempting to book a room for an hour that's already booked."""
    pass


class RoomAlreadyExistsError(Exception):
    """Raised when attempting to create a room with a room_no that already exists."""
    pass


# ----------------------------
# Room Data Class
# ----------------------------
class Room:
    """
    Represents a room.

    Attributes:
        room_no: unique identifier for the room (string).
        building: building/name of location (string).
        capacity: integer capacity.
        booked_hours: set of ints in 0..23 representing booked hours.
    """

    def __init__(self, room_no: str, building: str, capacity: int, booked_hours: Optional[Set[int]] = None):
        self.room_no = room_no
        self.building = building
        self.capacity = int(capacity)
        self.booked_hours: Set[int] = set(booked_hours or [])

    def is_free_at(self, hour: int) -> bool:
        """Return True if the room is free at the given hour."""
        return hour not in self.booked_hours

    def book_hour(self, hour: int):
        """Book the room for the specified hour, raising TimeslotAlreadyBookedError if occupied."""
        if hour in self.booked_hours:
            raise TimeslotAlreadyBookedError(f"Room {self.room_no} is already booked at hour {hour}.")
        self.booked_hours.add(hour)

    def booked_hours_str(self) -> str:
        """Return a semicolon-separated string of booked hours (sorted) for CSV storage."""
        if not self.booked_hours:
            return ""
        return ";".join(str(h) for h in sorted(self.booked_hours))

    def __str__(self) -> str:
        booked = ", ".join(str(h) for h in sorted(self.booked_hours)) or "No bookings"
        return (f"Room: {self.room_no} | Building: {self.building} | Capacity: {self.capacity} | "
                f"Booked hours: {booked}")


# ----------------------------
# Room Manager
# ----------------------------
class RoomManager:
    """
    Manages the collection of rooms and handles persistence.
    """

    CSV_FILENAME = "bookings_final_state.csv"
    CSV_HEADERS = ["room_no", "building", "capacity", "booked_hours"]

    def __init__(self):
        # rooms keyed by room_no
        self.rooms: Dict[str, Room] = {}
        self.load_from_csv()

    # Persistence
    def load_from_csv(self):
        """Load rooms and bookings from CSV file if it exists."""
        if not os.path.exists(self.CSV_FILENAME):
            # No file yet; start with an empty manager
            return
        try:
            with open(self.CSV_FILENAME, newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                # If headers don't match, ignore file (defensive)
                if reader.fieldnames is None or any(h not in reader.fieldnames for h in self.CSV_HEADERS):
                    print(f"Warning: CSV file found but headers don't match expected {self.CSV_HEADERS}. Skipping load.")
                    return
                for row in reader:
                    room_no = (row.get("room_no") or "").strip()
                    building = (row.get("building") or "").strip()
                    capacity_str = (row.get("capacity") or "0").strip()
                    booked_str = (row.get("booked_hours") or "").strip()
                    if not room_no:
                        continue  # skip invalid rows
                    try:
                        capacity = int(capacity_str)
                    except ValueError:
                        capacity = 0
                    booked_hours = set()
                    if booked_str:
                        for piece in booked_str.split(";"):
                            piece = piece.strip()
                            if piece == "":
                                continue
                            try:
                                h = int(piece)
                                if 0 <= h <= 23:
                                    booked_hours.add(h)
                            except ValueError:
                                continue
                    room = Room(room_no=room_no, building=building, capacity=capacity, booked_hours=booked_hours)
                    self.rooms[room_no] = room
        except Exception as e:
            print(f"Error loading CSV file '{self.CSV_FILENAME}': {e}")

    def save_to_csv(self):
        """Save current rooms to CSV (overwrites file)."""
        try:
            with open(self.CSV_FILENAME, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.CSV_HEADERS)
                writer.writeheader()
                for r in self.rooms.values():
                    writer.writerow({
                        "room_no": r.room_no,
                        "building": r.building,
                        "capacity": str(r.capacity),
                        "booked_hours": r.booked_hours_str()
                    })
        except Exception as e:
            print(f"Error saving to CSV file '{self.CSV_FILENAME}': {e}")

    # CRUD-like operations
    def add_room(self, room_no: str, building: str, capacity: int):
        """Add a new room. Raises RoomAlreadyExistsError if room_no already exists."""
        room_no = room_no.strip()
        if room_no in self.rooms:
            raise RoomAlreadyExistsError(f"Room with room_no '{room_no}' already exists.")
        room = Room(room_no=room_no, building=building.strip(), capacity=int(capacity))
        self.rooms[room_no] = room
        return room

    def get_room(self, room_no: str) -> Room:
        """Return a Room by room_no or raise RoomNotFoundError."""
        room_no = room_no.strip()
        if room_no not in self.rooms:
            raise RoomNotFoundError(f"Room '{room_no}' not found.")
        return self.rooms[room_no]

    def book_room(self, room_no: str, hour: int):
        """Book a room for a single hour. Raises RoomNotFoundError or TimeslotAlreadyBookedError."""
        r = self.get_room(room_no)
        r.book_hour(hour)
        return r

    def find_rooms(self,
                   building: Optional[str] = None,
                   min_capacity: Optional[int] = None,
                   free_at_hour: Optional[int] = None) -> List[Room]:
        """
        Return list of rooms matching ALL provided criteria (criteria are ANDed).
        Passing None for a criterion skips it.
        """
        results = []
        for r in self.rooms.values():
            if building is not None and r.building.lower() != building.lower():
                continue
            if min_capacity is not None and r.capacity < min_capacity:
                continue
            if free_at_hour is not None and not r.is_free_at(free_at_hour):
                continue
            results.append(r)
        return results

    def list_rooms(self) -> List[Room]:
        """Return all rooms sorted by room_no."""
        return sorted(self.rooms.values(), key=lambda rr: rr.room_no)


# ----------------------------
# CLI Helpers
# ----------------------------
def ask_non_empty(prompt: str) -> str:
    """Prompt until a non-empty response is given."""
    while True:
        s = input(prompt).strip()
        if s:
            return s
        print("Input cannot be empty. Please try again.")


def ask_int(prompt: str, min_value: Optional[int] = None, max_value: Optional[int] = None) -> int:
    """Prompt until a valid integer (and within optional bounds) is given."""
    while True:
        s = input(prompt).strip()
        try:
            v = int(s)
            if (min_value is not None and v < min_value) or (max_value is not None and v > max_value):
                rng = []
                if min_value is not None:
                    rng.append(f">= {min_value}")
                if max_value is not None:
                    rng.append(f"<= {max_value}")
                rng_text = " and ".join(rng)
                print(f"Please enter an integer {rng_text}.")
                continue
            return v
        except ValueError:
            print("Please enter a valid integer.")


def print_separator():
    print("-" * 60)


def show_room_list(rooms: List[Room]):
    if not rooms:
        print("(no rooms found)")
        return
    for r in rooms:
        print(r)


# ----------------------------
# Main Menu
# ----------------------------
def main_loop():
    manager = RoomManager()
    print("Welcome to the Room Booking CLI!")
    print(f"Loaded {len(manager.rooms)} room(s) from '{RoomManager.CSV_FILENAME}'.")
    print("Type the number for the desired action and press Enter.")
    while True:
        print_separator()
        print("Menu:")
        print("1) Create a new room")
        print("2) Book a room for a single hour")
        print("3) Find/filter rooms")
        print("4) View bookings for a room")
        print("5) List all rooms")
        print("6) Exit (save state and quit)")
        choice = input("Choose an option (1-6): ").strip()
        if choice == "1":
            # Create room
            try:
                room_no = ask_non_empty("Enter room_no (unique id, e.g., NAB101): ")
                building = ask_non_empty("Enter building/name (e.g., NAB): ")
                capacity = ask_int("Enter capacity (integer): ", min_value=0)
                manager.add_room(room_no=room_no, building=building, capacity=capacity)
                print(f"Room '{room_no}' created successfully.")
            except RoomAlreadyExistsError as e:
                print(f"[Error] {e}")
            except Exception as e:
                print(f"[Unexpected Error] {e}")

        elif choice == "2":
            # Book a room
            try:
                room_no = ask_non_empty("Enter room_no to book: ")
                hour = ask_int("Enter hour to book (0-23): ", min_value=0, max_value=23)
                manager.book_room(room_no=room_no, hour=hour)
                print(f"Successfully booked room '{room_no}' at hour {hour}.")
            except RoomNotFoundError as e:
                print(f"[Error] {e}")
            except TimeslotAlreadyBookedError as e:
                print(f"[Error] {e}")
            except Exception as e:
                print(f"[Unexpected Error] {e}")

        elif choice == "3":
            # Find/filter rooms
            print("Enter search criteria. Leave blank to skip a criterion.")
            bld = input("Building (exact match): ").strip()
            bld = bld if bld else None
            cap_input = input("Minimum capacity (integer): ").strip()
            min_cap = None
            if cap_input:
                try:
                    min_cap = int(cap_input)
                    if min_cap < 0:
                        print("Minimum capacity must be non-negative. Ignoring this criterion.")
                        min_cap = None
                except ValueError:
                    print("Invalid integer for capacity. Ignoring this criterion.")
                    min_cap = None
            hour_input = input("Free at hour (0-23): ").strip()
            free_at = None
            if hour_input:
                try:
                    h = int(hour_input)
                    if 0 <= h <= 23:
                        free_at = h
                    else:
                        print("Hour must be between 0 and 23. Ignoring this criterion.")
                except ValueError:
                    print("Invalid hour. Ignoring this criterion.")
            matches = manager.find_rooms(building=bld, min_capacity=min_cap, free_at_hour=free_at)
            print_separator()
            print(f"Found {len(matches)} room(s) matching criteria:")
            show_room_list(matches)

        elif choice == "4":
            # View bookings
            try:
                room_no = ask_non_empty("Enter room_no to view bookings: ")
                room = manager.get_room(room_no)
                print_separator()
                print(str(room))
            except RoomNotFoundError as e:
                print(f"[Error] {e}")
            except Exception as e:
                print(f"[Unexpected Error] {e}")

        elif choice == "5":
            # List all rooms
            rooms = manager.list_rooms()
            print_separator()
            print(f"All rooms ({len(rooms)}):")
            show_room_list(rooms)

        elif choice == "6":
            # Exit: save and quit
            print("Saving state to CSV and exiting...")
            manager.save_to_csv()
            print(f"Saved {len(manager.rooms)} room(s) to '{RoomManager.CSV_FILENAME}'. Goodbye!")
            break

        else:
            print("Invalid choice. Please enter a number between 1 and 6.")


if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        # catch Ctrl+C to save before exit
        print("\nKeyboardInterrupt detected. Saving state before exiting...")
        try:
            RoomManager().save_to_csv()
            print(f"Saved to {RoomManager.CSV_FILENAME}. Goodbye!")
        except Exception:
            print("Error saving state. Exiting without saving.")

