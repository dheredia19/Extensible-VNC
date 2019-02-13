#!/usr/bin/python

'''
Copyright (C) 2016-2017 RealVNC Limited. All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
this list of conditions and the following disclaimer in the documentation
and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors
may be used to endorse or promote products derived from this software without
specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
'''

import sys
import argparse
import webbrowser

from app import app

parser = argparse.ArgumentParser(description="Cloud Address Tool")
parser.add_argument("--browser", dest="browser", action="store_true",
                    help="Launch browser (default)")
parser.add_argument("--no-browser", dest="browser", action="store_false",
                    help="Do not launch browser or pause")
parser.add_argument("-p", "--port", action="store", type=int,
                    help="Listening port (default: 5000)")
parser.set_defaults(browser=True,
                    port=5000)

if __name__ == '__main__':
    assert sys.version_info[:2] in [(2, 6), (2, 7)], \
        "This application requires Python 2.6 or Python 2.7"

    args = parser.parse_args()

    if args.browser:
        # Display an explanatory message and pause.
        raw_input(
            "Use this tool and your VNC Cloud API key to obtain Viewer "
            "and Server Cloud addresses.\n"
            "See https://developer.realvnc.com/docs/latest/overview.html#using-vnc-cloud "
            "for more information.\n"
            "Press CTRL+C to quit.\n"
            "Press Enter to continue..."
        )

        # Open a web browser pointing to this tool.
        webbrowser.open_new_tab("http://127.0.0.1:%d/" % args.port)

    app.run(host=None,         # Host
            port=args.port,    # Port number
            threaded=True      # Threads to handle browser predictive prefetch
            )
