import os
from typing import List
import requests

from dotenv import load_dotenv

# Define the exchanges and security types for which to load IBKR listings
EXCHANGES = ["NYSE"]
SECURITY_TYPES = ["STK"]


# Load environment variables from .env file
load_dotenv()

# Load IBKR credentials and Quantrocket deployment from environment variables
ibkr_username = os.getenv("IBKR_USERNAME")
ibkr_password = os.getenv("IBKR_PASSWORD")
houston_username = os.getenv("HOUSTON_USERNAME")
houston_password = os.getenv("HOUSTON_PASSWORD")
url = os.getenv("HOUSTON_URL")

auth = (houston_username, houston_password) if houston_username and houston_password else None

def set_ibkr_credentials():
    # Set IBKR credentials for QuantRocket using HTTP request
    if auth is None:
        raise ValueError("Houston credentials are required to set IBKR credentials via HTTP request. " \
        "Please set HOUSTON_USERNAME and HOUSTON_PASSWORD in your environment variables.")
    
    response = requests.put(
        f"{url}/ibg1/credentials",
        params={
            "username": ibkr_username,
            "password": ibkr_password,
            "trading_mode": "paper"
        },
        auth=auth
    )
    response.raise_for_status()  # Raise an exception for HTTP errors


def ibkr_credentials_are_set():
    """Check if IBKR credentials are already set in QuantRocket by making an HTTP request."""
    try:
        response = requests.get(f"{url}/ibg1/credentials", auth=auth)
        response.raise_for_status()
        credentials = response.json()
        
        if credentials.get("TWSUSERID", None):
            return True
        else:
            return False
    except requests.exceptions.RequestException as e:
        print(f"Could not determine if IBKR credentials are set: {e}")
        return False

def start_ib_gateway():
    """Start IB Gateway by making an HTTP request to the QuantRocket API."""
    try:
        response = requests.post(f"{url}/ibgrouter/gateways?wait=True", auth=auth)
        response.raise_for_status()
        print("IB Gateway activation initiated successfully.")
    except requests.exceptions.RequestException as e:
        print(f"Failed to activate IB Gateway: {e}")

def ib_gateway_is_running():
    """Check if IB Gateway is running by making an HTTP request to the QuantRocket API."""
    try:
        response = requests.get(f"{url}/ibgrouter/gateways", auth=auth)
        response.raise_for_status()
        return response.json().get("ibg1", {}).get("status") == "running"
    except requests.exceptions.RequestException as e:
        print(f"Could not determine IB Gateway status: {e}")
        return False

def load_listings(exchange: str, security_type: str):
    """Load IBKR listings for the specified exchanges by making an HTTP request to the QuantRocket API."""
    try:
        response = requests.post(
            f"{url}/master/securities/ibkr?exchanges={exchange}&sec_types={security_type}",
            auth=auth
        )
        response.raise_for_status()
        print(f"IBKR listings for {exchange} loaded successfully.")
    except requests.exceptions.RequestException as e:
        print(f"Failed to load IBKR listings for {exchange}: {e}")
    

if __name__ == "__main__":
    if ibkr_credentials_are_set():
        print("IBKR credentials are already set. Skipping credential setup.")
    else:
        print("IBKR credentials are not set. Setting credentials...")
        set_ibkr_credentials()

    if ib_gateway_is_running():
        print("IB Gateway is already running. No action needed.")
    else:
        print("IB Gateway is not running. Attempting to start it...")
        start_ib_gateway()
    
    for exchange in EXCHANGES:
        for security_type in SECURITY_TYPES:
            load_listings(exchange, security_type)
