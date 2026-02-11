from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.deps import require_permissions
from app.db.session import get_session
from app.models.role import Permission, Role, role_permissions, user_roles
from app.models.user import User

router = APIRouter(prefix="/rbac")


def _role_out(r: Role) -> dict:
    return {
        "id": r.id,
        "code": r.code,
        "name": r.name,
        "description": r.description,
        "isSystem": bool(r.is_system),
        "permissions": [
            {"id": p.id, "code": p.code, "name": p.name, "description": p.description, "isSystem": bool(p.is_system)}
            for p in (r.permissions or [])
        ],
    }


def _perm_out(p: Permission) -> dict:
    return {
        "id": p.id,
        "code": p.code,
        "name": p.name,
        "description": p.description,
        "isSystem": bool(p.is_system),
    }


class RoleCreateIn(BaseModel):
    code: str
    name: str
    description: str | None = None


class RoleUpdateIn(BaseModel):
    name: str | None = None
    description: str | None = None


class PermissionCreateIn(BaseModel):
    code: str
    name: str
    description: str | None = None


class PermissionUpdateIn(BaseModel):
    name: str | None = None
    description: str | None = None


@router.get("/roles", dependencies=[Depends(require_permissions("rbac:manage"))])
async def list_roles(session: AsyncSession = Depends(get_session)) -> list[dict]:
    rows = (
        await session.execute(
            select(Role).options(selectinload(Role.permissions)).order_by(Role.code.asc())
        )
    ).scalars().all()
    return [_role_out(r) for r in rows]


@router.post("/roles", dependencies=[Depends(require_permissions("rbac:manage"))])
async def create_role(payload: RoleCreateIn, session: AsyncSession = Depends(get_session)) -> dict:
    code = payload.code.strip()
    name = payload.name.strip()
    if not code or not name:
        raise HTTPException(status_code=400, detail={"code": "VALIDATION", "message": "code and name are required"})

    existing = (await session.execute(select(Role).where(Role.code == code).limit(1))).scalars().first()
    if existing is not None:
        raise HTTPException(status_code=409, detail={"code": "CONFLICT", "message": "Role already exists"})

    role = Role(
        id=str(uuid4()),
        code=code,
        name=name,
        description=(payload.description or None),
        is_system=False,
    )
    session.add(role)
    await session.commit()
    return _role_out(role)


@router.patch("/roles/{role_id}", dependencies=[Depends(require_permissions("rbac:manage"))])
async def update_role(role_id: str, payload: RoleUpdateIn, session: AsyncSession = Depends(get_session)) -> dict:
    role = await session.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Role not found"})

    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail={"code": "VALIDATION", "message": "name cannot be empty"})
        role.name = name
    if payload.description is not None:
        role.description = payload.description.strip() or None

    await session.commit()
    return _role_out(role)


@router.delete("/roles/{role_id}", dependencies=[Depends(require_permissions("rbac:manage"))])
async def delete_role(role_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    role = await session.get(Role, role_id)
    if role is None:
        return {"status": "ok"}
    if role.is_system:
        raise HTTPException(status_code=400, detail={"code": "VALIDATION", "message": "Cannot delete system role"})

    await session.delete(role)
    await session.commit()
    return {"status": "ok"}


@router.get("/permissions", dependencies=[Depends(require_permissions("rbac:manage"))])
async def list_permissions(session: AsyncSession = Depends(get_session)) -> list[dict]:
    rows = (await session.execute(select(Permission).order_by(Permission.code.asc()))).scalars().all()
    return [_perm_out(p) for p in rows]


@router.post("/permissions", dependencies=[Depends(require_permissions("rbac:manage"))])
async def create_permission(payload: PermissionCreateIn, session: AsyncSession = Depends(get_session)) -> dict:
    code = payload.code.strip()
    name = payload.name.strip()
    if not code or not name:
        raise HTTPException(status_code=400, detail={"code": "VALIDATION", "message": "code and name are required"})

    existing = (
        await session.execute(select(Permission).where(Permission.code == code).limit(1))
    ).scalars().first()
    if existing is not None:
        raise HTTPException(status_code=409, detail={"code": "CONFLICT", "message": "Permission already exists"})

    perm = Permission(
        id=str(uuid4()),
        code=code,
        name=name,
        description=(payload.description or None),
        is_system=False,
    )
    session.add(perm)
    await session.commit()
    return _perm_out(perm)


@router.patch("/permissions/{permission_id}", dependencies=[Depends(require_permissions("rbac:manage"))])
async def update_permission(permission_id: str, payload: PermissionUpdateIn, session: AsyncSession = Depends(get_session)) -> dict:
    perm = await session.get(Permission, permission_id)
    if perm is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Permission not found"})

    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail={"code": "VALIDATION", "message": "name cannot be empty"})
        perm.name = name
    if payload.description is not None:
        perm.description = payload.description.strip() or None

    await session.commit()
    return _perm_out(perm)


@router.delete("/permissions/{permission_id}", dependencies=[Depends(require_permissions("rbac:manage"))])
async def delete_permission(permission_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    perm = await session.get(Permission, permission_id)
    if perm is None:
        return {"status": "ok"}
    if perm.is_system:
        raise HTTPException(status_code=400, detail={"code": "VALIDATION", "message": "Cannot delete system permission"})

    await session.delete(perm)
    await session.commit()
    return {"status": "ok"}


@router.post("/roles/{role_id}/permissions/{permission_id}", dependencies=[Depends(require_permissions("rbac:manage"))])
async def add_permission_to_role(role_id: str, permission_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    role = await session.get(Role, role_id)
    perm = await session.get(Permission, permission_id)
    if role is None or perm is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Role or Permission not found"})

    exists = (
        await session.execute(
            select(role_permissions.c.role_id)
            .where(role_permissions.c.role_id == role.id)
            .where(role_permissions.c.permission_id == perm.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if exists is None:
        await session.execute(insert(role_permissions).values(role_id=role.id, permission_id=perm.id))
        await session.commit()
    return {"status": "ok"}


@router.delete("/roles/{role_id}/permissions/{permission_id}", dependencies=[Depends(require_permissions("rbac:manage"))])
async def remove_permission_from_role(role_id: str, permission_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    role = await session.get(Role, role_id)
    perm = await session.get(Permission, permission_id)
    if role is None or perm is None:
        return {"status": "ok"}

    await session.execute(
        delete(role_permissions)
        .where(role_permissions.c.role_id == role.id)
        .where(role_permissions.c.permission_id == perm.id)
    )
    await session.commit()
    return {"status": "ok"}


@router.post("/users/{user_id}/roles/{role_id}", dependencies=[Depends(require_permissions("rbac:manage"))])
async def add_role_to_user(user_id: str, role_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    user = await session.get(User, user_id)
    role = await session.get(Role, role_id)
    if user is None or role is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "User or Role not found"})

    exists = (
        await session.execute(
            select(user_roles.c.user_id)
            .where(user_roles.c.user_id == user.id)
            .where(user_roles.c.role_id == role.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if exists is None:
        await session.execute(insert(user_roles).values(user_id=user.id, role_id=role.id))
        await session.commit()
    return {"status": "ok"}


@router.delete("/users/{user_id}/roles/{role_id}", dependencies=[Depends(require_permissions("rbac:manage"))])
async def remove_role_from_user(user_id: str, role_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    user = await session.get(User, user_id)
    role = await session.get(Role, role_id)
    if user is None or role is None:
        return {"status": "ok"}

    await session.execute(
        delete(user_roles).where(user_roles.c.user_id == user.id).where(user_roles.c.role_id == role.id)
    )
    await session.commit()
    return {"status": "ok"}


@router.get("/users/{user_id}/effective", dependencies=[Depends(require_permissions("rbac:manage"))])
async def effective_user_access(user_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "User not found"})

    role_codes = (
        await session.execute(
            select(Role.code)
            .join(user_roles, user_roles.c.role_id == Role.id)
            .where(user_roles.c.user_id == user.id)
            .order_by(Role.code.asc())
        )
    ).scalars().all()

    perm_codes = (
        await session.execute(
            select(Permission.code)
            .join(role_permissions, role_permissions.c.permission_id == Permission.id)
            .join(user_roles, user_roles.c.role_id == role_permissions.c.role_id)
            .where(user_roles.c.user_id == user.id)
            .distinct()
            .order_by(Permission.code.asc())
        )
    ).scalars().all()

    return {"userId": user.id, "roles": list(role_codes), "permissions": list(perm_codes)}
