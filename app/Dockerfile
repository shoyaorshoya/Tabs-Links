FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/data
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY closedtabs ./closedtabs
VOLUME /data
EXPOSE 3000
CMD ["uvicorn", "closedtabs.web:app", "--host", "0.0.0.0", "--port", "3000"]
