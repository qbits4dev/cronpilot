import os
import sqlite3
import psycopg2
from psycopg2 import sql

def migrate_sqlite_to_postgres(sqlite_db, postgres_config):
    """
    Migrate data from SQLite to PostgreSQL.

    :param sqlite_db: Path to the SQLite database file.
    :param postgres_config: Dictionary containing PostgreSQL connection parameters.
    """
    try:
        # Connect to SQLite database
        sqlite_conn = sqlite3.connect(sqlite_db)
        sqlite_cursor = sqlite_conn.cursor()

        # Connect to PostgreSQL database
        postgres_conn = psycopg2.connect(**postgres_config)
        postgres_cursor = postgres_conn.cursor()

        # Create table in PostgreSQL if it doesn't exist
        create_table_query = """
        CREATE TABLE IF NOT EXISTS whatsapp_users (
            phone TEXT PRIMARY KEY,
            is_on_whatsapp BOOLEAN
        )
        """
        postgres_cursor.execute(create_table_query)
        postgres_conn.commit()

        # Fetch data from SQLite
        sqlite_cursor.execute("SELECT phone, is_on_whatsapp FROM whatsapp_users")
        rows = sqlite_cursor.fetchall()

        # Insert data into PostgreSQL with type casting for boolean values
        insert_query = sql.SQL(
            """
            INSERT INTO whatsapp_users (phone, is_on_whatsapp)
            VALUES (%s, %s)
            ON CONFLICT (phone) DO UPDATE SET is_on_whatsapp = EXCLUDED.is_on_whatsapp
            """
        )
        for row in rows:
            # Cast integer to boolean (1 -> True, 0 -> False)
            phone, is_on_whatsapp = row
            is_on_whatsapp = bool(is_on_whatsapp)
            postgres_cursor.execute(insert_query, (phone, is_on_whatsapp))

        # Commit changes to PostgreSQL
        postgres_conn.commit()
        print("Data migration completed successfully.")

    except (sqlite3.Error, psycopg2.Error) as e:
        print(f"An error occurred: {e}")

    finally:
        # Close connections
        if sqlite_conn:
            sqlite_conn.close()
        if postgres_conn:
            postgres_conn.close()

if __name__ == "__main__":
    # SQLite database file
    sqlite_db = "whatsapp_users.db"

    # PostgreSQL connection parameters from environment variables
    postgres_config = {
        "host": os.getenv("DATABASE_HOST","10.10.10.124"),
        "port": os.getenv("DATABASE_PORT","5432"),
        "dbname": os.getenv("DATABASE_NAME","gowatest"),
        "user": os.getenv("DATABASE_USER","gowatest"),
        "password": os.getenv("DATABASE_PASSWORD","G0waT3stP@ssw0rd!"),
    }

    # Perform the migration
    migrate_sqlite_to_postgres(sqlite_db, postgres_config)
