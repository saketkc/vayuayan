"""
Custom exceptions for CPCB  package
"""


class CPCBError(Exception):
    """Base exception for all CPCB  related errors"""

    pass


class NetworkError(CPCBError):
    """Raised when network requests fail"""

    pass


class DataParsingError(CPCBError):
    """Raised when data parsing fails"""

    pass


class CityNotFoundError(CPCBError):
    """Raised when a city is not found in the CPCB database"""

    pass


class InvalidDataError(CPCBError):
    """Raised when received data is invalid or corrupted"""

    pass
