FROM docker:24.0.9

USER root

RUN apk add --no-cache \
    bash \
    yq \
    ca-certificates && \
    update-ca-certificates

# Trust local.test registry CA
COPY local-test-ca.crt /usr/local/share/ca-certificates/local-test-ca.crt
RUN update-ca-certificates