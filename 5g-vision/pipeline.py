from kfp import dsl
from kfp.dsl import component, pipeline, Input, Output, Dataset, Metrics


@component(base_image="python:3.11-slim")
def ingest_video(
    stream_url: str,
    duration_seconds: int,
    raw_frames: Output[Dataset],
):
    """Pull frames from an edge RTSP stream and store them as a dataset."""
    pass


@component(base_image="python:3.11-slim")
def preprocess_frames(
    raw_frames: Input[Dataset],
    target_width: int,
    target_height: int,
    preprocessed_frames: Output[Dataset],
):
    """Resize, normalize, and batch frames for inference."""
    pass


@component(base_image="quay.io/rhoai/yolo:latest")
def run_yolo_detection(
    preprocessed_frames: Input[Dataset],
    model_uri: str,
    confidence_threshold: float,
    raw_detections: Output[Dataset],
    metrics: Output[Metrics],
):
    """Run YOLO object detection on preprocessed frames."""
    pass


@component(base_image="python:3.11-slim")
def filter_and_annotate(
    raw_detections: Input[Dataset],
    preprocessed_frames: Input[Dataset],
    iou_threshold: float,
    annotated_frames: Output[Dataset],
    detection_report: Output[Dataset],
):
    """Apply NMS, filter by class, and draw bounding boxes on frames."""
    pass


@component(base_image="python:3.11-slim")
def upload_to_minio(
    annotated_frames: Input[Dataset],
    detection_report: Input[Dataset],
    minio_endpoint: str,
    bucket_name: str,
    object_prefix: str,
):
    """Upload annotated frames and detection report to MinIO object storage."""
    pass


@pipeline(
    name="5g-edge-yolo-detection",
    description="End-to-end video analytics pipeline: ingest from 5G edge stream, run YOLO detection, and store results in MinIO.",
)
def edge_detection_pipeline(
    stream_url: str = "rtsp://edge-node-1:8554/live",
    duration_seconds: int = 30,
    target_width: int = 640,
    target_height: int = 640,
    confidence_threshold: float = 0.5,
    iou_threshold: float = 0.45,
    minio_endpoint: str = "minio-service:9000",
    bucket_name: str = "yolo-results",
    object_prefix: str = "detections/run-001",
    model_uri: str = "s3://models/yolov8n.onnx",
):
    ingest_task = ingest_video(
        stream_url=stream_url,
        duration_seconds=duration_seconds,
    )

    preprocess_task = preprocess_frames(
        raw_frames=ingest_task.outputs["raw_frames"],
        target_width=target_width,
        target_height=target_height,
    )

    detect_task = run_yolo_detection(
        preprocessed_frames=preprocess_task.outputs["preprocessed_frames"],
        model_uri=model_uri,
        confidence_threshold=confidence_threshold,
    )

    annotate_task = filter_and_annotate(
        raw_detections=detect_task.outputs["raw_detections"],
        preprocessed_frames=preprocess_task.outputs["preprocessed_frames"],
        iou_threshold=iou_threshold,
    )

    upload_to_minio(
        annotated_frames=annotate_task.outputs["annotated_frames"],
        detection_report=annotate_task.outputs["detection_report"],
        minio_endpoint=minio_endpoint,
        bucket_name=bucket_name,
        object_prefix=object_prefix,
    )
