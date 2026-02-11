FROM python:3.13-slim

WORKDIR /app

COPY services/tasks/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/tasks/task_app/ ./task_app/
COPY services/tasks/config.py ./config.py
COPY services/tasks/wsgi.py ./wsgi.py

ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

EXPOSE 5000
CMD ["gunicorn", "-b", "0.0.0.0:5000", "wsgi:app"]

