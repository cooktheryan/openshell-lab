#!/usr/bin/env bash
set -euo pipefail

LAB_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd -- "$LAB_DIR/../.." && pwd)

sudo install -d -m 0755 /var/www/html/openshell-lab
podman unshare chown -R 1000:1000 /var/www/html/openshell-lab
sudo chmod 0755 /var/www/html/openshell-lab

install -d -m 0700 "$HOME/.config/openshell"
config="$HOME/.config/openshell/gateway.toml"
temporary=$(mktemp "$HOME/.config/openshell/gateway.toml.XXXXXX")
printf '%s\n' \
    '[openshell]' \
    'version = 1' \
    '' \
    '[openshell.gateway]' \
    'compute_drivers = ["podman"]' \
    '' \
    '[openshell.drivers.podman]' \
    'enable_bind_mounts = true' >"$temporary"
chmod 0600 "$temporary"
mv "$temporary" "$config"
systemctl --user restart openshell-gateway
openshell status >/dev/null

sudo install -m 0644 \
    "$ROOT/infra/remote/openshell-lab-httpd.conf" \
    /etc/httpd/conf.d/openshell-lab.conf
sudo setsebool -P httpd_can_network_connect 1
sudo systemctl enable --now firewalld httpd
sudo firewall-cmd --permanent --add-service=http >/dev/null
sudo firewall-cmd --reload >/dev/null
sudo apachectl configtest
