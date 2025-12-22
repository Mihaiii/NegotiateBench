# -*- coding: utf-8 -*-
"""
Improved bargaining agent for the haggling competition.

The agent:
* knows its own valuations, the counts of each item type and that the opponent’s
  total value equals our total value;
* accepts offers that are "good enough" according to a dynamic threshold;
* otherwise proposes a share that respects a linearly shrinking per‑type ratio
  and guarantees that the opponent can still possibly reach the required total
  value.
"""

from typing import List, Optional


class Agent:
    """
    Parameters
    ----------
    me : int
        0 if we move first, 1 otherwise (unused – the strategy is symmetric).
    counts : list[int]
        Number of objects of each type.
    values : list[int]
        Our value for a single object of each type.
    max_rounds : int
        Maximum number of *rounds* (a round = two turns, one per player).
    """

    def __init__(self, me: int, counts: List[int],
                 values: List[int], max_rounds: int) -> None:
        self.me = me
        self.counts = counts[:]          # immutable copy
        self.values = values[:]
        self.max_rounds = max_rounds
        # each round yields two turns → total turns we may act
        self.remaining_turns = max_rounds * 2
        # total value of the whole set (equals opponent's total value)
        self.total = sum(c * v for c, v in zip(self.counts, self.values))

    # -----------------------------------------------------------------
    # Helper utilities
    # -----------------------------------------------------------------
    def _value_of(self, share: List[int]) -> int:
        """Value of a share for us."""
        return sum(v * q for v, q in zip(self.values, share))

    def _max_fraction(self, share: List[int]) -> float:
        """
        Largest fraction of any item type we keep.
        Used for the guarantee calculation.
        """
        return max(
            (share[i] / self.counts[i]) if self.counts[i] else 0.0
            for i in range(len(self.counts))
        )

    def _opponent_guarantee(self, share: List[int]) -> float:
        """
        Minimal value the opponent can be forced to receive,
        given our share, using the formula from the problem statement.
        """
        max_frac = self._max_fraction(share)
        return self.total * (1.0 - max_frac)

    # -----------------------------------------------------------------
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        """
        Called on each of our turns.

        Parameters
        ----------
        o : list[int] | None
            The opponent's last proposal (what we would receive).  ``None`` on the
            very first turn.

        Returns
        -------
        list[int] | None
            * ``None`` – we accept the opponent's proposal.
            * list[int] – our counter‑proposal (how many of each type we want).
        """
        # One turn is consumed.
        self.remaining_turns -= 1

        # --------------------------------------------------------------
        # 1)  Accept if the offer is good enough.
        # --------------------------------------------------------------
        if o is not None:
            my_val = self._value_of(o)

            # Dynamic acceptance threshold:
            #   early rounds → greedy (70 % of total)
            #   later rounds → relax to the safe 50 %
            # Linear interpolation between 0.7 and 0.5 over the whole timeline.
            progress = (self.max_rounds * 2 - self.remaining_turns) \
                / (self.max_rounds * 2)
            threshold = 0.5 + 0.2 * (1.0 - progress)   # 0.7 → 0.5
            if my_val >= self.total * threshold:
                return None

        # --------------------------------------------------------------
        # 2)  No acceptable offer – build a counter‑proposal.
        # --------------------------------------------------------------
        n = len(self.counts)

        # If this is our very last turn we concede everything.
        if self.remaining_turns == 0:
            return [0] * n

        # Maximum proportion we may keep for each type.
        # It shrinks linearly from ~1 down to 0.5 as we approach the deadline.
        ratio = (self.remaining_turns) / (self.max_rounds * 2 + 1)

        # Start with the raw ratio limits.
        limits = [int(ratio * c) for c in self.counts]

        # Ensure the limits still allow the opponent to reach the required total.
        # If the guarantee produced by the current limits exceeds the opponent's
        # total value, we have to relax the most restrictive type(s).
        while True:
            provisional_share = limits[:]
            guarantee = self._opponent_guarantee(provisional_share)
            if guarantee <= self.total:
                break
            # Find the type with the *largest* fraction (the one causing the
            # guarantee to be too high) and relax it by one unit.
            idx = max(
                range(n),
                key=lambda i: (limits[i] / self.counts[i]) if self.counts[i] else -1
            )
            if limits[idx] == 0:
                # Should never happen, but guard against infinite loops.
                break
            limits[idx] -= 1

        # Greedy fill: take as many items as allowed, preferring higher‑valued types.
        order = sorted(range(n), key=lambda i: self.values[i], reverse=True)
        share = [0] * n
        for i in order:
            share[i] = limits[i]

        return share