import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.round_idx = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.num_items = len(counts)
        
        # Opponent modeling: track what items the opponent keeps.
        self.opp_history_sum = [0.0] * self.num_items

    def offer(self, o: list[int] | None) -> list[int] | None:
        # --- 1. Round Tracking ---
        # The framework specifies max_rounds. A round consists of 2 turns (one by each).
        # We track round_idx from 1 to max_rounds.
        if self.me == 0:
            # Player 1 moves at start of Round 1, 2, ...
            if o is None:
                self.round_idx = 1
            else:
                self.round_idx += 1
        else:
            # Player 2 moves as response.
            # Initial call with o != None is still Round 1.
            if self.round_idx == 0:
                self.round_idx = 1
            else:
                self.round_idx += 1

        # --- 2. Update Opponent Model ---
        offer_val_for_me = 0
        if o is not None:
            # Calculate value of their offer to me
            offer_val_for_me = sum(o[i] * self.values[i] for i in range(self.num_items))
            
            # Infer what they want: They keep `counts - o`
            for i in range(self.num_items):
                kept = self.counts[i] - o[i]
                if kept > 0:
                    self.opp_history_sum[i] += kept

        # --- 3. Acceptance Reasoning ---
        if o is not None:
            # A. Optimal Deal: Accept if we get everything or full value.
            if offer_val_for_me >= self.total_value:
                return None
            
            # B. Last Mover Disadvantage (Player 2):
            # If I am P2 and this is the very last turn of the game, 
            # rejecting means we both get 0. Rationality dictates accepting any > 0.
            if self.me == 1 and self.round_idx == self.max_rounds:
                if offer_val_for_me > 0:
                    return None
            
            # C. Concession Curve Accept:
            # Accept if offer meets our dynamic reservation price.
            # Starts high (1.0) and relaxes to ~0.55 over time.
            progress = (self.round_idx - 1) / max(1, self.max_rounds - 1)
            
            res_start = 1.0
            res_end = 0.55 # Slightly better than 50/50 split
            # Cubic decay - stay tough early, concede faster later
            factor = progress ** 3.0
            reservation_frac = res_start - (res_start - res_end) * factor
            
            if offer_val_for_me >= int(reservation_frac * self.total_value):
                return None
                
            # D. Pre-Ultimatum Safety (Round >= Max - 1):
            # If we are near the end, accept any "Fair" deal (50%) to avoid 
            # the risky Ultimatum round where P1 might squeeze us.
            if self.round_idx >= self.max_rounds - 1:
                # Accept if we get at least half value
                if offer_val_for_me >= self.total_value * 0.50:
                    return None

        # --- 4. Counter-Offer Generation ---
        
        # A. Ultimatum (Player 1, Last Round):
        # I make the final offer. If they reject, 0.
        # Strategy: Offer them a "crumb" (1 item they like) and keep the rest.
        if self.me == 0 and self.round_idx == self.max_rounds:
            return self._generate_ultimatum()

        # B. Standard Proposal Logic
        # Determine target value I want to keep.
        progress = (self.round_idx - 1) / max(1, self.max_rounds - 1)
        target_start = 1.0
        target_end = 0.70 # Don't aim too low, let the item-splitter efficiently satisfy us
        
        target_frac = target_start - (target_start - target_end) * (progress ** 1.5)
        
        # Special Case: Player 2 at Round (Max-1).
        # This is P2's last proposal. It MUST be accepted to avoid P1's Ultimatum turn.
        # We offer a generous deal (keep 51%, give 49%).
        if self.me == 1 and self.round_idx == self.max_rounds - 1:
            target_frac = 0.51
            
        target_val = int(target_frac * self.total_value)
        return self._generate_smart_split(target_val)

    def _generate_smart_split(self, target: int) -> list[int]:
        # Construct an offer where I keep items I value highly, 
        # and give away items the opponent Values (based on history).
        # Metric: Efficiency = MyVal / (OppVal + epsilon)
        
        candidates = []
        for i in range(self.num_items):
            val = self.values[i]
            opp_interest = self.opp_history_sum[i]
            # Score logic: Higher is better to KEEP.
            # Add small random noise to prevent loops in deterministic scenarios
            score = (val / (opp_interest + 0.1)) * random.uniform(0.99, 1.01)
            candidates.append((score, i))
            
        # Sort best items for ME to keep at the top
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        proposal = [0] * self.num_items
        current_val = 0
        
        for _, idx in candidates:
            if current_val >= target:
                break
            
            # Take all available of this type (Greedy Knapsack)
            # Since sorted by efficiency, these are the cheapest for me to "buy"
            # in terms of opportunity cost to the opponent.
            proposal[idx] = self.counts[idx]
            current_val += proposal[idx] * self.values[idx]
            
        return proposal

    def _generate_ultimatum(self) -> list[int]:
        # Start by taking everything
        proposal = list(self.counts)
        
        # Determine opponent's favorite item based on history
        best_idx = -1
        max_interest = -1
        
        indices = list(range(self.num_items))
        random.shuffle(indices) # Random break ties
        
        for i in indices:
            if self.counts[i] > 0 and self.opp_history_sum[i] >= max_interest:
                max_interest = self.opp_history_sum[i]
                best_idx = i
                
        # Give them 1 of their favorite item if possible
        if best_idx != -1:
            proposal[best_idx] -= 1
            
        return proposal