# cpcbfetch
A Python package for fetching pollution data from central pollution control baord(CPCB).


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
# List cities available in state for AQI
cpcbfetch list_cities "Maharashtra"
```

```bash
# List station available in city for AQI
cpcbfetch list_stations "Mumbai"
```

```bash
# save the whole year of data for specific past year city wise in csv file
cpcbfetch city_data --city "Mumbai" --year 2024 --path "AQI2024.csv"
```

```bash
# save the whole year of data for specific past year station wise in csv file
cpcbfetch station_data --site site_5964 --year 2024 --path "AQI2024.csv"
```

```bash
# Fetch PM2.5 data for particular past year for particular region
cpcbfetch pm25 --geojson_path "path/to/geojson/file.geojson --year 2019 --month 2 --combine True
```

## API Reference

### AQIClient

#### Methods
- `get_state_list()`: Get all available states
- `get_city_list(state)`: Get city list in state
- `get_station_list(city)`: Get station list in city
- `download_past_year_AQI_data_cityLevel(city, year, save_location)`: Get AQI data at city level
- `download_past_year_AQI_data_stationLevel(station_id, year, save_location)`: Get AQI data at station level

### PM25Client

#### Methods
- `get_pm25_stats(geojson_file, year, month)` : Get PM2.5 data for given geographic aread combined
- `get_pm25_stats_by_polygon(geojson_file, year, month, id_field)` : Get Pm2.5 data for all subpolygon inside geojson file

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

This package is not officially affiliated with the Central pollution control board. It's a third-party tool for accessing publicly available pollution data.

## Changelog

### v0.1.0
- Initial release
- Past year AQI data fetching
- City search functionality
- Station search functionality

