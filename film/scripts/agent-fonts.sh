#!/usr/bin/env bash
# Reproduce the font environment of the agents' jailed Chromium (hosted image: python:3.12-slim-bookworm + `playwright install --with-deps
# chromium`, i.e. the Playwright font packages and no DejaVu) so the 2x website renders match the agents' recorded screenshots
# (system-ui -> Loma, serif -> Liberation Serif). The packages are extracted into film/.fonts ONLY; the generated fonts.conf keeps the system's
# fontconfig rules but rejects every system font directory. Nothing is installed system-wide. Needs apt-get download (no root).
set -euo pipefail
cd "$(dirname "$0")/.."
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
(cd "$tmp" && apt-get download fonts-liberation fonts-freefont-ttf fonts-tlwg-loma-otf fonts-ipafont-gothic fonts-wqy-zenhei >/dev/null \
  && for d in *.deb; do dpkg-deb -x "$d" x; done)
rm -rf .fonts && mkdir -p .fonts && cp -r "$tmp"/x/usr/share/fonts .fonts/files
cat > .fonts/fonts.conf <<CONF
<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd"><fontconfig>
<include>/etc/fonts/fonts.conf</include>
<dir>$PWD/.fonts/files</dir><cachedir>$PWD/.fonts/cache</cachedir>
<selectfont><rejectfont><glob>/usr/share/fonts/*</glob><glob>/usr/local/share/fonts/*</glob><glob>$HOME/.local/share/fonts/*</glob><glob>$HOME/.fonts/*</glob></rejectfont></selectfont>
</fontconfig>
CONF
FONTCONFIG_FILE=$PWD/.fonts/fonts.conf fc-match system-ui
