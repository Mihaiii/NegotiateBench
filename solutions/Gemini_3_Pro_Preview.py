import itertools

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.n = len(counts)
        
        # Track opponent behavior for modeling
        self.opp_kept = [0] * self.n
        self.opp_offers_made = 0
        self.my_turn_idx = 0
        
        # State space analysis
        # Determine if we can use brute force or need greedy heuristics
        size = 1
        for c in counts:
            size *= (c + 1)
        
        # Threshold for brute force: 250,000 states (manageable in 5s limit)
        self.brute_force = (size <= 250000)
        self.all_states = []
        
        if self.brute_force:
            ranges = [range(c + 1) for c in counts]
            # Generate all possible partitions (from my perspective: what I get)
            for s in itertools.product(*ranges):
                v = sum(s[i] * values[i] for i in range(self.n))
                self.all_states.append((s, v))
            # Sort states by my value descending for efficient searching
            self.all_states.sort(key=lambda x: x[1], reverse=True)

    def get_opp_values(self):
        # Estimate opponent valuations based on items they keep in their offers.
        # Logic: If they keep an item often, they probably value it highly.
        est = []
        for i in range(self.n):
            denom = self.opp_offers_made * self.counts[i]
            kept = self.opp_kept[i]
            # Laplace smoothing (assuming uniform prior 0.5) to handle small samples
            prob = (kept + 0.5) / (denom + 1.0) if denom > 0 else 0.5
            est.append(prob)
            
        # Normalize to my total value for symmetric scale comparison
        total_est = sum(c * v for c, v in zip(self.counts, est))
        if total_est < 1e-9:
            return [1.0] * self.n
        
        scale = self.total_value / total_est
        return [v * scale for v in est]

    def get_proposal_for_target(self, target_val, opp_vals):
        # Find a proposal maximizing OppVal such that MyVal >= target_val.
        # This increases the chance of acceptance for a given utility level.
        
        if self.brute_force:
            best_off = None
            best_opp_val = -1.0
            # Iterate states (sorted desc by my value)
            for s, mv in self.all_states:
                if mv < target_val:
                    break # Optimization: no subsequent state will meet target
                
                # Calculate opponent value for this split (Opp gets Counts - s)
                ov = sum((self.counts[i] - s[i]) * opp_vals[i] for i in range(self.n))
                if ov > best_opp_val:
                    best_opp_val = ov
                    best_off = list(s)
            
            if best_off is None:
                # If target is too high (e.g. > max possible), return max possible for me
                best_off = list(self.all_states[0][0])
            return best_off

        else:
            # Greedy Heuristic:
            # Sort items by Efficiency = MyValue / OppValue.
            # I take (keep) items with high efficiency.
            units = []
            for i in range(self.n):
                ov = opp_vals[i] if opp_vals[i] > 1e-9 else 1e-9
                ratio = self.values[i] / ov
                for _ in range(self.counts[i]):
                    units.append({'i': i, 'mv': self.values[i], 'r': ratio})
            
            # Sort descending (I prefer high ration)
            units.sort(key=lambda x: x['r'], reverse=True)
            
            cur_counts = [0] * self.n
            cur_my_val = 0
            
            # Fill bucket until target met
            for u in units:
                idx = u['i']
                cur_counts[idx] += 1
                cur_my_val += u['mv']
                if cur_my_val >= target_val:
                    break
            
            return cur_counts

    def get_ultimatum_proposal(self, opp_vals):
        # Used when it's My Last Turn to offer. 
        # Create an offer that gives me Max value while leaving Opponent a small non-zero value.
        # This acts as a rational "Ultimatum".
        min_opp_val = 0.1 
        
        if self.brute_force:
            # Search sorted states for max MyVal with OppVal > threshold
            for s, mv in self.all_states:
                ov = sum((self.counts[i] - s[i]) * opp_vals[i] for i in range(self.n))
                if ov >= min_opp_val:
                    return list(s)
            return list(self.counts) # Fallback if impossible
        else:
            # Greedy Reverse:
            # Start with All for Me. Give back items with highest Opp/My ratio.
            cur_counts = list(self.counts)
            cur_ov = 0
            
            units = []
            for i in range(self.n):
                mv = self.values[i] if self.values[i] > 1e-9 else 1e-9
                ratio = opp_vals[i] / mv
                for _ in range(self.counts[i]):
                    units.append({'i': i, 'ov': opp_vals[i], 'r': ratio})
            
            units.sort(key=lambda x: x['r'], reverse=True) # Highest benefit to Opp per cost to Me
            
            for u in units:
                if cur_ov >= min_opp_val:
                    break
                idx = u['i']
                cur_counts[idx] -= 1
                cur_ov += u['ov']
                
            return cur_counts

    def offer(self, o: list[int] | None) -> list[int] | None:
        turn = self.my_turn_idx * 2 + self.me
        turns_left = (self.max_rounds * 2) - turn
        
        # 1. Process incoming offer and update model
        if o is not None:
            self.opp_offers_made += 1
            for i in range(self.n):
                self.opp_kept[i] += (self.counts[i] - o[i])
            
            val_o = sum(o[i] * self.values[i] for i in range(self.n))
            
            # --- Acceptance Logic ---
            
            # Forced Acceptance: If this is the absolute last possible agreement turn.
            # If I reject, negotiation fails (0 for both).
            if turns_left <= 1:
                return None
            
            # Strategic Acceptance
            # Calculate Aspiration Target based on Boulware tactics (Stay high, drop late)
            progress = turn / (self.max_rounds * 2)
            
            if progress < 0.4:
                # Initial Phase: High aspiration
                req = 0.98
            elif progress < 0.8:
                # Middle Phase: Linear concesion
                # Drop 0.98 -> 0.70
                req = 0.98 - (0.28 * (progress - 0.4) / 0.4)
            else:
                # End Phase: Rapid drop to Reservation
                # Drop 0.70 -> 0.55
                req = 0.70 - (0.15 * (progress - 0.8) / 0.2)
                
            curr_target = self.total_value * req
            
            # Safety Override: Accept "Good Enough" Fair deals to avoid risky endgames
            # Nash bargaining solution usually creates values around 60-75% of max for each
            if progress > 0.5 and val_o >= self.total_value * 0.75:
                return None
            if progress > 0.85 and val_o >= self.total_value * 0.60:
                return None
                
            if val_o >= curr_target:
                return None
        else:
            # Turn 0 (First Mover)
            curr_target = self.total_value

        # 2. Generate Counter-Offer
        opp_vals = self.get_opp_values()
        
        # Check for Ultimatum (Proposer) scenario
        # If me=0, last turn is at 2*Rounds - 2. turns_left=2.
        # I make the final offer. Opponent can only Accept or Reject.
        if turns_left == 2:
            proposal = self.get_ultimatum_proposal(opp_vals)
        else:
            proposal = self.get_proposal_for_target(curr_target, opp_vals)
            
        self.my_turn_idx += 1
        return proposal