import sys
from pydantic import BaseModel
from fastapi import Response

class FilterRequest(BaseModel):
    road_distance_min: int = 0
    road_distance_max: int = sys.maxsize
    port_distance_min: int = 0
    port_distance_max: int = sys.maxsize

class FilterResponse(Response):
    """Filters response."""

    def __init__(
        self,
        content: bytes,
        media_type: str = 'image/png',
        status_code: int = 200,
        headers: dict = {},
    ) -> None:
        """Init filter response."""
        headers.update({"Content-Type": media_type})
        self.body = self.render(content)
        self.status_code = 200
        self.media_type = media_type
        self.background = None
        self.init_headers(headers)