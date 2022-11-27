import logging

LOG_FILE = "camera_config_dialog.log"
LOG_LEVEL = logging.DEBUG
LOG_FORMAT = " %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s"

logging.basicConfig(filename=LOG_FILE, filemode="w", format=LOG_FORMAT, level=LOG_LEVEL)

import sys
from pathlib import Path
from threading import Thread

import cv2
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (QApplication, QComboBox, QDialog, QGroupBox,
                             QHBoxLayout, QLabel, QPushButton, QRadioButton,
                             QSlider, QVBoxLayout)

# Append main repo to top of path to allow import of backend
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from frame_emitter import FrameEmitter

from src.calibration.charuco import Charuco
from src.cameras.camera import Camera
from src.cameras.video_stream import VideoStream
from src.session import Session


class CameraConfigDialog(QDialog):
    def __init__(self, stream, monocalibrator):
        super(CameraConfigDialog, self).__init__()

        self.monocal = monocalibrator
        # stream reference needed to change resolution
        self.stream = stream
        App = QApplication.instance()
        DISPLAY_WIDTH = App.primaryScreen().size().width()
        DISPLAY_HEIGHT = App.primaryScreen().size().height()

        self.setWindowTitle("Camera Configuration and Calibration")

        self.pixmap_edge = min(DISPLAY_WIDTH / 3, DISPLAY_HEIGHT / 3)
        self.frame_emitter = FrameEmitter(self.monocal, self.pixmap_edge)
        self.frame_emitter.start()
        # self.setFixedSize(self.pixmap_edge, self.pixmap_edge*2)
        self.setContentsMargins(0, 0, 0, 0)

        ################### BUILD SUB WIDGETS #############################
        self.build_frame_display()
        self.build_fps_display()
        self.build_ccw_rotation_btn()
        self.build_cw_rotation_btn()
        self.build_resolution_combo()
        self.build_exposure_hbox()
        self.build_view_full_res_btn()
        self.build_toggle_grp()
        self.build_calibrate_grp()
        ###################################################################
        self.v_box = QVBoxLayout(self)
        self.v_box.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.v_box.setContentsMargins(0, 0, 0, 0)

        ################## FULL RESOLUTION LAUNCH BUTTON ######################
        self.v_box.addWidget(self.view_full_res_btn)
        #################      VIDEO AT TOP     ##########################
        self.v_box.addWidget(self.frame_display)

        ############################  ADD HBOX OF CONFIG ######################
        h_box = QHBoxLayout()

        ################ ROTATE CCW #######################################
        h_box.addWidget(self.ccw_rotation_btn)

        ############################## ROTATE CW ###########################
        h_box.addWidget(self.cw_rotation_btn)
        # VBL.addWidget(self.mediapipeLabel)
        ######################################### RESOLUTION DROPDOWN ######
        h_box.addWidget(self.resolution_combo)
        h_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.v_box.addLayout(h_box)

        #################### EXPOSURE SLIDER #################################
        self.v_box.addLayout(self.exposure_hbox)

        #######################     FPS         ##############################
        self.v_box.addWidget(self.fps_display)
        ################### RADIO BUTTONS OF OVERLAY TOGGLES ##################
        self.v_box.addWidget(self.toggle_grp)

        ###################### CALIBRATION  ################################
        self.v_box.addWidget(self.calibrate_grp)

        for w in self.children():
            self.v_box.setAlignment(w, Qt.AlignmentFlag.AlignHCenter)

    ####################### SUB_WIDGET CONSTRUCTION ###############################

    def build_calibrate_grp(self):
        logging.debug("Building Calibrate Group")
        self.calibrate_grp = QGroupBox("Calibrate")
        # Generally Horizontal Configuration
        hbox = QHBoxLayout()
        self.calibrate_grp.setLayout(hbox)

        # Build Charuco Image Display
        self.charuco_display = QLabel()
        charuco_img = self.monocal.corner_tracker.charuco.board_pixmap(
            self.pixmap_edge / 3, self.pixmap_edge / 3
        )
        self.charuco_display.setPixmap(charuco_img)
        hbox.addWidget(self.charuco_display)

        # Collect Calibration Corners
        vbox = QVBoxLayout()
        vbox.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        collect_crnr_btn = QPushButton("Capture")
        collect_crnr_btn.setMaximumWidth(100)
        vbox.addWidget(collect_crnr_btn)

        def capture():
            """change to turn on/off"""
            if self.monocal.capture_corners:
                self.monocal.capture_corners = False
                collect_crnr_btn.setText("Capture")
            else:
                self.monocal.capture_corners = True
                collect_crnr_btn.setText("Stop Capture")

        collect_crnr_btn.clicked.connect(capture)

        # Calibrate Button
        self.calibrate_btn = QPushButton("Calibrate")
        self.calibrate_btn.setMaximumWidth(100)
        vbox.addWidget(self.calibrate_btn)

        def calibrate():
            if len(self.monocal.all_ids) > 0:
                self.calib_output.setText("Calibration can take a moment...")

                def wrker():
                    self.monocal.calibrate()
                    self.calib_output.setText(self.monocal.camera.calibration_summary())

                self.calib_thread = Thread(target=wrker, args=(), daemon=True)
                self.calib_thread.start()
            else:
                self.calib_output.setText("Need to Collect Grids")

        self.calibrate_btn.clicked.connect(calibrate)

        # Clear calibration history
        clear_grid_history_btn = QPushButton("Clear History")
        clear_grid_history_btn.setMaximumWidth(100)
        vbox.addWidget(clear_grid_history_btn)

        def clear_capture_history():
            self.monocal.initialize_grid_history()

        clear_grid_history_btn.clicked.connect(clear_capture_history)

        # Save Calibration
        self.save_cal_btn = QPushButton("Save Calibration")
        self.save_cal_btn.setMaximumWidth(100)
        vbox.addWidget(self.save_cal_btn)

        # TODO: refactor so saves managed elsewhere...why build a whole session
        # here just to save. There's got to be a more modular approach to this
        # that I expect will pay dividends later
        def save_cal():
            pass
            # self.session.save_camera(self.monocal.camera.port)

        self.save_cal_btn.clicked.connect(save_cal)

        # include calibration grid in horizontal box
        hbox.addLayout(vbox)

        self.calib_output = QLabel()
        self.calib_output.setWordWrap(True)
        self.calib_output.setMaximumWidth(self.pixmap_edge / 3)
        self.calib_output.setText(self.monocal.camera.calibration_summary())
        hbox.addWidget(self.calib_output)
        # calib_output.setMaximumWidth()

    def build_toggle_grp(self):
        logging.debug("Building Toggle Group")

        def on_radio_btn():
            radio_grp = self.sender().text()
            if radio_grp == "None":
                self.stream.show_mediapipe = False
                self.stream.track_charuco = False
                self.stream.collect_charuco_corners = False
                self.stream.undistort = False

            if radio_grp == "Mediapipe Hands":
                self.stream.show_mediapipe = True
                self.stream.track_charuco = False
                self.stream.collect_charuco_corners = False
                self.stream.undistort = False

            if radio_grp == "Charuco":
                self.stream.show_mediapipe = False
                self.stream.track_charuco = True
                self.stream.collect_charuco_corners = False
                self.stream.undistort = False

            if radio_grp == "Undistort":
                self.stream.show_mediapipe = False
                self.stream.track_charuco = False
                self.stream.collect_charuco_corners = False
                self.stream.undistort = True

        self.toggle_grp = QGroupBox("Views")
        # self.toggle_grp.setFixedWidth(0.75* self.width-50())
        hbox = QHBoxLayout()
        for option in ["None", "Mediapipe Hands", "Charuco", "Undistort"]:
            btn = QRadioButton(option)
            hbox.addWidget(btn)
            if option == "None":
                btn.setChecked(True)
            btn.toggled.connect(on_radio_btn)

        self.toggle_grp.setLayout(hbox)
        hbox.setAlignment(Qt.AlignmentFlag.AlignHCenter)

    def build_fps_display(self):
        logging.debug("Building FPS Display")
        self.fps_display = QLabel()
        self.fps_display.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        def FPSUpdateSlot(fps):
            if fps == 0:
                self.fps_display.setText("reconnecting to camera...")
            else:
                self.fps_display.setText("FPS: " + str(round(fps, 1)))

        # TODO: #18 #17 #16 #15 Create FPS display on config dialog
        self.frame_emitter.FPSBroadcast.connect(FPSUpdateSlot)

    def build_cw_rotation_btn(self):
        self.cw_rotation_btn = QPushButton("Rotate CW")
        self.cw_rotation_btn.setMaximumSize(100, 50)

        # Counter Clockwise rotation called because the display image is flipped
        self.cw_rotation_btn.clicked.connect(self.monocal.camera.rotate_CCW)

    def build_ccw_rotation_btn(self):
        self.ccw_rotation_btn = QPushButton("Rotate CCW")
        self.ccw_rotation_btn.setMaximumSize(100, 50)

        # Clockwise rotation called because the display image is flipped
        self.ccw_rotation_btn.clicked.connect(self.monocal.camera.rotate_CW)

    def build_exposure_hbox(self):
        # construct a horizontal widget with label: slider: value display
        self.exposure_hbox = QHBoxLayout()
        label = QLabel("Exposure")
        label.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.exp_slider = QSlider(Qt.Orientation.Horizontal)
        self.exp_slider.setRange(-10, 0)
        self.exp_slider.setSliderPosition(int(self.monocal.camera.exposure))
        self.exp_slider.setPageStep(1)
        self.exp_slider.setSingleStep(1)
        self.exp_slider.setMaximumWidth(200)
        exp_number = QLabel()
        exp_number.setText(str(int(self.monocal.camera.exposure)))

        def update_exposure(s):
            self.monocal.camera.exposure = s
            exp_number.setText(str(s))

        self.exp_slider.valueChanged.connect(update_exposure)

        self.exposure_hbox.addWidget(label)
        self.exposure_hbox.addWidget(self.exp_slider)
        self.exposure_hbox.addWidget(exp_number)

        self.exposure_hbox.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def build_frame_display(self):
        # return a QLabel that is linked to the constantly changing image

        self.frame_display = QLabel()
        self.frame_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.frame_display.setFixedWidth(self.width())
        self.frame_display.setFixedHeight(self.width())
        w = self.frame_display.width()
        h = self.frame_display.height()

        def ImageUpdateSlot(QPixmap):
            self.frame_display.setPixmap(QPixmap)

        self.frame_emitter.ImageBroadcast.connect(ImageUpdateSlot)

    def build_resolution_combo(self):
        # possible resolutions is a list of tuples, but we need a list of Stext
        def resolutions_text():
            res_text = []
            for w, h in self.monocal.camera.possible_resolutions:
                res_text.append(f"{int(w)} x {int(h)}")
            return res_text

        def change_resolution(res_text):
            # call the cam_cap widget to change the resolution, but do it in a
            # thread so that it doesn't halt your progress
            w, h = res_text.split("x")
            w, h = int(w), int(h)
            new_res = (w, h)
            # self.cam_cap.change_resolution(new_res)
            self.change_res_thread = Thread(
                target=self.stream.change_resolution, args=(new_res,), daemon=True
            )
            self.change_res_thread.start()

            # whenever resolution changes, calibration parameters no longer apply
            self.monocal.camera.error = None
            self.monocal.camera.camera_matrix = None
            self.monocal.camera.distortion = None
            self.monocal.camera.grid_count = 0
            self.stream.undistort = False

        self.resolution_combo = QComboBox()

        self.resolution_combo.addItems(resolutions_text())
        self.resolution_combo.setMaximumSize(100, 50)

        w, h = self.monocal.camera.resolution
        self.resolution_combo.setCurrentText(f"{int(w)} x {int(h)}")
        self.resolution_combo.currentTextChanged.connect(change_resolution)

    def build_view_full_res_btn(self):
        self.view_full_res_btn = QPushButton(
            "Open Full Resolution Window (press 'q' to close)"
        )

        def cv2_view_worker():
            while True:
                frame = cv2.flip(self.monocal.frame, 1)

                cv2.imshow("Press 'q' to Quit", frame)

                key = cv2.waitKey(1)
                if key == ord("q"):
                    cv2.destroyAllWindows()
                    break

        def run_cv2_view():
            self.cv2_view = Thread(target=cv2_view_worker, args=(), daemon=True)
            self.cv2_view.start()

        self.view_full_res_btn.clicked.connect(run_cv2_view)

    def convert_cv_qt(self, cv_img):
        """Convert from an opencv image to QPixmap"""
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        charuco_QImage = QImage(
            rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888
        )

        p = charuco_QImage.scaled(
            self.charuco_display.width(),
            self.charuco_display.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        return QPixmap.fromImage(p)

    def pretty_matrix(mat):
        return "\n".join(
            ["\t".join([str(round(cell, 2)) for cell in row]) for row in mat]
        )


if __name__ == "__main__":
    App = QApplication(sys.argv)

    from queue import Queue

    config_dialogs = []

    from src.calibration.corner_tracker import CornerTracker
    from src.calibration.monocalibrator import MonoCalibrator
    from src.cameras.camera import Camera
    from src.cameras.dispatcher import Dispatcher
    from src.cameras.synchronizer import Synchronizer

    charuco = Charuco(
        4, 5, 11, 8.5, aruco_scale=0.75, square_size_overide=0.0525, inverted=True
    )

    trackr = CornerTracker(charuco)
    test_port = 0
    cam = Camera(test_port)
    stream = VideoStream(cam)
    streams_dict = {test_port: stream}  # synchronizer expects this format
    syncr = Synchronizer(streams_dict, fps_target=12)
    monocal = MonoCalibrator(cam, syncr, trackr)

    logging.info("Creating Camera Config Dialog")
    cam_dialog = CameraConfigDialog(stream, monocal)
    logging.info("About to show camera config dialog")
    cam_dialog.show()

    sys.exit(App.exec())
