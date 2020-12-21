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
                "filter_country", **dict(country_id="BOL", z="{z}", x="{x}", y="{y}")
            ),
            "lcoe_endpoint": request.url_for(
                "lcoe", **dict(country_id="AFG", z="{z}", x="{x}", y="{y}")
            ),
            "score_endpoint": request.url_for(
                "score", **dict(country_id="AFG", z="{z}", x="{x}", y="{y}")
            ),
            "layers_endpoint": request.url_for(
                "layers", **dict(country_id="CHN", id="{id}", z="{z}", x="{x}", y="{y}")
            ),
            "layer_list": request.url_for("layer_list"),
            "filter_schema": request.url_for("filter_schema"),
        },
    )
