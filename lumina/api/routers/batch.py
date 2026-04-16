from fastapi import APIRouter, HTTPException, Request

from lumina.api.protocol import BatchDocumentRequest, BatchImageRequest, BatchJobResponse

router = APIRouter(prefix="/v1/batch", tags=["batch"])


@router.post("/document", response_model=BatchJobResponse)
async def submit_document_batch(body: BatchDocumentRequest, raw: Request):
    manager = raw.app.state.batch_manager
    try:
        return manager.submit_document_job(
            input_dir=body.input_dir,
            output_dir=body.output_dir,
            task=body.task,
            target_language=body.target_language,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("/image", response_model=BatchJobResponse)
async def submit_image_batch(body: BatchImageRequest, raw: Request):
    manager = raw.app.state.batch_manager
    try:
        return manager.submit_image_job(
            input_dir=body.input_dir,
            output_dir=body.output_dir,
            task=body.task,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get("/{job_id}", response_model=BatchJobResponse)
async def batch_job_status(job_id: str, raw: Request):
    manager = raw.app.state.batch_manager
    job = manager.get_status(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job
