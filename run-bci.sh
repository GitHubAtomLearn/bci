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
    repository="localhost/bci"
    tag="latest"
    image=${repository}:${tag}
    # podman image pull ${container_image}
    podman container run \
        --pull newer \
        --rm \
        --interactive \
        --tty \
        --volume /run/podman:/run/podman \
        --cap-add=sys_admin,mknod \
        --device=/dev/fuse \
        --security-opt label=disable \
        --name ${name} \
        ${image} \
        "${@}"
}
# --volume .:/opt/bci \
# --volume /opt/bci/.venv \
# --privileged \
main "${@}"