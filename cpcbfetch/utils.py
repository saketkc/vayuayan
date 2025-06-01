"""
Utility functions for CPCB fetching
"""

import json
import math
import re
import ssl
import time
from base64 import b64decode
from datetime import datetime
from typing import Any, Dict, Optional, Union

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .constants import (
    DATE_FORMATS,
    DEFAULT_BACKOFF_FACTOR,
    DEFAULT_HEADERS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    MONTH_ABBREV,
)
from .exceptions import NetworkError


class NetworkError(Exception):
    """Custom exception for network-related errors"""

    pass


class DataProcessingError(Exception):
    """Custom exception for data processing errors"""

    pass


# Disable SSL warnings if needed (optional)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def make_robust_request(
    url: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    timeout: int = DEFAULT_TIMEOUT,
    verify_ssl: bool = True,
) -> Optional[requests.Response]:
    """
    Make HTTP request with retry logic and SSL error handling

    Args:
        url: URL to fetch
        max_retries: Maximum number of retry attempts
        backoff_factor: Backoff factor for exponential retry delay
        timeout: Request timeout in seconds
        verify_ssl: Whether to verify SSL certificates

    Returns:
        Response object if successful, None if all retries failed

    Raises:
        NetworkError: If all retries failed
    """

    for attempt in range(max_retries + 1):
        try:
            response = requests.get(
                url, headers=DEFAULT_HEADERS, timeout=timeout, verify=verify_ssl
            )
            response.raise_for_status()
            return response

        except requests.exceptions.SSLError as e:
            print(f"SSL Error on attempt {attempt + 1}/{max_retries + 1}: {e}")

            if attempt < max_retries:
                try:
                    print("Retrying with SSL verification disabled...")
                    response = requests.get(
                        url, headers=DEFAULT_HEADERS, timeout=timeout, verify=False
                    )
                    response.raise_for_status()
                    print("✅ Request succeeded with SSL verification disabled")
                    return response
                except Exception as fallback_error:
                    print(f"❌ Fallback also failed: {fallback_error}")

        except requests.exceptions.ConnectionError as e:
            print(f"Connection Error on attempt {attempt + 1}/{max_retries + 1}: {e}")

        except requests.exceptions.Timeout as e:
            print(f"Timeout Error on attempt {attempt + 1}/{max_retries + 1}: {e}")

        except requests.exceptions.RequestException as e:
            print(f"Request Error on attempt {attempt + 1}/{max_retries + 1}: {e}")

        except Exception as e:
            print(f"Unexpected Error on attempt {attempt + 1}/{max_retries + 1}: {e}")

        # Wait before retrying (exponential backoff)
        if attempt < max_retries:
            wait_time = backoff_factor * (2**attempt)
            print(f"⏳ Waiting {wait_time:.1f} seconds before retry...")
            time.sleep(wait_time)

    print(f"❌ All {max_retries + 1} attempts failed")
    raise NetworkError(
        f"Failed to fetch data from {url} after {max_retries + 1} attempts"
    )


def make_request_with_session(
    url: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    timeout: int = DEFAULT_TIMEOUT,
) -> Optional[requests.Response]:
    """
    Alternative approach using requests Session with built-in retry strategy

    Args:
        url: URL to fetch
        max_retries: Maximum number of retry attempts
        backoff_factor: Backoff factor for retry delay
        timeout: Request timeout in seconds

    Returns:
        Response object if successful, None if failed
    """

    session = requests.Session()

    retry_strategy = Retry(
        total=max_retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    try:
        response = session.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        response.raise_for_status()
        return response

    except requests.exceptions.SSLError as e:
        print(f"SSL Error with session: {e}")
        try:
            print("Retrying with SSL verification disabled...")
            response = session.get(
                url, headers=DEFAULT_HEADERS, timeout=timeout, verify=False
            )
            response.raise_for_status()
            return response
        except Exception as fallback_error:
            print(f"Session fallback failed: {fallback_error}")
            return None

    except Exception as e:
        print(f"Session request failed: {e}")
        return None

    finally:
        session.close()


def safe_get(
    url: str, max_retries: int = DEFAULT_MAX_RETRIES, timeout: int = DEFAULT_TIMEOUT
) -> requests.Response:
    """
    Simple drop-in replacement for requests.get() with retry logic

    Args:
        url: URL to fetch
        max_retries: Maximum retry attempts
        timeout: Request timeout

    Returns:
        requests.Response object

    Raises:
        NetworkError: If request fails after all retries
    """
    return make_robust_request(url, max_retries=max_retries, timeout=timeout)


def parse_date(date_text: str) -> Optional[str]:
    """
    Parse various date formats

    Args:
        date_text: Raw date text

    Returns:
        Standardized date in YYYY-MM-DD format, or None if parsing fails
    """
    if not date_text:
        return None

    # Clean the date text
    date_text = re.sub(r"[^\w\s\/\-,:]", "", date_text.strip())

    for fmt in DATE_FORMATS:
        try:
            parsed_date = datetime.strptime(date_text, fmt)
            return parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None


def clean_city_name(city_text: str) -> Optional[str]:
    """
    Clean and standardize city name

    Args:
        city_text: Raw city text

    Returns:
        Cleaned city name
    """
    if not city_text:
        return None

    # Remove extra whitespace
    city = re.sub(r"\s+", " ", city_text.strip())
    # Remove parantheses
    # city = re.sub(r"\(", "-", city)
    # city = re.sub(r"\)", "", city)
    city = re.sub(r"\s*\([^)]*\)", "", city)  # Remove space and parentheses content
    # OR if you want to keep the content:
    city = re.sub(
        r"\s*\(([^)]*)\)", r"-\1", city
    )  # Replace " (content)" with "-content"
    # Remove common prefixes/suffixes that aren't part of city name
    city = re.sub(r"^(For|Weather|Report|Forecast):\s*", "", city, flags=re.IGNORECASE)
    city = re.sub(
        r"\s*(Weather|Report|Forecast)$",
        "",
        city,
        flags=re.IGNORECASE,
    )

    # Remove any remaining HTML artifacts
    city = re.sub(r"[<>]", "", city)

    # Capitalize properly
    city = city.title()

    # Handle special cases
    city = city.replace("-", "-")  # Normalize hyphens
    city = city.replace(" -", "-")
    city = city.replace("- ", "-")
    return city.strip()


def convert_date_to_iso(date_str: str) -> Optional[str]:
    """
    Convert dates like "27-May", "2-Jun" to YYYY-MM-DD format using current year

    Args:
        date_str: Date string in format "DD-MMM" (e.g., "27-May", "2-Jun")

    Returns:
        Date in YYYY-MM-DD format, or None if parsing fails
    """
    if not date_str:
        return None

    current_year = datetime.now().year

    try:
        # Split by dash and clean
        parts = date_str.strip().replace("-", " ").replace("  ", " ").split(" ")
        if len(parts) != 2:
            return None

        day, month_abbr = parts

        # Convert day to 2-digit format
        day = day.zfill(2)

        # Convert month abbreviation to number
        month_key = month_abbr.lower()[:3]
        if month_key not in MONTH_ABBREV:
            return None

        month = MONTH_ABBREV[month_key]

        # Return in YYYY-MM-DD format
        return f"{current_year}-{month}-{day}"

    except Exception:
        return None


def format_date(date_str: str, include_day: bool = True) -> str:
    """
    Format date string to a more readable format with day of week.

    Args:
        date_str: Date string in various formats (e.g., "2027-05-25", "25-05-2027", "25/05/2027")
        include_day: Whether to include the day of week

    Returns:
        Formatted date string like "25 May, 2027 (Tuesday)"
    """

    # Try different date formats
    date_formats = [
        "%Y-%m-%d",  # ISO format: 2027-05-25
        "%d-%m-%Y",  # DD-MM-YYYY: 25-05-2027
        "%d/%m/%Y",  # DD/MM/YYYY: 25/05/2027
        "%d %b %Y",  # DD Mon YYYY: 25 May 2027
        "%d %B %Y",  # DD Month YYYY: 25 May 2027
    ]

    for fmt in date_formats:
        try:
            date_obj = datetime.strptime(date_str.strip(), fmt)
            # Format the date
            formatted = date_obj.strftime("%d %B, %Y")
            if include_day:
                day_name = date_obj.strftime("%A")
                formatted += f" ({day_name})"
            return formatted
        except ValueError:
            continue

    # If no format matches, return the original string
    return date_str


def safe_post(
    url: str,
    headers: Dict[str, str],
    data: Union[Dict[str, Any], str, bytes],
    cookies: Optional[Dict[str, str]] = None,
    max_retries: int = 3,
    backoff_factor: float = 0.3,
    timeout: int = 30,
    verify_ssl: bool = True,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Make robust POST request with retry logic, decode base64 response, and parse JSON

    Args:
        url: URL to send POST request to
        headers: Request headers
        data: Request data (dict, string, or bytes)
        cookies: Optional cookies dict
        max_retries: Maximum number of retry attempts
        backoff_factor: Backoff factor for exponential retry delay
        timeout: Request timeout in seconds
        verify_ssl: Whether to verify SSL certificates
        verbose: Whether to print status messages

    Returns:
        Parsed JSON response as dictionary

    Raises:
        NetworkError: If all retries failed or network issues
        DataProcessingError: If base64 decoding or JSON parsing fails
        ValueError: If input parameters are invalid
    """

    def log(message: str):
        """Print message only if verbose mode is enabled"""
        if verbose:
            print(message)

    # Input validation
    if not url or not isinstance(url, str):
        raise ValueError("URL must be a non-empty string")

    if not headers or not isinstance(headers, dict):
        raise ValueError("Headers must be a non-empty dictionary")

    # Ensure cookies is a dict or None
    if cookies is None:
        cookies = {}
    elif not isinstance(cookies, dict):
        raise ValueError("Cookies must be a dictionary or None")

    for attempt in range(max_retries + 1):
        try:
            log(
                f"🌐 Attempt {attempt + 1}/{max_retries + 1}: Making POST request to {url}"
            )

            # Make the POST request
            response = requests.post(
                url=url,
                headers=headers,
                data=data,
                cookies=cookies,
                timeout=timeout,
                verify=verify_ssl,
            )

            # Raise an exception for bad status codes
            response.raise_for_status()

            log(f"✅ Request successful (Status: {response.status_code})")

            # Process the response
            try:
                # Decode base64 content
                if not response.content:
                    raise DataProcessingError("Response content is empty")

                log("🔓 Decoding base64 content...")
                decoded_data = b64decode(response.content)

                # Parse JSON
                log("📄 Parsing JSON data...")
                json_data = json.loads(decoded_data)

                log("✅ Data processing successful")
                return json_data

            except Exception as decode_error:
                log(f"❌ Base64 decode error: {decode_error}")
                raise DataProcessingError(
                    f"Failed to decode base64 or parse JSON: {decode_error}"
                )

        except requests.exceptions.SSLError as e:
            log(f"🔒 SSL Error on attempt {attempt + 1}/{max_retries + 1}: {e}")

            if attempt < max_retries:
                try:
                    log("🔓 Retrying with SSL verification disabled...")
                    response = requests.post(
                        url=url,
                        headers=headers,
                        data=data,
                        cookies=cookies,
                        timeout=timeout,
                        verify=False,
                    )
                    response.raise_for_status()

                    # Process response (same as above)
                    try:
                        decoded_data = b64decode(response.content)
                        json_data = json.loads(decoded_data)
                        log("✅ Request succeeded with SSL verification disabled")
                        return json_data
                    except Exception as decode_error:
                        raise DataProcessingError(
                            f"Failed to decode base64 or parse JSON: {decode_error}"
                        )

                except Exception as fallback_error:
                    log(f"❌ SSL fallback also failed: {fallback_error}")

        except requests.exceptions.ConnectionError as e:
            log(f"🔌 Connection Error on attempt {attempt + 1}/{max_retries + 1}: {e}")

        except requests.exceptions.Timeout as e:
            log(f"⏰ Timeout Error on attempt {attempt + 1}/{max_retries + 1}: {e}")

        except requests.exceptions.HTTPError as e:
            log(f"🚫 HTTP Error on attempt {attempt + 1}/{max_retries + 1}: {e}")
            # For client errors (4xx), don't retry
            if (
                hasattr(e.response, "status_code")
                and 400 <= e.response.status_code < 500
            ):
                log(f"❌ Client error ({e.response.status_code}), not retrying")
                raise NetworkError(f"HTTP {e.response.status_code} error: {e}")

        except requests.exceptions.RequestException as e:
            log(f"📡 Request Error on attempt {attempt + 1}/{max_retries + 1}: {e}")

        except DataProcessingError:
            # Don't retry data processing errors
            raise

        except Exception as e:
            log(f"❓ Unexpected Error on attempt {attempt + 1}/{max_retries + 1}: {e}")

        # Wait before retrying (exponential backoff)
        if attempt < max_retries:
            wait_time = backoff_factor * (2**attempt)
            log(f"⏳ Waiting {wait_time:.1f} seconds before retry...")
            time.sleep(wait_time)

    log(f"❌ All {max_retries + 1} attempts failed")
    raise NetworkError(
        f"Failed to fetch data from {url} after {max_retries + 1} attempts"
    )


def safe_post_with_session(
    url: str,
    headers: Dict[str, str],
    data: Union[Dict[str, Any], str, bytes],
    cookies: Optional[Dict[str, str]] = None,
    max_retries: int = 3,
    backoff_factor: float = 0.3,
    timeout: int = 30,
    verbose: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Alternative approach using requests Session with built-in retry strategy

    Args:
        url: URL to send POST request to
        headers: Request headers
        data: Request data
        cookies: Optional cookies dict
        max_retries: Maximum number of retry attempts
        backoff_factor: Backoff factor for retry delay
        timeout: Request timeout in seconds
        verbose: Whether to print status messages

    Returns:
        Parsed JSON response as dictionary, or None if failed
    """

    def log(message: str):
        """Print message only if verbose mode is enabled"""
        if verbose:
            print(message)

    session = requests.Session()

    # Configure retry strategy
    retry_strategy = Retry(
        total=max_retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"],  # Allow retries for POST requests
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    try:
        log(f"🌐 Making POST request with session to {url}")

        response = session.post(
            url=url, headers=headers, data=data, cookies=cookies or {}, timeout=timeout
        )
        response.raise_for_status()

        # Process the response
        try:
            decoded_data = b64decode(response.content)
            json_data = json.loads(decoded_data)
            log("✅ Session request successful")
            return json_data
        except Exception as decode_error:
            log(f"❌ Data processing failed: {decode_error}")
            raise DataProcessingError(
                f"Failed to decode base64 or parse JSON: {decode_error}"
            )

    except requests.exceptions.SSLError as e:
        log(f"🔒 SSL Error with session: {e}")
        try:
            log("🔓 Retrying with SSL verification disabled...")
            response = session.post(
                url=url,
                headers=headers,
                data=data,
                cookies=cookies or {},
                timeout=timeout,
                verify=False,
            )
            response.raise_for_status()

            decoded_data = b64decode(response.content)
            json_data = json.loads(decoded_data)
            return json_data
        except Exception as fallback_error:
            log(f"❌ Session SSL fallback failed: {fallback_error}")
            return None

    except Exception as e:
        log(f"❌ Session request failed: {e}")
        return None

    finally:
        session.close()


def url_encode(data_dict):
    raw_body = json.dumps(data_dict)
    data = b64encode(raw_body.encode()).decode("utf-8")
    return data


def time_to_isodate(timestamp):
    datetime_object = datetime.utcfromtimestamp(timestamp / 1000)
    return datetime_object.strftime("%Y-%m-%dT%H:%M:%SZ")


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on Earth using Haversine formula
    More accurate than Euclidean distance for geographical coordinates

    Args:
        lat1, lon1: Latitude and longitude of first point
        lat2, lon2: Latitude and longitude of second point

    Returns:
        Distance in kilometers
    """
    # Convert to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))

    # Earth's radius in kilometers
    r = 6371

    return c * r


def euclidean_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate simple Euclidean distance (faster but less accurate for long distances)

    Args:
        lat1, lon1: Latitude and longitude of first point
        lat2, lon2: Latitude and longitude of second point

    Returns:
        Euclidean distance (arbitrary units)
    """
    return math.sqrt((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2)
