import argparse
import sys
from logic import init as logic_init
from cli import command_loop
from network import init_network, start_periodic_updates


def parse_topology_file(path):
    """
    Reads the topology file and returns:
    - servers: { server_id: (ip, port) }
    - neighbors: { neighbor_id: cost }
    """

    servers = {}
    neighbors = {}

    try:
        with open(path, "r") as f:
            lines = [line.strip() for line in f if line.strip()]
    except:
        print("Error opening topology file.")
        sys.exit(1)

    # First two lines
    num_servers = int(lines[0])
    num_neighbors = int(lines[1])

    # Next num_servers lines: server-id ip port
    idx = 2
    for _ in range(num_servers):
        parts = lines[idx].split()
        sid = int(parts[0])
        ip = parts[1]
        port = int(parts[2])
        servers[sid] = (ip, port)
        idx += 1

    # Remaining lines: self-id neighbor-id cost
    for _ in range(num_neighbors):
        parts = lines[idx].split()
        self_id = int(parts[0])
        nb = int(parts[1])
        cost = parts[2]
        neighbors.setdefault(self_id, {})[nb] = float("inf") if cost == "inf" else float(cost)
        idx += 1

    return servers, neighbors


def determine_my_id(servers, my_port):
    """
    Determine which server ID we are based on the port we bind to.
    This is the REQUIRED behavior in the project spec.
    """

    for sid, (ip, port) in servers.items():
        if port == my_port:
            return sid

    print("ERROR: Could not determine my server-id from topology file (port mismatch).")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Distance Vector Routing Server")

    parser.add_argument("-t", required=True, help="topology file")
    parser.add_argument("-i", required=True, type=int, help="routing update interval (seconds)")

    args = parser.parse_args()

    topo_path = args.t
    interval = args.i

    # ---- Parse topology file ----
    servers, all_neighbors = parse_topology_file(topo_path)

    # Find my port by looking at all entries in the topo
    # The trick: The topology file stores neighbors in blocks keyed by EACH server
    # We find which block corresponds to THIS server by matching ports after binding.
    # But we need to know my_port BEFORE init_network.
    #
    # Simple solution:
    # Every topoN.txt corresponds to server N.
    # So look for ONLY the neighbors with key "N".
    #
    # But the spec wants auto-detection:
    # Auto-detection must be done based on PORT after we bind.
    #
    # So: we must choose a dummy port first, but network.py will bind for us.
    #
    # Best solution:
    # Read MY port by looking for ANY server whose neighbors block exists.
    # Actually, project files always have the neighbors listed for the server whose topo it is.
    # Example: topo3.txt has lines:
    #     3 1 4
    #     3 4 3
    #
    # So: the "self-id" for neighbors tells us our identity before networking starts.
    #     my_id = the server id present in neighbors dict.

    if len(all_neighbors) == 0:
        print("ERROR: Topology file missing neighbor entries.")
        sys.exit(1)

    # Extract the server id THIS topo file belongs to
    my_id_from_file = list(all_neighbors.keys())[0]

    # Extract my port from server definitions
    my_port = servers[my_id_from_file][1]

    # ---- Initialize network and logic ----
    init_network(my_port, servers, None, None, my_id_from_file)

    # neighbors dict for logic.init() should be just the neighbor costs for THIS server
    my_neighbors = all_neighbors[my_id_from_file]

    # Initialize DV logic with our ID + neighbors
    logic_init(my_id_from_file, my_neighbors)

    # Start periodic DV updates
    start_periodic_updates(interval)

    # Enter command loop
    command_loop()


if __name__ == "__main__":
    main()
