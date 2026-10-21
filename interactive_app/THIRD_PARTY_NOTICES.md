# Third-party components

Light Interaction bundles these open-source components and offline models:

- MediaPipe and Google's Face Landmarker / Hand Landmarker models: Apache-2.0.
  Source: https://github.com/google-ai-edge/mediapipe
  Models: https://developers.google.com/edge/mediapipe/solutions/vision
- OpenCV: Apache-2.0. https://github.com/opencv/opencv
- NumPy: BSD-3-Clause. https://github.com/numpy/numpy
- PySide6 / Qt: LGPL-3.0 / GPL-3.0 / commercial, as applicable to each module.
  This application uses dynamically bundled Qt libraries; their license texts
  accompany the app under Resources/licenses. Qt source and LGPL information:
  https://www.qt.io/licensing/open-source-lgpl-obligations
  https://download.qt.io/official_releases/qt/
- PyObjC: MIT. https://github.com/ronaldoussoren/pyobjc
- Windows only: pygrabber (MIT), comtypes (MIT), DirectShow device enumeration.
  https://github.com/andreaschiavinato/python_grabber
  https://github.com/enthought/comtypes
- Python: PSF license. https://www.python.org/psf/license/
- PyInstaller: GPL-2.0 with the bootloader exception permitting bundled apps.
  https://pyinstaller.org/en/stable/license.html

Camera images are processed in memory. The application does not upload images
or retain camera recordings. Diagnostic logs contain operational errors only.

For the Windows portable/installed build, license texts are in `_internal/licenses`.
Qt DLLs remain dynamic and replaceable; complete application source and build
instructions are available at https://github.com/unravel-xu/yoga .
