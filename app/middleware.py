from fastapi import Request
from loguru import logger


async def log_requests(request: Request, call_next):
    logger.info("{} {}", request.method, request.url.path)
    response = await call_next(request)
    logger.info("{} {} -> {}", request.method, request.url.path, response.status_code)
    return response
