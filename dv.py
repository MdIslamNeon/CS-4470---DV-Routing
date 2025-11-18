#!/usr/bin/env python3
import argparse
import sys
import socket
from math import inf

import logic
import network
from cli import command_loop


# -------------------------------------------------------
# Load servers + neighbor costs from topology file
# -------------------------------------------------------
def load_topology_file(path: str, my_id: int):
    servers = {}
    neighbors = {}

    with open(path, "r") as f:
        lines = [line.strip() for line in f if line.strip()]

    num_servers = int(lines[0])
    num_links = int(lines[1])
    idx = 2

    # server entries
    for _ in range(num_servers):
        sid_str, ip, port_str = lines[idx].split()
        sid = int(sid_str)
        port = int(port_str)
        servers[sid] = (ip, port)
        idx += 1

    # neighbor entries
    for _ in range(num_links):
        a_str, b_str, c_str = lines[idx].split()
        a = int(a_str)
        b = int(b_str)

        if c_str.lower() == "inf":
            cost = inf
        else:
            cost = float(c_str)

        if a == my_id:
            neighbors[b] = cost
        elif b == my_id:
            neighbors[a] = cost

        idx += 1

    return servers, neighbors


# -------------------------------------------------------
# Auto-detect IP to find my server ID (demo mode)
# -------------------------------------------------------
def determine_my_id_and_port(path: str):
    """
    Determine this server's ID by matching REAL LAN IP
    to the topology file. Used in demo mode.
    """
    # Determine machine's LAN IP by outbound probe
    temp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        temp.connect(("8.8.8.8", 80))
        local_ip = temp.getsockname()[0]
    finally:
        temp.close()

    with open(path, "r") as f:
        lines = [line.strip() for line in f if line.strip()]

    num_servers = int(lines[0])
    idx = 2

    for _ in range(num_servers):
        sid_str, ip, port_str = lines[idx].split()
        sid = int(sid_str)
        port = int(port_str)

        # Must match exact IP AND port must be free
        if ip == local_ip:
            test = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                test.bind(("", port))
                test.close()
                return sid, ip, port   # success
            except OSError:
                pass

        idx += 1

    raise RuntimeError(
        f"Could not match this machine's IP ({local_ip}) to any entry in {path}.\n"
        "Update topology file IPs before demo."
    )


# -------------------------------------------------------
# Main
# -------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="DV Routing Protocol")
    parser.add_argument("-t", "--topology", required=True)
    parser.add_argument("-i", "--interval", required=True, type=float)
    parser.add_argument("-id", "--server-id", type=int,
                        help="Manual override (test mode)")

    args = parser.parse_args()

    topo_file = args.topology
    update_interval = args.interval

    # ------------ Mode selection ------------
    if args.server_id is not None:
        # Test mode: use override ID
        my_id = int(args.server_id)
        # Load topology entries
        with open(topo_file, "r") as f:
            lines = [line.strip() for line in f if line.strip()]
        idx = 2 + int(lines[0])  # skip server list
        # Now load all servers to look up IP/port
        idx = 2
        for _ in range(int(lines[0])):
            sid_str, ip, port_str = lines[idx].split()
            sid = int(sid_str)
            if sid == my_id:
                my_ip = ip
                my_port = int(port_str)
            idx += 1
    else:
        # Demo mode: auto-detect IP
        my_id, my_ip, my_port = determine_my_id_and_port(topo_file)

    # --------- Load topology with determined ID ---------
    servers, neighbor_costs = load_topology_file(topo_file, my_id)

    # --------- Initialize logic layer ---------
    logic.init(my_id, neighbor_costs)

    # --------- Initialize network layer ---------
    network.init_network(
        port=my_port,
        server_info=servers,
        routing_table=logic.routing,
        neighbors_dict=logic.neighbors,
        server_id=my_id,
    )

    # --------- Start periodic updates ---------
    network.start_periodic_updates(update_interval)

    # --------- Enter CLI loop ---------
    command_loop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)

