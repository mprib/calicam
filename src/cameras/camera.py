# The purpose of this module is to create a class that will operate as an
# interface for a given camera. It will  store data related to
# a variety of camera specific variables and allow setting of these variables:
#
# - port
#   - an integer for a live camera
#   - note this is focused on live feeds...pre-recorded video doesn't need this
# - cv2.VideoCapture object based on port
# - Default Resolution
# - list of possible resolutions
# - exposure
# - intrinsic camera properties (to be set following calibration/on load)
#   - camera matrix
#   - distortion parameters
#
# New camera configurations
#%%

import logging
import time
from threading import Thread

import cv2

TEST_FRAME_COUNT = 10
MIN_RESOLUTION_CHECK = 500
MAX_RESOLUTION_CHECK = 10000


class Camera(object):

    # https://docs.opencv.org/3.4/d4/d15/group__videoio__flags__base.html
    # see above for constants used to access properties
    def __init__(self, port):

        # check if source has a data feed before proceeding...if not it is
        # either in use or fake
        logging.debug(f"Attempting to connect video capure at port {port}")
        test_capture = cv2.VideoCapture(port)
        for _ in range(0, TEST_FRAME_COUNT):
            good_read, frame = test_capture.read()

            # pass # dealing with this in the else statemetn below...not a real camera
        if good_read:
            logging.debug(f"Good read at port {port}...proceeding")
            self.port = port
            self.capture = test_capture
            self.active_port = True
            # limit buffer size so that you are always reading the latest frame
            self.capture.set(
                cv2.CAP_PROP_BUFFERSIZE, 1
            )  # from https://stackoverflow.com/questions/58293187/opencv-real-time-streaming-video-capture-is-slow-how-to-drop-frames-or-getanother thread signaled a change to mediapipe overley-sync

            self.is_connected = True
            self.is_rolling = False
            self.stop_rolling_trigger = False  # used for managing threads
            self.ignore = False

            # read by RealTimeDevice to set orientation
            self.rotation_count = 0  # +1 for each 90 degree CW rotation, -1 for CCW

            self.set_exposure()
            self.set_default_resolution()
            self.set_possible_resolutions()

            # camera initializes as uncalibrated
            self.error = None
            self.camera_matrix = None
            self.distortion = None
            self.grid_count = None
        else:
            # probably busy
            self.port = port
            self.capture = None
            self.active_port = False
            logging.info(f"Camera at port {port} appears to be busy")
            raise Exception(f"Not reading at port {port}...likely in use")
        if isinstance(self.possible_resolutions[0], int):
            # probably not real
            self.port = port
            self.capture = None
            self.active_port = False
            logging.info(f"Camera at port {port} may be virtual")
            raise Exception(f"{port}...likely not real")

    @property
    def exposure(self):
        return self._exposure

    @exposure.setter
    def exposure(self, value):
        """Note that OpenCV appears to change the exposure value, but
        this is not read back accurately through the getter, so just
        track it manually after updating"""
        self.capture.set(cv2.CAP_PROP_EXPOSURE, value)
        self._exposure = value

    @property
    def _width(self):
        return int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))

    @_width.setter
    def _width(self, value):
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, value)

    @property
    def _height(self):
        return int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

    @_height.setter
    def _height(self, value):
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, value)

    @property
    def resolution(self):
        return (self._width, self._height)

    @resolution.setter
    def resolution(self, value):
        """Currently, this is how the resolution is actually changed"""
        self._width = value[0]
        self._height = value[1]

    def set_default_resolution(self):
        """called at initilization before anything has changed"""
        self.default_resolution = self.resolution

    def set_exposure(self):
        """Need an initial value, though it does not appear that updates to
        exposure reliably read back from"""
        self._exposure = self.capture.get(cv2.CAP_PROP_EXPOSURE)
        self.exposure = self._exposure  # port seemed to hold on to old exposure

    def get_nearest_resolution(self, test_width):
        """This strange little method just temporarly stores the current value
        of the resolution to be replaced at the end, then tries a value
        and then reads what resolution closest to it the capture offers,
        then returns the capture to its original state"""
        old_width = self._width
        self._width = test_width
        resolution = self.resolution
        self._width = old_width
        return resolution

    def set_possible_resolutions(self):
        min_res = self.get_nearest_resolution(MIN_RESOLUTION_CHECK)
        max_res = self.get_nearest_resolution(MAX_RESOLUTION_CHECK)

        min_width = min_res[0]
        max_width = max_res[0]

        STEPS_TO_CHECK = 10  # fast to check so cover your bases

        # the size of jump to make before checking on the resolution
        step_size = int((max_width - min_width) / STEPS_TO_CHECK)

        resolutions = {min_res, max_res}

        if max_width > min_width:  # i.e. only one size avaialable
            for test_width in range(
                int(min_width + step_size), int(max_width - step_size), int(step_size)
            ):
                new_res = self.get_nearest_resolution(test_width)
                # print(new_res)
                resolutions.add(new_res)
            resolutions = list(resolutions)
            resolutions.sort()
            self.possible_resolutions = resolutions
        else:
            self.possible_resolutions = self.default_resolution

    def rotate_CW(self):
        if self.rotation_count == 3:
            self.rotation_count = 0
        else:
            self.rotation_count = self.rotation_count + 1

    def rotate_CCW(self):
        if self.rotation_count == -3:
            self.rotation_count = 0
        else:
            self.rotation_count = self.rotation_count - 1

    def disconnect(self):
        self.capture.release()
        self.is_connected = False

    def connect(self):
        self.capture = cv2.VideoCapture(self.port)
        self.is_connected = True

    def stop_rolling(self):
        """
        Use .is_rolling as a trigger to kill threads
        that are reading in camera data
        """
        if self.is_rolling:  # don't create a loop if can't break out
            self.stop_rolling_trigger = True
            while self.is_rolling:  # give the thread time to wrap up
                logging.warning("Performing one cycle of loop that has danger of getting stuck.")
                time.sleep(0.01)
        self.stop_rolling_trigger = False  # reset the trigger

    def calibration_summary(self):
        # Calibration output presented in label on far right
        grid_count = "Grid Count:\t" + str(self.grid_count)
        size_text = "Resolution:\t" + str(self.resolution[0]) + "x" + str(self.resolution[1])

        # only grab if they exist
        if self.error and self.error != "NA":
            error_text = f"Error:\t{round(self.error,3)} "
            cam_matrix_text = "Camera Matrix:\n" + (
                "\n".join(
                    [
                        "\t".join([str(round(float(cell), 1)) for cell in row])
                        for row in self.camera_matrix
                    ]
                )
            )
            distortion_text = "Distortion:\t" + ",".join(
                [str(round(float(cell), 2)) for cell in self.distortion[0]]
            )

            # print(self.camera_matrix)
            summary = (
                grid_count
                + "\n\n"
                + error_text
                + "\n\n"
                + size_text
                + "\n\n"
                + cam_matrix_text
                + "\n\n"
                + distortion_text
            )
            return summary
        else:
            return "No Calibration Stored"


############################ DEBUG / TEST ######################################
# Here I include some helper functions to exhibit/test the functionality
# of the module
def display_worker(camera, win_name=None):
    if not win_name:
        win_name = f"'q' to quit video {camera.port}"

    frame_displayed = False
    while True:
        success, frame = camera.capture.read()

        if success:
            cv2.imshow(win_name, frame)
            frame_displayed = True

        if camera.stop_rolling_trigger:
            if frame_displayed:
                print("Successful Display")
                cv2.destroyWindow(win_name)
            camera.is_rolling = False
            break

        if cv2.waitKey(1) == ord("q"):
            if frame_displayed:
                print("Successful Display")
                cv2.destroyWindow(win_name)
            camera.is_rolling = False
            break


def display(camera, win_name=None):
    """Note, this is just for general observation purposes,
    while in the process of verifying this module.
    """
    camera.is_rolling = True
    display_thread = Thread(target=display_worker, args=(camera, win_name), daemon=True)
    display_thread.start()


######################### TEST FUNCTIONALITY OF CAMERAS ########################
#%%
if __name__ == "__main__":
    # if True:

    cam = Camera(2)
    print(cam.possible_resolutions)
    #%%

    for res in cam.possible_resolutions:
        print(f"Testing Resolution {res}")

        # cv2.imshow appears to throw errors after ~3 changes in resolution
        # disconnecting and reconnecting may not be necessary with other
        # display implementations
        cam.disconnect()
        cam.connect()
        cam.resolution = res
        display(cam)
        time.sleep(3)
        cam.stop_rolling()

    cam.connect()
    display(cam)

    for exp in range(-10, 0):
        print(f"Testing Exposure Level {exp}")
        cam.exposure = exp
        time.sleep(2)

    cam.stop_rolling()
    cam.exposure = -5
    cam.disconnect()

    # %%
