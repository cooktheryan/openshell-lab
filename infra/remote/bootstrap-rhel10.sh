#!/usr/bin/env bash
set -euo pipefail

if [[ $(id -u) -eq 0 ]]; then
    printf 'run this bootstrap as ec2-user, not root\n' >&2
    exit 1
fi

packages=(
    podman
    curl
    httpd
    python3
    git
    jq
    policycoreutils-python-utils
    firewalld
)
sudo dnf install -y "${packages[@]}"

if [[ ! -e /swapfile ]]; then
    sudo fallocate -l 2G /swapfile
    sudo chmod 0600 /swapfile
    sudo mkswap /swapfile
fi
if ! /usr/sbin/swapon --show=NAME --noheadings | grep -Fx /swapfile >/dev/null; then
    sudo /usr/sbin/swapon /swapfile
fi
if ! grep -Fqx '/swapfile none swap defaults 0 0' /etc/fstab; then
    printf '/swapfile none swap defaults 0 0\n' | sudo tee -a /etc/fstab >/dev/null
fi

if ! grep -q "^${USER}:" /etc/subuid || ! grep -q "^${USER}:" /etc/subgid; then
    sudo usermod --add-subuids 100000-165535 --add-subgids 100000-165535 "$USER"
fi
sudo loginctl enable-linger "$USER"
user_id=$(id -u)
export XDG_RUNTIME_DIR="/run/user/$user_id"
systemctl --user enable --now podman.socket
podman info --format '{{.Host.CgroupsVersion}}' | grep -Fx v2 >/dev/null

installer=$(mktemp)
trap 'rm -f "$installer"' EXIT
latest_release_url=$(curl -LsSf -o /dev/null -w '%{url_effective}' \
    https://github.com/NVIDIA/OpenShell/releases/latest)
if [[ ! "$latest_release_url" =~ /tag/(v[0-9]+\.[0-9]+\.[0-9]+)$ ]]; then
    printf 'unable to resolve a stable OpenShell release from %s\n' \
        "$latest_release_url" >&2
    exit 1
fi
latest_tag=${BASH_REMATCH[1]}
curl -LsSf \
    "https://raw.githubusercontent.com/NVIDIA/OpenShell/${latest_tag}/install.sh" \
    --output "$installer"
OPENSHELL_VERSION="${latest_tag}" sh "$installer"
installed_version=$(openshell --version)
installed_tag="v${installed_version#openshell }"
if [[ "$installed_tag" != "$latest_tag" ]]; then
    printf 'OpenShell version mismatch: expected %s, installed %s\n' \
        "$latest_tag" "$installed_tag" >&2
    exit 1
fi

install -d -m 0700 "$HOME/.config/openshell"
config="$HOME/.config/openshell/gateway.toml"
temporary=$(mktemp "$HOME/.config/openshell/gateway.toml.XXXXXX")
printf '%s\n' \
    '[openshell]' \
    'version = 1' \
    '' \
    '[openshell.gateway]' \
    'compute_drivers = ["podman"]' >"$temporary"
chmod 0600 "$temporary"
mv "$temporary" "$config"
systemctl --user enable openshell-gateway
systemctl --user restart openshell-gateway

if ! openshell gateway list --output json | jq -e \
    '.[] | select(.name == "openshell")' >/dev/null; then
    openshell gateway add --local https://127.0.0.1:17670
fi
gateway_ready=false
for _ in $(seq 1 30); do
    if openshell status >/dev/null 2>&1; then
        gateway_ready=true
        break
    fi
    sleep 2
done
if [[ "$gateway_ready" != true ]]; then
    printf 'OpenShell gateway readiness timed out after 60 seconds\n' >&2
    exit 1
fi
openshell status
openshell whoami
