# Hosted GPU inference preparation

## Current status

The portable service and local NeuroVista integration are implemented, but **no hosted service has been provisioned or published and no scans have been uploaded**. GPU execution of the container remains unverified until an approved provider deployment runs the exact public research test case. NeuroVista remains labelled **Research and education only — not for clinical diagnosis**.

The local viewer and manual **AI prediction · imported** workflow remain available independently of this optional service.

## Model and container contract

`inference_service/Dockerfile` builds a Python 3.12 image with the Colab-adapted stack: PyTorch 2.4.0/CUDA 12.1, MONAI 1.4.0, NumPy 1.26.4, nibabel 5.2.1, and the other notebook pins. Build time downloads the official MONAI `brats_mri_segmentation` 0.5.4 weight and refuses the build unless SHA-256 equals `860ccb3f1c21c99d0410ad8a1ac4ef6b8fab60cec0a503b0ba42675741a750ae`. Weights are embedded in the built image, never committed to Git.

The inference contract is unchanged from the verified notebook:

- inputs, in order: T1c/T1ce, T1, T2, FLAIR from one already aligned case
- finite numeric 3D NIfTI, millimetre units, 1 mm spacing, identical dimensions and affine
- SegResNet: 4 inputs, 3 sigmoid outputs, release-exact block configuration
- nonzero channel-wise intensity normalization
- sliding window `240 × 240 × 160`, batch 1, overlap 0.5
- threshold 0.5; convert nested TC/WT/ET channels to labels 1, 2 and 4
- write the label map with the original T1c shape, affine and header geometry

## Service API and controls

The worker provides:

- unauthenticated `GET /health`, containing no case data
- authenticated `POST /v1/jobs` with required multipart fields `t1c`, `t1`, `t2`, `flair`
- authenticated `GET /v1/jobs/{job_id}`
- authenticated `GET /v1/jobs/{job_id}/result`

All job routes require a bearer token supplied through `NEUROVISTA_INFERENCE_TOKEN`. Generate it outside Git and configure the same value only on the GPU service and local FastAPI backend. The browser never receives it.

The container runs one ASGI worker and one GPU job at a time. A bounded queue rejects excess jobs. A job runs in a child process so the parent can terminate it after the configured timeout. Per-file, total-request and decompressed-volume limits are enforced; failed inputs are deleted; accepted inputs are deleted immediately after packaging; result packages expire automatically. Uvicorn access logging is disabled and application errors do not include filenames, voxel data, credentials or request bodies.

Remote URLs configured in the local backend must use HTTPS. Plain HTTP is accepted only for `127.0.0.1`/`localhost` integration tests. TLS termination should be supplied by the hosting platform or a managed HTTPS load balancer; do not expose container port 8080 directly to the public internet.

## Local GPU smoke test

This requires Docker, NVIDIA Container Toolkit, a compatible NVIDIA driver and at least one GPU. It has not been run on the current Intel-only computer.

```powershell
$env:NEUROVISTA_INFERENCE_TOKEN = '<long random value>'
docker compose -f docker-compose.inference.yml build
docker compose -f docker-compose.inference.yml up -d
```

Configure the local backend for the localhost-only smoke test:

```powershell
$env:NEUROVISTA_INFERENCE_URL = 'http://127.0.0.1:8080'
$env:NEUROVISTA_INFERENCE_TOKEN = '<same value>'
```

Use only a de-identified public research case, initially MSD Task01 `BRATS_457`, acknowledging that possible model-training overlap remains unresolved. Do not interpret a successful run as independent validation or diagnostic accuracy.

## Hosting comparison (checked 20 October 2026)

| Option | Suitable GPU / memory | Published compute cost | Startup | Storage and deployment |
|---|---|---:|---|---|
| Runpod Serverless | 24 GB L4/A5000/3090 class | $0.69/hour, billed per second | Flex workers scale to zero; Runpod advertises sub-200 ms FlashBoot, but model/container initialization still adds time | Custom container; optional persistent network storage; adapt the included ASGI API to Runpod's serverless handler contract or use a Pod |
| Modal | 24 GB L4 | $0.000222/GPU-second ($0.7992/hour), plus CPU/RAM; volumes $0.09/GiB-month | Modal documents 1–2 second container spin-up; image/model initialization is additional; default 60-second billed idle window | Python-native deployment, secrets and volumes; the Docker application needs a thin Modal wrapper rather than direct container serving |
| Google Compute Engine | G2 `g2-standard-4`: one 24 GB L4, 4 vCPU, 16 GB system RAM | L4 GPU list price $0.56004024/hour, plus VM, disk and egress | VM provisioning is generally minutes rather than scale-to-zero request startup | Build/push the container, install/use NVIDIA runtime, configure HTTPS load balancer, firewall, disk and lifecycle automation |

Prices exclude taxes, data transfer and any provider-specific CPU, RAM, image-registry or storage charges unless explicitly stated. Provider prices and availability can change; re-check before approval.

Official sources:

- Runpod serverless product and pricing: https://www.runpod.io/product/serverless and https://www.runpod.io/pricing
- Modal GPU/cold-start/pricing documentation: https://modal.com/docs/guide/gpu, https://modal.com/docs/guide/cold-start and https://modal.com/pricing
- Google GPU types and pricing: https://docs.cloud.google.com/compute/docs/gpus/ and https://cloud.google.com/products/compute/gpus-pricing

## Recommended approval choice

For the first small research demonstration, use a **Runpod 24 GB L4 Pod**, stopped immediately after the test. It accepts the prepared Docker image directly, provides 50 GB system RAM in the current published configuration, and is simpler to audit than adding provider-specific serverless code before the first container benchmark. The current listed L4 Pod compute price is **$0.59/hour**. Budget **$1–$2 for up to two hours** of build/pull, startup, one BRATS_457 run, result retrieval and troubleshooting, plus small image/storage/egress charges. Set a hard spending limit where available and delete the Pod/storage after preserving the result.

This is a recommendation for approval, not authorization to create the Pod. Before deployment: choose region, review provider data handling, create a private container registry entry, configure a long random bearer token as a provider secret, put the service behind provider HTTPS, restrict inbound access where supported, and confirm automatic shutdown/deletion.

## Verification boundary

Completed locally:

- Python syntax and static frontend build
- geometry/finite-value validation tests
- mocked HTTPS client availability/submission tests
- backend-only bearer-token handling
- queue/status/result code paths and local result revalidation by inspection/tests

Still requires an approved GPU deployment:

- Docker image build and official weight download/checksum in the build environment
- CUDA/container compatibility and actual release-exact inference
- measured cold start, GPU/RAM/runtime and timeout behavior
- authenticated HTTPS round trip with public de-identified data
- provider-side deletion and local automatic overlay/measurement/3D loading after a real result

