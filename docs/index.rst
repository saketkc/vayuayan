vayuayan: Collect and Analyze Air Quality and Pollution Data
========================================================

A Python package for fetching and analysing air quality data from multiple sources worldwide:

.. image:: https://img.shields.io/pypi/v/vayuayan.svg
   :target: https://pypi.org/project/vayuayan/
   :alt: PyPI version

.. image:: https://img.shields.io/pypi/pyversions/vayuayan.svg
   :target: https://pypi.org/project/vayuayan/
   :alt: Python versions

.. image:: https://img.shields.io/github/license/saketkc/vayuayan.svg
   :target: https://github.com/saketkc/vayuayan/blob/master/LICENSE
   :alt: License

Overview
--------

vayuayan provides a simple and powerful interface to access pollution monitoring data from India's Central Pollution Control Board and WUSTL ACAG. It supports:

- **Air Quality Index (AQI) data**: Historical and real-time air quality measurements
- **PM2.5 data**: Fine particulate matter data for any geographic region using GeoJSON
- **Live monitoring**: Real-time air quality parameters for monitoring stations
- **Geolocation support**: Automatic detection and nearest station finding

Quick Start
-----------

Installation
~~~~~~~~~~~~

.. code-block:: bash

   pip install vayuayan

Basic Usage
~~~~~~~~~~~

.. code-block:: python

   from vayuayan import CPCBHistorical, CPCBLive, PM25Client

   # Initialize clients
   aqi_client = CPCBHistorical()
   live_client = CPCBLive()
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
   vayuayan list_states

   # Get city data for Mumbai in 2024
   vayuayan city_data --city "Mumbai" --year 2024 --path "mumbai_aqi.csv"

   # Get live AQI data for your location
   vayuayan live_aqi --path "current_aqi.json"

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   installation
   quickstart
   api_reference
   cli_reference
   examples
   notebooks
   contributing

Jupyter Notebooks
==================

Interactive Jupyter notebooks with hands-on examples are available in the ``notebooks/`` directory:

1. **Getting Started** - Learn the basics of vayuayan
2. **Historical Data Analysis** - Analyze AQI trends and patterns
3. **Live Monitoring** - Real-time air quality monitoring
4. **PM2.5 Regional Analysis** - Geographic analysis using GeoJSON

To run the notebooks::

   pip install vayuayan[notebooks]
   cd notebooks
   jupyter notebook

See the notebooks README for detailed information about each notebook.

API Reference
=============

.. toctree::
   :maxdepth: 2

   api/vayuayan

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

