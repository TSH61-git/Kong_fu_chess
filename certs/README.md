# certs/

Drop any extra CA certificate (`.crt`) your network requires here before
running `docker compose build` — e.g. a corporate TLS-inspecting proxy's
root CA. Every service Dockerfile trusts everything in this directory via
`update-ca-certificates` during the pip-install build stage, so `pip` can
reach PyPI even when the container's default trust store can't verify
your proxy's certificate.

Empty by default: nothing extra is trusted unless you add a file here.
Do not commit real corporate CA certs to version control — this directory
is gitignored except for this README.
