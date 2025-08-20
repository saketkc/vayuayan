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
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .constants import (DATE_FORMATS, DEFAULT_BACKOFF_FACTOR, DEFAULT_HEADERS,
                        DEFAULT_MAX_RETRIES, DEFAULT_TIMEOUT, MONTH_ABBREV)
from .exceptions import NetworkError


def clean_station_name(station_name: str) -> str:
    """
    Convert station name to clean underscore-separated format suitable for filenames/URLs

    Rules applied:
    1. Remove/replace special characters and punctuation
    2. Replace spaces with underscores
    3. Remove multiple consecutive underscores
    4. Remove leading/trailing underscores
    5. Handle common patterns like "City - Organization"

    Args:
        station_name: Original station name string

    Returns:
        Cleaned station name with underscores

    Examples:
        >>> clean_station_name("Dr. Karni Singh Shooting Range, Delhi - DPCC")
        'Dr_Karni_Singh_Shooting_Range_Delhi_DPCC'

        >>> clean_station_name("ITO, Delhi - DPCC")
        'ITO_Delhi_DPCC'

        >>> clean_station_name("Punjabi Bagh, Delhi - DPCC")
        'Punjabi_Bagh_Delhi_DPCC'
    """
    if not station_name or not isinstance(station_name, str):
        return ""

    # Start with the original string
    cleaned = station_name.strip()

    # Remove common patterns and replace with space
    # Handle "City - Organization" pattern
    cleaned = re.sub(r"\s*-\s*", " ", cleaned)  # "Delhi - DPCC" -> "Delhi DPCC"

    # Remove commas and replace with space
    cleaned = re.sub(r",\s*", " ", cleaned)  # "Range, Delhi" -> "Range Delhi"

    # Remove dots but keep the text
    cleaned = re.sub(r"\.", "", cleaned)  # "Dr." -> "Dr"

    # Remove other punctuation and special characters, replace with space
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)  # Remove all non-word, non-space chars

    # Replace multiple whitespace with single space
    cleaned = re.sub(r"\s+", " ", cleaned)

    # Replace spaces with underscores
    cleaned = cleaned.replace(" ", "_")

    # Remove multiple consecutive underscores
    cleaned = re.sub(r"_+", "_", cleaned)

    # Remove leading and trailing underscores
    cleaned = cleaned.strip("_")

    return cleaned


def sort_station_data(data: List[Dict]) -> List[Dict]:
    """
    Sort the list of city dictionaries by live status and city name

    For each city, stations are sorted by:
    1. Live status (live stations first: True before False)
    2. City name (alphabetically)

    Args:
        data: List of cities with nested stations from CPCB API

    Returns:
        Sorted list with the same structure but ordered by live status and city name

    Example:
        >>> data = [{'cityName': 'Zebra', 'stationsInCity': [...]}, ...]
        >>> sorted_data = sort_station_data(data)
        >>> # Cities with live stations will appear first, then alphabetically
    """

    def get_live_status_priority(city_dict):
        """Calculate priority for sorting: live stations get higher priority"""
        stations = city_dict.get("stationsInCity", [])

        # Count live stations
        live_count = sum(1 for station in stations if station.get("live", False))
        total_count = len(stations)

        # Calculate live percentage (0-100)
        live_percentage = (live_count / total_count * 100) if total_count > 0 else 0

        # Return tuple for sorting: (live_percentage desc, city_name asc)
        # Use negative live_percentage to sort descending
        return (-live_percentage, city_dict.get("cityName", "").lower())

    # Sort the cities
    sorted_data = sorted(data, key=get_live_status_priority)

    # Also sort stations within each city by live status
    for city in sorted_data:
        if "stationsInCity" in city:
            city["stationsInCity"] = sorted(
                city["stationsInCity"],
                key=lambda station: (
                    not station.get("live", False),
                    station.get("name", ""),
                ),
                # not live -> False comes before True, so live stations (True) come first
            )

    return sorted_data


def stations_to_dataframe(data: List[Dict]) -> pd.DataFrame:
    """
    Convert nested station data to a flat DataFrame with one row per station

    Args:
        data: List of cities with nested stations from CPCB API

    Returns:
        DataFrame with columns: city_name, city_id, state_id, station_id,
                               station_name, longitude, latitude, live, avg

    Example:
        >>> data = [{'cityName': 'Munger', 'cityID': 'Munger', ...}]
        >>> df = stations_to_dataframe(data)
        >>> print(df.head())
    """
    rows = []

    for city in data:
        city_name = city["cityName"]
        city_id = city["cityID"]
        state_id = city["stateID"]

        for station in city["stationsInCity"]:
            # Handle missing or empty avg values
            avg_value = station.get("avg", "")
            if avg_value == "" or avg_value is None:
                avg_value = np.nan
            else:
                try:
                    avg_value = float(avg_value)
                except (ValueError, TypeError):
                    avg_value = np.nan

            # Convert coordinates to float
            try:
                longitude = float(station["longitude"])
            except (ValueError, TypeError):
                longitude = np.nan

            try:
                latitude = float(station["latitude"])
            except (ValueError, TypeError):
                latitude = np.nan

            rows.append(
                {
                    "city_name": city_name,
                    "city_id": city_id,
                    "state_id": state_id,
                    "station_id": station["id"],
                    "station_name": station["name"],
                    "longitude": longitude,
                    "latitude": latitude,
                    "live": station["live"],
                    "avg_aqi": avg_value,
                }
            )

    return pd.DataFrame(rows)


def stations_to_city_summary(data: List[Dict]) -> pd.DataFrame:
    """
    Convert station data to city-level summary DataFrame

    Args:
        data: List of cities with nested stations

    Returns:
        DataFrame with city-level aggregated statistics
    """
    rows = []

    for city in data:
        stations = city["stationsInCity"]

        total_stations = len(stations)
        live_stations = sum(1 for station in stations if station["live"])
        offline_stations = total_stations - live_stations

        # Calculate average AQI for live stations
        live_aqi_values = []
        for station in stations:
            if station["live"] and station.get("avg") not in ["", None]:
                try:
                    live_aqi_values.append(float(station["avg"]))
                except (ValueError, TypeError):
                    continue

        avg_aqi = np.mean(live_aqi_values) if live_aqi_values else np.nan
        min_aqi = np.min(live_aqi_values) if live_aqi_values else np.nan
        max_aqi = np.max(live_aqi_values) if live_aqi_values else np.nan

        rows.append(
            {
                "city_name": city["cityName"],
                "city_id": city["cityID"],
                "state_id": city["stateID"],
                "total_stations": total_stations,
                "live_stations": live_stations,
                "offline_stations": offline_stations,
                "live_percentage": (
                    (live_stations / total_stations * 100) if total_stations > 0 else 0
                ),
                "avg_aqi": avg_aqi,
                "min_aqi": min_aqi,
                "max_aqi": max_aqi,
                "stations_with_data": len(live_aqi_values),
            }
        )

    return pd.DataFrame(rows)


def stations_to_coordinates_dataframe(data: List[Dict]) -> pd.DataFrame:
    """
    Convert station data to a DataFrame optimized for mapping/coordinates analysis

    Args:
        data: List of cities with nested stations

    Returns:
        DataFrame with geographic information and essential station details
    """
    rows = []

    for city in data:
        for station in city["stationsInCity"]:
            try:
                longitude = float(station["longitude"])
                latitude = float(station["latitude"])

                # Handle AQI value
                avg_value = station.get("avg", "")
                if avg_value not in ["", None]:
                    try:
                        avg_value = float(avg_value)
                    except (ValueError, TypeError):
                        avg_value = np.nan
                else:
                    avg_value = np.nan

                rows.append(
                    {
                        "station_id": station["id"],
                        "station_name": station["name"],
                        "city_name": city["cityName"],
                        "state_id": city["stateID"],
                        "longitude": longitude,
                        "latitude": latitude,
                        "live": station["live"],
                        "avg_aqi": avg_value,
                        # Add a status category for easy filtering/coloring
                        "status": "Live" if station["live"] else "Offline",
                        # Add AQI category if available
                        "aqi_category": (
                            get_aqi_category(avg_value)
                            if not pd.isna(avg_value)
                            else "No Data"
                        ),
                    }
                )
            except (ValueError, TypeError):
                # Skip stations with invalid coordinates
                continue

    return pd.DataFrame(rows)


def get_aqi_category(aqi_value: float) -> str:
    """
    Convert AQI numeric value to category

    Args:
        aqi_value: Numeric AQI value

    Returns:
        AQI category string
    """
    if pd.isna(aqi_value):
        return "No Data"
    elif aqi_value <= 50:
        return "Good"
    elif aqi_value <= 100:
        return "Satisfactory"
    elif aqi_value <= 200:
        return "Moderate"
    elif aqi_value <= 300:
        return "Poor"
    elif aqi_value <= 400:
        return "Very Poor"
    else:
        return "Severe"


def stations_to_pivot_table(data: List[Dict]) -> pd.DataFrame:
    """
    Create a pivot table with cities as rows and station status as columns

    Args:
        data: List of cities with nested stations

    Returns:
        Pivot table DataFrame
    """
    # First get flat DataFrame
    flat_df = stations_to_dataframe(data)

    # Create pivot table
    pivot_df = flat_df.pivot_table(
        index=["state_id", "city_name"],
        columns="live",
        values="station_id",
        aggfunc="count",
        fill_value=0,
    )

    # Rename columns for clarity
    pivot_df.columns = ["Offline", "Live"]

    # Add total column
    pivot_df["Total"] = pivot_df.sum(axis=1)

    # Calculate percentage
    pivot_df["Live_Percentage"] = (pivot_df["Live"] / pivot_df["Total"] * 100).round(1)

    return pivot_df


def convert_station_data_to_dataframe(
    data: List[Dict], method: str = "stations"
) -> pd.DataFrame:
    """
    Main conversion function with multiple output formats

    Args:
        data: List of cities with nested stations from CPCB API
        method: Conversion method ('stations', 'city_summary', 'coordinates', 'pivot')

    Returns:
        Converted DataFrame based on specified method

    Available methods:
        - 'stations': Flat DataFrame with one row per station (default)
        - 'city_summary': City-level summary with aggregated statistics
        - 'coordinates': Optimized for mapping with geographic data
        - 'pivot': Pivot table with station counts by status
    """

    methods = {
        "stations": stations_to_dataframe,
        "city_summary": stations_to_city_summary,
        "coordinates": stations_to_coordinates_dataframe,
        "pivot": stations_to_pivot_table,
    }

    if method not in methods:
        raise ValueError(f"Method must be one of: {list(methods.keys())}")

    return methods[method](data)


def analyze_station_data(data: List[Dict]) -> Dict[str, Any]:
    """
    Comprehensive analysis of station data

    Args:
        data: List of cities with nested stations

    Returns:
        Dictionary with analysis results
    """
    df = stations_to_dataframe(data)

    analysis = {
        "total_cities": len(data),
        "total_stations": len(df),
        "live_stations": len(df[df["live"] == True]),
        "offline_stations": len(df[df["live"] == False]),
        "states": df["state_id"].nunique(),
        "unique_states": list(df["state_id"].unique()),
        "stations_with_aqi_data": len(df[~pd.isna(df["avg_aqi"])]),
        "avg_aqi_overall": df["avg_aqi"].mean(),
        "min_aqi": df["avg_aqi"].min(),
        "max_aqi": df["avg_aqi"].max(),
        "stations_per_city": df.groupby("city_name").size().describe().to_dict(),
        "aqi_distribution": (
            df["avg_aqi"].describe().to_dict() if not df["avg_aqi"].empty else {}
        ),
    }

    # Add AQI category distribution
    df_with_categories = df.copy()
    df_with_categories["aqi_category"] = df_with_categories["avg_aqi"].apply(
        get_aqi_category
    )
    category_counts = df_with_categories["aqi_category"].value_counts().to_dict()
    analysis["aqi_categories"] = category_counts

    return analysis


# Example usage and demonstration
def demonstrate_station_conversion(data: List[Dict]):
    """
    Demonstrate all conversion methods with station data
    """

    print("=" * 70)
    print("STATION DATA ANALYSIS")
    print("=" * 70)

    # Overall analysis
    analysis = analyze_station_data(data)
    print(f"Total Cities: {analysis['total_cities']}")
    print(f"Total Stations: {analysis['total_stations']}")
    print(f"Live Stations: {analysis['live_stations']}")
    print(f"Offline Stations: {analysis['offline_stations']}")
    print(f"States: {analysis['unique_states']}")
    print(
        f"Average AQI: {analysis['avg_aqi_overall']:.1f}"
        if not pd.isna(analysis["avg_aqi_overall"])
        else "Average AQI: No data"
    )

    print("\n" + "=" * 70)
    print("METHOD 1: FLAT STATIONS DATAFRAME")
    print("=" * 70)
    df1 = convert_station_data_to_dataframe(data, method="stations")
    print(f"Shape: {df1.shape}")
    print("\nColumns:", list(df1.columns))
    print("\nFirst few rows:")
    print(df1.head())

    print("\n" + "=" * 70)
    print("METHOD 2: CITY SUMMARY")
    print("=" * 70)
    df2 = convert_station_data_to_dataframe(data, method="city_summary")
    print(f"Shape: {df2.shape}")
    print("\nSummary:")
    print(df2)

    print("\n" + "=" * 70)
    print("METHOD 3: COORDINATES FOR MAPPING")
    print("=" * 70)
    df3 = convert_station_data_to_dataframe(data, method="coordinates")
    print(f"Shape: {df3.shape}")
    print("\nFirst few rows:")
    print(df3.head())

    print("\n" + "=" * 70)
    print("METHOD 4: PIVOT TABLE")
    print("=" * 70)
    df4 = convert_station_data_to_dataframe(data, method="pivot")
    print(f"Shape: {df4.shape}")
    print("\nPivot table:")
    print(df4)

    return {
        "stations": df1,
        "city_summary": df2,
        "coordinates": df3,
        "pivot": df4,
        "analysis": analysis,
    }


def station_to_dataframe(data: List[Dict]) -> pd.DataFrame:
    """
    Convert nested JSON to a flat DataFrame with one row per city

    Args:
        data: List of states with nested cities

    Returns:
        DataFrame with columns: state_name, state_id, city_name, city_id, live
    """
    rows = []

    for state in data:
        state_name = state["stateName"]
        state_id = state["stateID"]

        for city in state["citiesInState"]:
            rows.append(
                {
                    "state_name": state_name,
                    "state_id": state_id,
                    "city_name": city["name"],
                    "city_id": city["id"],
                    "live": city["live"],
                }
            )

    return pd.DataFrame(rows)


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
