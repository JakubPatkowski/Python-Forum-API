"""Dependency-Injection container for the application.

Each ``get_*`` callable here is consumed by FastAPI through
``Annotated[..., Depends(get_*)]``. Stateless singletons (event bus, hasher,
token service) are cached with ``functools.lru_cache``; per-request
objects (UoW, use cases) are not, so each request gets a fresh session.
"""

from __future__ import annotations

from functools import lru_cache

from app.modules.content.application.ports import IContentUnitOfWork
from app.modules.content.application.use_cases import (
    AddCommentUseCase,
    CreateCategoryUseCase,
    CreatePostUseCase,
    CreateTagUseCase,
    DeleteCategoryUseCase,
    DeleteCommentUseCase,
    DeletePostUseCase,
    GetCommentTreeUseCase,
    GetPostUseCase,
    ListCategoriesUseCase,
    ListPostsUseCase,
    ListTagsUseCase,
    UpdateCommentUseCase,
    UpdatePostUseCase,
)
from app.modules.content.infrastructure import SqlAlchemyContentUnitOfWork
from app.modules.files.application.ports import (
    IFileProcessor,
    IFileStorage,
    IFilesUnitOfWork,
)
from app.modules.files.application.use_cases import (
    AttachFilesUseCase,
    CleanupOrphansUseCase,
    CompleteUploadUseCase,
    DeleteFileUseCase,
    DirectUploadUseCase,
    GetAvatarUseCase,
    GetCategoryImageUseCase,
    GetFileUseCase,
    GetPostIconUseCase,
    ListMyFilesUseCase,
    ListOwnerFilesUseCase,
    RequestUploadUseCase,
    SetAvatarUseCase,
    SetCategoryImageUseCase,
    SetPostIconUseCase,
)
from app.modules.files.infrastructure import (
    MinioFileStorage,
    PillowFileProcessor,
    SqlAlchemyFilesUnitOfWork,
)
from app.modules.identity.application.ports import (
    IIdentityUnitOfWork,
    IPasswordHasher,
    ITokenService,
)
from app.modules.identity.application.use_cases import (
    AssignRoleUseCase,
    DenyPermissionUseCase,
    GrantPermissionUseCase,
    LoginUseCase,
    LogoutAllUseCase,
    LogoutUseCase,
    RefreshSessionUseCase,
    RegisterUserUseCase,
    RevokeRoleUseCase,
    SetUserStatusUseCase,
)
from app.modules.identity.infrastructure.auth import (
    Argon2Hasher,
    PyJWTTokenService,
)
from app.modules.identity.infrastructure.unit_of_work import (
    SqlAlchemyIdentityUnitOfWork,
)
from app.shared.application.event_bus import IEventBus
from app.shared.infrastructure.db import SessionLocal
from app.shared.infrastructure.eventbus import InMemoryEventBus

# --------------------------------------------------------------------------- #
# Singletons                                                                  #
# --------------------------------------------------------------------------- #


@lru_cache
def get_event_bus() -> IEventBus:
    """In-memory bus until phase 4 swaps in RabbitMQ."""
    return InMemoryEventBus()


@lru_cache
def get_password_hasher() -> IPasswordHasher:
    return Argon2Hasher()


@lru_cache
def get_token_service() -> ITokenService:
    return PyJWTTokenService()


# --------------------------------------------------------------------------- #
# Per-request                                                                 #
# --------------------------------------------------------------------------- #


def get_identity_uow() -> IIdentityUnitOfWork:
    """A fresh UoW per FastAPI request. Caller must ``async with`` it."""
    return SqlAlchemyIdentityUnitOfWork(SessionLocal)


def get_content_uow() -> IContentUnitOfWork:
    """A fresh content UoW per FastAPI request."""
    return SqlAlchemyContentUnitOfWork(SessionLocal)


# --------------------------------------------------------------------------- #
# Use case providers                                                          #
# --------------------------------------------------------------------------- #


def get_register_user_uc() -> RegisterUserUseCase:
    return RegisterUserUseCase(
        uow=get_identity_uow(),
        hasher=get_password_hasher(),
        bus=get_event_bus(),
    )


def get_login_uc() -> LoginUseCase:
    return LoginUseCase(
        uow=get_identity_uow(),
        hasher=get_password_hasher(),
        tokens=get_token_service(),
        bus=get_event_bus(),
    )


def get_refresh_uc() -> RefreshSessionUseCase:
    return RefreshSessionUseCase(
        uow=get_identity_uow(),
        tokens=get_token_service(),
        bus=get_event_bus(),
    )


def get_logout_uc() -> LogoutUseCase:
    return LogoutUseCase(
        uow=get_identity_uow(),
        tokens=get_token_service(),
        bus=get_event_bus(),
    )


def get_logout_all_uc() -> LogoutAllUseCase:
    return LogoutAllUseCase(uow=get_identity_uow(), bus=get_event_bus())


def get_assign_role_uc() -> AssignRoleUseCase:
    return AssignRoleUseCase(uow=get_identity_uow(), bus=get_event_bus())


def get_revoke_role_uc() -> RevokeRoleUseCase:
    return RevokeRoleUseCase(uow=get_identity_uow(), bus=get_event_bus())


def get_grant_permission_uc() -> GrantPermissionUseCase:
    return GrantPermissionUseCase(uow=get_identity_uow(), bus=get_event_bus())


def get_deny_permission_uc() -> DenyPermissionUseCase:
    return DenyPermissionUseCase(uow=get_identity_uow(), bus=get_event_bus())


def get_set_user_status_uc() -> SetUserStatusUseCase:
    return SetUserStatusUseCase(uow=get_identity_uow(), bus=get_event_bus())


# --------------------------------------------------------------------------- #
# Content module use cases                                                    #
# --------------------------------------------------------------------------- #


def get_create_post_uc() -> CreatePostUseCase:
    return CreatePostUseCase(uow=get_content_uow(), bus=get_event_bus())


def get_update_post_uc() -> UpdatePostUseCase:
    return UpdatePostUseCase(uow=get_content_uow(), bus=get_event_bus())


def get_delete_post_uc() -> DeletePostUseCase:
    return DeletePostUseCase(uow=get_content_uow(), bus=get_event_bus())


def get_get_post_uc() -> GetPostUseCase:
    return GetPostUseCase(uow=get_content_uow())


def get_list_posts_uc() -> ListPostsUseCase:
    return ListPostsUseCase(uow=get_content_uow())


def get_add_comment_uc() -> AddCommentUseCase:
    return AddCommentUseCase(uow=get_content_uow(), bus=get_event_bus())


def get_update_comment_uc() -> UpdateCommentUseCase:
    return UpdateCommentUseCase(uow=get_content_uow(), bus=get_event_bus())


def get_delete_comment_uc() -> DeleteCommentUseCase:
    return DeleteCommentUseCase(uow=get_content_uow(), bus=get_event_bus())


def get_comment_tree_uc() -> GetCommentTreeUseCase:
    return GetCommentTreeUseCase(uow=get_content_uow())


def get_create_category_uc() -> CreateCategoryUseCase:
    return CreateCategoryUseCase(uow=get_content_uow(), bus=get_event_bus())


def get_delete_category_uc() -> DeleteCategoryUseCase:
    return DeleteCategoryUseCase(uow=get_content_uow(), bus=get_event_bus())


def get_list_categories_uc() -> ListCategoriesUseCase:
    return ListCategoriesUseCase(uow=get_content_uow())


def get_create_tag_uc() -> CreateTagUseCase:
    return CreateTagUseCase(uow=get_content_uow(), bus=get_event_bus())


def get_list_tags_uc() -> ListTagsUseCase:
    return ListTagsUseCase(uow=get_content_uow())


# --------------------------------------------------------------------------- #
# Files module — storage singletons, UoW, use cases                           #
# --------------------------------------------------------------------------- #


@lru_cache
def get_file_storage() -> IFileStorage:
    """MinIO client wrapper (singleton — holds connection pools)."""
    return MinioFileStorage()


@lru_cache
def get_file_processor() -> IFileProcessor:
    """libmagic + Pillow content processor (stateless singleton)."""
    return PillowFileProcessor()


def get_files_uow() -> IFilesUnitOfWork:
    """A fresh files UoW per FastAPI request."""
    return SqlAlchemyFilesUnitOfWork(SessionLocal)


def get_request_upload_uc() -> RequestUploadUseCase:
    return RequestUploadUseCase(uow=get_files_uow(), storage=get_file_storage())


def get_complete_upload_uc() -> CompleteUploadUseCase:
    return CompleteUploadUseCase(
        uow=get_files_uow(),
        storage=get_file_storage(),
        processor=get_file_processor(),
        bus=get_event_bus(),
    )


def get_direct_upload_uc() -> DirectUploadUseCase:
    return DirectUploadUseCase(
        uow=get_files_uow(),
        storage=get_file_storage(),
        processor=get_file_processor(),
        bus=get_event_bus(),
    )


def get_get_file_uc() -> GetFileUseCase:
    return GetFileUseCase(uow=get_files_uow(), storage=get_file_storage())


def get_list_my_files_uc() -> ListMyFilesUseCase:
    return ListMyFilesUseCase(uow=get_files_uow(), storage=get_file_storage())


def get_list_owner_files_uc() -> ListOwnerFilesUseCase:
    return ListOwnerFilesUseCase(uow=get_files_uow(), storage=get_file_storage())


def get_attach_files_uc() -> AttachFilesUseCase:
    return AttachFilesUseCase(uow=get_files_uow(), storage=get_file_storage(), bus=get_event_bus())


def get_delete_file_uc() -> DeleteFileUseCase:
    return DeleteFileUseCase(uow=get_files_uow(), storage=get_file_storage(), bus=get_event_bus())


def get_set_avatar_uc() -> SetAvatarUseCase:
    return SetAvatarUseCase(
        uow=get_files_uow(),
        storage=get_file_storage(),
        processor=get_file_processor(),
        bus=get_event_bus(),
    )


def get_set_category_image_uc() -> SetCategoryImageUseCase:
    return SetCategoryImageUseCase(
        uow=get_files_uow(),
        storage=get_file_storage(),
        processor=get_file_processor(),
        bus=get_event_bus(),
    )


def get_get_avatar_uc() -> GetAvatarUseCase:
    return GetAvatarUseCase(uow=get_files_uow(), storage=get_file_storage())


def get_get_category_image_uc() -> GetCategoryImageUseCase:
    return GetCategoryImageUseCase(uow=get_files_uow(), storage=get_file_storage())


def get_set_post_icon_uc() -> SetPostIconUseCase:
    return SetPostIconUseCase(
        uow=get_files_uow(),
        storage=get_file_storage(),
        processor=get_file_processor(),
        bus=get_event_bus(),
    )


def get_get_post_icon_uc() -> GetPostIconUseCase:
    return GetPostIconUseCase(uow=get_files_uow(), storage=get_file_storage())


def get_cleanup_orphans_uc() -> CleanupOrphansUseCase:
    return CleanupOrphansUseCase(
        uow=get_files_uow(), storage=get_file_storage(), bus=get_event_bus()
    )
