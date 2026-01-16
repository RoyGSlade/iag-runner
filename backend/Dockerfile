FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/db.py ./db.py
COPY backend/models ./models
COPY backend/rules ./rules
COPY backend/llm ./llm
COPY backend/gm_os ./gm_os
COPY db ./db
COPY docs ./docs

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
