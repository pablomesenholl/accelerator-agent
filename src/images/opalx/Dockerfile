# Image for OPALX serial CPU only build

FROM ubuntu:24.04

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install the tools needed to build OPALX -> Dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    gfortran \
    openmpi-bin \
    libopenmpi-dev \
    libgnutls28-dev \
    zlib1g-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Download OPALX source from my source
ARG OPALX_REPOSITORY=https://github.com/pablomesenholl/OPALX.git
ARG OPALX_REVISION=cb3b8ceea29645c9533233c3f6f14c3410c2b263

WORKDIR /opt
RUN git init OPALX \
    && cd OPALX \
    && git remote add origin "${OPALX_REPOSITORY}" \
    && git fetch --depth 1 origin "${OPALX_REVISION}" \
    && git checkout --detach FETCH_HEAD

# Configure and build a CPU serial Release version
WORKDIR /opt/OPALX
RUN cmake -S . -B build_serial \
    -DCMAKE_BUILD_TYPE=Release \
    -DPLATFORMS=SERIAL \
    -DOPALX_ENABLE_UNIT_TESTS=OFF \
    -DOPALX_ENABLE_EXAMPLES=OFF \
    -DOPALX_ENABLE_TESTS=OFF \
    && cmake --build build_serial -j 4

# Make "opalx" available as a normal command
RUN ln -s /opt/OPALX/build_serial/src/opalx /usr/local/bin/opalx

# Python runtime for Magnus integration
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Install the same Magnus SDK version used on the host
RUN python3 -m venv /opt/magnus-venv \
    && /opt/magnus-venv/bin/pip install --no-cache-dir "magnus-sdk==0.8.2"

# Make Python, pip and Magnus from the virtual environment available normally
ENV PATH="/opt/magnus-venv/bin:${PATH}"

# Magnus jobs will work in this directory
WORKDIR /work