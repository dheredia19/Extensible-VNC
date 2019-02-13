#!/usr/bin/env bash

# Copyright (C) 2016-2017 RealVNC Limited. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its
# contributors may be used to endorse or promote products derived from this
# software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

HERE="$(dirname "$0")"
VIRTENV="$HERE"/env

VIRTUALENV=`which virtualenv`
if [ -z "$VIRTUALENV" ]; then
  echo "Aborting. 'virtualenv' is not found on path."
  exit 1
fi

echo "Running VNC Cloud Address Tool ..."

vers=$(python --version 2>&1)

IFS='. ' read -ra versionArray <<< "$vers"

vmajor=${versionArray[1]}
vminor=${versionArray[2]}
vbuild=${versionArray[3]//[[:space:]]/}

if (( $vmajor != 2 )); then
  echo "You are running $vers." \
       "This version is not supported, fully-secure Python 2.7.9 is recommended."
elif (( ($vminor < 7) || (($vminor== 7) && ($vbuild < 9)) )); then
  echo "You are running $vers." \
    "You can still use the tool, but upgrading to fully-secure Python 2.7.9" \
    "is recommended."
fi

if [ ! -f "$VIRTENV/created" ]; then
  rm -rf "$VIRTENV"
  echo "Creating virtual environment"
  "$VIRTUALENV" -q "$VIRTENV"
  touch "$VIRTENV/created"
else
  echo "Using existing virtual environment '$VIRTENV'"
fi

echo "Installing requirements ..."
"$VIRTENV/bin/python" "$VIRTENV/bin/pip" install -r "$HERE"/requirements.txt -vvvv > "$VIRTENV/install.log"
"$VIRTENV/bin/python" "$HERE"/run.py "$@"
