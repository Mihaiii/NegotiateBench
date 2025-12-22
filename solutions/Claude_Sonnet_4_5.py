class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.current_round = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.n_items = len(counts)
        
        # Track opponent's offers to infer their valuation
        self.opponent_offers = []
        
        # Precompute item efficiency (value per item)
        self.item_priority = []
        for i in range(self.n_items):
            if counts[i] > 0:
                self.item_priority.append((values[i], i))
        self.item_priority.sort(reverse=True)
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.current_round += 1
        
        # If we receive an offer, evaluate it
        if o is not None:
            self.opponent_offers.append(o)
            offer_value = sum(o[i] * self.values[i] for i in range(self.n_items))
            
            # Accept if the offer is good enough based on remaining rounds
            acceptance_threshold = self._get_acceptance_threshold()
            
            if offer_value >= acceptance_threshold:
                return None
        
        # Generate our counter-offer
        return self._generate_offer()
    
    def _get_acceptance_threshold(self):
        """Calculate minimum acceptable value based on time pressure"""
        rounds_left = self.max_rounds * 2 - self.current_round
        
        if rounds_left <= 1:
            # Last chance - accept anything better than nothing
            return self.total_value * 0.3
        elif rounds_left <= 2:
            # Very little time left - be more flexible
            return self.total_value * 0.45
        elif rounds_left <= 4:
            # Time pressure building
            return self.total_value * 0.55
        else:
            # Early rounds - aim high
            return self.total_value * 0.65
    
    def _generate_offer(self):
        """Generate a strategic offer based on game state"""
        rounds_left = self.max_rounds * 2 - self.current_round
        
        # Estimate opponent's valuation from their offers
        opponent_values = self._estimate_opponent_values()
        
        # Generate offer that maximizes our value while being acceptable
        if rounds_left <= 2:
            # Urgent - make a more balanced offer
            return self._generate_balanced_offer(opponent_values)
        else:
            # More time - be more aggressive but fair
            return self._generate_strategic_offer(opponent_values, rounds_left)
    
    def _estimate_opponent_values(self):
        """Estimate opponent's valuation based on their offers"""
        if not self.opponent_offers:
            # No data yet - assume they value items we don't value
            estimated = [0] * self.n_items
            for i in range(self.n_items):
                if self.values[i] == 0:
                    estimated[i] = self.total_value // sum(self.counts)
            return estimated
        
        # Analyze what they keep for themselves
        estimated = [0] * self.n_items
        for offer in self.opponent_offers:
            for i in range(self.n_items):
                they_keep = self.counts[i] - offer[i]
                if they_keep > 0:
                    estimated[i] += 1
        
        return estimated
    
    def _generate_strategic_offer(self, opponent_values, rounds_left):
        """Generate an offer that's strategic but increasingly fair"""
        offer = [0] * self.n_items
        
        # Calculate aggression factor (decreases over time)
        aggression = min(0.8, rounds_left / (self.max_rounds * 2))
        
        # Sort items by our value minus estimated opponent value
        item_scores = []
        for i in range(self.n_items):
            our_priority = self.values[i]
            their_priority = opponent_values[i]
            score = our_priority - their_priority * (1 - aggression)
            item_scores.append((score, i))
        
        item_scores.sort(reverse=True)
        
        # Allocate items based on mutual benefit
        for score, i in item_scores:
            if score > 0 or (score == 0 and self.values[i] > 0):
                # We want these items more
                offer[i] = self.counts[i]
            else:
                # Give to opponent
                offer[i] = 0
        
        # Ensure we're getting reasonable value
        offer_value = sum(offer[i] * self.values[i] for i in range(self.n_items))
        if offer_value < self.total_value * 0.5:
            # Fallback: take our most valuable items
            return self._generate_greedy_offer()
        
        return offer
    
    def _generate_balanced_offer(self, opponent_values):
        """Generate a more balanced offer for endgame"""
        offer = [0] * self.n_items
        
        # Try to find a split that gives us at least 50% while being fair
        for i in range(self.n_items):
            if self.values[i] > opponent_values[i]:
                offer[i] = self.counts[i]
            elif self.values[i] < opponent_values[i]:
                offer[i] = 0
            else:
                # Equal value - split or give based on count
                offer[i] = self.counts[i] // 2
        
        # Check if we get enough value
        offer_value = sum(offer[i] * self.values[i] for i in range(self.n_items))
        if offer_value < self.total_value * 0.4:
            # Not enough - be more aggressive
            for i in range(self.n_items):
                if self.values[i] > 0:
                    offer[i] = self.counts[i]
        
        return offer
    
    def _generate_greedy_offer(self):
        """Fallback: request all items we value"""
        offer = [0] * self.n_items
        for i in range(self.n_items):
            if self.values[i] > 0:
                offer[i] = self.counts[i]
        return offer