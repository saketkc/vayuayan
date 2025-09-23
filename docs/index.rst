cpcbfetch: Central Pollution Control Board Data Fetcher
========================================================

A Python package for fetching and parsing air quality data from Central Pollution Control Board (CPCB India).

.. image:: https://img.shields.io/pypi/v/cpcbfetch.svg
   :target: https://pypi.org/project/cpcbfetch/
   :alt: PyPI version

.. image:: https://img.shields.io/pypi/pyversions/cpcbfetch.svg
   :target: https://pypi.org/project/cpcbfetch/
   :alt: Python versions

.. image:: https://img.shields.io/github/license/saketkc/cpcbfetch.svg
   :target: https://github.com/saketkc/cpcbfetch/blob/master/LICENSE
   :alt: License

Overview
--------

cpcbfetch provides a simple and powerful interface to access pollution monitoring data from India's Central Pollution Control Board. It supports:

- **Air Quality Index (AQI) data**: Historical and real-time air quality measurements
- **PM2.5 data**: Fine particulate matter data for any geographic region using GeoJSON
- **Live monitoring**: Real-time air quality parameters for monitoring stations
- **Geolocation support**: Automatic detection and nearest station finding

Quick Start
-----------

Installation
~~~~~~~~~~~~

.. code-block:: bash

   pip install cpcbfetch

Basic Usage
~~~~~~~~~~~

.. code-block:: python

   from cpcbfetch import AQIClient, LiveAQIClient, PM25Client

   # Initialize clients
   aqi_client = AQIClient()
   live_client = LiveAQIClient()
   pm25_client = PM25Client()

   # Get available states
   states = aqi_client.get_state_list()
   print(states)

   # Get live AQI data for your location
   location = live_client.get_system_location()
   nearest_station = live_client.get_nearest_station()
   live_data = live_client.get_live_aqi_data()

Command Line Interface
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # List available states
   cpcbfetch list_states

   # Get city data for Mumbai in 2024
   cpcbfetch city_data --city "Mumbai" --year 2024 --path "mumbai_aqi.csv"

   # Get live AQI data for your location
   cpcbfetch live_aqi --path "current_aqi.json"

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   installation
   quickstart
   api_reference
   cli_reference
   examples
   contributing

API Reference
=============

.. toctree::
   :maxdepth: 2

   api/cpcbfetch

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

