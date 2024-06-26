from typing import Callable
from fastapi import FastAPI, Response, Request
from starlette.background import BackgroundTask
from starlette.types import Message
import logging
import json

def parse_body(content):
    try:
        return content.decode('utf-8')
    except:
        return content


def default_logger(**kwargs):
    """Logs all the available information for a normal response"""
    # logging.info(json.dumps(kwargs, indent=4))
    for k, v in kwargs.items():
        if isinstance(v, dict):
            for kk, vv in v.items():
                logging.info(f'{k}: {kk} = {vv}')
        elif isinstance(v, bytes):
            logging.debug(f'{k}: "{v[:20]}"')
        else:
            logging.debug(f'{k}: {v}')


def default_error_logger(**kwargs):
    """Logs all the available information for a response with error"""
    # logging.info(json.dumps(kwargs, indent=4))
    for k, v in kwargs.items():
        if isinstance(v, dict):
            for kk, vv in v.items():
                logging.error(f'{k}: {kk} = {vv}')
        elif isinstance(v, bytes):
            logging.error(f'{k}: "{v[:20]}"')
        else:
            logging.error(f'{k}: {v}')


async def set_body(request: Request, body: bytes):
    """Utility function to recreate the body of a request"""

    async def receive() -> Message:
        return {"type": "http.request", "body": body}

    request._receive = receive


def disable_loggers():
    """Disable UVICORN and FASTAPI loggers by setting them to CRITICAL levels"""
    uvicorn_error = logging.getLogger("uvicorn.error")
    uvicorn_error.setLevel(level=logging.CRITICAL)
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.setLevel(level=logging.CRITICAL)
    uvicorn_access = logging.getLogger("uvicorn")
    uvicorn_access.setLevel(level=logging.CRITICAL)
    fastapi_logger = logging.getLogger("fastapi")
    fastapi_logger.setLevel(level=logging.CRITICAL)

def add_custom_logger(
    app: FastAPI,
    custom_logger: Callable = default_logger,
    custom_error_logger: Callable = default_error_logger,
    disable_uvicorn_logging: bool = True,
) -> FastAPI:
    """Function to add custom loggers to a FastAPI application

    Args:
        app (FastAPI): a FastAPI application
        custom_logger (callable, optional): function used to print logs when working normally.
            Defaults to `default_logger`.
        custom_error_logger (callable, optional): funtion used to print logs when an error occurs.
            Defaults to `default_error_logger`.
        disable_uvicorn_logging (bool, optional): if True, usual uvicorn and FastAPI logs are inhibited.
            Defaults to True.


    Returns:
        FastAPI: FastAPI app with the custom loggers
    """
    if disable_uvicorn_logging:
        disable_loggers()

    @app.middleware("http")
    async def middleware_logger(request: Request, call_next):
        request_body = await request.body()
        await set_body(request, request_body)
        try:
            response = await call_next(request)
        except Exception as exc:
            custom_error_logger(
                **{
                    "request_body": parse_body(request_body),
                    "request_headers": dict(request.headers),
                    "request_query_params": dict(request.query_params),
                    "request_method": request.method,
                    "request_url": str(request.url),
                    "error_message": str(exc),
                },
            )
            raise exc

        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk
        task = BackgroundTask(
            custom_logger,
            **{
                "request_body": parse_body(request_body),
                "request_headers": dict(request.headers),
                "request_query_params": dict(request.query_params),
                "request_method": request.method,
                "request_url": str(request.url),
                "response_body": parse_body(response_body),
                "response_headers": dict(response.headers),
                "response_media_type": response.media_type,
                "response_status_code": response.status_code,
            },
        )
        return Response(
            content=response_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
            background=task,
        )

    return app


class FastAPIMiddleWareLogger(FastAPI):
    """Class that inherits from FastAPI and allows to add custom loggers"""

    def __init__(
        self,
        custom_logger: callable = default_logger,
        custom_error_logger: callable = default_error_logger,
        disable_uvicorn_logger: bool = True,
        *args,
        **kwargs,
    ):
        FastAPI.__init__(self, *args, **kwargs)
        add_custom_logger(
            self,
            custom_logger=custom_logger,
            custom_error_logger=custom_error_logger,
            disable_uvicorn_logging=disable_uvicorn_logger,
        )
