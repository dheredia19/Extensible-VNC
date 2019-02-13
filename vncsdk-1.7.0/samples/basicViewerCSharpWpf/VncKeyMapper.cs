using RealVNC.VncSdk;
using System.Collections.Generic;
using System.Windows.Forms;

namespace BasicViewerCSharpWpf
{
    class VncKeyMapper
    {
        // Singleton
        public static VncKeyMapper Current = new VncKeyMapper();

        // A mapping between the non-printable keys and the SDK keysyms
        // This is used by the keyboard handlers.
        public readonly Dictionary<Keys, int> KeyMap = new Dictionary<Keys, int>
        {
            {Keys.Escape, Keyboard.XK_Escape},
            {Keys.Return, Keyboard.XK_Return},
            {Keys.Insert, Keyboard.XK_KP_Insert},
            {Keys.Delete, Keyboard.XK_Delete},
            {Keys.Pause, Keyboard.XK_Pause},
            {Keys.Print, Keyboard.XK_Print},
            //There is no SysReq key in the Keys enumeration!
            // {Keys.SysReq, Keyboard.XK_Sys_Req},
            {Keys.Home, Keyboard.XK_Home},
            {Keys.End, Keyboard.XK_End},
            {Keys.Left, Keyboard.XK_Left},
            {Keys.Up, Keyboard.XK_Up},
            {Keys.Right, Keyboard.XK_Right},
            {Keys.Down, Keyboard.XK_Down},
            {Keys.PageUp, Keyboard.XK_Page_Up},
            {Keys.PageDown, Keyboard.XK_Page_Down},
            {Keys.Shift, Keyboard.XK_Shift_L},
            {Keys.Alt, Keyboard.XK_Alt_L},
            {Keys.Menu, Keyboard.XK_Alt_L},
            {Keys.LMenu, Keyboard.XK_Alt_L},
            {Keys.RMenu, Keyboard.XK_Alt_R},
            {Keys.F1, Keyboard.XK_F1},
            {Keys.F2, Keyboard.XK_F2},
            {Keys.F3, Keyboard.XK_F3},
            {Keys.F4, Keyboard.XK_F4},
            {Keys.F5, Keyboard.XK_F5},
            {Keys.F6, Keyboard.XK_F6},
            {Keys.F7, Keyboard.XK_F7},
            {Keys.F8, Keyboard.XK_F8},
            {Keys.F9, Keyboard.XK_F9},
            {Keys.F10, Keyboard.XK_F10},
            {Keys.F11, Keyboard.XK_F11},
            {Keys.F12, Keyboard.XK_F12}
        };

        public Keys ctrlModifier { get; private set; }

        public VncKeyMapper()
        {
            if (!KeyMap.ContainsKey(Keys.Enter))
                KeyMap.Add(Keys.Enter, Keyboard.XK_KP_Enter);

            ctrlModifier = Keys.None;

            KeyMap.Add(Keys.ControlKey, Keyboard.XK_Control_L);
            ctrlModifier = Keys.Control;
        }
    }
}
