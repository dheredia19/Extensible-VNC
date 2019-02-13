# Building and running the rich Server sample app for Python

This sample Server app is designed to showcase particular functionality
in conjunction with the <vnc-sdk>/samples/richViewerPython sample app, for 
example monitor selection and messaging over the custom data channel. 
Please note the custom data channel requires a (free) trial add-on code.

Note this sample app remotes the desktop of the currently logged-in user
only. It cannot remote the login, lock, or any other elevated screen. Screen
capture does not persist between log and switch outs. For a (native) sample
app demonstrating this behavior, see <vnc-sdk>/samples/serviceServer<plat>.


## Requirements

* A Windows, Linux or Mac desktop computer, or a Raspberry Pi
* A Python 2.6, 2.7 or 3.x implementation supporting ctypes, for example
  CPython (www.python.org) or PyPy
* A trial custom data channel add-on code if you want to evaluate this 
  feature
* A trial direct TCP add-on code if you want to evaluate this feature

To obtain free trial add-on codes, sign in to your RealVNC account and 
follow the instructions on the Add-on codes page. Hard-code them at 
the top of ConnectionDetail.py.


## Deploying the sample app to other computers

If you want to run this sample app on multiple computers, deploy the 
following files:

* richServerPython.py (sample app)
* <vnc-sdk>/lib/python/vncsdk.py (Python SDK binding)
* <vnc-sdk>/lib/<desktop-plat>/vncagent (handles screen capture and event
  injection)
* <vnc-sdk>/lib/<desktop-plat>/<sdk-library> (note you must match the SDK
  library architecture to Python, so for example choose the 32-bit SDK library
  for 32-bit Python, even on a 64-bit computer)

By default, the sample app expects to find vncagent and the SDK library in
../../lib/<desktop-plat>/ and the binding in ../../lib/python/; you can
configure this at the top of richServerPython.py.


## Providing connectivity information and running the sample app

You can either join VNC Cloud and let it manage connectivity for you, or
listen for direct TCP connections on a (known, static) IP address and
(dedicated, open) port. Or enable the sample app to do both.

### Joining VNC Cloud

You must provide a separate Cloud address for each computer you deploy the
sample app to. Use <vnc-sdk>/tools/vnccloudaddresstool to freely obtain
Cloud addresses in conjunction with your sandbox API key, or call the
VNC Cloud API directly.

Hard-code the Cloud address and Cloud password in richServerPython.py 
(each computer will need its own credentials).

### Listening for direct TCP connections

Hard-code a trial direct TCP add-on code in richServerPython.py, as
detailed in the Requirements section, and also hard-code a listening port
(the default for VNC is 5900).

Note the sample app will listen on all IPv4 and IPv6 addresses available to
the computer on which it runs. To deter MITM attacks, inform Viewer app users 
of a computer's unique, memorable catchphrase (printed to the 
console at run-time).

### Joining VNC Cloud *and* listening for direct TCP connections

Simply follow both sets of instructions above.


## Using the custom data channel

Hard-code a trial custom data channel add-on code in ConnectionDetail.py, as
detailed in the Requirements section.

Note the corresponding Viewer app must also have a custom data channel add-on
code applied, and both endpoints must be capable of interpreting data
received via the channel.

This sample app demonstrates the custom data channel in conjunction with the 
richViewerPython sample app by enabling a connected Viewer
user to select which display to remote (providing the Server
computer has more than one display). See RPCFunctions.py for details of the
messages being sent and received.


Copyright (C) 2016-2018 RealVNC Limited. All rights reserved.
