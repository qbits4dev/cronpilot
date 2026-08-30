import os, json
from textwrap import indent
import pandas as pd
from scripts.gowa_api_wrapper import GowaAPIWrapper

# Example usage
if __name__ == "__main__":
    # Replace with your Gowa API base URL and load API key securely
    base_url = "https://gowarest.qbits4dev.com"
    api_key = os.getenv("GOWA_API_KEY", "your_api_key_here")

    # gowa_api = GowaAPIWrapper(base_url, api_key, device_id="e2735273-16b7-4fd7-8597-ae70d8c38e77")
    # # print(gowa_api.get_user_info("917386007683"))
    # print(gowa_api.send_message("917330722336", "Hello from Gowa API Wrapper!"))

    gowa_api = GowaAPIWrapper(
        base_url, api_key, device_id="e1735273-16b7-4fd7-8597-ae70d8c38e77"
    )
    # print(gowa_api.get_user_info("917386007683"))

    # Fetch chats and create a DataFrame
    chats_response = gowa_api.get_chats()

    if "error" in chats_response:
        print("Error fetching chats:", chats_response["error"])
    else:
        # Assuming the response contains a list of chats under a key like 'chats'
        # print("Fetched chats:", json.dumps(chats_response, indent=4))
        df = pd.json_normalize(chats_response['results']['data'])
        # Filter the DataFrame to keep only rows where 'jid' starts with '91' and ends with 'whatsapp.net'
        if 'jid' in df.columns:
            df = df[df['jid'].str.startswith('91') & df['jid'].str.endswith('whatsapp.net')]
        print(df)
