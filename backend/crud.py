from sqlalchemy.orm import Session
from . import models, schemas

def save_uploaded_file(db: Session, file: schemas.UploadedFileCreate):
    db_file = models.UploadedFile(
        filename=file.filename,
        content_type=file.content_type,
        upload_time=file.upload_time,
        output_json=file.output_json,
        analysis_id=file.analysis_id,
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    return db_file

def get_all_uploaded_files(db: Session):
    return db.query(models.UploadedFile).order_by(models.UploadedFile.id.desc()).all()

def save_analysis(db: Session, analysis: schemas.AnalysisCreate):
    db_analysis = models.Analysis(
        title=analysis.title,
        timestamp=analysis.timestamp,
        vendor_count=analysis.vendor_count,
        best_vendor=analysis.best_vendor,
        final_score=analysis.final_score,
        data_json=analysis.data_json,
        input_json=analysis.input_json,
        output_json=analysis.output_json,
        files_json=analysis.files_json,
        output_files_json=analysis.output_files_json,
        uploaded_file_id=analysis.uploaded_file_id
    )
    db.add(db_analysis)
    db.commit()
    db.refresh(db_analysis)
    return db_analysis

def get_all_analysis(db: Session):
    return db.query(models.Analysis).order_by(models.Analysis.id.desc()).all()
