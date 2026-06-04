"""Files use cases (one class per file, each returning a ``Result``)."""

from app.modules.files.application.use_cases.attach_files import AttachFilesUseCase
from app.modules.files.application.use_cases.cleanup_orphans import (
    CleanupOrphansUseCase,
)
from app.modules.files.application.use_cases.complete_upload import (
    CompleteUploadUseCase,
)
from app.modules.files.application.use_cases.delete_file import DeleteFileUseCase
from app.modules.files.application.use_cases.get_file import GetFileUseCase
from app.modules.files.application.use_cases.get_owner_image import (
    GetAvatarUseCase,
    GetCategoryImageUseCase,
    GetPostIconUseCase,
)
from app.modules.files.application.use_cases.list_my_files import ListMyFilesUseCase
from app.modules.files.application.use_cases.list_owner_files import (
    ListOwnerFilesUseCase,
)
from app.modules.files.application.use_cases.request_upload import RequestUploadUseCase
from app.modules.files.application.use_cases.set_avatar import SetAvatarUseCase
from app.modules.files.application.use_cases.set_category_image import (
    SetCategoryImageUseCase,
)
from app.modules.files.application.use_cases.set_post_icon import SetPostIconUseCase
from app.modules.files.application.use_cases.upload_direct import DirectUploadUseCase

__all__ = [
    "AttachFilesUseCase",
    "CleanupOrphansUseCase",
    "CompleteUploadUseCase",
    "DeleteFileUseCase",
    "DirectUploadUseCase",
    "GetAvatarUseCase",
    "GetCategoryImageUseCase",
    "GetPostIconUseCase",
    "GetFileUseCase",
    "ListMyFilesUseCase",
    "ListOwnerFilesUseCase",
    "RequestUploadUseCase",
    "SetAvatarUseCase",
    "SetCategoryImageUseCase",
    "SetPostIconUseCase",
]
