FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd -m clima
COPY . .
RUN mkdir -p /data && chown -R clima:clima /app /data
USER clima
ENV CLIMA_HOST=0.0.0.0 PORT=8080 CLIMA_DB=/data/clima.sqlite3
EXPOSE 8080
CMD ["python", "launch.py"]
