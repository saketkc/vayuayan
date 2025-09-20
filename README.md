# cpcbfetch
A Python package for fetching pollution data from central pollution control board (CPCB).

## Installation

```bash
pip install git+https://github.com/saketlab/cpcbfetch.git
```

Or install from source:

```bash
git clone https://github.com/saketkc/cpcbfetch.git
cd cpcbfetch
pip install -e .
```

### Command Line Interface

```bash
# List states available for AQI
cpcbfetch list_states
```

```bash
# List cities available in a state for AQI
cpcbfetch list_cities "Maharashtra"
```

```bash
# List stations available in a city for AQI
cpcbfetch list_stations "Mumbai"
```

```bash
# Save the whole year of data for a specific past year city-wise in a CSV file
cpcbfetch city_data --city "Mumbai" --year 2024 --path "AQI2024.csv"
```

```bash
# Save the whole year of data for a specific past year station-wise in a CSV file
cpcbfetch station_data --station_id "site_5964" --year 2024 --path "AQI2024.csv"
```

```bash
# Fetch current geolocation based on IP address
cpcbfetch locate_me
```

```bash
# Fetch nearest station details using IP-based geolocation
cpcbfetch nearest_station
```

```bash
# Fetch nearest station details using provided coordinates
cpcbfetch nearest_station --lat 19.0760 --lon 72.8777
```

```bash
# Fetch live AQI data for the nearest station using IP-based geolocation
cpcbfetch live_aqi --date 2024-02-25 --hour 10 --path "output.json"
```

```bash
# Fetch live AQI data for the nearest station using provided coordinates
cpcbfetch live_aqi --lat 19.0760 --lon 72.8777 --path "output.json"
```

```bash
# Fetch live AQI data for a specific station
cpcbfetch live_aqi --station_id "site_5964" --path "output.json"
```

```bash
# Fetch PM2.5 data for a particular past year for a specific region
cpcbfetch pm25 --geojson_path "path/to/geojson/file.geojson" --year 2019 --month 2 --combine True
```

## API Reference

### AQIClient

#### Methods
- `get_state_list()`: Get all available states
- `get_city_list(state)`: Get city list in a state
- `get_station_list(city)`: Get station list in a city
- `download_past_year_AQI_data_cityLevel(city, year, save_location)`: Get AQI data at the city level
- `download_past_year_AQI_data_stationLevel(station_id, year, save_location)`: Get AQI data at the station level

### LiveAQIClient

#### Methods
- `get_system_location()`: Retrieve the system's approximate latitude and longitude using IP-based geolocation
- `get_nearest_station(coords=None)`: Get the nearest air quality monitoring station based on given coordinates or system location
- `get_live_aqi_data(station_id=None, coords=None, date=None, hour=None)`: Get live air quality parameters for a given station or coordinates and date/time

### PM25Client

#### Methods
- `get_pm25_stats(geojson_file, year, month)`: Get PM2.5 data for a given geographic area combined
- `get_pm25_stats_by_polygon(geojson_file, year, month, id_field)`: Get PM2.5 data for all sub-polygons inside a GeoJSON file

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This package is not officially affiliated with the Central Pollution Control Board. It's a third-party tool for accessing publicly available pollution data.

## Changelog

### v0.1.0
- Initial release
- Past year AQI data fetching
- City search functionality
- Station search functionality

### v0.2.0
- PM2.5 past year data for any region in the world using geoJSON file of the region
- combined data of all polygon inside a geoJSON region
- granular detail of each polygon of geoJSON region

### v0.3.0
- Get system location(latitude and longitude)
- Get nearest station to any location
- Live air quality parameter values
- Currently available for India region only