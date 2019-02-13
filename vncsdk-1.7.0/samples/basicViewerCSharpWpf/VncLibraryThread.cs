using RealVNC.VncSdk;
using System;
using System.IO;
using System.Threading;
using System.Threading.Tasks;

namespace BasicViewerCSharpWpf
{
    /// <summary>
    /// Class to run a single thread/task that accesses the VNC library. This is because the thread can only have a single init and shutdown
    /// per process and needs to accessed on a single thread. This task will simply wait for a shutdown signal or
    /// another ViewerSession with which to make a connection attempt and run the connection via the session's Run() method.
    /// </summary>
    class VncLibraryThread : IDisposable
    {
        private readonly Task LibraryTask;
        private readonly TaskCompletionSource<VncLibraryThread> LibraryReady = new TaskCompletionSource<VncLibraryThread>();

        private readonly ManualResetEventSlim NewSession = new ManualResetEventSlim(false);
        private readonly ManualResetEventSlim ShouldStop = new ManualResetEventSlim(false);

        private VncViewerSession CurrentVncViewerSession;

        // To enable direct TCP connectivity you need to copy the content of your add-on code here
        private const string DirectTcpAddOnCode = @"";

        /// <summary>
        /// Starts a new VncLibraryThread.
        /// </summary>
        /// <returns>A task that will return the VncLibraryThread once it is ready.</returns>
        public static Task<VncLibraryThread> Start()
        {
            return new VncLibraryThread().LibraryReady.Task;
        }

        private VncLibraryThread()
        {
            LibraryTask = Task.Run(() =>
            {
                if (LoadLibrary())
                {
                    Run();
                }
            });
        }

        /// <summary>
        /// Starts the viewer session. Not safe to call again until the caller
        /// has been notified that the session has ended.
        /// </summary>
        /// <param name="viewerSession">The viewer session to start.</param>
        public void StartViewerSession(VncViewerSession viewerSession)
        {
            CurrentVncViewerSession = viewerSession;
            NewSession.Set();
        }

        private void Run()
        {
            try
            {
                RunLoop();
            }
            catch (Exception e)
            {
                Console.WriteLine("SDK error: {0}: {1}", e.GetType().Name, e.Message);
#if DEBUG
                Console.WriteLine(e.StackTrace);
#endif
            }
            finally
            {
                LibraryShutdown();
            }
        }

        /// <summary>
        /// Loads the library and updates the LibraryReady task result.
        /// </summary>
        /// <returns><code>true</code> on success or <code>false</code> if an
        /// exception occurred.</returns>
        private bool LoadLibrary()
        {
            try
            {
                LibraryInit();
                LibraryReady.SetResult(this);
                return true;
            }
            catch (Exception e)
            {
                Console.WriteLine("SDK error: {0}: {1}", e.GetType().Name, e.Message);
#if DEBUG
                Console.WriteLine(e.StackTrace);
#endif
                LibraryReady.SetException(e);
                return false;
            }
        }

        private void RunLoop()
        {
            // Wait for a new viewer session, or to be told to stop.
            var handles = new[] { NewSession.WaitHandle, ShouldStop.WaitHandle };
            while (WaitHandle.WaitAny(handles) == 0)  // NewSession
            {
                // Reset the event, so that the UI may start a new session
                // as soon as it is notified of this session's disconnection.
                NewSession.Reset();

                //
                // Do all the work in here!
                //
                CurrentVncViewerSession.Run();
            }
        }

        private static void LibraryInit()
        {
            // Get the directory containing the VNC SDK dynamic library.
            var libDir = GetLibraryDirectory();

            // Load the library.
            DynamicLoader.LoadLibrary(libDir);

            // Create a logger with outputs to sys.stderr
            Logger.CreateStderrLogger();

            // Create a file DataStore for storing persistent data for the viewer.
            // Ideally this would be created in a directory that only the viewer
            // user has access to.
            DataStore.CreateFileStore("dataStore.txt");

            // Now initialise the library proper.
            Library.Init();

            if (!string.IsNullOrEmpty(DirectTcpAddOnCode))
                Library.EnableAddOn(DirectTcpAddOnCode);
        }

        private static void LibraryShutdown()
        {
            Library.Shutdown();
        }

        #region FindLibrary
        /// <summary>
        /// Get the directory containing the VNC SDK dynamic library.
        /// </summary>
        static string GetLibraryDirectory()
        {
            var exeDir = AppDomain.CurrentDomain.BaseDirectory;
#if DEBUG
            // Get the default location of the VNC SDK "lib" directory
            // relative to the executable's build directory.
            var sdkRoot = new DirectoryInfo(exeDir).Parent.Parent.Parent.Parent;
            var libDir = Path.Combine(sdkRoot.FullName, "lib");

            // Return the appropriate platform-specific subdirectory.
            return DynamicLoader.GetPlatformSubdirectory(libDir);
#else
            // EDIT AS APPROPRIATE
            throw new NotImplementedException(
                $"{nameof(VncLibraryThread)}.{nameof(GetLibraryDirectory)}()\n\n" +
                "Production applications should return a trusted directory, " +
                "which will depend on details of how the application will be " +
                "deployed.");
            // return exeDir;  // Assumes all files are in a secure directory.
#endif
        }
        #endregion

        /// <summary>
        /// Stops the library altogether. Should only be called when no viewer
        /// sessions are in progress.
        /// </summary>
        /// <remarks>
        /// Once called, no further connections can be made by this process.
        /// </remarks>
        public void StopLibrary()
        {
            ShouldStop.Set();

            // Stop any running VncViewerSession without a clean disconnection.
            EventLoop.Stop();

            LibraryTask.Wait();
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

            NewSession.Dispose();
            ShouldStop.Dispose();
        }
    }
}
