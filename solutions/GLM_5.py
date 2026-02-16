class Agent:
    def __init__(self, me, counts, values, max_rounds):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.round = 0
        self.total = sum(c * v for c, v in zip(counts, values))
        self.n = len(counts)
        self.received_offers = []

    def value(self, offer):
        return sum(o * v for o, v in zip(offer, self.values)) if offer else 0

    def infer_opponent_prefs(self):
        """Infer items opponent likely doesn't value from their offers."""
        if not self.received_offers:
            return set()
        # Items fully given to me are likely low-value to opponent
        low_val = set()
        for offer in self.received_offers:
            for i in range(self.n):
                if offer[i] == self.counts[i]:
                    low_val.add(i)
        return low_val

    def offer(self, o):
        self.round += 1
        remaining = self.max_rounds - self.round

        if o is not None:
            self.received_offers.append(o)
            my_val = self.value(o)

            # Player 1 on final turn: must accept anything
            if self.me == 1 and remaining == 0:
                return None

            # Accept good offers (40%+)
            if my_val >= self.total * 0.4:
                return None

            # Accept decent offers in late game (30%+ with few rounds left)
            if remaining <= 1 and my_val >= self.total * 0.3:
                return None

            # Accept if it's getting desperate
            if remaining == 0 and my_val > 0:
                return None

        # Make counter-offer
        # Player 0's last turn: make take-it-or-leave-it offer
        if self.me == 0 and remaining == 0:
            return [c if v > 0 else 0 for c, v in zip(self.counts, self.values)]

        return self.build_offer(o)

    def build_offer(self, o):
        """Construct a strategic counter-offer."""
        target = self.total * 0.55

        # If responding, counter with something better for me
        if o is not None:
            offered = self.value(o)
            target = max(target, offered + self.total * 0.12)

        opp_low_val = self.infer_opponent_prefs()

        offer = [0] * self.n
        current = 0

        # Sort: prioritize items opponent might not want, then by my value
        def priority(i):
            return (1 if i in opp_low_val else 0, self.values[i])

        indices = sorted(range(self.n), key=priority, reverse=True)

        for i in indices:
            if self.values[i] == 0:
                continue
            if current >= target:
                break

            need = target - current
            take = max(1, min(self.counts[i], int(need / self.values[i]) + 1))
            offer[i] = take
            current += take * self.values[i]

        return offer