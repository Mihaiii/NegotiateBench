class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total = sum(c * v for c, v in zip(counts, values))
        self.me = me
        self.turn = 0
        self.opponent_offers = []
        self.n_items = len(counts)
        self.total_turns = 2 * max_rounds
        # Sort items by value density for smarter concessions
        self.item_priority = sorted(range(self.n_items), 
                                   key=lambda i: self.values[i], reverse=True)
        self.opp_wants = [0.0] * self.n_items  # Track what opponent wants
        
    def _my_value(self, offer: list[int]) -> int:
        return sum(o * v for o, v in zip(offer, self.values))
    
    def _update_opponent_model(self, opp_offer: list[int]):
        """Track what opponent consistently wants (gives us less of)."""
        for i in range(self.n_items):
            opp_keeps = self.counts[i] - opp_offer[i]
            # Exponential moving average
            self.opp_wants[i] = 0.7 * self.opp_wants[i] + 0.3 * opp_keeps

    def _generate_offer(self, target_value: int) -> list[int]:
        """Generate offer achieving at least target_value, giving opponent what they want."""
        # Start with everything
        offer = self.counts.copy()
        current_value = self.total
        
        # Give away items we value least that opponent wants most
        concession_order = sorted(range(self.n_items),
                                 key=lambda i: (self.values[i] - self.opp_wants[i] * 0.5))
        
        for i in concession_order:
            if current_value <= target_value:
                break
            while offer[i] > 0 and current_value - self.values[i] >= target_value:
                offer[i] -= 1
                current_value -= self.values[i]
        
        return offer
    
    def _best_offer_for_value(self, min_value: int) -> list[int] | None:
        """Find offer meeting min_value that maximizes opponent's likely satisfaction."""
        best = None
        best_opp_score = -1
        
        def generate(idx, current, cur_val):
            nonlocal best, best_opp_score
            if idx == self.n_items:
                if cur_val >= min_value:
                    opp_score = sum((self.counts[j] - current[j]) * self.opp_wants[j] 
                                   for j in range(self.n_items))
                    if opp_score > best_opp_score:
                        best_opp_score = opp_score
                        best = current.copy()
                return
            for c in range(self.counts[idx] + 1):
                current.append(c)
                generate(idx + 1, current, cur_val + c * self.values[idx])
                current.pop()
        
        generate(0, [], 0)
        return best

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        turns_remaining = self.total_turns - self.turn
        progress = self.turn / self.total_turns
        
        if o is not None:
            self.opponent_offers.append(o)
            self._update_opponent_model(o)
            my_val = self._my_value(o)
            
            # Acceptance thresholds - more generous early to secure deals
            if turns_remaining == 0:
                return None if my_val > 0 else self._generate_offer(1)
            
            # Progressive threshold: start ~50%, drop to ~20%
            threshold = self.total * max(0.2, 0.5 - 0.35 * progress)
            
            if my_val >= threshold:
                return None
        
        # Counter-offer: start demanding ~80%, reduce to ~25%
        demand_ratio = max(0.25, 0.8 - 0.6 * progress)
        target = max(1, int(self.total * demand_ratio))
        
        # Use smart offer generation if we have opponent data
        if len(self.opponent_offers) >= 2:
            offer = self._best_offer_for_value(target)
            if offer:
                return offer
        
        return self._generate_offer(target)