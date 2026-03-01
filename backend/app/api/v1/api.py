from fastapi import APIRouter

from app.api.v1 import analytics, auth, dashboard, events, objects, presence, rbac, reports, search, users
from app.api.v1.routes import db_meta, health, prototype

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(db_meta.router, prefix="/db", tags=["db"])
api_router.include_router(prototype.router, tags=["prototype"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(rbac.router, tags=["rbac"])
api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(events.router, tags=["events"])
api_router.include_router(objects.router, tags=["objects"])
api_router.include_router(reports.router, tags=["reports"])
api_router.include_router(analytics.router, tags=["analytics"])
api_router.include_router(presence.router, tags=["presence"])
api_router.include_router(search.router, tags=["search"])
api_router.include_router(users.router, tags=["users"])
