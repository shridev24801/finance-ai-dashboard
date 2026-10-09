from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.user import User
from app.models.user_access import UserAccess
from app.services.permissions import ALL_PERMISSIONS, DEFAULT_STAFF_PERMISSIONS, PERMISSION_LABELS, permissions_for_user
from app.services.security import create_access_token, get_current_user, hash_password, require_admin, verify_password

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name is required")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def public_user(user: User, db: Session):
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role,
            "permissions": sorted(permissions_for_user(db, user))}


@router.post("/register", status_code=201)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    email = str(data.email).lower()
    if db.query(User).filter(func.lower(User.email) == email).first():
        raise HTTPException(status_code=409, detail="Email is already registered")
    role = "admin" if db.query(User).count() == 0 else "staff"
    user = User(name=data.name.strip(), email=email, password=hash_password(data.password), role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"user": public_user(user, db), "access_token": create_access_token(user), "token_type": "bearer"}


@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(func.lower(User.email) == str(data.email).lower()).first()
    if not user or not user.is_active or not verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"user": public_user(user, db), "access_token": create_access_token(user), "token_type": "bearer"}


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return public_user(user, db)


@router.post("/logout")
def logout(user: User = Depends(get_current_user)):
    # Access tokens are short lived; clients must discard their bearer token.
    return {"message": "Logged out. Discard the access token on this device."}


@router.get("/users")
def list_users(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    return [public_user(user, db) | {"is_active": user.is_active, "created_at": user.created_at} for user in db.query(User).order_by(User.id).all()]


@router.get("/permissions")
def list_permissions(_admin: User = Depends(require_admin)):
    return [{"key": key, "label": label} for key, label in PERMISSION_LABELS.items()]


class UserAdminUpdate(BaseModel):
    role: str | None = Field(default=None, pattern="^(admin|staff)$")
    is_active: bool | None = None
    permissions: list[str] | None = None

    @field_validator("permissions")
    @classmethod
    def permissions_must_be_valid(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        invalid = set(value) - ALL_PERMISSIONS
        if invalid:
            raise ValueError(f"Unknown permission: {', '.join(sorted(invalid))}")
        normalized = sorted(set(value))
        if not any(permission.endswith(".view") for permission in normalized):
            raise ValueError("At least one view permission is required for an active account")
        selected = set(normalized)
        for permission in selected:
            area, action = permission.split(".", 1)
            if action != "view" and f"{area}.view" not in selected:
                raise ValueError(f"{area}.view is required when granting {permission}")
        if selected.intersection({"invoices.create", "invoices.edit"}) and "customers.view" not in selected:
            raise ValueError("customers.view is required to create or edit invoices")
        if "payments.create" in selected or "payments.edit" in selected:
            if "invoices.view" not in selected:
                raise ValueError("invoices.view is required to create or edit payments")
        return normalized


@router.patch("/users/{user_id}")
def update_user(user_id: int, data: UserAdminUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    changes = data.model_dump(exclude_unset=True)
    if changes.get("permissions", "missing") is None:
        changes["permissions"] = sorted(DEFAULT_STAFF_PERMISSIONS)
    if target.id == admin.id and (changes.get("role") == "staff" or changes.get("is_active") is False):
        raise HTTPException(status_code=409, detail="You cannot remove your own administrator access")
    removes_active_admin = target.role == "admin" and target.is_active and (
        changes.get("role") == "staff" or changes.get("is_active") is False
    )
    if removes_active_admin:
        other_admins = db.query(User).filter(
            User.role == "admin", User.is_active.is_(True), User.id != target.id
        ).count()
        if other_admins == 0:
            raise HTTPException(status_code=409, detail="At least one active administrator must remain")
    for key, value in changes.items():
        if key == "permissions":
            access = db.get(UserAccess, target.id)
            if access is None:
                access = UserAccess(user_id=target.id, permissions=value or [])
                db.add(access)
            else:
                access.permissions = value or []
            continue
        setattr(target, key, value)
    db.commit()
    return public_user(target, db) | {"is_active": target.is_active}
