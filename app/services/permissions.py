from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.user import User
from app.models.user_access import UserAccess
from app.services.security import get_current_user


DATA_AREAS = ("customers", "transactions", "invoices", "payments")
PAGE_AREAS = ("dashboard", "reports", "insights")
PERMISSION_LABELS = {
    "dashboard.view": "Dashboard",
    "reports.view": "Reports",
    "insights.view": "AI insights",
}
for _area in DATA_AREAS:
    PERMISSION_LABELS.update({
        f"{_area}.view": f"View {_area}",
        f"{_area}.create": f"Add {_area}",
        f"{_area}.edit": f"Edit {_area}",
        f"{_area}.delete": f"Delete {_area}",
    })

ALL_PERMISSIONS = frozenset(PERMISSION_LABELS)
DEFAULT_STAFF_PERMISSIONS = frozenset(
    f"{area}.{action}"
    for area in DATA_AREAS
    for action in ("view", "create", "edit")
)


def permissions_for_user(db: Session, user: User) -> set[str]:
    if user.role == "admin":
        return set(ALL_PERMISSIONS)
    settings = db.get(UserAccess, user.id)
    return set(settings.permissions) if settings is not None else set(DEFAULT_STAFF_PERMISSIONS)


def require_permission(permission: str):
    def check_permission(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if permission not in permissions_for_user(db, user):
            raise HTTPException(status_code=403, detail=f"Permission required: {permission}")
        return user

    return check_permission


def require_any_permission(*permissions: str):
    def check_permission(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        available = permissions_for_user(db, user)
        if not available.intersection(permissions):
            raise HTTPException(status_code=403, detail=f"One of these permissions is required: {', '.join(permissions)}")
        return user

    return check_permission
