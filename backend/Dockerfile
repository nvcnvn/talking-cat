FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HOME=/models
WORKDIR /srv

COPY requirements-base.txt requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Bake the Piper fallback voice into the image (~63 MB) so first start needs no download.
ARG PIPER_VOICE=vi_VN-vais1000-medium
RUN python -m piper.download_voices --data-dir /opt/piper ${PIPER_VOICE}

COPY app ./app
COPY scripts ./scripts

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
