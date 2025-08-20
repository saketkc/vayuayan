"""
Main client class for interacting with CPCB Airquality web services
"""

import heapq
import math
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd

from .constants import ALL_STATION_URL, BASE_URL, DOWNLOAD_URL, POST_HEADERS
from .exceptions import CPCBError, NetworkError
from .utils import (clean_station_name, euclidean_distance, haversine_distance,
                    safe_get, safe_post, sort_station_data,
                    stations_to_dataframe, time_to_isodate, url_encode)


class CPCBClient:
    """
    Main client for fetching weather data from India Meteorological Department
    """

    def __init__(self, use_test_endpoint: bool = True):
        """
        Initialize the CPCB  Client

        Args:
            use_test_endpoint: Whether to use the test endpoint for weather data
        """
        self.station_url = ALL_STATION_URL
        self.cookies = {"ccr_public": "A"}

    def list_stations(self, as_dataframe=False):
        """
        Get list of all available cities

        """
        try:
            data = "e30="
            response = safe_post(
                self.station_url, headers=POST_HEADERS, data=data, cookies=self.cookies
            )["stations"]
            response = sort_station_data(response)
        except Exception as e:
            raise CPCBError(f"Failed to fetch cities: {str(e)}")
        if as_dataframe:
            return stations_to_dataframe(response)
        return response

    def download_hourly_aqi(self):
        pass

    def download_yearly_aqi(self):
        pass
        # aqi hourly data: https://airquality.cpcb.gov.in/dataRepository/download_file?file_name=AQI_hourly/city_level/delhi/2023/January/delhi_January_2023.xlsx

    def download_raw_data(
        self,
        url: Optional[str] = None,
        site_id: Optional[str] = None,
        station_name: Optional[str] = None,
        time_period: Optional[str] = "15Min",
        year: Optional[str] = None,
        output_dir: str = "downloads",
        filename: Optional[str] = None,
        return_dataframe: bool = False,
        verbose: bool = False,
    ) -> Union[str, pd.DataFrame, None]:
        """
        Download CSV file from CPCB data repository

        Args:
            url: Direct URL to download from (if provided, other parameters are ignored)
            site_id: Station site ID (required if url not provided)
            station_name: Station name (required if url not provided)
            time_period: Time period for data (required if url not provided)
            year: Year for data (required if url not provided)
            output_dir: Directory to save downloaded file (default: "downloads")
            filename: Custom filename (optional, auto-generated if not provided)
            return_dataframe: Whether to return pandas DataFrame instead of file path
            verbose: Whether to print status messages

        Returns:
            str: Path to downloaded file (if return_dataframe=False)
            pd.DataFrame: Loaded DataFrame (if return_dataframe=True)
            None: If download fails and return_dataframe=True

        Raises:
            CPCBError: If required parameters are missing or download fails
            NetworkError: If network request fails

        Examples:
            # Download using direct URL
            file_path = client.download_csv(
                url="https://airquality.cpcb.gov.in/dataRepository/download_file?file_name=Raw_data/2024/Delhi_Punjabi_Bagh_2024.csv"
            )

            # Download using parameters
            file_path = client.download_csv(
                site_id="DL001",
                station_name="Punjabi_Bagh",
                time_period="2024",
                year="2024"
            )

            # Get data as DataFrame
            df = client.download_csv(
                site_id="DL001",
                station_name="Punjabi_Bagh",
                time_period="2024",
                year="2024",
                return_dataframe=True
            )
        """

        def log(message: str):
            """Print message only if verbose mode is enabled"""
            if verbose:
                print(message)

        # Construct URL if not provided directly
        if url is None:
            if not all([site_id, station_name, time_period, year]):
                raise CPCBError(
                    "Either 'url' must be provided, or all of 'site_id', 'station_name', "
                    "'time_period', and 'year' must be provided"
                )

            station_name = clean_station_name(station_name)
            # Construct URL using the pattern from constants
            csv_filename = f"{site_id}_{station_name}_{time_period}.csv"
            url = f"{DOWNLOAD_URL}/{time_period}/{year}/{csv_filename}"
            log(f"Constructed URL: {url}")
        log(f"Downloading CSV from: {url}")

        try:
            # Make the request
            response = safe_get(
                url, timeout=60, max_retries=3
            )  # Longer timeout for file downloads

            # Check if response contains CSV data
            content_type = response.headers.get("content-type", "").lower()
            if (
                "text/csv" not in content_type
                and "application/octet-stream" not in content_type
            ):
                # Sometimes CSV files are served with different content types
                log(f"Warning: Unexpected content type: {content_type}")

            # Generate filename if not provided
            if filename is None:
                if url:
                    # Extract filename from URL
                    filename = url.split("/")[-1]
                    if "?" in filename:
                        filename = filename.split("?")[0]
                    if not filename.endswith(".csv"):
                        filename += ".csv"
                else:
                    filename = f"{site_id}_{station_name}_{time_period}.csv"
            filename = filename.replace(".csv", f"_{year}.csv")
            # Ensure filename has .csv extension
            if not filename.endswith(".csv"):
                filename += ".csv"

            # Create output directory if it doesn't exist
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            file_path = Path(output_dir) / filename

            # Write file
            log(f"Saving to: {file_path}")
            with open(file_path, "wb") as f:
                f.write(response.content)

            log(f"✅ Successfully downloaded: {file_path}")

            # Return DataFrame if requested
            if return_dataframe:
                try:
                    df = pd.read_csv(file_path)
                    log(f"📊 Loaded DataFrame with shape: {df.shape}")
                    return df
                except Exception as e:
                    log(f"❌ Failed to load CSV as DataFrame: {e}")
                    if verbose:
                        print(f"File saved at: {file_path}")
                    return None

            return str(file_path)

        except NetworkError:
            raise
        except Exception as e:
            raise CPCBError(f"Failed to download CSV: {str(e)}")

    def get_station_params(self, sid, date):
        data = url_encode({"station_id": sid, "date": date})
        return safe_post(
            ALL_PARAMETERS_URL, headers=POST_HEADERS, data=data, cookies=self.cookies
        )

    def get_nearest_station(self, lat, lon):
        ## get all data first
        stations_ = {}
        cities = self.get_all_india()
        X1, Y1 = [float(lat), float(lon)]
        for stations in cities:
            for station in stations["stationsInCity"]:
                # find euclideon distance between this station coords vs given coords
                X2, Y2 = [float(station["longitude"]), float(station["latitude"])]
                distance = math.sqrt(((X1 - X2) ** 2) + ((Y1 - Y2) ** 2))
                stations_[station["id"]] = distance
        sorted_stations = dict(sorted(stations_.items(), key=lambda x: x[1]))
        return list(sorted_stations.keys())[0]

    def get_nearest_station(
        self, lat: float, lon: float, return_distance: bool = False
    ) -> Union[str, Tuple[str, float]]:
        """
        Find the nearest station to given coordinates using optimized algorithms

        Args:
            lat: Target latitude
            lon: Target longitude
            return_distance: Whether to return distance along with station ID

        Returns:
            Station ID of nearest station, or tuple of (station_id, distance) if return_distance=True
        """
        try:
            cities = self.list_stations()  # Assuming this gets all stations
        except Exception as e:
            raise CPCBError(f"Failed to fetch station data: {str(e)}")

        if not cities:
            raise CPCBError("No stations available")

        target_lat, target_lon = float(lat), float(lon)
        min_distance = float("inf")
        nearest_station_id = None

        # Single pass through all stations
        for city in cities:
            for station in city.get("stationsInCity", []):
                try:
                    station_lat = float(station["latitude"])
                    station_lon = float(station["longitude"])

                    # Use haversine distance for more accurate geographical distance
                    distance = haversine_distance(
                        target_lat, target_lon, station_lat, station_lon
                    )

                    if distance < min_distance:
                        min_distance = distance
                        nearest_station_id = station["id"]

                except (ValueError, KeyError, TypeError):
                    # Skip stations with invalid coordinates
                    continue

        if nearest_station_id is None:
            raise CPCBError("No valid stations found")

        return (
            (nearest_station_id, min_distance)
            if return_distance
            else nearest_station_id
        )

    def get_k_nearest_stations(
        self, lat: float, lon: float, k: int = 5
    ) -> List[Tuple[str, float]]:
        """
        Find the k nearest stations to given coordinates

        Args:
            lat: Target latitude
            lon: Target longitude
            k: Number of nearest stations to return

        Returns:
            List of tuples: [(station_id, distance), ...]
        """
        try:
            cities = self.list_stations()
        except Exception as e:
            raise CPCBError(f"Failed to fetch station data: {str(e)}")

        if not cities:
            raise CPCBError("No stations available")

        target_lat, target_lon = float(lat), float(lon)

        # Use a min-heap to efficiently track k nearest stations
        heap = []

        for city in cities:
            for station in city.get("stationsInCity", []):
                try:
                    station_lat = float(station["latitude"])
                    station_lon = float(station["longitude"])

                    distance = haversine_distance(
                        target_lat, target_lon, station_lat, station_lon
                    )

                    if len(heap) < k:
                        # Heap not full, add station
                        heapq.heappush(heap, (-distance, station["id"], distance))
                    elif distance < -heap[0][0]:
                        # Found closer station, replace farthest
                        heapq.heapreplace(heap, (-distance, station["id"], distance))

                except (ValueError, KeyError, TypeError):
                    continue

        # Extract results and sort by distance (closest first)
        results = [(station_id, distance) for _, station_id, distance in heap]
        return sorted(results, key=lambda x: x[1])

    def get_nearest_station_with_bounding_box(
        self, lat: float, lon: float, max_distance_km: float = 100
    ) -> Optional[Tuple[str, float]]:
        """
        Find nearest station within a bounding box for better performance on large datasets

        Args:
            lat: Target latitude
            lon: Target longitude
            max_distance_km: Maximum search radius in kilometers

        Returns:
            Tuple of (station_id, distance) or None if no station found within radius
        """
        try:
            cities = self.list_stations()
        except Exception as e:
            raise CPCBError(f"Failed to fetch station data: {str(e)}")

        target_lat, target_lon = float(lat), float(lon)

        # Calculate bounding box (approximate)
        # 1 degree latitude ≈ 111 km
        # 1 degree longitude ≈ 111 km * cos(latitude)
        lat_delta = max_distance_km / 111.0
        lon_delta = max_distance_km / (111.0 * math.cos(math.radians(target_lat)))

        min_lat = target_lat - lat_delta
        max_lat = target_lat + lat_delta
        min_lon = target_lon - lon_delta
        max_lon = target_lon + lon_delta

        min_distance = float("inf")
        nearest_station = None

        for city in cities:
            for station in city.get("stationsInCity", []):
                try:
                    station_lat = float(station["latitude"])
                    station_lon = float(station["longitude"])

                    # Quick bounding box check
                    if not (
                        min_lat <= station_lat <= max_lat
                        and min_lon <= station_lon <= max_lon
                    ):
                        continue

                    distance = haversine_distance(
                        target_lat, target_lon, station_lat, station_lon
                    )

                    if distance <= max_distance_km and distance < min_distance:
                        min_distance = distance
                        nearest_station = (station["id"], distance)

                except (ValueError, KeyError, TypeError):
                    continue

        return nearest_station

    def get_nearest_station(self, lat: float, lon: float) -> str:
        """
        Optimized version of the original get_nearest_station method
        """
        return get_nearest_station_optimized(self, lat, lon, return_distance=False)
