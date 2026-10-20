FROM python:3.12.13-slim-bookworm

ARG MODEL_URL=https://huggingface.co/MONAI/brats_mri_segmentation/resolve/0.5.4/models/model.pt
ARG MODEL_SHA256=860ccb3f1c21c99d0410ad8a1ac4ef6b8fab60cec0a503b0ba42675741a750ae

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    NEUROVISTA_MODEL_PATH=/opt/neurovista/weights/model.pt \
    NEUROVISTA_MODEL_SHA256=${MODEL_SHA256}

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/neurovista
COPY inference_service/requirements.txt /tmp/requirements.txt
RUN python -m pip install --index-url https://download.pytorch.org/whl/cu121 torch==2.4.0 torchvision==0.19.0 torchaudio==2.4.0 \
    && python -m pip install -r /tmp/requirements.txt
RUN mkdir -p /opt/neurovista/weights \
    && curl --fail --location --retry 3 --output /opt/neurovista/weights/model.pt "${MODEL_URL}" \
    && echo "${MODEL_SHA256}  /opt/neurovista/weights/model.pt" | sha256sum --check -
COPY inference_service/app /opt/neurovista/app
RUN useradd --create-home --uid 10001 neurovista && chown -R neurovista:neurovista /opt/neurovista
USER neurovista
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--no-access-log"]

