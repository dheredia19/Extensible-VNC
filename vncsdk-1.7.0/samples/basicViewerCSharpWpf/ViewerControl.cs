using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Drawing;
using System.Data;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;
using System.Windows;
using System.Runtime.InteropServices;

/// <summary>
/// ViewerControl is a winforms control for the remote screen to be painted onto.
/// This is used in WPF projects too, as only winforms controls have a Paint override
/// allowing us to invalidate and paint only the altered regions from the server.
/// </summary>

namespace BasicViewerCSharpWpf.WinFormsControls
{
    // Implement the control as a winforms control so we have access over the painting regions
    // and paint callbacks.
    public partial class ViewerControl : UserControl, IVncFramebufferCallback, IDisposable
    {
        BufferHolder bufferHolder = new BufferHolder();
        object bufferLock = new object();
        bool BeBlank = true;

        public ViewerControl()
        {
            InitializeComponent();

            // Do our own painting of this control
            Paint += ViewerControl_Paint;

            // Prevent flickering during the paint operation
            DoubleBuffered = true;

            Dock = DockStyle.Fill;
        }


        /// <summary>
        /// Implementation of the IVncFramebufferCallback interface.
        /// </summary>
        public void OnFrameBufferResized(int width, int height, int stride, byte[] buffer, bool resizeWindow)
        {
            lock (bufferLock)
            {
                if (bufferHolder != null)
                {
                    if (buffer != null)
                    {
                        bufferHolder.ResizeBuffer(width, height, stride, buffer);
                        BeBlank = false;
                    }
                    else
                    {
                        BeBlank = true;
                    }

                    // And redraw
                    BeginInvoke(new Action(() => { Invalidate(); }));
                }
            }

            if (resizeWindow)
            {
                // Here we can respond to the engine's request to change the size of the containing window
                // As this is a child control the parent needs to handle this request, either control it directly
                // or change which window implements the IVncFramebufferCallback interface and pass the relevant calls
                // down to this window.
            }
        }

        /// <summary>
        /// This is called after the buffer (BufferHolder) has been updated with new image data from the server.
        /// This is called to request a repaint of the updated region
        /// </summary>
        public void OnFrameBufferUpdated(Rect rc)
        {
            // Invalidate on the GUI thread
            BeginInvoke(new Action(() =>
            {
                Invalidate(new Rectangle((int)rc.Left, (int)rc.Top, (int)rc.Width, (int)rc.Height));
                Update();
            }));
        }

        /// <summary>
        /// Override the painting of this control
        /// </summary>
        private void ViewerControl_Paint(object sender, PaintEventArgs e)
        {
            lock (bufferLock)
            {
                if (bufferHolder != null && bufferHolder.IsValid && !BeBlank)
                {
                    int x = e.ClipRectangle.Left,
                        y = e.ClipRectangle.Top;

                    // Draw the invalidated (i.e. changed) part of the image from the canvas to the control
                    e.Graphics.DrawImage(bufferHolder.Canvas, x, y, e.ClipRectangle, GraphicsUnit.Pixel);

                    // This line would instead copy the whole canvas/image to the control every time there's a change
                    // e.Graphics.DrawImage(bufferHolder.Canvas, 0, 0, bufferHolder.Canvas.Width, bufferHolder.Canvas.Height);
                }
            }
        }

        /// <summary>
        /// Clean up any resources being used.
        /// </summary>
        /// <param name="disposing">true if managed resources should be disposed; otherwise, false.</param>
        protected override void Dispose(bool disposing)
        {
            if (disposing)
            {
                if (components != null)
                {
                    components.Dispose();
                }

                lock (bufferLock)
                {
                    if (bufferHolder != null)
                    {
                        bufferHolder.Dispose();
                        bufferHolder = null;
                    }
                }
            }

            base.Dispose(disposing);
        }
    }

    /// <summary>
    /// Our buffer container that looks after the low-level memory and resizing of the buffer
    /// </summary>
    public class BufferHolder : IDisposable
    {
        public byte[] Buffer { get; private set; }
        public Bitmap Canvas { get; private set; }

        private GCHandle PinnedBuffer;

        public void ResizeBuffer(int width, int height, int stride, byte[] buffer)
        {
            this.Buffer = buffer;
            if (PinnedBuffer.IsAllocated)
            {
                PinnedBuffer.Free();
            }
            PinnedBuffer = GCHandle.Alloc(buffer, GCHandleType.Pinned);
            IntPtr pointer = PinnedBuffer.AddrOfPinnedObject();

            var pixelFormat = System.Drawing.Imaging.PixelFormat.Format32bppRgb;

            // Create the canvas bitmap using the pointer provided from the SDK
            Canvas = new Bitmap(width, height, stride * 4, pixelFormat, pointer);
        }

        public bool IsValid => Canvas != null;

        public void Dispose()
        {
            Dispose(true);
            GC.SuppressFinalize(this);
        }

        protected virtual void Dispose(bool disposing)
        {
            if (!disposing)
                return;

            if (Canvas != null)
            {
                Canvas.Dispose();
                Canvas = null;
            }

            if (PinnedBuffer.IsAllocated)
            {
                PinnedBuffer.Free();
            }
        }
    }
}
