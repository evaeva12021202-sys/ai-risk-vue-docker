FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY api/requirements.txt ./api-requirements.txt
RUN pip install --no-cache-dir -r api-requirements.txt
COPY backend/ ./backend/
COPY api/backend_init.py ./backend/__init__.py
COPY api/ ./api/
RUN mkdir -p /app/data && chown -R 10001:10001 /app
USER 10001
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
