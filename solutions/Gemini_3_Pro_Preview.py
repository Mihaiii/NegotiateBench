import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        self.turn = me
        
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.opp_demands = []

    def offer(self, o: list[int] | None) -> list[int] | None:
        turns_left = self.total_turns - 1 - self.turn
        
        # Calculate valuation of the incoming offer
        opp_val = 0
        if o is not None:
            opp_val = sum(self.values[i] * o[i] for i in range(len(self.counts)))
            # Record what they kept (Total - Offered)
            kept = [self.counts[i] - o[i] for i in range(len(self.counts))]
            self.opp_demands.append(kept)
        
        # --- 1. End-Game Survival Logic ---
        
        # If I am the last mover (turns_left == 0), any counter-offer results in No Deal (0).
        # Rational choice is to accept anything that isn't strict 0 (and even then, 0 vs 0 is equal).
        if turns_left == 0:
            if o is not None:
                return None

        # --- 2. Target Calculation ---
        
        # Calculate negotiation progress (0.0 to 1.0)
        progress = self.turn / max(1, self.total_turns - 1)
        
        # Adaptive Concession Curve:
        # Phase 1 (0-30%): Anchor High (100%). Signal strength to stubborn opponents.
        # Phase 2 (30-75%): Linear concession to 80%.
        # Phase 3 (75-95%): "Deal Zone" concession to 65%.
        # Phase 4 (>95%): Panic drop to 50% to salvage value.
        
        if progress < 0.3:
            target_pct = 1.0
        elif progress < 0.75:
            # 0.3 -> 0.75 (range 0.45) drops 1.0 -> 0.8
            target_pct = 1.0 - (0.2 * (progress - 0.3) / 0.45)
        elif progress < 0.95:
            # 0.75 -> 0.95 (range 0.2) drops 0.8 -> 0.65
            target_pct = 0.8 - (0.15 * (progress - 0.75) / 0.2)
        else:
            # 0.95 -> 1.0 drops 0.65 -> 0.5
            target_pct = 0.65 - (0.15 * (progress - 0.95) / 0.05)
            
        target_val = int(self.total_value * target_pct)

        # Safety Override: In the second-to-last turn, ensure we don't demand impossible values
        # that risk the opponent walking away or failing their own constraints.
        if turns_left <= 2:
            target_val = min(target_val, int(self.total_value * 0.65))
        
        # --- 3. Acceptance Logic ---
        if o is not None:
            # Accept if target is met
            if opp_val >= target_val:
                return None
            
            # Acceptance "Sanity Floor" to prevent greed-based failures in late game
            # If we are past 50% time, and offer is really good (>80%), take it.
            if progress > 0.5 and opp_val >= self.total_value * 0.8:
                return None
            # If we are near end (>90%), accept >65%
            if progress > 0.9 and opp_val >= self.total_value * 0.65:
                return None

        # --- 4. Proposal Generation ---
        
        # A. Opponent Modeling
        # Estimate what opponent wants based on frequency of kept items.
        opp_weights = [1.0] * len(self.counts)
        if self.opp_demands:
            n = len(self.opp_demands)
            for i, demand in enumerate(self.opp_demands):
                # Weight recent moves significantly higher (Cube weighting)
                # This helps adapt quickly if opponent changes strategy.
                w = 1.0 + (5.0 * (i / max(1, n))**2)
                for j in range(len(self.counts)):
                    if self.counts[j] > 0:
                        opp_weights[j] += (demand[j] / self.counts[j]) * w
        
        # B. Greedy Construction (Subtraction Method)
        # Start with "I want everything I value".
        # Iteratively remove items that are "least painful" to give up.
        # Pain Metric = My Value / Opponent Interest.
        # Low metric = Easy concession.
        
        current_proposal = [0] * len(self.counts)
        current_prop_val = 0
        
        # Breakdown items into individual units for granular removal
        bag_items = []
        for i in range(len(self.counts)):
            if self.values[i] > 0:
                current_proposal[i] = self.counts[i]
                current_prop_val += self.counts[i] * self.values[i]
                
                # Metric: High means "I want this more than you do" (Keep)
                # Low means "You want this more than I do" (Give)
                metric = (self.values[i] + 1e-5) / (opp_weights[i] + 1e-5)
                # Jitter to avoid predictable loops
                metric *= random.uniform(0.98, 1.02)
                
                for _ in range(self.counts[i]):
                    bag_items.append({'idx': i, 'val': self.values[i], 'metric': metric})
        
        # Sort by metric ascending (lowest first = remove first)
        bag_items.sort(key=lambda x: x['metric'])
        
        # Remove items while we can afford to (keeping value >= target)
        for item in bag_items:
            if current_prop_val - item['val'] >= target_val:
                current_proposal[item['idx']] -= 1
                current_prop_val -= item['val']
            else:
                # We can't remove this item without going below target.
                # Stop removing to prioritize target value over efficiency.
                pass
                
        # --- 5. Final Comparison ---
        # If the opponent's offer is mathematically superior or equal to my planned counter,
        # accepting is strictly dominant.
        if o is not None and opp_val >= current_prop_val:
            return None
        
        self.turn += 2
        return current_proposal