Token Type: JWT (Stateless).

Claim Requirements: sub (User ID), role (RBAC), iat, exp, jti (for replay protection).

Mechanism: "All services must validate the signature using the shared Public Key provided by the auth_service."