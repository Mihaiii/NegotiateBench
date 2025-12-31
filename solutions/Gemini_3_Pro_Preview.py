import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        
        # Track the logical turn index (Player 0 acts on 0, 2... Player 1 on 1, 3...)
        self.turn_index = me
        
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Opponent modeling: Track how often opponent KEEPS each item.
        # If they offer us X, they kept (Total - X).
        self.opp_kept_sum = [0] * len(counts)
        self.opp_moves = 0

    def offer(self, o: list[int] | None) -> list[int] | None:
        turns_left = self.total_turns - 1 - self.turn_index
        
        # --- 1. Analyze Incoming Offer ---
        offer_val = 0
        if o is not None:
            offer_val = sum(v * c for v, c in zip(self.values, o))
            
            # Update opponent model
            # kept[i] is what they kept for themselves
            kept = [self.counts[i] - o[i] for i in range(len(self.counts))]
            for i in range(len(self.counts)):
                self.opp_kept_sum[i] += kept[i]
            self.opp_moves += 1

        # --- 2. End-Game Survival Logic ---
        # If I am the last mover (turns_left == 0), rejecting means 0 payoff.
        # We must accept any non-negative offer (conceptually anything > 0, 
        # but technically 0 is equal to the no-deal payoff).
        if turns_left == 0:
            if o is not None:
                return None

        # --- 3. Target Calculation ---
        # Progress 0.0 (start) to 1.0 (end)
        progress = self.turn_index / max(1, self.total_turns - 1)
        
        # Concession Curve Strategy:
        # 0% - 50%: Hardball (100% value). Only concede if it's "free" to do so.
        # 50% - 80%: Linear concession to 80% value to signal flexibility.
        # 80% - 95%: Drop to 65% (Deal Zone).
        # 95% - 100%: Panic drop to 50% to salvage a deal.
        
        if progress < 0.5:
            target_pct = 1.0
        elif progress < 0.8:
            # Drop from 1.0 to 0.8 over 0.3 progress
            ratio = (progress - 0.5) / 0.3
            target_pct = 1.0 - (0.2 * ratio)
        elif progress < 0.95:
            # Drop from 0.8 to 0.65 over 0.15 progress
            ratio = (progress - 0.8) / 0.15
            target_pct = 0.8 - (0.15 * ratio)
        else:
            # Drop from 0.65 to 0.5 over 0.05 progress
            ratio = (progress - 0.95) / 0.05
            target_pct = 0.65 - (0.15 * ratio)
            
        target_val = int(self.total_value * target_pct)
        
        # Safety Override: In the absolute final exchanges, ensure we don't demand
        # unreasonably high values that might cause the opponent to walk away.
        if turns_left <= 2:
            target_val = min(target_val, int(self.total_value * 0.7))

        # --- 4. Acceptance Logic ---
        if o is not None:
            # A. Standard Acceptance
            if offer_val >= target_val:
                return None
            
            # B. "Too Good To Refuse" (>= 95% value is always a win)
            if offer_val >= self.total_value * 0.95:
                return None
            
            # C. Late Game Safety (>= 60% with <= 2 turns left)
            # Prevents greed from killing a decent deal at the buzzer.
            if turns_left <= 2 and offer_val >= self.total_value * 0.60:
                return None

        # --- 5. Proposal Generation (Knapsack Heuristic) ---
        # Goal: Keep a set of items with sum(value) >= target_val.
        # Optimization: Prioritize keeping items that I value highly AND 
        # that the opponent seems to value less (low frequency of keeping).
        
        # Create a pool of individual items for granular selection
        pool = []
        for i in range(len(self.counts)):
            if self.counts[i] > 0:
                # Estimate Opponent Interest (0.0 to 1.0) based on frequency
                opp_freq = 0.0
                if self.opp_moves > 0:
                     opp_freq = (self.opp_kept_sum[i] / self.opp_moves) / self.counts[i]
                
                # Metric: My Value / (Opponent Interest + epsilon)
                # High Metric = I want it much more than they seem to. -> KEEP.
                # Low Metric = They want it more. -> GIVE.
                score = (self.values[i] + 0.01) / (opp_freq + 0.01)
                
                # Add slight noise to avoid deterministic loops and explore trade space
                score *= random.uniform(0.98, 1.02)
                
                for _ in range(self.counts[i]):
                    pool.append({'i': i, 'val': self.values[i], 'score': score})
        
        # Sort items by score descending (Keep the "best deals" for me first)
        pool.sort(key=lambda x: x['score'], reverse=True)
        
        my_offer_counts = [0] * len(self.counts)
        current_planning_val = 0
        
        # Fill my bag until target is met
        for item in pool:
            if current_planning_val < target_val:
                my_offer_counts[item['i']] += 1
                current_planning_val += item['val']
            else:
                # Once target is met, leave the remaining items for the opponent.
                # This explicitly maximizes the value for the opponent subject to my target.
                break
        
        # --- 6. Final Rationality Check ---
        # If the incoming offer is strictly better than the proposal I just engineered,
        # logic dictates I should just accept the offer instead of countering with something worse for me.
        if o is not None and offer_val >= current_planning_val:
            return None
            
        self.turn_index += 2
        return my_offer_counts