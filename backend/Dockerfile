FROM python:3.12-slim

WORKDIR /app

ENV PYTHONPATH=/app
ENV PIP_DEFAULT_TIMEOUT=300

# Install CPU-only PyTorch first.
# This prevents sentence-transformers from pulling
# the much larger CUDA-enabled PyTorch package from PyPI.
RUN pip install --no-cache-dir \
    torch \
    --index-url https://download.pytorch.org/whl/cpu

# Install the remaining application dependencies.
COPY backend/requirements.txt .

RUN pip install --no-cache-dir \
    -r requirements.txt

# Application source
COPY backend/app ./app

# Evaluation tests
COPY tests ./tests

CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port `${PORT:-8000}"
