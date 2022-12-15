
import logging
import sys

LOG_FILE = "log\charuco_group.log"
LOG_LEVEL = logging.DEBUG
# LOG_LEVEL = logging.INFO
LOG_FORMAT = " %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s"

logging.basicConfig(filename=LOG_FILE, filemode="w", format=LOG_FORMAT, level=LOG_LEVEL)

import time
from pathlib import Path
from threading import Thread

from numpy import char
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from src.session import Session
from src.gui.left_sidebar.charuco_summary import CharucoSummary
from src.gui.left_sidebar.camera_summary import CameraSummary
# from src.gui.left_sidebar.charuco_summary import CharucoSummary


class SideBar(QWidget):
    def __init__(self, session):
        super().__init__()
        self.session = session

        vbox = QVBoxLayout()
        self.setLayout(vbox)

        charuco_grp = QGroupBox("Charuco Builder")
        # ch_lay = QHBoxLayout()
        charuco_grp.setLayout(QHBoxLayout())
        charuco_summary = CharucoSummary(self.session)
        charuco_grp.layout().addWidget(charuco_summary)
        vbox.addWidget(charuco_grp)
       
        cam_grp = QGroupBox("Single Camera Calibration") 
        cam_grp.setLayout(QHBoxLayout())
        camera_summary = CameraSummary(self.session)
        cam_grp.layout().addWidget(camera_summary)
        vbox.addWidget(cam_grp)



if __name__ == "__main__":
    repo = Path(__file__).parent.parent.parent.parent
    config_path = Path(repo, "sessions", "high_res_session")
    
    session = Session(config_path)
    print(session.config)
    app = QApplication(sys.argv)

    side_bar = SideBar(session)
    side_bar.show()

    sys.exit(app.exec())