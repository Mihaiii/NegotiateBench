import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        self.turn_number = me
        
        self.max_val = sum(c * v for c, v in zip(counts, values))
        
        # Track history of what the opponent *keeps* (their demands)
        self.opp_history_demands = [] 
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        # Determine turns left for the whole game after this action
        turns_remaining = self.total_turns - 1 - self.turn_number

        val_offered = 0
        if o is not None:
            # Calculate value of the offer to me
            val_offered = sum(self.values[i] * o[i] for i in range(len(self.counts)))
            
            # Infer what opponent kept: Total - Offered
            kept = [self.counts[i] - o[i] for i in range(len(self.counts))]
            self.opp_history_demands.append(kept)
        
        # --- 1. Acceptance Logic ---

        # A. Last Mover Safety (I am acting on the very last turn of the session)
        # If I reject, the result is 0 for everyone. Rational interaction dictates accepting any gain.
        if turns_remaining == 0:
            if o is not None and val_offered > 0:
                return None
        
        # B. Calculate Dynamic Target
        # Linear descent from 1.0 (start) to 0.7 (80% time), then panic to 0.55 (end)
        progress = self.turn_number / max(1, self.total_turns - 1)
        
        if progress < 0.2:
            target_pct = 1.0
        elif progress < 0.8:
            # 1.0 -> 0.7
            target_pct = 1.0 - (0.3 * (progress - 0.2) / 0.6)
        else:
            # 0.7 -> 0.55
            target_pct = 0.7 - (0.15 * (progress - 0.8) / 0.2)
            
        target_val = int(self.max_val * target_pct)
        
        # C. Check Offer against Target and Safety Nets
        if o is not None:
            # 1. Met Target
            if val_offered >= target_val:
                return None
            
            # 2. End-game Compromise (Last 2 rounds)
            # Accept if > 55% of total value to avoid total failure
            if turns_remaining <= 3:
                if val_offered >= self.max_val * 0.55:
                    return None
            
            # 3. High Value Absolute Accept (Take the money and run)
            if val_offered >= self.max_val * 0.95:
                return None

        # --- 2. Counter-Offer Generation ---
        
        # A. Opponent Modeling (Identify Conflict Items)
        # Weights: Base 1.0. Increases if opponent keeps item.
        # Recency: Newer moves count 3x more than oldest.
        opp_weights = [1.0] * len(self.counts) 
        n_history = len(self.opp_history_demands)
        
        if n_history > 0:
            for t_idx, demand in enumerate(self.opp_history_demands):
                # Weight: Oldest = 1.0, Newest = 3.0
                w = 1.0 + (2.0 * t_idx / n_history)
                for i in range(len(self.counts)):
                    if self.counts[i] > 0:
                        # Add weighted proportion of item kept
                        opp_weights[i] += (demand[i] / self.counts[i]) * w
        
        # B. Efficiency Calculation (MyValue / Oppweight)
        # This prioritizes items I want that the opponent seems to ignore.
        candidates = []
        for i in range(len(self.counts)):
            if self.counts[i] > 0:
                # Add small epsilon to weight to avoid div/0
                eff = self.values[i] / (opp_weights[i] + 0.01)
                # Random tiebreaker
                eff += random.uniform(0, 0.00001)
                candidates.append((eff, i))
        
        # Sort descending by efficiency
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        proposal = [0] * len(self.counts)
        current_prop_val = 0
        
        # C. Greedy Knapsack Fill
        for _, idx in candidates:
            # If I value it 0, skip (unless strictly needed? No, worthless to me)
            if self.values[idx] == 0:
                continue
                
            count = self.counts[idx]
            val_per_item = self.values[idx]
            
            # Take items until target reached
            take = 0
            for _ in range(count):
                if current_prop_val < target_val:
                    take += 1
                    current_prop_val += val_per_item
                else:
                    break
            proposal[idx] = take

        # D. Top-up with "freebies"
        # If there are items I value that opponent strongly ignores (low weight), take them
        # even if target is met. This maximizes score without jeopardizing the deal much.
        max_w = max(opp_weights)
        # Threshold: Bottom 25% of contention relative to max interest
        threshold = 1.0 + 0.25 * (max_w - 1.0) 
        
        for i in range(len(self.counts)):
            if proposal[i] < self.counts[i] and self.values[i] > 0:
                if opp_weights[i] <= threshold:
                    taken = self.counts[i] - proposal[i]
                    proposal[i] += taken
                    current_prop_val += taken * self.values[i]

        # E. Final Sanity Check
        # If the proposal I built is worse for me than what they just offered, accept theirs.
        if o is not None and val_offered >= current_prop_val:
            return None

        self.turn_number += 2
        return proposal