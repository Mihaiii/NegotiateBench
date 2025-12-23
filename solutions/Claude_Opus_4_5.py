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
        
    def _my_value(self, offer: list[int]) -> int:
        return sum(o * v for o, v in zip(offer, self.values))
    
    def _opponent_gets(self, my_offer: list[int]) -> list[int]:
        return [c - o for c, o in zip(self.counts, my_offer)]
    
    def _generate_offers(self) -> list[list[int]]:
        """Generate all possible offers."""
        def generate(idx, current):
            if idx == self.n_items:
                yield current.copy()
                return
            for i in range(self.counts[idx] + 1):
                current.append(i)
                yield from generate(idx + 1, current)
                current.pop()
        return list(generate(0, []))
    
    def _best_offer_for_me(self) -> list[int]:
        """Get the offer that maximizes my value."""
        best = None
        best_val = -1
        for offer in self._generate_offers():
            val = self._my_value(offer)
            if val > best_val:
                best_val = val
                best = offer
        return best if best else self.counts.copy()
    
    def _find_offer_with_target(self, min_value: int) -> list[int] | None:
        """Find offer meeting my minimum that gives opponent most items."""
        best_offer = None
        best_opp_items = -1
        
        for offer in self._generate_offers():
            if self._my_value(offer) >= min_value:
                opp_gets = self._opponent_gets(offer)
                opp_items = sum(opp_gets)
                # Prefer giving opponent more items (likely more value for them)
                if opp_items > best_opp_items:
                    best_opp_items = opp_items
                    best_offer = offer
        return best_offer

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        if o is not None:
            self.opponent_offers.append(o)
        
        turns_remaining = self.total_turns - self.turn
        
        # Acceptance logic
        if o is not None:
            my_val = self._my_value(o)
            
            # Last turn - accept anything positive
            if turns_remaining == 0:
                return None if my_val > 0 else self._best_offer_for_me()
            
            # Calculate acceptance threshold - be stubborn early, flexible late
            # Use exponential curve to stay firm longer
            progress = (self.turn / self.total_turns) ** 2
            threshold = self.total * (0.75 - 0.45 * progress)
            
            # Accept if meets threshold
            if my_val >= threshold:
                return None
            
            # Near end, accept if reasonable
            if turns_remaining <= 2 and my_val >= self.total * 0.3:
                return None
        
        # Counter-offer logic
        # Stay aggressive early, concede gradually near deadline
        if turns_remaining <= 1:
            target = self.total * 0.3
        elif turns_remaining <= 3:
            target = self.total * 0.45
        else:
            progress = (self.turn / self.total_turns) ** 1.5
            target = self.total * (0.80 - 0.35 * progress)
        
        offer = self._find_offer_with_target(target)
        if offer is None:
            offer = self._find_offer_with_target(1)
        return offer if offer else self._best_offer_for_me()