# Built following the tutorials that begin here: 
# https://www.pythonguis.com/tutorials/pyqt6-creating-your-first-window/

from re import L
import sys

from PyQt6.QtCore import Qt, QAbstractTableModel
from PyQt6.QtGui import QPalette, QColor, QIcon
from PyQt6.QtWidgets import ( QVBoxLayout, QHBoxLayout, QLabel, QMainWindow, 
                            QPushButton, QTabWidget, QWidget,QGroupBox, 
                            QScrollArea, QApplication, QTableWidget, QTableView)

from pathlib import Path
from numpy import char

from qtpy import QT_VERSION

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.gui.charuco_builder import CharucoBuilder
from src.gui.camera_config_dialogue import CameraConfigDialog
from src.session import Session


# import sys
# from PyQt5 import QtCore, QtGui, QtWidgets
# from PyQt5.QtCore import Qt

class DictionaryTableModel(QAbstractTableModel):
    def __init__(self, data, headers):
        super(DictionaryTableModel, self).__init__()
        self._data = data
        self._headers = headers

    def data(self, index, role):
        if role == Qt.ItemDataRole.DisplayRole:
            # Look up the key by header index.
            column = index.column()
            column_key = self._headers[column]
            return self._data[index.row()][column_key]

    def rowCount(self, index):
        # The length of the outer list.
        return len(self._data)

    def columnCount(self, index):
        # The length of our headers.
        return len(self._headers)

    def headerData(self, section, orientation, role):
        # section is the index of the column/row.
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return str(self._headers[section])

            if orientation == Qt.Orientation.Vertical:
                return str(section)

class CameraTable(QWidget):
    def __init__(self,session):
        super().__init__()

        self.table = QTableView()
        self.session = session
        vbox = QVBoxLayout()
        self.setLayout(vbox)
        vbox.addWidget(self.table)   

        self._headers = ["port", "resolution", "error", "grid_count"]        
        self.update_data()        

        self.table.verticalHeader().setVisible(False)
        self.model = DictionaryTableModel(self.data, self._headers)
        self.table.setModel(self.model)
        self.table.resizeColumnsToContents()
        self.setFixedSize(self.table.size())
        # self.setCentralWidget(self.table)


    def update_data(self):
        self.data = []
        for key, params in self.session.config.items():
            if "cam" in key:
                print(f"Found {key}")
                if "error" in params.keys():
                    pass
                else:
                    params["error"] = "NA"
                    params["grid_count"] = 0
                # print(params)
                print(params)
                params = {k: params[k] for k in self._headers}
                res = params["resolution"]
                params["resolution"] = f"{res[0]} x {res[1]}"
                self.data.append(params)


if __name__ == "__main__":

    session = Session(r'C:\Users\Mac Prible\repos\learn-opencv\test_session')
    print(session.config)
    app=QApplication(sys.argv)
    window=CameraTable(session)
    window.show()
    app.exec()
    # data = []



    # print(data)