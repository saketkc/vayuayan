"""
A Python package for fetching and parsing air quality data from Central Pollution Control Board (CPCB India)
"""

__version__ = "0.1.0"
__author__ = "Saket Choudhary"
__email__ = "saketc@iitb.ac.in"

from .air_quality_client import AQIClient, PM25Client
from .client import CPCBClient

__all__ = ["CPCBClient", "AQIClient", "PM25Client"]
