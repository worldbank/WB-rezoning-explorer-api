"""API demo"""
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="rezoning_api/templates")


@router.get("/demo")
def demo(request: Request):
    """demo"""
    return templates.TemplateResponse(
        "demo.html",
        {
            "request": request,
            "filter_endpoint": request.url_for(
                "filter", **dict(z="{z}", x="{x}", y="{y}")
            ),
            "lcoe_endpoint": request.url_for("lcoe", **dict(z="{z}", x="{x}", y="{y}")),
            "score_endpoint": request.url_for(
                "score", **dict(country="AFG", z="{z}", x="{x}", y="{y}")
            ),
        },
    )
