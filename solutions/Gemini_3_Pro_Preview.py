import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.round_idx = 0  # Tracks the current round number (1-based)
        
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.num_items = len(counts)
        
        # Opponent modeling: Frequency of items opponent keeps in their offers.
        # Initiated with a small epsilon to valid division by zero.
        self.opp_kept_freq = [0.01] * self.num_items 

    def offer(self, o: list[int] | None) -> list[int] | None:
        # --- Update Round Counter ---
        if self.me == 0:
            # Player 1 moves at Turns 1, 3, 5... (Start of rounds)
            if o is None:
                self.round_idx = 1
            else:
                self.round_idx += 1
        else:
            # Player 2 moves at Turns 2, 4, 6... (End of rounds)
            # The first call is response to P1's first offer (Round 1)
            self.round_idx += 1

        # --- Update Opponent Model ---
        offer_val = 0
        if o is not None:
            offer_val = sum(o[i] * self.values[i] for i in range(self.num_items))
            # If they offer 'o' to me, it means they want to keep 'counts - o'
            for i in range(self.num_items):
                kept = self.counts[i] - o[i]
                if kept > 0:
                    self.opp_kept_freq[i] += kept

        # --- P2 Last Round Strategy (Rational Acceptance) ---
        # If I am Player 2 and this is the last turn of the entire game,
        # rejecting results in 0 for both. Rationality dictates accepting anything > 0.
        if self.me == 1 and self.round_idx == self.max_rounds:
            if o is not None:
                # Accept if we get any value (or even 0, to seal the deal, 
                # though usually > 0 is preferred, safeguarding against total loss).
                # To be strictly maximizing in a one-shot game:
                return None

        # --- Determine Target Value (Boulware Strategy) ---
        # t ranges from 0.0 (start) to 1.0 (end)
        t = (self.round_idx - 1) / max(1, self.max_rounds - 1)
        
        # Concession curve parameters
        # Beta > 1 means we concede slowly (tough negotiator)
        beta = 4.0 
        start_frac = 1.0
        end_frac = 0.6  # Final aspiration floor (60% of total)
        
        target_frac = start_frac + (end_frac - start_frac) * (t ** beta)
        target_val = int(target_frac * self.total_value)
        
        # --- Check Acceptance ---
        if o is not None:
            # Always accept if we get everything (max possible)
            if offer_val == self.total_value:
                return None
            # Accept if offer meets our current decayed target
            if offer_val >= target_val:
                return None

        # --- P1 Last Round Strategy (Ultimatum) ---
        # If I am Player 1 and this is the last round, my offer is final.
        # If P2 rejects, we get 0. I should offer the "Minimum Acceptable Deal".
        if self.me == 0 and self.round_idx == self.max_rounds:
            return self._generate_ultimatum()

        # --- Generate Counter-Offer ---
        return self._generate_smart_offer(target_val)

    def _generate_ultimatum(self) -> list[int]:
        # Identify the item the opponent seems to desire most (highest keep frequency)
        indices = list(range(self.num_items))
        random.shuffle(indices) # Randomize ties
        best_idx = max(indices, key=lambda i: self.opp_kept_freq[i])
        
        # Proposal: I take everything...
        proposal = list(self.counts)
        
        # ...except 1 unit of their favorite item
        if proposal[best_idx] > 0:
            proposal[best_idx] -= 1
        else:
            # Fallback: leave 1 of anything available
            for i in range(self.num_items):
                if proposal[i] > 0:
                    proposal[i] -= 1
                    break
        return proposal

    def _generate_smart_offer(self, target: int) -> list[int]:
        # Goal: Build a bundle for ME that sums to >= target.
        # Heuristic: Prioritize items where MyValue / OpponentInterest is high.
        # This gives me what I want and the opponent what they want (efficiency).
        
        candidates = []
        for i in range(self.num_items):
            val = self.values[i]
            if val == 0:
                continue # Don't demand items worthless to me
            
            opp_interest = self.opp_kept_freq[i]
            # Add slight noise to prevent deterministic loops
            noise = random.uniform(0.98, 1.02)
            metric = (val / (opp_interest + 0.1)) * noise
            candidates.append((metric, i))
            
        # Sort by efficiency descending
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        proposal = [0] * self.num_items
        current_val = 0
        
        # Greedy Knapsack Fill
        for _, idx in candidates:
            if current_val >= target:
                break
                
            available = self.counts[idx]
            val = self.values[idx]
            
            # Calculate how many needed to reach target
            needed_val = target - current_val
            needed_count = (needed_val + val - 1) // val
            
            take = min(available, needed_count)
            proposal[idx] += take
            current_val += take * val
            
        return proposal