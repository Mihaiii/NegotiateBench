class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.n = len(counts)
        self.total_val = sum(c * v for c, v in zip(counts, values))
        
        # Opponent modeling
        self.opp_kept_sum = [0] * self.n
        self.opp_offers_seen = 0
        # Start with uniform estimate, will be normalized
        self.opp_est_values = [1.0] * self.n
        self.normalize_opp_est()
        
        self.turns_played = 0
        self.last_offer_sent = None

    def normalize_opp_est(self):
        # Normalize opponent estimates so their total value matches mine (Symmetry assumption)
        est_total = sum(c * v for c, v in zip(self.counts, self.opp_est_values))
        if est_total > 1e-9:
            factor = self.total_val / est_total
            self.opp_est_values = [v * factor for v in self.opp_est_values]

    def update_opp_model(self, o: list[int]):
        self.opp_offers_seen += 1
        # 'o' is what I get. Opponent kept 'counts - o'.
        kept = [c - x for c, x in zip(self.counts, o)]
        for i in range(self.n):
            self.opp_kept_sum[i] += kept[i]
            
        # Update weights: Estimate value proportional to frequency of keeping items
        # Use Bayesian-like smoothing
        raw = []
        for i in range(self.n):
            denom = (self.opp_offers_seen * self.counts[i]) + 2.0 if self.counts[i] > 0 else 1.0
            prob = (self.opp_kept_sum[i] + 1.0) / denom
            raw.append(prob)
        self.opp_est_values = raw
        self.normalize_opp_est()

    def get_pareto(self):
        # Generate Pareto frontier approximations using greedy Efficiency = MeVal / OppVal
        items = []
        for i in range(self.n):
            v_me = self.values[i]
            v_opp = self.opp_est_values[i]
            # Add epsilon to avoid division by zero
            eff = v_me / (v_opp + 1e-9)
            # Treat each unit individually
            for _ in range(self.counts[i]):
                items.append((eff, v_me, v_opp, i))
        
        # Sort by efficiency descending (Best for Me first)
        items.sort(key=lambda x: x[0], reverse=True)
        
        frontier = []
        # State: I have 0 items
        curr_counts = [0] * self.n
        curr_me = 0
        curr_opp = sum(c * v for c, v in zip(self.counts, self.opp_est_values))
        
        frontier.append({'me': curr_me, 'opp': curr_opp, 'counts': list(curr_counts)})
        
        # Add items one by one
        for item in items:
            idx = item[3]
            curr_counts[idx] += 1
            curr_me += item[1]
            curr_opp -= item[2]
            frontier.append({'me': curr_me, 'opp': curr_opp, 'counts': list(curr_counts)})
            
        return frontier

    def offer(self, o: list[int] | None) -> list[int] | None:
        if o is not None:
            self.update_opp_model(o)
            
        # Calculate game time state
        # Turn 0-indexed: Me=0 plays 0, 2...; Me=1 plays 1, 3...
        curr_turn = self.turns_played * 2 + (1 if self.me == 1 else 0)
        total_turns = self.max_rounds * 2
        turns_left = total_turns - curr_turn
        
        o_val = sum(x * v for x, v in zip(o, self.values)) if o else 0
        
        # --- 1. Immediate Acceptance Conditions ---
        if o is not None:
            # End of game panic for Player 2 (Turn Total-1)
            # Rejecting here yields 0 for everyone. Rational to accept any positive value.
            if turns_left == 1:
                if o_val > 0: return None
        
        # --- 2. Calculate Strategy Points ---
        pareto = self.get_pareto()
        
        # Filter float noise
        valid_pareto = [p for p in pareto if p['opp'] > -1e-5]
        if not valid_pareto: valid_pareto = pareto
        
        # Nash Bargaining Point (maximize product of gains)
        # Represents a "Fair" deal in a cooperative sense
        nash_point = max(valid_pareto, key=lambda x: x['me'] * max(0, x['opp']))
        nash_val = nash_point['me']
        
        # Calculate Aspiration Target
        progress = curr_turn / total_turns
        
        if progress < 0.2:
            target = self.total_val * 0.98 # Start high
        elif progress < 0.85:
            # Smooth decay towards Nash point
            ratio = (progress - 0.2) / 0.65
            target = (self.total_val * 0.98) * (1 - ratio) + nash_val * ratio
        else:
            # Late game: Decay from Nash to valid Reservation price
            # Reservation: 65% of Nash is usually safe enough to ensure opponent value > 0
            res_price = nash_val * 0.65
            ratio = (progress - 0.85) / 0.15
            target = nash_val * (1 - ratio) + res_price * ratio
            
        # --- 3. Evaluate Offer vs Target ---
        if o is not None:
            # a) Meets current target
            if o_val >= target: return None
            
            # b) Is statistically "Good" (Nash-like)
            if o_val >= nash_val * 0.97: return None
            
            # c) Late game safety valve (Turn Total-2 or Total-3)
            # If offer is decent (>55% of total), accept to avoid risk of collision
            if turns_left <= 4 and o_val >= self.total_val * 0.55:
                return None

        # --- 4. Formulate Counter-Offer ---
        self.turns_played += 1
        
        # Special Logic: Ultimatum by Player 1 (Turn Total-2)
        # I initiate the last exchange. Opponent can only Accept/Reject after this.
        if turns_left == 2:
            # Find deal maximizing My Val s.t. Opp Val is "reasonable" enough to accept.
            # Reasonable = 40% of Total (Assuming symmetry) or Nash Opponent Val
            candidates = [p for p in valid_pareto if p['opp'] >= self.total_val * 0.4]
            if not candidates: 
                candidates = [p for p in valid_pareto if p['opp'] > 0]
            
            if candidates:
                best_ult = max(candidates, key=lambda x: x['me'])
                
                # Check consistency: if current offer 'o' is better than my ultimatum, take 'o'
                if o is not None and o_val >= best_ult['me']:
                    return None
                
                self.last_offer_sent = best_ult['counts']
                return best_ult['counts']

        # Standard Logic: Find best bundle for Opponent that satisfies My Target
        candidates = [p for p in valid_pareto if p['me'] >= target]
        
        if not candidates:
            # Target too high? Fallback to maximum possible for me
            candidates = [valid_pareto[-1]]
            
        # Pick candidate maximizing Opponent Utility (Probability of acceptance)
        best_offer = max(candidates, key=lambda x: x['opp'])
        
        self.last_offer_sent = best_offer['counts']
        return best_offer['counts']