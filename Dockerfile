FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY pipeline ./pipeline
COPY site ./site
COPY tests ./tests
EXPOSE 8080
CMD ["python", "-m", "pipeline.serve", "--bind", "0.0.0.0", "--port", "8080", "--interval-hours", "6"]
