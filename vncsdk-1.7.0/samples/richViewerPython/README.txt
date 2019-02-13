# Building and running the rich Viewer sample app for Python

This sample Viewer app is designed to showcase particular functionality
in conjunction with the <vnc-sdk>/samples/richServerPython sample app, for
example monitor selection and messaging over the custom data channel.
Please note the custom data channel requires a (free) trial add-on code.

This Viewer app can connect to any sample Server sample if you wish. Note, however, 
you cannot send Ctrl+Alt+Del to a Windows computer running the cross-platform 
<vnc-sdk>/samples/basicServer sample app because it doesn't have 
sufficient permissions to inject the sequence. Try connecting to the 
<vnc-sdk>/samples/serviceServerWin sample app instead.


## Requirements

* A Windows, Linux or Mac desktop computer, or a Raspberry Pi
* A Python 2.6, 2.7 or 3.x implementation supporting ctypes, for example
  CPython (www.python.org) or PyPy (though note not Python 3.5 under Windows
  in this release)
* pip (under Windows and Mac; bundled with CPython 2.7.9)
* PySide (a Python binding for the Qt 4 GUI framework. Note PySide is open
  source software licensed under the terms of the LGPL v2.1)
* A trial custom data channel add-on code if you want to evaluate this 
  feature
* A trial direct TCP add-on code if you want to evaluate this feature

To obtain free trial add-on codes, sign in to your RealVNC account and
follow the instructions on the Add-on codes page. Hard-code them at 
the top of ConnectionDetail.py.

  
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

* <vnc-sdk>/samples/richViewerPython/*.py
* <vnc-sdk>/samples/richViewerPython/icons/*.png
* <vnc-sdk>/lib/python/vncsdk.py (Python SDK binding)
* <vnc-sdk>/lib/<desktop-plat>/<sdk-library> (note you must match the SDK
  library architecture to Python, so for example choose the 32-bit SDK library 
  for 32-bit Python, even on a 64-bit computer)

By default, the sample app expects to find the SDK library in 
../../lib/<desktop-plat>/ and the binding in ../../lib/python/; you can
configure this in main.py. Icons, however, must be deployed in ./icons/. 


## Providing connectivity information and running the sample app

You can either join VNC Cloud and let it manage connectivity for you, or
establish direct TCP connections to computers listening on known IP addresses
and ports. Or enable the sample app to do both.

### Joining VNC Cloud

You must provide a separate Cloud address for each device you deploy the
sample app to. Use <vnc-sdk>/tools/vnccloudaddresstool to freely obtain
Cloud addresses in conjunction with your sandbox API key, or call the
VNC Cloud API directly.

To deploy to a single device, hard-code the Viewer Cloud address and Viewer 
Cloud password in ConnectionDetail.py. You can then start the sample app at 
the command line by navigating to <vnc-sdk>/samples/richViewerPython and 
running the following command: python main.py 

To deploy to multiple devices, modify ConnectionDetail.py to pick up the Viewer 
Cloud address and password from an alternative source, for example an 
environment variable. Alternatively, hard-code a separate Viewer Cloud address 
and Viewer Cloud password in ConnectionDetail.py for each device you deploy to.

### Setting up direct TCP connections

Hard-code a trial direct TCP add-on code in ConnectionDetail.py, as 
detailed in the Requirements section.

### Establishing a connection

Run the following command to start the sample app: python main.py

Choose File > Connect from the sample app menu and enter either:

* The Cloud address on which a Server app is listening
* The IP address of the computer on which the Server app is running, and
  the listening port if this is not 5900 (in the form address:port).


## Using the custom data channel

Hard-code a trial custom data channel add-on code in ConnectionDetail.py, as
detailed in the Requirements section.

Note the corresponding Server app must also have a custom data channel add-on
code applied, and both endpoints must be capable of interpreting data
received via the channel.

This sample app demonstrates the custom data channel in conjunction with the
richServerPython sample app by enabling a connected Viewer
user to select which display to remote (providing the Server
computer has more than one display). See RPCFunctions.py for details of the
messages being sent and received.

   
Copyright (C) 2016-2018 RealVNC Limited. All rights reserved.
