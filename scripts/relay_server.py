#!/usr/bin/env python3
"""WDA Relay Server — bridges reverse-connected WDA to local HTTP clients.

Architecture:
  iPhone WDA ---(reverse TCP)---> relay:8201 (pool of connections)
  MCP / curl ---(HTTP request)---> relay:8100 ---> pick a WDA conn ---> forward & respond

WDA continuously connects to relay:8201. Each connection handles one HTTP request.
After the response is sent, the connection closes, and WDA reconnects immediately.
This pool model is simple, reliable, and needs no multiplexing.

Usage:
    python3 relay_server.py [--tunnel-port 8201] [--proxy-port 8100]
"""

import argparse
import socket
import threading
import queue
import time

wda_pool: queue.Queue[socket.socket] = queue.Queue()
stats = {"total_requests": 0, "wda_connections": 0}


def accept_wda_connections(tunnel_sock: socket.socket):
    """Accept reverse connections from WDA into the pool."""
    tunnel_sock.listen(20)
    print(f"[tunnel] Waiting for WDA connections on :{tunnel_sock.getsockname()[1]}")
    while True:
        conn, addr = tunnel_sock.accept()
        conn.settimeout(60)
        wda_pool.put(conn)
        stats["wda_connections"] += 1
        pool_size = wda_pool.qsize()
        if pool_size == 1 or pool_size % 5 == 0:
            print(f"[tunnel] WDA connected from {addr[0]} (pool: {pool_size})")


def read_http_request(sock: socket.socket) -> bytes:
    """Read a complete HTTP request from a socket."""
    data = b""
    sock.settimeout(30)
    while True:
        chunk = sock.recv(65536)
        if not chunk:
            return data
        data += chunk
        if b"\r\n\r\n" in data:
            header_end = data.index(b"\r\n\r\n") + 4
            content_length = 0
            for line in data[:header_end].decode("utf-8", errors="replace").split("\r\n"):
                if line.lower().startswith("content-length:"):
                    content_length = int(line.split(":")[1].strip())
            body_so_far = len(data) - header_end
            while body_so_far < content_length:
                chunk = sock.recv(min(content_length - body_so_far, 65536))
                if not chunk:
                    break
                data += chunk
                body_so_far += len(chunk)
            return data


def read_http_response(sock: socket.socket) -> bytes:
    """Read a complete HTTP response from a socket."""
    data = b""
    sock.settimeout(30)
    while True:
        chunk = sock.recv(65536)
        if not chunk:
            return data
        data += chunk
        if b"\r\n\r\n" in data:
            header_end = data.index(b"\r\n\r\n") + 4
            headers_str = data[:header_end].decode("utf-8", errors="replace").lower()
            if "transfer-encoding: chunked" in headers_str:
                while not data.endswith(b"0\r\n\r\n"):
                    chunk = sock.recv(65536)
                    if not chunk:
                        break
                    data += chunk
                return data
            content_length = 0
            for line in headers_str.split("\r\n"):
                if line.startswith("content-length:"):
                    content_length = int(line.split(":")[1].strip())
            body_so_far = len(data) - header_end
            while body_so_far < content_length:
                chunk = sock.recv(min(content_length - body_so_far, 65536))
                if not chunk:
                    break
                data += chunk
                body_so_far += len(chunk)
            return data


def handle_http_client(client: socket.socket):
    """Forward one HTTP request to WDA via a pooled reverse connection."""
    try:
        request = read_http_request(client)
        if not request:
            client.close()
            return

        # Get a WDA connection from the pool
        try:
            wda_conn = wda_pool.get(timeout=10)
        except queue.Empty:
            error_resp = (
                b"HTTP/1.1 503 Service Unavailable\r\n"
                b"Content-Type: application/json\r\n\r\n"
                b'{"error": "No WDA connections available. Is WDA running with WDA_RELAY_HOST set?"}\n'
            )
            client.sendall(error_resp)
            client.close()
            return

        try:
            wda_conn.sendall(request)
            response = read_http_response(wda_conn)
            if response:
                client.sendall(response)
            stats["total_requests"] += 1
        except Exception as e:
            error_resp = (
                b"HTTP/1.1 502 Bad Gateway\r\n"
                b"Content-Type: application/json\r\n\r\n"
                b'{"error": "WDA connection error: ' + str(e).encode() + b'"}\n'
            )
            try:
                client.sendall(error_resp)
            except Exception:
                pass
        finally:
            try:
                wda_conn.close()
            except Exception:
                pass
    except Exception as e:
        print(f"[proxy] Client error: {e}")
    finally:
        try:
            client.close()
        except Exception:
            pass


def accept_http_clients(proxy_sock: socket.socket):
    """Accept HTTP clients and forward to WDA."""
    proxy_sock.listen(10)
    print(f"[proxy] HTTP proxy on :{proxy_sock.getsockname()[1]} — point your tools here")
    while True:
        client, _ = proxy_sock.accept()
        threading.Thread(target=handle_http_client, args=(client,), daemon=True).start()


def status_printer():
    """Print periodic status."""
    while True:
        time.sleep(60)
        print(f"[status] Pool: {wda_pool.qsize()} connections, Total requests: {stats['total_requests']}, WDA connects: {stats['wda_connections']}")


def main():
    parser = argparse.ArgumentParser(description="WDA Relay Server")
    parser.add_argument("--tunnel-port", type=int, default=8201)
    parser.add_argument("--proxy-port", type=int, default=8100)
    args = parser.parse_args()

    tunnel_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tunnel_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tunnel_sock.bind(("0.0.0.0", args.tunnel_port))

    proxy_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    proxy_sock.bind(("0.0.0.0", args.proxy_port))

    print("=" * 50)
    print("  WDA Relay Server")
    print(f"  Tunnel: :{args.tunnel_port} (WDA connects here)")
    print(f"  Proxy:  :{args.proxy_port} (your tools connect here)")
    print("=" * 50)

    threading.Thread(target=accept_wda_connections, args=(tunnel_sock,), daemon=True).start()
    threading.Thread(target=accept_http_clients, args=(proxy_sock,), daemon=True).start()
    threading.Thread(target=status_printer, daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down.")


if __name__ == "__main__":
    main()
