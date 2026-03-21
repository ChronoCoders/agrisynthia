"""
Custom throttle classes for rate limiting specific operations.
"""

from rest_framework.throttling import UserRateThrottle, AnonRateThrottle


class FileUploadAnonThrottle(AnonRateThrottle):
    """
    Rate limit for anonymous file uploads - very restrictive.
    """

    scope = "file_upload_anon"


class FileUploadUserThrottle(UserRateThrottle):
    """
    Rate limit for authenticated user file uploads.
    """

    scope = "file_upload_user"


class BurstFileUploadThrottle(UserRateThrottle):
    """
    Short-term burst protection for file uploads.
    """

    scope = "file_upload_burst"
