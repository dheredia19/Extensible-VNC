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

#import <Foundation/Foundation.h>

#import "AppDelegate.h"

/*
 * basicViewerMac sample
 *
 * This sample shows how to implement a basic VNC viewer using the VNC SDK
 * running on OS X.
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
#define LOCAL_CLOUD_ADDRESS @""

/* Either hard-code the Cloud password associated with this Cloud address OR
 * specify it at the command line. Example Cloud password: KMDgGgELSvAdvscgGfk2
 */
#define LOCAL_CLOUD_PASSWORD @""

/* Either hard-code the Cloud address of the Server (peer) to connect to OR
 * specify it at the command line. Example peer Cloud address:
 * LxyDgGgrhXQFiLj5M4M.LxyPXzA9sGLkB6pCtJv.devEX1Sg2Txs1CgVuW4.LxyPRydf9ZczNo13BcD
 */
#define PEER_CLOUD_ADDRESS @""

/* To enable direct TCP connectivity you need to copy the content of your
   add-on code into the string below. */
static const char* directTcpAddOnCode = "";

/* For direct TCP connections you must provide the server's TCP host address
   and port number. Either edit the macros below OR provide these connection
   details on the command line.
   The default direct TCP port number can be specified below by using:
   #define TCP_PORT VNC_DIRECT_TCP_DEFAULT_PORT
   Ignore these macros if you are not using the Direct TCP add-on */
#define TCP_ADDRESS @""
#define TCP_PORT 0

/* The value of this flag is set automatically according to the user-supplied
   command line arguments and macro definitions above. Cloud connectivity is
   presumed by default here. */
bool usingCloud = true;

/* Function prototypes */
bool parseCommandLine(int argc, const char** argv,
                      NSString** localCloudAddress,
                      NSString** localCloudPassword,
                      NSString** peerCloudAddress,
                      int* tcpPort, NSString** tcpHostAddress);
bool initializeSDKandAddOns();
bool initializeFileDescriptorSets();
bool createDataStore();
void usageAdvice();
void messageBox(NSString* message);
void showSDKError(NSString* message);
bool makeCloudConnection(NSString* localCloudAddress,
                         NSString* localCloudPassword,
                         NSString* peerCloudAddress,
                         vnc_Viewer* viewer);
bool makeDirectTcpConnection(NSString* hostAddress, int port,
                             vnc_Viewer* viewer);


@interface AppDelegate ()

@property (strong) NSWindow *window;
@end

@implementation AppDelegate

- (id)init
{
  if (self = [super init]) {
    NSRect contentSize = NSMakeRect(0, 0, 800, 600);
    NSUInteger windowStyleMask = NSTitledWindowMask | NSResizableWindowMask |
      NSClosableWindowMask | NSMiniaturizableWindowMask;
    _window = [[NSWindow alloc] initWithContentRect:contentSize
               styleMask:windowStyleMask backing:NSBackingStoreBuffered
               defer:YES];
    _window.backgroundColor = [NSColor blackColor];
    _window.title = @"BasicViewerMac";
    [_window setDelegate:self];

    view = [[BasicViewerView alloc] init];
  }
  return self;
}

- (void)applicationWillFinishLaunching:(NSNotification *)notification
{
  [_window setContentView:view];
}

- (void)applicationDidFinishLaunching:(NSNotification *)aNotification
{
  [NSApp activateIgnoringOtherApps:YES];

  int exitCode = 1;

  /* Parameter initialization */
  NSString* localCloudAddress = LOCAL_CLOUD_ADDRESS;
  NSString* localCloudPassword = LOCAL_CLOUD_PASSWORD;
  NSString* peerCloudAddress = PEER_CLOUD_ADDRESS;

  /* These are only relevant if you are using the Direct TCP add-on */
  NSString* hostAddress = TCP_ADDRESS;
  int port = TCP_PORT;

  if (!parseCommandLine(&localCloudAddress, &localCloudPassword,
                        &peerCloudAddress,
                        &port, &hostAddress)) {
    exit(exitCode);
  }

  /* Create a logger which outputs to stderr */
  vnc_Logger_createStderrLogger();

  /* Create a DataStore for storing persistent data for the viewer.
     This is created under Application Support. */
  if (!createDataStore()) {
    exit(exitCode);
  }

  /* Initialize SDK and optional Add-Ons */
  if (!initializeSDKandAddOns()) {
    exit(exitCode);
  }

  /* Create the viewer object */
  viewer = vnc_Viewer_create();
  if (!viewer) {
    showSDKError(@"Failed to create viewer");
    exit(exitCode);
  }

  /* Setup BasicViewerView with the viewer SDK object */
  NSRect frame = [_window frame];
  frame.size.width = vnc_Viewer_getViewerFbWidth(viewer);
  frame.size.height = vnc_Viewer_getViewerFbHeight(viewer);
  [_window setFrame:frame display:NO];
  [_window center];
  [_window makeKeyAndOrderFront:self];
  [view createDesktop: viewer];

  /* Make a connection to the server */
  if (usingCloud) {
    if (!makeCloudConnection(localCloudAddress, localCloudPassword,
                             peerCloudAddress, viewer)) {
      exit(exitCode);
    }
  } else {
    if (!makeDirectTcpConnection(hostAddress, port, viewer)) {
      exit(exitCode);
    }
  }
}

- (NSApplicationTerminateReply)applicationShouldTerminate:(NSApplication *)theApplication
{
  if (vnc_Viewer_getConnectionStatus(viewer) != vnc_Viewer_Disconnected) {
    vnc_Viewer_disconnect(viewer);
    return NSTerminateCancel;
  }
  return NSTerminateNow;
}

- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication *)theApplication
{
  return NO;
}

- (void)applicationWillTerminate:(NSNotification *)aNotification
{
  vnc_Viewer_destroy(viewer);
  vnc_shutdown();
}

- (BOOL)windowShouldClose:(id)sender
{
  vnc_Viewer_disconnect(viewer);
  return NO;
}

- (void)windowDidResignKey:(NSNotification *)aNotification
{
  /* Release any held keys when the viewer window loses focus */
  if (!vnc_Viewer_releaseAllKeys(viewer))
    NSLog(@"call to vnc_Viewer_releaseAllKeys: %s", vnc_getLastError());
}

/*
 * Shows a modal NSAlert message
 */
void messageBox(NSString* message)
{
  NSAlert *alert = [[NSAlert alloc] init];
  [alert setMessageText:message];
  [alert addButtonWithTitle:@"OK"];
  [alert runModal];
}

/*
 * Provide SDK error information in a modal NSAlert message
 */
void showSDKError(NSString* message)
{
  messageBox([NSString stringWithFormat:
              @"%@: %s",
              message, vnc_getLastError()]);
}

/*
 * Provide usage information .
 */
void usageAdvice()
{
  NSString* msg = [NSString stringWithFormat:
                   @"%@%@%@",
                   @"You must provide valid connection details\n\n",
                   @"Either:   localCloudAddress  localCloudPassword  peerCloudAddress\n\n",
                   @"     or:    peerTcpHostAddress  peerTcpPortNumber"
                   ];
  NSSize size = [msg sizeWithAttributes:@{NSFontAttributeName: [NSFont systemFontOfSize:[NSFont systemFontSize]]}];
  NSAlert *alert = [[NSAlert alloc] init];
  alert.accessoryView = [[NSView alloc] initWithFrame:NSMakeRect(0, 0, size.width, 0)];
  [alert setMessageText:@"Usage"];
  [alert setInformativeText:msg];
  [alert addButtonWithTitle:@"OK"];
  [alert runModal];
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
bool parseCommandLine(NSString** localCloudAddress,
                      NSString** localCloudPassword,
                      NSString** peerCloudAddress,
                      int* tcpPort, NSString** tcpHostAddress)
{
  bool badArgs = false;

  NSMutableArray *argv = [[[NSProcessInfo processInfo] arguments] mutableCopy];
  NSInteger argc = [argv count];

  /* If you run this application from within Xcode you may find an extra command line argument
     has been automatically added i.e. "-NSDocumentRevisionsDebugMode YES"
     This causes a problem for this basic command line parsing algorithm. Please edit your Debug
     Scheme Options to un-check "Allow debugging when using the documents Versions Browser"
   */
  
  /* Parse any supplied command line arguments */
  if (argc == 4 || argc == 3 || argc == 1) {
    if (argc == 4) {  /* Cloud arguments */
      *localCloudAddress = argv[1];
      *localCloudPassword = argv[2];
      *peerCloudAddress = argv[3];
    } else  if (argc == 3) {  /* Direct TCP arguments */
      *tcpHostAddress = argv[1];
      *tcpPort = extractPortNum([argv[2] UTF8String]);
      usingCloud = false;
    } else { /* Examine the initial values set by macros */
      if ([*localCloudAddress length] || [*localCloudPassword length] || [*peerCloudAddress length])
        usingCloud = true;
      else if (*tcpPort || [*tcpHostAddress length])
        usingCloud = false;
    }

    /* Check if all required connectivity details are provided */
    if (usingCloud && (![*localCloudAddress length] ||
                       ![*localCloudPassword length] ||
                       ![*peerCloudAddress length])) {
      badArgs = true;
    } else if (!usingCloud && (!*tcpPort || ![*tcpHostAddress length])) {
      badArgs = true;
    }
  } else { /* Invalid number of arguments */
    badArgs = true;
  }

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
    showSDKError(@"Failed to initialize VNC SDK");
    return false;
  }
  
  /* Enable Direct TCP Add-On */
  if (!usingCloud && !vnc_enableAddOn(directTcpAddOnCode)) {
    showSDKError(@"Failed to enable Direct TCP add-on");
    return false;
  }
  return true;
}

/*
 * Create data store under "Application Support"
 */
bool createDataStore()
{
  NSError* err = nil;
  NSFileManager* fm = [NSFileManager defaultManager];
  NSURL* appSupportDir = [fm URLForDirectory:NSApplicationSupportDirectory
                          inDomain:NSUserDomainMask
                          appropriateForURL:nil create:YES error:&err];
  if (err) {
    messageBox([NSString stringWithFormat:
                @"Failed to find or create application support directory: %@",
                err]);
    return false;
  }

  NSString* bundleID = [[NSBundle mainBundle] bundleIdentifier];
  NSURL* dirPath = [appSupportDir URLByAppendingPathComponent:bundleID];
  if (![fm createDirectoryAtURL:dirPath withIntermediateDirectories:YES
                     attributes:nil error:&err])
  {
    messageBox([NSString stringWithFormat:
                @"Could not create data store directory: %@", err]);
    return false;
  }
  dirPath = [dirPath URLByAppendingPathComponent:@"dataStore.txt"];
  if (!vnc_DataStore_createFileStore([[dirPath path] UTF8String])) {
    messageBox([NSString stringWithFormat:
                @"Could not create data store file: %s", vnc_getLastError()]);
    return false;
  }
  return true;
}

/*
 * Make a Cloud connection
 */
bool makeCloudConnection(NSString* localCloudAddress,
                         NSString* localCloudPassword,
                         NSString* peerCloudAddress,
                         vnc_Viewer* viewer)
{
  vnc_CloudConnector* cloudConnector = 0;
  /* Create connector */
  if (!(cloudConnector = vnc_CloudConnector_create([localCloudAddress UTF8String],
                                                   [localCloudPassword UTF8String]))) {
    showSDKError(@"Failed to create Cloud connector");
    return false;
  }
  /* Connect*/
  if (!vnc_CloudConnector_connect(cloudConnector, [peerCloudAddress UTF8String],
                                  vnc_Viewer_getConnectionHandler(viewer))) {
    showSDKError(@"Failed to make VNC Cloud connection");
    vnc_CloudConnector_destroy(cloudConnector);
    return false;
  }
  vnc_CloudConnector_destroy(cloudConnector); /* Connector no longer required */
  return true;
}

/*
 * Make a Direct TCP connection.
 * Ignore this if you do not intend to use the Direct TCP add-on
 */
bool makeDirectTcpConnection(NSString* hostAddress,
                             int port,
                             vnc_Viewer* viewer)
{
  vnc_DirectTcpConnector* tcpConnector = 0;
  /* Create direct TCP connector */
  if (!(tcpConnector = vnc_DirectTcpConnector_create())) {
    showSDKError(@"Failed to create direct TCP connector");
    return false;
  }
  /* Connect */
  if (!vnc_DirectTcpConnector_connect(tcpConnector, [hostAddress UTF8String], port,
                                      vnc_Viewer_getConnectionHandler(viewer))) {
    showSDKError(@"Failed to start connection");
    vnc_DirectTcpConnector_destroy(tcpConnector);
    return false;
  }
  vnc_DirectTcpConnector_destroy(tcpConnector);
  return true;
}


@end
