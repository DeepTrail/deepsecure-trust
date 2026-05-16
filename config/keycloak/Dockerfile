FROM quay.io/keycloak/keycloak:24.0
COPY deepsecure-realm.json /opt/keycloak/data/import/deepsecure-realm.json
COPY keycloak-start.sh /opt/keycloak/data/import/keycloak-start.sh
ENTRYPOINT ["/bin/bash", "/opt/keycloak/data/import/keycloak-start.sh"]
