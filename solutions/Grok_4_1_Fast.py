class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts.copy()
        self.values = values.copy()
        self.total = sum(c * v for c, v in zip(self.counts, self.values))
        self.max_rounds = max_rounds
        self.my_turns_made = 0
        self.last_proposal = None

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.my_turns_made += 1
        max_turns = max(1, self.max_rounds)
        progress = min(1.0, (self.my_turns_made - 1) / (max_turns - 1))

        if o is not None:
            incoming_val = sum(self.values[i] * o[i] for i in range(len(self.values)))
            accept_threshold = self.total * (0.7 - 0.5 * progress)
            if incoming_val >= accept_threshold or (progress >= 0.95 and incoming_val > 0):
                return None

        # Generate proposal
        if self.last_proposal is None or o is None:
            # Greedy initial proposal
            proposal = [self.counts[i] if self.values[i] > 0 else 0 for i in range(len(self.counts))]
        else:
            # Weighted average towards opponent's proposal
            bias = 0.8 * (1 - progress) + 0.4 * progress
            proposal = []
            for i in range(len(self.counts)):
                me_share = self.last_proposal[i]
                opp_offer_share = o[i]
                share = int(bias * me_share + (1 - bias) * opp_offer_share)
                share = max(0, min(self.counts[i], share))
                proposal.append(share)

        self.last_proposal = proposal[:]
        return proposal