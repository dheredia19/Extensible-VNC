# Building and running the WPF Viewer sample app for Windows

This sample Viewer app can connect to any sample Server app. Note to send 
Ctrl+Alt+Del to a sample Server app*, press Shift+Ctrl+Alt+Del.

*You cannot send Ctrl+Alt+Del to a Windows computer running the 
<vnc-sdk>\samples\basicServer because it doesn't have sufficient permissions 
to inject the sequence. Try <vnc-sdk>\samples\serviceServerWin instead. 


## Requirements

* Visual Studio 2017 or 2015 (for C# 6) allows you to build the project as-is,
  targeting .NET framework 4.6.1 by default.
* Visual Studio 2010+ is supported but appropriate modifications to the sample
  are required for earlier versions of the C# specification, such as removing
  the auto property initialisers.
* Earlier .NET 4+ framework targets may also require changes to the project and
  sample code.


## Building the sample app

Note you can optionally hard-code connectivity information in MainWindow.xaml.cs. 
The settings will then populate the Connect Settings dialog that appears at run-time.
 

## Deploying the sample app to other devices

If you want to run this sample app on multiple devices, deploy the following files:
 
* BasicViewerCSharpWpf.exe (sample app binary)
* RealVNC.VncSdk.dll (C# binding library)
* vncsdk.dll (SDK library)

The sample app binary expects to find the SDK files in the same directory or in the
directory specified in the VNCSDK_LIBRARY environment variable.


## Providing connectivity information and running the sample app

You can either join VNC Cloud and let it manage connectivity for you, or 
establish direct TCP connections to computers listening on known IP addresses 
and ports. Or enable the sample app to do both.

### Joining VNC Cloud

You must provide a separate Cloud address for each device you deploy the
sample app to. Use <vnc-sdk>\tools\vnccloudaddresstool to freely obtain
Cloud addresses in conjunction with your sandbox API key, or call the 
VNC Cloud API directly.

If the sample app will run on a single device, optionally hard-code the Viewer 
Cloud address, Viewer Cloud password, and Server (peer) Cloud address to 
connect to in MainWindow.xaml.cs before compiling.

To deploy to multiple devices, do not hard-code but instead instruct device 
users to provide the information in the Connect Settings dialog at run-time.

### Establishing direct TCP connections

1) Sign in to your RealVNC account and follow the instructions on the 
   Add-on codes page to obtain a trial direct TCP add-on code.
2) Apply the add-on code in VncLibraryThread.cs and recompile. If the sample 
   app will run on a single device, optionally hard-code the IP address and 
   port of the computer to connect to as well.
3) If deploying to multiple devices, instruct device users to provide this 
   information in the Connect Settings dialog at run-time instead.


Copyright (C) 2016-2018 RealVNC Limited. All rights reserved.
