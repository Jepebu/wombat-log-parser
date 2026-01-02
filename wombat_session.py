# wombat_session.py
# Handles networking for wombat log group sessions.

import miniupnpc
import secrets
import socket
import base64
import json
import struct

class GroupSession:
  def __init__(self):
    self.upnp = None
    self.secret = None
    self.status = None
    self.port = -1

  ### Establishes UPnP session.
  def __setup_upnp__(self):
    stage = 0 # Use 'stage' variable to track what part of UPnP setup we're on in error messages.
    try:
      # 1. Initialize UPnP to talk to the router
      stage = 1
      upnp = miniupnpc.UPnP()
      upnp.discoverdelay = 200
      upnp.discover()
      upnp.selectigd()


      
      # 2. Find a free internal port and map it externally
      stage = 2
      internal_ip = upnp.lanaddr
      external_port = 45678  # TODO: Set this to randomize later

    
      # Ask router to forward External:45678 -> Internal:45678
      # Protocol: TCP, Duration: 300 seconds (temporary)
      upnp.addportmapping(
        external_port, "TCP", 
        internal_ip, external_port, 
        "TnLCombatLogs", ""
      )

      self.port = external_port
      return upnp

    except Exception as e:
      raise self.UPNP_SETUP_EXCEPTION(e, stage)


  ### Calls the internal __setup_upnp__ if it isn't already done.
  ### Uses the created UPnP connection to generate a session code.
  def generate_session_code(self):

    # Make sure UPnP is setup
    if self.upnp is None:
      self.upnp = self.__setup_upnp__()

    public_ip = self.upnp.externalipaddress()
    self.secret = secrets.token_urlsafe(32)
    session_code_payload = {
      "ip": public_ip,
      "port": self.port,
      "secret": self.secret
    }

    # Encode the payload
    json_bytes = json.dumps(session_code_payload).encode('utf-8')
    session_code = base64.urlsafe_b64encode(json_bytes).decode('utf-8')

    return session_code
  
  ### Hosts a session
  def share(self, file_path):

    self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    with open(file_path, 'r') as csv_file:
      csv_data = csv_file.read()

    try:
      self.server_sock.bind(('0.0.0.0', self.port))
    except PermissionError:
      self.status = f"Port {self.port} is restricted."
      return

    conn = None
    try:
      while True:
        if self.server_sock._closed:
          break
        # Setup listening port
        self.server_sock.listen(2) # Listen for 1 connection
        conn, addr = self.server_sock.accept()


        ### --- Step 1: Authentication --- ###
        # Make sure the secret provided by the receiver matches the pre-generated secret.
        expected_secret_bytes = self.secret.encode('utf-8')
        buffer_size = len(expected_secret_bytes)
        received_secret = conn.recv(buffer_size)

        if received_secret != expected_secret_bytes:
          self.status = "Authentication from remote user failed."
          conn.close()


        ### --- Step 2: Transfer Prep --- ###
        # 1. Encode the data
        data_bytes = csv_data.encode('utf-8')

        # 2. Tell the receiver how many bytes of data to expect.
        #    Pack the length of the data into a 4-byte unsigned integer ('I')
        conn.sendall(struct.pack('>I', len(data_bytes)))


        ### --- Step 3: Send the payload --- ###
        conn.sendall(data_bytes)

    except OSError:
      pass

    except Exception as e:
      self.status = f"Error during transfer: {e}"
      return

    finally:
      if conn is not None:
        conn.close() 
      self.server_sock.close()



  ### Connects to the remote user through their provided session code.
  def connect_by_code(self, session_code):
    # Decode the string back to IP/Port
    try:
      decoded_bytes = base64.urlsafe_b64decode(session_code)
      info = json.loads(decoded_bytes)
    except:
      self.status = "Invalid code format."
      return

    target_ip = info["ip"]
    target_port = info["port"]
    secret = info["secret"]

    # Connect directly
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10) # 10 second timeout
    
    try:
        sock.connect((target_ip, target_port))
        
        ### --- Step 1: Authenticate --- ###
        sock.sendall(secret.encode('utf-8'))

        ### --- Step 2: Get exactly 4 bytes so we know the file size --- ###
        header = sock.recv(4)
        if not header:
          raise socket.error("Connection closed before metadata header was received.")

        (content_length,) = struct.unpack('>I', header)

        ### --- Step 3: Get the payload --- ###
        received_data = b''
        while len(received_data) < content_length:
          chunk = sock.recv(4096) # Receive up to 4KB at a time
          if not chunk:
            break
          received_data += chunk

        return received_data.decode('utf-8')
              

    except socket.error as e:
        self.status = f"Connection failed: {e}"

    finally:
      sock.close()




  ### GroupSession Exceptions
  class UPNP_SETUP_EXCEPTION(Exception):
    def __init__(self, message, stage):
      super().__init__(f"Error on stage {stage} of establishing UPnP connection: {message}")



### Test setup if run as main
if __name__ == "__main__":
  import sys
  if sys.argv[1] == "host":
    print(f"[DEBUG] Hosting session")
    host_session = GroupSession()
    session_code = host_session.generate_session_code()
    print(f"Session code is {session_code}")
    host_session.share(r"C:\Users\mbrag\AppData\Local\TL\Saved\CombatLogs\TLCombatLog-260101_211639.txt")

  elif sys.argv[1] == "receive":
    print(f"[DEBUG] Connection to host")
    recv_session = GroupSession()
    csv_data = recv_session.connect_by_code(sys.argv[2])
    print("Got data:")
    print(csv_data)