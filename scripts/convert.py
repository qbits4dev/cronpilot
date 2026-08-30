import os
import sqlite3

def export_sqlite_to_dump(db_file, dump_file):
    """
    Export the SQLite database to a .sql dump file.

    :param db_file: Path to the SQLite database file.
    :param dump_file: Path to the output dump file.
    """
    try:
        # Connect to the SQLite database
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # Open the dump file in write mode
        with open(dump_file, 'w') as f:
            for line in conn.iterdump():
                f.write(f"{line}\n")

        print(f"Database dump successful. Dump file created: {dump_file}")

    except sqlite3.Error as e:
        print(f"An error occurred: {e}")

    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # Define the database file and dump file paths
    db_file = "whatsapp_users.db"  # Replace with your database file name
    dump_file = "sqlite_dump.sql"  # Replace with your desired dump file name

    # Perform the database dump
    export_sqlite_to_dump(db_file, dump_file)
