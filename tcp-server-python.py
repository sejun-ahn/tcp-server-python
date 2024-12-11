import sys, netifaces

from timestamp import *
from PyQt6 import uic, QtWidgets, QtNetwork
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtCore import QThread, pyqtSignal, Qt



class ClientHandlerThread(QThread):
    message_received = pyqtSignal(str,tuple)
    client_disconnected = pyqtSignal(tuple)

    def __init__(self, client_socket):
        super().__init__()
        self.client_socket = client_socket
        self.client_address = client_socket.peerAddress().toString()
        self.client_port = client_socket.peerPort()
        self.client_full_address = (client_socket.peerAddress().toString(), client_socket.peerPort())
        self.client_socket.readyRead.connect(self.read_message)
        self.client_socket.disconnected.connect(self.handle_client_disconnect)

    def read_message(self):
        while self.client_socket.bytesAvailable():
            message = self.client_socket.readAll().data().decode()
            self.message_received.emit(message, self.client_full_address)

    def handle_client_disconnect(self):
        self.client_disconnected.emit(self.client_full_address)

    def run(self):
        pass

class TCPServerApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        uic.loadUi('tcp-server-python-ui.ui', self)
        self.label_hostAddress = self.findChild(QtWidgets.QLabel, 'label_hostAddress')
        self.lineEdit_portNumber = self.findChild(QtWidgets.QLineEdit, 'lineEdit_portNumber')
        self.pushButton_serverActivate = self.findChild(QtWidgets.QPushButton, 'pushButton_serverActivate')
        self.pushButton_serverDeactivate = self.findChild(QtWidgets.QPushButton, 'pushButton_serverDeactivate')
        self.listWidget_client = self.findChild(QtWidgets.QListWidget, 'listWidget_client')
        self.listWidget_log = self.findChild(QtWidgets.QListWidget, 'listWidget_log')
        self.lineEdit_messageToSend = self.findChild(QtWidgets.QLineEdit, 'lineEdit_messageToSend')
        self.lineEdit_flagToSendToStart = self.findChild(QtWidgets.QLineEdit, 'lineEdit_flagToSendToStart')
        self.lineEdit_flagToSendToStop = self.findChild(QtWidgets.QLineEdit, 'lineEdit_flagToSendToStop')
        self.pushButton_sendMessage = self.findChild(QtWidgets.QPushButton, 'pushButton_sendMessage')
        self.pushButton_sendStart = self.findChild(QtWidgets.QPushButton, 'pushButton_sendStart')
        self.pushButton_sendStop = self.findChild(QtWidgets.QPushButton, 'pushButton_sendStop')
        self.pushButton_clearLog = self.findChild(QtWidgets.QPushButton, 'pushButton_clearLog')
        self.checkBox_autoScroll = self.findChild(QtWidgets.QCheckBox, 'checkBox_autoScroll')

        self.server = QtNetwork.QTcpServer(self)
        self.server.newConnection.connect(self.handle_new_connection)
        
        self.is_running = False
        self.update_button_state()
        self.client_threads = []
        self.client_items = {}

        if self.get_host_address():
            self.label_hostAddress.setText(self.get_host_address())

        self.pushButton_serverActivate.clicked.connect(self.activate_server)
        self.pushButton_serverDeactivate.clicked.connect(self.deactivate_server)
        self.pushButton_sendMessage.clicked.connect(lambda: self.broadcast_message_from_lineEdit(self.lineEdit_messageToSend))
        self.pushButton_sendStart.clicked.connect(lambda: self.broadcast_message_from_lineEdit(f"{self.lineEdit_flagToSendToStart.text()};{get_timestamp_tx()}"))
        self.pushButton_sendStop.clicked.connect(lambda: self.broadcast_message_from_lineEdit(f"{self.lineEdit_flagToSendToStop.text()};{get_timestamp_tx()}"))
        self.pushButton_clearLog.clicked.connect(lambda: self.listWidget_log.clear())
    
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_F1:
            self.pushButton_sendStart.click()
            print("F1")
            event.accept()
        elif event.key() == Qt.Key.Key_F2:
            self.pushButton_sendStop.click()
            print("F2")
            event.accept()
        else:
            event.ignore()
            
    def update_button_state(self):
        self.pushButton_serverActivate.setEnabled(not self.is_running)
        self.pushButton_serverDeactivate.setEnabled(self.is_running)
        self.pushButton_sendMessage.setEnabled(self.is_running)
        self.pushButton_sendStart.setEnabled(self.is_running)
        self.pushButton_sendStop.setEnabled(self.is_running)

    def get_host_address(self):
        interfaces = netifaces.interfaces()
        for interface in interfaces:
            if interface.startswith("wlp") or interface.startswith("wlx") or interface.startswith("wl"):
                try:
                    addrs = netifaces.ifaddresses(interface)
                    if netifaces.AF_INET in addrs:
                        ip_info = addrs[netifaces.AF_INET][0]
                        ip_address = ip_info.get('addr')
                        if ip_address and ip_address != '127.0.0.1':
                            return ip_address
                except ValueError:
                    continue
        return None
    
    def activate_server(self):
        if not self.is_running:
            serverPortNumber = self.lineEdit_portNumber.text()
            try:
                serverHostAddress = self.get_host_address()
                serverPortNumber = int(serverPortNumber)
                if self.server.listen(QtNetwork.QHostAddress(serverHostAddress), serverPortNumber):
                    self.log_server_activated()
                    self.is_running = True
                    self.update_button_state()
                else:
                    print("failed")
            except ValueError:
                print("failed")

    def deactivate_server(self):
        if self.is_running:
            for client_thread in self.client_threads:
                client_thread.client_socket.disconnectFromHost()
                client_thread.wait()

            self.client_threads.clear()
            self.client_items.clear()
            self.listWidget_client.clear()

            self.server.close()
            self.is_running = False
            self.update_button_state()
            self.log_server_deactivated()
    
    def handle_new_connection(self):
        client_socket = self.server.nextPendingConnection()
        
        client_thread = ClientHandlerThread(client_socket)
        client_thread.message_received.connect(self.action_rx_message)
        client_thread.client_disconnected.connect(self.remove_client_from_list)
        client_thread.start()
        self.log_new_client(client_thread.client_full_address)
        self.client_threads.append(client_thread)
        self.add_client_to_list(client_thread.client_full_address)

    def add_client_to_list(self, client_full_address):
        client_id = str(client_full_address[1])
        client_full_address_str = f"{client_full_address[0]}:{client_full_address[1]}"
        
        item = QtWidgets.QListWidgetItem(client_full_address_str)
        self.listWidget_client.addItem(item) 
        self.client_items[client_id] = item

    def remove_client_from_list(self, client_full_address):
        client_id = str(client_full_address[1])
        if client_id in self.client_items:
            item = self.client_items.pop(client_id)
            row = self.listWidget_client.row(item)
            self.listWidget_client.takeItem(row)



    def log_server_activated(self):
        self.log_on_log(f"[{get_timestamp_log()}] Server activated")
    def log_server_deactivated(self):
        self.log_on_log(f"[{get_timestamp_log()}] Server deactivated")
    def log_new_client(self, client_full_address):
        self.log_on_log(f"[{get_timestamp_log()}][CO][{client_full_address[1]}] connected")
    def log_del_client(self, client_full_address):
        self.log_on_log(f"[{get_timestamp_log()}][CO][{client_full_address[1]}] disconnected")
    def log_rx_message(self, message, client_full_address):
        self.log_on_log(f"[{get_timestamp_log()}][RX][{client_full_address[1]}] {message}")
    def log_tx_message(self, message, client_full_address):
        self.log_on_log(f"[{get_timestamp_log()}][TX][{client_full_address[1]}] {message}")
    
    def action_rx_message(self, message, client_full_address):
        self.log_rx_message(message, client_full_address)
        if message == "ping":
            self.tx_pong(client_full_address)

    def log_on_log(self, message):
        self.listWidget_log.addItem(message)
        if self.checkBox_autoScroll.isChecked():
            self.listWidget_log.scrollToBottom()

    def broadcast_message_from_lineEdit(self, lineEdit):
        if type(lineEdit) == str:
            message = lineEdit
        else:
            message = lineEdit.text()
        real_client_ids = self.client_items.keys()
        if message:
            for client_thread in self.client_threads:
                if client_thread.client_socket and client_thread.client_socket.isWritable() and str(client_thread.client_port) in real_client_ids:
                    client_thread.client_socket.write(message.encode())
                    client_thread.client_socket.flush()
                    self.log_tx_message(message, client_thread.client_full_address)
                   
    def tx_pong(self, client_full_address):
        for client_thread in self.client_threads:
            if client_thread.client_full_address == client_full_address:
                client_thread.client_socket.write(f"pong;{get_timestamp_tx()}".encode())
                client_thread.client_socket.flush()
                self.log_tx_message("pong", client_full_address)
    

def main():
    app = QtWidgets.QApplication(sys.argv)
    window = TCPServerApp()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()