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
        self.my_offers = []
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.current_turn += 1
        
        # Evaluate and possibly accept opponent's offer
        if o is not None:
            self.opponent_offers.append(o)
            offer_value = sum(o[i] * self.values[i] for i in range(self.n_items))
            
            if self._should_accept(offer_value):
                return None
        
        # Generate our counter-offer
        return self._generate_offer()
    
    def _should_accept(self, offer_value: int) -> bool:
        """Decide whether to accept based on value and time pressure"""
        turns_left = self.max_rounds * 2 - self.current_turn
        
        # Calculate acceptance threshold based on time pressure
        if turns_left <= 1:
            # Last turn - accept anything positive
            return offer_value > 0
        elif turns_left <= 2:
            # Very urgent - accept 40%+
            threshold = self.total_value * 0.40
        elif turns_left <= 4:
            # Getting urgent - accept 50%+
            threshold = self.total_value * 0.50
        elif turns_left <= 6:
            # Some pressure - accept 55%+
            threshold = self.total_value * 0.55
        else:
            # Early game - be selective, accept 60%+
            threshold = self.total_value * 0.60
        
        return offer_value >= threshold
    
    def _generate_offer(self) -> list[int]:
        """Generate strategic offer with gradual concessions"""
        turns_left = self.max_rounds * 2 - self.current_turn
        
        # Infer opponent's preferences from their offers
        opponent_item_priority = self._infer_opponent_values()
        
        # Early game: be aggressive
        if turns_left > 10:
            return self._make_greedy_offer()
        
        # Mid game: start identifying win-win opportunities
        elif turns_left > 4:
            return self._make_strategic_offer(opponent_item_priority, aggressive=True)
        
        # Late game: make real concessions
        else:
            return self._make_strategic_offer(opponent_item_priority, aggressive=False)
    
    def _infer_opponent_values(self) -> list[float]:
        """Estimate opponent's item priorities from their offers"""
        if not self.opponent_offers:
            # No data - assume they value what we don't
            return [1.0 if self.values[i] == 0 else 0.0 for i in range(self.n_items)]
        
        # Count how often opponent keeps each item type
        keep_counts = [0.0] * self.n_items
        for offer in self.opponent_offers:
            for i in range(self.n_items):
                they_keep = self.counts[i] - offer[i]
                if self.counts[i] > 0:
                    keep_counts[i] += they_keep / self.counts[i]
        
        # Normalize
        max_keep = max(keep_counts) if max(keep_counts) > 0 else 1
        return [k / max_keep for k in keep_counts]
    
    def _make_greedy_offer(self) -> list[int]:
        """Take everything we value, give away what we don't"""
        offer = [0] * self.n_items
        for i in range(self.n_items):
            if self.values[i] > 0:
                offer[i] = self.counts[i]
        return offer
    
    def _make_strategic_offer(self, opponent_priority: list[float], aggressive: bool) -> list[int]:
        """Make offer based on mutual benefit analysis"""
        offer = [0] * self.n_items
        
        # Calculate relative value for each item type
        item_scores = []
        for i in range(self.n_items):
            if self.counts[i] == 0:
                continue
            
            # Normalize our value
            our_value = self.values[i] / max(self.values) if max(self.values) > 0 else 0
            opp_value = opponent_priority[i]
            
            # Score: how much more do we value this than opponent?
            # Positive = we want it more, negative = they want it more
            score = our_value - opp_value
            item_scores.append((score, i))
        
        item_scores.sort(reverse=True)
        
        # Allocate items
        for score, i in item_scores:
            if aggressive:
                # Take items we value equally or more
                if score >= -0.2:
                    offer[i] = self.counts[i]
            else:
                # Only take items we clearly value more
                if score > 0.1:
                    offer[i] = self.counts[i]
                elif score > -0.3:
                    # Split contested items
                    offer[i] = self.counts[i] // 2
        
        # Ensure we're getting reasonable value
        offer_value = sum(offer[i] * self.values[i] for i in range(self.n_items))
        
        # If offer is too weak, boost it with our most valuable items
        if offer_value < self.total_value * 0.35:
            value_order = sorted(range(self.n_items), 
                               key=lambda i: self.values[i], 
                               reverse=True)
            for i in value_order:
                if offer_value >= self.total_value * 0.45:
                    break
                if offer[i] < self.counts[i]:
                    offer[i] = self.counts[i]
                    offer_value = sum(offer[j] * self.values[j] for j in range(self.n_items))
        
        return offer