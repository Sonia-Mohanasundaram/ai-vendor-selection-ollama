from sqlalchemy import Column, Integer, String, Float, JSON, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    upload_time = Column(String, nullable=False)
    output_json = Column(JSON, nullable=True)

    # Link uploaded files to an analysis run (one analysis -> many uploaded files)
    analysis_id = Column(Integer, ForeignKey("analysis.id"), nullable=True)

    # Legacy relationship (Analysis.uploaded_file_id)
    analyses = relationship(
        "Analysis",
        back_populates="uploaded_file",
        foreign_keys="Analysis.uploaded_file_id",
    )

    # New relationship (UploadedFile.analysis_id)
    analysis = relationship(
        "Analysis",
        back_populates="uploaded_files",
        foreign_keys=[analysis_id],
    )

class Analysis(Base):
    __tablename__ = "analysis"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=True)
    timestamp = Column(String, nullable=False)
    vendor_count = Column(Integer, nullable=False)
    best_vendor = Column(String, nullable=False)
    final_score = Column(Float, nullable=False)
    # Full payload (input + output + audit) as a single JSON document.
    data_json = Column(JSON, nullable=False)

    # Convenience JSON columns for easier querying/debugging.
    # - input_json: extracted/normalized details from uploaded files
    # - output_json: the response payload shown in UI
    # - files_json: file metadata (name/size/type)
    # - output_files_json: output/export artifact metadata (name/size/type)
    input_json = Column(JSON, nullable=True)
    output_json = Column(JSON, nullable=True)
    files_json = Column(JSON, nullable=True)
    output_files_json = Column(JSON, nullable=True)
    uploaded_file_id = Column(Integer, ForeignKey("uploaded_files.id"), nullable=True)
    uploaded_file = relationship(
        "UploadedFile",
        back_populates="analyses",
        foreign_keys=[uploaded_file_id],
    )

    uploaded_files = relationship(
        "UploadedFile",
        back_populates="analysis",
        foreign_keys="UploadedFile.analysis_id",
    )
