"""路由聚合：统一 /api 前缀（Nginx 反代时剥掉 /api）。"""
from fastapi import APIRouter

from src.routes.audit import router as audit_router
from src.routes.auth import router as auth_router
from src.routes.exports import router as exports_router
from src.routes.health import router as health_router
from src.routes.model_runs import router as model_runs_router
from src.routes.model_suggestions import router as model_suggestions_router
from src.routes.overview import router as overview_router
from src.routes.profiles import router as profiles_router
from src.routes.relations import router as relations_router
from src.routes.source_tables import router as source_tables_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(overview_router)
api_router.include_router(source_tables_router)
api_router.include_router(profiles_router)
api_router.include_router(relations_router)
api_router.include_router(model_runs_router)
api_router.include_router(model_suggestions_router)
api_router.include_router(exports_router)
api_router.include_router(audit_router)
