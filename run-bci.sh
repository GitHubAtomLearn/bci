#! /usr/bin/env bash

set -euo pipefail
# set -x

function main() {
    if [[ "${EUID}" -ne 0 ]]; then
        echo -e " \n Root access is required to perform actions on bootable containers.\n" 1>&2
        exit 1
    fi

    # https://www.freedesktop.org/software/systemd/man/latest/systemctl.html#show%20PATTERN%E2%80%A6%7CJOB%E2%80%A6
    podman_socket_active_state=$(systemctl show podman.socket -P ActiveState)
    if [[ "${podman_socket_active_state}" != "active" ]]; then
        systemctl start podman.socket
    fi

    name="bci"
    # repository="localhost/bci"
    repository="quay.io/operatement/bci"
    tag="latest"
    image=${repository}:${tag}
    key="https://raw.githubusercontent.com/GitHubAtomLearn/bci/refs/heads/main/quay.io-operatement-bci.pub"

    podman image pull ${image}

    function cosign_verify() {
        podman container run \
            --pull newer \
            --rm \
            --interactive \
            --tty \
            --name cosign \
            ghcr.io/sigstore/cosign/cosign:latest \
            verify \
            --key ${1} \
            ${2}
    }
    if ! [[ ${repository} =~ ^localhost/.* ]]; then
        echo -e "\nVerifying ${image}..."
        cosign_verify ${key} ${image}
        echo -e "\n"
    fi

    podman container run \
        --pull newer \
        --rm \
        --interactive \
        --tty \
        --volume /var/lib/containers/storage:/var/lib/containers/storage \
        --volume /run/podman:/run/podman \
        --volume .:/data \
        --workdir /data \
        --cap-add=sys_admin,mknod \
        --device=/dev/fuse \
        --security-opt label=disable \
        --name ${name} \
        ${image} \
        "${@}"
}
# --volume /dev:/dev \
# --volume /run/udev:/run/udev \
# --volume .:/data \
# --workdir /data \

# --volume "${PWD}":/pwd \
# --workdir /pwd \

# --volume .:/opt/bci \
# --volume /opt/bci/.venv \
# --privileged \
main "${@}"