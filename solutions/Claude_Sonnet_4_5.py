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
        
        # On last turn, accept anything positive
        if turns_left <= 1:
            return offer_value > 0
        
        # Dynamic threshold based on remaining turns
        if turns_left <= 2:
            threshold = self.total_value * 0.25
        elif turns_left <= 4:
            threshold = self.total_value * 0.35
        elif turns_left <= 6:
            threshold = self.total_value * 0.42
        elif turns_left <= 10:
            threshold = self.total_value * 0.48
        else:
            threshold = self.total_value * 0.52
        
        return offer_value >= threshold
    
    def _generate_offer(self) -> list[int]:
        """Generate offer with adaptive strategy"""
        turns_left = self.max_rounds * 2 - self.current_turn
        
        # Estimate opponent preferences
        opponent_values = self._estimate_opponent_values()
        
        # Progress ratio (0 to 1)
        progress = self.current_turn / (self.max_rounds * 2)
        
        # Strategy selection based on progress
        if progress < 0.35:
            return self._make_aggressive_offer(opponent_values)
        elif progress < 0.70:
            return self._make_balanced_offer(opponent_values)
        else:
            return self._make_concession_offer(opponent_values)
    
    def _estimate_opponent_values(self) -> list[float]:
        """Estimate opponent's relative item preferences"""
        if not self.opponent_offers:
            # Initial assumption: opponent values what we don't
            max_val = max(self.values) if max(self.values) > 0 else 1
            return [1.0 - (self.values[i] / max_val) for i in range(self.n_items)]
        
        # Analyze opponent's consistent requests
        total_requests = [0.0] * self.n_items
        for offer in self.opponent_offers:
            for i in range(self.n_items):
                total_requests[i] += offer[i]
        
        # Normalize by counts and number of offers
        normalized = []
        for i in range(self.n_items):
            if self.counts[i] > 0:
                normalized.append(total_requests[i] / (self.counts[i] * len(self.opponent_offers)))
            else:
                normalized.append(0.0)
        
        # Scale to 0-1 range
        max_norm = max(normalized) if max(normalized) > 0 else 1
        return [x / max_norm for x in normalized]
    
    def _make_aggressive_offer(self, opp_values: list[float]) -> list[int]:
        """Claim high-value items, concede low-value items"""
        offer = [0] * self.n_items
        
        # Normalize our values
        max_my_val = max(self.values) if max(self.values) > 0 else 1
        my_normalized = [v / max_my_val for v in self.values]
        
        for i in range(self.n_items):
            # Take items where we have stronger preference
            if my_normalized[i] > opp_values[i] + 0.2:
                offer[i] = self.counts[i]
            elif my_normalized[i] > opp_values[i]:
                offer[i] = max(int(self.counts[i] * 0.7), self.counts[i] - 1) if self.counts[i] > 0 else 0
            elif my_normalized[i] > 0.3:
                offer[i] = max(1, self.counts[i] // 2)
        
        # Ensure we get at least 55% of total value
        self._ensure_minimum_value(offer, 0.55)
        return offer
    
    def _make_balanced_offer(self, opp_values: list[float]) -> list[int]:
        """Seek mutually beneficial distribution"""
        offer = [0] * self.n_items
        
        max_my_val = max(self.values) if max(self.values) > 0 else 1
        my_normalized = [v / max_my_val for v in self.values]
        
        for i in range(self.n_items):
            diff = my_normalized[i] - opp_values[i]
            
            if diff > 0.25:
                offer[i] = self.counts[i]
            elif diff > 0.1:
                offer[i] = max(int(self.counts[i] * 0.65), 1) if self.counts[i] > 0 else 0
            elif diff > -0.1:
                offer[i] = self.counts[i] // 2
            elif diff > -0.25:
                offer[i] = max(int(self.counts[i] * 0.35), 0)
            else:
                offer[i] = 0
        
        # Ensure we get at least 45% of total value
        self._ensure_minimum_value(offer, 0.45)
        return offer
    
    def _make_concession_offer(self, opp_values: list[float]) -> list[int]:
        """Make significant concessions to avoid deadlock"""
        offer = [0] * self.n_items
        
        max_my_val = max(self.values) if max(self.values) > 0 else 1
        my_normalized = [v / max_my_val for v in self.values]
        
        for i in range(self.n_items):
            diff = my_normalized[i] - opp_values[i]
            
            # Only strongly claim items we clearly value more
            if diff > 0.3:
                offer[i] = self.counts[i]
            elif diff > 0.15:
                offer[i] = max(int(self.counts[i] * 0.6), 1) if self.counts[i] > 0 else 0
            elif diff > 0:
                offer[i] = max(int(self.counts[i] * 0.4), 0)
            else:
                offer[i] = 0
        
        # Lower threshold for late-game: accept 35% of total value
        self._ensure_minimum_value(offer, 0.35)
        return offer
    
    def _ensure_minimum_value(self, offer: list[int], min_ratio: float) -> None:
        """Adjust offer to meet minimum value threshold"""
        current_value = sum(offer[i] * self.values[i] for i in range(self.n_items))
        target_value = self.total_value * min_ratio
        
        if current_value < target_value:
            # Sort items by value in descending order
            sorted_indices = sorted(range(self.n_items), key=lambda x: self.values[x], reverse=True)
            
            for i in sorted_indices:
                if self.values[i] > 0 and offer[i] < self.counts[i]:
                    # Increase allocation for this item
                    offer[i] = self.counts[i]
                    current_value = sum(offer[j] * self.values[j] for j in range(self.n_items))
                    
                    if current_value >= target_value:
                        break