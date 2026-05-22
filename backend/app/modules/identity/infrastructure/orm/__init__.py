"""SQLAlchemy ORM models for the identity module.

Importing this package registers all mappers on the shared ``Base.metadata``,
so Alembic's autogenerate sees them.
"""

from app.modules.identity.infrastructure.orm.permission_orm import PermissionOrm
from app.modules.identity.infrastructure.orm.refresh_token_orm import (
    RefreshTokenOrm,
)
from app.modules.identity.infrastructure.orm.role_orm import (
    RoleOrm,
    RolePermissionOrm,
)
from app.modules.identity.infrastructure.orm.user_orm import (
    UserOrm,
    UserPermissionOrm,
    UserRoleOrm,
)

__all__ = [
    "PermissionOrm",
    "RefreshTokenOrm",
    "RoleOrm",
    "RolePermissionOrm",
    "UserOrm",
    "UserPermissionOrm",
    "UserRoleOrm",
]
