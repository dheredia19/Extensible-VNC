# Building and running the basic Viewer sample app for Python

This sample Viewer app can connect to any sample Server app. Note, however, you 
cannot send Ctrl+Alt+Del to a Windows computer running 
<vnc-sdk>/samples/basicServer or <vnc-sdk>/samples/basicServerPython 
because these sample apps don't have sufficient permissions to inject the 
sequence. Try connecting to the (native) <vnc-sdk>/samples/serviceServerWin 
sample app instead.


## Requirements

* A Windows, Linux or Mac desktop computer, or a Raspberry Pi
* A Python 2.6, 2.7 or 3.x implementation supporting ctypes, for example
  CPython (www.python.org) or PyPy (though note not Python 3.5 under Windows
  in this release)
* pip (under Windows and Mac; bundled with CPython 2.7.9)
* PySide (a Python binding for the Qt 4 GUI framework. Note PySide is open
  source software licensed under the terms of the LGPL v2.1)


## Setting up Qt and PySide

### Windows

Run the following command to install both: pip install pyside

### Linux (including Raspberry Pi)

Run the appropriate command as an administrator to install both. If you have
Python 3.x, use python3-pyside:

* Ubuntu or Pi: apt-get install python-pyside
* Red Hat/CentOS: yum install python-pyside

### Mac

1) Download and install Qt 4.8 for macOS: wiki.qt.io/PySide_Binaries_MacOSX
2) Install pip: sudo easy_install pip
3) Install PySide 1.2: sudo pip install -v pyside

Alternatively, install using Homebrew:

    brew update
    brew install cartr/qt4/qt@4
    brew install cartr/qt4/pyside@1.2

and then follow the instructions for adding it to your Python path, specifically:

    mkdir -p ~/Library/Python/2.7/lib/python/site-packages
    echo 'import site; site.addsitedir("/usr/local/lib/python2.7/site-packages")' >> ~/Library/Python/2.7/lib/python/site-packages/homebrew.pth


## Deploying the sample app to other devices

If you want to run this sample app on multiple devices, deploy the 
following files:

* basicViewerPython.py (sample app)
* <vnc-sdk>/lib/python/vncsdk.py (Python SDK binding)
* <vnc-sdk>/lib/<desktop-plat>/<sdk-library> (note you must match the SDK
  library architecture to Python, so for example choose the 32-bit SDK library 
  for 32-bit Python, even on a 64-bit computer)

By default, the sample app expects to find the SDK library in
../../lib/<desktop-plat>/ and the binding in ../../lib/python/; you can
configure this at the top of basicViewerPython.py.


## Providing connectivity information and running the sample app

You can either join VNC Cloud and let it manage connectivity for you, or
establish direct TCP connections to computers listening on known IP addresses
and ports. Or enable the sample app to do both.

### Joining VNC Cloud

You must provide a separate Cloud address for each device you deploy the
sample app to. Use <vnc-sdk>/tools/vnccloudaddresstool to freely obtain
Cloud addresses in conjunction with your sandbox API key, or call the
VNC Cloud API directly.

If the sample app will run on a single device, optionally hard-code the Viewer
Cloud address, Viewer Cloud password, and Server (peer) Cloud address to
connect to in basicViewerPython.py before running.

To deploy to multiple devices, do not hard-code but instead instruct device
users to provide this information at run-time in the following format:

python basicViewerPython.py
  <Viewer-Cloud-addr> <Viewer-Cloud-pwd> <Server-Cloud-addr>

### Establishing direct TCP connections

1) Sign in to your RealVNC account and follow the instructions on the 
   Add-on codes page to obtain a trial direct TCP add-on code.
2) Apply the code in basicViewerPython.py. If the sample app will run on a 
   single device, optionally hard-code the IP address and port of the
   computer to connect to as well.
3) If deploying to multiple devices, instruct device users to provide this
   information at run-time instead:

   python basicViewerPython.py
     <Server-ip-address> <Server-tcp-port>


Copyright (C) 2016-2018 RealVNC Limited. All rights reserved.
