# Copyright (C) 2016 RealVNC Limited. All rights reserved.
from datetime import datetime
import atexit, os, sys, threading

_PYTHON3 = sys.version_info >= (3, 0)

if _PYTHON3:
  import queue
  try:
    callable(None)
  except NameError:
    # For some annoying reason, they took the callable() builtin out in Python
    # 3.0, but it's very hard to get exactly-correct behaviour without it.
    # Thankfully, it's back in 3.2, so we go with collections.Callable to cover
    # 3.0 and 3.1 (this is what Python's 2to3 tool uses as the replacement for
    # callable(), so I think it ought to be a usable replacement).
    callable = lambda fn: isinstance(fn, collections.Callable)
else:
  import Queue as queue

class DestroyedObjectException(Exception):
  def __init__(self):
    Exception.__init__(self, "Illegal method call after destroy()")

class VncException(Exception):
  def __init__(self, errorCode, callingFunction, detail=''):
    if detail: detail = ' (%s)' % detail
    Exception.__init__(self, "Error in %s: %s%s" %
                             (callingFunction, errorCode, detail))
    self.errorCode = errorCode

# Lookup table mapping native pointers (integers) to Python objects
_global_native_pointer_lookup = {}

# If we can't find a function via ctypes, we use _unavailable_function to
# create a suitable replacement which simply throws.
def _unavailable_function(name):
  @staticmethod
  def unavailable(*args):
    raise NameError('"%s" is not supported on the current platform' % (name,))
  return unavailable

def _wrap_sdk_function(dll, name, argtypes, restype):
  try:
    func = dll[name]
    func.argtypes = argtypes
    func.restype = restype
    return func
  except AttributeError:
    return _unavailable_function(name)

# Factory for SDK enum objects, which creates an object with similar usage to
# Python 3.4's enum.Enum.
def _create_enum(name, docstring, **values):
  enumerated = {}
  reverse_mapping = {}
  for k, v in values.items():
    klass = type('%s.%s' % (name, k), (object,), {'name': k, 'value': v})
    klass.__repr__ = lambda self: "<%s.%s: %d>" % (name, self.name, self.value)
    instance = klass()
    enumerated[k] = instance
    reverse_mapping[v] = instance
  enum = type(name, (object,), dict(enumerated, __doc__=docstring))
  enum.members = staticmethod(lambda: enumerated.values())
  enum.__new__ = staticmethod(lambda cls, v: reverse_mapping[v])
  return enum

# Convert the bits of n to a set of instances of enum_class.
# Ignores unexpected bits.
def _int_to_enums(n, enum_class):
  vals = [x.value for x in enum_class.members()]
  bits = [x for x in vals if x and x & (x-1) == 0]
  return set(enum_class(bit) for bit in bits if n & bit)

# Convert a set of Enum instances to an int.
def _enums_to_int(enums):
  rv = 0
  for e in enums:
    rv |= e.value
  return rv

# Convert Python string to SDK string (UTF-8 bytes)
def _encode_unicode(string, allowNone=False):
  if string is None and allowNone:
    return None

  if _PYTHON3:
    if isinstance(string, str):
      return string.encode("utf-8")
    elif isinstance(string, bytes):
      return string
    else:
      raise TypeError("expected string or bytes, got {type}".format(type=type(string)))
  else:
    if isinstance(string, str):
      return string
    elif isinstance(string, unicode):
      return string.encode("utf-8")
    else:
      raise TypeError("expected string or unicode, got {type}".format(type=type(string)))

# Convert SDK string (UTF-8 bytes) to Python string
def _decode_unicode(bytes):
  return bytes.decode("utf-8") if _PYTHON3 else bytes

# Unguarded import, the SDK wrapper requires ctypes.
import ctypes as _CT
import ctypes.util

# Locate a file in the SDK's default directory structure (locates the SDK library
# if filename is None)
def _find_binary(path, filename):
  sdk_lib_name = None
  sdk_exe_suffix = ''
  sdk_dir_name = None
  if sys.platform == 'win32' or sys.platform == 'cygwin':
    sdk_exe_suffix = '.exe'
    sdk_lib_name = 'vncsdk.dll'
    sdk_dir_name = 'win-x64' if _CT.sizeof(_CT.c_void_p) == 8 else 'win-x86'
  elif sys.platform == 'darwin' and _CT.sizeof(_CT.c_void_p) == 8:
    sdk_lib_name = "libvncsdk.{major}.{minor}.dylib".format(
      major=1,
      minor=7
    )
    sdk_dir_name = 'mac-x64'
  elif 'linux' in sys.platform:
    sdk_lib_name = "libvncsdk.so.{major}.{minor}".format(
      major=1,
      minor=7
    )
    sdk_dir_name = 'linux-armhf-raspi' if 'arm' in os.uname()[4] else \
                   'linux-x64' if _CT.sizeof(_CT.c_void_p) == 8 else \
                   'linux-x86'
  else:
    raise Exception("could not determine the default directory name for this platform")
  if filename is None:
    filename = sdk_lib_name
  else:
    filename = filename + sdk_exe_suffix
  sdk_path_pref_dir = os.path.join(path, filename)
  sdk_path_pref_dir2 = os.path.join(path, sdk_dir_name, filename)
  if os.path.exists(sdk_path_pref_dir):
    return sdk_path_pref_dir
  if os.path.exists(sdk_path_pref_dir2):
    return sdk_path_pref_dir2
  raise Exception("could not find the SDK binary {dir} or {dir2}".format(
    dir=sdk_path_pref_dir,
    dir2=sdk_path_pref_dir2
  ))

# Finds the path to the SDK library for the current platform
def _find_library():
  sdk_path_pref = None
  try:
    sdk_path_pref = os.path.abspath(os.environ['VNCSDK_LIBRARY'])
  except KeyError:
    sdk_path_auto = ctypes.util.find_library('vncsdk')
    if not sdk_path_auto:
      raise ImportError("could not find the SDK shared object: place it in the system path or set the VNCSDK_LIBRARY environment variable to point to it")
    return sdk_path_auto

  if not os.path.exists(sdk_path_pref):
    raise ImportError("could not find the SDK shared object: VNCSDK_LIBRARY is not a file or directory")

  if not os.path.isdir(sdk_path_pref):
    return sdk_path_pref

  try:
    return _find_binary(sdk_path_pref, None)
  except Exception as e:
    raise ImportError(str(e))

class SdkDll():
  ''' This class loads & unloads the sdk dll
      It is responsible for binding the functions in the dll
      as well as trying to force the unloading of the dll.
  '''
  instance = None
  nativeFunctionsToWrap = {}
  
  @classmethod
  def get_instance(clazz):
    if clazz.instance is None:
      clazz.instance = SdkDll(_find_library())
    return clazz.instance
    
  @classmethod
  def has_instance(clazz):
    return clazz.instance is not None
    
  @classmethod
  def unload_instance(clazz):
    clazz.instance = None

  @classmethod
  def register_class_function(clazz, name, *args):
    clazz.nativeFunctionsToWrap[name] = args
    def wrapper(*args, **kargs):
      return SdkDll.get_instance().get_function(name)(*args, **kargs)
    return staticmethod(wrapper)
  
  @classmethod
  def register_floating_function(clazz, name, *args):
    clazz.nativeFunctionsToWrap[name] = args
    def wrapper(*args, **kargs):
      return SdkDll.get_instance().get_function(name)(*args, **kargs)
    return wrapper

  def get_function(self, name):
    return getattr(self, name)
  
  def __init__(self, location):
    self.dllInstance = ctypes.cdll[location]
    for m, args in self.nativeFunctionsToWrap.items():
      wrapped = _wrap_sdk_function(self.dllInstance, m, *args)
      setattr(self, m, wrapped)
  
def init(eventLoopType = None):
  '''Initializes the SDK with the default vnc_EventLoopType for the platform.'''
  if   get_major_version() != 1\
    or get_minor_version() != 7\
    or get_patch_version() != 0\
    or get_build_number () != 37830:
    e = VncException("VersionError", "init()")
    _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', str(e))
    raise e
  init_internal(\
    1,\
    7,\
    0,\
    37830,\
    eventLoopType if eventLoopType else EventLoopType.DEFAULT)

def _throwVncException(callingFunction):
  ex = get_last_error()
  raise VncException(ex if ex else "Unknown", callingFunction)

class ConnectionHandler(object):
  '''Opaque type for a connection handler, enabling a Viewer or Server to perform
  a connection operation.
  '''
  def __init__(self):
    raise UserWarning("constructing an abstract class")

class Connection(object):
  '''Opaque type for a connection, identifying a Viewer connected to a Server.'''
  def __init__(self, nativePtr):
    self._nativePtr = nativePtr
    _global_native_pointer_lookup[nativePtr] = self
  def _getNativePtr(self):
    return self._nativePtr
  def _setNativePtr(self, v):
    self._nativePtr = v
  def __hash__(self):
    return int(self._getNativePtr())
  def __eq__(self, other):
    return (isinstance(other, self.__class__)
      and self._getNativePtr() == other._getNativePtr())

def shutdown():
  '''Shuts down the SDK, ensuring that any resources are cleared up.
  '''
  if SdkDll.has_instance():
    rv = __nativeShutdown()
    if rv == 0: _throwVncException("Library.shutdown()")
    SdkDll.unload_instance()

EventLoopType = _create_enum("EventLoopType",
  '''Enumeration of types of event loop used by the SDK.''',
  DEFAULT = 0,
  WIN = 1,
  FD = 2,
  CF = 3,
  ANDROID = 4,
)

def enable_add_on(add_on_code):
  '''Enable an SDK add-on by passing in the content of the add-on code,
  obtained from RealVNC.
  '''
  add_on_code = _encode_unicode(add_on_code, False)
  rv = __nativeEnableAddOn(add_on_code)
  if rv == 0: _throwVncException("Library.enable_add_on()")

def get_build_number():
  '''Returns the runtime build number of the SDK.
  '''
  rv = __nativeGetBuildNumber()
  return rv

def get_last_error():
  '''Gets the error produced by the last API call.
  '''
  rv = __nativeGetLastError()
  return _decode_unicode(rv) if rv is not None else rv

def get_major_version():
  '''Returns the runtime major version number of the SDK.
  '''
  rv = __nativeGetMajorVersion()
  return rv

def get_minor_version():
  '''Returns the runtime minor version number of the SDK.
  '''
  rv = __nativeGetMinorVersion()
  return rv

def get_patch_version():
  '''Returns the runtime patch version number of the SDK.
  '''
  rv = __nativeGetPatchVersion()
  return rv

def init_internal(major_version, minor_version, patch_version, build_number, event_loop_type):
  '''@internal
  This should not be called directly, instead the init() macro should be
  used.
  '''
  rv = __nativeInitInternal(major_version, minor_version, patch_version, build_number, event_loop_type.value)
  if rv == 0: _throwVncException("Library.init_internal()")

def set_cloud_proxy_settings(system_proxy, proxy_url):
  '''Specifies proxy server settings for Cloud connections; note these settings
  are adopted for all subsequent outgoing Cloud connections.
  '''
  proxy_url = _encode_unicode(proxy_url, True)
  rv = __nativeSetCloudProxySettings(bool(system_proxy), proxy_url)
  if rv == 0: _throwVncException("Library.set_cloud_proxy_settings()")

def unicode_to_keysym(unicode_char):
  '''Converts a unicode character to a keysym, suitable for passing to
  Viewer.sendKeyDown.
  '''
  if unicode_char < 0 or unicode_char > 0x7fffffff:
    raise IndexError("unicode_char out of bounds")

  rv = __nativeUnicodeToKeysym(unicode_char)
  return rv

__nativeEnableAddOn = SdkDll.register_floating_function('vnc_enableAddOn', [_CT.c_char_p], _CT.c_int)
__nativeGetBuildNumber = SdkDll.register_floating_function('vnc_getBuildNumber', [], _CT.c_int)
__nativeGetLastError = SdkDll.register_floating_function('vnc_getLastError', [], _CT.c_char_p)
__nativeGetMajorVersion = SdkDll.register_floating_function('vnc_getMajorVersion', [], _CT.c_int)
__nativeGetMinorVersion = SdkDll.register_floating_function('vnc_getMinorVersion', [], _CT.c_int)
__nativeGetPatchVersion = SdkDll.register_floating_function('vnc_getPatchVersion', [], _CT.c_int)
__nativeInitInternal = SdkDll.register_floating_function('vnc_initInternal', [_CT.c_int, _CT.c_int, _CT.c_int, _CT.c_int, _CT.c_int], _CT.c_int)
__nativeSetCloudProxySettings = SdkDll.register_floating_function('vnc_setCloudProxySettings', [_CT.c_int, _CT.c_char_p], _CT.c_int)
__nativeShutdown = SdkDll.register_floating_function('vnc_shutdown', [], _CT.c_int)
__nativeUnicodeToKeysym = SdkDll.register_floating_function('vnc_unicodeToKeysym', [_CT.c_uint], _CT.c_uint)

class AnnotationManager(object):
  '''Enables a Viewer or Server to annotate a Server device screen.
  '''
  class Callback(object):
    class CallbackImpl(_CT.Structure):
      _fields_ = [
        ("availabilityChanged", _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_int)),
      ]

    def __init__(self, availability_changed=None):
      if availability_changed is not None:
        self.availability_changed = availability_changed

      if self.availability_changed is not None and not callable(self.availability_changed):
        raise TypeError('availability_changed: callbacks must be callable')

      def _availability_changed(_, annotation_manager, is_available):
        is_available = bool(is_available)
        try:
          rv = self.availability_changed(_global_native_pointer_lookup[annotation_manager], is_available)
          assert rv is None
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback availabilityChanged generated an uncaught exception: \'%s\'' % e)
          return None

      self._annotationmanager_callback_callback = AnnotationManager.Callback.CallbackImpl(
        _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_int)(_availability_changed if self.availability_changed else 0),
      )
      _global_native_pointer_lookup[_CT.addressof(self._annotationmanager_callback_callback)] = self

    availability_changed = None

  def clear(self, fade, connection):
    '''Clears particular annotations.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    if connection is None:
      connection_ = None
    else:
      connection_ = connection._getNativePtr()
      if not connection_: raise DestroyedObjectException()
    rv = self.__nativeClear(self._getNativePtr(), bool(fade), connection_)
    if rv == 0: _throwVncException("AnnotationManager.clear()")

  def clear_all(self, fade):
    '''Clears all annotations.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeClearAll(self._getNativePtr(), bool(fade))
    assert rv is None

  def get_fade_duration(self):
    '''Gets how long annotations take to fade.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeGetFadeDuration(self._getNativePtr())
    return rv

  def get_pen_color(self):
    '''Gets the current pen color.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeGetPenColor(self._getNativePtr())
    return rv

  def get_pen_size(self):
    '''Gets the current pen size.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeGetPenSize(self._getNativePtr())
    return rv

  def get_persist_duration(self):
    '''Gets how long annotations persist as a solid color for.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeGetPersistDuration(self._getNativePtr())
    return rv

  def is_available(self):
    '''Queries whether it is possible to annotate.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeIsAvailable(self._getNativePtr())
    return bool(rv)

  def move_pen_to(self, x, y, pen_down):
    '''Draws a line on the Server screen from the current position to a
    new position.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeMovePenTo(self._getNativePtr(), x, y, bool(pen_down))
    if rv == 0: _throwVncException("AnnotationManager.move_pen_to()")

  def set_callback(self, callback):
    '''Sets annotation-related callbacks.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    callback_ = _CT.pointer(callback._annotationmanager_callback_callback) if callback is not None else None
    rv = self.__nativeSetCallback(self._getNativePtr(), callback_, callback_)
    if rv == 0: _throwVncException("AnnotationManager.set_callback()")

  def set_fade_duration(self, duration_ms):
    '''Sets how long annotations take to fade.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeSetFadeDuration(self._getNativePtr(), duration_ms)
    assert rv is None

  def set_pen_color(self, color):
    '''Sets the pen color, determining the color of the annotation line.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    if color < 0 or color > 0xffffffff:
      raise IndexError("color out of bounds")

    rv = self.__nativeSetPenColor(self._getNativePtr(), color)
    assert rv is None

  def set_pen_size(self, size):
    '''Sets the pen size, determining the width of the annotation line.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    if size < 0 or size > 0x7fffffff:
      raise IndexError("size out of bounds")

    rv = self.__nativeSetPenSize(self._getNativePtr(), size)
    assert rv is None

  def set_persist_duration(self, duration_ms):
    '''Sets how long annotations persist as a solid color for.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeSetPersistDuration(self._getNativePtr(), duration_ms)
    assert rv is None

  __nativeClear = SdkDll.register_class_function('vnc_AnnotationManager_clear', [_CT.c_void_p, _CT.c_int, _CT.c_void_p], _CT.c_int)
  __nativeClearAll = SdkDll.register_class_function('vnc_AnnotationManager_clearAll', [_CT.c_void_p, _CT.c_int], None)
  __nativeGetFadeDuration = SdkDll.register_class_function('vnc_AnnotationManager_getFadeDuration', [_CT.c_void_p], _CT.c_int)
  __nativeGetPenColor = SdkDll.register_class_function('vnc_AnnotationManager_getPenColor', [_CT.c_void_p], _CT.c_uint)
  __nativeGetPenSize = SdkDll.register_class_function('vnc_AnnotationManager_getPenSize', [_CT.c_void_p], _CT.c_uint)
  __nativeGetPersistDuration = SdkDll.register_class_function('vnc_AnnotationManager_getPersistDuration', [_CT.c_void_p], _CT.c_int)
  __nativeIsAvailable = SdkDll.register_class_function('vnc_AnnotationManager_isAvailable', [_CT.c_void_p], _CT.c_int)
  __nativeMovePenTo = SdkDll.register_class_function('vnc_AnnotationManager_movePenTo', [_CT.c_void_p, _CT.c_int, _CT.c_int, _CT.c_int], _CT.c_int)
  __nativeSetCallback = SdkDll.register_class_function('vnc_AnnotationManager_setCallback', [_CT.c_void_p, _CT.POINTER(Callback.CallbackImpl), _CT.c_void_p], _CT.c_int)
  __nativeSetFadeDuration = SdkDll.register_class_function('vnc_AnnotationManager_setFadeDuration', [_CT.c_void_p, _CT.c_int], None)
  __nativeSetPenColor = SdkDll.register_class_function('vnc_AnnotationManager_setPenColor', [_CT.c_void_p, _CT.c_uint], None)
  __nativeSetPenSize = SdkDll.register_class_function('vnc_AnnotationManager_setPenSize', [_CT.c_void_p, _CT.c_uint], None)
  __nativeSetPersistDuration = SdkDll.register_class_function('vnc_AnnotationManager_setPersistDuration', [_CT.c_void_p, _CT.c_int], None)
  def __init__(self):
    raise UserWarning("constructing static/abstract class")


class CloudAddressMonitor(object):
  '''Monitor used to query the availability of VNC Cloud addresses.
  '''
  Availability = _create_enum("CloudAddressMonitor.Availability",
    '''Enumeration of availabilities for a Cloud address.''',
    AVAILABLE = 0,
    UNAVAILABLE = 1,
    UNKNOWN_AVAILABILITY = 2,
  )

  class Callback(object):
    class CallbackImpl(_CT.Structure):
      _fields_ = [
        ("availabilityChanged", _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_char_p, _CT.c_int)),
        ("monitorPaused", _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p)),
      ]

    def __init__(self, availability_changed=None, monitor_paused=None):
      if availability_changed is not None:
        self.availability_changed = availability_changed

      if self.availability_changed is None:
        raise ValueError('availability_changed is a mandatory callback')
      elif not callable(self.availability_changed):
        raise TypeError('availability_changed: callbacks must be callable')

      def _availability_changed(_, monitor, cloud_address, availability):
        cloud_address = _decode_unicode(cloud_address) if cloud_address is not None else cloud_address
        availability = CloudAddressMonitor.Availability(availability)
        try:
          rv = self.availability_changed(_global_native_pointer_lookup[monitor], cloud_address, availability)
          assert rv is None
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback availabilityChanged generated an uncaught exception: \'%s\'' % e)
          return None

      if monitor_paused is not None:
        self.monitor_paused = monitor_paused

      if self.monitor_paused is not None and not callable(self.monitor_paused):
        raise TypeError('monitor_paused: callbacks must be callable')

      def _monitor_paused(_, monitor):
        try:
          rv = self.monitor_paused(_global_native_pointer_lookup[monitor])
          assert rv is None
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback monitorPaused generated an uncaught exception: \'%s\'' % e)
          return None

      self._cloudaddressmonitor_callback_callback = CloudAddressMonitor.Callback.CallbackImpl(
        _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_char_p, _CT.c_int)(_availability_changed if self.availability_changed else 0),
        _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p)(_monitor_paused if self.monitor_paused else 0),
      )
      _global_native_pointer_lookup[_CT.addressof(self._cloudaddressmonitor_callback_callback)] = self

    availability_changed = None
    monitor_paused = None

  def __init__(self, connector, cloud_addresses, callback):
    '''Creates a monitor, which queries whether a list of cloud addresses is
    available.
    '''
    if connector is None:
      raise ValueError('connector is a mandatory argument')
    else:
      connector_ = connector._getNativePtr()
      if not connector_: raise DestroyedObjectException()
    cloud_addresses_ = (_CT.c_char_p * len(cloud_addresses))(*map(_encode_unicode, cloud_addresses))
    if callback is None:
        raise ValueError('callback is a mandatory argument')
    callback_ = _CT.pointer(callback._cloudaddressmonitor_callback_callback) if callback is not None else None
    rv = self._nativePtr = CloudAddressMonitor.__nativeCreate(connector_, cloud_addresses_, len(cloud_addresses), callback_, callback_)
    if not self._getNativePtr(): _throwVncException("CloudAddressMonitor.__init__()")
    _global_native_pointer_lookup[self._getNativePtr()] = self

  def destroy(self):
    '''Destroys the Cloud monitor.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeDestroy(self._getNativePtr())
    assert rv is None
    del _global_native_pointer_lookup[self._getNativePtr()]
    self._setNativePtr(None)

  def pause(self):
    '''Pauses the Cloud monitor.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativePause(self._getNativePtr())
    assert rv is None

  def resume(self):
    '''Resumes the Cloud monitor.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeResume(self._getNativePtr())
    assert rv is None

  def set_pause_on_connect(self, pause_on_connect):
    '''Sets whether or not the Cloud monitor pauses automatically when a connection
    is established.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeSetPauseOnConnect(self._getNativePtr(), bool(pause_on_connect))
    assert rv is None

  __nativeCreate = SdkDll.register_class_function('vnc_CloudAddressMonitor_create', [_CT.c_void_p, _CT.POINTER(_CT.c_char_p), _CT.c_int, _CT.POINTER(Callback.CallbackImpl), _CT.c_void_p], _CT.c_void_p)
  __nativeDestroy = SdkDll.register_class_function('vnc_CloudAddressMonitor_destroy', [_CT.c_void_p], None)
  __nativePause = SdkDll.register_class_function('vnc_CloudAddressMonitor_pause', [_CT.c_void_p], None)
  __nativeResume = SdkDll.register_class_function('vnc_CloudAddressMonitor_resume', [_CT.c_void_p], None)
  __nativeSetPauseOnConnect = SdkDll.register_class_function('vnc_CloudAddressMonitor_setPauseOnConnect', [_CT.c_void_p, _CT.c_int], None)
  def __del__(self):
    if hasattr(self, "_nativePtr") and self._nativePtr is not None:
      self.destroy()
  def __enter__(self):
    return self
  def __exit__(self, exc_type, exc_value, traceback):
    self.destroy()

  def _getNativePtr(self):
    return self._nativePtr
  def _setNativePtr(self, v):
    self._nativePtr = v


class CloudConnector(object):
  '''Connector used to join VNC Cloud and establish an outgoing connection.
  '''
  def connect(self, peer_cloud_address, connection_handler):
    '''Begins an outgoing connection to the given Cloud address.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    peer_cloud_address = _encode_unicode(peer_cloud_address, False)
    if connection_handler is None:
      raise ValueError('connection_handler is a mandatory argument')
    else:
      connection_handler_ = connection_handler._getNativePtr()
      if not connection_handler_: raise DestroyedObjectException()
    rv = self.__nativeConnect(self._getNativePtr(), peer_cloud_address, connection_handler_)
    if rv == 0: _throwVncException("CloudConnector.connect()")

  def __init__(self, local_cloud_address, local_cloud_password):
    '''Creates a connector, which is used used to create connections to Cloud
    addresses.
    '''
    local_cloud_address = _encode_unicode(local_cloud_address, False)
    local_cloud_password = _encode_unicode(local_cloud_password, False)
    rv = self._nativePtr = CloudConnector.__nativeCreate(local_cloud_address, local_cloud_password)
    if not self._getNativePtr(): _throwVncException("CloudConnector.__init__()")
    _global_native_pointer_lookup[self._getNativePtr()] = self

  def destroy(self):
    '''Destroys the Cloud connector.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeDestroy(self._getNativePtr())
    assert rv is None
    del _global_native_pointer_lookup[self._getNativePtr()]
    self._setNativePtr(None)

  def set_relay_bandwidth_limit(self, relay_bandwidth_limit):
    '''Set the bandwidth limit applied to relayed Cloud connections.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeSetRelayBandwidthLimit(self._getNativePtr(), relay_bandwidth_limit)
    if rv == 0: _throwVncException("CloudConnector.set_relay_bandwidth_limit()")

  def set_wait_for_peer(self, wait_for_peer):
    '''Sets whether new connections created by the connector wait for the peer to
    start listening.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeSetWaitForPeer(self._getNativePtr(), bool(wait_for_peer))
    assert rv is None

  __nativeConnect = SdkDll.register_class_function('vnc_CloudConnector_connect', [_CT.c_void_p, _CT.c_char_p, _CT.c_void_p], _CT.c_int)
  __nativeCreate = SdkDll.register_class_function('vnc_CloudConnector_create', [_CT.c_char_p, _CT.c_char_p], _CT.c_void_p)
  __nativeDestroy = SdkDll.register_class_function('vnc_CloudConnector_destroy', [_CT.c_void_p], None)
  __nativeSetRelayBandwidthLimit = SdkDll.register_class_function('vnc_CloudConnector_setRelayBandwidthLimit', [_CT.c_void_p, _CT.c_int], _CT.c_int)
  __nativeSetWaitForPeer = SdkDll.register_class_function('vnc_CloudConnector_setWaitForPeer', [_CT.c_void_p, _CT.c_int], None)
  def __del__(self):
    if hasattr(self, "_nativePtr") and self._nativePtr is not None:
      self.destroy()
  def __enter__(self):
    return self
  def __exit__(self, exc_type, exc_value, traceback):
    self.destroy()

  def _getNativePtr(self):
    return self._nativePtr
  def _setNativePtr(self, v):
    self._nativePtr = v


class CloudListener(object):
  '''Listener used to join VNC Cloud and listen for a connection.
  '''
  Status = _create_enum("CloudListener.Status",
    '''Enumeration of listening statuses.''',
    STATUS_SEARCHING = 0,
    STATUS_ONLINE = 1,
  )

  class Callback(object):
    class CallbackImpl(_CT.Structure):
      _fields_ = [
        ("listeningFailed", _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_char_p, _CT.c_int)),
        ("filterConnection", _CT.CFUNCTYPE(_CT.c_int, _CT.c_void_p, _CT.c_void_p, _CT.c_char_p)),
        ("listeningStatusChanged", _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_int)),
      ]

    def __init__(self, listening_failed=None, filter_connection=None, listening_status_changed=None):
      if listening_failed is not None:
        self.listening_failed = listening_failed

      if self.listening_failed is None:
        raise ValueError('listening_failed is a mandatory callback')
      elif not callable(self.listening_failed):
        raise TypeError('listening_failed: callbacks must be callable')

      def _listening_failed(_, listener, cloud_error, retry_time_secs):
        cloud_error = _decode_unicode(cloud_error) if cloud_error is not None else cloud_error
        try:
          rv = self.listening_failed(_global_native_pointer_lookup[listener], cloud_error, retry_time_secs)
          assert rv is None
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback listeningFailed generated an uncaught exception: \'%s\'' % e)
          return None

      if filter_connection is not None:
        self.filter_connection = filter_connection

      if self.filter_connection is not None and not callable(self.filter_connection):
        raise TypeError('filter_connection: callbacks must be callable')

      def _filter_connection(_, listener, peer_cloud_address):
        peer_cloud_address = _decode_unicode(peer_cloud_address) if peer_cloud_address is not None else peer_cloud_address
        try:
          rv = self.filter_connection(_global_native_pointer_lookup[listener], peer_cloud_address)
          rv = bool(rv)
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback filterConnection generated an uncaught exception: \'%s\'' % e)
          return True

      if listening_status_changed is not None:
        self.listening_status_changed = listening_status_changed

      if self.listening_status_changed is not None and not callable(self.listening_status_changed):
        raise TypeError('listening_status_changed: callbacks must be callable')

      def _listening_status_changed(_, listener, status):
        status = CloudListener.Status(status)
        try:
          rv = self.listening_status_changed(_global_native_pointer_lookup[listener], status)
          assert rv is None
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback listeningStatusChanged generated an uncaught exception: \'%s\'' % e)
          return None

      self._cloudlistener_callback_callback = CloudListener.Callback.CallbackImpl(
        _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_char_p, _CT.c_int)(_listening_failed if self.listening_failed else 0),
        _CT.CFUNCTYPE(_CT.c_int, _CT.c_void_p, _CT.c_void_p, _CT.c_char_p)(_filter_connection if self.filter_connection else 0),
        _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_int)(_listening_status_changed if self.listening_status_changed else 0),
      )
      _global_native_pointer_lookup[_CT.addressof(self._cloudlistener_callback_callback)] = self

    listening_failed = None
    filter_connection = None
    listening_status_changed = None

  def __init__(self, local_cloud_address, local_cloud_password, connection_handler, callback):
    '''Begins listening for incoming connections on the given Cloud address.
    '''
    local_cloud_address = _encode_unicode(local_cloud_address, False)
    local_cloud_password = _encode_unicode(local_cloud_password, False)
    if connection_handler is None:
      raise ValueError('connection_handler is a mandatory argument')
    else:
      connection_handler_ = connection_handler._getNativePtr()
      if not connection_handler_: raise DestroyedObjectException()
    if callback is None:
        raise ValueError('callback is a mandatory argument')
    callback_ = _CT.pointer(callback._cloudlistener_callback_callback) if callback is not None else None
    rv = self._nativePtr = CloudListener.__nativeCreate(local_cloud_address, local_cloud_password, connection_handler_, callback_, callback_)
    if not self._getNativePtr(): _throwVncException("CloudListener.__init__()")
    _global_native_pointer_lookup[self._getNativePtr()] = self

  def destroy(self):
    '''Destroys the Cloud listener.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeDestroy(self._getNativePtr())
    assert rv is None
    del _global_native_pointer_lookup[self._getNativePtr()]
    self._setNativePtr(None)

  __nativeCreate = SdkDll.register_class_function('vnc_CloudListener_create', [_CT.c_char_p, _CT.c_char_p, _CT.c_void_p, _CT.POINTER(Callback.CallbackImpl), _CT.c_void_p], _CT.c_void_p)
  __nativeDestroy = SdkDll.register_class_function('vnc_CloudListener_destroy', [_CT.c_void_p], None)
  def __del__(self):
    if hasattr(self, "_nativePtr") and self._nativePtr is not None:
      self.destroy()
  def __enter__(self):
    return self
  def __exit__(self, exc_type, exc_value, traceback):
    self.destroy()

  def _getNativePtr(self):
    return self._nativePtr
  def _setNativePtr(self, v):
    self._nativePtr = v


class ImmutableDataBuffer(object):
  '''An immutable DataBuffer, owned by the SDK.'''
  def get_data(self):
    '''Gets the data contained in the buffer.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    length=_CT.c_int()

    rv = self.__nativeGetData(self._getNativePtr(), _CT.byref(length))
    return _CT.string_at(rv, length.value)

  def _getNativePtr(self):
    return self._nativePtr
  def _setNativePtr(self, v):
    self._nativePtr = None
  def __init__(self, nativePtr):
    self._nativePtr = nativePtr
    _global_native_pointer_lookup[nativePtr] = self
  def __del__(self):
    if hasattr(self, "_nativePtr") and self._nativePtr is not None and _global_native_pointer_lookup is not None:
      del _global_native_pointer_lookup[self._nativePtr]
  __nativeGetData = SdkDll.register_class_function('vnc_DataBuffer_getData', [_CT.c_void_p, _CT.POINTER(_CT.c_int)], _CT.POINTER(_CT.c_char))
class DataBuffer (ImmutableDataBuffer):
  '''Buffer containing data managed by the SDK.
  '''
  def __init__(self, data):
    '''Creates a data buffer containing a copy of the given data.
    '''
    rv = ImmutableDataBuffer.__init__(self, DataBuffer.__nativeCreate((_CT.c_char * len(data)).from_buffer(data), len(data)))
    if not self._getNativePtr(): _throwVncException("DataBuffer.__init__()")
  def destroy(self):
    '''Destroys the data buffer.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeDestroy(self._getNativePtr())
    assert rv is None
    del _global_native_pointer_lookup[self._getNativePtr()]
    self._setNativePtr(None)

  __nativeCreate = SdkDll.register_class_function('vnc_DataBuffer_create', [_CT.c_void_p, _CT.c_int], _CT.c_void_p)
  __nativeDestroy = SdkDll.register_class_function('vnc_DataBuffer_destroy', [_CT.c_void_p], None)
  def __del__(self):
    if hasattr(self, "_nativePtr") and self._nativePtr is not None:
      self.destroy()
  def __enter__(self):
    return self
  def __exit__(self, exc_type, exc_value, traceback):
    self.destroy()

  def _getNativePtr(self):
    return self._nativePtr
  def _setNativePtr(self, v):
    self._nativePtr = v


class DataStore(object):
  class Callback(object):
    class CallbackImpl(_CT.Structure):
      _fields_ = [
        ("put", _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_char_p, _CT.c_void_p)),
        ("get", _CT.CFUNCTYPE(_CT.c_void_p, _CT.c_void_p, _CT.c_char_p)),
      ]

    def __init__(self, put=None, get=None):
      if put is not None:
        self.put = put

      if self.put is None:
        raise ValueError('put is a mandatory callback')
      elif not callable(self.put):
        raise TypeError('put: callbacks must be callable')

      def _put(_, key, value):
        key = _decode_unicode(key) if key is not None else key
        value = _global_native_pointer_lookup[value] if value in _global_native_pointer_lookup else ImmutableDataBuffer(value)
        try:
          rv = self.put(key, value)
          assert rv is None
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback put generated an uncaught exception: \'%s\'' % e)
          return None

      if get is not None:
        self.get = get

      if self.get is None:
        raise ValueError('get is a mandatory callback')
      elif not callable(self.get):
        raise TypeError('get: callbacks must be callable')

      def _get(_, key):
        key = _decode_unicode(key) if key is not None else key
        try:
          rv = self.get(key)
          rv = rv._getNativePtr()
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback get generated an uncaught exception: \'%s\'' % e)
          return None

      self._datastore_callback_callback = DataStore.Callback.CallbackImpl(
        _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_char_p, _CT.c_void_p)(_put if self.put else 0),
        _CT.CFUNCTYPE(_CT.c_void_p, _CT.c_void_p, _CT.c_char_p)(_get if self.get else 0),
      )
      _global_native_pointer_lookup[_CT.addressof(self._datastore_callback_callback)] = self

    put = None
    get = None

  @staticmethod
  def create_custom_store(callback):
    '''Creates a custom data store.
    '''
    if callback is None:
        raise ValueError('callback is a mandatory argument')
    callback_ = _CT.pointer(callback._datastore_callback_callback) if callback is not None else None
    rv = DataStore.__nativeCreateCustomStore(callback_, callback_)
    if rv == 0: _throwVncException("DataStore.create_custom_store()")

  @staticmethod
  def create_file_store(path):
    '''Creates a file data store.
    '''
    path = _encode_unicode(path, False)
    rv = DataStore.__nativeCreateFileStore(path)
    if rv == 0: _throwVncException("DataStore.create_file_store()")

  @staticmethod
  def create_registry_store(registry_path):
    '''Creates a registry data store.
    '''
    registry_path = _encode_unicode(registry_path, False)
    rv = DataStore.__nativeCreateRegistryStore(registry_path)
    if rv == 0: _throwVncException("DataStore.create_registry_store()")

  @staticmethod
  def destroy_store():
    '''Destroys the current data store.
    '''
    rv = DataStore.__nativeDestroyStore()
    assert rv is None

  __nativeCreateCustomStore = SdkDll.register_class_function('vnc_DataStore_createCustomStore', [_CT.POINTER(Callback.CallbackImpl), _CT.c_void_p], _CT.c_int)
  __nativeCreateFileStore = SdkDll.register_class_function('vnc_DataStore_createFileStore', [_CT.c_char_p], _CT.c_int)
  __nativeCreateRegistryStore = SdkDll.register_class_function('vnc_DataStore_createRegistryStore', [_CT.c_char_p], _CT.c_int)
  __nativeDestroyStore = SdkDll.register_class_function('vnc_DataStore_destroyStore', [], None)
  def __init__(self):
    raise UserWarning("constructing static/abstract class")


class DirectTcpConnector(object):
  '''Connector used to make outgoing TCP connections
  '''
  def connect(self, host_or_ip_address, port, connection_handler):
    '''Begins an outgoing TCP connection to the given hostname or IP address.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    host_or_ip_address = _encode_unicode(host_or_ip_address, False)
    if connection_handler is None:
      raise ValueError('connection_handler is a mandatory argument')
    else:
      connection_handler_ = connection_handler._getNativePtr()
      if not connection_handler_: raise DestroyedObjectException()
    rv = self.__nativeConnect(self._getNativePtr(), host_or_ip_address, port, connection_handler_)
    if rv == 0: _throwVncException("DirectTcpConnector.connect()")

  def __init__(self):
    '''Creates a new TCP Connector which is used to make outgoing connections
    to TCP listeners.
    '''
    rv = self._nativePtr = DirectTcpConnector.__nativeCreate()
    if not self._getNativePtr(): _throwVncException("DirectTcpConnector.__init__()")
    _global_native_pointer_lookup[self._getNativePtr()] = self

  def destroy(self):
    '''Destroys the TCP Connector.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeDestroy(self._getNativePtr())
    assert rv is None
    del _global_native_pointer_lookup[self._getNativePtr()]
    self._setNativePtr(None)

  def set_proxy_settings(self, system_proxy, proxy_url):
    '''Set proxy server settings for this TCP Connector.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    proxy_url = _encode_unicode(proxy_url, True)
    rv = self.__nativeSetProxySettings(self._getNativePtr(), bool(system_proxy), proxy_url)
    if rv == 0: _throwVncException("DirectTcpConnector.set_proxy_settings()")

  __nativeConnect = SdkDll.register_class_function('vnc_DirectTcpConnector_connect', [_CT.c_void_p, _CT.c_char_p, _CT.c_int, _CT.c_void_p], _CT.c_int)
  __nativeCreate = SdkDll.register_class_function('vnc_DirectTcpConnector_create', [], _CT.c_void_p)
  __nativeDestroy = SdkDll.register_class_function('vnc_DirectTcpConnector_destroy', [_CT.c_void_p], None)
  __nativeSetProxySettings = SdkDll.register_class_function('vnc_DirectTcpConnector_setProxySettings', [_CT.c_void_p, _CT.c_int, _CT.c_char_p], _CT.c_int)
  def __del__(self):
    if hasattr(self, "_nativePtr") and self._nativePtr is not None:
      self.destroy()
  def __enter__(self):
    return self
  def __exit__(self, exc_type, exc_value, traceback):
    self.destroy()

  def _getNativePtr(self):
    return self._nativePtr
  def _setNativePtr(self, v):
    self._nativePtr = v


class DirectTcpListener(object):
  '''Listener used to receive incoming TCP connections
  '''
  class Callback(object):
    class CallbackImpl(_CT.Structure):
      _fields_ = [
        ("filterConnection", _CT.CFUNCTYPE(_CT.c_int, _CT.c_void_p, _CT.c_void_p, _CT.c_char_p, _CT.c_int)),
      ]

    def __init__(self, filter_connection=None):
      if filter_connection is not None:
        self.filter_connection = filter_connection

      if self.filter_connection is not None and not callable(self.filter_connection):
        raise TypeError('filter_connection: callbacks must be callable')

      def _filter_connection(_, listener, ip_address, port):
        ip_address = _decode_unicode(ip_address) if ip_address is not None else ip_address
        try:
          rv = self.filter_connection(_global_native_pointer_lookup[listener], ip_address, port)
          rv = bool(rv)
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback filterConnection generated an uncaught exception: \'%s\'' % e)
          return True

      self._directtcplistener_callback_callback = DirectTcpListener.Callback.CallbackImpl(
        _CT.CFUNCTYPE(_CT.c_int, _CT.c_void_p, _CT.c_void_p, _CT.c_char_p, _CT.c_int)(_filter_connection if self.filter_connection else 0),
      )
      _global_native_pointer_lookup[_CT.addressof(self._directtcplistener_callback_callback)] = self

    filter_connection = None

  def __init__(self, port, address_list, connection_handler, callback):
    '''Begin listening for incoming TCP connections on the given port (IPv4 and
    IPv6).
    '''
    address_list = _encode_unicode(address_list, True)
    if connection_handler is None:
      raise ValueError('connection_handler is a mandatory argument')
    else:
      connection_handler_ = connection_handler._getNativePtr()
      if not connection_handler_: raise DestroyedObjectException()
    callback_ = _CT.pointer(callback._directtcplistener_callback_callback) if callback is not None else None
    rv = self._nativePtr = DirectTcpListener.__nativeCreate(port, address_list, connection_handler_, callback_, callback_)
    if not self._getNativePtr(): _throwVncException("DirectTcpListener.__init__()")
    _global_native_pointer_lookup[self._getNativePtr()] = self

  def destroy(self):
    '''Destroys the TCP listener.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeDestroy(self._getNativePtr())
    assert rv is None
    del _global_native_pointer_lookup[self._getNativePtr()]
    self._setNativePtr(None)

  __nativeCreate = SdkDll.register_class_function('vnc_DirectTcpListener_create', [_CT.c_int, _CT.c_char_p, _CT.c_void_p, _CT.POINTER(Callback.CallbackImpl), _CT.c_void_p], _CT.c_void_p)
  __nativeDestroy = SdkDll.register_class_function('vnc_DirectTcpListener_destroy', [_CT.c_void_p], None)
  def __del__(self):
    if hasattr(self, "_nativePtr") and self._nativePtr is not None:
      self.destroy()
  def __enter__(self):
    return self
  def __exit__(self, exc_type, exc_value, traceback):
    self.destroy()

  def _getNativePtr(self):
    return self._nativePtr
  def _setNativePtr(self, v):
    self._nativePtr = v


class DisplayManager(object):
  '''Manages the list of displays made available by a Server.
  '''
  class Callback(object):
    class CallbackImpl(_CT.Structure):
      _fields_ = [
        ("displaysChanged", _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p)),
      ]

    def __init__(self, displays_changed=None):
      if displays_changed is not None:
        self.displays_changed = displays_changed

      if self.displays_changed is not None and not callable(self.displays_changed):
        raise TypeError('displays_changed: callbacks must be callable')

      def _displays_changed(_, display_manager):
        try:
          rv = self.displays_changed(_global_native_pointer_lookup[display_manager])
          assert rv is None
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback displaysChanged generated an uncaught exception: \'%s\'' % e)
          return None

      self._displaymanager_callback_callback = DisplayManager.Callback.CallbackImpl(
        _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p)(_displays_changed if self.displays_changed else 0),
      )
      _global_native_pointer_lookup[_CT.addressof(self._displaymanager_callback_callback)] = self

    displays_changed = None

  def get_display_count(self):
    '''Returns the number of displays.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeGetDisplayCount(self._getNativePtr())
    return rv

  def get_id(self, index):
    '''Gets the ID of the display (typically a short string).
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeGetId(self._getNativePtr(), index)
    if not rv: _throwVncException("DisplayManager.get_id()")
    return _decode_unicode(rv)

  def get_name(self, index):
    '''Gets the name of the display (typically a human-readable string).
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeGetName(self._getNativePtr(), index)
    if not rv: _throwVncException("DisplayManager.get_name()")
    return _decode_unicode(rv)

  def get_origin_x(self, index):
    '''Gets the horizontal origin of the display in pixels.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeGetOriginX(self._getNativePtr(), index)
    return rv

  def get_origin_y(self, index):
    '''Gets the vertical origin of the display in pixels.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeGetOriginY(self._getNativePtr(), index)
    return rv

  def get_resolution_x(self, index):
    '''Gets the horizontal resolution of the display in pixels.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeGetResolutionX(self._getNativePtr(), index)
    return rv

  def get_resolution_y(self, index):
    '''Gets the vertical resolution of the display in pixels.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeGetResolutionY(self._getNativePtr(), index)
    return rv

  def is_primary(self, index):
    '''Returns whether this is the primary (or main) display.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeIsPrimary(self._getNativePtr(), index)
    return bool(rv)

  def select_display(self, index):
    '''Chooses a particular display to remote to connected Viewer app users.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeSelectDisplay(self._getNativePtr(), index)
    if rv == 0: _throwVncException("DisplayManager.select_display()")

  def set_callback(self, callback):
    '''Registers a callback notifying when displays are added or removed, or the 
    resolution of an existing display changes.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    callback_ = _CT.pointer(callback._displaymanager_callback_callback) if callback is not None else None
    rv = self.__nativeSetCallback(self._getNativePtr(), callback_, callback_)
    if rv == 0: _throwVncException("DisplayManager.set_callback()")

  __nativeGetDisplayCount = SdkDll.register_class_function('vnc_DisplayManager_getDisplayCount', [_CT.c_void_p], _CT.c_int)
  __nativeGetId = SdkDll.register_class_function('vnc_DisplayManager_getId', [_CT.c_void_p, _CT.c_int], _CT.c_char_p)
  __nativeGetName = SdkDll.register_class_function('vnc_DisplayManager_getName', [_CT.c_void_p, _CT.c_int], _CT.c_char_p)
  __nativeGetOriginX = SdkDll.register_class_function('vnc_DisplayManager_getOriginX', [_CT.c_void_p, _CT.c_int], _CT.c_int)
  __nativeGetOriginY = SdkDll.register_class_function('vnc_DisplayManager_getOriginY', [_CT.c_void_p, _CT.c_int], _CT.c_int)
  __nativeGetResolutionX = SdkDll.register_class_function('vnc_DisplayManager_getResolutionX', [_CT.c_void_p, _CT.c_int], _CT.c_int)
  __nativeGetResolutionY = SdkDll.register_class_function('vnc_DisplayManager_getResolutionY', [_CT.c_void_p, _CT.c_int], _CT.c_int)
  __nativeIsPrimary = SdkDll.register_class_function('vnc_DisplayManager_isPrimary', [_CT.c_void_p, _CT.c_int], _CT.c_int)
  __nativeSelectDisplay = SdkDll.register_class_function('vnc_DisplayManager_selectDisplay', [_CT.c_void_p, _CT.c_int], _CT.c_int)
  __nativeSetCallback = SdkDll.register_class_function('vnc_DisplayManager_setCallback', [_CT.c_void_p, _CT.POINTER(Callback.CallbackImpl), _CT.c_void_p], _CT.c_int)
  def __init__(self):
    raise UserWarning("constructing static/abstract class")


class EventLoop(object):
  # AtomicBoolean provides a simple atomic test-and-set operation.  There
  # surely must be a Python built-in to do this, but we couldn't find it!
  class _AtomicBoolean:
    def set(self, new_value):
      rv = None
      with self.lock:
        rv = self.value
        self.value = new_value
      return rv
    def __init__(self):
      self.value = False
      self.lock = threading.Lock()
  _stop_loop = _AtomicBoolean()
  _tasks = queue.Queue()
  _run_lock = threading.Lock()

  @staticmethod
  def stop():
    '''Stops the event loop previously started with vncsdk.EventLoop.run(), causing
    vncsdk.EventLoop.run() to return promptly.
    '''
    EventLoop._stop_loop.set(True)
    EventLoop.__nativeStop()

  @staticmethod
  def run():
    '''Runs the event loop until vncsdk.EventLoop.stop() is called.
    '''
    if not EventLoop._run_lock.acquire(False):
      return

    try:
      while not EventLoop._stop_loop.set(False):
        EventLoop.__nativeRun()
        while not EventLoop._tasks.empty():
          try:
            task,args,kwargs = EventLoop._tasks.get()
            task(*args, **kwargs)
          except BaseException as e:
            _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', "task generated an uncaught exception: '%s'" % e)
    finally:
      EventLoop._run_lock.release()

  @staticmethod
  def run_on_loop(runnable, args=(), kwargs=None):
    '''Schedules a task for immediate execution on the SDK's thread.  The task
    will be run during the current or next invocation of vncsdk.EventLoop.run().
    '''
    if not callable(runnable):
      raise TypeError("tasks must be callable")
    if kwargs is None:
      kwargs = {}
    EventLoop._tasks.put((runnable, args, kwargs))
    EventLoop.__nativeStop()

  @staticmethod
  def should_stop():
    '''Returns a boolean flag indicating whether the event loop should stop,
    and immediately clears it.
    '''
    rv = EventLoop.__nativeShouldStop()
    return bool(rv)

  __nativeRun = SdkDll.register_class_function('vnc_EventLoop_run', [], None)
  __nativeShouldStop = SdkDll.register_class_function('vnc_EventLoop_shouldStop', [], _CT.c_int)
  __nativeStop = SdkDll.register_class_function('vnc_EventLoop_stop', [], None)
  def __init__(self):
    raise UserWarning("constructing static/abstract class")


class EventLoopFd(object):
  Event = _create_enum("EventLoopFd.Event",
    '''Enumeration of file descriptor events for event selection.''',
    READ = 1,
    WRITE = 2,
    EXCEPT = 4,
  )

  class Callback(object):
    class CallbackImpl(_CT.Structure):
      _fields_ = [
        ("eventUpdated", _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_int, _CT.c_int)),
        ("timerUpdated", _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_int)),
      ]

    def __init__(self, event_updated=None, timer_updated=None):
      if event_updated is not None:
        self.event_updated = event_updated

      if self.event_updated is None:
        raise ValueError('event_updated is a mandatory callback')
      elif not callable(self.event_updated):
        raise TypeError('event_updated: callbacks must be callable')

      def _event_updated(_, fd, event_mask):
        event_mask = _int_to_enums(event_mask, EventLoopFd.Event)
        try:
          rv = self.event_updated(fd, event_mask)
          assert rv is None
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback eventUpdated generated an uncaught exception: \'%s\'' % e)
          return None

      if timer_updated is not None:
        self.timer_updated = timer_updated

      if self.timer_updated is not None and not callable(self.timer_updated):
        raise TypeError('timer_updated: callbacks must be callable')

      def _timer_updated(_, expiry_ms):
        try:
          rv = self.timer_updated(expiry_ms)
          assert rv is None
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback timerUpdated generated an uncaught exception: \'%s\'' % e)
          return None

      self._eventloopfd_callback_callback = EventLoopFd.Callback.CallbackImpl(
        _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_int, _CT.c_int)(_event_updated if self.event_updated else 0),
        _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_int)(_timer_updated if self.timer_updated else 0),
      )
      _global_native_pointer_lookup[_CT.addressof(self._eventloopfd_callback_callback)] = self

    event_updated = None
    timer_updated = None

  @staticmethod
  def handle_events():
    '''Handles events on the file descriptors and process expired timers.
    '''
    rv = EventLoopFd.__nativeHandleEvents()
    return rv

  @staticmethod
  def mark_events(fd, events):
    '''Marks event(s) that occurred on the specified file descriptor.
    '''
    rv = EventLoopFd.__nativeMarkEvents(fd, _enums_to_int(events))
    if rv == 0: _throwVncException("EventLoopFd.mark_events()")

  @staticmethod
  def set_callback(callback):
    '''Sets the event loop callback.
    '''
    callback_ = _CT.pointer(callback._eventloopfd_callback_callback) if callback is not None else None
    rv = EventLoopFd.__nativeSetCallback(callback_, callback_)
    if rv == 0: _throwVncException("EventLoopFd.set_callback()")

  __nativeHandleEvents = SdkDll.register_class_function('vnc_EventLoopFd_handleEvents', [], _CT.c_int)
  __nativeMarkEvents = SdkDll.register_class_function('vnc_EventLoopFd_markEvents', [_CT.c_int, _CT.c_int], _CT.c_int)
  __nativeSetCallback = SdkDll.register_class_function('vnc_EventLoopFd_setCallback', [_CT.POINTER(Callback.CallbackImpl), _CT.c_void_p], _CT.c_int)
  def __init__(self):
    raise UserWarning("constructing static/abstract class")


class EventLoopWin(object):
  class Callback(object):
    class CallbackImpl(_CT.Structure):
      _fields_ = [
        ("eventUpdated", _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_int)),
        ("timerUpdated", _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_int)),
      ]

    def __init__(self, event_updated=None, timer_updated=None):
      if event_updated is not None:
        self.event_updated = event_updated

      if self.event_updated is None:
        raise ValueError('event_updated is a mandatory callback')
      elif not callable(self.event_updated):
        raise TypeError('event_updated: callbacks must be callable')

      def _event_updated(_, event, add):
        add = bool(add)
        try:
          rv = self.event_updated(event, add)
          assert rv is None
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback eventUpdated generated an uncaught exception: \'%s\'' % e)
          return None

      if timer_updated is not None:
        self.timer_updated = timer_updated

      if self.timer_updated is not None and not callable(self.timer_updated):
        raise TypeError('timer_updated: callbacks must be callable')

      def _timer_updated(_, expiry_ms):
        try:
          rv = self.timer_updated(expiry_ms)
          assert rv is None
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback timerUpdated generated an uncaught exception: \'%s\'' % e)
          return None

      self._eventloopwin_callback_callback = EventLoopWin.Callback.CallbackImpl(
        _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_int)(_event_updated if self.event_updated else 0),
        _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_int)(_timer_updated if self.timer_updated else 0),
      )
      _global_native_pointer_lookup[_CT.addressof(self._eventloopwin_callback_callback)] = self

    event_updated = None
    timer_updated = None

  @staticmethod
  def get_events():
    '''Gets the array of events that the SDK currently wishes to be notified of.
    '''
    events_ = (_CT.c_void_p * 64)()
    rv = EventLoopWin.__nativeGetEvents(events_)
    rv = map(int, events_[:rv])
    return rv

  @staticmethod
  def handle_event(event):
    '''Handles the given event (if any) and process expired timers.
    '''
    rv = EventLoopWin.__nativeHandleEvent(event)
    return rv

  @staticmethod
  def set_callback(callback):
    '''Sets the event loop callback.
    '''
    callback_ = _CT.pointer(callback._eventloopwin_callback_callback) if callback is not None else None
    rv = EventLoopWin.__nativeSetCallback(callback_, callback_)
    if rv == 0: _throwVncException("EventLoopWin.set_callback()")

  __nativeGetEvents = SdkDll.register_class_function('vnc_EventLoopWin_getEvents', [_CT.POINTER(_CT.c_void_p)], _CT.c_int)
  __nativeHandleEvent = SdkDll.register_class_function('vnc_EventLoopWin_handleEvent', [_CT.c_void_p], _CT.c_int)
  __nativeSetCallback = SdkDll.register_class_function('vnc_EventLoopWin_setCallback', [_CT.POINTER(Callback.CallbackImpl), _CT.c_void_p], _CT.c_int)
  def __init__(self):
    raise UserWarning("constructing static/abstract class")


class Logger(object):
  # overload createStderrLogger
  @staticmethod
  def create_stderr_logger():
    '''Creates a logger implementation that calls the given callback whenever a log message is written.'''
    def custom_log(level, message):
      sys.stderr.write("{date}T{time}Z [{level}] {message}\n".format(
        date=datetime.strftime(datetime.now(), "%Y-%m-%d"),
        time=datetime.strftime(datetime.now(), "%H:%M:%S.%f")[:-3],
        level=level.name,
        message=message
      ))
    Logger.create_custom_logger(Logger.Callback(log_message=custom_log))

  Level = _create_enum("Logger.Level",
    '''Enumeration of log levels.''',
    ERROR = 0,
    BASIC = 1,
    FULL = 2,
    DEBUG = 3,
  )

  class Callback(object):
    class CallbackImpl(_CT.Structure):
      _fields_ = [
        ("logMessage", _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_int, _CT.c_char_p)),
      ]

    def __init__(self, log_message=None):
      if log_message is not None:
        self.log_message = log_message

      if self.log_message is None:
        raise ValueError('log_message is a mandatory callback')
      elif not callable(self.log_message):
        raise TypeError('log_message: callbacks must be callable')

      def _log_message(_, level, message):
        level = Logger.Level(level)
        message = _decode_unicode(message) if message is not None else message
        try:
          rv = self.log_message(level, message)
          assert rv is None
          return rv
        except BaseException as e:
          return None

      self._logger_callback_callback = Logger.Callback.CallbackImpl(
        _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_int, _CT.c_char_p)(_log_message if self.log_message else 0),
      )
      _global_native_pointer_lookup[_CT.addressof(self._logger_callback_callback)] = self

    log_message = None

  @staticmethod
  def create_custom_logger(callback):
    '''Creates a logger implementation that calls the given callback whenever a log
    message is written.
    '''
    if callback is None:
        raise ValueError('callback is a mandatory argument')
    callback_ = _CT.pointer(callback._logger_callback_callback) if callback is not None else None
    rv = Logger.__nativeCreateCustomLogger(callback_, callback_)
    if rv == 0: _throwVncException("Logger.create_custom_logger()")

  @staticmethod
  def create_file_logger(path):
    '''Creates a logger that writes data to the specified log file.
    '''
    path = _encode_unicode(path, False)
    rv = Logger.__nativeCreateFileLogger(path)
    if rv == 0: _throwVncException("Logger.create_file_logger()")

  @staticmethod
  def destroy_logger():
    '''Destroys any previously created logger.
    '''
    rv = Logger.__nativeDestroyLogger()
    assert rv is None

  @staticmethod
  def set_level(level):
    '''Sets the current log level.
    '''
    rv = Logger.__nativeSetLevel(level.value)
    assert rv is None

  __nativeCreateCustomLogger = SdkDll.register_class_function('vnc_Logger_createCustomLogger', [_CT.POINTER(Callback.CallbackImpl), _CT.c_void_p], _CT.c_int)
  __nativeCreateFileLogger = SdkDll.register_class_function('vnc_Logger_createFileLogger', [_CT.c_char_p], _CT.c_int)
  __nativeCreateStderrLogger = SdkDll.register_class_function('vnc_Logger_createStderrLogger', [], None)
  __nativeDestroyLogger = SdkDll.register_class_function('vnc_Logger_destroyLogger', [], None)
  __nativeSetLevel = SdkDll.register_class_function('vnc_Logger_setLevel', [_CT.c_int], None)
  def __init__(self):
    raise UserWarning("constructing static/abstract class")


class MessagingManager(object):
  '''Enables a Viewer or Server to send custom messages.
  '''
  class Callback(object):
    class CallbackImpl(_CT.Structure):
      _fields_ = [
        ("messageReceived", _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_void_p, _CT.c_void_p)),
      ]

    def __init__(self, message_received=None):
      if message_received is not None:
        self.message_received = message_received

      if self.message_received is not None and not callable(self.message_received):
        raise TypeError('message_received: callbacks must be callable')

      def _message_received(_, messaging_manager, sender, buffer):
        sender = Connection(sender)
        buffer = _global_native_pointer_lookup[buffer] if buffer in _global_native_pointer_lookup else ImmutableDataBuffer(buffer)
        try:
          rv = self.message_received(_global_native_pointer_lookup[messaging_manager], sender, buffer)
          assert rv is None
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback messageReceived generated an uncaught exception: \'%s\'' % e)
          return None

      self._messagingmanager_callback_callback = MessagingManager.Callback.CallbackImpl(
        _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_void_p, _CT.c_void_p)(_message_received if self.message_received else 0),
      )
      _global_native_pointer_lookup[_CT.addressof(self._messagingmanager_callback_callback)] = self

    message_received = None

  def send_message(self, buffer, connection):
    '''Sends a message.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    if connection is None:
      connection_ = None
    else:
      connection_ = connection._getNativePtr()
      if not connection_: raise DestroyedObjectException()
    rv = self.__nativeSendMessage(self._getNativePtr(), (_CT.c_char * len(buffer)).from_buffer(buffer), len(buffer), connection_)
    if rv == 0: _throwVncException("MessagingManager.send_message()")

  def set_callback(self, callback):
    '''Registers a callback notifying when messages are received.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    callback_ = _CT.pointer(callback._messagingmanager_callback_callback) if callback is not None else None
    rv = self.__nativeSetCallback(self._getNativePtr(), callback_, callback_)
    if rv == 0: _throwVncException("MessagingManager.set_callback()")

  __nativeSendMessage = SdkDll.register_class_function('vnc_MessagingManager_sendMessage', [_CT.c_void_p, _CT.c_void_p, _CT.c_int, _CT.c_void_p], _CT.c_int)
  __nativeSetCallback = SdkDll.register_class_function('vnc_MessagingManager_setCallback', [_CT.c_void_p, _CT.POINTER(Callback.CallbackImpl), _CT.c_void_p], _CT.c_int)
  def __init__(self):
    raise UserWarning("constructing static/abstract class")


class ImmutablePixelFormat(object):
  '''An immutable PixelFormat, owned by the SDK.'''
  @staticmethod
  def bgr888():
    '''32 bits per pixel stored as XXXXXXXXBBBBBBBBGGGGGGGGRRRRRRRR in most
    significant to least significant bit order
    '''
    rv = PixelFormat.__nativeBgr888()
    return _global_native_pointer_lookup[rv] if rv in _global_native_pointer_lookup else ImmutablePixelFormat(rv)

  def blue_max(self):
    '''Gets the maximum value for the blue pixel value.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeBlueMax(self._getNativePtr())
    return rv

  def blue_shift(self):
    '''Gets the number of bits the blue pixel value is shifted.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeBlueShift(self._getNativePtr())
    return rv

  def bpp(self):
    '''Gets the total number of bits per pixel.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeBpp(self._getNativePtr())
    return rv

  def depth(self):
    '''Gets the number of significant bits that are used to store pixel data.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeDepth(self._getNativePtr())
    return rv

  def green_max(self):
    '''Gets the maximum value for the green pixel value.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeGreenMax(self._getNativePtr())
    return rv

  def green_shift(self):
    '''Gets the number of bits the green pixel value is shifted.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeGreenShift(self._getNativePtr())
    return rv

  def red_max(self):
    '''Gets the maximum value for the red pixel value.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeRedMax(self._getNativePtr())
    return rv

  def red_shift(self):
    '''Gets the number of bits the red pixel value is shifted.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeRedShift(self._getNativePtr())
    return rv

  @staticmethod
  def rgb555():
    '''16 bits per pixel stored as XRRRRRGGGGGBBBBB in most significant to least
    significant bit order
    '''
    rv = PixelFormat.__nativeRgb555()
    return _global_native_pointer_lookup[rv] if rv in _global_native_pointer_lookup else ImmutablePixelFormat(rv)

  @staticmethod
  def rgb565():
    '''16 bits per pixel stored as RRRRRGGGGGGBBBBB in most significant to least
    significant bit order
    '''
    rv = PixelFormat.__nativeRgb565()
    return _global_native_pointer_lookup[rv] if rv in _global_native_pointer_lookup else ImmutablePixelFormat(rv)

  @staticmethod
  def rgb888():
    '''32 bits per pixel stored as XXXXXXXXRRRRRRRRGGGGGGGGBBBBBBBB in most
    significant to least significant bit order
    '''
    rv = PixelFormat.__nativeRgb888()
    return _global_native_pointer_lookup[rv] if rv in _global_native_pointer_lookup else ImmutablePixelFormat(rv)

  def _getNativePtr(self):
    return self._nativePtr
  def _setNativePtr(self, v):
    self._nativePtr = None
  def __init__(self, nativePtr):
    self._nativePtr = nativePtr
    _global_native_pointer_lookup[nativePtr] = self
  def __del__(self):
    if hasattr(self, "_nativePtr") and self._nativePtr is not None and _global_native_pointer_lookup is not None:
      del _global_native_pointer_lookup[self._nativePtr]
  __nativeBgr888 = SdkDll.register_class_function('vnc_PixelFormat_bgr888', [], _CT.c_void_p)
  __nativeBlueMax = SdkDll.register_class_function('vnc_PixelFormat_blueMax', [_CT.c_void_p], _CT.c_int)
  __nativeBlueShift = SdkDll.register_class_function('vnc_PixelFormat_blueShift', [_CT.c_void_p], _CT.c_int)
  __nativeBpp = SdkDll.register_class_function('vnc_PixelFormat_bpp', [_CT.c_void_p], _CT.c_int)
  __nativeDepth = SdkDll.register_class_function('vnc_PixelFormat_depth', [_CT.c_void_p], _CT.c_int)
  __nativeGreenMax = SdkDll.register_class_function('vnc_PixelFormat_greenMax', [_CT.c_void_p], _CT.c_int)
  __nativeGreenShift = SdkDll.register_class_function('vnc_PixelFormat_greenShift', [_CT.c_void_p], _CT.c_int)
  __nativeRedMax = SdkDll.register_class_function('vnc_PixelFormat_redMax', [_CT.c_void_p], _CT.c_int)
  __nativeRedShift = SdkDll.register_class_function('vnc_PixelFormat_redShift', [_CT.c_void_p], _CT.c_int)
  __nativeRgb555 = SdkDll.register_class_function('vnc_PixelFormat_rgb555', [], _CT.c_void_p)
  __nativeRgb565 = SdkDll.register_class_function('vnc_PixelFormat_rgb565', [], _CT.c_void_p)
  __nativeRgb888 = SdkDll.register_class_function('vnc_PixelFormat_rgb888', [], _CT.c_void_p)
class PixelFormat (ImmutablePixelFormat):
  '''Description of how pixels are stored in a Viewer framebuffer.
  '''
  def __init__(self, bits_per_pixel, red_max, green_max, blue_max, red_shift, green_shift, blue_shift):
    '''Creates a custom pixel format based on the given parameters.
    '''
    rv = ImmutablePixelFormat.__init__(self, PixelFormat.__nativeCreate(bits_per_pixel, red_max, green_max, blue_max, red_shift, green_shift, blue_shift))
    if not self._getNativePtr(): _throwVncException("PixelFormat.__init__()")
  def destroy(self):
    '''Destroy a custom pixel format.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeDestroy(self._getNativePtr())
    assert rv is None
    del _global_native_pointer_lookup[self._getNativePtr()]
    self._setNativePtr(None)

  __nativeCreate = SdkDll.register_class_function('vnc_PixelFormat_create', [_CT.c_int, _CT.c_int, _CT.c_int, _CT.c_int, _CT.c_int, _CT.c_int, _CT.c_int], _CT.c_void_p)
  __nativeDestroy = SdkDll.register_class_function('vnc_PixelFormat_destroy', [_CT.c_void_p], None)
  def __del__(self):
    if hasattr(self, "_nativePtr") and self._nativePtr is not None:
      self.destroy()
  def __enter__(self):
    return self
  def __exit__(self, exc_type, exc_value, traceback):
    self.destroy()

  def _getNativePtr(self):
    return self._nativePtr
  def _setNativePtr(self, v):
    self._nativePtr = v


class _Private(object):
  @staticmethod
  def event_loop_step(timeout_ms):
    '''Waits for a specified time for an event to occur and then performs a single
    iteration of the event loop.
    '''
    rv = _Private.__nativeEventLoopStep(timeout_ms)
    assert rv is None

  @staticmethod
  def force_cloud_data_relay():
    '''Force data relay connections
    '''
    rv = _Private.__nativeForceCloudDataRelay()
    assert rv is None

  @staticmethod
  def get_receive_stream_pos(viewer):
    '''Get the receiving data rate
    '''
    if viewer is None:
      raise ValueError('viewer is a mandatory argument')
    else:
      viewer_ = viewer._getNativePtr()
      if not viewer_: raise DestroyedObjectException()
    rv = _Private.__nativeGetReceiveStreamPos(viewer_)
    return rv

  @staticmethod
  def logger_write(level, tag, message):
    '''Write to the logger instance.
    '''
    tag = _encode_unicode(tag, False)
    message = _encode_unicode(message, False)
    rv = _Private.__nativeLoggerWrite(level.value, tag, message)
    assert rv is None

  @staticmethod
  def set_cloud_deployment(buf):
    '''Pass in a buffer containing a HostedConfig.
    '''
    rv = _Private.__nativeSetCloudDeployment((_CT.c_char * len(buf)).from_buffer(buf), len(buf))
    assert rv is None

  __nativeEventLoopStep = SdkDll.register_class_function('vnc_Private_eventLoopStep', [_CT.c_int], None)
  __nativeForceCloudDataRelay = SdkDll.register_class_function('vnc_Private_forceCloudDataRelay', [], None)
  __nativeGetReceiveStreamPos = SdkDll.register_class_function('vnc_Private_getReceiveStreamPos', [_CT.c_void_p], _CT.c_int)
  __nativeLoggerWrite = SdkDll.register_class_function('vnc_Private_loggerWrite', [_CT.c_int, _CT.c_char_p, _CT.c_char_p], None)
  __nativeSetCloudDeployment = SdkDll.register_class_function('vnc_Private_setCloudDeployment', [_CT.c_void_p, _CT.c_int], None)
  def __init__(self):
    raise UserWarning("constructing static/abstract class")


class RsaKey(object):
  class Callback(object):
    class CallbackImpl(_CT.Structure):
      _fields_ = [
        ("detailsReady", _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_char_p, _CT.c_char_p)),
      ]

    def __init__(self, details_ready=None):
      if details_ready is not None:
        self.details_ready = details_ready

      if self.details_ready is None:
        raise ValueError('details_ready is a mandatory callback')
      elif not callable(self.details_ready):
        raise TypeError('details_ready: callbacks must be callable')

      def _details_ready(_, rsa_public, hex_fingerprint, catchphrase_fingerprint):
        rsa_public = _global_native_pointer_lookup[rsa_public] if rsa_public in _global_native_pointer_lookup else ImmutableDataBuffer(rsa_public)
        hex_fingerprint = _decode_unicode(hex_fingerprint) if hex_fingerprint is not None else hex_fingerprint
        catchphrase_fingerprint = _decode_unicode(catchphrase_fingerprint) if catchphrase_fingerprint is not None else catchphrase_fingerprint
        try:
          rv = self.details_ready(rsa_public, hex_fingerprint, catchphrase_fingerprint)
          assert rv is None
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback detailsReady generated an uncaught exception: \'%s\'' % e)
          return None

      self._rsakey_callback_callback = RsaKey.Callback.CallbackImpl(
        _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_char_p, _CT.c_char_p)(_details_ready if self.details_ready else 0),
      )
      _global_native_pointer_lookup[_CT.addressof(self._rsakey_callback_callback)] = self

    details_ready = None

  @staticmethod
  def cancel_details(_callback):
    '''Cancels any outstanding notifications for the given callback.
    '''
    rv = RsaKey.__nativeCancelDetails(_CT.pointer(_callback._rsakey_callback_callback))
    assert rv is None

  @staticmethod
  def clear():
    '''Removes any stored RSA key from the data store.
    '''
    rv = RsaKey.__nativeClear()
    if rv == 0: _throwVncException("RsaKey.clear()")

  @staticmethod
  def get_details(callback, generate_if_missing):
    '''Requests the details for the machine's identifying RSA public key.
    '''
    callback_ = _CT.pointer(callback._rsakey_callback_callback) if callback is not None else None
    rv = RsaKey.__nativeGetDetails(callback_, callback_, bool(generate_if_missing))
    if rv == 0: _throwVncException("RsaKey.get_details()")

  __nativeCancelDetails = SdkDll.register_class_function('vnc_RsaKey_cancelDetails', [_CT.POINTER(Callback.CallbackImpl)], None)
  __nativeClear = SdkDll.register_class_function('vnc_RsaKey_clear', [], _CT.c_int)
  __nativeGetDetails = SdkDll.register_class_function('vnc_RsaKey_getDetails', [_CT.POINTER(Callback.CallbackImpl), _CT.c_void_p, _CT.c_int], _CT.c_int)
  def __init__(self):
    raise UserWarning("constructing static/abstract class")


  class __AnnotationManagerImpl(AnnotationManager):
    def __init__(self, parent, f):
      # (don't call superclass __init__)
      self.__parent = parent
      self.__f = f
      _global_native_pointer_lookup[self._getNativePtr()] = self

    def _getNativePtr(self):
      parentPtr = self.__parent._getNativePtr()
      if not parentPtr: raise DestroyedObjectException()
      ptr = self.__f(parentPtr)
      if not ptr: _throwVncException("AnnotationManager")
      return ptr

    def __eq__(self, other):
      return (isinstance(other, self.__class__)
        and hash(self) == hash(other))

    def __hash__(self):
      # After invalidation this object should only equal itself
      parentPtr = self.__parent._getNativePtr()
      if not parentPtr: return id(self)
      return int(self.__f(parentPtr)) or id(self)

    def __ne__(self, other):
      return not self.__eq__(other)

  class __ConnectionHandlerImpl(ConnectionHandler):
    def __init__(self, parent, f):
      # (don't call superclass __init__)
      self.__parent = parent
      self.__f = f
      _global_native_pointer_lookup[self._getNativePtr()] = self

    def _getNativePtr(self):
      parentPtr = self.__parent._getNativePtr()
      if not parentPtr: raise DestroyedObjectException()
      ptr = self.__f(parentPtr)
      if not ptr: _throwVncException("ConnectionHandler")
      return ptr

    def __eq__(self, other):
      return (isinstance(other, self.__class__)
        and hash(self) == hash(other))

    def __hash__(self):
      # After invalidation this object should only equal itself
      parentPtr = self.__parent._getNativePtr()
      if not parentPtr: return id(self)
      return int(self.__f(parentPtr)) or id(self)

    def __ne__(self, other):
      return not self.__eq__(other)

  class __DisplayManagerImpl(DisplayManager):
    def __init__(self, parent, f):
      # (don't call superclass __init__)
      self.__parent = parent
      self.__f = f
      _global_native_pointer_lookup[self._getNativePtr()] = self

    def _getNativePtr(self):
      parentPtr = self.__parent._getNativePtr()
      if not parentPtr: raise DestroyedObjectException()
      ptr = self.__f(parentPtr)
      if not ptr: _throwVncException("DisplayManager")
      return ptr

    def __eq__(self, other):
      return (isinstance(other, self.__class__)
        and hash(self) == hash(other))

    def __hash__(self):
      # After invalidation this object should only equal itself
      parentPtr = self.__parent._getNativePtr()
      if not parentPtr: return id(self)
      return int(self.__f(parentPtr)) or id(self)

    def __ne__(self, other):
      return not self.__eq__(other)

  class __MessagingManagerImpl(MessagingManager):
    def __init__(self, parent, f):
      # (don't call superclass __init__)
      self.__parent = parent
      self.__f = f
      _global_native_pointer_lookup[self._getNativePtr()] = self

    def _getNativePtr(self):
      parentPtr = self.__parent._getNativePtr()
      if not parentPtr: raise DestroyedObjectException()
      ptr = self.__f(parentPtr)
      if not ptr: _throwVncException("MessagingManager")
      return ptr

    def __eq__(self, other):
      return (isinstance(other, self.__class__)
        and hash(self) == hash(other))

    def __hash__(self):
      # After invalidation this object should only equal itself
      parentPtr = self.__parent._getNativePtr()
      if not parentPtr: return id(self)
      return int(self.__f(parentPtr)) or id(self)

    def __ne__(self, other):
      return not self.__eq__(other)

class Server(object):
  '''A VNC-compatible Server enabling a computer to be remotely controlled.
  '''
  def __init__(self, agent_path, is_service=False):
    '''Creates a Server, optionally running as a service.'''
    try:
      if agent_path is None:
        # If we pass a NULL pointer for agentPath to the SDK library, it will
        # look in the same directory as the running binary, ie python.exe!  This
        # is not what we want, we instead search in the application script's
        # directory.
        import __main__
        agent_path = os.path.dirname(os.path.abspath(__main__.__file__))
      else:
        agent_path = os.path.abspath(agent_path)
      # We also want to override the search-in-directory functionality of the
      # SDK, so that we search in the platform's correct subdirectory as well as
      # the base directory itself.
      if not os.path.exists(agent_path):
        raise Exception("agent_path is not a file or directory")
      if os.path.isdir(agent_path):
        agent_path = _find_binary(agent_path, 'vncagent')
    except Exception as e:
      _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', str(e))
      raise VncException("FileError", "Server.__init__()", str(e))
    agent_path = _encode_unicode(agent_path)
    self._nativePtr = Server.__nativeCreateService(agent_path) if is_service else Server.__nativeCreate(agent_path)
    if not self._nativePtr: _throwVncException("Server.__init__()")
    _global_native_pointer_lookup[self._nativePtr] = self

  #make sure that the following constructors are not created:
  # create
  # createService

  CaptureMethod = _create_enum("Server.CaptureMethod",
    '''Enumeration of screen capture methods.''',
    CAPTURE_OPTIMAL = 0,
    CAPTURE_FALLBACK = 1,
  )

  DisconnectFlags = _create_enum("Server.DisconnectFlags",
    '''Enumeration of disconnection flags.''',
    DISCONNECT_ALERT = 1,
    DISCONNECT_RECONNECT = 2,
  )

  EncryptionLevel = _create_enum("Server.EncryptionLevel",
    '''Enumeration of encryption levels.''',
    DEFAULT = 0,
    MAXIMUM = 1,
  )

  Permissions = _create_enum("Server.Permissions",
    '''Enumeration of session permissions that can be granted to a connecting
    Viewer.''',
    PERM_VIEW = 1,
    PERM_KEYBOARD = 2,
    PERM_POINTER = 4,
    PERM_CLIPBOARD = 8,
    PERM_ANNOTATION = 16,
    PERM_ALL = 2147483647,
  )

  class AgentCallback(object):
    class AgentCallbackImpl(_CT.Structure):
      _fields_ = [
        ("agentStarted", _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p)),
        ("agentStopped", _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p)),
      ]

    def __init__(self, agent_started=None, agent_stopped=None):
      if agent_started is not None:
        self.agent_started = agent_started

      if self.agent_started is not None and not callable(self.agent_started):
        raise TypeError('agent_started: callbacks must be callable')

      def _agent_started(_, server):
        try:
          rv = self.agent_started(_global_native_pointer_lookup[server])
          assert rv is None
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback agentStarted generated an uncaught exception: \'%s\'' % e)
          return None

      if agent_stopped is not None:
        self.agent_stopped = agent_stopped

      if self.agent_stopped is not None and not callable(self.agent_stopped):
        raise TypeError('agent_stopped: callbacks must be callable')

      def _agent_stopped(_, server):
        try:
          rv = self.agent_stopped(_global_native_pointer_lookup[server])
          assert rv is None
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback agentStopped generated an uncaught exception: \'%s\'' % e)
          return None

      self._server_agentcallback_callback = Server.AgentCallback.AgentCallbackImpl(
        _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p)(_agent_started if self.agent_started else 0),
        _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p)(_agent_stopped if self.agent_stopped else 0),
      )
      _global_native_pointer_lookup[_CT.addressof(self._server_agentcallback_callback)] = self

    agent_started = None
    agent_stopped = None

  class ConnectionCallback(object):
    class ConnectionCallbackImpl(_CT.Structure):
      _fields_ = [
        ("connectionStarted", _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_void_p)),
        ("connectionEnded", _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_void_p)),
      ]

    def __init__(self, connection_started=None, connection_ended=None):
      if connection_started is not None:
        self.connection_started = connection_started

      if self.connection_started is not None and not callable(self.connection_started):
        raise TypeError('connection_started: callbacks must be callable')

      def _connection_started(_, server, connection):
        connection = Connection(connection)
        try:
          rv = self.connection_started(_global_native_pointer_lookup[server], connection)
          assert rv is None
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback connectionStarted generated an uncaught exception: \'%s\'' % e)
          return None

      if connection_ended is not None:
        self.connection_ended = connection_ended

      if self.connection_ended is not None and not callable(self.connection_ended):
        raise TypeError('connection_ended: callbacks must be callable')

      def _connection_ended(_, server, connection):
        connection = Connection(connection)
        try:
          rv = self.connection_ended(_global_native_pointer_lookup[server], connection)
          assert rv is None
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback connectionEnded generated an uncaught exception: \'%s\'' % e)
          return None

      self._server_connectioncallback_callback = Server.ConnectionCallback.ConnectionCallbackImpl(
        _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_void_p)(_connection_started if self.connection_started else 0),
        _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_void_p)(_connection_ended if self.connection_ended else 0),
      )
      _global_native_pointer_lookup[_CT.addressof(self._server_connectioncallback_callback)] = self

    connection_started = None
    connection_ended = None

  class SecurityCallback(object):
    class SecurityCallbackImpl(_CT.Structure):
      _fields_ = [
        ("verifyPeer", _CT.CFUNCTYPE(_CT.c_int, _CT.c_void_p, _CT.c_void_p, _CT.c_void_p, _CT.c_char_p, _CT.c_void_p)),
        ("isUserNameRequired", _CT.CFUNCTYPE(_CT.c_int, _CT.c_void_p, _CT.c_void_p, _CT.c_void_p)),
        ("isPasswordRequired", _CT.CFUNCTYPE(_CT.c_int, _CT.c_void_p, _CT.c_void_p, _CT.c_void_p)),
        ("authenticateUser", _CT.CFUNCTYPE(_CT.c_int, _CT.c_void_p, _CT.c_void_p, _CT.c_void_p, _CT.c_char_p, _CT.c_char_p)),
      ]

    def __init__(self, verify_peer=None, is_user_name_required=None, is_password_required=None, authenticate_user=None):
      if verify_peer is not None:
        self.verify_peer = verify_peer

      if self.verify_peer is not None and not callable(self.verify_peer):
        raise TypeError('verify_peer: callbacks must be callable')

      def _verify_peer(_, server, connection, viewer_hex_fingerprint, viewer_rsa_public):
        connection = Connection(connection)
        viewer_hex_fingerprint = _decode_unicode(viewer_hex_fingerprint) if viewer_hex_fingerprint is not None else viewer_hex_fingerprint
        viewer_rsa_public = _global_native_pointer_lookup[viewer_rsa_public] if viewer_rsa_public in _global_native_pointer_lookup else ImmutableDataBuffer(viewer_rsa_public)
        try:
          rv = self.verify_peer(_global_native_pointer_lookup[server], connection, viewer_hex_fingerprint, viewer_rsa_public)
          rv = bool(rv)
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback verifyPeer generated an uncaught exception: \'%s\'' % e)
          return True

      if is_user_name_required is not None:
        self.is_user_name_required = is_user_name_required

      if self.is_user_name_required is not None and not callable(self.is_user_name_required):
        raise TypeError('is_user_name_required: callbacks must be callable')

      def _is_user_name_required(_, server, connection):
        connection = Connection(connection)
        try:
          rv = self.is_user_name_required(_global_native_pointer_lookup[server], connection)
          rv = bool(rv)
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback isUserNameRequired generated an uncaught exception: \'%s\'' % e)
          return True

      if is_password_required is not None:
        self.is_password_required = is_password_required

      if self.is_password_required is not None and not callable(self.is_password_required):
        raise TypeError('is_password_required: callbacks must be callable')

      def _is_password_required(_, server, connection):
        connection = Connection(connection)
        try:
          rv = self.is_password_required(_global_native_pointer_lookup[server], connection)
          rv = bool(rv)
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback isPasswordRequired generated an uncaught exception: \'%s\'' % e)
          return True

      if authenticate_user is not None:
        self.authenticate_user = authenticate_user

      if self.authenticate_user is None:
        raise ValueError('authenticate_user is a mandatory callback')
      elif not callable(self.authenticate_user):
        raise TypeError('authenticate_user: callbacks must be callable')

      def _authenticate_user(_, server, connection, username, password):
        connection = Connection(connection)
        username = _decode_unicode(username) if username is not None else username
        password = _decode_unicode(password) if password is not None else password
        try:
          rv = self.authenticate_user(_global_native_pointer_lookup[server], connection, username, password)
          rv = _enums_to_int(rv)
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback authenticateUser generated an uncaught exception: \'%s\'' % e)
          return None

      self._server_securitycallback_callback = Server.SecurityCallback.SecurityCallbackImpl(
        _CT.CFUNCTYPE(_CT.c_int, _CT.c_void_p, _CT.c_void_p, _CT.c_void_p, _CT.c_char_p, _CT.c_void_p)(_verify_peer if self.verify_peer else 0),
        _CT.CFUNCTYPE(_CT.c_int, _CT.c_void_p, _CT.c_void_p, _CT.c_void_p)(_is_user_name_required if self.is_user_name_required else 0),
        _CT.CFUNCTYPE(_CT.c_int, _CT.c_void_p, _CT.c_void_p, _CT.c_void_p)(_is_password_required if self.is_password_required else 0),
        _CT.CFUNCTYPE(_CT.c_int, _CT.c_void_p, _CT.c_void_p, _CT.c_void_p, _CT.c_char_p, _CT.c_char_p)(_authenticate_user if self.authenticate_user else 0),
      )
      _global_native_pointer_lookup[_CT.addressof(self._server_securitycallback_callback)] = self

    verify_peer = None
    is_user_name_required = None
    is_password_required = None
    authenticate_user = None

  def destroy(self):
    '''Destroys the Server.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeDestroy(self._getNativePtr())
    assert rv is None
    del _global_native_pointer_lookup[self._getNativePtr()]
    self._setNativePtr(None)

  def disconnect(self, connection, message, flags):
    '''Disconnects a particular Viewer, optionally specifying a message.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    if connection is None:
      raise ValueError('connection is a mandatory argument')
    else:
      connection_ = connection._getNativePtr()
      if not connection_: raise DestroyedObjectException()
    message = _encode_unicode(message, False)
    rv = self.__nativeDisconnect(self._getNativePtr(), connection_, message, _enums_to_int(flags))
    assert rv is None

  def disconnect_all(self, message, flags):
    '''Disconnects all Viewers, optionally specifying a message.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    message = _encode_unicode(message, False)
    rv = self.__nativeDisconnectAll(self._getNativePtr(), message, _enums_to_int(flags))
    assert rv is None

  def get_annotation_manager(self):
    return Server.__AnnotationManagerImpl(self, Server.__nativeGetAnnotationManager)

  def get_connection_count(self):
    '''Returns the total number of Viewers currently connected to the Server.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeGetConnectionCount(self._getNativePtr())
    return rv

  def get_connection_handler(self):
    return Server.__ConnectionHandlerImpl(self, Server.__nativeGetConnectionHandler)

  def get_display_manager(self):
    return Server.__DisplayManagerImpl(self, Server.__nativeGetDisplayManager)

  def get_encryption_level(self, connection):
    '''Returns the encryption level being used with an incoming connection,
    or the Server's current encryption level if the connection is ``None``.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    if connection is None:
      raise ValueError('connection is a mandatory argument')
    else:
      connection_ = connection._getNativePtr()
      if not connection_: raise DestroyedObjectException()
    rv = self.__nativeGetEncryptionLevel(self._getNativePtr(), connection_)
    return Server.EncryptionLevel(rv)

  def get_idle_timeout(self):
    '''Gets the current number of seconds to wait before disconnecting idle
    Viewers.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeGetIdleTimeout(self._getNativePtr())
    return rv

  def get_messaging_manager(self):
    return Server.__MessagingManagerImpl(self, Server.__nativeGetMessagingManager)

  def get_peer_address(self, connection):
    '''Returns the address of a particular connected Viewer.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    if connection is None:
      raise ValueError('connection is a mandatory argument')
    else:
      connection_ = connection._getNativePtr()
      if not connection_: raise DestroyedObjectException()
    rv = self.__nativeGetPeerAddress(self._getNativePtr(), connection_)
    if not rv: _throwVncException("Server.get_peer_address()")
    return _decode_unicode(rv)

  def get_permissions(self, connection):
    '''Gets the set of current permissions for a Viewer.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    if connection is None:
      raise ValueError('connection is a mandatory argument')
    else:
      connection_ = connection._getNativePtr()
      if not connection_: raise DestroyedObjectException()
    rv = self.__nativeGetPermissions(self._getNativePtr(), connection_)
    return _int_to_enums(rv, Server.Permissions)

  def is_agent_ready(self):
    '''Determines if the vncagent process is ready and available to capture the
    display and inject input events.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeIsAgentReady(self._getNativePtr())
    return bool(rv)

  def set_agent_callback(self, callback):
    '''Sets agent-related callbacks for the Server.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    callback_ = _CT.pointer(callback._server_agentcallback_callback) if callback is not None else None
    rv = self.__nativeSetAgentCallback(self._getNativePtr(), callback_, callback_)
    if rv == 0: _throwVncException("Server.set_agent_callback()")

  def set_blacklist(self, threshold, timeout):
    '''Specifies a blacklist threshold and timeout for the Server.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeSetBlacklist(self._getNativePtr(), threshold, timeout)
    if rv == 0: _throwVncException("Server.set_blacklist()")

  def set_capture_method(self, capture_method):
    '''Specifies the screen capture method used by the Server.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeSetCaptureMethod(self._getNativePtr(), capture_method.value)
    if rv == 0: _throwVncException("Server.set_capture_method()")

  def set_connection_callback(self, callback):
    '''Sets connection-related callbacks for the Server.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    callback_ = _CT.pointer(callback._server_connectioncallback_callback) if callback is not None else None
    rv = self.__nativeSetConnectionCallback(self._getNativePtr(), callback_, callback_)
    if rv == 0: _throwVncException("Server.set_connection_callback()")

  def set_encryption_level(self, level):
    '''Sets the desired encryption level of the session from the range of options
    enumerated by Server_EncryptionLevel.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeSetEncryptionLevel(self._getNativePtr(), level.value)
    if rv == 0: _throwVncException("Server.set_encryption_level()")

  def set_friendly_name(self, name):
    '''Specifies a friendly name for the Server, to send to connected Viewers.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    name = _encode_unicode(name, False)
    rv = self.__nativeSetFriendlyName(self._getNativePtr(), name)
    assert rv is None

  def set_idle_timeout(self, idle_timeout):
    '''Sets the number of seconds to wait before disconnecting idle Viewers.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeSetIdleTimeout(self._getNativePtr(), idle_timeout)
    if rv == 0: _throwVncException("Server.set_idle_timeout()")

  def set_permissions(self, connection, perms):
    '''Changes permissions for a Viewer mid-session.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    if connection is None:
      raise ValueError('connection is a mandatory argument')
    else:
      connection_ = connection._getNativePtr()
      if not connection_: raise DestroyedObjectException()
    rv = self.__nativeSetPermissions(self._getNativePtr(), connection_, _enums_to_int(perms))
    if rv == 0: _throwVncException("Server.set_permissions()")

  def set_security_callback(self, callback):
    '''Sets security-related callbacks for the Server.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    callback_ = _CT.pointer(callback._server_securitycallback_callback) if callback is not None else None
    rv = self.__nativeSetSecurityCallback(self._getNativePtr(), callback_, callback_)
    if rv == 0: _throwVncException("Server.set_security_callback()")

  __nativeCreate = SdkDll.register_class_function('vnc_Server_create', [_CT.c_char_p], _CT.c_void_p)
  __nativeCreateService = SdkDll.register_class_function('vnc_Server_createService', [_CT.c_char_p], _CT.c_void_p)
  __nativeDestroy = SdkDll.register_class_function('vnc_Server_destroy', [_CT.c_void_p], None)
  __nativeDisconnect = SdkDll.register_class_function('vnc_Server_disconnect', [_CT.c_void_p, _CT.c_void_p, _CT.c_char_p, _CT.c_int], None)
  __nativeDisconnectAll = SdkDll.register_class_function('vnc_Server_disconnectAll', [_CT.c_void_p, _CT.c_char_p, _CT.c_int], None)

  class __AnnotationManagerImpl(AnnotationManager):
    def __init__(self, parent, f):
      # (don't call superclass __init__)
      self.__parent = parent
      self.__f = f
      _global_native_pointer_lookup[self._getNativePtr()] = self

    def _getNativePtr(self):
      parentPtr = self.__parent._getNativePtr()
      if not parentPtr: raise DestroyedObjectException()
      ptr = self.__f(parentPtr)
      if not ptr: _throwVncException("AnnotationManager")
      return ptr

    def __eq__(self, other):
      return (isinstance(other, self.__class__)
        and hash(self) == hash(other))

    def __hash__(self):
      # After invalidation this object should only equal itself
      parentPtr = self.__parent._getNativePtr()
      if not parentPtr: return id(self)
      return int(self.__f(parentPtr)) or id(self)

    def __ne__(self, other):
      return not self.__eq__(other)

  __nativeGetAnnotationManager = SdkDll.register_class_function('vnc_Server_getAnnotationManager', [_CT.c_void_p], _CT.c_void_p)
  __nativeGetConnectionCount = SdkDll.register_class_function('vnc_Server_getConnectionCount', [_CT.c_void_p], _CT.c_int)

  class __ConnectionHandlerImpl(ConnectionHandler):
    def __init__(self, parent, f):
      # (don't call superclass __init__)
      self.__parent = parent
      self.__f = f
      _global_native_pointer_lookup[self._getNativePtr()] = self

    def _getNativePtr(self):
      parentPtr = self.__parent._getNativePtr()
      if not parentPtr: raise DestroyedObjectException()
      ptr = self.__f(parentPtr)
      if not ptr: _throwVncException("ConnectionHandler")
      return ptr

    def __eq__(self, other):
      return (isinstance(other, self.__class__)
        and hash(self) == hash(other))

    def __hash__(self):
      # After invalidation this object should only equal itself
      parentPtr = self.__parent._getNativePtr()
      if not parentPtr: return id(self)
      return int(self.__f(parentPtr)) or id(self)

    def __ne__(self, other):
      return not self.__eq__(other)

  __nativeGetConnectionHandler = SdkDll.register_class_function('vnc_Server_getConnectionHandler', [_CT.c_void_p], _CT.c_void_p)

  class __DisplayManagerImpl(DisplayManager):
    def __init__(self, parent, f):
      # (don't call superclass __init__)
      self.__parent = parent
      self.__f = f
      _global_native_pointer_lookup[self._getNativePtr()] = self

    def _getNativePtr(self):
      parentPtr = self.__parent._getNativePtr()
      if not parentPtr: raise DestroyedObjectException()
      ptr = self.__f(parentPtr)
      if not ptr: _throwVncException("DisplayManager")
      return ptr

    def __eq__(self, other):
      return (isinstance(other, self.__class__)
        and hash(self) == hash(other))

    def __hash__(self):
      # After invalidation this object should only equal itself
      parentPtr = self.__parent._getNativePtr()
      if not parentPtr: return id(self)
      return int(self.__f(parentPtr)) or id(self)

    def __ne__(self, other):
      return not self.__eq__(other)

  __nativeGetDisplayManager = SdkDll.register_class_function('vnc_Server_getDisplayManager', [_CT.c_void_p], _CT.c_void_p)
  __nativeGetEncryptionLevel = SdkDll.register_class_function('vnc_Server_getEncryptionLevel', [_CT.c_void_p, _CT.c_void_p], _CT.c_int)
  __nativeGetIdleTimeout = SdkDll.register_class_function('vnc_Server_getIdleTimeout', [_CT.c_void_p], _CT.c_int)

  class __MessagingManagerImpl(MessagingManager):
    def __init__(self, parent, f):
      # (don't call superclass __init__)
      self.__parent = parent
      self.__f = f
      _global_native_pointer_lookup[self._getNativePtr()] = self

    def _getNativePtr(self):
      parentPtr = self.__parent._getNativePtr()
      if not parentPtr: raise DestroyedObjectException()
      ptr = self.__f(parentPtr)
      if not ptr: _throwVncException("MessagingManager")
      return ptr

    def __eq__(self, other):
      return (isinstance(other, self.__class__)
        and hash(self) == hash(other))

    def __hash__(self):
      # After invalidation this object should only equal itself
      parentPtr = self.__parent._getNativePtr()
      if not parentPtr: return id(self)
      return int(self.__f(parentPtr)) or id(self)

    def __ne__(self, other):
      return not self.__eq__(other)

  __nativeGetMessagingManager = SdkDll.register_class_function('vnc_Server_getMessagingManager', [_CT.c_void_p], _CT.c_void_p)
  __nativeGetPeerAddress = SdkDll.register_class_function('vnc_Server_getPeerAddress', [_CT.c_void_p, _CT.c_void_p], _CT.c_char_p)
  __nativeGetPermissions = SdkDll.register_class_function('vnc_Server_getPermissions', [_CT.c_void_p, _CT.c_void_p], _CT.c_int)
  __nativeIsAgentReady = SdkDll.register_class_function('vnc_Server_isAgentReady', [_CT.c_void_p], _CT.c_int)
  __nativeSetAgentCallback = SdkDll.register_class_function('vnc_Server_setAgentCallback', [_CT.c_void_p, _CT.POINTER(AgentCallback.AgentCallbackImpl), _CT.c_void_p], _CT.c_int)
  __nativeSetBlacklist = SdkDll.register_class_function('vnc_Server_setBlacklist', [_CT.c_void_p, _CT.c_int, _CT.c_int], _CT.c_int)
  __nativeSetCaptureMethod = SdkDll.register_class_function('vnc_Server_setCaptureMethod', [_CT.c_void_p, _CT.c_int], _CT.c_int)
  __nativeSetConnectionCallback = SdkDll.register_class_function('vnc_Server_setConnectionCallback', [_CT.c_void_p, _CT.POINTER(ConnectionCallback.ConnectionCallbackImpl), _CT.c_void_p], _CT.c_int)
  __nativeSetEncryptionLevel = SdkDll.register_class_function('vnc_Server_setEncryptionLevel', [_CT.c_void_p, _CT.c_int], _CT.c_int)
  __nativeSetFriendlyName = SdkDll.register_class_function('vnc_Server_setFriendlyName', [_CT.c_void_p, _CT.c_char_p], None)
  __nativeSetIdleTimeout = SdkDll.register_class_function('vnc_Server_setIdleTimeout', [_CT.c_void_p, _CT.c_int], _CT.c_int)
  __nativeSetPermissions = SdkDll.register_class_function('vnc_Server_setPermissions', [_CT.c_void_p, _CT.c_void_p, _CT.c_int], _CT.c_int)
  __nativeSetSecurityCallback = SdkDll.register_class_function('vnc_Server_setSecurityCallback', [_CT.c_void_p, _CT.POINTER(SecurityCallback.SecurityCallbackImpl), _CT.c_void_p], _CT.c_int)
  def __del__(self):
    if hasattr(self, "_nativePtr") and self._nativePtr is not None:
      self.destroy()
  def __enter__(self):
    return self
  def __exit__(self, exc_type, exc_value, traceback):
    self.destroy()

  def _getNativePtr(self):
    return self._nativePtr
  def _setNativePtr(self, v):
    self._nativePtr = v


  class __AnnotationManagerImpl(AnnotationManager):
    def __init__(self, parent, f):
      # (don't call superclass __init__)
      self.__parent = parent
      self.__f = f
      _global_native_pointer_lookup[self._getNativePtr()] = self

    def _getNativePtr(self):
      parentPtr = self.__parent._getNativePtr()
      if not parentPtr: raise DestroyedObjectException()
      ptr = self.__f(parentPtr)
      if not ptr: _throwVncException("AnnotationManager")
      return ptr

    def __eq__(self, other):
      return (isinstance(other, self.__class__)
        and hash(self) == hash(other))

    def __hash__(self):
      # After invalidation this object should only equal itself
      parentPtr = self.__parent._getNativePtr()
      if not parentPtr: return id(self)
      return int(self.__f(parentPtr)) or id(self)

    def __ne__(self, other):
      return not self.__eq__(other)

  class __ConnectionHandlerImpl(ConnectionHandler):
    def __init__(self, parent, f):
      # (don't call superclass __init__)
      self.__parent = parent
      self.__f = f
      _global_native_pointer_lookup[self._getNativePtr()] = self

    def _getNativePtr(self):
      parentPtr = self.__parent._getNativePtr()
      if not parentPtr: raise DestroyedObjectException()
      ptr = self.__f(parentPtr)
      if not ptr: _throwVncException("ConnectionHandler")
      return ptr

    def __eq__(self, other):
      return (isinstance(other, self.__class__)
        and hash(self) == hash(other))

    def __hash__(self):
      # After invalidation this object should only equal itself
      parentPtr = self.__parent._getNativePtr()
      if not parentPtr: return id(self)
      return int(self.__f(parentPtr)) or id(self)

    def __ne__(self, other):
      return not self.__eq__(other)

  class __MessagingManagerImpl(MessagingManager):
    def __init__(self, parent, f):
      # (don't call superclass __init__)
      self.__parent = parent
      self.__f = f
      _global_native_pointer_lookup[self._getNativePtr()] = self

    def _getNativePtr(self):
      parentPtr = self.__parent._getNativePtr()
      if not parentPtr: raise DestroyedObjectException()
      ptr = self.__f(parentPtr)
      if not ptr: _throwVncException("MessagingManager")
      return ptr

    def __eq__(self, other):
      return (isinstance(other, self.__class__)
        and hash(self) == hash(other))

    def __hash__(self):
      # After invalidation this object should only equal itself
      parentPtr = self.__parent._getNativePtr()
      if not parentPtr: return id(self)
      return int(self.__f(parentPtr)) or id(self)

    def __ne__(self, other):
      return not self.__eq__(other)

class Viewer(object):
  '''A VNC-compatible Viewer showing the screen of and controlling a remote computer.
  '''
  #Overridden to match JavaScript bindings; we avoid the ugly
  #"get_viewer_fb_data().get_data()" chain in the bindings for languages which have
  #a native buffer type
  def get_viewer_fb_data(self, x, y, w, h):
    if not self._nativePtr: raise DestroyedObjectException()
    rv = self.__nativeGetViewerFbData(self._nativePtr, x, y, w, h)
    if rv == 0: _throwVncException("Viewer.getViewerFbData()")
    return _global_native_pointer_lookup[rv].get_data() if rv in _global_native_pointer_lookup else ImmutableDataBuffer(rv).get_data()

  ConnectionStatus = _create_enum("Viewer.ConnectionStatus",
    '''Enumeration of connection statuses.''',
    DISCONNECTED = 0,
    CONNECTING = 1,
    CONNECTED = 2,
    DISCONNECTING = 3,
  )

  DisconnectFlags = _create_enum("Viewer.DisconnectFlags",
    '''Enumeration of disconnection flags.''',
    ALERT_USER = 1,
    CAN_RECONNECT = 2,
  )

  EncryptionLevel = _create_enum("Viewer.EncryptionLevel",
    '''Enumeration of encryption levels.''',
    DEFAULT = 0,
    MAXIMUM = 1,
  )

  MouseButton = _create_enum("Viewer.MouseButton",
    '''Enumeration of mouse buttons.''',
    MOUSE_BUTTON_LEFT = 1,
    MOUSE_BUTTON_MIDDLE = 2,
    MOUSE_BUTTON_RIGHT = 4,
  )

  MouseWheel = _create_enum("Viewer.MouseWheel",
    '''Enumeration of mouse wheel directions.''',
    MOUSE_WHEEL_HORIZONTAL = 1,
    MOUSE_WHEEL_VERTICAL = 2,
  )

  PictureQuality = _create_enum("Viewer.PictureQuality",
    '''Enumeration of picture quality levels.''',
    AUTO = 0,
    HIGH = 1,
    MEDIUM = 2,
    LOW = 3,
  )

  class AuthenticationCallback(object):
    class AuthenticationCallbackImpl(_CT.Structure):
      _fields_ = [
        ("requestUserCredentials", _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_int, _CT.c_int)),
        ("cancelUserCredentialsRequest", _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p)),
      ]

    def __init__(self, request_user_credentials=None, cancel_user_credentials_request=None):
      if request_user_credentials is not None:
        self.request_user_credentials = request_user_credentials

      if self.request_user_credentials is None:
        raise ValueError('request_user_credentials is a mandatory callback')
      elif not callable(self.request_user_credentials):
        raise TypeError('request_user_credentials: callbacks must be callable')

      def _request_user_credentials(_, viewer, need_user, need_passwd):
        need_user = bool(need_user)
        need_passwd = bool(need_passwd)
        try:
          rv = self.request_user_credentials(_global_native_pointer_lookup[viewer], need_user, need_passwd)
          assert rv is None
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback requestUserCredentials generated an uncaught exception: \'%s\'' % e)
          return None

      if cancel_user_credentials_request is not None:
        self.cancel_user_credentials_request = cancel_user_credentials_request

      if self.cancel_user_credentials_request is not None and not callable(self.cancel_user_credentials_request):
        raise TypeError('cancel_user_credentials_request: callbacks must be callable')

      def _cancel_user_credentials_request(_, viewer):
        try:
          rv = self.cancel_user_credentials_request(_global_native_pointer_lookup[viewer])
          assert rv is None
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback cancelUserCredentialsRequest generated an uncaught exception: \'%s\'' % e)
          return None

      self._viewer_authenticationcallback_callback = Viewer.AuthenticationCallback.AuthenticationCallbackImpl(
        _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_int, _CT.c_int)(_request_user_credentials if self.request_user_credentials else 0),
        _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p)(_cancel_user_credentials_request if self.cancel_user_credentials_request else 0),
      )
      _global_native_pointer_lookup[_CT.addressof(self._viewer_authenticationcallback_callback)] = self

    request_user_credentials = None
    cancel_user_credentials_request = None

  class ConnectionCallback(object):
    class ConnectionCallbackImpl(_CT.Structure):
      _fields_ = [
        ("connecting", _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p)),
        ("connected", _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p)),
        ("disconnected", _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_char_p, _CT.c_int)),
      ]

    def __init__(self, connecting=None, connected=None, disconnected=None):
      if connecting is not None:
        self.connecting = connecting

      if self.connecting is not None and not callable(self.connecting):
        raise TypeError('connecting: callbacks must be callable')

      def _connecting(_, viewer):
        try:
          rv = self.connecting(_global_native_pointer_lookup[viewer])
          assert rv is None
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback connecting generated an uncaught exception: \'%s\'' % e)
          return None

      if connected is not None:
        self.connected = connected

      if self.connected is not None and not callable(self.connected):
        raise TypeError('connected: callbacks must be callable')

      def _connected(_, viewer):
        try:
          rv = self.connected(_global_native_pointer_lookup[viewer])
          assert rv is None
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback connected generated an uncaught exception: \'%s\'' % e)
          return None

      if disconnected is not None:
        self.disconnected = disconnected

      if self.disconnected is not None and not callable(self.disconnected):
        raise TypeError('disconnected: callbacks must be callable')

      def _disconnected(_, viewer, reason, flags):
        reason = _decode_unicode(reason) if reason is not None else reason
        flags = _int_to_enums(flags, Viewer.DisconnectFlags)
        try:
          rv = self.disconnected(_global_native_pointer_lookup[viewer], reason, flags)
          assert rv is None
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback disconnected generated an uncaught exception: \'%s\'' % e)
          return None

      self._viewer_connectioncallback_callback = Viewer.ConnectionCallback.ConnectionCallbackImpl(
        _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p)(_connecting if self.connecting else 0),
        _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p)(_connected if self.connected else 0),
        _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_char_p, _CT.c_int)(_disconnected if self.disconnected else 0),
      )
      _global_native_pointer_lookup[_CT.addressof(self._viewer_connectioncallback_callback)] = self

    connecting = None
    connected = None
    disconnected = None

  class FramebufferCallback(object):
    class FramebufferCallbackImpl(_CT.Structure):
      _fields_ = [
        ("serverFbSizeChanged", _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_int, _CT.c_int)),
        ("viewerFbUpdated", _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_int, _CT.c_int, _CT.c_int, _CT.c_int)),
      ]

    def __init__(self, server_fb_size_changed=None, viewer_fb_updated=None):
      if server_fb_size_changed is not None:
        self.server_fb_size_changed = server_fb_size_changed

      if self.server_fb_size_changed is not None and not callable(self.server_fb_size_changed):
        raise TypeError('server_fb_size_changed: callbacks must be callable')

      def _server_fb_size_changed(_, viewer, w, h):
        try:
          rv = self.server_fb_size_changed(_global_native_pointer_lookup[viewer], w, h)
          assert rv is None
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback serverFbSizeChanged generated an uncaught exception: \'%s\'' % e)
          return None

      if viewer_fb_updated is not None:
        self.viewer_fb_updated = viewer_fb_updated

      if self.viewer_fb_updated is not None and not callable(self.viewer_fb_updated):
        raise TypeError('viewer_fb_updated: callbacks must be callable')

      def _viewer_fb_updated(_, viewer, x, y, w, h):
        try:
          rv = self.viewer_fb_updated(_global_native_pointer_lookup[viewer], x, y, w, h)
          assert rv is None
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback viewerFbUpdated generated an uncaught exception: \'%s\'' % e)
          return None

      self._viewer_framebuffercallback_callback = Viewer.FramebufferCallback.FramebufferCallbackImpl(
        _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_int, _CT.c_int)(_server_fb_size_changed if self.server_fb_size_changed else 0),
        _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_int, _CT.c_int, _CT.c_int, _CT.c_int)(_viewer_fb_updated if self.viewer_fb_updated else 0),
      )
      _global_native_pointer_lookup[_CT.addressof(self._viewer_framebuffercallback_callback)] = self

    server_fb_size_changed = None
    viewer_fb_updated = None

  class PeerVerificationCallback(object):
    class PeerVerificationCallbackImpl(_CT.Structure):
      _fields_ = [
        ("verifyPeer", _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_char_p, _CT.c_char_p, _CT.c_void_p)),
        ("cancelPeerVerification", _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p)),
      ]

    def __init__(self, verify_peer=None, cancel_peer_verification=None):
      if verify_peer is not None:
        self.verify_peer = verify_peer

      if self.verify_peer is None:
        raise ValueError('verify_peer is a mandatory callback')
      elif not callable(self.verify_peer):
        raise TypeError('verify_peer: callbacks must be callable')

      def _verify_peer(_, viewer, hex_fingerprint, catchphrase_fingerprint, server_rsa_public):
        hex_fingerprint = _decode_unicode(hex_fingerprint) if hex_fingerprint is not None else hex_fingerprint
        catchphrase_fingerprint = _decode_unicode(catchphrase_fingerprint) if catchphrase_fingerprint is not None else catchphrase_fingerprint
        server_rsa_public = _global_native_pointer_lookup[server_rsa_public] if server_rsa_public in _global_native_pointer_lookup else ImmutableDataBuffer(server_rsa_public)
        try:
          rv = self.verify_peer(_global_native_pointer_lookup[viewer], hex_fingerprint, catchphrase_fingerprint, server_rsa_public)
          assert rv is None
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback verifyPeer generated an uncaught exception: \'%s\'' % e)
          return None

      if cancel_peer_verification is not None:
        self.cancel_peer_verification = cancel_peer_verification

      if self.cancel_peer_verification is not None and not callable(self.cancel_peer_verification):
        raise TypeError('cancel_peer_verification: callbacks must be callable')

      def _cancel_peer_verification(_, viewer):
        try:
          rv = self.cancel_peer_verification(_global_native_pointer_lookup[viewer])
          assert rv is None
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback cancelPeerVerification generated an uncaught exception: \'%s\'' % e)
          return None

      self._viewer_peerverificationcallback_callback = Viewer.PeerVerificationCallback.PeerVerificationCallbackImpl(
        _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_char_p, _CT.c_char_p, _CT.c_void_p)(_verify_peer if self.verify_peer else 0),
        _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p)(_cancel_peer_verification if self.cancel_peer_verification else 0),
      )
      _global_native_pointer_lookup[_CT.addressof(self._viewer_peerverificationcallback_callback)] = self

    verify_peer = None
    cancel_peer_verification = None

  class ServerEventCallback(object):
    class ServerEventCallbackImpl(_CT.Structure):
      _fields_ = [
        ("serverClipboardTextChanged", _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_char_p)),
        ("serverFriendlyNameChanged", _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_char_p)),
      ]

    def __init__(self, server_clipboard_text_changed=None, server_friendly_name_changed=None):
      if server_clipboard_text_changed is not None:
        self.server_clipboard_text_changed = server_clipboard_text_changed

      if self.server_clipboard_text_changed is not None and not callable(self.server_clipboard_text_changed):
        raise TypeError('server_clipboard_text_changed: callbacks must be callable')

      def _server_clipboard_text_changed(_, viewer, text):
        text = _decode_unicode(text) if text is not None else text
        try:
          rv = self.server_clipboard_text_changed(_global_native_pointer_lookup[viewer], text)
          assert rv is None
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback serverClipboardTextChanged generated an uncaught exception: \'%s\'' % e)
          return None

      if server_friendly_name_changed is not None:
        self.server_friendly_name_changed = server_friendly_name_changed

      if self.server_friendly_name_changed is not None and not callable(self.server_friendly_name_changed):
        raise TypeError('server_friendly_name_changed: callbacks must be callable')

      def _server_friendly_name_changed(_, viewer, name):
        name = _decode_unicode(name) if name is not None else name
        try:
          rv = self.server_friendly_name_changed(_global_native_pointer_lookup[viewer], name)
          assert rv is None
          return rv
        except BaseException as e:
          _Private.logger_write(Logger.Level.ERROR, 'PythonSDK', 'callback serverFriendlyNameChanged generated an uncaught exception: \'%s\'' % e)
          return None

      self._viewer_servereventcallback_callback = Viewer.ServerEventCallback.ServerEventCallbackImpl(
        _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_char_p)(_server_clipboard_text_changed if self.server_clipboard_text_changed else 0),
        _CT.CFUNCTYPE(None, _CT.c_void_p, _CT.c_void_p, _CT.c_char_p)(_server_friendly_name_changed if self.server_friendly_name_changed else 0),
      )
      _global_native_pointer_lookup[_CT.addressof(self._viewer_servereventcallback_callback)] = self

    server_clipboard_text_changed = None
    server_friendly_name_changed = None

  def __init__(self):
    '''Creates and returns a new viewer.
    '''
    rv = self._nativePtr = Viewer.__nativeCreate()
    if not self._getNativePtr(): _throwVncException("Viewer.__init__()")
    _global_native_pointer_lookup[self._getNativePtr()] = self

  def destroy(self):
    '''Destroys the viewer.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeDestroy(self._getNativePtr())
    assert rv is None
    del _global_native_pointer_lookup[self._getNativePtr()]
    self._setNativePtr(None)

  def disconnect(self):
    '''Disconnects this viewer from the server.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeDisconnect(self._getNativePtr())
    if rv == 0: _throwVncException("Viewer.disconnect()")

  def get_annotation_manager(self):
    return Viewer.__AnnotationManagerImpl(self, Viewer.__nativeGetAnnotationManager)

  def get_connection_handler(self):
    return Viewer.__ConnectionHandlerImpl(self, Viewer.__nativeGetConnectionHandler)

  def get_connection_status(self):
    '''Returns the status of the viewer's connection.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeGetConnectionStatus(self._getNativePtr())
    return Viewer.ConnectionStatus(rv)

  def get_disconnect_message(self):
    '''Returns a human-readable message sent by the server for the last
    disconnection, or ``None`` if the last disconnection was not initiated by the
    server.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeGetDisconnectMessage(self._getNativePtr())
    return _decode_unicode(rv) if rv is not None else rv

  def get_disconnect_reason(self):
    '''Returns a string ID representing the reason for the last viewer
    disconnection.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeGetDisconnectReason(self._getNativePtr())
    return _decode_unicode(rv) if rv is not None else rv

  def get_encryption_level(self):
    '''Returns the Viewer's current encryption level.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeGetEncryptionLevel(self._getNativePtr())
    return Viewer.EncryptionLevel(rv)

  def get_messaging_manager(self):
    return Viewer.__MessagingManagerImpl(self, Viewer.__nativeGetMessagingManager)

  def get_peer_address(self):
    '''Returns the address of the viewer's server.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeGetPeerAddress(self._getNativePtr())
    if not rv: _throwVncException("Viewer.get_peer_address()")
    return _decode_unicode(rv)

  def get_picture_quality(self):
    '''Returns the viewer's current picture quality.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeGetPictureQuality(self._getNativePtr())
    return Viewer.PictureQuality(rv)

  def get_viewer_fb_height(self):
    '''Gets the height of the viewer framebuffer.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeGetViewerFbHeight(self._getNativePtr())
    return rv

  def get_viewer_fb_pixel_format(self):
    '''Gets the pixel format of the viewer framebuffer.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeGetViewerFbPixelFormat(self._getNativePtr())
    if rv == 0: _throwVncException("Viewer.get_viewer_fb_pixel_format()")
    return _global_native_pointer_lookup[rv] if rv in _global_native_pointer_lookup else ImmutablePixelFormat(rv)

  def get_viewer_fb_stride(self):
    '''Returns the stride of the viewer framebuffer data in pixels, that is, the
    number of pixels from the start of each row until the start of the next.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeGetViewerFbStride(self._getNativePtr())
    return rv

  def get_viewer_fb_width(self):
    '''Gets the width of the viewer framebuffer.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeGetViewerFbWidth(self._getNativePtr())
    return rv

  def release_all_keys(self):
    '''Send key up events for all currently pressed keys.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeReleaseAllKeys(self._getNativePtr())
    if rv == 0: _throwVncException("Viewer.release_all_keys()")

  def send_authentication_response(self, ok, user, passwd):
    '''Provides the SDK with the result of a username/password request.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    user = _encode_unicode(user, True)
    passwd = _encode_unicode(passwd, True)
    rv = self.__nativeSendAuthenticationResponse(self._getNativePtr(), bool(ok), user, passwd)
    if rv == 0: _throwVncException("Viewer.send_authentication_response()")

  def send_clipboard_text(self, text):
    '''Copies the given text to the server's clipboard.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    text = _encode_unicode(text, False)
    rv = self.__nativeSendClipboardText(self._getNativePtr(), text)
    if rv == 0: _throwVncException("Viewer.send_clipboard_text()")

  def send_key_down(self, keysym, key_code):
    '''Sends a key down (press) event to the server.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    if keysym < 0 or keysym > 0x7fffffff:
      raise IndexError("keysym out of bounds")

    rv = self.__nativeSendKeyDown(self._getNativePtr(), keysym, key_code)
    if rv == 0: _throwVncException("Viewer.send_key_down()")

  def send_key_up(self, key_code):
    '''Sends a key up (release) event to the server.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeSendKeyUp(self._getNativePtr(), key_code)
    if rv == 0: _throwVncException("Viewer.send_key_up()")

  def send_peer_verification_response(self, ok):
    '''Provides the SDK with the response to the
    Viewer.PeerVerificationCallback.verifyPeer() request.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeSendPeerVerificationResponse(self._getNativePtr(), bool(ok))
    if rv == 0: _throwVncException("Viewer.send_peer_verification_response()")

  def send_pointer_event(self, x, y, button_state, rel):
    '''Sends a pointer event to the server.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeSendPointerEvent(self._getNativePtr(), x, y, _enums_to_int(button_state), bool(rel))
    if rv == 0: _throwVncException("Viewer.send_pointer_event()")

  def send_scroll_event(self, delta, axis):
    '''Sends a scroll wheel event to the server.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeSendScrollEvent(self._getNativePtr(), delta, axis.value)
    if rv == 0: _throwVncException("Viewer.send_scroll_event()")

  def set_authentication_callback(self, callback):
    '''Sets the callback to be called when a username and/or password is required.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    callback_ = _CT.pointer(callback._viewer_authenticationcallback_callback) if callback is not None else None
    rv = self.__nativeSetAuthenticationCallback(self._getNativePtr(), callback_, callback_)
    if rv == 0: _throwVncException("Viewer.set_authentication_callback()")

  def set_connection_callback(self, callback):
    '''Sets the callbacks for the Viewer to call when various events occur during
    its lifetime.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    callback_ = _CT.pointer(callback._viewer_connectioncallback_callback) if callback is not None else None
    rv = self.__nativeSetConnectionCallback(self._getNativePtr(), callback_, callback_)
    if rv == 0: _throwVncException("Viewer.set_connection_callback()")

  def set_encryption_level(self, level):
    '''Sets the desired encryption level of the session from the range of options
    enumerated by Viewer_EncryptionLevel.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeSetEncryptionLevel(self._getNativePtr(), level.value)
    if rv == 0: _throwVncException("Viewer.set_encryption_level()")

  def set_framebuffer_callback(self, callback):
    '''Sets the framebuffer callback for this viewer.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    callback_ = _CT.pointer(callback._viewer_framebuffercallback_callback) if callback is not None else None
    rv = self.__nativeSetFramebufferCallback(self._getNativePtr(), callback_, callback_)
    if rv == 0: _throwVncException("Viewer.set_framebuffer_callback()")

  def set_peer_verification_callback(self, callback):
    '''Sets the callbacks to be called to verify the identity of the peer (server).
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    callback_ = _CT.pointer(callback._viewer_peerverificationcallback_callback) if callback is not None else None
    rv = self.__nativeSetPeerVerificationCallback(self._getNativePtr(), callback_, callback_)
    if rv == 0: _throwVncException("Viewer.set_peer_verification_callback()")

  def set_picture_quality(self, quality):
    '''Sets the desired picture quality of the session from the range of options
    enumerated by Viewer_PictureQuality.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    rv = self.__nativeSetPictureQuality(self._getNativePtr(), quality.value)
    if rv == 0: _throwVncException("Viewer.set_picture_quality()")

  def set_server_event_callback(self, callback):
    '''Sets the server event callback for this viewer.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    callback_ = _CT.pointer(callback._viewer_servereventcallback_callback) if callback is not None else None
    rv = self.__nativeSetServerEventCallback(self._getNativePtr(), callback_, callback_)
    if rv == 0: _throwVncException("Viewer.set_server_event_callback()")

  def set_viewer_fb(self, pixels, pf, width, height, stride):
    '''Sets the viewer framebuffer.
    '''
    if not self._getNativePtr(): raise DestroyedObjectException()
    if pixels is not None:
      pixels_view = memoryview(pixels)
      if pixels_view.readonly: raise TypeError("pixels must be writable")
      pixels = (_CT.c_char * len(pixels)).from_buffer(pixels)
    pf_ = pf._getNativePtr()
    if not pf_: raise DestroyedObjectException()
    rv = self.__nativeSetViewerFb(self._getNativePtr(), pixels, len(pixels) if pixels else 0, pf_, width, height, stride)
    if rv == 0: _throwVncException("Viewer.set_viewer_fb()")

  __nativeCreate = SdkDll.register_class_function('vnc_Viewer_create', [], _CT.c_void_p)
  __nativeDestroy = SdkDll.register_class_function('vnc_Viewer_destroy', [_CT.c_void_p], None)
  __nativeDisconnect = SdkDll.register_class_function('vnc_Viewer_disconnect', [_CT.c_void_p], _CT.c_int)

  class __AnnotationManagerImpl(AnnotationManager):
    def __init__(self, parent, f):
      # (don't call superclass __init__)
      self.__parent = parent
      self.__f = f
      _global_native_pointer_lookup[self._getNativePtr()] = self

    def _getNativePtr(self):
      parentPtr = self.__parent._getNativePtr()
      if not parentPtr: raise DestroyedObjectException()
      ptr = self.__f(parentPtr)
      if not ptr: _throwVncException("AnnotationManager")
      return ptr

    def __eq__(self, other):
      return (isinstance(other, self.__class__)
        and hash(self) == hash(other))

    def __hash__(self):
      # After invalidation this object should only equal itself
      parentPtr = self.__parent._getNativePtr()
      if not parentPtr: return id(self)
      return int(self.__f(parentPtr)) or id(self)

    def __ne__(self, other):
      return not self.__eq__(other)

  __nativeGetAnnotationManager = SdkDll.register_class_function('vnc_Viewer_getAnnotationManager', [_CT.c_void_p], _CT.c_void_p)

  class __ConnectionHandlerImpl(ConnectionHandler):
    def __init__(self, parent, f):
      # (don't call superclass __init__)
      self.__parent = parent
      self.__f = f
      _global_native_pointer_lookup[self._getNativePtr()] = self

    def _getNativePtr(self):
      parentPtr = self.__parent._getNativePtr()
      if not parentPtr: raise DestroyedObjectException()
      ptr = self.__f(parentPtr)
      if not ptr: _throwVncException("ConnectionHandler")
      return ptr

    def __eq__(self, other):
      return (isinstance(other, self.__class__)
        and hash(self) == hash(other))

    def __hash__(self):
      # After invalidation this object should only equal itself
      parentPtr = self.__parent._getNativePtr()
      if not parentPtr: return id(self)
      return int(self.__f(parentPtr)) or id(self)

    def __ne__(self, other):
      return not self.__eq__(other)

  __nativeGetConnectionHandler = SdkDll.register_class_function('vnc_Viewer_getConnectionHandler', [_CT.c_void_p], _CT.c_void_p)
  __nativeGetConnectionStatus = SdkDll.register_class_function('vnc_Viewer_getConnectionStatus', [_CT.c_void_p], _CT.c_int)
  __nativeGetDisconnectMessage = SdkDll.register_class_function('vnc_Viewer_getDisconnectMessage', [_CT.c_void_p], _CT.c_char_p)
  __nativeGetDisconnectReason = SdkDll.register_class_function('vnc_Viewer_getDisconnectReason', [_CT.c_void_p], _CT.c_char_p)
  __nativeGetEncryptionLevel = SdkDll.register_class_function('vnc_Viewer_getEncryptionLevel', [_CT.c_void_p], _CT.c_int)

  class __MessagingManagerImpl(MessagingManager):
    def __init__(self, parent, f):
      # (don't call superclass __init__)
      self.__parent = parent
      self.__f = f
      _global_native_pointer_lookup[self._getNativePtr()] = self

    def _getNativePtr(self):
      parentPtr = self.__parent._getNativePtr()
      if not parentPtr: raise DestroyedObjectException()
      ptr = self.__f(parentPtr)
      if not ptr: _throwVncException("MessagingManager")
      return ptr

    def __eq__(self, other):
      return (isinstance(other, self.__class__)
        and hash(self) == hash(other))

    def __hash__(self):
      # After invalidation this object should only equal itself
      parentPtr = self.__parent._getNativePtr()
      if not parentPtr: return id(self)
      return int(self.__f(parentPtr)) or id(self)

    def __ne__(self, other):
      return not self.__eq__(other)

  __nativeGetMessagingManager = SdkDll.register_class_function('vnc_Viewer_getMessagingManager', [_CT.c_void_p], _CT.c_void_p)
  __nativeGetPeerAddress = SdkDll.register_class_function('vnc_Viewer_getPeerAddress', [_CT.c_void_p], _CT.c_char_p)
  __nativeGetPictureQuality = SdkDll.register_class_function('vnc_Viewer_getPictureQuality', [_CT.c_void_p], _CT.c_int)
  __nativeGetViewerFbData = SdkDll.register_class_function('vnc_Viewer_getViewerFbData', [_CT.c_void_p, _CT.c_int, _CT.c_int, _CT.c_int, _CT.c_int], _CT.c_void_p)
  __nativeGetViewerFbHeight = SdkDll.register_class_function('vnc_Viewer_getViewerFbHeight', [_CT.c_void_p], _CT.c_int)
  __nativeGetViewerFbPixelFormat = SdkDll.register_class_function('vnc_Viewer_getViewerFbPixelFormat', [_CT.c_void_p], _CT.c_void_p)
  __nativeGetViewerFbStride = SdkDll.register_class_function('vnc_Viewer_getViewerFbStride', [_CT.c_void_p], _CT.c_int)
  __nativeGetViewerFbWidth = SdkDll.register_class_function('vnc_Viewer_getViewerFbWidth', [_CT.c_void_p], _CT.c_int)
  __nativeReleaseAllKeys = SdkDll.register_class_function('vnc_Viewer_releaseAllKeys', [_CT.c_void_p], _CT.c_int)
  __nativeSendAuthenticationResponse = SdkDll.register_class_function('vnc_Viewer_sendAuthenticationResponse', [_CT.c_void_p, _CT.c_int, _CT.c_char_p, _CT.c_char_p], _CT.c_int)
  __nativeSendClipboardText = SdkDll.register_class_function('vnc_Viewer_sendClipboardText', [_CT.c_void_p, _CT.c_char_p], _CT.c_int)
  __nativeSendKeyDown = SdkDll.register_class_function('vnc_Viewer_sendKeyDown', [_CT.c_void_p, _CT.c_uint, _CT.c_int], _CT.c_int)
  __nativeSendKeyUp = SdkDll.register_class_function('vnc_Viewer_sendKeyUp', [_CT.c_void_p, _CT.c_int], _CT.c_int)
  __nativeSendPeerVerificationResponse = SdkDll.register_class_function('vnc_Viewer_sendPeerVerificationResponse', [_CT.c_void_p, _CT.c_int], _CT.c_int)
  __nativeSendPointerEvent = SdkDll.register_class_function('vnc_Viewer_sendPointerEvent', [_CT.c_void_p, _CT.c_int, _CT.c_int, _CT.c_int, _CT.c_int], _CT.c_int)
  __nativeSendScrollEvent = SdkDll.register_class_function('vnc_Viewer_sendScrollEvent', [_CT.c_void_p, _CT.c_int, _CT.c_int], _CT.c_int)
  __nativeSetAuthenticationCallback = SdkDll.register_class_function('vnc_Viewer_setAuthenticationCallback', [_CT.c_void_p, _CT.POINTER(AuthenticationCallback.AuthenticationCallbackImpl), _CT.c_void_p], _CT.c_int)
  __nativeSetConnectionCallback = SdkDll.register_class_function('vnc_Viewer_setConnectionCallback', [_CT.c_void_p, _CT.POINTER(ConnectionCallback.ConnectionCallbackImpl), _CT.c_void_p], _CT.c_int)
  __nativeSetEncryptionLevel = SdkDll.register_class_function('vnc_Viewer_setEncryptionLevel', [_CT.c_void_p, _CT.c_int], _CT.c_int)
  __nativeSetFramebufferCallback = SdkDll.register_class_function('vnc_Viewer_setFramebufferCallback', [_CT.c_void_p, _CT.POINTER(FramebufferCallback.FramebufferCallbackImpl), _CT.c_void_p], _CT.c_int)
  __nativeSetPeerVerificationCallback = SdkDll.register_class_function('vnc_Viewer_setPeerVerificationCallback', [_CT.c_void_p, _CT.POINTER(PeerVerificationCallback.PeerVerificationCallbackImpl), _CT.c_void_p], _CT.c_int)
  __nativeSetPictureQuality = SdkDll.register_class_function('vnc_Viewer_setPictureQuality', [_CT.c_void_p, _CT.c_int], _CT.c_int)
  __nativeSetServerEventCallback = SdkDll.register_class_function('vnc_Viewer_setServerEventCallback', [_CT.c_void_p, _CT.POINTER(ServerEventCallback.ServerEventCallbackImpl), _CT.c_void_p], _CT.c_int)
  __nativeSetViewerFb = SdkDll.register_class_function('vnc_Viewer_setViewerFb', [_CT.c_void_p, _CT.c_char_p, _CT.c_int, _CT.c_void_p, _CT.c_int, _CT.c_int, _CT.c_int], _CT.c_int)
  def __del__(self):
    if hasattr(self, "_nativePtr") and self._nativePtr is not None:
      self.destroy()
  def __enter__(self):
    return self
  def __exit__(self, exc_type, exc_value, traceback):
    self.destroy()

  def _getNativePtr(self):
    return self._nativePtr
  def _setNativePtr(self, v):
    self._nativePtr = v


class Keyboard(object):
  XK_Alt_L = 0xffe9
  XK_Alt_R = 0xffea
  XK_BackSpace = 0xff08
  XK_Break = 0xff6b
  XK_Control_L = 0xffe3
  XK_Control_R = 0xffe4
  XK_Delete = 0xffff
  XK_Down = 0xff54
  XK_End = 0xff57
  XK_Escape = 0xff1b
  XK_F1 = 0xffbe
  XK_F10 = 0xffc7
  XK_F11 = 0xffc8
  XK_F12 = 0xffc9
  XK_F2 = 0xffbf
  XK_F3 = 0xffc0
  XK_F4 = 0xffc1
  XK_F5 = 0xffc2
  XK_F6 = 0xffc3
  XK_F7 = 0xffc4
  XK_F8 = 0xffc5
  XK_F9 = 0xffc6
  XK_Home = 0xff50
  XK_ISO_Level3_Shift = 0xfe03
  XK_Insert = 0xff63
  XK_KP_0 = 0xffb0
  XK_KP_1 = 0xffb1
  XK_KP_2 = 0xffb2
  XK_KP_3 = 0xffb3
  XK_KP_4 = 0xffb4
  XK_KP_5 = 0xffb5
  XK_KP_6 = 0xffb6
  XK_KP_7 = 0xffb7
  XK_KP_8 = 0xffb8
  XK_KP_9 = 0xffb9
  XK_KP_Add = 0xffab
  XK_KP_Decimal = 0xffae
  XK_KP_Delete = 0xff9f
  XK_KP_Divide = 0xffaf
  XK_KP_Down = 0xff99
  XK_KP_End = 0xff9c
  XK_KP_Enter = 0xff8d
  XK_KP_Home = 0xff95
  XK_KP_Insert = 0xff9e
  XK_KP_Left = 0xff96
  XK_KP_Multiply = 0xffaa
  XK_KP_Page_Down = 0xff9b
  XK_KP_Page_Up = 0xff9a
  XK_KP_Right = 0xff98
  XK_KP_Separator = 0xffac
  XK_KP_Subtract = 0xffad
  XK_KP_Up = 0xff97
  XK_Left = 0xff51
  XK_Menu = 0xff67
  XK_Page_Down = 0xff56
  XK_Page_Up = 0xff55
  XK_Pause = 0xff13
  XK_Print = 0xff61
  XK_Return = 0xff0d
  XK_Right = 0xff53
  XK_Scroll_Lock = 0xff14
  XK_Shift_L = 0xffe1
  XK_Shift_R = 0xffe2
  XK_Super_L = 0xffeb
  XK_Super_R = 0xffec
  XK_Sys_Req = 0xff15
  XK_Tab = 0xff09
  XK_Up = 0xff52
  def __init__(self): pass

class DirectTcp(object):
  DEFAULT_PORT = 5900
  def __init__(self): pass

