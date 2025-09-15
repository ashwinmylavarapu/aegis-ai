import subprocess
import json
import sys
import threading

# --- Helper function to read stderr without blocking ---
def read_stderr(pipe):
    """Reads from a pipe and prints to the script's stderr."""
    for line in iter(pipe.readline, b''):
        sys.stderr.write(line.decode('utf-8'))
    pipe.close()


# --- Functions to handle MCP message framing ---
def send_message(process, message_dict):
    """Sends a message to the MCP server process."""
    message_json = json.dumps(message_dict)
    message_bytes = message_json.encode('utf-8')
    
    # Create the Content-Length header
    header = f"Content-Length: {len(message_bytes)}\r\n\r\n".encode('utf-8')
    
    # Write header and message to stdin
    process.stdin.write(header + message_bytes)
    process.stdin.flush()
    print(f"--> Sent: {message_json}")


def receive_message(process):
    """Receives a message from the MCP server process."""
    header_lines = []
    content_length = -1
    
    # Read headers line by line from stdout
    while True:
        line_bytes = process.stdout.readline()
        if not line_bytes:
            return None # Process closed
        line = line_bytes.decode('utf-8').strip()
        if line.lower().startswith('content-length:'):
            content_length = int(line.split(':')[1].strip())
        elif line == '':
            # Empty line indicates end of headers
            break
            
    if content_length == -1:
        raise RuntimeError("Did not receive a Content-Length header.")
        
    # Read the exact number of bytes for the content
    content_bytes = process.stdout.read(content_length)
    content_json = content_bytes.decode('utf-8')
    
    print(f"<-- Received: {content_json}")
    return json.loads(content_json)


# --- Main execution logic ---
def main():
    """Starts the server via npx, sends a message, and shuts down."""
    
    print("Starting MCP server process via npx...")
    # This is the main change: we now use npx to run the package.
    # We also add `shell=True` for Windows compatibility, as npx is often a .cmd file.
    server_process = subprocess.Popen(
        ['npx', '@browsermcp/mcp'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=sys.platform == 'win32'
    )
    
    # Start a thread to read stderr so it doesn't block
    stderr_thread = threading.Thread(target=read_stderr, args=(server_process.stderr,))
    stderr_thread.daemon = True
    stderr_thread.start()

    print("Server started. Sending 'listTools' request...")
    
    # Construct a valid MCP request for 'listTools'
    list_tools_request = {
        "jsonrpc": "2.0",
        "id": 1, # Request ID to correlate requests and responses
        "method": "listTools",
        "params": {}
    }
    
    # Send the message and receive the response
    send_message(server_process, list_tools_request)
    response = receive_message(server_process)
    
    print("\n--- Test Result ---")
    if response:
        print("Successfully received response:")
        print(json.dumps(response, indent=2))
    else:
        print("Failed to receive response.")
        
    # Clean up
    print("\nShutting down server process...")
    server_process.terminate()
    server_process.wait(timeout=5)
    print("Server shut down.")


if __name__ == "__main__":
    main()