#!/bin/bash
# Generate self-signed SSL certificate for development
mkdir -p ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ssl/key.pem \
  -out ssl/cert.pem \
  -subj "/C=TR/ST=Istanbul/L=Istanbul/O=FarmVision/CN=localhost"
echo "SSL certificate generated in ./ssl/"
echo "For production, replace with a valid certificate from Let's Encrypt."
