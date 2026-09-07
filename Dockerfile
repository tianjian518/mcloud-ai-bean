# 多架构镜像：linux/amd64 + linux/arm64
FROM python:3.11-slim

ARG TARGETPLATFORM
ARG BUILDPLATFORM

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai \
    MCLD_DATA_DIR=/data

WORKDIR /app

COPY requirements.txt ./

# 优先用预编译 wheel（amd64 / arm64 都有）；没有 wheel 时再临时装编译器从源码构建
RUN pip install --no-cache-dir --only-binary=:all: -r requirements.txt \
    || (apt-get update \
        && apt-get install -y --no-install-recommends gcc python3-dev \
        && pip install --no-cache-dir -r requirements.txt \
        && apt-get purge -y --auto-remove gcc python3-dev \
        && rm -rf /var/lib/apt/lists/*)

COPY . /app

RUN mkdir -p /data && chmod 777 /data
VOLUME ["/data"]
EXPOSE 7860

HEALTHCHECK --interval=60s --timeout=8s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:7860/api/version',timeout=5).status==200 else 1)" || exit 1

CMD ["python", "-m", "app"]
