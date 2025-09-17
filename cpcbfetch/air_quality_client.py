"""
Main client class for interacting with AQI services
"""

import base64
from base64 import b64encode, b64decode
from wsgiref import headers
import requests
import json
import math
from datetime import datetime
import pandas as pd


class AQIClient:

    def __init__(self):
        """
        Initialize the AQI Client

        """

        self.BASE_URL = 'https://airquality.cpcb.gov.in'
        self.BASE_PATH = 'https://airquality.cpcb.gov.in/dataRepository/download_file?file_name='
        self.DATA_REPOSITORY = '/dataRepository/' 
        self.DATA_REPOSITORY_DROPDOWN = self.DATA_REPOSITORY + 'all_india_stationlist'
        self.FETCH_REPOSITORIES = self.DATA_REPOSITORY + 'file_Path'
        self.DEFAULT_HEADERS = { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'q=0.8;application/json;q=0.9' }
        self.options = { headers: self.DEFAULT_HEADERS  }

    # helper functions
    def encode_base64(self, data: bytes) -> str:
        """Encode bytes to base64 string."""
        return base64.b64encode(data).decode('utf-8')
    def decode_base64(self, data: str) -> str:
        """Decode base64 string to UTF-8 string."""
        return base64.b64decode(data.encode('utf-8')).decode('utf-8')

    def getCompleteList(self) -> dict:
        """Fetch the complete list of all India stations and cities."""
        form_body = self.encode_base64(b'{}')
        response = requests.post(
            self.BASE_URL + self.DATA_REPOSITORY_DROPDOWN,
            form_body
        )
        if response.status_code == 200:
            response = self.decode_base64(response.text)
            response = eval(response)
            if(response['status'] == 'success'):
                return response['dropdown']
            else:
                return {}
        else:
            response.raise_for_status()

    def get_state_list(self) -> list:
        """Return list of states available for AQI data."""
        try:
            complete_list = self.getCompleteList()
            stateList  = []
            for state in complete_list.get('cities',{}):
                stateList.append(state)
            return stateList
        except:
            return []

    def get_city_list(self, state: str) -> list:
        """Return list of cities available in given state for AQI data"""
        try:
            complete_list = self.getCompleteList()
            cityList = []
            cities = complete_list.get('cities',{})
            if(cities and state in cities):
                for city in cities[state]:
                    cityList.append(city['value'])
            return cityList
        except:
            return []

    def get_station_list(self, city: str) -> list:
        """Return station list in form 'station_id(station_name)' available in given city for AQI data"""
        try:
            complete_list = self.getCompleteList()
            stationList = []
            stations = complete_list.get('stations', {})
            if(stations and city in stations):
                for station in stations[city]:
                    stationList.append(station)
            return stationList
        except:
            return []

    def getFilePath(self, station_id:str, station_name:str, state:str, city:str, year:str, frequency:str, dataType:str) -> str:
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
            "dataType": dataType
        }
        payload_str = json.dumps(payload)
        encoded_payload = self.encode_base64(payload_str.encode("utf-8"))

        response = requests.post(
            self.BASE_URL + self.FETCH_REPOSITORIES,
            data=encoded_payload, headers=self.DEFAULT_HEADERS
        )
        if response.status_code == 200:
            response = self.decode_base64(response.text)
            response = eval(response)
            if(response['status'] == 'success'):
                return response['data']
            else:
                return {}
        else:
            response.raise_for_status()

    def download_past_year_AQI_data_cityLevel(self, city:str, year:str, save_location:str) -> dict:
        """
        Download past AQI data for a specific city.
        """
        data_file_paths = self.getFilePath("", "", "", city, "", "daily", "cityLevel")
        file_path = ""
        for entry in data_file_paths:
            if entry['year'] == year:
                file_path = entry['filepath']
                break
        if file_path:
            file_path = self.BASE_PATH + file_path
            df = pd.read_excel(file_path)
            df.to_csv(save_location, index=False)
            return df.head()
        return Exception("Data not found")

    def download_past_year_AQI_data_stationLevel(self, station_id:str, year:str, save_location:str) -> dict:
        """
        Download past AQI data for a specific station.
        """
        complete_list = self.getCompleteList()
        stationList = complete_list.get('stations', [])
        # Find the station label for the given station_id
        station_name = None
        for city_stations in stationList.values():
            for station in city_stations:
                if station['value'] == station_id:
                    station_name = station['label']
                    break
            if station_name:
                break
        if(station_name is None):
            return Exception("Station ID not found")
        data_file_paths = self.getFilePath(station_id, station_name, "", "", "", "daily", "stationLevel")
        file_path = ""
        for entry in data_file_paths:
            if entry['year'] == year:
                file_path = entry['filepath']
                break
        if file_path:
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
        resp = requests.post(url=url, headers=headers, data=data, cookies=cookies)
        data = b64decode(resp.content)
        return json.loads(data)
    
    def get_system_location(self):
        """Retrieve system's approximate longitude and latitude using IP-based geolocation.
        Returns:
            tuple: A tuple containing (longitude, latitude).
        Raises:
            Exception: If the geolocation lookup fails.
        """
        try:
            response = requests.get('http://ip-api.com/json')
            data = response.json()
            if data.get('status') == 'success':
                return data.get('lat'), data.get('lon')
            else:
                raise Exception(f"Geolocation lookup failed: {data.get('message')}")
        except Exception as e:
            raise Exception(f"Error retrieving system location: {e}")
    
    def get_nearest_station(self, coords):
        """
        Get the nearest air quality monitoring station based on given coordinates.
        Args:
            coords (tuple): A tuple containing (longitude, latitude).
        Returns:
            str: The ID of the nearest station.
        """
        try:
            stations_ = {}
            cities = self.get_all_india()
            X1, Y1 = [float(coords[0]), float(coords[1])]
            for stations in cities:
                for station in stations.get("stationsInCity", []):
                    try:
                        X2, Y2 = [float(station["latitude"]), float(station["longitude"])]
                        distance = math.sqrt(((X1 - X2) ** 2) + ((Y1 - Y2) ** 2))
                        stations_[station.get("id")] = distance
                    except (TypeError, ValueError):
                        continue
            if not stations_:
                raise Exception("No stations found or invalid station data.")
            sorted_stations = dict(sorted(stations_.items(), key=lambda x: x[1]))
            return list(sorted_stations.keys())[0]
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
    
    def get_live_data(self, station_id:str, date_time:str):
        """
        Get live air quality data for a specific station over past 24 hour from date_time provided.
        Args:
            station_id (str): Station ID.
            date (str): Date in 'YYYY-MM-DDTHH:00:00Z' format. //2025-09-16T23:00:00Z
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

    def get_aqi_data(self, station_id=None, date=None, hours: int = None):
        """
        Get air quality data for a specific station or nearest station based on coordinates.
        Args:
            station_id (str): Station ID. If None, system location will be used to find nearest station.
            date (str): Date in 'YYYY-MM-DD' format. Defaults to current date if None.
            hours (int): Hour of the day (0-23). If provided, it will be used to form the complete date-time.
        Returns:
            dict: Air quality data for the specified station and date-time.
        Raises:
            Exception: If the request fails, returns an error, or if invalid parameters are provided.
        """
        if not station_id:
            coords = self.get_system_location()
            station_id = self.get_nearest_station(coords)

        if not date:
            now = datetime.now()  # Use local time instead of UTC
            print(now)
            last_hour = now.replace(minute=0, second=0, microsecond=0)
            date = last_hour.strftime('%Y-%m-%dT%H:00:00Z')
        else:
            # check if date is of format YYYY-MM-DD
            try:
                datetime.strptime(date, '%Y-%m-%d')
                # If only date is provided, append last completed hour or use provided hour if available
                if hours is not None:
                    # Ensure hours is an int and between 0-23
                    try:
                        hour = int(hours)
                        if not (0 <= hour <= 23):
                            raise ValueError
                    except Exception:
                        raise ValueError("hours must be an integer between 0 and 23.")
                    date += f'T{hour:02d}:00:00Z'
                else:
                    # Use last completed hour (UTC)
                    now = datetime.now()  # Use local time instead of UTC
                    print(now)
                    last_hour = now.replace(minute=0, second=0, microsecond=0)
                    date += f'T{last_hour.hour:02d}:00:00Z'
            except ValueError:
                raise ValueError("Date must be in 'YYYY-MM-DD' format.")

        return self.get_live_data(station_id, date)
    
    def get_aqi_data_for_coords(self, coords=None, date=None, hours:int=None):
        """
        Get air quality data for nearest station based on given coordinates.
        Args:
            coords (tuple): A tuple containing (longitude, latitude).
            date (str): Date in 'YYYY-MM-DD' format. Defaults to current date if None.
            hours (int): Hour of the day (0-23). If provided, it will be used to form the complete date-time.
        Returns:
            dict: Air quality data for the specified station and date-time.
        Raises:
            Exception: If the request fails, returns an error, or if invalid parameters are provided.
        """
        if not coords:
            try:                                                                                               
                coords = self.get_system_location()
            except Exception as e:
                raise ValueError(f"Could not determine system location: {e}")
        station_id = self.get_nearest_station(coords)
        return self.get_aqi_data(station_id, date, hours)

