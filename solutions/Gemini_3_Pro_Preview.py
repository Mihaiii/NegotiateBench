import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        
        self.n_types = len(counts)
        self.my_max_val = sum(c * v for c, v in zip(counts, values))
        
        # Opponent Value Estimation
        # Initialize with 1.0 (neutral assumption). We will learn and normalize.
        self.opp_val_est = [1.0 for _ in range(self.n_types)]
        
        self.turn_count = 0

    def normalize_opp_est(self):
        # We assume opponent's total value is equal to ours (from problem statement).
        # We scale our estimates of their item values so the total matches this sum.
        est_total = sum(self.counts[i] * self.opp_val_est[i] for i in range(self.n_types))
        if est_total > 1e-6:
            factor = self.my_max_val / est_total
            self.opp_val_est = [w * factor for w in self.opp_val_est]

    def update_opp_est(self, opp_offer: list[int]):
        # The opponent offered me 'opp_offer'. They kept 'counts - opp_offer'.
        # Items they keep represent their preferences.
        kept = [self.counts[i] - opp_offer[i] for i in range(self.n_types)]
        
        for i in range(self.n_types):
            if kept[i] > 0:
                # Heuristic: Add weight proportional to how many they kept.
                # This increases the estimated value of items they are reluctant to give up.
                self.opp_val_est[i] += kept[i]
                
        self.normalize_opp_est()

    def offer(self, o: list[int] | None) -> list[int] | None:
        # Calculate global turn index: 0 to total_turns - 1
        global_turn = 2 * self.turn_count + self.me
        turns_left = self.total_turns - global_turn
        
        offer_val = 0
        if o is not None:
            offer_val = sum(o[i] * self.values[i] for i in range(self.n_types))
            self.update_opp_est(o)
            
        # --- 1. Acceptance Logic for Deadline ---
        # If this is the absolute last turn (I am Player 2 in the last round),
        # I must accept any valid offer (even low value) rather than getting 0.
        if turns_left == 1:
            if o is not None:
                return None
                
        # --- 2. Variable Target Calculation ---
        # Strategy: Start high, concede gradually, then drop to "fair" deal near deadline.
        # progress goes from 0.0 (start) to 1.0 (end)
        progress = global_turn / self.total_turns
        
        if progress < 0.2:
            # Exploration phase: Ask for near maximum
            target_pct = 1.0
        elif progress < 0.8:
            # Trading phase: Linear concession from 1.0 down to 0.7
            x = (progress - 0.2) / 0.6
            target_pct = 1.0 - 0.3 * x
        else:
            # Deadline phase: Linear concession from 0.7 down to 0.55
            x = (progress - 0.8) / 0.2
            target_pct = 0.7 - 0.15 * x
            
        # Deadline Override:
        # If I am making the final offer of the game (turns_left=2), ensure it's attractive enough 
        # to prevent the opponent (who speaks next) from rejecting and ending the game.
        if turns_left <= 2:
            target_pct = min(target_pct, 0.60)
            
        target_val = int(self.my_max_val * target_pct)
        
        # --- 3. Acceptance Check ---
        if o is not None:
            # Accept if offer meets our dynamic target
            if offer_val >= target_val:
                return None
            # Always accept if offer is extremely good (e.g., 95% of max possible)
            if offer_val >= 0.95 * self.my_max_val:
                return None
                
        # --- 4. Construct Efficient Counter-Offer ---
        # Loop through items and pick those that give ME the most value per unit of cost to OPPONENT.
        # Ratio = MyValue / OpponentEstimatedValue
        # This Greedy approach approximates the Efficient Frontier.
        
        items_to_pick = []
        for i in range(self.n_types):
            count = self.counts[i]
            val_me = self.values[i]
            val_opp = self.opp_val_est[i]
            
            # Efficiency metric: Value I gain / Value they lose
            # Add small epsilon to prevent division by zero
            eff = val_me / (val_opp + 1e-5)
            
            # Add tiny noise to handle ties and prevent deterministic loops
            eff *= random.uniform(0.999, 1.001)
            
            # Treat each unit of an item type individually
            for _ in range(count):
                items_to_pick.append({'idx': i, 'val': val_me, 'eff': eff})
                
        # Sort by efficiency descending (My best items first)
        items_to_pick.sort(key=lambda x: x['eff'], reverse=True)
        
        my_counter = [0] * self.n_types
        current_val = 0
        
        for item in items_to_pick:
            # Stop taking items once we hit our target value
            # This leaves the rest for the opponent, maximizing their satisfaction
            if current_val >= target_val:
                break
            my_counter[item['idx']] += 1
            current_val += item['val']
            
        self.turn_count += 1
        return my_counter