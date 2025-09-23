Command Line Interface
======================

The cpcbfetch command line interface provides convenient access to all package functionality.

Basic Usage
-----------

.. code-block:: bash

   cpcbfetch [command] [options]

To see all available commands:

.. code-block:: bash

   cpcbfetch --help

Data Discovery Commands
-----------------------

list_states
~~~~~~~~~~~

List all available states for AQI data.

.. code-block:: bash

   cpcbfetch list_states

list_cities
~~~~~~~~~~~

List cities available in a specific state.

.. code-block:: bash

   cpcbfetch list_cities "Maharashtra"

list_stations
~~~~~~~~~~~~~

List monitoring stations in a specific city.

.. code-block:: bash

   cpcbfetch list_stations "Mumbai"

Historical Data Commands
------------------------

city_data
~~~~~~~~~

Download yearly AQI data for a specific city.

.. code-block:: bash

   cpcbfetch city_data --city "Mumbai" --year 2024 --path "mumbai_aqi.csv"

**Parameters:**

- ``--city``: Name of the city (required)
- ``--year``: Year for data (required)
- ``--path``: Output file path (required)

station_data
~~~~~~~~~~~~

Download yearly AQI data for a specific monitoring station.

.. code-block:: bash

   cpcbfetch station_data --station_id "site_5964" --year 2024 --path "station_aqi.csv"

**Parameters:**

- ``--station_id``: ID of the monitoring station (required)
- ``--year``: Year for data (required)  
- ``--path``: Output file path (required)

Live Data Commands
------------------

locate_me
~~~~~~~~~

Get your current location based on IP address.

.. code-block:: bash

   cpcbfetch locate_me

nearest_station
~~~~~~~~~~~~~~~

Find the nearest air quality monitoring station.

.. code-block:: bash

   # Using IP-based geolocation
   cpcbfetch nearest_station

   # Using specific coordinates
   cpcbfetch nearest_station --lat 19.0760 --lon 72.8777

**Parameters:**

- ``--lat``: Latitude (optional, uses IP location if not provided)
- ``--lon``: Longitude (optional, uses IP location if not provided)

live_aqi
~~~~~~~~

Get live air quality data.

.. code-block:: bash

   # For your current location
   cpcbfetch live_aqi --path "current_aqi.json"

   # For specific coordinates
   cpcbfetch live_aqi --lat 19.0760 --lon 72.8777 --path "mumbai_aqi.json"

   # For specific station
   cpcbfetch live_aqi --station_id "site_5964" --path "station_aqi.json"

   # For specific date and time
   cpcbfetch live_aqi --date 2024-02-25 --hour 10 --path "historical_aqi.json"

**Parameters:**

- ``--lat``: Latitude (optional)
- ``--lon``: Longitude (optional)
- ``--station_id``: Station ID (optional)
- ``--date``: Date in YYYY-MM-DD format (optional)
- ``--hour``: Hour (0-23) (optional)
- ``--path``: Output file path (required)

PM2.5 Data Commands
-------------------

pm25
~~~~

Get PM2.5 data for geographic regions defined by GeoJSON files.

.. code-block:: bash

   # Get combined data for entire region
   cpcbfetch pm25 --geojson_path "region.geojson" --year 2024 --month 3 --combine

   # Get data for each polygon separately
   cpcbfetch pm25 --geojson_path "region.geojson" --year 2024 --month 3

**Parameters:**

- ``--geojson_path``: Path to GeoJSON file defining the region (required)
- ``--year``: Year for data (required)
- ``--month``: Month (1-12) (optional, annual data if not provided)
- ``--combine``: Combine data within polygon (flag)

Help and Information
--------------------

cli-help
~~~~~~~~

Get detailed help for the CLI:

.. code-block:: bash

   cpcbfetch --help

Examples
--------

Complete Workflow Example
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # 1. Find your location
   cpcbfetch locate_me

   # 2. Find nearest station
   cpcbfetch nearest_station

   # 3. Get current AQI
   cpcbfetch live_aqi --path "current_aqi.json"

   # 4. Explore available data
   cpcbfetch list_states
   cpcbfetch list_cities "Maharashtra"
   cpcbfetch list_stations "Mumbai"

   # 5. Download historical data
   cpcbfetch city_data --city "Mumbai" --year 2024 --path "mumbai_2024.csv"

Error Handling
--------------

The CLI provides clear error messages and exit codes:

- **Exit code 0**: Success
- **Exit code 1**: General error or user interruption
- **Exit code 2**: Invalid arguments or usage

Common error scenarios and solutions:

- **Network timeout**: Check internet connection and try again
- **Invalid city/station**: Use list commands to find valid names/IDs
- **File permission errors**: Ensure write access to output directory
- **Invalid coordinates**: Check latitude (-90 to 90) and longitude (-180 to 180) ranges