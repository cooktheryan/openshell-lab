#!/usr/bin/env bash
set -euo pipefail

LAB_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd -- "$LAB_DIR/../.." && pwd)

sudo install -d -m 0755 /var/www/html/openshell-lab
sudo chown -R "$USER:$USER" /var/www/html/openshell-lab
podman unshare chown -R 1500:1500 /var/www/html/openshell-lab
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
gateway_ready=false
for _ in $(seq 1 30); do
    if openshell status >/dev/null 2>&1; then
        gateway_ready=true
        break
    fi
    sleep 2
done
[[ "$gateway_ready" == true ]] || {
    printf 'OpenShell gateway did not become ready after restart\n' >&2
    exit 1
}

sudo install -m 0644 \
    "$ROOT/infra/remote/openshell-lab-httpd.conf" \
    /etc/httpd/conf.d/openshell-lab.conf
sudo setsebool -P httpd_can_network_connect 1
sudo systemctl enable --now firewalld httpd
sudo firewall-cmd --permanent --add-service=http >/dev/null
sudo firewall-cmd --reload >/dev/null
sudo apachectl configtest
sudo systemctl reload httpd
