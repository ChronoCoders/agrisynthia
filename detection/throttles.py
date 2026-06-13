from rest_framework.throttling import UserRateThrottle, AnonRateThrottle


class FileUploadAnonThrottle(AnonRateThrottle):
    scope = "file_upload_anon"


class FileUploadUserThrottle(UserRateThrottle):
    scope = "file_upload_user"


class BurstFileUploadThrottle(UserRateThrottle):
    scope = "file_upload_burst"
