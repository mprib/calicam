# There may be a mixed functionality here...I'm not sure. Between the corner
# detector and the corner drawer...like, there will need to be something that
# accumulates a frame of corners to be drawn onto the displayed frame.

import logging

logging.basicConfig(
    filename="monocalibrator.log",
    filemode="w",
    # level=logging.INFO)
    level=logging.DEBUG,
)

import sys
import time
from itertools import combinations
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.calibration.charuco import Charuco
from src.cameras.camera import Camera


class MonoCalibrator:
    def __init__(self, camera, charuco):

        # need camera to know resolution and to assign calibration parameters
        # to camera
        self.camera = camera
        self.charuco = charuco

        self._frame_corner_ids = np.array([])
        self._frame_corners = np.array([])

        self.corner_loc_img = []
        self.corner_loc_obj = []
        self.corner_ids = []

        self.connected_corners = self.charuco.get_connected_corners()
        self.last_calibration_time = time.time()  # need to initialize to *something*

        # for subpixel corner correction
        self._criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        self._conv_size = (11, 11)  # Don't make this too large.

        self.initialize_grid_history()

        self.is_calibrated = False  # starts out this way

    def initialize_grid_history(self):
        # get appropriately structured image size

        #!!! IF CAMERA RESOLUTION CHANGES THIS MUST BE RERUN
        self.image_size = list(self.camera.resolution)
        self.image_size.reverse()  # for some reason...
        self.image_size.append(3)
        self._grid_capture_history = np.zeros(self.image_size, dtype="uint8")

        # roll back collected corners to the beginning
        self.corner_loc_img = []
        self.corner_loc_obj = []
        self.corner_ids = []

    def find_corners(self, frame):
        """Will check for corners in the default board image, if it doesn't
        find any, then it will look for images in the mirror image of the
        default board"""
        self.frame = frame

        self.find_corners_single_frame(mirror=False)
        # print(self._frame_corner_ids)
        if not self._frame_corner_ids.any():
            # print("Checking mirror image")
            self.frame = cv2.flip(self.frame, 1)
            self.find_corners_single_frame(mirror=True)

    def find_corners_single_frame(self, mirror):
        """ """

        # invert the frame for detection if needed
        self.gray = cv2.cvtColor(self.frame, cv2.COLOR_BGR2GRAY)  # convert to gray
        if self.charuco.inverted:
            self.gray = ~self.gray  # invert

        # detect if aruco markers are present
        aruco_corners, aruco_ids, rejected = cv2.aruco.detectMarkers(
            self.gray, self.charuco.board.dictionary
        )

        # print(f"{len(aruco_corners)} corners found in image; Mirror: {mirror}")

        frame_width = frame.shape[1]  # used for flipping mirrored corners back

        # correct the mirror frame before putting text on it if it's flipped
        if mirror:
            self.frame = cv2.flip(self.frame, 1)

        # if so, then interpolate to the Charuco Corners and return what you found
        if len(aruco_corners) > 3:
            (
                success,
                self._frame_corners,
                self._frame_corner_ids,
            ) = cv2.aruco.interpolateCornersCharuco(
                aruco_corners, aruco_ids, self.gray, self.charuco.board
            )

            # This occasionally errors out...
            # only offers possible refinement so if it fails, just move along
            try:
                self._frame_corners = cv2.cornerSubPix(
                    self.gray,
                    self._frame_corners,
                    self._conv_size,
                    (-1, -1),
                    self._criteria,
                )
            except:
                pass

            if success:
                # clean up the data types
                self._frame_corner_ids.tolist()
                self._frame_corners.tolist()
                # flip coordinates if mirrored image fed in
                if mirror:
                    self._frame_corners[:, :, 0] = (
                        frame_width - self._frame_corners[:, :, 0]
                    )

                # update the list of corners exposed to outside callers
                self.frame_corner_ids = self._frame_corner_ids
                self.frame_corners = self._frame_corners

                # TODO: break out into seperate method.... this is about drawing
                for ID, coord in zip(
                    self._frame_corner_ids[:, 0], self._frame_corners[:, 0]
                ):
                    coord = list(coord)
                    # print(frame.shape[1])
                    x = round(coord[0])
                    y = round(coord[1])

                    cv2.circle(self.frame, (x, y), 5, (0, 0, 220), 3)
                    # cv2.putText(self.frame,str(ID), (x, y), cv2.FONT_HERSHEY_SIMPLEX, .5,(220,0,0), 3)

            else:
                self._frame_corner_ids = np.array([])
                self._frame_corners = np.array([])
        else:
            self._frame_corner_ids = np.array([])
            self._frame_corners = np.array([])

    @property
    def board_FOR_corners(self):
        """Objective position of charuco corners in a board frame of reference"""
        if self._frame_corner_ids.any():
            return self.charuco.board.chessboardCorners[self._frame_corner_ids, :]
        else:
            return np.array([])

    def collect_corners(self, board_threshold=0.7, wait_time=0.5):

        corner_count = len(self.charuco.board.chessboardCorners)
        min_points_to_process = int(corner_count * board_threshold)

        if self._frame_corner_ids.any():
            enough_corners = len(self._frame_corner_ids) > min_points_to_process
        else:
            enough_corners = False

        enough_time_from_last_cal = time.time() > self.last_calibration_time + wait_time

        if enough_corners and enough_time_from_last_cal:

            # store the corners and IDs
            self.corner_loc_img.append(self._frame_corners)
            self.corner_ids.append(self._frame_corner_ids)

            # store objective corner positions in a board frame of reference
            # board_FOR_corners = self.charuco.board.chessboardCorners[self._frame_corner_ids, :]
            self.corner_loc_obj.append(self.board_FOR_corners)
            #
            self.update_capture_history()
            self.last_calibration_time = time.time()

    def update_capture_history(self):
        """
        Given a frame and the location of the charuco board corners within in,
        draw a line connecting the outer bounds of the detected corners and add
        it in to the history of captrued frames. One frame will hold the whole
        history of the corners collected.
        """

        possible_pairs = {
            pair for pair in combinations(self._frame_corner_ids.squeeze().tolist(), 2)
        }
        connected_pairs = self.connected_corners.intersection(possible_pairs)

        # build dictionary of corner positions:
        observed_corners = {}
        for crnr_id, crnr in zip(
            self._frame_corner_ids.squeeze(), self._frame_corners.squeeze()
        ):
            observed_corners[crnr_id] = (round(crnr[0]), round(crnr[1]))

        # add them to the visual representation of the grid capture history
        for pair in connected_pairs:
            point_1 = observed_corners[pair[0]]
            point_2 = observed_corners[pair[1]]

            cv2.line(self._grid_capture_history, point_1, point_2, (255, 165, 0), 1)

    def merged_grid_history(self):
        alpha = 1
        beta = 1

        return cv2.addWeighted(self.frame, alpha, self._grid_capture_history, beta, 0)

    def calibrate(self):
        """
        Use the recorded image corner positions along with the objective
        corner positions based on the board definition to calculated
        the camera matrix and distortion parameters
        """
        logging.info(f"Calibrating camera {self.camera.port}....")

        # organize parameters for calibration function
        objpoints = self.corner_loc_obj
        imgpoints = self.corner_loc_img
        height = self.image_size[0]
        width = self.image_size[1]

        error, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
            objpoints, imgpoints, (width, height), None, None
        )

        self.is_calibrated = True

        # ret is RMSE of reprojection
        self.camera.error = round(error, 3)
        self.camera.camera_matrix = mtx
        self.camera.distortion = dist
        self.camera.grid_count = len(self.corner_ids)

        logging.info(f"Error: {error}")
        logging.info(f"Camera Matrix: {mtx}")
        logging.info(f"Distortion: {dist}")
        logging.info(f"Grid Count: {self.camera.grid_count}")


if __name__ == "__main__":

    charuco = Charuco(
        4, 5, 11, 8.5, aruco_scale=0.75, square_size_overide=0.0525, inverted=True
    )
    cam = Camera(0)

    print(f"Using Optimized Code?: {cv2.useOptimized()}")
    calib = MonoCalibrator(cam, charuco)
    last_calibration_time = time.time()

    print("About to enter main loop")
    while True:

        read_success, frame = cam.capture.read()
        calib.find_corners(frame)
        calib.collect_corners(wait_time=0.5)
        merged_frame = calib.merged_grid_history()

        cv2.imshow("Press 'q' to quit", merged_frame)
        key = cv2.waitKey(1)

        # end capture when enough grids collected
        if key == ord("q"):
            cam.capture.release()
            cv2.destroyAllWindows()
            break

    calib.calibrate()
    print(f"Error: {cam.error}")
    print(f"Camera Matrix: {cam.camera_matrix}")
    print(f"Distortion: {cam.distortion}")
    print(f"Grid Count: {cam.grid_count}")
