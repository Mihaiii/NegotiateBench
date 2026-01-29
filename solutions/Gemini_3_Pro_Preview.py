import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.step = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.num_items = len(counts)
        
        # Opponent modeling: Frequency of items kept by opponent
        # self.opp_kept_sum[i] increments each time opponent keeps item i
        self.opp_kept_sum = [0] * self.num_items

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.step += 1
        is_last_round = (self.step == self.max_rounds)
        
        # --- Update Opponent Model & Calculate Offer Value ---
        offer_val = 0
        if o is not None:
            # They offer 'o' to me, meaning they kept 'counts - o'
            kept = [self.counts[i] - o[i] for i in range(self.num_items)]
            for i in range(self.num_items):
                self.opp_kept_sum[i] += kept[i]
            
            offer_val = sum(o[i] * self.values[i] for i in range(self.num_items))
        
        # --- Decision Logic ---
        
        # 1. Player 1: End-Game Panic
        # If I am the second mover, the game ends immediately after my decision on the last round.
        # If I reject, we both get 0. Rational choice is to accept anything > 0.
        if self.me == 1 and is_last_round:
            if o is not None and offer_val > 0:
                return None
        
        # 2. Determine Target Value (Boulware Strategy)
        # Stay high for most of the negotiation, concede near the end.
        
        # t goes from 0.0 (first step) to 1.0 (last step)
        t = (self.step - 1) / (self.max_rounds - 1) if self.max_rounds > 1 else 1.0
        
        start_frac = 1.0
        end_frac = 0.7  # Aspiration floor
        
        # Curve: t**4 keeps the target near 100% for longer
        current_frac = start_frac + (end_frac - start_frac) * (t ** 4)
        target_val = int(current_frac * self.total_value)
        
        # 3. Standard Acceptance
        if o is not None and offer_val >= target_val:
            return None
            
        # --- Offer Generation ---
        
        # 4. Player 0: End-Game Ultimatum
        # If I am first mover, my last offer is the final proposal.
        # Opponent (if rational) will accept anything > 0.
        # Strategy: Offer a proposal that gives me nearly everything, 
        # but leaves 1 unit of the item the opponent desires most.
        if self.me == 0 and is_last_round:
            return self._generate_ultimatum()
            
        # 5. Smart Counter-Offer
        return self._generate_smart_offer(target_val)
        
    def _generate_ultimatum(self) -> list[int]:
        # Identify opponent's highest interest item
        best_opp_idx = -1
        max_interest = -1
        
        # Shuffle indices to randomize tie-breaking
        indices = list(range(self.num_items))
        random.shuffle(indices)
        
        for i in indices:
            if self.opp_kept_sum[i] > max_interest:
                max_interest = self.opp_kept_sum[i]
                best_opp_idx = i
        
        # I take everything...
        proposal = list(self.counts)
        
        # ...except 1 unit of their favorite item
        if best_opp_idx != -1 and proposal[best_opp_idx] > 0:
            proposal[best_opp_idx] -= 1
            
        return proposal

    def _generate_smart_offer(self, target: int) -> list[int]:
        # Sort by limit efficiency: MyValue / OpponentInterest
        item_scores = []
        for i in range(self.num_items):
            my_v = self.values[i]
            opp_int = self.opp_kept_sum[i]
            
            if my_v > 0:
                # Score = My Utility / (Their Estimated Utility + small)
                noise = 1.0 + random.random() * 0.05
                score = (my_v / (opp_int + 1.0)) * noise
            else:
                score = 0
            
            item_scores.append((score, i))
            
        # Sort descending by score
        item_scores.sort(key=lambda x: x[0], reverse=True)
        
        proposal = [0] * self.num_items
        current_val = 0
        
        # Fill proposal to meet target
        for score, idx in item_scores:
            if current_val >= target:
                break
                
            available = self.counts[idx]
            
            # Decide how many to take
            # We take just enough to reach target to maximize slack for opponent
            take = 0
            val_per_item = self.values[idx]
            
            if val_per_item > 0:
                needed_val = target - current_val
                needed_count = (needed_val + val_per_item - 1) // val_per_item
                take = min(available, needed_count)
            
            proposal[idx] += take
            current_val += take * val_per_item
            
        return proposal