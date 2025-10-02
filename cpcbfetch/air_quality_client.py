"""
Main client class for interacting with AQI services
"""

import base64
from base64 import b64encode, b64decode
from wsgiref import headers

import numpy as np
import math
import json
import os
from datetime import datetime
import pandas as pd
import requests
import rioxarray
import xarray as xr
import geopandas as gpd
from geopy.distance import geodesic


class AQIClient:

    def __init__(self):
        """
        Initialize the AQI Client

        """

        self.BASE_URL = "https://airquality.cpcb.gov.in"
        self.BASE_PATH = (
            "https://airquality.cpcb.gov.in/dataRepository/download_file?file_name="
        )
        self.DATA_REPOSITORY = "/dataRepository/"
        self.DATA_REPOSITORY_DROPDOWN = f"{self.DATA_REPOSITORY}all_india_stationlist"
        self.FETCH_REPOSITORIES = f"{self.DATA_REPOSITORY}file_Path"

        self.DEFAULT_HEADERS = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "q=0.8;application/json;q=0.9",
        }

    # helper functions
    def encode_base64(self, data: bytes) -> str:
        """Encode bytes to base64 string."""
        return base64.b64encode(data).decode("utf-8")

    def decode_base64(self, data: str) -> str:
        """Decode base64 string to UTF-8 string."""
        return base64.b64decode(data.encode("utf-8")).decode("utf-8")

    def getCompleteList(self) -> dict:
        """Fetch the complete list of all India stations and cities."""
        form_body = self.encode_base64(b"{}")
        response = requests.post(
            self.BASE_URL + self.DATA_REPOSITORY_DROPDOWN, form_body, timeout=30
        )
        if response.status_code == 200:
            response = self.decode_base64(response.text)
            response = json.loads(response)  # Replaced eval() with json.loads()
            return response["dropdown"] if response["status"] == "success" else {}
        else:
            response.raise_for_status()

    def get_state_list(self) -> list:
        """Return list of states available for AQI data."""
        try:
            complete_list = self.getCompleteList()
            return list(complete_list.get("cities", {}))
        except Exception:
            return []

    def get_city_list(self, state: str) -> list:
        """Return list of cities available in given state for AQI data"""
        try:
            complete_list = self.getCompleteList()
            cities = complete_list.get("cities", {})
            if cities and state in cities:
                return [city["value"] for city in cities[state]]
            return []
        except Exception:
            return []

    def get_station_list(self, city: str) -> list:
        """Return station list in form 'station_id(station_name)' available in given city for AQI data"""
        try:
            complete_list = self.getCompleteList()
            stations = complete_list.get("stations", {})
            if stations and city in stations:
                return list(stations[city])
            return []
        except Exception:
            return []

    def getFilePath(
        self,
        station_id: str,
        station_name: str,
        state: str,
        city: str,
        year: str,
        frequency: str,
        dataType: str,
    ) -> str:
        """
        Get File path which contain data for given query
        station_id: station id
        station_name: station name
        state: state
        city: city
        year: year
        frequency: option('hourly','daily')
        dataType: option('cityLevel', 'stationLevel')
        """

        payload = {
            "station_id": station_id,
            "station_name": station_name,
            "state": state,
            "city": city,
            "year": year,
            "frequency": frequency,
            "dataType": dataType,
        }
        payload_str = json.dumps(payload)
        encoded_payload = self.encode_base64(payload_str.encode("utf-8"))

        response = requests.post(
            self.BASE_URL + self.FETCH_REPOSITORIES,
            data=encoded_payload,
            headers=self.DEFAULT_HEADERS
        , timeout=30)
        if response.status_code == 200:
            response = self.decode_base64(response.text)
            response = json.loads(response) 
            return response["data"] if response["status"] == "success" else {}
        else:
            response.raise_for_status()

    def download_past_year_AQI_data_cityLevel(
        self, city: str, year: str, save_location: str
    ) -> dict:
        """
        Download past AQI data for a specific city.
        """
        data_file_paths = self.getFilePath("", "", "", city, "", "daily", "cityLevel")
        if file_path := next(
            (
                entry["filepath"]
                for entry in data_file_paths
                if entry["year"] == year
            ),
            "",
        ):
            file_path = self.BASE_PATH + file_path
            df = pd.read_excel(file_path)
            df = df.iloc[:31]
            df.to_csv(save_location, index=False)
            return df.head()
        raise Exception("Data not found")

    def download_past_year_AQI_data_stationLevel(
        self, station_id: str, year: str, save_location: str
    ) -> dict:
        """
        Download past AQI data for a specific station.
        """
        complete_list = self.getCompleteList()
        stationList = complete_list.get("stations", [])
        # Find the station label for the given station_id
        station_name = None
        for city_stations in stationList.values():
            for station in city_stations:
                if station["value"] == station_id:
                    station_name = station["label"]
                    break
            if station_name:
                break
        if station_name is None:
            return Exception("Station ID not found")
        data_file_paths = self.getFilePath(
            station_id, station_name, "", "", "", "daily", "stationLevel"
        )
        if file_path := next(
            (
                entry["filepath"]
                for entry in data_file_paths
                if entry["year"] == year
            ),
            "",
        ):
            file_path = self.BASE_PATH + file_path
            df = pd.read_excel(file_path)
            df.to_csv(save_location, index=False)
            return df.head()
        return Exception("Data not found")

class LiveAQIClient:
    """
    Client for fetching live air quality data.
    """
    def __init__(self):
        self.BASE_URL = 'https://airquality.cpcb.gov.in'
        self.COORDINATE_URL = "http://ip-api.com/json"
        self.DASHBOARD = '/aqi_dashboard/'
        self.aqi_station_all_india_url = f"{self.BASE_URL}{self.DASHBOARD}aqi_station_all_india"
        self.aqi_all_parameters_url = f"{self.BASE_URL}{self.DASHBOARD}aqi_all_Parameters"
        self.headers = { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'q=0.8;application/json;q=0.9' }
        self.cookies = {
            "ccr_public": "A"
        }

    def clean_pollution_data(self, data):
        """
        Clean the pollution data dictionary.
        - Reduce chartData values for each hour and pollutant.
        """
        cleaned_data = data.copy()

        # Clean chartData
        if 'chartData' in data:
            cleaned_chart_data = []
            i = 0
            for series in data['chartData']:
                if not series or not isinstance(series, list) or len(series) < 2:
                    continue
                rows = series[1:]  # Skip header
                live_data = []
                for row in rows:
                    if len(row) < 2:
                        continue
                    date = row[0]
                    value = row[1]
                    if date is None or value is None:
                        continue
                    live_data.append({'date': date, 'val': value})
                # Reconstruct series with min/max values
                reduced_series = {'name': cleaned_data['metrics'][i]['name'], 'data': live_data}
                i += 1
                cleaned_chart_data.append(reduced_series)
            cleaned_data['last_hours'] = cleaned_chart_data
            cleaned_data.pop('chartData', None)

        return cleaned_data
    
    def mkrqs(self, url, headers, data, cookies):
        """
        Makes a POST request to the specified URL with the given headers, data, and cookies.
        Args:
            url (str): The URL to send the POST request to.
            headers (dict): The headers to include in the request.
            data (str): The data to include in the request body.
            cookies (dict): The cookies to include in the request.
        Returns:
            dict: The JSON-decoded response from the server.
        Raises:
            requests.exceptions.RequestException: If the request fails.
            json.JSONDecodeError: If the response cannot be decoded as JSON.  
        """
        resp = requests.post(url=url, headers=headers, data=data, cookies=cookies, timeout=30)
        if resp.status_code != 200:
            raise requests.exceptions.RequestException(f"Request failed with status code {resp.status_code}")
        data = base64.b64decode(resp.content)
        return json.loads(data)
    
    def get_system_location(self):
        """Retrieve system's approximate longitude and latitude using IP-based geolocation.
        Returns:
            tuple: A tuple containing (longitude, latitude).
        Raises:
            Exception: If the geolocation lookup fails.
        """
        try:
            response = requests.get(self.COORDINATE_URL, timeout=30)
            data = response.json()
            if data.get('status') == 'success':
                return data.get('lat'), data.get('lon')
            else:
                raise Exception(f"Geolocation lookup failed: {data.get('message')}")
        except Exception as e:
            raise Exception(f"Error retrieving system location: {e}") from e
    
    def get_nearest_station(self, coords=None):
        """
        Get the nearest air quality monitoring station based on given coordinates.
        Args:
            coords (tuple): A tuple containing (longitude, latitude).
        Returns:
            str: The ID of the nearest station.
        """
        try:
            cities = self.get_all_india()
            if not coords:
                coords = self.get_system_location()
            user_location = (float(coords[0]), float(coords[1]))
            min_dist = float('inf')
            nearest_station = None
            for stations in cities:
                for station in stations.get("stationsInCity", []):
                    try:
                        station_location = (float(station["latitude"]), float(station["longitude"]))
                        dist = geodesic(user_location, station_location).kilometers
                        if dist < min_dist:
                            min_dist = dist
                            nearest_station = (station.get("id", None),station.get("name", None))
                    except (TypeError, ValueError):
                        continue
            if nearest_station:
                return nearest_station
            raise Exception("No stations found or invalid station data.")
        except Exception as e:
            raise Exception(f"Error finding nearest station: {e}")
    
    # Returns all station ids, locations etc.
    def get_all_india(self):
        """
        Get all air quality monitoring stations in India and their locations.
        """
        body = "e30="
        try:
            return self.mkrqs(self.aqi_station_all_india_url, self.headers, body, self.cookies)["stations"]
        except Exception:
            return self.mkrqs(self.aqi_station_all_india_url, self.headers, body, self.cookies)
    
    def live_aqi_data(self, station_id:str, date_time:str):
        """
        Get live air quality data for a specific station over past 24 hour from date_time provided.
        Args:
            station_id (str): Station ID.
            date (str): Date in 'YYYY-MM-DDTHH:00:00Z' format. Example: '2025-09-16T23:00:00Z'
        Returns:
            dict: Live Air quality data for the specified station and date.
        Raises:
            Exception: If the request fails or returns an error.
        """
        if not station_id or not date_time:
            raise ValueError("Both station_id and date_time must be provided.")
        raw_body = json.dumps({
            "station_id": station_id,
            "date": date_time
        })
        data = b64encode(raw_body.encode()).decode('utf-8')
        return self.mkrqs(self.aqi_all_parameters_url, self.headers, data, self.cookies)

    def get_live_aqi_data(self, station_id=None, coords=None, date=None, hour=None):
        """
        Function to get live AQI data.
        Args:
            station_id (str, optional): Station ID. If not provided, will use coords or system location.
            coords (tuple, optional): (latitude, longitude). Used if station_id is not provided.
            date (str, optional): Date in 'YYYY-MM-DD' format. Defaults to today if not provided.
            hour (int, optional): Hour (0-23). Defaults to last completed hour if not provided.
        Returns:
            dict: Live AQI data.
        """
        # Determine station_id
        if not station_id:
            if coords:
                station_id = self.get_nearest_station(coords)[0]
            else:
                sys_coords = self.get_system_location()
                station_id = self.get_nearest_station(sys_coords)[0]

        # Determine date and hour
        now = datetime.now()
        if not date:
            date = now.strftime('%Y-%m-%d')
        if hour is not None:
            try:
                hour = int(hour)
                if not (0 <= hour <= 23):
                    raise ValueError
            except Exception as e:
                raise ValueError("hour must be an integer between 0 and 23.") from e
            date_time = f"{date}T{hour:02d}:00:00Z"
        else:
            last_hour = now.replace(minute=0, second=0, microsecond=0)
            date_time = f"{date}T{last_hour.hour:02d}:00:00Z"
        aqi_data = self.live_aqi_data(station_id, date_time)
        if isinstance(aqi_data, Exception):
            return aqi_data
        aqi_data = self.clean_pollution_data(aqi_data)
        return aqi_data


class PM25Client:

    def __init__(self):
        """
        Initialize the PM2.5 Client

        """
        self.ANNUAL_PM2_DATA_BASE_PATH = "examples/V6GL01.0p10.CNNPM25.Global"
        self.MONTHLY_PM2_DATA_BASE_PATH = "examples/V6GL01.0p10.CNNPM25.Global"

    def get_netCDF_path(self, year: int, month: int = None) -> str:
        return (
            self.ANNUAL_PM2_DATA_BASE_PATH + f".{year}01-{year}12.nc"
            if month is None
            else self.MONTHLY_PM2_DATA_BASE_PATH + f".{year}{month:02d}-{year}{month:02d}.nc"
        )

    def get_pm25_stats(self, geojson_file, year: int, month: int = None):
        """
        Compute average and standard deviation of PM2.5
        inside a polygon region from GeoJSON.

        Args:
            geojson_file (str): Path to GeoJSON file with polygon.
            year (int): Year of the netCDF data.
            month (int, optional): Month of the netCDF data. If None, use annual data. Defaults to None.

        Returns:
            dict: {"mean": value, "std": value}
        """
        # Check if netCDF data exist
        nc_file = self.get_netCDF_path(year, month)

        if not os.path.exists(nc_file):
            raise FileNotFoundError(
                f"NetCDF data not found for year {year}, month {month}"
            )
        # check if geojson file exist
        if not os.path.exists(geojson_file):
            raise FileNotFoundError(f"GeoJSON file not found: {geojson_file}")

        # Load dataset
        ds = xr.open_dataset(nc_file)

        # Attach lat/lon coords
        ds = ds.assign_coords(
            lat=("lat", ds["latitude"].values),
            lon=("lon", ds["longitude"].values),
        )

        pm25 = ds["PM25"]
        # Rename lat/lon to y/x for rioxarray
        pm25 = pm25.rename({"lat": "y", "lon": "x"})
        # Write CRS (NetCDF is in WGS84 lat/lon)
        pm25 = pm25.rio.write_crs("EPSG:4326")

        # Read polygon from GeoJSON
        gdf = gpd.read_file(geojson_file)
        polygon = gdf.union_all()  # combine polygons if multiple

        # Clip to polygon
        clipped = pm25.rio.clip([polygon], crs="EPSG:4326")

        # Extract values, remove NaNs
        values = clipped.values.flatten()
        values = values[~np.isnan(values)]

        return {"mean": float(values.mean()), "std": float(values.std())}

    def get_pm25_stats_by_polygon(
        self, geojson_file, year: int, month: int = None, id_field=None
    ):
        """
        Compute average and standard deviation of PM2.5
        inside a polygon region from GeoJSON.

        Args:
            geojson_file (str): Path to GeoJSON file with polygon.
            year (int): Year of the netCDF data.
            month (int, optional): Month of the netCDF data. If None, use annual data. Defaults to None.
            id_field (str, optional): Field in GeoJSON properties to use as identifier. If None, use index. Defaults to None.

        Returns:
            dict: {"mean": value, "std": value}
        """
        # Check if netCDF data exist
        nc_file = self.get_netCDF_path(year, month)

        if not os.path.exists(nc_file):
            raise FileNotFoundError(
                f"NetCDF data not found for year {year}, month {month}"
            )
        # check if geojson file exist
        if not os.path.exists(geojson_file):
            raise FileNotFoundError(f"GeoJSON file not found: {geojson_file}")

        # Load dataset
        ds = xr.open_dataset(nc_file)

        # Attach coordinates
        ds = ds.assign_coords(
            lat=("lat", ds["latitude"].values),
            lon=("lon", ds["longitude"].values),
        )

        # --- FIX longitudes from [0,360] → [-180,180] ---
        lon = ds["lon"].values
        lon = np.where(lon > 180, lon - 360, lon)
        ds = ds.assign_coords(lon=("lon", lon))

        pm25 = ds["PM25"]

        # Rename for rioxarray
        pm25 = pm25.rename({"lat": "y", "lon": "x"})

        # Assign CRS
        pm25 = pm25.rio.write_crs("EPSG:4326")

        # Read polygons
        gdf = gpd.read_file(geojson_file)
        results = []
        for idx, row in gdf.iterrows():
            geom = row.geometry

            try:
                clipped = pm25.rio.clip([geom], crs="EPSG:4326")
                values = clipped.values.flatten()
                values = values[~np.isnan(values)]

                if values.size > 0:
                    mean_val = float(values.mean())
                    std_val = float(values.std())
                else:
                    mean_val, std_val = np.nan, np.nan
            except Exception as e:
                mean_val, std_val = np.nan, np.nan

            if id_field and id_field in row:
                feature_id = row[id_field]
            elif "NAME_1" in row:
                feature_id = row["NAME_1"]
            elif "name" in row:
                feature_id = row["name"]
            else:
                feature_id = idx
            results.append(
                {"State/Union Territory": feature_id, "mean": mean_val, "std": std_val}
            )

        return pd.DataFrame(results)
