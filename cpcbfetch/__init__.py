"""
A Python package for fetching and parsing air quality data from Central Pollution Control Board (CPCB India)
"""

__version__ = "0.1.0"
__author__ = "Saket Choudhary"
__email__ = "saketc@iitb.ac.in"

from .client import CPCBClient
from .air_quality_client import AQIClient

__all__ = [
    "CPCBClient",
    "AQIClient",
]
