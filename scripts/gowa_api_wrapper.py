try:
    import requests
except Exception:  # pragma: no cover - environment may not have requests installed
    requests = None
import json

class GowaAPIWrapper:
    """
    A Python wrapper for the Gowa API based on the provided OpenAPI specification.
    """

    def __init__(self, base_url, api_key, device_id):
        """
        Initialize the GowaAPIWrapper.

        Parameters:
            base_url (str): The base URL of the Gowa API.
            api_key (str): The API key for authentication.
        """
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Device-Id": f"{device_id}"
        }

    def check_user(self, phone):
        """
        Check if a user is on WhatsApp.

        Parameters:
            phone (str): The phone number to check.

        Returns:
            dict: The response from the API.
        """
        endpoint = f"{self.base_url}/user/check"
        params = {"phone": phone}
        if requests is None:
            return {"error": "requests library not available; install requirements.txt"}
        try:
            response = requests.get(endpoint, headers=self.headers, params=params)
            response.raise_for_status()
            result = response.json()

            return result
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}

    def send_message(self, phone, message):
        """
        Send a message to a WhatsApp user.

        Parameters:
            phone (str): The recipient's phone number.
            message (str): The message to send.

        Returns:
            dict: The response from the API.
        """
        endpoint = f"{self.base_url}/send/message"
        payload = {"phone": phone, "message": message}
        if requests is None:
            return {"error": "requests library not available; install requirements.txt"}
        try:
            response = requests.post(endpoint, headers=self.headers, json=payload)
            response.raise_for_status()
            result = response.json()

            return result
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}

    def app_login(self):
        """Login to WhatsApp server."""
        url = f"{self.base_url}/app/login"
        if requests is None:
            return {"error": "requests library not available; install requirements.txt"}
        response = requests.get(url, headers=self.headers)
        return response.json()

    def app_logout(self):
        """Logout from WhatsApp server."""
        url = f"{self.base_url}/app/logout"
        if requests is None:
            return {"error": "requests library not available; install requirements.txt"}
        response = requests.get(url, headers=self.headers)
        return response.json()

    def app_status(self):
        """Get connection status."""
        url = f"{self.base_url}/app/status"
        if requests is None:
            return {"error": "requests library not available; install requirements.txt"}
        response = requests.get(url, headers=self.headers)
        return response.json()

    def app_reconnect(self):
        """Reconnect to WhatsApp server."""
        url = f"{self.base_url}/app/reconnect"
        if requests is None:
            return {"error": "requests library not available; install requirements.txt"}
        response = requests.get(url, headers=self.headers)
        return response.json()

    def app_devices(self):
        """Get list of connected devices."""
        url = f"{self.base_url}/app/devices"
        if requests is None:
            return {"error": "requests library not available; install requirements.txt"}
        try:
            self.headers['limit'] = '100'
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            result = response.json()

            return result
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
