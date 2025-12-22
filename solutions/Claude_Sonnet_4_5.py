class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.current_turn = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.n_items = len(counts)
        self.opponent_offers = []
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.current_turn += 1
        
        if o is not None:
            self.opponent_offers.append(o)
            offer_value = sum(o[i] * self.values[i] for i in range(self.n_items))
            
            if self._should_accept(offer_value):
                return None
        
        return self._generate_offer()
    
    def _should_accept(self, offer_value: int) -> bool:
        """Accept based on value threshold and urgency"""
        turns_left = self.max_rounds * 2 - self.current_turn
        
        if turns_left <= 1:
            return offer_value > 0
        elif turns_left <= 3:
            threshold = self.total_value * 0.30
        elif turns_left <= 6:
            threshold = self.total_value * 0.40
        elif turns_left <= 10:
            threshold = self.total_value * 0.50
        else:
            threshold = self.total_value * 0.55
        
        return offer_value >= threshold
    
    def _generate_offer(self) -> list[int]:
        """Generate offer with adaptive strategy"""
        turns_left = self.max_rounds * 2 - self.current_turn
        
        # Analyze opponent preferences from their offers
        opponent_values = self._estimate_opponent_values()
        
        # Calculate progress ratio
        progress = self.current_turn / (self.max_rounds * 2)
        
        # Start aggressive, become cooperative
        if progress < 0.4:
            return self._make_aggressive_offer(opponent_values)
        elif progress < 0.7:
            return self._make_balanced_offer(opponent_values)
        else:
            return self._make_concession_offer(opponent_values)
    
    def _estimate_opponent_values(self) -> list[float]:
        """Estimate opponent's relative item values"""
        if not self.opponent_offers:
            # Assume complementary preferences initially
            max_val = max(self.values) if max(self.values) > 0 else 1
            return [1.0 - (self.values[i] / max_val) for i in range(self.n_items)]
        
        # Analyze what opponent consistently requests
        avg_request = [0.0] * self.n_items
        for offer in self.opponent_offers:
            for i in range(self.n_items):
                if self.counts[i] > 0:
                    avg_request[i] += offer[i] / self.counts[i]
        
        if len(self.opponent_offers) > 0:
            avg_request = [x / len(self.opponent_offers) for x in avg_request]
        
        # Normalize
        max_req = max(avg_request) if max(avg_request) > 0 else 1
        return [x / max_req for x in avg_request]
    
    def _make_aggressive_offer(self, opp_values: list[float]) -> list[int]:
        """Take most valuable items, give away less valuable ones"""
        offer = [0] * self.n_items
        
        for i in range(self.n_items):
            # Take items we value more than opponent likely does
            my_rel_val = self.values[i] / max(self.values) if max(self.values) > 0 else 0
            
            if my_rel_val > opp_values[i] + 0.1:
                offer[i] = self.counts[i]
            elif my_rel_val > opp_values[i] - 0.2:
                offer[i] = max(1, self.counts[i] // 2)
        
        # Ensure minimum value
        if sum(offer[i] * self.values[i] for i in range(self.n_items)) < self.total_value * 0.6:
            for i in sorted(range(self.n_items), key=lambda x: self.values[x], reverse=True):
                if offer[i] < self.counts[i]:
                    offer[i] = self.counts[i]
                    if sum(offer[j] * self.values[j] for j in range(self.n_items)) >= self.total_value * 0.6:
                        break
        
        return offer
    
    def _make_balanced_offer(self, opp_values: list[float]) -> list[int]:
        """Seek mutually beneficial split"""
        offer = [0] * self.n_items
        
        for i in range(self.n_items):
            my_rel_val = self.values[i] / max(self.values) if max(self.values) > 0 else 0
            
            if my_rel_val > opp_values[i] + 0.15:
                offer[i] = self.counts[i]
            elif my_rel_val < opp_values[i] - 0.15:
                offer[i] = 0
            else:
                # Split contested items
                offer[i] = self.counts[i] // 2
        
        # Ensure reasonable value
        current_value = sum(offer[i] * self.values[i] for i in range(self.n_items))
        if current_value < self.total_value * 0.45:
            for i in sorted(range(self.n_items), key=lambda x: self.values[x], reverse=True):
                if offer[i] < self.counts[i]:
                    offer[i] = self.counts[i]
                    current_value = sum(offer[j] * self.values[j] for j in range(self.n_items))
                    if current_value >= self.total_value * 0.5:
                        break
        
        return offer
    
    def _make_concession_offer(self, opp_values: list[float]) -> list[int]:
        """Make significant concessions to reach agreement"""
        offer = [0] * self.n_items
        
        for i in range(self.n_items):
            my_rel_val = self.values[i] / max(self.values) if max(self.values) > 0 else 0
            
            # Only take items we clearly value more
            if my_rel_val > opp_values[i] + 0.25:
                offer[i] = self.counts[i]
            elif my_rel_val > opp_values[i]:
                offer[i] = max(self.counts[i] // 2, 1) if self.counts[i] > 0 else 0
        
        # Accept lower threshold late in negotiation
        current_value = sum(offer[i] * self.values[i] for i in range(self.n_items))
        target = self.total_value * 0.35
        
        if current_value < target:
            for i in sorted(range(self.n_items), key=lambda x: self.values[x], reverse=True):
                if offer[i] < self.counts[i] and self.values[i] > 0:
                    offer[i] = min(offer[i] + 1, self.counts[i])
                    current_value = sum(offer[j] * self.values[j] for j in range(self.n_items))
                    if current_value >= target:
                        break
        
        return offer