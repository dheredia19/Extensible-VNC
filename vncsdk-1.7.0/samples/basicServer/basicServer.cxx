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
#include <string.h>
#include <stdlib.h>
#include <time.h>

#include <vnc/Vnc.h>

/*
 * basicServer sample
 *
 * This cross-platform sample shows how to implement a basic VNC server using
 * the VNC SDK.
 *
 * Two types of connectivity are supported: Cloud-based and direct TCP
 * connection, with the server permitted to use both mechanisms concurrently.
 *
 * Note: To use direct TCP you will need to apply an add-on code; a trial
 * code is available from your RealVNC account. You can ignore TCP-related
 * code below if you do not intend to use the Direct TCP add-on.
 *
 * The server listens for incoming connections using connectivity details that
 * can be either specified on the command line, or built-in using macro
 * definitions provided below.
 *
 * Each time it starts, the server generates a new random 4-digit password and
 * prints this to the console. A viewer must specify this password when prompted
 * in order to successfully connect.
 */


/* For Cloud connections, either hard-code the Cloud address for the Server OR
 * specify it at the command line. Example Cloud address:
 * LxygGgSrhXQFiLj5M4M.LxyPXzA9sGLkB6pCtJv.devEX1Sg2Txs1CgVuW4.LxyPRsVnXoDoue4Xqm
 */
#define LOCAL_CLOUD_ADDRESS ""

/* Either hard-code the Cloud password associated with this Cloud address OR
 * specify it at the command line. Example Cloud password: KMDgGgELSvAdvscgGfk2
 */
#define LOCAL_CLOUD_PASSWORD ""

/* To enable direct TCP connectivity you need to copy the content of your
   add-on code into the string below. */
static const char* directTcpAddOnCode = "";

/* For direct TCP connections, you must provide a TCP listening port number.
   Either edit the macro below OR provide the port number on the command line.
   The default direct TCP port number can be specified below by using:
   #define TCP_PORT VNC_DIRECT_TCP_DEFAULT_PORT
   Ignore this macro if you are not using the Direct TCP add-on */
#define TCP_PORT 0

/* The following flags indicate the type of connection(s) being used and they
   are set automatically according to user-supplied command line arguments and
   the macro definitions above. Each type of connection is optional.
   If you set any flag to true below then that makes that type of connection
   mandatory i.e. connectivity details MUST be provided via the command line or
   using the macros above. */
bool usingCloud = false;
bool usingDirectTcp = false;

/* Number of random digits in the auto-generated server password: */
const int serverPasswordLength = 4;

/* Stores the auto-generated server password: */
char serverPassword[serverPasswordLength + 1];

/* Function prototypes */
bool parseCommandLine(int argc, const char** argv,
                      const char** cloudAddress, const char** cloudPassword,
                      int* port);
bool initializeSDKandAddOns();
vnc_Server* createAndInitServer();
void setupSecurity(vnc_Server* server);
vnc_CloudListener* createCloudListener(vnc_Server* server,
                                       const char* cloudAddress,
                                       const char* cloudPassword);
vnc_DirectTcpListener* createDirectTcpListener(vnc_Server* server, int port);
void waitForEnter();
void usageAdvice();
void showSDKError(const char* errorString);

/* This flag is used to indicate that we need to retain the console after an
   error condition so the user has a chance to see the relevant logging. */
bool needWait = false;

/*
 * Server main function
 */
int main(int argc, const char** argv)
{
  int exitCode = 1;

  /* Parameter initialisation */
  const char* cloudAddress = LOCAL_CLOUD_ADDRESS;
  const char* cloudPassword = LOCAL_CLOUD_PASSWORD;

  vnc_Server* server = 0;
  vnc_CloudListener* cloudListener = 0;

  /* These are only relevant if you are using the Direct TCP add-on */
  int port = TCP_PORT;
  vnc_DirectTcpListener* directTcpListener = 0;

  /* Parse command line */
  if (!parseCommandLine(argc, argv, &cloudAddress, &cloudPassword, &port)) {
    return exitCode;
  }

  /* Create a logger which outputs to stderr.
     This is created before initializing the server so we receive logging
     as soon as the server starts up. */
  vnc_Logger_createStderrLogger();

  /* Create a file DataStore for storing persistent data for the server.
     Ideally this would be created in a directory that only the server
     user has access to. */
  if (!vnc_DataStore_createFileStore("fileStore.txt")) {
    waitForEnter();
    return exitCode;
  }

  /* Initialize SDK and optional Add-Ons */
  if (!initializeSDKandAddOns()) {
    return exitCode;
  }

  /* Create server and configure callbacks */
  server = createAndInitServer();
  if (server) {
    /* Setup security */
    setupSecurity(server);

    /* Listen on each transport that we intend to use. */
    bool proceed = true;
    if (usingCloud) {
      cloudListener = createCloudListener(server, cloudAddress, cloudPassword);
      if (!cloudListener) proceed = false;
    }
    if (proceed && usingDirectTcp) {
      directTcpListener = createDirectTcpListener(server, port);
      if (!directTcpListener) proceed = false;
    }

    /* Only continue if we have successfully created all intended listeners */
    if (proceed) {
      /* Run the EventLoop */
      vnc_EventLoop_run();
      exitCode = 0;
    }
  }
  if (needWait)
    waitForEnter();

  /* Cleanup */
  if (cloudListener) vnc_CloudListener_destroy(cloudListener);
  if (directTcpListener) vnc_DirectTcpListener_destroy(directTcpListener);
  if (server) vnc_Server_destroy(server);
  
  /* Shutdown the SDK */
  vnc_shutdown();
  return exitCode;
}

/*
 * Provide usage information on console.
 */
void usageAdvice()
{
  std::cerr << "Usage:  ./basicServer [cloudAddress cloudPassword] "
               "[directTcpPortNumber]" << std::endl;
  waitForEnter();
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
 *   3 arguments - Cloud and direct TCP connectivity to be used
 *                 [cloudAddress cloudPassword] [directTcpPortNumber]
 *
 *   2 arguments - Cloud connectivity to be used
 *                 [cloudAddress cloudPassword]

 *   1 argument  - Direct TCP connectivity to be used
 *                 [directTcpPortNumber]

 *   0 arguments - the built-in macros must be set appropriately
 */
bool parseCommandLine(int argc, const char** argv,
                      const char** cloudAddress,
                      const char** cloudPassword,
                      int* tcpPort)
{
  bool badArgs = false;

  /* Parse any supplied command line arguments */
  if (argc >= 1 && argc <= 4) {
    if (argc == 4) { /* Cloud and direct TCP arguments */
      *cloudAddress = argv[1];
      *cloudPassword = argv[2];
      *tcpPort = extractPortNum(argv[3]);
      usingCloud = usingDirectTcp = true;
    } else if (argc == 3) { /* Cloud arguments only */
      *cloudAddress = argv[1];
      *cloudPassword = argv[2];
      usingCloud = true;
    } else  if (argc == 2) { /* Direct TCP argument only */
      *tcpPort = extractPortNum(argv[1]);
      usingDirectTcp = true;
    } else { /* Examine initial values set by macros */
      if (**cloudAddress || **cloudPassword) usingCloud = true;
      if (*tcpPort) usingDirectTcp = true;
    }

    /* Check if all required connectivity details are provided */
    if (usingCloud && (!**cloudAddress || !**cloudPassword)) {
      std::cerr << "You must provide a valid Cloud address and password"
                << std::endl;
      badArgs = true;
    }
    if (usingDirectTcp && !*tcpPort) {
      std::cerr << "You must provide a valid TCP port number"
                << std::endl;
      badArgs = true;
    }
    if (!usingCloud && !usingDirectTcp) {
      std::cerr << "No connectivity information provided." << std::endl;
      badArgs = true;
    }
  } else badArgs = true; /* Invalid number of arguments */

  if (badArgs) {
    usageAdvice();
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

  /* Enable Direct TCP Add-On */
  if (usingDirectTcp && !vnc_enableAddOn(directTcpAddOnCode)) {
    showSDKError("Failed to enable Direct TCP add-on");
    return false;
  }

  return true;
}

/*
 * Connection callback - connection started
 */
void connectionStarted(void* userData,
                       vnc_Server* server,
                       vnc_Connection* connection)
{
  const char* peerAddress = vnc_Server_getPeerAddress(server, connection);
  std::cout << "Viewer " << peerAddress << " connected" << std::endl;
}

/*
 * Connection callback - connection ended
 */
void connectionEnded(void* userData,
                     vnc_Server* server,
                     vnc_Connection* connection)
{
  const char* peerAddress = vnc_Server_getPeerAddress(server, connection);
  std::cout << "Viewer " << peerAddress << " disconnected" << std::endl;
}

/*
 * Create Server, setting up connection callbacks
 */
vnc_Server* createAndInitServer()
{
  /* Initialize the server. Note that the vncagent path is not specified, so it
     should be found in the same directory as the main program */
  vnc_Server* server = vnc_Server_create(0);
  if (!server) {
    showSDKError("Failed to initialize server");
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
 * Security callback - checks if a username is required. Always false.
 */
static vnc_bool_t isUserNameRequired(void* userData, vnc_Server* server,
                                     vnc_Connection* connection)
{
  /* Don't prompt for a username when accessing this server, just a password
     is required */
  return vnc_false;
}

/*
 * Security callback - checks supplied authentication password.
 */
static int authenticateUser(void* userData, vnc_Server* server,
                            vnc_Connection* connection, const char* username,
                            const char* password)
{
  /* Check that the password supplied by the connecting viewer is the same as
     the server's auto-generated random password. If so, allow the connection
     with all permissions, otherwise do not allow the connection. */
  if (strcmp(password, serverPassword) == 0) {
    return vnc_Server_PermAll;
  }
  return 0;
}

/*
 * Setup server security-related settings and callbacks
 */
void setupSecurity(vnc_Server* server)
{
  /* Generate the server password using a series of random digits.
     Note that for generating random passwords for production use, it is
     advisable to use a better source of random numbers. The C library rand()
     function is only used here as a simple example as it is available on all
     platforms. */
  srand((unsigned int)time(0));
  for (int i=0; i<serverPasswordLength; ++i)
    serverPassword[i] = '0' + (rand() % 10);
  serverPassword[serverPasswordLength] = '\0';

  std::cout << "Server password is: " << serverPassword << std::endl;

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
 * Cloud listener callback - failed
 */
static void listeningFailed(void* userData, vnc_CloudListener* listener,
                            const char* cloudError, int suggestedRetryTime)
{
  std::cerr << "VNC Cloud listening error: " << cloudError << std::endl;
  needWait = true;
  vnc_EventLoop_stop();
}

/*
 * Cloud listener callback - status changed
 */
static void listeningStatusChanged(void* userData, vnc_CloudListener* listener,
                                   vnc_CloudListener_Status status)
{
  if(status == vnc_CloudListener_StatusSearching) {
    std::cout << "The listener is in the process of establishing an "
      "association with VNC Cloud" << std::endl;
  } else {
    std::cout << "Listening for VNC Cloud connections" << std::endl;
  }
}

/*
 * Start listening for connections made via VNC Cloud
 */
vnc_CloudListener* createCloudListener(vnc_Server* server,
                                       const char* cloudAddress,
                                       const char* cloudPassword)
{
  std::cout << "Signing in to VNC Cloud" << std::endl;
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
    showSDKError("Could not create Cloud listener");
  }
  return listener;
}

/*
 * RsaKey callback - key details ready
 */
void rsaKeyDetailsReady(void* userData,
                        const vnc_DataBuffer* rsaPublic,
                        const char* hexFingerprint,
                        const char* catchphraseFingerprint)
{
  std::cout << "Server id is: " << hexFingerprint << std::endl;
  std::cout << "Server catchphrase is: " << catchphraseFingerprint << std::endl;

}

/*
 * Start listening for connections made via direct TCP
 * Ignore this if you do not intend to use the Direct TCP add-on
 */
vnc_DirectTcpListener* createDirectTcpListener(vnc_Server* server, int port)
{
  std::cout << "Listening for Direct TCP connections" << std::endl;
  /* This listens on ALL addresses and does not employ callbacks */
  vnc_DirectTcpListener* listener =
      vnc_DirectTcpListener_create(port, 0,
                                   vnc_Server_getConnectionHandler(server),
                                   0, 0);

  if (!listener) {
    showSDKError("Could not create Direct TCP listener");
  } else {
    /* If DirectTcp is being used, request the RSA key details to display so
       that viewers can verify they are connecting to this server. */
    vnc_RsaKey_Callback keyCallback = {
      rsaKeyDetailsReady
    };
    vnc_RsaKey_getDetails(&keyCallback, 0, true);
  }
  return listener;
}


/*
 * Prompt and wait for user to press enter before continuing.
 * This is used when displaying error messages, allowing the user to read the
 * message on systems where the terminal closes when the program exits.
 */
void waitForEnter()
{
  std::cout << "Press ENTER to continue..." << std::endl;
  std::cin.ignore();
}

/*
 * Provide SDK error information on the console.
 */
void showSDKError(const char* errorString)
{
  std::cerr << errorString << ": " << vnc_getLastError() << std::endl;
  waitForEnter();
}

#ifdef WIN32
#include <Windows.h>
/*
 * Install a safer Ctrl+C/Ctrl+Break/End-Task handler on Windows. These run on
 * a newly injected thread, and the default handler unsafely unloads DLLs
 * while they may still be in-use on the main thread.
 *
 * This is necessary as the SDK's threading model does not allow unloading the
 * SDK from one thread while the event loop is still running on another thread.
 */
static struct Win32ConsoleCleanup {
  Win32ConsoleCleanup() { SetConsoleCtrlHandler(&cleanup, TRUE); }
  static BOOL WINAPI cleanup(DWORD dwCtrlType)
  {
    switch (dwCtrlType) {
    case CTRL_C_EVENT: case CTRL_BREAK_EVENT: case CTRL_CLOSE_EVENT:
      /* Tell the main thread to stop its event loop and exit cleanly,
         which will stop all threads including this one. */
      vnc_EventLoop_stop();
      Sleep(500);
      /* The main thread took too long to exit, so hard-kill the process
         with TerminateProcess, since ExitProcess is only safe on the main
         thread, and the default handler isn't safe to return to. */
      TerminateProcess(GetCurrentProcess(), STATUS_CONTROL_C_EXIT);
      return TRUE;  /* This is unreachable. */
    }
    return FALSE;
  }
} win32Cleanup;
#endif
