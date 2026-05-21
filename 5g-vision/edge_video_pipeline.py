# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: hydrogen
#       format_version: '1.3'
#       jupytext_version: 1.19.1
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Telco Edge Video Analytics
# Simulating inference and edge-compilation for 5G site security.

# %%
!pip install -q -r requirements.txt

# %%
from pathlib import Path

import cv2
from ultralytics import YOLO

print("Loading standard PyTorch model...")
model = YOLO('yolov8n.pt')

# Prefer the pre-converted MJPEG AVI — OpenCV reads it natively via its built-in
# libjpeg without going through FFmpeg at all, so no codec environment issues.
cwd = Path.cwd()
candidates = [
    (cwd / 'site_camera_01_mjpeg.avi',       cwd / 'site_camera_01.mp4'),
    (cwd / '5g-vision/site_camera_01_mjpeg.avi', cwd / '5g-vision/site_camera_01.mp4'),
    (cwd.parent / '5g-vision/site_camera_01_mjpeg.avi', cwd.parent / '5g-vision/site_camera_01.mp4'),
]
video_path = None
for mjpeg, mp4 in candidates:
    if mjpeg.exists():
        video_path = mjpeg
        break
    if mp4.exists():
        video_path = mp4
        break
if video_path is None:
    raise FileNotFoundError(f"Could not find site_camera_01_mjpeg.avi or site_camera_01.mp4 near cwd={cwd}")

print(f"Running inference on 5G site camera feed: {video_path}")
results = model(
    str(video_path),
    save=True,
    project="output",
    name="vision"
)

print("Video processed! Bounding boxes saved locally.")

# %%
import onnxruntime as ort

print("--- Edge Compilation Step ---")
print("Exporting YOLOv8n to ONNX format for edge deployment...")
export_path = model.export(format='onnx', opset=17, simplify=False)
print(f"ONNX model saved to: {export_path}")

print("\nValidating ONNX model with ONNX Runtime...")
session = ort.InferenceSession(export_path, providers=['CPUExecutionProvider'])
inputs = session.get_inputs()
outputs = session.get_outputs()

print(f"\nModel input  : {inputs[0].name} — shape {inputs[0].shape}")
print(f"Model output : {outputs[0].name} — shape {outputs[0].shape}")
print("\nEdge-ready ONNX model validated.")
print("Ready for deployment to OpenShift AI edge node via GitOps.")

# %%
import os
import boto3
from botocore.client import Config

# 1. Configuration - RHOAI injects these automatically if the Data Connection is attached!
s3_endpoint = 'http://minio-fallback.aistor.svc.cluster.local:9000'
s3_access_key = 'minioadm'
s3_secret_key = 'minioadm'
bucket_name = 'vision-models'
local_file = 'yolov8n.onnx'
s3_key = 'models/yolov8n.onnx'

print(f"Connecting to Edge Storage at: {s3_endpoint}")

# 2. Initialize the S3 client
s3 = boto3.client(
    's3',
    endpoint_url=s3_endpoint,
    aws_access_key_id=s3_access_key,
    aws_secret_access_key=s3_secret_key,
    config=Config(signature_version='s3v4'),
    region_name='us-east-1',
)

# 3. Ensure the bucket exists
try:
    s3.create_bucket(Bucket=bucket_name)
    print(f"Bucket '{bucket_name}' created.")
except s3.exceptions.BucketAlreadyOwnedByYou:
    print(f"Bucket '{bucket_name}' already exists — OK.")
except Exception as e:
    print(f"Bucket check: {e}")

# 4. Upload the ONNX model — two paths:
#    models/yolov8n.onnx  : human-readable archive copy
#    yolo-model/1/model.onnx : versioned path OVMS/KServe expects (storageUri s3://vision-models/yolo-model)
for dest_key, label in [
    (s3_key,                    "archive"),
    ('yolo-model/1/model.onnx', "OVMS serving path"),
]:
    print(f"Uploading {local_file} -> s3://{bucket_name}/{dest_key} ({label}) ...")
    try:
        s3.upload_file(local_file, bucket_name, dest_key)
        print(f"  ✅ OK")
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
