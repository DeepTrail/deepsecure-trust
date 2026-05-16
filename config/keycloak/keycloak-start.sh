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

# Sync redirect URIs for production domain if KC_PRODUCTION_DOMAIN is set
if [ -n "$KC_PRODUCTION_DOMAIN" ]; then
  echo "[keycloak-start] Adding production redirect URIs for ${KC_PRODUCTION_DOMAIN}..."
  CLIENT_ID=$(/opt/keycloak/bin/kcadm.sh get clients -r deepsecure -q clientId=deepsecure-control --fields id --format csv --noquotes 2>/dev/null | tail -1)
  if [ -n "$CLIENT_ID" ]; then
    /opt/keycloak/bin/kcadm.sh update "clients/${CLIENT_ID}" -r deepsecure \
      -s "redirectUris=[\"http://localhost:8000/api/v1/auth/sso/*/callback\",\"http://localhost:8000/*\",\"http://localhost:3000/api/auth/sso/*/callback\",\"http://localhost:3000/*\",\"https://localhost:8443/api/v1/auth/sso/*/callback\",\"https://localhost:8443/*\",\"https://${KC_PRODUCTION_DOMAIN}/api/v1/auth/sso/*/callback\",\"https://${KC_PRODUCTION_DOMAIN}/*\"]" \
      -s "webOrigins=[\"http://localhost:8000\",\"http://localhost:3000\",\"https://localhost:8443\",\"https://${KC_PRODUCTION_DOMAIN}\"]"
    echo "[keycloak-start] Production redirect URIs synced for ${KC_PRODUCTION_DOMAIN}."
  else
    echo "[keycloak-start] WARNING: Could not find deepsecure-control client."
  fi
fi

wait $KC_PID
