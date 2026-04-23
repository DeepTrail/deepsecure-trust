#!/bin/bash
# Wrapper script: start Keycloak, then disable sslRequired on the master realm
# so the admin console is accessible over plain HTTP in development.

/opt/keycloak/bin/kc.sh start-dev --import-realm &
KC_PID=$!

echo "[keycloak-start] Waiting for Keycloak to become ready..."
until /opt/keycloak/bin/kcadm.sh config credentials \
  --server http://localhost:8080 \
  --realm master \
  --user "$KEYCLOAK_ADMIN" \
  --password "$KEYCLOAK_ADMIN_PASSWORD" 2>/dev/null; do
  sleep 2
done

echo "[keycloak-start] Disabling sslRequired on master realm..."
/opt/keycloak/bin/kcadm.sh update realms/master -s sslRequired=NONE
echo "[keycloak-start] Master realm SSL requirement disabled — admin console accessible over HTTP."

wait $KC_PID
