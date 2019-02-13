# Copyright (C) 2016-2017 RealVNC Limited. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors
# may be used to endorse or promote products derived from this software without
# specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# Note this sample makes use of PySide, which is licensed under the terms of
# the LGPL v2.1.

"""
The "Preferences" dialog box.
"""

from PySide import QtGui, QtCore


class PreferencesDialog(QtGui.QDialog):
    """
    The "Preferences" dialog box, for modifying viewer preferences.
    """

    DEFAULT_WINDOW_TITLE = "richViewerPython - Preferences"
    IMAGE_WINDOW = "icons/application.png"

    # Signals
    onAnnotationPreferenceChanged = QtCore.Signal()
    onPictureQualityPreferenceChanged = QtCore.Signal()

    # Drop down text for durations
    # Text, time (ms)
    _defaultDurationIndex = 1
    _availableDurations = [("Short (2 sec)", 2000),
                           ("Medium (5 sec)", 5000),
                           ("Long (10 sec)", 10000)]

    # Drop down text for fade durations
    # Text, time(ms)
    _defaultFadeDurationIndex = 1
    _availableFadeDurations = [("Instant (0 sec)", 0),
                               ("Fast (0.5 sec)", 500),
                               ("Medium (1 sec)", 1000),
                               ("Slow (2 sec)", 2000)]

    # Drop down text for annotation pen sizes
    _defaultPenSizeIndex = 1
    _availablePenSizes = [("Small (5 DIP)", 5),
                          ("Medium (10 DIP)", 10),
                          ("Large (15 DIP)", 15)]

    # Drop down text for picture quality
    _defaultPictureQualityIndex = 0
    _availablePictureQualitySettings = [("Auto", "AUTO"),
                                        ("Low", "LOW"),
                                        ("Medium", "MEDIUM"),
                                        ("High", "HIGH")]

    # Drop down text for encryption level
    _defaultEncryptionLevelIndex = 0
    _availableEncryptionLevels = [("Default", "DEFAULT"),
                                  ("Maximum", "MAXIMUM")]

    def __init__(self):
        QtGui.QDialog.__init__(self)
        self.setModal(True)

        layout = QtGui.QFormLayout()
        layout.setSpacing(10)
        self._addAnnotationDuration(layout)
        self._addAnnotationFadeOut(layout)
        self._addAnnotationPenSize(layout)
        self._addPictureQuality(layout)
        self._addEncryptionLevel(layout)
        self._addCloseButton(layout)

        self.setWindowTitle(self.DEFAULT_WINDOW_TITLE)
        self.setWindowIcon(QtGui.QIcon(self.IMAGE_WINDOW))
        self.setLayout(layout)

        # Increase the width so that the title bar text doesn't get truncated
        self.setFixedSize(self.minimumSizeHint().width() + 200,
                          self.minimumSizeHint().height())

    #
    # Setup
    #

    def _addAnnotationDuration(self, layout):
        label = QtGui.QLabel()
        label.setText("Annotation &duration:")

        self.persistDurationDropdown = QtGui.QComboBox()
        self.persistDurationDropdown.currentIndexChanged.connect(self.persistSettingChanged)
        for name, value in self._availableDurations:
            self.persistDurationDropdown.addItem(name, value)
        self.persistDurationDropdown.setCurrentIndex(self._defaultDurationIndex)

        layout.addRow(label, self.persistDurationDropdown)
        label.setBuddy(self.persistDurationDropdown)

    def _addAnnotationFadeOut(self, layout):
        label = QtGui.QLabel()
        label.setText("Annotation &fade duration:")

        self.fadeDurationDropdown = QtGui.QComboBox()
        self.fadeDurationDropdown.currentIndexChanged.connect(self.fadeDurationChanged)
        for name, value in self._availableFadeDurations:
            self.fadeDurationDropdown.addItem(name, value)
        self.fadeDurationDropdown.setCurrentIndex(self._defaultFadeDurationIndex)

        layout.addRow(label, self.fadeDurationDropdown)
        label.setBuddy(self.fadeDurationDropdown)

    def _addAnnotationPenSize(self, layout):
        label = QtGui.QLabel()
        label.setText("Annotation &pen size:")

        self.penSizeDropdown = QtGui.QComboBox()
        self.penSizeDropdown.currentIndexChanged.connect(self.penSizeChanged)
        for name, value in self._availablePenSizes:
            self.penSizeDropdown.addItem(name, value)
        self.penSizeDropdown.setCurrentIndex(self._defaultPenSizeIndex)

        layout.addRow(label, self.penSizeDropdown)
        label.setBuddy(self.penSizeDropdown)

    def _addPictureQuality(self, layout):
        label = QtGui.QLabel()
        label.setText("Picture &quality:")

        self.pictureQualityDropdown = QtGui.QComboBox()
        self.pictureQualityDropdown.currentIndexChanged.connect(self.pictureQualityChanged)
        for name, value in self._availablePictureQualitySettings:
            self.pictureQualityDropdown.addItem(name, value)
        self.pictureQualityDropdown.setCurrentIndex(self._defaultPictureQualityIndex)

        layout.addRow(label, self.pictureQualityDropdown)
        label.setBuddy(self.pictureQualityDropdown)

    def _addEncryptionLevel(self, layout):
        label = QtGui.QLabel()
        label.setText("&Encryption:")

        self.encryptionLevelDropdown = QtGui.QComboBox()
        self.encryptionLevelDropdown.currentIndexChanged.connect(self.encryptionLevelChanged)
        for name, value in self._availableEncryptionLevels:
            self.encryptionLevelDropdown.addItem(name, value)
        self.encryptionLevelDropdown.setCurrentIndex(self._defaultEncryptionLevelIndex)

        layout.addRow(label, self.encryptionLevelDropdown)
        label.setBuddy(self.encryptionLevelDropdown)

    def _addCloseButton(self, layout):
        buttons = QtGui.QDialogButtonBox()
        buttons.addButton("&Ok", buttons.AcceptRole)
        buttons.accepted.connect(self.close)
        layout.addRow(buttons)
        layout.setAlignment(buttons, QtCore.Qt.AlignHCenter)

    #
    # Callbacks from edits to settings
    #

    def persistSettingChanged(self, index):
        self.annotationPersistDuration = self.persistDurationDropdown.itemData(index)
        self.onAnnotationPreferenceChanged.emit()

    def fadeDurationChanged(self, index):
        self.annotationFadeDuration = self.fadeDurationDropdown.itemData(index)
        self.onAnnotationPreferenceChanged.emit()

    def penSizeChanged(self, index):
        self.annotationPenSize = self.penSizeDropdown.itemData(index)
        self.onAnnotationPreferenceChanged.emit()

    def pictureQualityChanged(self, index):
        self.pictureQuality = self.pictureQualityDropdown.itemData(index)
        self.onPictureQualityPreferenceChanged.emit()

    def encryptionLevelChanged(self, index):
        self.encryptionLevel = self.encryptionLevelDropdown.itemData(index)
