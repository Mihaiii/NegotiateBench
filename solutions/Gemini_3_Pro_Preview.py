import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        
        # Track Global Turn Index.
        # Player 0 moves on 0, 2, 4... Player 1 on 1, 3, 5...
        self.current_turn = me
        
        self.my_total = sum(c * v for c, v in zip(counts, values))
        
        # Opponent Model: Track 'Affinity' (Probability of keeping an item).
        # Sum of items they demanded (kept) across turns.
        self.opp_demanded_sum = [0] * len(counts)
        self.opp_moves = 0

    def offer(self, o: list[int] | None) -> list[int] | None:
        incoming_val = 0
        if o is not None:
            # o is what they offer ME. They kept (counts - o).
            demanded = [self.counts[i] - o[i] for i in range(len(self.counts))]
            for i in range(len(self.counts)):
                self.opp_demanded_sum[i] += demanded[i]
            self.opp_moves += 1
            incoming_val = sum(c * v for c, v in zip(o, self.values))

        turns_left = self.total_turns - 1 - self.current_turn
        
        # --- 1. END-GAME SURVIVAL (Agent 1 Specific) ---
        # If I am the last mover (Turn 63/64), I must accept anything > 0.
        if turns_left == 0:
            if o is not None and incoming_val > 0:
                return None

        # --- 2. DYNAMIC TARGET CALCULATION ---
        progress = self.current_turn / max(1, self.total_turns - 1)
        
        # Base Concession Curve
        if progress < 0.2:
            target_pct = 1.0
        elif progress < 0.8:
            # Drop from 1.0 to 0.75
            p = (progress - 0.2) / 0.6
            target_pct = 1.0 - (0.25 * p)
        else:
            # Drop from 0.75 to 0.65 (Do not crash to 0.5 yet)
            p = (progress - 0.8) / 0.2
            target_pct = 0.75 - (0.10 * p)

        # Strategic Overrides based on Turn Structure
        is_ultimatum = (turns_left == 1)
        is_defense = (turns_left == 2)
        
        if is_ultimatum:
            # I am Agent 0 making the final offer. Agent 1 MUST accept or get 0.
            # Demand almost everything, but leave a rational crumb.
            target_pct = 0.90
            
        if is_defense:
            # I am Agent 1. Next turn Agent 0 gives Ultimatum. I must close NOW.
            # Offer a deal they can't refuse (fair/favorable to them).
            target_pct = 0.58 

        my_target_val = int(self.my_total * target_pct)
        
        # --- 3. ACCEPTANCE LOGIC ---
        if o is not None:
            # Accept if offer meets target
            if incoming_val >= my_target_val:
                return None
            
            # Panic Button: If in defense turn, accept any fair split to avoid ultimatum trap
            if is_defense and incoming_val >= self.my_total * 0.55:
                return None
            
        # --- 4. SMART PROPOSAL GENERATION ---
        # Heuristic: Dual Knapsack.
        # Maximize Opponent Utility subject to MyVal >= Target.
        # Metric: Efficiency = MyVal / OpponentAffinity.
        
        opp_weights = []
        for i in range(len(self.counts)):
            if self.opp_moves > 0:
                # Average count kept per turn normalized by total count available
                affinity = (self.opp_demanded_sum[i] / self.opp_moves) / max(1, self.counts[i])
                w = affinity + 0.05  # Smoothing
            else:
                w = 0.5
            opp_weights.append(w)
            
        candidates = []
        for i in range(len(self.counts)):
            # High Ratio = High Value for Me, Low Interest for Them -> KEEP
            ratio = (self.values[i] + 0.001) / (opp_weights[i] + 0.001)
            # Add noise to prevent loops
            ratio *= random.uniform(0.98, 1.02)
            candidates.append({'idx': i, 'ratio': ratio})
            
        candidates.sort(key=lambda x: x['ratio'], reverse=True)
        
        my_demand = [0] * len(self.counts)
        current_sum = 0
        
        for item in candidates:
            idx = item['idx']
            for _ in range(self.counts[idx]):
                should_take = False
                
                if current_sum < my_target_val:
                    should_take = True
                # Optimization: If opponent really doesn't want it, take it anyway (Pareto gain)
                elif opp_weights[idx] < 0.1:
                    should_take = True
                
                if should_take:
                    my_demand[idx] += 1
                    current_sum += self.values[idx]
                else:
                    break
        
        # --- 5. RATIONALITY CHECK ---
        # If I constructed a deal that is worse for me than what they offered, just accept theirs.
        generated_val = sum(c * v for c, v in zip(my_demand, self.values))
        if o is not None and incoming_val >= generated_val:
            return None
            
        self.current_turn += 2
        return my_demand