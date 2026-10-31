#!/bin/sh
set -eu
umask 077

case "${CADENTRA_TRUSTED_INGRESS-false}" in
  true) site=/etc/cadentra/nginx.production.conf ;;
  false) site=/etc/cadentra/nginx.development.conf ;;
  *) echo 'CADENTRA_TRUSTED_INGRESS must be exactly true or false' >&2; exit 64 ;;
esac

# The image filesystem may be read-only and the process runs as UID101. Only
# this container-local /tmp directory needs writes; /etc is never rewritten.
state=/tmp/cadentra-nginx
if [ -L "$state" ]; then
  echo 'Refusing a symbolic-link runtime directory' >&2
  exit 64
fi
mkdir -p "$state"
cat > "$state/nginx.conf" <<EOF
worker_processes auto;
pid $state/nginx.pid;
error_log stderr warn;
events { worker_connections 1024; }
http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    access_log off;
    sendfile on;
    keepalive_timeout 65;
    client_body_temp_path $state/client;
    proxy_temp_path $state/proxy;
    fastcgi_temp_path $state/fastcgi;
    uwsgi_temp_path $state/uwsgi;
    scgi_temp_path $state/scgi;
    include $site;
}
EOF

if [ "$#" -eq 0 ]; then
  set -- nginx -g 'daemon off;'
fi
if [ "$1" != nginx ]; then
  echo 'The frontend entrypoint only accepts nginx arguments' >&2
  exit 64
fi
shift
exec nginx -e stderr -p "$state/" -c "$state/nginx.conf" "$@"
