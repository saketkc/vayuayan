# Jupyter Notebook Examples for cpcbfetch

This directory contains interactive Jupyter notebooks demonstrating various use cases of the cpcbfetch package.

## 📚 Available Notebooks

### 1. Getting Started (`01_getting_started.ipynb`)
**Difficulty:** Beginner

Learn the basics of cpcbfetch:
- Installing and importing the package
- Exploring available states, cities, and monitoring stations
- Getting your location and finding nearest stations
- Fetching real-time air quality data
- Downloading historical AQI data

**Prerequisites:** Basic Python knowledge

---

### 2. Historical Data Analysis (`02_historical_data_analysis.ipynb`)
**Difficulty:** Intermediate

Analyze historical AQI trends:
- Downloading city-level historical data
- Data preprocessing and cleaning
- Statistical analysis and visualization
- Monthly and seasonal trend analysis
- Identifying worst air quality days
- Analyzing individual pollutant levels

**Prerequisites:** Familiarity with pandas and matplotlib

---

### 3. Live Monitoring (`03_live_monitoring.ipynb`)
**Difficulty:** Intermediate

Real-time air quality monitoring:
- Finding your location automatically
- Locating nearest monitoring stations
- Continuous monitoring setup
- Creating air quality alerts
- Visualizing real-time data
- Exporting monitoring logs

**Prerequisites:** Basic understanding of time series data

---

### 4. PM2.5 Regional Analysis (`04_pm25_regional_analysis.ipynb`)
**Difficulty:** Advanced

Analyze PM2.5 data for geographic regions:
- Working with GeoJSON files
- Creating custom geographic boundaries
- Analyzing PM2.5 statistics for regions
- Multi-polygon analysis
- Temporal comparison across months
- Creating choropleth maps

**Prerequisites:** Understanding of GeoJSON, geopandas, and spatial data

---

## 🚀 Getting Started

### Installation

1. Install cpcbfetch:
```bash
pip install cpcbfetch
```

2. Install Jupyter:
```bash
pip install jupyter
```

3. Install additional dependencies for notebooks:
```bash
pip install pandas matplotlib seaborn geopandas
```

### Running the Notebooks

1. Navigate to the notebooks directory:
```bash
cd notebooks
```

2. Start Jupyter:
```bash
jupyter notebook
```

3. Open any notebook and follow the instructions!

## 📊 Data Requirements

- **Notebooks 1-3:** Work out of the box with real-time CPCB data
- **Notebook 4 (PM2.5):** Requires netCDF files for PM2.5 data
  - Download from: https://sites.wustl.edu/acag/datasets/surface-pm2-5/
  - Place files in the `examples/` directory or update paths in the notebook

## 🎯 Use Cases

These notebooks cover:

- ✅ **Data Exploration:** Discover available monitoring stations and locations
- ✅ **Real-time Monitoring:** Track air quality changes as they happen
- ✅ **Historical Analysis:** Understand pollution trends over time
- ✅ **Geographic Analysis:** Analyze air quality across different regions
- ✅ **Visualization:** Create informative plots and maps
- ✅ **Alert Systems:** Set up notifications for unhealthy air quality

## 💡 Tips

1. **Start with Notebook 1** if you're new to cpcbfetch
2. **Uncomment code blocks** marked with `# Uncomment to run` when you're ready to execute them
3. **Customize locations** by changing coordinates to your area of interest
4. **Save your work** frequently - some analyses may take time
5. **Check data availability** - historical data may not be complete for all locations

## 🔧 Troubleshooting

### Common Issues

**Import errors:**
```bash
pip install --upgrade cpcbfetch pandas matplotlib geopandas
```

**Network timeouts:**
- Check your internet connection
- Some CPCB endpoints may be temporarily unavailable
- Try again after a few minutes

**Missing data:**
- Not all cities have complete historical data
- Some monitoring stations may be offline
- PM2.5 netCDF files must be downloaded separately

## 📖 Additional Resources

- **Full Documentation:** https://cpcbfetch.readthedocs.io/
- **GitHub Repository:** https://github.com/saketkc/cpcbfetch
- **Issue Tracker:** https://github.com/saketkc/cpcbfetch/issues

## 🤝 Contributing

Have an interesting analysis or use case? Consider contributing:

1. Create a new notebook with your analysis
2. Follow the existing notebook structure
3. Add clear documentation and comments
4. Submit a pull request

## 📝 License

These notebooks are part of the cpcbfetch package and are distributed under the MIT License.

---

**Happy Analyzing! 🌍💚**

For questions or issues, please visit the [GitHub repository](https://github.com/saketkc/cpcbfetch).
