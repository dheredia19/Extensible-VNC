using RealVNC.VncSdk;
using System;
using System.Collections.Generic;
using System.Windows.Forms;

namespace BasicViewerCSharpWpf
{
    public class VncWinformEventMap
    {
        private readonly VncViewerSession ViewerSession;
        public Control VncViewerControl { get; private set; }

        private Keys lastModifiers;

        public VncWinformEventMap(VncViewerSession viewerSession, Control control)
        {
            ViewerSession = viewerSession;
            VncViewerControl = control;

            // And also monitor its dimensions
            VncViewerControl.Resize += this.ResizeCapture;
        }

        public void RegisterKeyboardControls(bool register)
        {
            if (register)
            {
                VncViewerControl.PreviewKeyDown += this.PreviewKeyDownCapture;
                VncViewerControl.KeyDown += this.KeyDownCapture;
                VncViewerControl.KeyPress += this.KeyPressCapture;
                VncViewerControl.KeyUp += this.KeyUpCapture;
            }
            else
            {
                VncViewerControl.PreviewKeyDown -= this.PreviewKeyDownCapture;
                VncViewerControl.KeyDown -= this.KeyDownCapture;
                VncViewerControl.KeyPress -= this.KeyPressCapture;
                VncViewerControl.KeyUp -= this.KeyUpCapture;
            }
        }

        public void RegisterMouseControls(bool register)
        {
            if (register)
            {
                VncViewerControl.MouseMove += this.MouseMoveCapture;
                VncViewerControl.MouseUp += this.MouseUpCapture;
                VncViewerControl.MouseDown += this.MouseDownCapture;
                VncViewerControl.MouseWheel += this.MouseWheelCapture;
            }
            else
            {
                VncViewerControl.MouseMove -= this.MouseMoveCapture;
                VncViewerControl.MouseUp -= this.MouseUpCapture;
                VncViewerControl.MouseDown -= this.MouseDownCapture;
                VncViewerControl.MouseWheel -= this.MouseWheelCapture;
            }
        }


        public void ResizeCapture(object sender, EventArgs e)
        {
            var size = new System.Drawing.Size();

            // Get underlying control size (client/drawing area of it)
            if (sender is Control)
                size = (sender as Control).ClientSize;
            // else if (sender is Window) etc

            if (!size.IsEmpty)
                ViewerSession.ResizeFrameBuffer(size);
        }


        public void KeyPressCapture(object sender, KeyPressEventArgs e)
        {
            char ch = e.KeyChar;
            if (lastModifiers.HasFlag(VncKeyMapper.Current.ctrlModifier))
            {
                // Convert the control key-codes to their actual letters
                if (e.KeyChar < (int)' ')
                    ch = (char)((int)ch + (int)'a' - 1);
            }

            int keysym = Convert.ToInt32(ch);
            keysym = Library.UnicodeToKeysym(keysym);

            // Send to the keypress to the event loop thread to process in turn
            ViewerSession.SendKeyDown(keysym, ch);
        }

        public void PreviewKeyDownCapture(object sender, PreviewKeyDownEventArgs e)
        {
            // Mark every key-press as a standard input that we want to look at (i.e. send it to KeyDownCapture)
            e.IsInputKey = true;
        }

        public void KeyDownCapture(object sender, KeyEventArgs e)
        {
            lastModifiers = e.Modifiers;

            // Try first to send the keycode as a keysym directly, to handle non-
            // printing keycodes, which don't have associated Unicode text.
            int keySym;
            if (VncKeyMapper.Current.KeyMap.TryGetValue(e.KeyCode, out keySym))
            {
                ViewerSession.SendKeyDown(keySym, e.KeyValue);
            }
        }

        public void KeyUpCapture(object sender, KeyEventArgs e)
        {
            ViewerSession.SendKeyUp(Convert.ToInt32(e.KeyCode));
        }

        public void MouseMoveCapture(object sender, MouseEventArgs e)
        {
            HandleMouseEvent(sender, e);
        }

        public void MouseDownCapture(object sender, MouseEventArgs e)
        {
            HandleMouseEvent(sender, e);
        }

        public void MouseUpCapture(object sender, MouseEventArgs e)
        {
            HandleMouseEvent(sender, e);
        }

        public void MouseWheelCapture(object sender, MouseEventArgs e)
        {
            int delta = e.Delta;

            // Only send the source event: a 1 or -1
            // The Server machine will have its own wheel settings implemented, we need to send the source request
            delta = Math.Sign(delta);

            // Change the sign (this could be machine dependent?)
            delta = -delta;

            ViewerSession.SendScrollEvent(delta, Viewer.MouseWheel.Vertical);
        }


        private static Dictionary<MouseButtons, Viewer.MouseButton> MouseMap = new Dictionary<MouseButtons, Viewer.MouseButton>
        {
            { MouseButtons.Left, Viewer.MouseButton.Left },
            { MouseButtons.Right, Viewer.MouseButton.Right },
            { MouseButtons.Middle, Viewer.MouseButton.Middle }
        };


        private void HandleMouseEvent(object sender, MouseEventArgs e)
        {
            if (ViewerSession.AnnotationEnabled)
            {
                ViewerSession.MovePenTo(e.X, e.Y, e.Button.HasFlag(MouseButtons.Left));
            }
            else
            {
                Viewer.MouseButton button = Viewer.MouseButton.Zero;
                foreach (var item in MouseMap)
                {
                    if (e.Button.HasFlag(item.Key))
                        button |= item.Value;
                }

                ViewerSession.SendPointerEvent(e.X, e.Y, button, false);
            }
        }
    }
}
