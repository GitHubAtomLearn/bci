#! /usr/bin/env python3

import os
import subprocess
import argparse
import json
import tomllib
from pathlib import PurePosixPath, PosixPath
import re

import podman
from rich import progress


def main():
    if os.getuid() != 0:
        raise SystemExit(f"\n Root access is required to perform actions on bootable containers.\n")


    try:
        podman_socket_active_state = subprocess.run(
            ["systemctl", "show", "podman.socket", "-P", "ActiveState"], 
            capture_output=True, text=True, check=True).stdout.strip("\n")
        # print(f"Podman socket active state: {podman_socket_active_state}")
    except subprocess.CalledProcessError as error:
        print(f"\n Error executing command: {error}\n")
        raise SystemExit()
    try:
        if podman_socket_active_state != "active":
            subprocess.run(["systemctl", "start", "podman.socket"], check=True)
    except subprocess.CalledProcessError as error:
        print(f"\n Error executing command: {error}\n")
        raise SystemExit()


    parser = argparse.ArgumentParser(
        description="Build a (bootable) container image")
    # parser.set_defaults(func=lambda args: parser.print_usage())
    parser.add_argument("--version", action="version", version="%(prog)s Version 0.1.0")
    parser.add_argument("--podman-version", action="store_true",
        help="Show Podman and API version and exit")
    parser.add_argument("config_file", metavar="FILE",
        help="TOML file containing arguments to parse")

    args = parser.parse_args()
    # print(f"\n args: {type(args)} {args}\n")
    
    if args.podman_version:
        podman_api_version()
        raise SystemExit()
    
    run_auto_build(args)


def args_class_dict(args):
        class Arguments():
            def __init__(self, dictionary):
                for key, value in dictionary.items():
                    setattr(self, key, value)
        return Arguments(args)


# Provide a URI path for the libpod service.
def libpod_uri():
    uri = "unix:///run/podman/podman.sock"
    return uri


def client_connection_error():
    client.close()
    raise SystemExit(f"\n Error connecting to Podman service.\n")


def podman_api_version():
    with podman.PodmanClient(base_url=libpod_uri()) as client:
        if client.ping():
            try:
                client_version = client.version()
                print(f"\n Podman Release: {client_version["Version"]}")
                print(f" Podman API: {client_version["Components"][0]["Details"]["APIVersion"]}")
                print(f" Compatible API: {client_version["ApiVersion"]}\n")
                client.close()
            except podman.errors.exceptions.APIError as error:
                raise SystemExit(f"\n API Error: {error}\n")
            finally:
                client.close()
        else:
            client_connection_error()
    client.close()


def run_pull(args):
    images = []
    for image in args.images.values():
        images.append(image)
    for image in images:
        # print(f" image: {type({image})} {image}")
        repository = image.split(":")[0]
        # print(f" repository: {type({repository})} {repository}")
        tag = image.split(":")[1]
        # print(f" tag: {type({tag})} {tag}")
        with podman.PodmanClient(base_url=libpod_uri()) as client:
            if client.ping():
                try:
                    # TODO: Check the user input (type)
                    client.images.pull(
                        repository=repository,
                        tag=tag,
                        progress_bar=True
                    )
                except podman.errors.exceptions.APIError as error:
                    raise SystemExit(f"\n API Error: {error}\n")
            else:
                client_connection_error()
    client.close()


def run_verify(args):
    with podman.PodmanClient(base_url=libpod_uri()) as client:
        if client.ping():
            
            cosign_image = args.images["cosign"]

            try:
                # TODO: Check the user input (type)
                client_run_verify_cosign = client.containers.run(
                    image=cosign_image,
                    name="verify-cosign",
                    command=[
                        # "help",
                        r"verify",
                        cosign_image,
                        r"--certificate-identity",
                        r"keyless@projectsigstore.iam.gserviceaccount.com",
                        r"--certificate-oidc-issuer",
                        r"https://accounts.google.com"
                        ],
                    remove=True,
                    tty=True,
                    stdout=True,
                    stderr=True
                )
            except podman.errors.exceptions.ContainerError as error:
                raise SystemExit(f"\n Container Error: {error}\n")
            except podman.errors.exceptions.ImageNotFound as error:
                raise SystemExit(f"\n Image not found Error: {error}\n")
            except podman.errors.exceptions.APIError as error:
                raise SystemExit(f"\n API Error: {error}\n")
            finally:
                # TODO:
                # API Error: 500 Server Error:
                # Internal Server Error (creating container storage: the container name "verify-image" is already in use.
                # You have to remove that container to be able to reuse that name: that name is already in use)
                client.close()

            verify_cosign_image_output = client_run_verify_cosign.decode()
            # print(f"\n verify_cosign_image {type(verify_cosign_image_output)}:\n{verify_cosign_image_output}\n")
            print(f"{verify_cosign_image_output.rsplit("[")[0]}")

            try:
                # TODO: Check the user input (type)
                os_image = args.images["os"]
                os_verify_key = args.cosign["verify"]["os-verify-key"]

                client_run_verify_image = client.containers.run(
                    image=cosign_image,
                    name="verify-image",
                    command=[
                        r"verify",
                        r"--key",
                        os_verify_key,
                        os_image
                    ],
                    remove=True,
                    tty=True,
                    stdout=True,
                    stderr=True
                )
            except podman.errors.exceptions.ContainerError as error:
                raise SystemExit(f"\n Container Error: {error}\n")
            except podman.errors.exceptions.ImageNotFound as error:
                raise SystemExit(f"\n Image not found Error: {error}\n")
            except podman.errors.exceptions.APIError as error:
                raise SystemExit(f"\n API Error: {error}\n")
            finally:
                # TODO:
                # API Error: 500 Server Error:
                # Internal Server Error (creating container storage: the container name "verify-image" is already in use.
                # You have to remove that container to be able to reuse that name: that name is already in use)
                client.close()

            verify_image_output = client_run_verify_image.decode()
            # print(f"\n verify_image_output {type(verify_image_output)}:\n{verify_image_output}\n")
            print(f"{verify_image_output.rsplit("[")[0]}")

        else:
            client_connection_error()
    client.close()


def run_prune(args):
    with podman.PodmanClient(base_url=libpod_uri()) as client:
        if client.ping():
            try:
                # TODO: print(f"\n Removing dangling or unused images from local storage...\n")
                client_images_prune = client.images.prune(
                    filters={"dangling": "True"}
                )
                if client_images_prune["ImagesDeleted"]:
                    print(f"\n Deleted images:\n")
                    for image in client_images_prune["ImagesDeleted"]:
                        print(f" {image["Deleted"]}")
                if client_images_prune["SpaceReclaimed"]:
                    print(f"\n Reclaimed space: {round(client_images_prune["SpaceReclaimed"] / (1024 * 1024 * 1024), 2)} GB\n")
            except podman.errors.exceptions.APIError as error:
                raise SystemExit(f"\n API Error: {error}\n")
        else:
            client_connection_error()
    client.close()


def run_build(args):
    if PosixPath(args.build["dockerfile"]).exists():
        args_dockerfile_path = PurePosixPath(args.build["dockerfile"])
        parent_path = args_dockerfile_path.parent
        # print(f"\n path.is_absolute(): {type(parent_path.is_absolute())} {parent_path.is_absolute()}\n")
        if parent_path.is_absolute():
            full_path = parent_path
            # print(f"\n full_path: {type(full_path)} {full_path}\n")
            dockerfile = args.build["dockerfile"]
            # print(f"\n dockerfile: {type(dockerfile)} {dockerfile}\n")
        else:
            full_path = PosixPath.absolute(parent_path)
            # print(f"\n full_path: {type(full_path)} {full_path}\n")
            dockerfile = PurePosixPath(full_path/args_dockerfile_path.name)
            # print(f"\n dockerfile: {type(dockerfile)} {dockerfile}\n")
    else:
        raise SystemExit(f"\n Image file not found.\n")
    tag = args.build["tag"]
    with podman.PodmanClient(base_url=libpod_uri()) as client:
        if client.ping():
            # TODO: Check the user input (type)
            print(f"\n Building the container image. It may take a while.\n")
            try:
                if args.build["log"]:
                    print(f" A full log will be displayed when the image build process is complete.\n")
                    client_images_build = client.images.build(path=full_path, dockerfile=dockerfile, tag=tag, pull=True)
                    for line in client_images_build[-1]:
                        log_message = json.loads(line.decode("UTF-8"))["stream"]
                        print(log_message.strip("\n"))
                else:
                    client.images.build(path=path, dockerfile=dockerfile, tag=tag, pull=True)
            except podman.errors.exceptions.BuildError as error:
                raise SystemExit(f"\n Error building image: {error}\n")
            except podman.errors.exceptions.APIError as error:
                raise SystemExit(f"\n API Error: {error}\n")
            except podman.errors.exceptions.TypeError as error:
                raise SystemExit(f"\n Type Error: {error}\n")
        else:
            client_connection_error()
    client.close()
    run_prune(args)


def run_rechunk(args):
    argv = ["rpm-ostree",
            "compose",
            "build-chunked-oci"]
    if args.rechunk["max-layers"]:
        argv.append(f"--max-layers={args.rechunk["max-layers"]}")
    argv.extend(["--bootc",
            "--format-version=1",
            f"--from={args.rechunk["from-image"]}",
            f"--output=containers-storage:{args.rechunk["to-image"]}"])
    try:
        print(f"\n Rechunking the container image...\n")
        subprocess.run(argv, check=True)
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"\n Error executing command: {error}\n")
    run_prune(args)


def get_image_version(args):
    with podman.PodmanClient(base_url=libpod_uri()) as client:
        if client.ping():
            image = args.images["os"]
            image_labels = client.images.get(image).labels
            # print(f"\n image_labels: {type(image_labels)} {image_labels}\n")
            # for key, value in image_labels.items():
            #     print(f" {type({key})} {key}: {type({value})} {value}")
            
            image_version = image_labels["org.opencontainers.image.version"]
            return image_version
        else:
            client_connection_error()
    client.close()


def image_labels(args):
    with podman.PodmanClient(base_url=libpod_uri()) as client:
        os_image = args.images["os"]
        if client.ping():
            try:
                client_run_os_release = client.containers.run(
                    image=os_image,
                    name=r"add-labels",
                    command=[
                        r"cat",
                        r"/usr/lib/os-release"
                    ],
                    remove=True,
                    tty=True,
                    stdout=True,
                    stderr=True
                )
                os_release = client_run_os_release.decode()
            except podman.errors.exceptions.BuildError as error:
                print(f"\n Error building image: {error}\n")
                raise SystemExit()
            except podman.errors.exceptions.APIError as error:
                raise SystemExit(f"\n API Error: {error}\n")
            # except podman.errors.exceptions.TypeError as error:
            #     raise SystemExit(f"\n Type Error: {error}\n")
            finally:
                client.close()
        else:
            client_connection_error()
    client.close()
    toml_labels = args.labels
    compiled_labels = {
        "org.opencontainers.image.version": get_image_version(args),
        "org.opencontainers.image.title": f"{re.search(r"^PRETTY_NAME.+",
            os_release, re.MULTILINE).group(0).removeprefix("PRETTY_NAME=").replace("\"", "").rstrip("\r")}",
        "org.opencontainers.image.description": f"Customized image of {re.search(r"NAME.+",
            os_release, re.MULTILINE).group(0).removeprefix("NAME=").replace("\"", "").rstrip("\r")}",
    }
    labels = toml_labels.copy()
    for label, value in toml_labels.items():
        if not value:
            labels.update(compiled_labels)
    return labels


def run_add_labels(args):
    nop_dockerfile_content = f"FROM {args.rechunk["to-image"]}"
    nop_dockerfile_path = PosixPath("/tmp/nop_dockerfile")
    nop_dockerfile_path.write_text(nop_dockerfile_content)
    if PosixPath(nop_dockerfile_path).exists():
        args_dockerfile_path = PurePosixPath(nop_dockerfile_path)
        parent_path = args_dockerfile_path.parent
        # print(f"\n path.is_absolute(): {type(parent_path.is_absolute())} {parent_path.is_absolute()}\n")
        if parent_path.is_absolute():
            full_path = parent_path
            # print(f"\n full_path: {type(full_path)} {full_path}\n")
            dockerfile = nop_dockerfile_path
            # print(f"\n dockerfile: {type(dockerfile)} {dockerfile}\n")
        else:
            full_path = PosixPath.absolute(parent_path)
            print(f"\n full_path: {type(full_path)} {full_path}\n")
            dockerfile = PurePosixPath(full_path/args_dockerfile_path.name)
            print(f"\n dockerfile: {type(dockerfile)} {dockerfile}\n")
    else:
        raise SystemExit(f"\n Image file not found.\n")
    tag = args.build["labels"]["tag"]
    with podman.PodmanClient(base_url=libpod_uri()) as client:
        if client.ping():
            # TODO: Check the user input (type)
            labels = image_labels(args)
            # print(f"\n labels: {type(labels)} {labels}\n")
            # for key, value in labels.items():
            #     print(f" {type({key})} {key}: {type({value})} {value}")
            print(f"\n Adding labels to container image. It may take a while.\n")
            try:
                if args.build["log"]:
                    print(f" A full log will be displayed when the image build process is complete.\n")
                    client_images_build = client.images.build(
                        path=full_path,
                        dockerfile=dockerfile,
                        tag=tag,
                        pull=True,
                        labels=labels
                    )
                    for line in client_images_build[-1]:
                        log_message = json.loads(line.decode("UTF-8"))["stream"]
                        print(log_message.strip("\n"))
                else:
                    client.images.build(
                        path=path,
                        dockerfile=dockerfile,
                        tag=tag, pull=True
                    )
            except podman.errors.exceptions.BuildError as error:
                print(f"\n Error building image: {error}\n")
                raise SystemExit()
            except podman.errors.exceptions.APIError as error:
                raise SystemExit(f"\n API Error: {error}\n")
            # except podman.errors.exceptions.TypeError as error:
            #     raise SystemExit(f"\n Type Error: {error}\n")
            finally:
                client.close()
                nop_dockerfile_path.unlink()
        else:
            client_connection_error()
    client.close()
    run_prune(args)


def run_rm_intermediate_images(args):
    images_to_remove = []
    if args.build["remove-intermediate"]:
        images_to_remove.append(args.build["tag"])
    if args.rechunk["remove-intermediate"]:
        images_to_remove.append(args.rechunk["to-image"])
    if images_to_remove:
        print(f"\n Deleting intermediate images...\n")
        for image in images_to_remove:
            with podman.PodmanClient(base_url=libpod_uri()) as client:
                if client.ping():
                    try:
                        # TODO: Check the user input (type)
                        client_images_remove = client.images.remove(
                            image
                        )
                        # print(f"\n client_images_remove: {type(client_images_remove)} {client_images_remove}\n")
                        for removed_image in client_images_remove:
                            for key in ("Deleted", "Untagged"):
                                if key in removed_image.keys():
                                    print(f" {key}: {removed_image.get(key)}")
                    except podman.errors.exceptions.APIError as error:
                        raise SystemExit(f"\n API Error: {error}\n")
                    except podman.errors.exceptions.ImageNotFound as error:
                        raise SystemExit(f"\n Image not found: {error}\n")
                else:
                    client_connection_error()
            client.close()
        run_prune(args)


def run_auto_build(args):

    with open(args.config_file, "rb") as file:
        args_dict = tomllib.load(file)
    # print(f"\n args_dict: {type(args_dict)} {args_dict}\n")
    args = args_class_dict(args_dict)
    run_pull(args)
    if args.cosign["verify"]["verify"]:
        run_verify(args)
    run_build(args)
    run_rechunk(args)
    if args.build["labels"]["add-labels"]:
        run_add_labels(args)
    run_rm_intermediate_images(args)
    run_prune(args)


if __name__ == "__main__":
    # https://docs.python.org/library/exceptions.html#SystemExit
    raise SystemExit(main())
