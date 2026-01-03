"""
Air Quality Client module for interacting with CPCB AQI services.

This module provides client classes for fetching air quality data from India's
Central Pollution Control Board (CPCB) including AQI data, live monitoring data,
and PM2.5 satellite data.
"""

import base64
import json
import os
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, cast
from urllib.parse import urljoin

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
import rioxarray  # noqa: F401
import urllib3
import xarray as xr
from geopy.distance import geodesic
from tqdm import tqdm

try:
    import ee

    GEE_AVAILABLE = True
except ImportError:
    GEE_AVAILABLE = False

try:
    import boto3
    from botocore import UNSIGNED
    from botocore.config import Config

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

# Disable SSL warnings for CPCB endpoints with certificate issues
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _request_with_ssl_fallback(
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Union[str, bytes]] = None,
    cookies: Optional[Dict[str, str]] = None,
    timeout: int = 30,
    stream: bool = False,
    **kwargs: Any,
) -> requests.Response:
    """Make HTTP request with SSL fallback on certificate errors.

    First attempts with SSL verification enabled. If that fails with an SSL error,
    retries with SSL verification disabled.

    Args:
        method: HTTP method ('get' or 'post').
        url: Request URL.
        headers: Optional request headers.
        data: Optional request data.
        cookies: Optional request cookies.
        timeout: Request timeout in seconds.
        stream: Whether to stream the response.
        **kwargs: Additional arguments to pass to requests.

    Returns:
        Response object.

    Raises:
        requests.RequestException: If request fails after SSL fallback attempt.
    """
    request_kwargs = {
        "timeout": timeout,
        "stream": stream,
        **kwargs,
    }
    if headers:
        request_kwargs["headers"] = headers
    if data is not None:
        request_kwargs["data"] = data
    if cookies:
        request_kwargs["cookies"] = cookies

    try:
        request_kwargs["verify"] = True
        if method.lower() == "get":
            response = requests.get(url, **request_kwargs)
        else:
            response = requests.post(url, **request_kwargs)
        response.raise_for_status()
        return response
    except requests.exceptions.SSLError as e:
        print(f"SSL verification failed: {e}")
        print("Retrying with SSL verification disabled...")
        try:
            request_kwargs["verify"] = False
            if method.lower() == "get":
                response = requests.get(url, **request_kwargs)
            else:
                response = requests.post(url, **request_kwargs)
            response.raise_for_status()
            return response
        except Exception as fallback_error:
            raise requests.RequestException(
                f"Request failed even with SSL verification disabled: {fallback_error}"
            ) from fallback_error


class CPCBHistorical:
    """Client for fetching historical Air Quality Index (AQI) data from CPCB."""

    def __init__(self) -> None:
        """Initialize the AQI Client with CPCB endpoints and headers."""
        self.base_url = "https://airquality.cpcb.gov.in"
        self.base_path = f"{self.base_url}/dataRepository/download_file?file_name="
        self.data_repository = "/dataRepository/"
        self.dropdown_endpoint = f"{self.data_repository}all_india_stationlist"
        self.file_path_endpoint = f"{self.data_repository}file_Path"

        self.headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "q=0.8;application/json;q=0.9",
        }

    def _encode_base64(self, data: bytes) -> str:
        """Encode bytes to base64 string.

        Args:
            data: Bytes to encode.

        Returns:
            Base64 encoded string.
        """
        return base64.b64encode(data).decode("utf-8")

    def _decode_base64(self, data: str) -> str:
        """Decode base64 string to UTF-8 string.

        Args:
            data: Base64 encoded string.

        Returns:
            Decoded UTF-8 string.
        """
        return base64.b64decode(data.encode("utf-8")).decode("utf-8")

    def get_complete_list(self) -> Dict[str, Any]:
        """Fetch the complete list of all India stations and cities.

        Returns:
            Dictionary containing station and city data.

        Raises:
            requests.RequestException: If the HTTP request fails.
            json.JSONDecodeError: If response cannot be parsed as JSON.
        """
        form_body = self._encode_base64(b"{}")
        response = _request_with_ssl_fallback(
            method="post",
            url=f"{self.base_url}{self.dropdown_endpoint}",
            data=form_body,
            timeout=30,
        )

        decoded_response = self._decode_base64(response.text)
        parsed_response = cast(Dict[str, Any], json.loads(decoded_response))

        if parsed_response.get("status") == "success":
            dropdown = parsed_response.get("dropdown", {})
            if isinstance(dropdown, dict):
                return dropdown
        return {}

    def get_state_list(self) -> List[str]:
        """Get list of states available for AQI data.

        Returns:
            Sorted list of state names.
        """
        try:
            complete_list = self.get_complete_list()
            return list(sorted(complete_list.get("cities", {})))
        except KeyError as e:
            print(f"KeyError in get_state_list: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error in get_state_list: {e}")
            return []

    def get_city_list(self, state: str) -> List[str]:
        """Get list of cities available in given state for AQI data.

        Args:
            state: State name to get cities for.

        Returns:
            Sorted list of city names in the state.
        """
        try:
            complete_list = self.get_complete_list()
            cities = complete_list.get("cities", {})
            if cities and state in cities:
                return list(sorted([city["value"] for city in cities[state]]))
            return []
        except Exception:
            return []

    def get_station_list(self, city: str) -> List[Dict]:
        """Get station list available in given city for AQI data.

        Args:
            city: City name to get stations for.

        Returns:
            Sorted list of station dictionaries.
        """
        try:
            complete_list = self.get_complete_list()
            stations = complete_list.get("stations", {})
            if stations and city in stations:
                return list(sorted(stations[city], key=lambda x: x.get("label", "")))
            return []
        except Exception:
            return []

    def get_file_path(
        self,
        station_id: str,
        station_name: str,
        state: str,
        city: str,
        year: str,
        frequency: str,
        data_type: str,
    ) -> List[Dict[str, Any]]:
        """Get file path containing data for given query parameters.

        Args:
            station_id: Station ID.
            station_name: Station name.
            state: State name.
            city: City name.
            year: Year for data.
            frequency: Data frequency ('hourly' or 'daily').
            data_type: Type of data ('cityLevel' or 'stationLevel').

        Returns:
            Dictionary containing file path data.

        Raises:
            requests.RequestException: If the HTTP request fails.
        """
        payload = {
            "station_id": station_id,
            "station_name": station_name,
            "state": state,
            "city": city,
            "year": year,
            "frequency": frequency,
            "dataType": data_type,
        }

        payload_str = json.dumps(payload)
        encoded_payload = self._encode_base64(payload_str.encode("utf-8"))

        response = _request_with_ssl_fallback(
            method="post",
            url=f"{self.base_url}{self.file_path_endpoint}",
            data=encoded_payload,
            headers=self.headers,
            timeout=30,
        )

        decoded_response = self._decode_base64(response.text)
        parsed_response = cast(Dict[str, Any], json.loads(decoded_response))

        if parsed_response.get("status") == "success":
            data = parsed_response.get("data", [])
            if isinstance(data, list):
                return [
                    cast(Dict[str, Any], entry)
                    for entry in data
                    if isinstance(entry, dict)
                ]
        return []

    def download_past_year_aqi_data_city_level(
        self, city: str, year: str, save_location: str
    ) -> pd.DataFrame:
        """Download past AQI data for a specific city.

        Args:
            city: City name.
            year: Year for data.
            save_location: Path to save the downloaded data.

        Returns:
            DataFrame preview of the downloaded data.

        Raises:
            Exception: If data is not found or download fails.
        """
        data_file_paths = self.get_file_path("", "", "", city, "", "daily", "cityLevel")

        for entry in data_file_paths:
            if entry.get("year") == str(year):
                file_url = f"{self.base_path}{entry['filepath']}"
                df = pd.read_excel(file_url)
                df = df.iloc[:31]  # Limit to first 31 rows (max days in month)
                if save_location:
                    df.to_csv(save_location, index=False)
                return df

        raise Exception(f"Data not found for city {city} in year {year}")

    def download_past_year_aqi_data_station_level(
        self, station_id: str, year: str, save_location: str
    ) -> pd.DataFrame:
        """Download past AQI data for a specific station.

        Args:
            station_id: Station ID.
            year: Year for data.
            save_location: Path to save the downloaded data.

        Returns:
            DataFrame preview of the downloaded data.

        Raises:
            Exception: If station or data is not found.
        """
        complete_list = self.get_complete_list()
        station_list = complete_list.get("stations", [])

        station_name = None
        for city_stations in station_list.values():
            for station in city_stations:
                if station.get("value") == station_id:
                    station_name = station.get("label")
                    break
            if station_name:
                break

        if not station_name:
            raise Exception(f"Station ID {station_id} not found")

        data_file_paths = self.get_file_path(
            station_id, station_name, "", "", "", "daily", "stationLevel"
        )

        for entry in data_file_paths:
            if entry.get("year") == year:
                file_url = f"{self.base_path}{entry['filepath']}"
                df = pd.read_excel(file_url)
                df = df.iloc[:31]  # Limit to first 31 rows (max days in month)
                df.to_csv(save_location, index=False)
                return df.head()

        raise Exception(f"Data not found for station {station_id} in year {year}")


class CPCBLive:
    """Client for fetching live air quality data from CPCB."""

    def __init__(self) -> None:
        """Initialize the Live AQI Client."""
        self.base_url = "https://airquality.cpcb.gov.in"
        self.coordinate_url = "http://ip-api.com/json"
        self.dashboard_path = "/aqi_dashboard/"
        self.station_url = f"{self.base_url}{self.dashboard_path}aqi_station_all_india"
        self.parameters_url = f"{self.base_url}{self.dashboard_path}aqi_all_Parameters"

        self.headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "q=0.8;application/json;q=0.9",
        }
        self.cookies = {"ccr_public": "A"}

    def _make_request(
        self,
        url: str,
        headers: Dict[str, str],
        data: str,
        cookies: Dict[str, str],
    ) -> Dict[str, Any]:
        """Make a POST request and return base64 decoded JSON response.

        Args:
            url: Request URL.
            headers: Request headers.
            data: Request data.
            cookies: Request cookies.

        Returns:
            Parsed JSON response.

        Raises:
            requests.RequestException: If request fails.
            json.JSONDecodeError: If response cannot be decoded.
        """
        response = _request_with_ssl_fallback(
            method="post",
            url=url,
            headers=headers,
            data=data,
            cookies=cookies,
            timeout=30,
        )

        decoded_data = base64.b64decode(response.content)
        return cast(Dict[str, Any], json.loads(decoded_data))

    def _clean_pollution_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and format pollution data.

        Args:
            data: Raw pollution data dictionary.

        Returns:
            Cleaned pollution data dictionary.
        """
        cleaned_data = data.copy()

        if "chartData" not in data:
            return cleaned_data

        cleaned_chart_data = []
        for i, series in enumerate(data["chartData"]):
            if not series or not isinstance(series, list) or len(series) < 2:
                continue

            rows = series[1:]  # Skip header
            live_data = []

            for row in rows:
                if len(row) < 2 or row[0] is None or row[1] is None:
                    continue
                live_data.append({"date": row[0], "val": row[1]})

            if i < len(cleaned_data.get("metrics", [])):
                series_name = cleaned_data["metrics"][i].get("name", f"Series {i}")
                cleaned_chart_data.append({"name": series_name, "data": live_data})

        cleaned_data["last_hours"] = cleaned_chart_data
        cleaned_data.pop("chartData", None)
        return cleaned_data

    def get_system_location(self) -> Tuple[float, float]:
        """Retrieve system's geolocation using IP-based lookup.

        Returns:
            Tuple of (latitude, longitude).

        Raises:
            Exception: If geolocation lookup fails.
        """
        try:
            response = _request_with_ssl_fallback(
                method="get", url=self.coordinate_url, timeout=30
            )
            data = response.json()

            if data.get("status") == "success":
                return (data.get("lat"), data.get("lon"))
            else:
                raise Exception(f"Geolocation lookup failed: {data.get('message')}")
        except Exception as e:
            raise Exception(f"Error retrieving system location: {e}") from e

    def get_nearest_station(
        self, coords: Optional[Tuple[float, float]] = None
    ) -> Tuple[str, str]:
        """Get the nearest air quality monitoring station.

        Args:
            coords: Optional tuple of (latitude, longitude). If None, uses IP
                geolocation.

        Returns:
            Tuple of (station_id, station_name).

        Raises:
            Exception: If no stations found or coordinates invalid.
        """
        try:
            cities = self.get_all_india()
            if not coords:
                coords = self.get_system_location()

            user_location = (float(coords[0]), float(coords[1]))
            min_distance = float("inf")
            nearest_station = None

            for city_data in cities:
                for station in city_data.get("stationsInCity", []):
                    try:
                        station_location = (
                            float(station["latitude"]),
                            float(station["longitude"]),
                        )
                        distance = geodesic(user_location, station_location).kilometers

                        if distance < min_distance:
                            min_distance = distance
                            nearest_station = (station.get("id"), station.get("name"))
                    except (TypeError, ValueError):
                        continue

            if nearest_station:
                return nearest_station
            raise Exception("No stations found or invalid station data.")
        except Exception as e:
            raise Exception(f"Error finding nearest station: {e}") from e

    def get_all_india(self) -> List[Dict[str, Any]]:
        """Get all air quality monitoring stations in India.

        Returns:
            List of station dictionaries.
        """
        body = "e30="
        try:
            response = self._make_request(
                self.station_url, self.headers, body, self.cookies
            )
            stations = response.get("stations", [])
            if isinstance(stations, list):
                return [
                    cast(Dict[str, Any], station)
                    for station in stations
                    if isinstance(station, dict)
                ]
        except Exception:
            response = self._make_request(
                self.station_url, self.headers, body, self.cookies
            )
            stations = response.get("stations", [])
            if isinstance(stations, list):
                return [
                    cast(Dict[str, Any], station)
                    for station in stations
                    if isinstance(station, dict)
                ]
        return []

    def get_live_aqi_data_for_station(
        self, station_id: str, date_time: str
    ) -> Dict[str, Any]:
        """Get live air quality data for a specific station.

        Args:
            station_id: Station ID.
            date_time: Date and time in 'YYYY-MM-DDTHH:00:00Z' format.

        Returns:
            Live air quality data dictionary.

        Raises:
            ValueError: If parameters are invalid.
            Exception: If request fails.
        """
        if not station_id or not date_time:
            raise ValueError("Both station_id and date_time must be provided.")

        raw_body = json.dumps({"station_id": station_id, "date": date_time})
        encoded_data = base64.b64encode(raw_body.encode()).decode("utf-8")

        return self._make_request(
            self.parameters_url, self.headers, encoded_data, self.cookies
        )

    def get_live_aqi_data(
        self,
        station_id: Optional[str] = None,
        coords: Optional[Tuple[float, float]] = None,
        date: Optional[str] = None,
        hour: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get live AQI data with flexible parameter options.

        Args:
            station_id: Optional station ID. If not provided, uses nearest station.
            coords: Optional (latitude, longitude) tuple.
            date: Optional date in 'YYYY-MM-DD' format. Defaults to today.
            hour: Optional hour (0-23). Defaults to current hour.

        Returns:
            Processed live AQI data dictionary.

        Raises:
            ValueError: If hour is invalid.
            Exception: If data retrieval fails.
        """
        if not station_id:
            if coords:
                station_id = self.get_nearest_station(coords)[0]
            else:
                system_coords = self.get_system_location()
                station_id = self.get_nearest_station(system_coords)[0]

        now = datetime.now()
        if not date:
            date = now.strftime("%Y-%m-%d")

        if hour is not None:
            if not (0 <= hour <= 23):
                raise ValueError("Hour must be between 0 and 23")
            date_time = f"{date}T{hour:02d}:00:00Z"
        else:
            last_hour = now.replace(minute=0, second=0, microsecond=0)
            date_time = f"{date}T{last_hour.hour:02d}:00:00Z"

        aqi_data = self.get_live_aqi_data_for_station(station_id, date_time)
        return self._clean_pollution_data(aqi_data)


class PM25Client:
    """Client for processing PM2.5 satellite data from NetCDF files.

    Supports both V5.GL.05.02 (GWR-based) and V6.GL.02.04 (CNN-based) datasets
    from the WUSTL Atmospheric Composition Analysis Group (ACAG).
    """

    def __init__(self, version: str = "V6", cache_dir: str = "pm25_data") -> None:
        """Initialize the PM2.5 Client with data paths and AWS configuration.

        Args:
            version: Dataset version to use. Options:
                - "V6" (default): V6.GL.02.04 - CNN-based algorithm (1998-2023)
                  Most advanced, recommended for new studies
                - "V5": V5.GL.05.02 - GWR-based algorithm (1998-2024)
                  Traditional approach, compatible with published studies
            cache_dir: Directory to cache downloaded NetCDF files.

        Raises:
            ValueError: If version is not "V5" or "V6".

        Example:
            >>> # Use V6 (default, recommended)
            >>> client = PM25Client()

            >>> # Use V5
            >>> client = PM25Client(version="V5")
        """
        if version not in ["V5", "V6"]:
            raise ValueError(
                f"Invalid version: {version}. Must be 'V5' or 'V6'. "
                f"V6 (default) is recommended for new studies."
            )

        self.version = version
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Configure data source based on version
        if version == "V6":
            # V6.GL.02.04: CNN-based algorithm (most advanced)
            # Primary: AWS S3 Open Data Registry
            self.aws_base_url = (
                "https://s3.us-west-2.amazonaws.com/v6.gl.02.04/V6.GL.02.04/GL/"
            )
            # GEE Fallback: Google Earth Engine Community Catalog (V6.GL.02, 2000-2022)
            self.gee_collection_monthly = (
                "projects/sat-io/open-datasets/GLOBAL-SATELLITE-PM25/MONTHLY"
            )
            self.gee_collection_annual = (
                "projects/sat-io/open-datasets/GLOBAL-SATELLITE-PM25/ANNUAL"
            )
            self.variable_name = "PM25"  # V6 uses "PM25"
            self.year_range = (1998, 2023)
            self.gee_year_range = (2000, 2022)  # GEE has limited range
        else:  # V5
            # V5.GL.05.02: GWR-based algorithm (traditional, well-validated)
            self.aws_base_url = (
                "https://s3.us-west-2.amazonaws.com/acag-data/V5.GL.05.02/GL/"
            )
            # V5 not available on GEE
            self.gee_collection_monthly = None
            self.gee_collection_annual = None
            self.variable_name = "GWRPM25"  # V5 uses "GWRPM25"
            self.year_range = (1998, 2024)
            self.gee_year_range = None

        # Initialize GEE if available
        self.gee_initialized = False
        if GEE_AVAILABLE and self.gee_collection_monthly:
            try:
                # Try new high-volume endpoint first (recommended for server use)
                try:
                    ee.Initialize(
                        opt_url="https://earthengine-highvolume.googleapis.com"
                    )
                    self.gee_initialized = True
                    print("✓ Google Earth Engine initialized (high-volume endpoint)")
                except Exception:
                    # Fall back to standard endpoint
                    ee.Initialize()
                    self.gee_initialized = True
                    print("✓ Google Earth Engine initialized")
            except Exception as e:
                print(f"ℹ GEE not authenticated: {e}")
                print("  Run 'earthengine authenticate' to enable GEE data source")

        # Local paths (legacy support)
        self.annual_data_path = f"examples/{version}GL01.0p10.PM25.Global"
        self.monthly_data_path = f"examples/{version}GL01.0p10.PM25.Global"

        # Box shared folder URLs for manual downloads
        if version == "V6":
            self.box_shared_folder = "https://wustl.box.com/v/ACAG-V6GL0204-CNNPM25"
        else:  # V5
            self.box_shared_folder = "https://wustl.box.com/v/ACAG-V5GL0502-GWRPM25"

    def _get_aws_filename(self, year: int, month: Optional[int] = None) -> str:
        """Generate AWS filename for given year and optional month.

        Args:
            year: Year for data.
            month: Optional month (1-12). If None, returns annual filename.

        Returns:
            AWS filename for the NetCDF file.

        Raises:
            ValueError: If year is outside valid range for the version.
        """
        if not (self.year_range[0] <= year <= self.year_range[1]):
            raise ValueError(
                f"Year {year} is outside valid range for {self.version}: "
                f"{self.year_range[0]}-{self.year_range[1]}"
            )

        if self.version == "V6":
            # V6 filename pattern: V6GL02.04.CNNPM25.GL.YYYYMM-YYYYMM.nc
            if month is None:
                return f"V6GL02.04.CNNPM25.GL.{year}01-{year}12.nc"
            return f"V6GL02.04.CNNPM25.GL.{year}{month:02d}-{year}{month:02d}.nc"
        else:  # V5
            # V5 filename pattern: V5GL05.02.GWRPM25.GL.YYYYMM-YYYYMM.nc
            if month is None:
                return f"V5GL05.02.GWRPM25.GL.{year}01-{year}12.nc"
            return f"V5GL05.02.GWRPM25.GL.{year}{month:02d}-{year}{month:02d}.nc"

    def _get_aws_url(self, year: int, month: Optional[int] = None) -> str:
        """Generate AWS URL for given year and optional month.

        Args:
            year: Year for data.
            month: Optional month (1-12). If None, returns annual URL.

        Returns:
            Full AWS URL for the NetCDF file.
        """
        filename = self._get_aws_filename(year, month)
        if month is None:
            return urljoin(self.aws_base_url, f"Annual/{filename}")
        return urljoin(self.aws_base_url, f"Monthly/{year}/{filename}")

    def _download_from_s3_boto3(
        self, year: int, month: Optional[int] = None, cached_path: Optional[Path] = None
    ) -> Optional[str]:
        """Download PM2.5 data from AWS S3 using boto3 with anonymous access.

        Args:
            year: Year for data.
            month: Optional month (1-12). If None, downloads annual data.
            cached_path: Path where to save the file.

        Returns:
            Path to downloaded file if successful, None otherwise.
        """
        if not BOTO3_AVAILABLE:
            return None

        if cached_path is None:
            cached_path = Path(self.get_netcdf_path(year, month))

        try:
            s3 = boto3.client(
                "s3", region_name="us-west-2", config=Config(signature_version=UNSIGNED)
            )

            filename = self._get_aws_filename(year, month)
            if month is None:
                s3_key = f"V6.GL.02.04/GL/Annual/{filename}"
            else:
                s3_key = f"V6.GL.02.04/GL/Monthly/{year}/{filename}"

            bucket_name = "v6.gl.02.04"

            print(f"Downloading from S3: s3://{bucket_name}/{s3_key}")

            try:
                head_response = s3.head_object(Bucket=bucket_name, Key=s3_key)
                total_size = head_response["ContentLength"]
            except Exception:
                total_size = 0

            with open(cached_path, "wb") as f:
                with tqdm(
                    total=total_size,
                    unit="B",
                    unit_scale=True,
                    unit_divisor=1024,
                    desc="Downloading (boto3)",
                    ncols=80,
                ) as pbar:
                    s3.download_fileobj(
                        bucket_name,
                        s3_key,
                        f,
                        Callback=lambda bytes_transferred: pbar.update(
                            bytes_transferred
                        ),
                    )

            final_size = cached_path.stat().st_size
            print(f"✓ S3 download complete (boto3): {final_size / (1024*1024):.1f} MB")
            return str(cached_path)

        except Exception as e:
            print(f"⚠ S3 boto3 download failed: {e}")
            if cached_path and cached_path.exists():
                cached_path.unlink()
            return None

    def _download_from_gee(
        self,
        year: int,
        month: Optional[int] = None,
        region: Optional[ee.Geometry] = None,
    ) -> Optional[str]:
        """Download PM2.5 data from Google Earth Engine.

        Note: GEE has a 32768x32768 pixel download limit. For global data,
        you must provide a region to clip to, or use the export-to-Drive API.

        Args:
            year: Year for data.
            month: Optional month (1-12). If None, downloads annual data.
            region: Optional ee.Geometry to clip to. If None and image is too large,
                    will clip to India bounds as fallback.

        Returns:
            Path to downloaded GeoTIFF file, or None if GEE unavailable.

        Raises:
            ValueError: If year is outside GEE data range.
        """
        if not self.gee_initialized:
            return None

        if not (self.gee_year_range[0] <= year <= self.gee_year_range[1]):
            print(
                f"⚠ Year {year} outside GEE range "
                f"({self.gee_year_range[0]}-{self.gee_year_range[1]})"
            )
            return None

        try:
            if month is None:
                collection = ee.ImageCollection(self.gee_collection_annual)
                date_filter = ee.Filter.calendarRange(year, year, "year")
            else:
                collection = ee.ImageCollection(self.gee_collection_monthly)
                date_filter = ee.Filter.And(
                    ee.Filter.calendarRange(year, year, "year"),
                    ee.Filter.calendarRange(month, month, "month"),
                )

            image = collection.filter(date_filter).first()

            if image is None:
                print(f"⚠ No GEE data found for {year}-{month or 'annual'}")
                return None

            # If no region specified, use India bounds as default
            # (covers typical use case and avoids global download size limits)
            if region is None:
                print("ℹ No region specified, clipping to India bounds (default)")
                region = ee.Geometry.Rectangle([68.0, 8.0, 98.0, 37.0])  # India

            image = image.clip(region)

            base_filename = self._get_aws_filename(year, month)
            tif_filename = base_filename.replace(".nc", ".tif")
            output_path = self.cache_dir / tif_filename

            print(f"Requesting download URL from Google Earth Engine...")
            print(f"Region: {region.bounds().getInfo()}")
            url = image.getDownloadURL(
                {
                    "scale": 10000,  # ~0.1 degree at equator (0.1° x 0.1° resolution)
                    "crs": "EPSG:4326",
                    "fileFormat": "GeoTIFF",
                    "region": region,
                }
            )

            # GEE's getDownloadURL() returns a ZIP archive, not a raw GeoTIFF
            zip_path = output_path.with_suffix(".zip")
            print(f"Downloading from GEE...")
            print(f"Destination: {zip_path}")

            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))

            with open(zip_path, "wb") as f:
                with tqdm(
                    total=total_size,
                    unit="B",
                    unit_scale=True,
                    unit_divisor=1024,
                    desc="Downloading",
                    ncols=80,
                ) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))

            final_size = zip_path.stat().st_size
            print(f"✓ GEE download complete: {final_size / (1024*1024):.1f} MB")

            print(f"Extracting GeoTIFF from ZIP archive...")
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_contents = zip_ref.namelist()
                print(f"  ZIP contents: {zip_contents}")

                tif_files = [f for f in zip_contents if f.endswith(".tif")]
                if not tif_files:
                    raise ValueError(
                        f"No .tif file found in GEE download: {zip_contents}"
                    )

                tif_name = tif_files[0]
                zip_ref.extract(tif_name, self.cache_dir)

                extracted_path = self.cache_dir / tif_name
                if extracted_path != output_path:
                    extracted_path.rename(output_path)

            zip_path.unlink()

            print(f"✓ GeoTIFF extracted: {output_path}")
            return str(output_path)

        except Exception as e:
            print(f"✗ GEE download failed: {e}")
            if output_path.exists():
                output_path.unlink()
            return None

    def get_netcdf_path(self, year: int, month: Optional[int] = None) -> str:
        """Get NetCDF file path for given year and optional month.

        Args:
            year: Year for data.
            month: Optional month (1-12). If None, returns annual data path.

        Returns:
            Path to NetCDF file (cached locally).
        """
        filename = self._get_aws_filename(year, month)
        cached_path = self.cache_dir / filename

        # Return cached path regardless of whether file exists
        # (download_netcdf_if_needed will handle downloading)
        return str(cached_path)

    def download_netcdf_if_needed(
        self, year: int, month: Optional[int] = None, force_download: bool = False
    ) -> str:
        """Download NetCDF file from AWS if not cached.

        Args:
            year: Year for data.
            month: Optional month (1-12). If None, downloads annual data.
            force_download: Whether to re-download even if file exists.

        Returns:
            Path to the downloaded NetCDF file.

        Raises:
            requests.RequestException: If download fails.
            IOError: If file cannot be written.
        """
        cached_path = Path(self.get_netcdf_path(year, month))

        if cached_path.exists() and not force_download:
            file_size = cached_path.stat().st_size
            if file_size > 1024 * 1024:  # At least 1MB (reasonable for NetCDF)
                print(f"Using cached file: {cached_path}")
                return str(cached_path)
            else:
                print("Warning: Cached file appears incomplete, re-downloading...")

        cached_path.parent.mkdir(parents=True, exist_ok=True)

        # Try AWS S3 first with boto3 (proper anonymous access)
        print(f"Attempting download from AWS S3...")

        s3_result = self._download_from_s3_boto3(year, month, cached_path)
        if s3_result:
            return s3_result

        aws_url = self._get_aws_url(year, month)
        print(f"Trying S3 download via HTTP (fallback)...")
        print(f"Source: {aws_url}")

        try:
            response = _request_with_ssl_fallback(
                method="get", url=aws_url, stream=True, timeout=300
            )

            total_size = int(response.headers.get("content-length", 0))

            chunk_size = 8192
            with open(cached_path, "wb") as f:
                with tqdm(
                    total=total_size,
                    unit="B",
                    unit_scale=True,
                    unit_divisor=1024,
                    desc="Downloading (HTTP)",
                    ncols=80,
                ) as pbar:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))

            final_size = cached_path.stat().st_size
            print(f"✓ AWS download complete: {final_size / (1024*1024):.1f} MB")
            return str(cached_path)

        except requests.RequestException as aws_error:
            print(f"⚠ AWS download failed: {aws_error}")
            print(f"Trying fallback: Google Earth Engine...")

            if cached_path.exists():
                cached_path.unlink()

            gee_path = self._download_from_gee(year, month)
            if gee_path:
                return gee_path

            filename = self._get_aws_filename(year, month)
            if month is None:
                wustl_path = f"GL/Annual/{filename}"
            else:
                wustl_path = f"GL/Monthly/{year}/{filename}"

            if not self.gee_initialized:
                gee_error = "Not authenticated (run 'earthengine authenticate')"
            elif not (self.gee_year_range[0] <= year <= self.gee_year_range[1]):
                gee_error = f"Year {year} outside range ({self.gee_year_range[0]}-{self.gee_year_range[1]})"
            else:
                gee_error = "Download failed"

            manual_instructions = (
                f"\n{'='*80}\n"
                f"AUTOMATED DOWNLOAD FAILED\n"
                f"{'='*80}\n\n"
                f"All automated download sources are currently unavailable:\n"
                f"  ✗ AWS S3: {aws_error}\n"
                f"  ✗ Google Earth Engine: {gee_error}\n\n"
                f"MANUAL DOWNLOAD REQUIRED:\n\n"
                f"Visit the WUSTL data portal and download manually:\n\n"
                f"V6 Data (0.01° resolution, 1998-2023):\n"
                f"  URL: {self.box_shared_folder}\n"
                f"  Path: {wustl_path}\n\n"
                f"V5 Data (0.01° resolution, 1998-2024):\n"
                f"  URL: https://wustl.box.com/v/ACAG-V5GL0502-GWRPM25\n"
                f"  Path: {wustl_path}\n\n"
                f"After download:\n"
                f"  1. Save file as: {cached_path}\n"
                f"  2. Re-run your script\n\n"
                f"{'='*80}\n"
            )

            raise requests.RequestException(manual_instructions) from aws_error

    def _detect_pm25_variable(self, ds: xr.Dataset) -> Tuple[str, xr.Dataset]:
        """Detect PM2.5 variable name and prepare dataset.

        Args:
            ds: xarray Dataset.

        Returns:
            Tuple of (variable_name, processed_dataset).
        """
        if "band_data" in ds.variables:
            pm25_var = "band_data"
            if "band" in ds.dims:
                ds = ds.squeeze("band", drop=True)
        elif "PM25" in ds.variables:
            pm25_var = "PM25"
        elif "GWRPM25" in ds.variables:
            pm25_var = "GWRPM25"
        else:
            available_vars = list(ds.variables.keys())
            raise ValueError(
                f"PM2.5 variable not found. Available variables: {available_vars}"
            )
        return pm25_var, ds

    def _detect_coordinates(self, ds: xr.Dataset) -> Tuple[str, str]:
        """Detect coordinate names in dataset.

        Args:
            ds: xarray Dataset.

        Returns:
            Tuple of (latitude_coord, longitude_coord).
        """
        if "latitude" in ds.coords and "longitude" in ds.coords:
            return "latitude", "longitude"
        elif "lat" in ds.coords and "lon" in ds.coords:
            return "lat", "lon"
        elif "y" in ds.coords and "x" in ds.coords:
            return "y", "x"
        else:
            raise ValueError("Could not find latitude/longitude coordinates in file")

    def _prepare_pm25_data(
        self,
        ds: xr.Dataset,
        pm25_var: str,
        lat_coord: str,
        lon_coord: str,
        bbox: Tuple[float, float, float, float],
        buffer: float = 0.1,
    ) -> xr.DataArray:
        """Load and prepare PM2.5 data for a bounding box.

        Args:
            ds: xarray Dataset.
            pm25_var: Name of PM2.5 variable.
            lat_coord: Name of latitude coordinate.
            lon_coord: Name of longitude coordinate.
            bbox: Bounding box as (minx, miny, maxx, maxy).
            buffer: Buffer to add around bbox in degrees.

        Returns:
            PM2.5 DataArray ready for clipping.
        """
        lat_vals = ds[lat_coord].values
        lon_vals = ds[lon_coord].values
        lat_ascending = lat_vals[0] < lat_vals[-1]
        lon_ascending = lon_vals[0] < lon_vals[-1]

        if lat_ascending:
            lat_slice = slice(bbox[1] - buffer, bbox[3] + buffer)
        else:
            lat_slice = slice(bbox[3] + buffer, bbox[1] - buffer)

        if lon_ascending:
            lon_slice = slice(bbox[0] - buffer, bbox[2] + buffer)
        else:
            lon_slice = slice(bbox[2] + buffer, bbox[0] - buffer)

        ds_subset = ds.sel({lat_coord: lat_slice, lon_coord: lon_slice})
        pm25 = ds_subset[pm25_var].load()

        if not lat_ascending:
            pm25 = pm25.sortby(lat_coord)
        if not lon_ascending:
            pm25 = pm25.sortby(lon_coord)

        pm25 = pm25.rio.set_spatial_dims(x_dim=lon_coord, y_dim=lat_coord)
        pm25 = pm25.rio.write_crs("EPSG:4326")

        return pm25

    def _calculate_stats(
        self,
        clipped: xr.DataArray,
        include_count: bool = False,
        allow_empty: bool = False,
    ) -> Dict[str, float]:
        """Calculate statistics from clipped PM2.5 data.

        Args:
            clipped: Clipped PM2.5 DataArray.
            include_count: Whether to include count in results.
            allow_empty: If True, return NaN stats for empty data. If False, raise error.

        Returns:
            Dictionary with mean, std, min, max (and optionally count) statistics.

        Raises:
            ValueError: If no valid data found and allow_empty=False.
        """
        values = clipped.values.flatten()
        values = values[~np.isnan(values)]

        if len(values) == 0:
            if not allow_empty:
                raise ValueError(
                    "No valid PM2.5 data found within the polygon boundary"
                )
            stats = {
                "mean": np.nan,
                "std": np.nan,
                "min": np.nan,
                "max": np.nan,
            }
            if include_count:
                stats["count"] = 0
            return stats

        stats = {
            "mean": float(values.mean()),
            "std": float(values.std()),
            "min": float(values.min()),
            "max": float(values.max()),
        }
        if include_count:
            stats["count"] = len(values)
        return stats

    def get_pm25_at_point(
        self,
        latitude: float,
        longitude: float,
        year: int,
        month: Optional[int] = None,
    ) -> float:
        """Get PM2.5 value at a specific latitude/longitude point.

        Selects the nearest grid cell to the specified coordinates.

        Args:
            latitude: Latitude in decimal degrees.
            longitude: Longitude in decimal degrees.
            year: Year of the data.
            month: Optional month (1-12). If None, uses annual data.

        Returns:
            PM2.5 value in µg/m³ at the nearest grid cell.

        Raises:
            ValueError: If point is outside data bounds or no data available.
            requests.RequestException: If download fails.

        Example:
            >>> client = PM25Client()
            >>> pm25 = client.get_pm25_at_point(28.6139, 77.2090, year=2020, month=1)
            >>> print(f"PM2.5: {pm25:.2f} µg/m³")
        """
        nc_file = self.download_netcdf_if_needed(year, month)

        with xr.open_dataset(nc_file) as ds:
            pm25_var, ds = self._detect_pm25_variable(ds)
            lat_coord, lon_coord = self._detect_coordinates(ds)

            try:
                point_data = ds.sel(
                    {lat_coord: latitude, lon_coord: longitude}, method="nearest"
                )
            except (KeyError, ValueError) as e:
                raise ValueError(
                    f"Point ({latitude}, {longitude}) is outside data bounds"
                ) from e

            pm25_value = point_data[pm25_var].values

            if hasattr(pm25_value, "item"):
                pm25_value = pm25_value.item()
            else:
                pm25_value = float(pm25_value)

            if np.isnan(pm25_value):
                raise ValueError(
                    f"No PM2.5 data available at ({latitude}, {longitude})"
                )

            return pm25_value

    def get_pm25_stats(
        self,
        geojson_file: str,
        year: int,
        month: Optional[int] = None,
        group_by: Optional[str] = None,
    ) -> Union[Dict[str, float], pd.DataFrame]:
        """Compute PM2.5 statistics inside a polygon region from GeoJSON.

        This function automatically downloads the required NetCDF data from AWS
        if not cached locally.

        Args:
            geojson_file: Path to GeoJSON file with polygon.
            year: Year of the NetCDF data.
            month: Optional month of the NetCDF data.
            group_by: Optional column name(s) to group polygons by.
                     Can be a single column (e.g., 'state_name') or comma-separated
                     multiple columns (e.g., 'state_name,district_name').
                     If None, aggregates entire polygon boundary.
                     If specified, aggregates by unique combinations of values.

        Returns:
            If group_by is None: Dictionary with mean, std, min, and max PM2.5 values.
            If group_by is specified: DataFrame with statistics for each group.

        Raises:
            FileNotFoundError: If GeoJSON file not found.
            requests.RequestException: If NetCDF download fails.
            ValueError: If group_by column not found in GeoJSON.
        """
        if not os.path.exists(geojson_file):
            raise FileNotFoundError(f"GeoJSON file not found: {geojson_file}")

        nc_file = self.download_netcdf_if_needed(year, month)

        gdf = gpd.read_file(geojson_file)
        gdf = gdf.to_crs("EPSG:4326")

        # If group_by is specified, delegate to grouped processing
        if group_by is not None:
            group_cols = [col.strip() for col in group_by.split(",")]

            missing_cols = [col for col in group_cols if col not in gdf.columns]
            if missing_cols:
                available_columns = list(gdf.columns)
                raise ValueError(
                    f"Column(s) {missing_cols} not found in GeoJSON. "
                    f"Available columns: {available_columns}"
                )

            return self._get_pm25_stats_grouped(gdf, Path(nc_file), group_cols)
        # Combine polygons if multiple
        polygon = gdf.union_all()
        bounds = polygon.bounds

        with xr.open_dataset(nc_file) as ds:
            pm25_var, ds = self._detect_pm25_variable(ds)
            lat_coord, lon_coord = self._detect_coordinates(ds)
            pm25 = self._prepare_pm25_data(ds, pm25_var, lat_coord, lon_coord, bounds)

            clipped = pm25.rio.clip([polygon], crs="EPSG:4326", all_touched=True)
            return self._calculate_stats(clipped)

    def _get_pm25_stats_grouped(
        self, gdf: gpd.GeoDataFrame, nc_file: Path, group_by: Union[str, List[str]]
    ) -> pd.DataFrame:
        """Compute PM2.5 statistics grouped by column(s) in the GeoDataFrame.

        Args:
            gdf: GeoDataFrame with geometries (already in EPSG:4326).
            nc_file: Path to NetCDF file.
            group_by: Column name(s) to group by. Can be a string or list of strings.

        Returns:
            DataFrame with statistics for each unique value or combination in the
            group_by column(s).
        """
        group_cols = [group_by] if isinstance(group_by, str) else group_by
        bbox = gdf.total_bounds

        with xr.open_dataset(nc_file) as ds:
            pm25_var, ds = self._detect_pm25_variable(ds)
            lat_coord, lon_coord = self._detect_coordinates(ds)
            pm25 = self._prepare_pm25_data(ds, pm25_var, lat_coord, lon_coord, bbox)

            results = []
            groupby_arg = group_cols[0] if len(group_cols) == 1 else group_cols

            for group_name, group_gdf in gdf.groupby(groupby_arg):
                combined_geom = group_gdf.union_all()

                try:
                    clipped = pm25.rio.clip(
                        [combined_geom], crs="EPSG:4326", all_touched=True
                    )

                    result = {}
                    if len(group_cols) == 1:
                        result[group_cols[0]] = group_name
                    else:
                        for i, col in enumerate(group_cols):
                            result[col] = group_name[i]

                    result.update(
                        self._calculate_stats(
                            clipped, include_count=True, allow_empty=True
                        )
                    )

                    results.append(result)

                except Exception as e:
                    print(f"Warning: Error processing group '{group_name}': {e}")
                    result = {}
                    if len(group_cols) == 1:
                        result[group_cols[0]] = group_name
                    else:
                        for i, col in enumerate(group_cols):
                            result[col] = group_name[i]
                    result.update(
                        {
                            "mean": np.nan,
                            "std": np.nan,
                            "min": np.nan,
                            "max": np.nan,
                            "count": 0,
                        }
                    )
                    results.append(result)

            return pd.DataFrame(results)

    def get_pm25_stats_by_polygon(
        self,
        geojson_file: str,
        year: int,
        month: Optional[int] = None,
        id_field: Optional[str] = None,
    ) -> pd.DataFrame:
        """Compute PM2.5 statistics for each polygon in GeoJSON file.

        Args:
            geojson_file: Path to GeoJSON file with polygons.
            year: Year of the NetCDF data.
            month: Optional month of the NetCDF data.
            id_field: Optional field in GeoJSON properties to use as identifier.

        Returns:
            DataFrame with statistics for each polygon.

        Raises:
            FileNotFoundError: If NetCDF or GeoJSON file not found.

        This function automatically downloads the required NetCDF data from AWS
        if not cached locally.
        """
        if not os.path.exists(geojson_file):
            raise FileNotFoundError(f"GeoJSON file not found: {geojson_file}")

        nc_file = self.download_netcdf_if_needed(year, month)

        gdf = gpd.read_file(geojson_file)
        gdf = gdf.to_crs("EPSG:4326")
        bbox = gdf.total_bounds

        with xr.open_dataset(nc_file) as ds:
            pm25_var, ds = self._detect_pm25_variable(ds)
            lat_coord, lon_coord = self._detect_coordinates(ds)
            pm25 = self._prepare_pm25_data(ds, pm25_var, lat_coord, lon_coord, bbox)

            # Determine column name once at the beginning
            if id_field and id_field in gdf.columns:
                column_name = id_field
            elif "NAME_1" in gdf.columns:
                column_name = "NAME_1"
            elif "name" in gdf.columns:
                column_name = "name"
            else:
                column_name = "index"

            results = []

            # Process each polygon
            for idx, row in gdf.iterrows():
                geom = row.geometry

                try:
                    clipped = pm25.rio.clip([geom], crs="EPSG:4326", all_touched=True)
                    stats = self._calculate_stats(clipped, allow_empty=True)
                    mean_val, std_val = stats["mean"], stats["std"]
                except Exception:
                    mean_val, std_val = np.nan, np.nan

                if column_name == "index":
                    feature_id = idx
                else:
                    feature_id = row[column_name]

                results.append(
                    {
                        column_name: feature_id,
                        "mean": mean_val,
                        "std": std_val,
                    }
                )

            return pd.DataFrame(results)

    def clear_cache(self) -> None:
        """Clear all cached NetCDF files."""
        if self.cache_dir.exists():
            for file in self.cache_dir.glob("*.nc"):
                try:
                    file.unlink()
                    print(f"Removed: {file}")
                except Exception as e:
                    print(f"Warning: Could not remove {file}: {e}")
            print(f"Cache cleared: {self.cache_dir}")
        else:
            print("Cache directory does not exist")

    def list_cached_files(self) -> List[str]:
        """List all cached NetCDF files.

        Returns:
            List of cached file paths.
        """
        if not self.cache_dir.exists():
            return []

        cached_files = list(self.cache_dir.glob("*.nc"))
        if cached_files:
            print(f"Cached files in {self.cache_dir}:")
            for file in cached_files:
                size_mb = file.stat().st_size / (1024 * 1024)
                print(f"   {file.name} ({size_mb:.1f} MB)")
        else:
            print(f"No cached files in {self.cache_dir}")

        return [str(f) for f in cached_files]
