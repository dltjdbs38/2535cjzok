FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Pillow 등 이미지 처리 라이브러리가 필요로 하는 시스템 패키지.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo \
    zlib1g \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 정적파일을 미리 모아둔다 (whitenoise가 서빙할 수 있게). SECRET_KEY 등이 없어도
# collectstatic 자체는 돌아가게 임시 값을 넣어준다.
RUN DJANGO_SECRET_KEY=build-time-placeholder python manage.py collectstatic --noinput

EXPOSE 8000

# gunicorn으로 실제 프로덕션 WSGI 서버를 띄운다. worker 수는 나중에 부하테스트 결과 보고 조정하면 됨.
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
