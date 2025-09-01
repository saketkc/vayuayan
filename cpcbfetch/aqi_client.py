"""
Main client class for interacting with AQI services
"""

import base64
from wsgiref import headers
import requests
import json
import pandas as pd


class AQIClient:

    def __init__(self):
        """
        Initialize the IMD Weather Client

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
