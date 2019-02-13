# Building and running the service Server sample app for Mac

This persistent sample Server app maintains screen capture between switch and 
log outs, meaning the lock, login and other elevated screens can be remoted. 
It must, however, be integrated as a system service. For a single-shot sample 
app that does not need to run as root, see the cross-platform 
<vnc-sdk>/samples/basicServer.


## Requirements

* Xcode 7+
* Xcode developer tools (xcode-select --install)
* macOS 10.10+ SDK
* CMake 2.8.12.2 (make sure this is on your path)


## Building the sample app

You can optionally hard-code connectivity information and a VNC (Server) 
password in serviceServerMac.cxx before compiling. This may be convenient 
if you are deploying to a single device. If you are deploying to multiple 
devices, provide this information when you run the service instead. See the 
final section for more information.

To build, either generate an Xcode project, or makefiles:

### Generating an Xcode project

1) Navigate to the <vnc-sdk>/samples/serviceServerMac directory.
2) Run the following command (make sure to include the space and period):
   cmake -G"Xcode" .
3) To compile the sample app, either:
   * Open the project in Xcode, change ALL_BUILD to serviceServerMac, and
     build in the normal way.
   * Run the following command: xcodebuild
4) Examine build output in the appropriate folder, for example Debug.

### Generating makefiles

1) Navigate to the <vnc-sdk>/samples/serviceServerMac directory.
2) Run the following command (make sure to include the space and period):
   cmake .
3) Run the following command to compile the sample app: make


## Deploying the sample app to a secure location

1) Create a directory writable only by an Administrator (to prevent ordinary
   users running arbitrary code as the root user):

   sudo mkdir /Library/serviceServerMac

2) Copy the sample app binary, vncagent (handles screen capture and input
   injection), vncannotator (if required) and the SDK library to that 
   directory. Note these files may be in a Debug output directory or similar:

   sudo cp -R serviceServerMac vncagent vncannotator libvncsdk.<version>.dylib 
      /Library/serviceServerMac


## Running the sample app as a system service

1) In a text editor (not Xcode), open com.realvnc.serviceServerMac.plist:
   * Remove both ends of the XML comment tag.
   * If you did not hard-code connectivity information and a VNC password in 
     serviceServerMac.cxx before compiling, specify them here.
   * If you did not deploy to a /Library/serviceServerMac directory, change
     the <string> path to reference your location.

2) Run the following command to ensure the service starts automatically on 
   boot:

   sudo cp com.realvnc.serviceServerMac.plist /Library/LaunchDaemons

3) If you did not deploy to a /Library/serviceServerMac directory:
   * Open com.realvnc.serviceServerMac.peruser.plist in a text editor (not
     Xcode) and change the two <string> paths to reference your location.
   * Open com.realvnc.serviceServerMac.prelogin.plist in a text editor (not
     Xcode) and change one <string> path to reference your location.

4) Run the following commands to ensure each user's desktop and the login
   screen can be remoted:

   sudo cp com.realvnc.serviceServerMac.peruser.plist /Library/LaunchAgents
   sudo cp com.realvnc.serviceServerMac.prelogin.plist /Library/LaunchAgents

5) To start the sample app, either restart the computer or run the commands:
   
   sudo launchctl load /Library/LaunchDaemons/com.realvnc.serviceServerMac.plist
   launchctl load /Library/LaunchAgents/com.realvnc.serviceServerMac.peruser.plist

Note to stop the sample app, run the commands:

sudo launchctl unload /Library/LaunchDaemons/com.realvnc.serviceServerMac.plist
launchctl unload /Library/LaunchAgents/com.realvnc.serviceServerMac.peruser.plist

To prevent the sample app starting automatically on boot, remove the
com.realvnc.serviceServerMac*.plist files from the /Library/LaunchDaemons
and /Library/LaunchAgents directories.


## Providing connectivity information

You can either join VNC Cloud and let it manage connectivity for you, or 
listen for direct TCP connections on a (known, static) IP address and 
(dedicated, open) port. Or enable the sample app to do both.

### Joining VNC Cloud

You must provide a separate Cloud address for each device you deploy the 
sample app to. Use <vnc-sdk>/tools/vnccloudaddresstool to freely obtain 
Cloud addresses in conjunction with your sandbox API key, or call the 
VNC Cloud API directly.

If the sample app will run on a single device, optionally hard-code the 
Cloud address and Cloud password in serviceServerMac.cxx before compiling.

To deploy to multiple devices, do not hard-code but instead add this
information to the com.realvnc.serviceServerMac.plist file.

### Listening for direct TCP connections

1) Sign in to your RealVNC account and follow the instructions on the 
   Add-on codes page to obtain a trial direct TCP add-on code.
2) Apply the code in serviceServerMac.cxx and recompile. If the sample app 
   will run on a single device, optionally hard-code a listening port as 
   well (the default for VNC is 5900).
3) If deploying to multiple devices, do not hard code but instead add this 
   information to the com.realvnc.serviceServerMac.plist file.

Note the sample app will listen on all IPv4 and IPv6 addresses available to the 
device. To deter MITM attacks, inform sample Viewer app users of the device's 
unique, memorable catchphrase; examine syslog to find out what this is: 
cat /var/log/system.log | grep catchphrase

### Joining VNC Cloud *and* listening for direct TCP connections

You can add all the connectivity information required (Cloud address 
and Cloud password, listening port, and VNC password) to the appropriate 
service configuration file. The exception is the direct TCP add-on code, 
which must always be hard-coded in serviceServerMac.cxx.


## Logging

The sample app logs to /var/log/system.log by default.


Copyright (C) 2016-2018 RealVNC Limited. All rights reserved.
