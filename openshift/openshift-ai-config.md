# OpenShift AI — 5G Vision Config Notes

## Namespace

```
ericsson-projects
```

---

## Workbench

| | |
|---|---|
| **Pod** | `wb-5g-vision-dev-0` |
| **PVC** | `wb-5g-vision-dev-storage` |
| **Mount path (in workbench)** | `/opt/app-root/src/` |

---

## InferenceService

| | |
|---|---|
| **Name** | `yolo-onnx` |
| **Runtime** | OpenVINO Model Server (OVMS) |
| **REST port** | `8888` |
| **gRPC port** | `8001` |
| **Internal URL** | `http://yolo-onnx-predictor.ericsson-projects.svc.cluster.local:8888` |
| **Protocol** | KServe v2 REST |
| **Infer endpoint** | `/v2/models/yolo-onnx/infer` |
| **Health endpoint** | `/v2/health/ready` |
| **Model metadata** | `/v2/models/yolo-onnx` |

### storageUri (corrected)

```
pvc://wb-5g-vision-dev-storage/models
```

> **Note:** must point to the versioned **directory**, not the file.
> OVMS expects: `models/1/model.onnx` inside the PVC.

### Model input/output (confirmed via OVMS metadata)

```json
{
  "name": "yolo-onnx",
  "versions": ["1"],
  "platform": "OpenVINO",
  "inputs":  [{ "name": "images",  "datatype": "FP32", "shape": [1, 3, 640, 640] }],
  "outputs": [{ "name": "output0", "datatype": "FP32", "shape": [1, 84, 8400]   }]
}
```

Output layout: `[1, 84, 8400]` → transpose to `[8400, 84]`:
- Columns `0–3`: bounding box (cx, cy, w, h) in 640×640 space
- Columns `4–83`: class scores (80 COCO classes)

---

## Model file on PVC

| Path on PVC | Notes |
|---|---|
| `models/1/model.onnx` | Live model served by OVMS (YOLOv8n ONNX) |
| `models/yolov8.onnx/` | **Empty directory** — ignore, artefact from a failed export |

> **Gotcha:** `models/yolov8.onnx` is a directory (not a file) created by a previous
> notebook run. The storage initializer silently failed because of this, leaving
> `/mnt/models` empty in the predictor pod. Fixed by placing the model at
> `models/1/model.onnx` and patching the storageUri.

---

## MinIO (model registry + output storage)

See `minio.txt` for endpoint and credentials.

### Public Routes

| Route | URL | Purpose |
|---|---|---|
| `minio-console` | `https://minio-console-aistor.apps.cluster-ls8dt.ls8dt.sandbox1882.opentlc.com` | Web UI (port 9001) — login `minioadm/minioadm` |
| `minio-download` | `https://minio-download-aistor.apps.cluster-ls8dt.ls8dt.sandbox1882.opentlc.com` | S3 API (port 9000) — pre-signed URLs |

Both use edge TLS termination (ZeroSSL via OpenShift router) with HTTP → HTTPS redirect.

```bash
oc expose svc minio-fallback -n aistor --port=9001 --name=minio-console
oc expose svc minio-fallback -n aistor --port=9000 --name=minio-download
oc patch route minio-console  -n aistor --type=merge -p '{"spec":{"tls":{"termination":"edge","insecureEdgeTerminationPolicy":"Redirect"}}}'
oc patch route minio-download -n aistor --type=merge -p '{"spec":{"tls":{"termination":"edge","insecureEdgeTerminationPolicy":"Redirect"}}}'
```

| | |
|---|---|
| **Bucket** | `vision-models` |
| **Model key** | `models/yolov8n.onnx` |

---

## Useful oc commands

```bash
# Watch predictor pod
oc get pods -n ericsson-projects -w

# Check model is loaded in OVMS
oc exec -n ericsson-projects <predictor-pod> -- \
  curl -s http://localhost:8888/v2/models/yolo-onnx

# Tail predictor logs
oc logs -n ericsson-projects -l app=yolo-onnx-predictor -f

# Restart predictor (re-triggers storage initializer)
oc delete pod -n ericsson-projects -l app=yolo-onnx-predictor

# Port-forward for local testing
oc port-forward svc/yolo-onnx-predictor 8888:80 -n ericsson-projects
```
