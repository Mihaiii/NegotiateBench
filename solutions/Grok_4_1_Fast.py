import itertools

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts[:]
        self.values = values[:]
        self.n = len(counts)
        self.total = sum(c * v for c, v in zip(counts, values))
        self.max_turns = 2 * max_rounds
        self.turn_count = 0
        self.opp_fracs_history = []
        self.product_ranges = [range(counts[i] + 1) for i in range(self.n)]
        est_num = 1
        too_large = False
        for rlen in map(len, self.product_ranges):
            est_num *= rlen
            if est_num > 1000000:
                too_large = True
                break
        if not too_large:
            self.possible = list(itertools.product(*self.product_ranges))
            self.num_possible = len(self.possible)
            self.my_vals = [sum(self.values[i] * self.possible[k][i] for i in range(self.n)) for k in range(self.num_possible)]
            self.order = sorted(range(self.num_possible), key=lambda k: -self.my_vals[k])
        else:
            self.possible = None
            self.order = None
            self.my_vals = None

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        if o is not None:
            o_list = list(o)
            opp_keep = [self.counts[i] - o_list[i] for i in range(self.n)]
            fracs = [opp_keep[i] / self.counts[i] if self.counts[i] > 0 else 0.0 for i in range(self.n)]
            self.opp_fracs_history.append(tuple(fracs))

        global_turn = 2 * self.turn_count - 1 if self.me == 0 else 2 * self.turn_count
        remaining_turns = max(0, self.max_turns - global_turn + 1)
        frac_rem = remaining_turns / self.max_turns if self.max_turns > 0 else 0.0

        # Compute opp_vals
        num_obs = len(self.opp_fracs_history)
        avg_frac_keep = [0.0] * self.n
        if num_obs > 0:
            recent = self.opp_fracs_history[-3:] if num_obs >= 3 else self.opp_fracs_history
            num_r = len(recent)
            for i in range(self.n):
                avg_frac_keep[i] = sum(h[i] for h in recent) / num_r
        weighted = sum(avg_frac_keep[i] * self.counts[i] for i in range(self.n))
        if weighted > 1e-9:
            opp_vals = [avg_frac_keep[i] * self.total / weighted for i in range(self.n)]
        else:
            total_items = sum(self.counts)
            u = self.total / total_items if total_items > 0 else 0.0
            opp_vals = [u] * self.n

        # Decide to accept
        if o is not None:
            my_val_offer = sum(self.values[i] * (self.counts[i] - o[i]) for i in range(self.n))
            accept_threshold = 0.0 if remaining_turns <= 1 else self.total * (0.40 + 0.20 * frac_rem)
            if my_val_offer >= accept_threshold:
                return None

        # Make counter-offer
        frac_rem_opp = max(0.0, (remaining_turns - 1) / self.max_turns)
        opp_their_res = self.total * (0.40 + 0.20 * frac_rem_opp)
        best_x = None
        if self.possible is not None:
            best_my_val = -1.0
            for k in self.order:
                x = self.possible[k]
                opp_get = tuple(self.counts[i] - x[i] for i in range(self.n))
                opp_gv = sum(opp_vals[i] * opp_get[i] for i in range(self.n))
                my_gv = self.my_vals[k]
                if opp_gv >= opp_their_res and my_gv > best_my_val:
                    best_my_val = my_gv
                    best_x = list(x)
                    break
            if best_x is None:
                best_x = list(self.possible[self.order[0]])
        else:
            # Greedy knapsack approx
            total_opp_val = sum(opp_vals[i] * self.counts[i] for i in range(self.n))
            cap = total_opp_val - opp_their_res
            if cap <= 0:
                best_x = [0] * self.n
            else:
                densities = []
                for i in range(self.n):
                    w = opp_vals[i]
                    v = self.values[i]
                    dens = float('inf') if w <= 0 and v > 0 else (v / w if w > 0 else 0.0)
                    densities.append((dens, i))
                densities.sort(reverse=True)
                x = [0] * self.n
                curr_used = 0.0
                for _, i in densities:
                    if curr_used >= cap:
                        break
                    rem_cap = cap - curr_used
                    w_per = opp_vals[i]
                    max_k = self.counts[i]
                    if w_per > 0:
                        k = min(max_k, int(rem_cap / w_per))
                    else:
                        k = max_k
                    x[i] = k
                    curr_used += k * w_per
                best_x = x
        return best_x