import socket
from PyQt5.QtWidgets import ( #GUI components
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QLabel,
    QListWidget, QFileDialog, QLineEdit, QWidget, QInputDialog
)
import os
import traceback


class ClientApp(QMainWindow):
    def __init__(self): #client window
        super().__init__()

        self.initUI()
        self.client_socket = None
        self.server_ip = ""
        self.port = 0
        self.name = ""
        self.download_dir = ""

    def initUI(self): #UI components and their places
        self.setWindowTitle("Client Application")
        self.setGeometry(100, 100, 600, 600)

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        #IP and Port inputs
        self.ip_label = QLabel("Server IP Address:", self)
        layout.addWidget(self.ip_label)
        self.ip_input = QLineEdit(self)
        layout.addWidget(self.ip_input)

        self.port_label = QLabel("Server Port Number:", self)
        layout.addWidget(self.port_label)
        self.port_input = QLineEdit(self)
        layout.addWidget(self.port_input)

        #username of the client
        self.name_label = QLabel("Enter your username:", self)
        layout.addWidget(self.name_label)
        self.name_input = QLineEdit(self)
        layout.addWidget(self.name_input)

        #connection button
        self.connect_button = QPushButton("Connect to Server", self)
        self.connect_button.clicked.connect(self.connect_to_server)
        layout.addWidget(self.connect_button)

        #for default disabled button operations
        self.upload_button = QPushButton("Upload File", self)
        self.upload_button.clicked.connect(self.upload_file)
        self.upload_button.setEnabled(False)
        layout.addWidget(self.upload_button)

        self.list_button = QPushButton("List Files", self)
        self.list_button.clicked.connect(self.list_files)
        self.list_button.setEnabled(False)
        layout.addWidget(self.list_button)

        self.download_button = QPushButton("Download File", self)
        self.download_button.clicked.connect(self.download_file)
        self.download_button.setEnabled(False)
        layout.addWidget(self.download_button)

        self.delete_button = QPushButton("Delete File", self)
        self.delete_button.clicked.connect(self.delete_file)
        self.delete_button.setEnabled(False)
        layout.addWidget(self.delete_button)

        #directory for download
        self.dir_label = QLabel("Select download directory:", self)
        layout.addWidget(self.dir_label)
        self.dir_button = QPushButton("Browse", self)
        self.dir_button.clicked.connect(self.select_directory)
        layout.addWidget(self.dir_button)
        self.selected_dir = QLabel("No directory selected", self)
        layout.addWidget(self.selected_dir)

        #output log
        self.log_label = QLabel("Client Logs:", self)
        layout.addWidget(self.log_label)
        self.log_box = QListWidget(self)
        layout.addWidget(self.log_box)

    def select_directory(self):#choosing directory for downloads
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory:
            self.selected_dir.setText(directory)
            self.download_dir = directory

    def connect_to_server(self):#connecting the server
        try:
            self.server_ip = self.ip_input.text()#getting ip,port and the username
            self.port = int(self.port_input.text())
            self.name = self.name_input.text()

            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)#creating TCP socket
            self.client_socket.connect((self.server_ip, self.port))

            #sending username to the server
            self.client_socket.send(self.name.encode())
            response = self.client_socket.recv(1024).decode()
            if response.startswith("Error"):#connection error message
                self.log_message(response)
                self.client_socket.close()
                self.client_socket = None
            else:
                self.log_message("Connected to server.")#connection success message
                self.enable_buttons()#file operations are enabled
        except Exception as e:
            self.log_message(f"Error connecting to server: {e}")

    def upload_file(self):#uploading file to server
        if not self.client_socket:#checking connection
            self.log_message("Error: Not connected to the server.")
            return
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File to Upload")
        if file_path:
            filename = os.path.basename(file_path)
            filesize = os.path.getsize(file_path)
            command = f"UPLOAD|{filename}|{filesize}"#creating uopload command

            try:
                self.client_socket.send(command.encode())#upload command to server
                with open(file_path, 'rb') as f:
                    chunk = f.read(4096)
                    while chunk:
                        self.client_socket.send(chunk)
                        chunk = f.read(4096)
                response = self.client_socket.recv(1024).decode()#response of server
                self.log_message(response)#response of server on the log
            except Exception as e:
                self.log_message(f"Error during file upload: {e}")

    def list_files(self):#listing files that are in the server
        if not self.client_socket:#checking connection
            self.log_message("Error: Not connected to the server.")
            return
        try:
            self.client_socket.send("LIST".encode())#list command sent to server
            response = self.client_socket.recv(1024).decode()#response of server
            self.log_message(f"Raw server response: {response}")

            if response.startswith("LIST"):#check if response contains file list
                _, size = response.split('|')
                size = int(size)
                self.client_socket.send("READY".encode())#ready to receive list

                received_data = b""
                while len(received_data) < size:
                    chunk = self.client_socket.recv(4096)
                    if not chunk:
                        self.log_message("Connection closed prematurely.")
                        break
                    received_data += chunk

                file_list_str = received_data.decode()#decoding received data
                self.log_message("Available Files:")
                self.log_message(file_list_str)#display file list
            else:
                self.log_message(f"Unexpected response: {response}")
        except Exception as e:
            self.log_message(f"Error in list_files: {traceback.format_exc()}")

    def download_file(self):#downloading from the server
        if not self.client_socket:#check if connected
            self.log_message("Error: Not connected to the server.")
            return

        if not self.download_dir:#checking if there is a download directory
            self.log_message("Error: Please select a download directory first.")
            return

        owner_name, ok1 = QInputDialog.getText(self, "File Owner", "Enter owner's username:")#getting the data of the file
        filename, ok2 = QInputDialog.getText(self, "Filename", "Enter filename to download:")
        if not (ok1 and ok2 and owner_name and filename):
            self.log_message("File download canceled.")
            return

        try:
            command = f"DOWNLOAD|{owner_name}|{filename}"#download command
            self.client_socket.send(command.encode())#command send to server

            response = self.client_socket.recv(1024).decode()#server response
            if response.startswith("DOWNLOAD"):#checking the response
                _, filesize = response.split('|')
                filesize = int(filesize)

                self.client_socket.send("READY".encode())#ready to receive file
                filepath = os.path.join(self.download_dir, filename)#setting local file path

                with open(filepath, 'wb') as f:
                    bytes_received = 0
                    while bytes_received < filesize:#receiving file
                        chunk = self.client_socket.recv(4096)
                        if not chunk:
                            self.log_message("Error: Connection closed prematurely.")#error send to log if there is
                            break
                        f.write(chunk)
                        bytes_received += len(chunk)

                if bytes_received == filesize:#checking if file received correctly
                    self.log_message(f"Downloaded file '{filename}' to '{self.download_dir}'.")#success
                else:
                    self.log_message("Error: File download incomplete.")#errors
            else:
                self.log_message(f"Server error: {response}")
        except Exception as e:
            self.log_message(f"Error during file download: {e}")

    def delete_file(self):#delete an existing file from a server
        if not self.client_socket:#check connection
            self.log_message("Error: Not connected to the server.")
            return
        filename, ok = QInputDialog.getText(self, "Filename", "Enter filename to delete:")#filename to delete
        if ok and filename:
            command = f"DELETE|{filename}"#delete command
            try:
                self.client_socket.send(command.encode())#command sent
                response = self.client_socket.recv(1024).decode()#command received
                self.log_message(response)
            except Exception as e:#errors
                self.log_message(f"Error during file deletion: {e}")
        else:
            self.log_message("File deletion canceled.")

    def enable_buttons(self):#enabling file operation buttons
        self.upload_button.setEnabled(True)
        self.list_button.setEnabled(True)
        self.download_button.setEnabled(True)
        self.delete_button.setEnabled(True)

    def disable_buttons(self):#disabling file operation buttons
        self.upload_button.setEnabled(False)
        self.list_button.setEnabled(False)
        self.download_button.setEnabled(False)
        self.delete_button.setEnabled(False)

    def log_message(self, message):#displaying in log
        self.log_box.addItem(message)
        self.log_box.scrollToBottom()#scroll to the bottom of the log


if __name__ == "__main__":#application entry
    import sys
    app = QApplication(sys.argv)
    client_app = ClientApp()#client app window
    client_app.show()#show the app
    sys.exit(app.exec_())
