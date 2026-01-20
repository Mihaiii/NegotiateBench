import itertools

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.n = len(counts)
        self.opp_kept_sum = [0] * self.n
        self.opp_offers_count = 0
        self.turn_idx = 0
        
        # Calculate state space size to determine strategy
        self.prob_size = 1
        for c in counts:
            self.prob_size *= (c + 1)
        
        # Threshold for brute force (250k is safe for 5s timeout)
        self.is_brute_force = self.prob_size <= 250000
        self.sorted_states = []
        
        if self.is_brute_force:
            ranges = [range(c + 1) for c in counts]
            all_states = []
            # Generate all possible partitions (s represents what I GET)
            for s in itertools.product(*ranges):
                v = sum(s[i] * values[i] for i in range(self.n))
                all_states.append((v, s))
            # Sort states by My Value descending for efficient searching
            all_states.sort(key=lambda x: x[0], reverse=True)
            self.sorted_states = all_states

    def get_opp_vals(self):
        # Estimate opponent valuations based on what they keep in previous offers.
        # Logic: If Opponent keeps item i often, they likely value it highly.
        weights = []
        for i in range(self.n):
            kept = self.opp_kept_sum[i]
            # Laplace smoothing: start with 1.0 to avoid division by zero
            weights.append(kept + 1.0)
            
        # Normalize weights assuming their Total Value matches mine (symmetric assumption)
        w_total = sum(self.counts[i] * weights[i] for i in range(self.n))
        if w_total < 1e-9:
            return [1.0] * self.n
            
        scale = self.total_value / w_total
        return [w * scale for w in weights]

    def offer(self, o: list[int] | None) -> list[int] | None:
        # Calculate global turn index: 0, 1, ..., 2*max_rounds - 1
        turn = self.turn_idx * 2 + self.me
        turns_remaining = (self.max_rounds * 2) - turn
        
        # 1. Update Opponent Model
        if o is not None:
            self.opp_offers_count += 1
            for i in range(self.n):
                # Opponent kept = Total_Available - Offered_to_Me
                self.opp_kept_sum[i] += (self.counts[i] - o[i])

        # 2. Acceptance Logic
        if o is not None:
            my_val_o = sum(o[i] * self.values[i] for i in range(self.n))
            
            # Panic Condition: If I am the last mover (Agent 1) in the very last turn,
            # any non-zero value is better than the "No Deal" (0) result.
            if turns_remaining <= 1:
                if my_val_o > 0:
                    return None
            
            # Strategic Acceptance based on time (Boulware tactic)
            progress = turn / (self.max_rounds * 2)
            
            if progress < 0.2:
                req = 0.98
            elif progress < 0.6:
                req = 0.80
            elif progress < 0.90:
                req = 0.70
            elif progress < 0.98:
                req = 0.60
            else:
                req = 0.50
                
            # Accept if offer meets requirement
            if my_val_o >= (self.total_value * req):
                return None
            
            # Safety Net: If deal is "Good Enough" (e.g. 75%) past mid-game, take it
            # to avoid risky end-games against stubborn opponents.
            if progress > 0.4 and my_val_o >= self.total_value * 0.75:
                return None
            if progress > 0.8 and my_val_o >= self.total_value * 0.65:
                return None

        # 3. Counter-Offer Generation
        self.turn_idx += 1 # Prepare index for next call
        
        opp_vals = self.get_opp_vals()
        progress = turn / (self.max_rounds * 2)
        
        # Determine Value Target for the counter-offer
        if progress < 0.1:
            target_frac = 1.0
        elif progress < 0.8:
            # Linear drop 1.0 -> 0.75
            target_frac = 1.0 - (0.25 * (progress / 0.8))
        else:
            # End game drop 0.75 -> 0.50
            target_frac = 0.75 - (0.25 * (progress - 0.8) / 0.2)
            
        target_v = self.total_value * target_frac
        
        # Ultimatum Logic: If I am Agent 0 and this is my last turn (turns_left=2),
        # I must offer a deal the opponent will likely accept, or risk 0.
        is_ultimatum = (turns_remaining == 2)
        if is_ultimatum:
            min_opp_val = self.total_value * 0.20 # Guarantee them ~20%
        
        if self.is_brute_force:
            best_offer = None
            best_opp_val = -1.0
            valid_found = False
            
            # Use pre-sorted states (High MyVal -> Low MyVal)
            for mv, s in self.sorted_states:
                # Stop if we drop below target (unless we haven't found any valid cand)
                if mv < target_v:
                    if valid_found:
                        break
                    # If the maximum possible value is less than target, take max possible.
                    return list(self.sorted_states[0][1])

                valid_found = True
                
                # Calculate estimated Opponent Utility for this split
                ov = sum((self.counts[i] - s[i]) * opp_vals[i] for i in range(self.n))
                
                if is_ultimatum:
                    # Satisficing: Pick the first state (highest MyVal) where OppVal is decent
                    if ov >= min_opp_val:
                        return list(s)
                else:
                    # Maximizing: Find state with Max OppVal among those satisfying MyVal constraint
                    if ov > best_opp_val:
                        best_opp_val = ov
                        best_offer = list(s)
            
            if best_offer:
                return best_offer
            else:
                return list(self.sorted_states[0][1]) # Fallback
                
        else:
            # Greedy Heuristic for large state spaces
            # Break items into units and sort by efficiency: MyValue / OppValue
            units = []
            for i in range(self.n):
                ov = opp_vals[i] if opp_vals[i] > 1e-6 else 1e-6
                r = self.values[i] / ov
                for _ in range(self.counts[i]):
                    units.append( {'i': i, 'v': self.values[i], 'r': r} )
            
            # Sort units by Efficiency Descending
            units.sort(key=lambda x: x['r'], reverse=True)
            
            proposal = [0] * self.n
            curr_val = 0
            
            # Accumulate units until target is met
            for u in units:
                if curr_val >= target_v:
                    break
                proposal[u['i']] += 1
                curr_val += u['v']
                
            return proposal