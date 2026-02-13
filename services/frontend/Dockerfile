FROM python:3.13-slim

WORKDIR /app
RUN mkdir -p /app/keys

COPY services/frontend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/frontend/frontend_app/ ./frontend_app/
COPY services/frontend/config.py ./config.py
COPY services/frontend/wsgi.py ./wsgi.py

ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

EXPOSE 5000
CMD ["gunicorn", "-b", "0.0.0.0:5000", "wsgi:app"]
