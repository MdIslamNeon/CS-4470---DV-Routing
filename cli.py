import sys
from math import inf

import logic
import network


# --- main input loop ---
def command_loop():
    while True:
        try:
            line = input().strip()
        except EOFError:
            return  # user closed input (rare)

        if not line:
            continue

        parts = line.split()
        cmd = parts[0].lower()

        # ----------------------- update -----------------------
        if cmd == "update":
            if len(parts) != 4:
                print("update invalid_arguments")
                continue

            a = int(parts[1])
            b = int(parts[2])
            cost = parts[3]   # may be "inf"

            update(a, b, cost)
            continue

        # ----------------------- step -------------------------
        elif cmd == "step":
            step()
            continue

        # ----------------------- packets ----------------------
        elif cmd == "packets":
            packets()
            continue

        # ----------------------- display ----------------------
        elif cmd == "display":
            display()
            continue

        # ----------------------- disable ----------------------
        elif cmd == "disable":
            if len(parts) != 2:
                print("disable invalid_arguments")
                continue

            nid = int(parts[1])
            disable(nid)
            continue

        # ----------------------- crash ------------------------
        elif cmd == "crash":
            crash()
            continue

        # ----------------------- unknown ----------------------
        else:
            print(f"{cmd} unknown_command")


def update(a, b, cost):
    """
    Handle:  update <server-ID1> <server-ID2> <cost>

    - This command will be issued to ALL servers by the grader
    - Only the two endpoint servers (ID1 and ID2) actually update the link
    - Other servers ignore it but still print 'update SUCCESS'
    """
    try:
        a = int(a)
        b = int(b)

        # Only endpoints should actually change the link
        if logic.my_id in (a, b):
            # cost is a string; update_link will handle "inf" or integer conversion
            logic.update_link(a, b, cost)

        # Spec: even servers not involved still print SUCCESS (they just ignore)
        print("update SUCCESS")

    except Exception as e:
        print(f"update {e}")


def step():
    """
    Handle the 'step' command

    - Immediately send a distance vector update to all neighbors
      with a finite link cost.
    - After sending packets, print:  step SUCCESS
    """
    try:
        # Reuse the network helper that already knows how to send to neighbors
        network.send_to_neighbors()
        print("step SUCCESS")

    except Exception as e:
        print(f"step {e}")


def packets():
    """
    Handle the 'packets' command

    - Print number of DV packets received since last 'packets' call.
    - Reset the counter.
    - Print 'packets SUCCESS'.
    """
    try:
        # Print count first
        print(network.pkt_count)

        # Reset counter in the network module
        network.pkt_count = 0

        # Required by spec
        print("packets SUCCESS")

    except Exception as e:
        print(f"packets {e}")


def display():
    """
    Handle the 'display' command

    Print the routing table in sorted order:
       <destination-ID> <next-hop-ID> <cost>

    Required behaviors:
    - If next-hop is None, print -1
    - If cost is infinite, print 65535
    - MUST be sorted by destination ID
    - Print 'display SUCCESS' afterward
    """
    try:
        # Sort by destination ID
        for dest in sorted(logic.routing.keys()):
            next_hop, cost = logic.routing[dest]

            # Format next hop
            nh_print = next_hop if next_hop is not None else -1

            # Format cost (infinity => 65535)
            cost_print = int(cost) if cost < inf else 65535

            print(f"{dest} {nh_print} {cost_print}")

        print("display SUCCESS")

    except Exception as e:
        print(f"display {e}")


def disable(nid):
    """
    Handle:  disable <server-ID>

    - Only valid if nid is a direct neighbor.
    - If not a neighbor, print an error.
    - If valid, set link cost to infinity via logic.update_link.
    - Then print 'disable SUCCESS'.
    """
    try:
        nid = int(nid)

        # Check if it's a current direct neighbor with finite cost
        if nid not in logic.neighbors or logic.neighbors[nid] == inf:
            print("disable not_a_neighbor")
            return

        # Use the logic helper to update cost + recompute routing
        logic.update_link(logic.my_id, nid, "inf")

        print("disable SUCCESS")

    except Exception as e:
        print(f"disable {e}")


def crash():
    """
    Handle the 'crash' command

    - Set all neighbors' link costs to infinity via logic.update_link.
    - Print 'crash SUCCESS'.
    - Terminate the process.
    """
    try:
        # Mark all links down using logic helper
        for nid in list(logic.neighbors.keys()):
            logic.update_link(logic.my_id, nid, "inf")

        print("crash SUCCESS")

        # Terminate this server instance
        sys.exit(0)

    except Exception as e:
        print(f"crash {e}")
