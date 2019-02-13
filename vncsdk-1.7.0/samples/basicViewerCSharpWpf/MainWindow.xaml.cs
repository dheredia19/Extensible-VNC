using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Linq;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Media;

namespace BasicViewerCSharpWpf
{
    /// <summary>
    /// Interaction logic for MainWindow.xaml
    /// </summary>
    public partial class MainWindow : Window
    {
        // (DirectTcpAddOnCode is found in the VncLibraryThread.cs)

        // Leaving these blank will just raise the connect-settings dialog allowing user-input
        // LocalCloud settings are more predisposed to hard-coding
        private ConnectSettings ConnectSettings = new ConnectSettings
        {
            // Set this to false if you only wish to supply your own hard-coded local-cloud values
            LocalCloudIsEditable = true,

            //
            // === Cloud Connection ===

            // For Cloud connections, either hard-code the Cloud address for the Viewer OR
            // specify it at the command line. Example Cloud address:
            // LxygGgSrhXQFiLj5M4M.LxyPXzA9sGLkB6pCtJv.devEX1Sg2Txs1CgVuW4.LxyPRsVnXoDoue4Xqm
            LocalCloudAddress = "",

            // Either hard-code the Cloud password associated with this Cloud address OR
            // specify it at the command line. Example Cloud password: KMDgGgELSvAdvscgGfk2
            LocalCloudPassword = "",

            // Either hard-code the Cloud address of the Server (peer) to connect to OR
            // specify it at the command line. Example peer Cloud address:
            // LxyDgGgrhXQFiLj5M4M.LxyPXzA9sGLkB6pCtJv.devEX1Sg2Txs1CgVuW4.LxyPRydf9ZczNo13BcD
            PeerCloudAddress = "",

            //
            // == Direct Connection ==

            // The alternative to using cloud-credentials is to invoke a direct connection with these settings
            DirectTcpIpAddress = "",
            DirectTcpPort = 0,

            // The value of this flag is set automatically according to the user-supplied
            // command line arguments and macro definitions above. Cloud connectivity is
            // presumed by default here.
            UsingCloud = true,
        };

        // The viewer session we've started running, or null if it has disconnected.
        // Declared volatile so that changes become visible to all UI threads promptly.
        private volatile VncViewerSession ViewerSession;

        private Task<VncLibraryThread> VncLibraryThreadTask;
        private VncLibraryThread VncLibraryThread { get { return VncLibraryThreadTask.Result; } }

        public VncWinformEventMap EventMap { get; private set; }

        public MainWindow()
        {
            // Start the VncLibraryThread while the UI initializes.
            VncLibraryThreadTask = VncLibraryThread.Start();

            InitializeComponent();

            RefreshAnnotationColour();
            RefreshAnnotationDuration();

            Loaded += MainWindow_Loaded;
        }

        async void MainWindow_Loaded(object sender, RoutedEventArgs args)
        {
            // Wait for the VncLibraryThread to be ready to use.
            try
            {
                await VncLibraryThreadTask;
            }
            catch (Exception e)
            {
                // Stop immediately with a message box.
                MessageBox.Show($"{e.GetType().Name}: {e.Message}", "SDK loading failed");
                ImmediateClose();
                return;
            }

            // Enable the connect button now that the library has loaded.
            ButtonConnect.IsEnabled = true;

            // If we have valid existing/hard-coded settings and the -autoconnect command line has been specified then
            // immediately initiate a connection.
            if (HasCommandLineArg("-autoconnect") && ConnectSettings.SettingsArePresent)
            {
                StartConnection();
            }
        }

        private static bool HasCommandLineArg(string arg)
        {
            return Environment.GetCommandLineArgs().Any(a => a == arg);
        }

        private bool CloseImmediately = false;
        private bool IsClosing = false;

        protected override async void OnClosing(CancelEventArgs e)
        {
            Title = "Closing...";

            if (CloseImmediately)
            {
                base.OnClosing(e);
                return;
            }

            if (ViewerSession == null)
            {
                VncLibraryThread.StopLibrary();
                ImmediateClose();
                return;
            }

            // We have an active viewer session, disconnect it.

            // Prevent starting any new connections.
            ButtonConnect.IsEnabled = false;

            // Tell the window not to shut yet, we'll try again in a sec.
            e.Cancel = true;

            IsClosing = true;

            // Disconnect the viewer session within the next few seconds.
            await DisconnectSession(ViewerSession);
        }

        private void ImmediateClose()
        {
            // Close the main window without waiting for clean disconnection.
            CloseImmediately = true;
            Dispatcher.BeginInvoke(new Action(() => Close()));
        }

        private async Task DisconnectSession(VncViewerSession viewerSession, int timeoutMs = 5000)
        {
            // Tell the viewer session to disconnect gracefully.
            viewerSession.Disconnect();

            // Wait for the disconnect notification, a call to OnDisconnect().
            // (If the main window closes during this time, the work following
            // this "await" will never be scheduled).
            await Task.Delay(timeoutMs);

            // If the session is still running, stop it.
            if (ViewerSession == viewerSession)
                viewerSession.StopSession();

            // The session will now disconnect, if it has not done so already.
        }

        private void ButtonConnect_Click(object sender, RoutedEventArgs e)
        {
            // If we have no hard-coded settings then ask user for confirmation
            if (new ConnectSettingsWindow(ConnectSettings) { Owner = this }.ShowDialog() != true)
                return;

            StartConnection();
        }

        private void StartConnection()
        {
            VncViewerSession viewerSession;
            try
            {
                ButtonConnect.IsEnabled = false;

                DisplayMessage("Connecting...");

                StartAnnotation.IsChecked = false; // Default to off
                KeyboardControl.IsChecked = true; // So we can input code

                // Now start the connection
                viewerSession = new VncViewerSession
                {
                    LocalCloudAddress = ConnectSettings.LocalCloudAddress,
                    LocalCloudPassword = ConnectSettings.LocalCloudPassword,
                    PeerCloudAddress = ConnectSettings.PeerCloudAddress,
                    TcpAddress = ConnectSettings.DirectTcpIpAddress,
                    TcpPort = ConnectSettings.DirectTcpPort,
                    UsingCloud = ConnectSettings.UsingCloud,

                    FrameBufferHandler = VncViewerControl,

                    OnConnect = () => DisplayMessage("Connected"),
                    OnDisconnect = (msg, flags) =>
                        Dispatcher.BeginInvoke(new Action(() => OnDisconnect(msg))),

                    // Put status messages on the status-label
                    OnNewStatus = (msg) => DisplayMessage(msg),

                    CurrentCanvasSize = VncViewerControl.Size
                };

                EventMap = new VncWinformEventMap(viewerSession, VncViewerControl);

                // Give the viewer session user-input events
                if (KeyboardControl.IsChecked == true)
                    EventMap.RegisterKeyboardControls(true);

                if (MouseControl.IsChecked == true)
                    EventMap.RegisterMouseControls(true);

                ManageConnectControls(true);

                // Give the child-control the focus of keyboard
                VncViewerControl.Focus();
            }
            catch (Exception ex)
            {
                OnDisconnect(ex.Message);
                return;
            }

            // Start this viewer session on the library thread.
            VncLibraryThread.StartViewerSession(viewerSession);
            ViewerSession = viewerSession;
        }

        private void OnDisconnect(string disconnectMessage = null)
        {
            // This method is called at the end of every viewer session.

            ViewerSession = null;

            if (EventMap != null)
            {
                EventMap.RegisterKeyboardControls(false);
                EventMap.RegisterMouseControls(false);
                EventMap = null;
            }

            if (string.IsNullOrEmpty(disconnectMessage))
                disconnectMessage = "Disconnected";

            DisplayMessage(disconnectMessage);

            ManageConnectControls(false);

            // If we are closing the main window, continue to do so.
            if (IsClosing)
                Close();
        }

        private async void ButtonDisconnect_Click(object sender, RoutedEventArgs e)
        {
            ButtonDisconnect.IsEnabled = false;

            DisplayMessage("Disconnecting...");

            // Disconnect the viewer session within the next few seconds.
            await DisconnectSession(ViewerSession);
        }

        private void KeyboardControl_Checked(object sender, RoutedEventArgs e)
        {
            EventMap?.RegisterKeyboardControls(KeyboardControl.IsChecked == true);
        }

        private void MouseControl_Checked(object sender, RoutedEventArgs e)
        {
            EventMap?.RegisterMouseControls(MouseControl.IsChecked == true);
        }

        private void ManageConnectControls(bool connected)
        {
            ButtonConnect.Visibility = connected ? Visibility.Collapsed : Visibility.Visible;
            ButtonDisconnect.Visibility = connected ? Visibility.Visible : Visibility.Collapsed;

            ButtonDisconnect.IsEnabled = ButtonConnect.IsEnabled = true;

            UpdateLayout();
        }

        private void DisplayMessage(string v, bool asTitle = false)
        {
            // Dispatch to the GUI thread
            Dispatcher.BeginInvoke(new Action(() =>
            {
                if (asTitle)
                    Title = v;
                else
                    MyLabel.Content = v;
            }));
        }

        private void StartAnnotation_Checked(object sender, RoutedEventArgs e)
        {
            if (StartAnnotation.IsChecked == true)
                MouseControl.IsChecked = true;

            StartAnnotationWithOurSettings();
        }

        private void StartAnnotationWithOurSettings()
        {
            ViewerSession?.ChangeAnnotation(
                StartAnnotation.IsChecked == true,
                (int)AnnotationLine.StrokeThickness,
                CurrentAnnotationColour,
                CurrentAnnotationDuration*1000);
        }

        private void ClearAnnotation_Click(object sender, RoutedEventArgs e)
        {
            ViewerSession?.ClearAnnotation();
        }

        private List<Tuple<string, Color>> AnnotationColours = new List<Tuple<string, Color>> {
            new Tuple<string, Color>("Green", Color.FromArgb(0xff,0,0xff,0)),
            new Tuple<string, Color>("Blue", Color.FromArgb(0xff,0,0x80,0xff)),
            new Tuple<string, Color>("Red", Color.FromArgb(0xff,0xff,0x00,0x00)),
            new Tuple<string, Color>("Yellow", Color.FromArgb(0xff,0xff,0xff,0x00)),
            new Tuple<string, Color>("White", Color.FromArgb(0xff,0xff,0xff,0xff)),
        };

        private int CurrentColourIndex = 0;
        public Color CurrentAnnotationColour {  get { return AnnotationColours[CurrentColourIndex].Item2; } }

        private void AnnotationColour_Click(object sender, RoutedEventArgs e)
        {
            CurrentColourIndex = (CurrentColourIndex + 1) % AnnotationColours.Count();

            RefreshAnnotationColour();
            StartAnnotationWithOurSettings();
        }

        private void RefreshAnnotationColour()
        {
            var Brush = new SolidColorBrush(CurrentAnnotationColour);
            AnnotationLine.Stroke = Brush;
            AnnotationColour.Stroke = Brush;
            AnnotationColour.Fill = Brush;
        }

        private void AnnotationThickeness_Click(object sender, RoutedEventArgs e)
        {
            var newThickness = (AnnotationLine.StrokeThickness * 1.5);
            if (newThickness > 30)
                newThickness = 2;

            AnnotationLine.StrokeThickness = newThickness;

            StartAnnotationWithOurSettings();
        }

        private int CurrentAnnotationDuration { get { return Durations[AnnotationDurationIx]; } }
        private int AnnotationDurationIx = 2;
        private List<int> Durations = new List<int> { 1, 2, 5, 10, 30, 60 };

        private void AnnotationDuration_Click(object sender, RoutedEventArgs e)
        {
            AnnotationDurationIx = (AnnotationDurationIx + 1) % Durations.Count();

            RefreshAnnotationDuration();

            StartAnnotationWithOurSettings();
        }

        private void RefreshAnnotationDuration()
        {
            AnnotationDurationText.Text = $"Duration: {CurrentAnnotationDuration}sec";
        }
    }
}
