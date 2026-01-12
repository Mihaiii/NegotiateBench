import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.n = len(counts)
        self.my_max_val = sum(c * v for c, v in zip(counts, values))
        
        # Track history of what opponent keeps to infer their valuations
        # Higher count = higher likely value to opponent
        self.opp_kept_sum = [0] * self.n
        self.turns_elapsed = 0

    def offer(self, o: list[int] | None) -> list[int] | None:
        # Calculate negotiation progress
        current_global_turn = self.turns_elapsed * 2 + self.me
        total_turns = self.max_rounds * 2
        turns_left = total_turns - current_global_turn
        
        val_o = 0
        if o is not None:
            # Evaluate their offer for me
            val_o = sum(o[i] * self.values[i] for i in range(self.n))
            
            # Update opponent model: counts[i] - o[i] is what they kept
            for i in range(self.n):
                kept = self.counts[i] - o[i]
                self.opp_kept_sum[i] += kept
        
        # --- Acceptance Logic ---
        
        # 1. Ultimatum Strategy (Last Resort)
        # If I am the second mover (me=1) and this is the very last turn (turn index = total-1),
        # rejecting results in 0 for both. Mathematically, accepting any positive value maximizes yield.
        if turns_left == 1:
            if o is not None:
                # Accept if we get at least 1 point, or if we have 0 potential anyway
                if val_o > 0 or self.my_max_val == 0:
                    return None
        
        # 2. Dynamic Reservation Price
        # Calculate the minimum value I am willing to accept based on time remaining.
        # Strategy: Anchor high, then concede to a fair split, then dampen slightly at deadline.
        progress = current_global_turn / total_turns
        
        if progress < 0.2:
            # Anchor phase: Demand near max
            req_factor = 0.95
        elif progress < 0.8:
            # Concession phase: Linear decay from 95% to 65%
            # Normalized local progress p (0 to 1)
            p = (progress - 0.2) / 0.6
            req_factor = 0.95 - 0.30 * p
        else:
            # End game phase: Drop to Floor (55%)
            # We assume a fair deal gives both parties > 50% relative to their own max.
            req_factor = 0.55
            
        reservation = int(self.my_max_val * req_factor)
        # Ensure we don't accidentally ask for 0 if we have value
        if self.my_max_val > 0:
            reservation = max(reservation, 1)

        # Accept if offer meets reservation
        if o is not None and val_o >= reservation:
            return None
            
        # --- Counter-Offer Generation ---
        
        # Determine target value for my proposal
        # Aim slightly above reservation to leave room for concession
        target = int(reservation * 1.05)
        # But do not exceed max
        target = min(target, self.my_max_val)
        
        # If we are in the last round (P1 last offer), propose exactly reservation to maximize acceptance chance
        if turns_left <= 2:
            target = reservation

        # Build Priority List based on Efficiency
        # Efficiency = MyValue / LikelyOpponentCost
        # LikelyOpponentCost is estimated by how often they kept the item
        
        # Normalize opponent weights
        total_kept = sum(self.opp_kept_sum)
        opp_weights = []
        for i in range(self.n):
            w = 1.0 # Base weight
            if total_kept > 0:
                w += (self.opp_kept_sum[i] / total_kept) * 10
            opp_weights.append(w)
            
        priorities = []
        for i in range(self.n):
            if self.counts[i] > 0 and self.values[i] > 0:
                # Add noise (0.95-1.05) to randomize offers slightly and break deadlocks
                eff = self.values[i] / (opp_weights[i] * random.uniform(0.95, 1.05))
                priorities.append((eff, i))
            elif self.values[i] == 0:
                # Don't ask for 0-value items unless necessary (score -1)
                priorities.append((-1.0, i))
        
        # Sort by efficiency descending
        priorities.sort(key=lambda x: x[0], reverse=True)
        
        # Construct Proposal using Greedy approach
        my_offer = [0] * self.n
        current_sum = 0
        
        # Pass 1: Fill up to target
        for _, i in priorities:
            if current_sum >= target:
                break
            if self.values[i] == 0: 
                continue
                
            needed = target - current_sum
            # How many items to reach needed value? ceil(needed/val)
            count = (needed + self.values[i] - 1) // self.values[i]
            take = min(self.counts[i], count)
            
            my_offer[i] = take
            current_sum += take * self.values[i]
            
        # Pass 2: If we failed to reach target (e.g. big discrete chunks), take remaining positives
        if current_sum < target:
            for _, i in priorities:
                if self.values[i] > 0:
                    left = self.counts[i] - my_offer[i]
                    if left > 0:
                        my_offer[i] += left
                        current_sum += left * self.values[i]
        
        # Sanity Check:
        # If my best constructed offer is actually worse or equal to the opponent's offer,
        # just accept theirs. This avoids rejecting a 50-value offer to propose a 48-value one.
        if o is not None and current_sum <= val_o:
            return None
            
        self.turns_elapsed += 1
        return my_offer