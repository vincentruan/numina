from pydantic import BaseModel


class TravelReceiptUploadResponse(BaseModel):
    """Response for travel receipt upload endpoint.

    The AI extraction happens asynchronously via the import-parse chat flow,
    so ``extracted_data`` is null on initial upload and ``confidence`` is "pending".
    """

    receipt_image_url: str
    trip_id: str
    extracted_data: dict | None = None
    confidence: str = "pending"  # high/medium/low/pending
