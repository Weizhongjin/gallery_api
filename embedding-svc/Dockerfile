FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir "infinity-emb[all,cpu]>=0.0.54"

# Model cache directory — mount a volume to persist across restarts
ENV HF_HOME=/app/models
ENV INFINITY_QUEUE_SIZE=32

EXPOSE 7997

# CPU inference, batch-size 8 (adjust for your hardware)
CMD ["infinity_emb", \
     "--model-id", "Marqo/marqo-fashionSigLIP", \
     "--port", "7997", \
     "--host", "0.0.0.0", \
     "--device", "cpu", \
     "--batch-size", "8"]
