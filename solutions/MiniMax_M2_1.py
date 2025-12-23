class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.rounds_left = max_rounds
        self.total_value = sum(counts[i] * values[i] for i in range(len(counts)))
        self.sorted_indices = sorted(range(len(counts)), key=lambda i: -values[i])
        self.best_offer_value = 0
        self.best_offer = None
        self.offers_received = []
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.rounds_left -= 1
        
        # First turn: make strategic opening
        if o is None:
            return self._build_counter_offer(self.total_value * 0.52)
        
        # Track best offer received
        offered_value = sum(o[i] * self.values[i] for i in range(len(o)))
        if offered_value > self.best_offer_value:
            self.best_offer_value = offered_value
            self.best_offer = o
        self.offers_received.append(o)
        
        # Accept if offer meets minimum threshold
        min_acceptable = self._get_min_acceptable()
        if offered_value >= min_acceptable:
            return None
            
        # Last round: accept any positive offer
        if self.rounds_left == 0:
            return None
            
        # Calculate target value for counter-offer
        # Concede more as rounds progress, but stay above minimum
        progress = 1 - (self.rounds_left / self.max_rounds)
        target = self.total_value * (0.5 + 0.05 * (1 - progress))
        target = max(target, min_acceptable + 1)
        
        # Adapt based on partner's behavior
        if len(self.offers_received) >= 2:
            partner_concession = self._analyze_partner_concession()
            if partner_concession > 0:
                # Partner is conceding, match their pace
                target = min(target + partner_concession * self.total_value * 0.02, 
                           self.total_value * 0.48)
        
        return self._build_counter_offer(target)
    
    def _get_min_acceptable(self) -> float:
        """Calculate minimum acceptable value based on remaining time."""
        progress = 1 - (self.rounds_left / self.max_rounds)
        # Minimum starts at 50% and gradually decreases to 40% by end
        return self.total_value * (0.5 - 0.1 * progress)
    
    def _analyze_partner_concession(self) -> float:
        """Analyze how much partner has conceded from their opening."""
        if len(self.offers_received) < 2:
            return 0
            
        first_offer = self.offers_received[0]
        last_offer = self.offers_received[-1]
        
        first_value = sum(first_offer[i] * self.values[i] for i in range(len(first_offer)))
        last_value = sum(last_offer[i] * self.values[i] for i in range(len(last_offer)))
        
        if first_value > last_value:
            return (first_value - last_value) / self.total_value
        return 0
    
    def _build_counter_offer(self, target_value: float) -> list[int]:
        """Build counter-offer targeting specific value."""
        counter = [0] * len(self.counts)
        remaining = self.counts[:]
        current_value = 0
        
        # First pass: take highest-value items
        for i in self.sorted_indices:
            if remaining[i] > 0 and self.values[i] > 0:
                take = min(remaining[i], 1)
                counter[i] = take
                remaining[i] -= take
                current_value += take * self.values[i]
        
        # Second pass: strategically add items to reach target
        for i in self.sorted_indices:
            if remaining[i] > 0 and current_value < target_value:
                item_value = self.values[i]
                if item_value > 0:
                    needed = max(0, int((target_value - current_value + item_value - 1) / item_value))
                    take = min(remaining[i], needed)
                    if take > 0:
                        counter[i] = take
                        remaining[i] -= take
                        current_value += take * item_value
        
        # Add one more item to make deal attractive if we have room
        for i in self.sorted_indices:
            if remaining[i] > 0:
                counter[i] += 1
                break
        
        return counter