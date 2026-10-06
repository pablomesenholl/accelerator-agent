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

# Download OPALX source
WORKDIR /opt
RUN git clone --depth 1 https://github.com/OPALX-project/OPALX.git

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

# Magnus jobs will work in this directory
WORKDIR /work