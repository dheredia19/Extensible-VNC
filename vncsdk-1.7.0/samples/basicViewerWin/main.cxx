/*
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
*/

#include <iostream>
#include <sstream>
#include <vnc/Vnc.h>

#include "BasicViewerWindow.h"

/*
 * basicViewerWin sample
 * 
 * This sample shows how to implement a basic VNC viewer using the VNC SDK
 * running on Windows. 
 *
 * Two types of connectivity are supported: Cloud-based and direct TCP
 * connection. A viewer can only use one of these mechanisms at a time.
 *
 * Note: To use direct TCP you will need to apply an add-on code; a trial
 * code is available from your RealVNC account. You can ignore TCP-related
 * code below if you do not intend to use the Direct TCP add-on.
 *
 * The viewer attempts to connect to a server, using either Cloud-based or
 * direct TCP connectivity according to user-supplied connectivity details.
 * These details can be provided on the command line or built-in using macro
 * definitions below.
 */

/* For Cloud connections, either hard-code the Cloud address for the Viewer OR
 * specify it at the command line. Example Cloud address:
 * LxygGgSrhXQFiLj5M4M.LxyPXzA9sGLkB6pCtJv.devEX1Sg2Txs1CgVuW4.LxyPRsVnXoDoue4Xqm
 */
#define LOCAL_CLOUD_ADDRESS ""

/* Either hard-code the Cloud password associated with this Cloud address OR
 * specify it at the command line. Example Cloud password: KMDgGgELSvAdvscgGfk2
 */
#define LOCAL_CLOUD_PASSWORD ""

/* Either hard-code the Cloud address of the Server (peer) to connect to OR
 * specify it at the command line. Example peer Cloud address:
 * LxyDgGgrhXQFiLj5M4M.LxyPXzA9sGLkB6pCtJv.devEX1Sg2Txs1CgVuW4.LxyPRydf9ZczNo13BcD
 */
#define PEER_CLOUD_ADDRESS ""

/* To enable direct TCP connectivity you need to copy the content of your
   add-on code into the string below. */
static const char* directTcpAddOnCode = "";

/* For direct TCP connections you must provide the server's TCP host address
   and port number. Either edit the macros below OR provide these connection
   details on the command line.
   The default direct TCP port number can be specified below by using:
   #define TCP_PORT VNC_DIRECT_TCP_DEFAULT_PORT
   Ignore these macros if you are not using the direct TCP add-on */
#define TCP_ADDRESS ""
#define TCP_PORT 0

   /* The value of this flag is set automatically according to the user-supplied
   command line arguments and macro definitions above. Cloud connectivity is
   presumed by default here. */
bool usingCloud = true;

/* Function prototypes */
void showSDKError(const char* errorString);
bool parseCommandLine(int argc, const char **argv,
                      const char** localCloudAddress,
                      const char** localCloudPassword,
                      const char** peerCloudAddress,
                      int* tcpPort, const char** tcpHostAddress);
bool initializeSDKandAddOns();

bool makeCloudConnection(const char* localCloudAddress,
                         const char* localCloudPassword,
                         const char* peerCloudAddress,
                         vnc_Viewer* viewer);
bool makeDirectTcpConnection(const char* hostAddress, int port,
                             vnc_Viewer* viewer);
void runEventLoop(vnc_Viewer* viewer);

/*
 * main function - validates cloud addresses, initializes the SDK and the
 * viewer, creates connection handler
 */
int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nShowCmd)
{
  int exitCode = 1;

  /* Parameter initialisation */
  const char* localCloudAddress = LOCAL_CLOUD_ADDRESS;
  const char* localCloudPassword = LOCAL_CLOUD_PASSWORD;
  const char* peerCloudAddress = PEER_CLOUD_ADDRESS;

  vnc_Viewer* viewer = 0;
  BasicViewerWindow* win = 0;

  /* These are only relevant if you are using the direct TCP add-on */
  const char* hostAddress = TCP_ADDRESS;
  int port = TCP_PORT;
  
  /* Parse command line */
  if (!parseCommandLine(__argc, (const char**)__argv,
                        &localCloudAddress, &localCloudPassword,
                        &peerCloudAddress,
                        &port, &hostAddress)) {
    return exitCode;
  }

  /* Create a logger which outputs to a file in the current working directory */
  vnc_Logger_createFileLogger("logfile.txt");

  /* Create a registry DataStore for storing peristent data for the viewer
     under the specified registry key. */
  if (!vnc_DataStore_createRegistryStore(
    "HKEY_CURRENT_USER\\Software\\TestCompany\\basicViewerWin")) {
    std::cerr << "Failed to create Registry data store: " << vnc_getLastError()
              << std::endl;
    return exitCode;
  }

  /* Initialize SDK and optional Add-Ons */
  if (initializeSDKandAddOns()) {
 
    /* Create the viewer and window */
    if (!(viewer = vnc_Viewer_create())) {
      showSDKError("Failed to create viewer");
    }
    else {
      win = new BasicViewerWindow(viewer);

      /* Make a connection to the server */
      if (usingCloud) {
        if (makeCloudConnection(localCloudAddress, localCloudPassword,
          peerCloudAddress, viewer)) {
          exitCode = 0;
        }
      }
      else {
        if (makeDirectTcpConnection(hostAddress, port, viewer)) {
          exitCode = 0;
        }
      }
      if (exitCode == 0) {
        /* Connection object has been constructed. */
        runEventLoop(viewer);
      }
      delete win;
    }
  }

  /* Shutdown the SDK */
  vnc_shutdown();
  return exitCode;
}

/*
* Run the Windows message loop while the connection is running
*/
void runEventLoop(vnc_Viewer* viewer)
{
  MSG msg;
  int nextExpiry = 0;
  HANDLE events[MAXIMUM_WAIT_OBJECTS];
  while (vnc_Viewer_getConnectionStatus(viewer) != vnc_Viewer_Disconnected) {
    /* Check whether there are messages or events to be processed immediately */
    bool haveMsg = PeekMessage(&msg, (HWND)0, 0, 0, PM_REMOVE) != 0;
    int nEvents = vnc_EventLoopWin_getEvents(events);
    DWORD waitResult = WaitForMultipleObjects(nEvents, events, FALSE, 0);

    /* If there are no messages or events then block until there are */
    if (!haveMsg && waitResult == WAIT_TIMEOUT) {
      waitResult = MsgWaitForMultipleObjects(
        nEvents, events, FALSE, nextExpiry, QS_ALLINPUT);
    }

    /* Process event */
    HANDLE h = NULL;
    if (waitResult >= WAIT_OBJECT_0 &&
        (int)waitResult < WAIT_OBJECT_0 + nEvents)
      h = events[waitResult - WAIT_OBJECT_0];

    nextExpiry = vnc_EventLoopWin_handleEvent(h);

    /* Process messages */
    if (haveMsg) {
      TranslateMessage(&msg);
      DispatchMessage(&msg);
    }
  }
}

/*
* Extract port number from command line argument.
*/
int extractPortNum(const char* arg)
{
  char* tailPtr;
  int port = strtol(arg, &tailPtr, 10);
  if (*tailPtr) return 0; /* tailPtr should point to null */
  return port;
}

/*
* Parse the command line to obtain connectivity details to be used when
* listening for incoming connections. A simplistic approach is adopted:
*
*   3 arguments - Cloud connectivity to be used
*                 [localCloudAddress localCloudPassword peerCloudAddress]
*
*   2 arguments - Direct TCP connectivity to be used
*                 [directTcpHostAddress directTcpPortNumber]
*
*   0 arguments - the built-in macros must be set appropriately
*/
bool parseCommandLine(int argc, const char** argv,
  const char** localCloudAddress,
  const char** localCloudPassword,
  const char** peerCloudAddress,
  int* tcpPort, const char** tcpHostAddress)
{
  bool badArgs = false;

  /* Parse any supplied command line arguments */
  if (argc == 4 || argc == 3 || argc == 1) {
    if (argc == 4) {  /* Cloud arguments */
      *localCloudAddress = argv[1];
      *localCloudPassword = argv[2];
      *peerCloudAddress = argv[3];
    }
    else  if (argc == 3) {  /* Direct TCP arguments */
      *tcpHostAddress = argv[1];
      *tcpPort = extractPortNum(argv[2]);
      usingCloud = false;
    }
    else { /* Examine the initial values set by macros */
      if (**localCloudAddress || **localCloudPassword || **peerCloudAddress)
        usingCloud = true;
      else if (*tcpPort || **tcpHostAddress)
        usingCloud = false;
    }

    /* Check if all required connectivity details are provided */
    if (usingCloud && (!**localCloudAddress ||
      !**localCloudPassword ||
      !**peerCloudAddress)) {
      badArgs = true;
    }
    else if (!usingCloud && (!*tcpPort || !**tcpHostAddress)) {
      badArgs = true;
    }
  }
  else badArgs = true; /* Invalid number of arguments */

  if (badArgs) {
    MessageBox(0, "You must specify a local Cloud address, password and \n"
      "peer Cloud address, or DirectTcp host address and port number", "Error", MB_OK);

    return false;
  }
  return true;
}

/*
* Initialize SDK and Add-ons
*/
bool initializeSDKandAddOns()
{
  /* Initialize the SDK */
  if (!vnc_init()) {
    showSDKError("Failed to initialize VNC SDK");
    return false;
  }

  /* Enable Add-ons */

  /* For each add-on you intend to enable you must apply an add-on
  code, as shown for Direct TCP in the example below. */

  /* Direct TCP Add-On */
  if (!usingCloud && !vnc_enableAddOn(directTcpAddOnCode)) {
    showSDKError("Failed to enable Direct TCP add-on");
    return false;
  }

  return true;
}

/*
* Make a Cloud connection
*/
bool makeCloudConnection(const char* localCloudAddress,
  const char* localCloudPassword,
  const char* peerCloudAddress,
  vnc_Viewer* viewer)
{
  vnc_CloudConnector* cloudConnector = 0;
  /* Create connector */
  if (!(cloudConnector = vnc_CloudConnector_create(localCloudAddress,
    localCloudPassword))) {
    showSDKError("Failed to create Cloud connector");
    return false;
  }
  /* Connect*/
  std::cout << "Connecting via VNC Cloud, local address: " << localCloudAddress
    << " peer address: " << peerCloudAddress << std::endl;
  if (!vnc_CloudConnector_connect(cloudConnector, peerCloudAddress,
    vnc_Viewer_getConnectionHandler(viewer))) {
    showSDKError("Failed to make VNC Cloud connection");
    vnc_CloudConnector_destroy(cloudConnector);
    return false;
  }
  vnc_CloudConnector_destroy(cloudConnector); /* Connector no longer required */
  return true;
}

/*
* Make a Direct TCP connection.
* Ignore this if you do not intend to use the direct TCP add-on
*/
bool makeDirectTcpConnection(const char* hostAddress,
  int port,
  vnc_Viewer* viewer)
{
  vnc_DirectTcpConnector* tcpConnector = 0;
  /* Create direct TCP connector */
  if (!(tcpConnector = vnc_DirectTcpConnector_create())) {
    showSDKError("Failed to create direct TCP connector");
    return false;
  }
  /* Connect */
  std::cout << "Connecting to host address: " << hostAddress
    << " port: " << port << std::endl;

  if (!vnc_DirectTcpConnector_connect(tcpConnector, hostAddress, port,
    vnc_Viewer_getConnectionHandler(viewer))) {
    showSDKError("Failed to start connection");
    vnc_DirectTcpConnector_destroy(tcpConnector);
    return false;
  }
  vnc_DirectTcpConnector_destroy(tcpConnector);
  return true;
}

/*
* Provide SDK error information on the console.
*/
void showSDKError(const char* errorString)
{
  std::cerr << errorString << ": " << vnc_getLastError() << std::endl;
  MessageBox(0, errorString, "Error", MB_OK);
}
