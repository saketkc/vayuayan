#!/usr/bin/env python3
"""
Command-line interface for cpcbfetch package
"""

import argparse
import json
import sys
from datetime import datetime
from typing import Optional

from . import AQIClient, LiveAQIClient, PM25Client


##------------------------------ CLI Functions ------------------------------ ##
###########################-Past Year Data-#################################
def get_state_list(client: AQIClient) -> None:
    """Display list of states available for AQI data."""
    try:
        complete_list = client.getCompleteList()
        stateList = list(complete_list.get("cities", {}).keys())
        print("Available states for AQI data:")
        for state in stateList:
            print(f" - {state}")
    except Exception as e:
        print(f"❌ Error fetching state list: {e}")
        return


def get_city_list(client: AQIClient, state: str) -> None:
    """Display list of cities available in given state for AQI data"""
    try:
        complete_list = client.getCompleteList()
        cities = complete_list.get("cities", {})
        cityList = []
        if cities and state in cities:
            cityList.extend([city["value"] for city in cities[state]])
        print("Available cities for AQI data:")
        for city in cityList:
            print(f" - {city}")
        return
    except Exception as e:
        print(f"❌ Error fetching city list: {e}")
        return


def get_station_list(client: AQIClient, city: str) -> None:
    """Display station list in form 'station_id(station_name)' available in given city for AQI data"""
    try:
        complete_list = client.getCompleteList()
        stations = complete_list.get("stations", {})
        stationList = []
        if stations and city in stations:
            stationList.extend([f"{station['value']}({station['label']})" for station in stations[city]])
        print("Available stations for AQI data:")
        for station in stationList:
            print(f" - {station}")
        return
    except:
        print("❌ Error fetching station list")
        return


def get_city_data(client: AQIClient, city: str, year: int, path: str) -> None:
    """Display city-level AQI data for a specific year."""
    try:
        data = client.download_past_year_AQI_data_cityLevel(city, str(year), path)
        if isinstance(data, Exception):
            raise data
        print("City-level AQI data overview:")
        print(data)
        print("File saved to the location specified")
    except Exception as e:
        print(f"❌ Error fetching city data: {e}")
    return


def get_station_data(client: AQIClient, station_id: str, year: int, path: str) -> None:
    """Display station-level AQI data for a specific year."""
    try:
        data = client.download_past_year_AQI_data_stationLevel(
            station_id, str(year), path
        )
        if isinstance(data, Exception):
            raise data
        print("Station-level AQI data overview:")
        print(data)
        print("File saved to the location specified")
    except Exception as e:
        print(f"❌ Error fetching station data: {e}")
        return

############################-Live AQI Data-#################################
def locate_me(client: LiveAQIClient) -> None:
    """Fetch current geolocation based on IP address"""
    try:
        coords = client.get_system_location()
        print(f"Current location (lat, lon): {coords}")
    except Exception as e:
        print(f"❌ Error fetching location: {e}")
        return
    
def get_nearest_station(
    client: LiveAQIClient, lat: Optional[float], lon: Optional[float]
) -> None:
    """Fetch nearest station details using IP-based geolocation or provided coordinates"""
    try:
        if lat is not None and lon is not None:
            station_info = client.get_nearest_station((lat, lon))
        else:
            station_info = client.get_nearest_station()
        print("Nearest station details:")
        if isinstance(station_info, (list, tuple)) and len(station_info) == 2:
            station_id, station_name = station_info
            print(f"Station ID: {station_id}")
            print(f"Station Name: {station_name}")
        else:
            print(station_info)
    except Exception as e:
        print(f"❌ Error fetching nearest station: {e}")
        return

def get_live_aqi(
    client: LiveAQIClient,
    lat: Optional[float],
    lon: Optional[float],
    station_id: Optional[str],
    date: Optional[str],
    hour: Optional[int],
    path: Optional[str],
) -> None:
    """Fetch live AQI data for nearest station or specified station"""
    try:
        aqi_data = client.get_live_aqi_data(station_id=station_id, coords=(lat, lon) if lat is not None and lon is not None else None, date=date, hour=hour)
        if isinstance(aqi_data, Exception):
            print(f"❌ {aqi_data}")
        print("Live AQI data:")
        metrics = aqi_data.get('metrics', [])
        if metrics:
            print("Pollutant   Avg   Min   Max   Period")
            print("-" * 40)
            for m in metrics:
                print(f"{m['name']:<10} {m['avg']:<5} {m['min']:<5} {m['max']:<5} {m['avgDesc']}")
        else:
            print("No data available, possibly due to station being offline.")

        if path:
            with open(path, "w") as f:
                json.dump(aqi_data, f, indent=4)
            print(f"File saved to {path}")
    except Exception as e:
        print(f"❌ Error fetching live AQI data: {e}")
        return

############################-PM2.5 Data-#################################
def get_pm25_data(
    client: PM25Client, geojson_path: str, year: int, month: int, combine: bool
) -> None:
    """Fetch and process PM2.5 data for given polygon for given year and month"""
    try:
        if combine:
            combined_data = client.get_pm25_stats(geojson_path, year, month)
            print("Combined PM2.5 data overview:")
            print(combined_data)
        else:
            data = client.get_pm25_stats_by_polygon(geojson_path, year, month)
            print("PM2.5 data overview:")
            print(data)
    except Exception as e:
        print(f"❌ Error fetching PM2.5 data: {e}")
        return


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="cpcbfetch CLI - Get air quality(AQI, PM2.5), Water quality and Noise monitoring data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  cpcbfetch list_states
  cpcbfetch list_cities "Maharashtra"
  cpcbfetch list_stations "Mumbai"
  cpcbfetch city_data --city "Mumbai" --year 2024 --path "output.json"
  cpcbfetch station_data --station_id "site_5964" --year 2024 --path "output.json"

  cpcbfetch locate_me                       # Return lat, lon based on IP
  cpcbfetch nearest_station                 # Uses IP-based geolocation
  cpcbfetch nearest_station --lat 19.0760 --lon 72.8777
  cpcbfetch live_aqi --date 2024-02-25 --hour 10 --path "output.json"   # Uses IP-based geolocation
  cpcbfetch live_aqi --lat 19.0760 --lon 72.8777 --path "output.json"
  cpcbfetch live_aqi --station_id "site_5964" --path "output.json"

  For PM2.5 data:
  cpcbfetch pm25 --geojson_path "path/to/geojson/file.geojson --year 2019 --month 2 --combine True"
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    ## ------------------------------ AQI Commands ------------------------------ ##
    # List states command
    list_states_parser = subparsers.add_parser("list_states", help="List all states")

    # List cities command
    list_cities_parser = subparsers.add_parser(
        "list_cities", help="List all cities in a state"
    )
    list_cities_parser.add_argument("state", help="State name")

    # List stations command
    list_stations_parser = subparsers.add_parser(
        "list_stations", help="List all stations in a city"
    )
    list_stations_parser.add_argument("city", help="City name")

    # City data command
    city_data_parser = subparsers.add_parser(
        "city_data", help="Get city-level AQI data"
    )
    city_data_parser.add_argument("--city", required=True, help="City name")
    city_data_parser.add_argument(
        "--year",
        type=int,
        default=datetime.now().year,
        help="Year (default: current year)",
    )
    city_data_parser.add_argument("--path", required=True, help="Path to output file")

    # Station data command
    station_data_parser = subparsers.add_parser(
        "station_data", help="Get station-level AQI data"
    )
    station_data_parser.add_argument("--station_id", required=True, help="Station ID")
    station_data_parser.add_argument(
        "--year",
        type=int,
        default=datetime.now().year,
        help="Year (default: current year)",
    )
    station_data_parser.add_argument(
        "--path", required=True, help="Path to output file"
    )

    ## ------------------------------ Live AQI Commands ------------------------------ ##
    locate_me_parser = subparsers.add_parser(
        "locate_me", help="Fetch current geolocation based on IP address"
    )
    nearest_station_parser = subparsers.add_parser(
        "nearest_station", help="Fetch nearest station details using IP-based geolocation or provided coordinates"
    )
    nearest_station_parser.add_argument(
        "--lat", type=float, help="Latitude of geolocation"
    )
    nearest_station_parser.add_argument(
        "--lon", type=float, help="Longitude of geolocation"
    )

    live_aqi_parser = subparsers.add_parser(
        "live_aqi", help="Fetch live AQI data for nearest station or specified station"
    )
    live_aqi_parser.add_argument(
        "--lat", type=float, help="Latitude of geolocation"
    )
    live_aqi_parser.add_argument(
        "--lon", type=float, help="Longitude of geolocation"
    )
    live_aqi_parser.add_argument(
        "--station_id", help="Station ID for specific station data"
    )
    live_aqi_parser.add_argument(
        "--date", type=str, help="Date for the AQI data (format: YYYY-MM-DD)"
    )
    live_aqi_parser.add_argument(
        "--hour", type=int, help="Hour for the AQI data (0-23)"
    )
    live_aqi_parser.add_argument(
        "--path", help="Path to output file"
    )

    ## ------------------------------ PM2.5 Commands ------------------------------ ##
    pm25_parser = subparsers.add_parser(
        "pm25", help="Fetch PM2.5 data for given geographic polygon"
    )
    pm25_parser.add_argument(
        "--combine",
        action="store_true",
        help="Combine data within polygon (default: False)",
    )
    pm25_parser.add_argument(
        "--geojson_path", required=True, help="Path to the GeoJSON file with polygon"
    )
    pm25_parser.add_argument(
        "--year", type=int, required=True, help="Year of the netCDF data"
    )
    pm25_parser.add_argument(
        "--month",
        type=int,
        help="Month of the data (1-12), if not provided, annual data is used",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Initialize client
    AQIclient = AQIClient()
    LiveAQIclient = LiveAQIClient()
    PM25client = PM25Client()

    # Execute command
    try:
        if args.command == "list_states":
            get_state_list(AQIclient)
        elif args.command == "list_cities":
            get_city_list(AQIclient, args.state)
        elif args.command == "list_stations":
            get_station_list(AQIclient, args.city)
        elif args.command == "city_data":
            get_city_data(AQIclient, args.city, args.year, args.path)
        elif args.command == "station_data":
            get_station_data(AQIclient, args.station_id, args.year, args.path)
        
        elif args.command == "locate_me":
            locate_me(LiveAQIclient)
        elif args.command == "nearest_station":
            get_nearest_station(LiveAQIclient, args.lat, args.lon)
        elif args.command == "live_aqi":
            get_live_aqi(
                LiveAQIclient,
                args.lat,
                args.lon,
                args.station_id,
                args.date,
                args.hour,
                args.path,
            )

        elif args.command == "pm25":
            get_pm25_data(
                PM25client, args.geojson_path, args.year, args.month, args.combine
            )

    except KeyboardInterrupt:
        print("\n👋 Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
