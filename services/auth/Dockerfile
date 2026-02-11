FROM python:3.13-slim

WORKDIR /app

COPY services/auth/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/auth/auth_app/ ./auth_app/
COPY services/auth/config.py ./config.py
COPY services/auth/wsgi.py ./wsgi.py

ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

EXPOSE 5000
CMD ["gunicorn", "-b", "0.0.0.0:5000", "wsgi:app"]

