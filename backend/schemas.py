from pydantic import BaseModel
from typing import Any, Optional

class UploadedFileCreate(BaseModel):
    filename: str
    content_type: str
    upload_time: str
    output_json: Optional[Any] = None
    analysis_id: Optional[int] = None

class UploadedFileResponse(UploadedFileCreate):
    id: int

    class Config:
        from_attributes = True

class AnalysisCreate(BaseModel):
    title: Optional[str] = None
    timestamp: str
    vendor_count: int
    best_vendor: str
    final_score: float
    data_json: Any
    input_json: Optional[Any] = None
    output_json: Optional[Any] = None
    files_json: Optional[Any] = None
    output_files_json: Optional[Any] = None
    uploaded_file_id: Optional[int] = None

class AnalysisResponse(AnalysisCreate):
    id: int
    uploaded_file: Optional[UploadedFileResponse] = None

    class Config:
        from_attributes = True
