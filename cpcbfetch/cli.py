#!/usr/bin/env python3
"""
Command-line interface for cpcbfetch package
"""

import argparse
import json
import sys
from typing import Optional
from datetime import datetime

from . import AQIClient

def get_state_list(client : AQIClient) -> None:
    """Display list of states available for AQI data."""
    try:
        complete_list = client.getCompleteList()
        stateList  = []
        for state in complete_list.get('cities',{}):
            stateList.append(state)
        print("Available states for AQI data:")
        for state in stateList:
            print(f" - {state}")
    except:
        print("❌ Error fetching state list")
        return

def get_city_list(client: AQIClient, state: str) -> None:
    """Display list of cities available in given state for AQI data"""
    try:
        complete_list = client.getCompleteList()
        cityList = []
        cities = complete_list.get('cities',{})
        if(cities and state in cities):
            for city in cities[state]:
                cityList.append(city['value'])
        print("Available cities for AQI data:")
        for city in cityList:
            print(f" - {city}")
        return 
    except:
        print("❌ Error fetching city list")
        return

def get_station_list(client: AQIClient, city: str) -> None:
    """Display station list in form 'station_id(station_name)' available in given city for AQI data"""
    try:
        complete_list = client.getCompleteList()
        stationList = []
        stations = complete_list.get('stations', {})
        if(stations and city in stations):
            for station in stations[city]:
                stationList.append(f"{station['value']}({station['label']})")
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
        data = client.download_past_year_AQI_data_stationLevel(station_id, str(year), path)
        if isinstance(data, Exception):
            raise data
        print("Station-level AQI data overview:")
        print(data)
        print("File saved to the location specified")
    except Exception as e:
        print(f"❌ Error fetching station data: {e}")
        return

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="cpcbfetch CLI - Get air quality, Water quality and Noise monitoring data from Central Pollution Control Board",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  cpcbfetch list_states
  cpcbfetch list_cities "Maharashtra"
  cpcbfetch list_stations "Mumbai"
  cpcbfetch city_data --city "Mumbai" --year 2024 --path "output.json"
  cpcbfetch station_data --station_id "site_5964" --year 2024 --path "output.json"
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # List states command
    list_states_parser = subparsers.add_parser("list_states", help="List all states")

    # List cities command
    list_cities_parser = subparsers.add_parser("list_cities", help="List all cities in a state")
    list_cities_parser.add_argument("state", help="State name")

    # List stations command
    list_stations_parser = subparsers.add_parser("list_stations", help="List all stations in a city")
    list_stations_parser.add_argument("city", help="City name")

    # City data command
    city_data_parser = subparsers.add_parser("city_data", help="Get city-level AQI data")
    city_data_parser.add_argument("--city", required=True, help="City name")
    city_data_parser.add_argument("--year", type=int, default=datetime.now().year, help="Year (default: current year)")
    city_data_parser.add_argument("--path", required=True, help="Path to output file")

    # Station data command
    station_data_parser = subparsers.add_parser("station_data", help="Get station-level AQI data")
    station_data_parser.add_argument("--station_id", required=True, help="Station ID")
    station_data_parser.add_argument("--year", type=int, default=datetime.now().year, help="Year (default: current year)")
    station_data_parser.add_argument("--path", required=True, help="Path to output file")


    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Initialize client
    client = AQIClient()

    # Execute command
    try:
        if args.command == "list_states":
            get_state_list(client)
        elif args.command == "list_cities":
            get_city_list(client, args.state)
        elif args.command == "list_stations":
            get_station_list(client, args.city)
        elif args.command == "city_data":
            get_city_data(client, args.city, args.year, args.path)
        elif args.command == "station_data":
            get_station_data(client, args.station_id, args.year, args.path)

    except KeyboardInterrupt:
        print("\n👋 Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
