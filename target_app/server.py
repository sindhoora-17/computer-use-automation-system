import os
import time

from flask import (
    Flask,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from target_app.fixtures import MEMBERS
from target_app.scenarios import (
    SCENARIO,
    reset_scenario,
    set_scenario,
)


app = Flask(__name__)

app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "local-dev-secret",
)


DEMO_USERNAME = os.environ.get(
    "TARGET_APP_USERNAME",
    "operator",
)

DEMO_PASSWORD = os.environ.get(
    "TARGET_APP_PASSWORD",
    "demo123",
)


def is_authenticated() -> bool:
    if (
        os.environ.get(
            "TARGET_APP_BYPASS_AUTH",
            "false",
        ).lower()
        == "true"
    ):
        return True

    return bool(
        session.get("authenticated")
    )


def safe_next_path(
    value: str | None,
) -> str | None:
    if not value:
        return None

    if not value.startswith("/"):
        return None

    if value.startswith("//"):
        return None

    return value


@app.get("/")
def index():
    return redirect(
        url_for("login")
    )


@app.route(
    "/login",
    methods=["GET", "POST"],
)
def login():
    error = None

    next_path = safe_next_path(
        request.values.get("next")
    )

    if request.method == "POST":
        username = request.form.get(
            "username",
            "",
        )

        password = request.form.get(
            "password",
            "",
        )

        if (
            username == DEMO_USERNAME
            and password == DEMO_PASSWORD
        ):
            session["authenticated"] = True

            if next_path:
                return redirect(
                    next_path
                )

            return redirect(
                url_for("main")
            )

        error = (
            "Invalid operator credentials"
        )

    return render_template(
        "login.html",
        error=error,
        next_path=next_path,
    )


@app.get("/main")
def main():
    if not is_authenticated():
        return redirect(
            url_for("login")
        )

    return render_template(
        "main.html"
    )


@app.get("/nav")
def nav():
    if not is_authenticated():
        return redirect(
            url_for("login")
        )

    return render_template(
        "nav.html"
    )


@app.route(
    "/content/search",
    methods=["GET", "POST"],
)
def member_search():
    if not is_authenticated():
        return redirect(
            url_for("login")
        )

    if SCENARIO.slow_load:
        time.sleep(3)

    query = None
    results = []

    if request.method == "POST":
        query = request.form.get(
            "member_query",
            "",
        ).strip()

        if query in MEMBERS:
            results = [
                MEMBERS[query]
            ]

        else:
            results = [
                member
                for member
                in MEMBERS.values()
                if query.lower()
                in member[
                    "last_name"
                ].lower()
            ]

    return render_template(
        "search.html",
        query=query,
        results=results,
        show_interstitial=False,
    )


@app.get(
    "/content/member/<member_id>"
)
def member_detail(
    member_id: str,
):
    if SCENARIO.session_expired:
        SCENARIO.session_expired = False

        session.clear()

        return redirect(
            url_for(
                "login",
                next=(
                    f"/content/member/"
                    f"{member_id}"
                ),
            )
        )

    if not is_authenticated():
        return redirect(
            url_for(
                "login",
                next=(
                    f"/content/member/"
                    f"{member_id}"
                ),
            )
        )

    if SCENARIO.interstitial:
        return render_template(
            "manual_review.html",
            member_id=member_id,
        )

    if SCENARIO.app_error:
        return (
            "Application error",
            500,
        )

    member = MEMBERS.get(
        member_id
    )

    if member is None:
        return (
            render_template(
                "member_not_found.html",
                member_id=member_id,
            ),
            404,
        )

    if member["restricted"]:
        return (
            render_template(
                "permission_denied.html",
                member=member,
            ),
            403,
        )

    return render_template(
        "member.html",
        member=member,
    )


@app.post(
    "/content/member/"
    "<member_id>/continue"
)
def continue_member(
    member_id: str,
):
    if not is_authenticated():
        return redirect(
            url_for(
                "login",
                next=(
                    f"/content/member/"
                    f"{member_id}"
                ),
            )
        )

    SCENARIO.interstitial = False

    return redirect(
        url_for(
            "member_detail",
            member_id=member_id,
        )
    )


@app.post("/_control/scenario")
def control_scenario():
    name = request.form.get(
        "name",
        "",
    )

    enabled = (
        request.form.get(
            "enabled",
            "true",
        ).lower()
        == "true"
    )

    try:
        set_scenario(
            name,
            enabled,
        )

    except ValueError as exc:
        return {
            "ok": False,
            "error": str(exc),
        }, 400

    return {
        "ok": True,
        "scenario": name,
        "enabled": enabled,
    }


@app.post("/_control/reset")
def control_reset():
    reset_scenario()

    return {
        "ok": True,
    }


if __name__ == "__main__":
    app.run(
        debug=True,
        port=5000,
    )