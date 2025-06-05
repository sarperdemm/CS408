import socket
import threading#threading to handle multiple clients
import os
import json
from PyQt5.QtWidgets import (#needed for GUI components
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QLabel,
    QListWidget, QFileDialog, QLineEdit, QWidget
)
from PyQt5.QtCore import Qt


class ServerApp(QMainWindow):
    def __init__(self):#server application start
        super().__init__()

        self.initUI()#user interface
        self.server_socket = None
        self.client_threads = []#list to track the active client threads
        self.files = {}  # {filename: owner}
        self.connected_clients = {}  # {client_name: client_socket}
        self.directory = ""#stroing uploaded files
        self.port = 0#port num

        #load previous existing files
        self.load_files()

    def initUI(self):
        self.setWindowTitle("Server Application")#window title
        self.setGeometry(100, 100, 600, 500)#window properties

        #layout
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        #directory selection
        self.dir_label = QLabel("Select storage directory:", self)
        layout.addWidget(self.dir_label)
        self.dir_button = QPushButton("Browse", self)
        self.dir_button.clicked.connect(self.select_directory)
        layout.addWidget(self.dir_button)
        self.selected_dir = QLabel("No directory selected", self)
        layout.addWidget(self.selected_dir)

        #port value
        self.port_label = QLabel("Enter Port Number:", self)
        layout.addWidget(self.port_label)
        self.port_input = QLineEdit(self)
        layout.addWidget(self.port_input)

        #server activation button
        self.start_button = QPushButton("Start Server", self)
        self.start_button.clicked.connect(self.start_server)
        layout.addWidget(self.start_button)

        #log
        self.log_label = QLabel("Server Logs:", self)
        layout.addWidget(self.log_label)
        self.log_box = QListWidget(self)
        layout.addWidget(self.log_box)

    def select_directory(self):#directory selection
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory:
            self.selected_dir.setText(directory)
            self.directory = directory#store directory path

    def start_server(self):#starting the server
        if not self.directory:#check if tehre is a directory
            self.log_message("Error: Please select a storage directory.")
            return
        try:
            self.port = int(self.port_input.text())#port number
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)#TCP socket
            self.server_socket.bind(("0.0.0.0", self.port))
            self.server_socket.listen(5)#listens for connections
            self.log_message(f"Server started on port {self.port}...")

            #validate files in the storage directory
            self.validate_files()

            #disable inputs
            self.dir_button.setEnabled(False)
            self.port_input.setEnabled(False)
            self.start_button.setEnabled(False)

            #start accepting clients
            threading.Thread(target=self.accept_clients, daemon=True).start()
        except Exception as e:
            self.log_message(f"Error: {e}")

    def validate_files(self):
        """Synchronize the files dictionary with the actual directory contents."""
        if not os.path.exists(self.directory):#check if directory exists
            self.log_message("Warning: Storage directory does not exist.")
            return

        #list of files in the directory
        actual_files = set(os.listdir(self.directory))
        missing_files = []

        #identify missing files
        for unique_filename in list(self.files.keys()):
            if unique_filename not in actual_files:
                missing_files.append(unique_filename)

        #remove missing files
        for missing_file in missing_files:
            self.log_message(f"File {missing_file} not found in directory. Removing from records.")
            del self.files[missing_file]

        #save the updated file list
        self.save_files()
        self.log_message("File records synchronized with the directory.")

    def accept_clients(self):#accept incoming clients
        while True:
            client_socket, client_address = self.server_socket.accept()
            threading.Thread(#starting a new thread for the client
                target=self.handle_client, args=(client_socket,), daemon=True
            ).start()

    def handle_client(self, client_socket):#handle each client individually
        try:
            # Receive client name
            name = client_socket.recv(1024).decode()
            if name in self.connected_clients:#check if there is an existing name
                client_socket.send("Error: Name already in use".encode())
                client_socket.close()#close if there is an existing name
                return

            #add client to the connected clients list
            self.connected_clients[name] = client_socket
            self.log_message(f"{name} connected.")

            #acknowledge connection
            client_socket.send("Connected successfully.".encode())

            #processing client commands
            while True:
                try:
                    data = client_socket.recv(1024).decode()
                    if not data:
                        break

                    #understand the command type
                    self.log_message(f"Command from {name}: {data}")
                    command = data.split('|')[0]
                    if command == "UPLOAD":
                        self.handle_upload(client_socket, name, data)
                    elif command == "DOWNLOAD":
                        self.handle_download(client_socket, name, data)
                    elif command == "DELETE":
                        self.handle_delete(client_socket, name, data)
                    elif command == "LIST":
                        self.handle_list(client_socket)
                    else:
                        client_socket.send("Error: Unknown command.".encode())
                except Exception as inner_e:
                    self.log_message(f"Error while processing command from {name}: {inner_e}")
        except Exception as outer_e:
            self.log_message(f"Error with client {name}: {outer_e}")
        finally:
            #cleanup on disconnection
            if name in self.connected_clients:
                del self.connected_clients[name]
            client_socket.close()#close the client socket
            self.log_message(f"{name} disconnected.")

    def handle_upload(self, client_socket, client_name, data):#handling file upload
        try:
            _, filename, filesize = data.split('|')
            filesize = int(filesize)
            unique_filename = f"{client_name}_{filename}"#create uniwue filename for this
            filepath = os.path.join(self.directory, unique_filename)

            # Receive file data
            with open(filepath, 'wb') as f:
                bytes_received = 0
                while bytes_received < filesize:#receive data
                    chunk = client_socket.recv(4096)
                    if not chunk:
                        break
                    f.write(chunk)
                    bytes_received += len(chunk)

            #update file list
            self.files[unique_filename] = client_name
            self.save_files()#save updated file
            self.log_message(f"{client_name} uploaded {filename}.")
            client_socket.send("Upload successful.".encode())
        except Exception as e:
            client_socket.send(f"Error: {e}".encode())

    def handle_download(self, client_socket, client_name, data):#handle file downloads
        try:
            _, owner_name, filename = data.split('|')
            unique_filename = f"{owner_name}_{filename}"
            if unique_filename not in self.files:#check if file exist if not error
                client_socket.send("Error: File not found.".encode())
                return
            filepath = os.path.join(self.directory, unique_filename)#file path
            filesize = os.path.getsize(filepath)
            client_socket.send(f"DOWNLOAD|{filesize}".encode())#notfying client with the file size

            #wait for ACK
            ack = client_socket.recv(1024).decode()
            if ack != "READY":
                return

            #send file
            with open(filepath, 'rb') as f:
                chunk = f.read(4096)
                while chunk:
                    client_socket.send(chunk)
                    chunk = f.read(4096)
            self.log_message(f"{client_name} downloaded {filename} from {owner_name}.")

            #let owner know if connected
            if owner_name in self.connected_clients:
                owner_socket = self.connected_clients[owner_name]
                owner_socket.send(f"NOTIFY|{client_name} downloaded your file {filename}.".encode())
        except Exception as e:
            client_socket.send(f"Error: {e}".encode())

    def handle_delete(self, client_socket, client_name, data):#handle file deletion
        try:
            _, filename = data.split('|')
            unique_filename = f"{client_name}_{filename}"
            if unique_filename not in self.files:#check if file exist
                client_socket.send("Error: File not found.".encode())#error if no file found with that name
                return
            filepath = os.path.join(self.directory, unique_filename)
            os.remove(filepath)#delete file
            del self.files[unique_filename]#remove from file record
            self.save_files()#update the new list
            self.log_message(f"{client_name} deleted {filename}.")
            client_socket.send("Delete successful.".encode())#log message of success
        except Exception as e:
            client_socket.send(f"Error: {e}".encode())

    def handle_list(self, client_socket):
        try:
            #construct the file list
            file_list = []
            for unique_filename, owner in self.files.items():
                _, filename = unique_filename.split('_', 1)
                file_list.append(f"{filename} (Owner: {owner})")
            file_list_str = "\n".join(file_list)

            #convert to bytes and calculate size
            file_list_bytes = file_list_str.encode()
            file_list_size = len(file_list_bytes)

            #log the size of the file list
            self.log_message(f"Sending file list of size: {file_list_size} bytes.")

            #send the size of the file list
            client_socket.send(f"LIST|{file_list_size}".encode())
            self.log_message("File list size sent to client.")

            #wait for ACK
            try:
                ack = client_socket.recv(1024).decode()
                self.log_message(f"Received acknowledgment from client: {ack}")
                if ack != "READY":
                    self.log_message("Client failed to acknowledge list request.")
                    return
            except Exception as e:
                self.log_message(f"Error receiving acknowledgment from client: {e}")
                return

            #send the file list data
            try:
                client_socket.sendall(file_list_bytes)
                self.log_message("File list sent to client successfully.")
            except Exception as e:
                self.log_message(f"Error while sending file list data: {e}")
        except Exception as e:
            self.log_message(f"Error in handle_list: {e}")

    def log_message(self, message):#messages in log
        self.log_box.addItem(message)
        self.log_box.scrollToBottom()#go to the last message automatically

    def load_files(self):#loading files from JSON
        if os.path.exists("files.json"):#check if file exists
            with open("files.json", "r") as f:
                self.files = json.load(f)#load JSON data

    def save_files(self):#save file records to JSON
        with open("files.json", "w") as f:
            json.dump(self.files, f)#save JSON data


if __name__ == "__main__":#starting page of app
    import sys
    app = QApplication(sys.argv)
    server_app = ServerApp()#create server app window
    server_app.show()#showing window of the app
    sys.exit(app.exec_())
