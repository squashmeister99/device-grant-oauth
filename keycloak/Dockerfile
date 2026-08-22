FROM quay.io/keycloak/keycloak:23.0.0

# Copy realm configuration for auto-import
COPY realm-export.json /opt/keycloak/data/import/realm-export.json

# Set up logging
ENV QUARKUS_LOGGING_LEVEL=INFO
ENV QUARKUS_LOG_CONSOLE_JSON=false
