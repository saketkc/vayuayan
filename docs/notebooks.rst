Jupyter Notebooks
=================

Interactive Jupyter notebooks provide hands-on examples for learning and using vayuayan effectively.

Overview
--------

The notebooks are located in the ``notebooks/`` directory of the repository and cover various use cases from beginner to advanced levels.

Installation
------------

To use the notebooks, install the package with notebook dependencies:

.. code-block:: bash

   pip install vayuayan[notebooks]

This will install:

- jupyter - for running notebooks
- matplotlib - for plotting
- seaborn - for enhanced visualizations

Starting Jupyter
-----------------

Navigate to the notebooks directory and start Jupyter:

.. code-block:: bash

   cd notebooks
   jupyter notebook

Available Notebooks
-------------------

1. Getting Started
~~~~~~~~~~~~~~~~~~

**File:** ``01_getting_started.ipynb``

**Level:** Beginner

**Topics Covered:**

- Package installation and imports
- Exploring available data (states, cities, stations)
- Finding your location
- Getting real-time air quality data
- Downloading historical AQI data

**Ideal for:** First-time users learning the basics

2. Historical Data Analysis
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**File:** ``02_historical_data_analysis.ipynb``

**Level:** Intermediate

**Topics Covered:**

- Downloading city-level historical data
- Data cleaning and preprocessing
- Statistical analysis
- Time series visualization
- Monthly trend analysis
- Identifying worst pollution days
- Pollutant-level analysis

**Prerequisites:** Basic pandas and matplotlib knowledge

3. Live Monitoring
~~~~~~~~~~~~~~~~~~

**File:** ``03_live_monitoring.ipynb``

**Level:** Intermediate

**Topics Covered:**

- Auto-detecting location
- Finding nearest monitoring stations
- Fetching real-time air quality
- Continuous monitoring setup
- Creating air quality alerts
- Data logging and export

**Use Cases:** Real-time monitoring systems, alerting applications

4. PM2.5 Regional Analysis
~~~~~~~~~~~~~~~~~~~~~~~~~~

**File:** ``04_pm25_regional_analysis.ipynb``

**Level:** Advanced

**Topics Covered:**

- Working with GeoJSON boundaries
- Regional PM2.5 statistics
- Multi-polygon analysis
- Temporal comparisons
- Choropleth mapping
- Spatial data visualization

**Prerequisites:** Understanding of GeoJSON and spatial data

**Requirements:** PM2.5 netCDF data files

Data Requirements
-----------------

Most notebooks work with real-time CPCB data without additional setup. However:

**PM2.5 Analysis (Notebook 4):**

Requires netCDF files with PM2.5 data. Download from:

https://sites.wustl.edu/acag/datasets/surface-pm2-5/

Place files in the ``examples/`` directory or update paths in the notebook.

Running the Notebooks
---------------------

1. Open Jupyter Notebook in the notebooks directory
2. Select a notebook to open
3. Read through the markdown cells for context
4. Run code cells sequentially (Shift+Enter)
5. Modify and experiment with the code
6. Uncomment code blocks marked with ``# Uncomment to run``

Tips for Success
----------------

**For Beginners:**

- Start with Notebook 1 (Getting Started)
- Run cells one at a time and observe outputs
- Read the explanatory text carefully
- Try changing parameters to see different results

**For Intermediate Users:**

- Modify the notebooks for your region of interest
- Combine techniques from multiple notebooks
- Export and analyze data further

**For Advanced Users:**

- Use notebooks as templates for custom analyses
- Integrate with other data sources
- Create automated reports
- Build production pipelines

Common Issues
-------------

Import Errors
~~~~~~~~~~~~~

.. code-block:: bash

   pip install --upgrade vayuayan pandas matplotlib seaborn geopandas

Network Timeouts
~~~~~~~~~~~~~~~~

- Check internet connection
- CPCB endpoints may be temporarily unavailable
- Retry after a few minutes

Missing Data
~~~~~~~~~~~~

- Not all locations have complete historical data
- Some monitoring stations may be offline
- PM2.5 netCDF files must be downloaded separately

Kernel Issues
~~~~~~~~~~~~~

If the kernel becomes unresponsive:

- Kernel → Restart
- Re-run cells from the beginning

Customization
-------------

You can customize the notebooks for your needs:

**Change Location:**

.. code-block:: python

   # Instead of using system location
   location = client.get_system_location()
   
   # Use specific coordinates
   lat = 19.0760  # Your latitude
   lon = 72.8777  # Your longitude
   coords = (lat, lon)

**Modify Time Ranges:**

.. code-block:: python

   # Analyze different years or months
   year = 2023
   months = range(1, 13)  # All months

**Custom Regions:**

Create your own GeoJSON files for analyzing specific areas:

.. code-block:: python

   # Define custom polygon
   custom_region = {
       "type": "FeatureCollection",
       "features": [{
           "type": "Feature",
           "properties": {"name": "My Region"},
           "geometry": {
               "type": "Polygon",
               "coordinates": [[
                   [lon1, lat1],
                   [lon2, lat2],
                   [lon3, lat3],
                   [lon4, lat4],
                   [lon1, lat1]  # Close polygon
               ]]
           }
       }]
   }

Contributing Notebooks
----------------------

Have an interesting analysis? Contribute a new notebook:

1. Create a new notebook following the existing structure
2. Include clear documentation and comments
3. Add to the notebooks README
4. Submit a pull request

Guidelines:

- Clear, descriptive markdown cells
- Well-commented code
- Example outputs included
- Error handling demonstrated
- Follow existing naming conventions

Further Resources
-----------------

- **Complete Documentation:** https://vayuayan.readthedocs.io/
- **Source Code:** https://github.com/saketkc/vayuayan
- **Issues & Support:** https://github.com/saketkc/vayuayan/issues

Next Steps
----------

After working through the notebooks:

- Explore the :doc:`examples` for more code snippets
- Check the :doc:`api_reference` for detailed API documentation
- Review the :doc:`cli_reference` for command-line usage
- See :doc:`contributing` to contribute to the project
