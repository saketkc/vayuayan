History
=======

Release history and changelog for vayuayan.

v0.1.5 (2026-06-27)
------------------

* Added Google Earth Engine fallback for PM2.5 data when AWS S3 returns 403, with automatic GEE project detection and ``setup_earth_engine()`` helper
* Added support for V5 (V5.GL.05.02, GWR-based) WUSTL ACAG data alongside the default V6

v0.1.4 (2025-11-30)
------------------

* Added ssl fallback
* Return full dataframe for historical data

v0.1.3 (2025-10-12)
------------------

* Fixed documentation link 

v0.1.2 (2025-10-11)
------------------

* Fixed missing logo on PyPI 

v0.1.1 (2025-10-11)
------------------

* Updated installation instructions to use PyPI as primary method

v0.1.0 (2025-10-11)
------------------

* Initial release of vayuayan package
* Support for fetching historical AQI data from CPCB India
* Live air quality monitoring capabilities
* PM2.5 satellite data analysis with GeoJSON polygon support
* Command-line interface for easy data access
* Comprehensive Python API for programmatic access

**Data Sources**

* Central Pollution Control Board (CPCB) India
* WUSTL ACAG PM2.5 satellite data


