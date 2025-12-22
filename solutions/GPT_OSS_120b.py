"""Simple concession negotiation agent.

The agent accepts any offer worth at least a decreasing threshold.
If the offer is not good enough it builds a counter‑offer that just
reaches the current threshold, taking the most valuable items first.
"""

from typing import List, Optional


class Agent:
    """Negotiation agent for the haggling game."""

    def __init__(
        self,
        me: int,
        counts: List[int],
        values: List[int],
        max_rounds: int,
    ) -> None:
        """
        Parameters
        ----------
        me: int
            0 if this agent moves first, 1 otherwise (not used here).
        counts: list[int]
            Number of objects of each type.
        values: list[int]
            Own valuation of a single object of each type.
        max_rounds: int
            Maximum number of *rounds* (a round = two turns).
        """
        self.me = me
        self.counts = counts[:]          # immutable copy of the pool
        self.values = values[:]
        self.max_rounds = max_rounds

        # total value of the whole pool for us
        self.total = sum(c * v for c, v in zip(self.counts, self.values))

        # start with 50 % of the total, then linearly decrease to 0
        self.threshold = self.total / 2.0
        # number of *turns* left (each round has two turns)
        self.turns_left = max_rounds * 2

        # decrement per rejected turn – guarantees reaching 0 before the last turn
        self.decrement = self.threshold / self.turns_left if self.turns_left else 0.0

        # order of indices, most valuable first (ties broken by index)
        self.order = sorted(
            range(len(self.counts)),
            key=lambda i: self.values[i],
            reverse=True,
        )

    # --------------------------------------------------------------
    # public API required by the competition framework
    # --------------------------------------------------------------
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        """
        Called whenever it is this agent's turn.

        Parameters
        ----------
        o: list[int] | None
            The opponent's last proposal interpreted from *our* point of view,
            i.e. how many objects of each type they would give us.
            ``None`` on the very first turn.

        Returns
        -------
        list[int] | None
            * ``None``  – accept the opponent's proposal.
            * list[int] – a counter‑offer (how many objects we want for ourselves).
        """
        # one turn has passed
        self.turns_left -= 1
        # lower the threshold for the *next* decision
        self.threshold = max(0.0, self.threshold - self.decrement)

        # ------------------------------------------------------------------
        # 1) try to accept the opponent's proposal
        # ------------------------------------------------------------------
        if o is not None:
            offered_value = sum(o[i] * self.values[i] for i in range(len(o)))
            if offered_value >= self.threshold:
                return None          # accept

        # ------------------------------------------------------------------
        # 2) otherwise build a counter‑offer that just meets the threshold
        # ------------------------------------------------------------------
        target = self.threshold
        # we cannot ask for more value than the whole pool possesses
        target = min(target, self.total)

        keep = [0] * len(self.counts)          # how many of each type we keep
        remaining = target

        for idx in self.order:
            if self.values[idx] == 0:
                continue                     # zero‑value items are never kept

            max_available = self.counts[idx]   # cannot keep more than exist
            # How many copies are needed to cover the remaining value?
            # integer division gives a floor; we may need one extra copy.
            need = int(remaining // self.values[idx])
            if need * self.values[idx] < remaining:
                need += 1

            take = min(need, max_available)
            keep[idx] = take
            remaining -= take * self.values[idx]

            if remaining <= 0:
                break

        # All remaining items (including zero‑value ones) are given to the opponent.
        return keep