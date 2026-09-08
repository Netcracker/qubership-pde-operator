from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from pde_operator.utils.depend_utils import DependUtils
from pde_operator.utils.metrics_utils import MetricsUtils

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def metrics(session: AsyncSession = Depends(DependUtils.get_session)) -> Response:
    body = await MetricsUtils.render_metrics(session)
    return Response(content=body, media_type=MetricsUtils.CONTENT_TYPE)
