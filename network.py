import socket
import struct
import threading
import time
import sys
from math import inf

import logic

sock = None
servers: dict[int, tuple[str, int]] = {}   # server_id -> (ip, port)
pkt_count = 0
my_port = None
my_ip = None
my_id = None


def init_network(port, server_info, routing_table, neighbors_dict, server_id):
    """
    Set up UDP socket and start receiver thread.
    NOTE: routing_table and neighbors_dict arguments are ignored; we always
    read the live tables from logic.routing / logic.neighbors.
    """
    global sock, servers, my_port, my_ip, my_id

    my_id = int(server_id)
    my_port = int(port)
    servers = server_info

    # use IP from topo file
    my_ip = servers[my_id][0]

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", my_port))

    threading.Thread(target=receive_loop, daemon=True).start()


# ---------------------- PACK DV UPDATE -----------------------------
def pack_update():
    """
    Build routing update message:

    [num_entries:2] [sender_port:2] [sender_ip:4]
    For every server in the network (NOT just routing table):
        [dest_ip:4] [dest_port:2] [dest_id:2] [cost:2]
    """
    msg = bytearray()

    # include ALL servers
    all_ids = sorted(servers.keys())
    num_entries = len(all_ids)

    msg.extend(struct.pack("!H", num_entries))
    msg.extend(struct.pack("!H", my_port))
    msg.extend(socket.inet_aton(my_ip))

    for dest_id in all_ids:
        dest_ip, dest_port = servers[dest_id]
        next_hop, cost = logic.routing.get(dest_id, (None, inf))

        cost_field = int(cost) if cost < inf else 0xFFFF

        msg.extend(socket.inet_aton(dest_ip))
        msg.extend(struct.pack("!H", dest_port))
        msg.extend(struct.pack("!H", dest_id))
        msg.extend(struct.pack("!H", cost_field))

    return bytes(msg)



# ---------------------- UNPACK DV UPDATE ---------------------------
def unpack_update(data: bytes):
    """
    Reverse of pack_update(). Returns (sender_id, dv_dict)
    where dv_dict: dest_id -> advertised_cost_from_sender
    """
    offset = 0

    num_entries = struct.unpack_from("!H", data, offset)[0]
    offset += 2

    port = struct.unpack_from("!H", data, offset)[0]
    offset += 2

    ip = socket.inet_ntoa(data[offset:offset + 4])
    offset += 4

    sender_id = None
    for sid, (sip, sport) in servers.items():
        if sip == ip and sport == port:
            sender_id = sid
            break

    dv = {}

    for _ in range(num_entries):
        dest_ip = socket.inet_ntoa(data[offset:offset + 4])
        offset += 4

        dest_port = struct.unpack_from("!H", data, offset)[0]
        offset += 2

        dest_id = struct.unpack_from("!H", data, offset)[0]
        offset += 2

        cost = struct.unpack_from("!H", data, offset)[0]
        offset += 2

        if cost == 0xFFFF:
            dv[dest_id] = inf
        else:
            dv[dest_id] = float(cost)

    return sender_id, dv


# ---------------------- RECEIVE LOOP -------------------------------
def receive_loop():
    global pkt_count

    while True:
        try:
            data, addr = sock.recvfrom(4096)
            sender_id, dv = unpack_update(data)

            if sender_id is None:
                continue

            pkt_count += 1
            print(f"RECEIVED A MESSAGE FROM SERVER {sender_id}")

            # hand to logic
            logic.handle_update(sender_id, dv)

        except Exception as e:
            # swallow errors but log them to stderr so they don't kill the process
            print(f"[ERROR] receive_loop on server {my_id}: {e}", file=sys.stderr)


# ---------------------- PERIODIC SEND ------------------------------
def send_to_neighbors():
    try:
        payload = pack_update()

        for nid, cost in logic.neighbors.items():
            ip, port = servers[nid]
            if cost < inf:
                sock.sendto(payload, (ip, port))
    except Exception as e:
        print(f"[ERROR] send_to_neighbors on server {my_id}: {e}", file=sys.stderr)


def start_periodic_updates(interval):
    """
    Called by dv.py to start the periodic DV broadcast + maintenance.
    """
    logic.set_interval(interval)

    def loop():
        while True:
            time.sleep(interval)
            logic.maintenance()
            send_to_neighbors()

    threading.Thread(target=loop, daemon=True).start()

