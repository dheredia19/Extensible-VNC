using System.Windows;

namespace BasicViewerCSharpWpf
{
    /// <summary>
    /// Interaction logic for ConnectSettings.xaml
    /// </summary>
    public partial class ConnectSettingsWindow : Window
    {
        public ConnectSettingsWindow(ConnectSettings settings)
        {
            InitializeComponent();

            ConSettings = settings;
            DataContext = ConSettings;
        }

        public ConnectSettings ConSettings { get; private set; }

        private void ButtonConnect_Click(object sender, RoutedEventArgs e)
        {
            // Remember which tab we're on - does user want to cloud or port (if the settings don't infer it)
            ConSettings.UsingCloud = ConnectionTabControl.SelectedIndex != 1;

            DialogResult = true;
        }
    }
}
