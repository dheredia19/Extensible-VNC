# Building and running the basic Server sample app for Python

This sample Server app remotes the desktop of the currently logged-in user
only. It cannot remote the login, lock, or any other elevated screen. Screen
capture does not persist between log and switch outs. For a (native) sample
app demonstrating this behavior, see <vnc-sdk>/samples/serviceServer<plat>.


## Requirements

* A Windows, Linux or Mac desktop computer, or a Raspberry Pi
* A Python 2.6, 2.7 or 3.x implementation supporting ctypes, for example
  CPython (www.python.org) or PyPy


## Deploying the sample app to other devices

If you want to run this sample app on multiple devices, deploy the 
following files:

* basicServerPython.py (sample app)
* <vnc-sdk>/lib/python/vncsdk.py (Python SDK binding)
* <vnc-sdk>/lib/<desktop-plat>/vncagent (handles screen capture and event
  injection)
* <vnc-sdk>/lib/<desktop-plat>/<sdk-library> (note you must match the SDK
  library architecture to Python, so for example choose the 32-bit SDK library
  for 32-bit Python, even on a 64-bit computer)

By default, the sample app expects to find vncagent and the SDK library in
../../lib/<desktop-plat>/ and the binding in ../../lib/python/; you can
configure this at the top of basicServerPython.py.


## Providing connectivity information and running the sample app

You can either join VNC Cloud and let it manage connectivity for you, or
listen for direct TCP connections on a (known, static) IP address and
(dedicated, open) port. Or enable the sample app to do both.

### Joining VNC Cloud

You must provide a separate Cloud address for each device you deploy the
sample app to. Use <vnc-sdk>/tools/vnccloudaddresstool to freely obtain
Cloud addresses in conjunction with your sandbox API key, or call the
VNC Cloud API directly.

If the sample app will run on a single device, optionally hard-code the
Cloud address and Cloud password in basicServerPython.py before running.

To deploy to multiple devices, do not hard-code but instead instruct device
users to provide this information at run-time in the following format:

python basicServerPython.py <Cloud-addr> <Cloud-pwd>

### Listening for direct TCP connections

1) Sign in to your RealVNC account and follow the instructions on the 
   Add-on codes page to obtain a trial direct TCP add-on code.
2) Apply the code in basicServerPython.py. If the sample app will run on a 
   single device, optionally hard-code a listening port as well (the default 
   for VNC is 5900).
3) If deploying to multiple devices, instruct device users to provide this
   information at run-time instead:

   python basicServerPython.py <tcp-port>

Note the sample app will listen on all IPv4 and IPv6 addresses available to
the device. To deter MITM attacks, inform Viewer app users of the device's
unique, memorable catchphrase (printed to the console at run-time).

### Joining VNC Cloud *and* listening for direct TCP connections

With the exception of the direct TCP add-on code (which must always be
hard-coded in basicServerPython.py), you can instruct device users to
provide all the connectivity information required at the command line:

python basicServerPython.py <Cloud-addr> <Cloud-pwd> <tcp-port>


Copyright (C) 2016-2018 RealVNC Limited. All rights reserved.
