FROM python:3.13-slim

WORKDIR /app

COPY gateway/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY gateway/gateway_app/ ./gateway_app/
COPY gateway/config.py ./config.py
COPY gateway/wsgi.py ./wsgi.py

ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

EXPOSE 5000
CMD ["gunicorn", "-b", "0.0.0.0:5000", "wsgi:app"]

