from math import inf
from time import monotonic

# -------------------- exported globals --------------------
my_id: int | None = None
neighbors: dict[int, float] = {}
routing: dict[int, tuple[int | None, float]] = {}

# -------------------- internal state ----------------------
_neighbor_vectors: dict[int, dict[int, float]] = {}
_last_seen: dict[int, float] = {}

# -------------------- timing --------------------
UPDATE_INTERVAL: float = 1.0

def set_interval(interval: float) -> None:
    global UPDATE_INTERVAL
    UPDATE_INTERVAL = float(interval)
    
# -------------------- internal state ----------------------
_neighbor_vectors: dict[int, dict[int, float]] = {}
_last_seen: dict[int, float] = {}

# -------------------- init helpers ------------------------
def init(nid: int, initial_neighbors: dict[int, float]) -> None:
    global my_id, neighbors, routing, _neighbor_vectors, _last_seen

    my_id = int(nid)

    neighbors = {int(k): float(v) for k, v in initial_neighbors.items()}

    routing.clear()
    _neighbor_vectors.clear()
    _last_seen.clear()

    # Self route
    routing[my_id] = (None, 0.0)

    # Direct neighbors (finite only)
    for n, c in neighbors.items():
        if c < inf:
            routing[n] = (n, c)

    # Prevent timeout on startup
    now = monotonic()
    for n in neighbors:
        _last_seen[n] = now
        
def update_link(a: int, b: int, cost_str: str) -> None:
    """
    Change the cost of a direct link (a,b). Called by the CLI.
    Only applies if this node is either a or b.
    """
    global neighbors

    a = int(a)
    b = int(b)

    # If this server is not involved in the link, ignore
    if my_id not in (a, b):
        return

    # Determine which neighbor this refers to
    other = b if my_id == a else a

    # Parse cost
    cost_str = cost_str.strip().lower()
    if cost_str == "inf":
        new_cost = inf
    else:
        new_cost = float(cost_str)

    # Apply cost change
    neighbors[other] = new_cost

    # If link goes to INF, forget everything we know from that neighbor
    if new_cost == inf:
        _neighbor_vectors.pop(other, None)

    # Recompute routing table
    _recompute()

# -------------------- apply update from neighbor --------------------
def handle_update(sender_id: int, vector: dict[int, float]) -> None:
    s = int(sender_id)

    _last_seen[s] = monotonic()

    link_cost = neighbors.get(s, inf)
    if link_cost == inf:
        return

    norm = {}
    for d, c in vector.items():
        try:
            cost = float(c)
        except:
            cost = inf
        norm[int(d)] = (cost if cost >= 0 else inf)

    _neighbor_vectors[s] = norm
    _recompute()


# -------------------- recompute routing --------------------
def _recompute() -> None:
    if my_id is None:
        return

    new_table = {}

    # Always know route to self
    new_table[my_id] = (None, 0.0)

    # Direct neighbors
    for n, cost in neighbors.items():
        if cost < inf:
            new_table[n] = (n, cost)

    # All possible destinations
    all_dests = set(new_table.keys())
    for vec in _neighbor_vectors.values():
        all_dests |= set(vec.keys())

    for dest in sorted(all_dests):
        if dest == my_id:
            continue

        best_cost = new_table.get(dest, (None, inf))[1]
        best_next = new_table.get(dest, (None, inf))[0]

        # Try each neighbor
        for nbr, link_cost in neighbors.items():
            if link_cost == inf:
                continue

            # Poison reverse: if neighbor routes to dest *through me*, do not use it
            nbr_vec = _neighbor_vectors.get(nbr, {})
            nbr_best_cost = nbr_vec.get(dest, inf)

            # If neighbor's next-hop for dest == me → skip
            # i.e., neighbor advertises dest as if I am the next hop
            if nbr_vec.get(my_id, inf) == 0 and dest != nbr:
                # Neighbor’s best route to dest is through me → do poison reverse
                continue

            candidate = link_cost + nbr_best_cost
            if candidate < best_cost:
                best_cost = candidate
                best_next = nbr

        if best_cost < inf:
            new_table[dest] = (best_next, best_cost)

    routing.clear()
    routing.update(new_table)


# -------------------- periodic maintenance --------------------
def maintenance() -> None:
    """
    Remove neighbors that have not been heard from in > 3 × update interval.
    """
    if not neighbors:
        return

    now = monotonic()
    
    # NEW — correct timeout rule
    timeout = 3.0 * UPDATE_INTERVAL

    changed = False

    for nid, cost in list(neighbors.items()):
        if cost == inf:
            continue

        last = _last_seen.get(nid, 0.0)

        if now - last > timeout:
            neighbors[nid] = inf
            _neighbor_vectors.pop(nid, None)
            changed = True

    if changed:
        _recompute()



