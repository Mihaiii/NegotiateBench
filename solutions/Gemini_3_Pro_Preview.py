import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        
        # Current turn index: Starts at 0 or 1, increments by 2
        self.turn_idx = me 
        
        self.max_val = sum(c * v for c, v in zip(counts, values))
        
        # Opponent Modeling: lists of what opponent kept (Total - Offered)
        self.opp_demands = [] 
        self.best_offer_val = 0
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        # 1. Update Opponent Model & Parse Offer
        val_offered = 0
        if o is not None:
            # o is what partner offers ME.
            # Determine what partner WANTS for themselves: Total - Offered
            opp_wants = [self.counts[i] - o[i] for i in range(len(self.counts))]
            self.opp_demands.append(opp_wants)
            
            val_offered = sum(q * v for q, v in zip(o, self.values))
            if val_offered > self.best_offer_val:
                self.best_offer_val = val_offered

        # 2. Determine Progress and Status
        # valid turns remaining *after* this one (for me or opponent)
        turns_remaining_after_me = self.total_turns - 1 - self.turn_idx
        
        # Normalized progress 0.0 (start) -> 1.0 (end)
        progress = self.turn_idx / max(1, self.total_turns - 1)
        
        # 3. Acceptance Logic
        
        # A. Last Turn Absolute Safety (I am the last mover)
        # If I counter, the negotiation ends with no deal. I must accept anything > 0.
        if turns_remaining_after_me == 0:
            if o is not None and (val_offered > 0 or self.max_val == 0):
                return None
        
        # B. High Value Acceptance (Take the money and run)
        if o is not None:
             if val_offered >= self.max_val * 0.98:
                 return None
                 
        # 4. Target Calculation (Reservation Value)
        # Strategy: Stubborn start, linear middle, compromise end.
        if progress < 0.4:
            target_pct = 1.0
        elif progress < 0.9:
            # Descent from 1.0 to 0.7
            ratio = (progress - 0.4) / 0.5
            target_pct = 1.0 - (0.3 * ratio)
        else:
            # Endgame panic: 0.7 -> 0.55
            ratio = (progress - 0.9) / 0.1
            target_pct = 0.7 - (0.15 * ratio)
            
        target_val = int(self.max_val * target_pct)
        
        # 5. Check Offer vs Target (with fallback logic)
        if o is not None:
            if turns_remaining_after_me <= 2:
                # Near deadline: Accept if offer is decent (65%+) or best seen so far within reason
                safety_floor = int(self.max_val * 0.65)
                # If target is still high, relax it to the best reliable alternative
                relaxed_target = min(target_val, max(safety_floor, int(self.best_offer_val)))
                
                if val_offered >= relaxed_target:
                    return None
            else:
                # Standard phase: Hold firm to target
                if val_offered >= target_val:
                    return None
                    
        # 6. Generate Counter-Proposal (Knapsack Heuristic)
        # Estimate Opponent Interest (Cost) taking recency into account
        opp_weights = [0.0] * len(self.counts)
        hist_len = len(self.opp_demands)
        
        if hist_len > 0:
            denom = 0.0
            for i, d in enumerate(self.opp_demands):
                # Weight moves: 1.0 (oldest) to 3.0 (newest)
                w = 1.0 + (2.0 * i / hist_len)
                denom += w
                for k in range(len(self.counts)):
                    # Fraction of total available items they demanded
                    frac = d[k] / max(1, self.counts[k])
                    opp_weights[k] += frac * w
            for k in range(len(self.counts)):
                opp_weights[k] /= denom
        else:
            # Default assumption
            opp_weights = [0.5] * len(self.counts)
            
        # Create item candidates with efficiency score
        # Efficiency = MyValue / (OpponentCost + epsilon)
        candidates = []
        for i in range(len(self.counts)):
            cost = opp_weights[i] + 0.05
            val = self.values[i]
            
            if cost > 0:
                eff = val / cost
            else:
                eff = float('inf')
                
            # Tie-breaking jitter
            eff += random.uniform(0, 1e-6)
            
            candidates.append({
                'idx': i,
                'val': val,
                'eff': eff,
                'count': self.counts[i],
                'opp_weight': opp_weights[i]
            })
            
        # Sort by efficiency descending (Best for ME, cheapest for OPP)
        candidates.sort(key=lambda x: x['eff'], reverse=True)
        
        proposal = [0] * len(self.counts)
        current_prop_val = 0
        
        # Greedy Item Selection
        for item in candidates:
            idx = item['idx']
            v = item['val']
            n = item['count']
            
            # If value is 0, skipping it usually helps the deal (opponent might want it)
            if v == 0:
                continue
                
            # Take items one by one to hit target precisely
            for _ in range(n):
                if current_prop_val < target_val:
                    proposal[idx] += 1
                    current_prop_val += v
                else:
                    # Target met. Only add extra items if they are "cheap" (low opp interest)
                    if item['opp_weight'] < 0.2:
                        proposal[idx] += 1
                        current_prop_val += v
                    else:
                        break

        # 7. Rationality Check
        # If the proposal I just built is worth less than (or equal to) what they offered, use theirs.
        if o is not None and val_offered >= current_prop_val:
            return None

        # Prepare for next turn
        self.turn_idx += 2
        return proposal