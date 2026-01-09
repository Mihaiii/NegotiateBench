import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        
        self.turn_count = 0
        self.my_max_val = sum(c * v for c, v in zip(counts, values))
        self.n_types = len(counts)
        
        # Opponent Value Estimation
        # Initialize with 1.0 (neutral assumption).
        self.opp_val_est = [1.0] * self.n_types

    def offer(self, o: list[int] | None) -> list[int] | None:
        # Calculate global turn index: 0 to total_turns - 1
        global_turn = 2 * self.turn_count + self.me
        turns_left = self.total_turns - global_turn
        progress = global_turn / self.total_turns

        # --- 1. Update Opponent Model ---
        if o is not None:
            # Determine which items the opponent kept
            kept = [self.counts[i] - o[i] for i in range(self.n_types)]
            for i, k in enumerate(kept):
                if k > 0:
                    # Heuristic: Add weight proportional to retention
                    # If they keep it, they want it.
                    self.opp_val_est[i] += k
        
        # Normalize estimates: Assume their total value roughly equals ours
        est_total = sum(self.counts[i] * self.opp_val_est[i] for i in range(self.n_types))
        if est_total > 1e-6:
            norm_factor = self.my_max_val / est_total
            self.opp_val_est = [w * norm_factor for w in self.opp_val_est]

        # --- 2. Evaluate Incoming Offer ---
        if o is not None:
            offer_val = sum(o[i] * self.values[i] for i in range(self.n_types))
            
            # LAST TURN SAFETY (If I am P2 responding to the final offer)
            # If I reject here, game ends and we get 0. Rationally accept anything > 0.
            if turns_left == 1:
                if offer_val > 0:
                    return None
            
            # Acceptance Threshold Logic
            # Start strict (0.98), decay to around 0.60
            threshold_frac = 0.98 - (0.38 * (progress ** 2))
            threshold_frac = max(threshold_frac, 0.6)
            
            # Exceptional offer acceptance or threshold met
            if offer_val >= self.my_max_val * threshold_frac:
                return None
            if offer_val >= self.my_max_val * 0.95:
                # Always accept nearly perfect deals
                return None

        # --- 3. Construct Counter-Offer ---
        # Determine Target Value for Me
        # Start at 100%, decay linearly to 70%
        target_frac = 1.0 - (0.3 * progress)
        
        # End-game override:
        # If I am P1 making the last proposal (turns_left=2), I must be reasonable 
        # to prevent P2 from risking a crash, or trigger their acceptance logic.
        if turns_left <= 2:
            target_frac = 0.55
            
        target_val = int(target_frac * self.my_max_val)
        
        # Build bundle using Efficiency Ratio: MyValue / OpponentCost
        # We want to gain `target_val` using items that cost the opponent the least.
        # Ratio = MyValue / OppEst. Higher is better for us (high gain, low pain).
        
        items_ranking = []
        for i in range(self.n_types):
            my_v = self.values[i]
            opp_v = self.opp_val_est[i] + 1e-5 # Avoid division by zero
            
            ratio = my_v / opp_v
            # Add slight random noise to break ties non-deterministically
            ratio *= random.uniform(0.99, 1.01)
            
            for _ in range(self.counts[i]):
                items_ranking.append({
                    'id': i,
                    'val': my_v,
                    'ratio': ratio
                })
        
        # Sort by efficiency (Descending)
        items_ranking.sort(key=lambda x: x['ratio'], reverse=True)
        
        my_offer = [0] * self.n_types
        current_val = 0
        
        for item in items_ranking:
            # Stop if we reached our target value
            if current_val >= target_val:
                break
            
            # Add item to my stash
            my_offer[item['id']] += 1
            current_val += item['val']
            
        self.turn_count += 1
        return my_offer