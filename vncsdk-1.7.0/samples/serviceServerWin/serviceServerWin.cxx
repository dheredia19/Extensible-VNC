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
#include <windows.h>
#include <shlwapi.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

#include <vnc/Vnc.h>

/*
 * serviceServerWin sample
 *
 * This sample demonstrates how to implement a VNC server as a Windows service.
 * The code in this sample deals with the Windows service control manager,
 * implementing the routines required to run a Windows service.  The code which
 * runs the service is very simple, and similar to the basicServer sample.
 */

/* You can specify the server password here, which will be used if it is not
   specified in the service's commandline: */
const char* serverPassword = 0;

/* For Cloud connections, either hard-code the Cloud address for the Server OR
 * specify it at the command line. Example Cloud address:
 * LxygGgSrhXQFiLj5M4M.LxyPXzA9sGLkB6pCtJv.devEX1Sg2Txs1CgVuW4.LxyPRsVnXoDoue4Xqm
 */
const char* cloudAddress = 0;

/* Either hard-code the Cloud password associated with this Cloud address OR
 * specify it at the command line. Example Cloud password: KMDgGgELSvAdvscgGfk2
 */
const char* cloudPassword = 0;

/* To enable direct TCP connectivity you need to copy the content of your
   add-on code (available from your RealVNC account) into the string below. */
static const char* directTcpAddOnCode = "";

/* For direct TCP connections you must provide a TCP listening port number.
   Either specify the port number below OR provide the port number via the service's
   command line.
   The default direct TCP port number can be specified below by using:
   int directTcpPort = VNC_DIRECT_TCP_DEFAULT_PORT
   Ignore this if you are not using the Direct TCP add-on */
int directTcpPort = 0;

/* The following flags indicate the type of connection(s) being used and they
   are set automatically according to user-supplied command line arguments and
   the parameters above. Each type of connection is optional.
   If you set any flag to true below then that makes that type of connection
   mandatory i.e. connectivity details MUST be provided via the command line or
   using the parameters above. */
bool usingCloud = false;
bool usingDirectTcp = false;


/* Windows service name */
WCHAR* serviceName = L"vncsdkServer";

/* Globals */
SERVICE_STATUS status;
SERVICE_STATUS_HANDLE hStatus = 0;
CRITICAL_SECTION serviceMutex;
HANDLE eventLogHandle = 0;
HANDLE stopEvent = 0;
HANDLE stoppedEvent = 0;
vnc_Server* server = 0;
vnc_CloudListener* cloudListener = 0;
vnc_DirectTcpListener* directTcpListener = 0;
int exitCode = 1;
DWORD listenRetryTime = 0;

/* Flag to indicate that the service is to be stopped because of a system
   shutdown */
bool systemShutdown = false;

/* Flag to indicate that we will wait until all viewers have disconnected. */
bool waitForDisconnections = false;

/* Function prototypes */

void WINAPI serviceMain(DWORD argc, LPTSTR *argv);
DWORD WINAPI serviceCtrl(DWORD dwControl, DWORD dwEventType, LPVOID lpEventData,
                         LPVOID lpContext);
bool parseCommandLine(int argc, const char** argv);
void logEvent(const char* message, bool error);
vnc_Server* createAndInitServer();
void setupSecurity(vnc_Server* server);
vnc_CloudListener* createCloudListener(vnc_Server* server,
  const char* cloudAddress,
  const char* cloudPassword);
vnc_DirectTcpListener* createDirectTcpListener(vnc_Server* server, int port);

void runLoop();
struct Lock {
  Lock(CRITICAL_SECTION& m) : mutex(m) { EnterCriticalSection(&mutex); }
  ~Lock() { LeaveCriticalSection(&mutex); }
  CRITICAL_SECTION& mutex;
};

/* Connection callbacks */

void connectionStarted(void* userData,
                       vnc_Server* server,
                       vnc_Connection* connection)
{
  const char* peerAddress = vnc_Server_getPeerAddress(server, connection);
  std::ostringstream logBuf;
  logBuf << "Viewer " << peerAddress << " connected";
  logEvent(logBuf.str().c_str(), false);
}

void connectionEnded(void* userData,
                     vnc_Server* server,
                     vnc_Connection* connection)
{
  const char* peerAddress = vnc_Server_getPeerAddress(server, connection);
  std::ostringstream logBuf;
  logBuf << "Viewer " << peerAddress << " disconnected";
  logEvent(logBuf.str().c_str(), false);
  if (waitForDisconnections && vnc_Server_getConnectionCount(server) == 1) {
    /* The server can exit now as this is the last viewer to be disconnected. */
    SetEvent(stopEvent);
  }
}

/* Security callbacks */

static vnc_bool_t isUserNameRequired(void* userData, vnc_Server* server,
                                     vnc_Connection* connection)
{
  /* Don't prompt for a username when accessing this server, just a password
     is required */
  return vnc_false;
}

static int authenticateUser(void* userData, vnc_Server* server,
                            vnc_Connection* connection, const char* username,
                            const char* password)
{
  if (strcmp(password, serverPassword) == 0) {
    return vnc_Server_PermAll;
  }
  return 0;
}

/* Cloud callbacks */

static void listeningFailed(void* userData, vnc_CloudListener* listener_,
                            const char* cloudError, int suggestedRetryTime)
{
  std::ostringstream logBuf;
  logBuf << "The listener is disconnected from VNC Cloud: " << cloudError;

  if (suggestedRetryTime < 0) {
    SetEvent(stopEvent);
  } else {
    vnc_CloudListener_destroy(cloudListener);
    cloudListener = 0;
    listenRetryTime = GetTickCount() + suggestedRetryTime * 1000;
    logBuf << " (retrying in " << suggestedRetryTime << "s)";
  }
  logEvent(logBuf.str().c_str(), false);
}

static void listeningStatusChanged(void* userData, vnc_CloudListener* listener,
                                   vnc_CloudListener_Status status)
{
  if(status == vnc_CloudListener_StatusSearching) {
    logEvent("The listener is in the process of establishing an association "
             "with VNC Cloud", false);
  } else {
    logEvent("Listening for connections", false);
  }
}

/* RsaKey callback */

static void rsaKeyDetailsReady(void* userData,
                               const vnc_DataBuffer* rsaPublic,
                               const char* hexFingerprint,
                               const char* catchphraseFingerprint)
{
  std::ostringstream logBuf;
  logBuf << "Server id is: " << hexFingerprint << std::endl
         << "Server catchphrase is: " << catchphraseFingerprint;
  logEvent(logBuf.str().c_str(), false);
}


/* Logger callbacks */

static void logMessage(void* userData, vnc_Logger_Level level,
                       const char* message)
{
  logEvent(message, level == vnc_Logger_Error);
}

/*
 * main function - runs the service dispatcher, which creates another thread to
 * actually run the server.
 */
int main(int argc, const char** argv)
{
  /* Check whether we already have any hardcoded values */
  if (cloudAddress && cloudPassword) usingCloud = true;
  if (directTcpPort) usingDirectTcp = true;

  if (!parseCommandLine(argc, argv))
    return 1;

  /* Both the current thread (the service control dispatcher thread) and the
     service thread use the vnc_Server object, so we use a mutex to coordinate
     access.  The stopEvent is used to signal from the service control
     dispatcher thread that the service should stop, and the stoppedEvent
     signals in the reverse direction to acknowledge that it has done so. */
  InitializeCriticalSection(&serviceMutex);
  stopEvent = CreateEvent(0, TRUE, FALSE, 0);
  stoppedEvent = CreateEvent(0, TRUE, FALSE, 0);

  /* Run the service dispatcher and start the service */
  SERVICE_TABLE_ENTRY srvt[] = {
    {serviceName, serviceMain},
    {0,0}
  };
  if (!StartServiceCtrlDispatcher(srvt)) {
    std::cerr << "This program must be run by the service controller." << std::endl;
    logEvent("Could not connect to the service controller.", true);
    return 1;
  }

  return 0;
}

/*
 * Service entry point - runs the VNC server
 */
void WINAPI serviceMain(DWORD argc, LPTSTR *argv)
{
  hStatus = RegisterServiceCtrlHandlerEx(serviceName, serviceCtrl, 0);
  if (!hStatus) return;

  status.dwServiceType = SERVICE_WIN32_OWN_PROCESS;
  status.dwCurrentState = SERVICE_START_PENDING;
  status.dwControlsAccepted =
      SERVICE_ACCEPT_STOP | SERVICE_ACCEPT_SHUTDOWN |
      SERVICE_ACCEPT_SESSIONCHANGE;
  status.dwWin32ExitCode = NO_ERROR;
  status.dwServiceSpecificExitCode = 0;
  status.dwCheckPoint = 0;
  status.dwWaitHint = 0;
  SetServiceStatus(hStatus, &status);

  exitCode = 1;

  /* Create a logger which outputs to the Windows Event Log */
  vnc_Logger_Callback loggerCallback = { logMessage, };
  vnc_Logger_createCustomLogger(&loggerCallback, 0);

  if (!vnc_DataStore_createRegistryStore(
        "HKEY_CURRENT_USER\\Software\\TestCompany\\serviceServerWin")) {
    std::ostringstream logBuf;
    logBuf << "Failed to create Registry data store: " << vnc_getLastError();
    logEvent(logBuf.str().c_str(), true);
    goto cleanup;
  }
  {
    Lock l(serviceMutex);
    server = createAndInitServer();
  }
  if (!server) goto cleanup;

  setupSecurity(server);

  if (usingCloud) {
    cloudListener = createCloudListener(server, cloudAddress, cloudPassword);
    if (!cloudListener) goto cleanup;
  }
  if (usingDirectTcp) {
    directTcpListener = createDirectTcpListener(server, directTcpPort);
    if (!directTcpListener) goto cleanup;
  }

  /* Server setup complete, mark the service as running and run the loop */
  ResetEvent(stoppedEvent);
  status.dwCurrentState = SERVICE_RUNNING;
  SetServiceStatus(hStatus, &status);
  runLoop();

  logEvent("Service server is shutting down", false);

cleanup:
  if (cloudListener) vnc_CloudListener_destroy(cloudListener);
  if (directTcpListener) vnc_DirectTcpListener_destroy(directTcpListener);
  if (server) {
    Lock l(serviceMutex);
    vnc_Server_destroy(server);
    server = 0;
  }
  logEvent("Service server exiting", false);
  vnc_shutdown();
  status.dwCurrentState = SERVICE_STOPPED;
  status.dwServiceSpecificExitCode = exitCode;
  SetServiceStatus(hStatus, &status);
  /* Allow any waiting service control callback to proceed. */
  SetEvent(stoppedEvent);
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
* listening for incoming connections.
*
* For Cloud connectivity, specify the  cloudAddress and cloudPassword after
* a -cloud argument:
*
*   -cloud [cloudAddress cloudPassword]
*
* For Direct TCP connectivity, specify the listening port number after a
* -tcp argument:
*
*   -tcp [port]
*
* The server password can also be specified on the command line as a separate
* parameter:
*
*   [password]
*
*/
bool parseCommandLine(int argc, const char** argv)
{
  bool badArgs = false;

  /* Parse any supplied command line arguments */
  for (int i = 1; i<argc; ++i) {
    if (argv[i] && strcmp(argv[i], "-cloud") == 0) {
      if (argc > i + 2) {
        cloudAddress = argv[++i];
        cloudPassword = argv[++i];
      }
      usingCloud = true;
    }
    else if (argv[i] && strcmp(argv[i], "-tcp") == 0) {
      if (argc > i + 1) {
        directTcpPort = extractPortNum(argv[++i]);
      }
      usingDirectTcp = true;
    }
    else serverPassword = argv[i];
  }

  /* Check if all required connectivity details are provided */
  if (usingCloud && (!cloudAddress || !cloudPassword)) {
    logEvent("You must provide a valid Cloud address and password", true);
    badArgs = true;
  }
  if (usingDirectTcp && !directTcpPort) {
    logEvent("You must provide a valid TCP port number", true);
    badArgs = true;
  }
  if (!serverPassword) {
    logEvent("You must provide a server password", true);
    badArgs = true;
  }

  if (!usingCloud && !usingDirectTcp) {
    logEvent("No connection details provided", true);
    badArgs = true;
  }

  if (badArgs) {
    const char* help = "You must provide a Cloud address, Cloud password, "
      "and/or Direct TCP port, and a server password";
    logEvent(help, true);
    return false;
  }
  return true;
}

/*
 * Log an event to the Windows Event Log
 */
void logEvent(const char* message, bool error)
{
  if (!eventLogHandle)
    eventLogHandle = RegisterEventSourceW(NULL, serviceName);

  ReportEventA(eventLogHandle,
               error ? EVENTLOG_ERROR_TYPE : EVENTLOG_INFORMATION_TYPE, 1, 1, 0,
               1, 0, &message, 0);
}

/*
 * Initializes SDK and Server, setting up connection callbacks
 */
vnc_Server* createAndInitServer()
{
  /* Initialize the SDK */
  if (!vnc_init()) {
    std::ostringstream logBuf;
    logBuf << "Failed to initialize VNC SDK: " << vnc_getLastError();
    logEvent(logBuf.str().c_str(), true);
    return 0;
  }

  /* Enable Direct TCP Add-On */
  if (usingDirectTcp && !vnc_enableAddOn(directTcpAddOnCode)) {
    std::ostringstream logBuf;
    logBuf << "Failed to enable Direct TCP add-on: " << vnc_getLastError();
    logEvent(logBuf.str().c_str(), true);
    return 0;
  }

  /* Initialize the server.  Note that the vncagent path is not specified, so it
     should be found in the same directory as the main program.  In the case of
     a service, this directory ought to be in a secure location only writable
     by administrators. */
  vnc_Server* server = vnc_Server_createService(0);
  if (!server) {
    std::ostringstream logBuf;
    logBuf << "Failed to initialize server: " << vnc_getLastError();
    logEvent(logBuf.str().c_str(), true);
    return 0;
  }

  /* Setup connection callbacks */
  vnc_Server_ConnectionCallback connectionCallback = {
    connectionStarted,
    connectionEnded,
  };
  vnc_Server_setConnectionCallback(server, &connectionCallback, 0);

  return server;
}

/*
 * Initialize security-related settings for the server
 */
void setupSecurity(vnc_Server* server)
{
  /* Setup security callback */
  vnc_Server_SecurityCallback securityCallback = {
    0, /* verifyPeer not required */
    isUserNameRequired,
    0, /* isPasswordRequired always returns true if not specified */
    authenticateUser
  };
  vnc_Server_setSecurityCallback(server, &securityCallback, 0);
}

/*
 * Starts the server listening for connections made via VNC Cloud
 */
vnc_CloudListener* createCloudListener(vnc_Server* server, const char* cloudAddress,
                                      const char* cloudPassword)
{
  vnc_CloudListener_Callback listenerCallback = {
    listeningFailed,
    0, /* filterConnection not required here */
    listeningStatusChanged
  };
  vnc_CloudListener* listener =
      vnc_CloudListener_create(cloudAddress, cloudPassword,
                               vnc_Server_getConnectionHandler(server),
                               &listenerCallback, 0);

  if (!listener) {
    std::ostringstream logBuf;
    logBuf << "Could not create Cloud listener: " << vnc_getLastError();
    logEvent(logBuf.str().c_str(), true);
  }
  return listener;
}

/*
* Start listening for connections made via direct TCP
* Ignore this if you do not intend to use the Direct TCP add-on
*/
vnc_DirectTcpListener* createDirectTcpListener(vnc_Server* server, int port)
{
  /* This listens on ALL addresses and does not employ callbacks */
  vnc_DirectTcpListener* listener =
    vnc_DirectTcpListener_create(port, 0,
      vnc_Server_getConnectionHandler(server),
      0, 0);

  if (!listener) {
    std::ostringstream logBuf;
    logBuf << "Could not create DirectTcp listener: " << vnc_getLastError();
    logEvent(logBuf.str().c_str(), true);
  } else {
    /* If DirectTcp is being used, request the RSA key details to write to
       the log so that viewers can verify they are connecting to this server. */
    vnc_RsaKey_Callback keyCallback = {
      rsaKeyDetailsReady
    };
    vnc_RsaKey_getDetails(&keyCallback, 0, true);
  }
  return listener;
}

/*
 * Disconnect all viewers connected to the server if the service has been told
 * to stop or we can no longer maintain a connection to VNC Cloud
 */
bool disconnectViewers()
{
  if (vnc_Server_getConnectionCount(server) == 0) {
    return false;
  }

  if (cloudListener) {
    vnc_CloudListener_destroy(cloudListener);
    cloudListener = 0;
  }

  if (directTcpListener) {
    vnc_DirectTcpListener_destroy(directTcpListener);
    directTcpListener = 0;
  }

  /* Set flag to wait until all viewers have disconnected from the server. */
  waitForDisconnections = true;
  int disconnectFlags = vnc_Server_DisconnectAlert;
  /* Tell all viewers to reconnect if we have received a system shutdown
     notification in case the server comes back automatically after a reboot. */
  if (systemShutdown) disconnectFlags |= vnc_Server_DisconnectReconnect;
  vnc_Server_disconnectAll(server, "The server has been stopped",
                           disconnectFlags);
  return true;
}

/*
 * Run the SDK event loop
 */
void runLoop()
{
  int nextExpiry = 0;
  HANDLE events[MAXIMUM_WAIT_OBJECTS+1];
  while (true) {
    /* Fetch the SDK events to wait on, and add in our own stopEvent */
    events[0] = stopEvent;
    int nEvents = vnc_EventLoopWin_getEvents(events+1) + 1;

    /* If we're waiting before recreating the Cloud listener, adjust the expiry
       time */
    if ((usingCloud && !cloudListener) && !waitForDisconnections) {
      int listenerExpiry = (int)(listenRetryTime - GetTickCount());
      if (listenerExpiry <= 0) {
        logEvent("Recreating Cloud listener after disconnection from VNC Cloud",
                 false);
        cloudListener = createCloudListener(server, cloudAddress, cloudPassword);
        /* Quit if we cannot create the listener, aren't also listening for direct
           connections, and we don't have any existing connections */
        if (!cloudListener && !directTcpListener && !disconnectViewers()) {
          break;
        }
        /* Poll the event loop, as vnc_CloudListener_create may have updated
           the expiry time */
        nextExpiry = 0;
      } else if (nextExpiry == -1 || nextExpiry > listenerExpiry) {
        nextExpiry = listenerExpiry;
      }
    }

    /* Wait for events */
    DWORD waitResult =
      MsgWaitForMultipleObjects(nEvents, events, FALSE, nextExpiry, QS_ALLINPUT);

    /* Process event */
    HANDLE h = NULL;
    if (waitResult == WAIT_OBJECT_0 /* stopEvent */) {
      ResetEvent(stopEvent);
      exitCode = 0;
      /* Quit immediately if we don't have any connections. */
      if (!disconnectViewers()) {
        break;
      }
    } else if (waitResult >= WAIT_OBJECT_0 &&
               waitResult < WAIT_OBJECT_0 + nEvents) {
      h = events[waitResult - WAIT_OBJECT_0];
    }

    nextExpiry = vnc_EventLoopWin_handleEvent(h);
  }
}

/*
 * Service control callback
 */
DWORD WINAPI serviceCtrl(DWORD dwControl, DWORD dwEventType, LPVOID lpEventData,
                         LPVOID lpContext)
{
  {
    /* Use a lock to guard against access to the server during destruction. */
    Lock l(serviceMutex);
    /* We forward all serviceCtrl notifications to the SDK, in particular the
       SERVICE_CONTROL_SESSIONCHANGE notifications are used by the SDK to
       efficiently monitor which session is active. */
    if (server) vnc_Server_serviceControlHandlerEx(server, dwControl, dwEventType,
                                                   lpEventData);
  }

  switch (dwControl) {
  case SERVICE_CONTROL_STOP:
  case SERVICE_CONTROL_SHUTDOWN:
    /* Stop the service on system shutdown or a request to stop the service. */
    if (dwControl == SERVICE_CONTROL_SHUTDOWN)
      systemShutdown = 1;
    SetEvent(stopEvent);
    /* Wait for the service to stop before returning. */
    WaitForSingleObject(stoppedEvent, INFINITE);
    return NO_ERROR;

  case SERVICE_CONTROL_INTERROGATE:
    /* SERVICE_CONTROL_INTERROGATE has been a no-op since Windows NT. */
    return NO_ERROR;

  case SERVICE_CONTROL_SESSIONCHANGE:
    /* These events must be handled so that the SDK can take appropriate action,
       but the sample itself doesn't do anything. */
    return NO_ERROR;
  }

  return ERROR_CALL_NOT_IMPLEMENTED;
}
