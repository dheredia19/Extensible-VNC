# Using the VNC Cloud Address Tool (VCAT)

See <vnc-sdk>/StartHere.html for introductory information, and
<vnc-sdk>/VNCCloudAPI.html to learn about the underlying VNC Cloud API calls.

Note: VCAT requires that the SDK is not unpacked into a directory with
spaces in the path.


## Requirements

* A desktop computer or Raspberry Pi (mobile platforms are not supported)
* Python 2.7.x (2.7.9 or later is preferred; Python 3.x is not supported)
* virtualenv


## Installing and running VCAT

### Windows

1) Install Python 2.7.x and make sure <python-dir>\python.exe and 
   <python-dir>\Scripts\pip.exe are on your path (do this in the installer).
2) In a Command Prompt, install virtualenv: pip install virtualenv
3) Navigate to <vnc-sdk>\tools\vnccloudaddresstool
4) Start the tool: run.cmd

### Linux (including Raspberry Pi)

Install commands must be run as an administrator:

1) Install virtualenv:
   * Ubuntu or Pi: apt-get install python-virtualenv
   * Red Hat/CentOS: yum install epel-release; yum install python-virtualenv
2) Navigate to <vnc-sdk>/tools/vnccloudaddresstool
3) Start the tool: ./run.sh

### Mac

1) Install virtualenv: sudo easy_install pip; sudo pip install virtualenv
2) Navigate to <vnc-sdk>/tools/vnccloudaddresstool
3) Start the tool: ./run.sh


## Accessing VCAT

By default, VCAT opens in your web browser; log in using your development 
API key and secret (received via email). Alternatively, run with --no-browser 
and navigate to http://localhost:5000.

Colleagues can access VCAT by navigating to http://<your-ip-address>:5000. 
Or you can share Cloud addresses in JSON format.


Copyright (C) 2016-2018 RealVNC Limited. All rights reserved.
