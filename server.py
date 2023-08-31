from http.server import BaseHTTPRequestHandler, HTTPServer
from colorama import Fore, Style
import socket
import urllib.parse
import psutil
import threading
import os
import urllib.request
from datetime import datetime
from urllib.parse import urlparse

class Logger:
    def __init__(self, log_file_path):
        self.log_file_path = log_file_path

    def log(self, message, severity="INFO"):
        # Color log based on severity
        # So it would look like this BLUE [2021-01-01 00:00:00] SEVERITY_COLOR SEVERITY BLUE Message
        sev_colors = {
            "INFO": Fore.BLUE,
            "ERROR": Fore.RED,
            "WARNING": Fore.YELLOW
        }
        severity_color = sev_colors.get(severity, Fore.WHITE)
        timestamp = datetime.now().strftime('%d/%m/%Y:%H:%M:%S')
        with open(self.log_file_path, 'a') as log_file:
            log_message = f"[{timestamp}] {severity_color}{severity}{Style.RESET_ALL} {message.strip()}\n"
            log_file.write(log_message)

    def read_logs(self):
        with open(self.log_file_path, 'r') as log_file:
            logs = log_file.readlines()
        return logs

class Commands:
    def __init__(self, logger, server_ip):
        self.logger = logger
        self.server_ip = server_ip

    def post_command_poc(self):
        self.logger.log("Executed Post command POC")
        return f"To POST a file using curl: curl -X POST --data-binary @your_file.txt http://{self.server_ip}:8000"

    def list_served_files(self):
        served_files = os.listdir()
        self.logger.log(f"List Files: {', '.join(served_files)}")
        print(f"{Fore.GREEN}Files served:{Style.RESET_ALL}")
        for file in served_files:
            print(f"{Fore.YELLOW}  - http://{self.server_ip}:8000/{file}{Style.RESET_ALL}")

    def read_logs(self):
        logs = self.logger.read_logs()
        for log in logs:
            print(log)

    def add_file(self):
        url = input(f"{Fore.YELLOW}Enter the URL to download the file from:{Style.RESET_ALL} ")
        try:
            parsed_url = urlparse(url)
            file_name = os.path.basename(parsed_url.path)
            i = 0
            original_file_name = file_name
            while os.path.exists(file_name):
                i += 1
                name, extension = os.path.splitext(original_file_name)
                file_name = f"{name}.{i}{extension}"

            urllib.request.urlretrieve(url, file_name)
            self.logger.log(f"Add File: {file_name} from {url}")
            return file_name
        except Exception as e:
            self.logger.log(f"Error while downloading file: {e}", "ERROR")
            print(f"{Fore.RED}Error while downloading file: {e}{Style.RESET_ALL}")
            return None

class RequestHandler(BaseHTTPRequestHandler):
    def __init__(self, logger, *args, **kwargs):
        self.logger = logger
        super().__init__(*args, **kwargs)

    def log_message(self, format, *args):
        return

    def do_GET(self):
        self._log_request("GET")
        self._handle_get_request()

    def do_POST(self):
        self._log_request("POST")
        self._handle_post_request()

    def _handle_get_request(self):
        path = urllib.parse.unquote(self.path)
        try:
            with open(path[1:], 'rb') as file:
                self._send_response(file.read())
        except FileNotFoundError:
            self._send_response(b'File not found')

    def _handle_post_request(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        upload_path = f'uploads/{timestamp}.txt'
        
        with open(upload_path, 'wb') as file:
            file.write(post_data)

        self._log_request("POST", upload_path=upload_path)
        self._send_response()

    def _send_response(self, data=None):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(data or b'OK')

    def _log_request(self, method, upload_path=None):
        log_entry = f"{method} {self.client_address[0]}:{self.client_address[1]} ({self.path})"
        if upload_path:
            log_entry += f" - {upload_path}"
        self.logger.log(log_entry)


class Server:
    def __init__(self, logger):
        self.logger = logger
        self.ip = self.select_interface()

    def select_interface(self):
        interfaces = psutil.net_if_addrs()
        available_interfaces = {}
        for interface, addrs in interfaces.items():
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    available_interfaces[interface] = addr.address
                    print(f"{Fore.GREEN}Interface: {Fore.WHITE}{interface} {Fore.YELLOW}IP Address: {Fore.WHITE}{addr.address}{Style.RESET_ALL}")

        while True:
            selected_interface = input(f"{Fore.YELLOW}Enter the interface name to get its IP address:{Style.RESET_ALL} ")
            if selected_interface in available_interfaces:
                self.logger.log(f"Selected interface: {selected_interface}", "INFO")
                return available_interfaces[selected_interface]
            else:
                self.logger.log(f"Invalid interface name. Please try again.", "ERROR")
                print(f"{Fore.RED}Invalid interface name. Please try again.{Style.RESET_ALL}")

    def run(self):
        server_address = (self.ip, 8000)
        httpd = HTTPServer(server_address, lambda *args, **kwargs: RequestHandler(self.logger, *args, **kwargs))
        httpd.serve_forever()

class Menu:
    def __init__(self, logger, commands):
        self.logger = logger
        self.commands = commands
        self.menu_items = [
            {"name": "Exit", "func": None}
        ]

    def add_command(self, name, func):
        # Insert new command before the "Exit" option
        self.menu_items.insert(-1, {"name": name, "func": func})

    def display(self):
        while True:
            print(f"{Fore.GREEN}\nMenu:{Style.RESET_ALL}")
            for i, item in enumerate(self.menu_items):
                print(f"{Fore.BLUE}{i + 1}. {Fore.WHITE}{item['name']}{Style.RESET_ALL}")

            choice = int(input(f"{Fore.YELLOW}Enter your choice:{Style.RESET_ALL} ")) - 1

            if 0 <= choice < len(self.menu_items):
                selected_item = self.menu_items[choice]

                if selected_item['func']:
                    result = selected_item['func']()
                    if result:
                        print(result)
                    self.logger.log(f"Executed {selected_item['name']}", "INFO")
                else:
                    self.logger.log("Server Exit", "INFO")
                    print(f"{Fore.RED}Exiting...{Style.RESET_ALL}")
                    break


# Initialize logger
current_time = datetime.now().strftime('%d%m%Y%H%M%S')
logs_dir = './logs'
os.makedirs(logs_dir, exist_ok=True)
log_file_path = os.path.join(logs_dir, f"{current_time}.txt")
logger = Logger(log_file_path)

# Initialize server with the selected interface
server = Server(logger)

# Initialize command with the server's IP
commands = Commands(logger, server.ip)

# Initialize Menu
menu = Menu(logger, commands)
# Add commands to menu
menu.add_command("Add File", commands.add_file)
menu.add_command("Post command POC", commands.post_command_poc)
menu.add_command("List Files", commands.list_served_files)
menu.add_command("Read Logs", commands.read_logs)



# Run server in a separate thread
server_thread = threading.Thread(target=server.run)
server_thread.daemon = True
server_thread.start()

# Display menu
menu.display()