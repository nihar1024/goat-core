FROM python:3.11.12-bookworm
# create directory for the app user
RUN mkdir -p /app
WORKDIR /app/
# Create the app user
#RUN addgroup --system app && adduser --system --group app
# Set environment variables for Python
ENV DISPLAY :99
ENV DEBIAN_FRONTEND noninteractive
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV ENVIRONMENT prod
ENV PYTHONPATH "${PYTHONPATH}:."
ENV USE_PYGEOS 0

# Set environment variables for Celery
ENV CELERYD_NODES 1
ENV CELERY_BIN "celery"
ENV CELERYD_CHDIR "/app"
ENV CELERY_APP "src.workers.celery_app"
ENV CELERYD_LOG_FILE "/var/log/celery/%n%I.log"
ENV CELERYD_PID_FILE "/var/run/celery/%n.pid"
ENV CELERYD_USER "root"
ENV CELERYD_GROUP "root"
ENV CELERY_CREATE_DIRS 1
ENV CELERY_RESULT_EXPIRES 120
ENV UVICORN_PORT 5000


# Install system dependencies
RUN apt-get update \
    && apt-get -y install netcat-traditional gcc libpq-dev software-properties-common \
    && apt-get clean


# Install pymgl runtime dependencies
RUN apt install --fix-missing --no-install-recommends -y \
    xvfb \
    xauth \
    curl \
    libicu72 \
    libjpeg-turbo-progs \
    libpng16-16 \
    libprotobuf32 \
    libuv1 \
    libx11-6 \
    libegl1 \
    libopengl0


# Install gdal binaries
RUN apt-get update && apt-get install -y python3-dev gdal-bin libgdal-dev

# Install qgis
RUN wget -O /etc/apt/keyrings/qgis-archive-keyring.gpg https://download.qgis.org/downloads/qgis-archive-keyring.gpg
RUN printf "Types: deb deb-src\nURIs: https://qgis.org/debian\nSuites: %s\nArchitectures: amd64\nComponents: main\nSigned-By: /etc/apt/keyrings/qgis-archive-keyring.gpg\n" "$(lsb_release -cs)" | tee /etc/apt/sources.list.d/qgis.sources
RUN apt-get update && apt-get install -y qgis python3-qgis

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | POETRY_HOME=/opt/poetry python && \
    cd /usr/local/bin && \
    ln -s /opt/poetry/bin/poetry && \
    poetry config virtualenvs.create false

# Download Celery daemon
RUN curl -sSL https://raw.githubusercontent.com/celery/celery/master/extra/generic-init.d/celeryd > /etc/init.d/celeryd && \
    chmod +x /etc/init.d/celeryd

# Copy poetry.lock* in case it doesn't exist in the repo
COPY ./pyproject.toml ./poetry.lock* /app/
# Allow installing dev dependencies to run tests
ARG INSTALL_DEV=false
RUN bash -c "if [ $INSTALL_DEV == 'True' ] ; then apt-get update && apt-get install -y --no-install-recommends postgresql-client-15 ; fi"
RUN bash -c "if [ $INSTALL_DEV == 'True' ] ; then poetry install --no-root ; else poetry install --no-root --only main ; fi"
COPY . /app


CMD bash -c "Xvfb ${DISPLAY} -screen 0 '1024x768x24' -ac +extension GLX +render -noreset -nolisten tcp & exec uvicorn src.main:app --host 0.0.0.0 --port ${UVICORN_PORT}"

ENV PYTHONPATH "${PYTHONPATH}:/usr/lib/python3/dist-packages"
