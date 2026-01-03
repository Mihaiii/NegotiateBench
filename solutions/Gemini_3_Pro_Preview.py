import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        
        # Current Global Turn Index (0, 1, 2...)
        # me=0 => 0, 2, 4...
        # me=1 => 1, 3, 5...
        self.current_turn = me 
        
        self.my_total_val = sum(c * v for c, v in zip(counts, values))
        
        # Opponent Modeling:
        # We track the sum of items the opponent KEPT across rounds.
        # This helps estimate their valuation (Affinity).
        self.opp_kept_sum = [0] * len(counts)
        self.opp_moves = 0

    def offer(self, o: list[int] | None) -> list[int] | None:
        turns_left = self.total_turns - self.current_turn
        
        # --- 1. ANALYZE INCOMING OFFER ---
        incoming_val = 0
        if o is not None:
            incoming_val = sum(c * v for c, v in zip(o, self.values))
            
            # Update Opponent Model
            # 'o' is what they offer ME. Therefore they kept (counts - o).
            opp_kept = [self.counts[i] - o[i] for i in range(len(self.counts))]
            for i in range(len(self.counts)):
                self.opp_kept_sum[i] += opp_kept[i]
            self.opp_moves += 1

        # --- 2. END-GAME TERMINATION CHECK ---
        # If I am Player 1 and this is the absolute last turn (Turn N-1),
        # I cannot counter. I must accept anything > 0 to secure points.
        if turns_left == 1:
            if o is not None and incoming_val > 0:
                return None
            # If offer is 0, we can technicallly accept (gets 0) or counter (gets 0).
            # Accepting closes the deal successfully for stats purposes.
            if o is not None:
                return None

        # --- 3. DYNAMIC TARGET DETERMINATION ---
        # Calculate negotiation progress (0.0 start -> 1.0 end)
        progress = self.current_turn / max(1, self.total_turns - 1)
        
        # Concession Curve
        if progress < 0.5:
             # Phase 1: Hold High (100% -> 85%)
             target_pct = 1.0 - 0.3 * progress 
        else:
             # Phase 2: Concede (85% -> 65%)
             target_pct = 0.85 - 0.4 * (progress - 0.5)
        
        # Hard floor for target (unless urgent)
        if target_pct < 0.6: 
            target_pct = 0.6

        # TACTICAL OVERRIDES
        # Case A: P0 Ultimatum (Turn N-2)
        # I am P0. Next turn P1 must accept or die. I demand a lot.
        if turns_left == 2:
            target_pct = 0.85 
            
        # Case B: P1 Pre-Ultimatum (Turn N-3)
        # I am P1. Next turn P0 gives Ultimatum. I must offer a tempting deal.
        if turns_left == 3:
            target_pct = 0.62 # Slightly enticing
            
        target_val = int(self.my_total_val * target_pct)
        
        # --- 4. ACCEPTANCE LOGIC ---
        if o is not None:
            # A. Value is great (95%+)
            if incoming_val >= self.my_total_val * 0.95:
                return None
            
            # B. Value meets current target
            if incoming_val >= target_val:
                return None
                
            # C. Desperation / Smoothing
            # If we are deep in late game, accept "good enough" offers (70%+)
            if turns_left <= 6 and incoming_val >= self.my_total_val * 0.70:
                return None
                
            # D. Defense against P0 Ultimatum (P1 Specific)
            # If I am P1, late game, and offer is > 55%, take it before P0 crushes me.
            if self.me == 1 and turns_left <= 5 and incoming_val >= self.my_total_val * 0.55:
                return None

        # --- 5. GENERATE COUNTER-OFFER ---
        # Heuristic: Dual Knapsack. Maximize (MyValue) while minimizing (OpponentWeight).
        
        # Estimate Opponent Weights
        opp_weights = []
        for i in range(len(self.counts)):
            if self.opp_moves > 0 and self.counts[i] > 0:
                # Frequency they kept this item (0.0 to 1.0)
                freq = self.opp_kept_sum[i] / (self.counts[i] * self.opp_moves)
                w = 0.1 + freq # Base weight + Frequency
            else:
                w = 0.5 # Neutral Assumption
            opp_weights.append(w)
            
        # Sort object types by ratio: MyVal / OppWeight
        # Higher ratio = I value it much more than they seem to.
        candidates = []
        for i in range(len(self.counts)):
            ratio = (self.values[i] + 0.001) / (opp_weights[i] + 0.001)
            # Add noise to prevent deterministic loops in negotiation
            ratio *= random.uniform(0.98, 1.02)
            candidates.append({'idx': i, 'ratio': ratio})
            
        candidates.sort(key=lambda x: x['ratio'], reverse=True)
        
        my_demand = [0] * len(self.counts)
        current_sum = 0
        
        for item in candidates:
            idx = item['idx']
            qty_available = self.counts[idx]
            
            for _ in range(qty_available):
                should_take = False
                
                # Take if we haven't reached target yet
                if current_sum < target_val:
                    should_take = True
                
                # Take if it's "trash" to them (weight very low) and has value to me
                elif opp_weights[idx] < 0.2 and self.values[idx] > 0:
                     should_take = True
                     
                if should_take:
                    my_demand[idx] += 1
                    current_sum += self.values[idx]
                else:
                    break
        
        # --- 6. RATIONALITY CHECK ---
        # If the best deal I can propose is worse than what they offered, accept theirs.
        if o is not None:
             gen_val = sum(c * v for c, v in zip(my_demand, self.values))
             if incoming_val >= gen_val:
                 return None
        
        self.current_turn += 2
        return my_demand