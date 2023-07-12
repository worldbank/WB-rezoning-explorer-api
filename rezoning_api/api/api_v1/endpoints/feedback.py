"""Feedback endpoints"""
import requests
from fastapi import Request, APIRouter
from rezoning_api.core.config import FEEDBACK_URL, GITHUB_TOKEN
from fastapi.responses import JSONResponse


router = APIRouter()


@router.post("/feedback", description="Feedback submission")
async def feedback(request: Request):
    """This api creates a ticket in github repo, when user submits a feedback form."""
    data = await request.json()
    response = requests.post(FEEDBACK_URL, headers={'authorization': GITHUB_TOKEN}, json=data)
    return JSONResponse(status_code=response.status_code)
