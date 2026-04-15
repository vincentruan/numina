from fastapi.responses import JSONResponse


class EnvelopeResponse(JSONResponse):
    def __init__(self, content=None, **kwargs):
        super().__init__(
            content={"code": "OK", "message": "", "data": content},
            **kwargs,
        )
