#!/bin/bash
# Fix CA cert to include basicConstraints=CA:TRUE
set -euo pipefail

CERTS_DIR="/tls"
WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT

echo "Fixing CA certificate..."

# Create OpenSSL config for CA with proper extensions
cat >"$WORK_DIR/openssl-ca.cnf" <<EOF
[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_ca
prompt = no

[req_distinguished_name]
O = n8n-sandbox
CN = sandbox-mtls-ca

[v3_ca]
basicConstraints = critical,CA:TRUE
keyUsage = critical,keyCertSign,cRLSign
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always
EOF

# Regenerate CA cert with proper extensions (self-signed)
openssl req -new -x509 -key "$CERTS_DIR/ca.key" -out "$WORK_DIR/ca-new.crt" -days 3650 -config "$WORK_DIR/openssl-ca.cnf"

# Verify the new CA cert has proper extensions
echo "Verifying new CA cert..."
openssl x509 -in "$WORK_DIR/ca-new.crt" -noout -ext basicConstraints -ext keyUsage

# Replace the CA cert
cp "$WORK_DIR/ca-new.crt" "$CERTS_DIR/ca.crt"
cp "$WORK_DIR/ca-new.crt" "$CERTS_DIR/api/ca.crt"
cp "$WORK_DIR/ca-new.crt" "$CERTS_DIR/runner/ca.crt"

# Function to re-sign a leaf cert
resign_cert() {
    local key_file="$1"
    local subj="$2"
    local san="$3"
    local eku="$4"
    local out_file="$5"

    cat >"$WORK_DIR/leaf.ext" <<EOF
[v3_req]
subjectAltName = $san
extendedKeyUsage = $eku
EOF

    openssl req -new -key "$key_file" -subj "$subj" | \
    openssl x509 -req -CA "$WORK_DIR/ca-new.crt" -CAkey "$CERTS_DIR/ca.key" -CAcreateserial \
        -out "$out_file" -days 825 -extfile "$WORK_DIR/leaf.ext" -extensions v3_req
}

# Re-sign all leaf certificates with the new CA cert
echo "Re-signing API gRPC server cert..."
resign_cert "$CERTS_DIR/api/grpc-server.key" "/O=n8n-sandbox/CN=sandbox-api" "DNS:sandbox-api" "serverAuth" "$WORK_DIR/grpc-server-new.crt"
cp "$WORK_DIR/grpc-server-new.crt" "$CERTS_DIR/api/grpc-server.crt"

echo "Re-signing Runner gRPC client cert..."
resign_cert "$CERTS_DIR/runner/grpc-client.key" "/O=n8n-sandbox/CN=sandbox-runner-mtls-client" "DNS:sandbox-runner-mtls-client" "clientAuth" "$WORK_DIR/grpc-client-new.crt"
cp "$WORK_DIR/grpc-client-new.crt" "$CERTS_DIR/runner/grpc-client.crt"

echo "Re-signing Runner control gRPC server cert..."
resign_cert "$CERTS_DIR/runner/control-grpc-server.key" "/O=n8n-sandbox/CN=runner-sandbox-control" "DNS:sandbox-runner-1,DNS:localhost" "serverAuth" "$WORK_DIR/control-grpc-server-new.crt"
cp "$WORK_DIR/control-grpc-server-new.crt" "$CERTS_DIR/runner/control-grpc-server.crt"

echo "Re-signing API control gRPC client cert..."
resign_cert "$CERTS_DIR/api/control-grpc-api-client.key" "/O=n8n-sandbox/CN=sandbox-api-control-mtls-client" "DNS:sandbox-api-control-mtls-client" "clientAuth" "$WORK_DIR/control-grpc-api-client-new.crt"
cp "$WORK_DIR/control-grpc-api-client-new.crt" "$CERTS_DIR/api/control-grpc-api-client.crt"

echo "Certificates fixed successfully!"