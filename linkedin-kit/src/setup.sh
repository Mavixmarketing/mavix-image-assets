#!/bin/bash
# Sandbox setup for the LinkedIn kit. Run in the background at the start of a run.
cd /tmp/lk/kit || exit 1
pip install -q --disable-pip-version-check playwright pillow imageio-ffmpeg >/tmp/lk/pip.log 2>&1 &
npm i --silent --no-audit --no-fund >/tmp/lk/npm.log 2>&1 &
wait
python3 -c "import playwright, PIL, imageio_ffmpeg" && test -x node_modules/.bin/hyperframes && echo SETUP_OK || echo SETUP_FAILED
