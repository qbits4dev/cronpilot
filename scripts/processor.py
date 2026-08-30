import os
import time
import random
import logging
import json
import pandas as pd
import psycopg2
import psycopg2.extras


def run_processor(gowa_api, config):
    # Read consolidated mobile numbers
    try:
        consolidated_numbers_df = pd.read_csv(
            "consolidated_mobile_numbers.csv",
            header=0,
            names=["name", "mobile"],
            dtype={"mobile": str},
        )
        list_of_numbers = consolidated_numbers_df["mobile"].tolist()
    except FileNotFoundError:
        logging.warning("consolidated_mobile_numbers.csv not found. Proceeding with an empty list.")
        list_of_numbers = []

    # Connect to Postgres
    pg_conn = None
    try:
        pg_conn = psycopg2.connect(
            host=config.POSTGRES_CONFIG['host'],
            port=config.POSTGRES_CONFIG['port'],
            dbname=config.POSTGRES_CONFIG['dbname'],
            user=config.POSTGRES_CONFIG['user'],
            password=config.POSTGRES_CONFIG['password'],
        )
    except Exception as e:
        logging.error(f"Error: could not connect to Postgres: {e}")
        raise SystemExit(1)

    pg_cursor = pg_conn.cursor()
    pg_cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS whatsapp_users (
            phone TEXT PRIMARY KEY,
            is_on_whatsapp BOOLEAN,
            response JSONB
        )
        """
    )
    pg_conn.commit()

    try:
        pg_cursor.execute("ALTER TABLE whatsapp_users ADD COLUMN IF NOT EXISTS response JSONB")
        pg_conn.commit()
    except Exception:
        pass

    def process_phone_number(phone):
        pg_cursor.execute(
            "SELECT is_on_whatsapp FROM whatsapp_users WHERE phone = %s",
            (phone,)
        )
        result = pg_cursor.fetchone()

        if result is not None:
            logging.info(f"Phone {phone} already in database. Skipping API call.")
            return False

        user_check_response = gowa_api.check_user(phone)
        if isinstance(user_check_response, str):
            try:
                user_check_response = json.loads(user_check_response)
            except Exception:
                user_check_response = {"error": str(user_check_response), "results": {}}

        if not isinstance(user_check_response, dict):
            user_check_response = {"error": str(user_check_response), "results": {}}

        results = user_check_response.get('results', {}) if isinstance(user_check_response, dict) else {}
        if isinstance(results, dict) and 'is_on_whatsapp' in results:
            is_on_whatsapp = results['is_on_whatsapp']
        else:
            is_on_whatsapp = False

        try:
            pg_cursor.execute(
                """
                INSERT INTO whatsapp_users (phone, is_on_whatsapp, response)
                VALUES (%s, %s, %s)
                ON CONFLICT (phone) DO UPDATE SET is_on_whatsapp = EXCLUDED.is_on_whatsapp, response = EXCLUDED.response
                """,
                (phone, bool(is_on_whatsapp), psycopg2.extras.Json(user_check_response)),
            )
            pg_conn.commit()
        except Exception as e:
            logging.warning(f"Warning: failed to upsert to Postgres for {phone}: {e}")
            return False

        return True

    # Processing loop with rate limiting
    processed_count = 0
    start_time = time.time()

    for phone in list_of_numbers:
        pg_cursor.execute("SELECT is_on_whatsapp FROM whatsapp_users WHERE phone = %s", (phone,))
        exists = pg_cursor.fetchone() is not None

        if exists:
            logging.info(f"Phone {phone} already in DB. Skipping API and rate limit.")
            continue

        if processed_count >= config.NUM_ENTRIES_PER_HOUR:
            elapsed_time = time.time() - start_time
            remaining_time = 3600 - elapsed_time

            if remaining_time > 0:
                logging.info(f"Processed {config.NUM_ENTRIES_PER_HOUR} numbers. Waiting for {remaining_time / 60:.2f} minutes.")
                time.sleep(remaining_time)

            processed_count = 0
            start_time = time.time()

        made_api_call = process_phone_number(phone)

        if made_api_call:
            processed_count += 1
            elapsed_time = time.time() - start_time
            remaining_time = 3600 - elapsed_time
            max_delay = remaining_time / (config.NUM_ENTRIES_PER_HOUR - processed_count) if processed_count < config.NUM_ENTRIES_PER_HOUR else 0

            delay = random.uniform(0, max_delay) if max_delay > 0 else 0
            logging.info(f"Processed {phone}. Waiting for {delay:.2f} seconds before next.")
            time.sleep(delay)

    # Close connections
    try:
        if pg_cursor:
            pg_cursor.close()
        if pg_conn:
            pg_conn.close()
    except Exception:
        pass

    logging.info('Processing complete')
