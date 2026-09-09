FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV DB_PATH=/data/mychores.db
ENV PORT=5000
EXPOSE 5000

RUN mkdir -p /data
CMD ["python", "app.py"]

