from __future__ import annotations

import asyncio
from html import escape

import uvicorn
from fastapi import (
    FastAPI,
    HTTPException,
)
from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
)

from cua.escalation.session import (
    HandoffError,
    HandoffSession,
)


def create_operator_app(
    session: HandoffSession,
) -> FastAPI:
    app = FastAPI(
        title="CUA Operator Handoff"
    )

    @app.get(
        "/",
        response_class=HTMLResponse,
    )
    async def home() -> str:
        request = (
            session.current_request
        )

        if request is None:
            return """
            <!doctype html>
            <html>
            <head>
              <title>CUA Operator Handoff</title>
            </head>
            <body>
              <h1>Operator Handoff</h1>
              <p>
                No handoff request is currently pending.
              </p>
              <p>
                Refresh this page when automation
                requests human assistance.
              </p>
            </body>
            </html>
            """

        screenshot = ""

        if request.screenshot_path:
            screenshot = (
                "<p><b>Evidence screenshot:</b> "
                f"{escape(request.screenshot_path)}"
                "</p>"
            )

        checkpoint = ""

        if (
            request.checkpoint_description
        ):
            checkpoint = (
                "<p><b>Expected checkpoint:</b> "
                f"{escape(request.checkpoint_description)}"
                "</p>"
            )

        button = ""

        if request.status == "pending":
            button = """
            <form method="post" action="/resume">
              <button type="submit">
                Resume Automation
              </button>
            </form>
            """

        return f"""
        <!doctype html>
        <html>
        <head>
          <meta charset="utf-8">
          <title>CUA Operator Handoff</title>
        </head>
        <body>
          <h1>Operator Handoff</h1>

          <p>
            The live browser session is intentionally
            being kept open.
          </p>

          <p>
            Resolve the issue in that same browser,
            then return here and resume automation.
          </p>

          <hr>

          <p>
            <b>Request:</b>
            {escape(request.request_id)}
          </p>

          <p>
            <b>Capability:</b>
            {escape(request.capability_id)}
            /
            {escape(request.capability_version)}
          </p>

          <p>
            <b>Step:</b>
            {escape(request.step_id)}
          </p>

          <p>
            <b>Status:</b>
            {escape(request.status)}
          </p>

          <p>
            <b>Reason:</b>
            {escape(request.reason)}
          </p>

          <p>
            <b>Current URL:</b>
            {escape(request.current_url)}
          </p>

          {checkpoint}

          {screenshot}

          {button}
        </body>
        </html>
        """

    @app.post("/resume")
    async def resume():
        try:
            session.resume()

        except HandoffError as exc:
            raise HTTPException(
                status_code=409,
                detail=str(exc),
            ) from exc

        return RedirectResponse(
            url="/",
            status_code=303,
        )

    return app


class OperatorServer:
    def __init__(
        self,
        session: HandoffSession,
        host: str = "127.0.0.1",
        port: int = 8765,
    ) -> None:
        self.session = session
        self.host = host
        self.port = port

        self.app = (
            create_operator_app(
                session
            )
        )

        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="warning",
        )

        self.server = (
            uvicorn.Server(
                config
            )
        )

        self._task: (
            asyncio.Task[None]
            | None
        ) = None

    @property
    def url(self) -> str:
        return (
            f"http://"
            f"{self.host}:"
            f"{self.port}"
        )

    async def start(
        self,
    ) -> None:
        if self._task is not None:
            return

        self._task = (
            asyncio.create_task(
                self.server.serve()
            )
        )

        for _ in range(100):
            if self.server.started:
                return

            await asyncio.sleep(
                0.01
            )

        raise RuntimeError(
            "Operator server did "
            "not start."
        )

    async def stop(
        self,
    ) -> None:
        if self._task is None:
            return

        self.server.should_exit = True

        await self._task

        self._task = None