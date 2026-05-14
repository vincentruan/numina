from fastapi.responses import JSONResponse


class EnvelopeResponse(JSONResponse):
    def __init__(self, content=None, status_code: int = 200, **kwargs):
        super().__init__(
            content={"code": "OK", "message": "", "data": content},
            status_code=status_code,
            **kwargs,
        )
