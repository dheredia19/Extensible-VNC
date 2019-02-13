# Building and running the service Server sample app for Windows

This persistent sample Server app maintains screen capture between switch and 
log outs, meaning the lock, login, and UAC screens can be remoted. It must, 
however, be integrated as a Windows Service. For a single-shot sample app that 
does not need to run as a Service, see the cross-platform 
<vnc-sdk>\samples\basicServer.


## Requirements

* Visual Studio 2010/2013/2015 (Express for Windows *Desktop* is supported;
  Express for *Windows* is NOT supported.)
* CMake 2.8.11+ (make sure this is on your path). Note Visual Studio 
  2015 requires CMake 3.1.0+. 


## Building the sample app

You can optionally hard-code connectivity information and a VNC (Server) 
password in serviceServerWin.cxx before compiling. This may be convenient 
if you are deploying to a single device. If you are deploying to multiple 
devices, provide this information when you create the Windows Service instead. 
See the final section for more information.

1) Open the Developer Command Prompt for VS<version> app. This is likely to
   be in a Visual Studio Tools folder.
2) Navigate to the <vnc-sdk>\samples\serviceServerWin folder.
3) Run an appropriate CMake command to generate build files, for example:

   cmake .                                  # To build 32-bit project files
   cmake -G"Visual Studio 12 2013" .        # To build 32-bit project files
                                              for a particular generator
   cmake -G"Visual Studio 12 2013 Win64" .  # To build 64-bit project files
                                              for a particular generator
   Alternatively, you can use the CMake GUI.
4) To compile the sample app, either:
   * Open the solution in Visual Studio, set serviceServerWin as the startup
     project, and build in the normal way.
   * Run the following command, and check the current <configuration> folder
     (for example \Debug) for output: msbuild.exe serviceServerWin.sln


## Deploying the sample app to a secure location

You must deploy the sample app binary, vncagent.exe (handles screen capture 
and input injection), vncannotator.exe (if required) and the SDK library to 
one of the following secure locations. This is to prevent ordinary users 
running arbitrary code as the SYSTEM user, and also so vncagent can inject 
secure key sequences (such as Alt+Tab and Ctrl+Alt+Del) on Windows 8+ computers:

* %ProgramFiles%
* %ProgramFiles(x86)%

For example, from an Administrator command prompt:

mkdir "C:\Program Files\MyServer"
copy <configuration>\serviceServerWin.exe "C:\Program Files\MyServer"
copy <configuration>\vncagent.exe "C:\Program Files\MyServer"
copy <configuration>\vncannotator.exe "C:\Program Files\MyServer"
copy <configuration>\vncsdk.dll "C:\Program Files\MyServer"


## Creating and running a Windows Service

From an Administrator command prompt:

1) Create a vncsdkServer Service. For all targets except XP:
   * If you hard-coded connectivity information and a VNC password in 
     serviceServerWin.cxx before compiling, run the following command (all 
     on one line, and substituting your <secure-dir>):
   
     sc create vncsdkServer start= demand error= ignore 
     binPath= "<secure-dir>\serviceServerWin.exe" DisplayName= "VNC SDK Server"
   
   * If you did not hard-code this information, append the appropriate
     information to the sample app binary as follows:
   
     sc create vncsdkServer start= demand error= ignore
     binPath= "<secure-dir>\serviceServerWin.exe -cloud <Cloud-addr> 
     <Cloud-pwd> -tcp <tcp-port> <VNC-pwd>" DisplayName= "VNC SDK Server"

   For XP targets, insert 'type= interact type= own' after the name of the 
   Service, so for example if you hard-coded connectivity information in 
   serviceServerWin.cxx before compiling:

   sc create vncsdkServer type= interact type= own start= demand error= ignore
   binPath= "<secure-dir>\serviceServerWin.exe" DisplayName= "VNC SDK Server"

2) Start the vncsdkServer Service: sc start vncsdkServer.
   
To stop the vncsdkServer Service, run the command: sc stop vncsdkServer. 
Alternatively, you can operate the vncsdkServer Service from Control Panel > 
Administrative tools > Services, and also set it to start automatically on 
boot.


## Providing connectivity information

You can either join VNC Cloud and let it manage connectivity for you, or 
listen for direct TCP connections on a (known, static) IP address and 
(dedicated, open) port. Or enable the sample app to do both.

### Joining VNC Cloud

You must provide a separate Cloud address for each device you deploy the 
sample app to. Use <vnc-sdk>\tools\vnccloudaddresstool to freely obtain 
Cloud addresses in conjunction with your sandbox API key, or call the 
VNC Cloud API directly.

If the sample app will run on a single device, optionally hard-code the 
Cloud address and Cloud password in serviceServerWin.cxx before compiling.

To deploy to multiple devices, do not hard-code but instead provide this 
information when you create the Windows Service.

### Listening for direct TCP connections

1) Sign in to your RealVNC account and follow the instructions on the 
   Add-on codes page to obtain a trial direct TCP add-on code.
2) Apply the code in serviceServerWin.cxx and recompile. If the sample 
   app will run on a single device, optionally hard-code a listening port as 
   well (the default for VNC is 5900).
3) If deploying to multiple devices, do not hard-code but instead provide this 
   information when you create the Windows Service.

Note the sample app will listen on all IPv4 and IPv6 addresses available to the 
device. To deter MITM attacks, inform sample Viewer app users of the device's 
unique, memorable catchphrase; look for a recent Information level message in 
Windows Event Viewer > Windows Logs > Application to find out what this is.

### Joining VNC Cloud *and* listening for direct TCP connections

You can provide all the connectivity information required (Cloud address 
and Cloud password, listening port, and VNC password) when you create the 
Windows Service. The exception is the direct TCP add-on code, which must 
always be hard-coded in serviceServerWin.cxx.


## Logging

The sample app logs to Windows Event Viewer > Windows Logs > Application 
by default.


Copyright (C) 2016-2018 RealVNC Limited. All rights reserved.
