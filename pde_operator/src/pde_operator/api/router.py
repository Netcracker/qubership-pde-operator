from fastapi import APIRouter, Depends

from pde_operator.api.v1 import declarative_run_templates, manage, profiles, run_templates, runs
from pde_operator.utils.depend_utils import DependUtils

api_router = APIRouter(dependencies=[Depends(DependUtils.require_api_token)])
api_router.include_router(runs.router)
api_router.include_router(profiles.router)
api_router.include_router(run_templates.router)
api_router.include_router(declarative_run_templates.router)
api_router.include_router(manage.router)
