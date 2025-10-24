# Using standalone Python builds with multistage images.

# First, build the application in the `/bci` directory

# FROM docker.io/alpine AS builder
FROM quay.io/fedora/fedora-minimal:43 AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Compile Python files to bytecode after installation.
# https://docs.astral.sh/uv/reference/cli/#uv-sync--compile-bytecode
ENV UV_COMPILE_BYTECODE=1

# The method to use when installing packages from the global cache.
# https://docs.astral.sh/uv/reference/cli/#uv-sync--link-mode
ENV UV_LINK_MODE=copy

# Configure the Python directory so it is consistent.
# The directory to store the Python installation in.
# https://docs.astral.sh/uv/reference/cli/#uv-python-install--install-dir
ENV UV_PYTHON_INSTALL_DIR=/opt/python

# Whether uv should prefer system or managed Python versions.
# Only use the managed Python version.
# https://docs.astral.sh/uv/reference/environment/#uv_python_preference
# ENV UV_PYTHON_PREFERENCE=only-managed

# Require use of uv-managed Python versions.
# https://docs.astral.sh/uv/reference/cli/#uv-python-install--managed-python
ENV UV_MANAGED_PYTHON=1

# Disable the development dependency group
# https://docs.astral.sh/uv/reference/cli/#uv-sync--no-dev
ENV UV_NO_DEV=1

# Assert that the uv.lock will remain unchanged.
# https://docs.astral.sh/uv/reference/cli/#uv-sync--locked
ENV UV_LOCKED=1

WORKDIR /opt/bci

COPY . /opt/bci

# RUN --mount=type=bind,source=uv.lock,target=uv.lock \
#     --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
#     uv sync --no-install-local --no-install-project --no-install-workspace
RUN --mount=type=bind,source=uv.lock,target=uv.lock,relabel=shared \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml,relabel=shared \
    uv sync --no-install-local --no-install-project --no-install-workspace


# Then, use a final image without uv

# FROM docker.io/alpine
FROM quay.io/fedora/fedora-minimal:43

# Install rpm-ostree in the container
# --setopt=install_weak_deps=False \
# --exclude="container-selinux, bootc" \
RUN <<EORUN
    set -xeuo pipefail
    dnf --refresh install --assumeyes --allowerasing \
        --no-docs --disable-repo fedora-cisco-openh264 \
        --setopt=install_weak_deps=False \
        --exclude container-selinux \
    rpm-ostree
    dnf clean all
EORUN

# Copy the Python version
COPY --from=builder /opt/python /opt/python

# Copy the application from the builder
COPY --from=builder /opt/bci/.venv /opt/bci/.venv
COPY --from=builder /opt/bci/bci.py /opt/bci/bci.py

# Place executables in the environment at the front of the path
ENV PATH="/opt/bci/.venv/bin:${PATH}"

# Use `/bci` as the working directory
WORKDIR /opt/bci

# Run the bci application by default
# CMD ["/opt/bci/bci.py"]
ENTRYPOINT ["/opt/bci/bci.py"]
# CMD ["rpm-ostree",\
#     "compose",\
#     "build-chunked-oci",\
#     "--bootc",\
#     "--format-version=1",\
#     "--max-layers 96",\
#     "--from localhost/bci:build",\
#     "--output containers-storage:localhost/bci:rechunked"]
