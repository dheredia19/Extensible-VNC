using RealVNC.VncSdk;
using System;
using System.Runtime.InteropServices;
using System.Windows;

namespace BasicViewerCSharpWpf
{
    public class VncViewerSession
    {
        //
        // Cloud connection properties
        //
        public string LocalCloudAddress { get; set; }
        public string LocalCloudPassword { get; set; }
        public string PeerCloudAddress { get; set; }

        //
        // Or direct-connection properties
        //
        public string TcpAddress { get; set; }

        public int TcpPort { get; set; }

        //
        // Other settings

        public bool UsingCloud { get; set; } = true;

        public System.Drawing.Size? CurrentCanvasSize { get; set; }

        public IVncFramebufferCallback FrameBufferHandler { get; set; }


        private static VncViewerSession RunningSession;

        public Action OnConnect { get; set; }
        public Action<string, Viewer.DisconnectFlags> OnDisconnect { get; set; }

        public Action<string> OnNewStatus { get; set; }

        public bool AnnotationEnabled { get; set; }

        // A Viewer property that is only valid within a running session.
        private Viewer Viewer { get; set; }

        // A FrameBuffer property that is only valid within a running session.
        private FrameBuffer FrameBuffer { get; set; }

        // Callback properties that are only valid within a running session.
        private Viewer.ConnectionCallback ConnectionCallback { get; set; }
        private Viewer.FramebufferCallback FramebufferCallback { get; set; }
        private Viewer.ServerEventCallback ServerEventCallback { get; set; }
        private AnnotationManager.Callback AnnotationManagerCallback { get; set; }

        // Final result of a session, the disconnection reason and flags.
        private string DisconnectReason = "Stopped";
        private Viewer.DisconnectFlags DisconnectFlags = Viewer.DisconnectFlags.Zero;

        private double ServerAspectRatio;

        /// <summary>
        /// The main routine in which a connection is made and maintained.
        /// This function will only return once the EventLoop is stopped,
        /// which happens when the connection ends.
        /// </summary>
        public void Run()
        {
            try
            {
                // Keep these SDK objects available all the time the session is running.
                Viewer = new Viewer();
                FrameBuffer = new FrameBuffer(Viewer);

                SetUpCallbacks(Viewer);

                // Begin the connection to the Server.

                if (CurrentCanvasSize == null)
                    CurrentCanvasSize = new System.Drawing.Size(800, 600);

                UpdateFrameBufferToCanvasSize();

                // See if we should override the UsingCloud setting
                if (InferredUsingCloud != null)
                    UsingCloud = InferredUsingCloud.Value;

                if (UsingCloud)
                {
                    // Make a Cloud connection.
                    NewStatus("Connecting via VNC Cloud");
                    using (CloudConnector cloudConnector = new CloudConnector(LocalCloudAddress, LocalCloudPassword))
                    {
                        cloudConnector.Connect(PeerCloudAddress, Viewer.GetConnectionHandler());
                    }
                }
                else
                {
                    // Make a Direct TCP connection.
                    // Ignore this if you do not intend to use the Direct TCP add-on.
                    NewStatus($"Connecting to host address: {TcpAddress} port: {TcpPort}");
                    using (DirectTcpConnector tcpConnector = new DirectTcpConnector())
                    {
                        tcpConnector.Connect(TcpAddress, TcpPort, Viewer.GetConnectionHandler());
                    }
                }

                // Run the SDK's event loop.  This will return when any thread
                // calls EventLoop.Stop(), allowing this ViewerSession to stop.
                RunningSession = this;
                EventLoop.Run();
            }
            catch (Exception e)
            {
                Console.WriteLine("SDK error: {0}: {1}", e.GetType().Name, e.Message);

                // Handle the implied disconnect (or failed to connect) and show the exception message as a status
                DisconnectReason = e.GetType().Name + ": " + e.Message;
            }
            finally
            {
                RunningSession = null;

                // Dispose of the SDK objects.
                FrameBuffer?.Dispose();
                FrameBuffer = null;

                // If the viewer is still connected, this drops the connection.
                Viewer?.Dispose();
                Viewer = null;

                // Notify that the session is finished and another may be enqueued.
                ReportDisconnection();
            }
        }

        private void ReportDisconnection()
        {
            // Draw a blank control - show we're disconnected (omit this call to keep the last image on screen)
            FrameBufferHandler.OnFrameBufferResized(0, 0, 0, null, false);

            // And pass on to the caller's disconnect routine.
            OnDisconnect.Invoke(DisconnectReason, DisconnectFlags);
        }

        private void SetUpCallbacks(Viewer viewer)
        {
            // Define callbacks to handle session events.

            // Callbacks should be defined as class members, not locals,
            // to prevent them being garbage collected while in use.

            ConnectionCallback = new Viewer.ConnectionCallback(
                connected:
                    (vwr) => OnConnect?.Invoke(),
                disconnected:
                    (vwr, reason, df) =>
                    {
                        if (RunningSession != this)
                            return;  // Already stopped, don't overwrite reason.

                        // On disconnection, record the reason and stop the event loop.
                        // This will cause the EventLoop.Run() call in Run() to return.
                        DisconnectReason = reason;
                        DisconnectFlags = df;
                        EventLoop.Stop();
                    });

            FramebufferCallback = new Viewer.FramebufferCallback(
                serverFbSizeChanged: OnServerFbSizeChanged,
                viewerFbUpdated: OnViewerFbUpdated);

            ServerEventCallback = new Viewer.ServerEventCallback(
                serverClipboardTextChanged: null,
                serverFriendlyNameChanged: OnNameChange);

            AnnotationManagerCallback = new AnnotationManager.Callback(
                availabilityChanged:
                    (am, isAvailable) =>
                    {
                        if (!isAvailable)
                        {
                            NewStatus("Annotation unavailable");
                            AnnotationEnabled = false;
                        }
                    });

            // Set the callbacks on the viewer.
            viewer.SetConnectionCallback(ConnectionCallback);
            viewer.SetFramebufferCallback(FramebufferCallback);
            viewer.SetServerEventCallback(ServerEventCallback);

            // AnnotationManagerCallback is set when annotation is enabled.
        }

        private bool UpdateFrameBufferToCanvasSize(System.Drawing.Size? newSize = null, bool requestWindowResize = false)
        {
            if (newSize != null && !newSize.Value.IsEmpty)
                CurrentCanvasSize = newSize;

            System.Drawing.Size size = CurrentCanvasSize ?? new System.Drawing.Size();

            if (!size.IsEmpty)
            {
                if (ServerAspectRatio > 0)
                {
                    // Keep aspect ratio of the source screen and display within the dimensions of our canvas
                    var inferredH = (int)(size.Width / ServerAspectRatio);
                    var inferredW = (int)(size.Height * ServerAspectRatio);

                    // Go with the smallest size: keep within our canvas / window
                    if (inferredH < size.Height)
                        size.Height = inferredH;
                    else
                        size.Width = inferredW;
                }

                UpdateFrameBufferSize(size.Width, size.Height, requestWindowResize);
                return true;
            }

            return false;
        }

        private void UpdateFrameBufferSize(int width, int height, bool requestWindowResize = false)
        {
            width = Math.Max(width, 10);
            height = Math.Max(height, 10);
            FrameBuffer.SetBuffer(width, height);
            FrameBufferHandler.OnFrameBufferResized(width, height, width, FrameBuffer.Buffer, requestWindowResize);
        }


        private void OnServerFbSizeChanged(Viewer viewer, int w, int h)
        {
            // The Server screen size has changed, so we signal the window to
            // resize to match its aspect ratio.
            ServerAspectRatio = w / (double)h;
            w = viewer.GetViewerFbWidth();
            h = (int)(w / ServerAspectRatio);
            FrameBuffer.SetBuffer(w, h);

            // Before we pass it onto the frame-buffer-handler check we have correctly applied the resize to our
            if (!UpdateFrameBufferToCanvasSize())
                FrameBufferHandler.OnFrameBufferResized(w, h, w, FrameBuffer.Buffer, true);
        }

        private void OnViewerFbUpdated(Viewer viewer, int x, int y, int w, int h)
        {
            // The Server has sent fresh pixel data, so we redraw the specified part of the form
            FrameBufferHandler.OnFrameBufferUpdated(new Rect(x, y, w, h));
        }

        /// <summary>
        /// Display a status message to the user
        /// </summary>
        private void NewStatus(string statusMessage)
        {
            Console.WriteLine(statusMessage);

            OnNewStatus?.Invoke(statusMessage);
        }

        /// <summary>
        /// Process a change in the server's friendly name
        /// </summary>
        private void OnNameChange(Viewer vwr, string newName)
        {
            // Display name
            NewStatus($"Server name change: {newName}");
        }

        /// <summary>
        /// Return true if the settings infer to use cloud, false if the settings infer direct-tcp
        /// null if the settings could be either or none.
        /// </summary>
        public bool? InferredUsingCloud
        {
            get
            {
                bool GotCloudSettings =
                    !string.IsNullOrEmpty(LocalCloudAddress) &&
                    !string.IsNullOrEmpty(LocalCloudPassword) &&
                    !string.IsNullOrEmpty(PeerCloudAddress);

                bool GotDirectTcpSettings = !string.IsNullOrEmpty(TcpAddress) && TcpPort != 0;

                // If one of the settings allows us to infer which connection to use then return that
                if (GotCloudSettings != GotDirectTcpSettings)
                    return GotCloudSettings;

                // Otherwise show we don't know: null
                return null;
            }
        }

        #region Cross-thread calls

        // Runs an action within the session. Safe to call from any thread.
        private void RunInSession(Action action)
        {
            // The action will be run by the library within EventLoop.Run(),
            // so there will always be a running session when the action runs.
            EventLoop.RunOnLoop(() =>
            {
                // If the session is no longer running, ignore the action.
                if (RunningSession == this)
                    action.Invoke();
            });
        }

        /// <summary>
        /// Stops the session's event loop. Safe to call from any thread.
        /// </summary>
        /// <remarks>
        /// Runs the action on the library thread as part of this session.
        /// </remarks>
        public void StopSession()
        {
            RunInSession(EventLoop.Stop);
        }

        /// <summary>
        /// Starts to cleanly disconnect this session.
        /// Safe to call from any thread.
        /// </summary>
        /// <remarks>
        /// Runs the action on the library thread as part of this session.
        /// </remarks>
        public void Disconnect()
        {
            RunInSession(() => Viewer.Disconnect());
        }

        /// <summary>
        /// Calls Viewer.SendKeyDown() from any thread.
        /// </summary>
        /// <remarks>
        /// Runs the action on the library thread as part of this session.
        /// </remarks>
        public void SendKeyDown(int keysym, int keyCode)
        {
            RunInSession(() => Viewer.SendKeyDown(keysym, keyCode));
        }

        /// <summary>
        /// Calls Viewer.SendKeyUp() from any thread.
        /// </summary>
        /// <remarks>
        /// Runs the action on the library thread as part of this session.
        /// </remarks>
        public void SendKeyUp(int keyCode)
        {
            RunInSession(() => Viewer.SendKeyUp(keyCode));
        }

        /// <summary>
        /// Calls Viewer.SendScrollEvent() from any thread.
        /// </summary>
        /// <remarks>
        /// Runs the action on the library thread as part of this session.
        /// </remarks>
        public void SendScrollEvent(int delta, Viewer.MouseWheel axis)
        {
            RunInSession(() => Viewer.SendScrollEvent(delta, axis));
        }

        /// <summary>
        /// Calls Viewer.SendPointerEvent() from any thread.
        /// </summary>
        /// <remarks>
        /// Runs the action on the library thread as part of this session.
        /// </remarks>
        public void SendPointerEvent(int x, int y, Viewer.MouseButton buttonState, bool rel)
        {
            RunInSession(() => Viewer.SendPointerEvent(x, y, buttonState, rel));
        }

        /// <summary>
        /// Resizes the frame buffer. Safe to call from any thread.
        /// </summary>
        /// <remarks>
        /// Runs the action on the library thread as part of this session.
        /// </remarks>
        public void ResizeFrameBuffer(System.Drawing.Size newSize)
        {
            RunInSession(() => UpdateFrameBufferToCanvasSize(newSize));
        }

        // Annotations: draw an overlay on the Server's screen

        /// <summary>
        /// Start, alter or stop an annotation.
        /// </summary>
        /// <param name="start">true to start or alter settings of existing annotation. false to stop annotation</param>
        /// <param name="persistDurationMs">annotations will fade after this time (ms)</param>
        /// <remarks>
        /// Runs the action on the library thread as part of this session.
        /// </remarks>
        public void ChangeAnnotation(bool start, int penSize = 0, System.Windows.Media.Color? penColour = null, int persistDurationMs = 0)
        {
            if (!start)
            {
                AnnotationEnabled = false;
                return;
            }

            RunInSession(() =>
            {
                var annotationMgr = Viewer.GetAnnotationManager();

                if (annotationMgr != null)
                {
                    if (penSize > 0)
                        annotationMgr.SetPenSize(penSize);
                    if (penColour != null)
                        annotationMgr.SetPenColor(unchecked((int)0xff000000 | (penColour.Value.R << 16) | (penColour.Value.G << 8) | penColour.Value.B));
                    if (persistDurationMs > 0)
                        annotationMgr.SetPersistDuration(persistDurationMs);

                    annotationMgr.SetFadeDuration(300);

                    annotationMgr.SetCallback(AnnotationManagerCallback);
                }

                AnnotationEnabled = true;
            });
        }

        /// <summary>
        /// Calls AnnotationManager.MovePenTo() from any thread.
        /// </summary>
        /// <remarks>
        /// Runs the action on the library thread as part of this session.
        /// </remarks>
        public void MovePenTo(int x, int y, bool penDown)
        {
            RunInSession(() =>
            {
                try
                {
                    Viewer.GetAnnotationManager()?.MovePenTo(x, y, penDown);
                }
                catch (VncException e)
                {
                    // Servers may temporarily refuse annotation (NotSupported)
                    // e.g. when attempting to annotate before authenticating.
                    if (e.ErrorCode != "NotSupported")
                        throw;
                }
            });
        }

        /// <summary>
        /// Calls AnnotationManager.ClearAll() from any thread.
        /// </summary>
        /// <remarks>
        /// Runs the action on the library thread as part of this session.
        /// </remarks>
        public void ClearAnnotation()
        {
            RunInSession(() => Viewer.GetAnnotationManager()?.ClearAll(false));
        }
        #endregion
    }

    public interface IVncFramebufferCallback
    {
        void OnFrameBufferResized(int width, int height, int stride, byte[] buffer, bool resizeWindow);
        void OnFrameBufferUpdated(Rect rc);
    }


    class FrameBuffer : IDisposable
    {
        private readonly Viewer viewer;
        private GCHandle pinnedBuffer;

        public byte[] Buffer { get; private set; }

        public FrameBuffer(Viewer viewer)
        {
            this.viewer = viewer;
        }

        public void SetBuffer(int width, int height)
        {
            if (pinnedBuffer.IsAllocated)
                pinnedBuffer.Free();
            Buffer = new byte[width * height * 4];
            pinnedBuffer = GCHandle.Alloc(Buffer, GCHandleType.Pinned);
            viewer.SetViewerFb(Buffer, PixelFormat.Rgb888(), width, height, width);
        }

        public void Dispose()
        {
            Dispose(true);
            GC.SuppressFinalize(this);
        }

        protected virtual void Dispose(bool disposing)
        {
            if (!disposing)
                return;

            if (pinnedBuffer.IsAllocated)
                pinnedBuffer.Free();
        }
    }
}
