import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        
        self.my_max_val = sum(c * v for c, v in zip(counts, values))
        self.n = len(counts)
        
        # Track opponent behavior: how many of each item they KEPT in previous turns
        self.opp_kept_sum = [0] * self.n
        # Number of offers received from opponent
        self.opp_offers_count = 0
        
        # My turn counter (local)
        self.my_turns_taken = 0

    def offer(self, o: list[int] | None) -> list[int] | None:
        # Calculate negotiation progress
        current_global_turn = self.my_turns_taken * 2 + self.me
        turns_left = self.total_turns - current_global_turn
        
        val_o = -1
        if o is not None:
            self.opp_offers_count += 1
            # Infer opponent values: they keep items they want.
            # Record what they kept (history tracking).
            for i in range(self.n):
                kept_qty = self.counts[i] - o[i]
                self.opp_kept_sum[i] += kept_qty
            
            # Calculate value of their offer to me
            val_o = sum(o[i] * self.values[i] for i in range(self.n))
        
        # --- Acceptance Strategy ---
        
        # 1. Last Ditch Logic:
        # If we are the second mover in the very last round (Turn 2*rounds - 1),
        # returning a counter-offer results in No Deal (0 profit).
        # We MUST accept if the offer has any positive value.
        if turns_left == 1:
            if o is not None and val_o > 0:
                return None
        
        # 2. Reservation Price Curve
        # t goes from 0.0 (start) to 1.0 (end)
        t = current_global_turn / self.total_turns
        
        # Curve strategy:
        # 0% - 20%: Stay firm at 100% to anchor.
        # 20% - 80%: Linear decay from 100% to 70%.
        # 80% - 100%: Drop from 70% to 55%.
        if t < 0.2:
            curve = 1.0
        elif t < 0.8:
            # Normalized progress in this segment
            p = (t - 0.2) / 0.6
            curve = 1.0 - 0.3 * p
        else:
            # End game concession
            p = (t - 0.8) / 0.2
            curve = 0.7 - 0.15 * p
            
        # Hard floor for reservation percentage (never go below 45% unless desperate)
        curve = max(curve, 0.45) 
        
        reservation = int(self.my_max_val * curve)
        if self.my_max_val > 0:
            reservation = max(reservation, 1)
        
        # Accept if offer meets our current reservation criteria
        if o is not None and val_o >= reservation:
            return None
            
        # --- Counter-Offer Strategy ---
        
        # Set a target slightly higher than reservation to allow for negotiation room
        target = int(reservation * 1.05)
        
        # If we are effectively in the last round (turns_left <= 2),
        # stop posturing and aim exactly for reservation to maximize deal probability.
        if turns_left <= 2:
            target = reservation
            
        target = min(target, self.my_max_val)

        # Build bundle priorities based on Efficiency Ratio
        # Efficiency = MyValue / LikelyOpponentValue
        # LikelyOpponentValue is estimated via the frequency they kept the item.
        item_scores = []
        for i in range(self.n):
            if self.counts[i] == 0: continue
            
            # If I don't value it, rank it lowest (score -1). 
            # We generally shouldn't ask for items we don't value unless necessary.
            if self.values[i] == 0:
                item_scores.append((-1.0, i))
                continue
            
            # Estimate opponent desire (0.0 to 1.0)
            if self.opp_offers_count == 0:
                opp_freq = 0.5
            else:
                total_seen = self.opp_offers_count * self.counts[i]
                opp_freq = self.opp_kept_sum[i] / total_seen if total_seen > 0 else 0.5
            
            # Denom: Map 0.0->0.1 (low desire) to 1.0->1.1 (high desire)
            denom = 0.1 + opp_freq
            eff = self.values[i] / denom
            
            # Add slight noise to randomize behavior on identical items
            eff *= random.uniform(0.98, 1.02)
            
            item_scores.append((eff, i))
            
        # Sort items: highest efficiency first
        item_scores.sort(key=lambda x: x[0], reverse=True)
        
        # Construct Proposal using Greedy approach (Knapsack-like)
        my_proposal = [0] * self.n
        current_sum = 0
        
        for score, i in item_scores:
            if score < 0: continue # Skip 0-value items
            
            count_avail = self.counts[i]
            val = self.values[i]
            
            # We want to reach 'target' value
            needed = target - current_sum
            if needed <= 0:
                break
            
            # Take as many as needed to cover the gap
            # ceil(needed / val)
            take = (needed + val - 1) // val
            take = min(take, count_avail)
            
            my_proposal[i] = take
            current_sum += take * val
            
        # --- Final Sanity Check ---
        # If the best offer we could construct is actually worse (or equal) to what 
        # the opponent just offered, we should simply accept their offer.
        # This prevents rejecting a 22-value offer to propose a 20-value counter-offer
        # due to curve decay or greedy imperfections.
        if o is not None:
            if current_sum <= val_o:
                return None
        
        self.my_turns_taken += 1
        return my_proposal