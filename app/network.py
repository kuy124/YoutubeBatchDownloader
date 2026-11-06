"""Verified HTTPS for source installs and frozen releases."""
import os
import ssl
import sys

import certifi


def tls_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    # Respect administrator overrides; never retry with verification disabled.
    if os.environ.get("SSL_CERT_FILE") or os.environ.get("SSL_CERT_DIR"):
        return context
    if sys.platform.startswith("linux"):
        # Frozen Python may retain OpenSSL paths from the build distribution.
        for bundle in ("/etc/pki/tls/certs/ca-bundle.crt",
                       "/etc/ssl/certs/ca-certificates.crt",
                       "/etc/ssl/ca-bundle.pem"):
            if os.path.isfile(bundle):
                context.load_verify_locations(cafile=bundle)
                return context
    context.load_verify_locations(cafile=certifi.where())
    return context
