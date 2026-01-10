import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        
        self.turn_count = 0
        self.my_max_val = sum(c * v for c, v in zip(counts, values))
        self.n = len(counts)
        
        # Opponent model: track cumulative counts of items the opponent KEPT
        # to estimate their valuation.
        self.opp_kept_history = [0] * self.n
        self.opp_moves = 0

    def offer(self, o: list[int] | None) -> list[int] | None:
        # Calculate global turn index: 0, 1, 2 ... total_turns-1
        current_turn = self.turn_count * 2 + self.me
        turns_left = self.total_turns - current_turn
        
        # --- 1. Update Opponent Model ---
        if o is not None:
            self.opp_moves += 1
            # o is what they offer ME. They keep (counts - o).
            kept = [self.counts[i] - o[i] for i in range(self.n)]
            for i in range(self.n):
                self.opp_kept_history[i] += kept[i]
        
        # Estimate Opponent Weights
        # Higher weight = Opponent wants this more.
        opp_weights = []
        for i in range(self.n):
            if self.counts[i] == 0:
                opp_weights.append(0.0)
                continue
                
            # If no history, assume neutral (1.0)
            if self.opp_moves == 0:
                opp_weights.append(1.0)
                continue
            
            # Retention frequency (0.0 to 1.0)
            # freq = 1.0 means they kept ALL of this type every time.
            freq = self.opp_kept_history[i] / (self.opp_moves * self.counts[i])
            
            # Non-linear weighting to emphasize high retention items
            # Weight ranges approx 0.1 to 10
            w = 0.1 + (freq * freq) * 10
            opp_weights.append(w)
            
        # --- 2. Evaluate Incoming Offer ---
        if o is not None:
            val_o = sum(o[i] * self.values[i] for i in range(self.n))
            
            # Edge Case: Me (P2) Last Turn. 
            # If I reject, we get 0. Rationally accept anything > 0.
            if turns_left == 1:
                if val_o > 0:
                    return None
            
            # Standard Acceptance Logic
            # Curve: Accept ~95% at start, dropping to ~55% by end
            progress = current_turn / self.total_turns
            thresh_frac = 0.95 - 0.4 * progress
            
            # Safety for "Bulldozer" opponents: 
            # In last 4 turns (2 rounds), become very agreeable to avoid crash
            if turns_left <= 4:
                 thresh_frac = min(thresh_frac, 0.55)
            
            # Lower bound to strictly avoid bad deals until the very end
            thresh_frac = max(thresh_frac, 0.4)
            
            # Accept if threshold met
            if val_o >= int(self.my_max_val * thresh_frac):
                return None
                
            # Instant accept for near-perfect offers regardless of time
            if val_o >= self.my_max_val * 0.98:
                return None

        # --- 3. Construct Counter-Offer ---
        
        # Target Value Logic: Decay from 100% to ~60%
        progress = current_turn / self.total_turns
        target_frac = 1.0 - 0.35 * progress
        
        # End-game concession: If I am proposing in the last few turns,
        # I must offer a deal the opponent is likely to accept (sweetener).
        if turns_left <= 4:
            target_frac = min(target_frac, 0.60)
            
        target_val = int(self.my_max_val * target_frac)
        
        # Build bundle using Efficiency Ratio: MyValue / OpponentWeight
        # We pick items that are valuable to me but cheap/unwanted by opponent.
        items = []
        for i in range(self.n):
            if self.counts[i] > 0:
                # Add small epsilon to avoid div by zero
                # Add random noise for tie-breaking
                w = opp_weights[i] + 1e-6
                eff = self.values[i] / w
                eff *= random.uniform(0.99, 1.01)
                
                items.append({'i': i, 'val': self.values[i], 'c': self.counts[i], 'eff': eff})
        
        # Sort descending by efficiency
        items.sort(key=lambda x: x['eff'], reverse=True)
        
        my_offer_counts = [0] * self.n
        current_sum = 0
        
        # Greedy knapsack fill
        for item in items:
            if current_sum >= target_val:
                break
                
            idx = item['i']
            val = item['val']
            cnt = item['c']
            
            if val > 0:
                needed = target_val - current_sum
                # Ceil division to get exact count needed
                take = (needed + val - 1) // val
                take = min(take, cnt)
                
                my_offer_counts[idx] += take
                current_sum += take * val
            else:
                # Do not take 0 value items (leave them for opponent as sweetener)
                pass
                
        self.turn_count += 1
        return my_offer_counts